import httpx

from tests.conftest import DemoTenant, bearer, login

USERS = "/api/v1/users"


async def _admin(api: httpx.AsyncClient, t: DemoTenant) -> dict[str, str]:
    return bearer(await login(api, t.slug, f"admin@{t.slug}.com.br"))


async def test_admin_lista_apenas_usuarios_da_propria_empresa(
    api: httpx.AsyncClient, acme: DemoTenant, globex: DemoTenant
) -> None:
    resp = await api.get(USERS, headers=await _admin(api, acme))
    assert resp.status_code == 200
    emails = {u["email"] for u in resp.json()}
    assert emails == {"admin@acme.com.br", "aprovador@acme.com.br", "colaborador@acme.com.br"}


async def test_nao_admin_recebe_403(api: httpx.AsyncClient, acme: DemoTenant) -> None:
    for local in ("colaborador", "aprovador"):
        h = bearer(await login(api, "acme", f"{local}@acme.com.br"))
        assert (await api.get(USERS, headers=h)).status_code == 403
        novo = {"nome": "X Y", "email": "x@acme.com.br", "senha": "12345678"}
        assert (await api.post(USERS, json=novo, headers=h)).status_code == 403


async def test_admin_cria_usuario_que_consegue_entrar(
    api: httpx.AsyncClient, acme: DemoTenant, globex: DemoTenant
) -> None:
    novo = {
        "nome": "Nova Pessoa",
        "email": "Nova@Acme.com.br",
        "senha": "Segura@2026",
        "role": "aprovador",
        "nivel_aprovacao": 2,
        "tenant_id": str(globex.id),  # tentativa de criar em outra empresa: ignorada
    }
    resp = await api.post(USERS, json=novo, headers=await _admin(api, acme))

    assert resp.status_code == 201
    assert resp.json()["email"] == "nova@acme.com.br"
    assert "senha" not in resp.json() and "password_hash" not in resp.json()
    await login(api, "acme", "nova@acme.com.br", "Segura@2026")
    # não foi parar na globex
    assert (
        await api.post(
            "/api/v1/auth/login",
            json={"tenant_slug": "globex", "email": "nova@acme.com.br", "senha": "Segura@2026"},
        )
    ).status_code == 401


async def test_email_duplicado_na_mesma_empresa_da_409(
    api: httpx.AsyncClient, acme: DemoTenant, globex: DemoTenant
) -> None:
    dup = {"nome": "Outro", "email": "colaborador@acme.com.br", "senha": "12345678"}
    assert (await api.post(USERS, json=dup, headers=await _admin(api, acme))).status_code == 409
    # O mesmo e-mail em outra empresa é permitido.
    assert (await api.post(USERS, json=dup, headers=await _admin(api, globex))).status_code == 201


async def test_regras_de_nivel_por_papel(api: httpx.AsyncClient, acme: DemoTenant) -> None:
    h = await _admin(api, acme)
    base = {"nome": "Fulano", "senha": "12345678"}
    r = await api.post(
        USERS,
        json={**base, "email": "a@acme.com.br", "role": "colaborador", "nivel_aprovacao": 2},
        headers=h,
    )
    assert r.status_code == 422
    r = await api.post(
        USERS,
        json={**base, "email": "b@acme.com.br", "role": "aprovador", "nivel_aprovacao": 0},
        headers=h,
    )
    assert r.status_code == 422
    r = await api.post(USERS, json={**base, "email": "c@acme", "senha": "curta"}, headers=h)
    assert r.status_code == 422
    assert {e["campo"] for e in r.json()["errors"]} == {"email", "senha"}


async def test_promover_colaborador_a_aprovador(api: httpx.AsyncClient, acme: DemoTenant) -> None:
    uid = acme.users["colaborador"].id
    resp = await api.patch(
        f"{USERS}/{uid}",
        json={"role": "aprovador", "nivel_aprovacao": 1},
        headers=await _admin(api, acme),
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "aprovador"
    # O novo papel vale no próximo token.
    me = await api.get(
        "/api/v1/me", headers=bearer(await login(api, "acme", "colaborador@acme.com.br"))
    )
    assert me.json()["role"] == "aprovador"


async def test_rebaixar_para_colaborador_zera_nivel(
    api: httpx.AsyncClient, acme: DemoTenant
) -> None:
    uid = acme.users["aprovador"].id
    resp = await api.patch(
        f"{USERS}/{uid}", json={"role": "colaborador"}, headers=await _admin(api, acme)
    )
    assert resp.status_code == 200
    assert resp.json()["nivel_aprovacao"] == 0


async def test_admin_nao_se_tranca_para_fora(api: httpx.AsyncClient, acme: DemoTenant) -> None:
    h = await _admin(api, acme)
    me = acme.users["admin"].id
    assert (await api.patch(f"{USERS}/{me}", json={"ativo": False}, headers=h)).status_code == 409
    r = await api.patch(f"{USERS}/{me}", json={"role": "colaborador"}, headers=h)
    assert r.status_code == 409


async def test_desativar_derruba_sessoes_e_bloqueia_login(
    api: httpx.AsyncClient, acme: DemoTenant
) -> None:
    # colaborador entra em um "navegador"
    async with httpx.AsyncClient(transport=api._transport, base_url="https://testserver") as outro:
        await login(outro, "acme", "colaborador@acme.com.br")

        uid = acme.users["colaborador"].id
        resp = await api.patch(
            f"{USERS}/{uid}", json={"ativo": False}, headers=await _admin(api, acme)
        )
        assert resp.status_code == 200 and resp.json()["ativo"] is False

        assert (await outro.post("/api/v1/auth/refresh")).status_code == 401
    r = await api.post(
        "/api/v1/auth/login",
        json={"tenant_slug": "acme", "email": "colaborador@acme.com.br", "senha": "Senha@123"},
    )
    assert r.status_code == 401


async def test_usuario_inexistente_da_404(api: httpx.AsyncClient, acme: DemoTenant) -> None:
    r = await api.patch(
        f"{USERS}/00000000-0000-0000-0000-000000000000",
        json={"nome": "Nome"},
        headers=await _admin(api, acme),
    )
    assert r.status_code == 404
