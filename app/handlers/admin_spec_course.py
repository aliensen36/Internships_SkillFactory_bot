from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.filters.chat_types import ChatTypeFilter, IsAdmin
from app.fsm_states import *
from app.keyboards.reply import kb_specializations_courses, kb_specializations, kb_courses
from database.models import *

admin_spec_course_router = Router()
admin_spec_course_router.message.filter(ChatTypeFilter(["private"]), IsAdmin())


# Обработчик кнопки "📚 Специализации и курсы"
@admin_spec_course_router.message(F.text == "📚 Специализации и курсы")
async def specializations_and_courses(message: Message):
    await message.answer("Выберите раздел:",
                         reply_markup=kb_specializations_courses)


# Обработчик кнопки '🎯 Специализации'
@admin_spec_course_router.message(F.text == '🎯 Специализации')
async def specializations(message: Message):
    await message.answer("Выберите раздел:",
                         reply_markup=kb_specializations)


# Обработчик кнопки '👁️ Просмотр'
@admin_spec_course_router.message(F.text == '👁️ Просмотр')
async def view_specializations(message: Message, session: AsyncSession):
    result = await session.execute(select(Specialization))
    specializations = result.scalars().all()

    if not specializations:
        await message.answer("❗ Пока нет ни одной специализации.")
        return

    # Сформировать список специализаций
    text = "📚 Список специализаций:\n\n"
    for spec in specializations:
        text += f"{spec.name}\n\n"

    await message.answer(text)


# Обработчик кнопки '➕ Добавить'
@admin_spec_course_router.message(F.text == '➕ Добавить')
async def add_specialization_start(message: Message, state: FSMContext):
    await state.set_state(SpecializationState.waiting_for_specialization_name)
    await message.answer("Введите название новой специализации:")
@admin_spec_course_router.message(SpecializationState.waiting_for_specialization_name)
async def add_specialization_save(message: Message, state: FSMContext, session: AsyncSession):
    name = message.text.strip()

    # Проверка на дубликат
    existing = await session.execute(
        select(Specialization).where(Specialization.name == name)
    )
    if existing.scalar():
        await message.answer("❗ Такая специализация уже существует. Введите другое название.")
        return

    new_specialization = Specialization(name=name)
    session.add(new_specialization)
    await session.commit()

    await message.answer(f"✅ Специализация <b>{name}</b> успешно добавлена!",
                         parse_mode="HTML",
                         reply_markup=kb_specializations)
    await state.clear()



# Обработчик кнопки '📚 Курсы'
@admin_spec_course_router.message(F.text == '📚 Курсы')
async def courses(message: Message):
    await message.answer("Выберите раздел:",
                         reply_markup=kb_courses)


# Обработчик кнопки 'Просмотр 👁️'
@admin_spec_course_router.message(F.text == 'Просмотр 👁️')
async def view_courses(message: Message, session: AsyncSession):
    result = await session.execute(select(Specialization).options(selectinload(Specialization.courses)))
    specializations = result.scalars().all()

    if not specializations:
        await message.answer("❗ Пока нет ни одной специализации и курсов.")
        return

    text = "📚 Список специализаций и курсов:\n\n"

    for spec in specializations:
        text += f"🔸 <b>{spec.name}</b>:\n"
        if spec.courses:
            for course in spec.courses:
                text += f"  • {course.name}\n"
        else:
            text += "  (курсов пока нет)\n"
        text += "\n"

    await message.answer(text, parse_mode="HTML")


# Обработчик кнопки 'Добавить ➕'
@admin_spec_course_router.message(F.text == 'Добавить ➕')
async def add_course_start(message: Message, state: FSMContext, session: AsyncSession):
    result = await session.execute(select(Specialization))
    specializations = result.scalars().all()

    if not specializations:
        await message.answer("❗ Нет доступных специализаций. Сначала добавьте хотя бы одну.")
        return

    # Формируем инлайн-кнопки
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=spec.name, callback_data=f"select_spec_{spec.id}")]
        for spec in specializations
    ])
    await state.set_state(CourseState.waiting_for_specialization)
    await message.answer("Выберите специализацию, к которой относится курс:", reply_markup=kb)

# ✅ Шаг 2: Обработка нажатия на инлайн-кнопку
@admin_spec_course_router.callback_query(CourseState.waiting_for_specialization)
async def process_spec_choice(callback: CallbackQuery, state: FSMContext):
    if not callback.data.startswith("select_spec_"):
        await callback.answer("Неверный выбор")
        return

    # Извлекаем ID специализации
    spec_id = int(callback.data.replace("select_spec_", ""))
    await state.update_data(specialization_id=spec_id)

    await state.set_state(CourseState.waiting_for_course_name)
    await callback.message.edit_text("Теперь введите название нового курса:")
    await callback.answer()

# ✅ Шаг 3: Сохраняем курс
@admin_spec_course_router.message(CourseState.waiting_for_course)
async def add_course_save(message: Message, state: FSMContext, session: AsyncSession):
    name = message.text.strip()
    data = await state.get_data()
    specialization_id = int(data.get("specialization_id"))

    # Проверка на дубликат
    result = await session.execute(select(Course).where(Course.name == name))
    if result.scalar():
        await message.answer("❗ Такой курс уже существует. Введите другое название.")
        return

    new_course = Course(name=name, specialization_id=specialization_id)
    session.add(new_course)
    await session.commit()

    await message.answer(f"✅ Курс <b>{name}</b> успешно добавлен!", parse_mode="HTML")
    await state.clear()