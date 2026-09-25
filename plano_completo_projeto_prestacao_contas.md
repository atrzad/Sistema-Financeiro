# Sistema de Lançamento e Prestação de Contas com Scanner Embutido
### Documento Consolidado de Planejamento

## 1. Visão Geral
Sistema para captura de comprovantes (boletos, recibos, notas) via scanner/câmera ou upload de arquivo, extração automática via OCR, organização automática de lançamentos por faixa de valor e por data de vencimento, controle de fornecedor (nome fantasia), pagamento de boletos e geração de relatórios de prestação de contas.

Contexto de mercado: o setor de travel & expense management deve atingir US$ 10,69 bi até 2030 (CAGR 16,9%), com padrões de arquitetura maduros e diversos provedores de OCR de recibos/boletos (Veryfi, Mindee, Taggun, Tabscanner, Invoice Data Extraction).

## 2. Stack Tecnológica
- **Backend:** FastAPI (Python) + Pydantic
- **Banco de dados:** PostgreSQL (RLS nativo, JSONB para payload OCR)
- **Fila assíncrona:** Celery + Redis
- **Storage:** S3-compatible (MinIO self-hosted ou AWS S3), acesso via presigned URLs
- **OCR:** Veryfi, Mindee ou Taggun em produção (suportam PDF multi-página + imagem nativamente); Tesseract/PaddleOCR/ML Kit local para prototipagem
- **Frontend web:** React + TypeScript + Vite
- **App mobile/scanner:** React Native ou Kotlin nativo com CameraX + ML Kit Document Scanner
- **Auth:** JWT + refresh token, RBAC (admin, aprovador, colaborador)
- **Validação de arquivo:** python-magic (magic bytes) + pypdf/Pillow (parsing real)

## 3. Levantamento de Requisitos

### Requisitos Funcionais
- RF01: Captura via câmera (scanner embutido) ou upload de imagem/PDF, até 10 documentos simultâneos
- RF02: Extração automática de nome fantasia, CNPJ, data de emissão, data de vencimento, valor total, forma de pagamento, itens
- RF03: Classificação automática por faixa de valor (configurável) e reorganização automática por data de vencimento
- RF04: Edição manual dos campos extraídos antes de confirmar
- RF05: Vínculo de lançamentos a relatórios de prestação de contas (por período/projeto/centro de custo)
- RF06: Fluxo de aprovação (colaborador → aprovador)
- RF07: Exportação de relatório em PDF/Excel com comprovantes anexados
- RF08: Dashboard com totais por fornecedor, faixa de valor e status de pagamento
- RF09: Ação de pagamento de boleto com duas opções: "paguei hoje" ou "selecionar outro dia" (reagendar)
- RF10: Multiempresa/multiusuário com isolamento de dados por tenant
- RF11: Aceitar upload em PDF (multi-página) e imagem (JPG/JPEG/PNG)

### Requisitos Não Funcionais
- RNF01: Upload e OCR assíncronos; tela de progresso item a item, não bloqueante
- RNF02: Armazenamento imutável da imagem/PDF original (auditoria)
- RNF03: Isolamento via Row Level Security no banco (defesa em profundidade, além do filtro na aplicação)
- RNF04: Retenção configurável de dados (LGPD)
- RNF05: Medição de acurácia do OCR com dados reais próprios (papel térmico degrada muito a acurácia real vs. benchmark)
- RNF06: Retry automático em falha do provedor de OCR, por arquivo individual
- RNF07: Validação de upload em 3 camadas: extensão (allowlist), magic bytes, parsing real do arquivo
- RNF08: Limite de tamanho por arquivo (~10 MB) e por lote (~60 MB para 10 arquivos)

## 4. Regras de Negócio

**Faixas de valor:** configuráveis por tenant (ex.: até R$50 micro, R$50-300 pequeno, R$300-1.500 médio, acima de R$1.500 alto — exige aprovação de segundo nível). Campo `faixa_valor_id` recalculado sempre que o valor mudar.

**Nome fantasia:** tabela `suppliers` separada de razão social/CNPJ, com fuzzy matching contra o texto extraído pelo OCR para evitar duplicidade de cadastro.

**Datas:** `data_emissao` (quando ocorreu a despesa) e `data_pagamento_prevista` (vencimento) são campos distintos de `data_pagamento_efetiva` (quando foi realmente pago). Status (pago/pendente/atrasado) é derivado comparando a data prevista com a data atual — nunca fixo.

**Confiança do OCR:** cada campo extraído carrega score de confiança; abaixo de 80% força revisão manual obrigatória.

**Aprovação por faixa:** lançamentos "altos" exigem aprovador com papel específico e auditoria completa (quem aprovou, quando, edições pós-OCR).

**Pagamento de boleto:** ao clicar em "Pagar", duas ações possíveis:
- *Paguei hoje:* confirma imediatamente, `status = 'pago'`, `data_pagamento_efetiva = hoje`, registra evento no histórico.
- *Selecionar outro dia:* abre date picker (bloqueia datas passadas), atualiza `data_pagamento_prevista`, mantém `status = 'pendente'/'reagendado'`, registra evento no histórico.
Toda mudança de data de pagamento gera um registro append-only em `pagamento_eventos` — nunca sobrescreve sem rastro, pois isso é necessário para auditoria de prestação de contas.

