from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
import logging
import openai
from sqlalchemy.orm import Session
import sys
import os
import io
import tempfile
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import get_db, SessionLocal
from database.models import Child, Reminder, Appointment, Feeding, Stool, Weight, Medication, Prescription, Note, ChatHistory, User
from config import TELEGRAM_BOT_TOKEN, OPENAI_API_KEY, LOG_LEVEL, GOOGLE_SHEETS_ENABLED, GOOGLE_SHEETS_SPREADSHEET_ID
import re
from datetime import datetime, timedelta
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# Configure logging
logging.basicConfig(level=getattr(logging, LOG_LEVEL))
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(token=TELEGRAM_BOT_TOKEN, parse_mode=ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

# Configure OpenAI
openai.api_key = OPENAI_API_KEY

# Import AI assistant
from ai.assistant import MedicalAIAssistant
from ai.reminder_parser import ReminderParser

# Initialize AI assistant
ai_assistant = MedicalAIAssistant(OPENAI_API_KEY)

# Initialize reminder parser
reminder_parser = ReminderParser(OPENAI_API_KEY)

# Define states
class FeedingState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_food_type = State()

class StoolState(StatesGroup):
    waiting_for_description = State()

class WeightState(StatesGroup):
    waiting_for_weight = State()

class MedicationState(StatesGroup):
    waiting_for_name = State()
    waiting_for_dosage = State()

class PrescriptionState(StatesGroup):
    waiting_for_full_text = State()
    waiting_for_start_date = State()
    waiting_for_end_date = State()

class ChildRegistrationState(StatesGroup):
    waiting_for_name = State()
    waiting_for_birth_date = State()
    waiting_for_gender = State()

class ReminderState(StatesGroup):
    waiting_for_description = State()
    waiting_for_time = State()
    waiting_for_date = State()  # Новое состояние для выбора даты
    waiting_for_repeat_type = State()
    waiting_for_repeat_interval = State()
    waiting_for_edit_field = State()
    waiting_for_new_description = State()
    waiting_for_new_time = State()
    waiting_for_new_date = State()  # Новое состояние для редактирования даты
    waiting_for_new_repeat_type = State()
    waiting_for_new_repeat_interval = State()

class NotesState(StatesGroup):
    waiting_for_title = State()
    waiting_for_content = State()
    waiting_for_edit_content = State()

async def save_user(user_data: types.User, db: Session):
    """Сохраняет или обновляет информацию о пользователе в базе данных"""
    try:
        # Проверяем, существует ли пользователь
        user = db.query(User).filter_by(telegram_id=user_data.id).first()
        
        if not user:
            # Создаем нового пользователя
            user = User(
                telegram_id=user_data.id,
                username=user_data.username,
                first_name=user_data.first_name,
                last_name=user_data.last_name,
                is_active=1
            )
            db.add(user)
            logger.info(f"Добавлен новый пользователь: {user_data.id} ({user_data.username})")
        else:
            # Обновляем информацию о пользователе
            user.username = user_data.username
            user.first_name = user_data.first_name
            user.last_name = user_data.last_name
            user.updated_at = datetime.now()
            user.is_active = 1
            
        db.commit()
    except Exception as e:
        logger.error(f"Ошибка при сохранении пользователя: {e}")
        db.rollback()

@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    """Обработка команды /start"""
    db: Session = next(get_db())
    try:
        # Сохраняем информацию о пользователе
        await save_user(message.from_user, db)
        
        # Проверяем, есть ли зарегистрированный ребенок
        child = db.query(Child).first()
        if child:
            await show_main_menu(message)
        else:
            await message.reply(
                f"👋 Привет, {message.from_user.first_name}!\n\n"
                "Я - ваш семейный медицинский ассистент. "
                "Я помогу вам отслеживать здоровье вашего ребенка.\n\n"
                "Для начала давайте зарегистрируем ребенка.\n"
                "Введите имя ребенка:",
                reply_markup=types.ReplyKeyboardRemove()
            )
            await ChildRegistrationState.waiting_for_name.set()
    finally:
        db.close()

@dp.message_handler(commands=['help'])
async def send_help(message: types.Message):
    """Справка по командам"""
    help_text = """
📋 *Доступные команды:*

/start - Начать работу
/menu - Главное меню
/reminders - Показать напоминания
/stats - Статистика и анализ развития
/ai - Задать вопрос AI ассистенту
/reset - Сбросить историю диалога с AI
/help - Эта справка

🔸 *Основные функции:*
• Отслеживание кормлений
• Учет веса ребенка
• Запись о стуле
• Контроль приема лекарств
• Гибкие напоминания с повторениями
• AI-консультации с памятью контекста
• Анализ развития ребенка

🔹 *Текстовые команды:*
• "статистика", "сводка", "анализ", "развитие" - Получить сводку о развитии ребенка
• "напомни...", "напоминай..." - Создать напоминание из текста

🔸 *Примеры создания напоминаний:*
• "Напомни мне принять лекарство в 13:00"
• "Напоминай мне каждый день в 9:00 делать зарядку"
• "Напоминай мне каждую неделю в понедельник посетить врача"

_Выберите нужную функцию в главном меню_
"""
    await message.reply(help_text, parse_mode=ParseMode.MARKDOWN)

# Handlers for child registration
@dp.message_handler(state=ChildRegistrationState.waiting_for_name)
async def process_child_name(message: types.Message, state: FSMContext):
    """Обработка имени ребенка"""
    await state.update_data(name=message.text)
    await message.reply("Введите дату рождения ребенка (в формате ДД.ММ.ГГГГ):")
    await ChildRegistrationState.waiting_for_birth_date.set()

@dp.message_handler(state=ChildRegistrationState.waiting_for_birth_date)
async def process_birth_date(message: types.Message, state: FSMContext):
    """Обработка даты рождения"""
    try:
        birth_date = datetime.strptime(message.text, "%d.%m.%Y").date()
        await state.update_data(birth_date=birth_date)
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton("Мальчик", callback_data='gender_male'),
            InlineKeyboardButton("Девочка", callback_data='gender_female')
        )
        await message.reply("Выберите пол ребенка:", reply_markup=keyboard)
        await ChildRegistrationState.waiting_for_gender.set()
    except ValueError:
        await message.reply("❌ Неверный формат даты. Пожалуйста, введите дату в формате ДД.ММ.ГГГГ")

@dp.callback_query_handler(lambda c: c.data.startswith('gender_'), state=ChildRegistrationState.waiting_for_gender)
async def process_gender(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработка выбора пола"""
    gender = 'Мальчик' if callback_query.data == 'gender_male' else 'Девочка'
    data = await state.get_data()
    
    db: Session = next(get_db())
    try:
        child = Child(
            name=data['name'],
            birth_date=data['birth_date'],
            gender=gender
        )
        db.add(child)
        db.commit()
        
        await bot.send_message(
            callback_query.from_user.id,
            f"✅ Ребенок {data['name']} успешно зарегистрирован!"
        )
        await show_main_menu(callback_query.message)
        await state.finish()
    except Exception as e:
        logger.error(f"Ошибка при сохранении ребенка: {e}")
        await bot.send_message(
            callback_query.from_user.id,
            "❌ Произошла ошибка при сохранении. Попробуйте позже."
        )
        await state.finish()
    finally:
        db.close()

# Function to show reminders menu
async def show_reminders_menu(message: types.Message):
    """Показать меню управления напоминаниями"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("📝 Все напоминания", callback_data='reminders_list'),
        InlineKeyboardButton("➕ Создать напоминание", callback_data='reminder_create'),
        InlineKeyboardButton("📊 Статистика", callback_data='reminders_stats'),
        InlineKeyboardButton("🔙 Назад в меню", callback_data='back_to_menu')
    )
    await message.reply("⏰ *Управление напоминаниями*\nВыберите действие:", 
                       reply_markup=keyboard, 
                       parse_mode=ParseMode.MARKDOWN)

# Function to show all reminders
async def show_reminders_list(callback_query: types.CallbackQuery):
    """Показать список всех напоминаний"""
    db: Session = next(get_db())
    try:
        child = db.query(Child).first()
        if not child:
            await bot.send_message(
                callback_query.from_user.id,
                "Информация о ребенке отсутствует. Пожалуйста, зарегистрируйте ребенка."
            )
            return
        
        # Получаем все активные напоминания
        reminders = db.query(Reminder).filter(
            Reminder.child_id == child.id,
            Reminder.status == 'active'
        ).order_by(Reminder.reminder_time).all()
        
        if not reminders:
            # Создаем клавиатуру с кнопками
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                InlineKeyboardButton("➕ Добавить напоминание", callback_data="reminder_create"),
                InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")
            )
            
            await bot.send_message(
                callback_query.from_user.id,
                "У вас нет активных напоминаний.",
                reply_markup=keyboard
            )
            return
        
        # Создаем клавиатуру с кнопками для каждого напоминания и кнопками действий
        keyboard = InlineKeyboardMarkup(row_width=2)
        
        for reminder in reminders:
            # Форматируем время
            time_str = reminder.reminder_time.strftime("%H:%M")
            
            # Форматируем дату
            if reminder.repeat_type == 'once':
                date_str = reminder.reminder_time.strftime("%d.%m.%Y")
                button_text = f"⏰ {time_str} {date_str} - {reminder.description}"
            else:
                if reminder.repeat_type == 'daily':
                    repeat_text = "ежедневно"
                elif reminder.repeat_type == 'weekly':
                    repeat_text = "еженедельно"
                elif reminder.repeat_type == 'monthly':
                    repeat_text = "ежемесячно"
                elif reminder.repeat_type == 'hourly':
                    repeat_text = f"каждые {reminder.repeat_interval} час(ов)"
                else:
                    repeat_text = "повтор"
                button_text = f"⏰ {time_str} ({repeat_text}) - {reminder.description}"
            
            # Добавляем кнопку с напоминанием
            keyboard.add(
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"reminder_view_{reminder.id}"
                )
            )
            
            # Добавляем кнопки действий для этого напоминания
            keyboard.row(
                InlineKeyboardButton("✅ Выполнено", callback_data=f"reminder_complete_{reminder.id}"),
                InlineKeyboardButton("⏭️ Пропустить", callback_data=f"reminder_skip_{reminder.id}")
            )
        
        # Добавляем кнопки навигации
        keyboard.add(
            InlineKeyboardButton("➕ Добавить напоминание", callback_data="reminder_create"),
            InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")
        )
        
        await bot.send_message(
            callback_query.from_user.id,
            "📋 *Список активных напоминаний*\n\n"
            "Выберите напоминание для просмотра или отметьте его выполнение/пропуск:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка при отображении списка напоминаний: {e}")
        await bot.send_message(
            callback_query.from_user.id,
            "❌ Произошла ошибка при загрузке напоминаний"
        )
    finally:
        db.close()

# Function to view a specific reminder
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('reminder_view_'))
async def view_reminder(callback_query: types.CallbackQuery):
    """Просмотр напоминания"""
    await bot.answer_callback_query(callback_query.id)
    
    # Получаем ID напоминания из callback_data
    reminder_id = int(callback_query.data.split('_')[2])
    
    db: Session = next(get_db())
    try:
        # Получаем напоминание
        reminder = db.query(Reminder).get(reminder_id)
        if not reminder:
            await bot.send_message(
                callback_query.from_user.id,
                "❌ Напоминание не найдено"
            )
            return
        
        # Форматируем информацию о напоминании
        time_str = reminder.reminder_time.strftime("%H:%M")
        
        # Форматируем дату
        if reminder.repeat_type == 'once':
            date_str = reminder.reminder_time.strftime("%d.%m.%Y")
        else:
            date_str = "Повторяющееся"
        
        # Форматируем повторение
        if reminder.repeat_type == 'once':
            repeat_str = "Однократно"
        elif reminder.repeat_type == 'daily':
            repeat_str = "Ежедневно"
        elif reminder.repeat_type == 'weekly':
            repeat_str = "Еженедельно"
        elif reminder.repeat_type == 'monthly':
            repeat_str = "Ежемесячно"
        elif reminder.repeat_type == 'hourly':
            repeat_str = f"Каждые {reminder.repeat_interval} час(ов)"
        elif reminder.repeat_type == 'custom':
            repeat_str = f"Каждые {reminder.repeat_interval} дней"
        else:
            repeat_str = "Неизвестно"
        
        # Создаем клавиатуру с кнопками
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("✏️ Редактировать", callback_data=f"reminder_edit_{reminder.id}"),
            InlineKeyboardButton("🗑️ Удалить", callback_data=f"reminder_delete_{reminder.id}")
        )
        keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="reminders_list"))
        
        # Отправляем информацию о напоминании
        await bot.send_message(
            callback_query.from_user.id,
            f"⏰ *Напоминание*\n\n"
            f"📝 *Описание:* {reminder.description}\n"
            f"⏰ *Время:* {time_str}\n"
            f"📅 *Дата:* {date_str}\n"
            f"🔄 *Повторение:* {repeat_str}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка при просмотре напоминания: {e}")
        await bot.send_message(
            callback_query.from_user.id,
            "❌ Произошла ошибка при загрузке напоминания"
        )
    finally:
        db.close()

# Function to handle callback queries for reminders menu
@dp.callback_query_handler(lambda c: c.data == 'reminders_menu')
async def process_reminders_menu_callback(callback_query: types.CallbackQuery):
    """Обработка выбора меню напоминаний"""
    await bot.answer_callback_query(callback_query.id)
    await show_reminders_menu(callback_query.message)

# Function to handle callback for reminders list
@dp.callback_query_handler(lambda c: c.data == 'reminders_list')
async def process_reminders_list_callback(callback_query: types.CallbackQuery):
    """Обработка выбора списка напоминаний"""
    await bot.answer_callback_query(callback_query.id)
    await show_reminders_list(callback_query)

