from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.fsm_states import ChangeCourseState
from app.keyboards.inline import *
from app.keyboards.reply import kb_profile, kb_main
from database.models import *
from aiogram.exceptions import TelegramBadRequest


profile_router = Router()


@profile_router.message(F.text == "Мой курс")
async def profile_handler(message: Message, session: AsyncSession):
    stmt = select(User).where(User.tg_id == message.from_user.id).options(
        selectinload(User.specialization),
        selectinload(User.course)
    )
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        specialization = user.specialization.name if user.specialization else "не выбрано"
        course = user.course.name if user.course else "не выбран"

        # Создаем клавиатуру
        builder = InlineKeyboardBuilder()

        if user.course_id:  # Добавляем кнопки только если курс выбран
            builder.row(
                InlineKeyboardButton(
                    text="Все доступные мероприятия по моему курсу",
                    callback_data=f"view_course_events_{user.course_id}"
                )
            )

        # Добавляем кнопку "Изменить курс" в любом случае
        builder.row(
            InlineKeyboardButton(
                text="Изменить курс",
                callback_data="change_course_from_profile"
            )
        )

        await message.answer(
            f"🔸 Выбрана специализация:\n<b>{specialization}</b>\n\n"
            f"🔹 Выбран курс:\n<b>{course}</b>",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )
    else:
        await message.answer("Профиль не найден. Попробуй снова /start.")


@profile_router.callback_query(F.data == "change_course_from_profile")
async def change_specialization_start(callback: CallbackQuery,
                                      state: FSMContext,
                                      session: AsyncSession):
    # Загружаем текущие данные пользователя перед изменением
    stmt = select(User).where(User.tg_id == callback.from_user.id).options(
        selectinload(User.specialization),
        selectinload(User.course)
    )
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
    # Сохраняем текущие значения в state
        await state.update_data(
            old_spec_id = user.specialization_id,
            old_course_id = user.course_id
        )

    await callback.message.answer("🎯 Выбери специализацию:",
                         reply_markup=await change_specialization_keyboard(session))
    await callback.answer()
    await state.set_state(ChangeCourseState.waiting_for_specialization)


# Обработчик для команды /course
# @profile_router.message(Command("course"))
# async def course_command(message: Message, state: FSMContext, session: AsyncSession):
#     # Просто вызываем существующий обработчик
#     await change_specialization_start(message, state, session)


@profile_router.callback_query(ChangeCourseState.waiting_for_specialization,
                               F.data.startswith("change_spec_"))
async def change_specialization(callback: CallbackQuery,
                                state: FSMContext,
                                session: AsyncSession):
    spec_id = callback.data.replace("change_spec_", "").strip()
    if not spec_id.isdigit():
        await callback.answer("❌ Некорректный ID специализации.", show_alert=True)
        return

    # Сохраняем новую специализацию в state, но пока не применяем к пользователю
    await state.update_data(new_spec_id=int(spec_id))

    stmt = select(Specialization).where(Specialization.id == int(spec_id))
    spec_result = await session.execute(stmt)
    specialization = spec_result.scalar_one_or_none()

    if specialization:
        await callback.message.edit_text(
            f"✅ Выбрана специализация:\n\n<b>{specialization.name}</b>",
            parse_mode="HTML"
        )

        # Проверяем, есть ли курсы по этой специализации
        keyboard = await change_courses_keyboard(session, int(spec_id), 0)

        if keyboard is None:
            await callback.message.answer(
                "❌ Курсов не найдено. Выбери другую специализацию:",
                reply_markup=await specialization_keyboard(session)
            )
        else:
            await callback.message.answer(
                "🎓 Теперь выбери курс, который тебя интересует:",
                reply_markup=keyboard
            )
            await state.set_state(ChangeCourseState.waiting_for_course)
    else:
        await callback.answer("❌ Специализация не найдена.", show_alert=True)


@profile_router.callback_query(ChangeCourseState.waiting_for_course,
                               F.data.startswith("change_course_"))
