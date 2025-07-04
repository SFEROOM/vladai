# Инструкция по деплою ботов на Ubuntu сервер

## Требования
- Ubuntu 20.04 или выше
- Доступ к серверу по SSH с правами sudo
- Открытый доступ к интернету для установки пакетов

## Быстрая установка двух ботов (Влад и Санек)

1. Подключитесь к серверу по SSH:
```bash
ssh user@your-server-ip
```

2. Скачайте и запустите скрипт установки:
```bash
# Скачиваем скрипт
wget https://raw.githubusercontent.com/SFEROOM/vladai/main/deploy/setup_two_bots.sh

# Делаем скрипт исполняемым
chmod +x setup_two_bots.sh

# Запускаем установку
sudo ./setup_two_bots.sh
```

3. После установки проверьте статус ботов:
```bash
# Статус бота Влада
sudo systemctl status vlad-bot

# Статус бота Санька
sudo systemctl status sanek-bot
```

## Управление ботами

### Остановка ботов:
```bash
sudo systemctl stop vlad-bot
sudo systemctl stop sanek-bot
```

### Запуск ботов:
```bash
sudo systemctl start vlad-bot
sudo systemctl start sanek-bot
```

### Перезапуск ботов:
```bash
sudo systemctl restart vlad-bot
sudo systemctl restart sanek-bot
```

### Просмотр логов:
```bash
# Логи бота Влада
sudo journalctl -u vlad-bot -f

# Логи бота Санька
sudo journalctl -u sanek-bot -f
```

## Обновление ботов

Для обновления используйте скрипт:
```bash
cd /home/bots/vlad
sudo ./deploy/update_bot.sh

cd /home/bots/sanek
sudo ./deploy/update_bot.sh
```

## Структура на сервере

```
/home/bots/
├── vlad/          # Бот для Влада
│   ├── venv/      # Виртуальное окружение
│   ├── main.py    # Главный файл
│   ├── config.py  # Конфигурация
│   └── family_assistant.db  # База данных
│
└── sanek/         # Бот для Санька
    ├── venv/      # Виртуальное окружение
    ├── main.py    # Главный файл
    ├── config.py  # Конфигурация
    └── sanek_assistant.db  # База данных
```

## Важные замечания

1. **Токены ботов**: Убедитесь, что используете правильные токены для каждого бота
2. **База данных**: Каждый бот использует свою базу данных
3. **Миграции**: При первом запуске автоматически применяются все миграции
4. **Автозапуск**: Боты настроены на автоматический запуск при перезагрузке сервера

## Решение проблем

### Бот не запускается
1. Проверьте логи: `sudo journalctl -u vlad-bot -n 50`
2. Проверьте токен бота в config.py
3. Убедитесь, что порт не занят другим процессом

### Ошибки с базой данных
1. Удалите базу данных и перезапустите бота:
```bash
sudo rm /home/bots/vlad/family_assistant.db
sudo systemctl restart vlad-bot
```

### Проблемы с зависимостями
1. Активируйте виртуальное окружение и переустановите зависимости:
```bash
cd /home/bots/vlad
source venv/bin/activate
pip install -r requirements.txt --upgrade
deactivate
sudo systemctl restart vlad-bot
``` 