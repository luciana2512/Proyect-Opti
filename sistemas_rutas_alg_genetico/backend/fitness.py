"""
Módulo de fitness para evaluar la calidad de rutas (TSP).
Fitness = distancia total recorrida; menor es mejor.
"""
import numpy as np


def calcular_fitness(ruta, matriz_distancias):
    """Distancia total de una ruta (suma de aristas consecutivas)."""
    if len(ruta) < 2:
        return 0.0
    return sum(
        matriz_distancias[ruta[i]][ruta[i + 1]]
        for i in range(len(ruta) - 1)
    )


def evaluar_poblacion(poblacion, matriz_distancias):
    """Fitness de toda una población."""
    return [calcular_fitness(ind, matriz_distancias) for ind in poblacion]