# Function to handle callback for back to main menu
@dp.callback_query_handler(lambda c: c.data == 'back_to_menu')
async def process_back_to_menu(callback_query: types.CallbackQuery):
    """Возврат в главное меню"""
    await bot.answer_callback_query(callback_query.id)
    await show_main_menu(callback_query.message)

# Add a command to show reminders
@dp.message_handler(commands=['reminders'])
async def reminders_command(message: types.Message):
    """Команда для показа меню напоминаний"""
    await show_reminders_menu(message)

# Add a command to show reminders
@dp.message_handler(commands=['reminders'])
async def reminders_command(message: types.Message):
    await show_reminders(message)

# Function to show main menu with options
async def show_main_menu(message: types.Message):
    """Показать главное меню"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🍼 Кормление", callback_data='feeding'),
        InlineKeyboardButton("⚖️ Вес", callback_data='weight'),
        InlineKeyboardButton("💩 Стул", callback_data='stool'),
        InlineKeyboardButton("📝 Назначения", callback_data='prescriptions'),
        InlineKeyboardButton("⏰ Напоминания", callback_data='reminders_menu'),
        InlineKeyboardButton("📊 Статистика", callback_data='stats'),
        InlineKeyboardButton("📋 Заметки", callback_data='notes'),
        InlineKeyboardButton("📑 Таблица", callback_data='spreadsheet'),
        InlineKeyboardButton("⚙️ Настройки", callback_data='settings')
    )
    await message.reply("🏥 *Главное меню*\nВыберите действие:", 
                       reply_markup=keyboard, 
                       parse_mode=ParseMode.MARKDOWN)

# Function to handle callback queries for main menu
@dp.callback_query_handler(lambda c: c.data in ['feeding', 'stool', 'weight', 'reminders_menu', 'stats', 'prescriptions', 'spreadsheet', 'settings', 'notes'])
async def process_main_menu(callback_query: types.CallbackQuery):
    """Обработка выбора из главного меню"""
    action = callback_query.data
    db: Session = next(get_db())
    child = db.query(Child).first()
    
    if action == 'reminders_menu':
        await bot.answer_callback_query(callback_query.id)
        await show_reminders_menu(callback_query.message)
        return
        
    if action == 'stats':
        await bot.answer_callback_query(callback_query.id)
        await bot.send_message(
            callback_query.from_user.id,
            "🔄 Анализирую данные о развитии ребенка..."
        )
        try:
            # Генерируем сводку о развитии с помощью ИИ
            summary = ai_assistant.generate_development_summary(db)
            
            # Форматируем ответ
            response = f"📊 *Сводка о развитии ребенка*\n\n{summary}"
            
            # Добавляем кнопку возврата в меню
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("🔙 Назад в меню", callback_data='back_to_menu'))
            
            await bot.send_message(
                callback_query.from_user.id,
                response,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Ошибка при генерации сводки: {e}")
            await bot.send_message(
                callback_query.from_user.id,
                "❌ Произошла ошибка при анализе данных. Пожалуйста, попробуйте позже."
            )
        finally:
            db.close()
        return
    
    if action == 'notes':
        await bot.answer_callback_query(callback_query.id)
        try:
            # Получаем список заметок
            notes = db.query(Note).filter(Note.child_id == child.id).order_by(Note.timestamp.desc()).all()
            
            if not notes:
                # Создаем inline клавиатуру
                keyboard = InlineKeyboardMarkup(row_width=1)
                keyboard.add(
                    InlineKeyboardButton("📝 Добавить заметку", callback_data="add_note"),
                    InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")
                )
                
                await bot.send_message(
                    callback_query.from_user.id,
                    "У вас пока нет сохраненных заметок.",
                    reply_markup=keyboard
                )
                return
            
            # Создаем inline клавиатуру для списка заметок
            keyboard = InlineKeyboardMarkup(row_width=1)
            for note in notes:
                date_str = note.timestamp.strftime("%d.%m.%Y, %H:%M")
                keyboard.add(InlineKeyboardButton(
                    text=f"{note.title} ({date_str})",
                    callback_data=f"note_{note.id}"
                ))
            
            # Добавляем кнопки действий
            keyboard.add(
                InlineKeyboardButton("📝 Добавить заметку", callback_data="add_note"),
                InlineKeyboardButton("🔙 Назад в меню", callback_data="back_to_menu")
            )
            
            await bot.send_message(
                callback_query.from_user.id,
                "Список ваших заметок:",
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Ошибка при отображении заметок: {e}")
            await bot.send_message(
                callback_query.from_user.id,
                "❌ Произошла ошибка при загрузке заметок."
            )
        finally:
            db.close()
        return
        
    if action == 'feeding':
        await bot.answer_callback_query(callback_query.id)
        
        # Получаем последние 7 кормлений
        last_feedings = db.query(Feeding).filter_by(child_id=child.id).order_by(Feeding.timestamp.desc()).limit(7).all()
        
        if last_feedings:
            # Формируем список кормлений
            feedings_text = "🍼 *Последние 7 кормлений:*\n\n"
            for feeding in last_feedings:
                date_str = feeding.timestamp.strftime("%d.%m.%Y, %H:%M")
                food_type_emoji = "🤱" if feeding.food_type == "Грудное молоко" else "🍼" if feeding.food_type == "Смесь" else "🥄"
                feedings_text += f"{food_type_emoji} {date_str} - {feeding.amount} мл ({feeding.food_type})\n"
            
            # Генерируем AI сводку
            await bot.send_message(
                callback_query.from_user.id,
                feedings_text,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Отправляем сообщение о генерации сводки
            await bot.send_message(
                callback_query.from_user.id,
                "🤖 Анализирую данные о кормлениях..."
            )
            
            # Генерируем AI сводку по кормлениям
            feeding_summary = ai_assistant.generate_feeding_summary(db)
            
            # Создаем клавиатуру
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("➕ Добавить кормление", callback_data='add_feeding'),
                InlineKeyboardButton("📊 Статистика", callback_data='feeding_stats'),
                InlineKeyboardButton("🔙 Назад в меню", callback_data='back_to_menu')
            )
            
            await bot.send_message(
                callback_query.from_user.id,
                f"📊 *AI Анализ кормлений:*\n\n{feeding_summary}",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
        else:
            # Если нет данных о кормлениях
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                InlineKeyboardButton("➕ Добавить первое кормление", callback_data='add_feeding'),
                InlineKeyboardButton("🔙 Назад в меню", callback_data='back_to_menu')
            )
            
            await bot.send_message(
                callback_query.from_user.id,
                "У вас пока нет записей о кормлениях.",
                reply_markup=keyboard
            )
        
        db.close()
        return

    elif action == 'stool':
        await bot.answer_callback_query(callback_query.id)
        
        # Получаем последние 7 записей о стуле
        last_stools = db.query(Stool).filter_by(child_id=child.id).order_by(Stool.timestamp.desc()).limit(7).all()
        
        if last_stools:
            # Формируем список записей о стуле
            stools_text = "💩 *Последние 7 записей о стуле:*\n\n"
            for stool in last_stools:
                date_str = stool.timestamp.strftime("%d.%m.%Y, %H:%M")
                color_text = f" ({stool.color})" if stool.color else ""
                stools_text += f"📝 {date_str} - {stool.description}{color_text}\n"
            
            await bot.send_message(
                callback_query.from_user.id,
                stools_text,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Генерируем AI сводку
            await bot.send_message(
                callback_query.from_user.id,
                "🤖 Анализирую данные о пищеварении..."
            )
            
            stool_summary = ai_assistant.generate_stool_summary(db)
            
            # Создаем клавиатуру
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("➕ Добавить запись", callback_data='add_stool'),
                InlineKeyboardButton("🔙 Назад в меню", callback_data='back_to_menu')
            )
            
            await bot.send_message(
                callback_query.from_user.id,
                f"📊 *AI Анализ пищеварения:*\n\n{stool_summary}",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
        else:
            # Если нет данных о стуле
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                InlineKeyboardButton("➕ Добавить первую запись", callback_data='add_stool'),
                InlineKeyboardButton("🔙 Назад в меню", callback_data='back_to_menu')
            )
            
            await bot.send_message(
                callback_query.from_user.id,
                "У вас пока нет записей о стуле ребенка.",
                reply_markup=keyboard
            )
        
        db.close()
        return

    elif action == 'weight':
        await bot.answer_callback_query(callback_query.id)
        
        # Получаем последние 7 записей о весе
        last_weights = db.query(Weight).filter_by(child_id=child.id).order_by(Weight.timestamp.desc()).limit(7).all()
        
        if last_weights:
            # Формируем список измерений веса
            weights_text = "⚖️ *Последние 7 измерений веса:*\n\n"
            for weight in last_weights:
                date_str = weight.timestamp.strftime("%d.%m.%Y, %H:%M")
                weights_text += f"📊 {date_str} - {weight.weight} кг\n"
            
            # Вычисляем прирост за неделю
            if len(last_weights) > 1:
                current_weight = last_weights[0].weight
                week_ago_weight = last_weights[-1].weight
                week_gain = current_weight - week_ago_weight
                
                # Прирост за последние сутки
                day_gain = 0
                yesterday = datetime.now() - timedelta(days=1)
                for i in range(1, len(last_weights)):
                    if last_weights[i].timestamp >= yesterday:
                        day_gain = current_weight - last_weights[i].weight
                        break
                
                weights_text += f"\n📈 *Изменения:*\n"
                weights_text += f"• За последние сутки: {day_gain:+.2f} кг\n"
                weights_text += f"• За неделю: {week_gain:+.2f} кг\n"
            
            await bot.send_message(
                callback_query.from_user.id,
                weights_text,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Генерируем AI сводку
            await bot.send_message(
                callback_query.from_user.id,
                "🤖 Анализирую динамику веса..."
            )
            
            weight_summary = ai_assistant.generate_weight_summary(db)
            
            # Создаем клавиатуру
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("➕ Добавить вес", callback_data='add_weight'),
                InlineKeyboardButton("📊 График", callback_data='weight_chart'),
                InlineKeyboardButton("🔙 Назад в меню", callback_data='back_to_menu')
            )
            
            await bot.send_message(
                callback_query.from_user.id,
                f"📊 *AI Анализ веса:*\n\n{weight_summary}",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
        else:
            # Если нет данных о весе
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                InlineKeyboardButton("➕ Добавить первое измерение", callback_data='add_weight'),
                InlineKeyboardButton("🔙 Назад в меню", callback_data='back_to_menu')
            )
            
            await bot.send_message(
                callback_query.from_user.id,
                "У вас пока нет записей о весе ребенка.",
                reply_markup=keyboard
            )
        
        db.close()
        return



    elif action == 'prescriptions':
        await bot.answer_callback_query(callback_query.id)
        try:
            # Получаем список назначений
            prescriptions = db.query(Prescription).filter(
                Prescription.child_id == child.id,
                Prescription.is_active == 1
            ).order_by(Prescription.start_date.desc()).all()
            
            if not prescriptions:
                # Создаем клавиатуру с кнопками
                keyboard = InlineKeyboardMarkup(row_width=2)
                keyboard.add(
                    InlineKeyboardButton("➕ Добавить назначение", callback_data='add_prescription'),
                    InlineKeyboardButton("🔙 Назад в меню", callback_data='back_to_menu')
                )
                
                await bot.send_message(
                    callback_query.from_user.id,
                    "📋 *Назначения врачей*\n\n"
                    "У вас пока нет активных назначений.",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard
                )
                return
            
            # Формируем сообщение со списком назначений
            message_text = "📋 *Активные назначения врачей:*\n\n"
            
            for i, prescription in enumerate(prescriptions, 1):
                end_date_text = f"до {prescription.end_date.strftime('%d.%m.%Y')}" if prescription.end_date else "бессрочно"
                doctor_text = f"Врач: {prescription.doctor_name}\n" if prescription.doctor_name else ""
                
                # Если есть полный текст назначения, показываем его
                if prescription.full_text:
                    message_text += (
                        f"{i}. *{prescription.medication_name}*\n"
                        f"📄 *Полное назначение:*\n{prescription.full_text}\n"
                        f"📅 Период: с {prescription.start_date.strftime('%d.%m.%Y')} {end_date_text}\n\n"
                    )
                else:
                    # Иначе показываем стандартную информацию
                    message_text += (
                        f"{i}. *{prescription.medication_name}*\n"
                        f"💊 Дозировка: {prescription.dosage}\n"
                        f"🕒 Частота: {prescription.frequency}\n"
                        f"{doctor_text}"
                        f"📅 Период: с {prescription.start_date.strftime('%d.%m.%Y')} {end_date_text}\n"
                    )
                    
                    if prescription.notes:
                        message_text += f"📝 Примечание: {prescription.notes}\n"
                
                message_text += "\n"
            
            # Создаем клавиатуру с кнопками
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("➕ Добавить назначение", callback_data='add_prescription'),
                InlineKeyboardButton("✏️ Редактировать", callback_data='edit_prescriptions'),
                InlineKeyboardButton("➕ Создать напоминания", callback_data='create_all_prescription_reminders'),
                InlineKeyboardButton("🔙 Назад в меню", callback_data='back_to_menu')
            )
            
            await bot.send_message(
                callback_query.from_user.id,
                message_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Ошибка при отображении назначений: {e}")
            await bot.send_message(
                callback_query.from_user.id,
                "❌ Произошла ошибка при загрузке назначений."
            )
        finally:
            db.close()
        return

    elif action == 'spreadsheet':
        await bot.answer_callback_query(callback_query.id)
        try:
            # Проверяем, включена ли интеграция с Google Sheets
            if not GOOGLE_SHEETS_ENABLED:
                # Создаем клавиатуру для настройки
                keyboard = InlineKeyboardMarkup(row_width=1)
                keyboard.add(
                    InlineKeyboardButton("🔙 Назад в меню", callback_data='back_to_menu')
                )
                
                await bot.send_message(
                    callback_query.from_user.id,
                    "📑 *Google Sheets интеграция*\n\n"
                    "Интеграция с Google Sheets отключена. Чтобы включить её:\n\n"
                    "1. Создайте проект в Google Cloud Console\n"
                    "2. Включите Google Sheets API\n"
                    "3. Создайте сервисный аккаунт и скачайте ключ в формате JSON\n"
                    "4. Поместите файл ключа в директорию с ботом\n"
                    "5. Создайте таблицу Google Sheets и предоставьте доступ сервисному аккаунту\n"
                    "6. Обновите файл .env с настройками:\n"
                    "```\n"
                    "GOOGLE_SHEETS_CREDENTIALS=credentials.json\n"
                    "GOOGLE_SHEETS_SPREADSHEET_ID=your_spreadsheet_id\n"
                    "GOOGLE_SHEETS_ENABLED=true\n"
                    "```",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard
                )
                return
            
            # Импортируем менеджер Google Sheets и синхронизируем данные
            from google_sheets.sheets import sheets_manager
            
            # Отправляем сообщение о начале синхронизации
            progress_msg = await bot.send_message(
                callback_query.from_user.id,
                "🔄 Синхронизация данных с Google Sheets..."
            )
            
            # Синхронизируем данные
            success = sheets_manager.sync_all_data(db)
            
            # Создаем клавиатуру с кнопками
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("🔄 Синхронизировать", callback_data='spreadsheet'),
                InlineKeyboardButton("🔗 Открыть таблицу", url=f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEETS_SPREADSHEET_ID}")
            )
            keyboard.add(InlineKeyboardButton("🔙 Назад в меню", callback_data='back_to_menu'))
            
            if success:
                await bot.edit_message_text(
                    "✅ *Данные успешно синхронизированы с Google Sheets*\n\n"
                    "Все ваши данные теперь доступны в таблице Google Sheets.\n"
                    "Вы можете открыть таблицу, нажав на кнопку ниже.",
                    chat_id=callback_query.from_user.id,
                    message_id=progress_msg.message_id,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard
                )
            else:
                await bot.edit_message_text(
                    "❌ *Ошибка синхронизации с Google Sheets*\n\n"
                    "Не удалось синхронизировать данные с Google Sheets.\n"
                    "Проверьте настройки и попробуйте снова.",
                    chat_id=callback_query.from_user.id,
                    message_id=progress_msg.message_id,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard
                )
        except Exception as e:
            logger.error(f"Ошибка при работе с Google Sheets: {e}")
            await bot.send_message(
                callback_query.from_user.id,
                "❌ Произошла ошибка при работе с Google Sheets."
            )
        finally:
            db.close()
        return

    elif action == 'settings':
        await bot.answer_callback_query(callback_query.id)
        
        # Создаем клавиатуру для настроек
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            InlineKeyboardButton("🗑️ Очистить данные ребенка", callback_data='clear_child_data'),
            InlineKeyboardButton("🔙 Назад в меню", callback_data='back_to_menu')
        )
        
        await bot.send_message(
            callback_query.from_user.id,
            "⚙️ *Настройки*\n\n"
            "Здесь вы можете управлять настройками приложения.\n"
            "⚠️ Будьте осторожны с операциями удаления данных!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
        return

# Add a command to show the main menu
@dp.message_handler(commands=['menu'])
async def menu_command(message: types.Message):
    await show_main_menu(message)

@dp.message_handler(commands=['stats'])
async def stats_command(message: types.Message):
    """Команда для просмотра статистики"""
    db: Session = next(get_db())
    try:
        await message.reply("🔄 Анализирую данные о развитии ребенка...")
        
        # Генерируем сводку о развитии с помощью ИИ
        summary = ai_assistant.generate_development_summary(db)
        
        # Форматируем ответ
        response = f"📊 *Сводка о развитии ребенка*\n\n{summary}"
        
        # Добавляем кнопку возврата в меню
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("🔙 Назад в меню", callback_data='back_to_menu'))
        
        await message.reply(response, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка при генерации сводки: {e}")
        await message.reply("❌ Произошла ошибка при анализе данных. Пожалуйста, попробуйте позже.")
    finally:
        db.close()

@dp.callback_query_handler(lambda c: c.data == 'feeding')
async def process_feeding(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    db: Session = next(get_db())
    child = db.query(Child).first()
    last_feeding = db.query(Feeding).order_by(Feeding.timestamp.desc()).first()
    if last_feeding:
        last_feeding_info = f"Последнее кормление: {last_feeding.amount} {last_feeding.food_type} в {last_feeding.timestamp}"
    else:
        last_feeding_info = "Нет данных о предыдущих кормлениях."
    await bot.send_message(callback_query.from_user.id, last_feeding_info)
    await bot.send_message(callback_query.from_user.id, "Введите количество молока в граммах:")
    await FeedingState.waiting_for_amount.set()

@dp.message_handler(state=FeedingState.waiting_for_amount, content_types=types.ContentType.TEXT)
async def handle_feeding_amount(message: types.Message, state: FSMContext):
    """Обработка количества кормления"""
    try:
        amount = float(message.text.strip())
        await state.update_data(amount=amount)
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton("Грудное молоко", callback_data='food_breast_milk'),
            InlineKeyboardButton("Смесь", callback_data='food_formula'),
            InlineKeyboardButton("Прикорм", callback_data='food_solid')
        )
        await message.reply("Выберите тип питания:", reply_markup=keyboard)
        await FeedingState.waiting_for_food_type.set()
    except ValueError:
        await message.reply("❌ Пожалуйста, введите корректное количество в граммах.")

@dp.callback_query_handler(lambda c: c.data.startswith('food_'), state=FeedingState.waiting_for_food_type)
async def handle_food_type(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработка типа питания"""
    food_types = {
        'food_breast_milk': 'Грудное молоко',
        'food_formula': 'Смесь',
        'food_solid': 'Прикорм'
    }
    
    food_type = food_types.get(callback_query.data, 'Неизвестно')
    data = await state.get_data()
    
    db: Session = next(get_db())
    try:
        child = db.query(Child).first()
        feeding = Feeding(
            child_id=child.id, 
            amount=data['amount'], 
            food_type=food_type,
            timestamp=datetime.now()
        )
        db.add(feeding)
        db.commit()
        
        # Форматируем дату и время
        date_str = feeding.timestamp.strftime("%d.%m.%Y, %H:%M")
        
        await bot.send_message(
            callback_query.from_user.id,
            f"✅ Кормление записано: {data['amount']} мл {food_type.lower()}\n"
            f"📅 Время: {date_str}"
        )
        await show_main_menu(callback_query.message)
    except Exception as e:
        logger.error(f"Ошибка при сохранении кормления: {e}")
        await bot.send_message(
            callback_query.from_user.id,
            "❌ Ошибка при сохранении данных"
        )
    finally:
        db.close()
        await state.finish()

