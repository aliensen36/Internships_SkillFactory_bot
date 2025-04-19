import io
import logging
from aiogram import F, Router
from aiogram.filters import Filter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload
from app.filters.chat_types import ChatTypeFilter, IsAdmin
from app.fsm_states import ProjectAddState, ProjectEditState, ProjectDeleteState
from app.handlers.admin import hide_urls, extract_urls
from app.keyboards.inline import admin_projects_menu, confirm_delete_keyboard, admin_main_menu, \
    confirm_cancel_add_projects, confirm_cancel_edit_projects
from app.keyboards.reply import kb_admin_main
from database.models import Project
import pandas as pd


admin_project_router = Router()
admin_project_router.message.filter(ChatTypeFilter(["private"]), IsAdmin())


# Хендлер для кнопки "Проекты"
@admin_project_router.callback_query(F.data == "admin_projects")
async def show_projects_menu(callback: CallbackQuery,):
    try:
        # Удаляем инлайн-клавиатуру с предыдущего сообщения
        await callback.message.edit_reply_markup(reply_markup=None)

        # Отправляем новое меню проектов
        await callback.message.answer(
            text="<b>🏗️ Управление проектами</b>\n\nВыберите действие:",
            reply_markup=await admin_projects_menu(),
            parse_mode="HTML"
        )
        await callback.answer()
    except Exception as e:
        # logger.error(f"Ошибка в handle_projects_button: {e}")
        await callback.answer("⚠️ Ошибка при загрузке меню", show_alert=True)


# Хендлер для кнопки "Список"
@admin_project_router.callback_query(F.data == "projects:list")
async def view_projects(callback: CallbackQuery,
                        session: AsyncSession):
    try:
        result = await session.execute(select(Project))
        projects = result.scalars().all()

        if not projects:
            await callback.message.answer("📭 Список проектов пуст")
            return

        projects_list = "\n".join(
            f"{project.title}\n"
            for project in projects
        )

        await callback.message.answer(
            f"<b>Список проектов</b>:\n\n{projects_list}\n\n",
            reply_markup=await admin_projects_menu(),
            parse_mode="HTML"
        )

        # Подтверждаем обработку callback (убираем "часики" в интерфейсе)
        await callback.answer()

    except Exception as e:
        await callback.message.answer("⚠️ Произошла ошибка при загрузке проектов")
        logging.error(f"Error in view_projects: {e}")


# Хендлер для кнопки "Выгрузить в Excel"
@admin_project_router.callback_query(F.data == "projects:export")
async def export_projects_to_excel(callback: CallbackQuery, session: AsyncSession):
    try:
        # Получаем все проекты из базы данных
        result = await session.execute(select(Project))
        projects = result.scalars().all()

        if not projects:
            await callback.answer("📭 Список проектов пуст", show_alert=True)
            return

        # Создаем DataFrame с нужными полями
        data = {
            "Название": [],
            "Описание": [],
            "Бенефиты": [],
            "Примеры": []
        }

        for project in projects:
            data["Название"].append(project.title)
            data["Описание"].append(
                project.raw_description if hasattr(project, 'raw_description') else project.description)
            data["Бенефиты"].append(project.raw_benefit if hasattr(project, 'raw_benefit') else project.benefit)
            data["Примеры"].append(project.raw_example if hasattr(project, 'raw_example') else project.example)

        df = pd.DataFrame(data)

        # Создаем excel файл в памяти
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Проекты')
            workbook = writer.book
            worksheet = writer.sheets['Проекты']

            # Формат с переносом текста и выравниванием по верхнему левому краю
            wrap_format = workbook.add_format({
                'text_wrap': True,
                'valign': 'top',    # Вертикальное выравнивание по верху
                'align': 'left'      # Горизонтальное выравнивание по левому краю
            })

            # Формат для заголовков (жирный + выравнивание)
            header_format = workbook.add_format({
                'bold': True,
                'valign': 'top',
                'align': 'left',
                'text_wrap': True
            })

            # Устанавливаем ширину столбцов (в символах)
            column_widths = {
                "Название": 30,
                "Описание": 50,
                "Бенефиты": 50,
                "Примеры": 50
            }

            # Применяем настройки к каждому столбцу
            for i, column in enumerate(df.columns):
                worksheet.set_column(
                    i, i,
                    column_widths.get(column, 30),
                    wrap_format
                )

            # Устанавливаем формат заголовков
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)

            # Автоподбор высоты строк для данных
            for row_num in range(1, len(df) + 1):
                worksheet.set_row(row_num, None, wrap_format)

        output.seek(0)

        # Отправляем файл пользователю
        await callback.message.answer_document(
            document=BufferedInputFile(output.read(), filename="projects_export.xlsx"),
            caption="📊 Выгрузка проектов в Excel"
        )
        await callback.answer()

    except Exception as e:
        logging.error(f"Error in export_projects_to_excel: {e}")
        await callback.answer("⚠️ Ошибка при выгрузке проектов", show_alert=True)



