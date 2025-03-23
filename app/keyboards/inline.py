from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.constants import COURSE_TITLES, courses, change_courses


# Главное меню
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


# Кнопка "Прочитать" для скрытого текста
def get_hidden_text_keyboard(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📜 Прочитать", callback_data=key)]
        ]
    )


# Клавиатура для выбора направления
kb_specialization = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="💻 Разработка", callback_data="spec_Разработка")],
        [InlineKeyboardButton(text="🧪 Тестирование", callback_data="spec_Тестирование")],
        [InlineKeyboardButton(text="📊 Аналитика и Data Science", callback_data="spec_Аналитика и DS")],
        [InlineKeyboardButton(text="🎨 Дизайн", callback_data="spec_Дизайн")],
        [InlineKeyboardButton(text="📈 Менеджмент и маркетинг в IT", callback_data="spec_Менеджмент и маркетинг")],
        [InlineKeyboardButton(text="🎓 Высшее образование", callback_data="spec_Высшее образование")],
    ]
)


kb_change_specialization = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="💻 Разработка", callback_data="profile_spec_Разработка")],
        [InlineKeyboardButton(text="🧪 Тестирование", callback_data="profile_spec_Тестирование")],
        [InlineKeyboardButton(text="📊 Аналитика и Data Science", callback_data="profile_spec_Аналитика и DS")],
        [InlineKeyboardButton(text="🎨 Дизайн", callback_data="profile_spec_Дизайн")],
        [InlineKeyboardButton(text="📈 Менеджмент и маркетинг в IT", callback_data="profile_spec_Менеджмент и маркетинг")],
        [InlineKeyboardButton(text="🎓 Высшее образование", callback_data="profile_spec_Высшее образование")],
    ]
)


# Функция для создания клавиатуры для выбора курсов с кнопками навигации
def courses_keyboard(page: int = 0):
    items_per_page = 4

    start_index = page * items_per_page
    end_index = start_index + items_per_page
    current_courses = courses[start_index:end_index]

    inline_keyboard = []

    # Кнопки курсов с полными названиями
    for name, callback_data in current_courses:
        # Извлекаем аббревиатуру из полного названия курса
        course_code = callback_data.replace("course_", "")

        # Получаем полное название курса
        full_course_name = COURSE_TITLES.get(course_code, name)

        # Создаем кнопку
        button = InlineKeyboardButton(text=full_course_name, callback_data=callback_data)
        inline_keyboard.append([button])

    # Кнопки навигации
    navigation_buttons = []
    if page > 0:
        navigation_buttons.append(InlineKeyboardButton(text="⬅️ Назад",
                                                       callback_data=f"page_{page - 1}"))
    if end_index < len(courses):
        navigation_buttons.append(InlineKeyboardButton(text="➡️ Вперед",
                                                       callback_data=f"page_{page + 1}"))

    if navigation_buttons:
        inline_keyboard.append(navigation_buttons)

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


# Клавиатура для изменения курса в профиле
def change_courses_keyboard(page: int = 0):
    items_per_page = 4

    start_index = page * items_per_page
    end_index = start_index + items_per_page
    current_courses = change_courses[start_index:end_index]

    inline_keyboard = []

    # Кнопки курсов с полными названиями
    for name, callback_data in current_courses:
        # Извлекаем аббревиатуру из полного названия курса
        course_code = callback_data.replace("course_", "")

        # Получаем полное название курса
        full_course_name = COURSE_TITLES.get(course_code, name)

        # Создаем кнопку
        button = InlineKeyboardButton(text=full_course_name, callback_data=callback_data)
        inline_keyboard.append([button])

    # Кнопки навигации
    navigation_buttons = []
    if page > 0:
        navigation_buttons.append(InlineKeyboardButton(text="⬅️ Назад",
                                                       callback_data=f"page_{page - 1}"))
    if end_index < len(courses):
        navigation_buttons.append(InlineKeyboardButton(text="➡️ Вперед",
                                                       callback_data=f"page_{page + 1}"))

    if navigation_buttons:
        inline_keyboard.append(navigation_buttons)

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
