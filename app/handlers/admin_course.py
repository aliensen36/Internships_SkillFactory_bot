import logging
from aiogram import Router, F
from aiogram.filters import StateFilter, Filter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.filters.chat_types import ChatTypeFilter, IsAdmin
from app.fsm_states import *
from app.keyboards.inline import admin_courses_menu, confirm_cancel_add_courses, confirm_cancel_edit_courses, \
    admin_main_menu, confirm_delete_courses
from database.models import *
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from io import BytesIO
import pandas as pd
from aiogram.types import FSInputFile
from sqlalchemy.orm import selectinload
import tempfile
import os
from aiogram.types import BufferedInputFile





admin_course_router = Router()
admin_course_router.message.filter(ChatTypeFilter(["private"]), IsAdmin())


# Обработчик кнопки "Курсы"
@admin_course_router.callback_query(F.data == "admin_courses")
async def courses(callback: CallbackQuery):
    try:
        # Удаляем инлайн-клавиатуру с предыдущего сообщения
        await callback.message.edit_reply_markup(reply_markup=None)

        # Отправляем новое меню курсов
        await callback.message.answer(
            text="<b>🏗️ Управление курсами</b>\n\nВыбери действие:",
            reply_markup=await admin_courses_menu(),
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        await callback.answer("⚠️ Ошибка при загрузке меню", show_alert=True)


@admin_course_router.callback_query(F.data == "courses:list")
async def view_courses(callback: CallbackQuery,
                       session: AsyncSession):
    try:
        result = await (session
                        .execute(select(Specialization)
                                 .options(selectinload(Specialization.courses)))
                        )
        specializations = result.scalars().all()

        if not specializations:
            await callback.message.answer("❗ Пока нет ни одной специализации и курсов.")
            return

        text = "<b>Список курсов</b>:\n\n"

        for spec in specializations:
            text += f"🔸 <b>{spec.name}</b>:\n"
            if spec.courses:
                for course in spec.courses:
                    text += f"  • {course.name}\n"
            else:
                text += "  (курсов пока нет)\n"
            text += "\n"

        await callback.message.answer(text,
                                      reply_markup=await admin_courses_menu(),
                                      parse_mode="HTML")

        await callback.answer()

    except Exception as e:
        await callback.message.answer("⚠️ Произошла ошибка при загрузке курсов")
        logging.error(f"Error in view_courses: {e}")


# Обработчик выгрузки в Excel
@admin_course_router.callback_query(F.data == "courses:export")
async def export_courses_to_excel(callback: CallbackQuery, session: AsyncSession):
    try:
        await callback.answer("⏳ Формируем файл...")

        # Получаем данные из БД
        result = await session.execute(
            select(Course)
            .options(selectinload(Course.specialization))
            .order_by(Course.specialization_id, Course.id)
        )
        courses = result.scalars().all()

        if not courses:
            await callback.message.answer("❗ Нет курсов для выгрузки")
            return

        # Подготавливаем данные для Excel
        data = []
        for course in courses:
            data.append({
                "ID": course.id,
                "Название курса": course.name,
                "Специализация": course.specialization.name if course.specialization else "Не указана",
                "ID специализации": course.specialization_id
            })

        # Создаем DataFrame
        df = pd.DataFrame(data)

        # Создаем временный файл
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            with pd.ExcelWriter(tmp.name, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Курсы')

                # Настраиваем форматирование
                worksheet = writer.sheets['Курсы']
                for idx, col in enumerate(df.columns):
                    max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                    worksheet.set_column(idx, idx, max_len)

            # Читаем файл обратно в память
            tmp.seek(0)
            excel_data = tmp.read()

        # Создаем BufferedInputFile
        excel_file = BufferedInputFile(excel_data, filename="courses_export.xlsx")

        # Отправляем файл пользователю
        await callback.message.answer_document(
            document=excel_file,
            caption=f"📊 Выгрузка курсов ({len(courses)} записей)"
        )

    except Exception as e:
        logging.error(f"Ошибка при выгрузке курсов в Excel: {e}", exc_info=True)
        await callback.message.answer("⚠️ Произошла ошибка при формировании файла")
    finally:
        # Удаляем временный файл
        if 'tmp' in locals() and os.path.exists(tmp.name):
            os.unlink(tmp.name)
        await callback.answer()


# =====================================================================================
# ----------------------------------- Добавить курс -----------------------------------
# =====================================================================================



@admin_course_router.callback_query(F.data == "courses:add")
async def add_course_start(callback: CallbackQuery,
                           state: FSMContext,
                           session: AsyncSession,):
    result = await session.execute(select(Specialization))
    specializations = result.scalars().all()

    if not specializations:
        await callback.message.answer("❗ Нет доступных специализаций. "
                                      "Сначала добавь хотя бы одну.")
        return

    # Формируем инлайн-кнопки
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=spec.name,
                callback_data=f"select_spec_{spec.id}")
            ]
            for spec in specializations
        ])


    await state.set_state(CourseAddState.waiting_for_specialization)
    await callback.message.answer("Выбери специализацию, к которой относится курс:", reply_markup=kb)
    await callback.answer()


