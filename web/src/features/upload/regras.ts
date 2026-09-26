/**
 * Regras de envio checadas no navegador, antes de qualquer upload (H3.5).
 *
 * Espelham as da API (RNF07/RNF08), que revalida tudo — aqui é só para o usuário
 * saber do problema na hora, com um texto que diga o que fazer.
 */

import { formatBytes } from '../../lib/format'

export const MAX_ARQUIVOS = 10
export const MAX_BYTES_ARQUIVO = 10 * 1024 * 1024
export const MAX_BYTES_LOTE = 60 * 1024 * 1024

const EXTENSOES = new Set(['.pdf', '.jpg', '.jpeg', '.png'])

/** Para o seletor de arquivos do sistema operacional. */
export const ACCEPT = '.pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png'

/** Formatos comuns que as pessoas tentam enviar, com a saída para cada um. */
const DICAS: Record<string, string> = {
  heic: 'HEIC não suportado — converta para JPG',
  heif: 'HEIF não suportado — converta para JPG',
  webp: 'WEBP não suportado — converta para JPG ou PNG',
  gif: 'GIF não suportado — converta para PNG',
  tif: 'TIFF não suportado — converta para PDF ou PNG',
  tiff: 'TIFF não suportado — converta para PDF ou PNG',
  doc: 'Documento do Word não suportado — salve como PDF',
  docx: 'Documento do Word não suportado — salve como PDF',
  xls: 'Planilha não suportada — salve como PDF',
  xlsx: 'Planilha não suportada — salve como PDF',
  zip: 'Arquivo compactado não suportado — envie os comprovantes separadamente',
  rar: 'Arquivo compactado não suportado — envie os comprovantes separadamente',
}

/** ".PDF" → ".pdf"; sem extensão → "". Mesma regra do servidor (sufixo final). */
export function extensao(nome: string): string {
  const i = nome.lastIndexOf('.')
  return i > 0 ? nome.slice(i).toLowerCase() : ''
}

export function ehPdf(nome: string): boolean {
  return extensao(nome) === '.pdf'
}

/** Motivo para não enviar o arquivo, ou null se ele pode seguir. */
export function problemaDoArquivo(arquivo: { name: string; size: number }): string | null {
  const ext = extensao(arquivo.name)
  if (!EXTENSOES.has(ext)) {
    const sem = ext.slice(1)
    return (
      DICAS[sem] ??
      `${sem ? `${sem.toUpperCase()} não suportado` : 'Arquivo sem extensão'} — envie PDF, JPG ou PNG`
    )
  }
  if (arquivo.size === 0) return 'Arquivo vazio'
  if (arquivo.size > MAX_BYTES_ARQUIVO) {
    const limite = formatBytes(MAX_BYTES_ARQUIVO)
    const tamanho = formatBytes(arquivo.size)
    // Logo acima do limite, os dois arredondam igual ("10 MB — o limite é 10 MB").
    return tamanho === limite
      ? `Arquivo acima do limite de ${limite} por arquivo`
      : `Arquivo com ${tamanho} — o limite é ${limite} por arquivo`
  }
  return null
}
