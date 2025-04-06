from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.fsm_states import ChangeCourseState
from app.keyboards.inline import *
from app.keyboards.reply import kb_profile, kb_main
from database.models import *
from aiogram.exceptions import TelegramBadRequest


profile_router = Router()


@profile_router.message(F.text == "Мой курс")
async def profile_handler(message: Message,
                          session: AsyncSession):
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
            f"🔸 Выбрана специализация:\n<b>{specialization}</b>\n\n"
            f"🔹 Выбран курс:\n<b>{course}</b>",
            parse_mode="HTML",
            reply_markup=kb_profile
        )
    else:
        await message.answer("Профиль не найден. Попробуй снова /start.")


@profile_router.message(F.text == "Изменить курс")
async def change_specialization_start(message: Message,
                                      state: FSMContext,
                                      session: AsyncSession):
    # Загружаем текущие данные пользователя перед изменением
    stmt = select(User).where(User.tg_id == message.from_user.id).options(
        selectinload(User.specialization),
        selectinload(User.course)
    )
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
    # Сохраняем текущие значения в state
        await state.update_data(
            old_spec_id = user.specialization_id,
            old_course_id = user.course_id
        )

    await message.answer("🎯 Выбери специализацию:",
                         reply_markup=await change_specialization_keyboard(session))
    await state.set_state(ChangeCourseState.waiting_for_specialization)


# Новый обработчик для команды /course
@profile_router.message(Command("course"))
async def course_command(message: Message, state: FSMContext, session: AsyncSession):
    # Просто вызываем существующий обработчик
    await change_specialization_start(message, state, session)


@profile_router.callback_query(ChangeCourseState.waiting_for_specialization,
                               F.data.startswith("change_spec_"))
async def change_specialization(callback: CallbackQuery,
                                state: FSMContext,
                                session: AsyncSession):
    spec_id = callback.data.replace("change_spec_", "").strip()
    if not spec_id.isdigit():
        await callback.answer("❌ Некорректный ID специализации.", show_alert=True)
        return

    # Сохраняем новую специализацию в state, но пока не применяем к пользователю
    await state.update_data(new_spec_id=int(spec_id))

    stmt = select(Specialization).where(Specialization.id == int(spec_id))
    spec_result = await session.execute(stmt)
    specialization = spec_result.scalar_one_or_none()

    if specialization:
        await callback.message.edit_text(
            f"✅ Выбрана специализация:\n\n<b>{specialization.name}</b>",
            parse_mode="HTML"
        )

        # Проверяем, есть ли курсы по этой специализации
        keyboard = await change_courses_keyboard(session, int(spec_id), 0)

        if keyboard is None:
            await callback.message.answer(
                "❌ Курсов не найдено. Выбери другую специализацию:",
                reply_markup=await specialization_keyboard(session)
            )
        else:
            await callback.message.answer(
                "🎓 Теперь выбери курс, который тебя интересует:",
                reply_markup=keyboard
            )
            await state.set_state(ChangeCourseState.waiting_for_course)
    else:
        await callback.answer("❌ Специализация не найдена.", show_alert=True)


@profile_router.callback_query(ChangeCourseState.waiting_for_course,
                               F.data.startswith("change_course_"))
async def change_course(callback: CallbackQuery, state: FSMContext,
                        session: AsyncSession):
    course_id = callback.data.replace("change_course_", "")

    if not course_id.isdigit():
        await callback.answer("❌ Некорректный ID курса.", show_alert=True)
        return

    # Получаем все данные из state
    state_data = await state.get_data()
    new_spec_id = state_data.get('new_spec_id')

    stmt = select(User).where(User.tg_id == callback.from_user.id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        # Обновляем и специализацию, и курс
        user.specialization_id = new_spec_id
        user.course_id = int(course_id)
        await session.commit()

        stmt = select(Course).where(Course.id == int(course_id))
        result = await session.execute(stmt)
        course = result.scalar_one_or_none()

        await callback.message.edit_text(
            f"✅ Выбран курс:\n\n<b>{course.name}</b>",
            parse_mode="HTML"
        )
        await callback.message.answer(
            "Главное меню",
            reply_markup=kb_main
        )

    else:
        await callback.answer("❌ Пользователь не найден.", show_alert=True)
    await state.clear()


@profile_router.message(F.text == "Назад")
async def back_to_main_menu(message: Message, state: FSMContext, session: AsyncSession):
    # Проверяем, есть ли незавершенный процесс изменения курса
    current_state = await state.get_state()
    if current_state == ChangeCourseState.waiting_for_course:
        # Восстанавливаем старые значения
        state_data = await state.get_data()
        old_spec_id = state_data.get('old_spec_id')
        old_course_id = state_data.get('old_course_id')

        stmt = select(User).where(User.tg_id == message.from_user.id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            # Восстанавливаем только если пользователь не завершил выбор курса
            user.specialization_id = old_spec_id
            user.course_id = old_course_id
            await session.commit()

    await state.clear()
    await message.answer("Главное меню", reply_markup=kb_main)


# Пагинация при изменении курса
@profile_router.callback_query(F.data.startswith("changepage_"))
async def paginate_courses(callback: CallbackQuery, session: AsyncSession):
    _, specialization_id, page = callback.data.split("_")

    if not specialization_id.isdigit() or not page.isdigit():
        await callback.answer("❌ Некорректный запрос.", show_alert=True)
        return

    specialization_id, page = int(specialization_id), int(page)

    keyboard = await change_courses_keyboard(session, specialization_id, page)

    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest:
        pass  # Игнорируем, если клавиатура не изменилась
