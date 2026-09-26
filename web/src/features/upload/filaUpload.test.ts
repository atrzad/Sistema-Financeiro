import { describe, expect, it, vi } from 'vitest'

import { ApiError, NetworkError } from '../../lib/api'
import type { ItemStatus, LoteCriado, NovoLote, UploadInstrucao } from '../../lib/types'
import {
  FilaUpload,
  estadoExibido,
  itensExibidos,
  resumir,
  type ApiUpload,
  type OpcoesFila,
} from './filaUpload'
import { EnvioError, type EnviarArquivo, type OpcoesEnvio } from './storage'

const MB = 1024 * 1024
let seq = 0

function arquivo(nome: string, tamanho = 1000): File {
  const tipo = nome.endsWith('.pdf') ? 'application/pdf' : 'image/jpeg'
  const f = new File(['x'], nome, { type: tipo, lastModified: ++seq })
  Object.defineProperty(f, 'size', { value: tamanho })
  return f
}

function arquivos(n: number): File[] {
  return Array.from({ length: n }, (_, i) => arquivo(`doc${i + 1}.pdf`))
}

function apiFalsa(extra: Partial<ApiUpload> = {}) {
  return {
    criarLote: vi.fn(async (body: NovoLote): Promise<LoteCriado> => ({
      batch_id: 'lote-1',
      expira_em: '2026-11-16T12:15:00Z',
      itens: body.arquivos.map((a, i) => ({
        comprovante_id: `c${i + 1}`,
        nome: a.nome,
        upload_url: `https://storage/c${i + 1}`,
        headers: { 'Content-Type': 'application/pdf' },
      })),
    })),
    confirmar: vi.fn(async () => ({ status: 'validando' as const })),
    novaUrl: vi.fn(async (id: string) => ({
      comprovante_id: id,
      nome: id,
      upload_url: `https://storage/novo-${id}`,
      headers: { 'Content-Type': 'application/pdf' },
    })),
    ...extra,
  }
}

interface Envio {
  url: string
  nome: string
  opcoes: OpcoesEnvio
  concluir: () => void
  falhar: (e: unknown) => void
}

/** Storage controlado pelo teste: cada PUT fica pendente até concluir/falhar. */
function storageFalso() {
  const envios: Envio[] = []
  const enviar: EnviarArquivo = (url, blob, _headers, opcoes = {}) =>
    new Promise<void>((resolve, reject) => {
      opcoes.signal?.addEventListener('abort', () =>
        reject(new DOMException('cancelado', 'AbortError')),
      )
      envios.push({ url, nome: (blob as File).name, opcoes, concluir: resolve, falhar: reject })
    })
  return { enviar, envios }
}

function montar(extra: Partial<ApiUpload> = {}, opcoes: Partial<OpcoesFila> = {}) {
  const api = apiFalsa(extra)
  const storage = storageFalso()
  const fila = new FilaUpload(api, storage.enviar, {
    criarPreview: () => 'blob:preview',
    revogarPreview: vi.fn(),
    ...opcoes,
  })
  const estados = () => fila.getSnapshot().itens.map((i) => i.estado)
  return { api, fila, envios: storage.envios, estados }
}

describe('FilaUpload — seleção', () => {
  it('marca antes do envio o que não pode ir, sem contar no limite', () => {
    const { fila, estados } = montar()
    fila.adicionar([arquivo('boleto.pdf'), arquivo('foto.heic'), arquivo('g.pdf', 11 * MB)])

    expect(estados()).toEqual(['selecionado', 'invalido', 'invalido'])
    expect(fila.getSnapshot().itens[1]!.erro).toBe('HEIC não suportado — converta para JPG')
  })

  it('aceita no máximo 10 arquivos e ignora o mesmo arquivo adicionado de novo', () => {
    const { fila } = montar()
    const repetido = arquivo('a.pdf')
    fila.adicionar([repetido, repetido])
    expect(fila.getSnapshot().itens).toHaveLength(1)

    fila.adicionar(arquivos(10))
    expect(fila.getSnapshot().itens).toHaveLength(10)
    expect(fila.getSnapshot().aviso).toMatch(/no máximo 10 arquivos/)
  })

  it('imagens ganham miniatura local, liberada ao remover', () => {
    const revogarPreview = vi.fn()
    const { fila } = montar({}, { revogarPreview })
    fila.adicionar([arquivo('foto.jpg'), arquivo('boleto.pdf')])
    const [foto, pdf] = fila.getSnapshot().itens
    expect(foto!.preview).toBe('blob:preview')
    expect(pdf!.preview).toBeNull() // PDF mostra ícone

    fila.remover(foto!.id)
    expect(revogarPreview).toHaveBeenCalledWith('blob:preview')
    expect(fila.getSnapshot().itens).toHaveLength(1)
  })
})

