/**
 * Fila de envio de comprovantes (H3.5) — sem React, para ser testável sozinha.
 *
 * 1. O usuário escolhe os arquivos; os que não passam nas regras ficam marcados e
 *    não são enviados.
 * 2. "Continuar" declara o lote na API, que devolve uma URL de upload por arquivo.
 * 3. No máximo `concorrencia` arquivos sobem ao mesmo tempo, direto ao storage.
 * 4. Cada arquivo enviado é confirmado na API, que enfileira a validação. Daqui em
 *    diante quem manda é o status do servidor (ver `estadoExibido`).
 *
 * A fila vive acima das rotas (UploadProvider): trocar de tela não interrompe o envio.
 */

import { ApiError, NetworkError, apiFetch } from '../../lib/api'
import type {
  Confirmacao,
  ItemStatus,
  LoteCriado,
  LoteStatus,
  NovoLote,
  StatusProcessamento,
  UploadInstrucao,
} from '../../lib/types'
import { MAX_ARQUIVOS, MAX_BYTES_LOTE, ehPdf, problemaDoArquivo } from './regras'
import { EnvioError, enviarParaStorage, type EnviarArquivo } from './storage'

export type EstadoLocal =
  | 'selecionado' // escolhido, aguardando "Continuar"
  | 'invalido' // recusado antes do envio (formato, tamanho)
  | 'na_fila'
  | 'enviando'
  | 'enviado' // no storage e confirmado na API
  | 'erro_envio' // falhou o envio ou a confirmação — pode tentar de novo
  | 'cancelado'

export interface ItemFila {
  id: string
  arquivo: File
  nome: string
  tamanho: number
  pdf: boolean
  /** URL local (blob:) para a miniatura de imagens; PDFs mostram um ícone. */
  preview: string | null
  estado: EstadoLocal
  /** 0 a 1. */
  progresso: number
  erro: string | null
  comprovanteId: string | null
  /** Status devolvido pela confirmação, até o primeiro retorno do polling. */
  statusConfirmado: StatusProcessamento | null
}

export interface EstadoFila {
  fase: 'selecao' | 'criando' | 'envio'
  batchId: string | null
  itens: ItemFila[]
  /** Mensagem geral: limite de arquivos, falha ao criar o lote etc. */
  aviso: string | null
}

export interface ApiUpload {
  criarLote(body: NovoLote): Promise<LoteCriado>
  confirmar(comprovanteId: string): Promise<Confirmacao>
  novaUrl(comprovanteId: string): Promise<UploadInstrucao>
}

export const apiUpload: ApiUpload = {
  criarLote: (body) =>
    apiFetch<LoteCriado>('/api/v1/uploads/batch', { method: 'POST', body: JSON.stringify(body) }),
  confirmar: (id) => apiFetch<Confirmacao>(`/api/v1/uploads/${id}/complete`, { method: 'POST' }),
  novaUrl: (id) => apiFetch<UploadInstrucao>(`/api/v1/uploads/${id}/retry-url`, { method: 'POST' }),
}

export interface OpcoesFila {
  concorrencia: number
  /** A API emite links de 15 min; acima disto, pede um novo antes de começar o envio. */
  reusoLinkMs: number
  agora: () => number
  criarPreview: (arquivo: File) => string | null
  revogarPreview: (url: string) => void
}

const PADRAO: OpcoesFila = {
  concorrencia: 4,
  reusoLinkMs: 10 * 60_000,
  agora: () => Date.now(),
  criarPreview: (arquivo) => URL.createObjectURL(arquivo),
  revogarPreview: (url) => URL.revokeObjectURL(url),
}

interface Link {
  url: string
  headers: Record<string, string>
  recebidoEm: number
}

const VAZIO: EstadoFila = { fase: 'selecao', batchId: null, itens: [], aviso: null }

function mensagemDeErro(err: unknown): string {
  if (err instanceof EnvioError || err instanceof ApiError || err instanceof NetworkError) {
    return err.message
  }
  return 'Não foi possível enviar o arquivo.'
}

