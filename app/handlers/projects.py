from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.keyboards.reply import projects_keyboard

projects_router = Router()


# Хэндлер для кнопки "⭐ Проекты"
@projects_router.message(F.text == "⭐ Проекты")
async def handle_projects_button(message: Message, session: AsyncSession):
    try:
        keyboard = await projects_keyboard(session)
        await message.answer(
            "Выберите интересующий вас проект:",
            reply_markup=keyboard.as_markup(
                resize_keyboard=True,
                one_time_keyboard=False
            )
        )
    except Exception as e:
        print(f"Ошибка при показе проектов: {e}")
        await message.answer("⚠ Произошла ошибка при загрузке проектов. Попробуйте позже.")


