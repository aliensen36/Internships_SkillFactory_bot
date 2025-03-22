from aiogram.filters import CommandStart, StateFilter
from aiogram.types import CallbackQuery, Message
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
from sqlalchemy.ext.asyncio import AsyncSession
import app.keyboards.reply as reply_kb



start_router = Router()

class BaseMenuHandler:
    """Класс для обработки колбеков меню заданной тематики."""

    def __init__(self, lexicon: dict, title: str, name: str):
        self.lexicon = lexicon
        self.title = title
        self.name = name
        self.menu = reply_kb.BaseMenu(lexicon=self.lexicon, title=self.title)
        self.router = Router()

    @staticmethod
    async def handle_menu_callback(callback: CallbackQuery, text: str, menu_creator):
        """Базовая функция обработки колбеков."""
        await callback.message.edit_text(
            text=text,
            reply_markup=menu_creator(),
            parse_mode="HTML"
        )

    def register_handlers(self):
        """Регистрация обработчиков для Base."""

        @self.router.callback_query(F.data == self.title)
        async def callback_contest_menu(callback: CallbackQuery):
            """Колбек изменения клавиатуры на начальную заданного раздела."""
            await self.handle_menu_callback(
                callback,
                text=f"{self.lexicon['will_be_soon1']}{self.name}{self.lexicon['will_be_soon2']}",
                menu_creator=self.menu.create_base_menu_keyboard
            )

        @self.router.callback_query(F.data == f'{self.title}_is')
        async def callback_base_menu_base_is(callback: CallbackQuery):
            """Колбек вывода определения заданной тематики и изменения клавиатуры."""
            await self.handle_menu_callback(
                callback,
                text=self.lexicon[f'{self.title}_text'],
                menu_creator=self.menu.create_base_menu_base_is
            )

        @self.router.callback_query(F.data == f'{self.title}_benefits')
        async def callback_base_menu_benefits(callback: CallbackQuery):
            """Колбек вывода текста о бенефитах по заданной тематики и изменения клавиатуры."""
            await self.handle_menu_callback(
                callback,
                text=self.lexicon[f'benefits_{self.title}_text'],
                menu_creator=self.menu.create_base_menu_benefits
            )

        @self.router.callback_query(F.data == f'{self.title}_contests')
        async def callback_base_menu_examples(callback: CallbackQuery):
            """Колбек вывода текста о примерах по заданной тематики и изменения клавиатуры."""
            await self.handle_menu_callback(
                callback,
                text=self.lexicon[f'examples_{self.title}_text'],
                menu_creator=self.menu.create_base_menu_examples
            )

        @self.router.callback_query(F.data == f'answer_{self.title}')
        async def callback_base_menu_answer_no(callback: CallbackQuery):
            """Колбек вывода текста при нажатии на кнопку не хочу участвовать и изменения клавиатуры."""
            await self.handle_menu_callback(
                callback,
                text=f"{self.lexicon['calendar_offer1']}{self.lexicon[f'calendar_offer_{self.title}']}",
                menu_creator=self.menu.create_base_menu_backward
#             )
#
# @start_router.message(CommandStart(), StateFilter(default_state))
# async def cmd_start(message: Message, state: FSMContext,
#                     session: AsyncSession):
#     tg_user = message.from_user
#
#     # Обработка отсутствия username
#     if not tg_user.username:
#         photo_ios_path = 'docs/ios_guide.jpg'
#         photo_android_path = 'docs/android_guide.jpg'
#         ios_instructions = ios_instructions_message
#         android_instructions = android_instructions_message
#         await message.answer_photo(photo=FSInputFile(photo_ios_path), caption=ios_instructions)
#         await message.answer_photo(photo=FSInputFile(photo_android_path), caption=android_instructions)
#         await message.answer(
#             "Для взаимодействия с ботом необходимо задать **Username** в настройках Telegram, "
#             "после чего нажмите /start", parse_mode="Markdown"
#         )
#         return
#
#     # Проверка наличия пользователь в БД
#     stmt = select(User).where(User.tg_id == tg_user.id)
#     result = await session.execute(stmt)
#     user = result.scalar_one_or_none()
#
#     if not user:
#         # Создание пользователя
#         user = User(
#             tg_id=tg_user.id,
#             first_name=tg_user.first_name,
#             last_name=tg_user.last_name,
#             username=tg_user.username
#         )
#         session.add(user)
#         await session.commit()
#         await message.answer(welcome_message)
#         await state.set_state(Registration.gender)
#         await message.answer("Кто Вы?", reply_markup=inline_kb.kb_gender)
#     else:
#         # Приветствие зарегистрированного пользователя
#         await message.answer("Добро пожаловать! 🎉\nС возвращением!",
#                              reply_markup=reply_kb.main)
#
#
# @start_router.callback_query(StateFilter(Registration.gender), F.data.in_(
#     ['male', 'female']))
# async def gender_choice(callback: CallbackQuery, state: FSMContext):
#     gender_mapping = {
#         'male': 'Мужчина',
#         'female': 'Женщина'
#     }
#     gender = gender_mapping.get(callback.data)
#     await state.update_data(gender=gender)
#     await state.set_state(Registration.profession)
#     await callback.message.edit_text("Здорово! 😃 \n\nРасскажи, чем ты занимаешься?",
#                                      reply_markup=inline_kb.kb_profession)
#     await callback.answer()
#
#
# @start_router.callback_query(StateFilter(Registration.profession),
#                              F.data.in_(['student', 'businessman', 'employee',
#                                          'freelancer']))
# async def profession_choice(callback: CallbackQuery, state: FSMContext,
#                             session: AsyncSession):
#     profession_mapping = {
#         'student': 'Студент',
#         'businessman': 'Предприниматель',
#         'employee': 'Сотрудник',
#         'freelancer': 'Фрилансер'
#     }
#     profession = profession_mapping.get(callback.data)
#     tg_user = callback.from_user
#     await state.update_data(profession=profession)
#     await callback.answer()
#
#     data = await state.get_data()
#     gender = data.get('gender')
#     profession = data.get('profession')
#
#     stmt = select(User).where(User.tg_id == tg_user.id)
#     result = await session.execute(stmt)
#     user = result.scalar_one_or_none()
#
#     if user:
#         user.gender = gender
#         user.profession = profession
#         await session.commit()
#
#     await callback.message.edit_text("Отлично! 👍 \nДля получения скидки 10% остался "
#                                      "лишь один шаг.\nПерейди в меню и оформи карту "
#                                      "лояльности 💳")
#     await callback.message.answer("Если кнопки скрыты, то нажми на иконку 🎛 "
#                                   "в правом нижнем углу рядом с микрофоном 👌",
#                                   reply_markup=reply_kb.main)
#     await state.clear()