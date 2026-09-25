# Sprint 03 — Upload em lote

[← Sprint 02](sprint-02.md) · [Índice](README.md) · [Sprint 04 →](sprint-04.md)

| | |
|---|---|
| **Período** | 16/11 – 27/11/2026 |
| **Pontos** | 21 |
| **Fase do MVP** | Upload e OCR |

## 1. Objetivo
O usuário envia até 10 comprovantes (PDF, JPG, PNG) de uma vez, direto para o storage, acompanhando o progresso de cada arquivo; o backend valida cada um em três camadas e guarda o original de forma imutável. **Ainda sem OCR.**

## 2. Requisitos cobertos
RF01 (web) · RF11 · RNF01 (parcial) · RNF02 · RNF07 · RNF08 · Tela 1

## 3. Histórias de usuário

### H3.1 — Criar lote e obter URLs de upload `5 pts`
**Como** colaborador, **quero** selecionar vários arquivos e enviá-los de uma vez **para** não repetir o processo por comprovante.
- **Quando** chamo `POST /uploads/batch` com a lista `[{nome, tamanho_bytes, mime_type}]`, **então** recebo `batch_id` e, por arquivo, `comprovante_id` + URL presigned `PUT` (expira em 15 min) + headers obrigatórios.
- **Dado** mais de 10 arquivos, algum > 10 MB, total > 60 MB ou extensão fora da allowlist (`.pdf .jpg .jpeg .png`), **então** `422` apontando o arquivo infrator — nada é criado.
- **Então** a key do objeto é `{tenant_id}/{yyyy}/{mm}/{comprovante_id}.{ext}` — nunca o nome do cliente.
- **Então** a presigned URL fixa `Content-Type` e `Content-Length` (policy de upload), impedindo enviar arquivo maior que o declarado.
- **Quando** chamo `POST /uploads/{comprovante_id}/complete`, **então** o status vai para `validando` e a task `validar_arquivo` é enfileirada. Chamada repetida é idempotente.

### H3.2 — Validação em três camadas `5 pts`
**Como** responsável pela segurança, **quero** que nenhum arquivo malicioso ou corrompido seja aceito.
- **Camada 1 — extensão:** já verificada na criação do lote; revalidada no worker.
- **Camada 2 — magic bytes:** `python-magic` lê os primeiros bytes do objeto; o MIME detectado deve bater com a extensão (ex.: `.pdf` ⇒ `application/pdf`). O `Content-Type` do cliente é ignorado.
- **Camada 3 — parsing real:** PDF aberto com `pypdf` (rejeita criptografado, corrompido, com JavaScript/`/OpenAction` ou mais de 50 páginas); imagem aberta com `Pillow` com `Image.MAX_IMAGE_PIXELS` limitado (proteção contra *decompression bomb*) e `verify()`.
- **Dado** falha em qualquer camada, **então** `status_processamento = erro`, `erro_msg` legível ("O arquivo não é um PDF válido"), e o objeto é movido para o prefixo `quarentena/`.
- **Dado** sucesso, **então** `total_paginas` é preenchido (PDF) e o status vai para `na_fila` para OCR (ligado na Sprint 04; nesta sprint vai para `concluido`).

### H3.3 — Armazenamento imutável e deduplicação `3 pts`
- **Então** o bucket `comprovantes` tem versionamento + Object Lock (modo *governance* em dev, *compliance* em produção) — atende RNF02.
- **Então** o worker calcula `sha256` e grava; **dado** um sha256 já existente no tenant, **então** o comprovante é marcado com aviso `possivel_duplicado` (não bloqueia — o usuário decide na revisão).
- **Então** o worker gera miniatura (primeira página do PDF via `pypdfium2`, ou imagem redimensionada) em WebP 320px em `thumbnails/`.
- **Então** o EXIF das imagens é removido da miniatura (privacidade: localização GPS).

### H3.4 — Status do lote `2 pts`
- **Quando** chamo `GET /uploads/batch/{id}/status`, **então** recebo o status de cada item e os agregados `{total, concluidos, com_erro, em_andamento}`.
- **Então** a resposta é servida de um cache Redis atualizado pelo worker (evita martelar o Postgres com polling a cada 2s), com fallback ao banco.

