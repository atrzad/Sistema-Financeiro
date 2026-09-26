import type { TagOut } from '../../lib/types'

interface TagRef {
  id: string
  nome: string
}

/** Tags de um lançamento, só para leitura (listagem). */
export function TagChips({ tags }: { tags: TagRef[] }) {
  if (tags.length === 0) return <span className="muted">—</span>
  return (
    <ul className="chips" aria-label="Tags">
      {tags.map((t) => (
        <li key={t.id} className="chip">
          {t.nome}
        </li>
      ))}
    </ul>
  )
}

interface TagSelectorProps {
  opcoes: TagOut[]
  value: string[]
  onChange: (ids: string[]) => void
}

/**
 * Escolha de várias tags. Cada chip é uma caixa de seleção de verdade (escondida
 * visualmente), então funciona com teclado e leitor de tela; a marca ✓ indica a
 * seleção sem depender só da cor.
 */
export function TagSelector({ opcoes, value, onChange }: TagSelectorProps) {
  const alternar = (id: string) =>
    onChange(value.includes(id) ? value.filter((v) => v !== id) : [...value, id])

  return (
    <fieldset className="span-2 campo-tags">
      <legend>Tags</legend>
      {opcoes.length === 0 ? (
        <p className="muted">
          Nenhuma tag cadastrada. Um administrador pode criá-las em Cadastros.
        </p>
      ) : (
        <div className="chips">
          {opcoes.map((o) => {
            const marcada = value.includes(o.id)
            return (
              <label key={o.id} className={marcada ? 'chip chip-marcado' : 'chip'}>
                <input
                  type="checkbox"
                  className="sr-only"
                  checked={marcada}
                  onChange={() => alternar(o.id)}
                />
                <span aria-hidden="true">{marcada ? '✓' : '+'}</span>
                {o.nome}
                {/* O espaço fica fora do span: dentro dele, o nome acessível o descartaria. */}
                {!o.ativo && ' '}
                {!o.ativo && <span className="muted">(desativada)</span>}
              </label>
            )
          })}
        </div>
      )}
    </fieldset>
  )
}
