from io import BytesIO
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.handlers.jobs import submit_job
from app.bot.states.image_edit import ImageEditStates
from app.core.config import Settings
from app.queue.base import JobQueue
from app.services.rate_limiter import RateLimiter
from app.services.storage_service import InvalidImageError, StorageService

router = Router(name="image")

HEIF_EXTENSIONS = {".heic": "image/heic", ".heif": "image/heif"}


def _document_mime_type(mime_type: str | None, file_name: str | None) -> str | None:
    # Some Telegram clients send HEIC files as application/octet-stream.
    if mime_type in {None, "application/octet-stream"} and file_name:
        return HEIF_EXTENSIONS.get(Path(file_name).suffix.lower(), mime_type)
    return mime_type


async def _receive_image(
    message: Message,
    state: FSMContext,
    bot: Bot,
    storage_service: StorageService,
    settings: Settings,
    session_factory: async_sessionmaker,
    job_queue: JobQueue,
    rate_limiter: RateLimiter,
) -> None:
    if message.photo:
        telegram_file = message.photo[-1]
        mime_type = "image/jpeg"
    elif message.document:
        telegram_file = message.document
        mime_type = _document_mime_type(message.document.mime_type, message.document.file_name)
    else:
        await message.answer("Отправьте изображение как фото или файл.")
        return
    if telegram_file.file_size and telegram_file.file_size > settings.max_image_size_bytes:
        await message.answer(f"Файл больше допустимых {settings.max_image_size_mb} МБ.")
        return
    buffer = BytesIO()
    try:
        await bot.download(telegram_file.file_id, destination=buffer)
        path = await storage_service.save_input(buffer.getvalue(), mime_type)
    except InvalidImageError as exc:
        await message.answer(str(exc))
        return
    except Exception:
        await message.answer("Не удалось скачать или сохранить изображение. Попробуйте ещё раз.")
        return
    await state.update_data(input_path=str(path), telegram_file_id=telegram_file.file_id)
    caption = (message.caption or "").strip()
    if caption:
        # Photo sent with a caption: the caption is the outfit description, start right away.
        await submit_job(
            message,
            state,
            input_path=path,
            prompt=caption,
            session_factory=session_factory,
            job_queue=job_queue,
            rate_limiter=rate_limiter,
            settings=settings,
        )
        return
    await state.set_state(ImageEditStates.waiting_prompt)
    await message.answer("Фото получено. Теперь опишите, во что вас одеть.")


# No state filter: a new photo starts a new try-on at any point, even while a job is processing.
@router.message(F.photo | F.document)
async def receive_image(
    message: Message,
    state: FSMContext,
    bot: Bot,
    storage_service: StorageService,
    settings: Settings,
    session_factory: async_sessionmaker,
    job_queue: JobQueue,
    rate_limiter: RateLimiter,
) -> None:
    await _receive_image(
        message,
        state,
        bot,
        storage_service,
        settings,
        session_factory,
        job_queue,
        rate_limiter,
    )


@router.message(ImageEditStates.waiting_prompt)
async def require_prompt(message: Message) -> None:
    await message.answer("Опишите текстом, во что вас одеть.")


# Fallback for any state, including none (e.g. lost FSM data): never stay silent.
@router.message()
async def require_image(message: Message) -> None:
    await message.answer(
        "Отправьте своё фото (JPEG, PNG, WEBP или HEIC). "
        "Описание одежды можно сразу добавить подписью к фото."
    )
