import { describe, expect, it } from 'vitest'

import type { LancamentoOut } from '../../lib/types'
import { urgencia } from './urgencia'

const base = {
  status: 'pendente',
  data_pagamento_prevista: '2026-10-10',
  data_pagamento_efetiva: null,
} as unknown as LancamentoOut

const com = (o: Partial<LancamentoOut>) => ({ ...base, ...o }) as LancamentoOut

describe('selo de urgência', () => {
  it.each([
    [com({ status_efetivo: 'atrasado', dias_para_vencimento: -3 }), 'vencido há 3 dias', 'critico'],
    [com({ status_efetivo: 'atrasado', dias_para_vencimento: -1 }), 'vencido há 1 dia', 'critico'],
    [com({ status_efetivo: 'vence_hoje', dias_para_vencimento: 0 }), 'vence hoje', 'critico'],
    [com({ status_efetivo: 'pendente', dias_para_vencimento: 3 }), 'vence em 3 dias', 'alerta'],
    [com({ status_efetivo: 'pendente', dias_para_vencimento: 15 }), 'vence em 10/10', 'neutro'],
    [com({ status_efetivo: 'pendente', dias_para_vencimento: null }), 'sem vencimento', 'neutro'],
    [com({ status_efetivo: 'pago', data_pagamento_efetiva: '2026-09-20' }), 'pago em 20/09', 'ok'],
  ])('%#', (l, texto, tom) => {
    expect(urgencia(l)).toEqual({ texto, tom })
  })
})
