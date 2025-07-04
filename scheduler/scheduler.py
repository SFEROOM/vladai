"""
Модуль для работы с планировщиком задач
"""
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import get_db
from database.models import Reminder, Child, Feeding, Stool, Weight, Medication
from bot.bot import bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ParseMode
from config import LOG_LEVEL, GOOGLE_SHEETS_ENABLED

logger = logging.getLogger(__name__)
logging.basicConfig(level=getattr(logging, LOG_LEVEL))

# Создаем планировщик
scheduler = AsyncIOScheduler()

async def check_reminders():
    """Проверка напоминаний и отправка уведомлений"""
    try:
        db = next(get_db())
        
        # Получаем текущее время
        now = datetime.now()
        
        # Находим все активные напоминания, время которых наступило
        # но не старше 1 минуты (чтобы не отправлять старые напоминания)
        one_minute_ago = now - timedelta(minutes=1)
        reminders = db.query(Reminder).filter(
            Reminder.status == 'active',
            Reminder.reminder_time <= now,
            Reminder.reminder_time > one_minute_ago
        ).all()
        
        if not reminders:
            return
            
        logger.info(f"Найдено {len(reminders)} напоминаний для отправки")
        
        # Получаем всех активных пользователей из базы данных
        from database.models import User
        users = db.query(User).filter(User.is_active == 1).all()
        
        if not users:
            logger.warning("Не удалось найти пользователей для отправки напоминаний")
            return
            
        logger.info(f"Найдено {len(users)} активных пользователей для отправки напоминаний")
        
        # Обрабатываем каждое напоминание
        for reminder in reminders:
            try:
                # Получаем информацию о ребенке
                child = db.query(Child).get(reminder.child_id)
                if not child:
                    logger.warning(f"Ребенок с ID {reminder.child_id} не найден для напоминания {reminder.id}")
                    continue
                
                # Формируем сообщение
                message = f"⏰ *Напоминание для {child.name}*\n\n{reminder.description}"
                
                # Создаем клавиатуру с кнопками
                keyboard = InlineKeyboardMarkup()
                keyboard.row(
                    InlineKeyboardButton("✅ Выполнено", callback_data=f"reminder_complete_{reminder.id}"),
                    InlineKeyboardButton("⏭️ Пропустить", callback_data=f"reminder_skip_{reminder.id}")
                )
                
                # Отправляем напоминание всем активным пользователям
                for user in users:
                    try:
                        await bot.send_message(
                            chat_id=user.telegram_id,
                            text=message,
                            reply_markup=keyboard,
                            parse_mode='Markdown'
                        )
                        logger.info(f"Отправлено напоминание пользователю {user.telegram_id} ({user.username}): {reminder.description}")
                    except Exception as send_error:
                        logger.error(f"Ошибка при отправке напоминания пользователю {user.telegram_id}: {send_error}")
                
                # Если это однократное напоминание, помечаем его как отправленное
                if reminder.repeat_type == 'once':
                    reminder.status = 'sent'
                    db.commit()
                    
                # Если это повторяющееся напоминание, создаем следующее
                else:
                    next_time = None
                    
                    if reminder.repeat_type == 'daily':
                        next_time = reminder.reminder_time + timedelta(days=reminder.repeat_interval)
                    elif reminder.repeat_type == 'weekly':
                        next_time = reminder.reminder_time + timedelta(weeks=reminder.repeat_interval)
                    elif reminder.repeat_type == 'monthly':
                        # Простая реализация для месяцев (не учитывает разное количество дней)
                        next_month = reminder.reminder_time.month + reminder.repeat_interval
                        next_year = reminder.reminder_time.year + (next_month - 1) // 12
                        next_month = ((next_month - 1) % 12) + 1
                        
                        # Создаем дату следующего месяца
                        next_time = reminder.reminder_time.replace(year=next_year, month=next_month)
                    elif reminder.repeat_type == 'hourly':
                        # Для почасовых напоминаний
                        next_time = reminder.reminder_time + timedelta(hours=reminder.repeat_interval)
                    
                    if next_time:
                        # Создаем новое напоминание
                        new_reminder = Reminder(
                            child_id=reminder.child_id,
                            description=reminder.description,
                            reminder_time=next_time,
                            status='active',
                            repeat_type=reminder.repeat_type,
                            repeat_interval=reminder.repeat_interval
                        )
                        db.add(new_reminder)
                        
                        # Помечаем текущее напоминание как отправленное
                        reminder.status = 'sent'
                        
                        db.commit()
                
            except Exception as e:
                logger.error(f"Ошибка при обработке напоминания {reminder.id}: {e}")
                
    except Exception as e:
        logger.error(f"Ошибка при проверке напоминаний: {e}")
    finally:
        db.close()