# =====================================================================================
# ------------------------------------ Добавить проект --------------------------------
# =====================================================================================



@admin_project_router.callback_query(F.data == "projects:add")
async def add_project_start(callback: CallbackQuery,
                           state: FSMContext):
    await state.set_state(ProjectAddState.waiting_for_title)
    await callback.message.answer("Введите название проекта:")
    await callback.answer()

@admin_project_router.message(ProjectAddState.waiting_for_title)
async def add_project_title(message: Message,
                            state: FSMContext,
                            session: AsyncSession):
    project_title = message.text.strip()

    # Проверяем существование проекта с таким названием
    existing_project = await session.execute(
        select(Project).where(Project.title.ilike(project_title)))
    existing_project = existing_project.scalar_one_or_none()

    if existing_project:
    # Проект с таким названием уже существует
        await message.answer(
            f"⚠️ Проект с названием '{project_title}' уже существует.\n"
            "Пожалуйста, введите другое название:"
        )
        # Остаемся в том же состоянии для повторного ввода
        return

    # Если название уникальное - продолжаем
    await state.update_data(title=message.text)
    await state.set_state(ProjectAddState.waiting_for_description)
    await message.answer("Введите описание проекта:")


@admin_project_router.message(ProjectAddState.waiting_for_description)
async def add_project_description(message: Message,
                                  state: FSMContext,
                                  session: AsyncSession):
    await state.update_data(description=message.text)
    await state.set_state(ProjectAddState.waiting_for_benefit)
    await message.answer("Введите описание бенефитов от участия в проекте:")


@admin_project_router.message(ProjectAddState.waiting_for_benefit)
async def add_project_benefit(message: Message,
                              state: FSMContext,
                              session: AsyncSession):
    await state.update_data(benefit=message.text)
    data = await state.get_data()

    # Формируем сообщение с предпросмотром данных
    preview_message = (
        "📋 Предпросмотр нового проекта:\n\n"
        f"<b>Название:</b> {data['title']}\n\n"
        f"<b>Описание:</b> {data['description']}\n\n"
        f"<b>Бенефиты:</b> {message.text}\n\n"
        "Подтвердите добавление проекта или отмените:"
    )

    await message.answer(preview_message,
                         reply_markup = await confirm_cancel_add_projects(),
                         parse_mode="HTML")
    await state.set_state(ProjectAddState.waiting_for_confirmation)


@admin_project_router.callback_query(ProjectAddState.waiting_for_confirmation,
                              F.data == "confirm_add_project")
async def confirm_project_add(callback: CallbackQuery,
                              state: FSMContext,
                              session: AsyncSession):
    data = await state.get_data()

    new_project = Project(
        title=data["title"],
        description=data["description"],
        benefit=data["benefit"]
    )

    session.add(new_project)
    await session.commit()

    await callback.message.answer("✅ Новый проект добавлен!",
                         reply_markup=await admin_projects_menu())
    await callback.answer()
    await state.clear()


@admin_project_router.callback_query(F.data == "cancel_add_project")
async def confirm_project_add(callback: CallbackQuery,
                              state: FSMContext):
    await callback.message.answer("❌ Добавление проекта отменено.",
                                  reply_markup=await admin_projects_menu())
    await callback.answer()
    await state.clear()



# =====================================================================================
# ------------------------------------ Изменить проект --------------------------------
# =====================================================================================




