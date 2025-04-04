import asyncio

from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.fsm import state
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram import F, Router

from app.fsm_states import StartState
from app.keyboards.reply import *
from app.keyboards.inline import *
from app.text import *
from database.models import *


start_router = Router()


@start_router.message(CommandStart())
async def start_handler(message: Message,
                        state: FSMContext,
                        session: AsyncSession):
    tg_user = message.from_user

    # Проверка наличия пользователь в БД
    stmt = select(User).where(User.tg_id == tg_user.id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        # Создание пользователя
        user = User(
            tg_id=tg_user.id,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
            username=tg_user.username
        )
        session.add(user)
        await session.commit()

        await message.answer(welcome_msg, parse_mode="HTML")
        await asyncio.sleep(1)

        await message.answer(about_bot_msg, parse_mode="HTML")
        await asyncio.sleep(1)

        await message.answer(choose_msg,
                             reply_markup=await specialization_keyboard(session),
                             parse_mode="HTML")
        await state.set_state(StartState.waiting_for_specialization)
    else:
        # Приветствие зарегистрированного пользователя
        await message.answer("🎉 С возвращением!",
                             reply_markup=kb_main)


# Выбор специализации
@start_router.callback_query(StartState.waiting_for_specialization,
                             F.data.startswith("spec_"))
async def specialization(callback: CallbackQuery,
                         state: FSMContext,
                         session: AsyncSession):
    spec_id = callback.data.replace("spec_", "").strip()
    if not spec_id.isdigit():
        await callback.answer("❌ Некорректный ID специализации.", show_alert=True)
        return

    stmt = select(User).where(User.tg_id == callback.from_user.id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        spec_stmt = select(Specialization).where(Specialization.id == int(spec_id))
        spec_result = await session.execute(spec_stmt)
        specialization = spec_result.scalar_one_or_none()

        if specialization:
            user.specialization_id = specialization.id
            await session.commit()

            await callback.message.edit_text(
                f"✅ Выбрана специализация:\n\n<b>{specialization.name}</b>",
                parse_mode="HTML"
            )

            # Проверяем, есть ли курсы по этой специализации
            keyboard = await courses_keyboard(session, user.specialization_id, 0)

            if keyboard is None:
                await callback.message.answer(
                    "❌ Курсов не найдено. Выбери другую специализацию:",
                    reply_markup=await specialization_keyboard(session)  # Подставляем клавиатуру выбора специализации
                )
            else:
                await callback.message.answer(
                    "🎓 Теперь выбери курс, который тебя интересует:",
                    reply_markup=keyboard
                )
                await state.set_state(StartState.waiting_for_course)
        else:
            await callback.answer("❌ Специализация не найдена.", show_alert=True)
    else:
        await callback.answer("❌ Пользователь не найден.", show_alert=True)


# Выбор курса
@start_router.callback_query(StartState.waiting_for_course,
                             F.data.startswith("course_"))
async def course(callback: CallbackQuery,
                 state: FSMContext,
                 session: AsyncSession):
    course_id = callback.data.replace("course_", "")

    # Проверка на корректность id
    if not course_id.isdigit():
        await callback.answer("❌ Некорректный ID курса.", show_alert=True)
        return

    # Получаем пользователя
    stmt = select(User).where(User.tg_id == callback.from_user.id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        await callback.answer("❌ Пользователь не найден.", show_alert=True)
        return

    # Проверяем, существует ли курс и относится ли он к специализации пользователя
    stmt = select(Course).where(Course.id == int(course_id), Course.specialization_id == user.specialization_id)
    result = await session.execute(stmt)
    course = result.scalar_one_or_none()

    if course:
        user.course_id = course.id
        await session.commit()

        new_text = f"✅ Выбран курс:\n\n<b>{course.name}</b>"

        # Проверяем, изменилось ли сообщение
        if callback.message.text != new_text:
            try:
                await callback.message.edit_text(new_text, parse_mode="HTML")
            except TelegramBadRequest:
                pass  # Игнорируем ошибку, если сообщение не изменилось

        await callback.message.answer("🚀 Отлично! 🎉\n\nТеперь у тебя есть доступ к"
                                      " <b>проектам</b> курса 📚.\nТы будешь получать "
                                      "уведомления о новых проектах 🔔.\n\n"
                                      "<i>Изменить курс можно по кнопке 'Мой курс'.</i>",
                                      reply_markup=kb_main,
                                      parse_mode="HTML")
        await state.clear()
    else:
        await callback.answer("❌ Курс не найден или не соответствует твоей специализации.", show_alert=True)


# Пагинация при выборе курса
@start_router.callback_query(StartState.waiting_for_course,
                             F.data.startswith("page_"))
async def paginate_courses(callback: CallbackQuery,
                           session: AsyncSession):
    _, specialization_id, page = callback.data.split("_")

    if not specialization_id.isdigit() or not page.isdigit():
        await callback.answer("❌ Некорректный запрос.", show_alert=True)
        return

    specialization_id, page = int(specialization_id), int(page)

    keyboard = await courses_keyboard(session, specialization_id, page)

    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest:
        pass  # Игнорируем, если клавиатура не изменилась
