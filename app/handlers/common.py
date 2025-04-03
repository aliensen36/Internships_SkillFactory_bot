from aiogram import Router, F
from aiogram.filters import Filter
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Project

common_router = Router()

# Обработчик кнопки "О Factory"
@common_router.message(F.text == "О Factory")
async def about_us(message: Message):
    link_site = "https://skillfactory.ru/"
    link_calendar = "https://view.genially.com/66b2271a6ff343f7e18bb52f"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Наш сайт", url=link_site)],
        [InlineKeyboardButton(text="Календарь мероприятий", url=link_calendar)]
    ])
    await message.answer("🔗 Нажми, чтобы перейти на <b>наш сайт</b> "
                         "или посмотреть <b>календарь мероприятий</b>",
                         reply_markup=keyboard,
                         parse_mode="HTML")