### H3.5 — Tela 1: upload em lote `5 pts`
- **Então** a tela tem área de drag-and-drop e botão de seleção, contador `Anexar Comprovantes (N/10)`.
- **Então** cada item mostra: miniatura local (via `URL.createObjectURL`) ou ícone de PDF, nome, tamanho, barra de progresso real (`XMLHttpRequest.upload.onprogress`) e estado: *na fila → enviando → validando → concluído / erro*.
- **Então** no máximo **4 uploads simultâneos** (fila no cliente).
- **Então** erros de formato/tamanho aparecem antes do envio, com texto explícito ("HEIC não suportado — converta para JPG").
- **Então** cada item tem ações remover (antes do envio) e tentar novamente (em erro — pede nova presigned URL via `POST /uploads/{id}/retry-url`).
- **Então** há progresso geral "X de N processados" e botões *Cancelar tudo* / *Continuar*.
- **Então** o usuário pode sair da tela; o processamento continua (não bloqueante — RNF01).

### H3.6 — Visualização segura do comprovante `1 pt`
- **Quando** chamo `GET /comprovantes/{id}/arquivo`, **então** recebo redirect `302` para presigned `GET` de 5 min com `response-content-disposition=attachment` (ou `inline` apenas para miniatura WebP gerada pelo sistema).

## 4. Tarefas técnicas

**Dados**
- [ ] Migração `0004_uploads`: `upload_batches`, `comprovantes` (com `storage_key`, `sha256`, `tamanho_bytes`, `nome_original`, status estendidos), RLS

**Backend**
- [ ] `services/storage.py`: interface `ObjectStorage` (`presign_put`, `presign_get`, `get_stream`, `move`), implementação boto3 compatível com MinIO/S3
- [ ] `services/upload_validation.py`: três camadas como funções puras testáveis sobre `bytes`
- [ ] `workers/tasks/validar_arquivo.py` (fila `validation`, timeout 60s)
- [ ] Cache de status do lote em Redis (hash `batch:{id}`)
- [ ] Configuração CORS do bucket MinIO para `PUT` do frontend

**Frontend**
- [ ] `features/upload/` — `UploadPage`, `useUploadQueue` (fila com concorrência 4, retry, cancelamento via `AbortController`)
- [ ] Polling do status com TanStack Query (`refetchInterval: 2000` enquanto houver itens em andamento)

## 5. Contrato de API

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/v1/uploads/batch` | Cria lote, retorna presigned URLs |
| POST | `/api/v1/uploads/{comprovante_id}/complete` | Confirma upload e enfileira validação |
| POST | `/api/v1/uploads/{comprovante_id}/retry-url` | Nova presigned URL para item com erro de envio |
| GET | `/api/v1/uploads/batch/{id}/status` | Status item a item + agregados |
| GET | `/api/v1/comprovantes/{id}/arquivo` | Redirect para download seguro |
| GET | `/api/v1/comprovantes/{id}/thumbnail` | Redirect para miniatura |

## 6. Estratégia de testes
- Unidade (validação): corpus de fixtures maliciosas — PDF com extensão `.png`, PNG renomeado para `.pdf`, PDF criptografado, PDF com JavaScript, zip-bomb/decompression bomb, arquivo truncado, arquivo vazio, polyglot PDF/JPEG.
- Integração: fluxo completo contra MinIO real (testcontainers): criar lote → PUT → complete → worker → status.
- Limites: 11 arquivos, 10 MB + 1 byte, total 60 MB + 1 byte.
- Frontend: `useUploadQueue` (concorrência, retry, cancelamento) com MSW; E2E enviando 10 arquivos.

## 7. Definition of Done específica
- [ ] Todo o corpus de fixtures maliciosas é rejeitado
- [ ] Nenhum arquivo passa pela API (verificado: payload máximo de `/uploads/*` é JSON)
- [ ] Upload de 10 arquivos de 5 MB conclui em < 30 s em rede local

## 8. Riscos e mitigação

| Risco | Mitigação |
|-------|-----------|
| Cliente não chama `/complete` (fechou a aba) | Job `maintenance` varre comprovantes em `enviando` > 30 min e verifica se o objeto existe (`HEAD`) |
| CORS/presigned difícil de depurar entre MinIO e S3 | Testes de integração contra MinIO e documentação da policy de bucket |
| Object Lock impede limpeza em dev | Modo *governance* em dev, com role de admin para bypass |

## 9. Entregável / demo
Arrastar 10 arquivos (incluindo um `.exe` renomeado para `.pdf` e um PDF de carnê com 3 páginas): 9 concluem, o falso é rejeitado com mensagem clara, o carnê mostra `3 páginas`.

## 10. Retrospectiva
_Preencher ao final da sprint._
