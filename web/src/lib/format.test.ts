import { describe, expect, it } from 'vitest'

import { digitosParaDecimal, formatBRL, formatBytes, formatCNPJ, formatDate } from './format'

describe('formatação pt-BR', () => {
  it('formata dinheiro vindo da API como string', () => {
    // Intl separa "R$" do número com espaço inquebrável (U+00A0).
    expect(formatBRL('245.90')).toBe('R$\u00a0245,90')
    expect(formatBRL('1234567.8')).toBe('R$\u00a01.234.567,80')
  })

  it('não desloca datas por causa do fuso (AAAA-MM-DD é data local)', () => {
    expect(formatDate('2026-09-01')).toBe('01/09/2026')
    expect(formatDate('2026-09-01', false)).toBe('01/09')
    expect(formatDate(null)).toBe('—')
  })

  it('converte dígitos digitados em centavos', () => {
    expect(digitosParaDecimal('24590')).toBe('245.90')
    expect(digitosParaDecimal('R$ 2,45')).toBe('2.45')
    expect(digitosParaDecimal('5')).toBe('0.05')
    expect(digitosParaDecimal('')).toBe('')
    expect(digitosParaDecimal('000')).toBe('')
  })

  it('formata CNPJ numérico e alfanumérico', () => {
    expect(formatCNPJ('11222333000181')).toBe('11.222.333/0001-81')
    expect(formatCNPJ('12ABC34501DE35')).toBe('12.ABC.345/01DE-35')
  })

  it('formata tamanho de arquivo', () => {
    expect(formatBytes(900)).toBe('900 B')
    expect(formatBytes(184_320)).toBe('180 KB')
    expect(formatBytes(5_452_595)).toBe('5,2 MB')
    expect(formatBytes(10 * 1024 * 1024)).toBe('10 MB')
  })
})
