/**
 * Configuración del Tour Interactivo con Driver.js
 * Tour completo para la aplicación de Optimización de Red Logística
 * Acuícola Real del Meta
 */

const allTourSteps = [
  {
    element: 'header',
    popover: {
      title: '👋 Bienvenida a OptiRut',
      description: 'Sistema de Optimización de Red Logística para Acuícola Real del Meta. Este tour te mostrará todas las funcionalidades principales.',
      position: 'bottom',
      side: 'center',
    },
  },

  // ────────────────────────────────────────────────────────────────
  // SECCIÓN 1: NAVEGACIÓN PRINCIPAL
  // ────────────────────────────────────────────────────────────────

  {
    element: '[data-tour="tab-red"]',
    popover: {
      title: '🗺️ Pestaña: Red y Optimización',
      description: 'Aquí puedes visualizar la red logística completa, seleccionar orígenes y destinos, y ejecutar diferentes algoritmos de optimización.',
      position: 'bottom',
      side: 'center',
    },
    section: 'header',
  },

  {
    element: '[data-tour="tab-sensibilidad"]',
    popover: {
      title: '📊 Pestaña: Análisis de Sensibilidad',
      description: 'Explora 3 escenarios críticos (What-If) para evaluar el impacto de cambios en la red.',
      position: 'bottom',
      side: 'center',
    },
    section: 'header',
  },

  {
    element: '[data-tour="theme-toggle"]',
    popover: {
      title: '🌙 Tema Oscuro/Claro',
      description: 'Alterna entre tema claro y oscuro según tu preferencia. Tu selección se guardará automáticamente.',
      position: 'bottom',
      side: 'left',
    },
    section: 'header',
  },

  // ────────────────────────────────────────────────────────────────
  // SECCIÓN 2: SECCIÓN DE RED Y OPTIMIZACIÓN
  // ────────────────────────────────────────────────────────────────

  {
    element: '[data-tour="origen-selector"]',
    popover: {
      title: '📍 Seleccionar Origen',
      description: 'Elige uno de los 6 orígenes disponibles (Meta + Cundinamarca). El origen es el punto de partida de tus rutas logísticas.',
      position: 'right',
      side: 'center',
    },
    section: 'red',
  },

  {
    element: '[data-tour="destino-selector"]',
    popover: {
      title: '🎯 Seleccionar Destino',
      description: 'Elige uno de los 29 supermercados destino. Estos son los puntos finales donde debe llegar el producto.',
      position: 'right',
      side: 'center',
    },
    section: 'red',
  },

  {
    element: '[data-tour="algoritmo-selector"]',
    popover: {
      title: '⚙️ Selector de Algoritmo',
      description: 'Elige el algoritmo a usar:\n• Dijkstra: Camino más corto\n• Bellman-Ford: Maneja aristas negativas\n• Flujo Máximo: Capacidad máxima de la red\n• PL: Programación Lineal',
      position: 'right',
      side: 'center',
    },
    section: 'red',
  },

  {
    element: '[data-tour="btn-optimizar-pl"]',
    popover: {
      title: '▶️ Botón Optimizar (PL)',
      description: 'Ejecuta la optimización usando Programación Lineal. Este algoritmo encuentra la solución matemáticamente óptima con restricciones de capacidad.',
      position: 'right',
      side: 'center',
    },
    section: 'red',
  },

  {
    element: '[data-tour="parametros-ag"]',
    popover: {
      title: '🧬 Parámetros del Algoritmo Genético',
      description: 'Configura los parámetros del AG:\n• Población: Individuos por generación\n• Generaciones: Iteraciones\n• Cruce: Probabilidad de reproducción\n• Mutación: Variabilidad genética\n• Elitismo: Mejores individuos preservados',
      position: 'right',
      side: 'center',
    },
    section: 'red',
  },

  {
    element: '[data-tour="btn-optimizar-ag"]',
    popover: {
      title: '▶️ Botón Optimizar (AG)',
      description: 'Ejecuta la optimización usando Algoritmo Genético. Ideal para problemas complejos donde necesitas explorar múltiples soluciones posibles.',
      position: 'right',
      side: 'center',
    },
    section: 'red',
  },

  // ────────────────────────────────────────────────────────────────
  // SECCIÓN 3: VISUALIZACIÓN DE RED
  // ────────────────────────────────────────────────────────────────

  {
    element: '[data-tour="selector-vista"]',
    popover: {
      title: '👁️ Selector de Vista',
      description: 'Cambia entre:\n• Mapa: Vista geográfica real con OpenStreetMap\n• Grafo: Vista de red topológica simplificada',
      position: 'top',
      side: 'center',
    },
    section: 'red',
  },

  {
    element: '[data-tour="mapa-principal"]',
    popover: {
      title: '🗺️ Mapa Interactivo',
      description: 'Visualización en tiempo real de la red logística en OpenStreetMap. Puedes hacer zoom, desplazarte, y ver los nodos origen, tránsito y destino con sus flujos.',
      position: 'top',
      side: 'center',
    },
    section: 'red',
  },

  {
    element: '[data-tour="grafo-svg"]',
    popover: {
      title: '📐 Grafo Topológico',
      description: 'Representación simplificada de la red como grafo dirigido. Muestra claramente las conexiones y pesos (distancias/costos) entre nodos.',
      position: 'top',
      side: 'center',
    },
    section: 'red',
    autoShowGrafo: true,
  },

  // ────────────────────────────────────────────────────────────────
  // SECCIÓN 4: RESULTADOS Y ESTADÍSTICAS
  // ────────────────────────────────────────────────────────────────

  {
    element: '[data-tour="estadisticas-red"]',
    popover: {
      title: '📈 Estadísticas de la Red',
      description: 'Métricas clave:\n• Orígenes: Puntos de salida (6)\n• Tránsitos: Centros de acopio (10)\n• Destinos: Supermercados (29)\n• Oferta Total: Capacidad máxima de distribución',
      position: 'top',
      side: 'center',
    },
    section: 'red',
  },

  {
    element: '[data-tour="validacion-conectividad"]',
    popover: {
      title: '✅ Validación de Conectividad',
      description: 'Verifica que todos los destinos sean alcanzables desde cualquier origen. Muestra cobertura del 100% cuando es posible llegar a todos los supermercados.',
      position: 'top',
      side: 'center',
    },
    section: 'red',
  },

  {
    element: '[data-tour="resultados-pl"]',
    popover: {
      title: '📊 Resultados de Optimización (PL)',
      description: 'Muestra:\n• Ruta completa con nodos intermedios\n• Distancia/Costo total\n• Flujo de producto\n• Satisfacción de demanda\n• Visualización en mapa y grafo',
      position: 'top',
      side: 'center',
    },
    section: 'red',
  },

  {
    element: '[data-tour="resultados-ag"]',
    popover: {
      title: '🧬 Resultados del Algoritmo Genético',
      description: 'Muestra:\n• Mejor solución encontrada\n• Progreso generacional (gráfico)\n• Comparativa con PL\n• Ventajas: Explora múltiples soluciones posibles',
      position: 'top',
      side: 'center',
    },
    section: 'red',
  },

  // ────────────────────────────────────────────────────────────────
  // SECCIÓN 5: ANÁLISIS DE SENSIBILIDAD
  // ────────────────────────────────────────────────────────────────

  {
    element: '[data-tour="escenarios-sensibilidad"]',
    popover: {
      title: '⚠️ Tres Escenarios Críticos',
      description: 'Analiza el impacto de cambios en la red:\n\n1️⃣ Aumento de Combustible: ¿Cómo afecta en costos?\n2️⃣ Cierre de Vía: ¿Qué rutas alternativas existen?\n3️⃣ Pérdida de Calidad: ¿Cómo impacta la calidad?',
      position: 'top',
      side: 'center',
    },
    section: 'sensibilidad',
  },

  {
    element: '[data-tour="comparativa-resultados"]',
    popover: {
      title: '🔄 Comparativa Antes/Después',
      description: 'Para cada escenario ver:\n• Parámetro modificado\n• Rutas alternativas\n• Cambios en costos\n• Viabilidad de la solución',
      position: 'top',
      side: 'center',
    },
    section: 'sensibilidad',
  },

  // ────────────────────────────────────────────────────────────────
  // SECCIÓN 6: INFORMACIÓN Y AYUDA
  // ────────────────────────────────────────────────────────────────

  {
    element: '[data-tour="btn-ayuda"]',
    popover: {
      title: '❓ Botón de Ayuda',
      description: 'Haz clic en el signo de interrogación para volver a este tour en cualquier momento. ¡Repásalo cuantas veces quieras!',
      position: 'bottom',
      side: 'left',
    },
    section: 'both',
  },

  {
    element: 'footer',
    popover: {
      title: '🎓 Tecnologías Utilizadas',
      description: 'Este proyecto utiliza:\n• Programación Lineal (PL)\n• Teoría de Grafos\n• Algoritmos Genéticos\n\nDesarrollado como Proyecto Final en Ingeniería de Sistemas — Universidad de los Llanos',
      position: 'top',
      side: 'center',
    },
    section: 'both',
  },

  {
    element: 'body',
    popover: {
      title: '✨ ¡Tour Completado!',
      description: 'Ya conoces todas las funcionalidades. ¡Buena suerte optimizando tus rutas! 🚀',
      position: 'center',
      side: 'center',
    },
    section: 'both',
  },
];

/**
 * Retorna los pasos del tour según la pestaña activa
 */
export const getTourSteps = (tabActiva = 'red') => {
  return allTourSteps.filter(step => {
    if (!step.section) return true;
    return step.section === 'both' || step.section === tabActiva;
  });
};

/**
 * Configuración general del Driver
 */
export const driverConfig = {
  allowClose: true,
  overlayClickNext: false,
  showProgress: true,
  showButtons: ['next', 'previous', 'close'],
  nextBtnText: 'Siguiente →',
  prevBtnText: '← Anterior',
  doneBtnText: 'Finalizar ✓',
  closeBtnText: '✕',
  stageBackgroundPadding: 5,
  popoverOffset: 10,
  smoothScroll: true,
  allowKeyboardControl: true,
  disableActiveInteraction: false,
};

export default getTourSteps;