**Formatos de arquivo:** aceitar `.pdf`, `.jpg`, `.jpeg`, `.png` como base obrigatória; `.heic`/`.webp` opcionais conforme suporte do provedor de OCR. PDFs de boleto podem ter múltiplas páginas (carnê) — o campo `total_paginas` no comprovante reflete isso, e o provedor de OCR escolhido deve suportar PDF multi-página nativamente.

## 5. Wireframes (Descrição de Telas)

### Tela 1 — Upload em Lote (até 10 documentos)
Fila de arquivos com item individual (miniatura, nome, tamanho, barra de progresso real, estado textual: na fila / enviando / processando OCR / concluído / erro), ação de remover/retry por item, progresso geral "X de 10 processados", drag-and-drop ou seleção manual, ícone diferenciado para PDF vs. imagem, mensagem de erro explícita para formato não suportado.

```
Anexar Comprovantes (0/10)
[ Arraste arquivos aqui ou clique ]
☐ boleto_luz.pdf        ▓▓▓▓▓▓░░░  enviando
☐ nota_mercado.jpg       ▓▓▓▓▓▓▓▓▓  concluído
☐ recibo_internet.png    ░░░░░░░░░  na fila
☐ boleto_agua.pdf        ⚠ erro — [tentar de novo]
Progresso geral: 3 de 10 processados
[Cancelar tudo]  [Continuar]
```

### Tela 2 — Loading/Processamento
Status em etapas (não spinner genérico), processamento em background não bloqueante, notificação ao concluir, resultado final já ordenado por `data_pagamento_prevista` ascendente.

```
Organizando seus documentos
✔ Enviando arquivos        (10/10)
⏳ Escaneando via OCR       (6/10)
    Padaria Central — extraindo dados...
⏳ Organizando por vencimento
```

### Tela 3 — Revisão do OCR
Formulário pré-preenchido com indicador de confiança por campo (verde/amarelo/vermelho), miniatura da imagem/PDF ao lado para conferência.

### Tela 4 — Lista de Documentos / Boletos
Agrupável por faixa de valor, categoria, fornecedor ou status; ordenação padrão por vencimento ascendente; filtros (Todos, Pendentes, Atrasados, Pagos); badge colorido de urgência (vencido, vence hoje, vence em N dias, pago).

```
Meus Boletos
[Todos] [Pendentes] [Atrasados] [Pagos]
🔴 Energia Elétrica S.A. — vence hoje — R$ 245,90   [Pagar]
🟡 Padaria Central — vence em 3 dias — R$ 38,50     [Pagar]
🟢 Provedor Internet — pago em 20/09 — R$ 99,90
```

### Tela 5 — Modal de Pagamento
Duas opções diretas ao clicar em "Pagar":

```
Energia Elétrica S.A. — R$ 245,90
[ 📅 Selecionar outro dia ]
[ ✔ Paguei hoje ]
[Cancelar]
```

### Tela 6 — Relatório de Prestação de Contas
Agrupamento de lançamentos, total consolidado, gráfico por categoria, exportação PDF/Excel com miniaturas dos comprovantes.

### Tela 7 — Dashboard
Cards de resumo (total do mês, pendente, atrasado), gráfico por faixa de valor, ranking de fornecedores recorrentes.

### Tela 8 — Aprovação (gestor)
Fila de pendências, aprovar/rejeitar com justificativa obrigatória na rejeição.

## 6. Modelagem de Banco de Dados (PostgreSQL)

```sql
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    email VARCHAR(255) UNIQUE NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('admin','aprovador','colaborador')),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE suppliers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    nome_fantasia VARCHAR(255) NOT NULL,
    razao_social VARCHAR(255),
    cnpj VARCHAR(18),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE categorias (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    nome VARCHAR(100) NOT NULL
);

CREATE TABLE faixas_valor (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    nome VARCHAR(50) NOT NULL,
    valor_min NUMERIC(12,2) NOT NULL,
    valor_max NUMERIC(12,2)
);

CREATE TABLE upload_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    usuario_id UUID NOT NULL REFERENCES users(id),
    total_arquivos INT NOT NULL,
    concluidos INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE comprovantes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    lancamento_id UUID,
    upload_batch_id UUID REFERENCES upload_batches(id),
    storage_url TEXT NOT NULL,
    mime_type VARCHAR(50) NOT NULL,
    extensao_original VARCHAR(10),
    total_paginas INT DEFAULT 1,
    status_processamento VARCHAR(20) DEFAULT 'na_fila'
        CHECK (status_processamento IN
        ('na_fila','enviando','processando_ocr','concluido','erro')),
    ocr_raw_payload JSONB,
    ocr_confidence JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE lancamentos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    usuario_id UUID NOT NULL REFERENCES users(id),
    supplier_id UUID REFERENCES suppliers(id),
    categoria_id UUID REFERENCES categorias(id),
    faixa_valor_id UUID REFERENCES faixas_valor(id),
    valor NUMERIC(12,2) NOT NULL,
    data_emissao DATE NOT NULL,
    data_pagamento_prevista DATE,
    data_pagamento_efetiva DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'pendente'
        CHECK (status IN ('pendente','pago','atrasado','reagendado','rejeitado')),
    aprovado_por UUID REFERENCES users(id),
    aprovado_em TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE comprovantes
    ADD CONSTRAINT fk_lancamento FOREIGN KEY (lancamento_id) REFERENCES lancamentos(id);

CREATE TABLE pagamento_eventos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    lancamento_id UUID NOT NULL REFERENCES lancamentos(id),
    usuario_id UUID NOT NULL REFERENCES users(id),
    tipo_evento VARCHAR(20) NOT NULL
        CHECK (tipo_evento IN ('pago_hoje','reagendado','pago_atrasado')),
    data_anterior DATE,
    data_nova DATE,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE relatorios_prestacao (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    usuario_id UUID NOT NULL REFERENCES users(id),
    titulo VARCHAR(255),
    periodo_inicio DATE,
    periodo_fim DATE,
    total NUMERIC(14,2),
    status VARCHAR(20) DEFAULT 'aberto',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE relatorio_lancamentos (
    relatorio_id UUID REFERENCES relatorios_prestacao(id),
    lancamento_id UUID REFERENCES lancamentos(id),
    PRIMARY KEY (relatorio_id, lancamento_id)
);
```

