import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { mockApi } from '../../test/fetch'
import { CadastrosPage } from './CadastrosPage'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <CadastrosPage />
    </QueryClientProvider>,
  )
}

describe('CadastrosPage', () => {
  it('lista, cria e desativa tags de tipo de conta', async () => {
    const calls = mockApi((url, init) => {
      if (url.pathname === '/api/v1/tags' && init.method === 'POST')
        return { status: 201, body: { id: 't-9', nome: 'Aluguel', ativo: true } }
      if (url.pathname === '/api/v1/tags/t-1' && init.method === 'PATCH')
        return { body: { id: 't-1', nome: 'Recorrente', ativo: false } }
      if (url.pathname === '/api/v1/tags')
        return {
          body: [
            { id: 't-1', nome: 'Recorrente', ativo: true },
            { id: 't-2', nome: 'Folha de pagamento', ativo: false },
          ],
        }
      return { body: [] }
    })
    renderPage()
    const user = userEvent.setup()

    const secao = screen.getByRole('region', { name: 'Tags (tipo de conta)' })
    expect(await within(secao).findByText('Recorrente')).toBeInTheDocument()
    // A lista pede também as desativadas, que aparecem com "Reativar".
    expect(calls.find((c) => c.url.pathname === '/api/v1/tags')!.url.search).toBe(
      '?incluir_inativos=true',
    )
    expect(within(secao).getByRole('button', { name: 'Reativar' })).toBeInTheDocument()

    const campo = within(secao).getByRole('textbox', { name: 'Novo item em Tags (tipo de conta)' })
    expect(campo).toHaveAttribute('maxlength', '50')
    await user.type(campo, 'Aluguel')
    await user.click(within(secao).getByRole('button', { name: 'Adicionar' }))
    await waitFor(() =>
      expect(calls.find((c) => c.method === 'POST')).toMatchObject({ body: { nome: 'Aluguel' } }),
    )
    expect(calls.find((c) => c.method === 'POST')!.url.pathname).toBe('/api/v1/tags')

    await user.click(within(secao).getByRole('button', { name: 'Desativar' }))
    await waitFor(() =>
      expect(calls.find((c) => c.method === 'PATCH')).toMatchObject({ body: { ativo: false } }),
    )
  })
})
