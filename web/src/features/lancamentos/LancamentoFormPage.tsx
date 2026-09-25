import { zodResolver } from '@hookform/resolvers/zod'
import { useEffect, useState } from 'react'
import { Controller, useForm, useWatch } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { z } from 'zod'

import { MoneyInput } from '../../components/MoneyInput'
import { ApiError } from '../../lib/api'
import {
  FORMA_PAGAMENTO_LABELS,
  type FormaPagamento,
  type LancamentoOut,
  type SupplierRef,
} from '../../lib/types'
import { useAuth } from '../auth/AuthContext'
import { useCadastro } from '../cadastros/useCadastros'
import { SupplierAutocomplete } from '../fornecedores/SupplierAutocomplete'
import { UrgencyBadge } from './UrgencyBadge'
import { useExcluirLancamento, useLancamento, useSalvarLancamento } from './useLancamentos'

const opcional = z
  .string()
  .optional()
  .transform((v) => (v ? v : null))

const schema = z.object({
  supplier: z.custom<SupplierRef | null>().nullable(),
  descricao: z.string().max(500, 'Máximo de 500 caracteres').optional(),
  valor: z
    .string()
    .min(1, 'Informe o valor')
    .refine((v) => Number(v) > 0, 'O valor deve ser maior que zero'),
  data_emissao: z.string().min(1, 'Informe a data de emissão'),
  data_pagamento_prevista: opcional,
  forma_pagamento: opcional,
  linha_digitavel: opcional,
  categoria_id: opcional,
  projeto_id: opcional,
  centro_custo_id: opcional,
})

type FormInput = z.input<typeof schema>
type FormData = z.output<typeof schema>

