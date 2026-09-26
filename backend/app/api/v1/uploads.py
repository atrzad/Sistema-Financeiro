import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.api.deps import DB, CurrentUser, SettingsDep
from app.schemas.uploads import (
    LoteCriado,
    LoteStatus,
    NovoLote,
    StatusProcessamento,
    UploadInstrucao,
)
from app.services import upload_service as svc
from app.services.lote_cache import LoteStatusCache, get_lote_cache
from app.services.storage import ObjectStorage, comprovantes_storage

router = APIRouter(tags=["upload de comprovantes"])


def get_storage() -> ObjectStorage:
    return comprovantes_storage()


def get_enfileirar() -> svc.Enfileirar:
    from app.workers.tasks.uploads import enfileirar_validacao

    return enfileirar_validacao


StorageDep = Annotated[ObjectStorage, Depends(get_storage)]
EnfileirarDep = Annotated[svc.Enfileirar, Depends(get_enfileirar)]
CacheDep = Annotated[LoteStatusCache, Depends(get_lote_cache)]


class Confirmacao(BaseModel):
    status: StatusProcessamento


@router.post("/uploads/batch", response_model=LoteCriado, status_code=status.HTTP_201_CREATED)
async def criar_lote(
    body: NovoLote,
    user: CurrentUser,
    db: DB,
    settings: SettingsDep,
    storage: StorageDep,
    cache: CacheDep,
) -> LoteCriado:
    """Cria o lote e devolve uma URL de upload por arquivo (PUT direto no storage).

    A URL fixa tipo e tamanho declarados: um arquivo diferente é recusado pelo storage.
    """
    return await svc.criar_lote(db, user, body, settings, storage, cache)


@router.post(
    "/uploads/{comprovante_id}/complete",
    response_model=Confirmacao,
    status_code=status.HTTP_202_ACCEPTED,
)
async def confirmar(
    comprovante_id: uuid.UUID,
    user: CurrentUser,
    db: DB,
    storage: StorageDep,
    enfileirar: EnfileirarDep,
    cache: CacheDep,
) -> Confirmacao:
    """Confirma o envio e dispara a validação em segundo plano. Idempotente."""
    return Confirmacao(
        status=await svc.confirmar_upload(db, user, comprovante_id, storage, enfileirar, cache)
    )


@router.post("/uploads/{comprovante_id}/retry-url", response_model=UploadInstrucao)
async def nova_url(
    comprovante_id: uuid.UUID, user: CurrentUser, db: DB, settings: SettingsDep, storage: StorageDep
) -> UploadInstrucao:
    """Nova URL para reenviar um arquivo cujo upload falhou ou expirou."""
    return await svc.nova_url(db, user, comprovante_id, settings, storage)


@router.get("/uploads/batch/{batch_id}/status", response_model=LoteStatus)
async def status_lote(
    batch_id: uuid.UUID, user: CurrentUser, db: DB, cache: CacheDep
) -> LoteStatus:
    """Status item a item + agregados. Pensado para polling (servido do cache)."""
    return await svc.status_lote(db, user, batch_id, cache)


@router.get(
    "/comprovantes/{comprovante_id}/arquivo",
    status_code=status.HTTP_302_FOUND,
    response_class=RedirectResponse,
)
async def baixar_arquivo(
    comprovante_id: uuid.UUID, user: CurrentUser, db: DB, settings: SettingsDep, storage: StorageDep
) -> RedirectResponse:
    """Redireciona para o original (link temporário, sempre como download)."""
    url = await svc.url_arquivo(db, user, comprovante_id, settings, storage, miniatura=False)
    return RedirectResponse(url, status_code=status.HTTP_302_FOUND)


@router.get(
    "/comprovantes/{comprovante_id}/thumbnail",
    status_code=status.HTTP_302_FOUND,
    response_class=RedirectResponse,
)
async def miniatura(
    comprovante_id: uuid.UUID, user: CurrentUser, db: DB, settings: SettingsDep, storage: StorageDep
) -> RedirectResponse:
    url = await svc.url_arquivo(db, user, comprovante_id, settings, storage, miniatura=True)
    return RedirectResponse(url, status_code=status.HTTP_302_FOUND)
