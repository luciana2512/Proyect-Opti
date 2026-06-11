"""
Algoritmo Genético (AG-TSP) para optimización de rutas de última milla.

Resuelve el problema del viajante (TSP) para ordenar el reparto de un camión
que parte desde un centro de acopio (hub de tránsito) y visita todos los
supermercados asignados a ese hub, regresando al depósito.

Operadores:
  - Selección por torneo (k=3)
  - Cruce PMX (Partially Mapped Crossover) para permutaciones lineales
  - Mutación por intercambio de dos paradas intermedias
  - Elitismo configurable

Uso típico (vía grafo_acuicola.optimizar_distribucion_local):
    resultado = optimizar_distribucion_local('T1', red)
"""
import random
import time
import numpy as np
from fitness import calcular_fitness, evaluar_poblacion


# ─── AG-TSP: distribución local desde un hub ────────────────────────────────

def crear_individuo(n_paradas, punto_inicio_idx=0, punto_fin_idx=None):
    """Crea una ruta aleatoria con inicio y fin fijos."""
    if punto_fin_idx is None:
        punto_fin_idx = n_paradas - 1
    intermedias = list(range(n_paradas))
    intermedias.remove(punto_inicio_idx)
    if punto_fin_idx in intermedias:
        intermedias.remove(punto_fin_idx)
    random.shuffle(intermedias)
    return [punto_inicio_idx] + intermedias + [punto_fin_idx]


def crear_poblacion(tamano_poblacion, n_paradas, punto_inicio_idx=0, punto_fin_idx=None):
    """Crea una población inicial de rutas aleatorias."""
    return [crear_individuo(n_paradas, punto_inicio_idx, punto_fin_idx)
            for _ in range(tamano_poblacion)]


def seleccion_torneo(poblacion, fitness_poblacion, k=3):
    """
    Selección por torneo: elige k individuos al azar y retorna el de menor fitness.
    La presión selectiva (k) equilibra exploración vs. explotación.
    """
    indices   = random.sample(range(len(poblacion)), k)
    mejor_idx = min(indices, key=lambda i: fitness_poblacion[i])
    return poblacion[mejor_idx].copy()


def cruce_pmx(padre1, padre2):
    """
    Cruce PMX (Partially Mapped Crossover) para permutaciones.
    Mantiene inicio y fin fijos; solo permuta paradas intermedias.
    PMX preserva la legalidad de la permutación (sin repeticiones).
    """
    inicio = padre1[0]
    fin    = padre1[-1]
    p1_int = padre1[1:-1]
    p2_int = padre2[1:-1]

    if len(p1_int) < 2:
        return padre1.copy(), padre2.copy()

    size_int = len(p1_int)
    pt1 = random.randint(0, size_int - 1)
    pt2 = random.randint(pt1 + 1, size_int)

    hijo1 = [None] * size_int
    hijo2 = [None] * size_int
    hijo1[pt1:pt2] = p2_int[pt1:pt2]
    hijo2[pt1:pt2] = p1_int[pt1:pt2]

    def llenar(hijo, padre_main, padre_sec):
        for i in range(size_int):
            if hijo[i] is None:
                cand = padre_main[i]
                while cand in hijo:
                    idx  = padre_sec.index(cand)
                    cand = padre_main[idx]
                hijo[i] = cand
        return hijo

    h1 = llenar(hijo1, p1_int, p2_int)
    h2 = llenar(hijo2, p2_int, p1_int)
    return [inicio] + h1 + [fin], [inicio] + h2 + [fin]


def mutacion_intercambio(individuo, tasa_mutacion=0.1):
    """
    Mutación por intercambio de dos paradas intermedias.
    Solo actúa sobre índices interiores para preservar inicio y fin.
    """
    if random.random() < tasa_mutacion and len(individuo) > 3:
        idx1 = random.randint(1, len(individuo) - 2)
        idx2 = random.randint(1, len(individuo) - 3)
        if idx2 >= idx1:
            idx2 += 1
        individuo[idx1], individuo[idx2] = individuo[idx2], individuo[idx1]
    return individuo


