from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.fsm_states import ChangeCourseState
from app.keyboards.inline import *
from app.keyboards.reply import kb_main
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
async def show_course_broadcasts(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    try:
        course_id = int(callback.data.split("_")[-1])

        # Получаем курс
        course = await session.get(Course, course_id)
        if not course:
            await callback.answer("Курс не найден", show_alert=True)
            return

        # Получаем рассылки для курса
        stmt = (
            select(Broadcast)
            .join(Broadcast.course_associations)
            .where(
                Broadcast.is_sent == True,
                Broadcast.is_active == True,
                BroadcastCourseAssociation.course_id == course_id
            )
            .order_by(Broadcast.id.desc())
        )
        broadcasts_list = (await session.scalars(stmt)).all()

        if not broadcasts_list:
            await callback.answer("Нет доступных мероприятий для этого курса", show_alert=True)
            return

        # Отправляем первую рассылку и сохраняем сообщения
        new_messages = await send_broadcast_with_pagination(
            callback=callback,
            broadcasts=broadcasts_list,
            index=0,
            course_id=course_id,
            total=len(broadcasts_list),
            last_messages=[]  # Пустой список для первого сообщения
        )

        # Сохраняем состояние
        await state.update_data(
            last_messages=new_messages,
            current_index=0,
            broadcasts_list=broadcasts_list,
            course_id=course_id
        )

    except Exception as e:
        await callback.answer("Произошла ошибка", show_alert=True)


async def send_broadcast_with_pagination(
        callback: CallbackQuery,
        broadcasts: list[Broadcast],
        index: int,
        course_id: int,
        total: int,
        last_messages: list[int] = None
):
    """Функция пагинации для курсовых рассылок"""
    try:
        if index < 0 or index >= len(broadcasts):
            await callback.answer("Недопустимый индекс рассылки", show_alert=True)
            return

        # Удаляем предыдущие сообщения (и фото, и текст)
        if last_messages:
            for msg_id in last_messages:
                try:
                    await callback.message.bot.delete_message(
                        chat_id=callback.message.chat.id,
                        message_id=msg_id
                    )
                except Exception as e:
                    await callback.message.answer(f"Не удалось удалить сообщение {msg_id}: {e}")

        broadcast = broadcasts[index]
        pagination_text = f"<b>Мероприятие {index + 1} из {total}</b>"
        main_text = broadcast.text
        full_text = f"{main_text}\n\n{pagination_text}"

        # Создаем клавиатуру пагинации
        builder = InlineKeyboardBuilder()
        if index > 0:
            builder.button(
                text="⬅️ Назад",
                callback_data=f"prev_course_broadcast_{course_id}_{index}"
            )
        if index < total - 1:
            builder.button(
                text="➡️ Вперед",
                callback_data=f"next_course_broadcast_{course_id}_{index}"
            )

        builder.adjust(2)
        markup = builder.as_markup()

        # Список для хранения ID всех отправленных сообщений
        current_messages = []

        # Отправляем контент
        if broadcast.image_path:
            try:
                photo = FSInputFile(broadcast.image_path) if os.path.exists(
                    broadcast.image_path) else broadcast.image_path

                if len(full_text) <= 1024:
                    msg = await callback.message.bot.send_photo(
                        chat_id=callback.message.chat.id,
                        photo=photo,
                        caption=full_text,
                        reply_markup=markup,
                        parse_mode="HTML"
                    )
                    current_messages.append(msg.message_id)
                else:
                    photo_msg = await callback.message.bot.send_photo(
                        chat_id=callback.message.chat.id,
                        photo=photo
                    )
                    current_messages.append(photo_msg.message_id)

                    text_msg = await callback.message.bot.send_message(
                        chat_id=callback.message.chat.id,
                        text=full_text,
                        reply_markup=markup,
                        disable_web_page_preview=True,
                        parse_mode="HTML"
                    )
                    current_messages.append(text_msg.message_id)
            except Exception as e:
                error_msg = await callback.message.bot.send_message(
                    chat_id=callback.message.chat.id,
                    text=f"⚠️ Не удалось загрузить изображение\n\n{full_text}",
                    reply_markup=markup,
                    disable_web_page_preview=True,
                    parse_mode="HTML"
                )
                current_messages.append(error_msg.message_id)
        else:
            msg = await callback.message.bot.send_message(
                chat_id=callback.message.chat.id,
                text=full_text,
                reply_markup=markup,
                disable_web_page_preview=True,
                parse_mode="HTML"
            )
            current_messages.append(msg.message_id)

        return current_messages

    except Exception as e:
        await callback.answer("Ошибка при отображении рассылки", show_alert=True)
        return []
    finally:
        await callback.answer()


@profile_router.callback_query(F.data.startswith("prev_course_broadcast_"))
async def prev_course_broadcast(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    try:
        data = await state.get_data()
        last_messages = data.get("last_messages", [])
        current_index = data.get("current_index", 0)
        broadcasts_list = data.get("broadcasts_list", [])
        course_id = data.get("course_id")

        if not broadcasts_list:
            await callback.answer("Нет доступных рассылок", show_alert=True)
            return

        new_index = max(0, current_index - 1)

        new_messages = await send_broadcast_with_pagination(
            callback=callback,
            broadcasts=broadcasts_list,
            index=new_index,
            course_id=course_id,
            total=len(broadcasts_list),
            last_messages=last_messages
        )

        await state.update_data(
            last_messages=new_messages,
            current_index=new_index
        )

    except Exception as e:
        await callback.answer("Ошибка при загрузке", show_alert=True)


@profile_router.callback_query(F.data.startswith("next_course_broadcast_"))
async def next_course_broadcast(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    try:
        data = await state.get_data()
        last_messages = data.get("last_messages", [])
        current_index = data.get("current_index", 0)
        broadcasts_list = data.get("broadcasts_list", [])
        course_id = data.get("course_id")

        if not broadcasts_list:
            await callback.answer("Нет доступных рассылок", show_alert=True)
            return

        new_index = min(len(broadcasts_list) - 1, current_index + 1)

        new_messages = await send_broadcast_with_pagination(
            callback=callback,
            broadcasts=broadcasts_list,
            index=new_index,
            course_id=course_id,
            total=len(broadcasts_list),
            last_messages=last_messages
        )

        await state.update_data(
            last_messages=new_messages,
            current_index=new_index
        )

    except Exception as e:
        await callback.answer("Ошибка при загрузке", show_alert=True)
