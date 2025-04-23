import os
from pathlib import Path
from aiofiles import open as aio_open
from aiogram.types import FSInputFile, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import F, Router, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.testing.suite.test_reflection import users
from app.filters.chat_types import ChatTypeFilter, IsAdmin
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from sqlalchemy import select, func, update
import time
from collections import defaultdict
from app.fsm_states import BroadcastState, MailingState
from app.keyboards.inline import (projects_keyboard, bc_courses_keyboard,
                                  admin_main_menu, add_back_button, admin_broadcast_menu)
from app.keyboards.reply import kb_admin_main
from database.models import User, Specialization, Course, Broadcast, Project, BroadcastCourseAssociation
import logging
from typing import Union, Optional
from sqlalchemy import text


logger = logging.getLogger(__name__)



admin_broadcast_router = Router()
admin_broadcast_router.message.filter(ChatTypeFilter(["private"]), IsAdmin())


async def send_photo_with_caption(
    recipient_id: int,
    photo: Union[str, FSInputFile],
    text: str,
    bot: Bot,
    reply_markup: Optional[InlineKeyboardMarkup] = None
):
    """Универсальная функция для отправки фото с подписью"""
    try:
        # Если photo - это путь к файлу
        if isinstance(photo, str) and os.path.exists(photo):
            photo_file = FSInputFile(photo)
            if len(text) <= 1024:
                await bot.send_photo(
                    chat_id=recipient_id,
                    photo=photo_file,
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
            else:
                await bot.send_photo(
                    chat_id=recipient_id,
                    photo=photo_file,
                    parse_mode="HTML"
                )
                await bot.send_message(
                    chat_id=recipient_id,
                    text=text,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                    reply_markup=reply_markup
                )
        else:
            if len(text) <= 1024:
                await bot.send_photo(
                    chat_id=recipient_id,
                    photo=photo,
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
            else:
                await bot.send_photo(
                    chat_id=recipient_id,
                    photo=photo,
                    parse_mode="HTML"
                )
                await bot.send_message(
                    chat_id=recipient_id,
                    text=text,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                    reply_markup=reply_markup
                )
    except Exception as e:
        logger.error(f"Ошибка при отправке фото: {e}", exc_info=True)
        raise


MEDIA_DIR = 'media/images'
Path(MEDIA_DIR).mkdir(parents=True, exist_ok=True)  # Создаем папку, если ее нет


@admin_broadcast_router.callback_query(F.data == "admin_mailing")
async def mailing_management(callback: CallbackQuery):
    await callback.message.edit_text(
        "<b>📨 Управление рассылками</b>\n\n"
        "Выбери действие:",
        parse_mode="HTML",
        reply_markup=await admin_broadcast_menu()
    )
    await callback.answer()


@admin_broadcast_router.callback_query(F.data == "broadcasts:admin_main_menu")
async def back_to_admin_main_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "Возврат в главное админ-меню",
        reply_markup=await admin_main_menu()
    )
    await callback.answer()



# =====================================================================================
# ----------------------------------- Новая рассылка ----------------------------------
# =====================================================================================



@ admin_broadcast_router.callback_query(F.data == "broadcasts:new_mailing")
async def start_broadcast(callback: CallbackQuery,
                          state: FSMContext):
    builder = InlineKeyboardBuilder()
    await add_back_button(builder, "menu")

    await callback.message.answer(
        "<b>📨 Введи текст сообщения</b>",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()
    await state.set_state(BroadcastState.waiting_for_text)


# Получение текста
@admin_broadcast_router.message(BroadcastState.waiting_for_text)
async def get_broadcast_text(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.update_data(text=message.text)

    builder = InlineKeyboardBuilder()
    builder.button(text="Без изображения", callback_data="skip_photo")
    await add_back_button(builder, "waiting_for_text")


    await message.answer("<b>📷 Отправь изображение</b>",
                         parse_mode="HTML",
                         reply_markup=builder.as_markup()
                         )
    await state.set_state(BroadcastState.waiting_for_photo)


# Обработчик инлайн-кнопки пропуска
@admin_broadcast_router.callback_query(
    BroadcastState.waiting_for_photo,
    F.data == "skip_photo"
)
async def skip_photo_handler(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    await state.update_data(photo=None)
    await callback.answer()

    # Переход к выбору проекта
    keyboard = await projects_keyboard(session)
    builder = InlineKeyboardBuilder()
    builder.attach(keyboard)
    await add_back_button(builder, "waiting_for_photo")

    await callback.message.answer("<b>Укажи проект для рассылки</b>",
                                  parse_mode="HTML",
                                  reply_markup=builder.as_markup(resize_keyboard=True))
    await state.set_state(BroadcastState.waiting_for_project)


# Получение изображения
@admin_broadcast_router.message(BroadcastState.waiting_for_photo)
async def get_broadcast_photo(message: Message, state: FSMContext,
                              session: AsyncSession, bot: Bot):
    data = await state.get_data()

    photo_path = None
    if message.photo:
        # Скачиваем фото и сохраняем в папку
        photo = message.photo[-1]
        file_id = photo.file_id
        file = await bot.get_file(file_id)
        file_path = file.file_path

        # Создаем уникальное имя файла
        ext = os.path.splitext(file_path)[1] or '.jpg'
        filename = f"broadcast_{int(time.time())}{ext}"
        photo_path = os.path.join(MEDIA_DIR, filename)

        # Сохраняем файл
        await bot.download_file(file_path, photo_path)
    else:
        builder = InlineKeyboardBuilder()
        builder.button(text="Без изображения", callback_data="skip_photo")
        await add_back_button(builder, "waiting_for_text")

        await message.answer("⚠ Пожалуйста, отправь фото или нажми 'Без изображения'.",
                             reply_markup=builder.as_markup())
        return


    await state.update_data(photo=photo_path)  # Сохраняем путь к файлу

    # Переход к выбору проекта
    keyboard = await projects_keyboard(session)
    builder = InlineKeyboardBuilder()
    builder.attach(keyboard)
    await add_back_button(builder, "waiting_for_photo")

    await message.answer("<b>Укажи проект для рассылки</b>",
                         parse_mode="HTML",
                         reply_markup=builder.as_markup(resize_keyboard=True))

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
        await callback.answer("⚠ Проект не найден. Выбери из списка:",
                              show_alert=True)
        return

    # Сохраняем данные проекта
    await state.update_data(
        project_id=project.id,
        project_title=project.title
    )
    # Получаем клавиатуру и преобразуем в markup
    courses_kb = await bc_courses_keyboard(session)
    await callback.answer()
    await callback.message.answer(
        f"Проект: <b>{project.title}</b>\n\n"
        f"Выбери курсы для рассылки:",
        parse_mode="HTML",
        reply_markup=courses_kb.as_markup()
    )

    await state.set_state(BroadcastState.waiting_for_courses)


# Выбор курсов
@admin_broadcast_router.callback_query(
    BroadcastState.waiting_for_courses,
    F.data.startswith("bccourse_")
)
async def select_course(callback: CallbackQuery, state: FSMContext,
                        session: AsyncSession):
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


# Пагинация курсов
@admin_broadcast_router.callback_query(
    BroadcastState.waiting_for_courses,
    F.data.startswith("bcpage_")
)
async def courses_page_handler(callback: CallbackQuery, state: FSMContext,
                               session: AsyncSession):
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


# Поиск курса
@admin_broadcast_router.callback_query(
    BroadcastState.waiting_for_courses,
    F.data.startswith("courses_search")
)
async def search_courses_handler(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.message.answer("🔍 Введи название курса для поиска:")
        await state.set_state(BroadcastState.waiting_for_course_search)
        await callback.answer()
    except Exception as e:
        print(f"Error in search_courses_handler: {e}")
        await callback.answer("Ошибка при запуске поиска", show_alert=True)


# Поиск курса
@admin_broadcast_router.message(BroadcastState.waiting_for_course_search)
async def process_search_query(message: Message, state: FSMContext,
                               session: AsyncSession):
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


# Завершение выбора курсов
@admin_broadcast_router.callback_query(
    BroadcastState.waiting_for_courses,
    F.data == "finish_courses_selection"
)
async def finish_courses_selection(callback: CallbackQuery,
                                   state: FSMContext,
                                   session: AsyncSession,
                                   bot: Bot):
    data = await state.get_data()
    text = data.get("text")
    photo = data.get("photo")
    project_id = data.get("project_id")
    selected_courses = data.get("selected_courses", [])

    if not selected_courses:
        await callback.answer("❌ Не выбран ни один курс!",
                              show_alert=True)
        return

    project = await session.get(Project, project_id)
    if not project:
        await callback.answer("❌ Проект не найден!", show_alert=True)
        return

    result = await session.execute(
        select(Course)
        .where(Course.id.in_(selected_courses))
    )
    courses = result.scalars().all()

    # Получаем количество пользователей на каждом курсе
    course_stats = []
    total_recipients = 0

    # Запрос для получения количества пользователей по каждому курсу
    user_counts = await session.execute(
        select(
            Course.id,
            Course.name,
            func.count(User.id).label("user_count")
        )
        .join(User, User.course_id == Course.id)
        .where(Course.id.in_(selected_courses))
        .group_by(Course.id, Course.name)
    )

    # Собираем статистику
    course_stats_data = {}
    for course_id, course_name, user_count in user_counts:
        course_stats_data[course_id] = {
            "name": course_name,
            "count": user_count
        }
        total_recipients += user_count

    # Формируем строки для отображения
    for course in courses:
        count = course_stats_data.get(course.id, {}).get("count", 0)
        course_stats.append(f"• {course.name} - {count} получателей")

    message_text = (
            "📋 <b>Подтверждение рассылки:</b>\n\n"
            f"📄 <b>Текст:</b>\n{text}\n\n"
            f"📌 <b>Проект:</b> {project.title}\n\n"
            f"🎯 <b>Курсы и получатели:</b>\n" + "\n".join(course_stats) + "\n\n"
            f"👥 <b>Всего получателей:</b> {total_recipients}\n\n"
            "Подтверди отправку или измени данные:"
    )

    # Клавиатура подтверждения
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="confirm_broadcast")
    builder.button(text="❌ Отменить", callback_data="cancel_broadcast")
    builder.adjust(2)

    # Если есть фото, отправляем его с подписью
    try:
        if photo:
            await send_photo_with_caption(
                recipient_id=callback.message.chat.id,
                photo=photo,
                text=message_text,
                bot=bot,
                reply_markup=builder.as_markup()
            )
        else:
            await callback.message.answer(
                text=message_text,
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )
    except Exception as e:
        logger.error(f"Ошибка при отправке подтверждения: {e}", exc_info=True)
        await callback.message.answer(
            "⚠ Ошибка при формировании сообщения",
            parse_mode="HTML"
        )

    await state.set_state(BroadcastState.confirmation)
    await callback.answer()


@admin_broadcast_router.callback_query(
    BroadcastState.confirmation,
    F.data == "confirm_broadcast"
)
async def confirm_broadcast(callback: CallbackQuery,
                            state: FSMContext,
                            session: AsyncSession,
                            bot: Bot):
    try:
        data = await state.get_data()
        text = data.get("text", "")
        photo = data.get("photo")
        project_id = data.get("project_id")
        selected_courses = data.get("selected_courses", [])

        if not selected_courses:
            await callback.answer("❌ Не выбран ни один курс!", show_alert=True)
            return

        # Получаем только необходимые данные пользователей
        result = await session.execute(
            select(User.tg_id, User.course_id)
            .where(User.course_id.in_(selected_courses))
        )
        users = result.all()

        # Получаем статистику по курсам одним запросом
        course_stats = {}
        stats_result = await session.execute(
            select(
                Course.id,
                Course.name,
                func.count(User.id).label("total")
            )
            .join(User, User.course_id == Course.id)
            .where(Course.id.in_(selected_courses))
            .group_by(Course.id)
        )

        for course_id, name, total in stats_result:
            course_stats[course_id] = {
                "name": name,
                "total": total,
                "success": 0,
                "failed": 0
            }

        total_users = len(users)
        if not total_users:
            await callback.answer("❌ Нет получателей у выбранных курсов!", show_alert=True)
            return

        # Уведомление о начале рассылки
        progress_msg = await callback.message.answer(
            f"Рассылка для {total_users} пользователей...",
            parse_mode="HTML"
        )

        # Отправка сообщений
        success_count = 0
        failed_count = 0

        for tg_id, course_id in users:
            try:
                if photo:
                    await send_photo_with_caption(
                        recipient_id=tg_id,
                        photo=photo,
                        text=text,
                        bot=bot
                    )
                else:
                    await bot.send_message(
                        chat_id=tg_id,
                        text=text,
                        disable_web_page_preview=True,
                        parse_mode="HTML"
                    )
                success_count += 1
                course_stats[course_id]["success"] += 1
            except Exception as e:
                failed_count += 1
                course_stats[course_id]["failed"] += 1
                logger.error(f"Ошибка отправки для {tg_id}: {str(e)}", exc_info=True)

        # Сохранение рассылки в БД
        broadcast = Broadcast(
            text=text,
            image_path=photo,
            is_sent=True,
            project_id=project_id,
            is_active=True  # Добавлено явное указание is_active
        )

        # Убедитесь, что метод set_course_ids не пытается вызвать строку как функцию
        if hasattr(broadcast, 'set_course_ids'):
            await broadcast.set_course_ids(selected_courses, session)
        else:
            # Альтернативная реализация, если метод отсутствует
            broadcast.course_ids = selected_courses

        session.add(broadcast)

        try:
            await session.commit()
        except IntegrityError as e:
            await session.rollback()
            if "broadcasts_pkey" in str(e):
                # Сбрасываем последовательность
                await session.execute(
                    text("SELECT setval('broadcasts_id_seq', (SELECT COALESCE(MAX(id), 1) FROM broadcasts))")
                )
                await session.commit()
            else:
                raise

        # Отправка отчета
        report_lines = [
            "📊 <b>Отчет о рассылке:</b>",
            f"👥 Всего получателей: {total_users}",
            f"✅ Успешно: {success_count}",
            f"❌ Ошибки: {failed_count}",
            "",
            "<b>Статистика по курсам:</b>"
        ]

        for stats in course_stats.values():
            report_lines.append(
                f"• {stats['name']}: {stats['success']}/{stats['total']} "
                f"(ошибок: {stats['failed']})"
            )

        try:
            await progress_msg.delete()
        except:
            pass

        await callback.message.answer(
            "\n".join(report_lines),
            parse_mode="HTML",
            reply_markup=await admin_main_menu()
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка в confirm_broadcast: {str(e)}", exc_info=True)
        await callback.answer(
            "⚠ Ошибка при рассылке. Попробуйте снова.",
            show_alert=True
        )
    finally:
        await state.clear()


@admin_broadcast_router.callback_query(
    BroadcastState.confirmation,
    F.data == "cancel_broadcast"
)
async def cancel_broadcast_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("❌ Рассылка отменена",
                                     reply_markup=await admin_main_menu())
    await state.clear()
    await callback.answer()


# Универсальный обработчик кнопки Назад
@admin_broadcast_router.callback_query(F.data.startswith("back_"))
async def handle_back_button(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    back_state = callback.data.replace("back_", "")

    if back_state == "menu":
        await state.clear()
        await callback.message.edit_text(
            "Управление рассылками",
            reply_markup=await admin_broadcast_menu()
        )

    elif back_state == "waiting_for_text":
        await state.get_data()

        builder = InlineKeyboardBuilder()
        await add_back_button(builder, "menu")

        await callback.message.edit_text(
            "<b>Заново введи текст сообщения</b>",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
        await state.set_state(BroadcastState.waiting_for_text)

    elif back_state == "waiting_for_photo":
        await state.get_data()
        builder = InlineKeyboardBuilder()
        builder.button(text="Без изображения", callback_data="skip_photo")
        await add_back_button(builder, "waiting_for_text")

        await callback.message.edit_text(
            "<b>Заново отправь изображение</b>",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
        await state.set_state(BroadcastState.waiting_for_photo)

    elif back_state == "waiting_for_project":
        data = await state.get_data()
        builder = InlineKeyboardBuilder()
        builder.button(text="Без изображения", callback_data="skip_photo")
        await add_back_button(builder, "waiting_for_text")

        await callback.message.answer("<b>📷 Отправь изображение</b>",
                                    parse_mode="HTML",
                                    reply_markup=builder.as_markup())
        await state.set_state(BroadcastState.waiting_for_photo)

    elif back_state == "waiting_for_courses":
        keyboard = await projects_keyboard(session)
        await callback.message.answer("<b>Укажи проект для рассылки</b>",
                                    parse_mode="HTML",
                                    reply_markup=keyboard.as_markup(resize_keyboard=True))
        await state.set_state(BroadcastState.waiting_for_project)

    await callback.answer()



# =====================================================================================
# -------------------------------- Статусы рассылок ----------------------------------
# =====================================================================================



@admin_broadcast_router.callback_query(F.data == "broadcasts:mailing_status")
async def mailing_statuses_handler(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="Активные рассылки",
            callback_data="active_mailings"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="В архиве",
            callback_data="archived_mailings"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="Изменить статус",
            callback_data="change_mailing_status"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="back_to_broadcast_menu"
        )
    )

    await callback.message.edit_text(
        text="<b>Управление статусами рассылок</b>\n\n"
             "Выбери действие:",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@admin_broadcast_router.callback_query(F.data == "back_to_broadcast_menu")
async def back_to_broadcast_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        text="Управление рассылками",
        reply_markup=await admin_broadcast_menu()
    )
    await callback.answer()


# Хендлер для показа активных рассылок с пагинацией
@admin_broadcast_router.callback_query(F.data.startswith("active_mailings"))
async def show_active_mailings(callback: CallbackQuery, session: AsyncSession):
    try:
        # Парсим параметры пагинации из callback_data
        page = int(callback.data.split(":")[1]) if ":" in callback.data else 0

        # Получаем общее количество активных рассылок
        total_count = await session.scalar(
            select(func.count(Broadcast.id))
            .where(Broadcast.is_active == True)
        )

        # Получаем рассылки для текущей страницы
        result = await session.execute(
            select(Broadcast)
            .where(Broadcast.is_active == True)
            .order_by(Broadcast.created.desc())
            .offset(page * 5)
            .limit(5)
        )
        mailings = result.scalars().all()

        if not mailings:
            await callback.answer("ℹ️ Нет активных рассылок", show_alert=True)
            return

        builder = InlineKeyboardBuilder()

        # Формируем сообщение
        message_text = f"<b>Активные рассылки (страница {page + 1}):</b>\n\n"
        for mailing in mailings:
            created_date = mailing.created.strftime("%d.%m.%Y %H:%M")
            message_text += (
                f"<b>ID:</b> {mailing.id}\n"
                f"<b>Дата:</b> {created_date}\n"
                f"<b>Текст:</b> {mailing.text[:100]}...\n\n"
            )

            builder.row(
                InlineKeyboardButton(
                    text=f"ID {mailing.id}",
                    callback_data=f"mailing_detail:{mailing.id}"
                )
            )

        # Добавляем кнопки пагинации
        pagination_buttons = []
        if page > 0:
            pagination_buttons.append(
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data=f"active_mailings:{page - 1}"
                )
            )
        if (page + 1) * 5 < total_count:
            pagination_buttons.append(
                InlineKeyboardButton(
                    text="▶️ Вперед",
                    callback_data=f"active_mailings:{page + 1}"
                )
            )

        if pagination_buttons:
            builder.row(*pagination_buttons)

        # Кнопка возврата
        builder.row(
            InlineKeyboardButton(
                text="⬅️ Назад в меню рассылок",
                callback_data="broadcasts:mailing_status"
            )
        )

        await callback.message.edit_text(
            text=message_text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )

    except Exception as e:
        logger.error(f"Ошибка при показе активных рассылок: {e}")
        await callback.answer("⚠️ Произошла ошибка", show_alert=True)


# Хендлер для показа архивных рассылок
@admin_broadcast_router.callback_query(F.data == "archived_mailings")
async def show_archived_mailings(callback: CallbackQuery, session: AsyncSession):
    try:
        # Получаем архивные рассылки из БД (где is_active == False)
        result = await session.execute(
            select(Broadcast)
            .where(Broadcast.is_active == False)
            .order_by(Broadcast.created.desc())
            .limit(10)
        )
        archived_mailings = result.scalars().all()

        if not archived_mailings:
            await callback.answer("ℹ️ В архиве нет рассылок", show_alert=True)
            return

        builder = InlineKeyboardBuilder()

        # Формируем сообщение с информацией о рассылках
        message_text = "<b>Архивные рассылки</b>\n\n"
        for mailing in archived_mailings:
            created_date = mailing.created.strftime("%d.%m.%Y %H:%M")

            message_text += (
                f"<b>ID:</b> {mailing.id}\n"
                f"<b>Дата:</b> {created_date}\n"
                f"<b>Текст:</b> {mailing.text[:250]}...\n\n"
            )

            # Добавляем кнопку для каждой рассылки
            builder.row(
                InlineKeyboardButton(
                    text=f"ID {mailing.id}",
                    callback_data=f"mailing_detail_{mailing.id}"
                )
            )

        # Добавляем кнопку возврата
        builder.row(
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="mailing_statuses"
            )
        )

        await callback.message.edit_text(
            text=message_text,
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )

    except Exception as e:
        logger.error(f"Ошибка при показе архивных рассылок: {e}")
        await callback.answer("⚠️ Произошла ошибка", show_alert=True)


# Хендлер для изменения статуса рассылки
@admin_broadcast_router.callback_query(F.data == "change_mailing_status")
async def change_mailing_status_start(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="🔍 Выбрать по ID",
            callback_data="select_mailing_by_id"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="mailing_statuses"
        )
    )

    await callback.message.edit_text(
        text="🔄 <b>Изменение статуса рассылки по её ID</b>\n\n"
             "введи ID рассылки",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )


# Хендлер для возврата в предыдущее меню
@admin_broadcast_router.callback_query(F.data == "back_to_broadcast_menu")
async def back_to_broadcast_menu(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="✉️ Создать рассылку",
            callback_data="create_broadcast"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="📊 Статусы рассылок",
            callback_data="mailing_statuses"
        )
    )

    await callback.message.edit_text(
        text="<b>Меню управления рассылками</b>\n\n"
             "Выбери действие:",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )

    await callback.answer()


@admin_broadcast_router.callback_query(F.data.startswith("mailing_detail_"))
async def mailing_detail(callback: CallbackQuery, session: AsyncSession):
    mailing_id = int(callback.data.split("_")[-1])

    # Получаем информацию о рассылке
    result = await session.execute(
        select(Broadcast).where(Broadcast.id == mailing_id)
    )
    mailing = result.scalar_one_or_none()

    if not mailing:
        await callback.answer("❌ Рассылка не найдена", show_alert=True)
        return

    builder = InlineKeyboardBuilder()

    # Кнопки управления статусом
    if mailing.is_active:
        builder.row(
            InlineKeyboardButton(
                text="⛔ В архив",
                callback_data=f"deactivate_mailing_{mailing.id}"
            )
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text="✅ Активировать",
                callback_data=f"activate_mailing_{mailing.id}"
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="active_mailings"
        )
    )

    created_date = mailing.created.strftime("%d.%m.%Y %H:%M")

    await callback.message.edit_text(
        text=f"<b>Рассылка ID {mailing.id}</b>\n\n"
             f"<b>Дата:</b> {created_date}\n"
             f"<b>Текст:</b>\n{mailing.text[:250]}",
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )


@admin_broadcast_router.callback_query(F.data.startswith("activate_mailing_"))
async def activate_mailing(callback: CallbackQuery, session: AsyncSession):
    mailing_id = int(callback.data.split("_")[-1])

    await session.execute(
        update(Broadcast)
        .where(Broadcast.id == mailing_id)
        .values(is_active=True)
    )
    await session.commit()

    await callback.answer("✅ Рассылка активирована")
    await mailing_detail(callback, session)  # Обновляем сообщение


@admin_broadcast_router.callback_query(F.data.startswith("deactivate_mailing_"))
async def deactivate_mailing(callback: CallbackQuery, session: AsyncSession):
    mailing_id = int(callback.data.split("_")[-1])

    await session.execute(
        update(Broadcast)
        .where(Broadcast.id == mailing_id)
        .values(is_active=False)
    )
    await session.commit()

    await callback.answer("⛔ Рассылка отправлена в архив")
    await mailing_detail(callback, session)  # Обновляем сообщение


@admin_broadcast_router.callback_query(F.data == "select_mailing_by_id")
async def select_mailing_by_id(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        text="🔢 Введи ID рассылки:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="change_mailing_status")]
        ])
    )
    await state.set_state(MailingState.waiting_for_mailing_id)


