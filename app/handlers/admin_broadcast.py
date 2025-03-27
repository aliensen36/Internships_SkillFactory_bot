import os
from pathlib import Path
from aiofiles import open as aio_open
from aiogram.types import FSInputFile, CallbackQuery, InlineKeyboardMarkup
from aiogram import F, Router, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.testing.suite.test_reflection import users

from app.filters.chat_types import ChatTypeFilter, IsAdmin
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from sqlalchemy import select, func
import time
from collections import defaultdict
from app.fsm_states import BroadcastState
from app.keyboards.inline import projects_keyboard, bc_courses_keyboard
from app.keyboards.reply import kb_admin_main
from database.models import User, Specialization, Course, Broadcast, Project, BroadcastCourseAssociation
import logging
from typing import Union, Optional
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
                    reply_markup=reply_markup
                )
        else:
            # Предполагаем, что это file_id
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
                    reply_markup=reply_markup
                )
    except Exception as e:
        logger.error(f"Ошибка при отправке фото: {e}", exc_info=True)
        raise


MEDIA_DIR = 'media/images'
Path(MEDIA_DIR).mkdir(parents=True, exist_ok=True)  # Создаем папку, если ее нет


@admin_broadcast_router.message(F.text == "📢 Рассылка")
async def start_broadcast(message: Message, state: FSMContext):
    sent_msg = await message.answer(
        "<b>📨 Введите текст сообщения</b>",
        parse_mode="HTML"
    )
    await state.update_data(instruction_msg_id=sent_msg.message_id)
    await state.set_state(BroadcastState.waiting_for_text)


# Получение текста
@admin_broadcast_router.message(BroadcastState.waiting_for_text)
async def get_broadcast_text(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.update_data(text=message.text)

    builder = InlineKeyboardBuilder()
    builder.button(text="🚫 Без изображения", callback_data="skip_photo")


    await message.answer("<b>📷 Отправьте изображение</b>",
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
    # await callback.message.delete()

    # Переход к выбору проекта
    keyboard = await projects_keyboard(session)
    await callback.message.answer("<b>📌 Укажите проект для рассылки</b>",
                                 parse_mode="HTML",
                                  reply_markup=keyboard.as_markup(resize_keyboard=True))
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
        await message.answer("⚠ Пожалуйста, отправьте фото или нажмите 'Без изображения'.")
        return

    await state.update_data(photo=photo_path)  # Сохраняем путь к файлу

    # Переход к выбору проекта
    keyboard = await projects_keyboard(session)
    await message.answer("<b>📌 Укажите проект для рассылки</b>",
                         parse_mode="HTML",
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
        await callback.answer("⚠ Проект не найден. Выберите из списка:",
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
        f"Выберите курсы для рассылки:",
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
        await callback.message.answer("🔍 Введите название курса для поиска:")
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
        await callback.answer("❌ Вы не выбрали ни одного курса!",
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
            "Подтвердите отправку или измените данные:"
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
            await callback.answer("❌ Вы не выбрали ни одного курса!", show_alert=True)
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
            await callback.answer("❌ Нет пользователей на выбранных курсах!", show_alert=True)
            return

        # Уведомление о начале рассылки
        progress_msg = await callback.message.answer(
            f"⏳ Рассылка для {total_users} пользователей...",
            parse_mode="HTML"
        )

        # Отправка сообщений с обработкой длинных текстов
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
                        parse_mode="HTML"
                    )
                success_count += 1
                course_stats[course_id]["success"] += 1
            except Exception as e:
                failed_count += 1
                logger.error(f"Ошибка отправки для {tg_id}: {str(e)}", exc_info=True)

        # Формирование отчета
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

        # Сохранение рассылки в БД
        broadcast = Broadcast(
            text=text,
            image_path=photo,
            is_sent=True,
            project_id=project_id
        )
        await broadcast.set_course_ids(selected_courses, session)

        session.add(broadcast)
        await session.commit()

        # Отправка отчета
        try:
            await progress_msg.delete()
        except:
            pass

        await callback.message.answer(
            "\n".join(report_lines),
            parse_mode="HTML"
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка в confirm_broadcast: {str(e)}")
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
    await callback.message.edit_text("❌ Рассылка отменена")
    await state.clear()
    await callback.answer()

