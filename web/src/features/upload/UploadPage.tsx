import { useRef, useState, type DragEvent } from 'react'

import { formatBytes } from '../../lib/format'
import {
  itensExibidos,
  resumir,
  type EstadoExibido,
  type FilaUpload,
  type ItemExibido,
} from './filaUpload'
import { ACCEPT, MAX_ARQUIVOS, MAX_BYTES_ARQUIVO, MAX_BYTES_LOTE } from './regras'
import { useFilaUpload } from './UploadContext'
import { useLoteStatus } from './useLoteStatus'

const ROTULOS: Record<EstadoExibido, string> = {
  selecionado: 'pronto para enviar',
  invalido: 'não será enviado',
  na_fila: 'na fila',
  enviando: 'enviando',
  validando: 'validando',
  processando_ocr: 'processando OCR',
  aguardando_revisao: 'aguardando revisão',
  concluido: 'concluído',
  erro: 'erro',
  cancelado: 'cancelado',
}

const SELOS: Partial<Record<EstadoExibido, string>> = {
  enviando: 'badge-info',
  validando: 'badge-info',
  processando_ocr: 'badge-info',
  aguardando_revisao: 'badge-ok',
  concluido: 'badge-ok',
  erro: 'badge-critico',
  invalido: 'badge-critico',
}

function AreaDeSoltar({ onArquivos }: { onArquivos: (arquivos: File[]) => void }) {
  const input = useRef<HTMLInputElement>(null)
  const [arrastando, setArrastando] = useState(false)

  const soltar = (e: DragEvent) => {
    e.preventDefault()
    setArrastando(false)
    onArquivos([...e.dataTransfer.files])
  }

  return (
    <div
      className={arrastando ? 'dropzone arrastando' : 'dropzone'}
      onDragOver={(e) => {
        e.preventDefault()
        setArrastando(true)
      }}
      onDragLeave={(e) => {
        // Ignora a saída para um elemento de dentro da própria área.
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setArrastando(false)
      }}
      onDrop={soltar}
    >
      <p>Arraste os comprovantes para cá ou</p>
      <button type="button" className="primary" onClick={() => input.current?.click()}>
        Selecionar arquivos
      </button>
      <input
        ref={input}
        type="file"
        multiple
        accept={ACCEPT}
        className="sr-only"
        tabIndex={-1}
        aria-label="Selecionar arquivos"
        onChange={(e) => {
          onArquivos([...(e.target.files ?? [])])
          e.target.value = '' // permite escolher o mesmo arquivo de novo depois de removê-lo
        }}
      />
      <p className="muted">
        PDF, JPG ou PNG · até {formatBytes(MAX_BYTES_ARQUIVO)} por arquivo ·{' '}
        {formatBytes(MAX_BYTES_LOTE)} no total
      </p>
    </div>
  )
}

function ItemDaFila({
  linha,
  fila,
  selecao,
}: {
  linha: ItemExibido
  fila: FilaUpload
  selecao: boolean
}) {
  const { item, estado, erro, paginas, duplicado, podeTentarNovamente } = linha
  const pct = Math.round(item.progresso * 100)
  const mostraBarra = ['na_fila', 'enviando'].includes(item.estado) || item.estado === 'enviado'

  return (
    <li className="item-upload">
      <div className="item-miniatura" aria-hidden="true">
        {item.preview ? <img src={item.preview} alt="" /> : <span className="icone-pdf">PDF</span>}
      </div>
      <div className="item-info">
        <span className="item-nome" title={item.nome}>
          {item.nome}
        </span>
        <span className="muted">
          {formatBytes(item.tamanho)}
          {paginas !== null && item.pdf && ` · ${paginas} ${paginas === 1 ? 'página' : 'páginas'}`}
        </span>
        {mostraBarra && (
          <progress value={item.progresso} max={1} aria-label={`Envio de ${item.nome}`} />
        )}
        {erro && <span className="field-error">{erro}</span>}
      </div>
      <div className="item-estado">
        <span className={`badge ${SELOS[estado] ?? 'badge-neutro'}`}>
          {ROTULOS[estado]}
          {estado === 'enviando' && ` ${pct}%`}
        </span>
        {duplicado && (
          <span className="badge badge-alerta" title="Já existe um comprovante idêntico na empresa">
            possível duplicado
          </span>
        )}
      </div>
      <div className="item-acoes">
        {selecao && (
          <button
            type="button"
            aria-label={`Remover ${item.nome}`}
            onClick={() => fila.remover(item.id)}
          >
            Remover
          </button>
        )}
        {podeTentarNovamente && (
          <button
            type="button"
            aria-label={`Tentar novamente ${item.nome}`}
            onClick={() => void fila.tentarNovamente(item.id)}
          >
            Tentar novamente
          </button>
        )}
      </div>
    </li>
  )
}