# Обработчик для стула
@dp.message_handler(state=StoolState.waiting_for_description)
async def handle_stool_description(message: types.Message, state: FSMContext):
    """Обработка описания стула"""
    db: Session = next(get_db())
    try:
        child = db.query(Child).first()
        
        # Пытаемся определить цвет из описания
        description = message.text.strip()
        color = None
        
        # Простая логика для определения цвета
        color_keywords = {
            'черный': 'черный',
            'черн': 'черный',
            'темный': 'темный',
            'коричневый': 'коричневый',
            'корич': 'коричневый',
            'желтый': 'желтый',
            'желт': 'желтый',
            'зеленый': 'зеленый',
            'зелен': 'зеленый',
            'красный': 'красный',
            'красн': 'красный',
            'белый': 'белый',
            'бел': 'белый',
        }
        
        description_lower = description.lower()
        for keyword, color_value in color_keywords.items():
            if keyword in description_lower:
                color = color_value
                break
        
        # Создаем запись о стуле
        stool = Stool(
            child_id=child.id,
            description=description,
            color=color,  # Может быть None
            timestamp=datetime.now()
        )
        db.add(stool)
        db.commit()
        
        # Форматируем дату и время
        date_str = stool.timestamp.strftime("%d.%m.%Y, %H:%M")
        
        await message.reply(
            f"✅ Данные о стуле записаны\n"
            f"📅 Время: {date_str}"
        )
        await show_main_menu(message)
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных о стуле: {e}")
        await message.reply("❌ Ошибка при сохранении данных")
    finally:
        db.close()
        await state.finish()

# Обработчик для веса
@dp.message_handler(state=WeightState.waiting_for_weight)
async def handle_weight_input(message: types.Message, state: FSMContext):
    """Обработка ввода веса"""
    try:
        weight = float(message.text.strip())
        db: Session = next(get_db())
        child = db.query(Child).first()
        weight_record = Weight(
            child_id=child.id,
            weight=weight,
            timestamp=datetime.now()
        )
        db.add(weight_record)
        db.commit()
        
        # Форматируем дату и время
        date_str = weight_record.timestamp.strftime("%d.%m.%Y, %H:%M")
        
        await message.reply(
            f"✅ Вес {weight} кг записан\n"
            f"📅 Время: {date_str}"
        )
        await show_main_menu(message)
    except ValueError:
        await message.reply("❌ Пожалуйста, введите корректный вес в килограммах")
    except Exception as e:
        logger.error(f"Ошибка при сохранении веса: {e}")
        await message.reply("❌ Ошибка при сохранении данных")
    finally:
        db.close()
        await state.finish()

# Обработчики для лекарств
@dp.message_handler(state=MedicationState.waiting_for_name)
async def handle_medication_name(message: types.Message, state: FSMContext):
    """Обработка названия лекарства"""
    await state.update_data(medication_name=message.text)
    await message.reply("Введите дозировку:")
    await MedicationState.waiting_for_dosage.set()

@dp.message_handler(state=MedicationState.waiting_for_dosage)
async def handle_medication_dosage(message: types.Message, state: FSMContext):
    """Обработка дозировки лекарства"""
    data = await state.get_data()
    db: Session = next(get_db())
    try:
        child = db.query(Child).first()
        medication = Medication(
            child_id=child.id,
            medication_name=data['medication_name'],
            dosage=message.text,
            timestamp=datetime.now()
        )
        db.add(medication)
        db.commit()
        
        # Форматируем дату и время
        date_str = medication.timestamp.strftime("%d.%m.%Y, %H:%M")
        
        await message.reply(
            f"✅ Лекарство записано: {data['medication_name']} - {message.text}\n"
            f"📅 Время: {date_str}"
        )
        await show_main_menu(message)
    except Exception as e:
        logger.error(f"Ошибка при сохранении лекарства: {e}")
        await message.reply("❌ Ошибка при сохранении данных")
    finally:
        db.close()
        await state.finish()

# Команда для AI консультации
@dp.message_handler(commands=['ai'])
async def ai_command(message: types.Message):
    """Команда для запроса к AI ассистенту"""
    await message.reply(
        "🤖 Задайте ваш вопрос AI-ассистенту. Я помогу с вопросами о здоровье, развитии и уходе за ребенком.",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("🔙 Назад в меню", callback_data='back_to_menu')
        )
    )

@dp.message_handler(commands=['reset'])
async def reset_ai_history(message: types.Message):
    """Сброс истории диалога с AI"""
    ai_assistant.clear_history()
    await message.reply(
        "🔄 *История диалога с AI сброшена*\n\n"
        "Теперь AI не будет учитывать предыдущие сообщения в контексте.",
        parse_mode=ParseMode.MARKDOWN
    )

# Обработчик callback для AI консультации
@dp.callback_query_handler(lambda c: c.data == 'ai_consult')
async def process_ai_consult(callback_query: types.CallbackQuery):
    """Обработка запроса на AI консультацию"""
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(
        callback_query.from_user.id,
        "🤖 Задайте ваш вопрос AI-ассистенту. Я помогу с вопросами о здоровье, развитии и уходе за ребенком.",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("🔙 Назад в меню", callback_data='back_to_menu')
        )
    )

# Обработчик callback для статистики
@dp.callback_query_handler(lambda c: c.data == 'stats')
async def process_stats(callback_query: types.CallbackQuery):
    """Показать статистику"""
    await bot.answer_callback_query(callback_query.id)
    db: Session = next(get_db())
    try:
        child = db.query(Child).first()
        if not child:
            await bot.send_message(callback_query.from_user.id, "Сначала зарегистрируйте ребенка")
            return
            
        # Подсчет данных
        feedings_today = db.query(Feeding).filter(
            Feeding.child_id == child.id,
            Feeding.timestamp >= datetime.now().replace(hour=0, minute=0, second=0)
        ).count()
        
        total_ml_today = db.query(Feeding).filter(
            Feeding.child_id == child.id,
            Feeding.timestamp >= datetime.now().replace(hour=0, minute=0, second=0)
        ).with_entities(func.sum(Feeding.amount)).scalar() or 0
        
        last_weight = db.query(Weight).filter_by(child_id=child.id).order_by(Weight.timestamp.desc()).first()
        
        # Вычисление возраста
        age_days = (datetime.now().date() - child.birth_date).days
        age_months = age_days // 30
        
        stats_text = f"""📊 *Статистика для {child.name}*
        
👶 Возраст: {age_months} мес. ({age_days} дней)
🍼 Кормлений сегодня: {feedings_today}
�� Всего молока сегодня: {total_ml_today} мл
⚖️ Последний вес: {last_weight.weight if last_weight else 'Не указан'} кг
        """
        
        await bot.send_message(
            callback_query.from_user.id,
            stats_text,
            parse_mode=ParseMode.MARKDOWN
        )
    finally:
        db.close()

