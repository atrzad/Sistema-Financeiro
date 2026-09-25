import httpx
import pytest

from app.db.tenant import tenant_session
from app.services.cadastros_service import CATEGORIAS_PADRAO, garantir_categorias_padrao
from tests.conftest import DemoTenant, bearer, login


@pytest.mark.parametrize(
    ("url", "novo", "alterado"),
    [
        ("/api/v1/categorias", {"nome": "Viagens"}, {"nome": "Viagens nacionais"}),
        ("/api/v1/projetos", {"nome": "Cliente X"}, {"nome": "Cliente X — fase 2"}),
        ("/api/v1/centros-custo", {"codigo": "ADM-01", "nome": "Administrativo"}, {"nome": "Adm"}),
    ],
)
async def test_crud_de_cadastros(
    api: httpx.AsyncClient,
    acme: DemoTenant,
    url: str,
    novo: dict[str, str],
    alterado: dict[str, str],
) -> None:
    admin = bearer(await login(api, "acme", "admin@acme.com.br"))
    colab = bearer(await login(api, "acme", "colaborador@acme.com.br"))

    assert (await api.post(url, json=novo, headers=colab)).status_code == 403
    criado = await api.post(url, json=novo, headers=admin)
    assert criado.status_code == 201
    assert (await api.post(url, json=novo, headers=admin)).status_code == 409

    item_id = criado.json()["id"]
    r = await api.patch(f"{url}/{item_id}", json=alterado, headers=admin)
    assert r.status_code == 200 and r.json()["nome"] == alterado["nome"]

    # Colaborador lista; desativados somem da lista padrão.
    assert any(i["id"] == item_id for i in (await api.get(url, headers=colab)).json())
    await api.patch(f"{url}/{item_id}", json={"ativo": False}, headers=admin)
    assert all(i["id"] != item_id for i in (await api.get(url, headers=colab)).json())
    todos = (await api.get(url, params={"incluir_inativos": True}, headers=colab)).json()
    assert any(i["id"] == item_id and i["ativo"] is False for i in todos)


async def test_categorias_padrao_sao_idempotentes(acme: DemoTenant) -> None:
    async with tenant_session(acme.id) as db:
        assert await garantir_categorias_padrao(db, acme.id) == len(CATEGORIAS_PADRAO)
    async with tenant_session(acme.id) as db:
        assert await garantir_categorias_padrao(db, acme.id) == 0
