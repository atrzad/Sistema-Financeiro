"""Engine e sessões do banco.

A partir da Sprint 01, toda sessão de negócio passará por `tenant_context()`,
que executa `SET LOCAL app.current_tenant` (ADR 0002).
"""

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

_null_pool = False


def use_null_pool() -> None:
    """Workers Celery: cada task roda num event loop novo, e conexões asyncpg não
    podem ser reaproveitadas entre loops — então nada de pool nesses processos."""
    global _null_pool
    _null_pool = True
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()


@lru_cache
def get_engine() -> AsyncEngine:
    settings = get_settings()
    if _null_pool:
        return create_async_engine(str(settings.database_url), poolclass=NullPool)
    return create_async_engine(
        str(settings.database_url),
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=5,
    )


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session
