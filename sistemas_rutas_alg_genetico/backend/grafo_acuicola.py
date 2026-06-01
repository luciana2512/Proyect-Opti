"""
grafo_acuicola.py — Teoría de Grafos y Algoritmos de Red
=========================================================
Red Logística Acuícola Real del Meta · Proyecto Final 2026-1

Modela la red como Grafo Dirigido Ponderado G = (V, E) usando NetworkX.
Los pesos de las aristas son el costo total de transporte (dist_km × costo_ton_km).

Algoritmos implementados:
    · Dijkstra          — ruta de menor costo (sin pesos negativos)
    · Bellman-Ford      — ruta de menor costo (detecta ciclos negativos)
    · Edmonds-Karp      — flujo máximo y corte mínimo (cuellos de botella)
    · Betweenness       — centralidad de nodos (hub más crítico)
    · Haversine TSP     — distancias reales para AG de distribución local

Funciones públicas principales:
    construir_grafo(red, flujos_pl, aristas_bloqueadas)  → nx.DiGraph
    ruta_dijkstra(G, origen, destino)                    → dict
    ruta_bellman_ford(G, origen, destino)                → dict
    flujo_maximo(G, fuente, sumidero)                    → dict
    analizar_red(G, resultado_pl)                        → dict
    validar_conectividad(G)                              → dict
    optimizar_distribucion_local(transito_id, ...)       → dict  [AG TSP]
    optimizar_ag_flujos_red(transito_id, ...)            → dict  [AG Flujos]
    obtener_geometria_ruta_real(ruta_ids, nodos_dict)    → list  [OSRM]
"""
import json
import os
import math
import urllib.request as _urllib_req
import json as _json_util
import numpy as np
import networkx as nx
from genetic_algorithm import algoritmo_genetico, algoritmo_genetico_flujos


def cargar_red():
    ruta = os.path.join(os.path.dirname(__file__), 'red_acuicola.json')
    with open(ruta, 'r', encoding='utf-8') as f:
        return json.load(f)


def construir_grafo(red=None, flujos_pl=None, aristas_bloqueadas=None):
    """
    Construye el grafo dirigido ponderado NetworkX.

    El peso principal de cada arista es:
        costo_total = distancia_km * costo_por_ton_km (KCOP/ton)

    Si se proporcionan flujos_pl, agrega el flujo real calculado por el LP.

    Returns:
        networkx.DiGraph
    """
    if red is None:
        red = cargar_red()
    if aristas_bloqueadas is None:
        aristas_bloqueadas = []

    G = nx.DiGraph()

    # Añadir nodos con atributos
    for nodo in red['nodos']:
        G.add_node(
            nodo['id'],
            tipo=nodo['tipo'],
            nombre=nodo['nombre'],
            lat=nodo['lat'],
            lon=nodo['lon'],
            **{k: v for k, v in nodo.items()
               if k not in ('id', 'tipo', 'nombre', 'lat', 'lon')}
        )

    # Añadir aristas con atributos
    for a in red['aristas']:
        if a['id'] in aristas_bloqueadas:
            continue
        costo = float(a['distancia_km']) * float(a['costo_por_ton_km'])
        flujo = 0.0
        if flujos_pl and a['id'] in flujos_pl:
            flujo = flujos_pl[a['id']].get('flujo', 0.0)

        G.add_edge(
            a['origen'], a['destino'],
            arista_id=a['id'],
            distancia_km=float(a['distancia_km']),
            costo_por_ton_km=float(a['costo_por_ton_km']),
            capacidad=float(a['capacidad_ton']),
            costo=costo,           # peso principal (costo total por ton)
            flujo=flujo,
            es_critica=a.get('es_critica', False),
            descripcion=a.get('descripcion', '')
        )

    return G


# ─── Helpers internos de ruta ───────────────────────────────────────────────

