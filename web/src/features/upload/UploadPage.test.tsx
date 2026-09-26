import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { mockApi } from '../../test/fetch'
import { FilaUpload } from './filaUpload'
import { EnvioError, type EnviarArquivo } from './storage'
import { UploadPage } from './UploadPage'
import { UploadProvider } from './UploadProvider'

function arquivo(nome: string, tipo = 'application/pdf'): File {
  return new File(['conteudo'], nome, { type: tipo })
}

function renderPage(enviar: EnviarArquivo = async () => undefined) {
  const fila = new FilaUpload(undefined, enviar, {
    criarPreview: () => 'blob:preview',
    revogarPreview: () => undefined,
  })
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <UploadProvider fila={fila}>
        <UploadPage />
      </UploadProvider>
    </QueryClientProvider>,
  )
  // O seletor do sistema já filtra por tipo; aqui o teste simula arrastar qualquer arquivo.
  return { fila, user: userEvent.setup({ applyAccept: false }) }
}

const instrucao = (id: string, nome: string) => ({
  comprovante_id: id,
  nome,
  upload_url: `https://storage.test/${id}`,
  headers: { 'Content-Type': 'application/pdf' },
})

const itemServidor = (id: string, nome: string, extra: object) => ({
  comprovante_id: id,
  nome,
  tamanho_bytes: 8,
  mime_type: 'application/pdf',
  status: 'concluido',
  erro_msg: null,
  total_paginas: 1,
  possivel_duplicado: false,
  tem_miniatura: true,
  ...extra,
})

describe('UploadPage', () => {
  it('mostra o erro de formato antes do envio e conta só os arquivos válidos', async () => {
    const { user } = renderPage()
    await user.upload(screen.getByLabelText('Selecionar arquivos'), [
      arquivo('boleto.pdf'),
      arquivo('IMG_0042.HEIC', 'image/heic'),
    ])

    expect(screen.getByRole('heading')).toHaveTextContent('Anexar comprovantes (1/10)')
    expect(screen.getByText('HEIC não suportado — converta para JPG')).toBeInTheDocument()
    expect(screen.getByText('não será enviado')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Remover IMG_0042.HEIC' }))
    expect(screen.queryByText(/HEIC não suportado/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Continuar' })).toBeEnabled()
  })

  it('envia, acompanha a validação e mostra o resultado de cada arquivo', async () => {
    const calls = mockApi((url, init) => {
      if (url.pathname === '/api/v1/uploads/batch' && init.method === 'POST') {
        return {
          status: 201,
          body: {
            batch_id: 'lote-1',
            expira_em: '2026-11-16T12:15:00Z',
            itens: [instrucao('c1', 'carne.pdf'), instrucao('c2', 'falso.pdf')],
          },
        }
      }
      if (url.pathname.endsWith('/complete')) return { status: 202, body: { status: 'validando' } }
      if (url.pathname === '/api/v1/uploads/batch/lote-1/status') {
        return {
          body: {
            batch_id: 'lote-1',
            total: 2,
            concluidos: 1,
            com_erro: 1,
            em_andamento: 0,
            itens: [
              itemServidor('c1', 'carne.pdf', { total_paginas: 3 }),
              itemServidor('c2', 'falso.pdf', {
                status: 'erro',
                erro_msg:
                  'O conteúdo do arquivo não é PDF (a extensão não corresponde ao arquivo).',
              }),
            ],
          },
        }
      }
    })
    const enviar = vi.fn<EnviarArquivo>(async () => undefined)
    const { user } = renderPage(enviar)
    await user.upload(screen.getByLabelText('Selecionar arquivos'), [
      arquivo('carne.pdf'),
      arquivo('falso.pdf'),
    ])

    await user.click(screen.getByRole('button', { name: 'Continuar' }))

    expect(await screen.findByText(/3 páginas/)).toBeInTheDocument()
    expect(screen.getByText(/não é PDF/)).toBeInTheDocument()
    expect(
      screen.getByText(
        (_, el) => el?.tagName === 'P' && el.textContent === 'Progresso geral: 2 de 2 processados',
      ),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Enviar mais comprovantes' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Tentar novamente/ })).not.toBeInTheDocument()

    // O arquivo vai direto ao storage; a API só recebe a declaração (JSON).
    expect(enviar.mock.calls.map((c) => c[0])).toEqual([
      'https://storage.test/c1',
      'https://storage.test/c2',
    ])
    const lote = calls.find((c) => c.url.pathname === '/api/v1/uploads/batch')!
    expect(lote.body).toEqual({
      origem: 'web',
      arquivos: [
        { nome: 'carne.pdf', tamanho_bytes: 8, mime_type: 'application/pdf' },
        { nome: 'falso.pdf', tamanho_bytes: 8, mime_type: 'application/pdf' },
      ],
    })
  })

  it('falha no envio oferece "tentar novamente", que pede um link novo', async () => {
    const calls = mockApi((url) => {
      if (url.pathname === '/api/v1/uploads/batch') {
        return {
          status: 201,
          body: { batch_id: 'lote-1', expira_em: '', itens: [instrucao('c1', 'a.pdf')] },
        }
      }
      if (url.pathname === '/api/v1/uploads/c1/retry-url') {
        return { body: { ...instrucao('c1', 'a.pdf'), upload_url: 'https://storage.test/novo' } }
      }
      if (url.pathname.endsWith('/complete')) return { status: 202, body: { status: 'validando' } }
      if (url.pathname.endsWith('/status')) {
        return {
          body: {
            batch_id: 'lote-1',
            total: 1,
            concluidos: 0,
            com_erro: 0,
            em_andamento: 1,
            itens: [itemServidor('c1', 'a.pdf', { status: 'enviando' })],
          },
        }
      }
    })
    const enviar = vi
      .fn<EnviarArquivo>()
      .mockRejectedValueOnce(new EnvioError('Falha de conexão durante o envio.', null))
      .mockResolvedValue(undefined)
    const { user } = renderPage(enviar)
    await user.upload(screen.getByLabelText('Selecionar arquivos'), [arquivo('a.pdf')])
    await user.click(screen.getByRole('button', { name: 'Continuar' }))

    expect(await screen.findByText('Falha de conexão durante o envio.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Tentar novamente a.pdf' }))

    await waitFor(() => expect(screen.getByText('validando')).toBeInTheDocument())
    expect(enviar.mock.calls.at(-1)![0]).toBe('https://storage.test/novo')
    expect(calls.some((c) => c.url.pathname === '/api/v1/uploads/c1/complete')).toBe(true)
  })
})
