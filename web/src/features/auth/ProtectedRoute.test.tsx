import { render, screen } from '@testing-library/react'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { ANA, WithAuth, authState } from '../../test/auth'
import type { AuthState } from './AuthContext'
import { ProtectedRoute } from './ProtectedRoute'

function renderAt(state: AuthState) {
  const router = createMemoryRouter(
    [
      { path: '/login', element: <p>tela de login</p> },
      {
        path: '/usuarios',
        element: (
          <ProtectedRoute roles={['admin']}>
            <p>conteúdo restrito</p>
          </ProtectedRoute>
        ),
      },
    ],
    { initialEntries: ['/usuarios'] },
  )
  render(
    <WithAuth value={state}>
      <RouterProvider router={router} />
    </WithAuth>,
  )
}

describe('ProtectedRoute', () => {
  it('envia o visitante anônimo para o login', async () => {
    renderAt(authState({ status: 'anonimo', user: null }))
    expect(await screen.findByText('tela de login')).toBeInTheDocument()
  })

  it('aguarda enquanto a sessão é recuperada', () => {
    renderAt(authState({ status: 'carregando', user: null }))
    expect(screen.getByText('Carregando…')).toBeInTheDocument()
  })

  it('bloqueia perfis sem permissão', () => {
    renderAt(authState({ user: { ...ANA, role: 'colaborador' } }))
    expect(screen.getByText('Acesso negado')).toBeInTheDocument()
    expect(screen.queryByText('conteúdo restrito')).not.toBeInTheDocument()
  })

  it('libera o perfil permitido', () => {
    renderAt(authState())
    expect(screen.getByText('conteúdo restrito')).toBeInTheDocument()
  })
})
