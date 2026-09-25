"""Helpers de Row Level Security para as migrações (ADR 0002).

Toda tabela com `tenant_id` DEVE passar por `enable_rls()`. Um teste de
metadados (tests/security/test_rls_metadata.py) quebra o CI se alguma esquecer.
"""

from collections.abc import Callable

POLICY = "tenant_isolation"


def enable_rls_sql(table: str, column: str = "tenant_id") -> list[str]:
    return [
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY",
        f"""CREATE POLICY {POLICY} ON {table}
            USING ({column} = app_current_tenant())
            WITH CHECK ({column} = app_current_tenant())""",
    ]


def disable_rls_sql(table: str) -> list[str]:
    return [
        f"DROP POLICY IF EXISTS {POLICY} ON {table}",
        f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY",
        f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY",
    ]


def enable_rls(execute: Callable[[str], object], table: str, column: str = "tenant_id") -> None:
    for stmt in enable_rls_sql(table, column):
        execute(stmt)


def disable_rls(execute: Callable[[str], object], table: str) -> None:
    for stmt in disable_rls_sql(table):
        execute(stmt)