/** 422 da API: `errors[].campo = "arquivos.N"` aponta o arquivo recusado. */
function errosPorPosicao(err: unknown): Map<number, string> {
  const erros = new Map<number, string>()
  if (!(err instanceof ApiError)) return erros
  for (const e of err.problem?.errors ?? []) {
    const m = /^arquivos\.(\d+)$/.exec(e.campo)
    if (m) erros.set(Number(m[1]), e.erro)
  }
  return erros
}

export class FilaUpload {
  private estado: EstadoFila = VAZIO
  private readonly ouvintes = new Set<() => void>()
  private readonly links = new Map<string, Link>()
  private readonly controles = new Map<string, AbortController>()
  private readonly renovando = new Set<string>()
  private readonly opcoes: OpcoesFila
  private seq = 0

  constructor(
    private readonly api: ApiUpload = apiUpload,
    private readonly enviar: EnviarArquivo = enviarParaStorage,
    opcoes: Partial<OpcoesFila> = {},
  ) {
    this.opcoes = { ...PADRAO, ...opcoes }
  }

  // --- Leitura (useSyncExternalStore) ------------------------------------------------

  subscribe = (ouvinte: () => void): (() => void) => {
    this.ouvintes.add(ouvinte)
    return () => this.ouvintes.delete(ouvinte)
  }

  getSnapshot = (): EstadoFila => this.estado

  private definir(parcial: Partial<EstadoFila>): void {
    this.estado = { ...this.estado, ...parcial }
    this.ouvintes.forEach((o) => o())
  }

  private atualizar(id: string, parcial: Partial<ItemFila>): void {
    this.definir({ itens: this.estado.itens.map((i) => (i.id === id ? { ...i, ...parcial } : i)) })
  }

  private item(id: string): ItemFila | undefined {
    return this.estado.itens.find((i) => i.id === id)
  }

  // --- Seleção -----------------------------------------------------------------------

  adicionar = (arquivos: File[]): void => {
    if (this.estado.fase !== 'selecao') return
    const itens = [...this.estado.itens]
    let aviso: string | null = null
    for (const arquivo of arquivos) {
      const repetido = itens.some(
        (i) =>
          i.nome === arquivo.name &&
          i.tamanho === arquivo.size &&
          i.arquivo.lastModified === arquivo.lastModified,
      )
      if (repetido) continue
      const erro = problemaDoArquivo(arquivo)
      if (!erro && itens.filter((i) => i.estado === 'selecionado').length >= MAX_ARQUIVOS) {
        aviso = `São no máximo ${MAX_ARQUIVOS} arquivos por envio — os demais não foram adicionados.`
        continue
      }
      const pdf = ehPdf(arquivo.name)
      itens.push({
        id: `f${++this.seq}`,
        arquivo,
        nome: arquivo.name,
        tamanho: arquivo.size,
        pdf,
        preview: erro || pdf ? null : this.opcoes.criarPreview(arquivo),
        estado: erro ? 'invalido' : 'selecionado',
        progresso: 0,
        erro,
        comprovanteId: null,
        statusConfirmado: null,
      })
    }
    this.definir({ itens, aviso })
  }

  remover = (id: string): void => {
    const item = this.item(id)
    if (this.estado.fase !== 'selecao' || !item) return
    if (item.preview) this.opcoes.revogarPreview(item.preview)
    this.definir({ itens: this.estado.itens.filter((i) => i.id !== id), aviso: null })
  }

  /** Descarta tudo (também usado para começar um novo envio). */
  limpar = (): void => {
    this.controles.forEach((c) => c.abort())
    this.controles.clear()
    this.links.clear()
    this.estado.itens.forEach((i) => i.preview && this.opcoes.revogarPreview(i.preview))
    this.definir(VAZIO)
  }

  // --- Envio -------------------------------------------------------------------------

  /** O usuário cancelou enquanto o lote era criado. */
  private descartado(): boolean {
    return this.estado.fase !== 'criando'
  }

