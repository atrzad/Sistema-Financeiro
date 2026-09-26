import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, SmallInteger, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UploadBatch(Base):
    __tablename__ = "upload_batches"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    total_arquivos: Mapped[int]
    tamanho_total: Mapped[int] = mapped_column(BigInteger)
    origem: Mapped[str] = mapped_column(String(10), server_default=text("'web'"))
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class Comprovante(Base):
    __tablename__ = "comprovantes"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"))
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    upload_batch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("upload_batches.id"))
    lancamento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lancamentos.id"))
    storage_key: Mapped[str]
    thumbnail_key: Mapped[str | None]
    nome_original: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(50))
    extensao_original: Mapped[str] = mapped_column(String(10))
    tamanho_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(64))
    possivel_duplicado: Mapped[bool] = mapped_column(server_default=text("false"))
    total_paginas: Mapped[int] = mapped_column(server_default=text("1"))
    status_processamento: Mapped[str] = mapped_column(String(20), server_default=text("'enviando'"))
    erro_msg: Mapped[str | None]
    imutavel: Mapped[bool] = mapped_column(server_default=text("false"))
    tentativas_ocr: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    ocr_provider: Mapped[str | None] = mapped_column(String(30))
    ocr_raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ocr_confidence: Mapped[dict[str, float] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
