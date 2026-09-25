import { NavLink, Outlet } from 'react-router-dom'

const NAV = [
  { to: '/', label: 'Início', end: true },
  { to: '/lancamentos', label: 'Lançamentos' },
  { to: '/upload', label: 'Enviar comprovantes' },
  { to: '/relatorios', label: 'Relatórios' },
]

export function AppLayout() {
  return (
    <div className="app">
      <header className="app-header">
        <span className="brand">Prestação de Contas</span>
        <NavLink to="/login" className="header-link">
          Entrar
        </NavLink>
      </header>
      <nav className="app-nav" aria-label="Menu principal">
        <ul>
          {NAV.map((item) => (
            <li key={item.to}>
              <NavLink to={item.to} end={item.end}>
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  )
}