@admin_project_router.callback_query(F.data == "projects:edit")
async def edit_project(callback: CallbackQuery,
                       state: FSMContext,
                       session: AsyncSession):
    await state.set_state(ProjectEditState.waiting_for_project_selection)
    try:
        await callback.message.answer("Изменение проекта")
        await callback.answer()

        result = await session.execute(select(Project))
        projects = result.scalars().all()

        if not projects:
            await callback.message.answer("📭 Список проектов пуст")
            return

        builder = InlineKeyboardBuilder()
        for project in projects:
            builder.button(
                text=f"{project.title}",
                callback_data=f"edit_project_{project.id}"
            )

        builder.adjust(1, repeat=True)

        await callback.message.answer(
            "<b>Выбери проект для редактирования</b>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )

    except Exception as e:
        await callback.message.answer("⚠️ Произошла ошибка при загрузке проектов")
        logging.error(f"Error in view_projects: {e}")


@admin_project_router.callback_query(ProjectEditState.waiting_for_project_selection,
                                     F.data.startswith("edit_project_"))
async def select_project_to_edit(callback: CallbackQuery,
                                 state: FSMContext,
                                 session: AsyncSession):
    try:
        project_id = int(callback.data.split("_")[-1])
        project = await session.get(Project, project_id)

        if not project:
            await callback.answer("Проект не найден", show_alert=True)
            return

        await state.update_data(
            project_id=project_id,
            current_title=project.title,
            current_description=project.description,
            current_benefit=project.benefit,
            current_example=project.example,
            current_raw_description=project.raw_description,
            current_raw_benefit=project.raw_benefit,
            current_raw_example=project.raw_example
        )

        skip_title_edit_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="Пропустить",
                    callback_data="skip_title_edit")],
                [InlineKeyboardButton(
                    text="⬅️ Назад к выбору проекта",
                    callback_data="back_to_project_selection")]
            ]
        )

        await callback.message.answer(
            f"Редактирование проекта: <b>{project.title}</b>\n\n"
            f"Введите новое название проекта или нажмите «Пропустить»:",
            reply_markup=skip_title_edit_keyboard,
            parse_mode="HTML"
        )

        await callback.answer()
        await state.set_state(ProjectEditState.waiting_for_title)

    except Exception as e:
        logging.error(f"Error in select_project_to_edit: {e}", exc_info=True)
        await callback.answer("Произошла ошибка при обработке запроса", show_alert=True)
        await session.rollback()


# Обработчик возврата к выбору проекта
@admin_project_router.callback_query(ProjectEditState.waiting_for_title,
                                     F.data == "back_to_project_selection")
async def back_to_project_selection(callback: CallbackQuery,
                                    state: FSMContext,
                                    session: AsyncSession):
    await edit_project(callback, state, session)


@admin_project_router.callback_query(ProjectEditState.waiting_for_title,
                                     F.data == "skip_title_edit")
async def skip_title_edit(callback: CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        await state.update_data(new_title=data.get('current_title'))

        skip_description_edit_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="Пропустить",
                    callback_data="skip_description_edit")],
                [InlineKeyboardButton(
                    text="⬅️ Назад к названию",
                    callback_data="back_to_title_edit")]
            ]
        )

        await callback.message.answer(
            "Введите новое описание проекта или нажмите «Пропустить»:",
            reply_markup=skip_description_edit_kb
        )
        await callback.answer()
        await state.set_state(ProjectEditState.waiting_for_description)
    except Exception as e:
        logging.error(f"Error in skip_title_edit: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)


# Обработчик возврата к редактированию названия
@admin_project_router.callback_query(ProjectEditState.waiting_for_description,
                                     F.data == "back_to_title_edit")
async def back_to_title_edit(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    skip_title_edit_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="Пропустить",
                callback_data="skip_title_edit")],
            [InlineKeyboardButton(
                text="⬅️ Назад к выбору проекта",
                callback_data="back_to_project_selection")]
        ]
    )

    await callback.message.answer(
        f"Редактирование названия проекта: <b>{data.get('current_title', '')}</b>\n\n"
        f"Введите новое название проекта или нажмите «Пропустить»:",
        reply_markup=skip_title_edit_kb
    )
    await callback.answer()
    await state.set_state(ProjectEditState.waiting_for_title)


@admin_project_router.message(ProjectEditState.waiting_for_title)
async def process_new_title(message: Message, state: FSMContext):
    await state.update_data(new_title=message.text)

    skip_description_edit_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="Пропустить",
                callback_data="skip_description_edit")],
            [InlineKeyboardButton(
                text="⬅️ Назад к названию",
                callback_data="back_to_title_edit")]
        ]
    )

    await message.answer(
        "Введите новое описание проекта или нажмите «Пропустить»:",
        reply_markup=skip_description_edit_kb
    )
    await state.set_state(ProjectEditState.waiting_for_description)


