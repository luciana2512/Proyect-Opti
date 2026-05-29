import React, { useEffect, useRef, useState } from 'react';
import { MapContainer, TileLayer, Marker, Polyline, Popup, Tooltip, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import axios from 'axios';

// ── Configuración visual por tipo de nodo ─────────────────────────────────────
const TIPO_CFG = {
  origen:  { emoji: '🏭', bg: '#2563eb', border: '#1d4ed8', size: 36, label: 'Estación de Origen' },
  transito:{ emoji: '🏪', bg: '#b45309', border: '#92400e', size: 32, label: 'Centro de Acopio' },
  destino: { emoji: '🛒', bg: '#059669', border: '#047857', size: 26, label: 'Supermercado' },
};

// ── Crea un DivIcon de Leaflet con emoji + anillo de cuello de botella ────────
function crearIconoNodo(tipo, enRuta = false, esCuello = false, enAG = false) {
  const cfg  = TIPO_CFG[tipo] || TIPO_CFG.destino;
  const bg   = enRuta ? '#f97316' : cfg.bg;
  const brd  = enRuta ? '#ea580c' : cfg.border;
  const sz   = cfg.size;
  const warn = esCuello
    ? `<span style="position:absolute;top:-7px;right:-7px;font-size:13px;line-height:1;filter:drop-shadow(0 1px 2px #000)">⚠️</span>`
    : '';
  const agDot = enAG
    ? `<span style="position:absolute;bottom:-4px;right:-4px;width:10px;height:10px;background:#a855f7;border-radius:50%;border:2px solid white"></span>`
    : '';
  return L.divIcon({
    className: '',
    html: `<div style="
      position:relative;
      width:${sz}px;height:${sz}px;
      background:${bg};
      border-radius:50%;
      display:flex;align-items:center;justify-content:center;
      font-size:${Math.round(sz * 0.52)}px;
      border:2.5px solid ${brd};
      box-shadow:0 2px 8px rgba(0,0,0,0.35);
      cursor:pointer;
      ${esCuello ? 'outline:3px solid #ef4444;outline-offset:2px;' : ''}
    ">${cfg.emoji}${warn}${agDot}</div>`,
    iconSize:    [sz, sz],
    iconAnchor:  [sz / 2, sz / 2],
    popupAnchor: [0, -(sz / 2 + 4)],
  });
}

// ── Ajusta la vista para mostrar TODOS los nodos ──────────────────────────────
function FitBounds({ nodos }) {
  const map = useMap();
  useEffect(() => {
    if (!nodos || nodos.length === 0) return;
    const lats = nodos.map(n => n.lat);
    const lons = nodos.map(n => n.lon);
    map.fitBounds(
      [[Math.min(...lats) - 0.5, Math.min(...lons) - 0.8],
       [Math.max(...lats) + 0.5, Math.max(...lons) + 0.8]],
      { padding: [30, 30], animate: true }
    );
  }, [nodos, map]);
  return null;
}

// ── Animación del camión sobre la ruta óptima ─────────────────────────────────
function AnimacionCamion({ puntos }) {
  const map = useMap();
  const markerRef = useRef(null);
  const animRef   = useRef(null);
  const stepRef   = useRef(0);
  const lastTs    = useRef(0);

  useEffect(() => {
    if (!puntos || puntos.length < 2) return;
    const esOSM       = puntos.length > 30;
    const stepsPerSeg = esOSM ? 1 : 30;
    const segments = [];
    for (let i = 0; i < puntos.length - 1; i++) {
      const [la1, lo1] = puntos[i];
      const [la2, lo2] = puntos[i + 1];
      for (let s = 0; s < stepsPerSeg; s++) {
        const t = s / stepsPerSeg;
        segments.push([la1 + (la2 - la1) * t, lo1 + (lo2 - lo1) * t]);
      }
    }
    segments.push(puntos[puntos.length - 1]);
    const icon = L.divIcon({
      className: '',
      html: `<div style="font-size:22px;filter:drop-shadow(0 2px 4px rgba(0,0,0,0.4))">🚛</div>`,
      iconSize: [28, 28], iconAnchor: [14, 14],
    });
    if (markerRef.current) markerRef.current.remove();
    markerRef.current = L.marker(segments[0], { icon }).addTo(map);
    stepRef.current = 0;
    const msPerStep = 30000 / segments.length;
    const animate = (ts) => {
      if (ts - lastTs.current >= msPerStep) {
        if (stepRef.current >= segments.length) stepRef.current = 0;
        if (markerRef.current) markerRef.current.setLatLng(segments[stepRef.current]);
        stepRef.current++;
        lastTs.current = ts;
      }
      animRef.current = requestAnimationFrame(animate);
    };
    animRef.current = requestAnimationFrame(animate);
    return () => {
      cancelAnimationFrame(animRef.current);
      if (markerRef.current) { markerRef.current.remove(); markerRef.current = null; }
    };
  }, [puntos, map]);
  return null;
}

// ── Componente principal ──────────────────────────────────────────────────────
const MapaAcuicola = ({
  red,
  flujos    = {},
  cuellos   = [],
  rutaOptima    = null,
  distribucionGA = null,
  flujos_ag      = {},
  geometriaRuta  = [],
}) => {
  const [capas,   setCapas]   = useState({ inactivas: true, activas: true, optima: true, ga: true });
  const [animando, setAnimando] = useState(false);
  // Geometrías OSRM por arista: { "E1": [[lat,lon],…], "E1_ag": [[lat,lon],…], … }
  const [geoAristas, setGeoAristas] = useState({});
  const [cargandoGeo, setCargandoGeo] = useState(false);
  const pendienteRef = useRef(new Set());

  // ── Fetch OSRM en batch para todas las aristas activas ───────────────────
  useEffect(() => {
    if (!red) return;

    const toFetch = [];
    // LP activas
    for (const [id, f] of Object.entries(flujos)) {
      if (f.activa && !geoAristas[id] && !pendienteRef.current.has(id)) {
        toFetch.push({ id, origen: f.origen, destino: f.destino });
      }
    }
    // AG activas (clave con sufijo _ag para separar del LP)
    for (const [id, f] of Object.entries(flujos_ag)) {
      const key = id + '_ag';
      if (f.activa && !geoAristas[key] && !pendienteRef.current.has(key)) {
        toFetch.push({ id: key, origen: f.origen, destino: f.destino });
      }
    }
    // Cuellos de botella
    for (const cid of cuellos) {
      const a = red.aristas.find(x => x.id === cid);
      if (a && !geoAristas[cid + '_cuello'] && !pendienteRef.current.has(cid + '_cuello')) {
        toFetch.push({ id: cid + '_cuello', origen: a.origen, destino: a.destino });
      }
    }

    if (toFetch.length === 0) return;
    toFetch.forEach(e => pendienteRef.current.add(e.id));
    setCargandoGeo(true);

    axios.post('/api/acuicola/geometria_aristas', { aristas: toFetch }, { timeout: 60000 })
      .then(resp => {
        const datos = resp.data || {};
        const validos = Object.fromEntries(
          Object.entries(datos).filter(([, geo]) => Array.isArray(geo) && geo.length >= 2)
        );
        if (Object.keys(validos).length > 0) {
          setGeoAristas(prev => ({ ...prev, ...validos }));
        }
        setCargandoGeo(false);
        toFetch.forEach(e => pendienteRef.current.delete(e.id));
      })
      .catch(err => {
        console.warn('[OSRM] Error al obtener geometría de aristas:', err.message);
        setCargandoGeo(false);
        toFetch.forEach(e => pendienteRef.current.delete(e.id));
      });
  }, [flujos, flujos_ag, cuellos, red]);

  if (!red) return (
    <div className="flex items-center justify-center h-64 text-muted-foreground text-sm bg-muted/20 rounded-xl border border-border/50">
      Carga la red para ver el mapa
    </div>
  );

  const nodoMap = Object.fromEntries(red.nodos.map(n => [n.id, n]));

  // ── Flujo máximo (para escalar grosor proporcional) ───────────────────────
  const flujoMaxLP = Math.max(
    0.01,
    ...Object.values(flujos).map(f => f.flujo || 0)
  );
  const flujoMaxAG = Math.max(
    0.01,
    ...Object.values(flujos_ag).map(f => f.flujo || 0)
  );
  const pesoLP = flujo => 1 + (flujo / flujoMaxLP) * 6;
  const pesoAG = flujo => 1 + (flujo / flujoMaxAG) * 6;

  // ── Nodos involucrados en cuellos de botella ──────────────────────────────
  const nodosEnCuellos = new Set(
    red.aristas
      .filter(a => cuellos.includes(a.id))
      .flatMap(a => [a.origen, a.destino])
  );

  // ── Nodos con flujo AG activo ─────────────────────────────────────────────
  const nodosEnAG = new Set(
    Object.values(flujos_ag)
      .filter(f => f.activa)
      .flatMap(f => [f.origen, f.destino])
  );

  // ── Preparar aristas para render ─────────────────────────────────────────
  const aristasRender = red.aristas.map(a => {
    const o = nodoMap[a.origen], d = nodoMap[a.destino];
    if (!o || !d) return null;
    const f    = flujos[a.id];
    const flujo = f?.flujo || 0;
    return {
      ...a, o, d, flujo,
      activa:    flujo > 0.01,
      esCuello:  cuellos.includes(a.id),
      costo_arista: f?.costo_arista,
    };
  }).filter(Boolean);

  const aristasAGRender = Object.keys(flujos_ag).length > 0
    ? red.aristas.map(a => {
        const o = nodoMap[a.origen], d = nodoMap[a.destino];
        if (!o || !d) return null;
        const f = flujos_ag[a.id];
        if (!f?.activa) return null;
        return {
          ...a, o, d,
          flujo:       f.flujo,
          costo_arista: round2(f.flujo * a.distancia_km * a.costo_por_ton_km),
        };
      }).filter(Boolean)
    : [];

  // ── Ruta óptima ──────────────────────────────────────────────────────────
  const puntosRuta = (() => {
    if (!rutaOptima?.factible || !rutaOptima.ruta) return [];
    if (geometriaRuta.length > 2) return geometriaRuta;
    return rutaOptima.ruta
      .map(id => { const n = nodoMap[id]; return n ? [n.lat, n.lon] : null; })
      .filter(Boolean);
  })();
  const usandoOSM = geometriaRuta.length > 2;

  // Ruta GA TSP local (legado)
  const puntosGA = distribucionGA?.ruta_detalle
    ? (() => {
        const pts = distribucionGA.ruta_detalle.map(seg => {
          const n = nodoMap[seg.desde]; return n ? [n.lat, n.lon] : null;
        }).filter(Boolean);
        const ult = distribucionGA.ruta_detalle.slice(-1)[0];
        if (ult) { const n = nodoMap[ult.hasta]; if (n) pts.push([n.lat, n.lon]); }
        return pts;
      })()
    : [];

  const toggle = key => setCapas(p => ({ ...p, [key]: !p[key] }));

  // ── Helper para posiciones OSRM o fallback a recta ───────────────────────
  const posiciones = (cacheKey, o, d) =>
    geoAristas[cacheKey]?.length > 1
      ? geoAristas[cacheKey]
      : [[o.lat, o.lon], [d.lat, d.lon]];

  return (
    <div className="space-y-3">
      {/* ── Controles de capas ──────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-2 text-xs items-center">
        <span className="font-semibold text-muted-foreground uppercase tracking-wider">Capas:</span>
        {[
          { key: 'inactivas', color: '#94a3b8', label: 'Todas las rutas' },
          { key: 'activas',   color: '#3b82f6', label: 'Flujos LP' },
          { key: 'optima',    color: '#f97316', label: 'Ruta óptima' },
          { key: 'ga',        color: '#a855f7', label: 'Flujos AG' },
        ].map(({ key, color, label }) => (
          <button key={key} onClick={() => toggle(key)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border transition-all font-medium ${
              capas[key] ? 'bg-card border-border/70' : 'bg-muted/30 border-border/30 opacity-40'
            }`}>
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
            {label}
          </button>
        ))}

        {rutaOptima?.factible && (
          <span className={`flex items-center gap-1 px-2.5 py-1 rounded-full border text-[10px] font-semibold ${
            usandoOSM
              ? 'bg-orange-500/10 border-orange-500/30 text-orange-600'
              : 'bg-muted/20 border-border/40 text-muted-foreground'
          }`}>
            {usandoOSM ? '🛣 Calles OSM reales' : '📐 Línea recta (cargando…)'}
          </span>
        )}

        {cargandoGeo && (
          <span className="flex items-center gap-1 px-2.5 py-1 rounded-full border text-[10px] font-semibold bg-amber-500/10 border-amber-500/30 text-amber-600">
            ⏳ Cargando rutas OSM…
          </span>
        )}
        {!cargandoGeo && Object.keys(geoAristas).length > 0 && (
          <span className="flex items-center gap-1 px-2.5 py-1 rounded-full border text-[10px] font-semibold bg-blue-500/10 border-blue-500/30 text-blue-600">
            🗺 {Object.keys(geoAristas).length} aristas con ruta OSM
          </span>
        )}

        {puntosRuta.length > 1 && (
          <button onClick={() => setAnimando(v => !v)}
            className={`ml-auto flex items-center gap-1.5 px-3 py-1 rounded-full border font-semibold transition-all ${
              animando ? 'bg-orange-500 text-white border-orange-500' : 'bg-card border-border/70 hover:border-orange-400'
            }`}>
            {animando ? '⏹ Detener camión' : '🚛 Animar recorrido'}
          </button>
        )}
      </div>

      {/* ── Mapa ─────────────────────────────────────────────────────────── */}
      <div className="rounded-xl overflow-hidden border border-border/50" style={{ height: 520 }}>
        <MapContainer center={[5.0265, -74.747]} zoom={6} style={{ height: '100%', width: '100%' }}>
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            attribution='&copy; <a href="https://openstreetmap.org">OpenStreetMap</a>'
          />
          <FitBounds nodos={red.nodos} />

          {/* ── Aristas inactivas (sin flujo LP) ─── */}
          {capas.inactivas && aristasRender
            .filter(a => !a.activa && !a.esCuello)
            .map(a => (
              <Polyline key={a.id + '-i'}
                positions={[[a.o.lat, a.o.lon], [a.d.lat, a.d.lon]]}
                pathOptions={{ color: '#64748b', weight: 1.5, opacity: 0.45, dashArray: '5 6' }}>
                <Tooltip sticky>
                  <div style={{ fontSize: 11 }}>
                    <b>{a.o.id} → {a.d.id}</b><br />
                    {a.descripcion || a.id}<br />
                    Dist: {a.distancia_km} km · Cap: {a.capacidad_ton} t
                  </div>
                </Tooltip>
              </Polyline>
            ))
          }

          {/* ── Flujos LP activos (azul) y cuellos de botella (rojo) ─── */}
          {capas.activas && aristasRender
            .filter(a => a.activa || a.esCuello)
            .map(a => {
              const color    = a.esCuello ? '#ef4444' : '#3b82f6';
              const peso     = a.esCuello ? Math.max(4, pesoLP(a.flujo)) : pesoLP(a.flujo);
              const cacheKey = a.esCuello ? a.id + '_cuello' : a.id;
              return (
                <Polyline key={a.id + '-a'}
                  positions={posiciones(cacheKey, a.o, a.d)}
                  pathOptions={{ color, weight: peso, opacity: 0.9, lineJoin: 'round', lineCap: 'round' }}>
                  <Tooltip sticky>
                    <div style={{ fontSize: 11, lineHeight: 1.5 }}>
                      <b>{a.o.id} → {a.d.id}</b>
                      {a.esCuello && <span style={{ color: '#ef4444', fontWeight: 700 }}> ⚠ Cuello</span>}<br />
                      {a.descripcion || a.id}<br />
                      Flujo: <b>{a.flujo.toFixed(2)} t</b> · Uso: {flujos[a.id]?.uso_pct || 0}%<br />
                      Costo: {a.costo_arista != null ? a.costo_arista.toFixed(0) + ' KCOP' : '—'}<br />
                      Distancia: {a.distancia_km} km
                    </div>
                  </Tooltip>
                  <Popup>
                    <div className="text-xs space-y-0.5 min-w-[180px]">
                      <p className="font-bold text-sm">{a.o.id} → {a.d.id}</p>
                      <p className="text-gray-500">{a.descripcion || a.id}</p>
                      <p>Flujo LP: <strong>{a.flujo.toFixed(2)} t</strong></p>
                      <p>Capacidad: {a.capacidad_ton} t · Uso: {flujos[a.id]?.uso_pct || 0}%</p>
                      {a.costo_arista != null && <p>Costo: <strong>{a.costo_arista.toFixed(0)} KCOP</strong></p>}
                      <p>Distancia: {a.distancia_km} km</p>
                      {a.esCuello && <p className="text-red-600 font-bold">⚠ Cuello de botella</p>}
                    </div>
                  </Popup>
                </Polyline>
              );
            })
          }

          {/* ── Ruta óptima (naranja) ─── */}
          {capas.optima && puntosRuta.length > 1 && (
            <Polyline
              positions={puntosRuta}
              pathOptions={{
                color: '#f97316', weight: 6, opacity: 0.95,
                dashArray: usandoOSM ? undefined : '12 5',
                lineJoin: 'round', lineCap: 'round',
              }}
            />
          )}

          {/* ── Ruta GA TSP local (morado, legado) ─── */}
          {capas.ga && puntosGA.length > 1 && (
            <Polyline positions={puntosGA}
              pathOptions={{ color: '#a855f7', weight: 4, opacity: 0.9, dashArray: '8 4' }} />
          )}

          {/* ── Flujos AG red completa (morado punteado, OSRM) ─── */}
          {capas.ga && aristasAGRender.map(a => (
            <Polyline key={a.id + '-ag'}
              positions={posiciones(a.id + '_ag', a.o, a.d)}
              pathOptions={{
                color: '#a855f7',
                weight: pesoAG(a.flujo),
                opacity: 0.85,
                dashArray: '7 4',
                lineJoin: 'round',
                lineCap: 'round',
              }}>
              <Tooltip sticky>
                <div style={{ fontSize: 11, lineHeight: 1.5 }}>
                  <b>{a.o.id} → {a.d.id}</b> <span style={{ color: '#a855f7' }}>AG</span><br />
                  {a.descripcion || a.id}<br />
                  Flujo AG: <b>{a.flujo.toFixed(2)} t</b><br />
                  Costo: {a.costo_arista != null ? a.costo_arista.toFixed(0) + ' KCOP' : '—'}<br />
                  Distancia: {a.distancia_km} km
                </div>
              </Tooltip>
              <Popup>
                <div className="text-xs space-y-0.5 min-w-[180px]">
                  <p className="font-bold text-sm">{a.o.id} → {a.d.id} <span className="text-purple-600">(AG)</span></p>
                  <p className="text-gray-500">{a.descripcion || a.id}</p>
                  <p>Flujo AG: <strong>{a.flujo.toFixed(2)} t</strong></p>
                  <p>Capacidad: {a.capacidad_ton} t</p>
                  {a.costo_arista != null && <p>Costo: <strong>{a.costo_arista.toFixed(0)} KCOP</strong></p>}
                  <p>Distancia: {a.distancia_km} km</p>
                </div>
              </Popup>
            </Polyline>
          ))}

          {/* ── Camión animado ─── */}
          {animando && puntosRuta.length > 1 && <AnimacionCamion puntos={puntosRuta} />}

          {/* ── Nodos con iconos diferenciados ─── */}
          {red.nodos.map(n => {
            const enRuta   = rutaOptima?.ruta?.includes(n.id);
            const esCuello = nodosEnCuellos.has(n.id);
            const enAG     = nodosEnAG.has(n.id);
            const icono    = crearIconoNodo(n.tipo, enRuta, esCuello, enAG);
            const cfg      = TIPO_CFG[n.tipo] || TIPO_CFG.destino;
            return (
              <Marker key={n.id} position={[n.lat, n.lon]} icon={icono}>
                <Tooltip>
                  <div style={{ fontSize: 11, lineHeight: 1.4 }}>
                    <b>{n.nombre}</b><br />
                    {n.id} — {cfg.label}
                    {n.tipo === 'origen'   && <><br />Oferta: {n.oferta} t/sem</>}
                    {n.tipo === 'transito' && <><br />Cap: {n.capacidad} t · Calidad: {(n.calidad * 100).toFixed(0)}%</>}
                    {n.tipo === 'destino'  && <><br />Demanda: {n.demanda} t/sem</>}
                    {esCuello && <><br /><span style={{ color: '#ef4444', fontWeight: 700 }}>⚠ Cuello de botella</span></>}
                  </div>
                </Tooltip>
                <Popup>
                  <div className="text-xs space-y-0.5 min-w-[160px]">
                    <p className="font-bold text-sm">{n.nombre}</p>
                    <p className="text-gray-500">{n.id} — {cfg.label}</p>
                    {n.tipo === 'origen'   && <p>Oferta: <strong>{n.oferta} t/sem</strong></p>}
                    {n.tipo === 'transito' && <>
                      <p>Capacidad: <strong>{n.capacidad} t</strong></p>
                      <p>Calidad: <strong>{(n.calidad * 100).toFixed(0)}%</strong></p>
                      <p>Merma: <strong>{(n.merma * 100).toFixed(0)}%</strong></p>
                    </>}
                    {n.tipo === 'destino'  && <p>Demanda: <strong>{n.demanda} t/sem</strong></p>}
                    {esCuello && <p className="text-red-600 font-bold">⚠ Cuello de botella</p>}
                    {enAG && <p className="text-purple-600 font-semibold">● Con flujo AG</p>}
                  </div>
                </Popup>
              </Marker>
            );
          })}
        </MapContainer>
      </div>

      {/* ── Leyenda ──────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-x-5 gap-y-1.5 text-xs font-medium text-muted-foreground px-1">
        {[
          { emoji: '🏭', label: 'Estación origen', color: '#2563eb' },
          { emoji: '🏪', label: 'Centro de acopio', color: '#b45309' },
          { emoji: '🛒', label: 'Supermercado', color: '#059669' },
        ].map(({ emoji, label, color }) => (
          <span key={label} className="flex items-center gap-1.5">
            <span style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              width: 20, height: 20, borderRadius: '50%', background: color,
              fontSize: 11, border: '2px solid rgba(255,255,255,0.7)',
            }}>{emoji}</span>
            {label}
          </span>
        ))}
        <span className="flex items-center gap-1.5 ml-2">
          <span className="w-6 h-px border-t-2 border-dashed inline-block" style={{ borderColor: '#64748b' }} />
          Sin flujo
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-6 h-1 rounded inline-block" style={{ background: '#3b82f6' }} />
          Flujo LP
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-6 h-1 rounded inline-block" style={{ background: '#f97316' }} />
          Ruta óptima {usandoOSM ? '(OSM)' : ''}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-6 h-px border-t-2 border-dashed inline-block" style={{ borderColor: '#a855f7' }} />
          Flujos AG (OSM)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-6 h-1 rounded inline-block bg-red-500" />
          Cuello de botella
        </span>
        <span className="flex items-center gap-1.5">
          ⚠️ <span>Nodo en cuello</span>
        </span>
      </div>
    </div>
  );
};

// Pequeño helper para redondeo
function round2(v) { return Math.round(v * 100) / 100; }

export default MapaAcuicola;
