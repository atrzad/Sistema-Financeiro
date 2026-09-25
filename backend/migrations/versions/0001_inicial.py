"""Estrutura inicial: funções utilitárias e tabela de tenants.

Revision ID: 0001
Revises:
Create Date: 2026-09-25
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Mantém updated_at correto em qualquer UPDATE.
    op.execute("""
        CREATE FUNCTION set_updated_at() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at := now();
            RETURN NEW;
        END;
        $$
    """)

    # Tenant da transação corrente, definido por SET LOCAL app.current_tenant (ADR 0002).
    # Sem SET LOCAL retorna NULL, e as policies de RLS não casam nenhuma linha.
    op.execute("""
        CREATE FUNCTION app_current_tenant() RETURNS uuid
        LANGUAGE sql STABLE AS $$
            SELECT nullif(current_setting('app.current_tenant', true), '')::uuid
        $$
    """)

    # "Hoje" no fuso do negócio, independente do fuso do servidor (ADR 0004).
    op.execute("""
        CREATE FUNCTION hoje_negocio() RETURNS date
        LANGUAGE sql STABLE AS $$
            SELECT (now() AT TIME ZONE 'America/Sao_Paulo')::date
        $$
    """)

    op.execute("""
        CREATE TABLE tenants (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            nome        VARCHAR(255) NOT NULL,
            ativo       BOOLEAN NOT NULL DEFAULT true,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TRIGGER trg_tenants_updated_at
            BEFORE UPDATE ON tenants
            FOR EACH ROW EXECUTE FUNCTION set_updated_at()
    """)


def downgrade() -> None:
    op.execute("DROP TABLE tenants")
    op.execute("DROP FUNCTION hoje_negocio()")
    op.execute("DROP FUNCTION app_current_tenant()")
    op.execute("DROP FUNCTION set_updated_at()")
