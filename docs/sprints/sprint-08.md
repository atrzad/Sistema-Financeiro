# Sprint 08 — Aprovação multinível e auditoria

[← Sprint 07](sprint-07.md) · [Índice](README.md) · [Sprint 09 →](sprint-09.md)

| | |
|---|---|
| **Período** | 08/02 – 19/02/2027 |
| **Pontos** | 20 |
| **Fase do MVP** | Pagamento e prestação de contas |

## 1. Objetivo
Lançamentos passam por aprovação do gestor — com segundo nível obrigatório para a faixa "Alto" — e toda a vida do lançamento (criação, correções de OCR, edições, aprovações, pagamentos) fica visível numa trilha de auditoria única.

## 2. Requisitos cobertos
RF06 · Regra "Aprovação por faixa" · Regra "auditoria completa (quem aprovou, quando, edições pós-OCR)" · Tela 8

## 3. Histórias de usuário

### H8.1 — Enviar para aprovação `2 pts`
- **Então** lançamentos criados pela revisão de OCR já nascem `aguardando`; lançamentos manuais nascem `rascunho` e o colaborador envia com `POST /lancamentos/{id}/enviar-aprovacao`.
- **Dado** um lançamento sem comprovante anexado, **então** o envio é permitido, mas marcado com flag `sem_comprovante` visível ao aprovador.
- **Então** lançamentos `aguardando` ou `aprovado` não podem ter `valor`, fornecedor ou datas de emissão editados pelo colaborador (`409`); para editar, o aprovador precisa devolver (rejeitar).

### H8.2 — Fila do aprovador `3 pts`
- **Quando** o aprovador chama `GET /aprovacoes/pendentes`, **então** recebe lançamentos `aguardando` cujo **próximo nível exigido** ≤ `users.nivel_aprovacao`, ordenados por vencimento (o que vence antes aparece primeiro).
- **Então** cada item traz: colaborador, fornecedor, valor, faixa, vencimento, categoria/projeto/centro de custo, miniatura do comprovante, flags (`sem_comprovante`, `possivel_duplicado`, `ocr_corrigido`) e aprovações anteriores.
- **Então** filtros por colaborador, faixa, projeto e intervalo de vencimento.

### H8.3 — Aprovar e rejeitar `5 pts`
**Como** aprovador, **quero** aprovar ou rejeitar despesas com justificativa **para** controlar os gastos da empresa.
- **Quando** aprovo, **então** grava em `aprovacoes` (`nivel`, `decisao = aprovado`, `aprovador_id`, timestamp).
- **Dado** `nivel_aprovacao_exigido = 1`, **então** a aprovação de nível 1 finaliza: `status_aprovacao = aprovado`, `aprovado_por`, `aprovado_em`.
- **Dado** `nivel_aprovacao_exigido = 2` (faixa "Alto"), **então** após o nível 1 o lançamento continua `aguardando` e aparece apenas para aprovadores de nível 2; a aprovação final só ocorre após o nível 2.
- **Quando** rejeito, **então** a justificativa é **obrigatória** (≥ 10 caracteres — `422` caso contrário; constraint também no banco), `status_aprovacao = rejeitado`, e o colaborador é notificado por e-mail.
- **Então** o colaborador pode corrigir um lançamento rejeitado e reenviar — o histórico de aprovações anteriores é preservado.
- **Então** aprovação em lote: `POST /aprovacoes/lote` com até 50 IDs (apenas aprovar; rejeição é individual por exigir justificativa).
- **Dado** que o valor de um lançamento aprovado muda e ele troca de faixa, **então** a aprovação é invalidada e ele volta para `aguardando` (registrado no `audit_log`).

### H8.4 — Segregação de funções `2 pts`
- **Dado** que sou o autor do lançamento, **então** não posso aprová-lo (`403`), mesmo sendo aprovador ou admin.
- **Dado** que aprovei o nível 1, **então** não posso aprovar o nível 2 do mesmo lançamento.
- **Dado** um tenant com apenas um aprovador de nível 2, **então** o admin é alertado na tela de usuários (risco de gargalo).

### H8.5 — Tela 8: aprovação `5 pts`
- **Então** lista de pendências com seleção múltipla e botão *Aprovar selecionados*.
- **Então** painel de detalhe com visualizador do comprovante (reusa `DocumentViewer` da Sprint 05), dados do lançamento, correções de OCR destacadas ("valor alterado de R$ 254,90 para R$ 245,90") e histórico.
- **Então** botões **Aprovar** e **Rejeitar**; rejeitar abre campo de justificativa obrigatório com contador de caracteres.
- **Então** atalhos `A` (aprovar) / `R` (rejeitar) / `J`/`K` (próximo/anterior).
- **Então** o colaborador vê o status de aprovação e o motivo da rejeição na Tela 4 e no detalhe.

