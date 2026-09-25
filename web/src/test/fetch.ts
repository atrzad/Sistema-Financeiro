import { vi } from 'vitest'

type Handler = (url: URL, init: RequestInit) => { status?: number; body?: unknown } | undefined

/** Mock de fetch roteado por método + caminho. Registra as chamadas para asserções. */
export function mockApi(handler: Handler) {
  const calls: { method: string; url: URL; body: unknown; headers: Headers }[] = []
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init = {}) => {
    const url = new URL(String(input), 'http://api.test')
    const method = (init.method ?? 'GET').toUpperCase()
    const body = typeof init.body === 'string' ? JSON.parse(init.body) : undefined
    calls.push({ method, url, body, headers: new Headers(init.headers) })
    const res = handler(url, { ...init, method }) ?? { status: 404, body: { detail: 'sem mock' } }
    return new Response(res.body === undefined ? null : JSON.stringify(res.body), {
      status: res.status ?? 200,
      headers: { 'Content-Type': 'application/json' },
    })
  })
  return calls
}
