import uuid

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.image_job import ImageJob, JobStatus


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, job: ImageJob) -> ImageJob:
        self.session.add(job)
        await self.session.flush()
        return job

    async def get(self, job_id: uuid.UUID, *, for_update: bool = False) -> ImageJob | None:
        query = select(ImageJob).where(ImageJob.id == job_id)
        if for_update:
            query = query.with_for_update()
        return await self.session.scalar(query)

    async def latest_for_user(self, user_id: int) -> ImageJob | None:
        return await self.session.scalar(
            select(ImageJob)
            .where(ImageJob.user_id == user_id)
            .order_by(desc(ImageJob.created_at))
            .limit(1)
        )

    async def latest_active_for_telegram_user(self, telegram_user_id: int) -> ImageJob | None:
        from app.db.models.user import User

        return await self.session.scalar(
            select(ImageJob)
            .join(User)
            .where(
                User.telegram_user_id == telegram_user_id,
                ImageJob.status.in_([JobStatus.PENDING, JobStatus.QUEUED, JobStatus.PROCESSING]),
            )
            .order_by(desc(ImageJob.created_at))
            .limit(1)
        )
