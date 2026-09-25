# Sprint 09 — Relatórios de prestação de contas

[← Sprint 08](sprint-08.md) · [Índice](README.md) · [Sprint 10 →](sprint-10.md)

| | |
|---|---|
| **Período** | 22/02 – 05/03/2027 |
| **Pontos** | 21 |
| **Fase do MVP** | Pagamento e prestação de contas · fecha o **Marco M4 (MVP web completo)** |

## 1. Objetivo
O usuário monta um relatório de prestação de contas por período, projeto ou centro de custo, fecha-o (congelando o conteúdo) e exporta em PDF e Excel com os comprovantes anexados — pronto para entregar ao financeiro ou ao cliente.

## 2. Requisitos cobertos
RF05 · RF07 · RF12 (exportação assíncrona de grandes volumes) · Tela 6

## 3. Histórias de usuário

### H9.1 — Criar relatório e vincular lançamentos `3 pts`
**Como** colaborador, **quero** agrupar despesas de um período ou projeto num relatório **para** prestar contas.
- **Quando** crio um relatório com `titulo`, `periodo_inicio`, `periodo_fim` e opcionalmente `projeto_id`/`centro_custo_id`, **então** o sistema sugere automaticamente os lançamentos elegíveis (emissão no período, filtros aplicados, não rejeitados, não vinculados a outro relatório fechado).
- **Então** posso adicionar/remover lançamentos manualmente enquanto o relatório está `aberto`.
- **Dado** `periodo_fim < periodo_inicio`, **então** `422`.
- **Então** `total` é recalculado a cada alteração (soma de `valor` dos vinculados).
- **Então** `relatorio_lancamentos` tem `tenant_id` e RLS (correção do plano original).

### H9.2 — Fechar relatório `3 pts`
- **Dado** um relatório com lançamentos ainda `aguardando` aprovação, **quando** tento fechar, **então** `409` listando as pendências.
- **Quando** fecho, **então** `status = fechado`, `fechado_em` preenchido, e um **snapshot** JSON dos lançamentos (valores, fornecedores, datas, status, aprovadores) é gravado — o relatório fechado não muda mesmo que um lançamento seja editado depois.
- **Então** lançamentos de relatório fechado não podem ser editados nem estornados (`409`) — integração com Sprints 07/08.
- **Então** admin pode reabrir com justificativa (registrado no `audit_log`).
- **Então** um lançamento só pode estar em **um** relatório fechado.

### H9.3 — Tela 6: relatório `5 pts`
- **Então** listagem de relatórios com status e total; tela de edição com os lançamentos agrupados por categoria (padrão), fornecedor ou data.
- **Então** total consolidado, subtotais por grupo, gráfico de rosca por categoria (reusa componentes do dashboard).
- **Então** painel "Adicionar lançamentos" com busca e filtros; indicadores de lançamentos sem comprovante ou pendentes de aprovação.
- **Então** botões **Fechar relatório**, **Exportar PDF**, **Exportar Excel**.

### H9.4 — Exportação em PDF `5 pts`
- **Então** a exportação é assíncrona: `POST /relatorios/{id}/exportacoes {formato: "pdf"}` cria registro na tabela genérica `exportacoes` (`tipo = 'relatorio_pdf'`) e enfileira task na fila `reports`.
- **Então** o PDF (WeasyPrint + template HTML/CSS) contém: capa (empresa, título, período, responsável, data de geração), resumo por categoria com gráfico, tabela de lançamentos (data, fornecedor, CNPJ, categoria, valor, status de pagamento, aprovador), total.
- **Então** anexos: cada comprovante em página própria — imagens redimensionadas; PDFs originais **mesclados** página a página (`pypdf`), preservando carnês multi-página.
- **Então** cada linha da tabela referencia a página do anexo ("ver pág. 7").
- **Então** rodapé com hash SHA-256 do relatório e "gerado em … por …" para integridade.
- **Então** limite: relatórios com mais de 300 comprovantes geram aviso e são divididos em volumes.

### H9.5 — Exportação em Excel `3 pts`
- **Então** gerado pelo motor `services/export/tabular.py` da [Sprint 07](sprint-07.md) (mesma formatação, sanitização e aba Informações), com abas: *Resumo* (totais por categoria/fornecedor), *Lançamentos* (uma linha por lançamento, valores como número com formato BRL, datas como data), *Itens* (itens dos comprovantes), *Histórico de pagamentos*.
- **Então** coluna com **link** para cada comprovante (URL da API autenticada, não presigned — não expira em arquivo compartilhado).
- **Então** filtros automáticos e cabeçalho congelado.

