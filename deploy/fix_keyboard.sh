#!/bin/bash

# Скрипт для исправления проблемы с кнопками в Telegram боте
# Запускать с sudo: sudo bash fix_keyboard.sh

echo "Исправление проблемы с кнопками в Telegram боте..."

# Путь к файлу бота
BOT_FILE="/home/username/bots/vlad_bot/bot/bot.py"
SANEK_BOT_FILE="/home/username/bots/sanek_bot/bot/bot.py"

# Проверяем наличие файла бота Влада
if [ -f "$BOT_FILE" ]; then
    echo "Исправляем кнопки в боте Влада..."
    
    # Проверяем, использует ли функция get_main_keyboard ReplyKeyboardMarkup вместо InlineKeyboardMarkup
    if grep -q "ReplyKeyboardMarkup" "$BOT_FILE"; then
        echo "Найдена проблема с типом клавиатуры, исправляем..."
        
        # Заменяем функцию get_main_keyboard на правильную версию
        sed -i '/def get_main_keyboard/,/return keyboard/ c\
# Функция для создания основной клавиатуры\
def get_main_keyboard():\
    keyboard = InlineKeyboardMarkup(row_width=2)\
    keyboard.add(\
        InlineKeyboardButton("🍼 Кормление", callback_data="feeding"),\
        InlineKeyboardButton("⚖️ Вес", callback_data="weight"),\
        InlineKeyboardButton("💩 Стул", callback_data="stool"),\
        InlineKeyboardButton("💊 Лекарства", callback_data="medication"),\
        InlineKeyboardButton("📝 Назначения", callback_data="prescriptions"),\
        InlineKeyboardButton("⏰ Напоминания", callback_data="reminders_menu"),\
        InlineKeyboardButton("📊 Статистика", callback_data="stats"),\
        InlineKeyboardButton("📋 Заметки", callback_data="notes"),\
        InlineKeyboardButton("📑 Таблица", callback_data="spreadsheet"),\
        InlineKeyboardButton("⚙️ Настройки", callback_data="settings")\
    )\
    return keyboard\
' "$BOT_FILE"
        
        echo "Функция get_main_keyboard исправлена."
    else
        echo "Функция get_main_keyboard уже использует правильный тип клавиатуры."
    fi
else
    echo "Файл бота Влада не найден по пути $BOT_FILE"
fi

# Проверяем наличие файла бота Санька
if [ -f "$SANEK_BOT_FILE" ]; then
    echo "Исправляем кнопки в боте Санька..."
    
    # Проверяем, использует ли функция get_main_keyboard ReplyKeyboardMarkup вместо InlineKeyboardMarkup
    if grep -q "ReplyKeyboardMarkup" "$SANEK_BOT_FILE"; then
        echo "Найдена проблема с типом клавиатуры, исправляем..."
        
        # Заменяем функцию get_main_keyboard на правильную версию
        sed -i '/def get_main_keyboard/,/return keyboard/ c\
# Функция для создания основной клавиатуры\
def get_main_keyboard():\
    keyboard = InlineKeyboardMarkup(row_width=2)\
    keyboard.add(\
        InlineKeyboardButton("🍼 Кормление", callback_data="feeding"),\
        InlineKeyboardButton("⚖️ Вес", callback_data="weight"),\
        InlineKeyboardButton("💩 Стул", callback_data="stool"),\
        InlineKeyboardButton("💊 Лекарства", callback_data="medication"),\
        InlineKeyboardButton("📝 Назначения", callback_data="prescriptions"),\
        InlineKeyboardButton("⏰ Напоминания", callback_data="reminders_menu"),\
        InlineKeyboardButton("📊 Статистика", callback_data="stats"),\
        InlineKeyboardButton("📋 Заметки", callback_data="notes"),\
        InlineKeyboardButton("📑 Таблица", callback_data="spreadsheet"),\
        InlineKeyboardButton("⚙️ Настройки", callback_data="settings")\
    )\
    return keyboard\
' "$SANEK_BOT_FILE"
        
        echo "Функция get_main_keyboard исправлена."
    else
        echo "Функция get_main_keyboard уже использует правильный тип клавиатуры."
    fi
else
    echo "Файл бота Санька не найден по пути $SANEK_BOT_FILE"
fi

# Перезапускаем оба бота
echo "Перезапускаем ботов..."
systemctl restart vlad-bot
systemctl restart sanek-bot

echo "Исправление завершено! Проверьте работу ботов."
echo "Статус бота Влада: systemctl status vlad-bot"
echo "Статус бота Санька: systemctl status sanek-bot" 