import os
import asyncio
from aiogram import Bot, Dispatcher, types
from dotenv import load_dotenv
load_dotenv()

import logging
from app.bot_cmds_list import bot_cmds_list
from database.engine import create_db, drop_db, session_maker
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import default_state, State, StatesGroup
from middlewares.db import DataBaseSession
from app.handlers.start import start_router
from app.handlers.admin import admin_router
from app.handlers.user_group import user_group_router
from app.handlers.profile import profile_router
from app.handlers.admin_project import admin_project_router
from app.handlers.common import common_router
from app.handlers.projects import projects_router
from app.handlers.admin_specialization import admin_specialization_router
from app.handlers.admin_course import admin_course_router
from app.handlers.admin_broadcast import admin_broadcast_router


logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv('BOT_TOKEN')

bot = Bot(BOT_TOKEN)
bot.admins_list = []

dp = Dispatcher(storage=MemoryStorage())

dp.include_router(user_group_router)
dp.include_router(profile_router)
dp.include_router(start_router)
dp.include_router(common_router)
dp.include_router(projects_router)

dp.include_router(admin_router)
dp.include_router(admin_project_router)
dp.include_router(admin_specialization_router)
dp.include_router(admin_course_router)
dp.include_router(admin_broadcast_router)


async def on_startup(bot):
    run_param = False
    if run_param:
        await drop_db()
    await create_db()
    logging.info("Бот успешно запущен. https://t.me/Internships_SkillFactory_bot")

async def main():
    dp.startup.register(on_startup)
    dp.update.middleware(DataBaseSession(session_pool=session_maker))
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_my_commands(commands=bot_cmds_list, scope=types.BotCommandScopeAllPrivateChats())
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен.")
    except Exception as e:
        logging.error(f"Ошибка: {e}")