describe('FilaUpload — envio', () => {
  it('declara só os válidos, envia no máximo 4 por vez e confirma cada um', async () => {
    const { api, fila, envios, estados } = montar()
    fila.adicionar([...arquivos(6), arquivo('foto.heic')])

    await fila.iniciar()

    expect(api.criarLote).toHaveBeenCalledOnce()
    const declarados = vi.mocked(api.criarLote).mock.calls[0]![0].arquivos
    expect(declarados.map((a) => a.nome)).toEqual(arquivos(6).map((f) => f.name))
    expect(envios.map((e) => e.url)).toEqual([
      'https://storage/c1',
      'https://storage/c2',
      'https://storage/c3',
      'https://storage/c4',
    ])
    expect(estados()).toEqual([...Array(4).fill('enviando'), 'na_fila', 'na_fila', 'invalido'])

    envios[0]!.opcoes.onProgress?.(50, 100)
    expect(fila.getSnapshot().itens[0]!.progresso).toBe(0.5)

    envios[0]!.concluir()
    await vi.waitFor(() => expect(envios).toHaveLength(5)) // a vaga liberada puxa o próximo
    expect(api.confirmar).toHaveBeenCalledWith('c1')
    expect(estados()[0]).toBe('enviado')
    expect(fila.getSnapshot().itens[0]!.statusConfirmado).toBe('validando')
  })

  it('erro de envio permite tentar de novo com um link novo', async () => {
    const { api, fila, envios, estados } = montar()
    fila.adicionar([arquivo('a.pdf')])
    await fila.iniciar()

    envios[0]!.falhar(new EnvioError('O link de envio expirou ou não confere com o arquivo.', 403))
    await vi.waitFor(() => expect(estados()).toEqual(['erro_envio']))
    expect(fila.getSnapshot().itens[0]!.erro).toMatch(/expirou/)

    await fila.tentarNovamente(fila.getSnapshot().itens[0]!.id)

    expect(api.novaUrl).toHaveBeenCalledWith('c1')
    expect(envios[1]!.url).toBe('https://storage/novo-c1')
    envios[1]!.concluir()
    await vi.waitFor(() => expect(estados()).toEqual(['enviado']))
  })

  it('se o servidor já tinha recebido, "tentar novamente" não reenvia', async () => {
    const { api, fila, envios, estados } = montar({
      confirmar: vi.fn(async () => {
        throw new NetworkError(new TypeError('Failed to fetch'))
      }),
      novaUrl: vi.fn(async () => {
        throw new ApiError(409, { detail: 'Este arquivo já foi recebido.' })
      }),
    })
    fila.adicionar([arquivo('a.pdf')])
    await fila.iniciar()
    envios[0]!.concluir()
    await vi.waitFor(() => expect(estados()).toEqual(['erro_envio']))

    await fila.tentarNovamente(fila.getSnapshot().itens[0]!.id)

    expect(api.novaUrl).toHaveBeenCalledOnce()
    expect(envios).toHaveLength(1)
    expect(estados()).toEqual(['enviado'])
  })

  it('pede link novo se o arquivo esperou demais na fila', async () => {
    let agora = 0
    const { api, fila, envios } = montar({}, { concorrencia: 1, agora: () => agora })
    fila.adicionar(arquivos(2))
    await fila.iniciar()

    agora = 11 * 60_000 // o primeiro demorou 11 min para subir
    envios[0]!.concluir()

    await vi.waitFor(() => expect(envios).toHaveLength(2))
    expect(api.novaUrl).toHaveBeenCalledWith('c2')
    expect(envios[1]!.url).toBe('https://storage/novo-c2')
  })

  it('cancelar tudo interrompe os envios e tira os demais da fila', async () => {
    const { api, fila, envios, estados } = montar()
    fila.adicionar(arquivos(6))
    await fila.iniciar()

    fila.cancelarTudo()

    expect(envios.every((e) => e.opcoes.signal?.aborted)).toBe(true)
    await vi.waitFor(() => expect(estados()).toEqual(Array(6).fill('cancelado')))
    expect(envios).toHaveLength(4)
    expect(api.confirmar).not.toHaveBeenCalled()
  })

  it('item cancelado enquanto pedia link novo não volta para a fila', async () => {
    let entregarLink!: (i: UploadInstrucao) => void
    const { fila, envios, estados } = montar({
      novaUrl: vi.fn(() => new Promise<UploadInstrucao>((resolve) => (entregarLink = resolve))),
    })
    fila.adicionar([arquivo('a.pdf')])
    await fila.iniciar()
    envios[0]!.falhar(new EnvioError('Falha de conexão durante o envio.', null))
    await vi.waitFor(() => expect(estados()).toEqual(['erro_envio']))

    const tentando = fila.tentarNovamente(fila.getSnapshot().itens[0]!.id)
    fila.cancelarTudo()
    entregarLink({ comprovante_id: 'c1', nome: 'a.pdf', upload_url: 'https://x', headers: {} })
    await tentando

    expect(estados()).toEqual(['cancelado'])
    expect(envios).toHaveLength(1)
  })

  it('cancelar enquanto o lote é criado descarta tudo', async () => {
    let criar!: (l: LoteCriado) => void
    const { fila, envios } = montar({
      criarLote: vi.fn(() => new Promise<LoteCriado>((resolve) => (criar = resolve))),
    })
    fila.adicionar([arquivo('a.pdf')])
    const iniciando = fila.iniciar()
    expect(fila.getSnapshot().fase).toBe('criando')

    fila.cancelarTudo()
    criar({ batch_id: 'l', expira_em: '', itens: [] })
    await iniciando

    expect(fila.getSnapshot()).toMatchObject({ fase: 'selecao', itens: [] })
    expect(envios).toHaveLength(0)
  })

  it('arquivo recusado pela API volta marcado para a seleção', async () => {
    const { fila, envios, estados } = montar({
      criarLote: vi.fn(async () => {
        throw new ApiError(422, {
          detail: 'Há arquivos que não podem ser enviados.',
          errors: [{ campo: 'arquivos.1', erro: 'Arquivo acima de 10 MB.' }],
        })
      }),
    })
    fila.adicionar(arquivos(2))
    await fila.iniciar()

    expect(fila.getSnapshot()).toMatchObject({
      fase: 'selecao',
      aviso: 'Há arquivos que não podem ser enviados.',
    })
    expect(estados()).toEqual(['selecionado', 'invalido'])
    expect(fila.getSnapshot().itens[1]!.erro).toBe('Arquivo acima de 10 MB.')
    expect(envios).toHaveLength(0)
  })
})

