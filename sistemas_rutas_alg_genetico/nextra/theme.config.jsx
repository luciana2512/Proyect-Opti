const Logo = () => (
  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
    <span>🚌</span>
    <span style={{ fontWeight: 'bold' }}>Rutas Óptimas</span>
  </div>
)

export default {
  logo: <Logo />,
  project: {
    link: 'https://github.com/Santiagodutr/Sistema-de-Optimizacion-de-Rutas-de-Transporte-Estudiantil-mediante-Algoritmos-Geneticos',
  },
  docsRepositoryBase: 'https://github.com/Santiagodutr/Sistema-de-Optimizacion-de-Rutas-de-Transporte-Estudiantil-mediante-Algoritmos-Geneticos/blob/main/nextra',
  footer: {
    text: '© 2024 Sistema de Optimización de Rutas - Universidad de los Llanos',
  },
  search: {
    placeholder: 'Buscar...',
  },
  head: (
    <>
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <meta property="og:title" content="Rutas Óptimas" />
      <meta property="og:description" content="Sistema de Optimización de Rutas de Transporte Estudiantil" />
    </>
  ),
}
