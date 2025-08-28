from typing import Dict, List, TypedDict, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage
import sys
import os
import re
import math

# Estado compartilhado entre os agentes
class RestaurantAnalysisState(TypedDict):
    query: str
    restaurant_name: str
    reviews: List[str]
    food_scores: List[int]
    service_scores: List[int]
    final_score: float
    response: str
    messages: Annotated[list, add_messages]

def fetch_restaurant_data(restaurant_name: str) -> Dict[str, List[str]]:
    """
    Recupera avaliações de um restaurante específico do arquivo restaurantes.txt
    """
    reviews = []
    try:
        with open('restaurantes.txt', 'r', encoding='utf-8') as file:
            for line in file:
                line = line.strip()
                if line.startswith(f"{restaurant_name}."):
                    # Remove o nome do restaurante e o ponto inicial
                    review = line[len(restaurant_name) + 2:].strip()
                    reviews.append(review)
    except FileNotFoundError:
        print(f"Arquivo restaurantes.txt não encontrado")
        return {restaurant_name: []}
    
    return {restaurant_name: reviews}

def calculate_overall_score(restaurant_name: str, food_scores: List[int], customer_service_scores: List[int]) -> Dict[str, float]:
    """
    Calcula a pontuação geral do restaurante usando a fórmula especificada
    """
    if not food_scores or not customer_service_scores:
        return {restaurant_name: 0.000}
    
    n = len(food_scores)
    total_score = 0
    
    for i in range(n):
        # Fórmula: sqrt(food_scores[i]^2 * customer_service_scores[i])
        inner_calc = math.sqrt(food_scores[i]**2 * customer_service_scores[i])
        total_score += inner_calc
    
    # Aplicar a normalização: * 1/(N * sqrt(125)) * 10
    final_score = total_score * (1 / (n * math.sqrt(125))) * 10
    
    return {restaurant_name: round(final_score, 3)}

