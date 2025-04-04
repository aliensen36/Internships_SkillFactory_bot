import logging
from aiogram import F, Router
from aiogram.filters import Filter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.filters.chat_types import ChatTypeFilter, IsAdmin
from app.fsm_states import ProjectAddState, ProjectEditState, ProjectDeleteState
from app.keyboards.inline import admin_projects_menu, confirm_cancel_projects
from app.keyboards.reply import kb_admin_main, confirm_cancel_keyboard, confirm_delete_keyboard
from database.models import Project


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
                         reply_markup = await confirm_cancel_projects(),
                         parse_mode="HTML")
    await state.set_state(ProjectAddState.waiting_for_confirmation)


@admin_project_router.callback_query(ProjectAddState.waiting_for_confirmation,
                              F.data == "confirm_action")
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


@admin_project_router.callback_query(F.data == "cancel_action")
async def confirm_project_add(callback: CallbackQuery,
                              state: FSMContext,
                              session: AsyncSession):
    await callback.message.answer("❌ Добавление проекта отменено.",
                                  reply_markup=await admin_projects_menu())



# =====================================================================================
# ------------------------------------ Изменить проект --------------------------------
# =====================================================================================



# Общий обработчик кнопки "Отменить"
@admin_project_router.message(F.text == "Отменить",
                              ProjectEditState.waiting_for_project_selection)
@admin_project_router.message(F.text == "Отменить",
                              ProjectEditState.waiting_for_title)
@admin_project_router.message(F.text == "Отменить",
                              ProjectEditState.waiting_for_description)
@admin_project_router.message(F.text == "Отменить",
                              ProjectEditState.waiting_for_benefit)
@admin_project_router.message(F.text == "Отменить",
                              ProjectEditState.waiting_for_confirmation)
async def cancel_project_edit(message: Message,
                              state: FSMContext):
    await state.clear()
    await message.answer(
        "Изменение проекта отменено.",
        reply_markup=projects_menu_keyboard()
    )

# Обработчик для случаев, когда нет активного редактирования
# @admin_project_router.message(F.text == "❌ Отменить")
# async def cancel_without_active_edit(message: Message):
#     await message.answer("Нет активного процесса изменения проекта.")


@admin_project_router.message(F.text == "✏️ Изменить")
async def edit_project(message: Message,
                       state: FSMContext,
                       session: AsyncSession):
    await state.set_state(ProjectEditState.waiting_for_project_selection)
    try:
        await message.answer("Изменение проекта",
                             reply_markup=confirm_cancel_keyboard)

        result = await session.execute(select(Project))
        projects = result.scalars().all()

        if not projects:
            await message.answer("📭 Список проектов пуст")
            return

        # Создаем клавиатуру
        builder = InlineKeyboardBuilder()

        # Добавляем кнопки для каждого проекта
        for project in projects:
            builder.button(
                text=f"{project.title}",
                callback_data=f"edit_project_{project.id}"
            )

        # Форматируем кнопки
        builder.adjust(1, repeat=True)

        await message.answer(
            "<b>Выбери проект для редактирования</b>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )

    except Exception as e:
        await message.answer("⚠️ Произошла ошибка при загрузке проектов")
        logging.error(f"Error in view_projects: {e}")


# Обработчик выбора проекта для редактирования
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
            current_content=project.description,
            current_benefit=project.benefit
        )

        # Создаем клавиатуру с кнопкой пропуска
        skip_title_edit_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Пропустить",
                                      callback_data="skip_title_edit")]
            ]
        )

        await callback.message.edit_text(
            f"Редактирование проекта:  <b>{project.title}</b>\n\n"
            f"Введите новое название проекта или нажмите «Пропустить»:",
            reply_markup=skip_title_edit_keyboard,
            parse_mode="HTML"
        )

        await callback.answer()
        await state.set_state(ProjectEditState.waiting_for_title)

    except Exception as e:
        logging.error(f"Error in select_project_to_edit: {e}", exc_info=True)
        await callback.answer("Произошла ошибка при обработке запроса",
                              show_alert=True)
        await session.rollback()


# Обработчик пропуска изменения названия
@admin_project_router.callback_query(ProjectEditState.waiting_for_title,
                                     F.data == "skip_title_edit")
