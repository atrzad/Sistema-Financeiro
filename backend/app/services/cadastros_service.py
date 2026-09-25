"""Categorias, projetos e centros de custo (H2.2) — CRUD genérico por modelo."""

import uuid

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ProblemError
from app.models import Categoria, CentroCusto, Projeto

CATEGORIAS_PADRAO = [
    "Alimentação",
    "Transporte",
    "Hospedagem",
    "Utilidades",
    "Material",
    "Serviços",
    "Outros",
]

_ORDEM = {Categoria: Categoria.nome, Projeto: Projeto.nome, CentroCusto: CentroCusto.codigo}
_DUPLICADO = {
    Categoria: "Já existe uma categoria com este nome.",
    Projeto: "Já existe um projeto com este nome.",
    CentroCusto: "Já existe um centro de custo com este código.",
}


async def listar[M: (Categoria, Projeto, CentroCusto)](
    db: AsyncSession, model: type[M], incluir_inativos: bool
) -> list[M]:
    query = select(model).order_by(_ORDEM[model])
    if not incluir_inativos:
        query = query.where(model.ativo.is_(True))
    return list(await db.scalars(query))


async def criar[M: (Categoria, Projeto, CentroCusto)](
    db: AsyncSession, model: type[M], tenant_id: uuid.UUID, data: BaseModel
) -> M:
    valores = {k: v.strip() if isinstance(v, str) else v for k, v in data.model_dump().items()}
    obj = model(tenant_id=tenant_id, **valores)
    db.add(obj)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        raise ProblemError(409, _DUPLICADO[model]) from None
    await db.refresh(obj)
    return obj


async def atualizar[M: (Categoria, Projeto, CentroCusto)](
    db: AsyncSession, model: type[M], obj_id: uuid.UUID, data: BaseModel
) -> M:
    obj = await db.get(model, obj_id)
    if obj is None:
        raise ProblemError(404, "Registro não encontrado.")
    for k, v in data.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(obj, k, v.strip() if isinstance(v, str) else v)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        raise ProblemError(409, _DUPLICADO[model]) from None
    await db.refresh(obj)
    return obj


async def garantir_categorias_padrao(db: AsyncSession, tenant_id: uuid.UUID) -> int:
    existentes = set(await db.scalars(select(Categoria.nome)))
    novas = [n for n in CATEGORIAS_PADRAO if n not in existentes]
    db.add_all(Categoria(tenant_id=tenant_id, nome=n) for n in novas)
    await db.flush()
    return len(novas)
