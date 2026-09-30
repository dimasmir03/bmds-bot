import uuid
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.image_job import ImageJob, JobStatus
from app.services.job_service import (
    InvalidJobTransitionError,
    JobService,
    transition_job,
)


class FakeQueue:
    def __init__(self) -> None:
        self.items: list[uuid.UUID] = []

    async def enqueue(self, job_id: uuid.UUID) -> None:
        self.items.append(job_id)

    async def dequeue(self, wait_seconds: int = 0) -> uuid.UUID | None:
        return self.items.pop(0) if self.items else None

    async def close(self) -> None:
        return None


def test_job_state_transitions() -> None:
    job = ImageJob(status=JobStatus.PENDING)
    transition_job(job, JobStatus.QUEUED)
    transition_job(job, JobStatus.PROCESSING)
    transition_job(job, JobStatus.COMPLETED)
    assert job.started_at is not None
    assert job.completed_at is not None
    with pytest.raises(InvalidJobTransitionError):
        transition_job(job, JobStatus.PROCESSING)


@pytest.mark.asyncio
async def test_job_service_persists_and_enqueues(db_session: AsyncSession, tmp_path: Path) -> None:
    queue = FakeQueue()
    service = JobService(db_session, queue)

    job = await service.create_job(
        telegram_user_id=42,
        username="tester",
        first_name="Test",
        last_name=None,
        telegram_chat_id=42,
        telegram_message_id=10,
        input_path=tmp_path / "input.jpg",
        prompt="  darken the sky  ",
        provider="mock",
    )

    assert job.status == JobStatus.QUEUED
    assert job.prompt == "darken the sky"
    assert queue.items == [job.id]


@pytest.mark.asyncio
async def test_cancel_queued_job(db_session: AsyncSession, tmp_path: Path) -> None:
    queue = FakeQueue()
    service = JobService(db_session, queue)
    job = await service.create_job(
        telegram_user_id=7,
        username=None,
        first_name=None,
        last_name=None,
        telegram_chat_id=7,
        telegram_message_id=None,
        input_path=tmp_path / "input.jpg",
        prompt="edit",
        provider="mock",
    )

    cancelled = await service.request_cancel(7)

    assert cancelled is not None
    assert cancelled.id == job.id
    assert cancelled.status == JobStatus.CANCELLED