@admin_course_router.callback_query(CourseAddState.waiting_for_specialization,
                                    F.data.startswith("select_spec_"))
async def select_specialization(callback: CallbackQuery,
                                  state: FSMContext,
                                  session: AsyncSession):
    spec_id = int(callback.data.split("_")[-1])
    await state.update_data(specialization_id=spec_id)

    await state.set_state(CourseAddState.waiting_for_name)
    await callback.message.answer("Введи название нового курса:")
    await callback.answer()


@admin_course_router.message(CourseAddState.waiting_for_name)
async def enter_course_name(message: Message,
                            state: FSMContext,
                            session: AsyncSession):
    if not message.text:
        await message.answer("Пожалуйста, введи название курса текстом.")
        return

    course_name = message.text.strip()
    data = await state.get_data()
    spec_id = data['specialization_id']

    # Проверяем, существует ли уже курс с таким названием в этой специализации
    existing_course = await session.execute(
        select(Course)
        .where(
            and_(
                Course.name.ilike(course_name),
                Course.specialization_id == spec_id
            )
        )
    )
    existing_course = existing_course.scalar_one_or_none()

    if existing_course:
        await message.answer(
            f"❌ Курс с названием <b>'{course_name}'</b> уже существует "
            f"в выбранной специализации.\n\n"
            f"Пожалуйста, введи другое название.",
            parse_mode="HTML"
        )
        return

    await state.update_data(course_name=course_name)

    # Получаем информацию о специализации
    result = await session.execute(
        select(Specialization)
        .where(Specialization.id == spec_id)
    )
    specialization = result.scalar_one_or_none()

    if not specialization:
        await message.answer("Ошибка: специализация не найдена.")
        await state.clear()
        return

    await state.set_state(CourseAddState.waiting_for_confirmation)

    await message.answer(
        f"<b>Добавление нового курса</b>\n\n"
        f"Специализация: <b>{specialization.name}</b>\n\n"
        f"Название курса: <b>{course_name}</b>\n\n"
        f"Подтверди или отмени.",
        parse_mode="HTML",
        reply_markup=await confirm_cancel_add_courses()
    )


@admin_course_router.callback_query(CourseAddState.waiting_for_confirmation,
                                    F.data == "confirm_add_course")