  iniciar = async (): Promise<void> => {
    if (this.estado.fase !== 'selecao') return
    const envio = this.estado.itens.filter((i) => i.estado === 'selecionado')
    const total = envio.reduce((s, i) => s + i.tamanho, 0)
    if (envio.length === 0 || total > MAX_BYTES_LOTE) return

    this.definir({ fase: 'criando', aviso: null })
    let lote: LoteCriado
    try {
      lote = await this.api.criarLote({
        origem: 'web',
        arquivos: envio.map((i) => ({
          nome: i.nome,
          tamanho_bytes: i.tamanho,
          mime_type: i.arquivo.type || null,
        })),
      })
    } catch (err) {
      if (this.descartado()) return
      const recusados = errosPorPosicao(err)
      const posicao = new Map(envio.map((item, n) => [item.id, n]))
      this.definir({
        fase: 'selecao',
        aviso: mensagemDeErro(err),
        itens: this.estado.itens.map((i) => {
          const erro = recusados.get(posicao.get(i.id) ?? -1)
          return erro ? { ...i, estado: 'invalido', erro } : i
        }),
      })
      return
    }
    if (this.descartado()) return

    // A API devolve as instruções na mesma ordem em que os arquivos foram declarados.
    const recebidoEm = this.opcoes.agora()
    const porItem = new Map(envio.map((item, n) => [item.id, lote.itens[n]]))
    porItem.forEach((instr, id) => {
      if (instr) this.links.set(id, { url: instr.upload_url, headers: instr.headers, recebidoEm })
    })
    this.definir({
      fase: 'envio',
      batchId: lote.batch_id,
      itens: this.estado.itens.map((i) => {
        const instr = porItem.get(i.id)
        return instr ? { ...i, estado: 'na_fila', comprovanteId: instr.comprovante_id } : i
      }),
    })
    this.bombear()
  }

  /** Começa os próximos da fila até ocupar as vagas de envio simultâneo. */
  private bombear(): void {
    let vagas =
      this.opcoes.concorrencia - this.estado.itens.filter((i) => i.estado === 'enviando').length
    for (const item of this.estado.itens) {
      if (vagas <= 0) break
      if (item.estado === 'na_fila') {
        vagas--
        void this.enviarItem(item.id)
      }
    }
  }

  private async renovarLink(item: ItemFila): Promise<Link> {
    const instr = await this.api.novaUrl(item.comprovanteId!)
    const link = { url: instr.upload_url, headers: instr.headers, recebidoEm: this.opcoes.agora() }
    this.links.set(item.id, link)
    return link
  }

  private async enviarItem(id: string): Promise<void> {
    const controle = new AbortController()
    this.controles.set(id, controle)
    this.atualizar(id, { estado: 'enviando', progresso: 0, erro: null })
    try {
      const item = this.item(id)!
      let link = this.links.get(id)!
      if (this.opcoes.agora() - link.recebidoEm > this.opcoes.reusoLinkMs) {
        link = await this.renovarLink(item) // esperou demais na fila: o link pode ter expirado
      }
      await this.enviar(link.url, item.arquivo, link.headers, {
        signal: controle.signal,
        onProgress: (enviados, total) =>
          this.atualizar(id, { progresso: total > 0 ? enviados / total : 0 }),
      })
      controle.signal.throwIfAborted()
      const { status } = await this.api.confirmar(item.comprovanteId!)
      this.atualizar(id, { estado: 'enviado', progresso: 1, statusConfirmado: status })
    } catch (err) {
      if (controle.signal.aborted) this.atualizar(id, { estado: 'cancelado', progresso: 0 })
      else this.atualizar(id, { estado: 'erro_envio', erro: mensagemDeErro(err) })
    } finally {
      this.controles.delete(id)
      this.bombear()
    }
  }

  /** Reenvia um item que falhou, com um link novo (o anterior pode ter expirado). */
  tentarNovamente = async (id: string): Promise<void> => {
    const item = this.item(id)
    if (!item || item.estado !== 'erro_envio' || this.renovando.has(id)) return
    this.renovando.add(id)
    // Cancelado ou descartado enquanto o link novo era pedido: não volta para a fila.
    const aindaEmErro = () => this.item(id)?.estado === 'erro_envio'
    try {
      await this.renovarLink(item)
      if (!aindaEmErro()) return
      this.atualizar(id, { estado: 'na_fila', erro: null, progresso: 0 })
      this.bombear()
    } catch (err) {
      if (!aindaEmErro()) return
      if (err instanceof ApiError && err.status === 409) {
        // O servidor já recebeu o arquivo (a confirmação chegou, a resposta é que se perdeu).
        this.atualizar(id, { estado: 'enviado', erro: null, progresso: 1 })
      } else {
        this.atualizar(id, { erro: mensagemDeErro(err) })
      }
    } finally {
      this.renovando.delete(id)
    }
  }

