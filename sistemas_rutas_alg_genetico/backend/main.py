"""
main.py — Punto de entrada standalone para la Red Logística Acuícola Real del Meta.

Ejecuta en consola:
  1. Modelo de Programación Lineal (solución exacta)
  2. Algoritmo Genético de Flujos (solución heurística)

bajo los mismos datos de entrada y genera una tabla comparativa con:
  - Costo total de la solución
  - Tiempo de ejecución (ms)
  - Factibilidad (¿se cumple el 100% de restricciones?)
  - Gap porcentual respecto al óptimo LP

Uso:
    python main.py
    python main.py --seed 42
    python main.py --generaciones 300 --poblacion 100 --seed 7
"""
import sys
import argparse
import time

sys.stdout.reconfigure(encoding='utf-8')

from modelo_pl import resolver_pl, cargar_red
from genetic_algorithm import algoritmo_genetico_flujos


# ─── Helpers de formato ───────────────────────────────────────────────────────

def _sep(char='─', n=65):
    return char * n

def _fmt_costo(v):
    return f"{v:>14,.2f} KCOP" if v is not None else f"{'—':>14}"

def _fmt_tiempo(v):
    return f"{v:>10.1f} ms" if v is not None else f"{'—':>10}"

def _fmt_pct(v):
    return f"{v:>8.2f} %" if v is not None else f"{'—':>8}"


# ─── Verificar factibilidad del cromosoma AG ──────────────────────────────────

def _evaluar_factibilidad_ag(cromosoma, red, tol=0.5):
    """
    Devuelve (factible, violacion_total, cobertura_por_destino).
    Un individuo es factible si la violación total de demanda < tol toneladas.
    """
    aristas    = red['aristas']
    nodos_dict = {n['id']: n for n in red['nodos']}

    flujo_entrada = {}
    for i, a in enumerate(aristas):
        flujo_entrada[a['destino']] = flujo_entrada.get(a['destino'], 0.0) + cromosoma[i]

    cobertura = []
    violacion = 0.0
    for n in red['nodos']:
        if n['tipo'] == 'destino':
            dem  = float(n.get('demanda', 0))
            rec  = flujo_entrada.get(n['id'], 0.0)
            dev  = abs(rec - dem)
            violacion += dev
            cobertura.append({
                'id':       n['id'],
                'nombre':   n['nombre'],
                'demanda':  dem,
                'recibido': round(rec, 3),
                'desvio':   round(dev, 3),
                'ok':       dev < tol,
            })

    return violacion < tol, round(violacion, 3), cobertura


