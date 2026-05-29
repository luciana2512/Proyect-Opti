import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from './ui/card';
import { toast } from 'sonner';
import axios from 'axios';
import NetworkGraphSVG from './NetworkGraphSVG';
import MapaAcuicola from './MapaAcuicola';
import {
  Fish, Play, Loader2, TrendingDown, TrendingUp, Package,
  Network, MapPin, ChevronDown, ChevronUp, Route, BarChart3,
  AlertTriangle, CheckCircle, Dna, Info, Map, GitGraph,
  ShieldCheck, ShieldAlert, CornerDownRight,
} from 'lucide-react';

const NODOS_TRANSITO = [
  { id: 'T1', nombre: 'Hub Bogotá' },
  { id: 'T2', nombre: 'Acopio VVC' },
  { id: 'T3', nombre: 'Acopio Tunja' },
  { id: 'T4', nombre: 'Acopio Ibagué' },
  { id: 'T5', nombre: 'Acopio Neiva' },
  { id: 'T6', nombre: 'Acopio Bucaramanga' },
  { id: 'T7', nombre: 'Acopio Pereira' },
  { id: 'T8', nombre: 'Acopio Cali' },
  { id: 'T9', nombre: 'Acopio Manizales' },
  { id: 'T10', nombre: 'Acopio Medellín' },
];

const TarjetaEstadistica = ({ icono: Icono, etiqueta, valor, unidad = '', color = 'blue', subtitulo = '' }) => {
  const colores = {
    blue:   'bg-blue-500/10 border-blue-500/20 text-blue-600 dark:text-blue-400',
    green:  'bg-green-500/10 border-green-500/20 text-green-600 dark:text-green-400',
    amber:  'bg-amber-500/10 border-amber-500/20 text-amber-600 dark:text-amber-400',
    red:    'bg-red-500/10 border-red-500/20 text-red-600 dark:text-red-400',
    purple: 'bg-purple-500/10 border-purple-500/20 text-purple-600 dark:text-purple-400',
  };
  return (
    <div className={`rounded-xl border p-4 ${colores[color]}`}>
      <div className="flex items-center gap-2 mb-1">
        <Icono className="w-4 h-4" />
        <span className="text-xs font-bold uppercase tracking-wider opacity-75">{etiqueta}</span>
      </div>
      <p className="text-2xl font-black">
        {valor != null ? Number(valor).toLocaleString('es-CO') : '—'}
        {unidad && <span className="text-sm font-medium ml-1 opacity-70">{unidad}</span>}
      </p>
      {subtitulo && <p className="text-xs opacity-60 mt-0.5">{subtitulo}</p>}
    </div>
  );
};

