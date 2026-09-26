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
    "JWT_SECRET": "segredo-de-teste-com-pelo-menos-32-caracteres",
}
_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"
_file_values = {k: v for k, v in dotenv_values(_ROOT_ENV).items() if v is not None}
for key, value in {**_DEFAULTS, **_file_values}.items():
    os.environ.setdefault(key, value)
os.environ["ENVIRONMENT"] = "test"


def _test_database(url: str) -> str:
    """Os testes usam sempre <banco>_test (criado por infra/postgres/init/03-test-db.sh)
    e nunca o banco de desenvolvimento, pois limpam tabelas entre os testes."""
    from sqlalchemy.engine import make_url

    parsed = make_url(url)
    name = parsed.database or ""
    if not name.endswith("_test"):
        parsed = parsed.set(database=f"{name}_test")
    return parsed.render_as_string(hide_password=False)


for _key in ("DATABASE_URL", "DATABASE_URL_OWNER"):
    os.environ[_key] = _test_database(os.environ[_key])

# Bucket próprio dos testes: os arquivos validados ficam com retenção (Object Lock)
# e não podem se misturar aos de desenvolvimento.
os.environ["S3_BUCKET_COMPROVANTES"] = "comprovantes-test"
os.environ.setdefault("S3_PUBLIC_ENDPOINT_URL", os.environ["S3_ENDPOINT_URL"])

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


# --- Banco real (testes de integração) -------------------------------------------
import asyncio  # noqa: E402
import uuid  # noqa: E402
from collections.abc import AsyncIterator  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

import fakeredis  # noqa: E402
import httpx  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import DBAPIError  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.api.deps import get_auth_service  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.tenant import tenant_session  # noqa: E402
from app.models import Tenant, User  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402
from app.services.lote_cache import LoteStatusCache, get_lote_cache  # noqa: E402
from app.services.rate_limit import LoginRateLimiter  # noqa: E402
from tests.servicos import servico_indisponivel  # noqa: E402

SENHA = "Senha@123"
_SENHA_HASH = hash_password(SENHA)
_BACKEND = _Path(__file__).resolve().parents[1]


def alembic_config() -> Config:
    cfg = Config(str(_BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND / "migrations"))
    return cfg


async def _owner_exec(sql: str) -> None:
    engine = create_async_engine(str(get_settings().database_url_owner))
    try:
        async with engine.begin() as conn:
            await conn.execute(text(sql))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def database() -> None:
    """Garante banco acessível e migrado; pula os testes caso contrário."""
    try:
        asyncio.run(_owner_exec("SELECT 1"))
    except (OSError, DBAPIError) as exc:
        servico_indisponivel(f"Postgres indisponível: {exc!r}")
    command.upgrade(alembic_config(), "head")


@pytest.fixture
def clean_db(database: None) -> None:
    asyncio.run(_owner_exec("TRUNCATE tenants CASCADE"))


@dataclass
class DemoUser:
    id: uuid.UUID
    email: str
    role: str


@dataclass
class DemoTenant:
    id: uuid.UUID
    slug: str
    users: dict[str, DemoUser]


async def create_tenant(slug: str) -> DemoTenant:
    tenant_id = uuid.uuid4()
    users: dict[str, DemoUser] = {}
    async with tenant_session(tenant_id) as db:
        db.add(Tenant(id=tenant_id, nome=f"Empresa {slug}", slug=slug))
        await db.flush()
        for local, role, nivel in [
            ("admin", "admin", 2),
            ("aprovador", "aprovador", 1),
            ("colaborador", "colaborador", 0),
        ]:
            u = User(
                tenant_id=tenant_id,
                nome=f"{local.title()} {slug}",
                email=f"{local}@{slug}.com.br",
                password_hash=_SENHA_HASH,
                role=role,
                nivel_aprovacao=nivel,
            )
            db.add(u)
            await db.flush()
            users[local] = DemoUser(u.id, u.email, role)
    return DemoTenant(tenant_id, slug, users)


@pytest.fixture
async def acme(clean_db: None) -> DemoTenant:
    return await create_tenant("acme")


@pytest.fixture
async def globex(clean_db: None) -> DemoTenant:
    return await create_tenant("globex")


@pytest.fixture
def redis_server() -> fakeredis.FakeServer:
    return fakeredis.FakeServer()


@pytest.fixture
def fake_redis(redis_server: fakeredis.FakeServer) -> fakeredis.FakeAsyncRedis:
    return fakeredis.FakeAsyncRedis(server=redis_server, decode_responses=True)


@pytest.fixture
def lote_cache(
    redis_server: fakeredis.FakeServer, fake_redis: fakeredis.FakeAsyncRedis
) -> LoteStatusCache:
    """Cache de status de lote sobre o mesmo Redis falso (clientes síncrono e assíncrono)."""
    return LoteStatusCache(
        fakeredis.FakeRedis(server=redis_server, decode_responses=True), fake_redis
    )


@pytest.fixture
async def api(
    app: FastAPI, fake_redis: fakeredis.FakeAsyncRedis, lote_cache: LoteStatusCache
) -> AsyncIterator[httpx.AsyncClient]:
    settings = get_settings()
    app.dependency_overrides[get_auth_service] = lambda: AuthService(
        settings,
        LoginRateLimiter(fake_redis, settings.login_max_failures, settings.login_failure_window_s),
    )
    app.dependency_overrides[get_lote_cache] = lambda: lote_cache
    # https para que o cookie Secure de refresh seja armazenado pelo cliente
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://testserver"
    ) as client:
        yield client


async def login(client: httpx.AsyncClient, slug: str, email: str, senha: str = SENHA) -> str:
    resp = await client.post(
        "/api/v1/auth/login", json={"tenant_slug": slug, "email": email, "senha": senha}
    )
    assert resp.status_code == 200, resp.text
    token: str = resp.json()["access_token"]
    return token


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- Storage real (upload) --------------------------------------------------------


@pytest.fixture(scope="session")
def storage_bucket() -> str:
    """Garante o bucket de testes (com Object Lock); pula se o storage estiver fora."""
    from botocore.exceptions import BotoCoreError, ClientError

    from app.services.storage import get_s3_client

    bucket = get_settings().s3_bucket_comprovantes
    s3 = get_s3_client()
    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError:
        s3.create_bucket(Bucket=bucket, ObjectLockEnabledForBucket=True)
    except BotoCoreError as exc:
        servico_indisponivel(f"Storage indisponível: {exc!r}")
    return bucket