class RestaurantAnalysisSystem:
    def __init__(self):
        # Mapeamento de adjetivos para scores
        self.adjective_scores = {
            # Score 1/5
            'horrível': 1, 'nojento': 1, 'terrível': 1,
            # Score 2/5  
            'ruim': 2, 'desagradável': 2, 'ofensivo': 2,
            # Score 3/5
            'mediano': 3, 'sem graça': 3, 'irrelevante': 3, 'mediana': 3,
            # Score 4/5
            'bom': 4, 'bons': 4, 'agradável': 4, 'satisfatório': 4, 'boa': 4, 'eficiente': 4,
            # Score 5/5
            'incrível': 5, 'impressionante': 5, 'surpreendente': 5, 'incríveis': 5
        }
    
    def extract_restaurant_name(self, state: RestaurantAnalysisState) -> RestaurantAnalysisState:
        """Agente para extrair o nome do restaurante da consulta"""
        query = state["query"]
        
        # Lista de restaurantes conhecidos do arquivo
        known_restaurants = [
            "Bob's", "Casa do Pão de Queijo", "Pastelaria do Chinês", "Frango Assado",
            "Madero", "Ráscal", "Paris 6", "KFC", "Café do Ponto", "Dona Nuvem",
            "Santo Pão", "Havanna Café", "Mexicaníssimo", "Madeiro", "Bullguer",
            "China in Box", "Le Pain Quotidien", "Mr Cheney", "Brasileirinho", "Giraffas"
        ]
        
        restaurant_name = ""
        for restaurant in known_restaurants:
            if restaurant.lower() in query.lower():
                restaurant_name = restaurant
                break
        
        state["restaurant_name"] = restaurant_name
        state["messages"].append(AIMessage(content=f"Restaurante identificado: {restaurant_name}"))
        return state
    
    def fetch_reviews(self, state: RestaurantAnalysisState) -> RestaurantAnalysisState:
        """Agente para buscar avaliações do restaurante"""
        restaurant_name = state["restaurant_name"]
        
        if not restaurant_name:
            state["reviews"] = []
            state["messages"].append(AIMessage(content="Restaurante não encontrado"))
            return state
        
        restaurant_data = fetch_restaurant_data(restaurant_name)
        reviews = restaurant_data.get(restaurant_name, [])
        
        state["reviews"] = reviews
        state["messages"].append(AIMessage(content=f"Encontradas {len(reviews)} avaliações para {restaurant_name}"))
        return state
    
    def analyze_reviews(self, state: RestaurantAnalysisState) -> RestaurantAnalysisState:
        """Agente para analisar avaliações e extrair scores"""
        reviews = state["reviews"]
        
        if not reviews:
            state["food_scores"] = []
            state["service_scores"] = []
            return state
        
        food_scores = []
        service_scores = []
        
        for review in reviews:
            # Dividir a avaliação em partes sobre comida e atendimento
            review_lower = review.lower()
            
            # Extrair scores baseados nos adjetivos encontrados
            food_score = 3  # Score padrão
            service_score = 3  # Score padrão
            
            # Lógica específica para identificar scores de atendimento
            if 'atendimento' in review_lower:
                atendimento_part = review_lower[review_lower.find('atendimento'):]
                for word, score in self.adjective_scores.items():
                    if word in atendimento_part:
                        service_score = score
                        break
            
            # Procurar por adjetivos relacionados à comida (que não estão na parte de atendimento)
            for word, score in self.adjective_scores.items():
                if word in review_lower:
                    word_pos = review_lower.find(word)
                    atendimento_pos = review_lower.find('atendimento')
                    
                    # Se a palavra não está na parte de atendimento, considerar como comida
                    if atendimento_pos == -1 or word_pos < atendimento_pos:
                        food_score = score
            
            food_scores.append(food_score)
            service_scores.append(service_score)
        
        state["food_scores"] = food_scores
        state["service_scores"] = service_scores
        state["messages"].append(AIMessage(content=f"Análise concluída: {len(food_scores)} scores extraídos"))
        return state
    
    def calculate_score(self, state: RestaurantAnalysisState) -> RestaurantAnalysisState:
        """Agente para calcular score final"""
        restaurant_name = state["restaurant_name"]
        food_scores = state["food_scores"]
        service_scores = state["service_scores"]
        
        if not food_scores or not service_scores:
            state["final_score"] = 0.000
            state["response"] = f"Não foi possível calcular a avaliação para {restaurant_name}"
            return state
        
        score_result = calculate_overall_score(restaurant_name, food_scores, service_scores)
        final_score = score_result[restaurant_name]
        
        state["final_score"] = final_score
        state["response"] = f"A avaliação média do {restaurant_name} é {final_score}."
        state["messages"].append(AIMessage(content=f"Score final calculado: {final_score}"))
        return state
    
    def build_graph(self):
        """Constrói o grafo de execução"""
        workflow = StateGraph(RestaurantAnalysisState)
        
        # Adicionar nós
        workflow.add_node("extract_name", self.extract_restaurant_name)
        workflow.add_node("fetch_reviews", self.fetch_reviews)
        workflow.add_node("analyze_reviews", self.analyze_reviews)
        workflow.add_node("calculate_score", self.calculate_score)
        
        # Definir fluxo
        workflow.add_edge(START, "extract_name")
        workflow.add_edge("extract_name", "fetch_reviews")
        workflow.add_edge("fetch_reviews", "analyze_reviews")
        workflow.add_edge("analyze_reviews", "calculate_score")
        workflow.add_edge("calculate_score", END)
        
        return workflow.compile()

def main(user_query: str):
    """Função principal que executa o sistema multiagente"""
    system = RestaurantAnalysisSystem()
    graph = system.build_graph()
    
    # Estado inicial
    initial_state = {
        "query": user_query,
        "restaurant_name": "",
        "reviews": [],
        "food_scores": [],
        "service_scores": [],
        "final_score": 0.0,
        "response": "",
        "messages": [HumanMessage(content=user_query)]
    }
    
    # Executar o grafo
    result = graph.invoke(initial_state)
    
    # Imprimir resultado
    print(result["response"])

if __name__ == "__main__":
    assert len(sys.argv) > 1, "Certifique-se de incluir uma consulta para algum restaurante ao executar a função main."
    main(sys.argv[1])