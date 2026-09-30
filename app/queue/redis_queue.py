import uuid

from redis.asyncio import Redis


class RedisJobQueue:
    def __init__(self, redis: Redis, queue_name: str = "image_jobs") -> None:
        self.redis = redis
        self.queue_name = queue_name

    async def enqueue(self, job_id: uuid.UUID) -> None:
        await self.redis.rpush(self.queue_name, str(job_id))

    async def dequeue(self, wait_seconds: int = 0) -> uuid.UUID | None:
        item = await self.redis.blpop(self.queue_name, timeout=wait_seconds)
        if item is None:
            return None
        return uuid.UUID(item[1].decode())

    async def close(self) -> None:
        await self.redis.aclose()
