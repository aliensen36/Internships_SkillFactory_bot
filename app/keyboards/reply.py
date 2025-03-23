from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder


# Главное меню
kb_main = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🗓 Календарь мероприятий"), KeyboardButton(text="🌐 Наш сайт")],
    [KeyboardButton(text="⭐ Главное меню"), KeyboardButton(text="👤 Мой профиль")],
],
    resize_keyboard=True,
    input_field_placeholder='Выберите действие')


# Клавиатура Профиля
kb_profile = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🔄 Изменить направление"), KeyboardButton(text="🔁 Изменить курс")],
    [KeyboardButton(text="🔙 Назад")]
], resize_keyboard=True)
