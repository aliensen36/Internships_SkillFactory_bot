from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from mypyc.irbuild import builder
from sqlalchemy import or_

from database.models import *


# Проекты
def get_main_menu_keyboard():
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="💼 Стажировка", callback_data="internship")
    keyboard.button(text="🏁 Хакатоны", callback_data="hackathons")
    keyboard.button(text="🚀 Мегахакатоны", callback_data="mega_hackathons")
    keyboard.button(text="🏆 Конкурсы", callback_data="contests")
    keyboard.button(text="🎮 Геймджемы", callback_data="gamejams")
    keyboard.button(text="✨ Спецпроекты", callback_data="special_projects")
    keyboard.adjust(2)  # 2 кнопки в ряд
    return keyboard.as_markup()


kb_factory = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="💼 Стажировки", callback_data="factory_internship"),
     InlineKeyboardButton(text="⚡ Хакатоны", callback_data="factory_hackathon")],

    [InlineKeyboardButton(text="🚀 Мегахакатоны", callback_data="factory_megahack"),
     InlineKeyboardButton(text="🏆 Конкурсы", callback_data="factory_contest")],

    [InlineKeyboardButton(text="🎮 Геймджемы", callback_data="factory_gamejam"),
     InlineKeyboardButton(text="🎯 Спецпроекты", callback_data="factory_special")]
])


# Выбор специализации
async def specialization_keyboard(session: AsyncSession):
    specialization_stmt = select(Specialization)
    result = await session.execute(specialization_stmt)
    specializations = result.scalars().all()

    inline_keyboard = []
    for specialization in specializations:
        button = InlineKeyboardButton(text=specialization.name,
                                      callback_data=f"spec_{specialization.id}")
        inline_keyboard.append([button])

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


# Выбор курсов с пагинацией
async def courses_keyboard(session: AsyncSession, specialization_id: int,
                           page: int = 0):
    items_per_page = 4
    start_index = page * items_per_page

    # Запрос курсов только по нужной специализации
    stmt = select(Course).where(Course.specialization_id == specialization_id).offset(start_index).limit(items_per_page)
    result = await session.execute(stmt)
    current_courses = result.scalars().all()

    # Если курсы не найдены на первой странице
    if not current_courses and page == 0:
        return None

    inline_keyboard = [[InlineKeyboardButton(text=course.name, callback_data=f"course_{course.id}")]
                       for course in current_courses]

    navigation_buttons = []

    # Кнопка "Назад"
    if page > 0:
        navigation_buttons.append(InlineKeyboardButton(text="⬅️ Назад",
                                                       callback_data=f"page_{specialization_id}_{page - 1}"))

    # Проверяем, есть ли следующая страница
    next_page_stmt = (
        select(Course)
        .where(Course.specialization_id == specialization_id)
        .offset((page + 1) * items_per_page)
        .limit(1)
    )
    next_page_result = await session.execute(next_page_stmt)
    if next_page_result.scalars().first():
        navigation_buttons.append(InlineKeyboardButton(text="➡️ Вперед",
                                                       callback_data=f"page_{specialization_id}_{page + 1}"))

    if navigation_buttons:
        inline_keyboard.append(navigation_buttons)

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


# Изменение специализации
async def change_specialization_keyboard(session: AsyncSession):
    specialization_stmt = select(Specialization)
    result = await session.execute(specialization_stmt)
    specializations = result.scalars().all()

    inline_keyboard = []
    for specialization in specializations:
        button = InlineKeyboardButton(text=specialization.name,
                                      callback_data=f"change_spec_{specialization.id}")
        inline_keyboard.append([button])

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


# Изменение курсов с пагинацией
async def change_courses_keyboard(session: AsyncSession,
                                  specialization_id: int,
                                  page: int = 0):
    items_per_page = 4
    start_index = page * items_per_page

    # Запрос курсов только по нужной специализации
    stmt = (
        select(Course)
        .where(Course.specialization_id == specialization_id)
        .offset(start_index)
        .limit(items_per_page)
    )
    result = await session.execute(stmt)
    current_courses = result.scalars().all()

    # Если курсы не найдены на первой странице
    if not current_courses and page == 0:
        return None

    inline_keyboard = [[InlineKeyboardButton(text=course.name,
                                             callback_data=f"change_course_{course.id}")]
                       for course in current_courses]

    navigation_buttons = []

    # Кнопка "Назад"
    if page > 0:
        navigation_buttons.append(
            InlineKeyboardButton(text="⬅️ Назад",
                                 callback_data=f"changepage_{specialization_id}_{page - 1}"))

    # Проверяем, есть ли следующая страница
    next_page_stmt = select(Course).where(Course.specialization_id == specialization_id).offset(
        (page + 1) * items_per_page).limit(1)
    next_page_result = await session.execute(next_page_stmt)
    if next_page_result.scalars().first():
        navigation_buttons.append(
            InlineKeyboardButton(text="➡️ Вперед",
                                 callback_data=f"changepage_{specialization_id}_{page + 1}"))

    if navigation_buttons:
        inline_keyboard.append(navigation_buttons)

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)




async def projects_keyboard(session: AsyncSession):
    builder = InlineKeyboardBuilder()

    result = await session.execute(select(Project))
    projects = result.scalars().all()

    for project in projects:
        builder.button(
            text=project.title,
            callback_data=f"project_{project.id}"
        )

    builder.adjust(2)
    return builder


async def bc_courses_keyboard(
        session: AsyncSession,
        search_query: str = None,
        page: int = 0,
        per_page: int = 8,
        selected_ids: list[int] = None
):
    builder = InlineKeyboardBuilder()

    if selected_ids is None:
        selected_ids = []

    query = select(Course)
    if search_query:
        query = query.where(Course.name.ilike(f"%{search_query}%"))

    # Добавляем сортировку по имени курса
    query = query.order_by(Course.name.asc())

    query = query.offset(page * per_page).limit(per_page)
    result = await session.execute(query)
    courses = result.scalars().all()

    # Сортируем курсы по имени (уже отсортированы в запросе, но для надежности)
    sorted_courses = sorted(courses, key=lambda c: c.name)

    for course in sorted_courses:
        # Добавляем галочку для выбранных курсов
        prefix = "✅ " if course.id in selected_ids else ""
        builder.button(
            text=f"{prefix}{course.name}",
            callback_data=f"bccourse_{course.id}"
        )

    builder.adjust(2)

    # Навигация
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(
                text="◀️ Назад",
                callback_data=f"bcpage_{page - 1}_{search_query or ''}"
            )
        )

    next_page = await session.execute(query.offset((page + 1) * per_page).limit(1))
    if next_page.scalars().first():
        nav_buttons.append(
            InlineKeyboardButton(
                text="▶️ Вперед",
                callback_data=f"bcpage_{page + 1}_{search_query or ''}"
            )
        )

    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(
        InlineKeyboardButton(
            text="🔍 Поиск курсов",
            callback_data="courses_search"
        ),
        InlineKeyboardButton(
            text="✅ Завершить выбор",
            callback_data="finish_courses_selection"
        )
    )

    return builder
