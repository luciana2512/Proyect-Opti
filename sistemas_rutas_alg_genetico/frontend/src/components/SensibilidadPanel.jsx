import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';

/* ─── Paleta de colores por escenario ──────────────────────────────────────── */
const COLOR_MAP = {
  amber:  { badge: 'bg-amber-500/10 text-amber-600 border-amber-500/20',    border: 'border-amber-500/20',  icon: 'bg-amber-500/10'  },
  red:    { badge: 'bg-red-500/10 text-red-600 border-red-500/20',          border: 'border-red-500/20',    icon: 'bg-red-500/10'    },
  orange: { badge: 'bg-orange-500/10 text-orange-600 border-orange-500/20', border: 'border-orange-500/20', icon: 'bg-orange-500/10' },
};

/* ─── Badge de delta (rojo = malo, verde = bueno) ──────────────────────────── */
function DeltaBadge({ valor, unidad = 'KCOP', invertir = false }) {
  if (valor === null || valor === undefined) return <span className="text-muted-foreground">—</span>;
  const positivo = valor > 0;
  const malo = invertir ? positivo : !positivo;
  return (
    <span className={`font-semibold ${malo ? 'text-red-500' : 'text-green-500'}`}>
      {positivo ? '+' : ''}{typeof valor === 'number'
        ? valor.toLocaleString('es-CO', { maximumFractionDigits: 2 })
        : valor} {unidad}
    </span>
  );
}

/* ─── Resultado comparativo de un escenario ────────────────────────────────── */
function round2(v) { return Math.round(v * 100) / 100; }

