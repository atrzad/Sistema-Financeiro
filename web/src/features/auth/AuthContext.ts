import { createContext, useContext } from 'react'

import type { Me } from '../../lib/types'

export interface LoginInput {
  tenant_slug: string
  email: string
  senha: string
}

export type AuthStatus = 'carregando' | 'autenticado' | 'anonimo'

export interface AuthState {
  status: AuthStatus
  user: Me | null
  login: (input: LoginInput) => Promise<Me>
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthState | null>(null)

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth precisa estar dentro de <AuthProvider>')
  return ctx
}
