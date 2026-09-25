# Convenções do Projeto

[← README](../README.md)

## 1. Git

**Branching:** trunk-based com branches curtas a partir de `main`.

| Tipo | Padrão | Exemplo |
|------|--------|---------|
| Funcionalidade | `feat/sNN-descricao` | `feat/s03-presigned-urls` |
| Correção | `fix/sNN-descricao` | `fix/s05-confianca-cnpj` |
| Infra/tooling | `chore/descricao` | `chore/ci-cache-uv` |
| Documentação | `docs/descricao` | `docs/adr-0005` |

- `main` sempre implantável; merge via PR com CI verde (mesmo sendo dev solo — o PR é o registro da mudança).
- Squash merge; o título do PR vira a mensagem do commit.
- Tag por sprint concluída: `sprint-03`, e por release: `v0.1.0`.

**Commits:** [Conventional Commits](https://www.conventionalcommits.org/pt-br/), em português, no imperativo.

```
feat(upload): gerar presigned URL por arquivo do lote
fix(ocr): reprocessar somente o arquivo com falha
test(rls): garantir zero linhas sem tenant definido
```

Escopos sugeridos: `auth`, `rls`, `upload`, `ocr`, `revisao`, `faixas`, `pagamento`, `aprovacao`, `relatorio`, `dashboard`, `mobile`, `infra`, `ci`.

## 2. API REST

- Prefixo `/api/v1`. Recursos no plural, em português, `kebab-case` quando composto (`/centros-custo`).
- JSON em `snake_case`. Datas `YYYY-MM-DD`; timestamps ISO-8601 UTC. Valores monetários como **string decimal** (`"245.90"`) para evitar erro de ponto flutuante no cliente.
- Paginação por cursor: `?limit=50&cursor=<opaque>` → resposta `{ "items": [...], "next_cursor": "..." }`.
- Filtros por query string: `?status=pendente&supplier_id=...&vencimento_de=2026-10-01`.
- Erros no formato [RFC 9457 Problem Details](https://www.rfc-editor.org/rfc/rfc9457):

```json
{
  "type": "https://docs.app/erros/data-no-passado",
  "title": "Data de reagendamento inválida",
  "status": 422,
  "detail": "nova_data deve ser maior ou igual a hoje (2026-09-25).",
  "instance": "/api/v1/lancamentos/9b1.../pagamento"
}
```

- Operações não idempotentes com efeito financeiro aceitam header `Idempotency-Key` (UUID gerado pelo cliente).
- Concorrência de edição: `ETag`/`If-Match` baseado em `lancamentos.version` → `412 Precondition Failed` em conflito.
- OpenAPI gerado pelo FastAPI é a fonte de verdade; o cliente TypeScript do `web/` e `mobile/` é gerado a partir dele (`openapi-typescript`).

## 3. Código

### Backend (Python)
- Ruff (lint + format), mypy `--strict` em `domain/` e `services/`.
- Regras de negócio puras em `domain/`, sem I/O.
- Nada de SQL com f-string; sempre parâmetros bindados.
- `Decimal` para dinheiro; `datetime.date` para datas de negócio; relógio injetável (`Clock`) para testar "hoje".

### Frontend (TypeScript)
- ESLint + Prettier; `strict: true` no `tsconfig`.
- Estado de servidor com TanStack Query; formulários com React Hook Form + Zod.
- Componentes de tela em `web/src/features/<dominio>/`; componentes genéricos em `web/src/components/`.
- Formatação monetária e de data exclusivamente via `Intl` (`pt-BR`, `BRL`).

## 4. Testes

| Nível | Ferramenta | Meta |
|-------|------------|------|
| Unidade (domain) | pytest | ≥ 90% de cobertura em `domain/` |
| Integração (API + Postgres real) | pytest + testcontainers | Todo endpoint com caminho feliz + erro principal |
| Segurança de tenant | pytest | Todo endpoint novo entra na suíte cross-tenant |
| Frontend unidade | Vitest + Testing Library | Hooks e componentes com lógica |
| E2E | Playwright | Fluxos críticos: login, upload→revisão, pagar, aprovar, exportar |

Fixtures de OCR: pasta `backend/tests/fixtures/comprovantes/` com amostras reais **anonimizadas** (boletos, cupom térmico, NF-e, PDF multi-página).

## 5. Definition of Done (global)

Uma história só está pronta quando:

- [ ] Critérios de aceite atendidos e demonstráveis em ambiente local.
- [ ] Testes automatizados cobrindo o comportamento novo; CI verde.
- [ ] Endpoints novos incluídos na suíte de isolamento cross-tenant.
- [ ] Migração Alembic com `upgrade` e `downgrade` testados.
- [ ] OpenAPI atualizado e cliente TS regenerado.
- [ ] Sem segredos, logs com dados pessoais ou `TODO` sem issue vinculada.
- [ ] Documentação (`docs/`) atualizada quando houver mudança de arquitetura, modelo ou regra.

## 6. Estimativa

Pontos em Fibonacci (1, 2, 3, 5, 8). Referência: **1 ponto ≈ meio dia** de trabalho focado. Capacidade de sprint: **~20 pontos** (10 dias úteis, reservando ~20% para imprevistos, revisão e documentação). Histórias de 8 pontos devem ser quebradas antes de entrar na sprint.

## 7. Cerimônias (dev solo)

| Momento | Duração | Saída |
|---------|---------|-------|
| Planejamento (dia 1) | 1h | Sprint goal + histórias selecionadas |
| Checkpoint (dia 5) | 30 min | Replanejamento se > 30% atrasado |
| Review/demo (dia 10) | 30 min | Vídeo curto ou demo gravada do entregável |
| Retrospectiva (dia 10) | 30 min | 1 ação de melhoria registrada no arquivo da sprint |
