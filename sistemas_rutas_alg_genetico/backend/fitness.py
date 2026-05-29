"""
Módulo de fitness para evaluar la calidad de las rutas.
Fitness = distancia total recorrida (menor es mejor)
"""
import numpy as np


def calcular_fitness(ruta, matriz_distancias):
    """
    Calcula el fitness de una ruta basado en la distancia total.
    
    Args:
        ruta: Lista de índices representando el orden de paradas
        matriz_distancias: Matriz NxN con distancias entre puntos
    
    Returns:
        float: Distancia total de la ruta (menor = mejor fitness)
    """
    if len(ruta) < 2:
        return 0.0
    
    distancia_total = 0.0
    for i in range(len(ruta) - 1):
        origen = ruta[i]
        destino = ruta[i + 1]
        distancia_total += matriz_distancias[origen][destino]
    
    return distancia_total


def evaluar_poblacion(poblacion, matriz_distancias):
    """
    Evalúa el fitness de toda una población.
    
    Args:
        poblacion: Lista de rutas (cada ruta es una lista de índices)
        matriz_distancias: Matriz NxN con distancias entre puntos
    
    Returns:
        list: Lista de fitness para cada individuo de la población
    """
    return [calcular_fitness(individuo, matriz_distancias) for individuo in poblacion]


def calcular_fitness_con_penalizacion(ruta, matriz_distancias,
                                      capacidad_ton=50, demanda_nodos=None):
    """
    Calcula fitness con penalización por exceso de capacidad de carga (opcional).

    Útil para variantes del TSP con restricciones de capacidad de vehículo (CVRP).

    Args:
        ruta: Lista de índices representando el orden de paradas
        matriz_distancias: Matriz NxN con distancias en km
        capacidad_ton: Capacidad máxima del camión en toneladas
        demanda_nodos: Lista con la demanda (toneladas) de cada nodo de la ruta

    Returns:
        float: Fitness penalizado (distancia + penalización por exceso de carga)
    """
    distancia = calcular_fitness(ruta, matriz_distancias)

    if demanda_nodos is None:
        return distancia

    # Penalización por exceso de capacidad de carga
    demanda_total = sum(demanda_nodos[i] for i in ruta)
    if demanda_total > capacidad_ton:
        penalizacion = (demanda_total - capacidad_ton) * 1000  # Factor de penalización
        return distancia + penalizacion

    return distancia
