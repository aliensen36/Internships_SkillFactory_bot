import os
from aiofiles import open as aio_open
from aiogram.fsm import state
from aiogram.types import FSInputFile, CallbackQuery
from aiogram import F, Router, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from app.filters.chat_types import ChatTypeFilter, IsAdmin
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from sqlalchemy import select, func
from datetime import datetime, timedelta
from collections import defaultdict

from app.keyboards.inline import admin_main_menu
from app.keyboards.reply import kb_admin_main, kb_main
from database.models import User, Specialization, Course, Broadcast

admin_router = Router()
admin_router.message.filter(ChatTypeFilter(["private"]), IsAdmin())


@admin_router.message(Command("admin"))
async def confirmation(message: Message, bot: Bot):
    await message.answer(
        "🛠️ <b>Административная панель</b>",
        parse_mode="HTML",
        reply_markup=kb_admin_main
    )
    await message.answer(
        "Управление разделами:",
        reply_markup=await admin_main_menu()
    )



# Обработчик кнопки выхода
@admin_router.message(F.text == "Выйти из админ-панели")
async def exit_admin_panel(message: Message,
                           state: FSMContext):
    await message.answer(
        "Выход из админ-панели.",
        reply_markup=kb_main)
    await state.clear()



