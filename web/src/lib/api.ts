/**
 * Cliente HTTP mínimo da API.
 *
 * Erros seguem RFC 9457 (Problem Details) — ver docs/convencoes.md.
 * A partir da Sprint 02 as chamadas tipadas vêm de @financeiro/api-client;
 * este wrapper continua responsável por base URL, headers e tratamento de erro.
 */

export interface ProblemDetails {
  type?: string
  title?: string
  status?: number
  detail?: string
  instance?: string
}

export class ApiError extends Error {
  readonly status: number
  readonly problem: ProblemDetails | null
  /** Corpo bruto da resposta (útil quando o erro também carrega dados, ex.: /health 503). */
  readonly body: unknown

  constructor(status: number, body: unknown) {
    const problem = isProblem(body) ? body : null
    super(problem?.detail ?? problem?.title ?? `Erro HTTP ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.problem = problem
    this.body = body
  }
}

export class NetworkError extends Error {
  constructor(cause: unknown) {
    super('Não foi possível conectar à API.', { cause })
    this.name = 'NetworkError'
  }
}

function isProblem(body: unknown): body is ProblemDetails {
  return (
    typeof body === 'object' &&
    body !== null &&
    ('title' in body || 'detail' in body || 'type' in body)
  )
}

export const API_URL = (import.meta.env.VITE_API_URL ?? '').replace(/\/+$/, '')

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (init.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, { ...init, headers })
  } catch (err) {
    throw new NetworkError(err)
  }

  const text = await response.text()
  let body: unknown = null
  if (text) {
    try {
      body = JSON.parse(text)
    } catch {
      body = text
    }
  }

  if (!response.ok) throw new ApiError(response.status, body)
  return body as T
}