## 7. Row Level Security (RLS)

```sql
CREATE ROLE app_user NOLOGIN;

ALTER TABLE lancamentos ENABLE ROW LEVEL SECURITY;
ALTER TABLE lancamentos FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_lancamentos ON lancamentos
    USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid);

-- Repetir ENABLE/FORCE/POLICY para: comprovantes, suppliers, categorias,
-- faixas_valor, upload_batches, pagamento_eventos,
-- relatorios_prestacao, relatorio_lancamentos, users
```

Contexto por transação no backend:
```sql
BEGIN;
SET LOCAL app.current_tenant = 'uuid-do-tenant-autenticado';
-- queries normais
COMMIT;
```

Boas práticas:
- Nunca conectar a aplicação como superuser/owner (sempre ignoram RLS)
- Usar `SET LOCAL`, nunca `SET SESSION`, se usar PgBouncer em modo transaction pooling
- RLS é defesa em profundidade — manter filtro explícito de `tenant_id` também na aplicação
- Testar com role de produção real: usuário de outro tenant deve ver zero linhas

## 8. Fluxo de Upload em Lote + OCR

1. Frontend seleciona até 10 arquivos (PDF ou imagem) → `POST /uploads/batch` com metadados
2. Backend responde com presigned URL por arquivo + `upload_batch_id`
3. Frontend faz upload direto ao storage em paralelo (limite de 3-4 simultâneos)
4. A cada upload concluído, `POST /uploads/{id}/complete` dispara validação (magic bytes + parsing) e job Celery de OCR
5. Backend extrai nome fantasia, CNPJ, datas, valor; grava em `ocr_raw_payload` e `ocr_confidence`
6. Frontend faz polling/WebSocket em `GET /uploads/batch/{id}/status` para atualizar a UI item a item
7. Ao concluir, lista final é reorganizada automaticamente por `data_pagamento_prevista` ascendente

## 9. Fluxo de Pagamento de Boleto

```
POST /lancamentos/{id}/pagamento
Body: { "tipo": "pago_hoje" }
  ou
Body: { "tipo": "reagendado", "nova_data": "2026-10-05" }
```
- `pago_hoje`: `status = 'pago'`, `data_pagamento_efetiva = hoje`, grava evento em `pagamento_eventos`
- `reagendado`: valida `nova_data >= hoje`, atualiza `data_pagamento_prevista`, `status = 'reagendado'`, grava evento em `pagamento_eventos`

## 10. Validação de Upload (Segurança)

Três camadas obrigatórias no backend, nunca confiar apenas na extensão do arquivo:
1. **Allowlist de extensão:** `.pdf`, `.jpg`, `.jpeg`, `.png`
2. **Magic bytes:** checar assinatura real do arquivo (`python-magic`), independente do `Content-Type` enviado pelo cliente
3. **Parsing real:** abrir com `pypdf` (PDF) ou `Pillow` (imagem), rejeitando arquivos que não parseiem corretamente

Outras regras: renomear arquivo com UUID no storage (nunca usar nome do cliente), limite de 10 MB por arquivo e ~60 MB por lote, bucket separado sem permissão de execução, servir com `Content-Disposition: attachment`.

## 11. Roadmap MVP

1. **Núcleo:** CRUD manual + upload sem OCR, auth + RLS básico
2. **Upload e OCR:** tela de upload em lote (10 arquivos, PDF+imagem), fila assíncrona, tela de progresso, tela de revisão do OCR
3. **Organização automática:** faixas de valor, matching de fornecedor, reorganização por vencimento, dashboard
4. **Pagamento e Prestação de Contas:** ação de pagar boleto (hoje/reagendar) com histórico, relatórios agrupados, exportação, fluxo de aprovação multi-nível
</content>