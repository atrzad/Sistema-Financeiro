import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response, status

from app.api.deps import DB, CurrentUser
from app.domain.clock import Clock, get_clock
from app.domain.status import StatusEfetivo
from app.schemas.lancamentos import LancamentoIn, LancamentoOut, LancamentoPage, LancamentoUpdate
from app.services import lancamento_service as svc

router = APIRouter(prefix="/lancamentos", tags=["lançamentos"])

ClockDep = Annotated[Clock, Depends(get_clock)]


def _etag(response: Response, out: LancamentoOut) -> LancamentoOut:
    response.headers["ETag"] = f'"{out.version}"'
    return out


@router.get("", response_model=LancamentoPage)
async def listar(
    user: CurrentUser,
    db: DB,
    clock: ClockDep,
    status_: Annotated[
        list[StatusEfetivo] | None,
        Query(alias="status", description="Status efetivo (repita para vários)"),
    ] = None,
    supplier_id: uuid.UUID | None = None,
    categoria_id: uuid.UUID | None = None,
    projeto_id: uuid.UUID | None = None,
    centro_custo_id: uuid.UUID | None = None,
    vencimento_de: date | None = None,
    vencimento_ate: date | None = None,
    limit: Annotated[int, Query(ge=1, le=svc.LIMITE_MAXIMO)] = 50,
    cursor: str | None = None,
) -> LancamentoPage:
    """Lista ordenada por vencimento (mais próximo primeiro; sem vencimento no fim)."""
    hoje = clock()
    filtros = svc.Filtros(
        status=status_,
        supplier_id=supplier_id,
        categoria_id=categoria_id,
        projeto_id=projeto_id,
        centro_custo_id=centro_custo_id,
        vencimento_de=vencimento_de,
        vencimento_ate=vencimento_ate,
    )
    items, proximo = await svc.listar(db, user, filtros, hoje, limit, cursor)
    return LancamentoPage(items=[svc.to_out(i, hoje) for i in items], next_cursor=proximo)


@router.post("", response_model=LancamentoOut, status_code=status.HTTP_201_CREATED)
async def criar(
    body: LancamentoIn, response: Response, user: CurrentUser, db: DB, clock: ClockDep
) -> LancamentoOut:
    return _etag(response, svc.to_out(await svc.criar(db, user, body), clock()))


@router.get("/{lanc_id}", response_model=LancamentoOut)
async def obter(
    lanc_id: uuid.UUID, response: Response, user: CurrentUser, db: DB, clock: ClockDep
) -> LancamentoOut:
    return _etag(response, svc.to_out(await svc.obter(db, user, lanc_id), clock()))


@router.patch("/{lanc_id}", response_model=LancamentoOut)
async def atualizar(
    lanc_id: uuid.UUID,
    body: LancamentoUpdate,
    response: Response,
    user: CurrentUser,
    db: DB,
    clock: ClockDep,
    if_match: Annotated[str | None, Header(description='Versão esperada, ex.: "3"')] = None,
) -> LancamentoOut:
    lanc = await svc.atualizar(db, user, lanc_id, body, if_match)
    return _etag(response, svc.to_out(lanc, clock()))


@router.delete("/{lanc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def excluir(lanc_id: uuid.UUID, user: CurrentUser, db: DB) -> Response:
    await svc.excluir(db, user, lanc_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
