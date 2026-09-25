interface Props {
  title: string
  sprint: string
}

/** Tela ainda não implementada — indica em qual sprint ela entra. */
export function PlaceholderPage({ title, sprint }: Props) {
  return (
    <>
      <h1>{title}</h1>
      <p className="muted">Disponível a partir da Sprint {sprint}.</p>
    </>
  )
}
