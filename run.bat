@echo off
echo =====================================
echo 🏥 Семейный медицинский ассистент
echo =====================================

REM Проверка наличия виртуального окружения
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Активация виртуального окружения
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Установка зависимостей
echo Installing dependencies...
pip install -q -r requirements.txt

REM Проверка наличия .env файла
if not exist ".env" (
    echo ERROR: .env file not found!
    echo Please create .env file based on env.template
    echo.
    echo copy env.template .env
    echo notepad .env
    pause
    exit /b 1
)

REM Установка PYTHONPATH
set PYTHONPATH=%PYTHONPATH%;%cd%

REM Запуск бота
echo Starting bot...
echo =====================================
python main.py

pause 