import React, { useState } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';

const ESCENARIOS_INFO = [
  {
    numero: 1,
    icono: '⛽',
    titulo: 'Alza de Combustible',
    subtitulo: '+15% en rutas del Meta',
    descripcion: 'Simula un aumento del 15% en el costo de combustible para todas las rutas que salen de los orígenes del Meta (O1, O2, O3 — Villavicencio, Puerto López, San Martín).',
    color: 'amber',
  },
  {
    numero: 2,
    icono: '🚧',
    titulo: 'Cierre de Vía',
    subtitulo: 'Bloqueo de arista E20',
    descripcion: 'Simula el cierre de la vía Hub Bogotá → Cali (E20), la única ruta directa al suroccidente. Evalúa si el sistema puede redirigir flujos por rutas alternas.',
    color: 'red',
  },
  {
    numero: 3,
    icono: '🐟',
    titulo: 'Pérdida de Calidad',
    subtitulo: 'Falla en Hub Bogotá (T1)',
    descripcion: 'Simula una pérdida masiva de calidad en el nodo T1 (Hub Bogotá). La calidad cae al 35%, por debajo del umbral mínimo del 40%, bloqueando o penalizando sus salidas.',
    color: 'orange',
  },
];

const COLOR_MAP = {
  amber:  { badge: 'bg-amber-500/10 text-amber-600 border-amber-500/20',  border: 'border-amber-500/20', icon: 'bg-amber-500/10' },
  red:    { badge: 'bg-red-500/10 text-red-600 border-red-500/20',        border: 'border-red-500/20',   icon: 'bg-red-500/10'   },
  orange: { badge: 'bg-orange-500/10 text-orange-600 border-orange-500/20', border: 'border-orange-500/20', icon: 'bg-orange-500/10' },
};

function DeltaBadge({ valor, unidad = 'KCOP', invertir = false }) {
  if (valor === null || valor === undefined) return <span className="text-muted-foreground">—</span>;
  const positivo = valor > 0;
  const malo = invertir ? !positivo : positivo;
  return (
    <span className={`font-semibold ${malo ? 'text-red-500' : 'text-green-500'}`}>
      {positivo ? '+' : ''}{typeof valor === 'number' ? valor.toLocaleString('es-CO', { maximumFractionDigits: 2 }) : valor} {unidad}
    </span>
  );
}

