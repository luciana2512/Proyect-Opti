"""
Algoritmo Genético para optimización de rutas y flujos en la Red Acuícola.

Contiene dos algoritmos:
  1. algoritmo_genetico      — TSP para ordenar entregas locales de un hub.
  2. algoritmo_genetico_flujos — AG sobre vector de flujos de la red completa.

Operadores implementados:
  - Selección por torneo (k=3)
  - Cruce PMX para permutaciones (TSP) / Blend crossover BLX-α (flujos)
  - Mutación por intercambio (TSP) / Mutación gaussiana clampada (flujos)
  - Elitismo configurable
"""
import random
import time
import numpy as np
from fitness import calcular_fitness, evaluar_poblacion


# ─── AG tipo TSP (distribución local desde un hub) ───────────────────────────

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
            'generacion':       gen,
            'mejor_fitness':    float(mejor_fit),
            'peor_fitness':     float(np.max(fitness_pob)),
            'promedio_fitness': float(np.mean(fitness_pob)),
            'mejor_ruta':       poblacion[mejor_idx].copy(),
            'ejemplos_torneo':  [],
            'ejemplos_cruce':   [],
            'ejemplos_mutacion': [],
        }

        if mejor_fit < mejor_fitness_global:
            mejor_fitness_global = mejor_fit
            mejor_global         = poblacion[mejor_idx].copy()

        if verbose and gen % 20 == 0:
            print(f"      Gen {gen:3d}: {mejor_fit:.2f} km")

        # Nueva generación
        nueva_pob = [poblacion[i].copy() for i in np.argsort(fitness_pob)[:elitismo]]
        contadores = {'torneo': 0, 'cruce': 0, 'mutacion': 0}

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

    # Evaluación final
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


# ─── AG tipo Flujos (red completa) ───────────────────────────────────────────

def _costo_transporte_cromosoma(cromosoma, aristas):
    """Costo de transporte puro del cromosoma (sin penalizaciones)."""
    return sum(
        cromosoma[i] * float(a['distancia_km']) * float(a['costo_por_ton_km'])
        for i, a in enumerate(aristas)
    )