describe('estado exibido', () => {
  const servidor = (extra: Partial<ItemStatus>): ItemStatus => ({
    comprovante_id: 'c1',
    nome: 'carne.pdf',
    tamanho_bytes: 1000,
    mime_type: 'application/pdf',
    status: 'concluido',
    erro_msg: null,
    total_paginas: 3,
    possivel_duplicado: false,
    tem_miniatura: true,
    ...extra,
  })

  it('depois da confirmação vale o status do servidor', async () => {
    const { fila, envios } = montar()
    fila.adicionar([arquivo('carne.pdf'), arquivo('outro.pdf')])
    await fila.iniciar()
    envios[0]!.concluir()
    await vi.waitFor(() => expect(fila.getSnapshot().itens[0]!.estado).toBe('enviado'))
    const [enviado, subindo] = fila.getSnapshot().itens

    expect(estadoExibido(enviado!, undefined).estado).toBe('validando')
    // Retrato do servidor anterior à confirmação.
    expect(estadoExibido(enviado!, servidor({ status: 'enviando' })).estado).toBe('validando')
    expect(estadoExibido(enviado!, servidor({ possivel_duplicado: true }))).toMatchObject({
      estado: 'concluido',
      paginas: 3,
      duplicado: true,
    })
    // Enquanto sobe do navegador, vale o estado local.
    expect(estadoExibido(subindo!, servidor({ comprovante_id: 'c2' })).estado).toBe('enviando')
  })

  it('resume o lote sem contar cancelados nem inválidos', async () => {
    const { fila, envios } = montar()
    fila.adicionar([...arquivos(3), arquivo('x.heic')])
    await fila.iniciar()
    envios[0]!.concluir()
    envios[1]!.falhar(new EnvioError('Falha de conexão durante o envio.', null))
    await vi.waitFor(() => expect(fila.getSnapshot().itens[1]!.estado).toBe('erro_envio'))

    const lote = {
      batch_id: 'lote-1',
      total: 3,
      concluidos: 1,
      com_erro: 0,
      em_andamento: 2,
      itens: [servidor({})],
    }
    let resumo = resumir(fila.getSnapshot(), itensExibidos(fila.getSnapshot(), lote))
    expect(resumo).toMatchObject({ selecionados: 3, total: 3, processados: 2, emAndamento: 1 })
    expect(resumo.finalizado).toBe(false)

    fila.cancelarTudo()
    await vi.waitFor(() => expect(fila.getSnapshot().itens[2]!.estado).toBe('cancelado'))
    resumo = resumir(fila.getSnapshot(), itensExibidos(fila.getSnapshot(), lote))
    expect(resumo).toMatchObject({ total: 1, processados: 1, emAndamento: 0, finalizado: true })
  })
})
