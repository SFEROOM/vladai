from .bot import bot, dp

__all__ = ['bot', 'dp']

# Импортируем модули с обработчиками
import bot.reminders
import bot.reminders_edit 