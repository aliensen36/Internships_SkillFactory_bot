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
from app.keyboards.reply import kb_admin_main, projects_menu_keyboard, confirm_cancel_keyboard, confirm_delete_keyboard
from database.models import Project


admin_project_router = Router()
admin_project_router.message.filter(ChatTypeFilter(["private"]), IsAdmin())


# Хендлер для кнопки "📁 Проекты"
@admin_project_router.message(F.text == "📁 Проекты")
async def show_projects_menu(message: Message, state: FSMContext):
    await message.answer(
        text="📂 <b>Меню проектов</b>\nВыберите действие:",
        reply_markup=projects_menu_keyboard(),
        parse_mode="HTML"
    )


@admin_project_router.message(F.text == "👀 Просмотр")
async def view_projects(message: Message,
                        session: AsyncSession):
    # Получаем все проекты из базы с предзагрузкой связанных данных
    try:
        result = await session.execute(select(Project))
        projects = result.scalars().all()

        if not projects:
            await message.answer("📭 Список проектов пуст")
            return

        # Формируем текст сообщения
        projects_list = "\n".join(
            f"{project.title}\n"
            for project in projects
        )

        await message.answer(
            f"📂 <b>Список проектов</b>:\n\n{projects_list}\n\n",
            parse_mode="HTML"
        )

    except Exception as e:
        await message.answer("⚠️ Произошла ошибка при загрузке проектов")
        logging.error(f"Error in view_projects: {e}")
    # finally:
    #     await session.close()



# =====================================================================================
# ------------------------------------ Добавить проект --------------------------------
# =====================================================================================


# Общий обработчик кнопки "❌ Отменить"
@admin_project_router.message(F.text == "❌ Отменить")
async def cancel_project_add_anywhere(message: Message,
                                      state: FSMContext):
    current_state = await state.get_state()
    if current_state in [
        ProjectAddState.waiting_for_title,
        ProjectAddState.waiting_for_description,
        ProjectAddState.waiting_for_benefit,
        ProjectAddState.waiting_for_confirmation
    ]:
        await state.clear()
        await message.answer("❌ Добавление проекта отменено.",
                            reply_markup=projects_menu_keyboard())
    else:
        await message.answer("Нет активного процесса добавления проекта.")


@admin_project_router.message(F.text == "➕ Добавить")
async def add_project_start(message: Message,
                            state: FSMContext):
    await state.set_state(ProjectAddState.waiting_for_title)
    await message.answer("Введите название проекта:",
                         reply_markup=confirm_cancel_keyboard )


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
                         parse_mode="HTML")
    await state.set_state(ProjectAddState.waiting_for_confirmation)


@admin_project_router.message(ProjectAddState.waiting_for_confirmation,
                              F.text == "✅ Подтвердить")
async def confirm_project_add(message: Message,
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

    await message.answer("✅ Новый проект добавлен!",
                         reply_markup=projects_menu_keyboard())
    await state.clear()




# =====================================================================================
# ------------------------------------ Изменить проект --------------------------------
# =====================================================================================


@admin_project_router.message(F.text == "✏️ Изменить")
async def edit_project(message: Message,
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
                callback_data=f"edit_project_{project.id}"
            )

        # Форматируем кнопки
        builder.adjust(1, repeat=True)

        await message.answer(
            "📂 <b>Выбери проект для редактирования</b>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )

    except Exception as e:
        await message.answer("⚠️ Произошла ошибка при загрузке проектов")
        logging.error(f"Error in view_projects: {e}")

    await state.set_state(ProjectEditState.waiting_for_title)


# Обработчик выбора проекта для редактирования
@admin_project_router.callback_query(ProjectEditState.waiting_for_title,
                                     F.data.startswith("edit_project_"))
async def select_project_to_edit(callback: CallbackQuery, state: FSMContext,
                                 session: AsyncSession):
    try:
        project_id = int(callback.data.split("_")[-1])
        project = await session.get(Project, project_id)

        if not project:
            await callback.answer("Проект не найден", show_alert=True)
            return

        # Сохраняем данные в state
        await state.update_data(
            project_id=project_id,
            current_title=project.title,
            current_content=project.description,
            current_benefit=project.benefit
        )

        # Создаем клавиатуру с кнопкой пропуска
        skip_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_title")]
            ]
        )

        # Редактируем сообщение
        await callback.message.edit_text(
            f"✏️ <b>Редактирование проекта:\n\n</b> {project.title}\n\n"
            "Введите новое название проекта или нажмите «Пропустить»",
            reply_markup=skip_kb,
            parse_mode="HTML"
        )
        await callback.answer()

    except Exception as e:
        logging.error(f"Error in select_project_to_edit: {e}", exc_info=True)
        await callback.answer("Произошла ошибка при обработке запроса", show_alert=True)
        await session.rollback()


