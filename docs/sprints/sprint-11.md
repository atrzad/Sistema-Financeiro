# Sprint 11 — Hardening e go-live

[← Sprint 10](sprint-10.md) · [Índice](README.md)

| | |
|---|---|
| **Período** | 22/03 – 02/04/2027 |
| **Pontos** | 20 |
| **Fase do MVP** | Produção · fecha o **Marco M5** |

## 1. Objetivo
Colocar o sistema em produção com segurança: retenção de dados conforme LGPD, acurácia do OCR medida com dados reais, observabilidade para operar, revisão de segurança concluída e deploy reprodutível com backups testados.

## 2. Requisitos cobertos
RNF04 · RNF05 · consolidação de RNF02, RNF03, RNF06, RNF07

## 3. Histórias de usuário

### H11.1 — Retenção de dados configurável (LGPD) `5 pts`
**Como** admin, **quero** definir por quanto tempo os dados são mantidos **para** cumprir a LGPD e as obrigações fiscais.
- **Então** `tenants.retencao_meses` é configurável pelo admin, com mínimo de 60 meses (5 anos — prazo prescricional fiscal) e aviso explicando a razão do mínimo.
- **Então** a task mensal `aplicar_retencao` (fila `maintenance`), para cada tenant com `SET LOCAL`, identifica lançamentos com `data_emissao` além do prazo **e** que não estão em relatório aberto.
- **Então** para esses lançamentos: comprovantes originais e miniaturas são removidos do storage (Object Lock configurado com o mesmo prazo de retenção), `ocr_raw_payload` é apagado, dados pessoais em texto livre (descrição, itens, observações) são anonimizados; valores agregados permanecem para estatística. `anonimizado_em` é preenchido.
- **Então** execução em modo `dry_run` gera relatório do que seria afetado; o admin recebe e-mail 30 dias antes da primeira execução.
- **Então** cada execução gera registro de auditoria com contagens.

### H11.2 — Direitos do titular `2 pts`
- **Então** `GET /me/dados` exporta em JSON os dados pessoais do usuário (perfil, lançamentos criados, eventos).
- **Então** admin pode desativar e anonimizar um usuário desligado (`nome`, `email` → pseudônimo), preservando a integridade da trilha de auditoria (FKs intactas).

### H11.3 — Benchmark de acurácia do OCR `3 pts`
- **Então** o dataset da Sprint 04 é ampliado para ≥ 100 documentos reais anonimizados, estratificados por tipo (boleto, cupom térmico, NF-e, recibo manuscrito, PDF multi-página).
- **Então** `ocr-bench` roda contra Tesseract e os dois provedores pagos candidatos, e produz por provedor e tipo: acurácia exata por campo, erro absoluto médio de valor, taxa de campos < 0,80, latência p50/p95 e custo estimado por documento.
- **Então** métrica de produção: taxa de correção manual por campo (a partir do `audit_log` `ocr_corrigido`) exposta no dashboard de operação.
- **Então** resultado documentado em ADR 0006 (provedor final e calibração do limiar de confiança).

### H11.4 — Observabilidade `3 pts`
- **Então** Sentry no backend, worker, web e mobile, com `tenant_id` como tag e **sem** dados pessoais (scrubbing de e-mail, CNPJ, valores).
- **Então** métricas Prometheus: latência/erros por rota, tamanho das filas Celery, duração e falhas de OCR por provedor, tempo de exportação.
- **Então** alertas: fila `ocr` com > 100 itens por 10 min, taxa de erro 5xx > 2%, falha de backup, falha na task de retenção.
- **Então** logs estruturados com `request_id` correlacionando API → task Celery.

### H11.5 — Revisão de segurança `3 pts`
- **Então** checklist OWASP ASVS nível 2 aplicado aos pontos críticos (auth, upload, autorização, exportação) com resultado registrado em `docs/seguranca.md`.
- **Então** `pip-audit`, `pnpm audit`, Trivy (imagens Docker) e `gitleaks` no CI, bloqueando vulnerabilidades altas.
- **Então** cabeçalhos de segurança (CSP restrita, HSTS, `X-Content-Type-Options`, `Referrer-Policy`), CORS por lista de origens, cookies `Secure`.
- **Então** teste de intrusão básico nos endpoints de upload com o corpus malicioso da Sprint 03 contra o ambiente de staging.
- **Então** suíte cross-tenant executada contra staging (não só local).

