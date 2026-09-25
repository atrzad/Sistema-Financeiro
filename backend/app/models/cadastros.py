import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, text
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
