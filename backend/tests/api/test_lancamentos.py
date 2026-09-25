from datetime import date, timedelta
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text, update

from app.db.tenant import tenant_session
from app.domain.clock import get_clock
from app.models import Lancamento
from tests.conftest import DemoTenant, bearer, login

URL = "/api/v1/lancamentos"
HOJE = date(2026, 9, 25)


@pytest.fixture(autouse=True)
def relogio_fixo(app: FastAPI) -> None:
    app.dependency_overrides[get_clock] = lambda: lambda: HOJE


def _novo(**extra: Any) -> dict[str, Any]:
    return {"valor": "245.90", "data_emissao": "2026-09-10", **extra}


async def _h(api: httpx.AsyncClient, t: DemoTenant, who: str = "colaborador") -> dict[str, str]:
    return bearer(await login(api, t.slug, f"{who}@{t.slug}.com.br"))


async def _criar(api: httpx.AsyncClient, h: dict[str, str], **extra: Any) -> dict[str, Any]:
    r = await api.post(URL, json=_novo(**extra), headers=h)
    assert r.status_code == 201, r.text
    body: dict[str, Any] = r.json()
    return body


# --- Criação e validação ------------------------------------------------------------


async def test_cria_lancamento_com_status_derivado(
    api: httpx.AsyncClient, acme: DemoTenant
) -> None:
    h = await _h(api, acme)
    forn = (
        await api.post("/api/v1/suppliers", json={"nome_fantasia": "Energia S.A."}, headers=h)
    ).json()

    r = await api.post(
        URL,
        json=_novo(
            supplier_id=forn["id"],
            data_pagamento_prevista=HOJE.isoformat(),
            forma_pagamento="boleto",
            linha_digitavel="23793.38128 60000.000003 00000.000400 1 84340000024590",
        ),
        headers=h,
    )

    assert r.status_code == 201
    d = r.json()
    assert d["valor"] == "245.90"  # dinheiro sai como string decimal
    assert d["status"] == "pendente"
    assert d["status_efetivo"] == "vence_hoje"
    assert d["dias_para_vencimento"] == 0
    assert d["status_aprovacao"] == "rascunho"
    assert d["supplier"]["nome_fantasia"] == "Energia S.A."
    assert d["usuario"]["nome"] == "Colaborador acme"
    assert d["linha_digitavel"] == "23793381286000000000300000000400184340000024590"
    assert r.headers["etag"] == '"1"'


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("valor", "0"),
        ("valor", "-10"),
        ("valor", "12.345"),
        ("valor", "abc"),
        ("data_emissao", None),
    ],
)
async def test_validacao_de_campos(
    api: httpx.AsyncClient, acme: DemoTenant, campo: str, valor: Any
) -> None:
    body = _novo()
    body[campo] = valor
    r = await api.post(URL, json=body, headers=await _h(api, acme))
    assert r.status_code == 422
    assert r.json()["errors"][0]["campo"] == campo


async def test_referencia_de_outra_empresa_e_recusada(
    api: httpx.AsyncClient, acme: DemoTenant, globex: DemoTenant
) -> None:
    """A FK do Postgres ignora RLS; a API precisa barrar IDs de outra empresa."""
    h_globex = await _h(api, globex)
    forn_globex = (
        await api.post("/api/v1/suppliers", json={"nome_fantasia": "Da Globex"}, headers=h_globex)
    ).json()

    r = await api.post(URL, json=_novo(supplier_id=forn_globex["id"]), headers=await _h(api, acme))

    assert r.status_code == 422
    assert r.json()["errors"] == [{"campo": "supplier_id", "erro": "inválido"}]


async def test_categoria_inativa_e_recusada(api: httpx.AsyncClient, acme: DemoTenant) -> None:
    admin = await _h(api, acme, "admin")
    cat = (await api.post("/api/v1/categorias", json={"nome": "Antiga"}, headers=admin)).json()
    await api.patch(f"/api/v1/categorias/{cat['id']}", json={"ativo": False}, headers=admin)
    r = await api.post(URL, json=_novo(categoria_id=cat["id"]), headers=admin)
    assert r.status_code == 422


# --- Edição, concorrência e permissões ---------------------------------------------


async def test_edicao_com_controle_de_versao(api: httpx.AsyncClient, acme: DemoTenant) -> None:
    h = await _h(api, acme)
    lanc = await _criar(api, h)
    item = f"{URL}/{lanc['id']}"

    r = await api.patch(item, json={"valor": "300"}, headers={**h, "If-Match": '"1"'})
    assert r.status_code == 200
    assert r.json()["valor"] == "300.00" and r.json()["version"] == 2
    assert r.headers["etag"] == '"2"'

    # Outra aba ainda com a versão 1:
    r = await api.patch(item, json={"valor": "10"}, headers={**h, "If-Match": '"1"'})
    assert r.status_code == 412
    assert r.json()["versao_atual"] == 2

    # Limpar um campo opcional com null
    await api.patch(item, json={"descricao": "Conta de luz"}, headers=h)
    r = await api.patch(item, json={"descricao": None}, headers=h)
    assert r.json()["descricao"] is None


async def test_campos_obrigatorios_nao_podem_ser_limpos(
    api: httpx.AsyncClient, acme: DemoTenant
) -> None:
    h = await _h(api, acme)
    lanc = await _criar(api, h)
    r = await api.patch(f"{URL}/{lanc['id']}", json={"valor": None}, headers=h)
    assert r.status_code == 422


