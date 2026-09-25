"""Autenticação e multitenancy: usuários, refresh tokens e RLS.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-25
"""

from collections.abc import Sequence

from alembic import op

from app.db.rls import disable_rls, enable_rls

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE tenants
            ADD COLUMN slug VARCHAR(63) NOT NULL UNIQUE
                CHECK (slug ~ '^[a-z0-9]([a-z0-9-]*[a-z0-9])?$'),
            ADD COLUMN retencao_meses INT NOT NULL DEFAULT 60 CHECK (retencao_meses >= 60)
    """)

    op.execute("""
        CREATE TABLE users (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id        UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            nome             VARCHAR(255) NOT NULL,
            email            VARCHAR(255) NOT NULL CHECK (email = lower(email)),
            password_hash    TEXT NOT NULL,
            role             VARCHAR(20) NOT NULL
                CHECK (role IN ('admin','aprovador','colaborador')),
            nivel_aprovacao  SMALLINT NOT NULL DEFAULT 0 CHECK (nivel_aprovacao BETWEEN 0 AND 2),
            ativo            BOOLEAN NOT NULL DEFAULT true,
            ultimo_login_em  TIMESTAMPTZ,
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, email)
        )
    """)
    op.execute("""
        CREATE TRIGGER trg_users_updated_at
            BEFORE UPDATE ON users
            FOR EACH ROW EXECUTE FUNCTION set_updated_at()
    """)

    op.execute("""
        CREATE TABLE refresh_tokens (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash  CHAR(64) NOT NULL UNIQUE,
            family_id   UUID NOT NULL,
            expires_at  TIMESTAMPTZ NOT NULL,
            revoked_at  TIMESTAMPTZ,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ix_refresh_family ON refresh_tokens (tenant_id, family_id)")

    # --- RLS -----------------------------------------------------------------
    # tenants: a própria linha é "do tenant" quando id = tenant corrente.
    enable_rls(op.execute, "tenants", column="id")
    enable_rls(op.execute, "users")
    enable_rls(op.execute, "refresh_tokens")

    # Única brecha controlada: o login precisa descobrir o tenant pelo slug antes
    # de existir um tenant na sessão. A função roda como app_owner (SECURITY DEFINER),
    # que tem uma policy exclusiva de leitura em tenants, e devolve apenas o UUID.
    op.execute("""
        CREATE POLICY owner_resolve_tenant ON tenants
            FOR SELECT TO app_owner USING (true)
    """)
    op.execute("""
        CREATE FUNCTION resolve_tenant(p_slug text) RETURNS uuid
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
            SELECT id FROM tenants WHERE slug = lower(p_slug) AND ativo
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION resolve_tenant(text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION resolve_tenant(text) TO app_user")


def downgrade() -> None:
    op.execute("DROP FUNCTION resolve_tenant(text)")
    op.execute("DROP POLICY owner_resolve_tenant ON tenants")
    disable_rls(op.execute, "tenants")
    op.execute("DROP TABLE refresh_tokens")
    op.execute("DROP TABLE users")
    op.execute("ALTER TABLE tenants DROP COLUMN retencao_meses, DROP COLUMN slug")
