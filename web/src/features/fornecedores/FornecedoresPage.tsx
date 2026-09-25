import { useState } from 'react'

import { ApiError } from '../../lib/api'
import type { SupplierOut } from '../../lib/types'
import { useAuth } from '../auth/AuthContext'
import { useBuscaFornecedores, useExcluirFornecedor, useSalvarFornecedor } from './useFornecedores'

function erroDe(err: unknown): string {
  if (err instanceof ApiError) return err.problem?.errors?.[0]?.erro ?? err.message
  return 'Erro inesperado.'
}

function FornecedorForm({ inicial, onFim }: { inicial?: SupplierOut; onFim: () => void }) {
  const salvar = useSalvarFornecedor()
  const [nome, setNome] = useState(inicial?.nome_fantasia ?? '')
  const [razao, setRazao] = useState(inicial?.razao_social ?? '')
  const [cnpj, setCnpj] = useState(inicial?.cnpj_formatado ?? '')
  const [erro, setErro] = useState<string | null>(null)

  const enviar = async () => {
    setErro(null)
    try {
      await salvar.mutateAsync({
        id: inicial?.id,
        dados: { nome_fantasia: nome, razao_social: razao || null, cnpj: cnpj || null },
      })
      onFim()
    } catch (err) {
      setErro(erroDe(err))
    }
  }

  return (
    <div className="card inline-form" role="group" aria-label="Dados do fornecedor">
      <div className="grid-2">
        <label>
          Nome fantasia
          <input value={nome} onChange={(e) => setNome(e.target.value)} autoFocus />
        </label>
        <label>
          CNPJ
          <input value={cnpj} onChange={(e) => setCnpj(e.target.value)} placeholder="opcional" />
        </label>
        <label className="span-2">
          Razão social
          <input value={razao} onChange={(e) => setRazao(e.target.value)} placeholder="opcional" />
        </label>
      </div>
      {erro && <p className="form-error">{erro}</p>}
      <div className="actions">
        <button
          type="button"
          className="primary"
          disabled={nome.trim().length < 2 || salvar.isPending}
          onClick={() => void enviar()}
        >
          Salvar
        </button>
        <button type="button" onClick={onFim}>
          Cancelar
        </button>
      </div>
    </div>
  )
}

export function FornecedoresPage() {
  const { user } = useAuth()
  const [q, setQ] = useState('')
  const [editando, setEditando] = useState<SupplierOut | 'novo' | null>(null)
  const busca = useBuscaFornecedores(q.trim())
  const excluir = useExcluirFornecedor()

  return (
    <>
      <div className="page-header">
        <h1>Fornecedores</h1>
        <button type="button" className="primary" onClick={() => setEditando('novo')}>
          + Novo fornecedor
        </button>
      </div>

      {editando && (
        <FornecedorForm
          key={editando === 'novo' ? 'novo' : editando.id}
          inicial={editando === 'novo' ? undefined : editando}
          onFim={() => setEditando(null)}
        />
      )}

      <input
        className="busca"
        type="search"
        placeholder="Buscar por nome ou CNPJ…"
        aria-label="Buscar fornecedores"
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />

      <section className="card table-card">
        {busca.data?.length === 0 && <p className="muted vazio">Nenhum fornecedor encontrado.</p>}
        {!!busca.data?.length && (
          <table>
            <thead>
              <tr>
                <th>Nome fantasia</th>
                <th>Razão social</th>
                <th>CNPJ</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {busca.data.map((s) => (
                <tr key={s.id}>
                  <td>{s.nome_fantasia}</td>
                  <td>{s.razao_social ?? '—'}</td>
                  <td>{s.cnpj_formatado ?? '—'}</td>
                  <td className="acoes">
                    <button type="button" onClick={() => setEditando(s)}>
                      Editar
                    </button>
                    {user?.role === 'admin' && (
                      <button
                        type="button"
                        className="perigo"
                        onClick={() => {
                          if (window.confirm(`Excluir ${s.nome_fantasia}?`)) excluir.mutate(s.id)
                        }}
                      >
                        Excluir
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  )
}
