import os
from aiofiles import open as aio_open
from aiogram.types import FSInputFile, CallbackQuery
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
from app.keyboards.inline import projects_keyboard, bc_courses_keyboard
from app.keyboards.reply import kb_admin_main
from database.models import User, Specialization, Course, Broadcast, Project


admin_broadcast_router = Router()
admin_broadcast_router.message.filter(ChatTypeFilter(["private"]), IsAdmin())

MEDIA_DIR = 'media/images'


@admin_broadcast_router.message(F.text == "📢 Рассылка")
async def start_broadcast(message: Message, state: FSMContext):
    await message.answer("<b>📨 Введите ТЕКСТ сообщения</b>",
                         parse_mode="HTML")
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

    # Переход к выбору проекта
    keyboard = await projects_keyboard(session)
    await message.answer("📌 Выберите проект для рассылки:",
                         reply_markup=keyboard.as_markup(resize_keyboard=True))
    await state.set_state(BroadcastState.waiting_for_project)

# Выбор проекта
@admin_broadcast_router.callback_query(BroadcastState.waiting_for_project,
                                       F.data.startswith("project_"))
async def select_project(callback: CallbackQuery, state: FSMContext,
                         session: AsyncSession):
    project_id = callback.data.replace("project_", "").strip()
    if not project_id.isdigit():
        await callback.answer("❌ Некорректный ID проекта.", show_alert=True)
        return

    # Получаем проект из БД
    result = await session.execute(
        select(Project)
        .where(Project.id == int(project_id))
    )
    project = result.scalar_one_or_none()

    if not project:
        await callback.answer("⚠ Проект не найден. Выберите из списка:", show_alert=True)
        return

    # Сохраняем данные проекта
    await state.update_data(
        project_id=project.id,
        project_title=project.title
    )

    # Получаем клавиатуру и преобразуем в markup
    courses_kb = await bc_courses_keyboard(session)

    await callback.message.answer(
        f"Проект: <b>{project.title}</b>\n\n"
        f"Выберите курсы для рассылки:",
        parse_mode="HTML",
        reply_markup=courses_kb.as_markup()  # Преобразуем здесь
    )

    await state.set_state(BroadcastState.waiting_for_courses)


@admin_broadcast_router.callback_query(
    BroadcastState.waiting_for_courses,
    F.data.startswith("bccourse_")
)
async def select_course(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        course_id = int(callback.data.split("_")[1])

        # Получаем данные из состояния
        data = await state.get_data()
        selected_courses = data.get("selected_courses", [])

        # Получаем курс из БД
        result = await session.execute(select(Course).where(Course.id == course_id))
        course = result.scalar_one_or_none()

        if not course:
            await callback.answer("Курс не найден", show_alert=True)
            return

        # Добавляем/удаляем курс из выбранных
        if course.id in selected_courses:
            selected_courses.remove(course.id)
        else:
            selected_courses.append(course.id)

        # Обновляем состояние
        await state.update_data(selected_courses=selected_courses)

        # Получаем обновленную клавиатуру
        search_query = data.get("course_search_query")
        current_page = data.get("course_page", 0)
        keyboard = await bc_courses_keyboard(
            session,
            search_query=search_query,
            page=current_page,
            selected_ids=selected_courses
        )

        # Обновляем сообщение
        await callback.message.edit_reply_markup(
            reply_markup=keyboard.as_markup()
        )

        await callback.answer()

    except Exception as e:
        await callback.answer("Ошибка при выборе курса", show_alert=True)
        print(f"Error in select_course: {e}")


@admin_broadcast_router.callback_query(
    BroadcastState.waiting_for_courses,
    F.data.startswith("bcpage_")
)
async def courses_page_handler(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        _, page, search_query = callback.data.split("_", 2)
        page = int(page)
        if search_query == "":
            search_query = None

        # Сохраняем текущую страницу и поисковый запрос
        await state.update_data(
            course_page=page,
            course_search_query=search_query
        )

        # Получаем выбранные курсы
        data = await state.get_data()
        selected_courses = data.get("selected_courses", [])

        # Получаем обновленную клавиатуру
        keyboard = await bc_courses_keyboard(
            session,
            search_query=search_query,
            page=page,
            selected_ids=selected_courses
        )

        await callback.message.edit_reply_markup(
            reply_markup=keyboard.as_markup()
        )
        await callback.answer()

    except Exception as e:
        await callback.answer("Ошибка пагинации", show_alert=True)
        print(f"Error in courses_page_handler: {e}")


@admin_broadcast_router.callback_query(
    BroadcastState.waiting_for_courses,
    F.data.startswith("courses_search")
)
async def search_courses_handler(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.message.answer("🔍 Введите название курса для поиска:")
        await state.set_state(BroadcastState.waiting_for_course_search)
        await callback.answer()
    except Exception as e:
        print(f"Error in search_courses_handler: {e}")
        await callback.answer("Ошибка при запуске поиска", show_alert=True)


@admin_broadcast_router.message(BroadcastState.waiting_for_course_search)
async def process_search_query(message: Message, state: FSMContext, session: AsyncSession):
    search_query = message.text.strip()

    # Сохраняем поисковый запрос и сбрасываем страницу
    await state.update_data(
        course_search_query=search_query,
        course_page=0
    )

    # Получаем выбранные курсы
    data = await state.get_data()
    selected_courses = data.get("selected_courses", [])

    # Получаем клавиатуру с результатами поиска
    keyboard = await bc_courses_keyboard(
        session,
        search_query=search_query,
        page=0,
        selected_ids=selected_courses
    )

    await message.answer(
        f"Результаты поиска по '{search_query}':",
        reply_markup=keyboard.as_markup()
    )
    await state.set_state(BroadcastState.waiting_for_courses)


# @admin_broadcast_router.message(BroadcastState.waiting_for_courses,
#                                 F.data.startswith("course_"))
# async def select_course(message: Message, state: FSMContext, session: AsyncSession):
#     data = await state.get_data()
#     selected_courses = data.get("bccourse_", [])
#     course_name = message.text[2:]
#
#     result = await session.execute(select(Course).where(Course.name == course_name))
#     course = result.scalar_one_or_none()
#     if course and course.id not in selected_courses:
#         selected_courses.append(course.id)
#         await state.update_data(selected_courses=selected_courses)
#         await message.answer(f"Курс <b>{course_name} ✅</b> добавлен.\n\n"
#                              f"Выберите ещё или нажмите 'Завершить выбор'")
#
#
# @admin_broadcast_router.message(BroadcastState.waiting_for_courses,
#                                 F.text == "✅ Завершить выбор")
# async def confirm_broadcast(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
#     data = await state.get_data()
#     text = data.get("text")
#     photo = data.get("photo")
#     project_id = data.get("project_id")
#     course_ids = data.get("selected_courses")
#
#     if not course_ids:
#         await message.answer("⚠ Вы не выбрали ни одного курса!")
#         return
#
#     # ✅ Получаем пользователей, у которых course_id в выбранных
#     result = await session.execute(
#         select(User.tg_id).where(User.course_id.in_(course_ids))
#     )
#     user_ids = [row[0] for row in result.fetchall()]
#
#     # Создаем запись о рассылке в БД
#     broadcast = Broadcast(
#         text=text,
#         project_id=project_id
#     )
#     broadcast.set_course_ids(course_ids)
#
#     success, fail = 0, 0
#     for user_id in user_ids:
#         try:
#             if photo:
#                 if len(text) <= 1024:
#                     await bot.send_photo(chat_id=user_id, photo=photo, caption=text)
#                 else:
#                     await bot.send_photo(chat_id=user_id, photo=photo, caption=None)
#                     await bot.send_message(chat_id=user_id, text=text)
#             else:
#                 await bot.send_message(chat_id=user_id, text=text)
#
#             success += 1
#         except Exception as e:
#             print(f"Ошибка отправки {user_id}: {e}")
#             fail += 1
#
#     await message.answer(
#         f"✅ Рассылка завершена!\nУспешно: {success}\nОшибки: {fail}",
#     )
#     session.add(broadcast)
#     await session.commit()
#
#     await state.clear()
#
#
# @admin_broadcast_router.message(BroadcastState.confirmation, F.text == "❌ Отменить")
# async def cancel_broadcast(message: Message, state: FSMContext):
#     await state.clear()
#     await message.answer("Рассылка отменена.")
