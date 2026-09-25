import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { HealthPanel } from './HealthPanel'

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <HealthPanel />
    </QueryClientProvider>,
  )
}

function mockHealth(status: number, body: unknown) {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(body), { status }))
}

describe('HealthPanel', () => {
  it('mostra os três componentes operando', async () => {
    mockHealth(200, {
      status: 'ok',
      environment: 'local',
      components: {
        database: { status: 'ok', latency_ms: 1.2, detail: null },
        redis: { status: 'ok', latency_ms: 0.4, detail: null },
        storage: { status: 'ok', latency_ms: 3, detail: null },
      },
    })
    renderPanel()

    expect(await screen.findByText('Todos os componentes operando')).toBeInTheDocument()
    expect(screen.getByText('Banco de dados')).toBeInTheDocument()
    expect(screen.getByText('OK · 1.2 ms')).toBeInTheDocument()
  })

  it('exibe o componente com falha quando a API responde 503', async () => {
    mockHealth(503, {
      status: 'error',
      environment: 'local',
      components: {
        database: { status: 'ok', latency_ms: 1, detail: null },
        storage: { status: 'error', latency_ms: null, detail: 'timeout' },
      },
    })
    renderPanel()

    expect(await screen.findByText('Há componentes com falha')).toBeInTheDocument()
    expect(screen.getByText('Falha · timeout')).toBeInTheDocument()
  })

  it('avisa quando a API está fora do ar', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'))
    renderPanel()

    expect(await screen.findByRole('alert')).toHaveTextContent('API indisponível')
  })
})
