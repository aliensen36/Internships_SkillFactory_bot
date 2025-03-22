from aiogram.utils.keyboard import InlineKeyboardBuilder


class BaseMenu:
    """Вазовый класс для создания меню разделов."""
    def __init__(self, lexicon: dict, title: str):
        self.lexicon = lexicon
        self.title = title

    @staticmethod
    def create_menu_keyboard(buttons):
        """Базовая функция создания меню."""
        builder = InlineKeyboardBuilder()
        for text, callback_data in buttons:
            if callback_data.startswith("http"):
                builder.button(text=text, url=callback_data)
            else:
                builder.button(text=text, callback_data=callback_data)
        builder.adjust(1)
        return builder.as_markup()

    def create_base_menu_keyboard(self):
        """Функция создания начального меню Base."""
        buttons = [
            (self.lexicon[f'{self.title}_is'], f"{self.title}_is"),
            (self.lexicon['benefits'], f"{self.title}_benefits"),
            (self.lexicon['examples'], f"{self.title}_contests"),
            (self.lexicon['want_participate'], self.lexicon['url_calendar_events']),
            (self.lexicon['another_time'], f"answer_{self.title}"),
            (self.lexicon['return_menu'], "menu")
        ]
        return self.create_menu_keyboard(buttons)

    def create_base_menu_base_is(self):
        """Функция создания меню Base с определением конкурса."""
        buttons = [
            (self.lexicon['benefits'], f"{self.title}_benefits"),
            (self.lexicon['examples'], f"{self.title}_contests"),
            (self.lexicon['want_participate'], self.lexicon['url_calendar_events']),
            (self.lexicon['another_time'], f"answer_{self.title}"),
            (self.lexicon['backward'], f"{self.title}"),
            (self.lexicon['return_menu'], "menu")
        ]
        return self.create_menu_keyboard(buttons)

    def create_base_menu_benefits(self):
        """Функция создания меню Base с определением бенефиты от участия."""
        buttons = [
            (self.lexicon[f'{self.title}_is'], f"{self.title}_is"),
            (self.lexicon['examples'], f"{self.title}_contests"),
            (self.lexicon['want_participate'], self.lexicon['url_calendar_events']),
            (self.lexicon['another_time'], f"answer_{self.title}"),
            (self.lexicon['backward'], f"{self.title}"),
            (self.lexicon['return_menu'], "menu")
        ]
        return self.create_menu_keyboard(buttons)

    def create_base_menu_examples(self):
        """Функция создания меню Base с определением примеров."""
        buttons = [
            (self.lexicon[f'{self.title}_is'], f"{self.title}_is"),
            (self.lexicon['benefits'], f"{self.title}_benefits"),
            (self.lexicon['want_participate'], self.lexicon['url_calendar_events']),
            (self.lexicon['another_time'], f"answer_{self.title}"),
            (self.lexicon['backward'], f"{self.title}"),
            (self.lexicon['return_menu'], "menu")
        ]
        return self.create_menu_keyboard(buttons)

    def create_base_menu_backward(self):
        """Функция создания меню Base с кнопками назад."""
        buttons = [
            (self.lexicon['backward'], f"{self.title}"),
            (self.lexicon['return_menu'], "menu")
        ]
        return self.create_menu_keyboard(buttons)