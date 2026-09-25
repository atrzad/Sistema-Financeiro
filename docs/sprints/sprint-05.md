# Sprint 05 — Revisão do OCR

[← Sprint 04](sprint-04.md) · [Índice](README.md) · [Sprint 06 →](sprint-06.md)

| | |
|---|---|
| **Período** | 14/12/2026 – 08/01/2027 (estendida por festas de fim de ano) |
| **Pontos** | 20 |
| **Fase do MVP** | Upload e OCR · fecha o **Marco M2** |

## 1. Objetivo
O usuário revisa os dados extraídos lado a lado com o comprovante, corrige o que for necessário (obrigatoriamente os campos com confiança < 80%), e confirma — gerando um lançamento vinculado ao fornecedor certo, sem cadastros duplicados, com toda correção auditada.

## 2. Requisitos cobertos
RF02 (itens, fornecedor) · RF04 · Regra "Confiança do OCR" · Regra "Nome fantasia" · Tela 3

## 3. Histórias de usuário

### H5.1 — Fila de revisão `2 pts`
- **Quando** chamo `GET /comprovantes?status=aguardando_revisao`, **então** recebo os comprovantes pendentes do usuário ordenados por vencimento extraído, com contagem de campos de baixa confiança.
- **Então** o menu mostra um badge com o número de revisões pendentes.

### H5.2 — Tela 3: revisão lado a lado `5 pts`
**Como** colaborador, **quero** conferir os dados extraídos ao lado da imagem **para** corrigir erros rapidamente.
- **Então** à esquerda: visualizador do comprovante (zoom, rotação, navegação entre páginas de PDF com `pdf.js`).
- **Então** à direita: formulário pré-preenchido com fornecedor, CNPJ, data de emissão, vencimento, valor, forma de pagamento, linha digitável, categoria, projeto, centro de custo e tabela de itens editável.
- **Então** cada campo exibe indicador de confiança: 🟢 ≥ 90%, 🟡 80–89%, 🔴 < 80% (com cor **e** ícone/texto, para acessibilidade).
- **Então** campos 🔴 começam focados/destacados e exigem interação explícita (editar ou marcar "conferido") antes de habilitar *Confirmar*.
- **Então** atalhos de teclado: `Enter` confirma e vai para o próximo, `Ctrl+→` pula.
- **Então** a soma dos itens diferente do valor total gera aviso (não bloqueante).

### H5.3 — Regra de revisão obrigatória no backend `2 pts`
- **Dado** um campo com confiança < 0.80, **quando** o cliente confirma sem enviar esse campo em `campos_conferidos`, **então** `422` listando os campos pendentes.
- **Então** o limiar 0.80 é configuração por tenant (default 0.80) — a regra não depende da UI.

### H5.4 — Matching de fornecedor `3 pts`
**Como** colaborador, **quero** que o sistema reconheça fornecedores já cadastrados **para** não criar duplicatas.
- **Dado** um CNPJ extraído válido que existe no tenant, **então** o fornecedor é associado diretamente (match exato).
- **Senão**, **então** busca por `similarity(nome_fantasia, :texto) >= 0.6` (pg_trgm) após normalização (minúsculas, sem acentos, sem "LTDA/ME/EIRELI/S.A.") e retorna até 3 candidatos com score.
- **Então** a UI mostra: "Encontramos *Padaria Central* (92%) — usar este?" ou "Cadastrar novo fornecedor" pré-preenchido.
- **Então** ao confirmar um candidato, a associação `texto OCR → supplier_id` é memorizada (`supplier_aliases`) para matches futuros com confiança 1.0.

### H5.5 — Confirmar e gerar lançamento `3 pts`
- **Quando** confirmo, **então** em **uma transação**: cria `lancamentos` (status `pendente`, `status_aprovacao = aguardando`), cria `lancamento_itens`, vincula `comprovantes.lancamento_id`, muda o comprovante para `concluido`, grava `audit_log`.
- **Então** é idempotente: confirmar duas vezes o mesmo comprovante retorna o mesmo lançamento (`409` com `lancamento_id`).
- **Então** posso vincular vários comprovantes (ex.: boleto + nota fiscal) ao mesmo lançamento.
- **Então** posso descartar um comprovante (`POST /comprovantes/{id}/descartar`) com motivo — o arquivo permanece (imutável), apenas sai da fila.

