import logging
import uuid
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.image_job import JobStatus
from app.db.repositories.jobs import JobRepository
from app.services.image_service import ImageService
from app.services.job_service import transition_job

logger = logging.getLogger(__name__)


class JobProcessor:
    def __init__(self, session: AsyncSession, image_service: ImageService, bot: Bot) -> None:
        self.session = session
        self.image_service = image_service
        self.bot = bot
        self.jobs = JobRepository(session)

    async def process(self, job_id: uuid.UUID) -> None:
        job = await self.jobs.get(job_id, for_update=True)
        if job is None:
            logger.warning("job_id=%s status=missing", job_id)
            return
        if job.status in {JobStatus.COMPLETED, JobStatus.CANCELLED, JobStatus.FAILED}:
            logger.info("job_id=%s status=%s action=skip", job.id, job.status.value)
            return
        if job.status != JobStatus.QUEUED:
            logger.warning("job_id=%s status=%s action=unexpected_skip", job.id, job.status.value)
            return

        transition_job(job, JobStatus.PROCESSING)
        await self.session.commit()
        telegram_chat_id = job.telegram_chat_id
        logger.info(
            "job_id=%s user_id=%s status=processing provider=%s",
            job.id,
            job.user_id,
            job.provider,
        )
        try:
            result = await self.image_service.edit(Path(job.input_file_path), job.prompt)
            if not result.success or not result.outputs:
                raise RuntimeError(result.error or "Provider returned no output")
            await self.session.refresh(job)
            output_path = result.outputs[0].path
            job.output_file_path = str(output_path)
            if job.cancel_requested:
                transition_job(job, JobStatus.CANCELLED)
                await self.session.commit()
                logger.info("job_id=%s status=cancelled", job.id)
                return
            transition_job(job, JobStatus.COMPLETED)
            await self.session.commit()
            try:
                await self.bot.send_document(
                    job.telegram_chat_id,
                    FSInputFile(output_path),
                    caption="Готово.",
                )
            except Exception:
                logger.exception("job_id=%s telegram_send=failed", job.id)
            logger.info("job_id=%s status=completed", job.id)
        except Exception as exc:
            logger.exception("job_id=%s status=failed", job.id)
            await self.session.rollback()
            failed_job = await self.jobs.get(job_id, for_update=True)
            if failed_job and failed_job.status == JobStatus.PROCESSING:
                failed_job.error_message = str(exc)[:2000]
                transition_job(failed_job, JobStatus.FAILED)
                await self.session.commit()
            try:
                await self.bot.send_message(telegram_chat_id, "Не удалось обработать изображение.")
            except Exception:
                logger.exception("job_id=%s telegram_error_notification=failed", job_id)
