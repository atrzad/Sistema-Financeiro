"""Fornecedores (H2.1): CNPJ único por empresa, busca por similaridade, exclusão lógica."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ProblemError
from app.domain import cnpj as cnpj_mod
from app.models import Supplier
from app.schemas.cadastros import SupplierIn, SupplierUpdate

SIMILARIDADE_MINIMA = 0.2


async def _conflito_cnpj(db: AsyncSession, cnpj: str, ignorar: uuid.UUID | None = None) -> None:
    query = select(Supplier.id).where(Supplier.cnpj == cnpj, Supplier.deleted_at.is_(None))
    if ignorar:
        query = query.where(Supplier.id != ignorar)
    existente = await db.scalar(query)
    if existente:
        raise ProblemError(
            409,
            f"Já existe um fornecedor com o CNPJ {cnpj_mod.formatar(cnpj)}.",
            existente_id=str(existente),
        )


async def buscar(db: AsyncSession, q: str | None, limit: int) -> list[Supplier]:
    query = select(Supplier).where(Supplier.deleted_at.is_(None))
    termo = (q or "").strip()
    if not termo:
        return list(await db.scalars(query.order_by(Supplier.nome_fantasia).limit(limit)))

    digitos = cnpj_mod.normalizar(termo)
    nome = func.unaccent(func.lower(Supplier.nome_fantasia))
    alvo = func.unaccent(func.lower(termo))
    score = func.similarity(nome, alvo)
    filtros = [score >= SIMILARIDADE_MINIMA, nome.contains(alvo)]
    if len(digitos) >= 4:
        filtros.append(Supplier.cnpj.startswith(digitos))
    query = query.where(or_(*filtros)).order_by(score.desc(), Supplier.nome_fantasia).limit(limit)
    return list(await db.scalars(query))


async def obter(db: AsyncSession, supplier_id: uuid.UUID) -> Supplier:
    s = await db.get(Supplier, supplier_id)
    if s is None or s.deleted_at is not None:
        raise ProblemError(404, "Fornecedor não encontrado.")
    return s


async def criar(db: AsyncSession, tenant_id: uuid.UUID, data: SupplierIn) -> Supplier:
    if data.cnpj:
        await _conflito_cnpj(db, data.cnpj)
    s = Supplier(tenant_id=tenant_id, **data.model_dump())
    db.add(s)
    try:
        await db.flush()
    except IntegrityError:  # corrida entre duas criações simultâneas
        raise ProblemError(409, "Já existe um fornecedor com este CNPJ.") from None
    await db.refresh(s)
    return s


async def atualizar(db: AsyncSession, supplier_id: uuid.UUID, data: SupplierUpdate) -> Supplier:
    s = await obter(db, supplier_id)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("cnpj"):
        await _conflito_cnpj(db, changes["cnpj"], ignorar=s.id)
    if "nome_fantasia" in changes and not changes["nome_fantasia"]:
        raise ProblemError(422, "Nome fantasia é obrigatório.")
    for k, v in changes.items():
        setattr(s, k, v.strip() if isinstance(v, str) else v)
    await db.flush()
    await db.refresh(s)
    return s


async def excluir(db: AsyncSession, supplier_id: uuid.UUID) -> None:
    """Exclusão lógica: lançamentos existentes continuam apontando para o fornecedor."""
    s = await obter(db, supplier_id)
    s.deleted_at = datetime.now(UTC)
    await db.flush()
