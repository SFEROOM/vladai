# Деплой ботов на Ubuntu сервер

## Подготовка к деплою

1. Создайте репозиторий на GitHub и загрузите туда код бота Влада:

```bash
cd /Users/vladislavankovskij/Desktop/Влад
git init
git add .
git commit -m "Первоначальная загрузка кода бота"
git remote add origin https://github.com/SFEROOM/vladai.git
git push -u origin main
```

2. Убедитесь, что в файле `config.py` используются правильные токены и настройки для продакшена.

## Варианты деплоя

### Вариант 1: Деплой обоих ботов сразу

1. Подключитесь к вашему Ubuntu серверу по SSH:

```bash
ssh username@your_server_ip
```

2. Скопируйте скрипт настройки на сервер:

```bash
scp /Users/vladislavankovskij/Desktop/Влад/deploy/setup_two_bots.sh username@your_server_ip:/tmp/
```

3. Запустите скрипт настройки:

```bash
ssh username@your_server_ip "sudo bash /tmp/setup_two_bots.sh"
```

4. Проверьте статус ботов:

```bash
ssh username@your_server_ip "sudo systemctl status vlad-bot"
ssh username@your_server_ip "sudo systemctl status sanek-bot"
```

### Вариант 2: Деплой только бота Влада

1. Подключитесь к вашему Ubuntu серверу по SSH:

```bash
ssh username@your_server_ip
```

2. Скопируйте скрипт настройки на сервер:

```bash
scp /Users/vladislavankovskij/Desktop/Влад/deploy/setup_server.sh username@your_server_ip:/tmp/
```

3. Запустите скрипт настройки:

```bash
ssh username@your_server_ip "sudo bash /tmp/setup_server.sh"
```

4. Проверьте статус бота:

```bash
ssh username@your_server_ip "sudo systemctl status vlad-bot"
```

## Обновление ботов

### Обновление бота Влада

```bash
ssh username@your_server_ip "sudo bash /home/username/bots/vlad_bot/deploy/update_bot.sh"
```

### Обновление бота Санька

```bash
ssh username@your_server_ip "cd /home/username/bots/sanek_bot && sudo git pull && sudo systemctl restart sanek-bot"
```

## Просмотр логов

```bash
# Логи бота Влада
ssh username@your_server_ip "sudo journalctl -u vlad-bot -f"

# Логи бота Санька
ssh username@your_server_ip "sudo journalctl -u sanek-bot -f"
```

## Управление сервисами

```bash
# Остановка ботов
ssh username@your_server_ip "sudo systemctl stop vlad-bot"
ssh username@your_server_ip "sudo systemctl stop sanek-bot"

# Запуск ботов
ssh username@your_server_ip "sudo systemctl start vlad-bot"
ssh username@your_server_ip "sudo systemctl start sanek-bot"

# Перезапуск ботов
ssh username@your_server_ip "sudo systemctl restart vlad-bot"
ssh username@your_server_ip "sudo systemctl restart sanek-bot"
``` 