# Функция для обработки текста (общая для текстовых и голосовых сообщений)
async def process_message_text(text: str, message: types.Message, state: FSMContext):
    """Обработка текста сообщения с AI с полным контекстом и распознаванием напоминаний"""
    db: Session = next(get_db())
    try:
        # Проверяем, есть ли в сообщении команда для статистики
        if text.lower().strip() in ['статистика', 'сводка', 'анализ', 'развитие']:
            # Генерируем сводку о развитии ребенка
            await message.reply("🔄 Анализирую данные о развитии ребенка...")
            summary = ai_assistant.generate_development_summary(db)
            
            # Форматируем ответ
            response = f"📊 *Сводка о развитии ребенка*\n\n{summary}"
            await message.reply(response, parse_mode=ParseMode.MARKDOWN)
            return
        
        # Получаем информацию о ребенке
        child = db.query(Child).first()
        if not child:
            await message.reply("❌ Сначала зарегистрируйте ребенка")
            return
        
        # Проверяем, является ли сообщение запросом на добавление заметки
        if text.lower().startswith('добавь заметку') or text.lower().startswith('создай заметку'):
            # Извлекаем заголовок и содержание заметки
            note_text = text.split(' ', 2)[-1]  # Удаляем "добавь заметку" или "создай заметку"
            
            # Используем OpenAI для разделения на заголовок и содержание
            try:
                prompt = f"""Раздели следующий текст на заголовок и содержание заметки:

{note_text}

Верни ответ в формате JSON:
{{
  "title": "Заголовок заметки (короткий)",
  "content": "Содержание заметки (полный текст)"
}}"""

                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Ты - ассистент, который помогает создавать заметки."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=500
                )
                
                result = response['choices'][0]['message']['content'].strip()
                
                # Извлекаем JSON из ответа
                try:
                    # Находим начало и конец JSON
                    start_idx = result.find('{')
                    end_idx = result.rfind('}') + 1
                    
                    if start_idx >= 0 and end_idx > start_idx:
                        json_str = result[start_idx:end_idx]
                        note_data = json.loads(json_str)
                        
                        title = note_data.get('title', 'Новая заметка')
                        content = note_data.get('content', note_text)
                        
                        # Создаем заметку
                        note = Note(
                            child_id=child.id,
                            title=title,
                            content=content,
                            timestamp=datetime.now()
                        )
                        
                        db.add(note)
                        db.commit()
                        
                        await message.reply(
                            f"✅ Заметка \"{title}\" успешно сохранена!",
                            reply_markup=get_main_keyboard()
                        )
                        return
                except Exception as e:
                    logger.error(f"Ошибка при парсинге JSON с заметкой: {e}")
            except Exception as e:
                logger.error(f"Ошибка при создании заметки: {e}")
            
            # Если не удалось разделить на заголовок и содержание, создаем заметку с дефолтным заголовком
            note = Note(
                child_id=child.id,
                title="Новая заметка",
                content=note_text,
                timestamp=datetime.now()
            )
            
            db.add(note)
            db.commit()
            
            await message.reply(
                f"✅ Заметка успешно сохранена!",
                reply_markup=get_main_keyboard()
            )
            return
            
        # Проверяем, является ли сообщение запросом на создание напоминаний из назначений
        if ai_assistant.parse_prescription_reminders_request(text):
            # Получаем активные назначения
            prescriptions = db.query(Prescription).filter(
                Prescription.child_id == child.id,
                Prescription.is_active == 1
            ).all()
            
            if not prescriptions:
                await message.reply(
                    "❌ У вас нет активных назначений для создания напоминаний"
                )
                return
            
            # Формируем сообщение с предложенными напоминаниями
            message_text = "📋 *Предлагаемые напоминания из назначений*\n\n"
            
            all_options = []
            
            for prescription in prescriptions:
                # Генерируем варианты напоминаний
                options = generate_reminder_options(prescription)
                if options:
                    message_text += f"*{prescription.medication_name}*:\n"
                    for i, option in enumerate(options, 1):
                        message_text += (
                            f"  {i}. {option['description']}\n"
                            f"  ⏰ Время: {option['time']}\n"
                            f"  🔄 Повторение: {option['repeat_text']}\n\n"
                        )
                    all_options.extend(options)
            
            if not all_options:
                await message.reply(
                    "❌ Не удалось сгенерировать напоминания для ваших назначений"
                )
                return
            
            # Создаем клавиатуру с кнопками
            keyboard = InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                InlineKeyboardButton("✅ Добавить все напоминания", callback_data="add_all_prescription_reminders"),
                InlineKeyboardButton("❌ Отмена", callback_data="back_to_menu")
            )
            
            # Сохраняем варианты напоминаний в состоянии
            await state.update_data(prescription_reminder_options=all_options)
            
            await message.reply(
                message_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
            return
            
        # Проверяем, является ли сообщение записью о кормлении
        feeding_data = ai_assistant.parse_feeding(text)
        if feeding_data:
            try:
                # Создаем запись о кормлении
                feeding = Feeding(
                    child_id=child.id,
                    amount=feeding_data['amount'],
                    food_type=feeding_data['food_type'],
                    timestamp=datetime.now()
                )
                
                db.add(feeding)
                db.commit()
                
                # Определяем тип питания для сообщения
                food_type_text = "грудное молоко"
                if feeding_data['food_type'] == 'formula':
                    food_type_text = "смесь"
                elif feeding_data['food_type'] == 'food':
                    food_type_text = "прикорм"
                
                # Отправляем сообщение об успешном добавлении
                await message.reply(
                    f"✅ *Запись о кормлении добавлена*\n\n"
                    f"🍼 Количество: {feeding_data['amount']} мл\n"
                    f"🥛 Тип: {food_type_text}\n"
                    f"🕒 Время: {datetime.now().strftime('%H:%M')}\n",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            except Exception as e:
                logger.error(f"Ошибка при добавлении записи о кормлении: {e}")
        
        # Проверяем, является ли сообщение записью о стуле
        stool_data = ai_assistant.parse_stool(text)
        if stool_data:
            try:
                # Создаем запись о стуле
                stool = Stool(
                    child_id=child.id,
                    description=stool_data['description'],
                    color=stool_data['color'],
                    timestamp=datetime.now()
                )
                
                db.add(stool)
                db.commit()
                
                # Формируем сообщение о цвете
                color_text = f"🎨 Цвет: {stool_data['color']}\n" if stool_data['color'] else ""
                
                # Добавляем кнопку возврата в меню
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton("🔙 Назад в меню", callback_data='back_to_menu'))
                
                # Отправляем сообщение об успешном добавлении
                await message.reply(
                    f"✅ *Запись о стуле добавлена*\n\n"
                    f"📝 Описание: {stool_data['description']}\n"
                    f"{color_text}"
                    f"🕒 Время: {datetime.now().strftime('%H:%M')}\n",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard
                )
                return
            except Exception as e:
                logger.error(f"Ошибка при добавлении записи о стуле: {e}")
        
        # Проверяем, является ли сообщение записью о приеме лекарства
        medication_data = ai_assistant.parse_medication(text)
        if medication_data:
            try:
                # Создаем запись о лекарстве
                medication = Medication(
                    child_id=child.id,
                    medication_name=medication_data['medication_name'],
                    dosage=medication_data['dosage'] or "",
                    timestamp=datetime.now()
                )
                
                db.add(medication)
                db.commit()
                
                # Формируем сообщение о дозировке
                dosage_text = f"💊 Дозировка: {medication_data['dosage']}\n" if medication_data['dosage'] else ""
                
                # Отправляем сообщение об успешном добавлении
                await message.reply(
                    f"✅ *Запись о приеме лекарства добавлена*\n\n"
                    f"💊 Лекарство: {medication_data['medication_name']}\n"
                    f"{dosage_text}"
                    f"🕒 Время: {datetime.now().strftime('%H:%M')}\n",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            except Exception as e:
                logger.error(f"Ошибка при добавлении записи о лекарстве: {e}")
        
        # Проверяем, является ли сообщение запросом на создание напоминания
        reminder_data = reminder_parser.parse_reminder(text)
        if reminder_data:
            try:
                created_reminders = []
                
                # Обрабатываем каждое напоминание
                for reminder_info in reminder_data:
                    # Парсим дату и время
                    reminder_time_str = f"{reminder_info['date']} {reminder_info['time']}"
                    reminder_time = datetime.strptime(reminder_time_str, "%d.%m.%Y %H:%M")
                    
                    # Для повторяющихся напоминаний корректируем время
                    if reminder_info['repeat_type'] != 'once':
                        # Если время уже прошло сегодня, устанавливаем на завтра
                        if reminder_time <= datetime.now():
                            reminder_time = reminder_time + timedelta(days=1)
                    else:
                        # Для однократных напоминаний проверяем, что время в будущем
                        if reminder_time <= datetime.now():
                            await message.reply(f"❌ Время напоминания '{reminder_info['description']}' должно быть в будущем.")
                            continue
                    
                    # Создаем напоминание
                    reminder = Reminder(
                        child_id=child.id,
                        description=reminder_info['description'],
                        reminder_time=reminder_time,
                        status='active',
                        repeat_type=reminder_info['repeat_type'],
                        repeat_interval=reminder_info['repeat_interval']
                    )
                    
                    db.add(reminder)
                    created_reminders.append((reminder, reminder_info))
                
                if created_reminders:
                    db.commit()
                    
                    # Формируем сообщение об успехе
                    success_messages = []
                    for reminder, reminder_info in created_reminders:
                        repeat_text = "однократное"
                        if reminder_info['repeat_type'] == 'daily':
                            repeat_text = f"каждые {reminder_info['repeat_interval']} день(дней)"
                        elif reminder_info['repeat_type'] == 'weekly':
                            repeat_text = f"каждые {reminder_info['repeat_interval']} неделю(недель)"
                        elif reminder_info['repeat_type'] == 'monthly':
                            repeat_text = f"каждые {reminder_info['repeat_interval']} месяц(ев)"
                        elif reminder_info['repeat_type'] == 'hourly':
                            repeat_text = f"каждые {reminder_info['repeat_interval']} час(ов)"
                        
                        success_messages.append(
                            f"📝 {reminder_info['description']}\n"
                            f"⏰ Время: {reminder.reminder_time.strftime('%d.%m.%Y, %H:%M')}\n"
                            f"🔄 Повторение: {repeat_text}"
                        )
                    
                    # Добавляем кнопку возврата в меню
                    keyboard = InlineKeyboardMarkup()
                    keyboard.add(InlineKeyboardButton("🔙 Назад в меню", callback_data='back_to_menu'))
                    
                    if len(created_reminders) == 1:
                        await message.reply(
                            f"✅ Напоминание создано!\n\n{success_messages[0]}",
                            reply_markup=keyboard
                        )
                    else:
                        await message.reply(
                            f"✅ Создано напоминаний: {len(created_reminders)}\n\n" + "\n\n".join(success_messages),
                            reply_markup=keyboard
                        )
                    return
                
            except Exception as e:
                logger.error(f"Ошибка при создании напоминания: {e}")
                await message.reply("❌ Произошла ошибка при создании напоминания.")
                return
        
        # Если ничего не подошло, считаем сообщение запросом к AI ассистенту
        with SessionLocal() as db:
            try:
                # Получаем ответ от AI ассистента
                response = ai_assistant.get_response(text, db)
                
                # Добавляем кнопку возврата в меню
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton("🔙 Назад в меню", callback_data='back_to_menu'))
                
                await message.reply(response, reply_markup=keyboard)
            except Exception as e:
                logger.error(f"Ошибка при получении ответа от AI: {e}")
                await message.reply("❌ Произошла ошибка при обработке вашего запроса.")
        
        # Проверяем, является ли сообщение записью о весе
        weight_data = ai_assistant.parse_weight(text)
        if weight_data:
            try:
                # Создаем запись о весе
                weight = Weight(
                    child_id=child.id,
                    weight=weight_data['weight'],
                    timestamp=datetime.now()
                )
                
                db.add(weight)
                db.commit()
                
                # Добавляем кнопку возврата в меню
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton("🔙 Назад в меню", callback_data='back_to_menu'))
                
                # Отправляем сообщение об успешном добавлении
                await message.reply(
                    f"✅ *Запись о весе добавлена*\n\n"
                    f"⚖️ Вес: {weight_data['weight']} кг\n"
                    f"📅 Дата: {datetime.now().strftime('%d.%m.%Y, %H:%M')}\n",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard
                )
                return
            except Exception as e:
                logger.error(f"Ошибка при добавлении записи о весе: {e}")
        
        # Проверяем, является ли сообщение записью о стуле
        stool_data = ai_assistant.parse_stool(text)
        if stool_data:
            try:
                # Создаем запись о стуле
                stool = Stool(
                    child_id=child.id,
                    description=stool_data['description'],
                    color=stool_data['color'],
                    timestamp=datetime.now()
                )
                
                db.add(stool)
                db.commit()
                
                # Формируем сообщение о цвете
                color_text = f"🎨 Цвет: {stool_data['color']}\n" if stool_data['color'] else ""
                
                # Добавляем кнопку возврата в меню
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton("🔙 Назад в меню", callback_data='back_to_menu'))
                
                # Отправляем сообщение об успешном добавлении
                await message.reply(
                    f"✅ *Запись о стуле добавлена*\n\n"
                    f"📝 Описание: {stool_data['description']}\n"
                    f"{color_text}"
                    f"🕒 Время: {datetime.now().strftime('%H:%M')}\n",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard
                )
                return
            except Exception as e:
                logger.error(f"Ошибка при добавлении записи о стуле: {e}")
        
        # Проверяем, является ли сообщение записью о приеме лекарства
        medication_data = ai_assistant.parse_medication(text)
        if medication_data:
            try:
                # Создаем запись о лекарстве
                medication = Medication(
                    child_id=child.id,
                    medication_name=medication_data['medication_name'],
                    dosage=medication_data['dosage'] or "",
                    timestamp=datetime.now()
                )
                
                db.add(medication)
                db.commit()
                
                # Формируем сообщение о дозировке
                dosage_text = f"💊 Дозировка: {medication_data['dosage']}\n" if medication_data['dosage'] else ""
                
                # Отправляем сообщение об успешном добавлении
                await message.reply(
                    f"✅ *Запись о приеме лекарства добавлена*\n\n"
                    f"💊 Лекарство: {medication_data['medication_name']}\n"
                    f"{dosage_text}"
                    f"🕒 Время: {datetime.now().strftime('%H:%M')}\n",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            except Exception as e:
                logger.error(f"Ошибка при добавлении записи о лекарстве: {e}")
        
        # Проверяем, является ли сообщение запросом на создание напоминания
        reminder_data = reminder_parser.parse_reminder(text)
        if reminder_data:
            try:
                created_reminders = []
                
                # Обрабатываем каждое напоминание
                for reminder_info in reminder_data:
                    # Парсим дату и время
                    reminder_time_str = f"{reminder_info['date']} {reminder_info['time']}"
                    reminder_time = datetime.strptime(reminder_time_str, "%d.%m.%Y %H:%M")
                    
                    # Для повторяющихся напоминаний корректируем время
                    if reminder_info['repeat_type'] != 'once':
                        # Если время уже прошло сегодня, устанавливаем на завтра
                        if reminder_time <= datetime.now():
                            reminder_time = reminder_time + timedelta(days=1)
                    else:
                        # Для однократных напоминаний проверяем, что время в будущем
                        if reminder_time <= datetime.now():
                            await message.reply(f"❌ Время напоминания '{reminder_info['description']}' должно быть в будущем.")
                            continue
                    
                    # Создаем напоминание
                    reminder = Reminder(
                        child_id=child.id,
                        description=reminder_info['description'],
                        reminder_time=reminder_time,
                        status='active',
                        repeat_type=reminder_info['repeat_type'],
                        repeat_interval=reminder_info['repeat_interval']
                    )
                    
                    db.add(reminder)
                    created_reminders.append((reminder, reminder_info))
                
                if created_reminders:
                    db.commit()
                    
                    # Формируем сообщение об успехе
                    success_messages = []
                    for reminder, reminder_info in created_reminders:
                        repeat_text = "однократное"
                        if reminder_info['repeat_type'] == 'daily':
                            repeat_text = f"каждые {reminder_info['repeat_interval']} день(дней)"
                        elif reminder_info['repeat_type'] == 'weekly':
                            repeat_text = f"каждые {reminder_info['repeat_interval']} неделю(недель)"
                        elif reminder_info['repeat_type'] == 'monthly':
                            repeat_text = f"каждые {reminder_info['repeat_interval']} месяц(ев)"
                        elif reminder_info['repeat_type'] == 'hourly':
                            repeat_text = f"каждые {reminder_info['repeat_interval']} час(ов)"
                        
                        success_messages.append(
                            f"📝 {reminder_info['description']}\n"
                            f"⏰ Время: {reminder.reminder_time.strftime('%d.%m.%Y, %H:%M')}\n"
                            f"🔄 Повторение: {repeat_text}"
                        )
                    
                    # Добавляем кнопку возврата в меню
                    keyboard = InlineKeyboardMarkup()
                    keyboard.add(InlineKeyboardButton("🔙 Назад в меню", callback_data='back_to_menu'))
                    
                    if len(created_reminders) == 1:
                        await message.reply(
                            f"✅ Напоминание создано!\n\n{success_messages[0]}",
                            reply_markup=keyboard
                        )
                    else:
                        await message.reply(
                            f"✅ Создано напоминаний: {len(created_reminders)}\n\n" + "\n\n".join(success_messages),
                            reply_markup=keyboard
                        )
                    return
                
            except Exception as e:
                logger.error(f"Ошибка при создании напоминания: {e}")
                await message.reply("❌ Произошла ошибка при создании напоминания.")
                return
    finally:
        db.close()

# Обработчик текстовых сообщений
@dp.message_handler(content_types=types.ContentType.TEXT)
async def handle_text_message(message: types.Message, state: FSMContext):
    """Обработка текстовых сообщений"""
    # Сохраняем пользователя
    db: Session = next(get_db())
    try:
        await save_user(message.from_user, db)
    finally:
        db.close()
    
    # Получаем текущее состояние
    current_state = await state.get_state()
    
    # Если есть активное состояние, не обрабатываем как обычное сообщение
    if current_state:
        return
    
    # Обрабатываем текст
    await process_message_text(message.text, message, state)

# Обработчик голосовых сообщений
@dp.message_handler(content_types=types.ContentType.VOICE)
async def handle_voice_message(message: types.Message, state: FSMContext):
    """Обработка голосовых сообщений"""
    current_state = await state.get_state()
    if current_state is not None:
        return
    
    await message.reply("🔄 Обрабатываю ваше голосовое сообщение...")
    
    try:
        # Скачиваем голосовое сообщение
        file_info = await bot.get_file(message.voice.file_id)
        voice_file = io.BytesIO()
        await bot.download_file(file_info.file_path, voice_file)
        
        # Сохраняем во временный файл
        with tempfile.NamedTemporaryFile(suffix=".ogg") as temp_voice:
            temp_voice.write(voice_file.getvalue())
            temp_voice.flush()
            
            # Преобразуем в текст с помощью OpenAI Whisper API
            with open(temp_voice.name, "rb") as audio_file:
                transcript = openai.Audio.transcribe("whisper-1", audio_file)
            
            text = transcript.get("text", "")
            
            if text:
                await message.reply(f"🎤 Распознанный текст: {text}")
                await process_message_text(text, message, state)
            else:
                await message.reply("❌ Не удалось распознать текст в голосовом сообщении.")
    except Exception as e:
        logger.error(f"Ошибка при обработке голосового сообщения: {e}")
        await message.reply("❌ Произошла ошибка при обработке голосового сообщения.")

# Обработчик для кнопки очистки данных ребенка
@dp.callback_query_handler(lambda c: c.data == 'clear_child_data')
async def process_clear_child_data(callback_query: types.CallbackQuery):
    """Обработка запроса на очистку данных ребенка"""
    await bot.answer_callback_query(callback_query.id)
    
    # Создаем клавиатуру для подтверждения
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Да, очистить", callback_data='confirm_clear_data'),
        InlineKeyboardButton("❌ Нет, отмена", callback_data='settings')
    )
    
    await bot.send_message(
        callback_query.from_user.id,
        "⚠️ *ВНИМАНИЕ! Очистка данных*\n\n"
        "Вы собираетесь удалить ВСЕ данные о ребенке:\n"
        "• Записи о кормлениях\n"
        "• Записи о стуле\n"
        "• Записи о весе\n"
        "• Записи о приеме лекарств\n"
        "• Все напоминания\n"
        "• Все назначения\n\n"
        "Эта операция *необратима*. Вы уверены?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=keyboard
    )

