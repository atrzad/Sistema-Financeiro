# ADR 0004 — Status "atrasado" e "vence hoje" são derivados

- **Status:** aceito
- **Data:** 2026-09-25

## Contexto
O plano original afirma que o status (pago/pendente/atrasado) "é derivado comparando a data prevista com a data atual — nunca fixo", mas o schema tem `status` com o valor `'atrasado'` armazenado. Armazenar `atrasado` exige um job diário para atualizar linhas e cria janelas de inconsistência (virada de dia, fuso, job falho).

## Decisão
- A coluna `lancamentos.status` guarda apenas estados resultantes de **ações do usuário**: `pendente`, `reagendado`, `pago`, `rejeitado`.
- `status_efetivo` é calculado na view `v_lancamentos` (e espelhado em `domain/status.py` para uso em Python):

| status armazenado | condição | status_efetivo |
|-------------------|----------|----------------|
| `pago` / `rejeitado` | — | igual |
| `pendente` / `reagendado` | `data_pagamento_prevista < hoje` | `atrasado` |
| `pendente` / `reagendado` | `data_pagamento_prevista = hoje` | `vence_hoje` |
| `pendente` / `reagendado` | caso contrário | igual |

- Pagamento feito após o vencimento grava evento `pago_atrasado` (em vez de `pago_hoje`) em `pagamento_eventos`, preservando a informação para relatórios.
- "Hoje" é calculado no fuso `America/Sao_Paulo` e injetado via `Clock` para testes.

## Consequências
- (+) Nenhum job para manter status consistente; zero divergência.
- (+) Filtros "Atrasados" viram predicados sobre data, indexáveis por `(tenant_id, data_pagamento_prevista)`.
- (−) Toda leitura de listagem deve usar a view (ou a função de domínio), não a tabela crua.