# Обработчик пропуска изменения названия
@admin_project_router.callback_query(F.data == "skip_title",
                                     ProjectEditState.waiting_for_title)
async def skip_title_edit(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    # Если project_id нет — ошибка
    if 'project_id' not in data:
        await callback.answer("❌ Ошибка: проект не выбран.", show_alert=True)
        return

    # Сохраняем текущие данные и переходим к следующему шагу
    await state.update_data(
        new_title=data.get('current_title'),  # Если не меняли, оставляем старое название
        project_id=data['project_id']  # Обязательно передаём project_id дальше!
    )

    skip_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить",
                                  callback_data="skip_content")]
        ]
    )

    await callback.message.edit_text(
        f"✏️ <b>Редактирование описания проекта:</b> {data['current_title']}\n\n"
        "Введите новое описание проекта или нажмите «Пропустить»:",
        reply_markup=skip_kb,
        parse_mode="HTML"
    )
    await state.set_state(ProjectEditState.waiting_for_description)
    await callback.answer()


# Обработчик ввода нового названия
@admin_project_router.message(ProjectEditState.waiting_for_title)
async def process_new_title(message: Message, state: FSMContext):
    await state.update_data(new_title=message.text)

    skip_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_content")]
        ]
    )

    await message.answer(
        "✏️ Введите новое описание проекта или нажмите «Пропустить»:",
        reply_markup=skip_kb
    )
    await state.set_state(ProjectEditState.waiting_for_description)


# Обработчик пропуска изменения описания
@admin_project_router.callback_query(F.data == "skip_content",
                                   ProjectEditState.waiting_for_description)
async def skip_content_edit(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    skip_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_benefit")]
        ]
    )

    await callback.message.edit_text(
        f"✏️ <b>Редактирование бенефитов проекта:</b> {data.get('new_title', data['current_title'])}\n\n"
        "Введите новые бенефиты проекта или нажмите «Пропустить»:",
        reply_markup=skip_kb,
        parse_mode="HTML"
    )
    await state.set_state(ProjectEditState.waiting_for_benefit)
    await callback.answer()

# Обработчик ввода нового описания
@admin_project_router.message(ProjectEditState.waiting_for_description)
async def process_new_description(message: Message, state: FSMContext):
    await state.update_data(new_description=message.text)

    skip_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_benefit")]
        ]
    )

    await message.answer(
        "✏️ Введите новые бенефиты проекта или нажмите «Пропустить»:",
        reply_markup=skip_kb
    )
    await state.set_state(ProjectEditState.waiting_for_benefit)

# Обработчик пропуска изменения бенефитов
@admin_project_router.callback_query(F.data == "skip_benefit",
                                   ProjectEditState.waiting_for_benefit)
async def skip_benefit_edit(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()

    # Обновляем проект только если есть изменения
    project = await session.get(Project, data['project_id'])
    if project:
        if 'new_title' in data:
            project.title = data['new_title']
        if 'new_description' in data:
            project.description = data['new_description']
        # Бенефиты не изменяем, так как пропустили

        await session.commit()

        await callback.message.edit_text(
            f"✅ Проект <b>{project.title}</b> успешно изменен",
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text("⚠️ Проект не найден")

    await state.clear()
    await callback.answer()

# Обработчик ввода новых бенефитов
@admin_project_router.message(ProjectEditState.waiting_for_benefit)
async def process_new_benefit(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()

    if 'project_id' not in data:
        await message.answer("❌ Ошибка: проект не выбран. Начните заново.")
        await state.clear()
        return

    # Обновляем проект
    project = await session.get(Project, data['project_id'])
    if not project:
        await message.answer("⚠️ Проект не найден")
        await state.clear()
        return

    # Обновляем данные проекта
    if 'new_title' in data:
        project.title = data['new_title']
    if 'new_description' in data:
        project.description = data['new_description']
    project.benefit = message.text  # Обновляем бенефиты

    await session.commit()

    await message.answer(
        f"✅ Проект <b>{project.title}</b> успешно изменен",
        parse_mode="HTML"
    )
    await state.clear()


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
