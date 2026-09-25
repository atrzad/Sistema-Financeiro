import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'

import { apiFetch, onSessionChange, refreshSession, setSession } from '../../lib/api'
import type { Me, TokenResponse } from '../../lib/types'
import { AuthContext, type AuthState, type AuthStatus, type LoginInput } from './AuthContext'

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [user, setUser] = useState<Me | null>(null)
  const [status, setStatus] = useState<AuthStatus>('carregando')

  useEffect(() => {
    const unsubscribe = onSessionChange((u) => {
      setUser(u)
      setStatus(u ? 'autenticado' : 'anonimo')
    })
    // Recupera a sessão após recarregar a página (o cookie de refresh sobrevive).
    void refreshSession()
    return () => {
      unsubscribe()
    }
  }, [])

  const login = useCallback(async (input: LoginInput) => {
    const session = await apiFetch<TokenResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify(input),
      auth: false,
    })
    setSession(session)
    return session.user
  }, [])

  const logout = useCallback(async () => {
    try {
      await apiFetch('/api/v1/auth/logout', { method: 'POST', auth: false })
    } finally {
      setSession(null)
      queryClient.clear()
    }
  }, [queryClient])

  const value = useMemo<AuthState>(
    () => ({ status, user, login, logout }),
    [status, user, login, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
