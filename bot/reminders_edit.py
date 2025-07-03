"""
Модуль для редактирования напоминаний
"""
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ParseMode
from datetime import datetime, timedelta
import logging
from sqlalchemy.orm import Session
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import get_db
from database.models import Reminder
from bot.bot import bot, dp, ReminderState

logger = logging.getLogger(__name__)

# Обработчики для редактирования описания напоминания
@dp.callback_query_handler(lambda c: c.data.startswith('edit_description_'))
async def edit_description_start(callback_query: types.CallbackQuery, state: FSMContext):
    """Начало редактирования описания"""
    reminder_id = int(callback_query.data.split('_')[2])
    
    # Сохраняем ID напоминания в состоянии
    await state.update_data(reminder_id=reminder_id)
    
    db: Session = next(get_db())
    try:
        reminder = db.query(Reminder).get(reminder_id)
        if not reminder:
            await bot.answer_callback_query(callback_query.id, "❌ Напоминание не найдено")
            return
            
        await bot.send_message(
            callback_query.from_user.id,
            f"📝 *Редактирование описания*\n\n"
            f"Текущее описание: {reminder.description}\n\n"
            f"Введите новое описание:",
            parse_mode=ParseMode.MARKDOWN
        )
        
        await ReminderState.waiting_for_new_description.set()
        
    except Exception as e:
        logger.error(f"Ошибка при начале редактирования описания: {e}")
        await bot.answer_callback_query(
            callback_query.id,
            "❌ Произошла ошибка при редактировании"
        )
    finally:
        db.close()

@dp.message_handler(state=ReminderState.waiting_for_new_description)
async def process_new_description(message: types.Message, state: FSMContext):
    """Обработка нового описания"""
    new_description = message.text.strip()
    if len(new_description) < 3:
        await message.reply("❌ Описание должно содержать минимум 3 символа. Попробуйте еще раз:")
        return
    
    data = await state.get_data()
    reminder_id = data.get('reminder_id')
    
    db: Session = next(get_db())
    try:
        reminder = db.query(Reminder).get(reminder_id)
        if not reminder:
            await message.reply("❌ Напоминание не найдено")
            await state.finish()
            return
            
        # Обновляем описание
        old_description = reminder.description
        reminder.description = new_description
        db.commit()
        
        await message.reply(
            f"✅ Описание обновлено!\n\n"
            f"Было: {old_description}\n"
            f"Стало: {new_description}"
        )
        
        # Показываем обновленное напоминание
        await show_reminder_after_edit(message, reminder_id)
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении описания: {e}")
        await message.reply("❌ Произошла ошибка при обновлении описания")
    finally:
        db.close()
        await state.finish()

# Обработчики для редактирования времени напоминания
@dp.callback_query_handler(lambda c: c.data.startswith('edit_time_'))
async def edit_time_start(callback_query: types.CallbackQuery, state: FSMContext):
    """Начало редактирования времени"""
    reminder_id = int(callback_query.data.split('_')[2])
    
    # Сохраняем ID напоминания в состоянии
    await state.update_data(reminder_id=reminder_id)
    
    db: Session = next(get_db())
    try:
        reminder = db.query(Reminder).get(reminder_id)
        if not reminder:
            await bot.answer_callback_query(callback_query.id, "❌ Напоминание не найдено")
            return
            
        await bot.send_message(
            callback_query.from_user.id,
            f"⏰ *Редактирование времени*\n\n"
            f"Текущее время: {reminder.reminder_time.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Введите новое время в формате ДД.ММ.ГГГГ ЧЧ:ММ\n"
            f"Например: 01.08.2023 14:30\n\n"
            f"Или введите время через сколько напомнить в формате +ЧЧ:ММ\n"
            f"Например: +01:30 (через 1 час 30 минут)",
            parse_mode=ParseMode.MARKDOWN
        )
        
        await ReminderState.waiting_for_new_time.set()
        
    except Exception as e:
        logger.error(f"Ошибка при начале редактирования времени: {e}")
        await bot.answer_callback_query(
            callback_query.id,
            "❌ Произошла ошибка при редактировании"
        )
    finally:
        db.close()

