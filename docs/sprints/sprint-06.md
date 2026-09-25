# Sprint 06 — Organização automática e dashboard

[← Sprint 05](sprint-05.md) · [Índice](README.md) · [Sprint 07 →](sprint-07.md)

| | |
|---|---|
| **Período** | 11/01 – 22/01/2027 |
| **Pontos** | 21 |
| **Fase do MVP** | Organização automática · fecha o **Marco M3** |

## 1. Objetivo
Todo lançamento é classificado automaticamente em uma faixa de valor configurável pela empresa, a lista de boletos fica agrupável e ordenada por urgência, e o dashboard mostra a visão consolidada do mês.

## 2. Requisitos cobertos
RF03 · RF08 · Regra "Faixas de valor" · Tela 4 (completa) · Tela 7

## 3. Histórias de usuário

### H6.1 — Configuração de faixas de valor `3 pts`
**Como** admin, **quero** definir as faixas de valor da minha empresa **para** adequar a classificação e a exigência de aprovação à nossa realidade.
- **Então** o tenant novo recebe as faixas padrão: *Micro* (0–50), *Pequeno* (50–300), *Médio* (300–1.500), *Alto* (≥ 1.500, `exige_segundo_nivel = true`).
- **Dado** faixas que se sobrepõem, **então** o banco rejeita (`EXCLUDE USING gist` com `numrange '[)'`) e a API responde `422` com a faixa conflitante.
- **Dado** um "buraco" entre faixas (ex.: nada entre 300 e 350), **então** a API rejeita — a cobertura de 0 a ∞ deve ser contínua (validada em `domain/faixas.py`).
- **Então** a tela `/configuracoes/faixas` permite editar nome, limites, cor e flag de 2º nível, com pré-visualização da régua de faixas.
- **Então** a atualização das faixas é feita como substituição atômica do conjunto (`PUT /faixas-valor`), evitando estados intermediários sobrepostos.

### H6.2 — Classificação automática `3 pts`
- **Então** `faixa_valor_id` é recalculado sempre que `valor` muda (no service, dentro da mesma transação) — regra "recalculado sempre que o valor mudar".
- **Então** `nivel_aprovacao_exigido` = 2 se a faixa exige segundo nível, senão 1.
- **Dado** que o admin altera as faixas, **então** uma task `recalcular_faixas(tenant_id)` reclassifica em lotes de 1.000 os lançamentos **não aprovados e não pagos** (os já aprovados preservam a faixa histórica) e registra no `audit_log`.
- **Então** existe backfill para lançamentos criados nas sprints anteriores.

### H6.3 — Tela 4 completa: Meus Boletos `5 pts`
- **Então** ordenação padrão por vencimento ascendente; abas `Todos | Pendentes | Atrasados | Pagos` com contadores.
- **Então** seletor "Agrupar por": nenhum, faixa de valor, categoria, fornecedor, status — com subtotal por grupo.
- **Então** badges de urgência derivados de `status_efetivo`/`dias_para_vencimento`: 🔴 *vencido há N dias* / *vence hoje*, 🟡 *vence em N dias* (≤ 7), ⚪ *vence em DD/MM*, 🟢 *pago em DD/MM*.
- **Então** chip com a cor da faixa de valor em cada linha.
- **Então** botão **[Pagar]** visível em itens não pagos (ação implementada na Sprint 07).
- **Então** filtros e agrupamento persistem na URL; lista virtualizada para > 500 itens.
- **Então** layout responsivo (cartões no mobile, tabela no desktop).

### H6.4 — API de agregados `3 pts`
- **Então** `GET /dashboard/resumo?mes=2027-01` retorna: total do mês, total pendente, total atrasado, total pago, quantidade por status.
- **Então** `GET /dashboard/por-faixa`, `/dashboard/por-categoria`, `/dashboard/top-fornecedores?limit=10` (valor total e nº de lançamentos).
- **Então** consultas usam `v_lancamentos` e índices; tempo < 200 ms com 100 mil lançamentos no tenant (teste de performance com dados sintéticos).
- **Então** respostas são cacheadas em Redis por 60 s, invalidadas quando um lançamento do tenant muda.

