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
        [InlineKeyboardButton(text="Календарь мероприятий", url=link_calendar)],
        [InlineKeyboardButton(text="Команда разработки", callback_data="dev_team")]
    ])
    await message.answer("🔗 Нажми, чтобы перейти на <b>наш сайт</b> "
                         "или посмотреть <b>календарь мероприятий</b>",
                         reply_markup=keyboard,
                         parse_mode="HTML")


@common_router.callback_query(F.data == "dev_team")
async def show_dev_team(callback: CallbackQuery):
    dev_info = """
    👨‍💻 <b>Команда разработки</b> 👩‍💻
    Мы - команда энтузиастов, создающих этот бот для удобства студентов SkillFactory.
    <b>Контакты:</b>
    • Разработчик 1: @username1
    • Разработчик 2: @username2
    • Техподдержка: support@example.com
    Если у вас есть вопросы или предложения по улучшению бота - пишите нам!
        """
    await callback.message.answer(dev_info, parse_mode="HTML")
    await callback.answer()