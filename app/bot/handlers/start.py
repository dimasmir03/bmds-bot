from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.bot.states.image_edit import ImageEditStates

router = Router(name="start")

WELCOME = (
    "Я помогу отредактировать изображение.\n\n"
    "1. Отправьте изображение (JPEG, PNG или WEBP).\n"
    "2. Напишите, что нужно изменить.\n"
    "3. Дождитесь результата."
)


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(ImageEditStates.waiting_image)
    await message.answer(WELCOME)


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(
        f"{WELCOME}\n\n/status — состояние последней задачи\n/cancel — отменить текущую задачу"
    )
