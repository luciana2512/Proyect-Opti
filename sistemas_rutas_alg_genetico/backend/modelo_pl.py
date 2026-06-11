"""
Modelo de Programación Lineal para la Red Logística Acuícola Real del Meta.

Minimiza el costo total de transporte, operación y almacenamiento sujeto a:
  - Equilibrio de flujo en nodos de tránsito (con merma + variable de stock explícita)
  - Capacidad de aristas (camiones)
  - Cumplimiento exacto de demanda en destinos
  - Restricciones de calidad (penalización o bloqueo)

Cambios respecto a versión anterior:
  - costo_almacen_dia y costo_operacion_dia incluidos en la función objetivo
  - Balance de tránsito como igualdad con variable de stock explícita s_t
  - Medición de tiempo de ejecución del solver
"""
import sys
import os
import json
import time
import numpy as np
from scipy.optimize import linprog


def cargar_red():
    ruta = os.path.join(os.path.dirname(__file__), 'red_acuicola.json')
    with open(ruta, 'r', encoding='utf-8') as f:
        return json.load(f)


def resolver_pl(red=None, factores_costo=None, aristas_bloqueadas=None,
                penalizaciones_calidad=None, umbral_calidad=0.70):
    """
    Resuelve el LP de la red logística acuícola.

    Variables de decisión:
        x_e ∈ [0, cap_e]  — flujo (toneladas) en cada arista e
        s_t ∈ [0, cap_t]  — stock residual (toneladas) en cada nodo de tránsito t

    Función objetivo (minimizar):
        Σ_e  x_e × dist_e × costo_e           (costo transporte)
      + Σ_e  x_e × op_origen_e                (costo operación por tonelada despachada)
      + Σ_t  s_t × costo_almacen_t            (costo almacenamiento stock residual)

    Args:
        red:                  dict con datos de la red; si None carga desde archivo.
        factores_costo:       dict {arista_id: factor} para modificar costos (What-if).
        aristas_bloqueadas:   lista de IDs de aristas eliminadas del modelo (What-if).
        penalizaciones_calidad: dict {nodo_id: factor_extra} para calidad baja (What-if).
        umbral_calidad:       calidad mínima aceptable para nodos de tránsito (default 0.70).

    Returns:
        dict con resultado completo del LP, incluyendo tiempo_solver_ms.
    """
    t0 = time.perf_counter()

    if red is None:
        red = cargar_red()
    if factores_costo is None:
        factores_costo = {}
    if aristas_bloqueadas is None:
        aristas_bloqueadas = []
    if penalizaciones_calidad is None:
        penalizaciones_calidad = {}

    nodos = {n['id']: n for n in red['nodos']}

    # ── Filtrar aristas bloqueadas y nodos de tránsito bajo umbral de calidad ─
    aristas = []
    for a in red['aristas']:
        if a['id'] in aristas_bloqueadas:
            continue
        nodo_origen = nodos.get(a['origen'], {})
        # Nodo de tránsito con calidad crítica y sin penalización explícita → bloqueado
        if (nodo_origen.get('tipo') == 'transito' and
                nodo_origen.get('calidad', 1.0) < umbral_calidad and
                a['origen'] not in penalizaciones_calidad):
            continue
        aristas.append(a)

    if not aristas:
        return {'factible': False, 'error': 'No quedan aristas activas en la red.'}

    origenes  = [n for n in red['nodos'] if n['tipo'] == 'origen']
    transitos = [n for n in red['nodos'] if n['tipo'] == 'transito']
    destinos  = [n for n in red['nodos'] if n['tipo'] == 'destino']

    n_aristas  = len(aristas)
    n_transitos = len(transitos)
    n_vars     = n_aristas + n_transitos   # aristas + variables de stock

    arista_idx = {a['id']: i for i, a in enumerate(aristas)}
    stock_idx  = {t['id']: n_aristas + i for i, t in enumerate(transitos)}

    # ── Función objetivo ─────────────────────────────────────────────────────
    c = []

    # — Parte 1: costo por arista —
    for a in aristas:
        costo_transp = float(a['distancia_km']) * float(a['costo_por_ton_km'])

        # Costo de operación del origen prorrateado por tonelada despachada.
        # Modelamos: si un origen despacha flujo x en esta arista, incurre en
        # (costo_operacion_dia / oferta_max) × x unidades de costo operativo.
        nodo_orig = nodos.get(a['origen'], {})
        costo_op = 0.0
        if nodo_orig.get('tipo') == 'origen':
            oferta_max = max(float(nodo_orig.get('oferta', 1)), 1.0)
            costo_op = float(nodo_orig.get('costo_operacion_dia', 0)) / oferta_max

        factor = factores_costo.get(a['id'], 1.0)

        # Penalización de calidad del nodo tránsito en extremos de la arista.
        # Si un centro de acopio tiene calidad degradada, encarecemos su uso.
        pen_dest = penalizaciones_calidad.get(a['destino'], 1.0)
        pen_orig = penalizaciones_calidad.get(a['origen'],  1.0)

        c.append((costo_transp + costo_op) * factor * max(pen_dest, pen_orig))

    # — Parte 2: costo de almacenamiento de stock en nodos de tránsito —
    # Cada tonelada que queda en stock en un centro de acopio al final del día
    # incurre en costo_almacen_dia (KCOP/ton). Esto incentiva al LP a distribuir
    # el producto en lugar de retenerlo sin necesidad.
    for t in transitos:
        c.append(float(t.get('costo_almacen_dia', 0.0)))

    # ── Bounds ───────────────────────────────────────────────────────────────
    bounds = (
        [(0.0, float(a['capacidad_ton'])) for a in aristas]       # flujos
        + [(0.0, float(t['capacidad'])) for t in transitos]        # stocks ≤ cap_t
    )

    A_ub, b_ub = [], []
    A_eq, b_eq = [], []

    # ── Restricción 1: Oferta — salidas de origen ≤ oferta disponible ────────
    for origen in origenes:
        row = [0.0] * n_vars
        for i, a in enumerate(aristas):
            if a['origen'] == origen['id']:
                row[i] = 1.0
        A_ub.append(row)
        b_ub.append(float(origen['oferta']))

    # ── Restricción 2: Balance de tránsito (IGUALDAD con stock explícito) ────
    #    Σ_salidas + s_t = (1 − merma) × Σ_entradas
    #    → s_t absorbe el inventario residual que no se despachó
    #    → la variable de stock tiene costo en el objetivo, incentivando distribuir
    for i, transito in enumerate(transitos):
        row = [0.0] * n_vars
        r = transito.get('merma', 0.0)
        for j, a in enumerate(aristas):
            if a['destino'] == transito['id']:
                row[j] = -(1.0 - r)   # entrada efectiva (tras pérdida por merma)
            if a['origen'] == transito['id']:
                row[j] = 1.0           # salida hacia aguas abajo
        row[stock_idx[transito['id']]] = 1.0   # variable de stock s_t
        A_eq.append(row)
        b_eq.append(0.0)

    # ── Restricción 3: Capacidad de despacho del tránsito ────────────────────
    #    Σ_salidas ≤ capacidad_t  (throughput máximo por período)
    for transito in transitos:
        row = [0.0] * n_vars
        for i, a in enumerate(aristas):
            if a['origen'] == transito['id']:
                row[i] = 1.0
        A_ub.append(row)
        b_ub.append(float(transito['capacidad']))

    # ── Restricción 4: Demanda exacta en destinos ────────────────────────────
    for destino in destinos:
        row = [0.0] * n_vars
        tiene_entrada = False
        for i, a in enumerate(aristas):
            if a['destino'] == destino['id']:
                row[i] = 1.0
                tiene_entrada = True
        A_eq.append(row)
        b_eq.append(float(destino['demanda']))

    A_ub_np = np.array(A_ub, dtype=float) if A_ub else None
    b_ub_np = np.array(b_ub, dtype=float) if b_ub else None
    A_eq_np = np.array(A_eq, dtype=float) if A_eq else None
    b_eq_np = np.array(b_eq, dtype=float) if b_eq else None

    t1 = time.perf_counter()
    resultado = linprog(
        c,
        A_ub=A_ub_np, b_ub=b_ub_np,
        A_eq=A_eq_np, b_eq=b_eq_np,
        bounds=bounds,
        method='highs'
    )
    t2 = time.perf_counter()
    tiempo_solver_ms = round((t2 - t1) * 1000, 2)
    tiempo_total_ms  = round((t2 - t0) * 1000, 2)

    if resultado.status != 0:
        return {
            'factible':         False,
            'error':            resultado.message,
            'status':           resultado.status,
            'costo_total':      None,
            'flujos':           {},
            'tiempo_solver_ms': tiempo_solver_ms,
            'tiempo_total_ms':  tiempo_total_ms,
        }

    # ── Construir respuesta detallada ─────────────────────────────────────────
    flujos = {}
    costo_transporte   = 0.0
    costo_operacion    = 0.0
    ingreso_total      = 0.0

    for a in aristas:
        idx   = arista_idx[a['id']]
        flujo = float(resultado.x[idx])
        factor_costo = factores_costo.get(a['id'], 1.0)
        pen_orig = penalizaciones_calidad.get(a['origen'], 1.0)
        pen_dest = penalizaciones_calidad.get(a['destino'], 1.0)
        factor_total = factor_costo * max(pen_orig, pen_dest)
        costo_arista = flujo * float(a['distancia_km']) * float(a['costo_por_ton_km']) * factor_total
        costo_transporte += costo_arista

        # Costo operativo prorrateado de este despacho
        nodo_orig = nodos.get(a['origen'], {})
        if nodo_orig.get('tipo') == 'origen':
            oferta_max = max(float(nodo_orig.get('oferta', 1)), 1.0)
            costo_operacion += flujo * float(nodo_orig.get('costo_operacion_dia', 0)) / oferta_max

        nodo_dest = nodos.get(a['destino'], {})
        if nodo_dest.get('tipo') == 'destino':
            ingreso_total += flujo * float(nodo_dest.get('precio_venta', 0))

        flujos[a['id']] = {
            'arista_id':    a['id'],
            'origen':       a['origen'],
            'destino':      a['destino'],
            'descripcion':  a.get('descripcion', ''),
            'flujo':        round(flujo, 4),
            'capacidad':    float(a['capacidad_ton']),
            'uso_pct':      round(flujo / a['capacidad_ton'] * 100, 1) if a['capacidad_ton'] > 0 else 0,
            'costo_arista': round(costo_arista, 2),
            'activa':       flujo > 0.01,
        }

    # Stock en nodos de tránsito y costo de almacenamiento
    stock_por_nodo    = {}
    costo_almacen_total = 0.0
    for i, t in enumerate(transitos):
        stock = float(resultado.x[n_aristas + i])
        costo_alm = stock * float(t.get('costo_almacen_dia', 0.0))
        costo_almacen_total += costo_alm
        stock_por_nodo[t['id']] = {
            'nombre':        t['nombre'],
            'stock_ton':     round(stock, 3),
            'costo_almacen': round(costo_alm, 2),
        }

    costo_total = costo_transporte + costo_operacion + costo_almacen_total

    # Flujo por nodo (para compatibilidad con frontend)
    flujo_por_nodo = {}
    for n in red['nodos']:
        nid    = n['id']
        entrada = sum(flujos[a['id']]['flujo'] for a in aristas
                      if a['destino'] == nid and a['id'] in flujos)
        salida  = sum(flujos[a['id']]['flujo'] for a in aristas
                      if a['origen']  == nid and a['id'] in flujos)
        flujo_por_nodo[nid] = {
            'entrada_ton': round(entrada, 3),
            'salida_ton':  round(salida,  3),
            'stock_ton':   round(stock_por_nodo.get(nid, {}).get('stock_ton', 0), 3),
        }

    # Cuellos de botella: aristas con uso ≥ 90%
    cuellos_botella = [
        fid for fid, f in flujos.items()
        if f['uso_pct'] >= 90 and f['flujo'] > 0.01
    ]

    ganancia_valor = round(ingreso_total - costo_total, 2)

    return {
        'factible':               True,
        'viable':                 ganancia_valor >= 0,
        'razon_inviable':         'Ganancia negativa: los costos superan el ingreso total.' if ganancia_valor < 0 else None,
        'costo_total':            round(costo_total, 2),
        'costo_transporte':       round(costo_transporte, 2),
        'costo_operacion':        round(costo_operacion, 2),
        'costo_almacen':          round(costo_almacen_total, 2),
        'ingreso_total':          round(ingreso_total, 2),
        'ganancia':               ganancia_valor,
        'flujos':                 flujos,
        'flujo_por_nodo':         flujo_por_nodo,
        'stock_por_nodo':         stock_por_nodo,
        'cuellos_botella':        cuellos_botella,
        'total_aristas_activas':  sum(1 for f in flujos.values() if f['activa']),
        'solver_message':         resultado.message,
        'demanda_total':          sum(float(d['demanda']) for d in destinos),
        'oferta_total':           sum(float(o['oferta'])  for o in origenes),
        'tiempo_solver_ms':       tiempo_solver_ms,
        'tiempo_total_ms':        tiempo_total_ms,
    }


def calcular_costo_arista(a):
    """Costo unitario de transporte de una arista (KCOP/ton)."""
    return float(a['distancia_km']) * float(a['costo_por_ton_km'])


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    print("=== Resolviendo LP Red Acuícola ===")
    r = resolver_pl()
    if r['factible']:
        print(f"  FACTIBLE  ({r['tiempo_solver_ms']} ms solver / {r['tiempo_total_ms']} ms total)")
        print(f"  Costo transporte: {r['costo_transporte']:>12,.2f} KCOP")
        print(f"  Costo operación:  {r['costo_operacion']:>12,.2f} KCOP")
        print(f"  Costo almacén:    {r['costo_almacen']:>12,.2f} KCOP")
        print(f"  Costo TOTAL:      {r['costo_total']:>12,.2f} KCOP")
        print(f"  Ingreso total:    {r['ingreso_total']:>12,.2f} KCOP")
        print(f"  Ganancia:         {r['ganancia']:>12,.2f} KCOP")
        print(f"  Aristas activas:  {r['total_aristas_activas']}")
        print(f"  Cuellos botella:  {r['cuellos_botella']}")
    else:
        print(f"  INFACTIBLE: {r['error']}")
