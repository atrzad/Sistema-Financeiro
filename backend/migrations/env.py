"""Ambiente do Alembic.

As migrações rodam SEMPRE como `app_owner` (DATABASE_URL_OWNER). A API usa
`app_api`, que não é dono de nada e não ignora RLS (ADR 0002).
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Migrações escritas em SQL explícito (espelham docs/modelo-de-dados.md).
target_metadata = None


def _owner_url() -> str:
    url = config.attributes.get("url") or get_settings().database_url_owner
    if not url:
        raise RuntimeError("DATABASE_URL_OWNER não definida — migrações exigem a role app_owner.")
    return str(url)


def run_migrations_offline() -> None:
    context.configure(url=_owner_url(), literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def _do_run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(_owner_url())
    async with engine.connect() as connection:
        await connection.run_sync(_do_run)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
