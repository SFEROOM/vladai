#!/bin/bash

# Скрипт для настройки двух ботов на Ubuntu сервере
# Запускать с sudo: sudo bash setup_two_bots.sh

echo "===== НАСТРОЙКА БОТОВ ВЛАДА И САНЬКА НА СЕРВЕРЕ ====="

# Обновление системы
echo "Обновление системы..."
apt update && apt upgrade -y

# Установка необходимых пакетов
echo "Установка необходимых пакетов..."
apt install -y python3 python3-pip python3-venv git

# Создание директории для ботов
echo "Создание директорий для ботов..."
mkdir -p /home/bots/{vlad,sanek}

#############################
# УСТАНОВКА БОТА ВЛАДА
#############################
echo "===== НАСТРОЙКА БОТА ВЛАДА ====="

# Клонирование репозитория Влада
echo "Клонирование репозитория Влада..."
cd /home/bots/vlad
git clone https://github.com/SFEROOM/vladai.git .

# Настройка конфигурации для бота Влада
echo "Настройка конфигурации для бота Влада..."
cat > /home/bots/vlad/config.py << 'EOF'
import os

# Конфигурация для ребенка Влад
CHILD_NAME = "Влад"

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = "8003507941:AAGzJz7QJQqrKKYdWPOLKPzx7xJsEfwvVJg"

# OpenAI API Configuration  
OPENAI_API_KEY = "sk-proj-nJsAOvb9QJxcxB8DJKqLT3BlbkFJcRu8LGIlTvT5aqGHPGqO"

# Database Configuration - уникальная база для каждого ребенка
DATABASE_URL = f'sqlite:///family_assistant.db'

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
EOF

# Создание виртуального окружения
echo "Настройка виртуального окружения для бота Влада..."
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate

# Создание systemd сервиса для бота Влада
echo "Создание systemd сервиса для бота Влада..."
cat > /etc/systemd/system/vlad-bot.service << EOF
[Unit]
Description=Telegram Bot Vlad
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/home/bots/vlad
ExecStart=/home/bots/vlad/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

#############################
# УСТАНОВКА БОТА САНЬКА
#############################
echo "===== НАСТРОЙКА БОТА САНЬКА ====="

# Клонирование кода для бота Санька
echo "Клонирование кода для бота Санька..."
cd /home/bots/sanek
git clone https://github.com/SFEROOM/vladai.git .

# Изменение конфигурации для бота Санька
echo "Настройка конфигурации для бота Санька..."
cat > /home/bots/sanek/config.py << EOF
import os

# Конфигурация для ребенка Санек
CHILD_NAME = "Санек"

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = "7121245928:AAGveKEg8USR1GiWt-UXnv_ltb4UVfCJFEQ"

# OpenAI API Configuration  
OPENAI_API_KEY = "sk-proj-nJsAOvb9QJxcxB8DJKqLT3BlbkFJcRu8LGIlTvT5aqGHPGqO"

# Database Configuration - уникальная база для каждого ребенка
DATABASE_URL = f'sqlite:///санек_assistant.db'

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
EOF

# Удаление существующей базы данных для Санька
echo "Удаление существующей базы данных для Санька..."
rm -f /home/bots/sanek/family_assistant.db /home/bots/sanek/sanek_assistant.db /home/bots/sanek/санек_assistant.db

# Создание виртуального окружения для Санька
echo "Настройка виртуального окружения для бота Санька..."
cd /home/bots/sanek
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate

# Создание systemd сервиса для бота Санька
echo "Создание systemd сервиса для бота Санька..."
cat > /etc/systemd/system/sanek-bot.service << EOF
[Unit]
Description=Telegram Bot Sanek
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/home/bots/sanek
ExecStart=/home/bots/sanek/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

#############################
# ЗАПУСК БОТОВ
#############################
echo "===== ЗАПУСК БОТОВ ====="

# Перезагрузка systemd
systemctl daemon-reload

# Включение и запуск ботов
systemctl enable vlad-bot
systemctl enable sanek-bot
systemctl start vlad-bot
systemctl start sanek-bot

echo "===== УСТАНОВКА ЗАВЕРШЕНА ====="
echo "Бот Влада: systemctl status vlad-bot"
echo "Бот Санька: systemctl status sanek-bot"
echo ""
echo "Для просмотра логов:"
echo "journalctl -u vlad-bot -f"
echo "journalctl -u sanek-bot -f" 