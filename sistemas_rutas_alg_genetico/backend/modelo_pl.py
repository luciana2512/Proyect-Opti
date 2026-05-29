"""
Modelo de Programación Lineal para la Red Logística Acuícola Real del Meta.

Minimiza el costo total de transporte y operación sujeto a:
  - Equilibrio de flujo en nodos de tránsito (con merma)
  - Capacidad de aristas (camiones)
  - Cumplimiento exacto de demanda en destinos
  - Restricciones de calidad (penalización o bloqueo)
"""
import sys
import os
import json
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

    Args:
        red: dict con datos de la red; si None carga desde archivo.
        factores_costo: dict {arista_id: factor_multiplicador} para modificar costos.
        aristas_bloqueadas: lista de IDs de aristas eliminadas del modelo.
        penalizaciones_calidad: dict {nodo_id: factor_extra_costo} para calidad baja.
        umbral_calidad: calidad mínima aceptable (default 0.70).

    Returns:
        dict con resultado completo del LP.
    """
    if red is None:
        red = cargar_red()
    if factores_costo is None:
        factores_costo = {}
    if aristas_bloqueadas is None:
        aristas_bloqueadas = []
    if penalizaciones_calidad is None:
        penalizaciones_calidad = {}

    nodos = {n['id']: n for n in red['nodos']}

    # Filtrar aristas bloqueadas y aplicar restricciones de calidad por nodo
    aristas = []
    for a in red['aristas']:
        if a['id'] in aristas_bloqueadas:
            continue
        nodo_origen = nodos.get(a['origen'], {})
        # Si el nodo origen de tránsito tiene calidad por debajo del umbral → bloqueado
        if (nodo_origen.get('tipo') == 'transito' and
                nodo_origen.get('calidad', 1.0) < umbral_calidad and
                a['id'] not in penalizaciones_calidad):
            continue
        aristas.append(a)

    if not aristas:
        return {'factible': False, 'error': 'No quedan aristas activas en la red.'}

    origenes  = [n for n in red['nodos'] if n['tipo'] == 'origen']
    transitos = [n for n in red['nodos'] if n['tipo'] == 'transito']
    destinos  = [n for n in red['nodos'] if n['tipo'] == 'destino']

    n_vars = len(aristas)
    arista_idx = {a['id']: i for i, a in enumerate(aristas)}

    # ── Función objetivo: minimizar costo total de transporte ─────────────────
    c = []
    for a in aristas:
        costo_base = float(a['distancia_km']) * float(a['costo_por_ton_km'])
        factor     = factores_costo.get(a['id'], 1.0)
        # Penalización de calidad en el nodo de tránsito destino de la arista
        pen_destino = penalizaciones_calidad.get(a['destino'], 1.0)
        pen_origen  = penalizaciones_calidad.get(a['origen'],  1.0)
        c.append(costo_base * factor * max(pen_destino, pen_origen))

    # ── Bounds: 0 ≤ x_e ≤ cap_e ──────────────────────────────────────────────
    bounds = [(0.0, float(a['capacidad_ton'])) for a in aristas]

    A_ub, b_ub = [], []
    A_eq, b_eq = [], []

    # ── 1. Oferta: suma de salidas de cada origen ≤ oferta ───────────────────
    for origen in origenes:
        row = [0.0] * n_vars
        for i, a in enumerate(aristas):
            if a['origen'] == origen['id']:
                row[i] = 1.0
        A_ub.append(row)
        b_ub.append(float(origen['oferta']))

    # ── 2. Balance de flujo en tránsito: salidas ≤ entradas × (1 − merma) ───
    #    ⟺  Σ_salidas − (1−r)·Σ_entradas ≤ 0
    for transito in transitos:
        row = [0.0] * n_vars
        r = transito.get('merma', 0.0)
        for i, a in enumerate(aristas):
            if a['destino'] == transito['id']:
                row[i] = -(1.0 - r)   # entrada efectiva (negativa en la inecuación)
            if a['origen'] == transito['id']:
                row[i] = 1.0          # salida
        A_ub.append(row)
        b_ub.append(0.0)

    # ── 3. Capacidad de almacenamiento: suma de salidas de tránsito ≤ cap ────
    for transito in transitos:
        row = [0.0] * n_vars
        for i, a in enumerate(aristas):
            if a['origen'] == transito['id']:
                row[i] = 1.0
        A_ub.append(row)
        b_ub.append(float(transito['capacidad']))

    # ── 4. Demanda exacta en destinos ────────────────────────────────────────
    for destino in destinos:
        row = [0.0] * n_vars
        tiene_entrada = False
        for i, a in enumerate(aristas):
            if a['destino'] == destino['id']:
                row[i] = 1.0
                tiene_entrada = True
        if tiene_entrada:
            A_eq.append(row)
            b_eq.append(float(destino['demanda']))
        else:
            # Destino inaccesible → agregar como restricción infactible de costo cero
            # (se manejará en el status del solver)
            A_eq.append(row)
            b_eq.append(float(destino['demanda']))

    A_ub_np = np.array(A_ub, dtype=float) if A_ub else None
    b_ub_np = np.array(b_ub, dtype=float) if b_ub else None
    A_eq_np = np.array(A_eq, dtype=float) if A_eq else None
    b_eq_np = np.array(b_eq, dtype=float) if b_eq else None

    resultado = linprog(
        c,
        A_ub=A_ub_np, b_ub=b_ub_np,
        A_eq=A_eq_np, b_eq=b_eq_np,
        bounds=bounds,
        method='highs'
    )

    if resultado.status != 0:
        return {
            'factible': False,
            'error': resultado.message,
            'status': resultado.status,
            'costo_total': None,
            'flujos': {}
        }

    # ── Construir respuesta detallada ─────────────────────────────────────────
    flujos = {}
    costo_total = 0.0
    ingreso_total = 0.0

    for a in aristas:
        idx   = arista_idx[a['id']]
        flujo = float(resultado.x[idx])
        costo_arista = flujo * float(a['distancia_km']) * float(a['costo_por_ton_km'])
        costo_total += costo_arista

        nodo_dest = nodos.get(a['destino'], {})
        if nodo_dest.get('tipo') == 'destino':
            ingreso_total += flujo * float(nodo_dest.get('precio_venta', 0))

        flujos[a['id']] = {
            'arista_id':   a['id'],
            'origen':      a['origen'],
            'destino':     a['destino'],
            'descripcion': a.get('descripcion', ''),
            'flujo':       round(flujo, 4),
            'capacidad':   float(a['capacidad_ton']),
            'uso_pct':     round(flujo / a['capacidad_ton'] * 100, 1) if a['capacidad_ton'] > 0 else 0,
            'costo_arista':round(costo_arista, 2),
            'activa':      flujo > 0.01
        }

    # Cuellos de botella: aristas con uso ≥ 90%
    cuellos_botella = [
        fid for fid, f in flujos.items()
        if f['uso_pct'] >= 90 and f['flujo'] > 0.01
    ]

    # Flujo por nodo
    flujo_por_nodo = {}
    for n in red['nodos']:
        nid = n['id']
        entrada = sum(
            flujos[a['id']]['flujo']
            for a in aristas if a['destino'] == nid and a['id'] in flujos
        )
        salida = sum(
            flujos[a['id']]['flujo']
            for a in aristas if a['origen'] == nid and a['id'] in flujos
        )
        flujo_por_nodo[nid] = {
            'entrada_ton': round(entrada, 3),
            'salida_ton':  round(salida,  3),
            'stock_ton':   round(max(0, entrada * (1 - n.get('merma', 0)) - salida), 3)
        }

    return {
        'factible':         True,
        'costo_total':      round(costo_total, 2),
        'ingreso_total':    round(ingreso_total, 2),
        'ganancia':         round(ingreso_total - costo_total, 2),
        'flujos':           flujos,
        'flujo_por_nodo':  flujo_por_nodo,
        'cuellos_botella': cuellos_botella,
        'total_aristas_activas': sum(1 for f in flujos.values() if f['activa']),
        'solver_message':   resultado.message,
        'demanda_total':    sum(d['demanda'] for d in destinos),
        'oferta_total':     sum(o['oferta']  for o in origenes),
    }


def calcular_costo_arista(a):
    """Costo unitario de una arista (KCOP/ton)."""
    return float(a['distancia_km']) * float(a['costo_por_ton_km'])


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    print("=== Resolviendo LP Red Acuícola ===")
    resultado = resolver_pl()
    if resultado['factible']:
        print(f"FACTIBLE")
        print(f"  Costo total:   {resultado['costo_total']:,.2f} KCOP")
        print(f"  Ingreso total: {resultado['ingreso_total']:,.2f} KCOP")
        print(f"  Ganancia:      {resultado['ganancia']:,.2f} KCOP")
        print(f"  Aristas activas: {resultado['total_aristas_activas']}")
        print(f"  Cuellos de botella: {resultado['cuellos_botella']}")
    else:
        print(f"INFACTIBLE: {resultado['error']}")
