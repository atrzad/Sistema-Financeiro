# ADR 0002 — Multitenancy com banco compartilhado e Row Level Security

- **Status:** aceito
- **Data:** 2026-09-25

## Contexto
RF10 exige isolamento de dados entre empresas. Opções: banco por tenant, schema por tenant, ou tabelas compartilhadas com `tenant_id`. O volume esperado no MVP é de dezenas a poucas centenas de tenants.

## Decisão
Tabelas compartilhadas com coluna `tenant_id` em todas as entidades, com **duas barreiras**:

1. Filtro explícito de `tenant_id` nos repositórios da aplicação.
2. **RLS** com `ENABLE` + `FORCE ROW LEVEL SECURITY` e policy baseada em `current_setting('app.current_tenant')`.

Regras operacionais:
- A aplicação conecta como `app_api` (membro de `app_user`), **nunca** como owner/superuser.
- O tenant é definido por transação com `SET LOCAL` (compatível com PgBouncer em *transaction pooling*); `SET SESSION` é proibido.
- Migrações rodam como `app_owner`.
- Suíte de testes cross-tenant obrigatória para todo endpoint.

## Consequências
- (+) Operação simples (um banco, uma migração).
- (+) Um bug de filtro na aplicação não vaza dados — o banco retorna zero linhas.
- (−) Toda sessão precisa passar pelo `tenant_context()`; código que esquecer retorna vazio (falha segura, mas pode confundir no debug).
- (−) Consultas cross-tenant (métricas globais de operação) exigem role dedicada e auditada, fora do escopo do MVP.