async def check_feeding_intervals():
    """Проверка интервалов между кормлениями"""
    try:
        db = next(get_db())
        
        # Получаем текущее время
        now = datetime.now()
        
        # Получаем последнее кормление
        last_feeding = db.query(Feeding).order_by(Feeding.timestamp.desc()).first()
        
        if last_feeding:
            # Проверяем, прошло ли более 3 часов с последнего кормления
            time_since_last_feeding = now - last_feeding.timestamp
            
            if time_since_last_feeding > timedelta(hours=3):
                # Получаем информацию о ребенке
                child = db.query(Child).get(last_feeding.child_id)
                
                # Получаем ID пользователя для отправки уведомления
                from aiogram.types import User
                users = await bot.get_updates(limit=1, offset=-1)
                
                if users and users[0].message and users[0].message.from_user:
                    user_id = users[0].message.from_user.id
                    
                    # Отправляем напоминание о кормлении
                    await bot.send_message(
                        chat_id=user_id,
                        text=f"⚠️ *Напоминание о кормлении*\n\n"
                             f"Прошло более 3 часов с последнего кормления {child.name if child else ''}.\n"
                             f"Последнее кормление было в {last_feeding.timestamp.strftime('%H:%M')}.",
                        parse_mode='Markdown'
                    )
                    
                    logger.info(f"Отправлено напоминание о кормлении")
                else:
                    logger.warning("Не удалось определить пользователя для отправки напоминания о кормлении")
        
    except Exception as e:
        logger.error(f"Ошибка при проверке интервалов кормления: {e}")
    finally:
        db.close()

async def generate_daily_report():
    """Генерация ежедневного отчета"""
    try:
        db = next(get_db())
        
        # Получаем текущую дату
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        
        # Получаем данные за вчерашний день
        feedings = db.query(Feeding).filter(
            Feeding.timestamp >= datetime.combine(yesterday, datetime.min.time()),
            Feeding.timestamp < datetime.combine(today, datetime.min.time())
        ).all()
        
        stools = db.query(Stool).filter(
            Stool.timestamp >= datetime.combine(yesterday, datetime.min.time()),
            Stool.timestamp < datetime.combine(today, datetime.min.time())
        ).all()
        
        weights = db.query(Weight).filter(
            Weight.timestamp >= datetime.combine(yesterday, datetime.min.time()),
            Weight.timestamp < datetime.combine(today, datetime.min.time())
        ).all()
        
        # Формируем отчет
        report = f"📊 *Отчет за {yesterday.strftime('%d.%m.%Y')}*\n\n"
        
        # Кормления
        report += f"🍼 *Кормления:* {len(feedings)}\n"
        if feedings:
            total_amount = sum(f.amount for f in feedings)
            report += f"Всего: {total_amount} мл\n"
            report += f"Среднее: {total_amount / len(feedings):.1f} мл\n\n"
        else:
            report += "Нет данных\n\n"
        
        # Стул
        report += f"💩 *Стул:* {len(stools)}\n"
        if stools:
            for stool in stools:
                report += f"- {stool.timestamp.strftime('%H:%M')}: {stool.description}\n"
            report += "\n"
        else:
            report += "Нет данных\n\n"
        
        # Вес
        report += f"⚖️ *Вес:*\n"
        if weights:
            for weight in weights:
                report += f"- {weight.timestamp.strftime('%H:%M')}: {weight.weight} кг\n"
            report += "\n"
        else:
            report += "Нет данных\n\n"
        
        # Получаем ID пользователя для отправки отчета
        from aiogram.types import User
        users = await bot.get_updates(limit=1, offset=-1)
        
        if users and users[0].message and users[0].message.from_user:
            user_id = users[0].message.from_user.id
            
            # Отправляем отчет
            await bot.send_message(
                chat_id=user_id,
                text=report,
                parse_mode='Markdown'
            )
            
            logger.info(f"Отправлен ежедневный отчет")
        else:
            logger.warning("Не удалось определить пользователя для отправки ежедневного отчета")
        
    except Exception as e:
        logger.error(f"Ошибка при генерации ежедневного отчета: {e}")
    finally:
        db.close()

async def sync_google_sheets():
    """Синхронизация данных с Google Sheets"""
    if not GOOGLE_SHEETS_ENABLED:
        return
        
    try:
        db = next(get_db())
        
        # Импортируем менеджер Google Sheets
        from google_sheets.sheets import sheets_manager
        
        # Синхронизируем все данные
        sheets_manager.sync_all_data(db)
        
        logger.info("Выполнена плановая синхронизация с Google Sheets")
    except Exception as e:
        logger.error(f"Ошибка при синхронизации с Google Sheets: {e}")
    finally:
        db.close()

def start_scheduler():
    """Запуск планировщика задач"""
    # Проверка напоминаний каждую минуту
    scheduler.add_job(check_reminders, IntervalTrigger(minutes=1))
    
    # Проверка интервалов кормления каждые 30 минут
    scheduler.add_job(check_feeding_intervals, IntervalTrigger(minutes=30))
    
    # Генерация ежедневного отчета в 9:00
    scheduler.add_job(generate_daily_report, CronTrigger(hour=9, minute=0))
    
    # Синхронизация с Google Sheets каждый час
    if GOOGLE_SHEETS_ENABLED:
        scheduler.add_job(sync_google_sheets, IntervalTrigger(hours=1))
    
    scheduler.start()
    logger.info("Планировщик запущен")

def stop_scheduler():
    """Остановка планировщика задач"""
    scheduler.shutdown()
    logger.info("Планировщик остановлен") 