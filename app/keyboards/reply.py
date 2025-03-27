from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Project

# Главное меню
kb_main = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="ℹ️ О нас"), KeyboardButton(text="⭐ Проекты")],
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


# Главная клавиатура админа
kb_admin_main = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='📁 Проекты'), KeyboardButton(text='📚 Специализации и курсы')],
    [KeyboardButton(text='📢 Рассылка'), KeyboardButton(text='📊 Статистика')],
    [KeyboardButton(text='⬅️ Назад')],
],
    resize_keyboard=True
)


# Клавиатура проектов
kb_admin_projects = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='📥 Добавить проект'), KeyboardButton(text='✏️ Изменить проект')],
    [KeyboardButton(text='❌ Удалить проект'), KeyboardButton(text='⬅️ Назад')],
],
    resize_keyboard=True
)


kb_specializations_courses = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text= '🎯 Специализации'), KeyboardButton(text='📚 Курсы')],
    [KeyboardButton(text='⬅️ Назад')],
],
    resize_keyboard=True
)


kb_specializations = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='👁️ Просмотр'), KeyboardButton(text='➕ Добавить')],
    [KeyboardButton(text='✏️ Изменить'), KeyboardButton(text='🗑️ Удалить')],
    [KeyboardButton(text='⬅️ Назад')],
],
    resize_keyboard=True,
)


kb_courses = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='Просмотр 👁️'), KeyboardButton(text='Добавить ➕')],
    [KeyboardButton(text='Изменить ✏️'), KeyboardButton(text='Удалить 🗑️')],
    [KeyboardButton(text='Назад ⬅️')],
],
    resize_keyboard=True,
)

