from aiogram.types import message, FSInputFile, Message
from sqlalchemy import select, update, insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from database.models import *
from database.engine import session_maker
from datetime import datetime
from app.fsm_states import BookingState

# Информация о проектах СФ в приветствии
async def get_all_projects(session: AsyncSession):
    result = await session.execute(select(Project))
    return result.scalars().all()
