"""Cache do status dos lotes no Redis (H3.4).

Enquanto há arquivos em andamento, a tela consulta o status a cada 2 s; o cache
evita que cada consulta vá ao Postgres. Um hash `batch:{id}` por lote:

- `meta`: dono do lote (empresa e usuário) e quantidade de itens;
- `item:{comprovante_id}`: estado de cada comprovante.

Quem muda um item (API ou worker) grava o campo dele DEPOIS do commit. A leitura
que não encontra o lote completo vai ao banco e preenche só os campos ausentes
(HSETNX): um retrato lido do banco antes de uma mudança nunca sobrescreve o estado
mais novo que o worker gravou nesse meio-tempo. O Redis é só um atalho — qualquer
falha nele cai no banco.
"""

import json
import uuid

from redis import Redis as SyncRedis
from redis import RedisError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.redis import get_redis, get_redis_sync
from app.db.hooks import on_commit
from app.models import Comprovante, UploadBatch
from app.schemas.uploads import ItemStatus

log = get_logger("lote_cache")

# Renovado a cada gravação. Limita por quanto tempo um estado velho sobreviveria
# caso uma gravação se perca (Redis fora do ar no instante do commit).
TTL_S = 10 * 60


def _chave(batch_id: uuid.UUID) -> str:
    return f"batch:{batch_id}"


def _campo(comprovante_id: uuid.UUID) -> str:
    return f"item:{comprovante_id}"


def _meta(lote: UploadBatch) -> str:
    return json.dumps(
        {
            "tenant_id": str(lote.tenant_id),
            "usuario_id": str(lote.usuario_id),
            "total": lote.total_arquivos,
        }
    )


def item_status(c: Comprovante) -> ItemStatus:
    return ItemStatus(
        comprovante_id=c.id,
        nome=c.nome_original,
        tamanho_bytes=c.tamanho_bytes,
        mime_type=c.mime_type,
        status=c.status_processamento,
        erro_msg=c.erro_msg,
        total_paginas=c.total_paginas,
        possivel_duplicado=c.possivel_duplicado,
        tem_miniatura=c.thumbnail_key is not None,
    )


class LoteStatusCache:
    def __init__(self, sync: SyncRedis, aio: Redis, ttl_s: int = TTL_S) -> None:
        self.sync = sync
        self.aio = aio
        self.ttl_s = ttl_s

    # --- Gravação (quem altera o comprovante) -------------------------------------

    def apos_commit(
        self, db: AsyncSession, *comps: Comprovante, lote: UploadBatch | None = None
    ) -> None:
        """Agenda a gravação do estado ATUAL dos itens para depois do commit.

        O retrato é tirado agora: após o commit a sessão já pode estar fechada.
        """
        campos: dict[uuid.UUID, dict[str, str]] = {}
        for c in comps:
            if c.upload_batch_id is not None:
                campos.setdefault(c.upload_batch_id, {})[_campo(c.id)] = item_status(
                    c
                ).model_dump_json()
        if lote is not None:
            campos.setdefault(lote.id, {})["meta"] = _meta(lote)
        if campos:
            on_commit(db, lambda: self._gravar(campos))

    def _gravar(self, campos: dict[uuid.UUID, dict[str, str]]) -> None:
        try:
            with self.sync.pipeline(transaction=False) as pipe:
                for batch_id, mapping in campos.items():
                    pipe.hset(_chave(batch_id), mapping=mapping)
                    pipe.expire(_chave(batch_id), self.ttl_s)
                pipe.execute()
        except RedisError as exc:
            # Já está no banco; o cache se corrige na próxima leitura ou no TTL.
            log.warning("cache_lote_indisponivel", error=str(exc))

    # --- Leitura (tela de status) -------------------------------------------------

    async def ler(
        self, batch_id: uuid.UUID, tenant_id: uuid.UUID, usuario_id: uuid.UUID | None
    ) -> list[ItemStatus] | None:
        """Itens do lote, se o cache estiver completo e o lote pertencer a quem pede.

        `usuario_id=None` dispensa a checagem de dono (admin). Qualquer divergência
        devolve None e a consulta vai ao banco, onde o RLS decide.
        """
        try:
            dados: dict[str, str] = await self.aio.hgetall(_chave(batch_id))  # type: ignore[misc]
        except RedisError:
            return None
        bruto = dados.pop("meta", None)
        if bruto is None:
            return None
        try:
            meta = json.loads(bruto)
            if meta["tenant_id"] != str(tenant_id):
                return None
            if usuario_id is not None and meta["usuario_id"] != str(usuario_id):
                return None
            if len(dados) != meta["total"]:
                return None
            return [ItemStatus.model_validate_json(v) for v in dados.values()]
        except (ValueError, KeyError, TypeError):  # inclui JSON e ValidationError
            return None

    async def preencher(self, lote: UploadBatch, itens: list[ItemStatus]) -> None:
        """Completa o cache com o que veio do banco, sem sobrescrever o que já existe."""
        chave = _chave(lote.id)
        try:
            async with self.aio.pipeline(transaction=False) as pipe:
                pipe.hsetnx(chave, "meta", _meta(lote))
                for i in itens:
                    pipe.hsetnx(chave, _campo(i.comprovante_id), i.model_dump_json())
                pipe.expire(chave, self.ttl_s)
                await pipe.execute()
        except RedisError as exc:
            log.warning("cache_lote_indisponivel", error=str(exc))


def get_lote_cache() -> LoteStatusCache:
    return LoteStatusCache(get_redis_sync(), get_redis())
