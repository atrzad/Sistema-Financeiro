# Sprint 07 — Pagamento de boletos e exportação para planilha

[← Sprint 06](sprint-06.md) · [Índice](README.md) · [Sprint 08 →](sprint-08.md)

| | |
|---|---|
| **Período** | 25/01 – 05/02/2027 |
| **Pontos** | 21 |
| **Fase do MVP** | Pagamento e prestação de contas |

## 1. Objetivo
Ao clicar em **Pagar**, o usuário registra "Paguei hoje" ou reagenda para outro dia em dois cliques, e cada mudança de data fica registrada em um histórico append-only, auditável e à prova de clique duplo. Além disso, qualquer listagem de contas do sistema pode ser baixada como planilha (XLSX ou CSV) com os mesmos filtros da tela.

## 2. Requisitos cobertos
RF09 · RF12 · Regra "Pagamento de boleto" · Regra "Datas" · Tela 5 · Fluxo da seção 9 do plano

## 3. Histórias de usuário

### H7.1 — "Paguei hoje" `3 pts`
**Como** colaborador, **quero** marcar um boleto como pago hoje **para** manter o controle atualizado sem digitar datas.
- **Quando** envio `POST /lancamentos/{id}/pagamento {"tipo": "pago_hoje"}`, **então** em uma transação: `status = 'pago'`, `data_pagamento_efetiva = hoje` (fuso de negócio), `version++`, e insere em `pagamento_eventos` com `data_anterior = data_pagamento_prevista`, `data_nova = hoje`.
- **Dado** que o vencimento já passou, **então** o evento é gravado como `pago_atrasado` (ADR 0004), mas a UX é a mesma.
- **Dado** um lançamento já pago ou rejeitado, **então** `409`.
- **Dado** um lançamento com `status_aprovacao = rejeitado`, **então** `409` — não se paga despesa rejeitada.
- **Então** opcionalmente aceita `comprovante_pagamento_id` (upload do comprovante de pagamento reaproveitando o fluxo da Sprint 03).

### H7.2 — "Selecionar outro dia" (reagendar) `3 pts`
- **Quando** envio `{"tipo": "reagendado", "nova_data": "2027-02-10"}`, **então** `data_pagamento_prevista = nova_data`, `status = 'reagendado'`, evento com data anterior e nova.
- **Dado** `nova_data < hoje`, **então** `422` ("A data deve ser hoje ou futura").
- **Dado** `nova_data` igual à data atual prevista, **então** `422` (reagendamento sem efeito não gera evento).
- **Então** reagendar várias vezes gera um evento por mudança — **nunca** sobrescreve sem rastro.
- **Então** aceita `observacao` opcional (ex.: "aguardando repasse do cliente").

### H7.3 — Idempotência e concorrência `2 pts`
- **Dado** o header `Idempotency-Key`, **quando** o mesmo request chega duas vezes (duplo clique, retry de rede), **então** a segunda resposta é idêntica à primeira e nenhum evento extra é criado (`UNIQUE (tenant_id, idempotency_key)`).
- **Então** o lançamento é bloqueado com `SELECT … FOR UPDATE` durante a operação; dois pagamentos simultâneos resultam em um sucesso e um `409`.

### H7.4 — Estorno de pagamento `2 pts`
**Como** aprovador, **quero** desfazer um pagamento marcado por engano **sem apagar o histórico**.
- **Quando** envio `POST /lancamentos/{id}/pagamento {"tipo": "estornado", "observacao": "..."}` (papel aprovador/admin), **então** `status` volta para `pendente`, `data_pagamento_efetiva = NULL`, e um evento `estornado` é gravado.
- **Dado** observação vazia ou menor que 10 caracteres, **então** `422`.
- **Dado** lançamento incluído em relatório **fechado** (Sprint 09), **então** `409`.

### H7.5 — Tela 5: modal de pagamento `3 pts`
- **Então** ao clicar **[Pagar]** na Tela 4, abre modal com fornecedor, valor, vencimento e linha digitável com botão **copiar** (para colar no app do banco).
- **Então** duas ações diretas: **[✔ Paguei hoje]** e **[📅 Selecionar outro dia]**; esta abre date picker que bloqueia datas passadas.
- **Então** **[Cancelar]** fecha sem efeito; `Esc` e foco preso no modal (acessibilidade).
- **Então** atualização otimista na lista com rollback em erro; toast "Pagamento registrado" com ação *Desfazer* por 5 s (que chama estorno — permitido ao próprio autor nesse intervalo).
- **Então** o cliente gera e envia `Idempotency-Key` por abertura de modal.

