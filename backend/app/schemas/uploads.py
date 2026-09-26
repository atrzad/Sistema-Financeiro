import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

StatusProcessamento = Literal[
    "enviando", "validando", "processando_ocr", "aguardando_revisao", "concluido", "erro"
]


class ArquivoDeclarado(BaseModel):
    nome: str = Field(min_length=1, max_length=255, examples=["boleto_luz.pdf"])
    tamanho_bytes: int = Field(gt=0, examples=[184_320])
    mime_type: str | None = Field(
        default=None, description="Informativo: o tipo real é detectado pelo servidor"
    )

    @field_validator("nome")
    @classmethod
    def _sem_caminho(cls, v: str) -> str:
        # Só o nome do arquivo, sem diretórios (ex.: "C:\\Users\\x\\a.pdf" → "a.pdf").
        return v.replace("\\", "/").rsplit("/", 1)[-1].strip() or "arquivo"


class NovoLote(BaseModel):
    arquivos: list[ArquivoDeclarado] = Field(min_length=1)
    origem: Literal["web", "mobile"] = "web"


class UploadInstrucao(BaseModel):
    comprovante_id: uuid.UUID
    nome: str
    upload_url: str
    headers: dict[str, str]


class LoteCriado(BaseModel):
    batch_id: uuid.UUID
    expira_em: datetime
    itens: list[UploadInstrucao]


class ItemStatus(BaseModel):
    comprovante_id: uuid.UUID
    nome: str
    tamanho_bytes: int
    mime_type: str
    status: StatusProcessamento
    erro_msg: str | None
    total_paginas: int
    possivel_duplicado: bool
    tem_miniatura: bool


class LoteStatus(BaseModel):
    batch_id: uuid.UUID
    total: int
    concluidos: int
    com_erro: int
    em_andamento: int
    itens: list[ItemStatus]
