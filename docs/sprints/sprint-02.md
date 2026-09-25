# Sprint 02 — Núcleo de domínio

[← Sprint 01](sprint-01.md) · [Índice](README.md) · [Sprint 03 →](sprint-03.md)

| | |
|---|---|
| **Período** | 02/11 – 13/11/2026 |
| **Pontos** | 20 |
| **Fase do MVP** | Núcleo · fecha o **Marco M1** |

## 1. Objetivo
Um colaborador consegue cadastrar fornecedores e lançar despesas manualmente pela web, vendo a lista ordenada por vencimento com status efetivo (atrasado / vence hoje) calculado corretamente.

## 2. Requisitos cobertos
Roadmap fase 1 ("CRUD manual") · base para RF03, RF05 · Tela 4 (versão simples) · [ADR 0004](../adr/0004-status-derivado-de-lancamento.md)

## 3. Histórias de usuário

### H2.1 — Cadastro de fornecedores `3 pts`
**Como** colaborador, **quero** cadastrar fornecedores com nome fantasia e CNPJ **para** reutilizá-los nos lançamentos.
- **Dado** um CNPJ com dígito verificador inválido, **então** recebo `422` com `detail` explicando.
- **Dado** um CNPJ já cadastrado no meu tenant, **então** recebo `409` com o `id` do existente.
- **Dado** o mesmo CNPJ em outro tenant, **então** o cadastro é permitido.
- **Quando** busco `GET /suppliers?q=padaria`, **então** a busca usa similaridade trigram e ordena por relevância.
- **Então** exclusão é lógica (`deleted_at`) e não quebra lançamentos existentes.

### H2.2 — Categorias, projetos e centros de custo `3 pts`
- **Então** admin pode criar/editar/desativar categorias, projetos e centros de custo; colaborador apenas lista.
- **Então** o seed cria categorias padrão (Alimentação, Transporte, Hospedagem, Utilidades, Material, Serviços, Outros).

### H2.3 — Lançamento manual `5 pts`
**Como** colaborador, **quero** registrar uma despesa manualmente **para** controlar pagamentos mesmo sem comprovante digital.
- **Dado** `valor <= 0` ou `data_emissao` ausente, **então** `422`.
- **Então** `usuario_id` e `tenant_id` vêm do token.
- **Então** `status` inicial é `pendente` e `status_aprovacao` é `rascunho`.
- **Quando** edito um lançamento com `If-Match` desatualizado, **então** recebo `412` (optimistic locking via `version`).
- **Então** a resposta sempre inclui `status_efetivo` e `dias_para_vencimento`, calculados por `domain/status.py` (mesma regra da view `v_lancamentos`).
- **Dado** um lançamento `pago`, **então** não posso editar `valor` nem `data_pagamento_prevista` por este endpoint (`409`).

### H2.4 — Listagem com filtros `2 pts`
- **Quando** chamo `GET /lancamentos`, **então** a ordenação padrão é `data_pagamento_prevista ASC NULLS LAST`.
- **Então** posso filtrar por `status_efetivo` (`pendente`, `atrasado`, `vence_hoje`, `pago`, `reagendado`), `supplier_id`, `categoria_id`, intervalo de vencimento.
- **Então** a paginação é por cursor (`vencimento`, `id`).
- **Então** o plano de execução usa `ix_lanc_vencimento` (verificado com `EXPLAIN` num teste com 10 mil linhas).

### H2.5 — Telas de lista e formulário `5 pts`
- **Então** `/lancamentos` mostra a lista (versão simples da Tela 4) com badges coloridos: 🔴 atrasado/vence hoje, 🟡 vence em até 7 dias, 🟢 pago.
- **Então** existem abas de filtro `Todos | Pendentes | Atrasados | Pagos` sincronizadas com a URL (`?status=`).
- **Então** o formulário de lançamento tem autocomplete de fornecedor (com opção "cadastrar novo" inline), máscara monetária BRL e date pickers.
- **Então** valores e datas são formatados com `Intl` (`pt-BR`).

