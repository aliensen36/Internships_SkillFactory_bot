from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from app.filters.chat_types import ChatTypeFilter, IsAdmin
from app.fsm_states import ProjectAddState
from app.keyboards.reply import kb_admin_main
from database.models import Project


admin_project_router = Router()
admin_project_router.message.filter(ChatTypeFilter(["private"]), IsAdmin())


@admin_project_router.message(F.text == "📥 Добавить проект")
async def add_project_start(message: Message, state: FSMContext):
    await state.set_state(ProjectAddState.title)
    await message.answer("Введите заголовок для проекта:")

@admin_project_router.message(ProjectAddState.title)
async def add_project_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await state.set_state(ProjectAddState.content)
    await message.answer("Теперь введите описание проекта:")

@admin_project_router.message(ProjectAddState.content)
async def add_project_content(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    new_project = Project(title=data["title"], content=message.text)
    session.add(new_project)
    await session.commit()
    await state.clear()
    await message.answer("✅ Новый проект добавлен!", reply_markup=kb_admin_main)