# Обработчик подтверждения очистки данных
@dp.callback_query_handler(lambda c: c.data == 'confirm_clear_data')
async def confirm_clear_data(callback_query: types.CallbackQuery):
    """Подтверждение очистки данных ребенка"""
    await bot.answer_callback_query(callback_query.id)
    
    db: Session = next(get_db())
    try:
        # Получаем ребенка
        child = db.query(Child).first()
        if not child:
            await bot.send_message(
                callback_query.from_user.id,
                "❌ Ребенок не найден в базе данных."
            )
            return
        
        # Сохраняем имя ребенка
        child_name = child.name
        
        # Удаляем все связанные данные
        db.query(Feeding).filter(Feeding.child_id == child.id).delete()
        db.query(Stool).filter(Stool.child_id == child.id).delete()
        db.query(Weight).filter(Weight.child_id == child.id).delete()
        db.query(Medication).filter(Medication.child_id == child.id).delete()
        db.query(Reminder).filter(Reminder.child_id == child.id).delete()
        db.query(Prescription).filter(Prescription.child_id == child.id).delete()
        
        # Фиксируем изменения
        db.commit()
        
        # Отправляем сообщение об успешной очистке
        await bot.send_message(
            callback_query.from_user.id,
            f"✅ *Данные успешно очищены*\n\n"
            f"Все записи о ребенке {child_name} были удалены из базы данных.\n"
            f"Профиль ребенка сохранен, но все записи о кормлениях, стуле, весе, "
            f"лекарствах, напоминаниях и назначениях удалены.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Возвращаемся в настройки
        await process_main_menu(callback_query)
        
    except Exception as e:
        logger.error(f"Ошибка при очистке данных ребенка: {e}")
        await bot.send_message(
            callback_query.from_user.id,
            "❌ Произошла ошибка при очистке данных."
        )
    finally:
        db.close()

# Обработчик для кнопки добавления назначения
@dp.callback_query_handler(lambda c: c.data == 'add_prescription')
async def add_prescription_start(callback_query: types.CallbackQuery):
    """Начало процесса добавления назначения"""
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(
        callback_query.from_user.id,
        "📋 *Добавление нового назначения*\n\n"
        "Введите полный текст назначения от врача (все лекарства, процедуры, рекомендации):",
        parse_mode=ParseMode.MARKDOWN
    )
    await PrescriptionState.waiting_for_full_text.set()

# Обработчик полного текста назначения
@dp.message_handler(state=PrescriptionState.waiting_for_full_text)
async def handle_prescription_full_text(message: types.Message, state: FSMContext):
    """Обработка полного текста назначения"""
    full_text = message.text
    await state.update_data(full_text=full_text)
    
    # Используем OpenAI для извлечения списка лекарств
    try:
        prompt = f"""Проанализируй следующее медицинское назначение и определи все лекарства/препараты с их дозировками:

{full_text}

Верни ответ в формате JSON:
[
  {{
    "name": "Название лекарства",
    "dosage": "Дозировка"
  }}
]

Включи все лекарства, которые упоминаются в тексте."""

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Ты - медицинский ассистент, который анализирует назначения врачей."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        result = response['choices'][0]['message']['content'].strip()
        
        # Извлекаем JSON из ответа
        try:
            # Находим начало и конец JSON
            start_idx = result.find('[')
            end_idx = result.rfind(']') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = result[start_idx:end_idx]
                medications = json.loads(json_str)
                
                # Проверяем, что получили список словарей с нужными ключами
                valid_medications = []
                for med in medications:
                    if isinstance(med, dict) and 'name' in med:
                        valid_medications.append(med)
                
                if valid_medications:
                    await state.update_data(medications=valid_medications)
                    
                    # Формируем сообщение с найденными лекарствами
                    meds_text = "\n".join([f"• {med['name']} - {med.get('dosage', 'дозировка не указана')}" for med in valid_medications])
                    await message.reply(
                        f"💊 *Найдены следующие лекарства:*\n\n{meds_text}\n\n"
                        f"📅 Введите дату начала приема в формате ДД.ММ.ГГГГ (или 'сегодня'):",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    await PrescriptionState.waiting_for_start_date.set()
                    return
        except Exception as e:
            logger.error(f"Ошибка при парсинге JSON с лекарствами: {e}")
    except Exception as e:
        logger.error(f"Ошибка при извлечении лекарств: {e}")
    
    # Если не удалось извлечь лекарства, используем весь текст как название
    await state.update_data(medications=[{"name": "Назначение", "dosage": "См. полный текст"}])
    await message.reply(
        "📅 Введите дату начала приема в формате ДД.ММ.ГГГГ (или 'сегодня'):"
    )
    await PrescriptionState.waiting_for_start_date.set()

# Обработчик даты начала для назначения
@dp.message_handler(state=PrescriptionState.waiting_for_start_date)
async def handle_prescription_start_date(message: types.Message, state: FSMContext):
    """Обработка даты начала для назначения"""
    try:
        if message.text.lower() == 'сегодня':
            start_date = datetime.now().date()
        else:
            start_date = datetime.strptime(message.text, "%d.%m.%Y").date()
        
        await state.update_data(start_date=start_date)
        await message.reply(
            "📅 Введите дату окончания приема в формате ДД.ММ.ГГГГ (или '-' если бессрочно):"
        )
        await PrescriptionState.waiting_for_end_date.set()
    except ValueError:
        await message.reply(
            "❌ Неверный формат даты. Пожалуйста, используйте формат ДД.ММ.ГГГГ или слово 'сегодня'."
        )

# Обработчик даты окончания для назначения
@dp.message_handler(state=PrescriptionState.waiting_for_end_date)
async def handle_prescription_end_date(message: types.Message, state: FSMContext):
    """Обработка даты окончания и сохранение назначения"""
    try:
        end_date = None
        if message.text != '-':
            end_date = datetime.strptime(message.text, "%d.%m.%Y").date()
        
        await state.update_data(end_date=end_date)
        data = await state.get_data()
        
        db: Session = next(get_db())
        try:
            # Получаем информацию о ребенке
            child = db.query(Child).first()
            if not child:
                await message.reply("❌ Сначала зарегистрируйте ребенка")
                await state.finish()
                return
            
            # Используем OpenAI для извлечения частоты приема для каждого лекарства
            medications = data.get('medications', [])
            if not medications:
                medications = [{"name": "Назначение", "dosage": "См. полный текст"}]
            
            try:
                prompt = f"""Проанализируй следующее медицинское назначение и определи частоту приема для каждого лекарства:

{data['full_text']}

Лекарства:
{", ".join([med["name"] for med in medications])}

Верни ответ в формате JSON:
[
  {{
    "name": "Название лекарства",
    "frequency": "Частота приема (например: '2 раза в день', 'утром и вечером')"
  }}
]"""

                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Ты - медицинский ассистент, который анализирует назначения врачей."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=500
                )
                
                result = response['choices'][0]['message']['content'].strip()
                
                # Извлекаем JSON из ответа
                try:
                    # Находим начало и конец JSON
                    start_idx = result.find('[')
                    end_idx = result.rfind(']') + 1
                    
                    if start_idx >= 0 and end_idx > start_idx:
                        json_str = result[start_idx:end_idx]
                        frequencies = json.loads(json_str)
                        
                        # Добавляем частоту к каждому лекарству
                        for med in medications:
                            for freq in frequencies:
                                if med["name"].lower() in freq["name"].lower() or freq["name"].lower() in med["name"].lower():
                                    med["frequency"] = freq.get("frequency", "ежедневно")
                                    break
                            if "frequency" not in med:
                                med["frequency"] = "ежедневно"
                except Exception as e:
                    logger.error(f"Ошибка при парсинге JSON с частотами: {e}")
                    # Устанавливаем частоту по умолчанию
                    for med in medications:
                        if "frequency" not in med:
                            med["frequency"] = "ежедневно"
            except Exception as e:
                logger.error(f"Ошибка при извлечении частоты приема: {e}")
                # Устанавливаем частоту по умолчанию
                for med in medications:
                    if "frequency" not in med:
                        med["frequency"] = "ежедневно"
            
            # Создаем основное назначение
            main_medication = medications[0] if medications else {"name": "Назначение", "dosage": "См. полный текст", "frequency": "ежедневно"}
            
            prescription = Prescription(
                child_id=child.id,
                medication_name=main_medication["name"],
                dosage=main_medication.get("dosage", "См. полный текст"),
                frequency=main_medication.get("frequency", "ежедневно"),
                doctor_name=None,  # Не запрашиваем имя врача
                start_date=data['start_date'],
                end_date=data['end_date'],
                notes=None,
                full_text=data['full_text'],
                is_active=1,  # Активно по умолчанию
            )
            
            db.add(prescription)
            db.commit()
            
            # Формируем сообщение об успешном добавлении
            end_date_text = f"до {data['end_date'].strftime('%d.%m.%Y')}" if data['end_date'] else "бессрочно"
            
            # Формируем список лекарств
            meds_text = ""
            for i, med in enumerate(medications, 1):
                dosage_text = f" - {med.get('dosage', '')}" if med.get('dosage') else ""
                frequency_text = f", {med.get('frequency', 'ежедневно')}" if med.get('frequency') else ""
                meds_text += f"{i}. *{med['name']}*{dosage_text}{frequency_text}\n"
            
            success_message = f"""✅ *Назначение добавлено!*

📋 *Список лекарств:*
{meds_text}
📅 Период: с {data['start_date'].strftime('%d.%m.%Y')} {end_date_text}

📄 *Полный текст назначения:*
{data['full_text']}
"""
            
            # Создаем клавиатуру с кнопками для каждого лекарства
            keyboard = InlineKeyboardMarkup(row_width=1)
            
            # Добавляем кнопку для создания напоминаний для всех лекарств
            keyboard.add(
                InlineKeyboardButton("➕ Создать напоминания для всех", callback_data=f"create_reminders_for_{prescription.id}")
            )
            
            # Добавляем кнопки для создания напоминаний для каждого лекарства
            for i, med in enumerate(medications):
                keyboard.add(
                    InlineKeyboardButton(f"➕ Напоминания для {med['name']}", callback_data=f"create_reminders_for_med_{prescription.id}_{i}")
                )
            
            # Добавляем навигационные кнопки
            keyboard.add(
                InlineKeyboardButton("📋 К назначениям", callback_data="prescriptions"),
                InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")
            )
            
            # Сохраняем список лекарств в базе данных или в кэше для использования при создании напоминаний
            await state.update_data(prescription_id=prescription.id, medications=medications)
            
            await message.reply(
                success_message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Ошибка при сохранении назначения: {e}")
            await message.reply("❌ Произошла ошибка при сохранении назначения.")
        finally:
            db.close()
            await state.finish()
    except ValueError:
        await message.reply(
            "❌ Неверный формат даты. Пожалуйста, используйте формат ДД.ММ.ГГГГ или символ '-'."
        )

# Обработчик для кнопки создания напоминаний из назначения
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('create_reminders_for_'))
async def create_reminders_for_prescription(callback_query: types.CallbackQuery):
    """Создание напоминаний на основе назначения"""
    await bot.answer_callback_query(callback_query.id)
    
    # Получаем ID назначения из callback_data
    prescription_id = int(callback_query.data.split('_')[-1])
    
    db: Session = next(get_db())
    try:
        # Получаем назначение
        prescription = db.query(Prescription).get(prescription_id)
        if not prescription:
            await bot.send_message(
                callback_query.from_user.id,
                "❌ Назначение не найдено"
            )
            return
        
        # Генерируем варианты напоминаний на основе частоты приема
        reminder_options = generate_reminder_options(prescription)
        
        if not reminder_options:
            await bot.send_message(
                callback_query.from_user.id,
                "❌ Не удалось сгенерировать напоминания для данного назначения"
            )
            return
        
        # Формируем сообщение с предложенными напоминаниями
        message_text = f"📋 *Предлагаемые напоминания для {prescription.medication_name}*\n\n"
        
        for i, option in enumerate(reminder_options, 1):
            message_text += (
                f"{i}. {option['description']}\n"
                f"⏰ Время: {option['time']}\n"
                f"🔄 Повторение: {option['repeat_text']}\n\n"
            )
        
        # Создаем клавиатуру с кнопками
        keyboard = InlineKeyboardMarkup(row_width=1)
        for i, option in enumerate(reminder_options, 1):
            keyboard.add(
                InlineKeyboardButton(
                    f"✅ Добавить напоминание {i}",
                    callback_data=f"add_reminder_option_{prescription_id}_{i-1}"
                )
            )
        keyboard.add(
            InlineKeyboardButton("✅ Добавить все", callback_data=f"add_all_reminders_{prescription_id}"),
            InlineKeyboardButton("❌ Отмена", callback_data="prescriptions")
        )
        
        await bot.send_message(
            callback_query.from_user.id,
            message_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка при создании напоминаний: {e}")
        await bot.send_message(
            callback_query.from_user.id,
            "❌ Произошла ошибка при создании напоминаний"
        )
    finally:
        db.close()

# Обработчик для добавления одного напоминания из предложенных
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('add_reminder_option_'))
async def add_reminder_option(callback_query: types.CallbackQuery):
    """Добавление одного напоминания из предложенных"""
    await bot.answer_callback_query(callback_query.id)
    
    # Получаем ID назначения и индекс напоминания из callback_data
    parts = callback_query.data.split('_')
    prescription_id = int(parts[-2])
    option_index = int(parts[-1])
    
    db: Session = next(get_db())
    try:
        # Получаем назначение
        prescription = db.query(Prescription).get(prescription_id)
        if not prescription:
            await bot.send_message(
                callback_query.from_user.id,
                "❌ Назначение не найдено"
            )
            return
        
        # Генерируем варианты напоминаний
        reminder_options = generate_reminder_options(prescription)
        
        if option_index >= len(reminder_options):
            await bot.send_message(
                callback_query.from_user.id,
                "❌ Выбранное напоминание не найдено"
            )
            return
        
        # Получаем выбранное напоминание
        selected_option = reminder_options[option_index]
        
        # Создаем напоминание
        reminder = create_reminder_from_option(db, prescription.child_id, selected_option)
        
        if reminder:
            await bot.send_message(
                callback_query.from_user.id,
                f"✅ Напоминание добавлено: {selected_option['description']}"
            )
        else:
            await bot.send_message(
                callback_query.from_user.id,
                "❌ Не удалось добавить напоминание"
            )
        
        # Возвращаемся к списку назначений
        await process_main_menu(callback_query)
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении напоминания: {e}")
        await bot.send_message(
            callback_query.from_user.id,
            "❌ Произошла ошибка при добавлении напоминания"
        )
    finally:
        db.close()

# Обработчик для добавления всех напоминаний
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('add_all_reminders_'))
async def add_all_reminders(callback_query: types.CallbackQuery):
    """Добавление всех предложенных напоминаний"""
    await bot.answer_callback_query(callback_query.id)
    
    # Получаем ID назначения из callback_data
    prescription_id = int(callback_query.data.split('_')[-1])
    
    db: Session = next(get_db())
    try:
        # Получаем назначение
        prescription = db.query(Prescription).get(prescription_id)
        if not prescription:
            await bot.send_message(
                callback_query.from_user.id,
                "❌ Назначение не найдено"
            )
            return
        
        # Генерируем варианты напоминаний
        reminder_options = generate_reminder_options(prescription)
        
        if not reminder_options:
            await bot.send_message(
                callback_query.from_user.id,
                "❌ Не удалось сгенерировать напоминания"
            )
            return
        
        # Добавляем все напоминания
        added_count = 0
        for option in reminder_options:
            if create_reminder_from_option(db, prescription.child_id, option):
                added_count += 1
        
        await bot.send_message(
            callback_query.from_user.id,
            f"✅ Добавлено напоминаний: {added_count} из {len(reminder_options)}"
        )
        
        # Возвращаемся к списку назначений
        await process_main_menu(callback_query)
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении напоминаний: {e}")
        await bot.send_message(
            callback_query.from_user.id,
            "❌ Произошла ошибка при добавлении напоминаний"
        )
    finally:
        db.close()

