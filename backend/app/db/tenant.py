"""Sessão de banco vinculada a um tenant (ADR 0002).

Toda query de negócio roda dentro de `tenant_session()`, que abre uma transação e
executa `set_config('app.current_tenant', <uuid>, true)` — equivalente a
`SET LOCAL`, válido só até o fim da transação (seguro com pool de conexões e
PgBouncer em transaction pooling). Sem isso, as policies de RLS não casam
nenhuma linha.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_sessionmaker


async def set_tenant(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    await session.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"), {"tid": str(tenant_id)}
    )


@asynccontextmanager
async def tenant_session(tenant_id: uuid.UUID) -> AsyncIterator[AsyncSession]:
    """Transação com o tenant definido. Commit ao sair sem erro; rollback caso contrário."""
    async with get_sessionmaker()() as session, session.begin():
        await set_tenant(session, tenant_id)
        yield session


async def resolve_tenant(slug: str) -> uuid.UUID | None:
    """Descobre o tenant pelo slug (função SECURITY DEFINER — só devolve o UUID)."""
    async with get_sessionmaker()() as session:
        result = await session.execute(text("SELECT resolve_tenant(:slug)"), {"slug": slug})
        value = result.scalar_one_or_none()
        return uuid.UUID(str(value)) if value else None