### H7.6 — Histórico de pagamento `2 pts`
- **Então** `GET /lancamentos/{id}/pagamentos` retorna eventos em ordem cronológica.
- **Então** a tela de detalhe do lançamento mostra linha do tempo: "Reagendado de 25/01 para 10/02 por Ana — *aguardando repasse*", "Pago em 09/02 por Ana".

### H7.7 — Lembretes de vencimento `3 pts`
- **Então** task diária (Celery beat, 08:00 America/Sao_Paulo) seleciona, por tenant, lançamentos não pagos que vencem em 3 dias e hoje.
- **Então** envia e-mail resumo por usuário (um e-mail com a lista, não um por boleto) via SMTP configurável (Mailpit em dev).
- **Então** o usuário pode desligar lembretes no perfil.

### H7.8 — Exportar tabelas para planilha (XLSX/CSV) `3 pts`
**Como** colaborador ou gestor, **quero** baixar os dados das contas numa planilha **para** analisar no Excel, conferir com o extrato ou enviar ao contador.
- **Então** existe o botão **Exportar ▾** (Excel `.xlsx` / CSV) nas telas: *Meus Boletos / Lançamentos* (Tela 4), *Fornecedores*, *Histórico de pagamentos* e *Dashboard* (dados dos gráficos do mês).
- **Então** a exportação usa **exatamente a mesma consulta da tela**: mesmos filtros (status, fornecedor, categoria, faixa, período), mesma ordenação e mesmas regras de visibilidade (colaborador exporta só os próprios lançamentos; aprovador/admin, os do tenant) — além do RLS.
- **Então** o XLSX tem três abas:
  - **Dados** — uma linha por registro; cabeçalho em negrito, congelado e com autofiltro; valores como **número** com formato `R$ #.##0,00`; datas como **data** (`dd/mm/aaaa`); CNPJ formatado; status em português (`Atrasado`, `Vence hoje`, `Pago`…); coluna com link para o comprovante (URL autenticada da aplicação, não presigned).
  - **Resumo** — totais por status e por faixa de valor usando **fórmulas** (`SUBTOTAL`/`SUMIFS` sobre a aba Dados), para continuarem corretos se o usuário filtrar ou editar a planilha.
  - **Informações** — empresa, usuário que exportou, data/hora da geração, filtros aplicados e quantidade de linhas.
- **Então** o CSV é UTF-8 com BOM, separador `;` e vírgula decimal (abre corretamente no Excel em pt-BR).
- **Então** o usuário pode escolher as colunas (`?colunas=fornecedor,valor,vencimento,status`); o padrão é o conjunto completo.
- **Então** o nome do arquivo segue `lancamentos_<slug-empresa>_<AAAA-MM-DD>.xlsx`.
- **Dado** um texto começando com `=`, `+`, `-`, `@`, tab ou CR (ex.: descrição ou nome de fornecedor digitado pelo usuário ou lido pelo OCR), **então** a célula é gravada como texto escapado — proteção contra *CSV/formula injection*.
- **Então** até **10.000 linhas** a exportação é síncrona e em streaming (openpyxl `write_only`, memória constante); acima disso a API responde `413` com orientação para refinar os filtros (a exportação assíncrona de grandes volumes chega na [Sprint 09](sprint-09.md)).
- **Então** toda exportação é registrada no `audit_log` (`acao = 'exportar'`, entidade, filtros, nº de linhas) — rastreabilidade de quem extraiu dados (LGPD).
- **Então** rate limit de 10 exportações por minuto por usuário.

## 4. Tarefas técnicas

**Dados**
- [ ] Migração `0007_pagamentos`: `pagamento_eventos` (com `estornado`, `observacao`, `idempotency_key`), RLS, `REVOKE UPDATE, DELETE`
- [ ] `users.lembretes_ativos BOOLEAN DEFAULT true`
- [ ] Incluir `'exportar'` no CHECK de `audit_log.acao`

**Backend**
- [ ] `domain/pagamento.py`: máquina de estados (`transicionar(status, tipo, hoje, nova_data) -> (novo_status, tipo_evento)`), validações
- [ ] `services/pagamento_service.py` com `FOR UPDATE` e idempotência
- [ ] Middleware/dependência genérica de `Idempotency-Key` (reutilizável em `/uploads/{id}/complete`)
- [ ] `workers/tasks/lembretes.py` + templates de e-mail (Jinja2)
- [ ] Mailpit no docker-compose
- [ ] `services/export/tabular.py`: motor genérico de exportação — recebe uma *query* + lista de `ColunaExport(chave, titulo, tipo: texto|moeda|data|numero|link, largura)` e gera XLSX (write_only, abas Dados/Resumo/Informações) ou CSV em streaming; sanitização contra formula injection; reutilizado nas Sprints 08 e 09
- [ ] Definições de colunas por recurso: `export/definicoes/lancamentos.py`, `fornecedores.py`, `pagamentos.py`, `dashboard.py`
- [ ] Endpoints `/export` retornando `StreamingResponse` com `Content-Disposition: attachment`

