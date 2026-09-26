import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '../../lib/api'
import type { LoteStatus } from '../../lib/types'

/** A API serve o status do cache Redis, pensado para esta frequência (H3.4). */
export const INTERVALO_STATUS_MS = 2000

/** Consulta o status do lote enquanto `continuar` disser que há algo em andamento. */
export function useLoteStatus(
  batchId: string | null,
  continuar: (dados: LoteStatus | undefined) => boolean,
) {
  return useQuery({
    queryKey: ['uploads', 'lote', batchId],
    queryFn: () => apiFetch<LoteStatus>(`/api/v1/uploads/batch/${batchId}/status`),
    enabled: !!batchId,
    refetchInterval: (query) => (continuar(query.state.data) ? INTERVALO_STATUS_MS : false),
  })
}
