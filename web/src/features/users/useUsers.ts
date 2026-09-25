import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { apiFetch } from '../../lib/api'
import type { Role, UserOut } from '../../lib/types'

export interface NovoUsuario {
  nome: string
  email: string
  senha: string
  role: Role
  nivel_aprovacao: number
}

export type AlteracaoUsuario = Partial<Pick<UserOut, 'nome' | 'role' | 'nivel_aprovacao' | 'ativo'>>

const KEY = ['users']

export function useUsers() {
  return useQuery({ queryKey: KEY, queryFn: () => apiFetch<UserOut[]>('/api/v1/users') })
}

export function useCreateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: NovoUsuario) =>
      apiFetch<UserOut>('/api/v1/users', { method: 'POST', body: JSON.stringify(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  })
}

export function useUpdateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...data }: AlteracaoUsuario & { id: string }) =>
      apiFetch<UserOut>(`/api/v1/users/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEY }),
  })
}
