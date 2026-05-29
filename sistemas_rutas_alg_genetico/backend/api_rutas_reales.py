import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

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

        # Resolver LP
        print('Resolviendo LP...')
        resultado_pl = resolver_pl(red=red)
        if not resultado_pl['factible']:
            return jsonify({'error': 'LP infactible: ' + resultado_pl.get('error', ''),
                            'resultado_pl': resultado_pl}), 400
        print(f"  Costo optimo: {resultado_pl['costo_total']:,.2f} KCOP")

        # Construir grafo con flujos LP
        G = construir_grafo(red=red, flujos_pl=resultado_pl['flujos'])

        # Ruta optima
        origen   = request.args.get('origen', 'O1')
        destino  = request.args.get('destino', 'D1')
        alg      = request.args.get('algoritmo_grafo', 'dijkstra')
        ruta_opt = ruta_bellman_ford(G, origen, destino) if alg == 'bellman_ford' \
                   else ruta_dijkstra(G, origen, destino)

        # Flujo maximo
        fuente   = request.args.get('fuente_flujo',   'O1')
        sumidero = request.args.get('sumidero_flujo', 'D1')
        fm       = flujo_maximo(G, fuente, sumidero)

        # Metricas del grafo
        analisis = analizar_red(G, resultado_pl)

        return jsonify({
            'resultado_pl':      resultado_pl,
            'ruta_optima':       ruta_opt,
            'flujo_maximo':      fm,
            'analisis_red':      analisis,
            'parametros_usados': {
                'origen_ruta':    origen,
                'destino_ruta':   destino,
                'algoritmo':      alg,
                'fuente_flujo':   fuente,
                'sumidero_flujo': sumidero,
            }
        })
    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


# ── Ruta entre dos nodos ──────────────────────────────────────────────────────

@app.route('/api/acuicola/ruta', methods=['GET'])
def ruta_nodos():
    """
    Calcula la ruta optima entre dos nodos sin resolver el LP completo.

    Parámetros: origen, destino, algoritmo (dijkstra|bellman_ford)
    """
    try:
        red     = _red()
        origen  = request.args.get('origen',    'O1')
        destino = request.args.get('destino',   'D1')
        alg     = request.args.get('algoritmo', 'dijkstra')
        G       = construir_grafo(red=red)
        result  = ruta_bellman_ford(G, origen, destino) if alg == 'bellman_ford' \
                  else ruta_dijkstra(G, origen, destino)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


# ── Análisis de sensibilidad ─────────────────────────────────────────────────

@app.route('/api/acuicola/sensibilidad/<int:escenario>', methods=['GET'])
def sensibilidad(escenario):
    """
    Ejecuta uno de los 3 escenarios What-If.

    escenario 1 — Alza combustible +15% en rutas del Meta
        param: incremento_pct (default: 15)
    escenario 2 — Cierre de vía principal
        param: arista_id (default: E20)
    escenario 3 — Pérdida de calidad en centro de acopio
        param: nodo_id (default: T1), factor_penalizacion (default: 3.0)
    """
    try:
        red = _red()
        if escenario == 1:
            resultado = escenario_combustible_meta(
                incremento_pct=float(request.args.get('incremento_pct', 15.0)), red=red)
        elif escenario == 2:
            resultado = escenario_cierre_via(
                arista_id=request.args.get('arista_id', 'E20'), red=red)
        elif escenario == 3:
            resultado = escenario_calidad_acopio(
                nodo_id=request.args.get('nodo_id', 'T1'),
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
    usando el Algoritmo Genético (TSP con distancias Haversine).

    Parámetros: tamano_poblacion, generaciones, tasa_cruce, tasa_mutacion, elitismo
    """
    try:
        resultado = optimizar_distribucion_local(
            transito_id=transito_id,
            red=_red(),
            tamano_poblacion=int(request.args.get('tamano_poblacion', 80)),
            generaciones=int(request.args.get('generaciones', 150)),
            tasa_cruce=float(request.args.get('tasa_cruce', 0.8)),
            tasa_mutacion=float(request.args.get('tasa_mutacion', 0.15)),
            elitismo=int(request.args.get('elitismo', 2)),
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
    y gráfica de convergencia por generación.

    Parámetros GET (todos opcionales):
        transito_id      — hub de referencia para filtrar cobertura por zona (default: T1)
        tamano_poblacion — tamaño de la población (default: 80)
        generaciones     — número de generaciones (default: 150)
        tasa_cruce       — probabilidad de cruce (default: 0.8)
        tasa_mutacion    — probabilidad de mutación por gen (default: 0.15)
        elitismo         — individuos élite (default: 2)
    """
    try:
        resultado = optimizar_ag_flujos_red(
            transito_id=request.args.get('transito_id', 'T1'),
            red=_red(),
            tamano_poblacion=int(request.args.get('tamano_poblacion', 80)),
            generaciones=int(request.args.get('generaciones', 150)),
            tasa_cruce=float(request.args.get('tasa_cruce', 0.8)),
            tasa_mutacion=float(request.args.get('tasa_mutacion', 0.15)),
            elitismo=int(request.args.get('elitismo', 2)),
        )
        return jsonify(resultado)
    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


# ── Validación de conectividad del grafo ─────────────────────────────────────

@app.route('/api/acuicola/validar_conectividad', methods=['GET'])
def validar_conectividad_red():
    """
    Analiza la conectividad del grafo dirigido y reporta:
      - Cobertura de destinos (qué % es alcanzable desde algún origen)
      - Destinos inalcanzables
      - Orígenes sin salida a ningún destino
      - Nodos aislados
      - Componentes débilmente conexos
      - Cobertura por nodo de tránsito
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
    Devuelve polilíneas OSRM (carreteras reales) para una lista de aristas.
    Usa caché en memoria: las aristas ya consultadas no repiten petición HTTP.

    Body JSON:
        {"aristas": [{"id": "E1", "origen": "O1", "destino": "T1"}, ...]}
    Respuesta:
        {"E1": [[lat, lon], ...], ...}
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
    Devuelve la polilínea detallada (calles reales OSM) para una secuencia de nodos.

    Parámetro GET:
        nodos — IDs de nodos separados por coma, en orden (ej: O1,T2,T1,D1)

    Respuesta:
        {
          ruta:     ["O1", "T2", "T1", "D1"],
          geometria: [[lat, lon], ...],   ← muchos puntos siguiendo calles reales
          n_puntos: 1842,
          fuente:   "osrm" | "rectas"
        }
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

        geometria = obtener_geometria_ruta_real(ruta_ids, nodos_dict)

        return jsonify({
            'ruta':      ruta_ids,
            'geometria': geometria,
            'n_puntos':  len(geometria),
            'fuente':    'osrm' if len(geometria) > len(ruta_ids) + 1 else 'rectas',
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
    print('  GET  /api/acuicola/optimizar')
    print('  GET  /api/acuicola/ruta')
    print('  GET  /api/acuicola/sensibilidad/1  (combustible +15%)')
    print('  GET  /api/acuicola/sensibilidad/2  (cierre de vía)')
    print('  GET  /api/acuicola/sensibilidad/3  (pérdida de calidad)')
    print('  GET  /api/acuicola/sensibilidad/todos')
    print('  GET  /api/acuicola/distribucion/<transito_id>  (AG — TSP local)')
    print('  GET  /api/acuicola/ag_red                    (AG — flujos red completa + LP)')
    print('  POST /api/acuicola/geometria_aristas          (OSRM batch con caché)')
    print('  GET  /api/acuicola/validar_conectividad')
    print('='*65 + '\n')
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