  /** Antes do envio, descarta tudo; durante, interrompe o que ainda não subiu. */
  cancelarTudo = (): void => {
    if (this.estado.fase !== 'envio') {
      this.limpar()
      return
    }
    const pendente: EstadoLocal[] = ['na_fila', 'erro_envio']
    this.definir({
      itens: this.estado.itens.map((i) =>
        pendente.includes(i.estado) ? { ...i, estado: 'cancelado', progresso: 0 } : i,
      ),
    })
    this.controles.forEach((c) => c.abort())
  }
}

// --- Estado exibido (local + servidor) ----------------------------------------------

export type EstadoExibido = Exclude<EstadoLocal, 'enviado' | 'erro_envio'> | StatusProcessamento

export interface ItemExibido {
  item: ItemFila
  estado: EstadoExibido
  erro: string | null
  paginas: number | null
  duplicado: boolean
  /** Falhou no envio (e não na validação): dá para tentar de novo. */
  podeTentarNovamente: boolean
}

export function estadoExibido(item: ItemFila, servidor: ItemStatus | undefined): ItemExibido {
  const base = { item, paginas: null, duplicado: false, podeTentarNovamente: false }
  if (item.estado === 'erro_envio') {
    return { ...base, estado: 'erro', erro: item.erro, podeTentarNovamente: true }
  }
  if (item.estado !== 'enviado') return { ...base, estado: item.estado, erro: item.erro }

  const status = servidor?.status ?? item.statusConfirmado ?? 'validando'
  return {
    ...base,
    // "enviando" aqui é um retrato do servidor anterior à confirmação.
    estado: status === 'enviando' ? 'validando' : status,
    erro: servidor?.erro_msg ?? null,
    paginas: servidor && status !== 'erro' ? servidor.total_paginas : null,
    duplicado: servidor?.possivel_duplicado ?? false,
  }
}

/** Cada item da fila com o status mais recente do servidor, quando houver. */
export function itensExibidos(estado: EstadoFila, servidor: LoteStatus | undefined): ItemExibido[] {
  const porId = new Map(servidor?.itens.map((i) => [i.comprovante_id, i]))
  return estado.itens.map((item) =>
    estadoExibido(item, item.comprovanteId ? porId.get(item.comprovanteId) : undefined),
  )
}

const EM_ANDAMENTO = new Set<EstadoExibido>(['na_fila', 'enviando', 'validando', 'processando_ocr'])
const PROCESSADO = new Set<EstadoExibido>(['concluido', 'aguardando_revisao', 'erro'])

export interface Resumo {
  /** Arquivos que irão (ou foram) para o servidor — o "N" de "N/10". */
  selecionados: number
  bytesSelecionados: number
  /** "X de `total` processados" — sem os cancelados. */
  total: number
  processados: number
  emAndamento: number
  /** Algum arquivo ainda subindo do navegador (fechar a aba interromperia). */
  enviandoDoNavegador: boolean
  finalizado: boolean
}

export function resumir(estado: EstadoFila, itens: ItemExibido[]): Resumo {
  const doLote = itens.filter((i) => i.estado !== 'invalido')
  const validos = doLote.filter((i) => i.estado !== 'cancelado')
  return {
    selecionados: doLote.length,
    bytesSelecionados: doLote.reduce((s, i) => s + i.item.tamanho, 0),
    total: validos.length,
    processados: validos.filter((i) => PROCESSADO.has(i.estado)).length,
    emAndamento: validos.filter((i) => EM_ANDAMENTO.has(i.estado)).length,
    enviandoDoNavegador:
      estado.fase === 'criando' ||
      estado.itens.some((i) => i.estado === 'na_fila' || i.estado === 'enviando'),
    finalizado:
      estado.fase === 'envio' &&
      validos.every(
        (i) => PROCESSADO.has(i.estado) && !(i.estado === 'erro' && i.podeTentarNovamente),
      ),
  }
}
