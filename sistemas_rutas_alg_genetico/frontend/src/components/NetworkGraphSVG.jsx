import React, { useMemo, useState, useRef, useCallback, useEffect } from 'react';

const TIPO_COLOR = {
  origen:  { fill: '#3b82f6', stroke: '#1d4ed8', label: 'Origen',           ring: '#93c5fd' },
  transito:{ fill: '#f59e0b', stroke: '#b45309', label: 'Centro de Acopio', ring: '#fde68a' },
  destino: { fill: '#10b981', stroke: '#059669', label: 'Supermercado',      ring: '#6ee7b7' },
};

const RADIO = { origen: 16, transito: 13, destino: 9 };

// Canvas interno del SVG
const W = 1300, H = 820;

function proyectar(lat, lon, minLat, maxLat, minLon, maxLon, pad = 70) {
  const x = pad + ((lon - minLon) / (maxLon - minLon)) * (W - 2 * pad);
  const y = pad + ((maxLat - lat) / (maxLat - minLat)) * (H - 2 * pad);
  return { x, y };
}

/**
 * Algoritmo de separación iterativa por repulsión:
 * empuja los nodos que se solapan hasta que todos tengan
 * al menos (ri + rj + margen) píxeles entre sus centros.
 */
function separar(posiciones, nodos, iteraciones = 150, margen = 12) {
  const ids = nodos.map(n => n.id);
  const pos = {};
  ids.forEach(id => { pos[id] = { ...posiciones[id] }; });

  for (let iter = 0; iter < iteraciones; iter++) {
    for (let i = 0; i < ids.length; i++) {
      for (let j = i + 1; j < ids.length; j++) {
        const pi = pos[ids[i]], pj = pos[ids[j]];
        const dx = pj.x - pi.x;
        const dy = pj.y - pi.y;
        const d  = Math.sqrt(dx * dx + dy * dy) || 0.001;
        const ri = RADIO[nodos[i].tipo] || 9;
        const rj = RADIO[nodos[j].tipo] || 9;
        const dMin = ri + rj + margen;
        if (d < dMin) {
          const push = (dMin - d) * 0.5;
          const ux = dx / d, uy = dy / d;
          pos[ids[i]] = { x: pi.x - ux * push, y: pi.y - uy * push };
          pos[ids[j]] = { x: pj.x + ux * push, y: pj.y + uy * push };
        }
      }
    }
  }
  return pos;
}

