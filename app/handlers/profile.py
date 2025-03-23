from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import COURSE_TITLES
from app.keyboards.inline import kb_change_specialization, change_courses_keyboard
from app.keyboards.reply import kb_profile, kb_main
from database.models import User

profile_router = Router()

@profile_router.message(F.text == "👤 Мой профиль")
async def profile_handler(message: Message, session: AsyncSession):
    stmt = select(User).where(User.tg_id == message.from_user.id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        specialization = user.specialization or "не выбрано"
        course = user.course or "не выбран"
        await message.answer(
            f"👤 <b>Твой профиль</b>\n\n"
            f"🔸 Выбранное направление: <b>{specialization}</b>\n\n"
            f"🔹 Выбранный курс: <b>{course}</b>",
            parse_mode="HTML",
            reply_markup=kb_profile
        )
    else:
        await message.answer("Профиль не найден. Попробуй снова /start.")


@profile_router.message(F.text == "🔄 Изменить направление")
async def change_specialization(message: Message):
    await message.answer(
        "🎯 Выбери новое направление, чтобы обновить свой профиль:",
        reply_markup=kb_change_specialization
    )

@profile_router.callback_query(F.data.startswith("profile_spec_"))
async def change_specialization(callback: CallbackQuery,
                                       session: AsyncSession):

    spec = callback.data.replace("profile_spec_", "")

    # Получаем пользователя по ID из базы данных
    user_id = callback.from_user.id
    async with session.begin():
        result = await session.execute(select(User).filter(User.tg_id == user_id))
        user = result.scalars().first()

        if user:
            # Обновляем направление в базе данных
            user.specialization = spec
            await session.commit()

            # Подтверждаем изменение
            await callback.message.edit_text(f"✅ Выбрано направление: <b>{spec}</b> 🎯",
                                             parse_mode="HTML")

        else:
            await callback.answer("❌ Пользователь не найден, попробуйте снова.")


@profile_router.message(F.text == "🔁 Изменить курс")
async def change_course(message: Message, session: AsyncSession):
    await message.answer(
        "🎯 Выбери новый курс, чтобы обновить свой профиль:",
        reply_markup=change_courses_keyboard()
    )

@profile_router.callback_query(F.data.startswith("change_course_"))
async def change_courses(callback: CallbackQuery, session: AsyncSession):
    course = callback.data.replace("change_course_", "")
    course_title = COURSE_TITLES.get(course, "Неизвестный курс")  # Ищем полное название курса
    # Получаем пользователя по ID из базы данных
    user_id = callback.from_user.id
    async with session.begin():
        result = await session.execute(select(User).filter(User.tg_id == user_id))
        user = result.scalars().first()

        if user:
            user.course = course
            await session.commit()
            await callback.message.edit_text(f"✅ Выбран курс: <b>{course_title}</b> 🎯",
                                                 parse_mode="HTML")

        else:
            await callback.answer("❌ Пользователь не найден, попробуйте снова.")

@profile_router.callback_query(F.data.startswith("page_"))
async def page_navigation(callback: CallbackQuery):
    page = int(callback.data.replace("page_", ""))
    keyboard = change_courses_keyboard(page)

    # Обновляем сообщение с курсами и клавиатурой навигации
    await callback.message.edit_text(
        text=f"🎓 Выбери курс (страница {page + 1}):",
        reply_markup=keyboard
    )
    await callback.answer()

@profile_router.message(F.text == "🔙 Назад")
async def back_to_main_menu(message: Message):
    await message.answer("🔙 Возврат в главное меню.", reply_markup=kb_main)
