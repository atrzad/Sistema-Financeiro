import type { ReactNode } from 'react'
import { vi } from 'vitest'

import { AuthContext, type AuthState } from '../features/auth/AuthContext'
import type { Me } from '../lib/types'

export const ANA: Me = {
  id: 'u-1',
  nome: 'Ana Admin',
  email: 'admin@acme.com.br',
  role: 'admin',
  nivel_aprovacao: 2,
  tenant: { id: 't-1', nome: 'ACME Comércio Ltda', slug: 'acme' },
}

export function authState(overrides: Partial<AuthState> = {}): AuthState {
  return {
    status: 'autenticado',
    user: ANA,
    login: vi.fn(async () => ANA),
    logout: vi.fn(async () => undefined),
    ...overrides,
  }
}

export function WithAuth({ value, children }: { value: AuthState; children: ReactNode }) {
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
