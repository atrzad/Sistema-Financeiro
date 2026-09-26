import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { EnvioError, enviarParaStorage } from './storage'

/** XMLHttpRequest mínimo: o teste decide quando e como o storage responde. */
class XhrFalso {
  static ultimo: XhrFalso | null = null
  method = ''
  url = ''
  status = 0
  corpo: unknown = null
  headers: Record<string, string> = {}
  upload: { onprogress: ((e: Partial<ProgressEvent>) => void) | null } = { onprogress: null }
  onload: (() => void) | null = null
  onerror: (() => void) | null = null
  onabort: (() => void) | null = null
  onloadend: (() => void) | null = null

  constructor() {
    XhrFalso.ultimo = this
  }
  open(method: string, url: string) {
    this.method = method
    this.url = url
  }
  setRequestHeader(nome: string, valor: string) {
    this.headers[nome] = valor
  }
  send(corpo: unknown) {
    this.corpo = corpo
  }
  abort() {
    this.onabort?.()
    this.onloadend?.()
  }
  responder(status: number) {
    this.status = status
    this.onload?.()
    this.onloadend?.()
  }
}

const arquivo = new Blob(['%PDF-1.7'], { type: 'application/pdf' })

beforeEach(() => {
  XhrFalso.ultimo = null
  vi.stubGlobal('XMLHttpRequest', XhrFalso)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('enviarParaStorage', () => {
  it('faz PUT com os headers assinados e informa o progresso', async () => {
    const progresso = vi.fn()
    const envio = enviarParaStorage(
      'https://storage/obj',
      arquivo,
      { 'Content-Type': 'application/pdf' },
      { onProgress: progresso },
    )
    const xhr = XhrFalso.ultimo!
    expect([xhr.method, xhr.url, xhr.corpo]).toEqual(['PUT', 'https://storage/obj', arquivo])
    expect(xhr.headers).toEqual({ 'Content-Type': 'application/pdf' })

    xhr.upload.onprogress?.({ lengthComputable: true, loaded: 4, total: 8 })
    expect(progresso).toHaveBeenCalledWith(4, 8)

    xhr.responder(200)
    await expect(envio).resolves.toBeUndefined()
  })

  it('403 do storage vira erro legível (link expirado ou arquivo diferente)', async () => {
    const envio = enviarParaStorage('https://storage/obj', arquivo, {})
    XhrFalso.ultimo!.responder(403)
    await expect(envio).rejects.toThrow(EnvioError)
    await expect(envio).rejects.toMatchObject({ status: 403, message: /expirou/ })
  })

  it('falha de rede não tem status HTTP', async () => {
    const envio = enviarParaStorage('https://storage/obj', arquivo, {})
    XhrFalso.ultimo!.onerror?.()
    await expect(envio).rejects.toMatchObject({ status: null, message: /conexão/ })
  })

  it('cancela pelo AbortSignal', async () => {
    const controle = new AbortController()
    const envio = enviarParaStorage('https://storage/obj', arquivo, {}, { signal: controle.signal })
    controle.abort()
    await expect(envio).rejects.toMatchObject({ name: 'AbortError' })
  })

  it('nem começa se já estiver cancelado', async () => {
    const controle = new AbortController()
    controle.abort()
    const envio = enviarParaStorage('https://storage/obj', arquivo, {}, { signal: controle.signal })
    await expect(envio).rejects.toMatchObject({ name: 'AbortError' })
    expect(XhrFalso.ultimo).toBeNull()
  })
})
