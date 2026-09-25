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
- [ ] Migração `0002_auth`: `tenants.slug`, `users`, `refresh_tokens`, policies
- [ ] Função `resolve_tenant(slug) RETURNS uuid SECURITY DEFINER` (única brecha controlada, usada só no login)
- [ ] `GRANT` mínimos para `app_user` (SELECT/INSERT/UPDATE/DELETE por tabela, sem DDL)

**Backend**
- [ ] `app/core/security.py`: hash Argon2id, emissão/validação JWT (PyJWT, HS256 em dev, chave via env; RS256 opcional em prod)
- [ ] `app/api/deps.py`: `get_current_user`, `get_tenant_session`, `require_role`
- [ ] `app/api/v1/auth.py`, `app/api/v1/users.py`
- [ ] Rate limit com `slowapi` + Redis
- [ ] CLI `seed`

**Frontend**
- [ ] `features/auth/` (LoginPage, `useAuth`, `AuthProvider`)
- [ ] Interceptor de refresh e `ProtectedRoute`

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

## 10. Retrospectiva
_Preencher ao final da sprint._
