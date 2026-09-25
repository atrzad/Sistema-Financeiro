import { formatDate } from '../../lib/format'
import type { LancamentoOut } from '../../lib/types'

export type Tom = 'critico' | 'alerta' | 'neutro' | 'ok' | 'apagado'

export function urgencia(l: LancamentoOut): { texto: string; tom: Tom } {
  const dias = l.dias_para_vencimento
  switch (l.status_efetivo) {
    case 'pago':
      return { texto: `pago em ${formatDate(l.data_pagamento_efetiva, false)}`, tom: 'ok' }
    case 'rejeitado':
      return { texto: 'rejeitado', tom: 'apagado' }
    case 'atrasado': {
      const n = Math.abs(dias ?? 0)
      return { texto: `vencido há ${n} ${n === 1 ? 'dia' : 'dias'}`, tom: 'critico' }
    }
    case 'vence_hoje':
      return { texto: 'vence hoje', tom: 'critico' }
    default:
      if (dias == null) return { texto: 'sem vencimento', tom: 'neutro' }
      if (dias <= 7)
        return { texto: `vence em ${dias} ${dias === 1 ? 'dia' : 'dias'}`, tom: 'alerta' }
      return { texto: `vence em ${formatDate(l.data_pagamento_prevista, false)}`, tom: 'neutro' }
  }
}