function ResultadoComparativo({ resultado }) {
  if (!resultado) return null;
  const { resultado_base: base, resultado_nuevo: nuevo, impacto, cambios_flujo_top5, aristas_afectadas } = resultado;

  return (
    <div className="mt-4 space-y-4">
      {/* ── Hero: Impacto en la Ganancia Total ─────────────────────── */}
      {(() => {
        const ganBase  = base.ganancia;
        const ganNueva = nuevo.factible ? nuevo.ganancia : null;
        const delta    = impacto.delta_ganancia_kcop;
        const deltaPct = delta != null && ganBase ? round2(delta / ganBase * 100) : null;
        const positivo = delta > 0;
        return (
          <div className={`rounded-xl border-2 p-4 ${
            !nuevo.factible     ? 'border-red-500/40 bg-red-500/5'
            : delta < 0         ? 'border-green-500/40 bg-green-500/5'
            : delta > 0         ? 'border-red-500/40 bg-red-500/5'
            :                     'border-border bg-muted/20'
          }`}>
            <p className="text-xs font-bold uppercase tracking-widest text-muted-foreground mb-2">
              Impacto en la Ganancia Total
            </p>
            <div className="flex items-end justify-between flex-wrap gap-3">
              {/* Ganancia base */}
              <div className="text-center">
                <p className="text-[10px] text-muted-foreground mb-0.5">Antes del escenario</p>
                <p className="text-xl font-black text-foreground">
                  {ganBase != null ? ganBase.toLocaleString('es-CO') : '—'}
                  <span className="text-xs font-medium ml-1 text-muted-foreground">KCOP</span>
                </p>
              </div>
              {/* Flecha y delta */}
              <div className="text-center flex-1 min-w-[100px]">
                <p className={`text-3xl font-black ${
                  !nuevo.factible ? 'text-red-500'
                  : delta < 0     ? 'text-green-600 dark:text-green-400'
                  : delta > 0     ? 'text-red-500'
                  :                 'text-muted-foreground'
                }`}>
                  {!nuevo.factible
                    ? '— Infactible'
                    : delta != null
                    ? `${delta > 0 ? '+' : ''}${delta.toLocaleString('es-CO')} K`
                    : '—'}
                </p>
                {deltaPct != null && (
                  <p className={`text-xs font-bold mt-0.5 ${delta < 0 ? 'text-green-600 dark:text-green-400' : 'text-red-500'}`}>
                    {delta > 0 ? '+' : ''}{deltaPct}% de variación
                  </p>
                )}
              </div>
              {/* Ganancia nueva */}
              <div className="text-center">
                <p className="text-[10px] text-muted-foreground mb-0.5">Con el escenario</p>
                <p className={`text-xl font-black ${
                  !nuevo.factible ? 'text-red-500'
                  : delta < 0     ? 'text-green-600 dark:text-green-400'
                  : delta > 0     ? 'text-red-500'
                  :                 'text-foreground'
                }`}>
                  {ganNueva != null ? ganNueva.toLocaleString('es-CO') : '—'}
                  <span className="text-xs font-medium ml-1 text-muted-foreground">{ganNueva != null ? 'KCOP' : ''}</span>
                </p>
              </div>
            </div>
            <p className="text-xs text-muted-foreground mt-2 text-center">
              {!nuevo.factible
                ? '⚠️ El escenario hace la red infactible — no se puede calcular la ganancia.'
                : delta < 0
                ? '✅ Este escenario mejora la ganancia de la empresa.'
                : delta > 0
                ? '📉 Este escenario reduce la ganancia. Se requieren medidas de mitigación.'
                : '➡️ La ganancia no varía significativamente con este escenario.'}
            </p>
          </div>
        );
      })()}

      {/* Estado del sistema */}
      <div className={`rounded-xl border p-4 ${nuevo.factible ? 'border-border bg-card/60' : 'border-red-500/30 bg-red-500/5'}`}>
        <div className="flex items-center justify-between mb-2">
          <span className="font-semibold text-sm">Estado del sistema</span>
          <Badge variant="outline" className={nuevo.factible
            ? 'border-green-500/30 text-green-600 bg-green-500/10'
            : 'border-red-500/30 text-red-600 bg-red-500/10'}>
            {nuevo.factible ? 'Factible' : 'Infactible'}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground">{impacto.mensaje}</p>
      </div>

      {/* Tabla comparativa base vs escenario */}
      <div className="rounded-xl border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-muted/40 border-b border-border">
              <th className="text-left px-3 py-2 font-semibold text-xs text-muted-foreground">Métrica</th>
              <th className="text-right px-3 py-2 font-semibold text-xs text-muted-foreground">Base</th>
              <th className="text-right px-3 py-2 font-semibold text-xs text-muted-foreground">Escenario</th>
              <th className="text-right px-3 py-2 font-semibold text-xs text-muted-foreground">Delta</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            <tr>
              <td className="px-3 py-2 text-muted-foreground">Costo total</td>
              <td className="px-3 py-2 text-right font-mono">{base.costo_total?.toLocaleString('es-CO')} K</td>
              <td className="px-3 py-2 text-right font-mono">{nuevo.factible ? nuevo.costo_total?.toLocaleString('es-CO') + ' K' : '—'}</td>
              <td className="px-3 py-2 text-right"><DeltaBadge valor={impacto.delta_costo_kcop} unidad="K" invertir /></td>
            </tr>
            <tr>
              <td className="px-3 py-2 text-muted-foreground">Variación %</td>
              <td className="px-3 py-2 text-right">—</td>
              <td className="px-3 py-2 text-right">—</td>
              <td className="px-3 py-2 text-right"><DeltaBadge valor={impacto.delta_costo_pct} unidad="%" invertir /></td>
            </tr>
            <tr>
              <td className="px-3 py-2 text-muted-foreground">Ganancia</td>
              <td className="px-3 py-2 text-right font-mono">{base.ganancia?.toLocaleString('es-CO')} K</td>
              <td className="px-3 py-2 text-right font-mono">{nuevo.factible ? nuevo.ganancia?.toLocaleString('es-CO') + ' K' : '—'}</td>
              <td className="px-3 py-2 text-right"><DeltaBadge valor={impacto.delta_ganancia_kcop} unidad="K" /></td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* Parámetro modificado */}
      <div className="rounded-lg bg-muted/30 border border-border px-3 py-2 text-xs text-muted-foreground">
        <span className="font-semibold text-foreground">Parámetro modificado: </span>
        {resultado.parametro_modificado}
      </div>

      {/* Top 5 cambios de flujo */}
      {cambios_flujo_top5?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-muted-foreground mb-2 uppercase tracking-wide">
            Mayores cambios de flujo
          </p>
          <div className="space-y-1.5">
            {cambios_flujo_top5.map(cf => (
              <div key={cf.arista_id} className="flex items-center justify-between text-xs rounded-lg bg-card/60 border border-border/50 px-3 py-2">
                <span className="font-mono font-semibold text-muted-foreground">{cf.arista_id}</span>
                <span className="text-muted-foreground truncate mx-2 flex-1">{cf.descripcion || '—'}</span>
                <span className="font-mono whitespace-nowrap">
                  <span className="text-muted-foreground">{cf.flujo_base}t</span>
                  <span className="mx-1 text-muted-foreground">→</span>
                  <span className="font-semibold">{cf.flujo_nuevo}t</span>
                  <span className={`ml-1 ${cf.delta > 0 ? 'text-green-500' : 'text-red-500'}`}>
                    ({cf.delta > 0 ? '+' : ''}{cf.delta}t)
                  </span>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Cuellos de botella en escenario */}
      {nuevo.factible && resultado.cuellos_botella_nuevo?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-muted-foreground mb-2 uppercase tracking-wide">
            Cuellos de botella en escenario
          </p>
          <div className="flex flex-wrap gap-1.5">
            {resultado.cuellos_botella_nuevo.map(id => (
              <Badge key={id} variant="outline" className="text-xs font-mono border-red-500/40 text-red-600">
                {id}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Aristas afectadas */}
      {aristas_afectadas?.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-muted-foreground mb-2 uppercase tracking-wide">
            Aristas afectadas
          </p>
          <div className="flex flex-wrap gap-1.5">
            {aristas_afectadas.map(a => (
              <Badge key={a.arista_id} variant="outline" className="text-xs font-mono">
                {a.arista_id}
              </Badge>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Controles de parámetros por escenario ────────────────────────────────── */
function ControlesEscenario1({ valor, onChange }) {
  return (
    <div className="space-y-2 p-3 bg-amber-500/5 border border-amber-500/15 rounded-xl">
      <div className="flex items-center justify-between">
        <label className="text-xs font-semibold text-amber-700 dark:text-amber-400 uppercase tracking-wide">
          Incremento de combustible
        </label>
        <span className="text-sm font-black text-amber-600 dark:text-amber-400">+{valor}%</span>
      </div>
      <input
        type="range"
        min={5} max={50} step={5}
        value={valor}
        onChange={e => onChange(Number(e.target.value))}
        className="w-full accent-amber-500"
      />
      <div className="flex justify-between text-[10px] text-muted-foreground">
        <span>+5%</span><span>+25%</span><span>+50%</span>
      </div>
      <p className="text-[10px] text-muted-foreground">
        Se aplica a todas las aristas que salen de O1 (Villavicencio), O2 (Puerto López) y O3 (San Martín).
      </p>
    </div>
  );
}

function ControlesEscenario2({ valor, onChange, aristas }) {
  return (
    <div className="space-y-2 p-3 bg-red-500/5 border border-red-500/15 rounded-xl">
      <label className="text-xs font-semibold text-red-700 dark:text-red-400 uppercase tracking-wide">
        Vía a cerrar
      </label>
      <select
        value={valor}
        onChange={e => onChange(e.target.value)}
        className="w-full px-2 py-1.5 bg-background border border-border rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-red-500/40"
      >
        {aristas.map(a => (
          <option key={a.id} value={a.id}>
            {a.id} — {a.descripcion || `${a.origen} → ${a.destino}`} ({a.distancia_km} km)
          </option>
        ))}
      </select>
      <p className="text-[10px] text-muted-foreground">
        La arista seleccionada se elimina completamente del modelo. El LP buscará rutas alternativas.
      </p>
    </div>
  );
}

function ControlesEscenario3({ nodo, factor, onNodoChange, onFactorChange, transitos }) {
  return (
    <div className="space-y-2 p-3 bg-orange-500/5 border border-orange-500/15 rounded-xl">
      <div className="space-y-1">
        <label className="text-xs font-semibold text-orange-700 dark:text-orange-400 uppercase tracking-wide">
          Centro de acopio afectado
        </label>
        <select
          value={nodo}
          onChange={e => onNodoChange(e.target.value)}
          className="w-full px-2 py-1.5 bg-background border border-border rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-orange-500/40"
        >
          {transitos.map(t => (
            <option key={t.id} value={t.id}>{t.id} — {t.nombre}</option>
          ))}
        </select>
      </div>
      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <label className="text-xs font-semibold text-orange-700 dark:text-orange-400 uppercase tracking-wide">
            Factor de penalización
          </label>
          <span className="text-sm font-black text-orange-600 dark:text-orange-400">×{factor}</span>
        </div>
        <input
          type="range"
          min={1.5} max={10} step={0.5}
          value={factor}
          onChange={e => onFactorChange(Number(e.target.value))}
          className="w-full accent-orange-500"
        />
        <div className="flex justify-between text-[10px] text-muted-foreground">
          <span>×1.5</span><span>×5</span><span>×10</span>
        </div>
      </div>
      <p className="text-[10px] text-muted-foreground">
        La calidad cae al 35% (umbral mínimo: 40%). Las aristas del hub se bloquean o se penalizan
        con el factor elegido, forzando al LP a redirigir por otros centros.
      </p>
    </div>
  );
}

/* ─── Panel principal ───────────────────────────────────────────────────────── */
export default function SensibilidadPanel({ origenRuta = 'O1', destinoRuta = 'D1' }) {
  const [resultados,    setResultados]    = useState({});
  const [cargando,      setCargando]      = useState({});
  const [cargandoTodos, setCargandoTodos] = useState(false);
  const [abierto,       setAbierto]       = useState({});
  const [red,           setRed]           = useState(null);
  const [rutasImpacto,  setRutasImpacto]  = useState({});

  // Parámetros modificables por escenario
  const [params, setParams] = useState({
    1: { incremento_pct: 15 },
    2: { arista_id: 'E20'  },
    3: { nodo_id: 'T1', factor_penalizacion: 3.0 },
  });

  // Cargar red para poblar selectores dinámicamente
  useEffect(() => {
    axios.get('/api/acuicola/red')
      .then(r => setRed(r.data))
      .catch(() => {});
  }, []);

  const aristas   = red?.aristas  || [];
  const transitos = red?.nodos?.filter(n => n.tipo === 'transito') || [];

  const setParam = (escenario, clave, valor) =>
    setParams(prev => ({ ...prev, [escenario]: { ...prev[escenario], [clave]: valor } }));

  const ejecutarEscenario = async (numero) => {
    setCargando(prev => ({ ...prev, [numero]: true }));
    setAbierto(prev => ({ ...prev, [numero]: true }));
    try {
      const res = await axios.get(`/api/acuicola/sensibilidad/${numero}`, {
        params: params[numero],
      });
      setResultados(prev => ({ ...prev, [numero]: res.data }));
      // Calcular impacto en la ruta seleccionada
      const paramRuta = { origen: origenRuta, destino: destinoRuta, escenario: numero, ...params[numero] };
      axios.get('/api/acuicola/ruta_escenario', { params: paramRuta })
        .then(r => setRutasImpacto(prev => ({ ...prev, [numero]: r.data })))
        .catch(() => {});
    } catch {
      setResultados(prev => ({ ...prev, [numero]: { error: 'Error al ejecutar el escenario' } }));
    } finally {
      setCargando(prev => ({ ...prev, [numero]: false }));
    }
  };

  const ejecutarTodos = async () => {
    setCargandoTodos(true);
    setAbierto({ 1: true, 2: true, 3: true });
    try {
      // Ejecutar los 3 en paralelo con sus parámetros actuales
      const [r1, r2, r3] = await Promise.all([
        axios.get('/api/acuicola/sensibilidad/1', { params: params[1] }),
        axios.get('/api/acuicola/sensibilidad/2', { params: params[2] }),
        axios.get('/api/acuicola/sensibilidad/3', { params: params[3] }),
      ]);
      setResultados({ 1: r1.data, 2: r2.data, 3: r3.data });
      // Impacto en ruta para los 3 escenarios
      Promise.all([1,2,3].map(n =>
        axios.get('/api/acuicola/ruta_escenario', {
          params: { origen: origenRuta, destino: destinoRuta, escenario: n, ...params[n] }
        }).then(r => ({ n, data: r.data })).catch(() => null)
      )).then(results => {
        const map = {};
        results.forEach(r => { if (r) map[r.n] = r.data; });
        setRutasImpacto(map);
      });
    } catch {
      // silenciar error global
    } finally {
      setCargandoTodos(false);
    }
  };

  const ESCENARIOS = [
    {
      numero: 1,
      icono: '⛽',
      titulo: 'Alza de Combustible',
      subtitulo: `+${params[1].incremento_pct}% en rutas del Meta`,
      descripcion: `Simula un aumento del ${params[1].incremento_pct}% en el costo de combustible para todas las rutas que salen de los orígenes del Meta (O1, O2, O3 — Villavicencio, Puerto López, San Martín).`,
      color: 'amber',
      controles: (
        <ControlesEscenario1
          valor={params[1].incremento_pct}
          onChange={v => setParam(1, 'incremento_pct', v)}
        />
      ),
    },
    {
      numero: 2,
      icono: '🚧',
      titulo: 'Cierre de Vía',
      subtitulo: `Bloqueo de arista ${params[2].arista_id}`,
      descripcion: `Simula el cierre completo de la arista ${params[2].arista_id}. Evalúa si el sistema puede redirigir flujos por rutas alternas o si se vuelve infactible.`,
      color: 'red',
      controles: (
        <ControlesEscenario2
          valor={params[2].arista_id}
          onChange={v => setParam(2, 'arista_id', v)}
          aristas={aristas}
        />
      ),
    },
    {
      numero: 3,
      icono: '🐟',
      titulo: 'Pérdida de Calidad',
      subtitulo: `Falla en ${params[3].nodo_id} · ×${params[3].factor_penalizacion}`,
      descripcion: `Simula una pérdida masiva de calidad en el nodo ${params[3].nodo_id}. La calidad cae al 35%, bloqueando o penalizando sus salidas con un factor ×${params[3].factor_penalizacion}.`,
      color: 'orange',
      controles: (
        <ControlesEscenario3
          nodo={params[3].nodo_id}
          factor={params[3].factor_penalizacion}
          onNodoChange={v => setParam(3, 'nodo_id', v)}
          onFactorChange={v => setParam(3, 'factor_penalizacion', v)}
          transitos={transitos}
        />
      ),
    },
  ];

  return (
    <div className="space-y-6">

      {/* ── Encabezado ─────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold">Análisis de Sensibilidad</h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            Escenarios What-If — modifica los parámetros y evalúa el impacto en tiempo real{'  '}—{'  '}
          Ruta activa: <span className="font-bold text-foreground">{origenRuta} → {destinoRuta}</span>
          </p>
        </div>
        <Button onClick={ejecutarTodos} disabled={cargandoTodos} variant="outline" className="gap-2">
          {cargandoTodos
            ? <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
            : <span>▶</span>}
          Ejecutar todos
        </Button>
      </div>

      {/* ── Tarjetas de escenarios ─────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {ESCENARIOS.map(esc => {
          const colors       = COLOR_MAP[esc.color];
          const resultado    = resultados[esc.numero];
          const cargandoEste = cargando[esc.numero] || (cargandoTodos && !resultado);
          const expandido    = abierto[esc.numero];

          return (
            <Card key={esc.numero} className={`border ${colors.border} transition-all`}>
              <CardHeader className="pb-3">
                <div className="flex items-start gap-3">
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-xl flex-shrink-0 ${colors.icon}`}>
                    {esc.icono}
                  </div>
                  <div className="flex-1 min-w-0">
                    <CardTitle className="text-base">
                      <span className="text-muted-foreground font-normal mr-1">#{esc.numero}</span>
                      {esc.titulo}
                    </CardTitle>
                    <Badge variant="outline" className={`mt-1 text-xs ${colors.badge}`}>
                      {esc.subtitulo}
                    </Badge>
                  </div>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed mt-2">
                  {esc.descripcion}
                </p>
              </CardHeader>

              <CardContent className="pt-0 space-y-3">
                {/* ── Controles de parámetros ───────────────────────── */}
                {esc.controles}

                {/* ── Botón ejecutar ────────────────────────────────── */}
                <Button
                  onClick={() => ejecutarEscenario(esc.numero)}
                  disabled={cargandoEste}
                  className="w-full gap-2"
                  size="sm"
                >
                  {cargandoEste ? (
                    <>
                      <span className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
                      Ejecutando...
                    </>
                  ) : resultado ? 'Volver a ejecutar' : 'Ejecutar escenario'}
                </Button>

                {/* ── Error ─────────────────────────────────────────── */}
                {resultado?.error && (
                  <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-3 py-2 text-xs text-red-600">
                    {resultado.error}
                  </div>
                )}

                {/* ── Resultado expandido ───────────────────────────── */}
                {resultado && !resultado.error && expandido && (
                  <>
                    <ResultadoComparativo resultado={resultado} />

                {/* ── Impacto en la ruta seleccionada ── */}
                {rutasImpacto[esc.numero] && (() => {
                  const imp = rutasImpacto[esc.numero].impacto;
                  const rb  = rutasImpacto[esc.numero].ruta_base;
                  const rm  = rutasImpacto[esc.numero].ruta_escenario;
                  const cambio = imp?.ruta_cambio;
                  const factible = imp?.factible_mod;
                  return (
                    <div className={`mt-3 rounded-xl border p-3 space-y-2 ${
                      !factible ? 'bg-red-500/5 border-red-500/30'
                      : cambio  ? 'bg-amber-500/5 border-amber-500/30'
                      :           'bg-green-500/5 border-green-500/30'
                    }`}>
                      <div className="flex items-center justify-between">
                        <p className="text-xs font-bold flex items-center gap-1.5">
                          {!factible ? '🚫' : cambio ? '⚠️' : '✅'}
                          Impacto en ruta {origenRuta} → {destinoRuta}
                        </p>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                          !factible ? 'bg-red-500/15 text-red-600'
                          : cambio  ? 'bg-amber-500/15 text-amber-600'
                          :           'bg-green-500/15 text-green-600'
                        }`}>
                          {!factible ? 'Ruta bloqueada' : cambio ? 'Ruta cambiada' : 'Sin cambio'}
                        </span>
                      </div>
                      {/* Ruta base */}
                      <div className="space-y-1">
                        <p className="text-[10px] text-muted-foreground font-semibold uppercase">Ruta original:</p>
                        <div className="flex flex-wrap items-center gap-1">
                          {rb?.ruta?.map((nid,i) => (
                            <React.Fragment key={i}>
                              <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border font-bold ${
                                i===0 ? 'bg-blue-500 text-white border-blue-500'
                                : i===rb.ruta.length-1 ? 'bg-green-500 text-white border-green-500'
                                : 'bg-secondary/60 border-border/50'
                              }`}>{nid}</span>
                              {i<rb.ruta.length-1 && <span className="text-[9px] text-muted-foreground">→</span>}
                            </React.Fragment>
                          ))}
                          <span className="text-[10px] text-muted-foreground ml-1">({imp?.costo_base?.toFixed(0)} KCOP)</span>
                        </div>
                      </div>
                      {/* Ruta bajo escenario */}
                      <div className="space-y-1">
                        <p className="text-[10px] text-muted-foreground font-semibold uppercase">
                          Ruta bajo escenario:
                        </p>
                        {factible ? (
                          <div className="flex flex-wrap items-center gap-1">
                            {rm?.ruta?.map((nid,i) => (
                              <React.Fragment key={i}>
                                <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded border font-bold ${
                                  i===0 ? 'bg-blue-500 text-white border-blue-500'
                                  : i===rm.ruta.length-1 ? 'bg-green-500 text-white border-green-500'
                                  : cambio ? 'bg-amber-500/80 text-white border-amber-500'
                                  : 'bg-secondary/60 border-border/50'
                                }`}>{nid}</span>
                                {i<rm.ruta.length-1 && <span className="text-[9px] text-muted-foreground">→</span>}
                              </React.Fragment>
                            ))}
                            <span className={`text-[10px] ml-1 font-bold ${
                              imp?.delta_costo > 0 ? 'text-red-500' : 'text-green-500'
                            }`}>
                              ({imp?.costo_mod?.toFixed(0)} KCOP
                              {imp?.delta_costo !== 0 && imp?.delta_costo != null
                                ? ` / ${imp.delta_costo > 0 ? '+' : ''}${imp.delta_costo?.toFixed(0)} KCOP · ${imp.delta_pct > 0 ? '+' : ''}${imp.delta_pct?.toFixed(1)}%`
                                : ''})
                            </span>
                          </div>
                        ) : (
                          <p className="text-xs text-red-500 font-medium">
                            ❌ No existe ruta disponible — la vía quedó bloqueada.
                          </p>
                        )}
                      </div>
                    </div>
                  );
                })()}
                    <button
                      onClick={() => setAbierto(prev => ({ ...prev, [esc.numero]: false }))}
                      className="w-full text-xs text-muted-foreground hover:text-foreground transition-colors"
                    >
                      Colapsar ▲
                    </button>
                  </>
                )}

                {resultado && !resultado.error && !expandido && (
                  <button
                    onClick={() => setAbierto(prev => ({ ...prev, [esc.numero]: true }))}
                    className="w-full text-xs text-muted-foreground hover:text-foreground transition-colors"
                  >
                    Ver resultados ▼
                  </button>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* ── Resumen global cuando los 3 están ejecutados ──────────────── */}
      {[1, 2, 3].every(n => resultados[n] && !resultados[n].error) && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Resumen Comparativo — Los 3 Escenarios</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-2 px-3 text-xs text-muted-foreground font-semibold uppercase">Escenario</th>
                    <th className="text-right py-2 px-3 text-xs text-muted-foreground font-semibold uppercase">Costo base</th>
                    <th className="text-right py-2 px-3 text-xs text-muted-foreground font-semibold uppercase">Costo nuevo</th>
                    <th className="text-right py-2 px-3 text-xs text-muted-foreground font-semibold uppercase">Delta %</th>
                    <th className="text-right py-2 px-3 text-xs text-muted-foreground font-semibold uppercase">Delta KCOP</th>
                    <th className="text-center py-2 px-3 text-xs text-muted-foreground font-semibold uppercase">Estado</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/50">
                  {ESCENARIOS.map(esc => {
                    const r = resultados[esc.numero];
                    return (
                      <tr key={esc.numero} className="hover:bg-muted/20 transition-colors">
                        <td className="py-2.5 px-3">
                          <span className="font-medium">{esc.icono} {esc.titulo}</span>
                          <span className="block text-[10px] text-muted-foreground">{esc.subtitulo}</span>
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono text-xs">
                          {r.resultado_base?.costo_total?.toLocaleString('es-CO')} K
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono text-xs">
                          {r.resultado_nuevo?.factible
                            ? r.resultado_nuevo?.costo_total?.toLocaleString('es-CO') + ' K'
                            : '—'}
                        </td>
                        <td className="py-2.5 px-3 text-right text-xs">
                          <DeltaBadge valor={r.impacto?.delta_costo_pct} unidad="%" invertir />
                        </td>
                        <td className="py-2.5 px-3 text-right text-xs">
                          <DeltaBadge valor={r.impacto?.delta_costo_kcop} unidad="K" invertir />
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          <Badge variant="outline" className={
                            r.resultado_nuevo?.factible
                              ? 'border-green-500/30 text-green-600 bg-green-500/10 text-xs'
                              : 'border-red-500/30 text-red-600 bg-red-500/10 text-xs'
                          }>
                            {r.resultado_nuevo?.factible ? 'Factible' : 'Infactible'}
                          </Badge>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
