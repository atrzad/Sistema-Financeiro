"""Núcleo de domínio: fornecedores, cadastros auxiliares e lançamentos.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-25
"""

from collections.abc import Sequence

from alembic import op

from app.db.rls import disable_rls, enable_rls

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABELAS = ["suppliers", "categorias", "projetos", "centros_custo", "lancamentos"]


def _updated_at(table: str) -> None:
    op.execute(f"""
        CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION set_updated_at()
    """)


def upgrade() -> None:
    op.execute("""
        CREATE TABLE suppliers (
            id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id      UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            nome_fantasia  VARCHAR(255) NOT NULL,
            razao_social   VARCHAR(255),
            -- Somente dígitos/letras (CNPJ alfanumérico a partir de jul/2026).
            cnpj           CHAR(14) CHECK (cnpj ~ '^[0-9A-Z]{12}[0-9]{2}$'),
            created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at     TIMESTAMPTZ
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_suppliers_cnpj ON suppliers (tenant_id, cnpj)
            WHERE cnpj IS NOT NULL AND deleted_at IS NULL
    """)
    op.execute(
        "CREATE INDEX ix_suppliers_nome_trgm ON suppliers USING gin (nome_fantasia gin_trgm_ops)"
    )

    op.execute("""
        CREATE TABLE categorias (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            nome        VARCHAR(100) NOT NULL,
            ativo       BOOLEAN NOT NULL DEFAULT true,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, nome)
        )
    """)
    op.execute("""
        CREATE TABLE projetos (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            nome        VARCHAR(150) NOT NULL,
            ativo       BOOLEAN NOT NULL DEFAULT true,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, nome)
        )
    """)
    op.execute("""
        CREATE TABLE centros_custo (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            codigo      VARCHAR(30)  NOT NULL,
            nome        VARCHAR(150) NOT NULL,
            ativo       BOOLEAN NOT NULL DEFAULT true,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, codigo)
        )
    """)

    op.execute("""
        CREATE TABLE lancamentos (
            id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id                 UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            usuario_id                UUID NOT NULL REFERENCES users(id),
            supplier_id               UUID REFERENCES suppliers(id),
            categoria_id              UUID REFERENCES categorias(id),
            projeto_id                UUID REFERENCES projetos(id),
            centro_custo_id           UUID REFERENCES centros_custo(id),
            faixa_valor_id            UUID,  -- FK adicionada na Sprint 06
            descricao                 VARCHAR(500),
            valor                     NUMERIC(12,2) NOT NULL CHECK (valor > 0),
            forma_pagamento           VARCHAR(20) CHECK (forma_pagamento IN
                ('boleto','pix','cartao','dinheiro','transferencia','outro')),
            linha_digitavel           VARCHAR(60),
            data_emissao              DATE NOT NULL,
            data_pagamento_prevista   DATE,
            data_pagamento_efetiva    DATE,
            status                    VARCHAR(20) NOT NULL DEFAULT 'pendente'
                CHECK (status IN ('pendente','reagendado','pago','rejeitado')),
            status_aprovacao          VARCHAR(20) NOT NULL DEFAULT 'rascunho'
                CHECK (status_aprovacao IN ('rascunho','aguardando','aprovado','rejeitado')),
            nivel_aprovacao_exigido   SMALLINT NOT NULL DEFAULT 1,
            aprovado_por              UUID REFERENCES users(id),
            aprovado_em               TIMESTAMPTZ,
            version                   INT NOT NULL DEFAULT 1,
            created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at                TIMESTAMPTZ NOT NULL DEFAULT now(),
            deleted_at                TIMESTAMPTZ,
            CHECK (status <> 'pago' OR data_pagamento_efetiva IS NOT NULL)
        )
    """)
    op.execute("""
        CREATE INDEX ix_lanc_vencimento ON lancamentos (tenant_id, data_pagamento_prevista, id)
            WHERE deleted_at IS NULL
    """)
    op.execute("CREATE INDEX ix_lanc_supplier ON lancamentos (tenant_id, supplier_id)")
    op.execute("CREATE INDEX ix_lanc_usuario ON lancamentos (tenant_id, usuario_id)")
    op.execute("""
        CREATE INDEX ix_lanc_aprovacao
            ON lancamentos (tenant_id, status_aprovacao, nivel_aprovacao_exigido)
    """)

    for t in TABELAS:
        _updated_at(t)
        enable_rls(op.execute, t)

    # Status efetivo derivado (ADR 0004). security_invoker: a view respeita o RLS
    # de quem consulta, e não do dono da view.
    op.execute("""
        CREATE VIEW v_lancamentos WITH (security_invoker = true) AS
        SELECT l.*,
               CASE
                 WHEN l.status IN ('pago','rejeitado')            THEN l.status
                 WHEN l.data_pagamento_prevista < hoje_negocio()  THEN 'atrasado'
                 WHEN l.data_pagamento_prevista = hoje_negocio()  THEN 'vence_hoje'
                 ELSE l.status
               END AS status_efetivo,
               (l.data_pagamento_prevista - hoje_negocio()) AS dias_para_vencimento
        FROM lancamentos l
        WHERE l.deleted_at IS NULL
    """)


def downgrade() -> None:
    op.execute("DROP VIEW v_lancamentos")
    for t in reversed(TABELAS):
        disable_rls(op.execute, t)
        op.execute(f"DROP TABLE {t}")
