import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { z } from 'zod'

import { ApiError, NetworkError } from '../../lib/api'
import { useAuth } from './AuthContext'

const schema = z.object({
  tenant_slug: z
    .string()
    .trim()
    .min(1, 'Informe o código da empresa')
    .regex(/^[a-zA-Z0-9-]+$/, 'Use apenas letras, números e hífen'),
  email: z.string().trim().min(1, 'Informe o e-mail').email('E-mail inválido'),
  senha: z.string().min(1, 'Informe a senha'),
})

type FormData = z.infer<typeof schema>

function mensagemDeErro(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return 'Empresa, e-mail ou senha incorretos.'
    if (err.status === 429) return err.message
    return 'Não foi possível entrar. Tente novamente.'
  }
  if (err instanceof NetworkError) return 'Sem conexão com o servidor.'
  return 'Erro inesperado.'
}

export function LoginPage() {
  const { login, status } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const destino = (location.state as { from?: string } | null)?.from ?? '/'
  const [erro, setErro] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) })

  if (status === 'autenticado') return <Navigate to={destino} replace />

  const onSubmit = handleSubmit(async (data) => {
    setErro(null)
    try {
      await login({ ...data, tenant_slug: data.tenant_slug.toLowerCase() })
      navigate(destino, { replace: true })
    } catch (err) {
      setErro(mensagemDeErro(err))
    }
  })

  return (
    <main className="login-page">
      <form className="card login-card" onSubmit={onSubmit} noValidate>
        <h1>Prestação de Contas</h1>
        <p className="muted">Entre com os dados da sua empresa.</p>

        <label htmlFor="tenant_slug">Empresa</label>
        <input
          id="tenant_slug"
          autoComplete="organization"
          placeholder="ex.: acme"
          aria-invalid={!!errors.tenant_slug}
          {...register('tenant_slug')}
        />
        {errors.tenant_slug && <span className="field-error">{errors.tenant_slug.message}</span>}

        <label htmlFor="email">E-mail</label>
        <input
          id="email"
          type="email"
          autoComplete="username"
          aria-invalid={!!errors.email}
          {...register('email')}
        />
        {errors.email && <span className="field-error">{errors.email.message}</span>}

        <label htmlFor="senha">Senha</label>
        <input
          id="senha"
          type="password"
          autoComplete="current-password"
          aria-invalid={!!errors.senha}
          {...register('senha')}
        />
        {errors.senha && <span className="field-error">{errors.senha.message}</span>}

        {erro && (
          <p role="alert" className="form-error">
            {erro}
          </p>
        )}

        <button type="submit" className="primary" disabled={isSubmitting}>
          {isSubmitting ? 'Entrando…' : 'Entrar'}
        </button>
      </form>
    </main>
  )
}
