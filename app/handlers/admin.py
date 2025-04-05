import os
from aiofiles import open as aio_open
from aiogram.fsm import state
from aiogram.types import FSInputFile, CallbackQuery
from aiogram import F, Router, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from app.filters.chat_types import ChatTypeFilter, IsAdmin
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from sqlalchemy import select, func
from datetime import datetime, timedelta
from collections import defaultdict

from app.keyboards.inline import admin_main_menu
from app.keyboards.reply import kb_admin_main, kb_main
from database.models import User, Specialization, Course, Broadcast

admin_router = Router()
admin_router.message.filter(ChatTypeFilter(["private"]), IsAdmin())


@admin_router.message(Command("admin"))
async def confirmation(message: Message, bot: Bot):
    await message.answer(
        "🛠️ <b>Административная панель</b>",
        parse_mode="HTML",
        reply_markup=kb_admin_main
    )
    await message.answer(
        "Управление разделами:",
        reply_markup=await admin_main_menu()
    )


@admin_router.callback_query(F.data == 'admin_stats')
async def show_statistics(callback: CallbackQuery,
                          session: AsyncSession):
    total_users = await session.scalar(select(func.count()).select_from(User))
    total_specializations = await session.scalar(select(func.count()).select_from(Specialization))
    total_courses = await session.scalar(select(func.count()).select_from(Course))

    # Пользователи без выбранного курса
    users_without_course = await session.scalar(
        select(func.count()).where(User.course_id.is_(None))
    )

    # Статистика по курсам
    course_stats_query = (
        select(
            Course.name.label("course_name"),
            Specialization.name.label("specialization_name"),
            func.count(User.id).label("user_count")
        )
        .join(User.course)
        .join(Course.specialization)
        .group_by(Course.id, Specialization.id)
        .order_by(Specialization.name, Course.name)
    )

    course_stats = await session.execute(course_stats_query)
    course_stats_rows = course_stats.all()

    # Формируем текст сообщения
    text = (
        "<b>📊 Статистика чат-бота:</b>\n\n"
        f"Всего пользователей: <b>{total_users}</b>\n"
        f"   - из них без выбранного курса: <b>{users_without_course}</b>\n\n"
        f"Всего специализаций: <b>{total_specializations}</b>\n"
        f"Всего курсов: <b>{total_courses}</b>\n\n"
        "<b>Выбор курсов пользователями:</b>\n"
    )

    # Добавляем статистику по курсам
    current_specialization = None
    for row in course_stats_rows:
        course_name, specialization_name, user_count = row

        if specialization_name != current_specialization:
            text += f"\n<b>{specialization_name}:</b>\n"
            current_specialization = specialization_name

        text += f"   - {course_name} — <b>{user_count}</b>\n"

    await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=await admin_main_menu()
    )
    await callback.answer()


# Обработчик кнопки выхода
@admin_router.message(F.text == "Выйти из админ-панели")
async def exit_admin_panel(message: Message,
                           state: FSMContext):
    await message.answer(
        "Выход из админ-панели.",
        reply_markup=kb_main)
    await state.clear()
