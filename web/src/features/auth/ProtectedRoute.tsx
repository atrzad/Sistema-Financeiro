import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'

import type { Role } from '../../lib/types'
import { useAuth } from './AuthContext'

interface Props {
  children: ReactNode
  roles?: Role[]
}

export function ProtectedRoute({ children, roles }: Props) {
  const { status, user } = useAuth()
  const location = useLocation()

  if (status === 'carregando') {
    return <p className="page-loading">Carregando…</p>
  }
  if (status === 'anonimo' || !user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  if (roles && !roles.includes(user.role)) {
    return (
      <section>
        <h1>Acesso negado</h1>
        <p className="muted">Seu perfil não tem permissão para acessar esta página.</p>
      </section>
    )
  }
  return <>{children}</>
}
