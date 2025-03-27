import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.keyboards.inline import projects_keyboard, view_projects_keyboard
from database.models import User, Broadcast, BroadcastCourseAssociation, Project

projects_router = Router()

logger = logging.getLogger(__name__)


# Хэндлер для кнопки "⭐ Проекты"
@projects_router.message(F.text == "⭐ Проекты")
async def handle_projects_button(message: Message, session: AsyncSession):
    try:
        keyboard = await view_projects_keyboard(session)
        await message.answer(
            "<b>Выбери проект</b>",
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


@projects_router.callback_query(F.data.startswith("view_project_"))
async def view_projects(callback: CallbackQuery, session: AsyncSession):
    try:
        project_id = int(callback.data.split("_")[2])

        # Получаем пользователя с загруженным курсом
        user = await session.execute(
            select(User)
            .options(joinedload(User.course))
            .where(User.tg_id == callback.from_user.id)
        )
        user = user.scalar_one_or_none()

        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return
        if not user.course_id:
            await callback.answer("❌ Курс не выбран", show_alert=True)
            return

        # Получаем проект
        project = await session.get(Project, project_id)
        if not project:
            await callback.answer("❌ Проект не найден", show_alert=True)
            return

        # Получаем рассылки для проекта и курса
        broadcasts = await session.execute(
            select(Broadcast)
            .join(BroadcastCourseAssociation, Broadcast.id == BroadcastCourseAssociation.broadcast_id)
            .where(
                Broadcast.project_id == project_id,
                BroadcastCourseAssociation.course_id == user.course_id
            )
            .order_by(Broadcast.created.asc())
        )
        broadcasts = broadcasts.scalars().all()

        if not broadcasts:
            await callback.answer("ℹ️ Нет мероприятий для вашего курса", show_alert=True)
            return

        # Отправляем сообщение
        for idx, broadcast in enumerate(broadcasts, 1):
            # Формируем текст сообщения
            message = f"{idx}. {broadcast.text}"

            try:
                if broadcast.image_path:
                    # Проверяем существование файла
                    image_path = Path(broadcast.image_path)
                    if image_path.exists():
                        # Отправляем фото с текстом в подписи
                        await callback.message.answer_photo(
                            photo=InputFile(image_path),
                            caption=message,
                            parse_mode="HTML"
                        )
                    else:
                        # Если файл не найден, отправляем текстовое сообщение с уведомлением
                        await callback.message.answer(
                            f"🖼️ [Изображение не найдено по пути: {broadcast.image_path}]\n{message}",
                            parse_mode="HTML"
                        )
                        logger.warning(f"Изображение не найдено: {broadcast.image_path}")
                else:
                    # Если фото нет, просто отправляем текст
                    await callback.message.answer(
                        message,
                        parse_mode="HTML"
                    )
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения {idx}: {e}")
                await callback.message.answer(
                    f"⚠️ Ошибка при отправке сообщения {idx}. Попробуйте позже.",
                    parse_mode="HTML"
                )

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка в view_projects: {e}", exc_info=True)
        await callback.answer("⚠ Произошла ошибка", show_alert=True)


@projects_router.callback_query(F.data.startswith("broadcast_"))
async def show_broadcast_details(
        callback: CallbackQuery,
        session: AsyncSession
):
    try:
        broadcast_id = int(callback.data.split("_")[1])

        # Получаем рассылку с проектом
        broadcast = await session.execute(
            select(Broadcast)
            .options(joinedload(Broadcast.project))
            .where(Broadcast.id == broadcast_id)
        )
        broadcast = broadcast.scalar_one_or_none()

        if not broadcast:
            await callback.answer("❌ Рассылка не найдена!", show_alert=True)
            return

        # Формируем сообщение
        message_parts = []

        # Добавляем проект
        if broadcast.project:
            message_parts.append(f"📌 Проект: <b>{broadcast.project.title}</b>")

        # Добавляем текст рассылки
        message_parts.extend([
            "",
            "📄 <b>Текст рассылки:</b>",
            broadcast.text
        ])

        message_text = "\n".join(message_parts)

        # Отправляем контент
        if getattr(broadcast, 'image_path', None):
            try:
                # Проверяем длину текста для подписи
                caption = message_text if len(message_text) <= 1024 else message_text[:1000] + "..."
                await callback.message.answer_photo(
                    photo=broadcast.image_path,
                    caption=caption,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Ошибка отправки фото: {e}")
                await callback.message.answer(
                    "⚠ Не удалось загрузить изображение\n\n" + message_text,
                    parse_mode="HTML"
                )
        else:
            await callback.message.answer(
                message_text,
                parse_mode="HTML"
            )

        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка в show_broadcast_details: {str(e)}", exc_info=True)
        await callback.answer(
            "⚠ Произошла ошибка при загрузке рассылки",
            show_alert=True
        )