async def confirm_add_course(callback: CallbackQuery,
                             state: FSMContext,
                             session: AsyncSession):
    data = await state.get_data()
    spec_id = data['specialization_id']
    course_name = data['course_name']

    # Получаем информацию о специализации для сообщения об успешном добавлении
    result = await session.execute(select(Specialization).where(Specialization.id == spec_id))
    specialization = result.scalar_one_or_none()

    try:
        new_course = Course(
            name=course_name,
            specialization_id=spec_id
        )
        session.add(new_course)
        await session.commit()

        await callback.message.answer(
            f"✅ Курс успешно добавлен!\n\n"
            f"Специализация: <b>{specialization.name}</b>\n\n"
            f"Название курса: <b>{course_name}</b>",
            parse_mode="HTML",
            reply_markup=await admin_courses_menu()
        )

    except IntegrityError as e:
        await session.rollback()

        if "courses_pkey" in str(e):
            # Автоматически исправляем последовательность
            try:
                reset_query = text(
                    "SELECT setval('courses_id_seq', "
                    "(SELECT MAX(id) FROM courses))"
                )
                await session.execute(reset_query)
                await session.commit()
                await callback.message.answer(
                    "⚠️ Проблема с нумерацией курсов исправлена. Попробуйте добавить курс снова.",
                    reply_markup=await admin_courses_menu()
                )
            except Exception as reset_error:
                logging.error(f"Ошибка сброса последовательности: {reset_error}")
                await callback.message.answer(
                    "⚠️ Критическая ошибка. Обратитесь к администратору.",
                    reply_markup=await admin_courses_menu()
                )

        elif "unique constraint" in str(e).lower():
            await callback.message.answer(
                "⚠️ Курс с таким названием уже существует",
                reply_markup=await admin_courses_menu()
            )

    except Exception as e:
        await session.rollback()
        logging.error(f"Ошибка добавления курса: {e}", exc_info=True)
        await callback.message.answer(
            "⚠️ Неизвестная ошибка при добавлении курса",
            reply_markup=await admin_courses_menu()
        )

    finally:
        await callback.answer()
        await state.clear()


@admin_course_router.callback_query(F.data == "cancel_add_course")
async def cancel_add_course(callback: CallbackQuery,
                            state: FSMContext):
    await callback.message.answer("❌ Добавление курса отменено.",
                                  reply_markup=await admin_courses_menu())
    await callback.answer()
    await state.clear()




# =====================================================================================
# ------------------------------------- Изменить курс ---------------------------------
# =====================================================================================



@admin_course_router.callback_query(F.data == "courses:edit")
async def edit_courses(callback: CallbackQuery,
                       state: FSMContext,
                       session: AsyncSession):
    await state.set_state(CourseEditState.waiting_for_specialization_selection)
    try:
        await callback.message.answer("Изменение курса")
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
            "<b>Выбери специализацию, к которой относится курс</b>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )

    except Exception as e:
        await callback.message.answer("⚠️ Произошла ошибка при загрузке специализаций")
        logging.error(f"Error in view_specializations: {e}")


@admin_course_router.callback_query(F.data.startswith("edit_specialization_"),
                                    CourseEditState.waiting_for_specialization_selection)
