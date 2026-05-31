"""
ag_ruta_comparativa.py — Algoritmo Genético de Rutas para Comparativa con Dijkstra/LP.

Contexto:
    En la red logística Acuícola Real del Meta, este módulo implementa un AG que,
    dado un par (Origen, Destino) seleccionado por el usuario, busca el camino de
    menor costo pasando obligatoriamente por al menos un centro de acopio (tránsito).
    Su resultado se compara directamente con Dijkstra para evaluar qué tan cerca
    llega la heurística evolutiva al óptimo exacto.

Cromosoma:
    Una lista de nodos que representa un camino: [origen, T_i, ..., T_j, destino]
    Ejemplo: ['O1', 'T2', 'T1', 'D15']
    → Codificación directa (path encoding), longitud variable.

Operadores:
    - Selección:  Torneo de tamaño k=3.
    - Cruce:      Path Crossover por nodo común (nodo intermedio compartido).
    - Mutación:   Tres tipos — inserción de tránsito, sustitución de tránsito,
                  y re-enrutamiento completo.

Fitness (menor es mejor):
    fitness = costo_ruta + Σ penalizaciones

    Penalizaciones (PENALIZACION = 999_999):
      +PENALIZACION  si no empieza en el Origen correcto
      +PENALIZACION  si no termina en el Destino correcto
      +PENALIZACION  si no pasa por ningún tránsito intermedio
      +PENALIZACION  por cada arista inexistente en el grafo
      +PENALIZACION × 0.1 × exceso  si la demanda del destino supera la capacidad
"""

import random
import time
import json
import os

import networkx as nx
import numpy as np


# ─── Constante de penalización ────────────────────────────────────────────────

PENALIZACION = 999_999.0


# ─── Construcción del grafo ───────────────────────────────────────────────────

def _cargar_red_local():
    ruta = os.path.join(os.path.dirname(__file__), 'red_acuicola.json')
    with open(ruta, 'r', encoding='utf-8') as f:
        return json.load(f)


def _construir_grafo(red, aristas_bloqueadas=None):
    """
    Construye un DiGraph de NetworkX con atributos de costo, capacidad y distancia.
    Las aristas bloqueadas (escenario What-if) se excluyen del grafo.
    """
    if aristas_bloqueadas is None:
        aristas_bloqueadas = []
    G = nx.DiGraph()
    for n in red['nodos']:
        G.add_node(n['id'], **{k: v for k, v in n.items() if k != 'id'})
    for a in red['aristas']:
        if a['id'] in aristas_bloqueadas:
            continue
        costo = float(a['distancia_km']) * float(a['costo_por_ton_km'])
        G.add_edge(
            a['origen'], a['destino'],
            arista_id   = a['id'],
            costo       = costo,
            capacidad   = float(a['capacidad_ton']),
            distancia_km= float(a['distancia_km']),
            costo_ton_km= float(a['costo_por_ton_km']),
        )
    return G


# ─── Función de Fitness ───────────────────────────────────────────────────────

def _fitness_ruta(camino, G, origen, destino, nodos_dict):
    """
    Evalúa la aptitud de un cromosoma (camino).

    Retorna un escalar: costo_ruta + penalizaciones acumuladas.

    Cada penalización tiene un razonamiento económico/logístico:
      • No empezar/terminar en O/D → la ruta es físicamente inútil.
      • Saltarse tránsitos → viola la estructura jerárquica de la red.
      • Arista inexistente → el camión no puede circular por esa vía.
      • Exceso de capacidad → el camión no puede transportar más toneladas
        de las que admite; violar esto en la práctica implica pérdida de
        producto y sanciones regulatorias.
    """
    pen = 0.0

    # ── Restricción 1: inicio y fin correctos ────────────────────────────────
    # Un camino que no comienza en el origen o no termina en el destino
    # seleccionado es inútil para el problema planteado.
    if not camino or camino[0] != origen:
        pen += PENALIZACION
    if not camino or camino[-1] != destino:
        pen += PENALIZACION
    if len(camino) < 2:
        return pen + PENALIZACION

    # ── Restricción 2: obligatorio pasar por al menos un centro de acopio ────
    # La red es jerárquica: los orígenes no despachan directo a supermercados.
    # Un cromosoma que se salta los centros de acopio viola la estructura
    # del modelo de negocio y genera penalización masiva.
    nodos_intermedios = camino[1:-1]
    transitos_visitados = [
        n for n in nodos_intermedios
        if nodos_dict.get(n, {}).get('tipo') == 'transito'
    ]
    if not transitos_visitados:
        pen += PENALIZACION

    # ── Restricciones 3 y 4: aristas y capacidad ─────────────────────────────
    costo_ruta = 0.0
    demanda_destino = float(nodos_dict.get(destino, {}).get('demanda', 0))

    for i in range(len(camino) - 1):
        u, v = camino[i], camino[i + 1]
        if G.has_edge(u, v):
            edge = G[u][v]
            costo_ruta += edge['costo']
            # Penalización proporcional si la demanda del supermercado
            # excede la capacidad del camión en esa arista.
            # Refleja que no hay forma física de mover más carga de la permitida.
            exceso_cap = demanda_destino - edge['capacidad']
            if exceso_cap > 0:
                pen += PENALIZACION * 0.1 * exceso_cap
        else:
            # Arista fantasma: no existe en el grafo dirigido.
            # Penalización completa para eliminar este cromosoma del gen pool.
            pen += PENALIZACION

    return costo_ruta + pen