def _calcular_fitness_flujo(cromosoma, aristas, nodos_dict, penalizacion,
                             umbral_calidad=0.70):
    """
    Función de fitness para un cromosoma de flujos.

    fitness = costo_transporte + pen_demanda + pen_oferta + pen_calidad

    Componentes de penalización (todas × penalizacion, un valor alto ej. 100_000):

    pen_demanda:
        Por cada ton que un supermercado recibe de más o de menos respecto a su
        demanda exacta. Se penaliza el valor absoluto del desvío porque tanto el
        exceso (merma, devoluciones) como el déficit (cliente insatisfecho, multa
        contractual) son costos reales.

    pen_oferta:
        Por cada ton que un origen despacha por encima de su capacidad productiva.
        Despacharlo sería físicamente imposible, por lo que el cromosoma que lo
        propone es inviable y debe quedar muy abajo en el ranking.

    pen_calidad:
        Si un nodo de tránsito tiene calidad por debajo del umbral, el flujo que
        pasa por él tiene alta probabilidad de rechazo en el supermercado destino.
        Penalizamos proporcionalmente al déficit de calidad × flujo afectado.
        Esto modela el riesgo económico: un lote rechazado genera devoluciones,
        costos de transporte doble y pérdida del precio de venta pactado.

    Returns:
        float — costo total penalizado (menor es mejor).
    """
    costo = _costo_transporte_cromosoma(cromosoma, aristas)

    entrada = {}
    salida  = {}
    for i, a in enumerate(aristas):
        salida[a['origen']]   = salida.get(a['origen'],   0.0) + cromosoma[i]
        entrada[a['destino']] = entrada.get(a['destino'], 0.0) + cromosoma[i]

    # ── Penalización de demanda incumplida ────────────────────────────────────
    # Se usa |recibido − demanda| porque el LP exige satisfacción EXACTA.
    # Cualquier desvío implica incumplimiento contractual con el supermercado.
    pen_demanda = 0.0
    for nid, nodo in nodos_dict.items():
        if nodo.get('tipo') == 'destino':
            dem = float(nodo.get('demanda', 0))
            pen_demanda += penalizacion * abs(entrada.get(nid, 0.0) - dem)

    # ── Penalización de oferta excedida ───────────────────────────────────────
    # No se puede despachar más de lo que existe en el estanque/granja.
    # El exceso es físicamente inviable → penalización severa para eliminar
    # estos cromosomas del pool evolutivo.
    pen_oferta = 0.0
    for nid, nodo in nodos_dict.items():
        if nodo.get('tipo') == 'origen':
            oferta = float(nodo.get('oferta', 0))
            exceso = max(0.0, salida.get(nid, 0.0) - oferta)
            pen_oferta += penalizacion * exceso

    # ── Penalización de calidad en centros de acopio ─────────────────────────
    # Si calidad_t < umbral, la carne procesada en ese nodo tiene riesgo de
    # rechazo en los supermercados. Penalizamos en proporción al:
    #   (déficit_de_calidad / umbral) × flujo_afectado × 0.5 × penalizacion
    # El factor 0.5 refleja que no todo lote con calidad baja es rechazado,
    # sino que aumenta la probabilidad de rechazo proporcionalmente al déficit.
    pen_calidad = 0.0
    for i, a in enumerate(aristas):
        nodo_orig = nodos_dict.get(a['origen'], {})
        if nodo_orig.get('tipo') == 'transito':
            calidad = float(nodo_orig.get('calidad', 1.0))
            if calidad < umbral_calidad:
                deficit   = (umbral_calidad - calidad) / umbral_calidad
                pen_calidad += penalizacion * 0.5 * deficit * cromosoma[i]

    return costo + pen_demanda + pen_oferta + pen_calidad


