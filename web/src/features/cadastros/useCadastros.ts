import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '../../lib/api'
import type { CategoriaOut, CentroCustoOut, ProjetoOut } from '../../lib/types'

export type TipoCadastro = 'categorias' | 'projetos' | 'centros-custo'

interface PorTipo {
  categorias: CategoriaOut
  projetos: ProjetoOut
  'centros-custo': CentroCustoOut
}

export function useCadastro<T extends TipoCadastro>(tipo: T, incluirInativos = false) {
  return useQuery({
    queryKey: ['cadastros', tipo, incluirInativos],
    queryFn: () =>
      apiFetch<PorTipo[T][]>(`/api/v1/${tipo}${incluirInativos ? '?incluir_inativos=true' : ''}`),
    staleTime: 5 * 60_000,
  })
}

export function useSalvarCadastro(tipo: TipoCadastro) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, dados }: { id?: string; dados: Record<string, unknown> }) =>
      apiFetch(`/api/v1/${tipo}${id ? `/${id}` : ''}`, {
        method: id ? 'PATCH' : 'POST',
        body: JSON.stringify(dados),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cadastros', tipo] }),
  })
}
