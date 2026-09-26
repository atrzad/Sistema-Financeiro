"""Categorias, projetos, centros de custo e tags: todos listam; só admin altera."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from app.api.deps import DB, CurrentUser, require_role
from app.core.security import AccessClaims
from app.models import Categoria, CentroCusto, Projeto, Tag
from app.schemas.cadastros import (
    CategoriaIn,
    CategoriaOut,
    CategoriaUpdate,
    CentroCustoIn,
    CentroCustoOut,
    CentroCustoUpdate,
    ProjetoIn,
    ProjetoOut,
    ProjetoUpdate,
    TagIn,
    TagOut,
    TagUpdate,
)
from app.services import cadastros_service

Admin = Annotated[AccessClaims, Depends(require_role("admin"))]
IncluirInativos = Annotated[bool, Query(description="Inclui registros desativados")]


def _router(
    prefix: str,
    tag: str,
    model: Any,
    schema_in: type[BaseModel],
    schema_update: type[BaseModel],
    schema_out: type[BaseModel],
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag])

    @router.get("", response_model=list[schema_out])  # type: ignore[valid-type]
    async def listar(_: CurrentUser, db: DB, incluir_inativos: IncluirInativos = False) -> Any:
        return await cadastros_service.listar(db, model, incluir_inativos)

    @router.post("", response_model=schema_out, status_code=status.HTTP_201_CREATED)
    async def criar(body: schema_in, admin: Admin, db: DB) -> Any:  # type: ignore[valid-type]
        return await cadastros_service.criar(db, model, admin.tenant_id, body)

    @router.patch("/{obj_id}", response_model=schema_out)
    async def atualizar(obj_id: uuid.UUID, body: schema_update, _: Admin, db: DB) -> Any:  # type: ignore[valid-type]
        return await cadastros_service.atualizar(db, model, obj_id, body)

    return router


categorias = _router(
    "/categorias", "categorias", Categoria, CategoriaIn, CategoriaUpdate, CategoriaOut
)
projetos = _router("/projetos", "projetos", Projeto, ProjetoIn, ProjetoUpdate, ProjetoOut)
centros_custo = _router(
    "/centros-custo",
    "centros de custo",
    CentroCusto,
    CentroCustoIn,
    CentroCustoUpdate,
    CentroCustoOut,
)
tags = _router("/tags", "tags", Tag, TagIn, TagUpdate, TagOut)
