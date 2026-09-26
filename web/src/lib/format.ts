/** Formatação pt-BR via Intl (docs/convencoes.md). */

const brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })
const dataCurta = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit' })
const dataLonga = new Intl.DateTimeFormat('pt-BR', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
})

/** "245.90" → "R$ 245,90". A API trafega dinheiro como string decimal. */
export function formatBRL(valor: string | number): string {
  return brl.format(typeof valor === 'string' ? Number(valor) : valor)
}

/** Datas da API vêm como "AAAA-MM-DD" (sem fuso) — não usar new Date(str), que aplica UTC. */
function parseDate(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y!, m! - 1, d!)
}

export function formatDate(iso: string | null | undefined, longa = true): string {
  if (!iso) return '—'
  return (longa ? dataLonga : dataCurta).format(parseDate(iso))
}

/** Dígitos digitados → centavos → string decimal da API. "24590" → "245.90". */
export function digitosParaDecimal(digitos: string): string {
  const limpo = digitos.replace(/\D/g, '').replace(/^0+/, '')
  if (!limpo) return ''
  const centavos = limpo.padStart(3, '0')
  return `${centavos.slice(0, -2)}.${centavos.slice(-2)}`
}

export function formatCNPJ(cnpj: string | null | undefined): string {
  if (!cnpj || cnpj.length !== 14) return cnpj ?? ''
  return `${cnpj.slice(0, 2)}.${cnpj.slice(2, 5)}.${cnpj.slice(5, 8)}/${cnpj.slice(8, 12)}-${cnpj.slice(12)}`
}

const umaCasa = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 })

/** Tamanho de arquivo: 900 → "900 B", 184320 → "180 KB", 5452595 → "5,2 MB". */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${umaCasa.format(bytes / (1024 * 1024))} MB`
}
