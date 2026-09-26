"""Tags por tipo de conta: cadastro (admin) e uso nos lançamentos."""

from datetime import date
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.db.tenant import tenant_session
from app.domain.clock import get_clock
from app.services.cadastros_service import TAGS_PADRAO, garantir_tags_padrao
from tests.conftest import DemoTenant, bearer, login

TAGS = "/api/v1/tags"
LANC = "/api/v1/lancamentos"


@pytest.fixture(autouse=True)
def relogio_fixo(app: FastAPI) -> None:
    app.dependency_overrides[get_clock] = lambda: lambda: date(2026, 9, 25)


async def _h(api: httpx.AsyncClient, t: DemoTenant, who: str = "colaborador") -> dict[str, str]:
    return bearer(await login(api, t.slug, f"{who}@{t.slug}.com.br"))


async def _tag(api: httpx.AsyncClient, admin: dict[str, str], nome: str) -> str:
    r = await api.post(TAGS, json={"nome": nome}, headers=admin)
    assert r.status_code == 201, r.text
    tag_id: str = r.json()["id"]
    return tag_id


async def _lanc(api: httpx.AsyncClient, h: dict[str, str], **extra: Any) -> dict[str, Any]:
    body = {"valor": "100.00", "data_emissao": "2026-09-10", **extra}
    r = await api.post(LANC, json=body, headers=h)
    assert r.status_code == 201, r.text
    lanc: dict[str, Any] = r.json()
    return lanc


def _nomes(lanc: dict[str, Any]) -> list[str]:
    return [t["nome"] for t in lanc["tags"]]


# --- Cadastro --------------------------------------------------------------------


async def test_crud_de_tags_so_admin_altera(api: httpx.AsyncClient, acme: DemoTenant) -> None:
    admin, colab = await _h(api, acme, "admin"), await _h(api, acme)

    assert (await api.post(TAGS, json={"nome": "Aluguel"}, headers=colab)).status_code == 403
    tag_id = await _tag(api, admin, "Aluguel")
    # Mesmo nome com outra caixa é a mesma tag.
    assert (await api.post(TAGS, json={"nome": "ALUGUEL"}, headers=admin)).status_code == 409

    r = await api.patch(f"{TAGS}/{tag_id}", json={"nome": "Aluguel de imóvel"}, headers=admin)
    assert r.status_code == 200 and r.json()["nome"] == "Aluguel de imóvel"

    assert [t["nome"] for t in (await api.get(TAGS, headers=colab)).json()] == ["Aluguel de imóvel"]
    await api.patch(f"{TAGS}/{tag_id}", json={"ativo": False}, headers=admin)
    assert (await api.get(TAGS, headers=colab)).json() == []
    todas = (await api.get(TAGS, params={"incluir_inativos": True}, headers=colab)).json()
    assert todas == [{"id": tag_id, "nome": "Aluguel de imóvel", "ativo": False}]


async def test_tags_padrao_sao_idempotentes_e_ignoram_caixa(
    api: httpx.AsyncClient, acme: DemoTenant
) -> None:
    await _tag(api, await _h(api, acme, "admin"), "RECORRENTE")
    async with tenant_session(acme.id) as db:
        assert await garantir_tags_padrao(db, acme.id) == len(TAGS_PADRAO) - 1
    async with tenant_session(acme.id) as db:
        assert await garantir_tags_padrao(db, acme.id) == 0

    nomes = [t["nome"] for t in (await api.get(TAGS, headers=await _h(api, acme))).json()]
    assert len(nomes) == len(TAGS_PADRAO)
    assert "Folha de pagamento" in nomes and "RECORRENTE" in nomes


async def test_tag_de_outra_empresa_nao_e_editavel(
    api: httpx.AsyncClient, acme: DemoTenant, globex: DemoTenant
) -> None:
    tag_globex = await _tag(api, await _h(api, globex, "admin"), "Da Globex")
    r = await api.patch(
        f"{TAGS}/{tag_globex}", json={"nome": "invadida"}, headers=await _h(api, acme, "admin")
    )
    assert r.status_code == 404


# --- Lançamentos com tags ------------------------------------------------------------


async def test_lancamento_com_varias_tags(api: httpx.AsyncClient, acme: DemoTenant) -> None:
    admin = await _h(api, acme, "admin")
    recorrente = await _tag(api, admin, "Recorrente")
    conc = await _tag(api, admin, "Concessionárias")

    h = await _h(api, acme)
    criado = await _lanc(api, h, tag_ids=[recorrente, conc, recorrente])

    assert _nomes(criado) == ["Concessionárias", "Recorrente"]  # sem repetição, por nome
    lido = (await api.get(f"{LANC}/{criado['id']}", headers=h)).json()
    assert _nomes(lido) == ["Concessionárias", "Recorrente"]
    assert _nomes(await _lanc(api, h)) == []


