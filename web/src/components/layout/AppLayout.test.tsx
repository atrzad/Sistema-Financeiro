import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import type { AuthState } from '../../features/auth/AuthContext'
import { ANA, WithAuth, authState } from '../../test/auth'
import { AppLayout } from './AppLayout'

function renderAt(path: string, state: AuthState = authState()) {
  const router = createMemoryRouter(
    [
      { path: '/login', element: <p>tela de login</p> },
      {
        path: '/',
        element: <AppLayout />,
        children: [
          { index: true, element: <p>conteúdo início</p> },
          { path: 'lancamentos', element: <p>conteúdo lançamentos</p> },
        ],
      },
    ],
    { initialEntries: [path] },
  )
  return render(
    <WithAuth value={state}>
      <RouterProvider router={router} />
    </WithAuth>,
  )
}

describe('AppLayout', () => {
  it('renderiza menu principal e a rota filha', () => {
    renderAt('/lancamentos')
    expect(screen.getByRole('navigation', { name: 'Menu principal' })).toBeInTheDocument()
    expect(screen.getByText('conteúdo lançamentos')).toBeInTheDocument()
  })

  it('marca o item de menu ativo', () => {
    renderAt('/lancamentos')
    expect(screen.getByRole('link', { name: 'Lançamentos' })).toHaveClass('active')
    expect(screen.getByRole('link', { name: 'Início' })).not.toHaveClass('active')
  })

  it('mostra usuário, empresa e perfil no cabeçalho', () => {
    renderAt('/')
    expect(screen.getByText('Ana Admin')).toBeInTheDocument()
    expect(screen.getByText('ACME Comércio Ltda · Administrador')).toBeInTheDocument()
  })

  it('mostra "Usuários" só para administradores', () => {
    renderAt('/')
    expect(screen.getByRole('link', { name: 'Usuários' })).toBeInTheDocument()
  })

  it('esconde "Usuários" de quem não é administrador', () => {
    renderAt('/', authState({ user: { ...ANA, role: 'colaborador' } }))
    expect(screen.queryByRole('link', { name: 'Usuários' })).not.toBeInTheDocument()
  })

  it('sair encerra a sessão e volta ao login', async () => {
    const state = authState()
    renderAt('/', state)
    await userEvent.setup().click(screen.getByRole('button', { name: 'Sair' }))
    expect(state.logout).toHaveBeenCalled()
    expect(await screen.findByText('tela de login')).toBeInTheDocument()
  })
})
