# Sprint 04 — Pipeline de OCR assíncrono

[← Sprint 03](sprint-03.md) · [Índice](README.md) · [Sprint 05 →](sprint-05.md)

| | |
|---|---|
| **Período** | 30/11 – 11/12/2026 |
| **Pontos** | 21 |
| **Fase do MVP** | Upload e OCR |

## 1. Objetivo
Cada comprovante validado é processado por OCR em background, com retry independente por arquivo, e a Tela 2 mostra o progresso em etapas em tempo real — com um provedor local (Tesseract) em dev e um provedor pago pronto para produção.

## 2. Requisitos cobertos
RF02 (extração) · RF11 (PDF multi-página) · RNF01 · RNF05 (início do dataset) · RNF06 · Tela 2 · [ADR 0003](../adr/0003-ocr-via-adapter-de-provedor.md)

## 3. Histórias de usuário

### H4.1 — Interface `OcrProvider` e provedor local `5 pts`
- **Então** existe o `Protocol OcrProvider` e o `OcrResult` normalizado conforme ADR 0003.
- **Então** `TesseractProvider` (idioma `por`) converte PDF em imagens (`pypdfium2`, 300 dpi), pré-processa (escala de cinza, binarização adaptativa, correção de inclinação com OpenCV) e aplica extratores por regex para CNPJ, datas, valores, linha digitável.
- **Então** a confiança do Tesseract (por palavra) é agregada por campo e normalizada para 0–1.
- **Então** `FakeOcrProvider` retorna resultados determinísticos por nome de fixture, para testes.

### H4.2 — Provedor de produção `3 pts`
- **Então** existe `VeryfiProvider` **ou** `MindeeProvider` (escolher após teste com 20 amostras reais no dia 1 da sprint — registrar a escolha em ADR 0005).
- **Então** o mapeamento de campos do provedor → `OcrResult` é coberto por testes com respostas gravadas (VCR/`respx`), sem chamar a API real no CI.
- **Então** credenciais vêm de variáveis de ambiente; timeout de 60 s.

### H4.3 — Pós-processamento comum `3 pts`
- **Então** CNPJ extraído é normalizado e validado por dígito verificador; se inválido, confiança do campo = `min(conf, 0.3)`.
- **Então** a **linha digitável/código de barras de boleto** (padrão FEBRABAN, 47/48 dígitos) é decodificada para obter valor e fator de vencimento; se o DV for válido, valor e vencimento recebem confiança 0.99 e prevalecem sobre o texto livre.
- **Então** datas ambíguas são interpretadas como `dd/mm/aaaa`; vencimento anterior à emissão reduz a confiança do vencimento.

### H4.4 — Task de OCR com retry por arquivo `3 pts`
- **Então** `processar_ocr(tenant_id, comprovante_id)` roda na fila `ocr`, com `autoretry_for=(ProviderTimeout, ProviderRateLimited, ProviderUnavailable)`, backoff exponencial com jitter, `max_retries=3`.
- **Então** erros não recuperáveis (arquivo ilegível, resposta 4xx do provedor) não geram retry.
- **Então** `tentativas_ocr` é incrementado a cada tentativa; após esgotar, `status = erro` com `erro_msg`.
- **Então** a falha de um arquivo não afeta os outros do lote.
- **Então** resultado gravado em `ocr_raw_payload`, `ocr_confidence`, `ocr_provider`, e status vai para `aguardando_revisao`.
- **Então** `POST /comprovantes/{id}/reprocessar` permite reprocessar manualmente um item em erro.

### H4.5 — Progresso em tempo real `3 pts`
- **Então** o worker publica eventos no canal Redis `batch:{id}` a cada mudança de etapa (`enviado`, `ocr_iniciado`, `ocr_concluido`, `erro`), incluindo o nome do fornecedor quando já extraído.
- **Então** o endpoint `WS /uploads/batch/{id}/ws` retransmite os eventos (autenticação via token no primeiro frame; valida tenant do lote).
- **Então** se o WebSocket cair, o frontend volta automaticamente para polling.

