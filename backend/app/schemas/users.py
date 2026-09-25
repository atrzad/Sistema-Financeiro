import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core.security import Role


def _validar_nivel(role: Role | None, nivel: int | None) -> None:
    if role == "colaborador" and nivel not in (None, 0):
        raise ValueError("colaborador não tem nível de aprovação (use 0)")
    if role == "aprovador" and nivel == 0:
        raise ValueError("aprovador precisa de nível de aprovação 1 ou 2")


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    email: str
    role: Role
    nivel_aprovacao: int
    ativo: bool
    ultimo_login_em: datetime | None
    created_at: datetime


class UserCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=255)
    email: EmailStr
    senha: str = Field(min_length=8, max_length=128)
    role: Role = "colaborador"
    nivel_aprovacao: int = Field(default=0, ge=0, le=2)

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.strip().lower()

    @model_validator(mode="after")
    def _nivel(self) -> Self:
        _validar_nivel(self.role, self.nivel_aprovacao)
        return self


class UserUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=255)
    role: Role | None = None
    nivel_aprovacao: int | None = Field(default=None, ge=0, le=2)
    ativo: bool | None = None