def _costo_puro(camino, G):
    """Costo real del camino (sin penalizaciones), para reportar en la comparativa."""
    total = 0.0
    for i in range(len(camino) - 1):
        u, v = camino[i], camino[i + 1]
        if G.has_edge(u, v):
            total += G[u][v]['costo']
    return total


# ─── Generación de individuos ─────────────────────────────────────────────────

def _generar_individuo(G, origen, destino, nodos_dict, caminos_base, max_intentos=30):
    """
    Genera un individuo (camino) válido desde origen hasta destino.

    Estrategia en cascada:
      1. Usar un camino pre-calculado de caminos_base (garantiza validez).
      2. Caminata aleatoria dirigida hacia el destino, priorizando tránsitos.
      3. Fallback: camino con tránsito aleatorio si la caminata falla.
    """
    # Estrategia 1: reusar un camino válido conocido
    if caminos_base:
        return random.choice(caminos_base)[:]

    # Estrategia 2: caminata aleatoria inteligente
    for _ in range(max_intentos):
        camino   = [origen]
        visitado = {origen}
        actual   = origen

        for _ in range(8):   # hasta 8 saltos para redes de este tamaño
            vecinos = [v for v in G.successors(actual) if v not in visitado]
            if not vecinos:
                break

            hay_transito = any(
                nodos_dict.get(n, {}).get('tipo') == 'transito' for n in camino[1:]
            )

            # Si el destino es alcanzable y ya pasamos por un tránsito, terminar
            if destino in vecinos and hay_transito:
                camino.append(destino)
                return camino

            # Preferir tránsitos mientras no hayamos visitado ninguno
            transitos = [v for v in vecinos if nodos_dict.get(v, {}).get('tipo') == 'transito']
            if not hay_transito and transitos:
                actual = random.choice(transitos)
            else:
                # Ponderar: preferir vecinos que acerquen al destino
                actual = random.choice(vecinos)

            camino.append(actual)
            visitado.add(actual)

            if actual == destino:
                return camino

        # Forzar cierre si llegamos lejos
        if camino[-1] != destino:
            camino.append(destino)
        if any(nodos_dict.get(n, {}).get('tipo') == 'transito' for n in camino[1:-1]):
            return camino

    # Estrategia 3: fallback con tránsito aleatorio
    transitos = [n for n in G.nodes() if nodos_dict.get(n, {}).get('tipo') == 'transito']
    if transitos:
        t = random.choice(transitos)
        return [origen, t, destino]
    return [origen, destino]


def _crear_poblacion(G, origen, destino, nodos_dict, tamano, caminos_base):
    """Crea la población inicial de individuos."""
    return [
        _generar_individuo(G, origen, destino, nodos_dict, caminos_base)
        for _ in range(tamano)
    ]


# ─── Operador de Selección ────────────────────────────────────────────────────

def _seleccion_torneo(poblacion, fitnesses, k=3):
    """
    Torneo de tamaño k: elige k individuos al azar y devuelve el de menor fitness.
    k=3 equilibra presión selectiva y diversidad en redes de tamaño medio.
    """
    candidatos = random.sample(range(len(poblacion)), min(k, len(poblacion)))
    return poblacion[min(candidatos, key=lambda i: fitnesses[i])][:]


# ─── Operador de Cruce (Path Crossover) ──────────────────────────────────────

