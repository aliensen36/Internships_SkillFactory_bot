from aiogram import F, Router, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from app.filters.chat_types import ChatTypeFilter, IsAdmin
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from sqlalchemy import select, func
from datetime import datetime, timedelta
from collections import defaultdict
from app.fsm_states import BroadcastStates
from app.keyboards.reply import kb_admin_main
from database.models import User, Specialization, Course, Broadcast

admin_router = Router()
admin_router.message.filter(ChatTypeFilter(["private"]), IsAdmin())


@admin_router.message(Command("admin"))
async def confirmation(message: Message):
    await message.answer("Что хотите сделать?", reply_markup=kb_admin_main)


@admin_router.message(F.text == "📢 Рассылка")
async def start_broadcast(message: Message, state: FSMContext):
    await state.set_state(BroadcastStates.waiting_for_text)
    await message.answer("Введите текст рассылки:")


@admin_router.message(BroadcastStates.waiting_for_text)
async def process_text(message: Message, state: FSMContext):
    await state.update_data(text=message.text)
    await state.set_state(BroadcastStates.waiting_for_image)
    await message.answer("Отправьте изображение для рассылки (или нажмите /skip чтобы пропустить)")


@admin_router.message(BroadcastStates.waiting_for_image, F.text == "/skip")
async def skip_image(message: Message, state: FSMContext, session: AsyncSession):
    await process_course_selection(message, state, session)


@admin_router.message(BroadcastStates.waiting_for_image, F.photo)
async def process_image(message: Message, state: FSMContext, session: AsyncSession):
    photo = message.photo[-1]
    file_id = photo.file_id
    await state.update_data(image_path=file_id)
    await process_course_selection(message, state, session)


async def process_course_selection(message: Message, state: FSMContext, session: AsyncSession):
    # Получаем список всех курсов
    result = await session.execute(select(Course))
    courses = result.scalars().all()

    # Создаем клавиатуру с курсами
    from aiogram.utils.keyboard import ReplyKeyboardBuilder
    builder = ReplyKeyboardBuilder()
    for course in courses:
        builder.button(text=f"🎯 {course.name}")
    builder.button(text="✅ Завершить выбор")
    builder.adjust(2)

    await state.set_state(BroadcastStates.waiting_for_courses)
    await message.answer(
        "Выберите курсы для рассылки:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )
    await state.update_data(selected_courses=[])


@admin_router.message(BroadcastStates.waiting_for_courses, F.text.startswith("🎯"))
async def select_course(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    selected_courses = data.get("selected_courses", [])

    course_name = message.text[2:]  # Убираем эмодзи
    result = await session.execute(select(Course).where(Course.name == course_name))
    course = result.scalar_one_or_none()

    if course and course.id not in selected_courses:
        selected_courses.append(course.id)
        await state.update_data(selected_courses=selected_courses)
        await message.answer(f"Курс {course_name} добавлен. Выберите еще или нажмите 'Завершить выбор'")


@admin_router.message(BroadcastStates.waiting_for_courses, F.text == "✅ Завершить выбор")
async def finish_course_selection(message: Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("selected_courses"):
        await message.answer("Нужно выбрать хотя бы один курс!")
        return

    await state.set_state(BroadcastStates.confirmation)
    from aiogram.utils.keyboard import ReplyKeyboardBuilder
    builder = ReplyKeyboardBuilder()
    builder.button(text="✅ Подтвердить рассылку")
    builder.button(text="❌ Отменить")

    await message.answer(
        f"Подтвердите рассылку:\n\n"
        f"Текст: {data['text']}\n"
        f"Курсы: {len(data['selected_courses'])}\n"
        f"Изображение: {'Да' if 'image_path' in data else 'Нет'}",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )


@admin_router.message(BroadcastStates.confirmation, F.text == "✅ Подтвердить рассылку")
async def confirm_broadcast(message: Message, state: FSMContext,
                            session: AsyncSession, bot: Bot):
    data = await state.get_data()

    # Создаем запись о рассылке
    async with session.begin():
        broadcast = Broadcast(
            text=data['text'],
            image_path=data.get('image_path'),
            is_sent=False
        )
        broadcast.set_course_ids(data['selected_courses'])
        session.add(broadcast)
        await session.flush()

        # Отправляем рассылку
        sent_count = 0
        recipients = await broadcast.get_recipients(session)

        for user in recipients:
            try:
                if 'image_path' in data:
                    await bot.send_photo(
                        chat_id=user.tg_id,
                        photo=data['image_path'],
                        caption=data['text']
                    )
                else:
                    await bot.send_message(
                        chat_id=user.tg_id,
                        text=data['text']
                    )
                sent_count += 1
            except Exception as e:
                print(f"Ошибка отправки пользователю {user.tg_id}: {e}")

        broadcast.is_sent = True
        broadcast.sent_at = func.now()
        await session.commit()

    await message.answer(f"Рассылка завершена! Отправлено {sent_count} пользователям.")
    await state.clear()


@admin_router.message(BroadcastStates.confirmation, F.text == "❌ Отменить")
async def cancel_broadcast(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Рассылка отменена.")


@admin_router.message(F.text == '📊 Статистика')
async def show_statistics(message: Message, session: AsyncSession):
    total_users = await session.scalar(select(func.count()).select_from(User))
    total_specializations = await session.scalar(select(func.count()).select_from(Specialization))
    total_courses = await session.scalar(select(func.count()).select_from(Course))

    text = (
    "<b>📊 Статистика чат-бота:</b>\n\n"
    f"👥 Всего пользователей: <b>{total_users}</b>\n\n"
    f"🎯 Всего специализаций: <b>{total_specializations}</b>\n\n"
    f"📚 Всего курсов: <b>{total_courses}</b>\n\n"
    # f"🗣 Всего отзывов: <b>{total_feedbacks}</b>\n"
    )

    await message.answer(text, parse_mode="HTML", reply_markup=kb_admin_main)

