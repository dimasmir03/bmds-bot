from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.bot.states.image_edit import ImageEditStates
from app.queue.base import JobQueue
from app.services.job_service import JobService

router = Router(name="cancel")


@router.message(Command("cancel"))
async def cancel_command(
    message: Message,
    state: FSMContext,
    session_factory: async_sessionmaker,
    job_queue: JobQueue,
) -> None:
    if message.from_user is None:
        return
    current_state = await state.get_state()
    if current_state in {
        ImageEditStates.waiting_image.state,
        ImageEditStates.waiting_prompt.state,
    }:
        await state.clear()
        await state.set_state(ImageEditStates.waiting_image)
        await message.answer("Действие отменено. Можете отправить новое изображение.")
        return
    async with session_factory() as session:
        job = await JobService(session, job_queue).request_cancel(message.from_user.id)
    await state.clear()
    await state.set_state(ImageEditStates.waiting_image)
    if job is None:
        await message.answer("Активных задач нет.")
    elif job.cancel_requested:
        await message.answer("Отмена запрошена. Результат отправлен не будет.")
    else:
        await message.answer("Задача отменена.")
