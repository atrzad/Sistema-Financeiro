import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.status import StatusEfetivo
from app.schemas.cadastros import SupplierRef

FormaPagamento = Literal["boleto", "pix", "cartao", "dinheiro", "transferencia", "outro"]
MAX_TAGS = 20
Valor = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2, examples=["245.90"])]


def _linha(v: str | None) -> str | None:
    if v is None:
        return None
    digitos = "".join(ch for ch in v if ch.isdigit())
    return digitos or None


class LancamentoIn(BaseModel):
    valor: Valor
    data_emissao: date
    data_pagamento_prevista: date | None = None
    supplier_id: uuid.UUID | None = None
    categoria_id: uuid.UUID | None = None
    projeto_id: uuid.UUID | None = None
    centro_custo_id: uuid.UUID | None = None
    descricao: str | None = Field(default=None, max_length=500)
    forma_pagamento: FormaPagamento | None = None
    linha_digitavel: str | None = Field(default=None, max_length=60)
    tag_ids: list[uuid.UUID] = Field(default_factory=list, max_length=MAX_TAGS)

    _linha = field_validator("linha_digitavel")(_linha)


class LancamentoUpdate(BaseModel):
    """Atualização parcial: só os campos enviados são alterados (null limpa o campo)."""

    valor: Valor | None = None
    data_emissao: date | None = None
    data_pagamento_prevista: date | None = None
    supplier_id: uuid.UUID | None = None
    categoria_id: uuid.UUID | None = None
    projeto_id: uuid.UUID | None = None
    centro_custo_id: uuid.UUID | None = None
    descricao: str | None = Field(default=None, max_length=500)
    forma_pagamento: FormaPagamento | None = None
    linha_digitavel: str | None = Field(default=None, max_length=60)
    # Substitui o conjunto inteiro de tags; null ou [] remove todas.
    tag_ids: list[uuid.UUID] | None = Field(default=None, max_length=MAX_TAGS)

    _linha = field_validator("linha_digitavel")(_linha)


class Ref(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str


class CentroCustoRef(Ref):
    codigo: str


class LancamentoOut(BaseModel):
    id: uuid.UUID
    valor: Decimal
    data_emissao: date
    data_pagamento_prevista: date | None
    data_pagamento_efetiva: date | None
    supplier: SupplierRef | None
    categoria: Ref | None
    projeto: Ref | None
    centro_custo: CentroCustoRef | None
    tags: list[Ref]
    usuario: Ref
    descricao: str | None
    forma_pagamento: FormaPagamento | None
    linha_digitavel: str | None
    status: str
    status_efetivo: StatusEfetivo
    dias_para_vencimento: int | None
    status_aprovacao: str
    version: int
    created_at: datetime
    updated_at: datetime


class LancamentoPage(BaseModel):
    items: list[LancamentoOut]
    next_cursor: str | None
