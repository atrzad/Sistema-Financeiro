import { forwardRef, type InputHTMLAttributes } from 'react'

import { digitosParaDecimal, formatBRL } from '../lib/format'

interface Props extends Omit<InputHTMLAttributes<HTMLInputElement>, 'value' | 'onChange'> {
  /** Valor decimal da API, ex.: "245.90" (string vazia = sem valor). */
  value: string
  onChange: (valor: string) => void
}

/**
 * Campo monetário no padrão brasileiro: o usuário digita só números e o valor
 * é preenchido da direita para a esquerda (centavos) — "24590" vira "R$ 245,90".
 */
export const MoneyInput = forwardRef<HTMLInputElement, Props>(function MoneyInput(
  { value, onChange, ...rest },
  ref,
) {
  const exibido = value ? formatBRL(value) : ''
  return (
    <input
      {...rest}
      ref={ref}
      inputMode="numeric"
      placeholder={rest.placeholder ?? 'R$ 0,00'}
      value={exibido}
      onChange={(e) => onChange(digitosParaDecimal(e.target.value))}
    />
  )
})
