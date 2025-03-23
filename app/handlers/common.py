from aiogram import Router, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

common_router = Router()

# Обработчик кнопки "ℹ️ О нас"
@common_router.message(F.text == "ℹ️ О нас")
async def abouy_us(message: Message):
    link_site = "https://skillfactory.ru/"
    link_calendar = "https://view.genially.com/66b2271a6ff343f7e18bb52f"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Наш сайт", url=link_site)],
        [InlineKeyboardButton(text="🗓 Календарь мероприятий", url=link_calendar)]
    ])
    await message.answer("🔗 Нажмите кнопку ниже, чтобы перейти на наш сайт "
                         "или посмотреть календарь мероприятий:", reply_markup=keyboard)