async def skip_title_edit(callback: CallbackQuery,
                          state: FSMContext):
    data = await state.get_data()
    await state.update_data(new_title=data.get('current_title'))

    skip_description_edit_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить",
                                  callback_data="skip_description_edit")]
        ]
    )

    await callback.message.answer(
        "Введите новое описание проекта или нажмите «Пропустить»:",
        reply_markup=skip_description_edit_kb
    )

    await callback.answer()
    await state.set_state(ProjectEditState.waiting_for_description)


# Обработчик ввода нового названия
@admin_project_router.message(ProjectEditState.waiting_for_title)
async def process_new_title(message: Message,
                            state: FSMContext):
    await state.update_data(new_title=message.text)

    skip_description_edit_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить",
                                  callback_data="skip_description_edit")]
        ]
    )

    await message.answer(
        "Введите новое описание проекта или нажмите «Пропустить»:",
        reply_markup=skip_description_edit_kb
    )
    await state.set_state(ProjectEditState.waiting_for_description)


# Обработчик пропуска изменения описания
@admin_project_router.callback_query(ProjectEditState.waiting_for_description,
                                     F.data == "skip_description_edit")
async def skip_description_edit(callback: CallbackQuery,
                            state: FSMContext):
    data = await state.get_data()
    await state.update_data(new_description=data.get('current_description'))

    skip_benefit_edit_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить",
                                  callback_data="skip_benefit_edit")]
        ]
    )

    await callback.message.answer(
        "Введите новое описание бенефитов проекта или нажмите «Пропустить»:",
        reply_markup=skip_benefit_edit_kb
    )

    await callback.answer()
    await state.set_state(ProjectEditState.waiting_for_benefit)


# Обработчик ввода нового описания
@admin_project_router.message(ProjectEditState.waiting_for_description)
async def process_new_description(message: Message,
                                  state: FSMContext):
    await state.update_data(new_description=message.text)

    skip_benefit_edit_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить",
                                  callback_data="skip_benefit_edit")]
        ]
    )

    await message.answer(
        "Введите новое описание бенефитов проекта или нажмите «Пропустить»:",
        reply_markup=skip_benefit_edit_kb
    )
    await state.set_state(ProjectEditState.waiting_for_benefit)


# Обработчик пропуска изменения бенефитов
@admin_project_router.callback_query(ProjectEditState.waiting_for_benefit,
                                     F.data == "skip_benefit_edit")
async def skip_benefit_edit(callback: CallbackQuery,
                            state: FSMContext,
                            session: AsyncSession):
    data = await state.get_data()

    # Формируем сообщение с предпросмотром
    preview_message = (
        "📋 <b>Предпросмотр изменений:</b>\n\n"
        f"<b>Название:</b>\n"
        f"Было: {data.get('current_title', 'не указано')}\n"
        f"Стало: {data.get('new_title', data.get('current_title', 'не изменено'))}\n\n"
        f"<b>Описание:</b>\n"
        f"Было: {data.get('current_content', 'не указано')}\n"
        f"Стало: {data.get('new_description', data.get('current_content', 'не изменено'))}\n\n"
        f"<b>Бенефиты:</b>\n"
        f"Было: {data.get('current_benefit', 'не указано')}\n"
        f"Стало: {data.get('new_benefit', data.get('current_benefit', 'не изменено'))}\n\n"
        "Подтвердите изменения или отмените:"
    )

    await callback.message.answer(
        preview_message,
        parse_mode="HTML",
        reply_markup=confirm_cancel_keyboard
    )
    await state.set_state(ProjectEditState.waiting_for_confirmation)
    await callback.answer()


