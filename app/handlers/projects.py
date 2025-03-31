import logging
from pathlib import Path
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Filter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from app.handlers.admin_broadcast import send_photo_with_caption
from app.keyboards.inline import projects_keyboard, view_projects_keyboard, ProjectCallbackFilter, \
    project_details_message, get_project_details_keyboard, view_project_kb
from database.models import User, Broadcast, BroadcastCourseAssociation, Project, Course

projects_router = Router()

logger = logging.getLogger(__name__)


# Хэндлер для кнопки "⭐ Проекты"
@projects_router.message(F.text == "⭐ Проекты")
async def projects_button(message: Message, session: AsyncSession):
    try:
        keyboard = await view_projects_keyboard(session)
        await message.answer(
            "📂 <b>Выбери проект</b>",
            reply_markup=keyboard.as_markup(
                resize_keyboard=True,
                one_time_keyboard=False
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Ошибка при показе проектов: {e}")
        await message.answer("⚠ Произошла ошибка при загрузке проектов. "
                             "Попробуйте позже.")


# Хендлер для отображения списка проектов
@projects_router.callback_query(F.data == "back_to_projects_list")
async def back_to_projects_list(callback: CallbackQuery, session: AsyncSession):
    keyboard = await view_projects_keyboard(session)
    await callback.message.edit_text(
        "📂 <b>Выбери проект</b>",
        reply_markup=keyboard.as_markup(
            resize_keyboard=True,
            one_time_keyboard=False),
        parse_mode="HTML")
    await callback.answer()


# Хендлер для просмотра конкретного проекта
@projects_router.callback_query(ProjectCallbackFilter(prefix="view_project_"))
async def view_project(callback: CallbackQuery, session: AsyncSession):
    project_id = int(callback.data.split("_")[-1])
    project = await session.get(Project, project_id)

    if not project:
        await callback.answer("Проект не найден!", show_alert=True)
        return

    message_text = await project_details_message(project)

    await callback.message.edit_text(
        message_text,
        reply_markup=await get_project_details_keyboard(project_id, session),
        parse_mode="HTML"
    )
    await callback.answer()


@projects_router.callback_query(ProjectCallbackFilter(prefix="about_project_"))
async def about_project(callback: CallbackQuery, session: AsyncSession,
                        state: FSMContext):
    try:
        project_id = int(callback.data.split("_")[-1])
        project = await session.get(Project, project_id)

        if not project:
            await callback.answer("🚨 Проект не найден!", show_alert=True)
            return

        # Формируем подробное описание проекта
        about_text = (
            f"{project.description}"
        )

        await callback.message.edit_text(
            about_text,
            reply_markup=await get_project_details_keyboard(project_id, session),
            parse_mode="HTML"
            )
        await callback.answer()
        await state.update_data(current_project_id=project_id)

    except ValueError:
        await callback.answer("❌ Ошибка формата ID проекта", show_alert=True)
    except Exception as e:
        await callback.answer()


@projects_router.callback_query(ProjectCallbackFilter(prefix="benefits_project_"))
async def benefits_project(callback: CallbackQuery, session: AsyncSession,
                        state: FSMContext):
    try:
        project_id = int(callback.data.split("_")[-1])
        project = await session.get(Project, project_id)

        if not project:
            await callback.answer("🚨 Проект не найден!", show_alert=True)
            return

        # Формируем подробное описание проекта
        about_text = (
            f"{project.benefit}"
        )

        await callback.message.edit_text(
            about_text,
            reply_markup=await get_project_details_keyboard(project_id, session),
            parse_mode="HTML"
            )
        await callback.answer()
        await state.update_data(current_project_id=project_id)

    except ValueError:
        await callback.answer("❌ Ошибка формата ID проекта", show_alert=True)
    except Exception as e:
        await callback.answer()


@projects_router.callback_query(ProjectCallbackFilter(prefix="examples_project_"))
async def examples_project(callback: CallbackQuery,
                           session: AsyncSession,
                           state: FSMContext):
    try:
        project_id = int(callback.data.split("_")[-1])
        project = await session.get(Project, project_id)

        if not project:
            await callback.answer("🚨 Проект не найден!", show_alert=True)
            return

        # Проверяем, есть ли примеры
        examples_text = project.example if project.example else "📭 Примеров нет"

        # Формируем текст
        about_text = f"{examples_text}"

        await callback.message.edit_text(
            about_text,
            reply_markup=await get_project_details_keyboard(project_id, session),
            parse_mode="HTML"
            )
        await callback.answer()
        await state.update_data(current_project_id=project_id)


    except ValueError:
        await callback.answer("❌ Ошибка формата ID проекта", show_alert=True)
    except Exception as e:
        await callback.answer()



# =====================================================================================
#------------------------------ Доступные по моему курсу-------------------------------
# =====================================================================================



@projects_router.callback_query(ProjectCallbackFilter(prefix="available_to_me_project_"))
async def show_available_broadcasts(callback: CallbackQuery,
                                    session: AsyncSession):
    try:
        # Получаем пользователя с его курсом
        stmt = select(User).where(User.tg_id == callback.from_user.id).options(
            selectinload(User.course)
        )
        user = (await session.execute(stmt)).scalar_one_or_none()

        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return

        project_id = int(callback.data.split("_")[-1])
        project = await session.get(Project, project_id)

        if not project:
            await callback.answer("Проект не найден", show_alert=True)
            return

        if not user.course_id:
            await callback.answer("У вас не выбран курс", show_alert=True)
            return

        # Получаем рассылки для проекта и курса пользователя
        stmt = (
            select(Broadcast)
            .join(Broadcast.course_associations)
            .where(
                Broadcast.project_id == project_id,
                Broadcast.is_sent == True,
                BroadcastCourseAssociation.course_id == user.course_id
            )
            .order_by(Broadcast.id.desc())
        )
        broadcasts_list = (await session.scalars(stmt)).all()

        if not broadcasts_list:
            await callback.answer("Нет доступных рассылок для вашего курса", show_alert=True)
            return

        await send_broadcast_with_pagination(
            callback=callback,
            broadcasts=broadcasts_list,
            index=0,
            project_id=project_id,
            total=len(broadcasts_list),
            user_course_id=user.course_id
        )

    except Exception as e:
        logger.error(f"Error in show_available_broadcasts: {e}", exc_info=True)
        await callback.answer("Произошла ошибка", show_alert=True)



async def send_broadcast_with_pagination(
    callback: CallbackQuery,
    broadcasts: list[Broadcast],
    index: int,
    project_id: int,
    total: int,
    user_course_id: int
):
    """Функция пагинации с правильной обработкой фото и текста"""
    try:
        if index < 0 or index >= len(broadcasts):
            await callback.answer("Недопустимый индекс рассылки", show_alert=True)
            return

        broadcast = broadcasts[index]
        pagination_text = f"📌 Рассылка {index + 1} из {total}"
        main_text = broadcast.text
        full_text = f"{main_text}\n\n{pagination_text}"

        # Создаем клавиатуру пагинации
        builder = InlineKeyboardBuilder()
        if index > 0:
            builder.button(
                text="⬅️ Предыдущая",
                callback_data=f"prev_broadcast_{project_id}_{index}_{user_course_id}"
            )
        if index < total - 1:
            builder.button(
                text="Следующая ➡️",
                callback_data=f"next_broadcast_{project_id}_{index}_{user_course_id}"
            )
        builder.button(
            text="◀️ Назад к проекту",
            callback_data=f"view_project_{project_id}"
        )
        builder.adjust(2, 1)
        markup = builder.as_markup()

        # Удаляем предыдущее сообщение
        # try:
        #     await callback.message.delete()
        # except Exception as e:
        #     logger.warning(f"Не удалось удалить сообщение: {e}")

        # Отправляем контент
        if broadcast.image_path:
            try:
                # Если текст короткий (<=1024 символа) - отправляем фото с подписью
                if len(full_text) <= 1024:
                    await callback.message.bot.send_photo(
                        chat_id=callback.message.chat.id,
                        photo=broadcast.image_path,
                        caption=full_text,
                        reply_markup=markup
                    )
                else:
                    # Если текст длинный - отправляем фото без подписи и текст отдельно
                    await callback.message.bot.send_photo(
                        chat_id=callback.message.chat.id,
                        photo=broadcast.image_path,
                        reply_markup=markup
                    )
                    await callback.message.bot.send_message(
                        chat_id=callback.message.chat.id,
                        text=full_text,
                        reply_markup=None  # Клавиатура только у первого сообщения
                    )
            except Exception as e:
                logger.error(f"Ошибка при отправке фото: {e}")
                await callback.message.answer(
                    text=f"⚠️ Не удалось загрузить изображение\n\n{full_text}",
                    reply_markup=markup
                )
        else:
            await callback.message.answer(
                text=full_text,
                reply_markup=markup
            )

    except Exception as e:
        logger.error(f"Error in send_broadcast_with_pagination: {e}", exc_info=True)
        await callback.answer("Ошибка при отображении рассылки", show_alert=True)
    finally:
        await callback.answer()



@projects_router.callback_query(F.data.startswith("prev_broadcast_"))
async def prev_broadcast(callback: CallbackQuery, session: AsyncSession):
    try:
        parts = callback.data.split('_')
        project_id = int(parts[2])
        index = int(parts[3])
        course_id = int(parts[4])

        # Получаем рассылки для проекта и курса
        stmt = (
            select(Broadcast)
            .join(Broadcast.course_associations)
            .where(
                Broadcast.project_id == project_id,
                Broadcast.is_sent == True,
                BroadcastCourseAssociation.course_id == course_id
            )
            .order_by(Broadcast.id.desc())
        )
        broadcasts_list = (await session.scalars(stmt)).all()

        if not broadcasts_list:
            await callback.answer("Нет доступных рассылок", show_alert=True)
            return

        # Удаляем предыдущее сообщение
        try:
            await callback.message.delete()
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение: {e}")

        # Отправляем предыдущую рассылку
        await send_broadcast_with_pagination(
            callback=callback,
            broadcasts=broadcasts_list,
            index=max(0, index - 1),
            project_id=project_id,
            total=len(broadcasts_list),
            user_course_id=course_id
        )

    except Exception as e:
        logger.error(f"Error in prev_broadcast: {e}", exc_info=True)
        await callback.answer("Ошибка при загрузке", show_alert=True)

@projects_router.callback_query(F.data.startswith("next_broadcast_"))
async def next_broadcast(callback: CallbackQuery, session: AsyncSession):
    try:
        parts = callback.data.split('_')
        project_id = int(parts[2])
        index = int(parts[3])
        course_id = int(parts[4])

        # Получаем рассылки для проекта и курса
        stmt = (
            select(Broadcast)
            .join(Broadcast.course_associations)
            .where(
                Broadcast.project_id == project_id,
                Broadcast.is_sent == True,
                BroadcastCourseAssociation.course_id == course_id
            )
            .order_by(Broadcast.id.desc())
        )
        broadcasts_list = (await session.scalars(stmt)).all()

        if not broadcasts_list:
            await callback.answer("Нет доступных рассылок", show_alert=True)
            return

        # Удаляем предыдущее сообщение
        try:
            await callback.message.delete()
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение: {e}")

        # Отправляем следующую рассылку
        await send_broadcast_with_pagination(
            callback=callback,
            broadcasts=broadcasts_list,
            index=min(len(broadcasts_list) - 1, index + 1),
            project_id=project_id,
            total=len(broadcasts_list),
            user_course_id=course_id
        )

    except Exception as e:
        logger.error(f"Error in next_broadcast: {e}", exc_info=True)
        await callback.answer("Ошибка при загрузке", show_alert=True)