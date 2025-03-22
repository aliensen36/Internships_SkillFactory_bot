from aiogram.types import message, FSInputFile, Message
from sqlalchemy import select, update, insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from database.models import *
from database.engine import session_maker
from datetime import datetime
from app.fsm_states import BookingState

async def orm_survey(session: AsyncSession, tg_id: int, data: dict):
    data = Survey(
        tg_id=tg_id,
        age_group=data['age_group'],
        residence=data['residence'],
        company=data['company'],
        reason=data['reason'],
        advertising_sources=data['advertising_sources'],
        visit_frequency=data['visit_frequency'],
        purpose=data['purpose'],
        food_preferences=data['food_preferences'],
        suggestions=data['suggestions'],
        atmosphere=data['atmosphere'],
        service_rating=data['service_rating'],
        improvements=data['improvements'],
        obstacles=data['obstacles'],
        restaurants=data['restaurants'],
        news=data['news'],
        wishes=data['wishes'],
        recommendation=data['recommendation'],
        explanation=data['explanation'],
    )
    session.add(data)
    await session.commit()


async def orm_booking(session: AsyncSession, tg_id: int, data: dict):
    client_name = data.get("client_name")
    client_phone = data.get("client_phone")
    select_date = data.get("select_date")
    select_time = data.get("select_time")
    select_guests = int(data.get("select_guests"))
    additional_info = data.get("additional_info", "не указана")

    date_obj = datetime.strptime(select_date, "%d.%m.%Y").date()
    time_obj = datetime.strptime(select_time, "%H:%M").time()

    stmt = select(Booking).where(Booking.tg_id == tg_id,
                                 Booking.client_confirm == False).order_by(Booking.id.desc())
    result = await session.execute(stmt)
    booking = result.scalars().first()

    if booking:
        booking.client_name = client_name
        booking.client_phone = client_phone
        booking.select_date = date_obj
        booking.select_time = time_obj
        booking.select_guests = select_guests
        booking.additional_info = additional_info
        booking.client_confirm = True
        await session.commit()
    else:
        booking = Booking(
            tg_id=tg_id,
            client_name=client_name,
            client_phone=client_phone,
            select_date=date_obj,
            select_time=time_obj,
            select_guests=select_guests,
            additional_info=additional_info,
            client_confirm=True
        )
        session.add(booking)
        await session.commit()


async def get_new_bookings(session: AsyncSession) -> list[Booking]:
    stmt = (
        select(Booking)
        .options(selectinload(Booking.user))
        .where(
            Booking.client_confirm == True,
            Booking.admin_confirm == False,
            Booking.admin_cancelled == False
        )
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_confirmed_bookings(session: AsyncSession):
    stmt = (
        select(Booking)
        .options(selectinload(Booking.user))
        .where(
            Booking.admin_confirm == True
        )
    )
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_canceled_bookings(session: AsyncSession):
    stmt = (
        select(Booking)
        .options(selectinload(Booking.user))
        .where(
            Booking.admin_cancelled == True  # Фильтруем по заявкам, которые были отменены
        )
    )
    result = await session.execute(stmt)
    return result.scalars().all()
