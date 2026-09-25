# Sprint 01 — Autenticação e multitenancy

[← Sprint 00](sprint-00.md) · [Índice](README.md) · [Sprint 02 →](sprint-02.md)

| | |
|---|---|
| **Período** | 19/10 – 30/10/2026 |
| **Pontos** | 21 |
| **Fase do MVP** | Núcleo |

## 1. Objetivo
Usuários de empresas diferentes fazem login e o banco garante, por RLS, que nenhum deles enxerga dados de outro tenant — comprovado por uma suíte automatizada que será obrigatória em todas as sprints seguintes.

## 2. Requisitos cobertos
RF10 · RNF03 · parte do item "Auth" da stack (JWT + refresh + RBAC)

## 3. Histórias de usuário

### H1.1 — Modelo de tenants e usuários `3 pts`
- **Então** existem as tabelas `tenants` (com `slug`), `users` (`UNIQUE (tenant_id, email)`, `password_hash`, `role`, `nivel_aprovacao`) e `refresh_tokens`, conforme [modelo de dados](../modelo-de-dados.md#3-ddl-de-referência).
- **Então** um comando `uv run python -m app.cli seed` cria dois tenants de demonstração (`acme`, `globex`) com um usuário de cada papel.
- **Então** senhas são armazenadas com Argon2id (`argon2-cffi`).

### H1.2 — Login `3 pts`
**Como** colaborador, **quero** entrar com empresa, e-mail e senha **para** acessar meus lançamentos.
- **Dado** credenciais válidas, **quando** chamo `POST /auth/login {tenant_slug, email, senha}`, **então** recebo `access_token` (JWT, 15 min) com claims `sub`, `tid`, `role`, `nivel` e um `refresh_token` em cookie `HttpOnly; Secure; SameSite=Strict`.
- **Dado** credenciais inválidas, **então** recebo `401` com mensagem genérica (não revela se o e-mail existe) e o tempo de resposta é equivalente ao do caso válido.
- **Dado** 5 falhas em 15 min para o mesmo e-mail/IP, **então** recebo `429`.

### H1.3 — Refresh token com rotação `2 pts`
- **Quando** chamo `POST /auth/refresh`, **então** o refresh atual é revogado e um novo da mesma `family_id` é emitido.
- **Dado** que um refresh já revogado é reutilizado, **então** toda a família é revogada (detecção de roubo de token) e recebo `401`.
- **Quando** chamo `POST /auth/logout`, **então** o refresh é revogado e o cookie limpo.

### H1.4 — Contexto de tenant por transação `3 pts`
- **Dado** um request autenticado, **então** a dependência `get_tenant_session()` abre transação e executa `SET LOCAL app.current_tenant = :tid` antes de qualquer query.
- **Dado** uma task Celery, **então** ela recebe `tenant_id` explicitamente e usa o mesmo `tenant_context(tenant_id)`.
- **Então** é impossível obter uma sessão de negócio sem tenant (a dependência sem tenant só existe para `/auth/login` e `/health`).

### H1.5 — RLS em todas as tabelas + suíte cross-tenant `5 pts`
**Como** responsável pela segurança, **quero** que o banco bloqueie acesso entre empresas mesmo se a aplicação errar.
- **Então** `tenants`, `users`, `refresh_tokens` têm `ENABLE` + `FORCE ROW LEVEL SECURITY` e policy `tenant_isolation`.
- **Então** existe o helper de migração `enable_rls(table)` usado em todas as tabelas futuras.
- **Então** um teste verifica em `pg_class` que **toda** tabela com coluna `tenant_id` tem `relrowsecurity = true` e `relforcerowsecurity = true` (quebra o CI se alguém esquecer).
- **Dado** o usuário do tenant A, **quando** consulta qualquer recurso, **então** vê zero linhas do tenant B; **quando** tenta inserir com `tenant_id = B`, **então** falha.
- **Dado** uma sessão sem `SET LOCAL`, **então** todas as consultas retornam zero linhas.
- **Então** a suíte `tests/security/test_cross_tenant.py` é parametrizada por endpoint, para que novos endpoints sejam adicionados com uma linha.

### H1.6 — RBAC e gestão de usuários `3 pts`
**Como** admin, **quero** convidar e desativar usuários da minha empresa.
- **Então** a dependência `require_role(*roles)` retorna `403` para papéis não autorizados.
- **Dado** um admin, **quando** chama `POST /users`, **então** cria usuário no próprio tenant (o `tenant_id` vem do token, nunca do corpo).
- **Dado** um usuário desativado, **então** login e refresh são negados.
- **Dado** um colaborador, **quando** chama `/users`, **então** recebe `403`.

### H1.7 — Tela de login e sessão no web `2 pts`
- **Então** a tela `/login` tem campos empresa, e-mail, senha, com validação Zod e mensagens em pt-BR.
- **Então** o `api.ts` renova o access token automaticamente em `401` (uma única vez, com fila de requests pendentes) e redireciona para `/login` se o refresh falhar.
- **Então** o access token fica só em memória (não em `localStorage`).
- **Então** rotas privadas usam um `ProtectedRoute` que verifica papel.

## 4. Tarefas técnicas

**Dados**
- [x] Migração `0002_auth`: `tenants.slug`, `users`, `refresh_tokens`, policies
- [x] Função `resolve_tenant(slug) RETURNS uuid SECURITY DEFINER` (única brecha controlada, usada só no login)
- [x] `GRANT` mínimos para `app_user` (SELECT/INSERT/UPDATE/DELETE por tabela, sem DDL)

**Backend**
- [x] `app/core/security.py`: hash Argon2id, emissão/validação JWT (PyJWT, HS256 em dev, chave via env; RS256 opcional em prod)
- [x] `app/api/deps.py`: `get_current_user`, `get_tenant_session`, `require_role`
- [x] `app/api/v1/auth.py`, `app/api/v1/users.py`
- [x] Rate limit com `slowapi` + Redis
- [x] CLI `seed`

**Frontend**
- [x] `features/auth/` (LoginPage, `useAuth`, `AuthProvider`)
- [x] Interceptor de refresh e `ProtectedRoute`

## 5. Contrato de API

| Método | Rota | Papel | Descrição |
|--------|------|-------|-----------|
| POST | `/api/v1/auth/login` | público | Retorna access token + cookie de refresh |
| POST | `/api/v1/auth/refresh` | cookie | Rotação de refresh |
| POST | `/api/v1/auth/logout` | autenticado | Revoga refresh |
| GET | `/api/v1/me` | autenticado | Dados do usuário e tenant |
| GET | `/api/v1/users` | admin | Lista usuários do tenant |
| POST | `/api/v1/users` | admin | Cria usuário |
| PATCH | `/api/v1/users/{id}` | admin | Altera papel/nível/ativo |

## 6. Estratégia de testes
- Unidade: hash/verify de senha, emissão/expiração de JWT, detecção de reuso de refresh.
- Integração: fluxo login → me → refresh → logout; usuário desativado.
- Segurança: suíte cross-tenant (H1.5) + teste de metadados RLS.
- E2E (Playwright): login com sucesso e com erro.

## 7. Definition of Done específica
- [ ] Teste de metadados RLS no CI
- [ ] Nenhuma query de negócio fora de `get_tenant_session()` (verificado por revisão + teste de "sem SET LOCAL = zero linhas")

## 8. Riscos e mitigação

| Risco | Mitigação |
|-------|-----------|
| Login precisa ler `users` antes de conhecer o tenant | `resolve_tenant(slug)` `SECURITY DEFINER` retorna só o UUID; a leitura de `users` já ocorre com `SET LOCAL` |
| Pool de conexões reaproveitar tenant de outra request | Uso exclusivo de `SET LOCAL` (escopo de transação); teste que faz duas requests seguidas de tenants diferentes na mesma conexão |

## 9. Entregável / demo
Login como `colaborador@acme` e `colaborador@globex`; demonstrar no `psql` (como `app_api`) que sem `SET LOCAL` nada aparece e com o tenant de um nada do outro aparece.

## 10. Andamento

**Implementado (25/09/2026):** H1.1 a H1.7.

| Verificação | Resultado |
|-------------|-----------|
| Backend: ruff, mypy strict | ✔ |
| Backend: pytest com Postgres real | ✔ 66 testes — login, refresh com rotação e detecção de reuso, logout, bloqueio após 5 falhas, RBAC, gestão de usuários, RLS (metadados, isolamento, escrita cruzada, vazamento entre transações na mesma conexão) |
| Web: vitest | ✔ 27 testes — login, rotas protegidas, renovação automática (single-flight), layout por perfil |
| Ponta a ponta contra a API em container | ✔ login, cookie `HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth`, refresh, roubo de token derruba a sessão, 403 para colaborador, 429 após 5 falhas |
| E2E Playwright | ⏳ adiado — coberto por testes de componente + roteiro ponta a ponta via HTTP; Playwright entra quando houver fluxo de negócio (Sprint 02) |

Decisões tomadas durante a implementação:
- **Refresh token no formato `<tenant_id>.<aleatório>`**: o tenant (não secreto) permite abrir a transação com `SET LOCAL` antes de consultar `refresh_tokens` sob RLS, sem precisar de outra função `SECURITY DEFINER`. No banco fica só o SHA-256.
- **`resolve_tenant(slug)`** roda como `app_owner` (dono das tabelas); como o RLS é forçado também para o dono, foi criada uma policy exclusiva de leitura em `tenants` para `app_owner`. `app_api` continua sem enxergar outras empresas.
- **Mensagem única para credencial inválida** (empresa, e-mail ou senha) e verificação de hash "falsa" quando o usuário não existe, para não revelar cadastros pelo tempo de resposta.
- **Admin não pode se desativar nem remover o próprio papel de admin** (evita empresa sem administrador). Desativar um usuário revoga todas as sessões dele na hora.
- **Colaborador sempre com nível 0; aprovador com nível 1 ou 2** — validado na API e na tela.
- **Tela de Usuários** (admin) adicionada na web, além da API prevista, para permitir testar a gestão de usuários pela interface.
- **Banco de testes separado (`financeiro_test`)**: a suíte limpa tabelas entre testes e estava apagando os dados de desenvolvimento.
- **Erros no formato Problem Details (RFC 9457)** implementados globalmente, inclusive para erros de validação (`errors: [{campo, erro}]`).

## 11. Retrospectiva
_Preencher ao final da sprint._
