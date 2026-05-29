# 📘 Documentación Manual de Usuario - Sistema de Optimización de Rutas

Este directorio contiene la documentación completa del proyecto en formato Nextra.

## 📂 Estructura de Archivos

```
nextra/
├── pages/                          # Páginas de documentación
│   ├── index.mdx                  # 🏠 Página principal
│   ├── instalacion.mdx            # 🚀 Guía de instalación
│   ├── guia-rapida.mdx            # ⚡ Guía rápida (5 min)
│   ├── uso-detallado.mdx          # 📖 Manual completo de uso
│   ├── conceptos-tecnicos.mdx     # 🔬 Cómo funciona el algoritmo
│   ├── troubleshooting.mdx        # 🔧 Solución de problemas
│   ├── faq.mdx                    # ❓ Preguntas frecuentes
│   └── _meta.json                 # Orden de navegación
├── package.json                   # Dependencias npm
├── next.config.js                 # Configuración Next.js
├── theme.config.jsx               # Configuración de tema
├── .gitignore                     # Archivos a ignorar en git
└── README.md                      # Este archivo

```

## 🚀 Cómo Ejecutar la Documentación

### Requisitos

- Node.js 16+
- npm 8+

### Instalación

```bash
cd nextra
npm install
```

### Iniciar servidor de desarrollo

```bash
npm run dev
```

La documentación estará disponible en: **http://localhost:3000**

### Build para producción

```bash
npm run build
npm run start
```

## 📖 Contenido de las Páginas

| Página | Archivo | Descripción |
|--------|---------|------------|
| 🏠 Inicio | `index.mdx` | Presentación del proyecto y tabla de contenidos |
| 🚀 Instalación | `instalacion.mdx` | Paso a paso para instalar backend y frontend |
| ⚡ Guía Rápida | `guia-rapida.mdx` | Cómo optimizar la primera ruta en 5 minutos |
| 📖 Uso Detallado | `uso-detallado.mdx` | Explicación detallada de cada sección de la UI |
| 🔬 Conceptos Técnicos | `conceptos-tecnicos.mdx` | Cómo funciona el algoritmo genético y OSM |
| 🔧 Troubleshooting | `troubleshooting.mdx` | Solución de problemas comunes |
| ❓ FAQ | `faq.mdx` | Preguntas frecuentes con respuestas |

## 🎯 Orden de Lectura Recomendado

1. **[Inicio](pages/index.mdx)** - Presentación general
2. **[Instalación](pages/instalacion.mdx)** - Instalar el proyecto
3. **[Guía Rápida](pages/guia-rapida.mdx)** - Primera experiencia
4. **[Uso Detallado](pages/uso-detallado.mdx)** - Explorar todas las funciones
5. **[Conceptos Técnicos](pages/conceptos-tecnicos.mdx)** - Entender cómo funciona
6. **[Troubleshooting](pages/troubleshooting.mdx)** - Si hay problemas
7. **[FAQ](pages/faq.mdx)** - Consultas específicas

## 🎨 Características

- ✅ **Navegación intuitiva** con sidebar automático
- ✅ **Búsqueda integrada** en todas las páginas
- ✅ **Sintaxis resaltada** para código
- ✅ **Responsive design** (móvil, tablet, desktop)
- ✅ **Tema claro/oscuro** automático
- ✅ **Markdown completo** con MDX
- ✅ **Links internos** entre secciones

## 📝 Editar Documentación

Para agregar o editar páginas:

1. Crear/editar archivo `.mdx` en `pages/`
2. Actualizar `pages/_meta.json` si es nueva página
3. Las cambios se reflejan automáticamente en `npm run dev`

Ejemplo de nueva página:

```markdown
# 📚 Mi Nueva Sección

Contenido aquí...

---

**Siguiente paso**: [Siguiente Página](/siguiente-pagina)
```

Luego agregarlo a `_meta.json`:

```json
{
  "mi-nueva-pagina": "📚 Mi Nueva Sección"
}
```

## 🔗 Recursos Relacionados

- **Backend:** `../backend/` - Código Python del algoritmo
- **Frontend:** `../frontend/` - Código React de la interfaz
- **Resumen Completo:** `../RESUMEN_COMPLETO_PROYECTO.md` - Documento técnico

## 📚 Tecnologías Utilizadas

- [Next.js 14](https://nextjs.org/) - Framework React
- [Nextra 3](https://nextra.site/) - Documentación con Next.js
- [Tailwind CSS](https://tailwindcss.com/) - Estilos
- [MDX](https://mdxjs.com/) - Markdown extendido

## 🤝 Contribuir

Para mejorar la documentación:

1. Fork el repositorio
2. Edita/agrega archivos en `nextra/pages/`
3. Prueba localmente con `npm run dev`
4. Envía un Pull Request

## 📄 Licencia

Documento de la Universidad de los Llanos - Proyecto de Optimización Semestre VI

---

**Última actualización:** Noviembre 2024
**Mantenedor:** Equipo de Desarrollo del Proyecto
