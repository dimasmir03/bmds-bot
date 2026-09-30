from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.states.image_edit import ImageEditStates
from app.core.config import Settings
from app.queue.base import JobQueue
from app.services.job_service import JobService
from app.services.rate_limiter import RateLimiter

router = Router(name="jobs")


@router.message(Command("status"))
async def status_command(
    message: Message,
    session_factory: async_sessionmaker,
    job_queue: JobQueue,
) -> None:
    if message.from_user is None:
        return
    async with session_factory() as session:
        job = await JobService(session, job_queue).latest_for_telegram_user(message.from_user.id)
    if job is None:
        await message.answer("У вас пока нет задач.")
    else:
        await message.answer(f"Последняя задача: {job.id}\nСтатус: {job.status.value}")


# In `processing` the last photo is still in FSM data: a new description re-uses it,
# so the user can try several outfits on one photo.
@router.message(StateFilter(ImageEditStates.waiting_prompt, ImageEditStates.processing), F.text)
async def receive_prompt(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker,
    job_queue: JobQueue,
    rate_limiter: RateLimiter,
    settings: Settings,
) -> None:
    if message.from_user is None or not message.text or message.text.startswith("/"):
        await message.answer("Опишите текстом, во что вас одеть.")
        return
    data = await state.get_data()
    input_path = data.get("input_path")
    if not input_path:
        await state.set_state(ImageEditStates.waiting_image)
        await message.answer("Изображение не найдено. Отправьте его ещё раз.")
        return
    await submit_job(
        message,
        state,
        input_path=Path(input_path),
        prompt=message.text,
        session_factory=session_factory,
        job_queue=job_queue,
        rate_limiter=rate_limiter,
        settings=settings,
    )


async def submit_job(
    message: Message,
    state: FSMContext,
    *,
    input_path: Path,
    prompt: str,
    session_factory: async_sessionmaker,
    job_queue: JobQueue,
    rate_limiter: RateLimiter,
    settings: Settings,
) -> None:
    """Create a job for a saved photo and prompt; shared by the text and photo-caption flows."""
    if message.from_user is None:
        return
    if not await rate_limiter.allow(message.from_user.id):
        # Keep the photo so the user can retry with the same description later.
        await state.update_data(input_path=str(input_path))
        await state.set_state(ImageEditStates.waiting_prompt)
        await message.answer("Слишком много задач. Попробуйте немного позже.")
        return
    try:
        async with session_factory() as session:
            job = await JobService(session, job_queue).create_job(
                telegram_user_id=message.from_user.id,
                username=message.from_user.username,
                first_name=message.from_user.first_name,
                last_name=message.from_user.last_name,
                telegram_chat_id=message.chat.id,
                telegram_message_id=message.message_id,
                input_path=input_path,
                prompt=prompt,
                provider=settings.image_provider,
            )
    except Exception:
        await message.answer("Не удалось создать задачу. Попробуйте позже.")
        return
    await state.set_state(ImageEditStates.processing)
    await message.answer(f"Задача создана: {job.id}\nПодбираю образ…")