@admin_broadcast_router.message(MailingState.waiting_for_mailing_id)
async def process_mailing_id(message: Message, state: FSMContext, session: AsyncSession):
    try:
        # Получаем и очищаем ввод
        user_input = message.text.strip()

        # Проверяем что ввод - число
        if not user_input.isdigit():
            await message.answer("⚠️ Пожалуйста, введите только число (например: 7)")
            return

        mailing_id = int(user_input)

        # Проверяем существование рассылки
        result = await session.execute(
            select(Broadcast).where(Broadcast.id == mailing_id)
        )
        mailing = result.scalar_one_or_none()

        if not mailing:
            await message.answer(f"❌ Рассылка с ID {mailing_id} не найдена")
            return

        # Получаем данные для отображения
        created_date = mailing.created.strftime("%d.%m.%Y %H:%M")
        status = "✅ Активна" if mailing.is_active else "⛔ В архиве"

        builder = InlineKeyboardBuilder()
        if mailing.is_active:
            builder.row(InlineKeyboardButton(
                text="⛔ В архив",
                callback_data=f"deactivate_mailing_{mailing.id}"
            ))
        else:
            builder.row(InlineKeyboardButton(
                text="✅ Активировать",
                callback_data=f"activate_mailing_{mailing.id}"
            ))
        builder.row(InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="active_mailings"
        ))

        # Отправляем новое сообщение с деталями
        await message.answer(
            text=f"<b>Детали рассылки ID {mailing.id}</b>\n\n"
                 f"<b>Дата:</b> {created_date}\n"
                 f"<b>Статус:</b> {status}\n"
                 f"<b>Текст:</b>\n{mailing.text[:250]}",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )

        await state.clear()

    except Exception as e:
        logger.error(f"Ошибка при обработке ID рассылки: {e}", exc_info=True)
        await message.answer("⚠️ Произошла ошибка. Попробуйте еще раз.")