const NetworkGraphSVG = ({ red, flujos = {}, cuellos = [] }) => {
  const svgRef = useRef(null);

  const [tooltip, setTooltip]       = useState(null);
  const [nodoFiltro, setNodoFiltro] = useState(null);
  const [transform, setTransform]   = useState({ x: 0, y: 0, scale: 1 });
  const dragging = useRef(false);
  const lastPos  = useRef({ x: 0, y: 0 });

  // ── Datos derivados ──────────────────────────────────────────────────────
  const nodoMap = useMemo(() => {
    if (!red) return {};
    return Object.fromEntries(red.nodos.map(n => [n.id, n]));
  }, [red]);

  const posiciones = useMemo(() => {
    if (!red) return {};
    const lats = red.nodos.map(n => n.lat);
    const lons = red.nodos.map(n => n.lon);
    // Márgenes geográficos para no pegar nodos al borde
    const minLat = Math.min(...lats) - 0.4;
    const maxLat = Math.max(...lats) + 0.4;
    const minLon = Math.min(...lons) - 0.6;
    const maxLon = Math.max(...lons) + 0.6;

    // Proyección geográfica
    const raw = {};
    red.nodos.forEach(n => {
      raw[n.id] = proyectar(n.lat, n.lon, minLat, maxLat, minLon, maxLon);
    });

    // Separación por fuerza para eliminar solapamientos
    return separar(raw, red.nodos, 150, 14);
  }, [red]);

  // ── Pan ──────────────────────────────────────────────────────────────────
  const onMouseDown = useCallback(e => {
    if (e.button !== 0) return;
    dragging.current = true;
    lastPos.current = { x: e.clientX, y: e.clientY };
    e.currentTarget.style.cursor = 'grabbing';
  }, []);

  const onMouseMove = useCallback(e => {
    if (!dragging.current) return;
    const dx = e.clientX - lastPos.current.x;
    const dy = e.clientY - lastPos.current.y;
    lastPos.current = { x: e.clientX, y: e.clientY };
    setTransform(t => ({ ...t, x: t.x + dx, y: t.y + dy }));
  }, []);

  const onMouseUp = useCallback(e => {
    dragging.current = false;
    if (e.currentTarget) e.currentTarget.style.cursor = 'grab';
  }, []);

  // ── Zoom con rueda ────────────────────────────────────────────────────────
  const onWheel = useCallback(e => {
    e.preventDefault();
    const rect = svgRef.current.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
    setTransform(t => {
      const newScale = Math.max(0.25, Math.min(10, t.scale * factor));
      const ratio    = newScale / t.scale;
      return { scale: newScale, x: mx - ratio * (mx - t.x), y: my - ratio * (my - t.y) };
    });
  }, []);

  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, [onWheel]);

  const resetView = () => setTransform({ x: 0, y: 0, scale: 1 });
  const zoom = delta => setTransform(t => {
    const newScale = Math.max(0.25, Math.min(10, t.scale * delta));
    const ratio    = newScale / t.scale;
    return { scale: newScale, x: W / 2 - ratio * (W / 2 - t.x), y: H / 2 - ratio * (H / 2 - t.y) };
  });

  const showTip = (e, texto) => setTooltip({ x: e.clientX, y: e.clientY, texto });
  const hideTip = ()          => setTooltip(null);

  if (!red) return (
    <div className="flex items-center justify-center h-64 text-muted-foreground text-sm">
      Carga la red para visualizar el grafo
    </div>
  );

  const aristasFiltradas = nodoFiltro
    ? red.aristas.filter(a => a.origen === nodoFiltro || a.destino === nodoFiltro)
    : red.aristas;

  const tfStr = `translate(${transform.x},${transform.y}) scale(${transform.scale})`;
  const s     = transform.scale;

  // Tamaño de fuente de etiquetas externas inversamente proporcional al zoom
  // → la etiqueta mantiene un tamaño razonable en pantalla sin importar el nivel de zoom
  const labelFs  = Math.min(9, 8 / Math.sqrt(s));   // crece lento al alejar, no se dispara al acercar
  const labelOff = 13 / Math.sqrt(s);               // offset bajo el nodo, también regulado

  return (
    <div className="relative select-none">

      {/* ── Leyenda + Controles ─────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-3 mb-3 text-xs font-semibold">
        {Object.entries(TIPO_COLOR).map(([tipo, cfg]) => (
          <span key={tipo} className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded-full inline-block border-2"
              style={{ background: cfg.fill, borderColor: cfg.stroke }} />
            {cfg.label}
          </span>
        ))}
        <span className="flex items-center gap-1.5 ml-1">
          <span className="w-5 h-1.5 inline-block rounded" style={{ background: '#ef4444' }} />
          Cuello
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-5 h-1.5 inline-block rounded" style={{ background: '#3b82f6' }} />
          Flujo LP
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-5 h-0.5 inline-block rounded" style={{ background: '#94a3b8', opacity: 0.5 }} />
          Sin flujo
        </span>

        <div className="ml-auto flex items-center gap-1">
          <button onClick={() => zoom(1.3)}
            className="w-7 h-7 rounded-lg border border-border bg-card hover:bg-muted flex items-center justify-center text-sm font-bold transition-colors"
            title="Acercar">+</button>
          <button onClick={() => zoom(1 / 1.3)}
            className="w-7 h-7 rounded-lg border border-border bg-card hover:bg-muted flex items-center justify-center text-sm font-bold transition-colors"
            title="Alejar">−</button>
          <button onClick={resetView}
            className="h-7 px-2 rounded-lg border border-border bg-card hover:bg-muted text-xs font-semibold transition-colors">
            ↺ Reset
          </button>
          <span className="text-[10px] text-muted-foreground ml-1">{Math.round(s * 100)}%</span>
        </div>
      </div>

      {/* ── SVG ─────────────────────────────────────────────────────────── */}
      <div className="rounded-xl border border-border/50 overflow-hidden bg-card/60"
        style={{ cursor: 'grab' }}>
        <svg
          ref={svgRef}
          viewBox={`0 0 ${W} ${H}`}
          className="w-full"
          style={{ maxHeight: 600, display: 'block' }}
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
          onMouseLeave={onMouseUp}
        >
          <defs>
            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="currentColor" strokeWidth="0.3" opacity="0.07" />
            </pattern>
            {[
              { id: 'arrow',        color: '#94a3b8' },
              { id: 'arrow-flow',   color: '#3b82f6' },
              { id: 'arrow-cuello', color: '#ef4444' },
            ].map(({ id, color }) => (
              <marker key={id} id={id} markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">
                <polygon points="0 0, 8 4, 0 8" fill={color} opacity="0.9" />
              </marker>
            ))}
            <filter id="glow" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="2" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
            <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="1" stdDeviation="2" floodOpacity="0.2" />
            </filter>
          </defs>

          <rect width={W} height={H} fill="url(#grid)" />

          <g transform={tfStr}>

            {/* ── Aristas ──────────────────────────────────────────────── */}
            {aristasFiltradas.map(a => {
              const p1 = posiciones[a.origen];
              const p2 = posiciones[a.destino];
              if (!p1 || !p2) return null;

              const f      = flujos[a.id];
              const flujo  = f?.flujo || 0;
              const activa = flujo > 0.01;
              const esCuello = cuellos.includes(a.id);

              const dx  = p2.x - p1.x, dy = p2.y - p1.y;
              const len = Math.sqrt(dx * dx + dy * dy) || 1;
              const off = 4;
              const ox  = -dy / len * off, oy = dx / len * off;

              const color    = esCuello ? '#ef4444' : activa ? '#3b82f6' : '#94a3b8';
              const grosor   = esCuello ? 3.5 : activa ? Math.max(1.5, Math.min(5, flujo / 4)) : 1;
              const opacidad = nodoFiltro
                ? (a.origen === nodoFiltro || a.destino === nodoFiltro ? 1 : 0.05)
                : (activa || esCuello ? 0.88 : 0.18);
              const markerId = esCuello ? 'arrow-cuello' : activa ? 'arrow-flow' : 'arrow';

              const rO = RADIO[nodoMap[a.origen]?.tipo] || 10;
              const rD = RADIO[nodoMap[a.destino]?.tipo] || 10;
              const sx = p1.x + ox + dx / len * rO;
              const sy = p1.y + oy + dy / len * rO;
              const ex = p2.x + ox - dx / len * (rD + 6);
              const ey = p2.y + oy - dy / len * (rD + 6);
              const mx = (sx + ex) / 2 + ox;
              const my = (sy + ey) / 2 + oy - 5;

              return (
                <g key={a.id}>
                  {/* Hit-area invisible */}
                  <line x1={sx} y1={sy} x2={ex} y2={ey}
                    stroke="transparent" strokeWidth={12}
                    className="cursor-pointer"
                    onMouseEnter={e => showTip(e,
                      `${a.descripcion || a.id}\n${a.distancia_km} km · ${a.costo_por_ton_km} KCOP/t·km\nCap: ${a.capacidad_ton} t${flujo > 0.01 ? `\nFlujo: ${flujo.toFixed(2)} t (${f?.uso_pct || 0}%)` : ''}`
                    )}
                    onMouseLeave={hideTip}
                  />
                  <line x1={sx} y1={sy} x2={ex} y2={ey}
                    stroke={color} strokeWidth={grosor}
                    opacity={opacidad}
                    markerEnd={`url(#${markerId})`}
                    strokeDasharray={activa || esCuello ? 'none' : '5 4'}
                    filter={activa || esCuello ? 'url(#glow)' : undefined}
                    style={{ pointerEvents: 'none' }}
                  />
                  {/* Etiqueta de flujo */}
                  {activa && flujo > 0.5 && (
                    <g style={{ pointerEvents: 'none' }}>
                      <rect x={mx - 14} y={my - 8} width={28} height={13}
                        rx={3} fill="white" opacity={0.78} />
                      <text x={mx} y={my + 2}
                        fontSize="7.5" fill={color}
                        textAnchor="middle" fontWeight="700">
                        {flujo.toFixed(1)}t
                      </text>
                    </g>
                  )}
                </g>
              );
            })}

            {/* ── Nodos ────────────────────────────────────────────────── */}
            {red.nodos.map(n => {
              const pos = posiciones[n.id];
              if (!pos) return null;
              const cfg  = TIPO_COLOR[n.tipo] || TIPO_COLOR.destino;
              const r    = RADIO[n.tipo] || 9;
              const dim  = nodoFiltro && nodoFiltro !== n.id ? 0.2 : 1;
              const sel  = nodoFiltro === n.id;
              const esDestino = n.tipo === 'destino';

              return (
                <g key={n.id}
                  className="cursor-pointer"
                  opacity={dim}
                  onClick={e => {
                    e.stopPropagation();
                    setNodoFiltro(prev => prev === n.id ? null : n.id);
                  }}
                  onMouseEnter={e => showTip(e,
                    `${n.nombre} (${n.id})\n` +
                    (n.tipo === 'origen'
                      ? `Oferta: ${n.oferta} t/sem`
                      : n.tipo === 'transito'
                      ? `Cap: ${n.capacidad} t | Calidad: ${(n.calidad * 100).toFixed(0)}% | Merma: ${(n.merma * 100).toFixed(0)}%`
                      : `Demanda: ${n.demanda} t/sem`)
                  )}
                  onMouseLeave={hideTip}
                  filter="url(#shadow)"
                >
                  {/* Halo pulsante al seleccionar */}
                  {sel && (
                    <circle cx={pos.x} cy={pos.y} r={r + 7}
                      fill="none" stroke={cfg.fill} strokeWidth={2} opacity={0.4}>
                      <animate attributeName="r" values={`${r+5};${r+9};${r+5}`} dur="1.5s" repeatCount="indefinite" />
                      <animate attributeName="opacity" values="0.4;0.1;0.4" dur="1.5s" repeatCount="indefinite" />
                    </circle>
                  )}

                  {/* Ring exterior */}
                  <circle cx={pos.x} cy={pos.y} r={r + 4}
                    fill={cfg.ring} opacity={sel ? 0.45 : 0.18} />

                  {/* Círculo principal */}
                  <circle cx={pos.x} cy={pos.y} r={r}
                    fill={cfg.fill} stroke={cfg.stroke}
                    strokeWidth={sel ? 2.5 : 1.8} />

                  {/* ID del nodo dentro del círculo — siempre visible, escala con zoom */}
                  <text x={pos.x} y={pos.y + 1}
                    fontSize={r > 10 ? '7.5' : '6'}
                    fill="white" textAnchor="middle"
                    dominantBaseline="middle"
                    fontWeight="800"
                    style={{ pointerEvents: 'none' }}>
                    {n.id}
                  </text>

                  {/* Etiqueta exterior — sólo para origen y tránsito,
                      con tamaño inversamente proporcional al zoom para evitar
                      que se dispare y tape a otros nodos al acercar */}
                  {!esDestino && (
                    <text
                      x={pos.x}
                      y={pos.y + r + labelOff}
                      fontSize={labelFs}
                      fill="currentColor"
                      textAnchor="middle"
                      fontWeight="600"
                      opacity={0.85}
                      style={{ pointerEvents: 'none' }}>
                      {n.nombre?.split(' ').slice(0, 2).join(' ')}
                    </text>
                  )}
                </g>
              );
            })}
          </g>
        </svg>
      </div>

      {/* ── Tooltip flotante ──────────────────────────────────────────────── */}
      {tooltip && (
        <div
          className="fixed z-50 pointer-events-none bg-popover border border-border rounded-xl shadow-xl px-3 py-2 text-xs font-medium text-popover-foreground whitespace-pre-line max-w-[220px]"
          style={{ left: tooltip.x + 14, top: tooltip.y - 14 }}
        >
          {tooltip.texto}
        </div>
      )}

      {/* ── Pie ───────────────────────────────────────────────────────────── */}
      <div className="mt-2 flex items-center justify-between text-[11px] text-muted-foreground px-1">
        <span>Rueda: zoom · Arrastrar: mover · Clic en nodo: filtrar aristas</span>
        {nodoFiltro ? (
          <button
            onClick={() => setNodoFiltro(null)}
            className="flex items-center gap-1 px-2 py-0.5 bg-blue-500/10 text-blue-600 border border-blue-500/20 rounded-full font-semibold hover:bg-blue-500/20 transition-colors"
          >
            Filtrando: {nodoFiltro} ✕
          </button>
        ) : (
          <span className="italic opacity-60">Supermercados: pasa el cursor para ver nombre</span>
        )}
      </div>
    </div>
  );
};

export default NetworkGraphSVG;
