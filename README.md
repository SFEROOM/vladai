# 🏥 Интеллектуальный семейный медицинский ассистент в Telegram

## 📋 Описание
Telegram-бот для управления здоровьем семьи с AI-консультациями на базе OpenAI GPT.

## 🚀 Возможности
- 🍼 Отслеживание кормлений (количество, тип питания)
- ⚖️ Контроль веса ребенка
- 💩 Учет стула
- 💊 Управление приемом лекарств
- 🤖 AI-консультации по здоровью
- ⏰ Автоматические напоминания
- 📊 Статистика и отчеты
- 📱 Удобный Telegram интерфейс

## 📁 Структура проекта
```
аи/
├── bot/           # Код Telegram-бота
├── ai/            # AI ассистент (OpenAI GPT)
├── database/      # Модели и работа с БД
├── scheduler/     # Планировщик задач
├── config.py      # Конфигурация
├── main.py        # Главный файл запуска
└── requirements.txt
```

## 🛠 Установка

### 1. Клонирование репозитория
```bash
git clone <repository-url>
cd аи
```

### 2. Создание виртуального окружения
```bash
python3 -m venv venv
source venv/bin/activate  # Для Linux/Mac
# или
venv\Scripts\activate  # Для Windows
```

### 3. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 4. Настройка переменных окружения
Создайте файл `.env` в корне проекта:
```env
# Telegram Bot
TELEGRAM_BOT_TOKEN=your_telegram_bot_token

# OpenAI API
OPENAI_API_KEY=your_openai_api_key

# База данных
DATABASE_URL=sqlite:///./family_assistant.db

# Логирование
LOG_LEVEL=INFO
```

### 5. Получение токенов
- **Telegram Bot Token**: Создайте бота через [@BotFather](https://t.me/botfather)
- **OpenAI API Key**: Получите на [platform.openai.com](https://platform.openai.com/api-keys)

## 🚀 Запуск

### Основной способ:
```bash
python main.py
```

### Альтернативный способ:
```bash
cd bot
python bot.py
```

## 💻 Использование

### Основные команды:
- `/start` - Начать работу/регистрация ребенка
- `/menu` - Главное меню
- `/help` - Справка по командам
- `/ai` - Активировать AI консультанта
- `/stats` - Показать статистику
- `/reminders` - Управление напоминаниями

### Процесс работы:
1. При первом запуске зарегистрируйте ребенка
2. Используйте главное меню для записи данных
3. Задавайте вопросы AI ассистенту в любое время
4. Получайте автоматические напоминания и отчеты

## 🔧 Дополнительная настройка

### Настройка напоминаний:
Планировщик автоматически:
- Проверяет интервалы между кормлениями
- Отправляет ежедневные отчеты в 21:00
- Обрабатывает пользовательские напоминания

### База данных:
SQLite база данных создается автоматически при первом запуске.
Для миграции на PostgreSQL измените `DATABASE_URL` в `.env`.

## 🐛 Решение проблем

### Ошибка импорта модулей:
```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)
```

### Ошибка с токенами:
Убедитесь, что файл `.env` создан и содержит корректные токены.

### Ошибка базы данных:
Удалите файл `family_assistant.db` для пересоздания БД.

## 🔒 Безопасность
- Никогда не публикуйте файл `.env`
- Добавьте `.env` в `.gitignore`
- Регулярно обновляйте зависимости
- Используйте отдельные токены для разработки и продакшена

## 📝 TODO
- [ ] Веб-интерфейс для визуализации данных
- [ ] Экспорт данных в PDF/Excel
- [ ] Поддержка нескольких детей
- [ ] Интеграция с медицинскими API
- [ ] Мобильное приложение

## 👥 Поддержка
При возникновении проблем создайте issue в репозитории.

## 📄 Лицензия
MIT License 