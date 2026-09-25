# Sprint 00 — Fundação do projeto

[← Índice de sprints](README.md) · Próxima: [Sprint 01 →](sprint-01.md)

| | |
|---|---|
| **Período** | 05/10 – 16/10/2026 |
| **Pontos** | 19 |
| **Fase do MVP** | Núcleo |

## 1. Objetivo
Ter um monorepo executável localmente com um comando, com API, worker, banco, fila, storage e frontend "hello world" conversando entre si, e CI bloqueando merges quebrados.

## 2. Requisitos cobertos
Nenhum RF diretamente — habilita todos. Prepara RNF03 (roles de banco) e RNF01 (infra de fila).

## 3. Histórias de usuário

### H0.1 — Estrutura do monorepo `3 pts`
**Como** desenvolvedor, **quero** um repositório organizado com padrões automáticos **para** não gastar tempo com formatação e estrutura.

- **Dado** um clone novo, **quando** executo `pre-commit install`, **então** Ruff, Prettier, ESLint e verificação de segredos (`gitleaks`) rodam a cada commit.
- **Dado** o repositório, **então** existem `backend/`, `web/`, `mobile/` (placeholder), `infra/`, `packages/api-client/`, `docs/`, `.editorconfig`, `.env.example`.

### H0.2 — Infraestrutura local com Docker Compose `3 pts`
- **Quando** executo `docker compose -f infra/docker-compose.yml up -d`, **então** Postgres 16, Redis 7 e o storage S3 (RustFS) sobem com healthchecks verdes.
- **Então** o Postgres já tem as extensões `pgcrypto`, `pg_trgm`, `btree_gist` e as roles `app_owner`, `app_user`, `app_api` criadas por script em `infra/postgres/init/`.
- **Então** o storage tem os buckets `comprovantes` (versionamento ligado) e `exports` criados por um container `storage-init`.

### H0.3 — Esqueleto da API `3 pts`
- **Quando** acesso `GET /api/v1/health`, **então** recebo `200` com status de Postgres, Redis e storage.
- **Então** a configuração vem de `pydantic-settings` com validação na inicialização (falha rápido se faltar variável).
- **Então** os logs são JSON (structlog) com `request_id` propagado via header `X-Request-ID`.

### H0.4 — Migrações e roles `3 pts`
- **Quando** executo `alembic upgrade head` como `app_owner`, **então** a migração inicial cria a tabela `tenants`, a função `set_updated_at()` e a função `app_current_tenant()`.
- **Então** `app_api` não é owner de nenhuma tabela e não possui `BYPASSRLS` (verificado por teste).
- **Então** `alembic downgrade base` executa sem erro.

### H0.5 — Esqueleto do frontend web `2 pts`
- **Quando** executo `pnpm dev` em `web/`, **então** abre um layout base (header, menu lateral, área de conteúdo) com React Router e TanStack Query configurados.
- **Então** a página inicial exibe o resultado de `/api/v1/health` (prova de integração e CORS).

### H0.6 — Worker Celery `2 pts`
- **Quando** o worker está no ar e chamo `POST /api/v1/_debug/ping-worker` (somente em `local`), **então** uma task `ping` é executada e o resultado aparece no log.
- **Então** as filas `validation`, `ocr`, `reports`, `maintenance` estão declaradas.

### H0.7 — Pipeline de CI `3 pts`
- **Dado** um PR, **então** o GitHub Actions executa: `ruff check`, `ruff format --check`, `mypy`, `pytest` (com Postgres como service), `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm build`.
- **Então** os jobs rodam apenas quando os caminhos correspondentes mudam (`backend/**`, `web/**`).
- **Então** o cache de `uv` e `pnpm` reduz o tempo do pipeline para menos de 5 minutos.

## 4. Tarefas técnicas

**Infra**
- [x] `infra/docker-compose.yml` com `postgres`, `redis`, `storage`, `storage-init`, `api`, `worker` (profiles `infra` e `app`)
- [x] `infra/postgres/init/01-extensions.sql`, `02-roles.sql`
- [x] `Makefile` com alvos `up`, `down`, `migrate`, `test`, `lint`, `fmt`

