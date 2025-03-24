from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.constants import COURSE_TITLES
from app.keyboards.inline import kb_change_specialization, change_courses_keyboard
from app.keyboards.reply import kb_profile, kb_main
from database.models import *

profile_router = Router()

@profile_router.message(F.text == "👤 Мой профиль")
async def profile_handler(message: Message, session: AsyncSession):
    stmt = select(User).where(User.tg_id == message.from_user.id).options(
        selectinload(User.specialization),
        selectinload(User.course)
    )
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        specialization = user.specialization.name if user.specialization else "не выбрано"
        course = user.course.name if user.course else "не выбран"
        await message.answer(
            f"👤 <b>Твой профиль</b>\n\n"
            f"🔸 Выбранное направление: <b>{specialization}</b>\n"
            f"🔹 Выбранный курс: <b>{course}</b>",
            parse_mode="HTML",
            reply_markup=kb_profile
        )
    else:
        await message.answer("Профиль не найден. Попробуй снова /start.")


@profile_router.message(F.text == "🔁 Изменить курс")
async def change_course_start(message: Message, session: AsyncSession):
    # Получаем все специализации
    result = await session.execute(select(Specialization))
    specializations = result.scalars().all()

    # Создаем клавиатуру со специализациями
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=spec.name, callback_data=f"select_spec_{spec.id}")]
            for spec in specializations
        ]
    )

    await message.answer("🎯 Выберите специализацию:", reply_markup=keyboard)

@profile_router.callback_query(F.data.startswith("select_spec_"))
async def choose_course_after_spec(callback: CallbackQuery, session: AsyncSession):
    spec_id = int(callback.data.replace("select_spec_", ""))

    # Получаем специализацию и связанные курсы
    spec_result = await session.execute(select(Specialization).filter(Specialization.id == spec_id))
    specialization = spec_result.scalars().first()

    if not specialization:
        await callback.answer("❌ Специализация не найдена")
        return

    courses_result = await session.execute(
        select(Course).filter(Course.specialization_id == spec_id)
    )
    courses = courses_result.scalars().all()

    if not courses:
        await callback.message.edit_text("⚠️ Нет доступных курсов для этой специализации.")
        return

    # Создаем клавиатуру с курсами
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=course.name, callback_data=f"select_course_{course.id}_{spec_id}")]
            for course in courses
        ]
    )

    await callback.message.edit_text(f"🎓 Выбрана специализация: <b>{specialization.name}</b>\nТеперь выберите курс:", parse_mode="HTML", reply_markup=keyboard)

@profile_router.callback_query(F.data.startswith("select_course_"))
async def set_course_and_spec(callback: CallbackQuery, session: AsyncSession):
    data = callback.data.replace("select_course_", "")
    course_id_str, spec_id_str = data.split("_")
    course_id = int(course_id_str)
    spec_id = int(spec_id_str)

    user_id = callback.from_user.id

    async with session.begin():
        result = await session.execute(select(User).filter(User.tg_id == user_id))
        user = result.scalars().first()

        course_result = await session.execute(select(Course).filter(Course.id == course_id))
        course = course_result.scalars().first()

        spec_result = await session.execute(select(Specialization).filter(Specialization.id == spec_id))
        spec = spec_result.scalars().first()

        if user and course and spec:
            user.specialization_id = spec.id
            user.course_id = course.id
            await session.commit()

            await callback.message.edit_text(
                f"✅ Обновлено направление: <b>{spec.name}</b>\n✅ Обновлён курс: <b>{course.name}</b>",
                parse_mode="HTML"
            )
        else:
            await callback.answer("❌ Ошибка при обновлении профиля. Попробуйте снова.")


@profile_router.message(F.text == "🔙 Назад")
async def back_to_main_menu(message: Message):
    await message.answer("🔙 Возврат в главное меню.", reply_markup=kb_main)
