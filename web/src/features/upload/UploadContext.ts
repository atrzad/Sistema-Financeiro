import { createContext, useContext, useSyncExternalStore } from 'react'

import type { EstadoFila, FilaUpload } from './filaUpload'

export const UploadContext = createContext<FilaUpload | null>(null)

export function useFilaUpload(): { fila: FilaUpload; estado: EstadoFila } {
  const fila = useContext(UploadContext)
  if (!fila) throw new Error('useFilaUpload precisa estar dentro de <UploadProvider>')
  const estado = useSyncExternalStore(fila.subscribe, fila.getSnapshot)
  return { fila, estado }
}
