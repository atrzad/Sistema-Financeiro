/**
 * Tipos da API gerados do OpenAPI (src/schema.d.ts — não editar à mão).
 * Regenerar: `make gen-api` na raiz do monorepo.
 */
import type { components, operations, paths } from './schema'

export type { components, operations, paths }

type S = components['schemas']

export type Me = S['Me']
export type TenantInfo = S['TenantInfo']
export type TokenResponse = S['TokenResponse']
export type Role = Me['role']

export type UserOut = S['UserOut']
export type UserCreate = S['UserCreate']
export type UserUpdate = S['UserUpdate']

export type SupplierOut = S['SupplierOut']
export type SupplierIn = S['SupplierIn']
export type SupplierRef = S['SupplierRef']

export type CategoriaOut = S['CategoriaOut']
export type ProjetoOut = S['ProjetoOut']
export type CentroCustoOut = S['CentroCustoOut']
export type TagOut = S['TagOut']

export type LancamentoOut = S['LancamentoOut']
export type LancamentoIn = S['LancamentoIn']
export type LancamentoUpdate = S['LancamentoUpdate']
export type LancamentoPage = S['LancamentoPage']
export type StatusEfetivo = LancamentoOut['status_efetivo']
export type FormaPagamento = NonNullable<LancamentoOut['forma_pagamento']>

export type NovoLote = S['NovoLote']
export type ArquivoDeclarado = S['ArquivoDeclarado']
export type LoteCriado = S['LoteCriado']
export type UploadInstrucao = S['UploadInstrucao']
export type Confirmacao = S['Confirmacao']
export type LoteStatus = S['LoteStatus']
export type ItemStatus = S['ItemStatus']
export type StatusProcessamento = ItemStatus['status']

export type HealthReport = S['HealthReport']