def algoritmo_genetico_flujos(
    red,
    tamano_poblacion=80,
    generaciones=150,
    tasa_cruce=0.8,
    tasa_mutacion=0.15,
    elitismo=2,
    penalizacion=100_000.0,
    sigma_mutacion=0.15,
    umbral_calidad=0.70,
    seed=None,
    verbose=False,
):
    """
    AG para optimizar los flujos en la red completa.

    Cromosoma: vector real [x_1, …, x_m], una variable por arista del grafo.
    Cada gen x_i ∈ [0, cap_i] representa las toneladas enviadas por esa arista.

    Operadores:
      - Selección: torneo de tamaño 3.
      - Cruce: BLX-α (Blend Crossover con α aleatorio ∈ [0,1]) para diversidad.
        Un α aleatorio en cada cruce evita convergencia prematura al punto medio.
      - Mutación: perturbación gaussiana σ = sigma_mutacion × capacidad, clampada
        en [0, cap] para garantizar factibilidad de capacidad por construcción.
      - Elitismo: los `elitismo` mejores individuos pasan intactos.

    Función de fitness: ver _calcular_fitness_flujo() — incluye penalizaciones
    por demanda incumplida, oferta excedida y calidad baja en tránsito.

    Args:
        red:              dict con 'nodos' y 'aristas'.
        tamano_poblacion: individuos por generación.
        generaciones:     iteraciones evolutivas.
        tasa_cruce:       probabilidad de cruce BLX-α por pareja.
        tasa_mutacion:    probabilidad de mutación por gen.
        elitismo:         individuos élite conservados sin cambio.
        penalizacion:     factor de penalización por violación de restricciones.
        sigma_mutacion:   desviación gaussiana como fracción de la capacidad.
        umbral_calidad:   calidad mínima aceptable para nodos de tránsito.
        seed:             semilla para reproducibilidad de resultados.
        verbose:          imprime progreso cada 20 generaciones.

    Returns:
        dict con mejor_cromosoma, costo_transporte, historial_fitness,
        historial_costo, tiempo_ms.
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    t_inicio = time.perf_counter()

    aristas    = red['aristas']
    nodos_dict = {n['id']: n for n in red['nodos']}
    caps       = [float(a['capacidad_ton']) for a in aristas]

    # Población inicial: cada gen uniforme ∈ [0, cap_e]
    poblacion = [
        [random.uniform(0.0, cap) for cap in caps]
        for _ in range(tamano_poblacion)
    ]

    mejor_global       = None
    mejor_fit_global   = float('inf')
    mejor_costo_global = float('inf')
    historial_fitness  = []
    historial_costo    = []

    for gen in range(generaciones):
        fitnesses = [
            _calcular_fitness_flujo(ind, aristas, nodos_dict, penalizacion, umbral_calidad)
            for ind in poblacion
        ]

        mejor_idx   = int(np.argmin(fitnesses))
        mejor_fit   = fitnesses[mejor_idx]
        mejor_costo = _costo_transporte_cromosoma(poblacion[mejor_idx], aristas)

        historial_fitness.append(float(mejor_fit))
        historial_costo.append(round(mejor_costo, 2))

        if mejor_fit < mejor_fit_global:
            mejor_fit_global   = mejor_fit
            mejor_costo_global = mejor_costo
            mejor_global       = poblacion[mejor_idx].copy()

        if verbose and gen % 20 == 0:
            print(f"      Gen {gen:3d}: fitness={mejor_fit:.1f}  costo={mejor_costo:.2f}")

        # Elitismo
        elite_idx = list(np.argsort(fitnesses)[:elitismo])
        nueva_pob = [poblacion[i].copy() for i in elite_idx]

        def _torneo():
            cands = random.sample(range(len(poblacion)), min(3, len(poblacion)))
            return poblacion[min(cands, key=lambda i: fitnesses[i])].copy()

        while len(nueva_pob) < tamano_poblacion:
            p1, p2 = _torneo(), _torneo()

            if random.random() < tasa_cruce:
                # BLX-α con α aleatorio: evita convergencia prematura al punto
                # medio que ocurría con alpha fijo = 0.5
                alpha = random.random()
                h1 = [alpha * a + (1.0 - alpha) * b for a, b in zip(p1, p2)]
                h2 = [(1.0 - alpha) * a + alpha * b for a, b in zip(p1, p2)]
            else:
                h1, h2 = p1[:], p2[:]

            def _mutar(ind):
                for i, cap in enumerate(caps):
                    if random.random() < tasa_mutacion:
                        sigma = sigma_mutacion * cap if cap > 0 else 0.1
                        ind[i] = max(0.0, min(cap, ind[i] + random.gauss(0, sigma)))
                return ind

            nueva_pob.append(_mutar(h1))
            if len(nueva_pob) < tamano_poblacion:
                nueva_pob.append(_mutar(h2))

        poblacion = nueva_pob

    # Evaluación final
    fitnesses = [
        _calcular_fitness_flujo(ind, aristas, nodos_dict, penalizacion, umbral_calidad)
        for ind in poblacion
    ]
    mejor_idx = int(np.argmin(fitnesses))
    if fitnesses[mejor_idx] < mejor_fit_global:
        mejor_global       = poblacion[mejor_idx].copy()
        mejor_fit_global   = fitnesses[mejor_idx]
        mejor_costo_global = _costo_transporte_cromosoma(mejor_global, aristas)

    tiempo_ms = round((time.perf_counter() - t_inicio) * 1000, 2)

    if verbose:
        print(f"      ✅ AG Flujos — Costo: {mejor_costo_global:.2f} KCOP en {tiempo_ms} ms")

    return {
        'mejor_cromosoma':   mejor_global,
        'costo_transporte':  round(mejor_costo_global, 2),
        'historial_fitness': historial_fitness,
        'historial_costo':   historial_costo,
        'tiempo_ms':         tiempo_ms,
    }