async def change_course(callback: CallbackQuery, state: FSMContext,
                        session: AsyncSession):
    course_id = callback.data.replace("change_course_", "")

    if not course_id.isdigit():
        await callback.answer("❌ Некорректный ID курса.", show_alert=True)
        return

    # Получаем все данные из state
    state_data = await state.get_data()
    new_spec_id = state_data.get('new_spec_id')

    stmt = select(User).where(User.tg_id == callback.from_user.id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        # Обновляем и специализацию, и курс
        user.specialization_id = new_spec_id
        user.course_id = int(course_id)
        await session.commit()

        stmt = select(Course).where(Course.id == int(course_id))
        result = await session.execute(stmt)
        course = result.scalar_one_or_none()

        await callback.message.edit_text(
            f"✅ Выбран курс:\n\n<b>{course.name}</b>",
            parse_mode="HTML"
        )
        await callback.message.answer(
            "Выбери действие:",
            reply_markup=kb_main
        )

    else:
        await callback.answer("❌ Пользователь не найден.", show_alert=True)
    await state.clear()


# @profile_router.message(F.text == "Назад")
# async def back_to_main_menu(message: Message, state: FSMContext, session: AsyncSession):
#     # Проверяем, есть ли незавершенный процесс изменения курса
#     current_state = await state.get_state()
#     if current_state == ChangeCourseState.waiting_for_course:
#         # Восстанавливаем старые значения
#         state_data = await state.get_data()
#         old_spec_id = state_data.get('old_spec_id')
#         old_course_id = state_data.get('old_course_id')
#
#         stmt = select(User).where(User.tg_id == message.from_user.id)
#         result = await session.execute(stmt)
#         user = result.scalar_one_or_none()
#
#         if user:
#             # Восстанавливаем только если пользователь не завершил выбор курса
#             user.specialization_id = old_spec_id
#             user.course_id = old_course_id
#             await session.commit()
#
#     await state.clear()
#     await message.answer("Выбери действие", reply_markup=kb_main)


# Пагинация при изменении курса
@profile_router.callback_query(F.data.startswith("changepage_"))
async def paginate_courses(callback: CallbackQuery, session: AsyncSession):
    _, specialization_id, page = callback.data.split("_")

    if not specialization_id.isdigit() or not page.isdigit():
        await callback.answer("❌ Некорректный запрос.", show_alert=True)
        return

    specialization_id, page = int(specialization_id), int(page)

    keyboard = await change_courses_keyboard(session, specialization_id, page)

    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except TelegramBadRequest:
        pass  # Игнорируем, если клавиатура не изменилась


# Все доступные мероприятия курса
@profile_router.callback_query(F.data.startswith("view_course_events_"))
async def view_course_events(callback: CallbackQuery, session: AsyncSession):
    try:
        # Получаем ID курса из callback данных
        course_id = int(callback.data.split("_")[-1])

        async with session.begin():
            # Проверяем существование курса
            course = await session.get(Course, course_id)
            if not course:
                await callback.answer("❌ Курс не найден", show_alert=True)
                return

            # Получаем ВСЕ активные рассылки для этого курса
            stmt = (
                select(Broadcast)
                .join(Broadcast.course_associations)
                .options(selectinload(Broadcast.project))
                .where(
                    Broadcast.is_sent == True,
                    Broadcast.is_active == True,
                    BroadcastCourseAssociation.course_id == course_id
                )
                .order_by(Broadcast.created.desc())
            )

            broadcasts = (await session.scalars(stmt)).all()

            if not broadcasts:
                await callback.answer("📭 Нет доступных мероприятий для вашего курса", show_alert=True)
                return

            # Создаем клавиатуру с рассылками
            builder = InlineKeyboardBuilder()

            for broadcast in broadcasts:
                # Формируем текст кнопки (только первые 40 символов текста)
                if broadcast.text:
                    text_preview = broadcast.text[:40].strip()
                    # Добавляем многоточие только если текст был обрезан
                    if len(broadcast.text) > 40:
                        text_preview += "..."
                else:
                    text_preview = "Нет описания"

                builder.row(
                    InlineKeyboardButton(
                        text=text_preview,
                        callback_data=f"view_broadcast_{broadcast.id}"
                    )
                )

            await callback.message.edit_text(
                f"📅 Доступные мероприятия по курсу <b>{course.name}</b>:",
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )

    except ValueError:
        await callback.answer("❌ Ошибка: некорректный ID курса", show_alert=True)
    except Exception as e:
        print(f"Ошибка в view_course_events: {str(e)}")
        await callback.answer("⚠️ Произошла ошибка при загрузке мероприятий", show_alert=True)


@profile_router.callback_query(F.data.startswith("view_broadcast_"))
async def show_broadcast_details(callback: CallbackQuery, session: AsyncSession):
    try:
        broadcast_id = int(callback.data.split("_")[-1])

        async with session.begin():
            # Получаем рассылку с загрузкой связанных данных
            broadcast = await session.get(
                Broadcast,
                broadcast_id,
                options=[
                    selectinload(Broadcast.project),
                    selectinload(Broadcast.course_associations)
                ]
            )

            if not broadcast:
                await callback.answer("❌ Рассылка не найдена", show_alert=True)
                return

            # Получаем ID курса для кнопки "Назад"
            course_id = broadcast.course_associations[0].course_id if broadcast.course_associations else None

            # Формируем текст сообщения
            message_text = []

            # Добавляем заголовок (если есть проект)
            if broadcast.project:
                message_text.append(f"<b>Проект: {broadcast.project.title}</b>\n\n")

            # Добавляем дату создания
            message_text.append(f"Дата: {broadcast.created.strftime('%d.%m.%Y %H:%M')}\n\n")

            # Добавляем основной текст
            message_text.append(broadcast.text if broadcast.text else "Описание отсутствует")

            # Создаем клавиатуру
            builder = InlineKeyboardBuilder()

            # Кнопка "Назад к списку"
            if course_id:
                builder.row(
                    InlineKeyboardButton(
                        text="⬅️ Назад к списку",
                        callback_data=f"view_course_events_{course_id}"
                    )
                )

            # Отправляем сообщение
            await callback.message.edit_text(
                text="".join(message_text),
                parse_mode="HTML",
                reply_markup=builder.as_markup(),
                disable_web_page_preview=True
            )

    except Exception as e:
        print(f"Ошибка в show_broadcast_details: {str(e)}")
        await callback.answer("⚠️ Ошибка при загрузке рассылки", show_alert=True)


@profile_router.callback_query(F.data.startswith("view_course_events_"))
async def back_to_broadcasts_list(callback: CallbackQuery, session: AsyncSession):
    try:
        # Получаем ID курса из callback данных
        course_id = int(callback.data.split("_")[-1])

        async with session.begin():
            # Проверяем существование курса
            course = await session.get(Course, course_id)
            if not course:
                await callback.answer("❌ Курс не найден", show_alert=True)
                return

            # Получаем активные рассылки для этого курса
            stmt = (
                select(Broadcast)
                .join(Broadcast.course_associations)
                .options(selectinload(Broadcast.project))
                .where(
                    Broadcast.is_sent == True,
                    Broadcast.is_active == True,
                    BroadcastCourseAssociation.course_id == course_id
                )
                .order_by(Broadcast.created.desc())
            )

            broadcasts = (await session.scalars(stmt)).all()

            if not broadcasts:
                await callback.answer("📭 Нет доступных мероприятий", show_alert=True)
                return

            # Создаем клавиатуру с рассылками
            builder = InlineKeyboardBuilder()
            for broadcast in broadcasts:
                text_preview = broadcast.text[:40].strip() + "..." if broadcast.text and len(
                    broadcast.text) > 40 else broadcast.text or "Нет описания"
                builder.row(
                    InlineKeyboardButton(
                        text=text_preview,
                        callback_data=f"view_broadcast_{broadcast.id}"
                    )
                )

            await callback.message.edit_text(
                f"📅 Доступные мероприятия по курсу <b>{course.name}</b>:",
                parse_mode="HTML",
                reply_markup=builder.as_markup()
            )

    except Exception as e:
        print(f"Ошибка в back_to_broadcasts_list: {str(e)}")
        await callback.answer("⚠️ Ошибка при загрузке списка", show_alert=True)
