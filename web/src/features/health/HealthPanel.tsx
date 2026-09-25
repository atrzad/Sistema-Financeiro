import { useHealth } from './useHealth'

const LABELS: Record<string, string> = {
  database: 'Banco de dados',
  redis: 'Fila (Redis)',
  storage: 'Armazenamento',
}

export function HealthPanel() {
  const { data, error, isPending, refetch, isFetching } = useHealth()

  return (
    <section className="card" aria-labelledby="health-title">
      <header className="card-header">
        <h2 id="health-title">Status do sistema</h2>
        <button type="button" onClick={() => refetch()} disabled={isFetching}>
          {isFetching ? 'Verificando…' : 'Verificar agora'}
        </button>
      </header>

      {isPending && <p className="muted">Consultando a API…</p>}

      {error && (
        <p role="alert" className="status-line status-error">
          API indisponível — {error.message}
        </p>
      )}

      {data && (
        <>
          <p className={`status-line status-${data.status}`}>
            {data.status === 'ok' ? 'Todos os componentes operando' : 'Há componentes com falha'}
            <span className="muted"> · ambiente {data.environment}</span>
          </p>
          <ul className="health-list">
            {Object.entries(data.components).map(([name, c]) => (
              <li key={name} className={`status-${c.status}`}>
                <span className="dot" aria-hidden="true" />
                <span className="health-name">{LABELS[name] ?? name}</span>
                <span className="health-value">
                  {c.status === 'ok'
                    ? `OK · ${c.latency_ms ?? '–'} ms`
                    : `Falha · ${c.detail ?? ''}`}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
