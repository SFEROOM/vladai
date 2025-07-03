#!/bin/bash

# Скрипт для настройки Ubuntu-сервера для запуска двух ботов: Влада и Санька
# Запускать с sudo: sudo bash setup_two_bots.sh

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

#############################
# УСТАНОВКА БОТА ВЛАДА
#############################
echo "=== НАСТРОЙКА БОТА ВЛАДА ==="

# Клонирование репозитория Влада
echo "Клонирование репозитория Влада..."
if [ ! -d "vlad_bot" ]; then
    git clone https://github.com/SFEROOM/vladai.git vlad_bot
    cd vlad_bot
else
    cd vlad_bot
    git pull
fi

# Создание виртуального окружения для Влада
echo "Настройка виртуального окружения для Влада..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

# Создание systemd сервиса для Влада
echo "Создание systemd сервиса для Влада..."
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

#############################
# УСТАНОВКА БОТА САНЬКА
#############################
echo "=== НАСТРОЙКА БОТА САНЬКА ==="

# Клонирование репозитория Санька (или копирование из Влада)
echo "Настройка репозитория Санька..."
cd /home/username/bots
if [ ! -d "sanek_bot" ]; then
    # Копируем из репозитория Влада и меняем настройки
    cp -r vlad_bot sanek_bot
    cd sanek_bot
    
    # Изменяем конфигурацию для Санька
    sed -i 's/CHILD_NAME = "Влад"/CHILD_NAME = "Санек"/g' config.py
    sed -i 's/TELEGRAM_BOT_TOKEN = "8003507941:AAE7bDO0Z1QIkEBEFGaAaBkwELl_PB_WIR4"/TELEGRAM_BOT_TOKEN = "7121245928:AAGveKEg8USR1GiWt-UXnv_ltb4UVfCJFEQ"/g' config.py
    sed -i 's/DATABASE_URL = .*/DATABASE_URL = "sqlite:\/\/\/sanek_assistant.db"/g' config.py
    
    # Удаляем старую базу данных, если она есть
    rm -f family_assistant.db sanek_assistant.db
else
    cd sanek_bot
    git pull
fi

# Создание виртуального окружения для Санька
echo "Настройка виртуального окружения для Санька..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

# Создание systemd сервиса для Санька
echo "Создание systemd сервиса для Санька..."
cat > /etc/systemd/system/sanek-bot.service << EOF
[Unit]
Description=Telegram Bot Sanek
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/home/username/bots/sanek_bot
ExecStart=/home/username/bots/sanek_bot/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

#############################
# ЗАПУСК ОБОИХ БОТОВ
#############################
echo "Перезагрузка systemd и запуск ботов..."
systemctl daemon-reload
systemctl enable vlad-bot
systemctl enable sanek-bot
systemctl start vlad-bot
systemctl start sanek-bot

echo "Настройка завершена! Оба бота запущены."
echo "Проверить статус бота Влада: systemctl status vlad-bot"
echo "Проверить статус бота Санька: systemctl status sanek-bot" 