### H11.6 — Deploy de produção `3 pts`
- **Então** imagens Docker versionadas por tag; ambientes `staging` e `production` com infraestrutura declarada (Terraform ou docker-compose de produção + provedor gerenciado, conforme orçamento).
- **Então** pipeline: merge em `main` → deploy em staging automático → testes E2E em staging → deploy em produção com aprovação manual.
- **Então** migrações rodam como `app_owner` em etapa separada, antes da nova versão da API; migrações devem ser compatíveis com a versão anterior (expand/contract).
- **Então** backups do Postgres com PITR e **teste de restauração** documentado; versionamento do bucket de comprovantes.
- **Então** apps mobile publicados (Play Store — faixa de teste fechado; App Store — TestFlight externo).

### H11.7 — Onboarding de nova empresa `1 pt`
- **Então** comando `app.cli criar-tenant --nome --slug --admin-email` cria tenant com faixas e categorias padrão e envia convite ao admin.
- **Então** runbook de operação em `docs/runbook.md` (criar tenant, reprocessar OCR em massa, restaurar backup, rotacionar segredos).

## 4. Tarefas técnicas
- [ ] Migração `0011_lgpd`: `lancamentos.anonimizado_em`, `comprovantes.removido_em`, validação `retencao_meses >= 60`
- [ ] `workers/tasks/retencao.py` com `dry_run`
- [ ] `app/cli.py`: `ocr-bench`, `criar-tenant`
- [ ] Integração Sentry + `prometheus-fastapi-instrumentator` + exporter Celery
- [ ] Workflows `deploy-staging.yml`, `deploy-production.yml`
- [ ] Docs: `docs/seguranca.md`, `docs/runbook.md`, ADR 0006

## 5. Contrato de API

| Método | Rota | Papel | Descrição |
|--------|------|-------|-----------|
| PATCH | `/api/v1/tenant/configuracoes` | admin | `retencao_meses`, `limiar_confianca` |
| GET | `/api/v1/tenant/retencao/previa` | admin | Resultado de `dry_run` |
| GET | `/api/v1/me/dados` | autenticado | Exportação de dados pessoais |
| POST | `/api/v1/users/{id}/anonimizar` | admin | Anonimiza usuário desativado |
| GET | `/metrics` | interno | Prometheus (não exposto publicamente) |

## 6. Estratégia de testes
- Retenção: dataset com datas antigas; `dry_run` e execução real; verificar objetos removidos, dados anonimizados e relatórios fechados ainda gerando PDF (com aviso "comprovante removido por política de retenção").
- Restauração de backup em ambiente isolado com checagem de contagens.
- Teste de carga (k6/Locust) em staging: 50 usuários simultâneos enviando lotes de 10 → p95 da API < 500 ms; fila de OCR drena sem erros.

## 7. Definition of Done específica
- [ ] Restauração de backup testada e cronometrada
- [ ] ADR 0006 com números do benchmark
- [ ] Nenhuma vulnerabilidade alta aberta
- [ ] **Marco M5**: primeira empresa real usando em produção

## 8. Riscos e mitigação

| Risco | Mitigação |
|-------|-----------|
| Prazo de retenção conflita com obrigação fiscal | Mínimo de 60 meses travado; validação com contador/jurídico antes de ativar |
| Provedor de OCR escolhido ficar caro em escala | Adapter permite troca; custo por documento monitorado |
| Primeira semana em produção revelar problemas | Rollout para uma empresa piloto; feature flag para OCR pago vs. local |

## 9. Entregável / demo
Deploy de uma versão em produção pelo pipeline, empresa piloto criada via CLI, dashboard de operação com métricas reais, relatório do benchmark de OCR e restauração de backup demonstrada.

## 10. Retrospectiva do projeto
_Preencher ao final:_ velocidade média por sprint, desvios em relação ao plano, backlog pós-MVP priorizado (integração bancária/Open Finance para pagamento real, aprovação configurável, conciliação bancária, multi-moeda, app offline completo).