def _construir_aristas_ruta(G, camino):
    """
    Construye la lista de aristas para un camino dado.
    Si algún tramo usa una arista en sentido inverso (retroceso en grafo no-dirigido),
    la marca con invertida=True para que el frontend pueda advertirlo.
    """
    aristas = []
    for i in range(len(camino) - 1):
        u, v = camino[i], camino[i + 1]
        if G.has_edge(u, v):
            data = G[u][v]
            aristas.append({
                'arista_id':    data['arista_id'],
                'origen':       u,
                'destino':      v,
                'descripcion':  data['descripcion'],
                'distancia_km': data['distancia_km'],
                'costo':        round(data['costo'], 2),
                'invertida':    False,
            })
        elif G.has_edge(v, u):
            # Tramo recorrido en sentido contrario al arco dirigido original
            data = G[v][u]
            aristas.append({
                'arista_id':    data['arista_id'] + '_inv',
                'origen':       u,
                'destino':      v,
                'descripcion':  f"↩ {data['descripcion']} (sentido inverso)",
                'distancia_km': data['distancia_km'],
                'costo':        round(data['costo'], 2),
                'invertida':    True,
            })
    return aristas


def _sugerir_alternativas(G, origen, destino, n=3):
    """
    Cuando no existe ningún camino, sugiere los destinos más baratos
    alcanzables desde el origen y los orígenes/tránsitos que sí llegan al destino.
    """
    resultado = {'desde_origen': [], 'hacia_destino': []}

    if origen in G:
        tipo_obj = G.nodes[destino].get('tipo', 'destino') if destino in G else 'destino'
        alcanzables = nx.descendants(G, origen)
        candidatos_costo = {}
        for nid in alcanzables:
            if G.nodes[nid].get('tipo') == tipo_obj:
                try:
                    candidatos_costo[nid] = nx.dijkstra_path_length(G, origen, nid, weight='costo')
                except Exception:
                    pass
        for nid in sorted(candidatos_costo, key=lambda k: candidatos_costo.get(k, float('inf')))[:n]:
            resultado['desde_origen'].append({
                'id':     nid,
                'nombre': G.nodes[nid].get('nombre', nid),
                'costo':  round(candidatos_costo[nid], 2),
            })

    if destino in G:
        tipo_org = G.nodes[origen].get('tipo', 'origen') if origen in G else 'origen'
        antecesores = nx.ancestors(G, destino)
        candidatos_costo = {}
        for nid in antecesores:
            if G.nodes[nid].get('tipo') in ('origen', 'transito'):
                try:
                    candidatos_costo[nid] = nx.dijkstra_path_length(G, nid, destino, weight='costo')
                except Exception:
                    pass
        for nid in sorted(candidatos_costo, key=lambda k: candidatos_costo.get(k, float('inf')))[:n]:
            resultado['hacia_destino'].append({
                'id':     nid,
                'nombre': G.nodes[nid].get('nombre', nid),
                'costo':  round(candidatos_costo[nid], 2),
            })

    return resultado


# ─── Algoritmos de ruta óptima ──────────────────────────────────────────────

def ruta_dijkstra(G, origen, destino):
    """
    Ruta de menor costo usando Dijkstra.

    Intenta primero el grafo DIRIGIDO. Si no existe camino, recurre al grafo
    NO-DIRIGIDO (permite retroceder por aristas en sentido inverso) y señala
    los tramos invertidos. Si tampoco hay camino, devuelve alternativas.

    Returns:
        dict con ruta, costo, distancia y nodos intermedios.
    """
    try:
        camino = nx.dijkstra_path(G, origen, destino, weight='costo')
        costo  = nx.dijkstra_path_length(G, origen, destino, weight='costo')
        distancia_km = sum(
            G[camino[i]][camino[i + 1]]['distancia_km'] for i in range(len(camino) - 1)
        )
        return {
            'algoritmo':    'Dijkstra',
            'factible':     True,
            'via_retroceso': False,
            'ruta':         camino,
            'costo_total':  round(costo, 2),
            'distancia_km': round(distancia_km, 2),
            'n_saltos':     len(camino) - 1,
            'aristas_ruta': _construir_aristas_ruta(G, camino),
        }
    except nx.NetworkXNoPath:
        # ── Fallback: grafo no-dirigido ──────────────────────────────────────
        G_u = G.to_undirected()
        try:
            camino = nx.dijkstra_path(G_u, origen, destino, weight='costo')
            costo  = nx.dijkstra_path_length(G_u, origen, destino, weight='costo')
            distancia_km = sum(
                G_u[camino[i]][camino[i + 1]]['distancia_km'] for i in range(len(camino) - 1)
            )
            aristas = _construir_aristas_ruta(G, camino)
            n_inv   = sum(1 for a in aristas if a['invertida'])
            return {
                'algoritmo':    'Dijkstra',
                'factible':     True,
                'via_retroceso': True,
                'advertencia':  (
                    f'No existe ruta directa de {origen} a {destino} en el grafo dirigido. '
                    f'Se encontró un camino usando {n_inv} arista(s) recorrida(s) en sentido '
                    f'inverso (retroceso por el hub). El costo puede no ser comercialmente óptimo.'
                ),
                'ruta':         camino,
                'costo_total':  round(costo, 2),
                'distancia_km': round(distancia_km, 2),
                'n_saltos':     len(camino) - 1,
                'aristas_ruta': aristas,
            }
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            pass

        alternativas = _sugerir_alternativas(G, origen, destino)
        return {
            'algoritmo':    'Dijkstra',
            'factible':     False,
            'error':        f'No existe ningún camino entre {origen} y {destino} (ni dirigido ni no-dirigido).',
            'alternativas': alternativas,
        }
    except nx.NodeNotFound as e:
        return {'algoritmo': 'Dijkstra', 'factible': False, 'error': str(e)}


