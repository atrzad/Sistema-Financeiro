import { describe, expect, it } from 'vitest'

import { extensao, problemaDoArquivo } from './regras'

const MB = 1024 * 1024

describe('regras de envio no navegador', () => {
  it('aceita PDF, JPG e PNG em qualquer caixa', () => {
    for (const name of ['boleto.pdf', 'CARNE.PDF', 'foto.jpg', 'foto.JPEG', 'nota.png']) {
      expect(problemaDoArquivo({ name, size: 1000 })).toBeNull()
    }
  })

  it('explica o que fazer com formatos comuns não suportados', () => {
    expect(problemaDoArquivo({ name: 'IMG_0001.HEIC', size: 1000 })).toBe(
      'HEIC não suportado — converta para JPG',
    )
    expect(problemaDoArquivo({ name: 'nota.docx', size: 1000 })).toBe(
      'Documento do Word não suportado — salve como PDF',
    )
    expect(problemaDoArquivo({ name: 'programa.exe', size: 1000 })).toBe(
      'EXE não suportado — envie PDF, JPG ou PNG',
    )
    expect(problemaDoArquivo({ name: 'sem_extensao', size: 1000 })).toBe(
      'Arquivo sem extensão — envie PDF, JPG ou PNG',
    )
  })

  it('recusa arquivo vazio ou acima de 10 MB', () => {
    expect(problemaDoArquivo({ name: 'a.pdf', size: 0 })).toBe('Arquivo vazio')
    expect(problemaDoArquivo({ name: 'a.pdf', size: 10 * MB })).toBeNull()
    expect(problemaDoArquivo({ name: 'a.pdf', size: 10 * MB + 1 })).toBe(
      'Arquivo acima do limite de 10 MB por arquivo',
    )
    expect(problemaDoArquivo({ name: 'a.pdf', size: 12.3 * MB })).toBe(
      'Arquivo com 12,3 MB — o limite é 10 MB por arquivo',
    )
  })

  it('usa só o sufixo final como extensão, como o servidor', () => {
    expect(extensao('boleto.pdf.exe')).toBe('.exe')
    expect(extensao('.pdf')).toBe('')
  })
})
