"""Execução de código assíncrono dentro das tasks Celery (que são síncronas)."""

import asyncio
from collections.abc import Coroutine
from typing import Any

from app.db.session import get_engine


def run_async[T](coro: Coroutine[Any, Any, T]) -> T:
    """Roda a corrotina num event loop próprio e devolve as conexões ao final.

    Cada task cria um loop novo (asyncio.run); conexões do asyncpg ficam presas ao
    loop em que nasceram. Nos processos do worker o engine usa NullPool (ver
    db.session.use_null_pool); o dispose final cobre qualquer outro uso.
    """

    async def _main() -> T:
        try:
            return await coro
        finally:
            await get_engine().dispose()

    return asyncio.run(_main())
