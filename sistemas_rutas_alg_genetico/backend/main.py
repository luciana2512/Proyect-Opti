"""
main.py — Demo de la Red Logística Acuícola Real del Meta.

Ejecuta en consola:
  1. Modelo LP (solución exacta): muestra costo total, ingreso, ganancia y tiempo.
  2. AG-TSP por hub: para cada centro de acopio imprime el orden de reparto
     optimizado, número de destinos, distancia total (km) y tiempo del AG.

Uso:
    python main.py
    python main.py --seed 42
"""
import sys
import argparse
import time

sys.stdout.reconfigure(encoding='utf-8')

from modelo_pl import resolver_pl, cargar_red
from grafo_acuicola import optimizar_distribucion_local


def _sep(char='─', n=65):
    return char * n


def main():
    parser = argparse.ArgumentParser(
        description='Demo Red Logística Acuícola — LP + AG-TSP por hub'
    )
    parser.add_argument('--seed',         type=int, default=42,
                        help='Semilla para el AG-TSP (default: 42)')
    parser.add_argument('--generaciones', type=int, default=150,
                        help='Generaciones del AG-TSP (default: 150)')
    parser.add_argument('--poblacion',    type=int, default=80,
                        help='Tamaño de población del AG-TSP (default: 80)')
    args = parser.parse_args()

    print()
    print('═' * 65)
    print('  ACUÍCOLA REAL DEL META — Demo LP + AG-TSP')
    print('═' * 65)

    # ── Cargar red ────────────────────────────────────────────────────────────
    red       = cargar_red()
    origenes  = [n for n in red['nodos'] if n['tipo'] == 'origen']
    transitos = [n for n in red['nodos'] if n['tipo'] == 'transito']
    destinos  = [n for n in red['nodos'] if n['tipo'] == 'destino']

    print(f"\n  Red: {red.get('nombre', 'Acuícola')}")
    print(f"  Orígenes: {len(origenes)} | Tránsitos: {len(transitos)} | "
          f"Destinos: {len(destinos)} | Aristas: {len(red['aristas'])}")
    print(f"  Oferta total:  {sum(float(o.get('oferta', 0)) for o in origenes):.1f} ton")
    print(f"  Demanda total: {sum(float(d.get('demanda', 0)) for d in destinos):.1f} ton")

    # ── 1. Programación Lineal ────────────────────────────────────────────────
    print(f"\n{_sep()}")
    print('  [1/2]  Programación Lineal (scipy HiGHS)')
    print(_sep())

    res_lp = resolver_pl(red=red)

    if res_lp.get('factible'):
        print(f"  Estado:           FACTIBLE ✅")
        print(f"  Costo transporte: {res_lp.get('costo_transporte', 0):>14,.2f} KCOP")
        print(f"  Costo operación:  {res_lp.get('costo_operacion',  0):>14,.2f} KCOP")
        print(f"  Costo almacén:    {res_lp.get('costo_almacen',    0):>14,.2f} KCOP")
        print(f"  Costo TOTAL:      {res_lp.get('costo_total',      0):>14,.2f} KCOP")
        print(f"  Ingreso total:    {res_lp.get('ingreso_total',    0):>14,.2f} KCOP")
        ganancia = res_lp.get('ganancia', 0)
        signo    = '+' if ganancia >= 0 else ''
        print(f"  Ganancia:         {signo}{ganancia:>13,.2f} KCOP")
        print(f"  Aristas activas:  {res_lp.get('total_aristas_activas', '—')}")
        print(f"  Tiempo solver:    {res_lp.get('tiempo_solver_ms', 0):>10.1f} ms")
    else:
        print(f"  Estado:  INFACTIBLE ❌  — {res_lp.get('error', '')}")

    # ── 2. AG-TSP por hub de tránsito ─────────────────────────────────────────
    print(f"\n{_sep()}")
    print(f"  [2/2]  AG-TSP — reparto de última milla por hub")
    print(f"         Población: {args.poblacion} | Generaciones: {args.generaciones} | "
          f"Semilla: {args.seed}")
    print(_sep())

    filas = []
    for t in transitos:
        tid = t['id']
        res = optimizar_distribucion_local(
            transito_id=tid,
            red=red,
            seed=args.seed,
            tamano_poblacion=args.poblacion,
            generaciones=args.generaciones,
        )
        if 'error' in res:
            print(f"  {tid}: {res['error']}")
            continue

        orden = ' → '.join(res['orden_optimizado'])
        filas.append((
            tid,
            t['nombre'],
            res['n_destinos'],
            res['distancia_total_km'],
            res['tiempo_ms'],
            orden,
        ))

    # Tabla resumen
    print(f"\n  {'Hub':<4}  {'Destinos':>8}  {'Dist. total (km)':>17}  {'Tiempo AG':>10}")
    print('  ' + '─' * 45)
    for tid, nombre, n_dest, dist, t_ms, orden in filas:
        print(f"  {tid:<4}  {n_dest:>8}  {dist:>17.2f}  {t_ms:>8.1f} ms")

    print()

    # Detalle de rutas
    for tid, nombre, n_dest, dist, t_ms, orden in filas:
        print(f"  {tid} — {nombre}")
        print(f"    Ruta: {orden}")
        print(f"    Distancia: {dist:.2f} km | {n_dest} destino(s)")
        print()

    print('═' * 65)
    print('  Fin del demo.')
    print('═' * 65)
    print()


if __name__ == '__main__':
    main()