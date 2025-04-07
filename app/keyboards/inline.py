from aiogram.filters import Filter
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from mypyc.irbuild import builder
from sqlalchemy import or_

from database.models import *


# =====================================================================================
# -------------------------------------- Старт бота -----------------------------------
# =====================================================================================


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

    inline_keyboard = [
        [InlineKeyboardButton(
            text=course.name,
            callback_data=f"course_{course.id}"
        )
        ]
        for course in current_courses
    ]

    navigation_buttons = []

    # Кнопка "Назад"
    if page > 0:
        navigation_buttons.append(
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=f"page_{specialization_id}_{page - 1}")
        )

    # Проверяем, есть ли следующая страница
    next_page_stmt = (
        select(Course)
        .where(Course.specialization_id == specialization_id)
        .offset((page + 1) * items_per_page)
        .limit(1)
    )
    next_page_result = await session.execute(next_page_stmt)
    if next_page_result.scalars().first():
        navigation_buttons.append(
            InlineKeyboardButton(
                text="➡️ Вперед",
                callback_data=f"page_{specialization_id}_{page + 1}")
        )

    if navigation_buttons:
        inline_keyboard.append(navigation_buttons)

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)



# =====================================================================================
# ------------------------------ Проекты (клиентская часть) ---------------------------
# =====================================================================================


# Проекты - обзор проектов (первый уровень)
async def view_projects_keyboard(session: AsyncSession):
    builder = InlineKeyboardBuilder()
    result = await session.execute(select(Project))
    projects = result.scalars().all()

    for project in projects:
        builder.button(
            text=project.title,
            callback_data=f"view_project_{project.id}"
        )

    builder.adjust(2)
    return builder

# Просмотр конкретного проекта (второй уровень)
class ProjectCallbackFilter(Filter):
    def __init__(self, prefix: str):
        self.prefix = prefix

    async def __call__(self, callback: CallbackQuery) -> bool:
        return callback.data.startswith(self.prefix)

async def view_project_kb(session: AsyncSession):
    builder = InlineKeyboardBuilder()
    result = await session.execute(select(Project))
    projects = result.scalars().all()

    for project in projects:
        builder.button(
            text=project.title,
            callback_data=f"view_project_{project.id}"
        )

    builder.button(text="Назад", callback_data="back_to_main_menu")
    builder.adjust(2)
    return builder.as_markup()

# Кнопка для каждого проекта
async def get_project_details_keyboard(project_id: int, session: AsyncSession):
    builder = InlineKeyboardBuilder()

    # Получаем проект из базы данных
    project = await session.get(Project, project_id)
    if not project:
        raise ValueError("Project not found")

    # Первая кнопка - индивидуальное название проекта
    builder.button(
        text=f"{project.title} – это...",
        callback_data=f"about_project_{project.id}"
    )

    # Вторая кнопка - бенефиты
    builder.button(
        text="Бенефиты от участия",
        callback_data=f"benefits_project_{project.id}"
    )

    # Третья кнопка - примеры
    builder.button(
        text="Примеры",
        callback_data=f"examples_project_{project.id}"
    )

    # Четвертая кнопка - все мероприятия
    builder.button(
        text="Перейти ко всем мероприятиям",
        url="https://view.genially.com/66b2271a6ff343f7e18bb52f"
    )

    # Пятая кнопка - доступные по курсу
    builder.button(
        text="Доступные по моему курсу",
        callback_data=f"available_to_me_project_{project.id}"
    )

    # Шестая кнопка - назад
    builder.button(
        text="Назад",
        callback_data="back_to_projects_list"
    )

    # Распределяем кнопки по 2 в ряду
    builder.adjust(1)
    return builder.as_markup()

async def project_details_message(project: Project) -> str:
    return (f"<b>{project.title}</b>\n\n")



# =====================================================================================
# ------------------------------ Профиль (клиентская часть) ---------------------------
# =====================================================================================


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