@admin_project_router.callback_query(ProjectEditState.waiting_for_description, F.data == "skip_description_edit")
async def skip_description_edit(callback: CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        await state.update_data(
            new_description=data.get('current_description', ''),
            new_raw_description=data.get('current_raw_description', '')
        )

        skip_benefit_edit_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="Пропустить",
                    callback_data="skip_benefit_edit")],
                [InlineKeyboardButton(
                    text="⬅️ Назад к описанию",
                    callback_data="back_to_description_edit")]
            ]
        )

        await callback.message.answer(
            "Введите новое описание бенефитов проекта или нажмите «Пропустить»:",
            reply_markup=skip_benefit_edit_kb
        )
        await callback.answer()
        await state.set_state(ProjectEditState.waiting_for_benefit)
    except Exception as e:
        logging.error(f"Error in skip_description_edit: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)


# Обработчик возврата к редактированию описания
@admin_project_router.callback_query(ProjectEditState.waiting_for_benefit,
                                     F.data == "back_to_description_edit")
async def back_to_description_edit(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    skip_description_edit_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="Пропустить",
                callback_data="skip_description_edit")],
            [InlineKeyboardButton(
                text="⬅️ Назад к названию",
                callback_data="back_to_title_edit")]
        ]
    )

    await callback.message.answer(
        "Введите новое описание проекта или нажмите «Пропустить»:",
        reply_markup=skip_description_edit_kb
    )
    await callback.answer()
    await state.set_state(ProjectEditState.waiting_for_description)


@admin_project_router.message(ProjectEditState.waiting_for_description)
async def process_new_description(message: Message, state: FSMContext):
    processed_text = hide_urls(message.text)
    await state.update_data(
        new_description=processed_text,
        new_raw_description=message.text
    )


    skip_benefit_edit_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="Пропустить",
                callback_data="skip_benefit_edit")],
            [InlineKeyboardButton(
                text="⬅️ Назад к описанию",
                callback_data="back_to_description_edit")]
        ]
    )

    await message.answer(
        "Введите новое описание бенефитов проекта или нажмите «Пропустить»:",
        reply_markup=skip_benefit_edit_kb
    )
    await state.set_state(ProjectEditState.waiting_for_benefit)


@admin_project_router.callback_query(ProjectEditState.waiting_for_benefit, F.data == "skip_benefit_edit")
async def skip_benefit_edit(callback: CallbackQuery, state: FSMContext):
    try:
        data = await state.get_data()
        await state.update_data(
            new_benefit=data.get('current_benefit', ''),
            new_raw_benefit=data.get('current_raw_benefit', '')
        )

        skip_example_edit_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="Пропустить",
                    callback_data="skip_example_edit")],
                [InlineKeyboardButton(
                    text="⬅️ Назад к бенефитам",
                    callback_data="back_to_benefit_edit")]
            ]
        )

        await callback.message.answer(
            "Введите новые примеры успеха или нажмите «Пропустить»:",
            reply_markup=skip_example_edit_kb
        )
        await callback.answer()
        await state.set_state(ProjectEditState.waiting_for_example)
    except Exception as e:
        logging.error(f"Error in skip_benefit_edit: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)


@admin_project_router.message(ProjectEditState.waiting_for_benefit)
async def process_new_benefit(message: Message, state: FSMContext):
    urls = extract_urls(message.text)
    await state.update_data(
        new_benefit=hide_urls(message.text),
        new_raw_benefit=message.text,
        benefit_urls=urls
    )

    skip_example_edit_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="Пропустить",
                callback_data="skip_example_edit")],
            [InlineKeyboardButton(
                text="⬅️ Назад к бенефитам",
                callback_data="back_to_benefit_edit")]
        ]
    )

    await message.answer(
        "Введите новые примеры успеха или нажмите «Пропустить»:",
        reply_markup=skip_example_edit_kb
    )
    await state.set_state(ProjectEditState.waiting_for_example)