export function UploadPage() {
  const { fila, estado } = useFilaUpload()
  const selecao = estado.fase === 'selecao'
  // Consulta o servidor só enquanto houver arquivo subindo ou sendo validado.
  const { data: servidor } = useLoteStatus(
    estado.batchId,
    (dados) => resumir(estado, itensExibidos(estado, dados)).emAndamento > 0,
  )
  const linhas = itensExibidos(estado, servidor)
  const resumo = resumir(estado, linhas)

  const excedeLote = resumo.bytesSelecionados > MAX_BYTES_LOTE
  const podeContinuar = selecao && resumo.selecionados > 0 && !excedeLote

  return (
    <>
      <div className="page-header">
        <h1>
          Anexar comprovantes ({resumo.selecionados}/{MAX_ARQUIVOS})
        </h1>
      </div>

      {selecao && resumo.selecionados < MAX_ARQUIVOS && (
        <AreaDeSoltar onArquivos={fila.adicionar} />
      )}

      {estado.aviso && (
        <p className="form-error" role="alert">
          {estado.aviso}
        </p>
      )}
      {excedeLote && (
        <p className="form-error" role="alert">
          Os arquivos somam {formatBytes(resumo.bytesSelecionados)} — o limite é{' '}
          {formatBytes(MAX_BYTES_LOTE)} por envio. Remova algum para continuar.
        </p>
      )}

      {linhas.length > 0 && (
        <ul className="fila-upload card" aria-label="Arquivos">
          {linhas.map((linha) => (
            <ItemDaFila key={linha.item.id} linha={linha} fila={fila} selecao={selecao} />
          ))}
        </ul>
      )}

      {!selecao && (
        <div className="progresso-geral">
          <p>
            Progresso geral: <strong>{resumo.processados}</strong> de {resumo.total} processados
          </p>
          <progress
            value={resumo.processados}
            max={Math.max(resumo.total, 1)}
            aria-label="Progresso geral"
          />
        </div>
      )}

      <div className="actions acoes-upload">
        {!resumo.finalizado && linhas.length > 0 && (
          <button type="button" onClick={fila.cancelarTudo}>
            Cancelar tudo
          </button>
        )}
        {selecao && (
          <button
            type="button"
            className="primary"
            disabled={!podeContinuar}
            onClick={() => void fila.iniciar()}
          >
            Continuar
          </button>
        )}
        {estado.fase === 'criando' && (
          <button type="button" className="primary" disabled>
            Preparando o envio…
          </button>
        )}
        {resumo.finalizado && (
          <button type="button" className="primary" onClick={fila.limpar}>
            Enviar mais comprovantes
          </button>
        )}
      </div>

      {estado.fase === 'envio' && resumo.enviandoDoNavegador && (
        <p className="muted">
          Você pode usar outras telas do sistema enquanto os arquivos são enviados e validados — só
          não feche esta aba até o envio terminar.
        </p>
      )}
    </>
  )
}
