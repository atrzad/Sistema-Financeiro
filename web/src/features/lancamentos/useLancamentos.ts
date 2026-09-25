import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '../../lib/api'
import type {
  LancamentoIn,
  LancamentoOut,
  LancamentoPage,
  LancamentoUpdate,
  StatusEfetivo,
} from '../../lib/types'

export type Aba = 'todos' | 'pendentes' | 'atrasados' | 'pagos'

export const ABAS: { id: Aba; label: string; status: StatusEfetivo[] }[] = [
  { id: 'todos', label: 'Todos', status: [] },
  { id: 'pendentes', label: 'Pendentes', status: ['pendente', 'reagendado', 'vence_hoje'] },
  { id: 'atrasados', label: 'Atrasados', status: ['atrasado'] },
  { id: 'pagos', label: 'Pagos', status: ['pago'] },
]

const KEY = 'lancamentos'

export function useLancamentos(aba: Aba) {
  const status = ABAS.find((a) => a.id === aba)?.status ?? []
  return useInfiniteQuery({
    queryKey: [KEY, 'lista', aba],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) => {
      const params = new URLSearchParams({ limit: '50' })
      status.forEach((s) => params.append('status', s))
      if (pageParam) params.set('cursor', pageParam)
      return apiFetch<LancamentoPage>(`/api/v1/lancamentos?${params}`)
    },
    getNextPageParam: (last) => last.next_cursor,
  })
}

export function useLancamento(id: string | undefined) {
  return useQuery({
    queryKey: [KEY, 'item', id],
    queryFn: () => apiFetch<LancamentoOut>(`/api/v1/lancamentos/${id}`),
    enabled: !!id,
  })
}

export function useSalvarLancamento() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      id,
      version,
      dados,
    }: {
      id?: string
      version?: number
      dados: LancamentoIn | LancamentoUpdate
    }) =>
      id
        ? apiFetch<LancamentoOut>(`/api/v1/lancamentos/${id}`, {
            method: 'PATCH',
            body: JSON.stringify(dados),
            headers: version ? { 'If-Match': `"${version}"` } : undefined,
          })
        : apiFetch<LancamentoOut>('/api/v1/lancamentos', {
            method: 'POST',
            body: JSON.stringify(dados),
          }),
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY] }),
  })
}

export function useExcluirLancamento() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiFetch<null>(`/api/v1/lancamentos/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: [KEY] }),
  })
}
