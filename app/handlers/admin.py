import os
from aiofiles import open as aio_open
from aiogram.types import FSInputFile
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
from app.keyboards.reply import kb_admin_main
from database.models import User, Specialization, Course, Broadcast

admin_router = Router()
admin_router.message.filter(ChatTypeFilter(["private"]), IsAdmin())


@admin_router.message(Command("admin"))
async def confirmation(message: Message):
    await message.answer("Что хотите сделать?", reply_markup=kb_admin_main)


@admin_router.message(F.text == '📊 Статистика')
async def show_statistics(message: Message, session: AsyncSession):
    total_users = await session.scalar(select(func.count()).select_from(User))
    total_specializations = await session.scalar(select(func.count()).select_from(Specialization))
    total_courses = await session.scalar(select(func.count()).select_from(Course))

    text = (
    "<b>📊 Статистика чат-бота:</b>\n\n"
    f"👥 Всего пользователей: <b>{total_users}</b>\n\n"
    f"🎯 Всего специализаций: <b>{total_specializations}</b>\n\n"
    f"📚 Всего курсов: <b>{total_courses}</b>\n\n"
    # f"🗣 Всего отзывов: <b>{total_feedbacks}</b>\n"
    )

    await message.answer(text, parse_mode="HTML", reply_markup=kb_admin_main)

