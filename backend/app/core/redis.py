from functools import lru_cache

from redis import Redis as SyncRedis
from redis.asyncio import Redis

from app.core.config import get_settings


@lru_cache
def get_redis() -> Redis:
    client: Redis = Redis.from_url(str(get_settings().redis_url), decode_responses=True)
    return client


@lru_cache
def get_redis_sync() -> SyncRedis:
    """Para código síncrono: callbacks pós-commit (ver db.hooks) e tasks Celery."""
    client: SyncRedis = SyncRedis.from_url(
        str(get_settings().redis_url), decode_responses=True, socket_timeout=2
    )
    return client
