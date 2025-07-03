#!/bin/bash

# Скрипт для обновления бота на сервере
# Запускать с sudo: sudo bash update_bot.sh

echo "Обновление бота Влада..."

# Переход в директорию проекта
cd /home/username/bots/vlad_bot

# Получение последних изменений из репозитория
echo "Получение последних изменений из репозитория..."
git pull

# Обновление зависимостей
echo "Обновление зависимостей..."
source venv/bin/activate
pip install -r requirements.txt

# Перезапуск сервиса
echo "Перезапуск сервиса бота..."
systemctl restart vlad-bot

echo "Обновление завершено! Бот перезапущен."
echo "Проверить статус: systemctl status vlad-bot" 