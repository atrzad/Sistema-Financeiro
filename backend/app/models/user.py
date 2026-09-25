import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, SmallInteger, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))
    nome: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str]
    role: Mapped[str] = mapped_column(String(20))
    nivel_aprovacao: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    ativo: Mapped[bool] = mapped_column(server_default=text("true"))
    ultimo_login_em: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), server_onupdate=text("now()")
    )
