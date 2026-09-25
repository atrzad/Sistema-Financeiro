import { useAuth } from '../features/auth/AuthContext'
import { HealthPanel } from '../features/health/HealthPanel'

export function HomePage() {
  const { user } = useAuth()
  return (
    <>
      <h1>Olá, {user?.nome.split(' ')[0]}</h1>
      <HealthPanel />
    </>
  )
}