@admin_project_router.callback_query(ProjectEditState.waiting_for_example, F.data == "back_to_benefit_edit")
async def back_to_benefit_edit(callback: CallbackQuery, state: FSMContext):
    try:
        skip_benefit_edit_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="Пропустить",
                    callback_data="skip_benefit_edit")],
                [InlineKeyboardButton(
                    text="⬅️ Назад к описанию",
                    callback_data="back_to_description_edit")]
            ]
        )

        await callback.message.answer(
            "Введите новое описание бенефитов проекта или нажмите «Пропустить»:",
            reply_markup=skip_benefit_edit_kb
        )
        await callback.answer()
        await state.set_state(ProjectEditState.waiting_for_benefit)
    except Exception as e:
        logging.error(f"Error in back_to_benefit_edit: {e}")
        await callback.answer("Произошла ошибка", show_alert=True)


@admin_project_router.callback_query(ProjectEditState.waiting_for_example,
                                     F.data == "skip_example_edit")
async def skip_example_edit(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    await state.update_data(
        new_example=data.get('current_example', ''),
        new_raw_example=data.get('current_raw_example', '')
    )

    preview_message = (
        "📋 <b>Предпросмотр изменений:</b>\n\n"
        f"<b>Название:</b>\n"
        f"Было: {data.get('current_title', 'не указано')}\n"
        f"Стало: {data.get('new_title', data.get('current_title', 'не изменено'))}\n\n"
        f"<b>Описание:</b>\n"
        f"Было: {data.get('current_description', 'не указано')}\n"
        f"Стало: {data.get('new_description', data.get('current_description', 'не изменено'))}\n\n"
        f"<b>Бенефиты:</b>\n"
        f"Было: {data.get('current_benefit', 'не указано')}\n"
        f"Стало: {data.get('new_benefit', data.get('current_benefit', 'не изменено'))}\n\n"
        f"<b>Примеры:</b>\n"
        f"Было: {data.get('current_example', 'не указано')}\n"
        f"Стало: {data.get('new_example', data.get('current_example', 'не изменено'))}\n\n"
        "Подтвердите изменения или отмените:"
    )

    await callback.message.answer(
        preview_message,
        parse_mode="HTML",
        reply_markup=await confirm_cancel_edit_projects(),
        disable_web_page_preview=True
    )
    await callback.answer()
    await state.set_state(ProjectEditState.waiting_for_confirmation)


@admin_project_router.message(ProjectEditState.waiting_for_example)
async def process_new_example(message: Message, state: FSMContext, session: AsyncSession):
    urls = extract_urls(message.text)
    await state.update_data(
        new_example=hide_urls(message.text),
        new_raw_example=message.text,
        example_urls=urls
    )

    data = await state.get_data()
    preview_message = (
        "📋 <b>Предпросмотр изменений:</b>\n\n"
        f"<b>Название:</b>\n"
        f"Было: {data.get('current_title', 'не указано')}\n"
        f"Стало: {data.get('new_title', data.get('current_title', 'не изменено'))}\n\n"
        f"<b>Описание:</b>\n"
        f"Было: {data.get('current_description', 'не указано')}\n"
        f"Стало: {data.get('new_description', data.get('current_description', 'не изменено'))}\n\n"
        f"<b>Бенефиты:</b>\n"
        f"Было: {data.get('current_benefit', 'не указано')}\n"
        f"Стало: {data.get('new_benefit', data.get('current_benefit', 'не изменено'))}\n\n"
        f"<b>Примеры:</b>\n"
        f"Было: {data.get('current_example', 'не указано')}\n"
        f"Стало: {data.get('new_example', data.get('current_example', 'не изменено'))}\n\n"
        "Подтвердите изменения или отмените:"
    )

    await message.answer(
        preview_message,
        parse_mode="HTML",
        reply_markup=await confirm_cancel_edit_projects(),
        disable_web_page_preview=True
    )
    await state.set_state(ProjectEditState.waiting_for_confirmation)


@admin_project_router.callback_query(ProjectEditState.waiting_for_confirmation,
                                     F.data == "confirm_edit_project")
async def confirm_project_edit(callback: CallbackQuery,
                               state: FSMContext,
                               session: AsyncSession):
    data = await state.get_data()

    if 'project_id' not in data:
        await callback.message.answer("❌ Ошибка: проект не выбран. Начните заново.")
        await state.clear()
        return

    project = await session.get(Project, data['project_id'])
    if not project:
        await callback.message.answer("⚠️ Проект не найден")
        await state.clear()
        return

    # Применяем изменения
    if 'new_title' in data:
        project.title = data['new_title']
    if 'new_description' in data:
        project.description = data['new_description']
        project.raw_description = data.get('new_raw_description', data['new_description'])
    if 'new_benefit' in data:
        project.benefit = data['new_benefit']
        project.raw_benefit = data.get('new_raw_benefit', data['new_benefit'])
    if 'new_example' in data:
        project.example = data['new_example']
        project.raw_example = data.get('new_raw_example', data['new_example'])

    await session.commit()

    await callback.message.answer(
        f"Проект <b>{project.title}</b> успешно изменен",
        parse_mode="HTML",
        reply_markup=await admin_projects_menu()
    )
    await callback.answer()
    await state.clear()


@admin_project_router.callback_query(F.data == "cancel_edit_project")
async def cancel_project_edit(callback: CallbackQuery,
                               state: FSMContext,
                               session: AsyncSession):
    await callback.message.answer("Изменение проекта отменено.",
                                  reply_markup=await admin_projects_menu())
    await callback.answer()
    await state.clear()




# =====================================================================================
# ------------------------------------ Удалить проект --------------------------------
# =====================================================================================



@admin_project_router.callback_query(F.data == "projects:delete")
async def delete_project_start(callback: CallbackQuery,
                               state: FSMContext,
                               session: AsyncSession):
    try:
        result = await session.execute(select(Project))
        projects = result.scalars().all()

        if not projects:
            await callback.message.answer("📭 Список проектов пуст")
            return

        # Создаем клавиатуру
        builder = InlineKeyboardBuilder()

        # Добавляем кнопки для каждого проекта
        for project in projects:
            builder.button(
                text=f"{project.title}",
                callback_data=f"delete_project_{project.id}"
            )

        # Форматируем кнопки
        builder.adjust(1, repeat=True)

        await callback.message.answer(
            "📂 <b>Выбери проект для удаления</b>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        await callback.answer()

    except Exception as e:
        await callback.message.answer("⚠️ Произошла ошибка при загрузке проектов")
        logging.error(f"Error in view_projects: {e}")
        await callback.answer()

    await state.set_state(ProjectDeleteState.waiting_for_delete)


@admin_project_router.callback_query(ProjectDeleteState.waiting_for_delete,
                                     F.data.startswith("delete_project_"))
async def select_project_to_delete(callback: CallbackQuery,
                                   state: FSMContext,
                                   session: AsyncSession):
    project_id = int(callback.data.split("_")[-1])
    project = await session.get(Project, project_id)

    if not project:
        await callback.answer("Проект не найден", show_alert=True)
        return

    await state.update_data(project_id=project_id, project_title=project.title)
    await state.set_state(ProjectDeleteState.waiting_for_confirmation)

    await callback.message.answer(
        f"⚠️ Вы уверены, что хотите удалить проект  <b>{project.title}</b>?",
        parse_mode="HTML",
        reply_markup=await confirm_delete_keyboard()
    )
    await callback.answer()


@admin_project_router.callback_query(ProjectDeleteState.waiting_for_confirmation,
                              F.data == "delete_projects:confirm")
async def confirm_project_delete(callback: CallbackQuery,
                                 state: FSMContext,
                                 session: AsyncSession):
    data = await state.get_data()
    project = await session.get(Project, data['project_id'])

    if project:
        await session.delete(project)
        await session.commit()
        await callback.message.answer(
            f"🗑️ Проект <b>{data['project_title']}</b> успешно удален!",
            parse_mode="HTML",
            reply_markup=await admin_projects_menu()
        )
        await callback.answer()
    else:
        await callback.message.answer(
            "⚠️ Проект не найден или уже был удален",
            reply_markup=await admin_projects_menu()
        )
        await callback.answer()

    await state.clear()


@admin_project_router.callback_query(ProjectDeleteState.waiting_for_confirmation,
                                     F.data == "delete_projects:cancel")
async def cancel_project_delete(callback: CallbackQuery,
                                state: FSMContext):
    data = await state.get_data()
    await callback.message.answer(
        f"❌ Удаление проекта <b>{data.get('project_title', '')}</b> отменено",
        parse_mode="HTML",
        reply_markup=await admin_projects_menu()
    )
    await callback.answer()
    await state.clear()



# =====================================================================================
# ---------------------------------------- Назад -------------------------------------
# =====================================================================================



@admin_project_router.callback_query(F.data == "projects:admin_main_menu")
async def back_to_main_menu(callback: CallbackQuery):
    await callback.message.answer("Возврат в главное админ-меню",
                                  reply_markup=await admin_main_menu())
    await callback.answer()
