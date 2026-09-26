"""Upload em lote: lotes e comprovantes (Sprint 03).

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-25
"""

from collections.abc import Sequence

from alembic import op

from app.db.rls import disable_rls, enable_rls

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE upload_batches (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            usuario_id      UUID NOT NULL REFERENCES users(id),
            total_arquivos  INT NOT NULL CHECK (total_arquivos BETWEEN 1 AND 10),
            tamanho_total   BIGINT NOT NULL CHECK (tamanho_total BETWEEN 1 AND 62914560),
            origem          VARCHAR(10) NOT NULL DEFAULT 'web' CHECK (origem IN ('web','mobile')),
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ix_batches_usuario ON upload_batches (tenant_id, usuario_id)")

    op.execute("""
        CREATE TABLE comprovantes (
            id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id             UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            usuario_id            UUID NOT NULL REFERENCES users(id),
            upload_batch_id       UUID REFERENCES upload_batches(id),
            lancamento_id         UUID REFERENCES lancamentos(id),
            storage_key           TEXT NOT NULL UNIQUE,
            thumbnail_key         TEXT,
            nome_original         VARCHAR(255) NOT NULL,
            mime_type             VARCHAR(50) NOT NULL
                CHECK (mime_type IN ('application/pdf','image/jpeg','image/png')),
            extensao_original     VARCHAR(10) NOT NULL,
            tamanho_bytes         BIGINT NOT NULL CHECK (tamanho_bytes BETWEEN 1 AND 10485760),
            sha256                CHAR(64),
            possivel_duplicado    BOOLEAN NOT NULL DEFAULT false,
            total_paginas         INT NOT NULL DEFAULT 1 CHECK (total_paginas >= 1),
            status_processamento  VARCHAR(20) NOT NULL DEFAULT 'enviando'
                CHECK (status_processamento IN ('enviando','validando','processando_ocr',
                       'aguardando_revisao','concluido','erro')),
            erro_msg              TEXT,
            imutavel              BOOLEAN NOT NULL DEFAULT false,
            tentativas_ocr        SMALLINT NOT NULL DEFAULT 0,
            ocr_provider          VARCHAR(30),
            ocr_raw_payload       JSONB,
            ocr_confidence        JSONB,
            created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ix_comp_batch ON comprovantes (upload_batch_id)")
    op.execute("CREATE INDEX ix_comp_sha ON comprovantes (tenant_id, sha256)")
    op.execute("CREATE INDEX ix_comp_status ON comprovantes (status_processamento, created_at)")
    op.execute("""
        CREATE TRIGGER trg_comprovantes_updated_at
            BEFORE UPDATE ON comprovantes
            FOR EACH ROW EXECUTE FUNCTION set_updated_at()
    """)

    enable_rls(op.execute, "upload_batches")
    enable_rls(op.execute, "comprovantes")

    # Rotinas de manutenção (workers) percorrem as empresas e processam cada uma
    # com SET LOCAL do próprio tenant — nunca com uma role que ignore o RLS.
    op.execute("""
        CREATE FUNCTION listar_tenants_ativos() RETURNS SETOF uuid
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$ SELECT id FROM tenants WHERE ativo ORDER BY created_at $$
    """)
    op.execute("REVOKE ALL ON FUNCTION listar_tenants_ativos() FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION listar_tenants_ativos() TO app_user")


def downgrade() -> None:
    op.execute("DROP FUNCTION listar_tenants_ativos()")
    disable_rls(op.execute, "comprovantes")
    disable_rls(op.execute, "upload_batches")
    op.execute("DROP TABLE comprovantes")
    op.execute("DROP TABLE upload_batches")
