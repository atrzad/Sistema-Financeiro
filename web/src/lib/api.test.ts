import { describe, expect, it, vi } from 'vitest'

import { ApiError, NetworkError, apiFetch } from './api'

function mockFetch(status: number, body: unknown) {
  return vi
    .spyOn(globalThis, 'fetch')
    .mockResolvedValue(new Response(body === undefined ? null : JSON.stringify(body), { status }))
}

describe('apiFetch', () => {
  it('retorna o JSON em respostas de sucesso', async () => {
    mockFetch(200, { ok: true })
    await expect(apiFetch('/x')).resolves.toEqual({ ok: true })
  })

  it('envia Accept e Content-Type quando há corpo', async () => {
    const spy = mockFetch(201, {})
    await apiFetch('/x', { method: 'POST', body: '{}' })
    const headers = spy.mock.calls[0]![1]!.headers as Headers
    expect(headers.get('Accept')).toBe('application/json')
    expect(headers.get('Content-Type')).toBe('application/json')
  })

  it('converte Problem Details em ApiError com mensagem legível', async () => {
    mockFetch(422, { title: 'Data inválida', detail: 'nova_data deve ser futura', status: 422 })
    const err = await apiFetch('/x').catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect((err as ApiError).status).toBe(422)
    expect((err as ApiError).message).toBe('nova_data deve ser futura')
    expect((err as ApiError).problem?.title).toBe('Data inválida')
  })

  it('usa mensagem genérica quando o erro não é Problem Details', async () => {
    mockFetch(500, undefined)
    await expect(apiFetch('/x')).rejects.toThrow('Erro HTTP 500')
  })

  it('lança NetworkError quando a API não responde', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
    await expect(apiFetch('/x')).rejects.toBeInstanceOf(NetworkError)
  })
})
