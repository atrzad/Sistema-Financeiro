import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

import { ApiError } from '../../lib/api'
import { ROLE_LABELS, type Role, type UserOut } from '../../lib/types'
import { useAuth } from '../auth/AuthContext'
import { useCreateUser, useUpdateUser, useUsers } from './useUsers'

const schema = z
  .object({
    nome: z.string().trim().min(2, 'Informe o nome'),
    email: z.string().trim().email('E-mail inválido'),
    senha: z.string().min(8, 'Mínimo de 8 caracteres'),
    role: z.enum(['admin', 'aprovador', 'colaborador']),
    nivel_aprovacao: z.coerce.number().int().min(0).max(2),
  })
  .refine((d) => d.role !== 'colaborador' || d.nivel_aprovacao === 0, {
    path: ['nivel_aprovacao'],
    message: 'Colaborador não aprova (use 0)',
  })
  .refine((d) => d.role !== 'aprovador' || d.nivel_aprovacao > 0, {
    path: ['nivel_aprovacao'],
    message: 'Aprovador precisa de nível 1 ou 2',
  })

type FormInput = z.input<typeof schema>
type FormData = z.output<typeof schema>

function erroDaApi(err: unknown): string | null {
  if (!err) return null
  return err instanceof ApiError ? err.message : 'Erro inesperado.'
}

function NovoUsuarioForm() {
  const create = useCreateUser()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormInput, unknown, FormData>({
    resolver: zodResolver(schema),
    defaultValues: { role: 'colaborador', nivel_aprovacao: 0 },
  })

  const onSubmit = handleSubmit(async (data) => {
    await create.mutateAsync(data)
    reset()
  })

  return (
    <form className="card user-form" onSubmit={onSubmit} noValidate aria-label="Novo usuário">
      <h2>Novo usuário</h2>
      <div className="grid-2">
        <label>
          Nome
          <input {...register('nome')} aria-invalid={!!errors.nome} />
          {errors.nome && <span className="field-error">{errors.nome.message}</span>}
        </label>
        <label>
          E-mail
          <input type="email" {...register('email')} aria-invalid={!!errors.email} />
          {errors.email && <span className="field-error">{errors.email.message}</span>}
        </label>
        <label>
          Senha inicial
          <input type="password" {...register('senha')} aria-invalid={!!errors.senha} />
          {errors.senha && <span className="field-error">{errors.senha.message}</span>}
        </label>
        <label>
          Perfil
          <select {...register('role')}>
            {(Object.keys(ROLE_LABELS) as Role[]).map((r) => (
              <option key={r} value={r}>
                {ROLE_LABELS[r]}
              </option>
            ))}
          </select>
        </label>
        <label>
          Nível de aprovação
          <select {...register('nivel_aprovacao')}>
            <option value={0}>0 — não aprova</option>
            <option value={1}>1 — primeiro nível</option>
            <option value={2}>2 — segundo nível (valores altos)</option>
          </select>
          {errors.nivel_aprovacao && (
            <span className="field-error">{errors.nivel_aprovacao.message}</span>
          )}
        </label>
      </div>
      {create.error && (
        <p role="alert" className="form-error">
          {erroDaApi(create.error)}
        </p>
      )}
      {create.isSuccess && <p className="form-ok">Usuário criado.</p>}
      <button type="submit" className="primary" disabled={create.isPending}>
        {create.isPending ? 'Salvando…' : 'Criar usuário'}
      </button>
    </form>
  )
}

function LinhaUsuario({ user, souEu }: { user: UserOut; souEu: boolean }) {
  const update = useUpdateUser()
  const [erro, setErro] = useState<string | null>(null)

  const alterar = async (data: Parameters<typeof update.mutateAsync>[0]) => {
    setErro(null)
    try {
      await update.mutateAsync(data)
    } catch (err) {
      setErro(erroDaApi(err))
    }
  }

  return (
    <tr className={user.ativo ? undefined : 'inativo'}>
      <td>
        {user.nome}
        {souEu && <span className="tag">você</span>}
        {erro && <div className="field-error">{erro}</div>}
      </td>
      <td>{user.email}</td>
      <td>
        <select
          aria-label={`Perfil de ${user.nome}`}
          value={user.role}
          disabled={souEu || update.isPending}
          onChange={(e) => {
            const role = e.target.value as Role
            void alterar({
              id: user.id,
              role,
              nivel_aprovacao: role === 'colaborador' ? 0 : Math.max(user.nivel_aprovacao, 1),
            })
          }}
        >
          {(Object.keys(ROLE_LABELS) as Role[]).map((r) => (
            <option key={r} value={r}>
              {ROLE_LABELS[r]}
            </option>
          ))}
        </select>
      </td>
      <td className="num">{user.nivel_aprovacao}</td>
      <td>{user.ultimo_login_em ? new Date(user.ultimo_login_em).toLocaleString('pt-BR') : '—'}</td>
      <td>
        <button
          type="button"
          disabled={souEu || update.isPending}
          onClick={() => void alterar({ id: user.id, ativo: !user.ativo })}
        >
          {user.ativo ? 'Desativar' : 'Reativar'}
        </button>
      </td>
    </tr>
  )
}

export function UsersPage() {
  const { user: me } = useAuth()
  const { data, isPending, error } = useUsers()

  return (
    <>
      <h1>Usuários</h1>
      <NovoUsuarioForm />
      <section className="card table-card">
        {isPending && <p className="muted">Carregando…</p>}
        {error && <p className="form-error">{erroDaApi(error)}</p>}
        {data && (
          <table>
            <thead>
              <tr>
                <th>Nome</th>
                <th>E-mail</th>
                <th>Perfil</th>
                <th className="num">Nível</th>
                <th>Último acesso</th>
                <th>Situação</th>
              </tr>
            </thead>
            <tbody>
              {data.map((u) => (
                <LinhaUsuario key={u.id} user={u} souEu={u.id === me?.id} />
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  )
}