function hojeISO(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function valoresDe(l?: LancamentoOut): FormInput {
  return {
    supplier: l?.supplier ?? null,
    descricao: l?.descricao ?? '',
    valor: l?.valor ?? '',
    data_emissao: l?.data_emissao ?? hojeISO(),
    data_pagamento_prevista: l?.data_pagamento_prevista ?? '',
    forma_pagamento: l?.forma_pagamento ?? '',
    linha_digitavel: l?.linha_digitavel ?? '',
    categoria_id: l?.categoria?.id ?? '',
    projeto_id: l?.projeto?.id ?? '',
    centro_custo_id: l?.centro_custo?.id ?? '',
  }
}

function mensagem(err: unknown): { texto: string; conflito: boolean } {
  if (err instanceof ApiError) {
    return { texto: err.problem?.detail ?? err.message, conflito: err.status === 412 }
  }
  return { texto: 'Erro inesperado ao salvar.', conflito: false }
}

export function LancamentoFormPage() {
  const { id } = useParams()
  const editando = !!id
  const navigate = useNavigate()
  const { user } = useAuth()
  const existente = useLancamento(id)
  const salvar = useSalvarLancamento()
  const excluir = useExcluirLancamento()
  const categorias = useCadastro('categorias')
  const projetos = useCadastro('projetos')
  const centros = useCadastro('centros-custo')
  const [erro, setErro] = useState<{ texto: string; conflito: boolean } | null>(null)

  const {
    control,
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormInput, unknown, FormData>({
    resolver: zodResolver(schema),
    defaultValues: valoresDe(),
  })

  useEffect(() => {
    if (existente.data) reset(valoresDe(existente.data))
  }, [existente.data, reset])

  const formaPagamento = useWatch({ control, name: 'forma_pagamento' })
  const lanc = existente.data
  const somenteLeitura = !!lanc && user?.role !== 'admin' && lanc.usuario.id !== user?.id
  const pago = lanc?.status === 'pago'

  const onSubmit = handleSubmit(async ({ supplier, descricao, ...resto }) => {
    setErro(null)
    const dados = {
      ...resto,
      descricao: descricao?.trim() ? descricao.trim() : null,
      supplier_id: supplier?.id ?? null,
      forma_pagamento: (resto.forma_pagamento as FormaPagamento | null) ?? null,
    }
    try {
      await salvar.mutateAsync({ id, version: lanc?.version, dados })
      navigate('/lancamentos')
    } catch (err) {
      setErro(mensagem(err))
    }
  })

  const onExcluir = async () => {
    if (!id || !window.confirm('Excluir este lançamento?')) return
    try {
      await excluir.mutateAsync(id)
      navigate('/lancamentos')
    } catch (err) {
      setErro(mensagem(err))
    }
  }

  if (editando && existente.isPending) return <p className="muted">Carregando…</p>
  if (editando && existente.error) {
    return (
      <>
        <h1>Lançamento</h1>
        <p className="form-error">{existente.error.message}</p>
        <Link to="/lancamentos">Voltar</Link>
      </>
    )
  }

  return (
    <>
      <div className="page-header">
        <h1>{editando ? 'Editar lançamento' : 'Novo lançamento'}</h1>
        {lanc && <UrgencyBadge lancamento={lanc} />}
      </div>
      {lanc && (
        <p className="muted">
          Criado por {lanc.usuario.nome} · versão {lanc.version}
        </p>
      )}

      <form className="card form-lancamento" onSubmit={onSubmit} noValidate>
        <fieldset disabled={somenteLeitura}>
          <div className="grid-2">
            <label className="span-2">
              Fornecedor
              <Controller
                control={control}
                name="supplier"
                render={({ field }) => (
                  <SupplierAutocomplete value={field.value ?? null} onChange={field.onChange} />
                )}
              />
            </label>

            <label className="span-2">
              Descrição
              <input {...register('descricao')} placeholder="Ex.: conta de energia de setembro" />
              {errors.descricao && <span className="field-error">{errors.descricao.message}</span>}
            </label>

            <label>
              Valor
              <Controller
                control={control}
                name="valor"
                render={({ field }) => (
                  <MoneyInput
                    value={field.value}
                    onChange={field.onChange}
                    onBlur={field.onBlur}
                    disabled={pago}
                    aria-invalid={!!errors.valor}
                  />
                )}
              />
              {errors.valor && <span className="field-error">{errors.valor.message}</span>}
            </label>

            <label>
              Forma de pagamento
              <select {...register('forma_pagamento')}>
                <option value="">—</option>
                {Object.entries(FORMA_PAGAMENTO_LABELS).map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Data de emissão
              <input
                type="date"
                {...register('data_emissao')}
                aria-invalid={!!errors.data_emissao}
              />
              {errors.data_emissao && (
                <span className="field-error">{errors.data_emissao.message}</span>
              )}
            </label>

            <label>
              Vencimento
              <input type="date" {...register('data_pagamento_prevista')} disabled={pago} />
            </label>

            {formaPagamento === 'boleto' && (
              <label className="span-2">
                Linha digitável
                <input
                  {...register('linha_digitavel')}
                  inputMode="numeric"
                  placeholder="00000.00000 00000.000000 00000.000000 0 00000000000000"
                />
              </label>
            )}

            <label>
              Categoria
              <select {...register('categoria_id')}>
                <option value="">—</option>
                {categorias.data?.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nome}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Projeto
              <select {...register('projeto_id')}>
                <option value="">—</option>
                {projetos.data?.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.nome}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Centro de custo
              <select {...register('centro_custo_id')}>
                <option value="">—</option>
                {centros.data?.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.codigo} — {c.nome}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </fieldset>

        {pago && (
          <p className="muted">Lançamento pago: valor e vencimento não podem ser alterados.</p>
        )}
        {somenteLeitura && (
          <p className="muted">Você pode visualizar, mas só o autor ou um administrador edita.</p>
        )}
        {erro && (
          <div role="alert" className="form-error">
            {erro.texto}{' '}
            {erro.conflito && (
              <button
                type="button"
                onClick={() => void existente.refetch().then(() => setErro(null))}
              >
                Recarregar
              </button>
            )}
          </div>
        )}

        <div className="actions">
          {!somenteLeitura && (
            <button type="submit" className="primary" disabled={isSubmitting}>
              {isSubmitting ? 'Salvando…' : 'Salvar'}
            </button>
          )}
          <Link to="/lancamentos" className="button">
            Cancelar
          </Link>
          {editando && !somenteLeitura && !pago && (
            <button type="button" className="perigo" onClick={() => void onExcluir()}>
              Excluir
            </button>
          )}
        </div>
      </form>
    </>
  )
}