### H6.5 — Tela 7: Dashboard `5 pts`
- **Então** cards de resumo: *Total do mês*, *Pendente*, *Atrasado* (vermelho, clicável → lista filtrada), *Pago*.
- **Então** gráfico de barras por faixa de valor (cores das faixas), rosca por categoria, ranking dos 10 fornecedores recorrentes.
- **Então** seletor de mês; comparação com mês anterior (%) nos cards.
- **Então** gráficos acessíveis (tabela alternativa, não dependem só de cor) — biblioteca Recharts.
- **Então** o dashboard é a tela inicial após login.

### H6.6 — Reorganização ao fim do lote `2 pts`
- **Então** ao concluir a revisão de um lote, o usuário é levado à Tela 4 com os lançamentos recém-criados destacados e já posicionados por vencimento (etapa "Organizando por vencimento" da Tela 2 concluída).

## 4. Tarefas técnicas

**Dados**
- [ ] Migração `0006_faixas`: `faixas_valor` com `EXCLUDE`, FK em `lancamentos`, seed de faixas padrão por tenant, backfill
- [ ] Índices para agregação: `(tenant_id, data_emissao)`, `(tenant_id, faixa_valor_id)`, `(tenant_id, categoria_id)`

**Backend**
- [ ] `domain/faixas.py`: `classificar(valor, faixas)`, `validar_cobertura(faixas)`
- [ ] `services/faixa_service.py`, task `recalcular_faixas`
- [ ] `api/v1/dashboard.py` + cache Redis com invalidação por tenant

**Frontend**
- [ ] `features/lancamentos/` — agrupamento, virtualização (`@tanstack/react-virtual`), `UrgencyBadge`, `FaixaChip`
- [ ] `features/dashboard/` — cards, gráficos, seletor de mês
- [ ] `features/configuracoes/FaixasPage`

## 5. Contrato de API

| Método | Rota | Papel | Descrição |
|--------|------|-------|-----------|
| GET | `/api/v1/faixas-valor` | todos | Lista faixas do tenant |
| PUT | `/api/v1/faixas-valor` | admin | Substitui o conjunto de faixas atomicamente |
| GET | `/api/v1/lancamentos?agrupar_por=faixa` | todos | Lista agrupada com subtotais |
| GET | `/api/v1/dashboard/resumo` | todos | Cards do mês |
| GET | `/api/v1/dashboard/por-faixa` · `/por-categoria` · `/top-fornecedores` | todos | Séries dos gráficos |

Visibilidade: colaborador vê apenas os próprios lançamentos no dashboard; aprovador e admin veem os do tenant inteiro.

## 6. Estratégia de testes
- Unidade: `classificar` nas fronteiras (49,99 / 50,00 / 1.499,99 / 1.500,00), `validar_cobertura` (sobreposição, buraco, faixa sem teto duplicada).
- Integração: alteração de faixas reclassifica apenas não aprovados/não pagos; `EXCLUDE` rejeita no banco.
- Performance: seed de 100 mil lançamentos, asserção de tempo dos agregados.
- E2E: mudar faixa "Alto" para ≥ 1.000 e ver lançamento de 1.200 mudar de chip.

## 7. Definition of Done específica
- [ ] Fronteiras de faixa com intervalo semiaberto `[min, max)` documentadas e testadas
- [ ] **Marco M3** demonstrado

## 8. Riscos e mitigação

| Risco | Mitigação |
|-------|-----------|
| Reclassificação em massa trava a tabela | Lotes de 1.000 com commit por lote, fora do request |
| Dashboard lento com crescimento | Cache + índices; materialized view mensal fica como evolução pós-MVP |

## 9. Entregável / demo
Admin redefine faixas; lista agrupada por faixa reflete a mudança; dashboard mostra cards e gráficos do mês com drill-down para "Atrasados".

## 10. Retrospectiva
_Preencher ao final da sprint._
