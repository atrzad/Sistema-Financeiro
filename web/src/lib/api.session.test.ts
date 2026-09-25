import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch, getAccessToken, onSessionChange, setSession } from './api'
import type { TokenResponse } from './types'

const SESSAO: TokenResponse = {
  access_token: 'novo-token',
  token_type: 'bearer',
  expires_in: 900,
  user: {
    id: 'u',
    nome: 'Ana',
    email: 'a@a.com',
    role: 'admin',
    nivel_aprovacao: 2,
    tenant: { id: 't', nome: 'ACME', slug: 'acme' },
  },
}

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

function authHeader(call: unknown[]): string | null {
  return ((call[1] as RequestInit).headers as Headers).get('Authorization')
}

afterEach(() => setSession(null))

describe('renovação automática da sessão', () => {
  it('em 401 renova o token pelo cookie e repete a requisição', async () => {
    setSession({ ...SESSAO, access_token: 'expirado' })
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(json(401, { title: 'Não autenticado' }))
      .mockResolvedValueOnce(json(200, SESSAO)) // /auth/refresh
      .mockResolvedValueOnce(json(200, { ok: true }))

    await expect(apiFetch('/api/v1/users')).resolves.toEqual({ ok: true })

    expect(fetchMock.mock.calls[1]![0]).toContain('/api/v1/auth/refresh')
    expect((fetchMock.mock.calls[1]![1] as RequestInit).credentials).toBe('include')
    expect(authHeader(fetchMock.mock.calls[0]!)).toBe('Bearer expirado')
    expect(authHeader(fetchMock.mock.calls[2]!)).toBe('Bearer novo-token')
    expect(getAccessToken()).toBe('novo-token')
  })

  it('requisições simultâneas compartilham um único refresh', async () => {
    setSession({ ...SESSAO, access_token: 'expirado' })
    let refreshes = 0
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = String(input)
      if (url.endsWith('/auth/refresh')) {
        refreshes++
        return json(200, SESSAO)
      }
      const auth = ((init as RequestInit).headers as Headers).get('Authorization')
      return auth === 'Bearer novo-token' ? json(200, { url }) : json(401, {})
    })

    await Promise.all([apiFetch('/a'), apiFetch('/b'), apiFetch('/c')])

    expect(refreshes).toBe(1)
  })

  it('se o refresh falhar, encerra a sessão e propaga o 401', async () => {
    setSession(SESSAO)
    const listener = vi.fn()
    const off = onSessionChange(listener)
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(json(401, { detail: 'expirou' }))
      .mockResolvedValueOnce(json(401, { detail: 'Sessão expirada' }))

    const err = await apiFetch('/api/v1/me').catch((e: unknown) => e)

    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).status).toBe(401)
    expect(listener).toHaveBeenCalledWith(null)
    expect(getAccessToken()).toBeNull()
    off()
  })

  it('não tenta renovar em chamadas sem autenticação (ex.: login)', async () => {
    const fetchMock = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(json(401, { detail: 'Empresa, e-mail ou senha incorretos.' }))

    await expect(apiFetch('/api/v1/auth/login', { method: 'POST', auth: false })).rejects.toThrow(
      'Empresa, e-mail ou senha incorretos.',
    )
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
