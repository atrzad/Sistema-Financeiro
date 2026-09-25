"""Quebra o CI se alguma tabela com tenant_id ficar sem RLS forçado (H1.5)."""

from sqlalchemy import text

from app.db.session import get_engine

SQL = """
SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
       EXISTS (SELECT 1 FROM pg_policy p WHERE p.polrelid = c.oid) AS tem_policy
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = 'public'
WHERE c.relkind = 'r'
  AND (c.relname = 'tenants' OR EXISTS (
        SELECT 1 FROM pg_attribute a
        WHERE a.attrelid = c.oid AND a.attname = 'tenant_id' AND NOT a.attisdropped))
ORDER BY 1
"""


async def test_toda_tabela_multitenant_tem_rls_forcado(database: None) -> None:
    async with get_engine().connect() as conn:
        rows = (await conn.execute(text(SQL))).all()

    assert rows, "nenhuma tabela multitenant encontrada"
    sem_rls = [r.relname for r in rows if not (r.relrowsecurity and r.relforcerowsecurity)]
    sem_policy = [r.relname for r in rows if not r.tem_policy]
    assert sem_rls == [], f"tabelas sem RLS forçado: {sem_rls}"
    assert sem_policy == [], f"tabelas sem policy: {sem_policy}"
    assert {"tenants", "users", "refresh_tokens"} <= {r.relname for r in rows}