def generate_reminder_options(prescription):
    """
    Генерирует варианты напоминаний на основе назначения с использованием ИИ
    
    Args:
        prescription: Объект назначения
        
    Returns:
        Список словарей с вариантами напоминаний
    """
    try:
        # Если есть полный текст назначения, используем ИИ для анализа
        if prescription.full_text:
            # Определяем, анализируем ли мы конкретное лекарство или все назначение
            is_single_medication = len(prescription.full_text.split('\n')) <= 2
            
            if is_single_medication:
                prompt = f"""Проанализируй следующее медицинское назначение для лекарства и создай список напоминаний для его приема:

Лекарство: {prescription.medication_name}
Дозировка: {prescription.dosage}
Частота приема: {prescription.frequency}
Полная информация: {prescription.full_text}

Учитывай следующие правила:
1. Если указано конкретное время приема, используй его
2. Если указано "до еды" или "после еды", учитывай это в расписании
3. Если указана связь с приемами пищи, распредели приемы на стандартные часы (завтрак - 8:00, обед - 13:00, ужин - 19:00)
4. Если указано количество приемов в день без конкретного времени, равномерно распредели по дню
5. Для "утром" используй 8:00, для "днем" - 14:00, для "вечером" - 20:00

Верни список напоминаний в формате JSON:
[
  {{
    "description": "Принять {prescription.medication_name} {prescription.dosage}",
    "time": "ЧЧ:ММ",
    "repeat_type": "daily/weekly/monthly",
    "repeat_interval": число,
    "repeat_text": "ежедневно/еженедельно/ежемесячно"
  }}
]

Создай от 1 до 3 напоминаний в зависимости от частоты приема."""
            else:
                prompt = f"""Проанализируй следующее медицинское назначение и создай список напоминаний для приема лекарств:

Назначение:
{prescription.full_text}

Препарат: {prescription.medication_name}
Дозировка: {prescription.dosage}
Частота: {prescription.frequency}

Учитывай следующие правила:
1. Если указано конкретное время приема, используй его
2. Если указано "до еды" или "после еды", учитывай это в расписании
3. Если указана связь с приемами пищи, распредели приемы на стандартные часы (завтрак - 8:00, обед - 13:00, ужин - 19:00)
4. Если указано количество приемов в день без конкретного времени, равномерно распредели по дню
5. Для "утром" используй 8:00, для "днем" - 14:00, для "вечером" - 20:00

Верни список напоминаний в формате JSON:
[
  {{
    "description": "Принять [название] [дозировка]",
    "time": "ЧЧ:ММ",
    "repeat_type": "daily/weekly/monthly",
    "repeat_interval": число,
    "repeat_text": "ежедневно/еженедельно/ежемесячно"
  }}
]

Создай от 1 до 5 напоминаний в зависимости от сложности назначения."""

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Ты - медицинский ассистент, который анализирует назначения врачей и создает расписание приема лекарств."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            result = response['choices'][0]['message']['content'].strip()
            
            # Извлекаем JSON из ответа
            try:
                # Находим начало и конец JSON
                start_idx = result.find('[')
                end_idx = result.rfind(']') + 1
                
                if start_idx >= 0 and end_idx > start_idx:
                    json_str = result[start_idx:end_idx]
                    options = json.loads(json_str)
                    
                    # Проверяем, что получили список словарей с нужными ключами
                    valid_options = []
                    for opt in options:
                        if isinstance(opt, dict) and all(k in opt for k in ['description', 'time', 'repeat_type', 'repeat_interval', 'repeat_text']):
                            # Если в описании нет названия лекарства, добавляем его
                            if prescription.medication_name not in opt['description']:
                                opt['description'] = f"Принять {prescription.medication_name} {prescription.dosage}"
                            valid_options.append(opt)
                    
                    if valid_options:
                        return valid_options
            except Exception as e:
                logger.error(f"Ошибка при парсинге JSON с напоминаниями: {e}")
        
        # Если не удалось получить напоминания через ИИ или нет полного текста, используем стандартную логику
        options = []
        
        # Анализируем частоту приема
        frequency_lower = prescription.frequency.lower()
        
        # Определяем тип повторения и интервал
        repeat_type = 'daily'  # По умолчанию ежедневно
        repeat_interval = 1
        
        # Определяем время приема
        times = []
        
        # Проверяем ключевые слова для определения частоты
        if 'раз в день' in frequency_lower or 'раза в день' in frequency_lower:
            # Извлекаем количество раз в день
            match = re.search(r'(\d+)\s*раза?\s*в\s*день', frequency_lower)
            if match:
                times_per_day = int(match.group(1))
                
                # Распределяем приемы равномерно в течение дня
                if times_per_day == 1:
                    times = ['09:00']
                elif times_per_day == 2:
                    times = ['09:00', '21:00']
                elif times_per_day == 3:
                    times = ['08:00', '14:00', '20:00']
                elif times_per_day == 4:
                    times = ['08:00', '12:00', '16:00', '20:00']
                else:
                    # Для других случаев распределяем равномерно с 8 утра до 8 вечера
                    start_hour = 8
                    end_hour = 20
                    interval = (end_hour - start_hour) / (times_per_day - 1) if times_per_day > 1 else 0
                    
                    for i in range(times_per_day):
                        hour = int(start_hour + i * interval)
                        times.append(f"{hour:02d}:00")
        
        elif 'каждый день' in frequency_lower or 'ежедневно' in frequency_lower:
            times = ['09:00']
        
        elif 'утром' in frequency_lower:
            times = ['08:00']
        
        elif 'днем' in frequency_lower or 'днём' in frequency_lower:
            times = ['14:00']
        
        elif 'вечером' in frequency_lower:
            times = ['20:00']
        
        elif 'утром и вечером' in frequency_lower:
            times = ['08:00', '20:00']
        
        elif 'каждую неделю' in frequency_lower or 'еженедельно' in frequency_lower or 'раз в неделю' in frequency_lower:
            repeat_type = 'weekly'
            times = ['10:00']
        
        elif 'каждый месяц' in frequency_lower or 'ежемесячно' in frequency_lower or 'раз в месяц' in frequency_lower:
            repeat_type = 'monthly'
            times = ['10:00']
        
        else:
            # Если не удалось определить частоту, используем один раз в день
            times = ['09:00']
        
        # Создаем варианты напоминаний для каждого времени
        for time_str in times:
            # Определяем текст повторения
            repeat_text = "ежедневно"
            if repeat_type == 'weekly':
                repeat_text = "еженедельно"
            elif repeat_type == 'monthly':
                repeat_text = "ежемесячно"
            
            # Создаем описание напоминания
            dosage_text = f" ({prescription.dosage})" if prescription.dosage and prescription.dosage != "См. полный текст" else ""
            description = f"Принять {prescription.medication_name}{dosage_text}"
            
            # Добавляем вариант напоминания
            options.append({
                'description': description,
                'time': time_str,
                'repeat_type': repeat_type,
                'repeat_interval': repeat_interval,
                'repeat_text': repeat_text
            })
        
        return options
    except Exception as e:
        logger.error(f"Ошибка при генерации вариантов напоминаний: {e}")
        # Возвращаем базовый вариант в случае ошибки
        return [{
            'description': f"Принять {prescription.medication_name}",
            'time': '09:00',
            'repeat_type': 'daily',
            'repeat_interval': 1,
            'repeat_text': 'ежедневно'
        }]

