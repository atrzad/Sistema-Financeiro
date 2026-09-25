"""Bloqueio temporário após falhas de login (H1.2: 5 falhas em 15 min → 429)."""

from redis.asyncio import Redis


class LoginRateLimiter:
    def __init__(self, redis: Redis, max_failures: int, window_s: int) -> None:
        self.redis = redis
        self.max_failures = max_failures
        self.window_s = window_s

    @staticmethod
    def _key(tenant_slug: str, email: str, ip: str) -> str:
        return f"login:falhas:{tenant_slug.lower()}:{email.lower()}:{ip}"

    async def retry_after(self, tenant_slug: str, email: str, ip: str) -> int | None:
        """Segundos até liberar, se bloqueado; None se pode tentar."""
        key = self._key(tenant_slug, email, ip)
        falhas = await self.redis.get(key)
        if falhas is not None and int(falhas) >= self.max_failures:
            ttl = await self.redis.ttl(key)
            return max(int(ttl), 1)
        return None

    async def register_failure(self, tenant_slug: str, email: str, ip: str) -> None:
        key = self._key(tenant_slug, email, ip)
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, self.window_s, nx=True)
            await pipe.execute()

    async def reset(self, tenant_slug: str, email: str, ip: str) -> None:
        await self.redis.delete(self._key(tenant_slug, email, ip))
