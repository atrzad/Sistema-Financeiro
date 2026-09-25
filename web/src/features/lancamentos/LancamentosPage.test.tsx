import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { WithAuth, authState } from '../../test/auth'
import { mockApi } from '../../test/fetch'
import { LancamentosPage } from './LancamentosPage'

const item = (id: string, extra: object) => ({
  id,
  valor: '245.90',
  data_emissao: '2026-09-10',
  data_pagamento_prevista: '2026-09-25',
  data_pagamento_efetiva: null,
  supplier: { id: 's', nome_fantasia: 'Energia Elétrica S.A.', cnpj: null },
  categoria: { id: 'c', nome: 'Utilidades' },
  projeto: null,
  centro_custo: null,
  usuario: { id: 'u', nome: 'Ana' },
  descricao: 'Conta de luz',
  forma_pagamento: 'boleto',
  linha_digitavel: null,
  status: 'pendente',
  status_efetivo: 'vence_hoje',
  dias_para_vencimento: 0,
  status_aprovacao: 'rascunho',
  version: 1,
  created_at: '',
  updated_at: '',
  ...extra,
})

function renderPage(path = '/lancamentos') {
  const router = createMemoryRouter(
    [
      { path: '/lancamentos', element: <LancamentosPage /> },
      { path: '/lancamentos/:id', element: <p>detalhe</p> },
    ],
    { initialEntries: [path] },
  )
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <WithAuth value={authState()}>
        <RouterProvider router={router} />
      </WithAuth>
    </QueryClientProvider>,
  )
  return router
}

describe('LancamentosPage', () => {
  it('lista com valor em reais, vencimento e selo', async () => {
    mockApi(() => ({ body: { items: [item('1', {})], next_cursor: null } }))
    renderPage()

    expect(await screen.findByText('Energia Elétrica S.A.')).toBeInTheDocument()
    expect(screen.getByText('R$ 245,90')).toBeInTheDocument()
    expect(screen.getByText('25/09/2026')).toBeInTheDocument()
    expect(screen.getByText('vence hoje')).toHaveClass('badge-critico')
  })

  it('aba "Pendentes" filtra pelos status corretos e fica na URL', async () => {
    const calls = mockApi(() => ({ body: { items: [], next_cursor: null } }))
    const router = renderPage()
    await screen.findByText(/Nenhum lançamento/)

    await userEvent.setup().click(screen.getByRole('tab', { name: 'Pendentes' }))

    expect(router.state.location.search).toBe('?aba=pendentes')
    await screen.findByText('Nenhum lançamento nesta situação.')
    const ultima = calls.at(-1)!.url
    expect(ultima.searchParams.getAll('status')).toEqual(['pendente', 'reagendado', 'vence_hoje'])
  })

  it('abre já filtrado quando a URL tem a aba', async () => {
    const calls = mockApi(() => ({ body: { items: [], next_cursor: null } }))
    renderPage('/lancamentos?aba=atrasados')
    await screen.findByText('Nenhum lançamento nesta situação.')
    expect(screen.getByRole('tab', { name: 'Atrasados' })).toHaveAttribute('aria-selected', 'true')
    expect(calls[0]!.url.searchParams.getAll('status')).toEqual(['atrasado'])
  })

  it('carrega a próxima página pelo cursor', async () => {
    const calls = mockApi((url) =>
      url.searchParams.get('cursor')
        ? { body: { items: [item('2', { descricao: 'Segunda página' })], next_cursor: null } }
        : { body: { items: [item('1', {})], next_cursor: 'abc' } },
    )
    renderPage()
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Carregar mais' }))
    expect(await screen.findByText('Segunda página')).toBeInTheDocument()
    expect(calls.at(-1)!.url.searchParams.get('cursor')).toBe('abc')
    expect(screen.queryByRole('button', { name: 'Carregar mais' })).not.toBeInTheDocument()
  })

  it('clicar na linha abre o lançamento', async () => {
    mockApi(() => ({ body: { items: [item('42', {})], next_cursor: null } }))
    const router = renderPage()
    await userEvent.setup().click(await screen.findByText('Conta de luz'))
    expect(router.state.location.pathname).toBe('/lancamentos/42')
  })
})
