import React, { useEffect, useState } from 'react';
import { driver } from 'driver.js';
import 'driver.js/dist/driver.css';
import { getTourSteps, driverConfig } from '../utils/tourConfig';
import { HelpCircle } from 'lucide-react';
import './TourGuide.css';

/**
 * Componente TourGuide
 * Implementa el tour interactivo con Driver.js
 */
const TourGuide = ({ tabActiva = 'red' }) => {
  const [driverInstance, setDriverInstance] = useState(null);

  // Inicializar Driver.js
  useEffect(() => {
    const instance = driver({
      ...driverConfig,
      steps: getTourSteps(tabActiva),
      onNext: (step) => {
        // Scroll suave al elemento
        const element = document.querySelector(step.element);
        if (element) {
          element.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }

        // Cambiar automáticamente a vista de grafo si es necesario
        if (step.element === '[data-tour="grafo-svg"]') {
          const btnGrafo = document.querySelector('[data-tour="selector-vista"] button:nth-child(2)');
          if (btnGrafo) {
            btnGrafo.click();
          }
        }
      },
      onPrevious: (step) => {
        // Scroll suave al elemento
        const element = document.querySelector(step.element);
        if (element) {
          element.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      },
    });
    setDriverInstance(instance);
  }, [tabActiva]);

  // Iniciar el tour
  const iniciarTour = () => {
    if (driverInstance) {
      driverInstance.drive();
    }
  };

  // Cargar estilos personalizados para Driver.js
  useEffect(() => {
    // Personalizar estilos del Driver
    const style = document.createElement('style');
    style.innerHTML = `
      .driver-popover {
        background-color: var(--card-bg, white);
        border: 1px solid var(--border-color, #e5e7eb);
        border-radius: 12px;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
        color: var(--text-color, #000);
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      }

      .driver-popover-title {
        font-size: 18px;
        font-weight: 700;
        margin: 0 0 8px 0;
        color: var(--text-color, #000);
      }

      .driver-popover-description {
        font-size: 14px;
        color: var(--text-muted, #666);
        margin: 0 0 16px 0;
        line-height: 1.5;
      }

      .driver-overlay {
        background-color: rgba(0, 0, 0, 0.5);
      }

      .driver-popover-button {
        background-color: #3b82f6;
        color: white;
        border: none;
        padding: 8px 16px;
        border-radius: 6px;
        cursor: pointer;
        font-weight: 600;
        font-size: 14px;
        transition: all 0.2s;
      }

      .driver-popover-button:hover {
        background-color: #2563eb;
        transform: translateY(-1px);
      }

      .driver-popover-button-next {
        background-color: #3b82f6;
      }

      .driver-popover-button-prev {
        background-color: #6b7280;
      }

      .driver-popover-button-close {
        background-color: #ef4444;
        font-size: 16px;
        padding: 6px 12px;
      }

      .driver-highlighted {
        box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.5) !important;
        border-radius: 8px !important;
      }

      .driver-progress {
        color: #3b82f6;
        font-weight: 600;
      }
    `;
    document.head.appendChild(style);

    return () => {
      document.head.removeChild(style);
    };
  }, []);

  return (
    <button
      data-tour="btn-ayuda"
      onClick={iniciarTour}
      title="Inicia el tour interactivo"
      className="fixed bottom-6 right-6 z-40 flex items-center justify-center w-14 h-14 rounded-full bg-blue-600 hover:bg-blue-700 text-white shadow-lg hover:shadow-xl transition-all duration-200 hover:scale-110 active:scale-95"
      aria-label="Mostrar tour de ayuda"
    >
      <HelpCircle className="w-6 h-6" />
    </button>
  );
};

export default TourGuide;