**Backend**
- [x] `uv init`; dependências: fastapi, uvicorn, sqlalchemy[asyncio], asyncpg, alembic, pydantic-settings, structlog, celery[redis], boto3, python-magic, pypdf, pillow
- [x] `app/core/config.py`, `app/core/logging.py`, `app/main.py` com middleware de `request_id`
- [x] `app/db/session.py` com engine assíncrona e *dependency* de sessão
- [x] `app/workers/celery_app.py` com roteamento de filas
- [x] Alembic configurado com `DATABASE_URL_OWNER` separado de `DATABASE_URL`

**Frontend**
- [x] Vite + React + TS strict; ESLint + Prettier; Vitest
- [x] `src/lib/api.ts` (fetch wrapper com base URL e tratamento de Problem Details)
- [x] Layout base e rotas placeholder (`/`, `/login`, `/lancamentos`)

**Docs**
- [x] Revisar `README.md` e `docs/convencoes.md` com os comandos reais

## 5. Contrato de API

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/v1/health` | Status dos componentes |
| POST | `/api/v1/_debug/ping-worker` | Apenas `local`; dispara task de teste |

## 6. Estratégia de testes
- `tests/test_health.py` (integração com Postgres real via testcontainers ou service do CI)
- `tests/test_roles.py`: consulta `pg_roles`/`pg_tables` e garante que `app_api` não é owner nem `BYPASSRLS`
- Vitest: smoke test do layout

## 7. Definition of Done específica
- [ ] `make up && make migrate && make test` funciona num clone limpo
- [ ] CI verde no primeiro PR
- [ ] Tempo de CI < 5 min

## 8. Riscos e mitigação

| Risco | Mitigação |
|-------|-----------|
| `python-magic` depende de `libmagic` do SO | Documentar no README e instalar no Dockerfile/CI (`apt-get install libmagic1`) |
| Configuração de roles errada torna RLS inócuo desde o início | Teste automatizado de roles (H0.4) |

## 9. Entregável / demo
Clone → `make up` → navegador mostra a página inicial com os três componentes "OK" vindos do `/health`.

## 10. Andamento

**Implementado (25/09/2026):** H0.1 a H0.7 — Definition of Done completa.

| Verificação | Resultado |
|-------------|-----------|
| Backend: ruff, ruff format, mypy strict | ✔ |
| Backend: pytest com Postgres real | ✔ 21 testes (inclui roles, RLS-ready e upgrade/downgrade de migrações) |
| Web: prettier, eslint, tsc, vitest (10 testes), build | ✔ |
| `make up` → Postgres, Redis e storage saudáveis; roles e extensões criadas; buckets criados | ✔ |
| `/health` com dependências reais → 200, três componentes OK | ✔ |
| API → Redis → worker: `ping-worker` executado pelo worker | ✔ (local e em containers) |
| `make up-app`: imagens de API e worker construídas, rodando como usuário sem privilégios | ✔ |
| CI verde no GitHub Actions / tempo < 5 min | ✔ primeira execução verde em ~1 min (backend 47 s, web 25 s) |

Decisões tomadas durante a implementação:
- TypeScript fixado em 6.x porque o typescript-eslint ainda não suporta o TypeScript 7.
- `/health` responde **503** (em vez de 200) quando algum componente falha, com o mesmo corpo — load balancers e monitores entendem o status sem ler o JSON; o frontend trata o 503 como dado.
- Bucket `comprovantes` criado já com Object Lock, pois o Object Lock só pode ser ligado na criação do bucket.
- **MinIO substituído por RustFS** no ambiente de desenvolvimento: a MinIO deixou de publicar imagens da edição comunitária (Docker Hub sem imagem, quay.io exige login). RustFS é S3-compatible, com versionamento e Object Lock verificados; os buckets são criados com o `aws-cli` oficial. Produção continua em AWS S3 — nenhum código depende do fornecedor.
- **Portas do host configuráveis** (`POSTGRES_PORT`, `REDIS_PORT`, `S3_PORT`, `S3_CONSOLE_PORT`), para conviver com outros projetos que já usem 5432/6379.
- Testes carregam o `.env` da raiz antes dos padrões — evita que apontem para o banco de outro projeto.

## 11. Retrospectiva
_Preencher ao final da sprint._
- O que funcionou:
- O que atrapalhou:
- Ação de melhoria:
