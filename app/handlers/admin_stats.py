import io
import os
from aiofiles import open as aio_open
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm import state
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import FSInputFile, CallbackQuery, InlineKeyboardButton, BufferedInputFile
from aiogram import F, Router, Bot
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from app.filters.chat_types import ChatTypeFilter, IsAdmin
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from sqlalchemy import select, func, distinct
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd
from aiogram.types import BufferedInputFile

from app.keyboards.inline import admin_main_menu
from app.keyboards.reply import kb_admin_main, kb_main
from database.models import User, Specialization, Course, Broadcast, BroadcastCourseAssociation

admin_stats_router = Router()
admin_stats_router.message.filter(ChatTypeFilter(["private"]), IsAdmin())



@admin_stats_router.callback_query(F.data == 'admin_stats')
async def show_statistics_menu(callback: CallbackQuery):
    # Создаем клавиатуру с выбором раздела статистики
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="Пользователи",
            callback_data="stats_users"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="Рассылки",
            callback_data="stats_mailings"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="admin_back_to_main"
        )
    )

    await callback.message.edit_text(
        "📊 <b>Выберите раздел статистики:</b>",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()







# Обработчик статистики по пользователям
class UserStatsState(StatesGroup):
    SORTING = State()
    SEARCH = State()



@admin_stats_router.callback_query(F.data == 'stats_users')
async def show_users_statistics(
        callback: CallbackQuery,
        session: AsyncSession,
        state: FSMContext = None,
        sort_by: str = 'users',
        search_query: str = None
):
    # Получаем статистику
    total_users = await session.scalar(select(func.count()).select_from(User))
    users_without_course = await session.scalar(
        select(func.count()).where(User.course_id.is_(None)))

    # Получаем данные о курсах
    course_stats = await get_course_stats(session, sort_by=sort_by, search_query=search_query)

    # Формируем текст сообщения
    text = [
        "<b>👥 Статистика пользователей:</b>\n\n",
        f"Всего пользователей: <b>{total_users}</b>\n",
        f"Без выбранного курса: <b>{users_without_course}</b>\n\n",
    ]

    if search_query:
        text.append(f"<b>🔍 Результаты поиска по запросу '{search_query}':</b>\n\n")
    else:
        text.append(
            f"<b>Распределение по курсам (сортировка по {'имени' if sort_by == 'name' else 'количеству пользователей'}):</b>\n")

    for course_name, user_count in course_stats:
        text.append(f"• {course_name}: <b>{user_count}</b>\n")

    # Создаем клавиатуру
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🔍 Поиск курса",
            callback_data="stats_search_course")
    )
    builder.row(
        InlineKeyboardButton(
            text="Сортировка по названию курса",
            callback_data="stats_sort_name")
    )
    builder.row(
        InlineKeyboardButton(
            text="Сортировка по числу подписчиков",
            callback_data="stats_sort_users")
    )
    builder.row(
        InlineKeyboardButton(
            text="Выгрузить в Excel",
            callback_data="export_users_excel")
    )
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="admin_stats")
    )

    try:
        await callback.message.edit_text(
            "".join(text),
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer("Данные не изменились")
        else:
            raise

    await callback.answer()



async def get_course_stats(session: AsyncSession, sort_by: str = 'users', search_query: str = None):
    query = select(
        Course.name,
        func.count(User.id).label("user_count")
    ).join(User, Course.id == User.course_id, isouter=True)

    if search_query:
        query = query.where(Course.name.ilike(f"%{search_query}%"))

    query = query.group_by(Course.id)

    if sort_by == 'name':
        query = query.order_by(Course.name.asc())
    else:  # 'users'
        query = query.order_by(func.count(User.id).desc())

    result = await session.execute(query)
    return result.all()


@admin_stats_router.callback_query(F.data == 'stats_sort_name')
async def sort_by_name(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    await show_users_statistics(
        callback=callback,
        session=session,
        state=state,
        sort_by='name'
    )
    course_stats = await get_course_stats(session, sort_by='name')

    text = [
        "<b>👥 Статистика пользователей (сортировка по имени):</b>\n\n",
        "<b>Распределение по курсам:</b>\n"
    ]

    for course_name, user_count in course_stats:
        text.append(f"• {course_name}: <b>{user_count}</b>\n")

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🔍 Поиск курса",
            callback_data="stats_search_course")
    )
    builder.row(
        InlineKeyboardButton(
            text="Сортировка по названию курса",
            callback_data="stats_sort_name")
    )
    builder.row(
        InlineKeyboardButton(
            text="Сортировка по числу подписчиков",
            callback_data="stats_sort_users")
    )
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="admin_stats")
    )

    await callback.message.edit_text(
        "".join(text),
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()



@admin_stats_router.callback_query(F.data == 'stats_sort_users')
async def sort_by_users(callback: CallbackQuery,
                        session: AsyncSession,
                        state: FSMContext):
    try:
        await show_users_statistics(
            callback=callback,
            session=session,
            state=state,
            sort_by='users'
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await callback.answer("Уже отсортировано по количеству пользователей")
        else:
            raise


@admin_stats_router.callback_query(F.data == 'stats_search_course')
async def search_course(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("🔍 Введите название курса для поиска:")
    await state.set_state(UserStatsState.SEARCH)
    await callback.answer()


@admin_stats_router.message(StateFilter(UserStatsState.SEARCH))
async def process_search(message: Message, session: AsyncSession, state: FSMContext):
    search_query = message.text
    course_stats = await get_course_stats(session, search_query=search_query)

    if not course_stats:
        await message.answer("❌ Курсы не найдены. Попробуйте другой запрос.")
        return

    text = [
        f"<b>🔍 Результаты поиска по запросу '{search_query}':</b>\n\n",
        "<b>Распределение по курсам:</b>\n"
    ]

    for course_name, user_count in course_stats:
        text.append(f"• {course_name}: <b>{user_count}</b>\n")

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🔍 Новый поиск",
            callback_data="stats_search_course")
    )
    builder.row(
        InlineKeyboardButton(
            text="Сортировать по названию курса",
            callback_data="stats_sort_name")
    )
    builder.row(
        InlineKeyboardButton(
            text="Сортировать по числу подписчиков",
            callback_data="stats_sort_users")
    )
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="admin_stats")
    )

    await message.answer(
        "".join(text),
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await state.clear()


@admin_stats_router.callback_query(F.data == 'export_users_excel')
async def export_users_to_excel(callback: CallbackQuery, session: AsyncSession):
    # Получаем данные пользователей с информацией о курсах
    query = (
        select(
            User.first_name,
            User.last_name,
            User.username,
            Course.name.label("course_name")
        )
        .join(Course, User.course_id == Course.id, isouter=True)
        .order_by(User.id)
    )

    result = await session.execute(query)
    users_data = result.all()

    # Преобразуем данные в DataFrame
    df = pd.DataFrame(
        [(u.first_name or '', u.last_name or '', u.username or '', u.course_name or '')
         for u in users_data],
        columns=['Имя', 'Фамилия', 'Username', 'Курс']
    )

    # Создаем Excel файл в памяти
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Пользователи')
        worksheet = writer.sheets['Пользователи']

        # Настраиваем ширину колонок
        worksheet.set_column('A:A', 20)
        worksheet.set_column('B:B', 20)
        worksheet.set_column('C:C', 20)
        worksheet.set_column('D:D', 30)

    # Подготавливаем файл для отправки
    output.seek(0)
    excel_file = BufferedInputFile(output.read(), filename='users_report.xlsx')

    # Отправляем файл
    await callback.message.answer_document(
        document=excel_file,
        caption="📊 Отчет по пользователям"
    )
    await callback.answer()








# Обработчик статистики по рассылкам
@admin_stats_router.callback_query(F.data == 'stats_mailings')
async def show_mailings_statistics(callback: CallbackQuery,
                                   session: AsyncSession):
    # Получаем общую статистику по рассылкам
    total_mailings = await session.scalar(
        select(func.count()).select_from(Broadcast)
    )

    # Получаем детализированную информацию о последних 5 рассылках
    latest_mailings_query = (
        select(Broadcast)
        .order_by(Broadcast.created.desc())
        .limit(5)
    )
    latest_mailings = await session.scalars(latest_mailings_query)

    # Формируем текст сообщения
    text = [
        "<b>📊 Статистика рассылок</b>\n\n",
        f"• Всего рассылок: <b>{total_mailings}</b>\n\n",
        "<b>Последние рассылки:</b>\n"
    ]

    for mailing in latest_mailings:
        # Получаем названия курсов для этой рассылки
        courses_query = (
            select(Course.name)
            .join(BroadcastCourseAssociation,
                  BroadcastCourseAssociation.course_id == Course.id)
            .where(BroadcastCourseAssociation.broadcast_id == mailing.id)
        )
        courses = await session.scalars(courses_query)
        course_names = [name for name in courses]

        # Получаем количество получателей
        recipients_count = await session.scalar(
            select(func.count(User.id))
            .join(BroadcastCourseAssociation,
                  User.course_id == BroadcastCourseAssociation.course_id)
            .where(BroadcastCourseAssociation.broadcast_id == mailing.id)
        )

        # Форматируем дату и текст
        date_str = mailing.created.strftime("%d.%m.%Y %H:%M") if mailing.created else "N/A"
        short_text = (mailing.text[:125] + "...") if len(mailing.text) > 125 else mailing.text

        # Форматируем список курсов с нумерацией
        formatted_courses = ""
        if course_names:
            formatted_courses = "\n".join(
                f"{i + 1}) {name}"
                for i, name in enumerate(course_names)
            )
        else:
            formatted_courses = "Нет курсов"

        text.append(
            f"\n<b>#{mailing.id}</b>\n"
            f"<b>{date_str}</b>\n"
            f"Курсы:\n<b>{formatted_courses}</b>\n"
            f"Получателей: <b>{recipients_count}</b>\n"
            f"Текст: <i>{short_text}</i>\n"
            "────────────────"
        )

    # Кнопки навигации
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="admin_stats"
        )
    )

    await callback.message.edit_text(
        "".join(text),
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()



@admin_stats_router.callback_query(F.data == 'admin_back_to_main')
async def back_to_admin_main(callback: CallbackQuery):
    await callback.message.edit_text(
        "Управление разделами:",
        reply_markup=await admin_main_menu()
    )
    await callback.answer()