def create_reminder_from_option(db, child_id, option):
    """
    Создает напоминание из варианта
    
    Args:
        db: Сессия базы данных
        child_id: ID ребенка
        option: Словарь с параметрами напоминания
        
    Returns:
        Созданное напоминание или None в случае ошибки
    """
    try:
        # Получаем текущую дату
        today = datetime.now().date()
        
        # Парсим время
        hour, minute = map(int, option['time'].split(':'))
        
        # Создаем дату и время напоминания
        reminder_time = datetime.combine(today, datetime.min.time().replace(hour=hour, minute=minute))
        
        # Если время уже прошло сегодня, переносим на завтра
        if reminder_time <= datetime.now():
            reminder_time += timedelta(days=1)
        
        # Создаем напоминание
        reminder = Reminder(
            child_id=child_id,
            description=option['description'],
            reminder_time=reminder_time,
            status='active',
            repeat_type=option['repeat_type'],
            repeat_interval=option['repeat_interval'],
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        db.add(reminder)
        db.commit()
        
        return reminder
    except Exception as e:
        logger.error(f"Ошибка при создании напоминания: {e}")
        db.rollback()
        return None

# Импорт функции sum для статистики
from sqlalchemy import func

# Обработчик для добавления всех напоминаний из назначений
@dp.callback_query_handler(lambda c: c.data == 'add_all_prescription_reminders')
async def add_all_prescription_reminders(callback_query: types.CallbackQuery, state: FSMContext):
    """Добавление всех предложенных напоминаний из назначений"""
    await bot.answer_callback_query(callback_query.id)
    
    # Получаем сохраненные варианты напоминаний
    data = await state.get_data()
    options = data.get('prescription_reminder_options', [])
    
    if not options:
        await bot.send_message(
            callback_query.from_user.id,
            "❌ Не найдены варианты напоминаний для добавления"
        )
        return
    
    db: Session = next(get_db())
    try:
        # Получаем информацию о ребенке
        child = db.query(Child).first()
        if not child:
            await bot.send_message(
                callback_query.from_user.id,
                "❌ Сначала зарегистрируйте ребенка"
            )
            return
        
        # Добавляем все напоминания
        added_count = 0
        for option in options:
            if create_reminder_from_option(db, child.id, option):
                added_count += 1
        
        await bot.send_message(
            callback_query.from_user.id,
            f"✅ Добавлено напоминаний: {added_count} из {len(options)}"
        )
        
        # Очищаем состояние
        await state.finish()
        
        # Возвращаемся в главное меню
        await show_main_menu(callback_query.message)
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении напоминаний: {e}")
        await bot.send_message(
            callback_query.from_user.id,
            "❌ Произошла ошибка при добавлении напоминаний"
        )
    finally:
        db.close()

# Обработчик для кнопки создания напоминаний из всех назначений
@dp.callback_query_handler(lambda c: c.data == 'create_all_prescription_reminders')
async def create_all_prescription_reminders_handler(callback_query: types.CallbackQuery):
    """Создание напоминаний на основе всех активных назначений"""
    await bot.answer_callback_query(callback_query.id)
    
    db: Session = next(get_db())
    try:
        # Получаем информацию о ребенке
        child = db.query(Child).first()
        if not child:
            await bot.send_message(
                callback_query.from_user.id,
                "❌ Сначала зарегистрируйте ребенка"
            )
            return
        
        # Получаем все активные назначения
        prescriptions = db.query(Prescription).filter(
            Prescription.child_id == child.id,
            Prescription.is_active == 1
        ).all()
        
        if not prescriptions:
            await bot.send_message(
                callback_query.from_user.id,
                "❌ У вас нет активных назначений для создания напоминаний"
            )
            return
        
        # Формируем сообщение с предложенными напоминаниями
        message_text = "📋 *Предлагаемые напоминания из назначений*\n\n"
        
        all_options = []
        
        for prescription in prescriptions:
            # Генерируем варианты напоминаний
            options = generate_reminder_options(prescription)
            if options:
                message_text += f"*{prescription.medication_name}*:\n"
                for i, option in enumerate(options, 1):
                    message_text += (
                        f"  {i}. {option['description']}\n"
                        f"  ⏰ Время: {option['time']}\n"
                        f"  🔄 Повторение: {option['repeat_text']}\n\n"
                    )
                all_options.extend(options)
        
        if not all_options:
            await bot.send_message(
                callback_query.from_user.id,
                "❌ Не удалось сгенерировать напоминания для ваших назначений"
            )
            return
        
        # Создаем клавиатуру с кнопками
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            InlineKeyboardButton("✅ Добавить все напоминания", callback_data="add_all_prescription_reminders"),
            InlineKeyboardButton("❌ Отмена", callback_data="prescriptions")
        )
        
        # Сохраняем варианты напоминаний в состоянии
        state = dp.current_state(user=callback_query.from_user.id)
        await state.update_data(prescription_reminder_options=all_options)
        
        await bot.send_message(
            callback_query.from_user.id,
            message_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка при создании напоминаний: {e}")
        await bot.send_message(
            callback_query.from_user.id,
            "❌ Произошла ошибка при создании напоминаний"
        )
    finally:
        db.close()

# Обработчик для кнопки создания напоминаний для конкретного лекарства
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('create_reminders_for_med_'))
async def create_reminders_for_medication(callback_query: types.CallbackQuery, state: FSMContext):
    """Создание напоминаний на основе конкретного лекарства из назначения"""
    await bot.answer_callback_query(callback_query.id)
    
    # Получаем ID назначения и индекс лекарства из callback_data
    parts = callback_query.data.split('_')
    prescription_id = int(parts[-2])
    medication_index = int(parts[-1])
    
    db: Session = next(get_db())
    try:
        # Получаем назначение
        prescription = db.query(Prescription).get(prescription_id)
        if not prescription:
            await bot.send_message(
                callback_query.from_user.id,
                "❌ Назначение не найдено"
            )
            return
        
        # Получаем данные о лекарствах из состояния
        user_data = await dp.storage.get_data(user=callback_query.from_user.id)
        medications = user_data.get('medications', [])
        
        if not medications or medication_index >= len(medications):
            await bot.send_message(
                callback_query.from_user.id,
                "❌ Информация о лекарстве не найдена"
            )
            return
        
        # Получаем выбранное лекарство
        selected_medication = medications[medication_index]
        
        # Создаем временное назначение для этого лекарства
        temp_prescription = Prescription(
            id=prescription.id,
            child_id=prescription.child_id,
            medication_name=selected_medication['name'],
            dosage=selected_medication.get('dosage', ''),
            frequency=selected_medication.get('frequency', 'ежедневно'),
            doctor_name=prescription.doctor_name,
            start_date=prescription.start_date,
            end_date=prescription.end_date,
            notes=None,
            full_text=f"{selected_medication['name']} {selected_medication.get('dosage', '')} {selected_medication.get('frequency', 'ежедневно')}",
            is_active=1
        )
        
        # Генерируем варианты напоминаний для этого лекарства
        reminder_options = generate_reminder_options(temp_prescription)
        
        if not reminder_options:
            await bot.send_message(
                callback_query.from_user.id,
                "❌ Не удалось сгенерировать напоминания для данного лекарства"
            )
            return
        
        # Формируем сообщение с предложенными напоминаниями
        message_text = f"📋 *Предлагаемые напоминания для {selected_medication['name']}*\n\n"
        
        for i, option in enumerate(reminder_options, 1):
            message_text += (
                f"{i}. {option['description']}\n"
                f"⏰ Время: {option['time']}\n"
                f"🔄 Повторение: {option['repeat_text']}\n\n"
            )
        
        # Создаем клавиатуру с кнопками
        keyboard = InlineKeyboardMarkup(row_width=1)
        for i, option in enumerate(reminder_options, 1):
            keyboard.add(
                InlineKeyboardButton(
                    f"✅ Добавить напоминание {i}",
                    callback_data=f"add_med_reminder_{prescription_id}_{medication_index}_{i-1}"
                )
            )
        keyboard.add(
            InlineKeyboardButton("✅ Добавить все", callback_data=f"add_all_med_reminders_{prescription_id}_{medication_index}"),
            InlineKeyboardButton("❌ Отмена", callback_data="prescriptions")
        )
        
        # Сохраняем варианты напоминаний в состоянии
        await state.update_data(med_reminder_options=reminder_options)
        
        await bot.send_message(
            callback_query.from_user.id,
            message_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка при создании напоминаний для лекарства: {e}")
        await bot.send_message(
            callback_query.from_user.id,
            "❌ Произошла ошибка при создании напоминаний"
        )
    finally:
        db.close()

# Обработчик для добавления одного напоминания для лекарства
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('add_med_reminder_'))
async def add_med_reminder(callback_query: types.CallbackQuery, state: FSMContext):
    """Добавление одного напоминания для лекарства"""
    await bot.answer_callback_query(callback_query.id)
    
    # Получаем ID назначения, индекс лекарства и индекс напоминания из callback_data
    parts = callback_query.data.split('_')
    prescription_id = int(parts[-3])
    medication_index = int(parts[-2])
    option_index = int(parts[-1])
    
    # Получаем данные из состояния
    user_data = await dp.storage.get_data(user=callback_query.from_user.id)
    medications = user_data.get('medications', [])
    reminder_options = user_data.get('med_reminder_options', [])
    
    if not medications or medication_index >= len(medications) or not reminder_options or option_index >= len(reminder_options):
        await bot.send_message(
            callback_query.from_user.id,
            "❌ Информация о напоминании не найдена"
        )
        return
    
    db: Session = next(get_db())
    try:
        # Получаем информацию о ребенке
        child = db.query(Child).first()
        if not child:
            await bot.send_message(
                callback_query.from_user.id,
                "❌ Сначала зарегистрируйте ребенка"
            )
            return
        
        # Получаем выбранное напоминание
        selected_option = reminder_options[option_index]
        
        # Создаем напоминание
        reminder = create_reminder_from_option(db, child.id, selected_option)
        
        if reminder:
            await bot.send_message(
                callback_query.from_user.id,
                f"✅ Напоминание добавлено: {selected_option['description']}"
            )
        else:
            await bot.send_message(
                callback_query.from_user.id,
                "❌ Не удалось добавить напоминание"
            )
        
        # Возвращаемся к списку назначений
        await process_main_menu(callback_query)
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении напоминания: {e}")
        await bot.send_message(
            callback_query.from_user.id,
            "❌ Произошла ошибка при добавлении напоминания"
        )
    finally:
        db.close()