async def test_visibilidade_por_perfil(api: httpx.AsyncClient, acme: DemoTenant) -> None:
    colab = await _h(api, acme)
    aprovador = await _h(api, acme, "aprovador")
    admin = await _h(api, acme, "admin")
    do_colab = await _criar(api, colab)
    do_admin = await _criar(api, admin)

    def ids(r: httpx.Response) -> set[str]:
        return {i["id"] for i in r.json()["items"]}

    assert ids(await api.get(URL, headers=colab)) == {do_colab["id"]}
    assert ids(await api.get(URL, headers=aprovador)) == {do_colab["id"], do_admin["id"]}
    assert (await api.get(f"{URL}/{do_admin['id']}", headers=colab)).status_code == 404

    # Aprovador vê, mas não edita o que não é dele; admin edita tudo.
    item = f"{URL}/{do_colab['id']}"
    assert (await api.patch(item, json={"descricao": "x"}, headers=aprovador)).status_code == 403
    assert (await api.patch(item, json={"descricao": "x"}, headers=admin)).status_code == 200


async def test_lancamento_pago_protege_valor_e_vencimento(
    api: httpx.AsyncClient, acme: DemoTenant
) -> None:
    h = await _h(api, acme)
    lanc = await _criar(api, h, data_pagamento_prevista="2026-09-20")
    async with tenant_session(acme.id) as db:  # pagamento chega na Sprint 07
        await db.execute(
            update(Lancamento)
            .where(Lancamento.id == lanc["id"])
            .values(status="pago", data_pagamento_efetiva=HOJE)
        )
    item = f"{URL}/{lanc['id']}"

    assert (await api.patch(item, json={"valor": "1"}, headers=h)).status_code == 409
    r = await api.patch(item, json={"data_pagamento_prevista": "2026-10-01"}, headers=h)
    assert r.status_code == 409
    r = await api.patch(item, json={"descricao": "Pago no caixa"}, headers=h)
    assert r.status_code == 200
    assert r.json()["status_efetivo"] == "pago"
    assert (await api.delete(item, headers=h)).status_code == 409


async def test_exclusao_logica(api: httpx.AsyncClient, acme: DemoTenant) -> None:
    h = await _h(api, acme)
    lanc = await _criar(api, h)
    assert (await api.delete(f"{URL}/{lanc['id']}", headers=h)).status_code == 204
    assert (await api.get(f"{URL}/{lanc['id']}", headers=h)).status_code == 404
    assert (await api.get(URL, headers=h)).json()["items"] == []
    async with tenant_session(acme.id) as db:  # continua no banco para auditoria
        assert (await db.execute(text("SELECT count(*) FROM lancamentos"))).scalar_one() == 1


# --- Listagem --------------------------------------------------------------------------


async def test_ordem_por_vencimento_e_filtros_de_status(
    api: httpx.AsyncClient, acme: DemoTenant
) -> None:
    h = await _h(api, acme)
    sem_venc = await _criar(api, h, descricao="sem vencimento")
    futuro = await _criar(api, h, descricao="futuro", data_pagamento_prevista="2026-10-10")
    vencido = await _criar(api, h, descricao="vencido", data_pagamento_prevista="2026-09-01")
    hoje = await _criar(api, h, descricao="hoje", data_pagamento_prevista=HOJE.isoformat())

    r = await api.get(URL, headers=h)
    assert [i["descricao"] for i in r.json()["items"]] == [
        "vencido",
        "hoje",
        "futuro",
        "sem vencimento",
    ]

    def ids(resp: httpx.Response) -> list[str]:
        return [i["id"] for i in resp.json()["items"]]

    assert ids(await api.get(URL, params={"status": "atrasado"}, headers=h)) == [vencido["id"]]
    assert ids(await api.get(URL, params={"status": "vence_hoje"}, headers=h)) == [hoje["id"]]
    pendentes = await api.get(
        URL, params=[("status", "pendente"), ("status", "vence_hoje")], headers=h
    )
    assert ids(pendentes) == [hoje["id"], futuro["id"], sem_venc["id"]]
    faixa = await api.get(
        URL, params={"vencimento_de": "2026-09-20", "vencimento_ate": "2026-09-30"}, headers=h
    )
    assert ids(faixa) == [hoje["id"]]


async def test_paginacao_por_cursor_percorre_tudo_sem_repetir(
    api: httpx.AsyncClient, acme: DemoTenant
) -> None:
    h = await _h(api, acme)
    esperados = []
    for i in range(7):
        prevista = (HOJE + timedelta(days=i % 3)).isoformat() if i < 5 else None
        esperados.append((await _criar(api, h, data_pagamento_prevista=prevista))["id"])

    vistos: list[str] = []
    cursor = None
    paginas = 0
    while True:
        params: dict[str, Any] = {"limit": 3}
        if cursor:
            params["cursor"] = cursor
        body = (await api.get(URL, params=params, headers=h)).json()
        vistos += [i["id"] for i in body["items"]]
        paginas += 1
        cursor = body["next_cursor"]
        if not cursor:
            break

    assert paginas == 3
    assert sorted(vistos) == sorted(esperados)
    assert len(vistos) == len(set(vistos))


async def test_cursor_invalido_da_400(api: httpx.AsyncClient, acme: DemoTenant) -> None:
    r = await api.get(URL, params={"cursor": "lixo"}, headers=await _h(api, acme))
    assert r.status_code == 400
