import { NavLink, Outlet, useNavigate } from 'react-router-dom'

import { useAuth } from '../../features/auth/AuthContext'
import { ROLE_LABELS, type Role } from '../../lib/types'

interface NavItem {
  to: string
  label: string
  end?: boolean
  roles?: Role[]
}

const NAV: NavItem[] = [
  { to: '/', label: 'Início', end: true },
  { to: '/lancamentos', label: 'Lançamentos' },
  { to: '/upload', label: 'Enviar comprovantes' },
  { to: '/relatorios', label: 'Relatórios' },
  { to: '/usuarios', label: 'Usuários', roles: ['admin'] },
]

export function AppLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const sair = async () => {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="app">
      <header className="app-header">
        <span className="brand">Prestação de Contas</span>
        {user && (
          <div className="user-box">
            <span className="user-info">
              <strong>{user.nome}</strong>
              <span className="muted">
                {user.tenant.nome} · {ROLE_LABELS[user.role]}
              </span>
            </span>
            <button type="button" onClick={() => void sair()}>
              Sair
            </button>
          </div>
        )}
      </header>
      <nav className="app-nav" aria-label="Menu principal">
        <ul>
          {NAV.filter((i) => !i.roles || (user && i.roles.includes(user.role))).map((item) => (
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
