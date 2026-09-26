/**
 * Envio do arquivo direto ao storage, pela URL pré-assinada que a API devolve.
 *
 * O arquivo nunca passa pela API. A URL fixa tipo e tamanho: qualquer divergência
 * é recusada pelo próprio storage (403). Usa XMLHttpRequest porque o fetch não
 * informa o progresso do envio.
 */

export class EnvioError extends Error {
  /** null = sem resposta (rede, CORS, storage fora do ar). */
  readonly status: number | null

  constructor(message: string, status: number | null) {
    super(message)
    this.name = 'EnvioError'
    this.status = status
  }
}

export interface OpcoesEnvio {
  onProgress?: (enviados: number, total: number) => void
  signal?: AbortSignal
}

export type EnviarArquivo = (
  url: string,
  arquivo: Blob,
  headers: Record<string, string>,
  opcoes?: OpcoesEnvio,
) => Promise<void>

function cancelado(): DOMException {
  return new DOMException('Envio cancelado.', 'AbortError')
}

function mensagemHttp(status: number): string {
  if (status === 403) return 'O link de envio expirou ou não confere com o arquivo.'
  if (status === 413) return 'O armazenamento recusou o arquivo por ser grande demais.'
  return `O armazenamento recusou o arquivo (HTTP ${status}).`
}

export const enviarParaStorage: EnviarArquivo = (url, arquivo, headers, opcoes = {}) => {
  const { onProgress, signal } = opcoes
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) {
      reject(cancelado())
      return
    }
    const xhr = new XMLHttpRequest()
    const abortar = () => xhr.abort()

    xhr.open('PUT', url)
    // Os headers assinados (Content-Type) precisam ir exatamente como vieram.
    for (const [nome, valor] of Object.entries(headers)) xhr.setRequestHeader(nome, valor)
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress?.(e.loaded, e.total)
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve()
      else reject(new EnvioError(mensagemHttp(xhr.status), xhr.status))
    }
    xhr.onerror = () =>
      reject(new EnvioError('Falha de conexão durante o envio. Verifique a internet.', null))
    xhr.onabort = () => reject(cancelado())
    xhr.onloadend = () => signal?.removeEventListener('abort', abortar)
    signal?.addEventListener('abort', abortar, { once: true })
    xhr.send(arquivo)
  })
}
