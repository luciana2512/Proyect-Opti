"""
analisis_sensibilidad.py — Análisis de Sensibilidad (Escenarios What-If)
=========================================================================
Red Logística Acuícola Real del Meta · Proyecto Final 2026-1

Implementa los 3 escenarios críticos solicitados en el proyecto:

Escenario 1 — Alza de combustible en el Meta
    Incrementa el costo por tonelada-km en un % configurable para todas
    las aristas que salen de los orígenes del Meta (O1, O2, O3).

Escenario 2 — Cierre de una vía principal
    Elimina una arista del modelo (simula bloqueo, desastre o mantenimiento).
    El LP busca rutas alternativas o declara infactibilidad.

Escenario 3 — Pérdida masiva de calidad en un centro de acopio
    Baja la calidad de un nodo de tránsito al 35% (umbral mínimo: 40%).
    Bloquea o penaliza sus aristas de salida según el factor configurado.

Cada escenario retorna una comparativa base vs escenario con:
    · Δ Costo total (KCOP y %)   · Δ Ganancia (KCOP)
    · Top 5 cambios de flujo     · Cuellos de botella nuevos
    · Estado (factible / infactible)

Funciones públicas:
    escenario_combustible_meta(incremento_pct, red)        → dict
    escenario_cierre_via(arista_id, red)                   → dict
    escenario_calidad_acopio(nodo_id, factor_penalizacion) → dict
    ejecutar_todos_los_escenarios(red)                     → dict
"""
import json
import os
from modelo_pl import resolver_pl, cargar_red


def _cargar_red():
    return cargar_red()


def ejecutar_escenario_base(red=None):
    """Resuelve el LP en condiciones normales para usarlo como referencia."""
    if red is None:
        red = _cargar_red()
    return resolver_pl(red=red)


# ─── Escenario 1 ─────────────────────────────────────────────────────────────

def escenario_combustible_meta(incremento_pct=15.0, red=None):
    """
    Escenario 1: Aumento del {incremento_pct}% en el costo de combustible
    para todas las aristas que salen de orígenes del Meta (O1, O2, O3).

    Modela el impacto de un alza de precios de combustible en la región llanera.
    """
    if red is None:
        red = _cargar_red()

    origenes_meta = {'O1', 'O2', 'O3'}
    factor = 1.0 + incremento_pct / 100.0

    factores_costo = {
        a['id']: factor
        for a in red['aristas']
        if a['origen'] in origenes_meta
    }

    base    = ejecutar_escenario_base(red)
    nuevo   = resolver_pl(red=red, factores_costo=factores_costo)

    aristas_afectadas = [
        {'arista_id': aid, 'descripcion': next(
            (a['descripcion'] for a in red['aristas'] if a['id'] == aid), ''
        )}
        for aid in factores_costo
    ]

    return _formatear_resultado(
        escenario=1,
        nombre=f"Alza de combustible +{incremento_pct}% en rutas del Meta",
        descripcion=(
            f"Se incrementa el costo por tonelada-km en un {incremento_pct}% "
            f"para todas las rutas que salen de las estaciones del Meta "
            f"(Est. Villavicencio, Puerto López y San Martín). "
            f"Esto presiona al sistema a redirigir flujos por rutas de Cundinamarca."
        ),
        parametro_modificado=f"Factor de costo: ×{factor:.2f} en {len(factores_costo)} aristas",
        aristas_afectadas=aristas_afectadas,
        resultado_base=base,
        resultado_nuevo=nuevo
    )


# ─── Escenario 2 ─────────────────────────────────────────────────────────────