def ruta_bellman_ford(G, origen, destino):
    """
    Ruta de menor costo usando Bellman-Ford (detecta ciclos negativos).

    Aplica la misma estrategia de fallback que ruta_dijkstra: intenta primero
    el grafo dirigido y luego el no-dirigido si no hay camino.

    Returns:
        dict con ruta, costo y detalles.
    """
    try:
        costo, camino = nx.single_source_bellman_ford(G, origen, target=destino, weight='costo')
        distancia_km = sum(
            G[camino[i]][camino[i + 1]]['distancia_km'] for i in range(len(camino) - 1)
        )
        return {
            'algoritmo':    'Bellman-Ford',
            'factible':     True,
            'via_retroceso': False,
            'ruta':         camino,
            'costo_total':  round(costo, 2),
            'distancia_km': round(distancia_km, 2),
            'n_saltos':     len(camino) - 1,
            'aristas_ruta': _construir_aristas_ruta(G, camino),
        }
    except nx.NetworkXNoPath:
        # ── Fallback: grafo no-dirigido ──────────────────────────────────────
        G_u = G.to_undirected()
        try:
            camino = nx.dijkstra_path(G_u, origen, destino, weight='costo')
            costo  = nx.dijkstra_path_length(G_u, origen, destino, weight='costo')
            distancia_km = sum(
                G_u[camino[i]][camino[i + 1]]['distancia_km'] for i in range(len(camino) - 1)
            )
            aristas = _construir_aristas_ruta(G, camino)
            n_inv   = sum(1 for a in aristas if a['invertida'])
            return {
                'algoritmo':    'Bellman-Ford',
                'factible':     True,
                'via_retroceso': True,
                'advertencia':  (
                    f'No existe ruta directa de {origen} a {destino} en el grafo dirigido. '
                    f'Se encontró un camino usando {n_inv} arista(s) recorrida(s) en sentido '
                    f'inverso (retroceso por el hub). El costo puede no ser comercialmente óptimo.'
                ),
                'ruta':         camino,
                'costo_total':  round(costo, 2),
                'distancia_km': round(distancia_km, 2),
                'n_saltos':     len(camino) - 1,
                'aristas_ruta': aristas,
            }
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            pass

        alternativas = _sugerir_alternativas(G, origen, destino)
        return {
            'algoritmo':    'Bellman-Ford',
            'factible':     False,
            'error':        f'No existe ningún camino entre {origen} y {destino} (ni dirigido ni no-dirigido).',
            'alternativas': alternativas,
        }
    except nx.NodeNotFound as e:
        return {'algoritmo': 'Bellman-Ford', 'factible': False, 'error': str(e)}
    except nx.NetworkXUnbounded:
        return {'algoritmo': 'Bellman-Ford', 'factible': False,
                'error': 'Ciclo de costo negativo detectado'}


# ─── Flujo Máximo ────────────────────────────────────────────────────────────

