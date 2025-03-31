from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Project

# Главное меню
kb_main = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="ℹ️ О Factory"), KeyboardButton(text="⭐ Проекты")],
    [KeyboardButton(text="👤 Мой профиль")],
],
    resize_keyboard=True
)



# Клавиатура Профиля
kb_profile = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🔁 Изменить курс"), KeyboardButton(text="🔙 Назад")]
],
    resize_keyboard=True
)



# =====================================================================================
# ------------------------------- Административный раздел -----------------------------
# =====================================================================================



# Главная клавиатура админа
kb_admin_main = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='📁 Проекты'), KeyboardButton(text='📚 Специализации и курсы')],
    [KeyboardButton(text='📢 Рассылка'), KeyboardButton(text='📊 Статистика')],
    [KeyboardButton(text='Выйти из админ-панели')],
],
    resize_keyboard=True
)


# Клавиатура проектов
def projects_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👀 Просмотр"), KeyboardButton(text="➕ Добавить")],
            [KeyboardButton(text="✏️ Изменить"), KeyboardButton(text="🗑️ Удалить")],
            [KeyboardButton(text="◀️ Назад")]
        ],
        resize_keyboard=True,
    )


# Подтверждение/отмена добавления проекта
confirm_cancel_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Подтвердить"), KeyboardButton(text="❌ Отменить")]
    ],
    resize_keyboard=True
)


# Клавиатура для подтверждения удаления проекта
confirm_delete_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Да, удалить"), KeyboardButton(text="❌ Нет, отменить")]
    ],
    resize_keyboard=True
)


kb_specializations_courses = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text= '🎯 Специализации'), KeyboardButton(text='📚 Курсы')],
    [KeyboardButton(text='⬅️ Назад')],
],
    resize_keyboard=True
)


# kb_specializations = ReplyKeyboardMarkup(keyboard=[
#     [KeyboardButton(text='👁️ Просмотр'), KeyboardButton(text='➕ Добавить')],
#     [KeyboardButton(text='✏️ Изменить'), KeyboardButton(text='🗑️ Удалить')],
#     [KeyboardButton(text='⬅️ Назад')],
# ],
#     resize_keyboard=True,
# )


async def specializations_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text='👁️ Просмотр')
    builder.button(text='➕ Добавить')
    builder.button(text='✏️ Изменить')
    builder.button(text='🗑️ Удалить')
    builder.button(text='⬅️ Назад')
    builder.adjust(2, 2, 1)
    return builder.as_markup(
        resize_keyboard=True,
    )


kb_courses = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='Просмотр 👁️'), KeyboardButton(text='Добавить ➕')],
    [KeyboardButton(text='Изменить ✏️'), KeyboardButton(text='Удалить 🗑️')],
    [KeyboardButton(text='Назад ⬅️')],
],
    resize_keyboard=True,
)

