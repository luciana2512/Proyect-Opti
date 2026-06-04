"""
api_rutas_reales.py — API REST Flask
=====================================
Red Logística Acuícola Real del Meta · Proyecto Final 2026-1

Servidor Flask que expone todos los algoritmos del proyecto como endpoints HTTP.
El frontend React consume esta API en http://localhost:5000.

Endpoints disponibles:
    GET  /api/health
    GET  /api/acuicola/red
    GET  /api/acuicola/optimizar          → LP + Dijkstra/BF + Flujo Máximo
    GET  /api/acuicola/ruta               → Solo ruta óptima (Dijkstra/BF)
    GET  /api/acuicola/ruta_escenario     → Ruta bajo condiciones What-If
    GET  /api/acuicola/sensibilidad/1     → Escenario: alza combustible
    GET  /api/acuicola/sensibilidad/2     → Escenario: cierre de vía
    GET  /api/acuicola/sensibilidad/3     → Escenario: pérdida de calidad
    GET  /api/acuicola/sensibilidad/todos → Los 3 escenarios en paralelo
    GET  /api/acuicola/distribucion/<hub> → AG TSP desde un hub
    GET  /api/acuicola/ag_red             → AG Flujos vs LP (comparativa)
    GET  /api/acuicola/validar_conectividad
    POST /api/acuicola/geometria_aristas  → Geometría OSRM por aristas
    GET  /api/acuicola/geometria_ruta     → Geometría OSRM por secuencia de nodos
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, jsonify, request
from flask_cors import CORS

from modelo_pl import resolver_pl, cargar_red as cargar_red_acuicola
from grafo_acuicola import (
    construir_grafo, ruta_dijkstra, ruta_bellman_ford,
    flujo_maximo, analizar_red, optimizar_distribucion_local,
    optimizar_ag_flujos_red, obtener_geometria_ruta_real,
    obtener_geometria_arista, validar_conectividad,
)
from analisis_sensibilidad import (
    escenario_combustible_meta,
    escenario_cierre_via,
    escenario_calidad_acopio,
    ejecutar_todos_los_escenarios,
)

app = Flask(__name__)
CORS(app)

# Caché en memoria para no recargar el JSON en cada request
_cache = {}


def _red():
    if 'red' not in _cache:
        _cache['red'] = cargar_red_acuicola()
    return _cache['red']


def _validar_nodo(nodo_id, red, campo='nodo'):
    """Devuelve un mensaje de error si el nodo_id no existe en la red."""
    ids_validos = {n['id'] for n in red['nodos']}
    if nodo_id not in ids_validos:
        return f"El {campo} '{nodo_id}' no existe en la red. IDs válidos: {sorted(ids_validos)}"
    return None


# ── Health check ─────────────────────────────────────────────────────────────

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


# ── Red logística ─────────────────────────────────────────────────────────────

@app.route('/api/acuicola/red', methods=['GET'])
def obtener_red():
    """Devuelve la estructura completa de la red logística acuícola."""
    try:
        red = _red()
        return jsonify({
            'nombre':  red['nombre'],
            'nodos':   red['nodos'],
            'aristas': red['aristas'],
            'resumen': {
                'n_origenes':   sum(1 for n in red['nodos'] if n['tipo'] == 'origen'),
                'n_transitos':  sum(1 for n in red['nodos'] if n['tipo'] == 'transito'),
                'n_destinos':   sum(1 for n in red['nodos'] if n['tipo'] == 'destino'),
                'n_aristas':    len(red['aristas']),
                'oferta_total': sum(n.get('oferta', 0) for n in red['nodos'] if n['tipo'] == 'origen'),
                'demanda_total':sum(n.get('demanda', 0) for n in red['nodos'] if n['tipo'] == 'destino'),
            }
        })
    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


# ── Optimización LP + Grafos ─────────────────────────────────────────────────

@app.route('/api/acuicola/optimizar', methods=['GET'])
def optimizar():
    """
    Resuelve el modelo de Programación Lineal y ejecuta algoritmos de grafos.

    Parámetros GET:
        origen          — nodo origen para Dijkstra/BF     (default: O1)
        destino         — nodo destino para Dijkstra/BF    (default: D1)
        algoritmo_grafo — 'dijkstra' | 'bellman_ford'      (default: dijkstra)
        fuente_flujo    — nodo fuente para flujo máximo    (default: O1)
        sumidero_flujo  — nodo sumidero para flujo máximo  (default: D1)
    """
    try:
        red = _red()

        # ── Validar nodos de entrada ─────────────────────────────────────────
        origen   = request.args.get('origen',         'O1')
        destino  = request.args.get('destino',         'D1')
        fuente   = request.args.get('fuente_flujo',   'O1')
        sumidero = request.args.get('sumidero_flujo', 'D1')
        alg      = request.args.get('algoritmo_grafo', 'dijkstra')

        for nid, campo in [(origen, 'origen'), (destino, 'destino'),
                           (fuente, 'fuente_flujo'), (sumidero, 'sumidero_flujo')]:
            err = _validar_nodo(nid, red, campo)
            if err:
                return jsonify({'error': err}), 400

        # ── Resolver LP (con cronómetro incluido dentro de resolver_pl) ──────
        print('Resolviendo LP...')
        t_lp_total = time.perf_counter()
        resultado_pl = resolver_pl(red=red)
        t_lp_total   = round((time.perf_counter() - t_lp_total) * 1000, 2)

        if not resultado_pl['factible']:
            return jsonify({'error': 'LP infactible: ' + resultado_pl.get('error', ''),
                            'resultado_pl': resultado_pl}), 400
        print(f"  LP: {resultado_pl['costo_total']:,.2f} KCOP en {resultado_pl['tiempo_solver_ms']} ms")

        # Construir grafo con flujos LP
        G = construir_grafo(red=red, flujos_pl=resultado_pl['flujos'])

        # Ruta óptima
        ruta_opt = (ruta_bellman_ford(G, origen, destino)
                    if alg == 'bellman_ford'
                    else ruta_dijkstra(G, origen, destino))

        # Flujo máximo
        fm = flujo_maximo(G, fuente, sumidero)

        # Métricas de red
        analisis = analizar_red(G, resultado_pl)

        return jsonify({
            'resultado_pl':      resultado_pl,
            'ruta_optima':       ruta_opt,
            'flujo_maximo':      fm,
            'analisis_red':      analisis,
            'tiempos_ms': {
                'lp_solver':    resultado_pl.get('tiempo_solver_ms'),
                'lp_total':     resultado_pl.get('tiempo_total_ms'),
            },
            'parametros_usados': {
                'origen_ruta':    origen,
                'destino_ruta':   destino,
                'algoritmo':      alg,
                'fuente_flujo':   fuente,
                'sumidero_flujo': sumidero,
            },
        })
    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


# ── Ruta entre dos nodos ──────────────────────────────────────────────────────

@app.route('/api/acuicola/ruta', methods=['GET'])
def ruta_nodos():
    """
    Calcula la ruta óptima entre dos nodos sin resolver el LP completo.

    Parámetros: origen, destino, algoritmo (dijkstra|bellman_ford)
    """
    try:
        red     = _red()
        origen  = request.args.get('origen',    'O1')
        destino = request.args.get('destino',   'D1')
        alg     = request.args.get('algoritmo', 'dijkstra')

        for nid, campo in [(origen, 'origen'), (destino, 'destino')]:
            err = _validar_nodo(nid, red, campo)
            if err:
                return jsonify({'error': err}), 400

        G = construir_grafo(red=red)
        result = (ruta_bellman_ford(G, origen, destino)
                  if alg == 'bellman_ford'
                  else ruta_dijkstra(G, origen, destino))
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


# ── Análisis de sensibilidad ─────────────────────────────────────────────────

@app.route('/api/acuicola/sensibilidad/<int:escenario>', methods=['GET'])
def sensibilidad(escenario):
    """
    Ejecuta uno de los 3 escenarios What-If.

    Escenario 1 — Alza combustible en rutas del Meta
        param: incremento_pct (default: 15)

    Escenario 2 — Cierre de vía principal
        param: arista_id (default: E20)

    Escenario 3 — Pérdida de calidad en centro de acopio
        param: nodo_id (default: T1)
        param: factor_penalizacion (default: 3.0)
    """
    try:
        red = _red()
        if escenario == 1:
            resultado = escenario_combustible_meta(
                incremento_pct=float(request.args.get('incremento_pct', 15.0)),
                red=red)
        elif escenario == 2:
            arista_id = request.args.get('arista_id', 'E20')
            ids_aristas = {a['id'] for a in red['aristas']}
            if arista_id not in ids_aristas:
                return jsonify({'error': f"Arista '{arista_id}' no existe. "
                                         f"IDs válidos: {sorted(ids_aristas)}"}), 400
            resultado = escenario_cierre_via(arista_id=arista_id, red=red)
        elif escenario == 3:
            nodo_id = request.args.get('nodo_id', 'T1')
            err = _validar_nodo(nodo_id, red, 'nodo_id')
            if err:
                return jsonify({'error': err}), 400
            resultado = escenario_calidad_acopio(
                nodo_id=nodo_id,
                factor_penalizacion=float(request.args.get('factor_penalizacion', 3.0)),
                red=red)
        else:
            return jsonify({'error': 'Escenario debe ser 1, 2 o 3'}), 400
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/api/acuicola/sensibilidad/todos', methods=['GET'])
def sensibilidad_todos():
    """Ejecuta los 3 escenarios y devuelve un resumen comparativo."""
    try:
        resultado = ejecutar_todos_los_escenarios(red=_red())
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


# ── Distribución local con Algoritmo Genético ─────────────────────────────────

@app.route('/api/acuicola/distribucion/<transito_id>', methods=['GET'])
def distribucion_local(transito_id):
    """
    Optimiza el orden de entrega de un centro de acopio a sus supermercados
    usando el AG tipo TSP con distancias Haversine.

    Parámetros: tamano_poblacion, generaciones, tasa_cruce, tasa_mutacion,
                elitismo, seed (para reproducibilidad)
    """
    try:
        red = _red()
        err = _validar_nodo(transito_id, red, 'transito_id')
        if err:
            return jsonify({'error': err}), 400

        seed_param = request.args.get('seed')
        resultado = optimizar_distribucion_local(
            transito_id=transito_id,
            red=red,
            tamano_poblacion=int(request.args.get('tamano_poblacion', 80)),
            generaciones=int(request.args.get('generaciones', 150)),
            tasa_cruce=float(request.args.get('tasa_cruce', 0.8)),
            tasa_mutacion=float(request.args.get('tasa_mutacion', 0.15)),
            elitismo=int(request.args.get('elitismo', 2)),
            seed=int(seed_param) if seed_param is not None else None,
        )
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


# ── AG sobre la red completa (flujos + comparación LP) ───────────────────────

@app.route('/api/acuicola/ag_red', methods=['GET'])
def ag_optimizacion_red():
    """
    Optimiza flujos en la red completa con el AG basado en cromosomas de flujo.
    Ejecuta el LP primero para comparar: costo LP vs costo AG, gap porcentual
    y gráfica de convergencia.

    Parámetros GET (todos opcionales):
        transito_id      — hub de referencia para filtrar cobertura por zona (default: T1)
        tamano_poblacion — tamaño de la población (default: 80)
        generaciones     — número de generaciones (default: 150)
        tasa_cruce       — probabilidad de cruce (default: 0.8)
        tasa_mutacion    — probabilidad de mutación por gen (default: 0.15)
        elitismo         — individuos élite (default: 2)
        seed             — semilla aleatoria para reproducibilidad (default: None)
    """
    try:
        red = _red()
        transito_id = request.args.get('transito_id', 'T1')
        if transito_id:
            err = _validar_nodo(transito_id, red, 'transito_id')
            if err:
                return jsonify({'error': err}), 400

        seed_param = request.args.get('seed')

        resultado = optimizar_ag_flujos_red(
            transito_id=transito_id,
            red=red,
            tamano_poblacion=int(request.args.get('tamano_poblacion', 80)),
            generaciones=int(request.args.get('generaciones', 150)),
            tasa_cruce=float(request.args.get('tasa_cruce', 0.8)),
            tasa_mutacion=float(request.args.get('tasa_mutacion', 0.15)),
            elitismo=int(request.args.get('elitismo', 2)),
            seed=int(seed_param) if seed_param is not None else None,
        )
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


# ── Validación de conectividad del grafo ─────────────────────────────────────

@app.route('/api/acuicola/validar_conectividad', methods=['GET'])
def validar_conectividad_red():
    """
    Analiza la conectividad del grafo dirigido y reporta cobertura,
    destinos inalcanzables, nodos aislados y componentes débilmente conexos.
    """
    try:
        red = _red()
        G   = construir_grafo(red=red)
        return jsonify(validar_conectividad(G))
    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


# ── Geometrías de aristas en batch (OSRM con caché) ──────────────────────────

@app.route('/api/acuicola/geometria_aristas', methods=['POST'])
def geometria_aristas_batch():
    """
    Devuelve polilíneas OSRM (calles reales) para una lista de aristas.

    Body JSON:
        {"aristas": [{"id": "E1", "origen": "O1", "destino": "T1"}, ...]}
    """
    try:
        body       = request.get_json(force=True) or {}
        aristas_in = body.get('aristas', [])
        red        = _red()
        nodos_dict = {n['id']: n for n in red['nodos']}

        resultado = {}

        def _fetch(a):
            eid = a.get('id')
            if not eid:
                return None, None
            geo = obtener_geometria_arista(a['origen'], a['destino'], nodos_dict, timeout=5)
            return eid, geo

        with ThreadPoolExecutor(max_workers=10) as ex:
            futures = {ex.submit(_fetch, a): a for a in aristas_in}
            for fut in as_completed(futures):
                eid, geo = fut.result()
                if eid:
                    resultado[eid] = geo

        return jsonify(resultado)
    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


# ── Geometría de ruta real (OSRM) ─────────────────────────────────────────────

@app.route('/api/acuicola/geometria_ruta', methods=['GET'])
def geometria_ruta():
    """
    Devuelve la polilínea OSRM para una secuencia de nodos.

    Parámetro GET:
        nodos — IDs separados por coma (ej: O1,T2,T1,D1)
    """
    try:
        nodos_str = request.args.get('nodos', '').strip()
        if not nodos_str:
            return jsonify({'error': 'Parámetro "nodos" requerido (ej: O1,T2,T1,D1)'}), 400

        ruta_ids = [n.strip() for n in nodos_str.split(',') if n.strip()]
        if len(ruta_ids) < 2:
            return jsonify({'error': 'Se necesitan al menos 2 nodos'}), 400

        red        = _red()
        nodos_dict = {n['id']: n for n in red['nodos']}

        # Validar todos los nodos
        ids_validos = set(nodos_dict.keys())
        invalidos   = [nid for nid in ruta_ids if nid not in ids_validos]
        if invalidos:
            return jsonify({'error': f"Nodos no encontrados: {invalidos}"}), 400

        geometria = obtener_geometria_ruta_real(ruta_ids, nodos_dict)
        return jsonify({
            'ruta':      ruta_ids,
            'geometria': geometria,
            'n_puntos':  len(geometria),
            'fuente':    'osrm' if len(geometria) > len(ruta_ids) + 1 else 'rectas',
        })
    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500




# ── Ruta bajo condiciones de escenario What-If ────────────────────────────────

@app.route('/api/acuicola/ruta_escenario', methods=['GET'])
def ruta_escenario():
    """
    Recalcula la ruta óptima entre dos nodos aplicando las modificaciones
    de un escenario What-If, para ver si la ruta original se vio afectada.

    Parámetros GET:
        origen, destino        — par de nodos (default: O1, D1)
        algoritmo              — 'dijkstra' | 'bellman_ford' (default: dijkstra)
        escenario              — 1, 2 o 3
        # Escenario 1:
        incremento_pct         — % de alza en combustible (default: 15)
        # Escenario 2:
        arista_id              — ID de la arista bloqueada (default: E20)
        # Escenario 3:
        nodo_id                — ID del nodo con calidad degradada (default: T1)
    """
    try:
        red      = _red()
        origen   = request.args.get('origen',    'O1')
        destino  = request.args.get('destino',   'D1')
        algoritmo = request.args.get('algoritmo', 'dijkstra')
        escenario = int(request.args.get('escenario', 1))

        for nid, campo in [(origen, 'origen'), (destino, 'destino')]:
            err = _validar_nodo(nid, red, campo)
            if err:
                return jsonify({'error': err}), 400

        aristas_bloqueadas = []
        factores_costo     = {}

        if escenario == 1:
            # Alza de combustible: subir el peso de aristas desde orígenes Meta
            pct    = float(request.args.get('incremento_pct', 15))
            factor = 1.0 + pct / 100.0
            origenes_meta = {'O1', 'O2', 'O3'}
            factores_costo = {
                a['id']: factor
                for a in red['aristas']
                if a['origen'] in origenes_meta
            }

        elif escenario == 2:
            # Cierre de vía: eliminar la arista del grafo
            arista_id = request.args.get('arista_id', 'E20')
            aristas_bloqueadas = [arista_id]

        elif escenario == 3:
            # Pérdida de calidad: bloquear salidas del nodo afectado
            nodo_id = request.args.get('nodo_id', 'T1')
            aristas_bloqueadas = [
                a['id'] for a in red['aristas']
                if a['origen'] == nodo_id
            ]

        # Construir grafo con aristas bloqueadas
        G = construir_grafo(red=red, aristas_bloqueadas=aristas_bloqueadas)

        # Aplicar factores de costo (escenario 1)
        if factores_costo:
            for u, v, data in G.edges(data=True):
                aid = data.get('arista_id', '')
                if aid in factores_costo:
                    data['costo'] = round(data['costo'] * factores_costo[aid], 4)

        # Calcular ruta con el grafo modificado
        if algoritmo == 'bellman_ford':
            ruta_mod = ruta_bellman_ford(G, origen, destino)
        else:
            ruta_mod = ruta_dijkstra(G, origen, destino)

        # Calcular también la ruta original (sin modificaciones) para comparar
        G_base = construir_grafo(red=red)
        if algoritmo == 'bellman_ford':
            ruta_base = ruta_bellman_ford(G_base, origen, destino)
        else:
            ruta_base = ruta_dijkstra(G_base, origen, destino)

        # Detectar si la ruta cambió
        ruta_cambio = (ruta_base.get('ruta') != ruta_mod.get('ruta'))
        costo_base  = ruta_base.get('costo_total')
        costo_mod   = ruta_mod.get('costo_total')
        delta_costo = round(costo_mod - costo_base, 2) if (costo_base and costo_mod) else None
        delta_pct   = round(delta_costo / costo_base * 100, 2) if (costo_base and delta_costo is not None) else None

        return jsonify({
            'origen':        origen,
            'destino':       destino,
            'escenario':     escenario,
            'ruta_base':     ruta_base,
            'ruta_escenario': ruta_mod,
            'impacto': {
                'ruta_cambio':   ruta_cambio,
                'factible_base': ruta_base.get('factible', False),
                'factible_mod':  ruta_mod.get('factible', False),
                'costo_base':    costo_base,
                'costo_mod':     costo_mod,
                'delta_costo':   delta_costo,
                'delta_pct':     delta_pct,
                'aristas_bloqueadas': aristas_bloqueadas,
            },
        })
    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500

# ── Arranque ──────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('\n' + '='*65)
    print('  ACUICOLA REAL DEL META — Servidor Flask')
    print('='*65)
    print('  GET  /api/health')
    print('  GET  /api/acuicola/red')
    print('  GET  /api/acuicola/optimizar               ?origen=O1&destino=D1&algoritmo_grafo=dijkstra')
    print('  GET  /api/acuicola/ruta                    ?origen=O1&destino=D1&algoritmo=bellman_ford')
    print('  GET  /api/acuicola/sensibilidad/1          ?incremento_pct=15')
    print('  GET  /api/acuicola/sensibilidad/2          ?arista_id=E20')
    print('  GET  /api/acuicola/sensibilidad/3          ?nodo_id=T1&factor_penalizacion=3.0')
    print('  GET  /api/acuicola/sensibilidad/todos')
    print('  GET  /api/acuicola/distribucion/<hub>      ?seed=42&generaciones=150')
    print('  GET  /api/acuicola/ag_red                  ?seed=42&generaciones=150&transito_id=T1')
    print('  POST /api/acuicola/geometria_aristas')
    print('  GET  /api/acuicola/geometria_ruta          ?nodos=O1,T2,T1,D1')
    print('  GET  /api/acuicola/validar_conectividad')
    print('='*65 + '\n')
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