def flujo_maximo(G, fuente, sumidero):
    """
    Calcula el flujo máximo y detecta el corte mínimo (cuello de botella).

    Usa el algoritmo de Edmonds-Karp implementado en NetworkX.

    Returns:
        dict con flujo máximo, aristas del corte mínimo y saturadas.
    """
    # Construir grafo de capacidades
    G_cap = nx.DiGraph()
    for u, v, data in G.edges(data=True):
        G_cap.add_edge(u, v, capacity=data['capacidad'])

    if fuente not in G_cap or sumidero not in G_cap:
        return {'error': f'Nodo {fuente} o {sumidero} no encontrado en la red'}

    try:
        valor_flujo, dict_flujo = nx.maximum_flow(
            G_cap, fuente, sumidero, capacity='capacity', flow_func=nx.algorithms.flow.edmonds_karp
        )

        # Si el flujo es 0 y no hay ruta dirigida, retornar advertencia clara
        if valor_flujo == 0:
            try:
                nx.shortest_path(G_cap, fuente, sumidero)
                sin_ruta_dirigida = False
            except nx.NetworkXNoPath:
                sin_ruta_dirigida = True
            if sin_ruta_dirigida:
                return {
                    'fuente':           fuente,
                    'sumidero':         sumidero,
                    'flujo_maximo':     0,
                    'corte_minimo':     0,
                    'aristas_corte':    [],
                    'aristas_saturadas': [],
                    'n_aristas_corte':  0,
                    'advertencia':      (
                        f'No existe ruta dirigida de {fuente} a {sumidero} en el grafo. '
                        f'El flujo máximo es 0. Elija un par origen-destino con camino dirigido.'
                    ),
                }

        # Corte mínimo
        corte_valor, (lado_s, lado_t) = nx.minimum_cut(G_cap, fuente, sumidero, capacity='capacity')

        aristas_corte = [
            {
                'origen':    u,
                'destino':   v,
                'capacidad': G_cap[u][v]['capacity'],
            }
            for u in lado_s for v in lado_t
            if G_cap.has_edge(u, v)
        ]

        # Aristas saturadas (flujo = capacidad)
        aristas_saturadas = []
        for u, v, data in G.edges(data=True):
            flujo_uv = dict_flujo.get(u, {}).get(v, 0)
            if flujo_uv >= data['capacidad'] * 0.99 and data['capacidad'] > 0:
                aristas_saturadas.append({
                    'origen':    u,
                    'destino':   v,
                    'arista_id': data.get('arista_id', ''),
                    'capacidad': data['capacidad'],
                    'flujo':     round(flujo_uv, 3),
                    'descripcion': data.get('descripcion', '')
                })

        return {
            'fuente':           fuente,
            'sumidero':         sumidero,
            'flujo_maximo':     round(valor_flujo, 3),
            'corte_minimo':     round(corte_valor, 3),
            'aristas_corte':    aristas_corte,
            'aristas_saturadas': aristas_saturadas,
            'n_aristas_corte':  len(aristas_corte)
        }
    except Exception as e:
        return {'error': str(e)}


# ─── Análisis de red ─────────────────────────────────────────────────────────

def analizar_red(G, resultado_pl=None):
    """
    Calcula métricas generales del grafo y detecta nodos/aristas críticas.

    Returns:
        dict con estadísticas de la red.
    """
    nodos_transito = [n for n, d in G.nodes(data=True) if d.get('tipo') == 'transito']
    nodos_origen   = [n for n, d in G.nodes(data=True) if d.get('tipo') == 'origen']
    nodos_destino  = [n for n, d in G.nodes(data=True) if d.get('tipo') == 'destino']

    # Centralidad de intermediación (betweenness)
    betweenness = nx.betweenness_centrality(G, weight='costo', normalized=True)
    nodo_mas_central = max(betweenness, key=betweenness.get) if betweenness else None

    # Aristas con mayor flujo (si hay resultados LP)
    aristas_criticas = []
    if resultado_pl and 'flujos' in resultado_pl:
        for aid, f in resultado_pl['flujos'].items():
            if f.get('uso_pct', 0) >= 80:
                aristas_criticas.append({
                    'arista_id': aid,
                    'origen':    f['origen'],
                    'destino':   f['destino'],
                    'uso_pct':   f['uso_pct'],
                    'flujo':     f['flujo']
                })
        aristas_criticas.sort(key=lambda x: x['uso_pct'], reverse=True)

    return {
        'n_nodos':          G.number_of_nodes(),
        'n_aristas':        G.number_of_edges(),
        'n_origenes':       len(nodos_origen),
        'n_transitos':      len(nodos_transito),
        'n_destinos':       len(nodos_destino),
        'densidad':         round(nx.density(G), 4),
        'nodo_mas_central': nodo_mas_central,
        'centralidad_max':  round(betweenness.get(nodo_mas_central, 0), 4) if nodo_mas_central else 0,
        'aristas_criticas': aristas_criticas[:5],
        'betweenness':      {k: round(v, 4) for k, v in
                             sorted(betweenness.items(), key=lambda x: x[1], reverse=True)[:10]}
    }


