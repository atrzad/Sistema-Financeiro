from collections.abc import Callable
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Environment, Settings
from app.main import create_app


def test_gera_request_id_quando_ausente(client: TestClient) -> None:
    resp = client.get("/api/v1/_nao_existe")
    rid = resp.headers["X-Request-ID"]
    assert len(rid) == 32


def test_propaga_request_id_valido(client: TestClient) -> None:
    resp = client.get("/api/v1/_nao_existe", headers={"X-Request-ID": "abc-123"})
    assert resp.headers["X-Request-ID"] == "abc-123"


def test_substitui_request_id_invalido(client: TestClient) -> None:
    resp = client.get("/api/v1/_nao_existe", headers={"X-Request-ID": "<script>"})
    assert resp.headers["X-Request-ID"] != "<script>"


def test_cors_permite_origem_do_frontend(client: TestClient) -> None:
    resp = client.options(
        "/api/v1/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_bloqueia_origem_desconhecida(client: TestClient) -> None:
    resp = client.options(
        "/api/v1/health",
        headers={"Origin": "https://malicioso.example", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in resp.headers


def test_rota_debug_existe_em_local(client: TestClient) -> None:
    fake = MagicMock(id="t-1")
    with patch("app.api.v1.debug.ping.delay", return_value=fake) as delay:
        resp = client.post("/api/v1/_debug/ping-worker")
    assert resp.status_code == 202
    assert resp.json() == {"task_id": "t-1"}
    delay.assert_called_once_with("api")


def test_rota_debug_nao_existe_em_producao(make_settings: Callable[..., Settings]) -> None:
    app = create_app(make_settings(environment=Environment.PRODUCTION))
    with TestClient(app) as c:
        assert c.post("/api/v1/_debug/ping-worker").status_code == 404
        assert c.get("/docs").status_code == 404


def test_config_falha_rapido_sem_variavel_obrigatoria(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL")
    with pytest.raises(ValidationError, match="database_url"):
        Settings(_env_file=None)


def test_cors_origins_aceita_lista_separada_por_virgula(
    make_settings: Callable[..., Settings],
) -> None:
    s = make_settings(cors_origins="http://a.com, http://b.com")
    assert s.cors_origins == ["http://a.com", "http://b.com"]