# Изменение курса с пагинацией
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
            InlineKeyboardButton(text="Назад",
                                 callback_data=f"changepage_{specialization_id}_{page - 1}"))

    # Проверяем, есть ли следующая страница
    next_page_stmt = select(Course).where(Course.specialization_id == specialization_id).offset(
        (page + 1) * items_per_page).limit(1)
    next_page_result = await session.execute(next_page_stmt)
    if next_page_result.scalars().first():
        navigation_buttons.append(
            InlineKeyboardButton(text="Вперед",
                                 callback_data=f"changepage_{specialization_id}_{page + 1}"))

    if navigation_buttons:
        inline_keyboard.append(navigation_buttons)

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


# =====================================================================================
# ------------------------------- Административный раздел -----------------------------
# =====================================================================================

# Главное меню админа
async def admin_main_menu():
    builder = InlineKeyboardBuilder()

    buttons = [
        InlineKeyboardButton(text="Проекты",
                             callback_data="admin_projects"),
        InlineKeyboardButton(text="Специализации",
                             callback_data="admin_specializations"),
        InlineKeyboardButton(text="Курсы",
                             callback_data="admin_courses"),
        InlineKeyboardButton(text="Рассылка",
                             callback_data="admin_mailing"),
        InlineKeyboardButton(text="Статистика",
                             callback_data="admin_stats")
    ]

    builder.add(*buttons)
    builder.adjust(2, 2, 1)

    return builder.as_markup()

# ------------------------------------- Проекты ---------------------------------------

# Главное меню управления проектами
async def admin_projects_menu():
    builder = InlineKeyboardBuilder()

    buttons = [
        InlineKeyboardButton(text="Список", callback_data="projects:list"),
        InlineKeyboardButton(text="Добавить", callback_data="projects:add"),
        InlineKeyboardButton(text="Изменить", callback_data="projects:edit"),
        InlineKeyboardButton(text="Удалить", callback_data="projects:delete"),
        InlineKeyboardButton(text="Назад", callback_data="projects:admin_main_menu")
    ]

    builder.add(*buttons)
    builder.adjust(2, 2, 1)

    return builder.as_markup()


# Подтверждение/отмена добавления проекта
async def confirm_cancel_add_projects():
    builder = InlineKeyboardBuilder()

    buttons = [
        InlineKeyboardButton(text="Подтвердить", callback_data="confirm_add_project"),
        InlineKeyboardButton(text="Отменить", callback_data="cancel_add_project")
    ]

    builder.add(*buttons)
    builder.adjust(2)

    return builder.as_markup()


# Подтверждение/отмена изменения проекта
async def confirm_cancel_edit_projects():
    builder = InlineKeyboardBuilder()

    buttons = [
        InlineKeyboardButton(text="Подтвердить", callback_data="confirm_edit_project"),
        InlineKeyboardButton(text="Отменить", callback_data="cancel_edit_project")
    ]

    builder.add(*buttons)
    builder.adjust(2)

    return builder.as_markup()

# Подтверждение/отмена удаления проектов
async def confirm_delete_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="Да, удалить", callback_data="delete_projects:confirm"),
        InlineKeyboardButton(text="Нет, отменить", callback_data="delete_projects:cancel")
    )
    return builder.as_markup()



# ------------------------------------- Специализации ---------------------------------



# Главное меню управления специализациями
async def admin_specializations_menu():
    builder = InlineKeyboardBuilder()

    buttons = [
        InlineKeyboardButton(text="Список",
                             callback_data="specializations:list"),
        InlineKeyboardButton(text="Добавить",
                             callback_data="specializations:add"),
        InlineKeyboardButton(text="Изменить",
                             callback_data="specializations:edit"),
        InlineKeyboardButton(text="Удалить",
                             callback_data="specializations:delete"),
        InlineKeyboardButton(text="Назад",
                             callback_data="specializations:admin_main_menu")
    ]

    builder.add(*buttons)
    builder.adjust(2, 2, 1)

    return builder.as_markup()


# Подтверждение/отмена добавления специализации
async def confirm_cancel_add_specializations():
    builder = InlineKeyboardBuilder()

    buttons = [
        InlineKeyboardButton(text="Подтвердить",
                             callback_data="confirm_add_specialization"),
        InlineKeyboardButton(text="Отменить",
                             callback_data="cancel_add_specialization")
    ]

    builder.add(*buttons)
    builder.adjust(2)

    return builder.as_markup()


