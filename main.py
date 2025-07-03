#!/usr/bin/env python3
"""
Главный модуль запуска приложения
"""
import logging
import sys
import signal
from aiogram import executor
import os

# Настройка путей для импорта
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot.bot import dp
from config import LOG_LEVEL, APP_NAME, APP_VERSION
from database.migrations import run_migrations
from scheduler.scheduler import start_scheduler, stop_scheduler

# Настройка логирования
logging.basicConfig(level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger(__name__)

def signal_handler(sig, frame):
    """Обработчик сигналов для корректного завершения работы"""
    logger.info("Остановка бота...")
    stop_scheduler()
    logger.info("Планировщик остановлен")
    logger.info("Бот остановлен")
    sys.exit(0)

async def on_startup(dp):
    """Действия при запуске бота"""
    # Запускаем планировщик задач
    start_scheduler()
    logger.info("Планировщик задач запущен")

if __name__ == '__main__':
    # Регистрируем обработчик сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Запускаем миграции базы данных
    run_migrations()
    
    # Выводим информацию о запуске
    logger.info(f"Запуск {APP_NAME} v{APP_VERSION}")
    
    # Запускаем бота с указанием функции on_startup
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
    logger.info("Бот успешно запущен и готов к работе!") 