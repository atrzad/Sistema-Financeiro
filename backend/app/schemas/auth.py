import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.security import Role


class LoginRequest(BaseModel):
    tenant_slug: str = Field(min_length=1, max_length=63, examples=["acme"])
    email: str = Field(min_length=3, max_length=255, examples=["colaborador@acme.com.br"])
    senha: str = Field(min_length=1, max_length=128)

    @field_validator("tenant_slug", "email")
    @classmethod
    def _normalizar(cls, v: str) -> str:
        return v.strip().lower()


class TenantInfo(BaseModel):
    id: uuid.UUID
    nome: str
    slug: str


class Me(BaseModel):
    id: uuid.UUID
    nome: str
    email: str
    role: Role
    nivel_aprovacao: int
    tenant: TenantInfo


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 — tipo do token, não senha
    expires_in: int
    user: Me
