from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession



# Главное меню
kb_main = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="О Factory"),
     KeyboardButton(text="Проекты"),
     KeyboardButton(text="Мой курс")]
],
    resize_keyboard=True
)



# =====================================================================================
# ------------------------------- Административный раздел -----------------------------
# =====================================================================================


# Кнопка выхода из админ-панели
kb_admin_main = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='Выйти из админ-панели')],
],
    resize_keyboard=True
)
