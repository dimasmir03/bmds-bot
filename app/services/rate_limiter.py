from redis.asyncio import Redis


class RateLimiter:
    def __init__(self, redis: Redis, limit: int, window_seconds: int) -> None:
        self.redis = redis
        self.limit = limit
        self.window_seconds = window_seconds

    async def allow(self, user_id: int) -> bool:
        key = f"rate:jobs:{user_id}"
        count = await self.redis.incr(key)
        if count == 1:
            await self.redis.expire(key, self.window_seconds)
        return count <= self.limit
