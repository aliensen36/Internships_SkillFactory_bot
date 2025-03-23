from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder


# Главное меню
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

kb_main = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="ℹ️ О нас")],
    [KeyboardButton(text="⭐ Главное меню"), KeyboardButton(text="👤 Мой профиль")],
],
    resize_keyboard=True,
    input_field_placeholder='Выберите действие')


# Клавиатура Профиля
kb_profile = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🔄 Изменить направление"), KeyboardButton(text="🔁 Изменить курс")],
    [KeyboardButton(text="🔙 Назад")]
], resize_keyboard=True)


# Главная клавиатура админа
admin_main = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='📚 Специализации и курсы'), KeyboardButton(text='📢 Рассылка')],
    [KeyboardButton(text='📥 Добавить проект'), KeyboardButton(text='✏️ Изменить проект')],
    [KeyboardButton(text='❌ Удалить проект')],
    [KeyboardButton(text='⬅️ Назад')],
],
    resize_keyboard=True,
    input_field_placeholder='Выберите действие')


kb_specializations_courses = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text= '🎯 Специализации'), KeyboardButton(text='📚 Курсы')],
    [KeyboardButton(text='⬅️ Назад')],
],
    resize_keyboard=True,
    input_field_placeholder='Выберите действие')


kb_specializations = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='👁️ Просмотр'), KeyboardButton(text='➕ Добавить')],
    [KeyboardButton(text='✏️ Изменить'), KeyboardButton(text='🗑️ Удалить')],
    [KeyboardButton(text='⬅️ Назад')],
],
    resize_keyboard=True,
    input_field_placeholder='Выберите действие'
)
