import { useFilaUpload } from './UploadContext'

/** Progresso no menu enquanto há arquivos subindo — visível de qualquer tela. */
export function IndicadorEnvio() {
  const { estado } = useFilaUpload()
  const doLote = estado.itens.filter((i) => i.comprovanteId)
  const subindo = doLote.some((i) => i.estado === 'na_fila' || i.estado === 'enviando')
  if (!subindo) return null
  const enviados = doLote.filter((i) => i.estado === 'enviado').length
  return (
    <span className="nav-badge" title={`${enviados} de ${doLote.length} arquivos enviados`}>
      {enviados}/{doLote.length}
    </span>
  )
}
