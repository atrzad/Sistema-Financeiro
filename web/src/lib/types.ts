/** Tipos da API: gerados do OpenAPI em @financeiro/api-client (H2.6). */

import type { FormaPagamento, Role, StatusEfetivo } from '@financeiro/api-client'

export type * from '@financeiro/api-client'

export const ROLE_LABELS: Record<Role, string> = {
  admin: 'Administrador',
  aprovador: 'Aprovador',
  colaborador: 'Colaborador',
}

export const FORMA_PAGAMENTO_LABELS: Record<FormaPagamento, string> = {
  boleto: 'Boleto',
  pix: 'Pix',
  cartao: 'Cartão',
  dinheiro: 'Dinheiro',
  transferencia: 'Transferência',
  outro: 'Outro',
}

export const STATUS_LABELS: Record<StatusEfetivo, string> = {
  pendente: 'Pendente',
  reagendado: 'Reagendado',
  vence_hoje: 'Vence hoje',
  atrasado: 'Atrasado',
  pago: 'Pago',
  rejeitado: 'Rejeitado',
}