### H4.6 — Tela 2: processamento `3 pts`
- **Então** a tela mostra etapas, não spinner genérico: `✔ Enviando arquivos (10/10)`, `⏳ Escaneando via OCR (6/10)` com o item atual (`Padaria Central — extraindo dados...`), `⏳ Organizando por vencimento`.
- **Então** o usuário pode navegar para outra tela; ao concluir o lote aparece um *toast* global "10 documentos prontos para revisão" (e notificação do navegador, se permitida).
- **Então** o resultado final é listado ordenado por vencimento extraído ascendente.

### H4.7 — Dataset de acurácia `1 pt`
- **Então** existe `backend/tests/ocr_dataset/` com pelo menos 30 comprovantes reais anonimizados (boletos, cupons térmicos, NF-e, recibos manuscritos, carnê multi-página) e um `gabarito.json` com os valores corretos.
- **Então** `uv run python -m app.cli ocr-bench --provider tesseract` gera relatório de acurácia por campo (usado de forma completa na Sprint 11).

## 4. Tarefas técnicas

**Backend**
- [ ] `services/ocr/base.py`, `tesseract.py`, `veryfi.py`/`mindee.py`, `fake.py`, `postprocess.py`, `boleto.py`
- [ ] `workers/tasks/processar_ocr.py`; encadeamento `validar_arquivo → processar_ocr`
- [ ] Rate limit da fila `ocr` (`rate_limit` do Celery conforme plano do provedor)
- [ ] WebSocket com `fastapi` + `redis.asyncio` pub/sub
- [ ] Dockerfile do worker com `tesseract-ocr`, `tesseract-ocr-por`, `libgl1`

**Frontend**
- [ ] `features/upload/ProcessingPage` + `useBatchEvents` (WebSocket com fallback)
- [ ] Toast global e Notification API

**Docs**
- [ ] ADR 0005 — escolha do provedor de OCR de produção

## 5. Contrato de API

| Método | Rota | Descrição |
|--------|------|-----------|
| WS | `/api/v1/uploads/batch/{id}/ws` | Eventos de progresso do lote |
| GET | `/api/v1/comprovantes/{id}` | Detalhe com campos extraídos e confiança |
| POST | `/api/v1/comprovantes/{id}/reprocessar` | Reenfileira OCR |

Formato de `ocr_confidence`:

```json
{ "nome_fantasia": 0.91, "cnpj": 0.62, "data_emissao": 0.88,
  "data_vencimento": 0.99, "valor_total": 0.99, "forma_pagamento": 0.75 }
```

## 6. Estratégia de testes
- Unidade: decodificação de linha digitável (boletos bancários e de convênio), extratores regex, normalização de confiança.
- Integração: task com `FakeOcrProvider` simulando timeout 2x e sucesso na 3ª; simulando erro permanente.
- Contrato: respostas gravadas do provedor pago.
- Carga leve: 10 lotes × 10 arquivos com `FakeOcrProvider` → todos concluem, sem deadlock.

## 7. Definition of Done específica
- [ ] Retry comprovado por teste; falha de um item não altera os demais
- [ ] Linha digitável válida sempre prevalece sobre texto livre
- [ ] Relatório inicial de acurácia gerado e anexado ao PR

## 8. Riscos e mitigação

| Risco | Mitigação |
|-------|-----------|
| Tesseract com acurácia baixa em cupom térmico | Aceitável em dev; produção usa provedor pago; medição na Sprint 11 |
| Custo por página do provedor pago | Limite de 50 páginas por PDF; cache por `sha256` (mesmo arquivo não é reprocessado) |
| WebSocket atrás de proxy/load balancer | Fallback automático para polling |

## 9. Entregável / demo
Enviar 10 comprovantes, fechar a aba, reabrir na Tela 2 e ver o progresso item a item; forçar falha do provedor em um arquivo e ver retry e recuperação sem afetar os demais.

## 10. Retrospectiva
_Preencher ao final da sprint._