def _cruce_rutas(padre1, padre2, origen, destino):
    """
    Cruce por nodo común (Path Crossover).

    Encuentra nodos INTERMEDIOS compartidos entre los dos caminos padres.
    En el punto de cruce, intercambia los sub-caminos para generar dos hijos.

    Ejemplo:
        padre1 = [O1, T2, T1, D5]
        padre2 = [O1, T1, T3, D5]
        Nodo común intermedio: T1
        hijo1  = [O1, T2] + [T1, T3, D5] = [O1, T2, T1, T3, D5]
        hijo2  = [O1] + [T1, D5]          = [O1, T1, D5]

    Si no hay nodo común, los hijos son copias de los padres.
    Se eliminan ciclos (nodos repetidos) para mantener la validez del camino.
    """
    intermedios1 = set(padre1[1:-1])
    intermedios2 = set(padre2[1:-1])
    comunes = list(intermedios1 & intermedios2)

    if not comunes:
        return padre1[:], padre2[:]

    punto_cruce = random.choice(comunes)
    idx1 = padre1.index(punto_cruce)
    idx2 = padre2.index(punto_cruce)

    hijo1 = padre1[:idx1] + padre2[idx2:]
    hijo2 = padre2[:idx2] + padre1[idx1:]

    def _eliminar_ciclos(camino):
        """Elimina nodos repetidos manteniendo el orden de aparición."""
        vistos, limpio = set(), []
        for n in camino:
            if n not in vistos:
                limpio.append(n)
                vistos.add(n)
        return limpio

    hijo1 = _eliminar_ciclos(hijo1)
    hijo2 = _eliminar_ciclos(hijo2)

    # Reparación: si el cruce rompió inicio o fin, usar los padres originales
    if not hijo1 or hijo1[0] != origen or hijo1[-1] != destino:
        hijo1 = padre1[:]
    if not hijo2 or hijo2[0] != origen or hijo2[-1] != destino:
        hijo2 = padre2[:]

    return hijo1, hijo2


# ─── Operador de Mutación ─────────────────────────────────────────────────────

def _mutar_ruta(camino, G, origen, destino, nodos_dict, tasa, caminos_base):
    """
    Mutación por re-enrutamiento con tres modalidades elegidas al azar:

    Tipo 1 — Inserción de tránsito:
        Busca un nodo de tránsito NO presente en el camino que sea alcanzable
        desde algún nodo anterior Y que alcance algún nodo posterior.
        Introduce diversidad al explorar centros de acopio alternativos.

    Tipo 2 — Sustitución de tránsito:
        Reemplaza un centro de acopio del camino por otro equivalente que
        mantenga la conectividad (u → t_nuevo → v sigue existiendo en el grafo).
        Modela la búsqueda de hubs alternativos con menor costo o menor merma.

    Tipo 3 — Reemplazo completo:
        Genera un individuo completamente nuevo desde cero.
        Actúa como operador de diversificación para escapar de mínimos locales.
    """
    if random.random() >= tasa:
        return camino[:]

    tipo = random.randint(1, 3)
    nuevo = camino[:]

    if tipo == 1:
        # Insertar un tránsito nuevo en algún punto donde la arista lo permita
        todos_transitos = [
            n for n in G.nodes()
            if nodos_dict.get(n, {}).get('tipo') == 'transito'
            and n not in nuevo
        ]
        random.shuffle(todos_transitos)
        for t in todos_transitos:
            for idx in range(1, len(nuevo)):
                u, v = nuevo[idx - 1], nuevo[idx]
                if G.has_edge(u, t) and G.has_edge(t, v):
                    nuevo.insert(idx, t)
                    return nuevo
        # No se pudo insertar, tipo 3 como fallback

    elif tipo == 2:
        # Sustituir un tránsito por otro con misma conectividad de vecindad
        idx_transitos = [
            i for i, n in enumerate(nuevo)
            if nodos_dict.get(n, {}).get('tipo') == 'transito'
        ]
        if idx_transitos:
            idx = random.choice(idx_transitos)
            u = nuevo[idx - 1] if idx > 0 else origen
            v = nuevo[idx + 1] if idx + 1 < len(nuevo) else destino
            alternativas = [
                n for n in G.nodes()
                if nodos_dict.get(n, {}).get('tipo') == 'transito'
                and G.has_edge(u, n) and G.has_edge(n, v)
                and n not in nuevo
            ]
            if alternativas:
                nuevo[idx] = random.choice(alternativas)
                return nuevo
        # Si no hay alternativas, tipo 3

    # Tipo 3 (también fallback de 1 y 2): individuo completamente nuevo
    nuevo = _generar_individuo(G, origen, destino, nodos_dict, caminos_base)

    # Seguridad: garantizar inicio y fin correctos
    if not nuevo or nuevo[0] != origen or nuevo[-1] != destino:
        return camino[:]
    return nuevo


# ─── Función principal ────────────────────────────────────────────────────────