def algoritmo_genetico(
    matriz_distancias,
    punto_inicio_idx=0,
    punto_fin_idx=None,
    tamano_poblacion=100,
    generaciones=200,
    tasa_cruce=0.8,
    tasa_mutacion=0.15,
    elitismo=2,
    seed=None,
    verbose=True,
):
    """
    AG para optimizar el orden de entrega a supermercados desde un hub (TSP).

    Args:
        matriz_distancias: Matriz NxN con distancias (km) entre paradas.
        punto_inicio_idx:  Índice del depósito (hub de tránsito).
        punto_fin_idx:     Índice del punto final (None = depósito, ciclo).
        tamano_poblacion:  Individuos por generación.
        generaciones:      Número de iteraciones evolutivas.
        tasa_cruce:        Probabilidad de cruce PMX por pareja.
        tasa_mutacion:     Probabilidad de intercambio por individuo.
        elitismo:          Individuos élite copiados sin cambio.
        seed:              Semilla aleatoria para reproducibilidad.
        verbose:           Imprime progreso cada 20 generaciones.

    Returns:
        dict con mejor_ruta, mejor_fitness, historial_fitness, historial_detallado,
        tiempo_ms (tiempo de ejecución total en milisegundos).
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    t_inicio = time.perf_counter()

    n_paradas = matriz_distancias.shape[0]
    if punto_fin_idx is None:
        punto_fin_idx = n_paradas - 1

    poblacion = crear_poblacion(tamano_poblacion, n_paradas, punto_inicio_idx, punto_fin_idx)

    historial_fitness   = []
    historial_detallado = []
    mejor_global        = None
    mejor_fitness_global = float('inf')

    for gen in range(generaciones):
        fitness_pob = evaluar_poblacion(poblacion, matriz_distancias)

        mejor_idx = int(np.argmin(fitness_pob))
        mejor_fit = fitness_pob[mejor_idx]
        historial_fitness.append(mejor_fit)

        info_gen = {
            'generacion':        gen,
            'mejor_fitness':     float(mejor_fit),
            'peor_fitness':      float(np.max(fitness_pob)),
            'promedio_fitness':  float(np.mean(fitness_pob)),
            'mejor_ruta':        poblacion[mejor_idx].copy(),
            'ejemplos_torneo':   [],
            'ejemplos_cruce':    [],
            'ejemplos_mutacion': [],
        }

        if mejor_fit < mejor_fitness_global:
            mejor_fitness_global = mejor_fit
            mejor_global         = poblacion[mejor_idx].copy()

        if verbose and gen % 20 == 0:
            print(f"      Gen {gen:3d}: {mejor_fit:.2f} km")

        nueva_pob   = [poblacion[i].copy() for i in np.argsort(fitness_pob)[:elitismo]]
        contadores  = {'torneo': 0, 'cruce': 0, 'mutacion': 0}

        while len(nueva_pob) < tamano_poblacion:
            p1 = seleccion_torneo(poblacion, fitness_pob)
            p2 = seleccion_torneo(poblacion, fitness_pob)

            if contadores['torneo'] < 3:
                info_gen['ejemplos_torneo'].append({'padre1': p1[:7], 'padre2': p2[:7]})
                contadores['torneo'] += 1

            if random.random() < tasa_cruce:
                h1, h2 = cruce_pmx(p1, p2)
                if contadores['cruce'] < 3:
                    info_gen['ejemplos_cruce'].append({
                        'padre1': p1[:7], 'padre2': p2[:7],
                        'hijo1': h1[:7], 'hijo2': h2[:7],
                    })
                    contadores['cruce'] += 1
            else:
                h1, h2 = p1.copy(), p2.copy()

            h1_ant, h2_ant = h1.copy(), h2.copy()
            h1 = mutacion_intercambio(h1, tasa_mutacion)
            h2 = mutacion_intercambio(h2, tasa_mutacion)

            if contadores['mutacion'] < 3:
                for antes, despues in [(h1_ant, h1), (h2_ant, h2)]:
                    if antes != despues and contadores['mutacion'] < 3:
                        info_gen['ejemplos_mutacion'].append(
                            {'antes': antes[:7], 'despues': despues[:7]}
                        )
                        contadores['mutacion'] += 1

            nueva_pob.append(h1)
            if len(nueva_pob) < tamano_poblacion:
                nueva_pob.append(h2)

        poblacion = nueva_pob
        historial_detallado.append(info_gen)

    fitness_pob = evaluar_poblacion(poblacion, matriz_distancias)
    mejor_idx   = int(np.argmin(fitness_pob))
    if fitness_pob[mejor_idx] < mejor_fitness_global:
        mejor_global         = poblacion[mejor_idx].copy()
        mejor_fitness_global = fitness_pob[mejor_idx]

    tiempo_ms = round((time.perf_counter() - t_inicio) * 1000, 2)

    if verbose:
        print(f"      ✅ AG (TSP) — Mejor: {mejor_fitness_global:.2f} km en {tiempo_ms} ms")

    return {
        'mejor_ruta':          mejor_global,
        'mejor_fitness':       mejor_fitness_global,
        'historial_fitness':   historial_fitness,
        'historial_detallado': historial_detallado,
        'tiempo_ms':           tiempo_ms,
    }