function ResultadoComparativo({ resultado }) {
  if (!resultado) return null;

  const { resultado_base: base, resultado_nuevo: nuevo, impacto, cambios_flujo_top5, aristas_afectadas } = resultado;

  return (
    <div className="mt-4 space-y-4">
      {/* Impacto principal */}
      <div className={`rounded-xl border p-4 ${nuevo.factible ? 'border-border bg-card/60' : 'border-red-500/30 bg-red-500/5'}`}>
        <div className="flex items-center justify-between mb-3">
          <span className="font-semibold text-sm">Estado del sistema</span>
          <Badge variant="outline" className={nuevo.factible ? 'border-green-500/30 text-green-600 bg-green-500/10' : 'border-red-500/30 text-red-600 bg-red-500/10'}>
            {nuevo.factible ? 'Factible' : 'Infactible'}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground">{impacto.mensaje}</p>
      </div>

      {/* Tabla comparativa */}
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
              <td className="px-3 py-2 text-right">
                <DeltaBadge valor={impacto.delta_costo_kcop} unidad="K" invertir />
              </td>
            </tr>
            <tr>
              <td className="px-3 py-2 text-muted-foreground">Variación %</td>
              <td className="px-3 py-2 text-right">—</td>
              <td className="px-3 py-2 text-right">—</td>
              <td className="px-3 py-2 text-right">
                <DeltaBadge valor={impacto.delta_costo_pct} unidad="%" invertir />
              </td>
            </tr>
            <tr>
              <td className="px-3 py-2 text-muted-foreground">Ganancia</td>
              <td className="px-3 py-2 text-right font-mono">{base.ganancia?.toLocaleString('es-CO')} K</td>
              <td className="px-3 py-2 text-right font-mono">{nuevo.factible ? nuevo.ganancia?.toLocaleString('es-CO') + ' K' : '—'}</td>
              <td className="px-3 py-2 text-right">
                <DeltaBadge valor={impacto.delta_ganancia_kcop} unidad="K" />
              </td>
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
      {cambios_flujo_top5 && cambios_flujo_top5.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-muted-foreground mb-2 uppercase tracking-wide">Mayores cambios de flujo</p>
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

      {/* Aristas afectadas */}
      {aristas_afectadas && aristas_afectadas.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-muted-foreground mb-2 uppercase tracking-wide">Aristas afectadas</p>
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

export default function SensibilidadPanel() {
  const [resultados, setResultados] = useState({});
  const [cargando, setCargando] = useState({});
  const [cargandoTodos, setCargandoTodos] = useState(false);
  const [abierto, setAbierto] = useState({});

  const ejecutarEscenario = async (numero) => {
    setCargando(prev => ({ ...prev, [numero]: true }));
    setAbierto(prev => ({ ...prev, [numero]: true }));
    try {
      const res = await axios.get(`/api/acuicola/sensibilidad/${numero}`);
      setResultados(prev => ({ ...prev, [numero]: res.data }));
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
      const res = await axios.get('/api/acuicola/sensibilidad/todos');
      const escenarios = res.data.escenarios || [];
      const map = {};
      escenarios.forEach(e => { map[e.escenario] = e; });
      setResultados(map);
    } catch {
      // silenciar
    } finally {
      setCargandoTodos(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold">Análisis de Sensibilidad</h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            Escenarios What-If — Red Logística Acuícola Real del Meta
          </p>
        </div>
        <Button
          onClick={ejecutarTodos}
          disabled={cargandoTodos}
          variant="outline"
          className="gap-2"
        >
          {cargandoTodos ? (
            <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
          ) : (
            <span>▶</span>
          )}
          Ejecutar todos
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {ESCENARIOS_INFO.map(esc => {
          const colors = COLOR_MAP[esc.color];
          const resultado = resultados[esc.numero];
          const cargandoEste = cargando[esc.numero] || (cargandoTodos && !resultado);
          const expandido = abierto[esc.numero];

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

              <CardContent className="pt-0">
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
                  ) : resultado ? (
                    'Volver a ejecutar'
                  ) : (
                    'Ejecutar escenario'
                  )}
                </Button>

                {resultado?.error && (
                  <div className="mt-3 rounded-lg bg-red-500/10 border border-red-500/20 px-3 py-2 text-xs text-red-600">
                    {resultado.error}
                  </div>
                )}

                {resultado && !resultado.error && expandido && (
                  <ResultadoComparativo resultado={resultado} />
                )}

                {resultado && !resultado.error && !expandido && (
                  <button
                    onClick={() => setAbierto(prev => ({ ...prev, [esc.numero]: true }))}
                    className="mt-2 w-full text-xs text-muted-foreground hover:text-foreground transition-colors"
                  >
                    Ver resultados ▼
                  </button>
                )}

                {resultado && !resultado.error && expandido && (
                  <button
                    onClick={() => setAbierto(prev => ({ ...prev, [esc.numero]: false }))}
                    className="mt-3 w-full text-xs text-muted-foreground hover:text-foreground transition-colors"
                  >
                    Colapsar ▲
                  </button>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Resumen global si hay los 3 resultados */}
      {[1, 2, 3].every(n => resultados[n] && !resultados[n].error) && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Resumen Comparativo</CardTitle>
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
                    <th className="text-center py-2 px-3 text-xs text-muted-foreground font-semibold uppercase">Estado</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/50">
                  {[1, 2, 3].map(n => {
                    const r = resultados[n];
                    const esc = ESCENARIOS_INFO[n - 1];
                    return (
                      <tr key={n} className="hover:bg-muted/20 transition-colors">
                        <td className="py-2.5 px-3">
                          <span className="font-medium">{esc.icono} {esc.titulo}</span>
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono text-xs">
                          {r.resultado_base?.costo_total?.toLocaleString('es-CO')} K
                        </td>
                        <td className="py-2.5 px-3 text-right font-mono text-xs">
                          {r.resultado_nuevo?.factible ? r.resultado_nuevo?.costo_total?.toLocaleString('es-CO') + ' K' : '—'}
                        </td>
                        <td className="py-2.5 px-3 text-right text-xs">
                          <DeltaBadge valor={r.impacto?.delta_costo_pct} unidad="%" invertir />
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