@dp.message_handler(state=ReminderState.waiting_for_new_time)
async def process_new_time(message: types.Message, state: FSMContext):
    """Обработка нового времени"""
    time_str = message.text.strip()
    
    try:
        # Проверяем, если это относительное время (+ЧЧ:ММ)
        if time_str.startswith('+'):
            time_parts = time_str[1:].split(':')
            hours = int(time_parts[0])
            minutes = int(time_parts[1]) if len(time_parts) > 1 else 0
            
            new_time = datetime.now() + timedelta(hours=hours, minutes=minutes)
        else:
            # Абсолютное время в формате ДД.ММ.ГГГГ ЧЧ:ММ
            new_time = datetime.strptime(time_str, "%d.%m.%Y %H:%M")
            
            # Проверка, что время в будущем
            if new_time <= datetime.now():
                await message.reply("❌ Время напоминания должно быть в будущем. Попробуйте еще раз:")
                return
    except ValueError:
        await message.reply(
            "❌ Неверный формат времени. Используйте ДД.ММ.ГГГГ ЧЧ:ММ или +ЧЧ:ММ. Попробуйте еще раз:"
        )
        return
    
    data = await state.get_data()
    reminder_id = data.get('reminder_id')
    
    db: Session = next(get_db())
    try:
        reminder = db.query(Reminder).get(reminder_id)
        if not reminder:
            await message.reply("❌ Напоминание не найдено")
            await state.finish()
            return
            
        # Обновляем время
        old_time = reminder.reminder_time
        reminder.reminder_time = new_time
        db.commit()
        
        await message.reply(
            f"✅ Время обновлено!\n\n"
            f"Было: {old_time.strftime('%d.%m.%Y %H:%M')}\n"
            f"Стало: {new_time.strftime('%d.%m.%Y %H:%M')}"
        )
        
        # Показываем обновленное напоминание
        await show_reminder_after_edit(message, reminder_id)
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении времени: {e}")
        await message.reply("❌ Произошла ошибка при обновлении времени")
    finally:
        db.close()
        await state.finish()