const AcuicolaPanel = () => {
  const [red, setRed]                                   = useState(null);
  const [resultado, setResultado]                       = useState(null);
  const [resultadoGA, setResultadoGA]                   = useState(null);
  const [geometriaRuta, setGeometriaRuta]               = useState([]);
  const [conectividad, setConectividad]                 = useState(null);
  const [cargandoRed, setCargandoRed]                   = useState(false);
  const [cargandoPL, setCargandoPL]                     = useState(false);
  const [cargandoGA, setCargandoGA]                     = useState(false);
  const [errorRed, setErrorRed]                         = useState(false);
  const [mostrarConectividad, setMostrarConectividad]   = useState(false);

  // Controles
  const [origenRuta, setOrigenRuta]                     = useState('O1');
  const [destinoRuta, setDestinoRuta]                   = useState('D1');
  const [algoritmo, setAlgoritmo]                       = useState('dijkstra');
  const [transitoGA, setTransitoGA]                     = useState('T1');
  const [mostrarFlujos, setMostrarFlujos]               = useState(false);
  const [vistaGrafo, setVistaGrafo]                     = useState('mapa');

  // Parámetros AG
  const [parametrosGA, setParametrosGA] = useState({
    tamano_poblacion: 80,
    generaciones: 150,
    tasa_cruce: 0.8,
    tasa_mutacion: 0.15,
    elitismo: 5,
  });
  const [mostrarParametrosGA, setMostrarParametrosGA] = useState(false);

  useEffect(() => { cargarRed(); }, []);

  const cargarRed = async () => {
    setCargandoRed(true);
    setErrorRed(false);
    try {
      const resp = await axios.get('/api/acuicola/red');
      setRed(resp.data);
      axios.get('/api/acuicola/validar_conectividad')
        .then(respConect => setConectividad(respConect.data))
        .catch(() => {});
    } catch (e) {
      setErrorRed(true);
      toast.error('Error cargando la red — verifica que el backend esté corriendo en puerto 5000');
    } finally {
      setCargandoRed(false);
    }
  };

  const optimizarPL = useCallback(async () => {
    setCargandoPL(true);
    setResultado(null);
    setGeometriaRuta([]);
    toast.loading('Resolviendo LP + Grafos...', { id: 'pl' });
    try {
      const resp = await axios.get('/api/acuicola/optimizar', {
        params: {
          origen: origenRuta,
          destino: destinoRuta,
          algoritmo_grafo: algoritmo,
          fuente_flujo: origenRuta,
          sumidero_flujo: destinoRuta,
        }
      });
      setResultado(resp.data);
      toast.success('Optimización LP completada', { id: 'pl' });

      const idsRuta = resp.data.ruta_optima?.ruta;
      if (resp.data.ruta_optima?.factible && idsRuta?.length >= 2) {
        toast.loading('Cargando ruta por calles reales...', { id: 'osrm' });
        axios.get('/api/acuicola/geometria_ruta', {
          params: { nodos: idsRuta.join(',') },
          timeout: 18000,
        }).then(respGeometria => {
          const puntos = respGeometria.data?.geometria || [];
          if (puntos.length > 2) {
            setGeometriaRuta(puntos);
            const fuente = respGeometria.data?.fuente === 'osrm' ? 'calles OSM' : 'líneas rectas';
            toast.success(`Ruta real: ${puntos.length} puntos (${fuente})`, { id: 'osrm', duration: 3000 });
          } else {
            toast.dismiss('osrm');
          }
        }).catch(() => toast.dismiss('osrm'));
      }
    } catch (e) {
      toast.error('Error en la optimización: ' + (e.response?.data?.error || e.message), { id: 'pl' });
    } finally {
      setCargandoPL(false);
    }
  }, [origenRuta, destinoRuta, algoritmo]);

  const optimizarDistribucion = async () => {
    setCargandoGA(true);
    setResultadoGA(null);
    toast.loading(`AG — optimizando red completa (${parametrosGA.generaciones} gen.)...`, { id: 'ga' });
    try {
      const resp = await axios.get('/api/acuicola/ag_red', {
        params: { ...parametrosGA, transito_id: transitoGA },
        timeout: 120000,
      });
      if (resp.data.error) throw new Error(resp.data.error);
      setResultadoGA(resp.data);
      const comparacion = resp.data.comparacion_lp_ag;
      const textoGap = comparacion?.gap_pct != null
        ? ` — Gap vs LP: +${comparacion.gap_pct}%`
        : (comparacion?.ag_factible === false ? ' — solución infactible' : '');
      toast.success(`AG completado${textoGap}`, { id: 'ga' });
    } catch (e) {
      toast.error('Error AG: ' + (e.response?.data?.error || e.message), { id: 'ga' });
    } finally {
      setCargandoGA(false);
    }
  };

  const resultadoPL  = resultado?.resultado_pl;
  const rutaOptima   = resultado?.ruta_optima;
  const flujoMaximo  = resultado?.flujo_maximo;
  const analisisRed  = resultado?.analisis_red;

  return (
    <div className="space-y-6">

      {/* ── Métricas de la red ─────────────────────────────────────────── */}
      <Card className="glass-effect border-border/50 overflow-hidden">
        <CardHeader className="bg-blue-500/5 border-b border-border/50 pb-4">
          <div className="flex items-center gap-3">
            <div className="bg-blue-600 p-2.5 rounded-xl text-white shadow-lg shadow-blue-500/30">
              <Fish className="w-6 h-6" />
            </div>
            <div>
              <CardTitle className="text-xl font-bold">Red Logística Acuícola Real del Meta</CardTitle>
              <CardDescription className="font-medium">
                Programación Lineal · Teoría de Grafos · Algoritmo Genético
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-5">
          {cargandoRed ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="w-4 h-4 animate-spin" /> Cargando estructura de la red...
            </div>
          ) : errorRed ? (
            <div className="flex items-center gap-4">
              <p className="text-sm text-red-500 font-medium">No se pudo conectar con el backend.</p>
              <button
                onClick={cargarRed}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-bold rounded-lg flex items-center gap-2 transition-all"
              >
                <Loader2 className="w-3.5 h-3.5" /> Reintentar
              </button>
            </div>
          ) : red && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <TarjetaEstadistica icono={Package}   etiqueta="Orígenes"     valor={red.resumen.n_origenes}   color="blue"   subtitulo="Meta + Cundinamarca" />
              <TarjetaEstadistica icono={Network}   etiqueta="Tránsitos"    valor={red.resumen.n_transitos}  color="amber"  subtitulo="Centros de acopio" />
              <TarjetaEstadistica icono={MapPin}    etiqueta="Destinos"     valor={red.resumen.n_destinos}   color="green"  subtitulo="Supermercados" />
              <TarjetaEstadistica icono={BarChart3} etiqueta="Oferta total" valor={red.resumen.oferta_total} unidad="ton/sem" color="purple" subtitulo={`Demanda: ${red.resumen.demanda_total} ton`} />
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Informe de conectividad ────────────────────────────────────── */}
      {conectividad && (
        <Card className={`glass-effect border-border/50 overflow-hidden transition-all ${
          conectividad.resumen.grafo_sano ? 'border-green-500/30' : 'border-amber-500/30'
        }`}>
          <button
            onClick={() => setMostrarConectividad(v => !v)}
            className="w-full flex items-center justify-between px-5 py-3 text-sm font-semibold"
          >
            <div className="flex items-center gap-2">
              {conectividad.resumen.grafo_sano
                ? <ShieldCheck className="w-4 h-4 text-green-500" />
                : <ShieldAlert className="w-4 h-4 text-amber-500" />}
              <span>Validación de Conectividad del Grafo</span>
              <span className={`text-xs px-2 py-0.5 rounded-full font-bold ${
                conectividad.resumen.grafo_sano
                  ? 'bg-green-500/15 text-green-700 dark:text-green-400'
                  : 'bg-amber-500/15 text-amber-700 dark:text-amber-400'
              }`}>
                {conectividad.resumen.pct_cobertura}% cobertura
                · {conectividad.resumen.n_destinos_alcanzables}/{conectividad.resumen.n_destinos_total} destinos
              </span>
            </div>
            {mostrarConectividad ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>

          {mostrarConectividad && (
            <div className="px-5 pb-4 space-y-3 border-t border-border/40 pt-3">

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                {[
                  { etiqueta: 'Nodos |V|',   valor: conectividad.n_nodos,                    color: 'blue' },
                  { etiqueta: 'Aristas |E|', valor: conectividad.n_aristas,                  color: 'blue' },
                  { etiqueta: 'Componentes', valor: conectividad.n_componentes_debiles,       color: conectividad.conexo_debilmente ? 'green' : 'amber' },
                  { etiqueta: 'Aislados',    valor: conectividad.nodos_aislados.length,       color: conectividad.nodos_aislados.length === 0 ? 'green' : 'red' },
                ].map(({ etiqueta, valor, color }) => {
                  const clase = {
                    blue:  'bg-blue-500/10 text-blue-700 dark:text-blue-400',
                    green: 'bg-green-500/10 text-green-700 dark:text-green-400',
                    amber: 'bg-amber-500/10 text-amber-700 dark:text-amber-400',
                    red:   'bg-red-500/10 text-red-700 dark:text-red-400',
                  }[color];
                  return (
                    <div key={etiqueta} className={`rounded-lg p-2 text-center ${clase}`}>
                      <p className="opacity-70 mb-0.5">{etiqueta}</p>
                      <p className="font-black text-base">{valor}</p>
                    </div>
                  );
                })}
              </div>

              {conectividad.destinos_inalcanzables.length > 0 && (
                <div className="bg-red-500/5 border border-red-500/20 rounded-xl p-3">
                  <p className="text-xs font-bold text-red-600 dark:text-red-400 mb-2 flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    Destinos inalcanzables desde cualquier origen ({conectividad.destinos_inalcanzables.length})
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {conectividad.destinos_inalcanzables.map(d => (
                      <span key={d.id} className="text-[10px] bg-red-500/15 text-red-700 dark:text-red-300 px-2 py-0.5 rounded-full font-mono" title={d.nombre}>
                        {d.id}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div>
                <p className="text-xs font-semibold text-muted-foreground mb-2 uppercase tracking-wide">
                  Cobertura por centro de acopio:
                </p>
                <div className="grid grid-cols-2 gap-1.5">
                  {Object.entries(conectividad.cobertura_transitos).map(([idTransito, datosTransito]) => (
                    <div key={idTransito} className="flex items-center justify-between text-xs px-2.5 py-1.5 bg-secondary/20 rounded-lg">
                      <span className="font-mono font-bold">{idTransito}</span>
                      <span className="text-muted-foreground text-[10px] truncate mx-1">{datosTransito.nombre.replace('Acopio ', '').replace('Hub ', '')}</span>
                      <span className={`font-bold ml-auto ${datosTransito.n_destinos > 0 ? 'text-green-600 dark:text-green-400' : 'text-red-500'}`}>
                        {datosTransito.n_destinos}D
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {conectividad.resumen.grafo_sano && (
                <p className="text-xs text-green-600 dark:text-green-400 flex items-center gap-1.5 font-medium">
                  <CheckCircle className="w-3.5 h-3.5" />
                  Grafo íntegro — todos los destinos son alcanzables y no hay nodos aislados.
                </p>
              )}
            </div>
          )}
        </Card>
      )}

      {/* ── Visualización — selector Mapa / Grafo SVG ─────────────────── */}
      <Card className="glass-effect border-border/50">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base font-bold flex items-center gap-2">
              <Network className="w-4 h-4 text-blue-500" />
              Grafo Dirigido Ponderado G = (V, E)
            </CardTitle>
            <div className="flex bg-muted/40 rounded-lg p-0.5 gap-0.5">
              <button
                onClick={() => setVistaGrafo('mapa')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
                  vistaGrafo === 'mapa'
                    ? 'bg-background shadow text-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <Map className="w-3.5 h-3.5" /> OpenStreetMap
              </button>
              <button
                onClick={() => setVistaGrafo('svg')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
                  vistaGrafo === 'svg'
                    ? 'bg-background shadow text-foreground'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                <GitGraph className="w-3.5 h-3.5" /> Grafo SVG
              </button>
            </div>
          </div>
          <CardDescription className="text-xs">
            {vistaGrafo === 'mapa'
              ? 'Mapa real con OpenStreetMap. Los flujos LP se muestran como líneas (grosor = toneladas). Haz clic en nodos para ver detalles.'
              : 'Proyección geográfica SVG. Haz clic en un nodo para filtrar sus aristas.'}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {vistaGrafo === 'mapa' ? (
            <MapaAcuicola
              red={red}
              flujos={resultadoPL?.flujos || {}}
              cuellos={resultadoPL?.cuellos_botella || []}
              rutaOptima={rutaOptima}
              distribucionGA={resultadoGA}
              flujos_ag={resultadoGA?.flujos_ag || {}}
              geometriaRuta={geometriaRuta}
            />
          ) : (
            <NetworkGraphSVG
              red={red}
              flujos={resultadoPL?.flujos || {}}
              cuellos={resultadoPL?.cuellos_botella || []}
            />
          )}
        </CardContent>
      </Card>

      {/* ── Panel de optimización LP + Grafos ─────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* ── Programación Lineal ──────────────────────────────────────── */}
        <Card className="glass-effect border-border/50">
          <CardHeader className="pb-4">
            <CardTitle className="text-base font-bold flex items-center gap-2">
              <Route className="w-4 h-4 text-amber-500" />
              Modelo de Programación Lineal + Grafos
            </CardTitle>
            <CardDescription className="text-xs">
              Minimiza costos de transporte satisfaciendo toda la demanda con restricciones de capacidad y calidad.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Nodo Origen</label>
                <select
                  value={origenRuta}
                  onChange={e => setOrigenRuta(e.target.value)}
                  className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                >
                  {red?.nodos.filter(n => n.tipo !== 'destino').map(n => (
                    <option key={n.id} value={n.id}>{n.id} — {n.nombre}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-1">
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Nodo Destino</label>
                <select
                  value={destinoRuta}
                  onChange={e => setDestinoRuta(e.target.value)}
                  className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                >
                  {red?.nodos.filter(n => n.tipo === 'destino').map(n => (
                    <option key={n.id} value={n.id}>{n.id} — {n.nombre}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Algoritmo de Ruta Óptima</label>
              <select
                value={algoritmo}
                onChange={e => setAlgoritmo(e.target.value)}
                className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              >
                <option value="dijkstra">Dijkstra — menor costo (grafos sin pesos negativos)</option>
                <option value="bellman_ford">Bellman-Ford — detecta ciclos de costo negativo</option>
              </select>
            </div>

            <button
              onClick={optimizarPL}
              disabled={cargandoPL || !red}
              className="w-full h-12 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white font-bold rounded-xl flex items-center justify-center gap-2 transition-all shadow-lg shadow-blue-500/20"
            >
              {cargandoPL
                ? <><Loader2 className="w-4 h-4 animate-spin" /> Resolviendo LP...</>
                : <><Play className="w-4 h-4" /> Resolver LP + Visualizar en Mapa</>}
            </button>

            {/* Resultados LP */}
            {resultadoPL && (
              <div className="space-y-3 animate-in fade-in duration-500">
                <div className={`rounded-xl border p-3 flex items-center gap-2 text-sm font-semibold ${
                  resultadoPL.factible
                    ? 'bg-green-500/10 border-green-500/30 text-green-700 dark:text-green-400'
                    : 'bg-red-500/10 border-red-500/30 text-red-700 dark:text-red-400'
                }`}>
                  {resultadoPL.factible
                    ? <CheckCircle className="w-4 h-4" />
                    : <AlertTriangle className="w-4 h-4" />}
                  {resultadoPL.factible ? 'LP Factible — Solución óptima encontrada' : 'LP Infactible'}
                </div>

                {resultadoPL.factible && (
                  <>
                    <div className="grid grid-cols-3 gap-2">
                      <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 text-center">
                        <TrendingDown className="w-4 h-4 text-red-500 mx-auto mb-1" />
                        <p className="text-xs text-muted-foreground">Costo Total</p>
                        <p className="font-black text-red-600 dark:text-red-400 text-sm">{resultadoPL.costo_total?.toLocaleString('es-CO')}</p>
                        <p className="text-[10px] text-muted-foreground">KCOP</p>
                      </div>
                      <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-3 text-center">
                        <TrendingUp className="w-4 h-4 text-green-500 mx-auto mb-1" />
                        <p className="text-xs text-muted-foreground">Ingreso</p>
                        <p className="font-black text-green-600 dark:text-green-400 text-sm">{resultadoPL.ingreso_total?.toLocaleString('es-CO')}</p>
                        <p className="text-[10px] text-muted-foreground">KCOP</p>
                      </div>
                      <div className={`border rounded-lg p-3 text-center ${
                        resultadoPL.ganancia >= 0
                          ? 'bg-blue-500/10 border-blue-500/20'
                          : 'bg-orange-500/10 border-orange-500/20'
                      }`}>
                        <BarChart3 className={`w-4 h-4 mx-auto mb-1 ${resultadoPL.ganancia >= 0 ? 'text-blue-500' : 'text-orange-500'}`} />
                        <p className="text-xs text-muted-foreground">Ganancia</p>
                        <p className={`font-black text-sm ${resultadoPL.ganancia >= 0 ? 'text-blue-600 dark:text-blue-400' : 'text-orange-600'}`}>
                          {resultadoPL.ganancia?.toLocaleString('es-CO')}
                        </p>
                        <p className="text-[10px] text-muted-foreground">KCOP</p>
                      </div>
                    </div>

                    {resultadoPL.cuellos_botella?.length > 0 && (
                      <div className="bg-red-500/5 border border-red-500/20 rounded-xl p-3">
                        <p className="text-xs font-bold text-red-600 dark:text-red-400 mb-1.5 flex items-center gap-1.5">
                          <AlertTriangle className="w-3.5 h-3.5" /> Cuellos de botella
                        </p>
                        <div className="flex flex-wrap gap-1">
                          {resultadoPL.cuellos_botella.map(id => (
                            <span key={id} className="text-[10px] bg-red-500/20 text-red-700 dark:text-red-300 px-2 py-0.5 rounded-full font-mono">{id}</span>
                          ))}
                        </div>
                      </div>
                    )}

                    <button
                      onClick={() => setMostrarFlujos(v => !v)}
                      className="w-full flex items-center justify-between px-3 py-2 bg-secondary/30 rounded-lg text-xs font-semibold text-muted-foreground hover:bg-secondary/50 transition-colors"
                    >
                      <span>Flujos por arista ({resultadoPL.total_aristas_activas} activas)</span>
                      {mostrarFlujos ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                    </button>
                    {mostrarFlujos && (
                      <div className="max-h-48 overflow-y-auto rounded-xl border border-border/50">
                        <table className="w-full text-xs">
                          <thead className="bg-secondary/40 sticky top-0">
                            <tr>
                              <th className="px-2 py-1.5 text-left font-bold">Arista</th>
                              <th className="px-2 py-1.5 text-right font-bold">Flujo</th>
                              <th className="px-2 py-1.5 text-right font-bold">Uso%</th>
                              <th className="px-2 py-1.5 text-right font-bold">Costo</th>
                            </tr>
                          </thead>
                          <tbody>
                            {Object.entries(resultadoPL.flujos)
                              .filter(([, f]) => f.activa)
                              .sort((a, b) => b[1].flujo - a[1].flujo)
                              .map(([id, f]) => (
                                <tr key={id} className="border-t border-border/30 hover:bg-secondary/20">
                                  <td className="px-2 py-1 font-mono text-[10px]">{f.origen}→{f.destino}</td>
                                  <td className="px-2 py-1 text-right">{f.flujo.toFixed(2)}t</td>
                                  <td className={`px-2 py-1 text-right font-bold ${f.uso_pct >= 90 ? 'text-red-500' : f.uso_pct >= 70 ? 'text-amber-500' : 'text-green-500'}`}>
                                    {f.uso_pct}%
                                  </td>
                                  <td className="px-2 py-1 text-right text-muted-foreground">{f.costo_arista?.toFixed(0)}</td>
                                </tr>
                              ))
                            }
                          </tbody>
                        </table>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* ── Columna derecha: Ruta + Flujo Máximo + Métricas ─────────── */}
        <div className="space-y-4">

          {/* Ruta óptima */}
          {rutaOptima && (
            <Card className="glass-effect border-border/50">
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-bold flex items-center gap-2">
                  <Route className="w-4 h-4 text-orange-500" />
                  Ruta Óptima — {rutaOptima.algoritmo}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {rutaOptima.factible ? (
                  <>
                    {rutaOptima.via_retroceso && (
                      <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-2.5 text-xs text-amber-700 dark:text-amber-400 flex items-start gap-2">
                        <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                        <span>{rutaOptima.advertencia}</span>
                      </div>
                    )}

                    <div className="flex items-center gap-1.5 flex-wrap">
                      {rutaOptima.ruta?.map((nid, i) => (
                        <React.Fragment key={i}>
                          <span className={`text-xs font-mono px-2 py-1 rounded-lg border font-bold ${
                            i === 0
                              ? 'bg-blue-500 text-white border-blue-500'
                              : i === rutaOptima.ruta.length - 1
                              ? 'bg-green-500 text-white border-green-500'
                              : 'bg-secondary/50 border-border/50'
                          }`}>
                            {nid}
                          </span>
                          {i < rutaOptima.ruta.length - 1 && (
                            <span className={`text-xs ${rutaOptima.aristas_ruta?.[i]?.invertida ? 'text-amber-500 font-bold' : 'text-muted-foreground'}`}>
                              {rutaOptima.aristas_ruta?.[i]?.invertida ? '↩' : '→'}
                            </span>
                          )}
                        </React.Fragment>
                      ))}
                    </div>

                    <div className="grid grid-cols-3 gap-2 text-center text-xs">
                      <div className="bg-secondary/30 rounded-lg p-2">
                        <p className="text-muted-foreground">Costo total</p>
                        <p className="font-black text-orange-600 dark:text-orange-400">{rutaOptima.costo_total?.toFixed(0)} K</p>
                      </div>
                      <div className="bg-secondary/30 rounded-lg p-2">
                        <p className="text-muted-foreground">Distancia</p>
                        <p className="font-black">{rutaOptima.distancia_km} km</p>
                      </div>
                      <div className="bg-secondary/30 rounded-lg p-2">
                        <p className="text-muted-foreground">Saltos</p>
                        <p className="font-black">{rutaOptima.n_saltos}</p>
                      </div>
                    </div>
                    <p className="text-[10px] text-muted-foreground text-center">
                      {rutaOptima.via_retroceso
                        ? 'Ruta con retroceso (↩) — Los tramos invertidos se muestran punteados en el mapa'
                        : 'La ruta se resalta en naranja en el mapa'}
                    </p>
                  </>
                ) : (
                  <div className="space-y-2">
                    <p className="text-xs text-red-500 flex items-center gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5 shrink-0" /> {rutaOptima.error}
                    </p>

                    {rutaOptima.alternativas && (
                      <div className="space-y-2">
                        {rutaOptima.alternativas.desde_origen?.length > 0 && (
                          <div className="bg-blue-500/5 border border-blue-500/20 rounded-xl p-2.5">
                            <p className="text-[10px] font-bold text-blue-600 dark:text-blue-400 mb-1.5 flex items-center gap-1">
                              <CornerDownRight className="w-3 h-3" />
                              Destinos alcanzables desde {origenRuta}:
                            </p>
                            <div className="flex flex-wrap gap-1">
                              {rutaOptima.alternativas.desde_origen.map(alt => (
                                <button
                                  key={alt.id}
                                  onClick={() => setDestinoRuta(alt.id)}
                                  className="text-[10px] bg-blue-500/15 hover:bg-blue-500/30 text-blue-700 dark:text-blue-300 px-2 py-0.5 rounded-full font-mono transition-colors"
                                  title={`Seleccionar ${alt.nombre} — costo: ${alt.costo}`}
                                >
                                  {alt.id}
                                </button>
                              ))}
                            </div>
                          </div>
                        )}
                        {rutaOptima.alternativas.hacia_destino?.length > 0 && (
                          <div className="bg-green-500/5 border border-green-500/20 rounded-xl p-2.5">
                            <p className="text-[10px] font-bold text-green-600 dark:text-green-400 mb-1.5 flex items-center gap-1">
                              <CornerDownRight className="w-3 h-3" />
                              Nodos que conectan con {destinoRuta}:
                            </p>
                            <div className="flex flex-wrap gap-1">
                              {rutaOptima.alternativas.hacia_destino.map(alt => (
                                <button
                                  key={alt.id}
                                  onClick={() => setOrigenRuta(alt.id)}
                                  className="text-[10px] bg-green-500/15 hover:bg-green-500/30 text-green-700 dark:text-green-300 px-2 py-0.5 rounded-full font-mono transition-colors"
                                  title={`Seleccionar ${alt.nombre} — costo: ${alt.costo}`}
                                >
                                  {alt.id}
                                </button>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Flujo Máximo */}
          {flujoMaximo && !flujoMaximo.error && (
            <Card className="glass-effect border-border/50">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-bold flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-cyan-500" />
                  Flujo Máximo — Corte Mínimo (Edmonds-Karp)
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="grid grid-cols-2 gap-2">
                  <div className="bg-cyan-500/10 border border-cyan-500/20 rounded-lg p-2.5 text-center">
                    <p className="text-xs text-muted-foreground">Flujo máximo</p>
                    <p className="font-black text-cyan-600 dark:text-cyan-400 text-lg">{flujoMaximo.flujo_maximo} t</p>
                  </div>
                  <div className="bg-orange-500/10 border border-orange-500/20 rounded-lg p-2.5 text-center">
                    <p className="text-xs text-muted-foreground">Corte mínimo</p>
                    <p className="font-black text-orange-600 dark:text-orange-400 text-lg">{flujoMaximo.corte_minimo} t</p>
                  </div>
                </div>
                {flujoMaximo.aristas_saturadas?.length > 0 && (
                  <div className="text-xs">
                    <p className="font-semibold text-muted-foreground mb-1">Aristas saturadas:</p>
                    {flujoMaximo.aristas_saturadas.slice(0, 3).map((a, i) => (
                      <div key={i} className="flex items-center gap-1.5 py-0.5">
                        <span className="w-1.5 h-1.5 bg-red-500 rounded-full" />
                        <span className="font-mono">{a.origen}→{a.destino}</span>
                        <span className="text-muted-foreground ml-auto">{a.flujo}/{a.capacidad}t</span>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Métricas del grafo */}
          {analisisRed && (
            <Card className="glass-effect border-border/50">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-bold flex items-center gap-2">
                  <Info className="w-4 h-4 text-indigo-500" />
                  Métricas del Grafo
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-1.5 text-xs">
                  {[
                    ['Nodos |V|',       analisisRed.n_nodos],
                    ['Aristas |E|',     analisisRed.n_aristas],
                    ['Densidad',        analisisRed.densidad],
                    ['Hub más central', analisisRed.nodo_mas_central],
                  ].map(([nombre, dato]) => (
                    <div key={nombre} className="flex justify-between px-2 py-1.5 bg-secondary/20 rounded-lg">
                      <span className="text-muted-foreground">{nombre}</span>
                      <span className="font-bold">{dato}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>

      {/* ── Algoritmo Genético — Red Completa ─────────────────────────── */}
      <Card className="glass-effect border-purple-500/20 overflow-hidden">
        <CardHeader className="bg-purple-500/5 border-b border-purple-500/10">
          <div className="flex items-center gap-3">
            <div className="bg-purple-600 p-2.5 rounded-xl text-white shadow-lg shadow-purple-500/30">
              <Dna className="w-6 h-6" />
            </div>
            <div>
              <CardTitle className="text-lg font-bold">Algoritmo Genético — Red Completa</CardTitle>
              <CardDescription>
                Cromosoma = flujo en cada arista del grafo. Fitness = costo total + penalización por
                demanda incumplida y capacidad excedida. Operadores: selección por torneo, cruce aritmético
                y mutación gaussiana. Compara la solución AG con el óptimo del modelo LP.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-5">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

            {/* Configuración */}
            <div className="space-y-4">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Hub de referencia (filtro de cobertura)</label>
                <select
                  value={transitoGA}
                  onChange={e => setTransitoGA(e.target.value)}
                  className="w-full px-3 py-2 bg-background border border-border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/50"
                >
                  {NODOS_TRANSITO.map(t => (
                    <option key={t.id} value={t.id}>{t.id} — {t.nombre}</option>
                  ))}
                </select>
                <p className="text-[10px] text-muted-foreground">
                  El AG optimiza la red completa. Este hub filtra la cobertura de demanda en los resultados.
                </p>
              </div>

              <button
                onClick={() => setMostrarParametrosGA(v => !v)}
                className="w-full flex items-center justify-between px-3 py-2 bg-purple-500/5 border border-purple-500/20 rounded-lg text-xs font-semibold text-purple-700 dark:text-purple-300 hover:bg-purple-500/10 transition-colors"
              >
                <span>Ajustes avanzados del AG</span>
                {mostrarParametrosGA ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              </button>

              {mostrarParametrosGA && (
                <div className="grid grid-cols-2 gap-3 p-3 bg-secondary/20 rounded-xl border border-border/50">
                  {[
                    { clave: 'tamano_poblacion', etiqueta: 'Población',     minimo: 20,   maximo: 300,  paso: 10   },
                    { clave: 'generaciones',     etiqueta: 'Generaciones',  minimo: 50,   maximo: 500,  paso: 10   },
                    { clave: 'tasa_cruce',       etiqueta: 'Tasa cruce',    minimo: 0.5,  maximo: 1.0,  paso: 0.05 },
                    { clave: 'tasa_mutacion',    etiqueta: 'Tasa mutación', minimo: 0.01, maximo: 0.5,  paso: 0.01 },
                    { clave: 'elitismo',         etiqueta: 'Elitismo',      minimo: 1,    maximo: 20,   paso: 1    },
                  ].map(({ clave, etiqueta, minimo, maximo, paso }) => (
                    <div key={clave} className="space-y-1">
                      <label className="text-[10px] font-semibold text-muted-foreground uppercase">{etiqueta}</label>
                      <input
                        type="number"
                        value={parametrosGA[clave]}
                        onChange={e => setParametrosGA(prev => ({ ...prev, [clave]: parseFloat(e.target.value) }))}
                        min={minimo} max={maximo} step={paso}
                        className="w-full px-2 py-1 bg-background border border-border rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-purple-500/40"
                      />
                    </div>
                  ))}
                </div>
              )}

              <button
                onClick={optimizarDistribucion}
                disabled={cargandoGA || !red}
                className="w-full h-12 bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white font-bold rounded-xl flex items-center justify-center gap-2 transition-all shadow-lg shadow-purple-500/20"
              >
                {cargandoGA
                  ? <><Loader2 className="w-4 h-4 animate-spin" /> Ejecutando AG ({parametrosGA.generaciones} gen.)...</>
                  : <><Dna className="w-4 h-4" /> Optimizar Red con Algoritmo Genético</>}
              </button>
            </div>

            {/* Resultado GA */}
            <div>
              {resultadoGA ? (
                <div className="space-y-4 animate-in fade-in duration-500">

                  {/* ── Comparación LP vs AG ──────────────────────────────── */}
                  {resultadoGA.comparacion_lp_ag && (
                    <div className="grid grid-cols-3 gap-2">
                      <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-3 text-center">
                        <TrendingDown className="w-4 h-4 text-blue-500 mx-auto mb-1" />
                        <p className="text-[10px] text-muted-foreground">Costo LP (óptimo)</p>
                        <p className="font-black text-blue-600 dark:text-blue-400 text-sm leading-tight">
                          {resultadoGA.comparacion_lp_ag.costo_lp != null
                            ? Number(resultadoGA.comparacion_lp_ag.costo_lp).toLocaleString('es-CO')
                            : '—'}
                        </p>
                        <p className="text-[10px] text-muted-foreground">KCOP</p>
                      </div>
                      <div className="bg-purple-500/10 border border-purple-500/20 rounded-xl p-3 text-center">
                        <Dna className="w-4 h-4 text-purple-500 mx-auto mb-1" />
                        <p className="text-[10px] text-muted-foreground">Costo AG</p>
                        <p className="font-black text-purple-600 dark:text-purple-400 text-sm leading-tight">
                          {Number(resultadoGA.comparacion_lp_ag.costo_ag).toLocaleString('es-CO')}
                        </p>
                        <p className="text-[10px] text-muted-foreground">KCOP</p>
                      </div>
                      <div className={`border rounded-xl p-3 text-center ${
                        resultadoGA.comparacion_lp_ag.gap_pct == null
                          ? 'bg-red-500/10 border-red-500/20'
                          : (resultadoGA.comparacion_lp_ag.gap_pct < 20
                            ? 'bg-green-500/10 border-green-500/20'
                            : 'bg-amber-500/10 border-amber-500/20')
                      }`}>
                        <BarChart3 className={`w-4 h-4 mx-auto mb-1 ${
                          resultadoGA.comparacion_lp_ag.gap_pct == null
                            ? 'text-red-500'
                            : (resultadoGA.comparacion_lp_ag.gap_pct < 20 ? 'text-green-500' : 'text-amber-500')
                        }`} />
                        <p className="text-[10px] text-muted-foreground">Gap AG vs LP</p>
                        <p className={`font-black text-sm leading-tight ${
                          resultadoGA.comparacion_lp_ag.gap_pct == null
                            ? 'text-red-600 dark:text-red-400'
                            : (resultadoGA.comparacion_lp_ag.gap_pct < 20
                              ? 'text-green-600 dark:text-green-400'
                              : 'text-amber-600 dark:text-amber-400')
                        }`}>
                          {resultadoGA.comparacion_lp_ag.gap_pct != null
                            ? `+${resultadoGA.comparacion_lp_ag.gap_pct}%`
                            : 'Infact.'}
                        </p>
                        <p className="text-[10px] text-muted-foreground">
                          {resultadoGA.comparacion_lp_ag.gap_pct != null ? 'vs óptimo' : 'demanda incompleta'}
                        </p>
                      </div>
                    </div>
                  )}

                  {/* ── Gráfica de convergencia ───────────────────────────── */}
                  {resultadoGA.historial_fitness?.length > 1 && (() => {
                    const valores   = resultadoGA.historial_fitness;
                    const valorMax  = Math.max(...valores);
                    const valorMin  = Math.min(...valores);
                    const paso      = Math.max(1, Math.floor(valores.length / 80));
                    const muestras  = valores.filter((_, i) => i % paso === 0 || i === valores.length - 1);
                    return (
                      <div>
                        <p className="text-xs font-semibold text-muted-foreground mb-1 uppercase tracking-wide">
                          Convergencia AG — fitness por generación (↓ decrece):
                        </p>
                        <div className="flex items-end gap-px h-16 bg-purple-500/5 rounded-lg p-1">
                          {muestras.map((val, i) => {
                            const altura = valorMax === valorMin ? 50 : ((val - valorMin) / (valorMax - valorMin)) * 100;
                            return (
                              <div
                                key={i}
                                className="flex-1 bg-purple-500/70 rounded-t transition-all"
                                style={{ height: `${Math.max(4, altura)}%` }}
                                title={`Gen ${i * paso + 1}: ${val.toLocaleString('es-CO')}`}
                              />
                            );
                          })}
                        </div>
                        <div className="flex justify-between text-[10px] text-muted-foreground mt-0.5 px-1">
                          <span>Gen 1: {valores[0].toLocaleString('es-CO')}</span>
                          <span>Gen {valores.length}: {valores[valores.length - 1].toLocaleString('es-CO')}</span>
                        </div>
                      </div>
                    );
                  })()}

                  {/* ── Cobertura de demanda ──────────────────────────────── */}
                  {resultadoGA.cobertura_demanda?.length > 0 && (() => {
                    const satisfechas   = resultadoGA.cobertura_demanda.filter(d => d.satisfecha).length;
                    const totalDestinos = resultadoGA.cobertura_demanda.length;
                    const hayHub        = resultadoGA.cobertura_hub?.length > 0;
                    const datosHub      = (hayHub && !resultadoGA._verTodos)
                      ? resultadoGA.cobertura_hub
                      : resultadoGA.cobertura_demanda;
                    const etiqueta      = (hayHub && !resultadoGA._verTodos)
                      ? `Zona ${transitoGA} — ${resultadoGA.cobertura_hub.filter(d => d.satisfecha).length}/${resultadoGA.cobertura_hub.length} sat.`
                      : `Red completa — ${satisfechas}/${totalDestinos} destinos satisfechos`;
                    return (
                      <div>
                        <p className="text-xs font-semibold text-muted-foreground mb-2 uppercase tracking-wide flex items-center gap-2">
                          <span>Cobertura de demanda</span>
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                            satisfechas === totalDestinos
                              ? 'bg-green-500/15 text-green-700 dark:text-green-400'
                              : 'bg-amber-500/15 text-amber-700 dark:text-amber-400'
                          }`}>
                            {etiqueta}
                          </span>
                        </p>
                        <div className="max-h-36 overflow-y-auto space-y-0.5 rounded-lg border border-border/40">
                          {datosHub.map((d, i) => (
                            <div key={i} className={`flex items-center gap-2 text-xs px-2 py-1 ${
                              d.satisfecha ? 'bg-green-500/8' : 'bg-amber-500/8'
                            }`}>
                              <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${d.satisfecha ? 'bg-green-500' : 'bg-amber-400'}`} />
                              <span className="font-mono font-bold w-8 shrink-0">{d.id}</span>
                              <span className="text-muted-foreground text-[10px] flex-1 truncate">{d.nombre}</span>
                              <span className={`font-bold shrink-0 ${d.satisfecha ? 'text-green-600 dark:text-green-400' : 'text-amber-600'}`}>
                                {d.flujo_ag.toFixed(1)}/{d.demanda}t
                              </span>
                            </div>
                          ))}
                        </div>
                        {hayHub && (
                          <button
                            className="mt-1.5 text-[10px] text-purple-600 dark:text-purple-400 hover:underline"
                            onClick={() => setResultadoGA(prev => ({ ...prev, _verTodos: !prev._verTodos }))}
                          >
                            {resultadoGA._verTodos ? '▲ Ver solo zona hub' : `▼ Ver los ${totalDestinos} destinos`}
                          </button>
                        )}
                      </div>
                    );
                  })()}

                  <p className="text-[10px] text-muted-foreground text-center">
                    Los flujos AG aparecen en morado en el mapa
                  </p>
                </div>
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-center p-8 border border-dashed border-purple-500/20 rounded-xl bg-purple-500/5">
                  <Dna className="w-10 h-10 text-purple-500/40 mb-3" />
                  <p className="text-sm font-medium text-muted-foreground">
                    Selecciona un hub de referencia y ejecuta el AG
                  </p>
                  <p className="text-xs text-muted-foreground/70 mt-1">
                    El AG optimiza flujos en la red completa y compara con el LP
                  </p>
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default AcuicolaPanel;
