import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.health import HealthService, get_health_service


async def _ok() -> None:
    return None


async def _falha() -> None:
    raise ConnectionRefusedError("recusado")


async def _lento() -> None:
    await asyncio.sleep(1)


def _usar(app: FastAPI, service: HealthService) -> None:
    app.dependency_overrides[get_health_service] = lambda: service


def test_todos_componentes_ok_retorna_200(app: FastAPI, client: TestClient) -> None:
    _usar(app, HealthService({"database": _ok, "redis": _ok, "storage": _ok}, timeout_s=0.5))

    resp = client.get("/api/v1/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert set(body["components"]) == {"database", "redis", "storage"}
    assert all(c["status"] == "ok" for c in body["components"].values())
    assert body["components"]["database"]["latency_ms"] is not None


def test_componente_fora_retorna_503_com_detalhe(app: FastAPI, client: TestClient) -> None:
    _usar(app, HealthService({"database": _ok, "redis": _falha}, timeout_s=0.5))

    resp = client.get("/api/v1/health")

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "error"
    assert body["components"]["database"]["status"] == "ok"
    assert body["components"]["redis"] == {
        "status": "error",
        "latency_ms": None,
        "detail": "ConnectionRefusedError",
    }


def test_componente_lento_estoura_timeout(app: FastAPI, client: TestClient) -> None:
    _usar(app, HealthService({"storage": _lento}, timeout_s=0.05))

    resp = client.get("/api/v1/health")

    assert resp.status_code == 503
    assert resp.json()["components"]["storage"]["detail"] == "timeout"
