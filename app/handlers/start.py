import asyncio
from aiogram.filters import CommandStart, StateFilter
from aiogram.types import CallbackQuery, Message
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.constants import courses
from app.keyboards.reply import *
from app.keyboards.inline import *
from app.text import *
from database.models import User, Project
from database.orm_query import get_all_projects

start_router = Router()


@start_router.message(CommandStart())
async def start_handler(message: Message, session: AsyncSession):
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
        # await asyncio.sleep(1)
        await message.answer(about_bot_msg)
        # await asyncio.sleep(1)
        # Отправка кнопок с возможностью раскрытия текста
        projects = await get_all_projects(session)
        for item in projects:
            await message.answer(item.title, reply_markup=get_projects_keyboard(item.id),
                                 parse_mode="HTML")
            # await asyncio.sleep(1)
        # await asyncio.sleep(1)
        await message.answer('<b>🎯 Хочешь принять участие?</b>\n\n'
                                 '👇 Выбери интересующие тебя направления, и мы '
                                 'предложим тебе соответствующие мероприятия 🌟',
                                 reply_markup=kb_specialization,
                                 parse_mode="HTML"
                                 )
    else:
        # Приветствие зарегистрированного пользователя
        await message.answer("Добро пожаловать! 🎉\nС возвращением!",
                             reply_markup=kb_main)


# Обработчик кнопки "📜 Прочитать"
@start_router.message(F.text == "📜 Прочитать")
async def send_projects_list(message: Message, session: AsyncSession):
    result = await session.execute(select(Project))
    projects = result.scalars().all()

    for project in projects:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📜 Прочитать", callback_data=f"project_{project.id}")]
        ])
        await message.answer(project.title, reply_markup=keyboard, parse_mode="HTML")


# Обработчик нажатия на кнопку "📜 Прочитать"
@start_router.callback_query(F.data.startswith("project_"))
async def show_project(callback: CallbackQuery, session: AsyncSession):
    project_id_str = callback.data.split("project_")[1]

    if not project_id_str.isdigit():
        await callback.answer("Некорректный проект.")
        return

    project_id = int(project_id_str)
    result = await session.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()

    if project:
        await callback.message.edit_text(project.content, parse_mode="HTML")
    else:
        await callback.answer("⚠️ Проект не найден.")


# Выбор направления
@start_router.callback_query(F.data.startswith("spec_"))
async def specialization(callback: CallbackQuery, session: AsyncSession):
    spec = callback.data.replace("spec_", "")

    # Сохранение направления в БД
    stmt = select(User).where(User.tg_id == callback.from_user.id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        user.specialization = spec
        await session.commit()

        await callback.message.edit_text(f"✅ Выбрано направление: <b>{spec}</b> 🎯",
                                         parse_mode="HTML")
        await callback.message.answer("🎓 Теперь выбери курс, который тебя интересует",
                                      reply_markup=courses_keyboard())


# Выбор курса
@start_router.callback_query(F.data.startswith("course_"))
async def course(callback: CallbackQuery, session: AsyncSession):
    course_code = callback.data.replace("course_", "")  # Извлекаем код курса из callback_data
    course_title = COURSE_TITLES.get(course_code, "Неизвестный курс")  # Ищем полное название курса

    # Сохранение полного названия курса в БД
    stmt = select(User).where(User.tg_id == callback.from_user.id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        user.course = course_title  # Сохраняем полное название
        await session.commit()

        # Отправляем сообщение с полным названием курса
        await callback.message.edit_text(f"✅ Выбран курс: <b>{course_title}</b> 🎓", parse_mode="HTML")
        await callback.message.answer(
            "🚀 Отлично! Теперь ты можешь перейти к подбору мероприятий.\n\nПри необходимости "
            "ты можешь изменить направление или курс в профиле.",
            reply_markup=kb_main
        )

@start_router.callback_query(F.data.startswith("page_"))
async def page_navigation(callback: CallbackQuery):
    page = int(callback.data.replace("page_", ""))
    keyboard = courses_keyboard(page)

    # Обновляем сообщение с курсами и клавиатурой навигации
    await callback.message.edit_text(
        text=f"🎓 Выбери курс (страница {page + 1}):",
        reply_markup=keyboard
    )
    await callback.answer()
