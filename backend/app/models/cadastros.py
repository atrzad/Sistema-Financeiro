import uuid
from datetime import datetime

from sqlalchemy import Column, ForeignKey, String, Table, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))
    nome_fantasia: Mapped[str] = mapped_column(String(255))
    razao_social: Mapped[str | None] = mapped_column(String(255))
    cnpj: Mapped[str | None] = mapped_column(String(14))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    deleted_at: Mapped[datetime | None]


class Categoria(Base):
    __tablename__ = "categorias"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))
    nome: Mapped[str] = mapped_column(String(100))
    ativo: Mapped[bool] = mapped_column(server_default=text("true"))


class Projeto(Base):
    __tablename__ = "projetos"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))
    nome: Mapped[str] = mapped_column(String(150))
    ativo: Mapped[bool] = mapped_column(server_default=text("true"))


class CentroCusto(Base):
    __tablename__ = "centros_custo"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))
    codigo: Mapped[str] = mapped_column(String(30))
    nome: Mapped[str] = mapped_column(String(150))
    ativo: Mapped[bool] = mapped_column(server_default=text("true"))


class Tag(Base):
    """Tipo de conta (recorrente, folha de pagamento...). Um lançamento pode ter várias."""

    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))
    nome: Mapped[str] = mapped_column(String(50))
    ativo: Mapped[bool] = mapped_column(server_default=text("true"))


# tenant_id é preenchido pelo banco a partir da sessão (app_current_tenant()).
lancamento_tags = Table(
    "lancamento_tags",
    Base.metadata,
    Column(
        "tenant_id",
        ForeignKey("tenants.id"),
        nullable=False,
        server_default=text("app_current_tenant()"),
    ),
    Column("lancamento_id", ForeignKey("lancamentos.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)
