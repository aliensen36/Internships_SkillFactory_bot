import os
from aiofiles import open as aio_open
from aiogram.types import FSInputFile
from aiogram import F, Router, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from app.filters.chat_types import ChatTypeFilter, IsAdmin
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from sqlalchemy import select, func
from datetime import datetime, timedelta
from collections import defaultdict
from app.fsm_states import BroadcastState
from app.keyboards.reply import kb_admin_main
from database.models import User, Specialization, Course, Broadcast


admin_broadcast_router = Router()
admin_broadcast_router.message.filter(ChatTypeFilter(["private"]), IsAdmin())

MEDIA_DIR = 'media/images'


@admin_broadcast_router.message(F.text == "📢 Рассылка")
async def start_broadcast(message: Message, state: FSMContext):
    await message.answer("📨 Введите текст сообщения для рассылки:")
    await state.set_state(BroadcastState.waiting_for_text)

# Получение текста
@admin_broadcast_router.message(BroadcastState.waiting_for_text)
async def get_broadcast_text(message: Message, state: FSMContext):
    await state.update_data(text=message.text)
    await message.answer("📷 Отправьте изображение или кликлине /skip, если его нет:")
    await state.set_state(BroadcastState.waiting_for_photo)

# Получение изображения
@admin_broadcast_router.message(BroadcastState.waiting_for_photo)
async def get_broadcast_photo(message: Message, state: FSMContext,
                              session: AsyncSession):
    data = await state.get_data()

    photo = None
    if message.photo:
        photo = message.photo[-1].file_id
    elif message.text == "/skip":
        photo = None
    else:
        await message.answer("⚠ Пожалуйста, отправьте фото или кликлине /skip'.")
        return

    await state.update_data(photo=photo)

    # Переход к выбору курсов
    result = await session.execute(select(Course))
    courses = result.scalars().all()

    builder = ReplyKeyboardBuilder()
    for course in courses:
        builder.button(text=f"🎯 {course.name}")
    builder.button(text="✅ Завершить выбор")
    builder.adjust(2)

    await state.set_state(BroadcastState.waiting_for_courses)
    await state.update_data(selected_courses=[])
    await message.answer("Выберите курсы для рассылки:",
                         reply_markup=builder.as_markup(resize_keyboard=True))


@admin_broadcast_router.message(BroadcastState.waiting_for_courses,
                                F.text.startswith("🎯"))
async def select_course(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    selected_courses = data.get("selected_courses", [])
    course_name = message.text[2:]

    result = await session.execute(select(Course).where(Course.name == course_name))
    course = result.scalar_one_or_none()
    if course and course.id not in selected_courses:
        selected_courses.append(course.id)
        await state.update_data(selected_courses=selected_courses)
        await message.answer(f"Курс {course.name} добавлен. Выберите ещё или нажмите 'Завершить выбор'")


@admin_broadcast_router.message(BroadcastState.waiting_for_courses,
                                F.text == "✅ Завершить выбор")
async def confirm_broadcast(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    data = await state.get_data()
    text = data.get("text")
    photo = data.get("photo")
    course_ids = data.get("selected_courses")

    if not course_ids:
        await message.answer("⚠ Вы не выбрали ни одного курса!")
        return

    # ✅ Получаем пользователей, у которых course_id в выбранных
    result = await session.execute(
        select(User.tg_id).where(User.course_id.in_(course_ids))
    )
    user_ids = [row[0] for row in result.fetchall()]

    success, fail = 0, 0
    for user_id in user_ids:
        try:
            if photo:
                if len(text) <= 1024:
                    await bot.send_photo(chat_id=user_id, photo=photo, caption=text)
                else:
                    await bot.send_photo(chat_id=user_id, photo=photo, caption=None)
                    await bot.send_message(chat_id=user_id, text=text)
            else:
                await bot.send_message(chat_id=user_id, text=text)

            success += 1
        except Exception as e:
            print(f"Ошибка отправки {user_id}: {e}")
            fail += 1

    await message.answer(
        f"✅ Рассылка завершена!\nУспешно: {success}\nОшибки: {fail}",
    )
    await state.clear()


@admin_broadcast_router.message(BroadcastState.confirmation, F.text == "❌ Отменить")
async def cancel_broadcast(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Рассылка отменена.")
