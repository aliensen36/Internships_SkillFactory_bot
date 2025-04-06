import logging
from aiogram import Router, F
from aiogram.filters import StateFilter, Filter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.filters.chat_types import ChatTypeFilter, IsAdmin
from app.fsm_states import *
from app.keyboards.inline import admin_specializations_menu, confirm_cancel_add_specializations, \
    confirm_cancel_edit_specializations, admin_main_menu, confirm_delete_specializations
from app.keyboards.reply import kb_specializations_courses, kb_courses, specializations_keyboard
from database.models import *

admin_specialization_router = Router()
admin_specialization_router.message.filter(ChatTypeFilter(["private"]), IsAdmin())


# Обработчик кнопки "Специализации"
@admin_specialization_router.callback_query(F.data == "admin_specializations")
async def specializations(callback: CallbackQuery):
    try:
        # Удаляем инлайн-клавиатуру с предыдущего сообщения
        await callback.message.edit_reply_markup(reply_markup=None)

        # Отправляем новое меню специализаций
        await callback.message.answer(
            text="<b>🏗️ Управление специализациями</b>\n\nВыбери действие:",
            reply_markup=await admin_specializations_menu(),
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        # logger.error(f"Ошибка в handle_projects_button: {e}")
        await callback.answer("⚠️ Ошибка при загрузке меню", show_alert=True)


@admin_specialization_router.callback_query(F.data == "specializations:list")
async def view_specializations(callback: CallbackQuery,
                        session: AsyncSession):
    try:
        result = await session.execute(select(Specialization))
        specializations = result.scalars().all()

        if not specializations:
            await callback.message.answer("📭 Список специализаций пуст")
            return

        specializations_list = "\n".join(
            f"{specialization.name}\n"
            for specialization in specializations
        )

        await callback.message.answer(
            f"<b>Список специализаций</b>:\n\n{specializations_list}\n\n",
            reply_markup=await admin_specializations_menu(),
            parse_mode="HTML"
        )

        await callback.answer()

    except Exception as e:
        await callback.message.answer("⚠️ Произошла ошибка при загрузке специализаций")
        logging.error(f"Error in view_specializations: {e}")



# =====================================================================================
# ------------------------------ Добавить специализацию -------------------------------
# =====================================================================================



@admin_specialization_router.callback_query(F.data == "specializations:add")
async def add_specialization_start(callback: CallbackQuery,
                                   state: FSMContext):
    await state.set_state(SpecializationAddState.waiting_for_name)
    await callback.message.answer("Введи название специализации:")
    await callback.answer()


@admin_specialization_router.message(SpecializationAddState.waiting_for_name)
async def add_specialization_name(message: Message,
                                  state: FSMContext,
                                  session: AsyncSession):
    specialization_name = message.text.strip()

    # Проверяем существование специализации с таким названием
    existing_specialization = await session.execute(
        select(Specialization).where(Specialization.name.ilike(specialization_name)))
    existing_specialization = existing_specialization.scalar_one_or_none()

    if existing_specialization:
    # Если специализация с таким названием уже существует
        await message.answer(
            f"⚠️ Специализация с названием '{specialization_name}' уже существует.\n"
            "Пожалуйста, введите другое название:"
        )
        # Остаемся в том же состоянии для повторного ввода
        return

    # Если название уникальное - продолжаем
    data = await state.update_data(name=message.text)

    # Формируем сообщение с предпросмотром данных
    preview_message = (
        f"📋 Новая специализация: <b>{data['name']}</b>\n\n"
        "Подтвердите добавление или отмените:"
    )

    await message.answer(preview_message,
                         reply_markup=await confirm_cancel_add_specializations(),
                         parse_mode="HTML")
    await state.set_state(SpecializationAddState.waiting_for_confirmation)


@admin_specialization_router.callback_query(
    SpecializationAddState.waiting_for_confirmation,
    F.data == "confirm_add_specialization")
async def confirm_ass_specialization(callback: CallbackQuery,
                                     state: FSMContext,
                                     session: AsyncSession):
    data = await state.get_data()

    new_specialization = Specialization(
        name=data["name"]
    )

    session.add(new_specialization)
    await session.commit()

    await callback.message.answer("✅ Новая специализация добавлена!",
                         reply_markup=await admin_specializations_menu())
    await callback.answer()
    await state.clear()


@admin_specialization_router.callback_query(F.data == "cancel_add_specialization")
async def cancel_add_specialization(callback: CallbackQuery,
                                    state: FSMContext):
    await callback.message.answer("❌ Добавление специализации отменено.",
                                  reply_markup=await admin_specializations_menu())
    await callback.answer()
    await state.clear()



# =====================================================================================
# -------------------------------- Изменить специализацию -----------------------------
# =====================================================================================



@admin_specialization_router.callback_query(F.data == "specializations:edit")
async def edit_specialization(callback: CallbackQuery,
                              state: FSMContext,
                              session: AsyncSession):
    await state.set_state(SpecializationEditState.waiting_for_specialization_selection)
    try:
        await callback.message.answer("Изменение специализации")
        await callback.answer()

        result = await session.execute(select(Specialization))
        specializations = result.scalars().all()

        if not specializations:
            await callback.message.answer("📭 Список специализаций пуст")
            return

        # Создаем клавиатуру
        builder = InlineKeyboardBuilder()

        # Добавляем кнопки для каждого проекта
        for specialization in specializations:
            builder.button(
                text=f"{specialization.name}",
                callback_data=f"edit_specialization_{specialization.id}"
            )

        # Форматируем кнопки
        builder.adjust(1, repeat=True)

        await callback.message.answer(
            "<b>Выбери специализацию для редактирования</b>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )

    except Exception as e:
        await callback.message.answer("⚠️ Произошла ошибка при загрузке специализаций")
        logging.error(f"Error in view_specializations: {e}")


# Обработчик выбора проекта для редактирования
@admin_specialization_router.callback_query(
    SpecializationEditState.waiting_for_specialization_selection,
    F.data.startswith("edit_specialization_"))
async def select_specialization_to_edit(callback: CallbackQuery,
                                        state: FSMContext,
                                        session: AsyncSession):
    try:
        specialization_id = int(callback.data.split("_")[-1])
        specialization = await session.get(Specialization, specialization_id)

        if not specialization:
            await callback.message.answer("⚠️ Специализация не найдена",
                                          show_alert=True)
            return

        await state.update_data(
            specialization_id=specialization_id,
            current_name=specialization.name
        )

        await callback.message.edit_text(
            f"Редактирование специализации:  <b>{specialization.name}</b>\n\n"
            f"Введите новое название специализации:",
            parse_mode="HTML"
        )

        await callback.answer()
        await state.set_state(SpecializationEditState.waiting_for_name)

    except Exception as e:
        logging.error(f"Error in select_specialization_to_edit: {e}", exc_info=True)
        await callback.answer("Произошла ошибка при обработке запроса",
                              show_alert=True)
        await session.rollback()


# Обработчик ввода нового названия
@admin_specialization_router.message(SpecializationEditState.waiting_for_name)
async def process_new_name(message: Message,
                           state: FSMContext):
    await state.update_data(new_name=message.text)
    await message.answer("Подтверди изменения или отмени:",
                         reply_markup=await confirm_cancel_edit_specializations())
    await state.set_state(SpecializationEditState.waiting_for_confirmation)


# Обработчик подтверждения изменений
@admin_specialization_router.callback_query(
    SpecializationEditState.waiting_for_confirmation,
    F.data == "confirm_edit_specialization")
async def confirm_edit_specialization(callback: CallbackQuery,
                                      state: FSMContext,
                                      session: AsyncSession):
    data = await state.get_data()

    if 'specialization_id' not in data:
        await callback.message.answer("❌ Ошибка: специализация не выбрана. Начните заново.")
        await state.clear()
        return

    specialization = await session.get(Specialization, data['specialization_id'])
    if not specialization:
        await callback.message.answer("⚠️ Специализация не найдена")
        await state.clear()
        return

    # Применяем изменения
    if 'new_name' in data:
        specialization.name = data['new_name']

    await session.commit()

    await callback.message.answer(
        f"Специализация <b>{specialization.name}</b> успешно изменена",
        parse_mode="HTML",
        reply_markup=await admin_specializations_menu()
    )
    await callback.answer()
    await state.clear()


# Обработчик отмены изменений
@admin_specialization_router.callback_query(F.data == "cancel_edit_specialization")
async def cancel_edit_specialization(callback: CallbackQuery,
                                     state: FSMContext,
                                     session: AsyncSession):
    await callback.message.answer("Изменение специализации отменено.",
                                  reply_markup=await admin_specializations_menu())
    await callback.answer()
    await state.clear()




# =====================================================================================
# --------------------------------- Удалить специализацию -----------------------------
# =====================================================================================



@admin_specialization_router.callback_query(F.data == "specializations:delete")
async def delete_specialization_start(callback: CallbackQuery,
                                      state: FSMContext,
                                      session: AsyncSession):
    try:
        result = await session.execute(select(Specialization))
        specializations = result.scalars().all()

        if not specializations:
            await callback.message.answer("📭 Список специализаций пуст")
            return

        # Создаем клавиатуру
        builder = InlineKeyboardBuilder()

        # Добавляем кнопки для каждого проекта
        for specialization in specializations:
            builder.button(
                text=f"{specialization.name}",
                callback_data=f"delete_specialization_{specialization.id}"
            )

        # Форматируем кнопки
        builder.adjust(1, repeat=True)

        await callback.message.answer(
            "📂 <b>Выбери специализацию для удаления</b>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        await callback.answer()

    except Exception as e:
        await callback.message.answer("⚠️ Произошла ошибка при загрузке специализаций")
        logging.error(f"Error in view_specializations: {e}")
        await callback.answer()

    await state.set_state(SpecializationDeleteState.waiting_for_delete)


@admin_specialization_router.callback_query(
    SpecializationDeleteState.waiting_for_delete,
    F.data.startswith("delete_specialization_"))
async def select_specialization_to_delete(callback: CallbackQuery,
                                          state: FSMContext,
                                          session: AsyncSession):
    specialization_id = int(callback.data.split("_")[-1])
    specialization = await session.get(Specialization, specialization_id)

    if not specialization:
        await callback.answer("Специализация не найдена", show_alert=True)
        return

    await state.update_data(specialization_id=specialization_id,
                            specialization_name=specialization.name)
    await state.set_state(SpecializationDeleteState.waiting_for_confirmation)

    await callback.message.answer(
        f"⚠️ Удалить специализацию  <b>{specialization.name}</b>?",
        parse_mode="HTML",
        reply_markup=await confirm_delete_specializations()
    )
    await callback.answer()


@admin_specialization_router.callback_query(
                              SpecializationDeleteState.waiting_for_confirmation,
                              F.data == "delete_specializations:confirm")
async def confirm_delete_specialization(callback: CallbackQuery,
                                        state: FSMContext,
                                        session: AsyncSession):
    data = await state.get_data()
    specialization = await session.get(Specialization, data['specialization_id'])

    if specialization:
        await session.delete(specialization)
        await session.commit()
        await callback.message.answer(
            f"🗑️ Специализация <b>{data['specialization_name']}</b> успешно удалена!",
            parse_mode="HTML",
            reply_markup=await admin_specializations_menu()
        )
        await callback.answer()
    else:
        await callback.message.answer(
            "⚠️ Специализация не найдена или уже была удалена",
            reply_markup=await admin_specializations_menu()
        )
        await callback.answer()

    await state.clear()


@admin_specialization_router.callback_query(
    SpecializationDeleteState.waiting_for_confirmation,
    F.data == "delete_specializations:cancel")
async def cancel_delete_specialization(callback: CallbackQuery,
                                       state: FSMContext):
    data = await state.get_data()
    await callback.message.answer(
        f"❌ Удаление специализации <b>{data.get('specialization_name', '')}</b> отменено",
        parse_mode="HTML",
        reply_markup=await admin_specializations_menu()
    )
    await callback.answer()
    await state.clear()



# =====================================================================================
# ---------------------------------------- Назад -------------------------------------
# =====================================================================================



@admin_specialization_router.callback_query(F.data == "specializations:admin_main_menu")
async def back_to_main_menu(callback: CallbackQuery):
    await callback.message.answer("Возврат в главное админ-меню",
                                  reply_markup=await admin_main_menu())
    await callback.answer()
