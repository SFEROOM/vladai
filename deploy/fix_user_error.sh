#!/bin/bash

# Скрипт для исправления ошибки с пользователем (код 217/USER) в systemd сервисе
# Запускать с sudo: sudo bash fix_user_error.sh

echo "Исправление ошибки с пользователем в systemd сервисе..."

# Остановка сервиса, если он запущен
systemctl stop vlad-bot

# Обновление конфигурации сервиса
cat > /etc/systemd/system/vlad-bot.service << EOF
[Unit]
Description=Telegram Bot Vlad
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/home/username/bots/vlad_bot
ExecStart=/home/username/bots/vlad_bot/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Перезагрузка systemd и запуск сервиса
systemctl daemon-reload
systemctl start vlad-bot

echo "Исправление завершено! Проверьте статус сервиса:"
systemctl status vlad-bot 