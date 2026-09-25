import { useQuery } from '@tanstack/react-query'

import { ApiError, apiFetch } from '../../lib/api'

export type ComponentStatus = 'ok' | 'error'

export interface ComponentHealth {
  status: ComponentStatus
  latency_ms: number | null
  detail: string | null
}

export interface HealthReport {
  status: ComponentStatus
  environment: string
  components: Record<string, ComponentHealth>
}

/** Busca /health. Um 503 ainda traz o relatório por componente, então é tratado como dado. */
export async function fetchHealth(): Promise<HealthReport> {
  try {
    return await apiFetch<HealthReport>('/api/v1/health')
  } catch (err) {
    if (err instanceof ApiError && err.status === 503) return err.body as HealthReport
    throw err
  }
}

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 15_000,
    retry: false,
  })
}
