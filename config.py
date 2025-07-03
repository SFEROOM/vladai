import os

# Конфигурация для ребенка Влад
CHILD_NAME = "Влад"

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = "8003507941:AAE7bDO0Z1QIkEBEFGaAaBkwELl_PB_WIR4"

# OpenAI API Configuration
OPENAI_API_KEY = "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"

# Database Configuration
DATABASE_URL = 'sqlite:///family_assistant.db'

# Logging Configuration
LOG_LEVEL = 'INFO'

# Bot Configuration
BOT_ADMIN_IDS = []  # Добавьте ID администраторов при необходимости

# Application Configuration
APP_NAME = f"Медицинский ассистент - {CHILD_NAME}"
APP_VERSION = "1.0.0"

# Google Sheets API
GOOGLE_SHEETS_CREDENTIALS = 'credentials.json'
GOOGLE_SHEETS_SPREADSHEET_ID = None  # Установите ID таблицы при необходимости
GOOGLE_SHEETS_ENABLED = False 