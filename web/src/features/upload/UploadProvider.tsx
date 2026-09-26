import { useEffect, useState, type ReactNode } from 'react'

import { FilaUpload } from './filaUpload'
import { UploadContext } from './UploadContext'

interface Props {
  children: ReactNode
  /** Injeção para testes; por padrão, fila real (API + storage). */
  fila?: FilaUpload
}

/**
 * Mantém a fila de envio acima das rotas: o usuário pode ir a outra tela enquanto
 * os arquivos sobem e são validados (RNF01). Fechar a aba interromperia os envios
 * em curso — nesse caso o navegador pede confirmação.
 */
export function UploadProvider({ children, fila: injetada }: Props) {
  const [fila] = useState(() => injetada ?? new FilaUpload())

  useEffect(() => {
    const aoSair = (e: BeforeUnloadEvent) => {
      const { fase, itens } = fila.getSnapshot()
      const subindo = itens.some((i) => i.estado === 'na_fila' || i.estado === 'enviando')
      if (fase === 'criando' || subindo) e.preventDefault()
    }
    window.addEventListener('beforeunload', aoSair)
    return () => {
      window.removeEventListener('beforeunload', aoSair)
      fila.limpar() // saiu da área logada (logout): nada continua subindo
    }
  }, [fila])

  return <UploadContext.Provider value={fila}>{children}</UploadContext.Provider>
}
