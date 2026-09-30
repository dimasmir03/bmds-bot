import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.image_job import ImageJob, JobStatus
from app.db.repositories.jobs import JobRepository
from app.db.repositories.users import UserRepository
from app.queue.base import JobQueue

ALLOWED_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.PENDING: {JobStatus.QUEUED, JobStatus.FAILED, JobStatus.CANCELLED},
    JobStatus.QUEUED: {JobStatus.PROCESSING, JobStatus.FAILED, JobStatus.CANCELLED},
    JobStatus.PROCESSING: {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED},
    JobStatus.COMPLETED: set(),
    JobStatus.FAILED: set(),
    JobStatus.CANCELLED: set(),
}


class InvalidJobTransitionError(ValueError):
    pass


def transition_job(job: ImageJob, target: JobStatus) -> None:
    if target not in ALLOWED_TRANSITIONS[job.status]:
        raise InvalidJobTransitionError(f"Cannot transition job from {job.status} to {target}")
    now = datetime.now(UTC)
    job.status = target
    if target == JobStatus.PROCESSING:
        job.started_at = now
    if target in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
        job.completed_at = now


class JobService:
    def __init__(self, session: AsyncSession, queue: JobQueue) -> None:
        self.session = session
        self.queue = queue
        self.jobs = JobRepository(session)
        self.users = UserRepository(session)

    async def create_job(
        self,
        *,
        telegram_user_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        telegram_chat_id: int,
        telegram_message_id: int | None,
        input_path: Path,
        prompt: str,
        provider: str,
        parent_job_id: uuid.UUID | None = None,
    ) -> ImageJob:
        clean_prompt = prompt.strip()
        if not clean_prompt:
            raise ValueError("Prompt must not be empty")
        user = await self.users.get_or_create(telegram_user_id, username, first_name, last_name)
        job = await self.jobs.add(
            ImageJob(
                user_id=user.id,
                telegram_chat_id=telegram_chat_id,
                telegram_message_id=telegram_message_id,
                input_file_path=str(input_path),
                prompt=clean_prompt,
                provider=provider,
                status=JobStatus.PENDING,
                parent_job_id=parent_job_id,
            )
        )
        await self.session.commit()
        transition_job(job, JobStatus.QUEUED)
        await self.session.commit()
        try:
            await self.queue.enqueue(job.id)
        except Exception:
            transition_job(job, JobStatus.FAILED)
            job.error_message = "Queue unavailable"
            await self.session.commit()
            raise
        return job

    async def request_cancel(self, telegram_user_id: int) -> ImageJob | None:
        job = await self.jobs.latest_active_for_telegram_user(telegram_user_id)
        if job is None:
            return None
        if job.status in {JobStatus.PENDING, JobStatus.QUEUED}:
            transition_job(job, JobStatus.CANCELLED)
        elif job.status == JobStatus.PROCESSING:
            job.cancel_requested = True
        await self.session.commit()
        return job

    async def latest_for_telegram_user(self, telegram_user_id: int) -> ImageJob | None:
        user = await self.users.get_by_telegram_id(telegram_user_id)
        if user is None:
            return None
        return await self.jobs.latest_for_user(user.id)
