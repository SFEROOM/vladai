#!/bin/bash

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🏥 Семейный медицинский ассистент${NC}"
echo "================================"

# Проверка наличия виртуального окружения
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠️  Виртуальное окружение не найдено. Создаю...${NC}"
    python3 -m venv venv
fi

# Активация виртуального окружения
echo -e "${GREEN}✓ Активация виртуального окружения${NC}"
source venv/bin/activate

# Проверка и установка зависимостей
echo -e "${GREEN}✓ Проверка зависимостей${NC}"
pip install -q -r requirements.txt

# Проверка наличия .env файла
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ Файл .env не найден!${NC}"
    echo -e "${YELLOW}Создайте файл .env на основе env.template${NC}"
    echo "cp env.template .env"
    echo "nano .env"
    exit 1
fi

# Установка PYTHONPATH
export PYTHONPATH=$PYTHONPATH:$(pwd)

# Запуск бота
echo -e "${GREEN}🚀 Запуск бота...${NC}"
echo "================================"
python main.py 