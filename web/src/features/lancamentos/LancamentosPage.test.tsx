import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
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
  tags: [],
  version: 1,
  created_at: '',
  updated_at: '',
  ...extra,
})

const TAGS = [
  { id: 't-rec', nome: 'Recorrente', ativo: true },
  { id: 't-con', nome: 'Concessionárias', ativo: true },
]

/** Responde a lista de tags do filtro e delega o resto (lançamentos) ao handler. */
function api(lista: (url: URL) => { body: unknown }) {
  return mockApi((url) => (url.pathname === '/api/v1/tags' ? { body: TAGS } : lista(url)))
}

function doLancamento(calls: ReturnType<typeof mockApi>) {
  return calls.filter((c) => c.url.pathname === '/api/v1/lancamentos')
}

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
    api(() => ({ body: { items: [item('1', {})], next_cursor: null } }))
    renderPage()

    expect(await screen.findByText('Energia Elétrica S.A.')).toBeInTheDocument()
    expect(screen.getByText('R$ 245,90')).toBeInTheDocument()
    expect(screen.getByText('25/09/2026')).toBeInTheDocument()
    expect(screen.getByText('vence hoje')).toHaveClass('badge-critico')
  })

  it('aba "Pendentes" filtra pelos status corretos e fica na URL', async () => {
    const calls = api(() => ({ body: { items: [], next_cursor: null } }))
    const router = renderPage()
    await screen.findByText(/Nenhum lançamento/)

    await userEvent.setup().click(screen.getByRole('tab', { name: 'Pendentes' }))

    expect(router.state.location.search).toBe('?aba=pendentes')
    await screen.findByText('Nenhum lançamento nesta situação.')
    const ultima = doLancamento(calls).at(-1)!.url
    expect(ultima.searchParams.getAll('status')).toEqual(['pendente', 'reagendado', 'vence_hoje'])
  })

  it('abre já filtrado quando a URL tem a aba', async () => {
    const calls = api(() => ({ body: { items: [], next_cursor: null } }))
    renderPage('/lancamentos?aba=atrasados')
    await screen.findByText('Nenhum lançamento nesta situação.')
    expect(screen.getByRole('tab', { name: 'Atrasados' })).toHaveAttribute('aria-selected', 'true')
    expect(doLancamento(calls)[0]!.url.searchParams.getAll('status')).toEqual(['atrasado'])
  })

  it('carrega a próxima página pelo cursor', async () => {
    const calls = api((url) =>
      url.searchParams.get('cursor')
        ? { body: { items: [item('2', { descricao: 'Segunda página' })], next_cursor: null } }
        : { body: { items: [item('1', {})], next_cursor: 'abc' } },
    )
    renderPage()
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Carregar mais' }))
    expect(await screen.findByText('Segunda página')).toBeInTheDocument()
    expect(doLancamento(calls).at(-1)!.url.searchParams.get('cursor')).toBe('abc')
    expect(screen.queryByRole('button', { name: 'Carregar mais' })).not.toBeInTheDocument()
  })

  it('clicar na linha abre o lançamento', async () => {
    api(() => ({ body: { items: [item('42', {})], next_cursor: null } }))
    const router = renderPage()
    await userEvent.setup().click(await screen.findByText('Conta de luz'))
    expect(router.state.location.pathname).toBe('/lancamentos/42')
  })

  it('mostra as tags de cada lançamento', async () => {
    api(() => ({
      body: {
        items: [item('1', { tags: [{ id: 't-rec', nome: 'Recorrente' }] })],
        next_cursor: null,
      },
    }))
    renderPage()
    const chips = await screen.findByRole('list', { name: 'Tags' })
    expect(within(chips).getByText('Recorrente')).toBeInTheDocument()
  })

  it('filtra por várias tags ao mesmo tempo sem perder a aba', async () => {
    const calls = api(() => ({ body: { items: [], next_cursor: null } }))
    const router = renderPage('/lancamentos?aba=pendentes')
    const user = userEvent.setup()

    await user.click(await screen.findByRole('button', { name: 'Recorrente' }))
    await user.click(screen.getByRole('button', { name: 'Concessionárias' }))

    expect(screen.getByRole('button', { name: 'Recorrente' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(router.state.location.search).toBe('?aba=pendentes&tag=t-rec&tag=t-con')
    await screen.findByText('Nenhum lançamento com as tags selecionadas.')
    const ultima = doLancamento(calls).at(-1)!.url
    expect(ultima.searchParams.getAll('tag_id')).toEqual(['t-rec', 't-con'])
    expect(ultima.searchParams.getAll('status')).toEqual(['pendente', 'reagendado', 'vence_hoje'])

    // Trocar de aba mantém as tags; "Limpar tags" remove só as tags.
    await user.click(screen.getByRole('tab', { name: 'Atrasados' }))
    expect(router.state.location.search).toBe('?aba=atrasados&tag=t-rec&tag=t-con')
    await user.click(screen.getByRole('button', { name: 'Limpar tags' }))
    expect(router.state.location.search).toBe('?aba=atrasados')
    await waitFor(() =>
      expect(doLancamento(calls).at(-1)!.url.searchParams.getAll('tag_id')).toEqual([]),
    )
  })

  it('clicar de novo na tag desfaz o filtro', async () => {
    api(() => ({ body: { items: [], next_cursor: null } }))
    const router = renderPage()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Recorrente' }))
    expect(router.state.location.search).toBe('?tag=t-rec')
    await user.click(screen.getByRole('button', { name: 'Recorrente' }))
    expect(router.state.location.search).toBe('')
    expect(screen.queryByRole('button', { name: 'Limpar tags' })).not.toBeInTheDocument()
  })

  it('sem a lista de tags, um filtro vindo da URL ainda pode ser limpo', async () => {
    mockApi((url) =>
      url.pathname === '/api/v1/tags'
        ? { status: 500, body: { detail: 'falhou' } }
        : { body: { items: [], next_cursor: null } },
    )
    const router = renderPage('/lancamentos?tag=t-antiga')
    await screen.findByText('Nenhum lançamento com as tags selecionadas.')
    await userEvent.setup().click(screen.getByRole('button', { name: 'Limpar tags' }))
    expect(router.state.location.search).toBe('')
  })
})
