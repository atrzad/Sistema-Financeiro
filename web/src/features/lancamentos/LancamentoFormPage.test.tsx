import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RouterProvider, createMemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { WithAuth, authState } from '../../test/auth'
import { mockApi } from '../../test/fetch'
import { LancamentoFormPage } from './LancamentoFormPage'

const CATS = [{ id: 'cat-1', nome: 'Utilidades', ativo: true }]

function renderForm(path: string) {
  const router = createMemoryRouter(
    [
      { path: '/lancamentos', element: <p>lista</p> },
      { path: '/lancamentos/novo', element: <LancamentoFormPage /> },
      { path: '/lancamentos/:id', element: <LancamentoFormPage /> },
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

function cadastros(url: URL) {
  if (url.pathname === '/api/v1/categorias') return { body: CATS }
  if (url.pathname === '/api/v1/projetos' || url.pathname === '/api/v1/centros-custo')
    return { body: [] }
  if (url.pathname === '/api/v1/suppliers')
    return { body: [{ id: 's-1', nome_fantasia: 'Padaria Central', cnpj: null }] }
  return undefined
}

describe('LancamentoFormPage', () => {
  it('valida valor obrigatório', async () => {
    mockApi(cadastros)
    renderForm('/lancamentos/novo')
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Salvar' }))
    expect(await screen.findByText('Informe o valor')).toBeInTheDocument()
  })

  it('cria lançamento com fornecedor escolhido e valor digitado em centavos', async () => {
    const calls = mockApi((url, init) => {
      if (init.method === 'POST' && url.pathname === '/api/v1/lancamentos')
        return { status: 201, body: { id: 'novo' } }
      return cadastros(url)
    })
    const router = renderForm('/lancamentos/novo')
    const user = userEvent.setup()

    await user.type(screen.getByRole('combobox', { name: 'Fornecedor' }), 'pada')
    await user.click(await screen.findByRole('option', { name: /Padaria Central/ }))
    await user.type(screen.getByPlaceholderText('R$ 0,00'), '24590')
    expect(screen.getByPlaceholderText('R$ 0,00')).toHaveValue('R$\u00a0245,90')
    await user.type(screen.getByLabelText('Vencimento'), '2026-10-05')
    await user.selectOptions(await screen.findByLabelText('Categoria'), 'cat-1')
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/lancamentos'))
    const post = calls.find((c) => c.method === 'POST')!
    expect(post.body).toMatchObject({
      supplier_id: 's-1',
      valor: '245.90',
      data_pagamento_prevista: '2026-10-05',
      categoria_id: 'cat-1',
      projeto_id: null,
      forma_pagamento: null,
      descricao: null,
    })
  })

  it('edição envia If-Match e trata conflito de versão (412)', async () => {
    const lanc = {
      id: 'l-1',
      valor: '100.00',
      data_emissao: '2026-09-01',
      data_pagamento_prevista: '2026-09-30',
      data_pagamento_efetiva: null,
      supplier: null,
      categoria: null,
      projeto: null,
      centro_custo: null,
      usuario: { id: 'u-1', nome: 'Ana Admin' },
      descricao: 'Aluguel',
      forma_pagamento: null,
      linha_digitavel: null,
      status: 'pendente',
      status_efetivo: 'pendente',
      dias_para_vencimento: 5,
      status_aprovacao: 'rascunho',
      version: 3,
      created_at: '',
      updated_at: '',
    }
    const calls = mockApi((url, init) => {
      if (url.pathname === '/api/v1/lancamentos/l-1' && init.method === 'PATCH')
        return {
          status: 412,
          body: { detail: 'Este lançamento foi alterado por outra pessoa.', versao_atual: 4 },
        }
      if (url.pathname === '/api/v1/lancamentos/l-1') return { body: lanc }
      return cadastros(url)
    })
    renderForm('/lancamentos/l-1')
    const user = userEvent.setup()

    expect(await screen.findByDisplayValue('Aluguel')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Salvar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('alterado por outra pessoa')
    expect(screen.getByRole('button', { name: 'Recarregar' })).toBeInTheDocument()
    const patch = calls.find((c) => c.method === 'PATCH')!
    expect(patch.headers.get('If-Match')).toBe('"3"')
  })

  it('cadastra fornecedor novo sem sair do formulário', async () => {
    const calls = mockApi((url, init) => {
      if (url.pathname === '/api/v1/suppliers' && init.method === 'POST')
        return { status: 201, body: { id: 's-9', nome_fantasia: 'Mercado Bom', cnpj: null } }
      if (url.pathname === '/api/v1/suppliers') return { body: [] }
      return cadastros(url)
    })
    renderForm('/lancamentos/novo')
    const user = userEvent.setup()

    await user.type(screen.getByRole('combobox', { name: 'Fornecedor' }), 'Mercado Bom')
    await user.click(await screen.findByRole('option', { name: '+ Cadastrar “Mercado Bom”' }))
    await user.click(screen.getByRole('button', { name: 'Cadastrar fornecedor' }))

    expect(await screen.findByRole('combobox', { name: 'Fornecedor' })).toHaveValue('Mercado Bom')
    expect(calls.find((c) => c.method === 'POST')!.body).toEqual({
      nome_fantasia: 'Mercado Bom',
      cnpj: null,
    })
  })
})