# Обработчики для редактирования типа повторения
@dp.callback_query_handler(lambda c: c.data.startswith('edit_repeat_type_'))
async def edit_repeat_type_start(callback_query: types.CallbackQuery, state: FSMContext):
    """Начало редактирования типа повторения"""
    reminder_id = int(callback_query.data.split('_')[3])
    
    # Сохраняем ID напоминания в состоянии
    await state.update_data(reminder_id=reminder_id)
    
    # Создаем клавиатуру с типами повторения
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🔂 Однократно", callback_data='new_repeat_once'),
        InlineKeyboardButton("🔄 Ежедневно", callback_data='new_repeat_daily'),
        InlineKeyboardButton("📅 Еженедельно", callback_data='new_repeat_weekly'),
        InlineKeyboardButton("📆 Ежемесячно", callback_data='new_repeat_monthly')
    )
    
    await bot.send_message(
        callback_query.from_user.id,
        "🔄 *Редактирование типа повторения*\n\n"
        "Выберите новый тип повторения:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    
    await ReminderState.waiting_for_new_repeat_type.set()

@dp.callback_query_handler(lambda c: c.data.startswith('new_repeat_'), state=ReminderState.waiting_for_new_repeat_type)
async def process_new_repeat_type(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработка нового типа повторения"""
    new_repeat_type = callback_query.data.split('_')[2]  # once, daily, weekly, monthly
    
    data = await state.get_data()
    reminder_id = data.get('reminder_id')
    
    db: Session = next(get_db())
    try:
        reminder = db.query(Reminder).get(reminder_id)
        if not reminder:
            await bot.answer_callback_query(callback_query.id, "❌ Напоминание не найдено")
            await state.finish()
            return
            
        # Если меняем на однократное, сразу обновляем
        if new_repeat_type == 'once':
            old_repeat_type = reminder.repeat_type
            reminder.repeat_type = new_repeat_type
            db.commit()
            
            await bot.send_message(
                callback_query.from_user.id,
                f"✅ Тип повторения обновлен на 'Однократно'!"
            )
            
            # Показываем обновленное напоминание
            await show_reminder_after_edit(callback_query.message, reminder_id)
            await state.finish()
        else:
            # Сохраняем новый тип повторения в состоянии
            await state.update_data(new_repeat_type=new_repeat_type)
            
            # Запрашиваем интервал
            await bot.send_message(
                callback_query.from_user.id,
                f"📊 Введите интервал повторения (каждые N {'дней' if new_repeat_type == 'daily' else 'недель' if new_repeat_type == 'weekly' else 'месяцев'}):"
            )
            
            await ReminderState.waiting_for_new_repeat_interval.set()
            
    except Exception as e:
        logger.error(f"Ошибка при обновлении типа повторения: {e}")
        await bot.answer_callback_query(
            callback_query.id,
            "❌ Произошла ошибка при обновлении типа повторения"
        )
        await state.finish()
    finally:
        db.close()

@dp.message_handler(state=ReminderState.waiting_for_new_repeat_interval)
async def process_new_repeat_interval(message: types.Message, state: FSMContext):
    """Обработка нового интервала повторения"""
    try:
        new_interval = int(message.text.strip())
        if new_interval <= 0:
            await message.reply("❌ Интервал должен быть положительным числом. Попробуйте еще раз:")
            return
            
        data = await state.get_data()
        reminder_id = data.get('reminder_id')
        new_repeat_type = data.get('new_repeat_type')
        
        db: Session = next(get_db())
        try:
            reminder = db.query(Reminder).get(reminder_id)
            if not reminder:
                await message.reply("❌ Напоминание не найдено")
                await state.finish()
                return
                
            # Обновляем тип повторения и интервал
            old_repeat_type = reminder.repeat_type
            old_interval = reminder.repeat_interval
            
            reminder.repeat_type = new_repeat_type
            reminder.repeat_interval = new_interval
            db.commit()
            
            # Формируем текст типа повторения
            repeat_text = {
                'daily': 'Ежедневно',
                'weekly': 'Еженедельно',
                'monthly': 'Ежемесячно'
            }
            
            await message.reply(
                f"✅ Тип повторения обновлен!\n\n"
                f"Было: {repeat_text.get(old_repeat_type, 'Однократно')} "
                f"(интервал: {old_interval if old_repeat_type != 'once' else 'Н/Д'})\n"
                f"Стало: {repeat_text.get(new_repeat_type)} (интервал: {new_interval})"
            )
            
            # Показываем обновленное напоминание
            await show_reminder_after_edit(message, reminder_id)
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении интервала повторения: {e}")
            await message.reply("❌ Произошла ошибка при обновлении интервала повторения")
        finally:
            db.close()
            await state.finish()
    except ValueError:
        await message.reply("❌ Введите целое число. Попробуйте еще раз:")

# Обработчик для редактирования интервала повторения
@dp.callback_query_handler(lambda c: c.data.startswith('edit_repeat_interval_'))
async def edit_repeat_interval_start(callback_query: types.CallbackQuery, state: FSMContext):
    """Начало редактирования интервала повторения"""
    reminder_id = int(callback_query.data.split('_')[3])
    
    # Сохраняем ID напоминания в состоянии
    await state.update_data(reminder_id=reminder_id)
    
    db: Session = next(get_db())
    try:
        reminder = db.query(Reminder).get(reminder_id)
        if not reminder:
            await bot.answer_callback_query(callback_query.id, "❌ Напоминание не найдено")
            return
            
        # Проверяем, что напоминание повторяющееся
        if reminder.repeat_type == 'once':
            await bot.send_message(
                callback_query.from_user.id,
                "❌ Нельзя изменить интервал для однократного напоминания.\n"
                "Сначала измените тип повторения."
            )
            return
            
        repeat_type_text = {
            'daily': 'дней',
            'weekly': 'недель',
            'monthly': 'месяцев'
        }
        
        await bot.send_message(
            callback_query.from_user.id,
            f"📊 *Редактирование интервала повторения*\n\n"
            f"Текущий интервал: каждые {reminder.repeat_interval} {repeat_type_text.get(reminder.repeat_type)}\n\n"
            f"Введите новый интервал (целое положительное число):",
            parse_mode=ParseMode.MARKDOWN
        )
        
        await ReminderState.waiting_for_new_repeat_interval.set()
        
    except Exception as e:
        logger.error(f"Ошибка при начале редактирования интервала: {e}")
        await bot.answer_callback_query(
            callback_query.id,
            "❌ Произошла ошибка при редактировании"
        )
    finally:
        db.close()

# Вспомогательная функция для показа напоминания после редактирования
async def show_reminder_after_edit(message, reminder_id):
    """Показать напоминание после редактирования"""
    db: Session = next(get_db())
    try:
        reminder = db.query(Reminder).get(reminder_id)
        if not reminder:
            await message.reply("❌ Напоминание не найдено")
            return
            
        # Формируем информацию о напоминании
        status_text = "✅ Выполнено" if reminder.status == 'completed' else "⏳ Активно" if reminder.status == 'active' else "⏭️ Пропущено"
        repeat_text = "Однократное" if reminder.repeat_type == 'once' else f"Повторяется каждые {reminder.repeat_interval} "
        
        if reminder.repeat_type == 'daily':
            repeat_text += "день(дней)"
        elif reminder.repeat_type == 'weekly':
            repeat_text += "неделю(недель)"
        elif reminder.repeat_type == 'monthly':
            repeat_text += "месяц(ев)"
            
        reminder_info = f"""📝 *{reminder.description}*

⏰ Время: {reminder.reminder_time.strftime('%d.%m.%Y %H:%M')}
🔄 Повторение: {repeat_text}
📊 Статус: {status_text}
"""
        
        # Создаем клавиатуру для управления
        keyboard = InlineKeyboardMarkup(row_width=2)
        
        # Кнопки действий в зависимости от статуса
        if reminder.status == 'active':
            keyboard.row(
                InlineKeyboardButton("✅ Выполнено", callback_data=f'reminder_complete_{reminder_id}'),
                InlineKeyboardButton("⏭️ Пропустить", callback_data=f'reminder_skip_{reminder_id}')
            )
        
        # Кнопки редактирования и удаления
        keyboard.row(
            InlineKeyboardButton("✏️ Редактировать", callback_data=f'reminder_edit_{reminder_id}'),
            InlineKeyboardButton("🗑️ Удалить", callback_data=f'reminder_delete_{reminder_id}')
        )
        
        # Кнопки навигации
        keyboard.row(
            InlineKeyboardButton("📝 Все напоминания", callback_data='reminders_list'),
            InlineKeyboardButton("🔙 В меню", callback_data='reminders_menu')
        )
        
        await message.reply(
            reminder_info,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Ошибка при показе напоминания: {e}")
        await message.reply("❌ Произошла ошибка при показе напоминания")
    finally:
        db.close()

# Импорт для обеспечения работы обработчиков
from bot.reminders import show_reminders_list 