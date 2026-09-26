"""Tags por tipo de conta nos lançamentos.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-26
"""

from collections.abc import Sequence

from alembic import op

from app.db.rls import disable_rls, enable_rls

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Cópia fixa (a migração não muda se a lista do app mudar depois).
TAGS_PADRAO = [
    "Recorrente",
    "Aquisição",
    "Serviços prestados",
    "Concessionárias",
    "Manutenção geral",
    "Despesas administrativas",
    "Materiais para manutenção",
    "Folha de pagamento",
]


def upgrade() -> None:
    op.execute("""
        CREATE TABLE tags (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            nome        VARCHAR(50) NOT NULL,
            ativo       BOOLEAN NOT NULL DEFAULT true,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    # "Recorrente" e "recorrente" são a mesma tag.
    op.execute("CREATE UNIQUE INDEX uq_tags_nome ON tags (tenant_id, lower(nome))")
    op.execute("""
        CREATE TRIGGER trg_tags_updated_at
            BEFORE UPDATE ON tags
            FOR EACH ROW EXECUTE FUNCTION set_updated_at()
    """)

    # tenant_id vem da sessão (o ORM grava só o par lançamento/tag); o RLS confere.
    op.execute("""
        CREATE TABLE lancamento_tags (
            tenant_id      UUID NOT NULL DEFAULT app_current_tenant()
                               REFERENCES tenants(id) ON DELETE CASCADE,
            lancamento_id  UUID NOT NULL REFERENCES lancamentos(id) ON DELETE CASCADE,
            tag_id         UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
            PRIMARY KEY (lancamento_id, tag_id)
        )
    """)
    op.execute("CREATE INDEX ix_lancamento_tags_tag ON lancamento_tags (tenant_id, tag_id)")

    for t in ("tags", "lancamento_tags"):
        enable_rls(op.execute, t)

    # Tags padrão nas empresas que já existem, cada uma no próprio tenant (RLS forçado).
    nomes = ", ".join("'" + n.replace("'", "''") + "'" for n in TAGS_PADRAO)
    op.execute(f"""
        DO $$
        DECLARE t uuid;
        BEGIN
            FOR t IN SELECT listar_tenants_ativos() LOOP
                PERFORM set_config('app.current_tenant', t::text, true);
                INSERT INTO tags (tenant_id, nome)
                SELECT t, n FROM unnest(ARRAY[{nomes}]) AS n
                ON CONFLICT DO NOTHING;
            END LOOP;
            PERFORM set_config('app.current_tenant', '', true);
        END $$
    """)


def downgrade() -> None:
    for t in ("lancamento_tags", "tags"):
        disable_rls(op.execute, t)
        op.execute(f"DROP TABLE {t}")