# Подтверждение/отмена изменения специализации
async def confirm_cancel_edit_specializations():
    builder = InlineKeyboardBuilder()

    buttons = [
        InlineKeyboardButton(text="Подтвердить",
                             callback_data="confirm_edit_specialization"),
        InlineKeyboardButton(text="Отменить",
                             callback_data="cancel_edit_specialization")
    ]

    builder.add(*buttons)
    builder.adjust(2)

    return builder.as_markup()

# Подтверждение/отмена удаления специализаций
async def confirm_delete_specializations():
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="Да, удалить",
                             callback_data="delete_specializations:confirm"),
        InlineKeyboardButton(text="Нет, отменить",
                             callback_data="delete_specializations:cancel")
    )
    return builder.as_markup()




# --------------------------------------- Курсы ---------------------------------------



# Главное меню управления курсами
async def admin_courses_menu():
    builder = InlineKeyboardBuilder()

    buttons = [
        InlineKeyboardButton(text="Список",
                             callback_data="courses:list"),
        InlineKeyboardButton(text="Добавить",
                             callback_data="courses:add"),
        InlineKeyboardButton(text="Изменить",
                             callback_data="courses:edit"),
        InlineKeyboardButton(text="Удалить",
                             callback_data="courses:delete"),
        InlineKeyboardButton(text="Назад",
                             callback_data="courses:admin_main_menu")
    ]

    builder.add(*buttons)
    builder.adjust(2, 2, 1)

    return builder.as_markup()


# Подтверждение/отмена добавления курса
async def confirm_cancel_add_courses():
    builder = InlineKeyboardBuilder()

    buttons = [
        InlineKeyboardButton(text="Подтвердить",
                             callback_data="confirm_add_course"),
        InlineKeyboardButton(text="Отменить",
                             callback_data="cancel_add_course")
    ]

    builder.add(*buttons)
    builder.adjust(2)

    return builder.as_markup()


# Подтверждение/отмена изменения курса
async def confirm_cancel_edit_courses():
    builder = InlineKeyboardBuilder()

    buttons = [
        InlineKeyboardButton(text="Подтвердить",
                             callback_data="confirm_edit_course"),
        InlineKeyboardButton(text="Отменить",
                             callback_data="cancel_edit_course")
    ]

    builder.add(*buttons)
    builder.adjust(2)

    return builder.as_markup()

# Подтверждение/отмена удаления курса
async def confirm_delete_courses():
    builder = InlineKeyboardBuilder()
    builder.add(
        InlineKeyboardButton(text="Да, удалить",
                             callback_data="delete_сourses:confirm"),
        InlineKeyboardButton(text="Нет, отменить",
                             callback_data="delete_сourses:cancel")
    )
    return builder.as_markup()



# ======================================================================================
# -------------------------------------- Рассылка -------------------------------------
# ======================================================================================



# Проекты
async def bc_projects_keyboard(session: AsyncSession):
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


# Курсы
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
                text="Назад",
                callback_data=f"bcpage_{page - 1}_{search_query or ''}"
            )
        )

    next_page = await session.execute(query.offset((page + 1) * per_page).limit(1))
    if next_page.scalars().first():
        nav_buttons.append(
            InlineKeyboardButton(
                text="Вперед",
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


# Клавиатура подтверждения
builder = InlineKeyboardBuilder()
builder.button(text="✅ Подтвердить", callback_data="confirm_broadcast")
builder.button(text="✏️ Изменить текст", callback_data="edit_text")
builder.button(text="🖼️ Изменить фото", callback_data="edit_photo")
builder.button(text="📌 Изменить проект", callback_data="edit_project")
builder.button(text="🎯 Изменить курсы", callback_data="edit_courses")
builder.button(text="❌ Отменить", callback_data="cancel_broadcast")
builder.adjust(2, 2, 2)
# ======================================================================================



# ------------------------------- Админ-панель ------------------------------------
# ======================================================================================

# Проекты
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




