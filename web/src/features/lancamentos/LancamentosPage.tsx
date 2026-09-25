import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { formatBRL, formatDate } from '../../lib/format'
import { ABAS, useLancamentos, type Aba } from './useLancamentos'
import { UrgencyBadge } from './UrgencyBadge'

function abaDaUrl(valor: string | null): Aba {
  return ABAS.some((a) => a.id === valor) ? (valor as Aba) : 'todos'
}

export function LancamentosPage() {
  const [params, setParams] = useSearchParams()
  const aba = abaDaUrl(params.get('aba'))
  const navigate = useNavigate()
  const { data, error, isPending, fetchNextPage, hasNextPage, isFetchingNextPage } =
    useLancamentos(aba)
  const itens = data?.pages.flatMap((p) => p.items) ?? []

  return (
    <>
      <div className="page-header">
        <h1>Lançamentos</h1>
        <Link to="/lancamentos/novo" className="button primary">
          + Novo lançamento
        </Link>
      </div>

      <div className="tabs" role="tablist" aria-label="Filtrar por situação">
        {ABAS.map((a) => (
          <button
            key={a.id}
            role="tab"
            type="button"
            aria-selected={a.id === aba}
            className={a.id === aba ? 'tab ativo' : 'tab'}
            onClick={() => setParams(a.id === 'todos' ? {} : { aba: a.id })}
          >
            {a.label}
          </button>
        ))}
      </div>

      {isPending && <p className="muted">Carregando…</p>}
      {error && <p className="form-error">{error.message}</p>}
      {!isPending && itens.length === 0 && (
        <div className="card vazio">
          <p>Nenhum lançamento {aba === 'todos' ? 'cadastrado' : 'nesta situação'}.</p>
          {aba === 'todos' && <Link to="/lancamentos/novo">Cadastrar o primeiro</Link>}
        </div>
      )}

      {itens.length > 0 && (
        <section className="card table-card">
          <table className="tabela-lancamentos">
            <thead>
              <tr>
                <th>Fornecedor</th>
                <th>Descrição</th>
                <th>Categoria</th>
                <th>Vencimento</th>
                <th className="num">Valor</th>
                <th>Situação</th>
              </tr>
            </thead>
            <tbody>
              {itens.map((l) => (
                <tr
                  key={l.id}
                  className="clicavel"
                  tabIndex={0}
                  onClick={() => navigate(`/lancamentos/${l.id}`)}
                  onKeyDown={(e) => e.key === 'Enter' && navigate(`/lancamentos/${l.id}`)}
                >
                  <td data-label="Fornecedor">
                    {l.supplier?.nome_fantasia ?? <span className="muted">—</span>}
                  </td>
                  <td data-label="Descrição" className="truncar">
                    {l.descricao ?? <span className="muted">—</span>}
                  </td>
                  <td data-label="Categoria">{l.categoria?.nome ?? '—'}</td>
                  <td data-label="Vencimento">{formatDate(l.data_pagamento_prevista)}</td>
                  <td data-label="Valor" className="num">
                    {formatBRL(l.valor)}
                  </td>
                  <td data-label="Situação">
                    <UrgencyBadge lancamento={l} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {hasNextPage && (
            <div className="carregar-mais">
              <button
                type="button"
                onClick={() => void fetchNextPage()}
                disabled={isFetchingNextPage}
              >
                {isFetchingNextPage ? 'Carregando…' : 'Carregar mais'}
              </button>
            </div>
          )}
        </section>
      )}
    </>
  )
}