# Обработчик для добавления всех напоминаний для лекарства
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('add_all_med_reminders_'))
async def add_all_med_reminders(callback_query: types.CallbackQuery, state: FSMContext):
    """Добавление всех предложенных напоминаний для лекарства"""
    await bot.answer_callback_query(callback_query.id)
    
    # Получаем ID назначения и индекс лекарства из callback_data
    parts = callback_query.data.split('_')
    prescription_id = int(parts[-2])
    medication_index = int(parts[-1])
    
    # Получаем данные из состояния
    user_data = await dp.storage.get_data(user=callback_query.from_user.id)
    reminder_options = user_data.get('med_reminder_options', [])
    
    if not reminder_options:
        await bot.send_message(
            callback_query.from_user.id,
            "❌ Информация о напоминаниях не найдена"
        )
        return
    
    db: Session = next(get_db())
    try:
        # Получаем информацию о ребенке
        child = db.query(Child).first()
        if not child:
            await bot.send_message(
                callback_query.from_user.id,
                "❌ Сначала зарегистрируйте ребенка"
            )
            return
        
        # Добавляем все напоминания
        added_count = 0
        for option in reminder_options:
            if create_reminder_from_option(db, child.id, option):
                added_count += 1
        
        await bot.send_message(
            callback_query.from_user.id,
            f"✅ Добавлено напоминаний: {added_count} из {len(reminder_options)}"
        )
        
        # Возвращаемся к списку назначений
        await process_main_menu(callback_query)
        
    except Exception as e:
        logger.error(f"Ошибка при добавлении напоминаний: {e}")
        await bot.send_message(
            callback_query.from_user.id,
            "❌ Произошла ошибка при добавлении напоминаний"
        )
    finally:
        db.close()

# Обработчик для кнопки "Назад в меню"
@dp.message_handler(lambda message: message.text == "🔙 Назад в меню", state="*")
async def back_to_menu(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        await state.finish()
    
    with SessionLocal() as db:
        child = db.query(Child).first()
        if not child:
            await message.answer(
                "Похоже, информация о ребенке отсутствует. Давайте начнем с регистрации."
            )
            await ChildRegistrationState.waiting_for_name.set()
            return
        
    await show_main_menu(message)

# Обработчик для кнопки "Заметки"
@dp.message_handler(lambda message: message.text == "📋 Заметки")
async def notes_menu(message: types.Message):
    # Этот обработчик больше не нужен, так как мы используем InlineKeyboardMarkup
    # Вместо него используется обработчик callback_query в process_main_menu
    pass

# Обработчик для кнопки "Добавить заметку"
@dp.message_handler(lambda message: message.text == "📝 Добавить заметку")
async def add_note_start(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard = add_back_button(keyboard)
    
    await NotesState.waiting_for_title.set()
    await message.answer(
        "Введите заголовок заметки:",
        reply_markup=keyboard
    )

# Обработчик для ввода заголовка заметки
@dp.message_handler(state=NotesState.waiting_for_title)
async def process_note_title(message: types.Message, state: FSMContext):
    if message.text == "🔙 Назад в меню":
        await back_to_menu(message, state)
        return
    
    async with state.proxy() as data:
        data['note_title'] = message.text
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard = add_back_button(keyboard)
    
    await NotesState.waiting_for_content.set()
    await message.answer(
        "Теперь введите содержание заметки:",
        reply_markup=keyboard
    )

# Обработчик для ввода содержания заметки
@dp.message_handler(state=NotesState.waiting_for_content)
async def process_note_content(message: types.Message, state: FSMContext):
    if message.text == "🔙 Назад в меню":
        await back_to_menu(message, state)
        return
    
    async with state.proxy() as data:
        title = data['note_title']
        content = message.text
    
    with SessionLocal() as db:
        child = db.query(Child).first()
        if not child:
            await message.answer("Информация о ребенке отсутствует. Пожалуйста, зарегистрируйте ребенка.")
            await state.finish()
            return
        
        note = Note(
            child_id=child.id,
            title=title,
            content=content,
            timestamp=datetime.now()
        )
        
        db.add(note)
        db.commit()
    
    await state.finish()
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton("📝 Добавить заметку"), types.KeyboardButton("📋 Список заметок"))
    keyboard = add_back_button(keyboard)
    
    await message.answer(
        f"✅ Заметка \"{title}\" успешно сохранена!",
        reply_markup=keyboard
    )

# Обработчик для кнопки "Список заметок"
@dp.message_handler(lambda message: message.text == "📋 Список заметок")
async def list_notes(message: types.Message):
    with SessionLocal() as db:
        child = db.query(Child).first()
        if not child:
            await message.answer("Информация о ребенке отсутствует. Пожалуйста, зарегистрируйте ребенка.")
            return
        
        notes = db.query(Note).filter(Note.child_id == child.id).order_by(Note.timestamp.desc()).all()
        
        if not notes:
            keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
            keyboard.row(types.KeyboardButton("📝 Добавить заметку"))
            keyboard = add_back_button(keyboard)
            
            await message.answer(
                "У вас пока нет сохраненных заметок.",
                reply_markup=keyboard
            )
            return
        
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        for note in notes:
            date_str = note.timestamp.strftime("%d.%m.%Y, %H:%M")
            keyboard.add(types.InlineKeyboardButton(
                text=f"{note.title} ({date_str})",
                callback_data=f"note_{note.id}"
            ))
        
        reply_keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        reply_keyboard.row(types.KeyboardButton("📝 Добавить заметку"))
        reply_keyboard = add_back_button(reply_keyboard)
        
        await message.answer(
            "Список ваших заметок:",
            reply_markup=keyboard
        )
        await message.answer(
            "Выберите действие:",
            reply_markup=reply_keyboard
        )

# Обработчик для выбора заметки из списка
@dp.callback_query_handler(lambda c: c.data.startswith('note_'))
async def show_note(callback_query: types.CallbackQuery):
    note_id = int(callback_query.data.split('_')[1])
    
    with SessionLocal() as db:
        note = db.query(Note).filter(Note.id == note_id).first()
        
        if not note:
            await callback_query.answer("Заметка не найдена.")
            return
        
        date_str = note.timestamp.strftime("%d.%m.%Y, %H:%M")
        
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_note_{note.id}"),
            types.InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete_note_{note.id}")
        )
        
        await callback_query.message.answer(
            f"📝 <b>{note.title}</b>\n"
            f"📅 {date_str}\n\n"
            f"{note.content}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await callback_query.answer()

# Обработчик для удаления заметки
@dp.callback_query_handler(lambda c: c.data.startswith('delete_note_'))
async def delete_note(callback_query: types.CallbackQuery):
    note_id = int(callback_query.data.split('_')[2])
    
    with SessionLocal() as db:
        note = db.query(Note).filter(Note.id == note_id).first()
        
        if not note:
            await callback_query.answer("Заметка не найдена.")
            return
        
        title = note.title
        db.delete(note)
        db.commit()
        
        await callback_query.message.answer(f"✅ Заметка \"{title}\" успешно удалена!")
        await callback_query.answer()

# Обработчик для редактирования заметки
@dp.callback_query_handler(lambda c: c.data.startswith('edit_note_'))
async def edit_note_start(callback_query: types.CallbackQuery, state: FSMContext):
    note_id = int(callback_query.data.split('_')[2])
    
    with SessionLocal() as db:
        note = db.query(Note).filter(Note.id == note_id).first()
        
        if not note:
            await callback_query.answer("Заметка не найдена.")
            return
        
        async with state.proxy() as data:
            data['note_id'] = note.id
            data['note_title'] = note.title
        
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard = add_back_button(keyboard)
        
        await NotesState.waiting_for_edit_content.set()
        await callback_query.message.answer(
            f"Редактирование заметки \"{note.title}\"\n\n"
            f"Текущий текст:\n{note.content}\n\n"
            f"Введите новый текст заметки:",
            reply_markup=keyboard
        )
        
        await callback_query.answer()

# Обработчик для ввода нового содержания заметки
@dp.message_handler(state=NotesState.waiting_for_edit_content)
async def process_edit_note_content(message: types.Message, state: FSMContext):
    if message.text == "🔙 Назад в меню":
        await back_to_menu(message, state)
        return
    
    async with state.proxy() as data:
        note_id = data['note_id']
        title = data['note_title']
    
    with SessionLocal() as db:
        note = db.query(Note).filter(Note.id == note_id).first()
        
        if not note:
            await message.answer("Заметка не найдена.")
            await state.finish()
            return
        
        note.content = message.text
        db.commit()
    
    await state.finish()
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(types.KeyboardButton("📝 Добавить заметку"), types.KeyboardButton("📋 Список заметок"))
    keyboard = add_back_button(keyboard)
    
    await message.answer(
        f"✅ Заметка \"{title}\" успешно обновлена!",
        reply_markup=keyboard
    )

# Обновляем функцию для AI-консультации, добавляя кнопку возврата в меню
@dp.message_handler(lambda message: message.text == "🤖 AI-консультация")
async def ai_consultation(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard = add_back_button(keyboard)
    
    await message.answer(
        "Вы можете задать мне любой вопрос о здоровье и развитии ребенка.\n"
        "Я использую данные о вашем ребенке и медицинскую информацию для ответа.\n\n"
        "Просто напишите свой вопрос:",
        reply_markup=keyboard
    )

# Функция для создания основной клавиатуры
def get_main_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🍼 Кормление", callback_data='feeding'),
        InlineKeyboardButton("⚖️ Вес", callback_data='weight'),
        InlineKeyboardButton("💩 Стул", callback_data='stool'),
        InlineKeyboardButton("💊 Лекарства", callback_data='medication'),
        InlineKeyboardButton("📝 Назначения", callback_data='prescriptions'),
        InlineKeyboardButton("⏰ Напоминания", callback_data='reminders_menu'),
        InlineKeyboardButton("📊 Статистика", callback_data='stats'),
        InlineKeyboardButton("📋 Заметки", callback_data='notes'),
        InlineKeyboardButton("📑 Таблица", callback_data='spreadsheet'),
        InlineKeyboardButton("⚙️ Настройки", callback_data='settings')
    )
    return keyboard

# Функция для добавления кнопки "Назад в меню"
def add_back_button(keyboard):
    keyboard.row(types.KeyboardButton("🔙 Назад в меню"))
    return keyboard

# Обработчик для кнопки "Добавить заметку" из inline клавиатуры
@dp.callback_query_handler(lambda c: c.data == 'add_note')
async def add_note_callback(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard = add_back_button(keyboard)
    
    await NotesState.waiting_for_title.set()
    await bot.send_message(
        callback_query.from_user.id,
        "Введите заголовок заметки:",
        reply_markup=keyboard
    )

# Function to handle callback for add reminder
@dp.callback_query_handler(lambda c: c.data == 'add_reminder')
async def process_add_reminder(callback_query: types.CallbackQuery):
    """Обработка добавления напоминания"""
    await bot.answer_callback_query(callback_query.id)
    
    # Импортируем функцию для начала создания напоминания
    from bot.reminders import create_reminder_start
    await create_reminder_start(callback_query)

# Обработчик для кнопки добавления кормления
@dp.callback_query_handler(lambda c: c.data == 'add_feeding')
async def process_add_feeding(callback_query: types.CallbackQuery):
    """Обработка кнопки добавления кормления"""
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(
        callback_query.from_user.id,
        "Введите количество молока в миллилитрах (например: 80):"
    )
    await FeedingState.waiting_for_amount.set()

# Обработчик для создания напоминаний из назначений с помощью AI
@dp.callback_query_handler(lambda c: c.data == 'create_reminders_from_prescriptions')
async def create_reminders_from_prescriptions(callback_query: types.CallbackQuery):
    """Создание напоминаний на основе назначений с помощью AI"""
    await bot.answer_callback_query(callback_query.id)
    
    db: Session = next(get_db())
    try:
        child = db.query(Child).first()
        
        # Получаем активные назначения
        prescriptions = db.query(Prescription).filter(
            Prescription.child_id == child.id,
            Prescription.is_active == 1
        ).all()
        
        if not prescriptions:
            await bot.send_message(
                callback_query.from_user.id,
                "У вас нет активных назначений для создания напоминаний."
            )
            return
        
        # Отправляем сообщение о генерации
        await bot.send_message(
            callback_query.from_user.id,
            "🤖 Анализирую назначения и создаю напоминания..."
        )
        
        # Генерируем предложения по напоминаниям с помощью AI
        reminders_suggestions = ai_assistant.generate_prescription_reminders(db)
        
        # Добавляем кнопки для управления
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            InlineKeyboardButton("✅ Создать все предложенные", callback_data='create_all_suggested_reminders'),
            InlineKeyboardButton("🔙 Назад к назначениям", callback_data='prescriptions')
        )
        
        await bot.send_message(
            callback_query.from_user.id,
            f"📋 *AI предлагает создать следующие напоминания:*\n\n{reminders_suggestions}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.error(f"Ошибка при создании напоминаний из назначений: {e}")
        await bot.send_message(
            callback_query.from_user.id,
            "❌ Произошла ошибка при создании напоминаний."
        )
    finally:
        db.close()

# Обработчик для кнопки добавления записи о стуле
@dp.callback_query_handler(lambda c: c.data == 'add_stool')
async def process_add_stool(callback_query: types.CallbackQuery):
    """Обработка кнопки добавления записи о стуле"""
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(
        callback_query.from_user.id,
        "💩 Опишите стул ребенка (цвет, консистенция):"
    )
    await StoolState.waiting_for_description.set()

# Обработчик для кнопки добавления веса
@dp.callback_query_handler(lambda c: c.data == 'add_weight')
async def process_add_weight(callback_query: types.CallbackQuery):
    """Обработка кнопки добавления веса"""
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(
        callback_query.from_user.id,
        "Введите текущий вес в килограммах (например: 8.5):"
    )
    await WeightState.waiting_for_weight.set()

if __name__ == '__main__':
    logger.info("Запуск бота...")
    executor.start_polling(dp, skip_updates=True) 