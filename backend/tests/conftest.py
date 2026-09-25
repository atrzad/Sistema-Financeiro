import os
from pathlib import Path

from dotenv import dotenv_values

# Valores padrão para os testes unitários (não abrem conexão). Precedência:
# variáveis de ambiente reais (ex.: CI) > .env da raiz do monorepo > padrões abaixo.
_DEFAULTS = {
    "DATABASE_URL": "postgresql+asyncpg://app_api:api_dev_password@localhost:5432/financeiro",
    "DATABASE_URL_OWNER": "postgresql+asyncpg://app_owner:owner_dev_password@localhost:5432/financeiro",
    "REDIS_URL": "redis://localhost:6379/0",
    "S3_ENDPOINT_URL": "http://localhost:9000",
    "S3_ACCESS_KEY": "devaccesskey",
    "S3_SECRET_KEY": "devsecretkey123",
    "CORS_ORIGINS": "http://localhost:5173",
}
_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"
_file_values = {k: v for k, v in dotenv_values(_ROOT_ENV).items() if v is not None}
for key, value in {**_DEFAULTS, **_file_values}.items():
    os.environ.setdefault(key, value)
os.environ["ENVIRONMENT"] = "test"

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