def escenario_cierre_via(arista_id='E20', red=None):
    """
    Escenario 2: Cierre de la vía principal identificada por arista_id.

    Por defecto cierra E20 (Hub Bogotá → Cali), que es la única ruta
    directa hacia el suroccidente del país.
    Permite evaluar si el sistema puede redirigir el flujo por rutas alternas.
    """
    if red is None:
        red = _cargar_red()

    arista_info = next((a for a in red['aristas'] if a['id'] == arista_id), None)
    if arista_info is None:
        return {'error': f'Arista {arista_id} no encontrada en la red.'}

    base  = ejecutar_escenario_base(red)
    nuevo = resolver_pl(red=red, aristas_bloqueadas=[arista_id])

    return _formatear_resultado(
        escenario=2,
        nombre=f"Cierre de vía: {arista_info.get('descripcion', arista_id)}",
        descripcion=(
            f"Se bloquea completamente la arista {arista_id} "
            f"({arista_info.get('descripcion', '')}). "
            f"Este escenario simula el cierre de una vía por desastres naturales, "
            f"bloqueos o mantenimiento vial prolongado. "
            f"El sistema debe encontrar rutas alternativas o declarar infactibilidad."
        ),
        parametro_modificado=f"Arista bloqueada: {arista_id} — "
                              f"{arista_info.get('descripcion', '')} "
                              f"(cap: {arista_info.get('capacidad_ton')} ton, "
                              f"{arista_info.get('distancia_km')} km)",
        aristas_afectadas=[{'arista_id': arista_id,
                             'descripcion': arista_info.get('descripcion', '')}],
        resultado_base=base,
        resultado_nuevo=nuevo
    )


# ─── Escenario 3 ─────────────────────────────────────────────────────────────

def escenario_calidad_acopio(nodo_id='T1', factor_penalizacion=3.0, red=None):
    """
    Escenario 3: Pérdida masiva de calidad en un centro de acopio.

    Por defecto afecta T1 (Hub Bogotá), el nodo más crítico de la red.
    Se triplica el costo de las aristas que salen del nodo afectado
    para modelar el impacto económico de rechazos de calidad, devoluciones
    y penalizaciones contractuales.
    Si la calidad cae por debajo del umbral de 0.40, el nodo se bloquea
    completamente (flujo se detiene).
    """
    if red is None:
        red = _cargar_red()

    # Reducir la calidad del nodo en la copia de la red
    red_modificada = json.loads(json.dumps(red))  # deep copy
    nodo_encontrado = False
    for nodo in red_modificada['nodos']:
        if nodo['id'] == nodo_id:
            nodo['calidad'] = 0.35    # calidad crítica
            nodo_encontrado = True
            break

    if not nodo_encontrado:
        return {'error': f'Nodo {nodo_id} no encontrado.'}

    # Aristas de salida del nodo afectado → penalización de costo
    penalizaciones = {
        a['id']: factor_penalizacion
        for a in red['aristas']
        if a['origen'] == nodo_id
    }

    nodo_info = next((n for n in red['nodos'] if n['id'] == nodo_id), {})
    aristas_afectadas = [
        {'arista_id': aid, 'descripcion': next(
            (a['descripcion'] for a in red['aristas'] if a['id'] == aid), ''
        )}
        for aid in penalizaciones
    ]

    base  = ejecutar_escenario_base(red)
    nuevo = resolver_pl(
        red=red_modificada,
        penalizaciones_calidad={nodo_id: factor_penalizacion},
        umbral_calidad=0.40
    )

    return _formatear_resultado(
        escenario=3,
        nombre=f"Pérdida de calidad en {nodo_info.get('nombre', nodo_id)}",
        descripcion=(
            f"Se detecta una pérdida masiva de calidad en el nodo {nodo_id} "
            f"({nodo_info.get('nombre', '')}). "
            f"La calidad cae de {nodo_info.get('calidad', 1.0):.0%} a 35%, "
            f"por debajo del umbral mínimo (40%). "
            f"El sistema aplica una penalización de {factor_penalizacion}× en el costo "
            f"de todas las salidas del nodo o redirige el flujo por nodos alternos. "
            f"Si el nodo cae por debajo del umbral, sus aristas son bloqueadas."
        ),
        parametro_modificado=f"Calidad de {nodo_id}: 95% → 35% | "
                              f"Penalización: ×{factor_penalizacion} en {len(penalizaciones)} aristas",
        aristas_afectadas=aristas_afectadas,
        resultado_base=base,
        resultado_nuevo=nuevo
    )


# ─── Formateador de resultados ────────────────────────────────────────────────

