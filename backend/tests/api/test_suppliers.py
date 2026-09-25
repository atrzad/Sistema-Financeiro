import httpx

from tests.conftest import DemoTenant, bearer, login

URL = "/api/v1/suppliers"


async def _h(api: httpx.AsyncClient, t: DemoTenant, who: str = "colaborador") -> dict[str, str]:
    return bearer(await login(api, t.slug, f"{who}@{t.slug}.com.br"))


async def test_cria_fornecedor_normalizando_cnpj(api: httpx.AsyncClient, acme: DemoTenant) -> None:
    body = {"nome_fantasia": " Padaria Central ", "cnpj": "11.222.333/0001-81"}
    r = await api.post(URL, json=body, headers=await _h(api, acme))
    assert r.status_code == 201
    d = r.json()
    assert d["nome_fantasia"] == "Padaria Central"
    assert d["cnpj"] == "11222333000181"
    assert d["cnpj_formatado"] == "11.222.333/0001-81"


async def test_aceita_cnpj_alfanumerico(api: httpx.AsyncClient, acme: DemoTenant) -> None:
    body = {"nome_fantasia": "Nova Empresa", "cnpj": "12.abc.345/01de-35"}
    r = await api.post(URL, json=body, headers=await _h(api, acme))
    assert r.status_code == 201
    assert r.json()["cnpj_formatado"] == "12.ABC.345/01DE-35"


async def test_cnpj_invalido_da_422(api: httpx.AsyncClient, acme: DemoTenant) -> None:
    body = {"nome_fantasia": "X Ltda", "cnpj": "11.222.333/0001-82"}
    r = await api.post(URL, json=body, headers=await _h(api, acme))
    assert r.status_code == 422
    assert r.json()["errors"][0]["campo"] == "cnpj"


async def test_cnpj_duplicado_da_409_com_id_existente(
    api: httpx.AsyncClient, acme: DemoTenant, globex: DemoTenant
) -> None:
    h = await _h(api, acme)
    primeiro = await api.post(
        URL, json={"nome_fantasia": "Fornecedor A", "cnpj": "11222333000181"}, headers=h
    )
    r = await api.post(
        URL, json={"nome_fantasia": "Outro nome", "cnpj": "11.222.333/0001-81"}, headers=h
    )
    assert r.status_code == 409
    assert r.json()["existente_id"] == primeiro.json()["id"]
    # Outra empresa pode cadastrar o mesmo CNPJ.
    r = await api.post(
        URL,
        json={"nome_fantasia": "Fornecedor A", "cnpj": "11222333000181"},
        headers=await _h(api, globex),
    )
    assert r.status_code == 201


async def test_busca_tolera_acento_e_erro_de_digitacao(
    api: httpx.AsyncClient, acme: DemoTenant
) -> None:
    h = await _h(api, acme)
    for nome in ["Padaria Central", "Energia Elétrica S.A.", "Provedor Internet", "Papelaria Sol"]:
        await api.post(URL, json={"nome_fantasia": nome}, headers=h)

    r = await api.get(URL, params={"q": "energia eletrica"}, headers=h)
    assert r.json()[0]["nome_fantasia"] == "Energia Elétrica S.A."
    r = await api.get(URL, params={"q": "padaira"}, headers=h)  # erro de digitação
    assert r.json()[0]["nome_fantasia"] == "Padaria Central"
    r = await api.get(URL, params={"q": "pa"}, headers=h)
    assert {s["nome_fantasia"] for s in r.json()} >= {"Padaria Central", "Papelaria Sol"}


async def test_busca_por_inicio_do_cnpj(api: httpx.AsyncClient, acme: DemoTenant) -> None:
    h = await _h(api, acme)
    await api.post(URL, json={"nome_fantasia": "Alvo", "cnpj": "11222333000181"}, headers=h)
    r = await api.get(URL, params={"q": "11.222"}, headers=h)
    assert [s["nome_fantasia"] for s in r.json()] == ["Alvo"]


async def test_exclusao_logica_so_admin_e_libera_cnpj(
    api: httpx.AsyncClient, acme: DemoTenant
) -> None:
    h = await _h(api, acme)
    s = (
        await api.post(URL, json={"nome_fantasia": "Some", "cnpj": "11222333000181"}, headers=h)
    ).json()
    assert (await api.delete(f"{URL}/{s['id']}", headers=h)).status_code == 403
    admin = await _h(api, acme, "admin")
    assert (await api.delete(f"{URL}/{s['id']}", headers=admin)).status_code == 204
    assert (await api.get(f"{URL}/{s['id']}", headers=h)).status_code == 404
    assert (await api.get(URL, params={"q": "Some"}, headers=h)).json() == []
    # CNPJ volta a ficar disponível
    r = await api.post(URL, json={"nome_fantasia": "Nova", "cnpj": "11222333000181"}, headers=h)
    assert r.status_code == 201


async def test_editar_fornecedor(api: httpx.AsyncClient, acme: DemoTenant) -> None:
    h = await _h(api, acme)
    a = (
        await api.post(
            URL, json={"nome_fantasia": "Fornecedor A", "cnpj": "11222333000181"}, headers=h
        )
    ).json()
    b = (await api.post(URL, json={"nome_fantasia": "Fornecedor B"}, headers=h)).json()
    r = await api.patch(f"{URL}/{b['id']}", json={"razao_social": "B Serviços Ltda"}, headers=h)
    assert r.status_code == 200 and r.json()["razao_social"] == "B Serviços Ltda"
    r = await api.patch(f"{URL}/{b['id']}", json={"cnpj": "11222333000181"}, headers=h)
    assert r.status_code == 409
    r = await api.patch(f"{URL}/{a['id']}", json={"cnpj": "11222333000181"}, headers=h)
    assert r.status_code == 200  # o próprio CNPJ não conflita
