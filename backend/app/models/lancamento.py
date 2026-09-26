import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, SmallInteger, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.cadastros import Categoria, CentroCusto, Projeto, Supplier, Tag, lancamento_tags
from app.models.user import User


class Lancamento(Base):
    __tablename__ = "lancamentos"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("suppliers.id"))
    categoria_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("categorias.id"))
    projeto_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projetos.id"))
    centro_custo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("centros_custo.id"))
    faixa_valor_id: Mapped[uuid.UUID | None]
    descricao: Mapped[str | None] = mapped_column(String(500))
    valor: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    forma_pagamento: Mapped[str | None] = mapped_column(String(20))
    linha_digitavel: Mapped[str | None] = mapped_column(String(60))
    data_emissao: Mapped[date]
    data_pagamento_prevista: Mapped[date | None]
    data_pagamento_efetiva: Mapped[date | None]
    status: Mapped[str] = mapped_column(String(20), server_default=text("'pendente'"))
    status_aprovacao: Mapped[str] = mapped_column(String(20), server_default=text("'rascunho'"))
    nivel_aprovacao_exigido: Mapped[int] = mapped_column(SmallInteger, server_default=text("1"))
    aprovado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    aprovado_em: Mapped[datetime | None]
    version: Mapped[int] = mapped_column(server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    deleted_at: Mapped[datetime | None]

    supplier: Mapped[Supplier | None] = relationship(lazy="raise")
    categoria: Mapped[Categoria | None] = relationship(lazy="raise")
    projeto: Mapped[Projeto | None] = relationship(lazy="raise")
    centro_custo: Mapped[CentroCusto | None] = relationship(lazy="raise")
    usuario: Mapped[User] = relationship(foreign_keys=[usuario_id], lazy="raise")
    tags: Mapped[list[Tag]] = relationship(
        secondary=lancamento_tags, order_by=Tag.nome, lazy="raise"
    )