def ejecutar_comparativa_ag(
    origen_seleccionado: str,
    destino_seleccionado: str,
    parametros_ag: dict = None,
    red: dict = None,
    aristas_bloqueadas: list = None,
) -> dict:
    """
    Ejecuta el Algoritmo Genético de Rutas entre el par (origen, destino)
    seleccionado por el usuario, para comparativa directa con Dijkstra/LP.

    El AG busca el camino de menor costo en la red jerárquica que:
      - Empiece obligatoriamente en origen_seleccionado.
      - Termine obligatoriamente en destino_seleccionado.
      - Pase por al menos un nodo de tránsito (centro de acopio).
      - Respete las capacidades de las aristas.

    Args:
        origen_seleccionado:  ID del nodo origen (ej: 'O1').
        destino_seleccionado: ID del nodo destino (ej: 'D15').
        parametros_ag:        Diccionario con parámetros del AG:
                                tamano_poblacion (default 80)
                                generaciones     (default 150)
                                tasa_cruce       (default 0.8)
                                tasa_mutacion    (default 0.2)
                                elitismo         (default 2)
                                seed             (default None)
        red:                  Dict de la red; None carga desde archivo.
        aristas_bloqueadas:   IDs de aristas eliminadas (escenario What-if).

    Returns:
        dict con:
            mejor_camino       — lista de nodos del mejor camino hallado
            costo_total        — costo del camino (KCOP/ton)
            distancia_total_km — distancia del camino en km
            tiempo_segundos    — tiempo de ejecución total
            tiempo_ms          — ídem en milisegundos
            historial_fitness  — mejor fitness por generación (convergencia)
            historial_costo    — costo real (sin penalizaciones) por generación
            factible           — True si el camino cumple todas las restricciones
            aristas_ruta       — detalle de cada arista del camino
            n_caminos_validos  — caminos simples encontrados en el grafo (referencia)
    """
    if red is None:
        red = _cargar_red_local()
    if aristas_bloqueadas is None:
        aristas_bloqueadas = []
    if parametros_ag is None:
        parametros_ag = {}

    # ── Parámetros con defaults ────────────────────────────────────────────────
    tamano_pob   = int(parametros_ag.get('tamano_poblacion', 80))
    generaciones = int(parametros_ag.get('generaciones', 150))
    tasa_cruce   = float(parametros_ag.get('tasa_cruce', 0.8))
    tasa_mut     = float(parametros_ag.get('tasa_mutacion', 0.2))
    elitismo     = int(parametros_ag.get('elitismo', 2))
    seed         = parametros_ag.get('seed')

    if seed is not None:
        random.seed(int(seed))
        np.random.seed(int(seed))

    t_inicio = time.perf_counter()

    # ── Construir grafo y diccionario de nodos ─────────────────────────────────
    G          = _construir_grafo(red, aristas_bloqueadas)
    nodos_dict = {n['id']: n for n in red['nodos']}

    # ── Validaciones de entrada ────────────────────────────────────────────────
    if origen_seleccionado not in G:
        return {'error': f"Origen '{origen_seleccionado}' no existe en el grafo."}
    if destino_seleccionado not in G:
        return {'error': f"Destino '{destino_seleccionado}' no existe en el grafo."}

    # ── Pre-calcular caminos simples válidos (cutoff=5 saltos) ────────────────
    # Se usan como base para la inicialización de la población.
    # cutoff=5 cubre el 100% de los caminos con ≤ 2 tránsitos intermedios.
    # Filtramos para mantener solo los que pasan por al menos un tránsito.
    try:
        todos_caminos = [
            p for p in nx.all_simple_paths(
                G, origen_seleccionado, destino_seleccionado, cutoff=5
            )
            if any(nodos_dict.get(n, {}).get('tipo') == 'transito' for n in p[1:-1])
        ]
    except Exception:
        todos_caminos = []

    n_caminos_validos = len(todos_caminos)

    # ── Población inicial ──────────────────────────────────────────────────────
    poblacion = _crear_poblacion(
        G, origen_seleccionado, destino_seleccionado,
        nodos_dict, tamano_pob, todos_caminos
    )

    mejor_global     = None
    mejor_fit_global = float('inf')
    historial_fitness = []
    historial_costo   = []

    # ── Bucle evolutivo ────────────────────────────────────────────────────────
    for gen in range(generaciones):

        # Evaluar fitness de toda la población
        fitnesses = [
            _fitness_ruta(ind, G, origen_seleccionado, destino_seleccionado, nodos_dict)
            for ind in poblacion
        ]

        mejor_idx = int(np.argmin(fitnesses))
        mejor_fit = fitnesses[mejor_idx]
        costo_gen = _costo_puro(poblacion[mejor_idx], G)

        historial_fitness.append(float(mejor_fit))
        historial_costo.append(round(costo_gen, 2))

        if mejor_fit < mejor_fit_global:
            mejor_fit_global = mejor_fit
            mejor_global     = poblacion[mejor_idx][:]

        # Construir nueva generación
        nueva_pob = []

        # Elitismo: copiar los mejores sin modificación
        for idx in list(np.argsort(fitnesses)[:elitismo]):
            nueva_pob.append(poblacion[idx][:])

        while len(nueva_pob) < tamano_pob:
            p1 = _seleccion_torneo(poblacion, fitnesses)
            p2 = _seleccion_torneo(poblacion, fitnesses)

            # Cruce
            if random.random() < tasa_cruce:
                h1, h2 = _cruce_rutas(
                    p1, p2, origen_seleccionado, destino_seleccionado
                )
            else:
                h1, h2 = p1[:], p2[:]

            # Mutación
            h1 = _mutar_ruta(h1, G, origen_seleccionado, destino_seleccionado,
                              nodos_dict, tasa_mut, todos_caminos)
            h2 = _mutar_ruta(h2, G, origen_seleccionado, destino_seleccionado,
                              nodos_dict, tasa_mut, todos_caminos)

            nueva_pob.append(h1)
            if len(nueva_pob) < tamano_pob:
                nueva_pob.append(h2)

        poblacion = nueva_pob

    # ── Evaluación final ───────────────────────────────────────────────────────
    fitnesses = [
        _fitness_ruta(ind, G, origen_seleccionado, destino_seleccionado, nodos_dict)
        for ind in poblacion
    ]
    mejor_idx = int(np.argmin(fitnesses))
    if fitnesses[mejor_idx] < mejor_fit_global:
        mejor_global     = poblacion[mejor_idx][:]
        mejor_fit_global = fitnesses[mejor_idx]

    tiempo_total = time.perf_counter() - t_inicio

    # ── Construir detalle del mejor camino ────────────────────────────────────
    aristas_ruta    = []
    costo_final_km  = 0.0
    dist_final_km   = 0.0
    factible        = True

    for i in range(len(mejor_global) - 1):
        u, v = mejor_global[i], mejor_global[i + 1]
        if G.has_edge(u, v):
            e = G[u][v]
            costo_final_km += e['costo']
            dist_final_km  += e['distancia_km']
            aristas_ruta.append({
                'arista_id':    e.get('arista_id', f'{u}→{v}'),
                'origen':       u,
                'destino':      v,
                'descripcion':  f"{nodos_dict.get(u,{}).get('nombre',u)} → "
                                f"{nodos_dict.get(v,{}).get('nombre',v)}",
                'distancia_km': e['distancia_km'],
                'costo':        round(e['costo'], 2),
                'capacidad':    e['capacidad'],
                'invertida':    False,
            })
        else:
            factible = False
            aristas_ruta.append({
                'arista_id': f'{u}→{v}-NO-EXISTE',
                'origen': u, 'destino': v,
                'distancia_km': 0, 'costo': PENALIZACION,
                'capacidad': 0, 'invertida': False,
            })

    # Verificaciones de factibilidad
    tiene_transito = any(
        nodos_dict.get(n, {}).get('tipo') == 'transito'
        for n in mejor_global[1:-1]
    )
    if not tiene_transito:
        factible = False
    if (not mejor_global
            or mejor_global[0]  != origen_seleccionado
            or mejor_global[-1] != destino_seleccionado):
        factible = False

    return {
        'algoritmo':          'Genético — Path AG',
        'origen':             origen_seleccionado,
        'destino':            destino_seleccionado,
        'mejor_camino':       mejor_global,
        'n_nodos_ruta':       len(mejor_global),
        'aristas_ruta':       aristas_ruta,
        'costo_total':        round(costo_final_km, 2),
        'distancia_total_km': round(dist_final_km, 2),
        'n_saltos':           len(mejor_global) - 1,
        'factible':           factible,
        'tiene_transito':     tiene_transito,
        'historial_fitness':  historial_fitness,
        'historial_costo':    historial_costo,
        'tiempo_segundos':    round(tiempo_total, 4),
        'tiempo_ms':          round(tiempo_total * 1000, 2),
        'n_generaciones':     generaciones,
        'n_caminos_validos':  n_caminos_validos,
        'parametros': {
            'tamano_poblacion': tamano_pob,
            'generaciones':     generaciones,
            'tasa_cruce':       tasa_cruce,
            'tasa_mutacion':    tasa_mut,
            'elitismo':         elitismo,
            'seed':             seed,
        },
    }