async def test_edicao_substitui_ou_limpa_as_tags(api: httpx.AsyncClient, acme: DemoTenant) -> None:
    admin = await _h(api, acme, "admin")
    a, b = await _tag(api, admin, "Aquisição"), await _tag(api, admin, "Manutenção geral")
    h = await _h(api, acme)
    lanc = await _lanc(api, h, tag_ids=[a])
    url = f"{LANC}/{lanc['id']}"

    r = await api.patch(url, json={"tag_ids": [b]}, headers=h)
    assert _nomes(r.json()) == ["Manutenção geral"]
    assert r.json()["version"] == lanc["version"] + 1

    # Sem tag_ids no corpo, as tags ficam como estão.
    r = await api.patch(url, json={"descricao": "troca de lâmpadas"}, headers=h)
    assert _nomes(r.json()) == ["Manutenção geral"]

    r = await api.patch(url, json={"tag_ids": None}, headers=h)
    assert _nomes(r.json()) == []


async def test_tag_de_outra_empresa_e_recusada(
    api: httpx.AsyncClient, acme: DemoTenant, globex: DemoTenant
) -> None:
    """A FK do Postgres ignora o RLS; a API precisa barrar a tag de outra empresa."""
    tag_globex = await _tag(api, await _h(api, globex, "admin"), "Folha de pagamento")
    h = await _h(api, acme)

    r = await api.post(
        LANC,
        json={"valor": "1.00", "data_emissao": "2026-09-10", "tag_ids": [tag_globex]},
        headers=h,
    )
    assert r.status_code == 422
    assert r.json()["errors"] == [{"campo": "tag_ids", "erro": "inválido", "ids": [tag_globex]}]

    lanc = await _lanc(api, h)
    r = await api.patch(f"{LANC}/{lanc['id']}", json={"tag_ids": [tag_globex]}, headers=h)
    assert r.status_code == 422


async def test_tag_desativada_fica_nos_lancamentos_antigos(
    api: httpx.AsyncClient, acme: DemoTenant
) -> None:
    admin = await _h(api, acme, "admin")
    antiga = await _tag(api, admin, "Despesas administrativas")
    h = await _h(api, acme)
    lanc = await _lanc(api, h, tag_ids=[antiga])
    await api.patch(f"{TAGS}/{antiga}", json={"ativo": False}, headers=admin)

    # Não entra em lançamento novo...
    r = await api.post(
        LANC, json={"valor": "1.00", "data_emissao": "2026-09-10", "tag_ids": [antiga]}, headers=h
    )
    assert r.status_code == 422
    # ...mas continua onde já estava, inclusive ao reenviar o formulário com ela.
    r = await api.patch(f"{LANC}/{lanc['id']}", json={"tag_ids": [antiga]}, headers=h)
    assert r.status_code == 200 and _nomes(r.json()) == ["Despesas administrativas"]


async def test_filtro_por_tag_exige_todas(api: httpx.AsyncClient, acme: DemoTenant) -> None:
    admin = await _h(api, acme, "admin")
    rec, conc = await _tag(api, admin, "Recorrente"), await _tag(api, admin, "Concessionárias")
    h = await _h(api, acme)
    energia = await _lanc(api, h, descricao="energia", tag_ids=[rec, conc])
    software = await _lanc(api, h, descricao="software", tag_ids=[rec])
    await _lanc(api, h, descricao="avulso")

    async def ids(**params: Any) -> set[str]:
        r = await api.get(LANC, params=params, headers=h)
        assert r.status_code == 200, r.text
        return {i["id"] for i in r.json()["items"]}

    assert await ids(tag_id=rec) == {energia["id"], software["id"]}
    assert await ids(tag_id=[rec, conc]) == {energia["id"]}
    assert await ids(tag_id=conc) == {energia["id"]}


# --- Isolamento no banco -------------------------------------------------------------


async def test_lancamento_tags_isolado_por_empresa(
    api: httpx.AsyncClient, acme: DemoTenant, globex: DemoTenant
) -> None:
    admin = await _h(api, acme, "admin")
    lanc = await _lanc(api, admin, tag_ids=[await _tag(api, admin, "Recorrente")])

    async with tenant_session(acme.id) as db:
        linha = (
            await db.execute(
                text("SELECT tenant_id, tag_id FROM lancamento_tags WHERE lancamento_id = :l"),
                {"l": lanc["id"]},
            )
        ).one()
        assert linha.tenant_id == acme.id  # preenchido pelo banco a partir da sessão
    async with tenant_session(globex.id) as db:
        assert (await db.execute(text("SELECT count(*) FROM lancamento_tags"))).scalar_one() == 0

    with pytest.raises(DBAPIError, match="row-level security"):
        async with tenant_session(globex.id) as db:
            await db.execute(
                text(
                    "INSERT INTO lancamento_tags (tenant_id, lancamento_id, tag_id) "
                    "VALUES (:t, :l, :g)"
                ),
                {"t": str(acme.id), "l": lanc["id"], "g": str(linha.tag_id)},
            )