def _formatear_resultado(escenario, nombre, descripcion, parametro_modificado,
                          aristas_afectadas, resultado_base, resultado_nuevo):
    """Construye el dict de respuesta unificado para todos los escenarios."""
    base_costo = resultado_base.get('costo_total') or 0
    nuevo_costo = resultado_nuevo.get('costo_total') or 0
    factible_nuevo = resultado_nuevo.get('factible', False)

    delta_costo = nuevo_costo - base_costo if factible_nuevo else None
    delta_pct   = (delta_costo / base_costo * 100) if (factible_nuevo and base_costo > 0 and delta_costo is not None) else None

    base_gan  = resultado_base.get('ganancia', 0) or 0
    nuevo_gan = resultado_nuevo.get('ganancia', 0) if factible_nuevo else None
    delta_gan = (nuevo_gan - base_gan) if nuevo_gan is not None else None

    # Aristas que cambiaron de flujo significativamente
    cambios_flujo = []
    if factible_nuevo:
        flujos_base  = resultado_base.get('flujos', {})
        flujos_nuevo = resultado_nuevo.get('flujos', {})
        for aid in set(list(flujos_base.keys()) + list(flujos_nuevo.keys())):
            f_base  = flujos_base.get(aid, {}).get('flujo', 0)
            f_nuevo = flujos_nuevo.get(aid, {}).get('flujo', 0)
            delta   = abs(f_nuevo - f_base)
            if delta > 0.1:
                cambios_flujo.append({
                    'arista_id': aid,
                    'flujo_base':  round(f_base, 3),
                    'flujo_nuevo': round(f_nuevo, 3),
                    'delta':       round(f_nuevo - f_base, 3),
                    'descripcion': flujos_base.get(aid, flujos_nuevo.get(aid, {})).get('descripcion', '')
                })
        cambios_flujo.sort(key=lambda x: abs(x['delta']), reverse=True)

    return {
        'escenario':            escenario,
        'nombre':               nombre,
        'descripcion':          descripcion,
        'parametro_modificado': parametro_modificado,
        'aristas_afectadas':    aristas_afectadas,
        'resultado_base': {
            'factible':      resultado_base.get('factible', False),
            'costo_total':   round(base_costo, 2),
            'ganancia':      round(base_gan, 2),
            'ingreso_total': round(resultado_base.get('ingreso_total', 0) or 0, 2),
        },
        'resultado_nuevo': {
            'factible':       factible_nuevo,
            'costo_total':    round(nuevo_costo, 2) if factible_nuevo else None,
            'ganancia':       round(nuevo_gan, 2)   if nuevo_gan is not None else None,
            'ingreso_total':  round(resultado_nuevo.get('ingreso_total', 0) or 0, 2) if factible_nuevo else None,
            'error':          resultado_nuevo.get('error') if not factible_nuevo else None,
        },
        'impacto': {
            'delta_costo_kcop':   round(delta_costo, 2)  if delta_costo is not None else None,
            'delta_costo_pct':    round(delta_pct, 2)    if delta_pct   is not None else None,
            'delta_ganancia_kcop':round(delta_gan, 2)    if delta_gan   is not None else None,
            'sistema_factible':   factible_nuevo,
            'mensaje': (
                'El sistema absorbe el impacto y redirige flujos óptimamente.'
                if factible_nuevo else
                'El sistema no puede satisfacer toda la demanda. Se requieren medidas de contingencia.'
            )
        },
        'cambios_flujo_top5':   cambios_flujo[:5],
        'cuellos_botella_nuevo': resultado_nuevo.get('cuellos_botella', []) if factible_nuevo else [],
    }


def ejecutar_todos_los_escenarios(red=None):
    """Ejecuta los 3 escenarios y devuelve un resumen comparativo."""
    if red is None:
        red = _cargar_red()

    base = ejecutar_escenario_base(red)
    e1   = escenario_combustible_meta(red=red)
    e2   = escenario_cierre_via(red=red)
    e3   = escenario_calidad_acopio(red=red)

    return {
        'base':       base,
        'escenarios': [e1, e2, e3]
    }