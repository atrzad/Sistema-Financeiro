import os

# Valores padrão para os testes unitários (não abrem conexão). Variáveis reais
# do ambiente (ex.: CI) têm precedência.
_DEFAULTS = {
    "ENVIRONMENT": "test",
    "DATABASE_URL": "postgresql+asyncpg://app_api:api_dev_password@localhost:5432/financeiro",
    "DATABASE_URL_OWNER": "postgresql+asyncpg://app_owner:owner_dev_password@localhost:5432/financeiro",
    "REDIS_URL": "redis://localhost:6379/0",
    "S3_ENDPOINT_URL": "http://localhost:9000",
    "S3_ACCESS_KEY": "minioadmin",
    "S3_SECRET_KEY": "minioadmin",
    "CORS_ORIGINS": "http://localhost:5173",
}
for key, value in _DEFAULTS.items():
    os.environ.setdefault(key, value)

from collections.abc import Callable, Iterator  # noqa: E402

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import Environment, Settings  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture
def make_settings() -> Callable[..., Settings]:
    def _make(**overrides: object) -> Settings:
        return Settings(**overrides)  # type: ignore[arg-type]

    return _make


@pytest.fixture
def app(make_settings: Callable[..., Settings]) -> FastAPI:
    return create_app(make_settings(environment=Environment.TEST))


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c
