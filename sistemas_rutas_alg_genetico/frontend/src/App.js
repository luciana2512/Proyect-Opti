import React, { useState } from 'react';
import { BrowserRouter as Router } from 'react-router-dom';
import { Toaster } from 'sonner';
import { Fish, Network, BarChart2, Sparkles } from 'lucide-react';
import ThemeToggle from './components/ThemeToggle';
import AcuicolaPanel from './components/AcuicolaPanel';
import SensibilidadPanel from './components/SensibilidadPanel';

const TABS = [
  {
    id: 'red',
    label: 'Red y Optimización',
    icon: Network,
    desc: 'Grafo · PL · Dijkstra · Bellman-Ford · Flujo Máximo · AG',
  },
  {
    id: 'sensibilidad',
    label: 'Análisis de Sensibilidad',
    icon: BarChart2,
    desc: 'Escenarios What-If — 3 escenarios críticos',
  },
];

function App() {
  const [tabActiva,   setTabActiva]   = useState('red');
  const [origenRuta,  setOrigenRuta]  = useState('O1');
  const [destinoRuta, setDestinoRuta] = useState('D1');

  return (
    <Router>
      <div className="min-h-screen bg-background text-foreground transition-colors duration-300">
        <Toaster position="top-right" richColors />

        {/* ── Header ─────────────────────────────────────────────────── */}
        <header className="sticky top-0 z-50 glass-effect border-b">
          <div className="max-w-[1400px] mx-auto px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="bg-blue-600 p-2.5 rounded-xl text-white shadow-lg shadow-blue-500/30">
                  <Fish className="w-7 h-7" />
                </div>
                <div>
                  <h1 className="text-xl font-bold tracking-tight leading-tight">
                    Acuícola Real del Meta
                  </h1>
                  <p className="text-xs text-muted-foreground flex items-center gap-1.5 font-medium">
                    <Sparkles className="w-3 h-3 text-blue-500" />
                    Optimización de Red Logística — Proyecto Final 2026-1
                  </p>
                </div>
              </div>
              <ThemeToggle />
            </div>

            {/* Pestañas */}
            <div className="flex gap-1 mt-4">
              {TABS.map(tab => {
                const Icon = tab.icon;
                const activa = tabActiva === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setTabActiva(tab.id)}
                    className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-t-lg transition-all border-b-2 ${
                      activa
                        ? 'border-blue-500 text-blue-600 dark:text-blue-400 bg-blue-500/5'
                        : 'border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/40'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    <span>{tab.label}</span>
                    {activa && (
                      <span className="hidden sm:inline text-[10px] text-muted-foreground font-normal ml-1">
                        — {tab.desc}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        </header>

        {/* ── Contenido ──────────────────────────────────────────────── */}
        <main className="max-w-[1400px] mx-auto px-6 py-6">
          {tabActiva === 'red'          && <AcuicolaPanel
            origenRuta={origenRuta}   setOrigenRuta={setOrigenRuta}
            destinoRuta={destinoRuta} setDestinoRuta={setDestinoRuta}
          />}
          {tabActiva === 'sensibilidad' && <SensibilidadPanel
            origenRuta={origenRuta}
            destinoRuta={destinoRuta}
          />}
        </main>

        {/* ── Footer ─────────────────────────────────────────────────── */}
        <footer className="mt-12 border-t border-border bg-card/50 backdrop-blur-sm">
          <div className="max-w-[1400px] mx-auto px-6 py-5">
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-muted-foreground font-medium">
              <span>Programación Lineal · Teoría de Grafos · Algoritmos Genéticos</span>
              <span>Universidad de los Llanos — Ingeniería de Sistemas</span>
            </div>
          </div>
        </footer>
      </div>
    </Router>
  );
}

export default App;
