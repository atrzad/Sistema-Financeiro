import httpx
import pytest
from sqlalchemy import update

from app.db.tenant import tenant_session
from app.models import RefreshToken
from tests.conftest import SENHA, DemoTenant, bearer, login

LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"


async def _refresh_com(api: httpx.AsyncClient, token: str) -> httpx.Response:
    """Apresenta um refresh token específico, como faria outro navegador/atacante."""
    async with httpx.AsyncClient(transport=api._transport, base_url="https://testserver") as c:
        return await c.post(REFRESH, headers={"Cookie": f"refresh_token={token}"})


def _body(slug: str, email: str, senha: str = SENHA) -> dict[str, str]:
    return {"tenant_slug": slug, "email": email, "senha": senha}


async def test_login_retorna_token_usuario_e_cookie_seguro(
    api: httpx.AsyncClient, acme: DemoTenant
) -> None:
    resp = await api.post(LOGIN, json=_body("acme", "colaborador@acme.com.br"))

    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 900
    assert body["user"]["role"] == "colaborador"
    assert body["user"]["tenant"]["slug"] == "acme"
    cookie = resp.headers["set-cookie"].lower()
    for flag in ("httponly", "secure", "samesite=strict", "path=/api/v1/auth"):
        assert flag in cookie
    assert resp.headers["cache-control"] == "no-store"


async def test_login_ignora_maiusculas_e_espacos(api: httpx.AsyncClient, acme: DemoTenant) -> None:
    resp = await api.post(LOGIN, json=_body(" ACME ", " Colaborador@ACME.com.br "))
    assert resp.status_code == 200


@pytest.mark.parametrize(
    ("slug", "email", "senha"),
    [
        ("acme", "colaborador@acme.com.br", "senha-errada"),
        ("acme", "ninguem@acme.com.br", SENHA),
        ("inexistente", "colaborador@acme.com.br", SENHA),
        ("globex", "colaborador@acme.com.br", SENHA),  # usuário existe, mas em outra empresa
    ],
)
async def test_credenciais_invalidas_tem_mensagem_generica(
    api: httpx.AsyncClient, acme: DemoTenant, globex: DemoTenant, slug: str, email: str, senha: str
) -> None:
    resp = await api.post(LOGIN, json=_body(slug, email, senha))

    assert resp.status_code == 401
    assert resp.headers["content-type"] == "application/problem+json"
    assert resp.json()["detail"] == "Empresa, e-mail ou senha incorretos."
    assert "set-cookie" not in resp.headers


async def test_bloqueia_apos_cinco_falhas(api: httpx.AsyncClient, acme: DemoTenant) -> None:
    for _ in range(5):
        r = await api.post(LOGIN, json=_body("acme", "colaborador@acme.com.br", "errada"))
        assert r.status_code == 401

    # Mesmo com a senha certa, fica bloqueado até a janela expirar.
    resp = await api.post(LOGIN, json=_body("acme", "colaborador@acme.com.br"))
    assert resp.status_code == 429
    assert int(resp.headers["retry-after"]) > 0

    # Outro usuário não é afetado.
    assert (await api.post(LOGIN, json=_body("acme", "admin@acme.com.br"))).status_code == 200


async def test_sucesso_zera_contador_de_falhas(api: httpx.AsyncClient, acme: DemoTenant) -> None:
    for _ in range(4):
        await api.post(LOGIN, json=_body("acme", "colaborador@acme.com.br", "errada"))
    assert (await api.post(LOGIN, json=_body("acme", "colaborador@acme.com.br"))).status_code == 200
    for _ in range(4):
        await api.post(LOGIN, json=_body("acme", "colaborador@acme.com.br", "errada"))
    assert (await api.post(LOGIN, json=_body("acme", "colaborador@acme.com.br"))).status_code == 200


async def test_validacao_retorna_problem_details(api: httpx.AsyncClient) -> None:
    resp = await api.post(LOGIN, json={"tenant_slug": "acme"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["title"] == "Dados inválidos"
    assert {e["campo"] for e in body["errors"]} == {"email", "senha"}


async def test_me_exige_token_valido(api: httpx.AsyncClient, acme: DemoTenant) -> None:
    sem = await api.get("/api/v1/me")
    assert sem.status_code == 401
    assert sem.headers["www-authenticate"] == "Bearer"
    assert (await api.get("/api/v1/me", headers=bearer("lixo"))).status_code == 401

    token = await login(api, "acme", "aprovador@acme.com.br")
    me = await api.get("/api/v1/me", headers=bearer(token))
    assert me.status_code == 200
    assert me.json()["email"] == "aprovador@acme.com.br"
    assert me.json()["nivel_aprovacao"] == 1


async def test_refresh_rotaciona_o_token(api: httpx.AsyncClient, acme: DemoTenant) -> None:
    await login(api, "acme", "colaborador@acme.com.br")
    primeiro = api.cookies["refresh_token"]

    resp = await api.post(REFRESH)

    assert resp.status_code == 200
    segundo = api.cookies["refresh_token"]
    assert segundo != primeiro
    me = await api.get("/api/v1/me", headers=bearer(resp.json()["access_token"]))
    assert me.status_code == 200


async def test_reuso_de_refresh_revoga_a_familia_inteira(
    api: httpx.AsyncClient, acme: DemoTenant
) -> None:
    await login(api, "acme", "colaborador@acme.com.br")
    roubado = api.cookies["refresh_token"]
    assert (await api.post(REFRESH)).status_code == 200  # usuário legítimo rotaciona
    legitimo = api.cookies["refresh_token"]

    # Atacante reapresenta o token antigo.
    assert (await _refresh_com(api, roubado)).status_code == 401

    # A sessão do usuário legítimo também caiu.
    assert (await _refresh_com(api, legitimo)).status_code == 401


async def test_refresh_sem_cookie_ou_malformado(api: httpx.AsyncClient, acme: DemoTenant) -> None:
    assert (await api.post(REFRESH)).status_code == 401
    assert (await _refresh_com(api, "lixo")).status_code == 401
    assert (await _refresh_com(api, f"{acme.id}.inexistente")).status_code == 401


async def test_refresh_expirado(api: httpx.AsyncClient, acme: DemoTenant) -> None:
    await login(api, "acme", "colaborador@acme.com.br")
    async with tenant_session(acme.id) as db:
        await db.execute(update(RefreshToken).values(expires_at=RefreshToken.created_at))
    assert (await api.post(REFRESH)).status_code == 401


async def test_logout_revoga_e_limpa_cookie(api: httpx.AsyncClient, acme: DemoTenant) -> None:
    await login(api, "acme", "colaborador@acme.com.br")
    token = api.cookies["refresh_token"]

    resp = await api.post(LOGOUT)

    assert resp.status_code == 204
    assert "refresh_token" not in api.cookies
    assert (await _refresh_com(api, token)).status_code == 401


async def test_logout_sem_sessao_e_idempotente(api: httpx.AsyncClient) -> None:
    assert (await api.post(LOGOUT)).status_code == 204