# ─── Validación de conectividad del grafo ───────────────────────────────────

def validar_conectividad(G):
    """
    Analiza la conectividad del grafo dirigido e identifica:
      - Destinos inalcanzables desde cualquier origen
      - Orígenes sin camino a ningún destino
      - Nodos aislados (sin aristas)
      - Componentes débilmente conexos
      - Cobertura de cada nodo de tránsito

    Returns:
        dict con reporte completo de conectividad.
    """
    nodos_data = dict(G.nodes(data=True))
    origenes  = [n for n, d in nodos_data.items() if d.get('tipo') == 'origen']
    transitos = [n for n, d in nodos_data.items() if d.get('tipo') == 'transito']
    destinos  = [n for n, d in nodos_data.items() if d.get('tipo') == 'destino']

    # Conjunto global de nodos alcanzables desde cualquier origen
    alcanzables_global = set()
    for o in origenes:
        if o in G:
            alcanzables_global |= nx.descendants(G, o)

    # Destinos que no puede alcanzar ningún origen
    destinos_inalcanzables = [
        {'id': d, 'nombre': nodos_data[d].get('nombre', d)}
        for d in destinos if d not in alcanzables_global
    ]

    # Orígenes que no alcanzan ningún destino
    origenes_sin_destino = []
    for o in origenes:
        desc = nx.descendants(G, o) if o in G else set()
        if not any(nodos_data[n].get('tipo') == 'destino' for n in desc):
            origenes_sin_destino.append({'id': o, 'nombre': nodos_data[o].get('nombre', o)})

    # Nodos completamente aislados (grado 0)
    nodos_aislados = [
        {'id': n, 'nombre': nodos_data[n].get('nombre', n)}
        for n in G.nodes()
        if G.in_degree(n) == 0 and G.out_degree(n) == 0
    ]

    # Componentes débilmente conexos
    n_comp = nx.number_weakly_connected_components(G)
    componentes = [
        sorted(list(c))
        for c in sorted(nx.weakly_connected_components(G), key=len, reverse=True)
    ]

    # Cobertura de cada nodo de tránsito (qué destinos puede alcanzar)
    cobertura_transitos = {}
    for t in transitos:
        desc = nx.descendants(G, t) if t in G else set()
        destinos_t = sorted([d for d in desc if nodos_data[d].get('tipo') == 'destino'])
        cobertura_transitos[t] = {
            'nombre':    nodos_data[t].get('nombre', t),
            'n_destinos': len(destinos_t),
            'destinos':  destinos_t,
        }

    n_alcanzables = len(destinos) - len(destinos_inalcanzables)
    pct = round(n_alcanzables / len(destinos) * 100, 1) if destinos else 0.0

    print(f'[Conectividad] {n_alcanzables}/{len(destinos)} destinos alcanzables ({pct}%). '
          f'Componentes débiles: {n_comp}.')

    return {
        'n_nodos':                G.number_of_nodes(),
        'n_aristas':              G.number_of_edges(),
        'n_componentes_debiles':  n_comp,
        'conexo_debilmente':      n_comp == 1,
        'componentes':            componentes,
        'nodos_aislados':         nodos_aislados,
        'destinos_inalcanzables': destinos_inalcanzables,
        'origenes_sin_destino':   origenes_sin_destino,
        'cobertura_transitos':    cobertura_transitos,
        'resumen': {
            'n_destinos_total':        len(destinos),
            'n_destinos_alcanzables':  n_alcanzables,
            'n_destinos_inalcanzables': len(destinos_inalcanzables),
            'pct_cobertura':           pct,
            'grafo_sano':              (
                len(destinos_inalcanzables) == 0
                and len(origenes_sin_destino) == 0
                and len(nodos_aislados) == 0
            ),
        },
    }


# ─── Optimización de ruta de distribución local con AG ───────────────────────