async def select_course_from_specialization(callback: CallbackQuery,
                                            state: FSMContext,
                                            session: AsyncSession):
    try:
        spec_id = int(callback.data.split("_")[-1])
        await state.update_data(specialization_id=spec_id)

        # Получаем курсы для выбранной специализации
        result = await session.execute(
            select(Course)
            .where(Course.specialization_id == spec_id)
            .order_by(Course.name)
        )
        courses = result.scalars().all()

        if not courses:
            await callback.answer("ℹ️ В этой специализации нет курсов",
                                  show_alert=True)
            return

        # Создаем клавиатуру с курсами
        builder = InlineKeyboardBuilder()

        for course in courses:
            builder.button(
                text=f"{course.name}",
                callback_data=f"select_course_{course.id}"
            )

        # Добавляем кнопку "Назад"
        builder.button(
            text="Назад",
            callback_data="back_to_specializations"
        )

        builder.adjust(1, repeat=True)

        await state.set_state(CourseEditState.waiting_for_course_selection)
        await callback.message.edit_text(
            "<b>Выбери курс для редактирования:</b>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        await callback.answer()

    except Exception as e:
        logging.error(f"Error in select_course_from_specialization: {e}")
        await callback.message.answer("⚠️ Произошла ошибка при загрузке курсов")
        await callback.answer()


@admin_course_router.callback_query(F.data == "back_to_specializations",
                                    CourseEditState.waiting_for_course_selection)
async def back_to_specializations(callback: CallbackQuery,
                                  state: FSMContext,
                                  session: AsyncSession):
    # Возвращаемся к выбору специализации
    result = await session.execute(select(Specialization))
    specializations = result.scalars().all()

    builder = InlineKeyboardBuilder()
    for specialization in specializations:
        builder.button(
            text=f"{specialization.name}",
            callback_data=f"edit_specialization_{specialization.id}"
        )
    builder.adjust(1, repeat=True)

    await state.set_state(CourseEditState.waiting_for_specialization_selection)
    await callback.message.edit_text(
        "<b>Выбери специализацию, к которой относится курс</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@admin_course_router.callback_query(F.data.startswith("select_course_"),
                                    CourseEditState.waiting_for_course_selection)
async def select_course_action(callback: CallbackQuery,
                               state: FSMContext,
                               session: AsyncSession):
    try:
        course_id = int(callback.data.split("_")[-1])
        await state.update_data(course_id=course_id)

        # Получаем информацию о курсе
        result = await session.execute(
            select(Course)
            .where(Course.id == course_id)
        )
        course = result.scalar_one()

        # Создаем клавиатуру действий
        builder = InlineKeyboardBuilder()

        builder.button(
            text="Изменить название курса",
            callback_data="edit_course_name"
        )
        builder.button(
            text="Назад",
            callback_data="back_to_courses"
        )

        builder.adjust(1, repeat=True)

        await state.set_state(CourseEditState.waiting_for_name)
        await callback.message.edit_text(
            f"Изменение курса <b>'{course.name}'</b>\n\n"
            "<b>Введи новое название:</b>",
            parse_mode="HTML"
        )
        await callback.answer()

    except Exception as e:
        logging.error(f"Error in select_course_action: {e}")
        await callback.message.answer("⚠️ Произошла ошибка при загрузке данных курса")
        await callback.answer()


# Обработчик ввода нового названия
@admin_course_router.message(CourseEditState.waiting_for_name)
async def process_new_name(message: Message,
                           state: FSMContext):
    await state.update_data(new_name=message.text)
    await message.answer("Подтверди изменения или отмени:",
                         reply_markup=await confirm_cancel_edit_courses())
    await state.set_state(CourseEditState.waiting_for_confirmation)


# Обработчик подтверждения изменений
@admin_course_router.callback_query(
    CourseEditState.waiting_for_confirmation,
    F.data == "confirm_edit_course")
async def confirm_edit_course(callback: CallbackQuery,
                              state: FSMContext,
                              session: AsyncSession):
    data = await state.get_data()

    if 'course_id' not in data:
        await callback.message.answer("❌ Ошибка: курс не выбран. Начните заново.")
        await state.clear()
        return

    course = await session.get(Course, data['course_id'])
    if not course:
        await callback.message.answer("⚠️ Курс не найден")
        await state.clear()
        return

    # Применяем изменения
    if 'new_name' in data:
        course.name = data['new_name']

    await session.commit()

    await callback.message.answer(
        f"Курс <b>{course.name}</b> успешно изменен",
        parse_mode="HTML",
        reply_markup=await admin_courses_menu()
    )
    await callback.answer()
    await state.clear()


# Обработчик отмены изменений
@admin_course_router.callback_query(F.data == "cancel_edit_course")
async def cancel_edit_course(callback: CallbackQuery,
                             state: FSMContext,
                             session: AsyncSession):
    await callback.message.answer("Изменение курса отменено.",
                                  reply_markup=await admin_courses_menu())
    await callback.answer()
    await state.clear()





# =====================================================================================
# --------------------------------------- Удалить курс --------------------------------
# =====================================================================================



@admin_course_router.callback_query(F.data == "courses:delete")
async def delete_course_start(callback: CallbackQuery,
                             state: FSMContext,
                             session: AsyncSession):
    try:
        result = await session.execute(select(Specialization))
        specializations = result.scalars().all()

        if not specializations:
            await callback.message.answer("📭 Список специализаций пуст")
            return

        builder = InlineKeyboardBuilder()
        for specialization in specializations:
            builder.button(
                text=specialization.name,
                callback_data=f"delete_spec_{specialization.id}"
            )
        builder.adjust(1)

        await state.set_state(CourseDeleteState.waiting_for_specialization)
        await callback.message.answer(
            "<b>Выбери специализацию:</b>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        await callback.answer()

    except Exception as e:
        await callback.message.answer("⚠️ Ошибка при загрузке специализаций")
        logging.error(f"Error in delete_course_start: {e}")

@admin_course_router.callback_query(F.data.startswith("delete_spec_"),
                                   CourseDeleteState.waiting_for_specialization)
async def select_specialization(callback: CallbackQuery,
                               state: FSMContext,
                               session: AsyncSession):
    spec_id = int(callback.data.split("_")[-1])
    await state.update_data(spec_id=spec_id)

    result = await session.execute(
        select(Course)
        .where(Course.specialization_id == spec_id)
        .order_by(Course.name)
    )
    courses = result.scalars().all()

    if not courses:
        await callback.answer("ℹ️ В этой специализации нет курсов", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for course in courses:
        builder.button(
            text=course.name,
            callback_data=f"delete_course_{course.id}"
        )
    builder.adjust(1)

    await state.set_state(CourseDeleteState.waiting_for_course)
    await callback.message.edit_text(
        "<b>Выбери курс для удаления:</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()

@admin_course_router.callback_query(F.data == "delete_back_to_specs",
                                   CourseDeleteState.waiting_for_course)
async def back_to_specializations(callback: CallbackQuery,
                                 state: FSMContext,
                                 session: AsyncSession):
    result = await session.execute(select(Specialization))
    specializations = result.scalars().all()

    builder = InlineKeyboardBuilder()
    for specialization in specializations:
        builder.button(
            text=specialization.name,
            callback_data=f"delete_spec_{specialization.id}"
        )
    builder.adjust(1)

    await state.set_state(CourseDeleteState.waiting_for_specialization)
    await callback.message.edit_text(
        "<b>Выбери специализацию:</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()

@admin_course_router.callback_query(F.data.startswith("delete_course_"),
                                   CourseDeleteState.waiting_for_course)
async def confirm_course_delete(callback: CallbackQuery,
                               state: FSMContext,
                               session: AsyncSession):
    course_id = int(callback.data.split("_")[-1])
    await state.update_data(course_id=course_id)

    result = await session.execute(
        select(Course)
        .where(Course.id == course_id)
    )
    course = result.scalar_one()

    await state.set_state(CourseDeleteState.waiting_for_confirmation)
    await callback.message.edit_text(
        f"<b>Подтверди удаление курса:</b>\n\n"
        f"Специализация: <b>{course.specialization.name}</b>\n"
        f"Курс: <b>{course.name}</b>\n\n",
        reply_markup=await confirm_delete_courses(),
        parse_mode="HTML"
    )
    await callback.answer()

@admin_course_router.callback_query(F.data == "delete_сourses:cancel",
                                   StateFilter(CourseDeleteState))
async def cancel_deletion(callback: CallbackQuery,
                         state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Удаление курса отменено")
    await callback.message.answer(
        "Выбери действие:",
        reply_markup=await admin_courses_menu()
    )
    await callback.answer()

@admin_course_router.callback_query(F.data == "delete_сourses:confirm",
                                   CourseDeleteState.waiting_for_confirmation)
async def process_course_deletion(callback: CallbackQuery,
                                 state: FSMContext,
                                 session: AsyncSession):
    data = await state.get_data()
    course_id = data['course_id']

    try:
        result = await session.execute(
            select(Course)
            .where(Course.id == course_id)
        )
        course = result.scalar_one()

        await session.delete(course)
        await session.commit()

        await callback.message.edit_text(
            f"✅ Курс <b>{course.name}</b> успешно удален",
            parse_mode="HTML"
        )
        await callback.message.answer(
            "Выбери действие:",
            reply_markup=await admin_courses_menu()
        )
    except Exception as e:
        await callback.message.answer(
            "⚠️ Ошибка при удалении курса",
            reply_markup=await admin_courses_menu()
        )
        logging.error(f"Error in process_course_deletion: {e}")
    finally:
        await state.clear()
        await callback.answer()




# =====================================================================================
# ---------------------------------------- Назад -------------------------------------
# =====================================================================================



@admin_course_router.callback_query(F.data == "courses:admin_main_menu")
async def back_to_main_menu(callback: CallbackQuery):
    await callback.message.answer("Возврат в главное админ-меню",
                                  reply_markup=await admin_main_menu())
    await callback.answer()