### H8.6 — Trilha de auditoria unificada `3 pts`
**Como** auditor/admin, **quero** ver tudo o que aconteceu com um lançamento **para** prestar contas com segurança.
- **Então** todas as mutações de lançamento (criar, editar campo a campo, excluir, reclassificar faixa) passam por `services/audit.py`.
- **Então** `GET /lancamentos/{id}/historico` agrega `audit_log` + `pagamento_eventos` + `aprovacoes` numa linha do tempo única, ordenada, com autor.
- **Então** `aprovacoes` e `audit_log` são append-only no banco.
- **Então** `GET /auditoria?entidade=&usuario_id=&de=&ate=` (admin) permite pesquisa ampla, com exportação XLSX/CSV pelo motor de exportação da [Sprint 07](sprint-07.md) (`GET /auditoria/export`).
- **Então** a fila de aprovação também pode ser exportada (`GET /aprovacoes/export`) com as colunas da Tela 8 e o histórico de decisões — útil para o gestor conferir fora do sistema.

## 4. Tarefas técnicas

**Dados**
- [ ] Migração `0008_aprovacoes`: `aprovacoes` com CHECK de justificativa, RLS, `REVOKE UPDATE, DELETE`
- [ ] Índice `(tenant_id, status_aprovacao, nivel_aprovacao_exigido)` já criado; adicionar `(tenant_id, lancamento_id)` em `aprovacoes`

**Backend**
- [ ] `domain/aprovacao.py`: `proximo_nivel(aprovacoes, exigido)`, `pode_aprovar(user, lancamento, aprovacoes)` — funções puras
- [ ] `services/aprovacao_service.py` (com `FOR UPDATE`), notificação por e-mail na rejeição
- [ ] `api/v1/aprovacoes.py`, `api/v1/auditoria.py`
- [ ] Dependência `require_nivel(n)`

**Frontend**
- [ ] `features/aprovacao/` — `AprovacaoPage`, `RejeicaoDialog`, seleção múltipla
- [ ] `HistoricoTimeline` unificada (substitui a timeline da Sprint 07)

## 5. Contrato de API

| Método | Rota | Papel | Descrição |
|--------|------|-------|-----------|
| POST | `/api/v1/lancamentos/{id}/enviar-aprovacao` | autor | Rascunho → aguardando |
| GET | `/api/v1/aprovacoes/pendentes` | aprovador | Fila por nível |
| POST | `/api/v1/lancamentos/{id}/aprovacao` | aprovador | `{decisao, justificativa?}` |
| POST | `/api/v1/aprovacoes/lote` | aprovador | Aprova até 50 |
| GET | `/api/v1/lancamentos/{id}/historico` | envolvidos | Linha do tempo unificada |
| GET | `/api/v1/auditoria` | admin | Pesquisa na trilha de auditoria |
| GET | `/api/v1/auditoria/export` | admin | Planilha XLSX/CSV da auditoria filtrada |
| GET | `/api/v1/aprovacoes/export` | aprovador | Planilha da fila/histórico de aprovações |

## 6. Estratégia de testes
- Unidade: matriz `pode_aprovar` (papel × nível × autoria × aprovações anteriores × faixa).
- Integração: fluxo nível 1; fluxo nível 1 → nível 2; rejeição → correção → reenvio; mudança de valor invalida aprovação; aprovação em lote parcialmente inválida (retorna sucesso/erro por item).
- Segurança: aprovador de outro tenant não vê a fila (suíte cross-tenant); colaborador recebe `403`.
- E2E: colaborador envia 1.800,00 → aprovador N1 aprova → aprovador N2 aprova → histórico mostra as duas assinaturas.

## 7. Definition of Done específica
- [ ] Impossível autoaprovação (teste)
- [ ] Histórico unificado cobre 100% das mutações de lançamento

## 8. Riscos e mitigação

| Risco | Mitigação |
|-------|-----------|
| Regras de aprovação variam muito entre empresas | Manter 2 níveis fixos no MVP, parametrizados por faixa; motor de regras configurável é pós-MVP |
| Gargalo com um único aprovador | Alerta ao admin (H8.4) e lembrete diário de pendências ao aprovador |

## 9. Entregável / demo
Três lançamentos (micro, médio, alto) percorrendo o fluxo; um rejeitado com justificativa, corrigido e reaprovado; auditoria mostra toda a história.

## 10. Retrospectiva
_Preencher ao final da sprint._
