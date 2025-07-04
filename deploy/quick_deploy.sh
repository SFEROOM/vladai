#!/bin/bash

# Быстрый деплой ботов на сервер
# Использование: ./quick_deploy.sh user@server-ip

if [ -z "$1" ]; then
    echo "Использование: ./quick_deploy.sh user@server-ip"
    exit 1
fi

SERVER=$1
SCRIPT_URL="https://raw.githubusercontent.com/SFEROOM/vladai/main/deploy/setup_two_bots.sh"

echo "===== БЫСТРЫЙ ДЕПЛОЙ БОТОВ НА СЕРВЕР $SERVER ====="

# Загружаем и запускаем скрипт установки на сервере
ssh $SERVER "
    echo 'Загрузка скрипта установки...'
    wget -O /tmp/setup_two_bots.sh $SCRIPT_URL
    chmod +x /tmp/setup_two_bots.sh
    echo 'Запуск установки (требуются права sudo)...'
    sudo /tmp/setup_two_bots.sh
"

echo "===== УСТАНОВКА ЗАВЕРШЕНА ====="
echo "Проверьте статус ботов:"
echo "ssh $SERVER 'sudo systemctl status vlad-bot'"
echo "ssh $SERVER 'sudo systemctl status sanek-bot'" 