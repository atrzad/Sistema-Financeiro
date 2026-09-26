import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { formatBRL, formatDate } from '../../lib/format'
import { useCadastro } from '../cadastros/useCadastros'
import { TagChips } from '../tags/Tags'
import { ABAS, useLancamentos, type Aba } from './useLancamentos'
import { UrgencyBadge } from './UrgencyBadge'

function abaDaUrl(valor: string | null): Aba {
  return ABAS.some((a) => a.id === valor) ? (valor as Aba) : 'todos'
}

export function LancamentosPage() {
  const [params, setParams] = useSearchParams()
  const aba = abaDaUrl(params.get('aba'))
  const tagIds = params.getAll('tag')
  const navigate = useNavigate()
  const tags = useCadastro('tags')
  const { data, error, isPending, fetchNextPage, hasNextPage, isFetchingNextPage } = useLancamentos(
    aba,
    tagIds,
  )
  const itens = data?.pages.flatMap((p) => p.items) ?? []

  // Muda um filtro na URL preservando os demais (aba e tags).
  const mudarFiltros = (mudar: (p: URLSearchParams) => void) => {
    const novos = new URLSearchParams(params)
    mudar(novos)
    setParams(novos)
  }
  const alternarTag = (id: string) =>
    mudarFiltros((p) => {
      p.delete('tag')
      const proximas = tagIds.includes(id) ? tagIds.filter((t) => t !== id) : [...tagIds, id]
      proximas.forEach((t) => p.append('tag', t))
    })

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
            onClick={() =>
              mudarFiltros((p) => (a.id === 'todos' ? p.delete('aba') : p.set('aba', a.id)))
            }
          >
            {a.label}
          </button>
        ))}
      </div>

      {/* Com filtro ativo a linha sempre aparece: sem a lista de tags (erro, tag
          desativada), "Limpar tags" ainda precisa estar ao alcance. */}
      {((tags.data?.length ?? 0) > 0 || tagIds.length > 0) && (
        <div className="filtro-tags" role="group" aria-label="Filtrar por tag">
          <span className="rotulo" aria-hidden="true">
            Tags:
          </span>
          {tags.data?.map((t) => {
            const ativa = tagIds.includes(t.id)
            return (
              <button
                key={t.id}
                type="button"
                className={ativa ? 'chip chip-marcado' : 'chip'}
                aria-pressed={ativa}
                onClick={() => alternarTag(t.id)}
              >
                <span aria-hidden="true">{ativa ? '✓' : '+'}</span>
                {t.nome}
              </button>
            )
          })}
          {tagIds.length > 0 && (
            <button
              type="button"
              className="link"
              onClick={() => mudarFiltros((p) => p.delete('tag'))}
            >
              Limpar tags
            </button>
          )}
        </div>
      )}

      {isPending && <p className="muted">Carregando…</p>}
      {error && <p className="form-error">{error.message}</p>}
      {!isPending && itens.length === 0 && (
        <div className="card vazio">
          <p>
            {tagIds.length > 0
              ? 'Nenhum lançamento com as tags selecionadas.'
              : `Nenhum lançamento ${aba === 'todos' ? 'cadastrado' : 'nesta situação'}.`}
          </p>
          {aba === 'todos' && tagIds.length === 0 && (
            <Link to="/lancamentos/novo">Cadastrar o primeiro</Link>
          )}
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
                <th>Tags</th>
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
                  <td data-label="Tags" className="tags">
                    <TagChips tags={l.tags} />
                  </td>
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