def _haversine(lat1, lon1, lat2, lon2):
    """Distancia en km entre dos coordenadas geográficas."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi  = math.radians(lat2 - lat1)
    dlam  = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def optimizar_distribucion_local(transito_id, red=None, seed=None,
                                  tamano_poblacion=80, generaciones=150,
                                  tasa_cruce=0.8, tasa_mutacion=0.15, elitismo=2):
    """
    Optimiza el orden de entrega a los supermercados atendidos por un nodo de tránsito,
    usando el Algoritmo Genético existente sobre una matriz de distancias Haversine.

    El nodo de tránsito actúa como depósito (inicio y fin del recorrido).

    Returns:
        dict con ruta optimizada, distancia total y métricas del AG.
    """
    if red is None:
        red = cargar_red()

    nodos = {n['id']: n for n in red['nodos']}

    # Verificar que el nodo existe y es de tránsito
    if transito_id not in nodos or nodos[transito_id]['tipo'] != 'transito':
        return {'error': f'{transito_id} no es un nodo de tránsito válido'}

    # Destinos servidos directamente por este nodo de tránsito
    destinos_ids = [
        a['destino'] for a in red['aristas']
        if a['origen'] == transito_id and nodos.get(a['destino'], {}).get('tipo') == 'destino'
    ]

    if len(destinos_ids) < 2:
        return {'error': f'{transito_id} atiende menos de 2 destinos; no se puede optimizar.'}

    # Construir lista de puntos: [tránsito, destino1, destino2, ...]
    puntos = [transito_id] + destinos_ids
    n = len(puntos)

    # Matriz de distancias Haversine (en km)
    matriz = np.zeros((n, n))
    for i in range(n):
        ni = nodos[puntos[i]]
        for j in range(n):
            if i != j:
                nj = nodos[puntos[j]]
                matriz[i, j] = _haversine(ni['lat'], ni['lon'], nj['lat'], nj['lon'])

    # Ejecutar AG (inicio y fin en el nodo de tránsito = índice 0)
    resultado_ga = algoritmo_genetico(
        matriz_distancias=matriz,
        punto_inicio_idx=0,
        punto_fin_idx=0,     # ciclo: regresa al depósito
        tamano_poblacion=tamano_poblacion,
        generaciones=generaciones,
        tasa_cruce=tasa_cruce,
        tasa_mutacion=tasa_mutacion,
        seed=seed,
        elitismo=elitismo,
        verbose=False
    )

    orden = resultado_ga['mejor_ruta']
    ruta_nombres = [puntos[i] for i in orden]
    ruta_detalle = []
    for i in range(len(orden) - 1):
        ni = nodos[puntos[orden[i]]]
        nj = nodos[puntos[orden[i+1]]]
        ruta_detalle.append({
            'desde':       puntos[orden[i]],
            'hasta':       puntos[orden[i+1]],
            'nombre_desde': ni['nombre'],
            'nombre_hasta': nj['nombre'],
            'distancia_km': round(matriz[orden[i], orden[i+1]], 2)
        })

    return {
        'transito_id':       transito_id,
        'transito_nombre':   nodos[transito_id]['nombre'],
        'destinos_atendidos': destinos_ids,
        'n_destinos':        len(destinos_ids),
        'orden_optimizado':  ruta_nombres,
        'ruta_detalle':      ruta_detalle,
        'distancia_total_km': round(resultado_ga['mejor_fitness'], 2),
        'tiempo_ms':          resultado_ga.get('tiempo_ms', 0),
        'historial_fitness':  [round(f, 2) for f in resultado_ga['historial_fitness'][::10]],
        'parametros_ga': {
            'tamano_poblacion': tamano_poblacion,
            'generaciones':     generaciones,
            'tasa_cruce':       tasa_cruce,
            'tasa_mutacion':    tasa_mutacion,
            'elitismo':         elitismo
        }
    }


# ─── Optimización de flujos en la red completa con AG ────────────────────────

def optimizar_ag_flujos_red(transito_id=None, red=None, seed=None,
                              tamano_poblacion=80, generaciones=150,
                              tasa_cruce=0.8, tasa_mutacion=0.15, elitismo=2):
    """
    Optimiza los flujos en la red completa usando el AG basado en flujos.

    El cromosoma representa el flujo en cada arista del grafo.
    El fitness minimiza el costo total de transporte más penalizaciones por:
      - Demanda incumplida en destinos
      - Oferta excedida en orígenes
    Ejecuta el LP primero para obtener el costo óptimo de referencia y calcula
    el gap porcentual entre la solución LP y la solución AG.

    Args:
        transito_id      -- hub de referencia para filtrar resultados por zona (opcional)
        red              -- dict de la red; si None carga desde archivo
        tamano_poblacion -- tamaño de la población del AG
        generaciones     -- número de generaciones
        tasa_cruce       -- probabilidad de cruce por pareja
        tasa_mutacion    -- probabilidad de mutación por gen
        elitismo         -- individuos élite conservados sin cambio

    Returns:
        dict con comparacion_lp_ag, historial_costo, flujos_ag, cobertura_demanda
    """
    from modelo_pl import resolver_pl as _resolver_pl

    if red is None:
        red = cargar_red()

    aristas    = red['aristas']
    nodos_dict = {n['id']: n for n in red['nodos']}

    # ── Solución LP como referencia ───────────────────────────────────────────
    resultado_lp = _resolver_pl(red=red)
    costo_lp     = resultado_lp.get('costo_total') if resultado_lp.get('factible') else None

    # ── AG sobre la red completa ──────────────────────────────────────────────
    resultado_ga = algoritmo_genetico_flujos(
        red=red,
        tamano_poblacion=tamano_poblacion,
        generaciones=generaciones,
        tasa_cruce=tasa_cruce,
        tasa_mutacion=tasa_mutacion,
        seed=seed,
        elitismo=elitismo,
        verbose=False,
    )

    costo_ag  = resultado_ga['costo_transporte']
    cromosoma = resultado_ga['mejor_cromosoma']

    # ── Flujos AG por arista ──────────────────────────────────────────────────
    flujos_ag = {}
    for i, a in enumerate(aristas):
        flujo = round(cromosoma[i], 4) if cromosoma else 0.0
        cap   = float(a['capacidad_ton'])
        flujos_ag[a['id']] = {
            'arista_id':   a['id'],
            'origen':      a['origen'],
            'destino':     a['destino'],
            'descripcion': a.get('descripcion', ''),
            'flujo':       flujo,
            'capacidad':   cap,
            'uso_pct':     round(flujo / cap * 100, 1) if cap > 0 else 0.0,
            'activa':      flujo > 0.01,
        }

    # ── Cobertura de demanda por destino ──────────────────────────────────────
    flujo_entrada = {}
    for i, a in enumerate(aristas):
        flujo_entrada[a['destino']] = (
            flujo_entrada.get(a['destino'], 0.0) + (cromosoma[i] if cromosoma else 0.0)
        )

    cobertura = []
    for n in red['nodos']:
        if n['tipo'] == 'destino':
            demanda  = float(n.get('demanda', 0))
            recibido = flujo_entrada.get(n['id'], 0.0)
            cobertura.append({
                'id':        n['id'],
                'nombre':    n['nombre'],
                'demanda':   demanda,
                'flujo_ag':  round(recibido, 3),
                'satisfecha': abs(recibido - demanda) < 0.5,
            })

    # ── Factibilidad y gap LP vs AG ───────────────────────────────────────────
    violacion_total = sum(
        abs(flujo_entrada.get(n['id'], 0.0) - float(n.get('demanda', 0)))
        for n in red['nodos'] if n['tipo'] == 'destino'
    )
    factible_ag = violacion_total < 0.5
    gap_pct = None
    if factible_ag and costo_lp and costo_lp > 0:
        brecha = (costo_ag - costo_lp) / costo_lp * 100
        gap_pct = round(max(0.0, brecha), 2)
    else:
        gap_pct = None

    # Filtrar cobertura por hub si se especificó
    destinos_hub = None
    if transito_id:
        destinos_hub = {
            a['destino'] for a in aristas
            if a['origen'] == transito_id
            and nodos_dict.get(a['destino'], {}).get('tipo') == 'destino'
        }

    return {
        'comparacion_lp_ag': {
            'costo_lp':          costo_lp,
            'costo_ag':          costo_ag,
            'gap_pct':           gap_pct,
            'lp_factible':       resultado_lp.get('factible', False),
            'ag_factible':       factible_ag,
            'violacion_demanda': round(violacion_total, 3),
        },
        'historial_fitness': resultado_ga['historial_fitness'],
        'historial_costo':   resultado_ga['historial_costo'],
        'flujos_ag':         flujos_ag,
        'cobertura_demanda': cobertura,
        'cobertura_hub': [
            c for c in cobertura if destinos_hub and c['id'] in destinos_hub
        ] if destinos_hub else [],
        'transito_id':   transito_id,
        'parametros_ga': {
            'tamano_poblacion': tamano_poblacion,
            'generaciones':     generaciones,
            'tasa_cruce':       tasa_cruce,
            'tasa_mutacion':    tasa_mutacion,
            'elitismo':         elitismo,
        },
        'n_aristas': len(aristas),
        'n_nodos':   len(red['nodos']),
    }


# ─── Geometría de ruta real (OSRM) ───────────────────────────────────────────

# Cache en memoria para no repetir peticiones OSRM: (origen_id, destino_id) → [[lat,lon],…]
_osrm_cache: dict = {}


def obtener_geometria_arista(origen_id, destino_id, nodos_dict, timeout=8):
    """
    Devuelve la polilínea OSRM (carreteras reales) para la arista (origen → destino).
    Cachea el resultado en _osrm_cache. Si OSRM falla, retorna línea recta como fallback.
    """
    key = (origen_id, destino_id)
    if key in _osrm_cache:
        return _osrm_cache[key]

    nu = nodos_dict.get(origen_id)
    nv = nodos_dict.get(destino_id)
    if not nu or not nv:
        _osrm_cache[key] = []
        return []

    fallback = [[nu['lat'], nu['lon']], [nv['lat'], nv['lon']]]
    url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{nu['lon']},{nu['lat']};{nv['lon']},{nv['lat']}"
        f"?overview=full&geometries=geojson&steps=false"
    )
    try:
        req = _urllib_req.Request(
            url, headers={'User-Agent': 'AcuicolaRealDelMeta/1.0 (proyecto-academico)'}
        )
        with _urllib_req.urlopen(req, timeout=timeout) as resp:
            data = _json_util.loads(resp.read().decode('utf-8'))
        if data.get('code') == 'Ok' and data.get('routes'):
            coords = data['routes'][0]['geometry']['coordinates']
            geo = [[c[1], c[0]] for c in coords]
            _osrm_cache[key] = geo
            return geo
    except Exception as exc:
        print(f'[OSRM] Arista {origen_id}→{destino_id} fallback a línea recta ({exc})')

    _osrm_cache[key] = fallback
    return fallback


def obtener_geometria_ruta_real(ruta_ids, nodos_dict, timeout=12):
    """
    Obtiene la polilínea detallada de una ruta siguiendo calles reales usando
    el servicio público de OSRM (router.project-osrm.org).

    Envía todos los waypoints en una sola petición HTTP para minimizar latencia.
    Si OSRM no está disponible, devuelve líneas rectas entre los nodos.

    Args:
        ruta_ids:    lista de IDs de nodos en orden ['O1', 'T2', 'T1', 'D1']
        nodos_dict:  dict {id: nodo} con campos lat y lon
        timeout:     segundos de espera máximos por la petición HTTP

    Returns:
        lista de [lat, lon] — polilínea siguiendo calles reales (o rectas)
    """
    validos = [nid for nid in ruta_ids if nid in nodos_dict]
    if len(validos) < 2:
        return []

    # OSRM espera coordenadas en formato lon,lat separadas por ";"
    waypoints = ";".join(
        f"{nodos_dict[nid]['lon']},{nodos_dict[nid]['lat']}"
        for nid in validos
    )
    url = (
        f"http://router.project-osrm.org/route/v1/driving/{waypoints}"
        f"?overview=full&geometries=geojson&steps=false"
    )

    try:
        req = _urllib_req.Request(
            url,
            headers={'User-Agent': 'AcuicolaRealDelMeta/1.0 (proyecto-academico)'}
        )
        with _urllib_req.urlopen(req, timeout=timeout) as resp:
            data = _json_util.loads(resp.read().decode('utf-8'))

        if data.get('code') == 'Ok' and data.get('routes'):
            # OSRM retorna [lon, lat]; convertimos a [lat, lon] para Leaflet
            coords = data['routes'][0]['geometry']['coordinates']
            geometria = [[c[1], c[0]] for c in coords]
            print(f'[OSRM] Geometría real: {len(geometria)} puntos para ruta {validos}')
            return geometria

    except Exception as exc:
        print(f'[OSRM] No disponible ({exc}); usando líneas rectas como fallback.')

    # Fallback: líneas rectas entre los nodos de la ruta
    return [[nodos_dict[nid]['lat'], nodos_dict[nid]['lon']] for nid in validos]