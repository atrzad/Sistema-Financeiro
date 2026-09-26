"""Upload em lote (H3.1, H3.4, H3.6): o arquivo vai do navegador direto ao storage."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ProblemError
from app.core.security import AccessClaims
from app.db.hooks import on_commit
from app.domain.upload_validation import EXTENSOES, ArquivoInvalidoError, extensao, validar_extensao
from app.models import Comprovante, UploadBatch
from app.schemas.uploads import (
    ItemStatus,
    LoteCriado,
    LoteStatus,
    NovoLote,
    UploadInstrucao,
)
from app.services.lote_cache import LoteStatusCache, item_status
from app.services.storage import ObjectStorage

Enfileirar = Callable[[uuid.UUID, uuid.UUID], None]

EM_ANDAMENTO = {"enviando", "validando", "processando_ocr"}
FINALIZADOS_OK = {"aguardando_revisao", "concluido"}


def _mb(n: int) -> str:
    return f"{n / (1024 * 1024):.0f} MB"


def _validar_declaracao(data: NovoLote, settings: Settings) -> None:
    arquivos = data.arquivos
    if len(arquivos) > settings.upload_max_arquivos:
        raise ProblemError(422, f"Envie no máximo {settings.upload_max_arquivos} arquivos por vez.")
    erros = []
    for i, a in enumerate(arquivos):
        try:
            validar_extensao(a.nome)
        except ArquivoInvalidoError as exc:
            erros.append({"campo": f"arquivos.{i}", "arquivo": a.nome, "erro": str(exc)})
            continue
        if a.tamanho_bytes > settings.upload_max_bytes_arquivo:
            erros.append(
                {
                    "campo": f"arquivos.{i}",
                    "arquivo": a.nome,
                    "erro": f"Arquivo acima de {_mb(settings.upload_max_bytes_arquivo)}.",
                }
            )
    if erros:
        raise ProblemError(422, "Há arquivos que não podem ser enviados.", errors=erros)
    total = sum(a.tamanho_bytes for a in arquivos)
    if total > settings.upload_max_bytes_lote:
        raise ProblemError(422, f"O lote passa de {_mb(settings.upload_max_bytes_lote)} no total.")


def _chave(tenant_id: uuid.UUID, comp_id: uuid.UUID, ext: str) -> str:
    agora = datetime.now(UTC)
    return f"{tenant_id}/{agora:%Y}/{agora:%m}/{comp_id}{ext}"


def _instrucao(comp: Comprovante, storage: ObjectStorage, settings: Settings) -> UploadInstrucao:
    url = storage.presign_put(
        comp.storage_key, comp.mime_type, comp.tamanho_bytes, settings.upload_url_ttl_s
    )
    return UploadInstrucao(
        comprovante_id=comp.id,
        nome=comp.nome_original,
        upload_url=url,
        headers={"Content-Type": comp.mime_type},
    )


async def criar_lote(
    db: AsyncSession,
    user: AccessClaims,
    data: NovoLote,
    settings: Settings,
    storage: ObjectStorage,
    cache: LoteStatusCache,
) -> LoteCriado:
    _validar_declaracao(data, settings)
    lote = UploadBatch(
        tenant_id=user.tenant_id,
        usuario_id=user.user_id,
        total_arquivos=len(data.arquivos),
        tamanho_total=sum(a.tamanho_bytes for a in data.arquivos),
        origem=data.origem,
    )
    db.add(lote)
    await db.flush()

    comprovantes = []
    for a in data.arquivos:
        comp_id = uuid.uuid4()
        ext = extensao(a.nome)
        comp = Comprovante(
            id=comp_id,
            tenant_id=user.tenant_id,
            usuario_id=user.user_id,
            upload_batch_id=lote.id,
            storage_key=_chave(user.tenant_id, comp_id, ext),  # nunca o nome do cliente
            nome_original=a.nome,
            mime_type=EXTENSOES[ext],
            extensao_original=ext,
            tamanho_bytes=a.tamanho_bytes,
        )
        db.add(comp)
        comprovantes.append(comp)
    await db.flush()
    cache.apos_commit(db, *comprovantes, lote=lote)

    return LoteCriado(
        batch_id=lote.id,
        expira_em=datetime.now(UTC) + timedelta(seconds=settings.upload_url_ttl_s),
        itens=[_instrucao(c, storage, settings) for c in comprovantes],
    )


async def _meu_comprovante(
    db: AsyncSession, user: AccessClaims, comp_id: uuid.UUID, *, for_update: bool = False
) -> Comprovante:
    query = select(Comprovante).where(Comprovante.id == comp_id)
    if user.role != "admin":
        query = query.where(Comprovante.usuario_id == user.user_id)
    if for_update:
        query = query.with_for_update()
    comp = await db.scalar(query)
    if comp is None:
        raise ProblemError(404, "Comprovante não encontrado.")
    return comp


async def confirmar_upload(
    db: AsyncSession,
    user: AccessClaims,
    comp_id: uuid.UUID,
    storage: ObjectStorage,
    enfileirar: Enfileirar,
    cache: LoteStatusCache,
) -> str:
    """Chamado pelo navegador após o PUT. Idempotente."""
    comp = await _meu_comprovante(db, user, comp_id, for_update=True)
    if comp.status_processamento != "enviando":
        return comp.status_processamento

    info = storage.head(comp.storage_key)
    if info is None:
        raise ProblemError(409, "O arquivo ainda não chegou ao armazenamento. Envie novamente.")
    if info.size != comp.tamanho_bytes:
        comp.status_processamento = "erro"
        comp.erro_msg = "O tamanho recebido difere do declarado. Envie novamente."
        cache.apos_commit(db, comp)
        return comp.status_processamento

    comp.status_processamento = "validando"
    tenant_id, cid = comp.tenant_id, comp.id
    # Nesta ordem: o cache recebe "validando" antes de o worker poder gravar o resultado.
    cache.apos_commit(db, comp)
    on_commit(db, lambda: enfileirar(tenant_id, cid))
    return comp.status_processamento


async def nova_url(
    db: AsyncSession,
    user: AccessClaims,
    comp_id: uuid.UUID,
    settings: Settings,
    storage: ObjectStorage,
) -> UploadInstrucao:
    comp = await _meu_comprovante(db, user, comp_id)
    if comp.status_processamento != "enviando":
        raise ProblemError(409, "Este arquivo já foi recebido; não é possível reenviar.")
    return _instrucao(comp, storage, settings)


def _ordenados(itens: list[ItemStatus]) -> list[ItemStatus]:
    return sorted(itens, key=lambda i: (i.nome, str(i.comprovante_id)))


async def status_lote(
    db: AsyncSession, user: AccessClaims, batch_id: uuid.UUID, cache: LoteStatusCache
) -> LoteStatus:
    """Servido do cache Redis (a tela consulta a cada 2 s); banco como fallback."""
    dono = None if user.role == "admin" else user.user_id
    itens = await cache.ler(batch_id, user.tenant_id, dono)
    if itens is None:
        query = select(UploadBatch).where(UploadBatch.id == batch_id)
        if dono is not None:
            query = query.where(UploadBatch.usuario_id == dono)
        lote = await db.scalar(query)
        if lote is None:
            raise ProblemError(404, "Lote não encontrado.")
        comps = await db.scalars(select(Comprovante).where(Comprovante.upload_batch_id == batch_id))
        itens = [item_status(c) for c in comps]
        await cache.preencher(lote, itens)

    itens = _ordenados(itens)
    return LoteStatus(
        batch_id=batch_id,
        total=len(itens),
        concluidos=sum(i.status in FINALIZADOS_OK for i in itens),
        com_erro=sum(i.status == "erro" for i in itens),
        em_andamento=sum(i.status in EM_ANDAMENTO for i in itens),
        itens=itens,
    )


async def url_arquivo(
    db: AsyncSession,
    user: AccessClaims,
    comp_id: uuid.UUID,
    settings: Settings,
    storage: ObjectStorage,
    *,
    miniatura: bool,
) -> str:
    query = select(Comprovante).where(Comprovante.id == comp_id)
    if user.role == "colaborador":
        query = query.where(Comprovante.usuario_id == user.user_id)
    comp = await db.scalar(query)
    if comp is None:
        raise ProblemError(404, "Comprovante não encontrado.")
    if miniatura:
        if not comp.thumbnail_key:
            raise ProblemError(404, "Miniatura ainda não disponível.")
        return storage.presign_get(comp.thumbnail_key, settings.download_url_ttl_s, inline=True)
    if comp.status_processamento in ("enviando", "erro"):
        raise ProblemError(409, "O arquivo não está disponível.")
    return storage.presign_get(
        comp.storage_key, settings.download_url_ttl_s, filename=comp.nome_original
    )
