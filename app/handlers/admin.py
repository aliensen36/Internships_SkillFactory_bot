from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from app.filters.chat_types import ChatTypeFilter, IsAdmin
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from sqlalchemy import select, func
from datetime import datetime, timedelta
from collections import defaultdict
from app.fsm_states import BroadcastState
from database.models import User


admin_router = Router()
admin_router.message.filter(ChatTypeFilter(["private"]), IsAdmin())


# Главная клавиатура
admin_main = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='📢 Рассылка'), KeyboardButton(text='⬅️ Назад')],
],
    resize_keyboard=True,
    input_field_placeholder='Выберите действие')


@admin_router.message(Command("admin"))
async def confirmation(message: Message):
    await message.answer("Что хотите сделать?", reply_markup=admin_main)


@admin_router.message(F.text == "📢 Рассылка")
async def start_broadcast(message: Message, state: FSMContext):
    await message.answer("📨 Введите текст рекламного сообщения:")
    await state.set_state(BroadcastState.waiting_for_text)


@admin_router.message(BroadcastState.waiting_for_text)
async def get_broadcast_text(message: Message, state: FSMContext):
    await state.update_data(text=message.text)
    await message.answer("📷 Теперь отправьте изображение (или напишите 'нет', если без фото).")
    await state.set_state(BroadcastState.waiting_for_photo)


@admin_router.message(BroadcastState.waiting_for_photo)
async def get_broadcast_photo(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    text = data.get("text")

    photo = None
    if message.photo:
        photo = message.photo[-1].file_id
    elif message.text.lower() == "нет":
        photo = None
    else:
        await message.answer("⚠ Пожалуйста, отправьте фото или напишите 'нет'.")
        return

    # Получаем список пользователей (пример функции ниже)
    result = await session.execute(select(User.tg_id))
    user_ids = [row[0] for row in result.fetchall()]

    success, fail = 0, 0

    for user_id in user_ids:
        try:
            if photo:
                await message.bot.send_photo(chat_id=user_id, photo=photo, caption=text)
            else:
                await message.bot.send_message(chat_id=user_id, text=text)
            success += 1
        except Exception:
            fail += 1

    await message.answer(f"✅ Рассылка завершена.\nУспешно: {success}\nОшибки: {fail}",
                         reply_markup=admin_main)
    await state.clear()
