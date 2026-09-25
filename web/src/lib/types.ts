/** Tipos da API. Serão gerados do OpenAPI a partir da Sprint 02 (H2.6). */

export type Role = 'admin' | 'aprovador' | 'colaborador'

export interface TenantInfo {
  id: string
  nome: string
  slug: string
}

export interface Me {
  id: string
  nome: string
  email: string
  role: Role
  nivel_aprovacao: number
  tenant: TenantInfo
}

export interface TokenResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  user: Me
}

export interface UserOut {
  id: string
  nome: string
  email: string
  role: Role
  nivel_aprovacao: number
  ativo: boolean
  ultimo_login_em: string | null
  created_at: string
}

export const ROLE_LABELS: Record<Role, string> = {
  admin: 'Administrador',
  aprovador: 'Aprovador',
  colaborador: 'Colaborador',
}
