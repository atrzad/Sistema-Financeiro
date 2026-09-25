import type { LancamentoOut } from '../../lib/types'
import { urgencia } from './urgencia'

export function UrgencyBadge({ lancamento }: { lancamento: LancamentoOut }) {
  const { texto, tom } = urgencia(lancamento)
  return <span className={`badge badge-${tom}`}>{texto}</span>
}
