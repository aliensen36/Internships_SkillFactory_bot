import logging

from aiogram import Router, F
from aiogram.filters import StateFilter, Filter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.filters.chat_types import ChatTypeFilter, IsAdmin
from app.fsm_states import *
from app.keyboards.inline import admin_courses_menu
from database.models import *

admin_course_router = Router()
admin_course_router.message.filter(ChatTypeFilter(["private"]), IsAdmin())


# Обработчик кнопки "Курсы"
@admin_course_router.callback_query(F.data == "admin_courses")
async def courses(callback: CallbackQuery):
    try:
        # Удаляем инлайн-клавиатуру с предыдущего сообщения
        await callback.message.edit_reply_markup(reply_markup=None)

        # Отправляем новое меню курсов
        await callback.message.answer(
            text="<b>🏗️ Управление курсами</b>\n\nВыбери действие:",
            reply_markup=await admin_courses_menu(),
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        await callback.answer("⚠️ Ошибка при загрузке меню", show_alert=True)


@admin_course_router.callback_query(F.data == "courses:list")
async def view_courses(callback: CallbackQuery,
                       session: AsyncSession):
    try:
        result = await (session
                        .execute(select(Specialization)
                                 .options(selectinload(Specialization.courses)))
                        )
        specializations = result.scalars().all()

        if not specializations:
            await callback.message.answer("❗ Пока нет ни одной специализации и курсов.")
            return

        text = "<b>Список курсов</b>:\n\n"

        for spec in specializations:
            text += f"🔸 <b>{spec.name}</b>:\n"
            if spec.courses:
                for course in spec.courses:
                    text += f"  • {course.name}\n"
            else:
                text += "  (курсов пока нет)\n"
            text += "\n"

        await callback.message.answer(text,
                                      reply_markup=await admin_courses_menu(),
                                      parse_mode="HTML")

        await callback.answer()

    except Exception as e:
        await callback.message.answer("⚠️ Произошла ошибка при загрузке курсов")
        logging.error(f"Error in view_courses: {e}")




# =====================================================================================
# ----------------------------------- Добавить курс -----------------------------------
# =====================================================================================



@admin_course_router.callback_query(F.data == "courses:add")
async def add_course_start(callback: CallbackQuery,
                           state: FSMContext,
                           session: AsyncSession,):
    result = await session.execute(select(Specialization))
    specializations = result.scalars().all()

    if not specializations:
        await callback.message.answer("❗ Нет доступных специализаций. "
                                      "Сначала добавь хотя бы одну.")
        return

    # Формируем инлайн-кнопки
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=spec.name,
                callback_data=f"select_spec_{spec.id}")
            ]
            for spec in specializations
        ])


    await state.set_state(CourseAddState.waiting_for_specialization)
    await callback.message.answer("Выбери специализацию, к которой относится курс:", reply_markup=kb)
    await callback.answer()