### H5.6 — Auditoria de correções pós-OCR `3 pts`
- **Então** para cada campo em que o valor confirmado difere do extraído, grava `audit_log` com `acao = 'ocr_corrigido'`, `valor_antigo` (OCR), `valor_novo`, usuário e timestamp.
- **Então** `audit_log` é append-only (`REVOKE UPDATE, DELETE`), com RLS.
- **Então** `GET /lancamentos/{id}/historico` retorna a trilha de auditoria.
- **Então** as correções alimentam uma métrica de acurácia real por campo (taxa de correção) — base para RNF05.

### H5.7 — Alerta de duplicidade `2 pts`
- **Dado** um comprovante com mesmo `sha256` **ou** mesmo (fornecedor, valor, vencimento) de um lançamento existente, **então** a revisão mostra alerta "Possível duplicado de *lançamento X*" com link.
- **Então** o usuário pode prosseguir mesmo assim (registrado no `audit_log`).

## 4. Tarefas técnicas

**Dados**
- [ ] Migração `0005_revisao`: `lancamento_itens`, `audit_log`, `supplier_aliases (tenant_id, texto_normalizado, supplier_id)`, `tenants.limiar_confianca NUMERIC(3,2) DEFAULT 0.80`, RLS
- [ ] Função SQL `normalizar_nome(text)` (`unaccent` + remoção de sufixos societários) com índice trigram de expressão

**Backend**
- [ ] `domain/revisao.py`: `campos_obrigatorios(confidence, limiar)`, `diff_campos(ocr, confirmado)`
- [ ] `services/supplier_matching.py`
- [ ] `services/revisao_service.py` (transação de confirmação)
- [ ] `services/audit.py` reutilizável por todas as sprints seguintes

**Frontend**
- [ ] `features/revisao/` — `RevisaoPage`, `DocumentViewer` (pdf.js + imagem com zoom), `ConfidenceField`, `SupplierMatchCard`, `ItensTable`
- [ ] Navegação sequencial pela fila de revisão

## 5. Contrato de API

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/v1/comprovantes?status=aguardando_revisao` | Fila de revisão |
| GET | `/api/v1/comprovantes/{id}/sugestoes-fornecedor` | Candidatos de matching |
| POST | `/api/v1/comprovantes/{id}/confirmar` | Cria/vincula lançamento |
| POST | `/api/v1/comprovantes/{id}/descartar` | Remove da fila com motivo |
| GET | `/api/v1/lancamentos/{id}/historico` | Trilha de auditoria |

Corpo de `confirmar`:

```json
{
  "supplier_id": "…",                      // ou "novo_supplier": {...}
  "lancamento_id": null,                   // preencher para vincular a existente
  "valor": "245.90",
  "data_emissao": "2026-09-10",
  "data_pagamento_prevista": "2026-10-05",
  "forma_pagamento": "boleto",
  "linha_digitavel": "23793.38128 …",
  "categoria_id": "…", "projeto_id": null, "centro_custo_id": "…",
  "itens": [{ "descricao": "Energia 09/2026", "quantidade": "1", "valor_total": "245.90" }],
  "campos_conferidos": ["cnpj", "forma_pagamento"]
}
```

## 6. Estratégia de testes
- Unidade: `campos_obrigatorios`, `diff_campos`, normalização de nome (tabela de casos: "PADARIA CENTRAL LTDA ME" ≈ "Padaria Central").
- Integração: confirmação transacional (falha no meio não deixa lançamento órfão), idempotência, duplicidade.
- E2E: upload → processamento → revisão corrigindo CNPJ → lançamento aparece na lista com o fornecedor correto → histórico mostra a correção.

## 7. Definition of Done específica
- [ ] Impossível confirmar pela API sem conferir campos < limiar
- [ ] Toda correção pós-OCR aparece no histórico
- [ ] **Marco M2** demonstrado: fluxo completo foto/PDF → lançamento revisado

## 8. Riscos e mitigação

| Risco | Mitigação |
|-------|-----------|
| Fuzzy matching gera falso positivo (duas "Padaria Central" diferentes) | Nunca associa automaticamente sem CNPJ ou alias confirmado — sempre sugere |
| Sprint atravessa festas de fim de ano | Período estendido; mesma pontuação |
| `pdf.js` pesado no bundle | Carregamento *lazy* do visualizador |

## 9. Entregável / demo
Revisar um lote de 5 documentos em sequência só com teclado, incluindo um cupom térmico com CNPJ ilegível (🔴 forçando correção) e um fornecedor reconhecido por similaridade.

## 10. Retrospectiva
_Preencher ao final da sprint._
