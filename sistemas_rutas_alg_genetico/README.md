# Acuícola Real del Meta — Optimización de Red Logística

Proyecto Final 2026-1 · Curso de Optimización · Universidad de los Llanos  
Ingeniería de Sistemas

---

## Descripción

Sistema de optimización de la red logística de distribución de pescado de la empresa **Acuícola Real del Meta**. Modela la red como un **Grafo Dirigido Ponderado G = (V, E)** y resuelve el problema mediante:

- **Programación Lineal** (scipy HiGHS) — minimización de costos de transporte
- **Teoría de Grafos** — Dijkstra, Bellman-Ford, Flujo Máximo (Edmonds-Karp)
- **Algoritmo Genético** — optimización de rutas de distribución local (TSP)
- **Análisis de Sensibilidad** — 3 escenarios What-If críticos

---

## Estructura de la Red

| Tipo | Cantidad | Descripción |
|------|----------|-------------|
| Orígenes | 6 | Estaciones productoras (3 Meta + 3 Cundinamarca) |
| Tránsito | 10 | Centros de acopio intermedios |
| Destinos | 29 | Supermercados con demanda fija |
| Aristas | 53 | Rutas de transporte con capacidad y costo |

- **Oferta total:** 345 ton/semana
- **Demanda total:** 157 ton/semana

---

## Cómo correr el programa

### Requisitos previos

- Python 3.10 o superior
- Node.js 18 o superior (LTS recomendado)

### 1. Instalar dependencias del backend

Abre una terminal en la carpeta raíz del proyecto y ejecuta:

```bash
cd backend
pip install flask flask-cors numpy scipy networkx
```

### 2. Iniciar el backend

```bash
cd backend
python api_rutas_reales.py
```

Verás en la terminal:
```
=================================================================
  ACUICOLA REAL DEL META — Servidor Flask
=================================================================
 * Running on http://127.0.0.1:5000
```

> Deja esta terminal abierta mientras usas la aplicación.

### 3. Instalar dependencias del frontend (solo la primera vez)

Abre **otra terminal**:

```bash
cd frontend
npm install
```

### 4. Iniciar el frontend

```bash
cd frontend
npm start
```

El navegador se abrirá automáticamente en `http://localhost:3000`.

---

## Uso de la aplicación

### Pestaña: Red y Optimización

1. La red se carga automáticamente al abrir la app (45 nodos y 53 rutas visibles en el mapa).
2. Usa el toggle **OpenStreetMap / Grafo SVG** para cambiar entre el mapa real y el grafo abstracto.
3. En el **Grafo SVG**: rueda del mouse para zoom, arrastrar para mover, clic en nodo para filtrar sus aristas.
4. Selecciona un **Nodo Origen**, un **Nodo Destino** y el **algoritmo de ruta** (Dijkstra o Bellman-Ford).
5. Pulsa **Resolver LP + Visualizar en Mapa**:
   - Las rutas con flujo se vuelven azules (grosor proporcional a toneladas)
   - La ruta óptima se resalta en naranja punteado
   - Los cuellos de botella aparecen en rojo
   - Pulsa **Animar recorrido** para ver el camión 🚛 moviéndose por la ruta óptima
6. En la sección **Algoritmo Genético**, selecciona un centro de acopio y pulsa **Optimizar con AG** para calcular el orden óptimo de entrega a supermercados locales. El resultado aparece en morado en el mapa.

### Pestaña: Análisis de Sensibilidad

Ejecuta cualquiera de los 3 escenarios What-If:

| Escenario | Descripción |
|-----------|-------------|
| 1 — Alza combustible | +15% en costos de rutas del Meta (O1, O2, O3) |
| 2 — Cierre de vía | Bloquea la ruta Hub Bogotá → Cali (E20) |
| 3 — Pérdida de calidad | Falla de calidad en Hub Bogotá (T1), calidad cae al 35% |

Cada escenario muestra la comparación base vs. nuevo: costo, ganancia, variación % y los 5 flujos más afectados.

---

## Estructura de archivos