# ─── Punto de entrada principal ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Comparación LP vs AG — Red Logística Acuícola Real del Meta'
    )
    parser.add_argument('--seed',         type=int, default=None,
                        help='Semilla aleatoria para el AG (reproducibilidad)')
    parser.add_argument('--generaciones', type=int, default=150,
                        help='Generaciones del AG (default: 150)')
    parser.add_argument('--poblacion',    type=int, default=80,
                        help='Tamaño de población del AG (default: 80)')
    parser.add_argument('--tasa_cruce',   type=float, default=0.8)
    parser.add_argument('--tasa_mutacion',type=float, default=0.15)
    parser.add_argument('--elitismo',     type=int,   default=2)
    parser.add_argument('--penalizacion', type=float, default=100_000.0,
                        help='Factor de penalización del AG por restricción violada')
    args = parser.parse_args()

    print()
    print(_sep('═'))
    print('  ACUÍCOLA REAL DEL META — Comparación LP vs Algoritmo Genético')
    print(_sep('═'))

    # ── Cargar red ────────────────────────────────────────────────────────────
    red = cargar_red()
    origenes  = [n for n in red['nodos'] if n['tipo'] == 'origen']
    transitos = [n for n in red['nodos'] if n['tipo'] == 'transito']
    destinos  = [n for n in red['nodos'] if n['tipo'] == 'destino']

    print(f"\n  Red: {red.get('nombre', 'Acuícola')}")
    print(f"  Orígenes:   {len(origenes)} | Tránsitos: {len(transitos)} | "
          f"Destinos: {len(destinos)} | Aristas: {len(red['aristas'])}")
    print(f"  Oferta total:  {sum(float(o.get('oferta',0)) for o in origenes):.1f} ton")
    print(f"  Demanda total: {sum(float(d.get('demanda',0)) for d in destinos):.1f} ton")
    print()

    # ──────────────────────────────────────────────────────────────────────────
    # 1. PROGRAMACIÓN LINEAL
    # ──────────────────────────────────────────────────────────────────────────
    print(_sep())
    print('  [1/2] Resolviendo Programación Lineal (scipy HiGHS)...')
    print(_sep())

    res_lp = resolver_pl(red=red)

    lp_factible      = res_lp.get('factible', False)
    lp_costo         = res_lp.get('costo_total')
    lp_costo_transp  = res_lp.get('costo_transporte')
    lp_costo_almacen = res_lp.get('costo_almacen')
    lp_costo_op      = res_lp.get('costo_operacion')
    lp_ingreso       = res_lp.get('ingreso_total')
    lp_ganancia      = res_lp.get('ganancia')
    lp_tiempo_ms     = res_lp.get('tiempo_solver_ms')

    if lp_factible:
        print(f"  Resultado:        FACTIBLE ✅")
        print(f"  Costo transporte: {_fmt_costo(lp_costo_transp)}")
        print(f"  Costo operación:  {_fmt_costo(lp_costo_op)}")
        print(f"  Costo almacén:    {_fmt_costo(lp_costo_almacen)}")
        print(f"  Costo TOTAL:      {_fmt_costo(lp_costo)}")
        print(f"  Ingreso total:    {_fmt_costo(lp_ingreso)}")
        print(f"  Ganancia:         {_fmt_costo(lp_ganancia)}")
        print(f"  Aristas activas:  {res_lp.get('total_aristas_activas')}")
        print(f"  Cuellos botella:  {res_lp.get('cuellos_botella', [])}")
        print(f"  Tiempo solver:    {_fmt_tiempo(lp_tiempo_ms)}")
    else:
        print(f"  Resultado:  INFACTIBLE ❌")
        print(f"  Error: {res_lp.get('error')}")
        lp_costo = None

    print()

    # ──────────────────────────────────────────────────────────────────────────
    # 2. ALGORITMO GENÉTICO DE FLUJOS
    # ──────────────────────────────────────────────────────────────────────────
    print(_sep())
    print(f"  [2/2] Ejecutando Algoritmo Genético de Flujos...")
    print(f"        Población: {args.poblacion} | Generaciones: {args.generaciones} | "
          f"Semilla: {args.seed if args.seed is not None else 'aleatoria'}")
    print(_sep())

    res_ag = algoritmo_genetico_flujos(
        red=red,
        tamano_poblacion=args.poblacion,
        generaciones=args.generaciones,
        tasa_cruce=args.tasa_cruce,
        tasa_mutacion=args.tasa_mutacion,
        elitismo=args.elitismo,
        penalizacion=args.penalizacion,
        seed=args.seed,
        verbose=True,
    )

    ag_costo   = res_ag['costo_transporte']
    ag_tiempo  = res_ag['tiempo_ms']
    cromosoma  = res_ag['mejor_cromosoma']

    ag_factible, ag_violacion, ag_cobertura = _evaluar_factibilidad_ag(cromosoma, red)

    print(f"\n  Resultado:        {'FACTIBLE ✅' if ag_factible else 'INFACTIBLE ❌'}")
    print(f"  Costo transporte: {_fmt_costo(ag_costo)}")
    print(f"  Violación demanda:{ag_violacion:.3f} ton")
    print(f"  Tiempo total:     {_fmt_tiempo(ag_tiempo)}")

    # Destinos no cubiertos
    no_cubiertos = [c for c in ag_cobertura if not c['ok']]
    if no_cubiertos:
        print(f"\n  ⚠ Destinos con desvío > 0.5 ton ({len(no_cubiertos)}):")
        for c in no_cubiertos[:5]:
            print(f"    {c['id']:4s} {c['nombre']:35s}  "
                  f"demanda={c['demanda']:.1f}  recibido={c['recibido']:.1f}  "
                  f"desvío={c['desvio']:.3f}")
        if len(no_cubiertos) > 5:
            print(f"    ... y {len(no_cubiertos)-5} más")

    print()

    # ──────────────────────────────────────────────────────────────────────────
    # 3. TABLA COMPARATIVA LP vs AG
    # ──────────────────────────────────────────────────────────────────────────
    gap_pct = None
    if lp_factible and lp_costo and lp_costo > 0 and ag_factible:
        gap_pct = max(0.0, (ag_costo - lp_costo) / lp_costo * 100)

    print(_sep('═'))
    print('  TABLA COMPARATIVA — LP vs Algoritmo Genético')
    print(_sep('═'))
    print(f"  {'Métrica':<30} {'LP (Exacto)':>16} {'AG (Heurístico)':>18}")
    print(_sep())
    print(f"  {'Método':<30} {'Prog. Lineal (HiGHS)':>16} {'Genético (BLX-α)':>18}")
    print(f"  {'Costo total (KCOP)':<30} {_fmt_costo(lp_costo):>16} {_fmt_costo(ag_costo):>18}")
    print(f"  {'Tiempo de ejecución':<30} {_fmt_tiempo(lp_tiempo_ms):>16} {_fmt_tiempo(ag_tiempo):>18}")
    print(f"  {'Factibilidad':<30} {'✅ Sí' if lp_factible else '❌ No':>16} {'✅ Sí' if ag_factible else '❌ No':>18}")
    print(f"  {'Violación demanda (ton)':<30} {'0.000':>16} {ag_violacion:>18.3f}")
    print(f"  {'Gap vs óptimo LP':<30} {'0.00 %':>16} {_fmt_pct(gap_pct):>18}")
    print(_sep('═'))

    # Veredicto
    print()
    if lp_factible and ag_factible and gap_pct is not None:
        if gap_pct < 1.0:
            veredicto = "El AG alcanzó una solución casi óptima (gap < 1%)."
        elif gap_pct < 5.0:
            veredicto = f"El AG se acercó al óptimo con un gap del {gap_pct:.2f}%."
        else:
            veredicto = (f"El AG tiene un gap del {gap_pct:.2f}%. "
                         f"Puede mejorar aumentando generaciones o población.")
        print(f"  📊 {veredicto}")
    elif not ag_factible:
        print(f"  ⚠  El AG no satisfizo todas las restricciones "
              f"(violación: {ag_violacion:.3f} ton). "
              f"Prueba aumentar generaciones o la penalización.")

    aceleracion = None
    if lp_tiempo_ms and ag_tiempo and ag_tiempo > 0:
        aceleracion = lp_tiempo_ms / ag_tiempo if lp_tiempo_ms > ag_tiempo else ag_tiempo / lp_tiempo_ms
        mas_lento = 'LP' if lp_tiempo_ms > ag_tiempo else 'AG'
        print(f"  ⏱  El {mas_lento} tardó {aceleracion:.1f}× más que el otro método.")

    print()
    print(_sep('═'))
    print('  Fin del análisis.')
    print(_sep('═'))
    print()


if __name__ == '__main__':
    main()
