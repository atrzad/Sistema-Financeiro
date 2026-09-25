import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '../../lib/api'
import type { SupplierIn, SupplierOut } from '../../lib/types'

const KEY = 'suppliers'

export function useBuscaFornecedores(q: string) {
  return useQuery({
    queryKey: [KEY, q],
    queryFn: () =>
      apiFetch<SupplierOut[]>(`/api/v1/suppliers?${new URLSearchParams({ q, limit: '10' })}`),
    placeholderData: (anterior) => anterior,
  })
}

export function useSalvarFornecedor() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, dados }: { id?: string; dados: Partial<SupplierIn> }) =>
      id
        ? apiFetch<SupplierOut>(`/api/v1/suppliers/${id}`, {
            method: 'PATCH',
            body: JSON.stringify(dados),
          })
        : apiFetch<SupplierOut>('/api/v1/suppliers', {
            method: 'POST',
            body: JSON.stringify(dados),
          }),
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY] }),
  })
}

export function useExcluirFornecedor() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiFetch<null>(`/api/v1/suppliers/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY] }),
  })
}