```
backend/
├── api_rutas_reales.py       Flask — todos los endpoints de la API
├── modelo_pl.py              Modelo de Programación Lineal (scipy HiGHS)
├── grafo_acuicola.py         Grafos: Dijkstra, Bellman-Ford, Flujo Máximo, AG local
├── analisis_sensibilidad.py  3 escenarios What-If
├── genetic_algorithm.py      Algoritmo Genético (torneo, PMX, mutación)
├── fitness.py                Función de aptitud del AG
└── red_acuicola.json         Datos de la red (nodos, aristas, coordenadas)

frontend/src/
├── App.js                    Navegación principal (2 pestañas)
├── components/
│   ├── AcuicolaPanel.jsx     Panel principal: LP + grafos + AG
│   ├── MapaAcuicola.jsx      Mapa OpenStreetMap con Leaflet
│   ├── NetworkGraphSVG.jsx   Grafo SVG interactivo (zoom/pan)
│   ├── SensibilidadPanel.jsx Análisis de sensibilidad What-If
│   ├── ThemeToggle.jsx       Modo claro/oscuro
│   └── ui/                   Componentes de interfaz (card, button, badge)
└── lib/utils.js
```

---

## Modelo Matemático

### Variables de decisión
- `x_e ≥ 0` : toneladas transportadas por la arista `e`

### Función objetivo
```
Minimizar: Σ (distancia_e × costo_ton_km_e × x_e)
```

### Restricciones

| Tipo | Descripción |
|------|-------------|
| Oferta | Salida de cada origen ≤ oferta disponible |
| Equilibrio de flujo | Entrada × (1 − merma) = Salida en cada tránsito |
| Capacidad de aristas | x_e ≤ capacidad_e |
| Demanda | Flujo que llega a cada supermercado = demanda exacta |
| Calidad | Nodos con calidad < 40% tienen sus aristas bloqueadas |

---

## API Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/health` | Estado del servidor |
| GET | `/api/acuicola/red` | Estructura completa de la red |
| GET | `/api/acuicola/optimizar` | LP + Dijkstra/BF + Flujo Máximo |
| GET | `/api/acuicola/ruta` | Ruta óptima entre dos nodos |
| GET | `/api/acuicola/sensibilidad/1` | Escenario: alza combustible |
| GET | `/api/acuicola/sensibilidad/2` | Escenario: cierre de vía |
| GET | `/api/acuicola/sensibilidad/3` | Escenario: pérdida de calidad |
| GET | `/api/acuicola/sensibilidad/todos` | Los 3 escenarios comparados |
| GET | `/api/acuicola/distribucion/<id>` | AG distribución local |

---

## Algoritmo Genético

El AG optimiza el **orden de entrega** de un centro de acopio a sus supermercados (problema TSP).

- **Representación:** permutación de índices de supermercados
- **Función de aptitud:** distancia total Haversine del recorrido
- **Selección:** torneo de tamaño 3
- **Cruce:** PMX (Partially Mapped Crossover) — preserva inicio/fin en el depósito
- **Mutación:** intercambio aleatorio de dos paradas intermedias
- **Elitismo:** los mejores N individuos pasan sin cambios a la siguiente generación

Parámetros por defecto (configurables desde la interfaz):

| Parámetro | Valor |
|-----------|-------|
| Población | 80 individuos |
| Generaciones | 150 |
| Tasa de cruce | 0.80 |
| Tasa de mutación | 0.15 |
| Elitismo | 2 |

---

## Solución de problemas

**La red no carga / "Error cargando la red"**
- Verifica que el backend esté corriendo en el puerto 5000
- Usa el botón **Reintentar** que aparece en la app
- Revisa la ventana de la terminal del backend para ver el error exacto

**"Network Error" al resolver LP**
- El backend se reinició o cayó — vuelve a ejecutar `python api_rutas_reales.py`
- Recarga la página del navegador

**El mapa no muestra todos los nodos**
- Pulsa el botón **Reset** en el grafo SVG, o
- Haz zoom out en el mapa OpenStreetMap (todos los nodos están ahí, de Villavicencio hasta Cali)

**npm no se reconoce**
- Instala Node.js LTS desde https://nodejs.org
- Cierra y vuelve a abrir la terminal después de instalar

---

## Dependencias

### Backend (Python)
```
flask
flask-cors
numpy
scipy
networkx
```

### Frontend (Node.js)
```
react 18
react-leaflet 4
leaflet 1.9
axios
lucide-react
sonner
tailwindcss
```

---

Universidad de los Llanos · Ingeniería de Sistemas · Proyecto Final 2026-1
