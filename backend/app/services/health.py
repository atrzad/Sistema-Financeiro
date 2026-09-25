"""Verificação de saúde dos componentes externos (Postgres, Redis, storage)."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from enum import StrEnum

from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import get_engine
from app.services.storage import get_s3_client

log = get_logger("health")


class Status(StrEnum):
    OK = "ok"
    ERROR = "error"


class ComponentHealth(BaseModel):
    status: Status
    latency_ms: float | None = None
    detail: str | None = None


class HealthReport(BaseModel):
    status: Status
    environment: str
    components: dict[str, ComponentHealth]


Check = Callable[[], Awaitable[None]]


async def _check_database() -> None:
    async with get_engine().connect() as conn:
        await conn.execute(text("SELECT 1"))


async def _check_redis() -> None:
    client = Redis.from_url(str(get_settings().redis_url))
    try:
        await client.ping()
    finally:
        await client.aclose()


async def _check_storage() -> None:
    settings = get_settings()
    await run_in_threadpool(get_s3_client().head_bucket, Bucket=settings.s3_bucket_comprovantes)


class HealthService:
    def __init__(self, checks: dict[str, Check] | None = None, timeout_s: float | None = None):
        self.checks = checks or {
            "database": _check_database,
            "redis": _check_redis,
            "storage": _check_storage,
        }
        self.timeout_s = timeout_s or get_settings().health_check_timeout_s

    async def _run(self, name: str, check: Check) -> ComponentHealth:
        start = time.perf_counter()
        try:
            await asyncio.wait_for(check(), timeout=self.timeout_s)
        except TimeoutError:
            return ComponentHealth(status=Status.ERROR, detail="timeout")
        except Exception as exc:
            # Detalhe genérico na resposta; causa completa só no log.
            log.warning("health_check_failed", component=name, error=repr(exc))
            return ComponentHealth(status=Status.ERROR, detail=type(exc).__name__)
        return ComponentHealth(
            status=Status.OK, latency_ms=round((time.perf_counter() - start) * 1000, 1)
        )

    async def report(self) -> HealthReport:
        names = list(self.checks)
        results = await asyncio.gather(*(self._run(n, self.checks[n]) for n in names))
        components = dict(zip(names, results, strict=True))
        overall = (
            Status.OK if all(c.status is Status.OK for c in components.values()) else Status.ERROR
        )
        return HealthReport(
            status=overall,
            environment=get_settings().environment.value,
            components=components,
        )


def get_health_service() -> HealthService:
    return HealthService()
