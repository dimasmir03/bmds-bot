import uuid
from typing import Protocol


class JobQueue(Protocol):
    async def enqueue(self, job_id: uuid.UUID) -> None: ...

    async def dequeue(self, wait_seconds: int = 0) -> uuid.UUID | None: ...

    async def close(self) -> None: ...
