"""Testes contra Postgres real (com os scripts de infra/postgres/init aplicados).

Pulados automaticamente se o banco não estiver acessível. No CI, rodam sempre.
"""

import asyncio
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings

pytestmark = pytest.mark.integration

BACKEND = Path(__file__).resolve().parents[1]


def _run[T](coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


async def _query(url: str, sql: str) -> list[tuple[object, ...]]:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            return [tuple(r) for r in (await conn.execute(text(sql))).all()]
    finally:
        await engine.dispose()


def _alembic_cfg() -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    return cfg


@pytest.fixture(scope="module")
def urls() -> tuple[str, str]:
    s = get_settings()
    api, owner = str(s.database_url), str(s.database_url_owner)
    try:
        _run(_query(api, "SELECT 1"))
    except (OSError, DBAPIError) as exc:
        pytest.skip(f"Postgres indisponível: {exc!r}")
    command.upgrade(_alembic_cfg(), "head")
    return api, owner


def test_app_api_nao_e_superuser_nem_ignora_rls(urls: tuple[str, str]) -> None:
    api, _ = urls
    [(superuser, bypass)] = _run(
        _query(api, "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
    )
    assert superuser is False
    assert bypass is False


def test_app_api_nao_e_dono_de_nenhuma_tabela(urls: tuple[str, str]) -> None:
    api, _ = urls
    rows = _run(_query(api, "SELECT tablename FROM pg_tables WHERE tableowner = 'app_api'"))
    assert rows == []


def test_app_api_nao_pode_criar_tabelas(urls: tuple[str, str]) -> None:
    api, _ = urls
    with pytest.raises(DBAPIError, match="permission denied"):
        _run(_query(api, "CREATE TABLE invasora (id int)"))


def test_app_api_pode_ler_tabelas_do_owner(urls: tuple[str, str]) -> None:
    api, _ = urls
    assert _run(_query(api, "SELECT count(*) FROM tenants")) is not None


def test_funcoes_utilitarias(urls: tuple[str, str]) -> None:
    api, _ = urls
    [(tenant, hoje)] = _run(_query(api, "SELECT app_current_tenant(), hoje_negocio()"))
    assert tenant is None  # sem SET LOCAL não há tenant
    assert hoje is not None


def test_downgrade_e_upgrade_completos(urls: tuple[str, str]) -> None:
    cfg = _alembic_cfg()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