**Frontend**
- [ ] `features/pagamento/` — `PagamentoModal`, `useRegistrarPagamento` (otimista), `CopyLinhaDigitavel`
- [ ] `Timeline` de eventos no detalhe do lançamento
- [ ] Componente `ExportButton` reutilizável (formato, seleção de colunas, repassa os filtros atuais da URL, download via `blob`)

## 5. Contrato de API

```
POST /api/v1/lancamentos/{id}/pagamento
Idempotency-Key: 7c1e…

{ "tipo": "pago_hoje" }
{ "tipo": "reagendado", "nova_data": "2027-02-10", "observacao": "..." }
{ "tipo": "estornado", "observacao": "Marcado por engano" }
```

Resposta `200`:

```json
{
  "lancamento": { "id": "…", "status": "pago", "status_efetivo": "pago",
                  "data_pagamento_efetiva": "2027-01-28", "version": 5 },
  "evento": { "id": "…", "tipo_evento": "pago_hoje",
              "data_anterior": "2027-01-30", "data_nova": "2027-01-28" }
}
```

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/v1/lancamentos/{id}/pagamento` | Pagar / reagendar / estornar |
| GET | `/api/v1/lancamentos/{id}/pagamentos` | Histórico de eventos |
| PATCH | `/api/v1/me/preferencias` | Liga/desliga lembretes |
| GET | `/api/v1/lancamentos/export` | Planilha da lista de lançamentos (`?formato=xlsx\|csv&colunas=…` + mesmos filtros da listagem) |
| GET | `/api/v1/suppliers/export` | Planilha de fornecedores |
| GET | `/api/v1/pagamentos/export` | Histórico de pagamentos do período (`?de=&ate=`) |
| GET | `/api/v1/dashboard/export` | Dados do dashboard do mês (`?mes=`) |

Colunas padrão da exportação de lançamentos:

| Coluna | Tipo na planilha |
|--------|------------------|
| ID | texto (8 primeiros caracteres) |
| Fornecedor · CNPJ | texto |
| Categoria · Projeto · Centro de custo · Faixa de valor | texto |
| Descrição · Forma de pagamento · Linha digitável | texto |
| Valor | moeda (número) |
| Emissão · Vencimento · Pago em | data |
| Status · Situação de aprovação · Aprovado por | texto |
| Criado por · Criado em | texto · data/hora |
| Comprovante | link |

## 6. Estratégia de testes
- Unidade: tabela completa de transições (estado × tipo × data) da máquina de estados, com `Clock` fixo.
- Integração: idempotência (mesma chave 2x), concorrência (duas requisições paralelas com `asyncio.gather`), `UPDATE`/`DELETE` em `pagamento_eventos` como `app_api` falha.
- E2E: pagar hoje, reagendar, desfazer.
- Exportação: abrir o XLSX gerado com openpyxl e verificar tipos (valor é número, datas são datas), cabeçalho, filtros aplicados, fórmulas da aba Resumo; CSV lido de volta com `;` e acentuação correta; célula `=HYPERLINK(...)` vinda de descrição sai escapada; colaborador não exporta lançamentos de outro usuário; tenant B nunca aparece (suíte cross-tenant); 10.000 linhas geradas com memória estável.

## 7. Definition of Done específica
- [ ] Nenhum caminho de código altera datas de pagamento sem gerar evento (revisão + teste)
- [ ] `pagamento_eventos` comprovadamente append-only no banco
- [ ] Planilha exportada abre sem avisos no Excel, LibreOffice e Google Sheets, e os totais batem com a tela

## 8. Riscos e mitigação

| Risco | Mitigação |
|-------|-----------|
| "Hoje" diferente entre servidor (UTC) e usuário | `Clock` do fuso de negócio; teste às 23:30 de São Paulo (02:30 UTC do dia seguinte) |
| Planilha grande consumir memória da API | `write_only` + streaming; teto de 10.000 linhas síncronas |
| Dados exportados saem do controle do sistema | Registro no `audit_log`, respeito às permissões de visibilidade e aviso na UI |
| Usuários esperam pagamento real (integração bancária) | Fora do escopo do MVP; deixar explícito na UI ("registrar pagamento") e no roadmap pós-MVP |

## 9. Entregável / demo
Pagar hoje um boleto que vence hoje, reagendar outro duas vezes, dar duplo clique rápido em "Paguei hoje" (um único evento), estornar como aprovador e mostrar a linha do tempo completa. Por fim, filtrar "Atrasados" na lista, exportar para Excel e mostrar a planilha com valores somáveis, datas filtráveis e o resumo por faixa.

## 10. Retrospectiva
_Preencher ao final da sprint._
