#!/bin/bash

# Скрипт для настройки Ubuntu-сервера для запуска бота Влада
# Запускать с sudo: sudo bash setup_server.sh

# Обновление системы
echo "Обновление системы..."
apt update && apt upgrade -y

# Установка необходимых пакетов
echo "Установка необходимых пакетов..."
apt install -y python3 python3-pip python3-venv git supervisor

# Создание пользователя для бота (если нужно)
if ! id -u botuser > /dev/null 2>&1; then
    echo "Создание пользователя botuser..."
    useradd -m -s /bin/bash botuser
fi

# Переход в домашнюю директорию пользователя
cd /home/botuser

# Клонирование репозитория (замените на свой репозиторий)
echo "Клонирование репозитория..."
if [ ! -d "vlad_bot" ]; then
    sudo -u botuser git clone https://github.com/yourusername/vlad_bot.git
    cd vlad_bot
else
    cd vlad_bot
    sudo -u botuser git pull
fi

# Создание виртуального окружения и установка зависимостей
echo "Настройка виртуального окружения..."
if [ ! -d "venv" ]; then
    sudo -u botuser python3 -m venv venv
fi
sudo -u botuser venv/bin/pip install -r requirements.txt

# Создание systemd сервиса для бота Влада
echo "Создание systemd сервиса..."
cat > /etc/systemd/system/vlad-bot.service << EOL
[Unit]
Description=Telegram Bot Vlad
After=network.target

[Service]
User=botuser
WorkingDirectory=/home/botuser/vlad_bot
ExecStart=/home/botuser/vlad_bot/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=vlad-bot

[Install]
WantedBy=multi-user.target
EOL

# Перезагрузка systemd и запуск сервиса
echo "Запуск сервиса..."
systemctl daemon-reload
systemctl enable vlad-bot
systemctl start vlad-bot

echo "Настройка завершена! Бот Влада запущен как systemd сервис."
echo "Проверить статус: systemctl status vlad-bot"
echo "Просмотр логов: journalctl -u vlad-bot -f" 