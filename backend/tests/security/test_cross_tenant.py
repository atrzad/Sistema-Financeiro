"""Isolamento entre empresas (H1.5): o banco garante, mesmo se a aplicação errar.

Para cada endpoint novo, adicione uma linha em ENDPOINTS_POR_ID (acesso a um
recurso da outra empresa deve responder 404) ou ENDPOINTS_DE_LISTA.
"""

import uuid

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.db.session import get_sessionmaker
from app.db.tenant import set_tenant, tenant_session
from tests.conftest import DemoTenant, bearer, login

TABELAS = ["tenants", "users", "refresh_tokens"]


async def _contagens(tenant_id: uuid.UUID | None) -> dict[str, int]:
    async with get_sessionmaker()() as db, db.begin():
        if tenant_id:
            await set_tenant(db, tenant_id)
        # Nomes de tabela vêm da constante TABELAS acima, não de entrada externa.
        sql = "SELECT count(*) FROM {}"
        return {t: (await db.execute(text(sql.format(t)))).scalar_one() for t in TABELAS}


async def test_cada_tenant_ve_apenas_os_proprios_dados(
    api: httpx.AsyncClient, acme: DemoTenant, globex: DemoTenant
) -> None:
    await login(api, "acme", "admin@acme.com.br")  # gera refresh_tokens na acme
    await login(api, "globex", "admin@globex.com.br")

    assert await _contagens(acme.id) == {"tenants": 1, "users": 3, "refresh_tokens": 1}
    assert await _contagens(globex.id) == {"tenants": 1, "users": 3, "refresh_tokens": 1}


async def test_sem_tenant_definido_nada_e_visivel(acme: DemoTenant, globex: DemoTenant) -> None:
    assert await _contagens(None) == dict.fromkeys(TABELAS, 0)


async def test_nao_insere_dados_em_outra_empresa(acme: DemoTenant, globex: DemoTenant) -> None:
    with pytest.raises(DBAPIError, match="row-level security"):
        async with tenant_session(acme.id) as db:
            await db.execute(
                text(
                    "INSERT INTO users (tenant_id, nome, email, password_hash, role) "
                    "VALUES (:t, 'Invasor', 'x@x.com', 'h', 'admin')"
                ),
                {"t": str(globex.id)},
            )


async def test_nao_altera_dados_de_outra_empresa(acme: DemoTenant, globex: DemoTenant) -> None:
    async with tenant_session(acme.id) as db:
        result = await db.execute(
            text("UPDATE users SET nome = 'hackeado' WHERE tenant_id = :t"), {"t": str(globex.id)}
        )
        assert result.rowcount == 0  # type: ignore[attr-defined]


async def test_tenant_nao_vaza_entre_transacoes_na_mesma_conexao(
    acme: DemoTenant, globex: DemoTenant
) -> None:
    """SET LOCAL morre com a transação: uma conexão reaproveitada do pool não herda o tenant."""
    engine = create_async_engine(str(get_settings().database_url), pool_size=1, max_overflow=0)
    try:
        async with engine.connect() as conn:
            async with conn.begin():
                await conn.execute(
                    text("SELECT set_config('app.current_tenant', :t, true)"), {"t": str(acme.id)}
                )
                assert (await conn.execute(text("SELECT count(*) FROM users"))).scalar_one() == 3
            async with conn.begin():
                assert (await conn.execute(text("SELECT count(*) FROM users"))).scalar_one() == 0
    finally:
        await engine.dispose()


# --- Nível de API ---------------------------------------------------------------

ENDPOINTS_POR_ID = [
    ("PATCH", "/api/v1/users/{id}", {"nome": "Hackeado"}),
]


@pytest.mark.parametrize(("metodo", "rota", "corpo"), ENDPOINTS_POR_ID)
async def test_recurso_de_outra_empresa_responde_404(
    api: httpx.AsyncClient,
    acme: DemoTenant,
    globex: DemoTenant,
    metodo: str,
    rota: str,
    corpo: dict[str, str],
) -> None:
    h = bearer(await login(api, "acme", "admin@acme.com.br"))
    alvo = globex.users["colaborador"].id
    resp = await api.request(metodo, rota.format(id=alvo), json=corpo, headers=h)
    assert resp.status_code == 404


async def test_me_e_listas_mostram_so_a_propria_empresa(
    api: httpx.AsyncClient, acme: DemoTenant, globex: DemoTenant
) -> None:
    h = bearer(await login(api, "globex", "admin@globex.com.br"))
    assert (await api.get("/api/v1/me", headers=h)).json()["tenant"]["slug"] == "globex"
    emails = [u["email"] for u in (await api.get("/api/v1/users", headers=h)).json()]
    assert emails and all(e.endswith("@globex.com.br") for e in emails)
