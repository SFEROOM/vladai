#!/bin/bash

# Скрипт для настройки Ubuntu-сервера для запуска бота Влада
# Запускать с sudo: sudo bash setup_server.sh

# Обновление системы
echo "Обновление системы..."
apt update && apt upgrade -y

# Установка необходимых пакетов
echo "Установка необходимых пакетов..."
apt install -y python3 python3-pip python3-venv git supervisor

# Создание директории для ботов
echo "Создание директории для ботов..."
mkdir -p /home/username/bots
cd /home/username/bots

# Клонирование репозитория (замените на свой репозиторий)
echo "Клонирование репозитория..."
if [ ! -d "vlad_bot" ]; then
    git clone https://github.com/SFEROOM/vladai.git vlad_bot
    cd vlad_bot
else
    cd vlad_bot
    git pull
fi

# Создание виртуального окружения
echo "Настройка виртуального окружения..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Создание systemd сервиса
echo "Создание systemd сервиса..."
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

# Перезагрузка systemd и запуск бота
echo "Запуск сервиса..."
systemctl daemon-reload
systemctl enable vlad-bot
systemctl start vlad-bot

echo "Настройка завершена! Бот запущен."
echo "Проверить статус: systemctl status vlad-bot" 