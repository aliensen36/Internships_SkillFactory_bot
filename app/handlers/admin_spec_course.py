from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.filters.chat_types import ChatTypeFilter, IsAdmin
from app.fsm_states import SpecializationStates
from app.keyboards.reply import kb_specializations_courses, kb_specializations
from database.models import Specialization

admin_spec_course_router = Router()
admin_spec_course_router.message.filter(ChatTypeFilter(["private"]), IsAdmin())


# Обработчик кнопки "📚 Специализации и курсы"
@admin_spec_course_router.message(F.text == "📚 Специализации и курсы")
async def specializations_and_courses(message: Message):
    await message.answer("Выберите раздел:",
                         reply_markup=kb_specializations_courses)


# Обработчик кнопки '🎯 Специализации'
@admin_spec_course_router.message(F.text == '🎯 Специализации')
async def specializations_and_courses(message: Message):
    await message.answer("Выберите раздел:",
                         reply_markup=kb_specializations)


# Обработчик кнопки '➕ Добавить'
@admin_spec_course_router.message(F.text == '➕ Добавить')
async def add_specialization_start(message: Message, state: FSMContext):
    await state.set_state(SpecializationStates.waiting_for_specialization_name)
    await message.answer("Введите название новой специализации:")


@admin_spec_course_router.message(SpecializationStates.waiting_for_specialization_name)
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

    await message.answer(f"✅ Специализация «{name}» успешно добавлена!",
                         reply_markup=kb_specializations)
    await state.clear()
