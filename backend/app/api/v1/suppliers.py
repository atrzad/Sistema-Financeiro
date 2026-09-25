import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import DB, CurrentUser, require_role
from app.core.security import AccessClaims
from app.schemas.cadastros import SupplierIn, SupplierOut, SupplierUpdate
from app.services import supplier_service

router = APIRouter(prefix="/suppliers", tags=["fornecedores"])


@router.get("", response_model=list[SupplierOut])
async def buscar(
    _: CurrentUser,
    db: DB,
    q: Annotated[str | None, Query(max_length=100, description="Nome ou início do CNPJ")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[SupplierOut]:
    """Busca por similaridade de nome (tolerante a acentos e erros de digitação) ou CNPJ."""
    return [SupplierOut.model_validate(s) for s in await supplier_service.buscar(db, q, limit)]


@router.post("", response_model=SupplierOut, status_code=status.HTTP_201_CREATED)
async def criar(body: SupplierIn, user: CurrentUser, db: DB) -> SupplierOut:
    return SupplierOut.model_validate(await supplier_service.criar(db, user.tenant_id, body))


@router.get("/{supplier_id}", response_model=SupplierOut)
async def obter(supplier_id: uuid.UUID, _: CurrentUser, db: DB) -> SupplierOut:
    return SupplierOut.model_validate(await supplier_service.obter(db, supplier_id))


@router.patch("/{supplier_id}", response_model=SupplierOut)
async def atualizar(
    supplier_id: uuid.UUID, body: SupplierUpdate, _: CurrentUser, db: DB
) -> SupplierOut:
    return SupplierOut.model_validate(await supplier_service.atualizar(db, supplier_id, body))


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def excluir(
    supplier_id: uuid.UUID,
    _: Annotated[AccessClaims, Depends(require_role("admin"))],
    db: DB,
) -> Response:
    await supplier_service.excluir(db, supplier_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
