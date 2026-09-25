/**
 * Cliente HTTP da API.
 *
 * - Erros seguem RFC 9457 (Problem Details) — ver docs/convencoes.md.
 * - O access token fica só em memória (nunca em localStorage). O refresh token
 *   vive num cookie HttpOnly que o JavaScript não enxerga.
 * - Em 401, tenta renovar a sessão uma única vez (single-flight: várias
 *   requisições simultâneas esperam o mesmo refresh) e repete a requisição.
 */

import type { Me, TokenResponse } from './types'

export interface ProblemDetails {
  type?: string
  title?: string
  status?: number
  detail?: string
  instance?: string
  errors?: { campo: string; erro: string }[]
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

// --- Sessão em memória -----------------------------------------------------------

type SessionListener = (user: Me | null) => void

let accessToken: string | null = null
const listeners = new Set<SessionListener>()

export function onSessionChange(listener: SessionListener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function setSession(session: TokenResponse | null): void {
  accessToken = session?.access_token ?? null
  listeners.forEach((l) => l(session?.user ?? null))
}

export function getAccessToken(): string | null {
  return accessToken
}

// --- Requisições -----------------------------------------------------------------

async function rawFetch(path: string, init: RequestInit): Promise<Response> {
  try {
    // credentials: 'include' para o navegador enviar/receber o cookie de refresh.
    return await fetch(`${API_URL}${path}`, { ...init, credentials: 'include' })
  } catch (err) {
    throw new NetworkError(err)
  }
}

async function parseBody(response: Response): Promise<unknown> {
  const text = await response.text()
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

let refreshing: Promise<boolean> | null = null

/** Troca o cookie de refresh por um novo access token. Retorna false se a sessão acabou. */
export function refreshSession(): Promise<boolean> {
  refreshing ??= (async () => {
    try {
      const response = await rawFetch('/api/v1/auth/refresh', { method: 'POST' })
      if (!response.ok) {
        setSession(null)
        return false
      }
      setSession((await parseBody(response)) as TokenResponse)
      return true
    } catch {
      setSession(null)
      return false
    } finally {
      refreshing = null
    }
  })()
  return refreshing
}

export interface ApiRequestInit extends RequestInit {
  /** Anexa o access token e tenta renovar a sessão em 401. Padrão: true. */
  auth?: boolean
}

export async function apiFetch<T>(path: string, init: ApiRequestInit = {}): Promise<T> {
  const { auth = true, ...rest } = init

  const build = (): RequestInit => {
    const headers = new Headers(rest.headers)
    headers.set('Accept', 'application/json')
    if (rest.body !== undefined && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json')
    }
    if (auth && accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
    return { ...rest, headers }
  }

  let response = await rawFetch(path, build())
  if (response.status === 401 && auth) {
    if (await refreshSession()) response = await rawFetch(path, build())
  }

  const body = await parseBody(response)
  if (!response.ok) throw new ApiError(response.status, body)
  return body as T
}
