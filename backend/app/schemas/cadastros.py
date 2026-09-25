import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.domain import cnpj as cnpj_mod


def _validar_cnpj(v: str | None) -> str | None:
    if v is None or not v.strip():
        return None
    if not cnpj_mod.valido(v):
        raise ValueError("CNPJ inválido (dígitos verificadores não conferem)")
    return cnpj_mod.normalizar(v)


class SupplierIn(BaseModel):
    nome_fantasia: str = Field(min_length=2, max_length=255)
    razao_social: str | None = Field(default=None, max_length=255)
    cnpj: str | None = Field(default=None, examples=["11.222.333/0001-81", "12.ABC.345/01DE-35"])

    _cnpj = field_validator("cnpj")(_validar_cnpj)

    @field_validator("nome_fantasia", "razao_social")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        return v.strip() if v else v


class SupplierUpdate(BaseModel):
    nome_fantasia: str | None = Field(default=None, min_length=2, max_length=255)
    razao_social: str | None = Field(default=None, max_length=255)
    cnpj: str | None = None

    _cnpj = field_validator("cnpj")(_validar_cnpj)


class SupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome_fantasia: str
    razao_social: str | None
    cnpj: str | None
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cnpj_formatado(self) -> str | None:
        return cnpj_mod.formatar(self.cnpj) if self.cnpj else None


class SupplierRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome_fantasia: str
    cnpj: str | None


# --- Categorias, projetos e centros de custo ------------------------------------


class CategoriaIn(BaseModel):
    nome: str = Field(min_length=2, max_length=100)


class CategoriaUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=100)
    ativo: bool | None = None


class CategoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    ativo: bool


class ProjetoIn(BaseModel):
    nome: str = Field(min_length=2, max_length=150)


class ProjetoUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=150)
    ativo: bool | None = None


class ProjetoOut(CategoriaOut):
    pass


class CentroCustoIn(BaseModel):
    codigo: str = Field(min_length=1, max_length=30)
    nome: str = Field(min_length=2, max_length=150)


class CentroCustoUpdate(BaseModel):
    codigo: str | None = Field(default=None, min_length=1, max_length=30)
    nome: str | None = Field(default=None, min_length=2, max_length=150)
    ativo: bool | None = None


class CentroCustoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    codigo: str
    nome: str
    ativo: bool
