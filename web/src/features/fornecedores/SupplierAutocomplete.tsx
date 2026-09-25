import { useEffect, useId, useState, type KeyboardEvent } from 'react'

import { ApiError } from '../../lib/api'
import { formatCNPJ } from '../../lib/format'
import type { SupplierRef } from '../../lib/types'
import { useBuscaFornecedores, useSalvarFornecedor } from './useFornecedores'

interface Props {
  value: SupplierRef | null
  onChange: (fornecedor: SupplierRef | null) => void
  invalid?: boolean
}

function useDebounced<T>(valor: T, ms = 250): T {
  const [atual, setAtual] = useState(valor)
  useEffect(() => {
    const t = setTimeout(() => setAtual(valor), ms)
    return () => clearTimeout(t)
  }, [valor, ms])
  return atual
}

/**
 * Combobox acessível: busca por similaridade na API; se não achar, permite
 * cadastrar o fornecedor ali mesmo (nome fantasia + CNPJ opcional).
 */
export function SupplierAutocomplete({ value, onChange, invalid }: Props) {
  const listId = useId()
  const [texto, setTexto] = useState(value?.nome_fantasia ?? '')
  const [aberto, setAberto] = useState(false)
  const [ativo, setAtivo] = useState(0)
  const [cadastrando, setCadastrando] = useState(false)
  const busca = useBuscaFornecedores(useDebounced(texto.trim()))
  const opcoes = busca.data ?? []

  // Sincroniza o texto quando um fornecedor é escolhido/carregado de fora. Ao
  // limpar (value = null enquanto o usuário digita), o texto digitado é preservado.
  const [ultimoId, setUltimoId] = useState(value?.id)
  if (value && value.id !== ultimoId) {
    setUltimoId(value.id)
    setTexto(value.nome_fantasia)
  }

  const escolher = (f: SupplierRef) => {
    onChange({ id: f.id, nome_fantasia: f.nome_fantasia, cnpj: f.cnpj })
    setAberto(false)
  }

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (!aberto && (e.key === 'ArrowDown' || e.key === 'Enter')) {
      setAberto(true)
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setAtivo((i) => Math.min(i + 1, opcoes.length))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setAtivo((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      const f = opcoes[ativo]
      if (f) escolher(f)
      else if (texto.trim()) setCadastrando(true)
    } else if (e.key === 'Escape') {
      setAberto(false)
    }
  }

  if (cadastrando) {
    return (
      <NovoFornecedor
        nomeInicial={texto.trim()}
        onCancelar={() => setCadastrando(false)}
        onCriado={(f) => {
          setCadastrando(false)
          escolher(f)
        }}
      />
    )
  }

  return (
    <div className="combobox">
      <input
        role="combobox"
        aria-label="Fornecedor"
        aria-expanded={aberto}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-invalid={invalid}
        placeholder="Busque pelo nome ou CNPJ"
        value={texto}
        onChange={(e) => {
          setTexto(e.target.value)
          setAberto(true)
          setAtivo(0)
          if (value) onChange(null)
        }}
        onFocus={() => setAberto(true)}
        onBlur={() => setTimeout(() => setAberto(false), 150)}
        onKeyDown={onKeyDown}
      />
      {aberto && (
        <ul id={listId} role="listbox" className="combobox-list">
          {opcoes.map((f, i) => (
            <li
              key={f.id}
              role="option"
              aria-selected={i === ativo}
              className={i === ativo ? 'ativo' : undefined}
              onMouseDown={() => escolher(f)}
            >
              <span>{f.nome_fantasia}</span>
              {f.cnpj && <span className="muted">{formatCNPJ(f.cnpj)}</span>}
            </li>
          ))}
          {texto.trim() && (
            <li
              role="option"
              aria-selected={ativo === opcoes.length}
              className={`combobox-novo ${ativo === opcoes.length ? 'ativo' : ''}`}
              onMouseDown={() => setCadastrando(true)}
            >
              + Cadastrar “{texto.trim()}”
            </li>
          )}
          {!texto.trim() && opcoes.length === 0 && (
            <li className="muted combobox-vazio">Nenhum fornecedor cadastrado ainda.</li>
          )}
        </ul>
      )}
    </div>
  )
}

function NovoFornecedor({
  nomeInicial,
  onCancelar,
  onCriado,
}: {
  nomeInicial: string
  onCancelar: () => void
  onCriado: (f: SupplierRef) => void
}) {
  const salvar = useSalvarFornecedor()
  const [nome, setNome] = useState(nomeInicial)
  const [cnpj, setCnpj] = useState('')
  const [erro, setErro] = useState<string | null>(null)

  const criar = async () => {
    setErro(null)
    try {
      const f = await salvar.mutateAsync({ dados: { nome_fantasia: nome, cnpj: cnpj || null } })
      onCriado(f)
    } catch (err) {
      if (err instanceof ApiError && err.status === 409 && err.problem) {
        // CNPJ já cadastrado: usa o existente em vez de duplicar.
        const existenteId = (err.body as { existente_id?: string }).existente_id
        if (existenteId) {
          onCriado({ id: existenteId, nome_fantasia: nome, cnpj: cnpj || null })
          return
        }
      }
      setErro(
        err instanceof ApiError
          ? (err.problem?.errors?.[0]?.erro ?? err.message)
          : 'Erro ao salvar fornecedor.',
      )
    }
  }

  return (
    <div className="inline-form" role="group" aria-label="Novo fornecedor">
      <label>
        Nome fantasia
        <input value={nome} onChange={(e) => setNome(e.target.value)} autoFocus />
      </label>
      <label>
        CNPJ (opcional)
        <input
          value={cnpj}
          onChange={(e) => setCnpj(e.target.value)}
          placeholder="00.000.000/0000-00"
        />
      </label>
      {erro && <span className="field-error">{erro}</span>}
      <div className="actions">
        <button
          type="button"
          className="primary"
          disabled={nome.trim().length < 2 || salvar.isPending}
          onClick={() => void criar()}
        >
          Cadastrar fornecedor
        </button>
        <button type="button" onClick={onCancelar}>
          Cancelar
        </button>
      </div>
    </div>
  )
}