# Обработчик ввода новых бенефитов
@admin_project_router.message(ProjectEditState.waiting_for_benefit)
async def process_new_benefit(message: Message,
                              state: FSMContext,
                              session: AsyncSession):
    await state.update_data(new_benefit=message.text)

    # Получаем все данные для предпросмотра
    data = await state.get_data()

    # Формируем сообщение с предпросмотром изменений
    preview_message = (
        "📋 <b>Предпросмотр изменений:</b>\n\n"
        f"<b>Название:</b>\n"
        f"Было: {data.get('current_title', 'не указано')}\n"
        f"Стало: {data.get('new_title', data.get('current_title', 'не изменено'))}\n\n"
        f"<b>Описание:</b>\n"
        f"Было: {data.get('current_content', 'не указано')}\n"
        f"Стало: {data.get('new_description', data.get('current_content', 'не изменено'))}\n\n"
        f"<b>Бенефиты:</b>\n"
        f"Было: {data.get('current_benefit', 'не указано')}\n"
        f"Стало: {data.get('new_benefit', data.get('current_benefit', 'не изменено'))}\n\n"
        "Подтвердите изменения или отмените:"
    )

    await message.answer(
        preview_message,
        parse_mode="HTML",
        reply_markup=confirm_cancel_keyboard
    )
    await state.set_state(ProjectEditState.waiting_for_confirmation)


# Обработчик подтверждения изменений
@admin_project_router.message(ProjectEditState.waiting_for_confirmation,
                              F.text == "Подтвердить")
async def confirm_project_edit(message: Message,
                               state: FSMContext,
                               session: AsyncSession):
    data = await state.get_data()

    if 'project_id' not in data:
        await message.answer("❌ Ошибка: проект не выбран. Начните заново.")
        await state.clear()
        return

    project = await session.get(Project, data['project_id'])
    if not project:
        await message.answer("⚠️ Проект не найден")
        await state.clear()
        return

    # Применяем изменения
    if 'new_title' in data:
        project.title = data['new_title']
    if 'new_description' in data:
        project.description = data['new_description']
    if 'new_benefit' in data:
        project.benefit = data['new_benefit']

    await session.commit()

    await message.answer(
        f"Проект <b>{project.title}</b> успешно изменен",
        parse_mode="HTML",
        reply_markup=projects_menu_keyboard()
    )
    await state.clear()


# @admin_project_router.message(F.text == "❌ Отменить")
# async def cancel_without_active_process(message: Message):
#     await message.answer("Нет активного процесса добавления или изменения проекта.")


# =====================================================================================
# ------------------------------------ Удалить проект --------------------------------
# =====================================================================================



@admin_project_router.message(F.text == "🗑️ Удалить")
async def delete_project_start(message: Message,
                         state: FSMContext,
                         session: AsyncSession):
    try:
        result = await session.execute(select(Project))
        projects = result.scalars().all()

        if not projects:
            await message.answer("📭 Список проектов пуст")
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

        await message.answer(
            "📂 <b>Выбери проект для удаления</b>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )

    except Exception as e:
        await message.answer("⚠️ Произошла ошибка при загрузке проектов")
        logging.error(f"Error in view_projects: {e}")

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
        f"⚠️ Вы уверены, что хотите удалить проект:\n\n"
        f"<b>{project.title}</b>?",
        parse_mode="HTML",
        reply_markup=confirm_delete_keyboard
    )
    await callback.answer()


@admin_project_router.message(ProjectDeleteState.waiting_for_confirmation,
                              F.text == "✅ Да, удалить")
async def confirm_project_delete(message: Message,
                                 state: FSMContext,
                                 session: AsyncSession):
    data = await state.get_data()
    project = await session.get(Project, data['project_id'])

    if project:
        await session.delete(project)
        await session.commit()
        await message.answer(
            f"🗑️ Проект <b>{data['project_title']}</b> успешно удален!",
            parse_mode="HTML",
            reply_markup=projects_menu_keyboard()
        )
    else:
        await message.answer(
            "⚠️ Проект не найден или уже был удален",
            reply_markup=projects_menu_keyboard()
        )

    await state.clear()


@admin_project_router.message(ProjectDeleteState.waiting_for_confirmation,
                              F.text == "❌ Нет, отменить")
async def cancel_project_delete(message: Message,
                                state: FSMContext):
    data = await state.get_data()
    await message.answer(
        f"❌ Удаление проекта <b>{data.get('project_title', '')}</b> отменено",
        parse_mode="HTML",
        reply_markup=projects_menu_keyboard()
    )
    await state.clear()






@admin_project_router.message(F.text == "◀️ Назад")
async def back_to_main_menu(message: Message):
    await message.answer("Возврат в главное админ-меню",
                       reply_markup=kb_admin_main)
