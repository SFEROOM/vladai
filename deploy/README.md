# Деплой бота Влада на Ubuntu сервер

## Подготовка к деплою

1. Создайте репозиторий на GitHub и загрузите туда код бота:

```bash
cd /path/to/Влад
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/yourusername/vlad_bot.git
git push -u origin main
```

2. Убедитесь, что в файле `config.py` используются правильные токены и настройки для продакшена.

## Деплой на сервер

1. Подключитесь к вашему Ubuntu серверу по SSH:

```bash
ssh username@your_server_ip
```

2. Скопируйте скрипт настройки на сервер:

```bash
scp setup_server.sh username@your_server_ip:/tmp/
```

3. Запустите скрипт настройки:

```bash
ssh username@your_server_ip "sudo bash /tmp/setup_server.sh"
```

4. Проверьте статус бота:

```bash
ssh username@your_server_ip "sudo systemctl status vlad-bot"
```

## Обновление бота

1. Внесите изменения в локальный репозиторий и отправьте их на GitHub:

```bash
git add .
git commit -m "Описание изменений"
git push
```

2. Подключитесь к серверу и запустите скрипт обновления:

```bash
ssh username@your_server_ip "sudo bash /home/botuser/vlad_bot/deploy/update_bot.sh"
```

## Управление ботом

- **Проверка статуса**: `sudo systemctl status vlad-bot`
- **Просмотр логов**: `sudo journalctl -u vlad-bot -f`
- **Перезапуск бота**: `sudo systemctl restart vlad-bot`
- **Остановка бота**: `sudo systemctl stop vlad-bot`
- **Запуск бота**: `sudo systemctl start vlad-bot`

## Настройка автоматического обновления (опционально)

Вы можете настроить GitHub Actions для автоматического деплоя при пуше в ветку main:

1. Создайте файл `.github/workflows/deploy.yml` в вашем репозитории:

```yaml
name: Deploy Bot

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - name: Deploy to server
      uses: appleboy/ssh-action@master
      with:
        host: ${{ secrets.SERVER_IP }}
        username: ${{ secrets.SERVER_USER }}
        key: ${{ secrets.SSH_PRIVATE_KEY }}
        script: sudo bash /home/botuser/vlad_bot/deploy/update_bot.sh
```

2. Добавьте секреты в настройках репозитория на GitHub:
   - `SERVER_IP`: IP-адрес вашего сервера
   - `SERVER_USER`: имя пользователя для SSH
   - `SSH_PRIVATE_KEY`: приватный SSH-ключ для доступа к серверу 