### H9.6 — Exportações assíncronas, download e notificação `2 pts`
- **Então** a tabela `exportacoes` é genérica (relatórios **e** listagens): exportações de listas com mais de 10.000 linhas (limite síncrono da Sprint 07) passam a ser enfileiradas em vez de retornar `413` — `POST /exportacoes {tipo: "lancamentos", formato: "xlsx", filtros: {...}}`.
- **Então** a tela **Minhas exportações** lista as gerações (relatórios e planilhas) com status; ao ficar `pronto`, toast/notificação e botão de download (presigned 5 min, `attachment`).
- **Então** arquivos exportados ficam no bucket `exports` com expiração de 30 dias (lifecycle rule).

## 4. Tarefas técnicas

**Dados**
- [ ] Migração `0009_relatorios`: `relatorios_prestacao` (com `projeto_id`, `centro_custo_id`, `fechado_em`, `snapshot JSONB`), `relatorio_lancamentos` (com `tenant_id`), `exportacoes` (genérica), RLS
- [ ] Índice único parcial garantindo um lançamento por relatório fechado (via tabela/trigger, pois depende do status do relatório)

**Backend**
- [ ] `services/relatorio_service.py` (sugestão, vínculo, fechamento com snapshot)
- [ ] `services/export/pdf.py` (templates Jinja2 + WeasyPrint + merge `pypdf`); Excel do relatório reutiliza `services/export/tabular.py`
- [ ] `workers/tasks/exportar.py` — relatórios e listas grandes (fila `reports`, timeout 10 min, memória limitada — processa anexos em streaming)
- [ ] Lifecycle rule no bucket `exports`
- [ ] Dockerfile do worker com dependências do WeasyPrint (Pango, fontes)

**Frontend**
- [ ] `features/relatorios/` — `RelatoriosListPage`, `RelatorioPage`, `AdicionarLancamentosPanel`
- [ ] `features/exportacoes/MinhasExportacoesPage`; `ExportButton` passa a oferecer "gerar em segundo plano" quando o total excede 10.000 linhas

## 5. Contrato de API

| Método | Rota | Descrição |
|--------|------|-----------|
| GET/POST | `/api/v1/relatorios` | Lista / cria |
| GET/PATCH/DELETE | `/api/v1/relatorios/{id}` | Detalhe / edita (aberto) / exclui (aberto) |
| GET | `/api/v1/relatorios/{id}/sugestoes` | Lançamentos elegíveis |
| POST/DELETE | `/api/v1/relatorios/{id}/lancamentos` | Vincula / desvincula (`{lancamento_ids: []}`) |
| POST | `/api/v1/relatorios/{id}/fechar` | Fecha e gera snapshot |
| POST | `/api/v1/relatorios/{id}/reabrir` | Admin, com justificativa |
| POST | `/api/v1/relatorios/{id}/exportacoes` | `{formato: "pdf" \| "xlsx"}` |
| GET | `/api/v1/relatorios/{id}/exportacoes` | Status das exportações do relatório |
| POST | `/api/v1/exportacoes` | Exportação assíncrona de listagem grande (`{tipo, formato, filtros}`) |
| GET | `/api/v1/exportacoes` | Minhas exportações (relatórios e planilhas) |
| GET | `/api/v1/exportacoes/{id}/download` | Redirect para arquivo |

## 6. Estratégia de testes
- Unidade: cálculo de totais com `Decimal`, montagem do snapshot.
- Integração: regras de fechamento (pendências, lançamento em dois relatórios, edição pós-fechamento bloqueada), reabertura auditada.
- Exportação: gerar PDF com fixture de 20 lançamentos (imagens + PDF multi-página) e verificar nº de páginas, presença do texto do total (`pypdf.extract_text`) e hash; gerar XLSX e ler de volta com openpyxl.
- Performance: relatório com 200 comprovantes gerado em < 2 min com memória < 512 MB.

## 7. Definition of Done específica
- [ ] PDF abre corretamente em Acrobat, navegador e visualizador do celular
- [ ] Relatório fechado idêntico antes e depois de editar um lançamento vinculado
- [ ] **Marco M4** demonstrado: fluxo ponta a ponta do upload ao PDF de prestação de contas

## 8. Riscos e mitigação

| Risco | Mitigação |
|-------|-----------|
| Consumo de memória ao mesclar muitos PDFs | Processamento em streaming e divisão em volumes |
| Fidelidade do layout do WeasyPrint | Template simples e testado; revisão visual do PDF no PR |
| PDF de comprovante com fontes/estrutura estranhas quebra o merge | Fallback: rasterizar a página com `pypdfium2` |

## 9. Entregável / demo
Criar relatório "Viagem cliente X — fev/2027" pelo projeto, fechar, exportar PDF e Excel, abrir o PDF e navegar da tabela para o comprovante anexado.

## 10. Retrospectiva
_Preencher ao final da sprint._
