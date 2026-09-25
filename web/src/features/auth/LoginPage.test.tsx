import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../lib/api'
import { ANA, WithAuth, authState } from '../../test/auth'
import type { AuthState } from './AuthContext'
import { LoginPage } from './LoginPage'

function renderLogin(state: AuthState, from?: string) {
  const router = createMemoryRouter(
    [
      { path: '/login', element: <LoginPage /> },
      { path: '/', element: <p>página inicial</p> },
      { path: '/usuarios', element: <p>página usuários</p> },
    ],
    { initialEntries: [{ pathname: '/login', state: from ? { from } : null }] },
  )
  render(
    <WithAuth value={state}>
      <RouterProvider router={router} />
    </WithAuth>,
  )
}

async function preencher(empresa: string, email: string, senha: string) {
  const user = userEvent.setup()
  if (empresa) await user.type(screen.getByLabelText('Empresa'), empresa)
  if (email) await user.type(screen.getByLabelText('E-mail'), email)
  if (senha) await user.type(screen.getByLabelText('Senha'), senha)
  await user.click(screen.getByRole('button', { name: 'Entrar' }))
}

describe('LoginPage', () => {
  it('valida os campos antes de enviar', async () => {
    const state = authState({ status: 'anonimo', user: null })
    renderLogin(state)

    await preencher('', 'invalido', '')

    expect(await screen.findByText('Informe o código da empresa')).toBeInTheDocument()
    expect(screen.getByText('E-mail inválido')).toBeInTheDocument()
    expect(screen.getByText('Informe a senha')).toBeInTheDocument()
    expect(state.login).not.toHaveBeenCalled()
  })

  it('entra e volta para a página que o usuário tentou abrir', async () => {
    const login = vi.fn(async () => ANA)
    renderLogin(authState({ status: 'anonimo', user: null, login }), '/usuarios')

    await preencher('ACME', 'admin@acme.com.br', 'Senha@123')

    expect(await screen.findByText('página usuários')).toBeInTheDocument()
    expect(login).toHaveBeenCalledWith({
      tenant_slug: 'acme',
      email: 'admin@acme.com.br',
      senha: 'Senha@123',
    })
  })

  it('mostra mensagem de credenciais inválidas', async () => {
    const login = vi.fn(async () => {
      throw new ApiError(401, { detail: 'Empresa, e-mail ou senha incorretos.' })
    })
    renderLogin(authState({ status: 'anonimo', user: null, login }))

    await preencher('acme', 'admin@acme.com.br', 'errada')

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Empresa, e-mail ou senha incorretos.',
    )
  })

  it('mostra o aviso de bloqueio por excesso de tentativas', async () => {
    const login = vi.fn(async () => {
      throw new ApiError(429, { detail: 'Muitas tentativas de login. Tente novamente em 15 min.' })
    })
    renderLogin(authState({ status: 'anonimo', user: null, login }))

    await preencher('acme', 'admin@acme.com.br', 'x')

    expect(await screen.findByRole('alert')).toHaveTextContent('Tente novamente em 15 min')
  })

  it('redireciona quem já está logado', async () => {
    renderLogin(authState())
    expect(await screen.findByText('página inicial')).toBeInTheDocument()
  })
})
