import { useState } from 'react'

import { ApiError } from '../../lib/api'
import { useCadastro, useSalvarCadastro, type TipoCadastro } from './useCadastros'

interface Item {
  id: string
  nome: string
  ativo: boolean
  codigo?: string
}

const TITULOS: Record<TipoCadastro, string> = {
  categorias: 'Categorias',
  tags: 'Tags (tipo de conta)',
  projetos: 'Projetos',
  'centros-custo': 'Centros de custo',
}

// Mesmos limites do backend (schemas/cadastros.py).
const MAX_NOME: Record<TipoCadastro, number> = {
  categorias: 100,
  tags: 50,
  projetos: 150,
  'centros-custo': 150,
}

function Lista({ tipo }: { tipo: TipoCadastro }) {
  const { data } = useCadastro(tipo, true)
  const salvar = useSalvarCadastro(tipo)
  const [nome, setNome] = useState('')
  const [codigo, setCodigo] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const comCodigo = tipo === 'centros-custo'

  const adicionar = async () => {
    setErro(null)
    try {
      await salvar.mutateAsync({ dados: comCodigo ? { nome, codigo } : { nome } })
      setNome('')
      setCodigo('')
    } catch (err) {
      setErro(err instanceof ApiError ? err.message : 'Erro ao salvar.')
    }
  }

  return (
    <section className="card cadastro" aria-labelledby={`t-${tipo}`}>
      <h2 id={`t-${tipo}`}>{TITULOS[tipo]}</h2>
      <ul className="cadastro-lista">
        {(data as Item[] | undefined)?.map((i) => (
          <li key={i.id} className={i.ativo ? undefined : 'inativo'}>
            <span>
              {i.codigo && <strong>{i.codigo} </strong>}
              {i.nome}
            </span>
            <button
              type="button"
              onClick={() => salvar.mutate({ id: i.id, dados: { ativo: !i.ativo } })}
            >
              {i.ativo ? 'Desativar' : 'Reativar'}
            </button>
          </li>
        ))}
      </ul>
      <form
        className="cadastro-novo"
        onSubmit={(e) => {
          e.preventDefault()
          void adicionar()
        }}
      >
        {comCodigo && (
          <input
            aria-label="Código"
            placeholder="Código"
            value={codigo}
            onChange={(e) => setCodigo(e.target.value)}
            className="codigo"
          />
        )}
        <input
          aria-label={`Novo item em ${TITULOS[tipo]}`}
          placeholder="Nome"
          maxLength={MAX_NOME[tipo]}
          value={nome}
          onChange={(e) => setNome(e.target.value)}
        />
        <button type="submit" disabled={nome.trim().length < 2 || (comCodigo && !codigo.trim())}>
          Adicionar
        </button>
      </form>
      {erro && <p className="form-error">{erro}</p>}
    </section>
  )
}

export function CadastrosPage() {
  return (
    <>
      <h1>Cadastros</h1>
      <p className="muted">
        Itens desativados deixam de aparecer nos formulários, mas continuam nos lançamentos antigos.
      </p>
      <div className="cadastros-grid">
        <Lista tipo="categorias" />
        <Lista tipo="tags" />
        <Lista tipo="projetos" />
        <Lista tipo="centros-custo" />
      </div>
    </>
  )
}
