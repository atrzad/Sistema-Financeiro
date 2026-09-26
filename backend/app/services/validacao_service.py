"""Validação assíncrona de comprovantes (H3.2, H3.3) — executada pelo worker."""

import asyncio
import hashlib
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.db.session import get_sessionmaker
from app.db.tenant import tenant_session
from app.domain.upload_validation import ArquivoInvalidoError, validar
from app.models import Comprovante, Tenant
from app.services.lote_cache import LoteStatusCache
from app.services.storage import ObjectStorage, ObjectTooLargeError
from app.services.thumbnails import gerar_miniatura

log = get_logger("validacao")

ABANDONO_APOS = timedelta(minutes=30)
# Validar leva segundos; além disto a task se perdeu (worker derrubado no meio etc.).
VALIDACAO_TRAVADA_APOS = timedelta(minutes=30)

FALHA_VALIDACAO = "Não foi possível validar o arquivo agora. Envie-o novamente."

EnfileirarValidacao = Callable[[uuid.UUID, uuid.UUID], None]


async def _duplicado(db: AsyncSession, comp: Comprovante, sha: str) -> bool:
    outro = await db.scalar(
        select(Comprovante.id).where(
            Comprovante.sha256 == sha,
            Comprovante.id != comp.id,
            Comprovante.status_processamento != "erro",
        )
    )
    return outro is not None


async def validar_comprovante(
    tenant_id: uuid.UUID,
    comp_id: uuid.UUID,
    settings: Settings,
    storage: ObjectStorage,
    cache: LoteStatusCache,
) -> str:
    """Retorna o status final. Erros transitórios (storage fora) sobem para o retry do Celery."""
    async with tenant_session(tenant_id) as db:
        comp = await db.get(Comprovante, comp_id, with_for_update=True)
        if comp is None or comp.status_processamento != "validando":
            return comp.status_processamento if comp else "inexistente"

        try:
            data = await asyncio.to_thread(
                storage.read, comp.storage_key, settings.upload_max_bytes_arquivo
            )
            resultado = await asyncio.to_thread(
                validar,
                comp.nome_original,
                data,
                max_bytes=settings.upload_max_bytes_arquivo,
                max_paginas=settings.upload_max_paginas_pdf,
            )
        except (ArquivoInvalidoError, ObjectTooLargeError) as exc:
            motivo = str(exc) if isinstance(exc, ArquivoInvalidoError) else "Arquivo grande demais."
            comp.status_processamento = "erro"
            comp.erro_msg = motivo
            comp.storage_key = await asyncio.to_thread(storage.quarantine, comp.storage_key)
            cache.apos_commit(db, comp)
            log.info("comprovante_recusado", comprovante_id=str(comp.id), motivo=motivo)
            return comp.status_processamento

        sha = hashlib.sha256(data).hexdigest()
        thumb_key = await _miniatura(storage, comp.storage_key, data, resultado.mime_type)

        tenant = await db.get_one(Tenant, tenant_id)
        comp.imutavel = await asyncio.to_thread(
            storage.lock, comp.storage_key, tenant.retencao_meses
        )
        comp.mime_type = resultado.mime_type
        comp.total_paginas = resultado.total_paginas
        comp.sha256 = sha
        comp.possivel_duplicado = await _duplicado(db, comp, sha)
        comp.thumbnail_key = thumb_key
        comp.erro_msg = None
        # O OCR entra na Sprint 04; até lá o arquivo validado já fica disponível.
        comp.status_processamento = "concluido"
        cache.apos_commit(db, comp)
        log.info("comprovante_validado", comprovante_id=str(comp.id), paginas=comp.total_paginas)
        return comp.status_processamento


async def _miniatura(storage: ObjectStorage, key: str, data: bytes, mime: str) -> str | None:
    """A miniatura é conveniência: se o renderizador falhar num arquivo que já passou
    na validação, o comprovante segue sem ela. Falha do storage continua subindo (retry)."""
    try:
        miniatura = await asyncio.to_thread(gerar_miniatura, data, mime)
    except Exception as exc:
        log.warning("miniatura_falhou", key=key, error=repr(exc))
        return None
    thumb_key = f"thumbnails/{key.rsplit('.', 1)[0]}.webp"
    await asyncio.to_thread(storage.put, thumb_key, miniatura, "image/webp")
    return thumb_key


async def marcar_falha_validacao(
    tenant_id: uuid.UUID, comp_id: uuid.UUID, cache: LoteStatusCache
) -> None:
    """Tentativas esgotadas (storage fora por muito tempo, erro inesperado, tempo
    estourado): o comprovante sai de "validando" em vez de ficar sem resposta."""
    async with tenant_session(tenant_id) as db:
        comp = await db.get(Comprovante, comp_id, with_for_update=True)
        if comp is None or comp.status_processamento != "validando":
            return
        comp.status_processamento = "erro"
        comp.erro_msg = FALHA_VALIDACAO
        cache.apos_commit(db, comp)


async def tenants_ativos() -> list[uuid.UUID]:
    async with get_sessionmaker()() as db:
        rows = await db.execute(text("SELECT listar_tenants_ativos()"))
        return [uuid.UUID(str(r[0])) for r in rows]


async def recuperar_abandonados(
    storage: ObjectStorage,
    enfileirar_validacao: EnfileirarValidacao,
    cache: LoteStatusCache,
    agora: datetime | None = None,
) -> dict[str, int]:
    """Uploads em 'enviando' há mais de 30 min: se o arquivo chegou (o navegador
    fechou antes de confirmar), segue para validação; senão, marca erro. Validações
    paradas há mais de 30 min (task perdida) também terminam em erro — sem reenfileirar,
    para um arquivo que derruba o worker não entrar em ciclo."""
    agora = agora or datetime.now(UTC)
    limite = agora - ABANDONO_APOS
    contagem = {"retomados": 0, "expirados": 0, "travados": 0}
    for tenant_id in await tenants_ativos():
        retomar: list[uuid.UUID] = []
        async with tenant_session(tenant_id) as db:
            # Antes dos parados: os retomados abaixo também viram "validando".
            travados = await db.scalars(
                select(Comprovante)
                .where(
                    Comprovante.status_processamento == "validando",
                    Comprovante.updated_at < agora - VALIDACAO_TRAVADA_APOS,
                )
                .with_for_update(skip_locked=True)
            )
            for comp in travados:
                comp.status_processamento = "erro"
                comp.erro_msg = FALHA_VALIDACAO
                contagem["travados"] += 1
                cache.apos_commit(db, comp)

            parados = await db.scalars(
                select(Comprovante)
                .where(
                    Comprovante.status_processamento == "enviando",
                    Comprovante.created_at < limite,
                )
                .with_for_update(skip_locked=True)
            )
            for comp in parados:
                info = await asyncio.to_thread(storage.head, comp.storage_key)
                if info is not None and info.size == comp.tamanho_bytes:
                    comp.status_processamento = "validando"
                    retomar.append(comp.id)
                else:
                    comp.status_processamento = "erro"
                    comp.erro_msg = "O envio não foi concluído. Envie o arquivo novamente."
                    contagem["expirados"] += 1
                cache.apos_commit(db, comp)
        # Só depois do commit: o worker precisa enxergar o status "validando".
        for comp_id in retomar:
            enfileirar_validacao(tenant_id, comp_id)
        contagem["retomados"] += len(retomar)
    return contagem