### H2.6 — Cliente de API tipado `2 pts`
- **Então** `pnpm gen:api` gera `packages/api-client` a partir do `openapi.json` (`openapi-typescript` + `openapi-fetch`).
- **Então** o CI falha se o cliente gerado estiver desatualizado em relação ao OpenAPI.

## 4. Tarefas técnicas

**Dados**
- [ ] Migração `0003_dominio`: `suppliers`, `categorias`, `projetos`, `centros_custo`, `lancamentos`, view `v_lancamentos` (`security_invoker`), índices, RLS
- [ ] Trigger `set_updated_at` em todas as tabelas novas

**Backend**
- [ ] `domain/cnpj.py` (normalizar + validar DV), `domain/status.py` (`status_efetivo(status, prevista, hoje)`), `domain/clock.py`
- [ ] Repositórios e services: `SupplierService`, `LancamentoService`
- [ ] Routers `suppliers`, `categorias`, `projetos`, `centros-custo`, `lancamentos`
- [ ] Paginação por cursor genérica (`app/api/pagination.py`)

**Frontend**
- [ ] `features/lancamentos/` (ListaPage, FormPage, `useLancamentos`)
- [ ] `features/fornecedores/` (autocomplete + modal de cadastro rápido)
- [ ] Componentes `MoneyInput`, `DateInput`, `StatusBadge`

## 5. Contrato de API

| Método | Rota | Descrição |
|--------|------|-----------|
| GET/POST | `/api/v1/suppliers` | Busca (trigram) / cria |
| GET/PATCH/DELETE | `/api/v1/suppliers/{id}` | Detalhe / edita / exclusão lógica |
| GET/POST | `/api/v1/categorias`, `/projetos`, `/centros-custo` | Cadastros auxiliares |
| GET/POST | `/api/v1/lancamentos` | Lista com filtros / cria |
| GET/PATCH/DELETE | `/api/v1/lancamentos/{id}` | Detalhe / edita (`If-Match`) / exclusão lógica |

Exemplo de resposta de lançamento:

```json
{
  "id": "5f0c…",
  "supplier": { "id": "…", "nome_fantasia": "Energia Elétrica S.A." },
  "valor": "245.90",
  "data_emissao": "2026-09-10",
  "data_pagamento_prevista": "2026-09-25",
  "status": "pendente",
  "status_efetivo": "vence_hoje",
  "dias_para_vencimento": 0,
  "version": 3
}
```

## 6. Estratégia de testes
- Unidade: `cnpj.validar` (tabela de casos válidos/inválidos), `status_efetivo` (tabela da ADR 0004 com `Clock` fixo, incluindo virada de dia no fuso de São Paulo).
- Integração: CRUD completo, 409/412/422, busca trigram.
- Segurança: todos os endpoints novos adicionados à suíte cross-tenant.
- Frontend: `StatusBadge` e `MoneyInput` (Vitest); E2E criar lançamento → aparece na lista.

## 7. Definition of Done específica
- [ ] Regra de status idêntica em SQL (view) e Python (domain) — teste de propriedade comparando ambos para datas aleatórias
- [ ] **Marco M1** demonstrado: login → cadastrar fornecedor → lançar → ver na lista

## 8. Riscos e mitigação

| Risco | Mitigação |
|-------|-----------|
| Divergência entre status calculado em SQL e em Python | Teste de propriedade (Hypothesis) comparando os dois |
| Fuso horário: servidor em UTC, negócio em São Paulo | `Clock` retorna `date` em `America/Sao_Paulo`; view usa a função `hoje_negocio()` |

## 9. Entregável / demo
Criar três lançamentos (vencido, vence hoje, vence em 10 dias) e mostrar a lista ordenada, com badges corretos e filtros funcionando.

## 10. Retrospectiva
_Preencher ao final da sprint._
