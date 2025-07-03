"""
Модуль для работы с напоминаниями
"""
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ParseMode
from datetime import datetime, timedelta
import logging
import re
from sqlalchemy.orm import Session
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.database import get_db
from database.models import Reminder, Child
from bot.bot import bot, dp, ReminderState

logger = logging.getLogger(__name__)

# Обработчик для создания нового напоминания
@dp.callback_query_handler(lambda c: c.data == 'reminder_create')
async def create_reminder_start(callback_query: types.CallbackQuery):
    """Начало создания напоминания"""
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(
        callback_query.from_user.id,
        "📝 *Создание нового напоминания*\n\n"
        "Введите текст напоминания (например: 'Принять лекарство', 'Посетить врача'):",
        parse_mode=ParseMode.MARKDOWN
    )
    await ReminderState.waiting_for_description.set()

# Обработчик описания напоминания
@dp.message_handler(state=ReminderState.waiting_for_description)
async def process_reminder_description(message: types.Message, state: FSMContext):
    """Обработка описания напоминания"""
    description = message.text.strip()
    if len(description) < 3:
        await message.reply("❌ Описание должно содержать минимум 3 символа. Попробуйте еще раз:")
        return
    
    await state.update_data(description=description)
    await message.reply(
        "⏰ Введите время напоминания в формате ЧЧ:ММ (по МСК)\n"
        "Например: 13:00"
    )
    await ReminderState.waiting_for_time.set()

# Обработчик времени напоминания
@dp.message_handler(state=ReminderState.waiting_for_time)
async def process_reminder_time(message: types.Message, state: FSMContext):
    """Обработка времени напоминания"""
    time_str = message.text.strip()
    
    try:
        # Проверяем формат времени ЧЧ:ММ
        time_obj = datetime.strptime(time_str, "%H:%M").time()
        
        # Создаем дату с сегодняшним днем и указанным временем
        now = datetime.now()
        reminder_time = datetime.combine(now.date(), time_obj)
        
        # Если время уже прошло сегодня, переносим на завтра
        if reminder_time <= now:
            reminder_time = reminder_time + timedelta(days=1)
            
        await state.update_data(reminder_time=reminder_time)
        
        # Спрашиваем о типе повторения
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton("🔂 Определенная дата", callback_data='repeat_once'),
            InlineKeyboardButton("🔄 Каждый день", callback_data='repeat_daily')
        )
        
        await message.reply(
            "🔄 Выберите тип повторения напоминания:",
            reply_markup=keyboard
        )
        await ReminderState.waiting_for_repeat_type.set()
        
    except ValueError:
        await message.reply(
            "❌ Неверный формат времени. Используйте формат ЧЧ:ММ (например: 13:00). Попробуйте еще раз:"
        )
        return

# Обработчик типа повторения
@dp.callback_query_handler(lambda c: c.data.startswith('repeat_'), state=ReminderState.waiting_for_repeat_type)
async def process_reminder_repeat_type(callback_query: types.CallbackQuery, state: FSMContext):
    """Обработка типа повторения"""
    repeat_type = callback_query.data.split('_')[1]  # once или daily
    await state.update_data(repeat_type=repeat_type)
    
    if repeat_type == 'once':
        # Если выбрана определенная дата, спрашиваем дату
        await bot.send_message(
            callback_query.from_user.id,
            "📅 Введите дату напоминания в формате ДД.ММ.ГГГГ\n"
            "Например: 01.08.2023"
        )
        await ReminderState.waiting_for_date.set()
    else:
        # Если каждый день, устанавливаем интервал 1 и создаем напоминание
        await state.update_data(repeat_interval=1)
        await create_reminder(callback_query, state)

# Обработчик даты для однократного напоминания
@dp.message_handler(state=ReminderState.waiting_for_date)
async def process_reminder_date(message: types.Message, state: FSMContext):
    """Обработка даты для однократного напоминания"""
    date_str = message.text.strip()
    
    try:
        # Парсим дату
        date_obj = datetime.strptime(date_str, "%d.%m.%Y").date()
        
        # Проверяем, что дата не в прошлом
        if date_obj < datetime.now().date():
            await message.reply("❌ Дата напоминания должна быть в будущем. Попробуйте еще раз:")
            return
        
        # Получаем сохраненное время
        data = await state.get_data()
        reminder_time = data['reminder_time']
        
        # Создаем новую дату с указанной датой и сохраненным временем
        new_reminder_time = datetime.combine(date_obj, reminder_time.time())
        
        # Обновляем время напоминания
        await state.update_data(reminder_time=new_reminder_time)
        
        # Устанавливаем интервал 1 для однократного напоминания
        await state.update_data(repeat_interval=1)
        
        # Создаем напоминание
        await create_reminder(message, state)
        
    except ValueError:
        await message.reply(
            "❌ Неверный формат даты. Используйте формат ДД.ММ.ГГГГ (например: 01.08.2023). Попробуйте еще раз:"
        )
        return

# Обработчик интервала повторения
@dp.message_handler(state=ReminderState.waiting_for_repeat_interval)
async def process_reminder_interval(message: types.Message, state: FSMContext):
    """Обработка интервала повторения"""
    try:
        interval = int(message.text.strip())
        if interval <= 0:
            await message.reply("❌ Интервал должен быть положительным числом. Попробуйте еще раз:")
            return
            
        await state.update_data(repeat_interval=interval)
        await create_reminder(message, state)
    except ValueError:
        await message.reply("❌ Введите целое число. Попробуйте еще раз:")

# Функция создания напоминания
async def create_reminder(message_or_callback, state: FSMContext):
    """Создание напоминания в базе данных"""
    user_id = message_or_callback.from_user.id if isinstance(message_or_callback, types.Message) else message_or_callback.from_user.id
    
    data = await state.get_data()
    description = data.get('description')
    reminder_time = data.get('reminder_time')
    repeat_type = data.get('repeat_type', 'once')
    repeat_interval = data.get('repeat_interval', 1)
    
    db: Session = next(get_db())
    try:
        # Получаем ребенка
        child = db.query(Child).first()
        if not child:
            await bot.send_message(user_id, "❌ Сначала зарегистрируйте ребенка")
            await state.finish()
            return
            
        # Создаем напоминание
        reminder = Reminder(
            child_id=child.id,
            description=description,
            reminder_time=reminder_time,
            status='active',
            repeat_type=repeat_type,
            repeat_interval=repeat_interval
        )
        
        db.add(reminder)
        db.commit()
        
        # Формируем сообщение об успехе
        repeat_text = "однократное"
        if repeat_type == 'daily':
            repeat_text = f"каждые {repeat_interval} день(дней)"
        elif repeat_type == 'weekly':
            repeat_text = f"каждые {repeat_interval} неделю(недель)"
        elif repeat_type == 'monthly':
            repeat_text = f"каждые {repeat_interval} месяц(ев)"
            
        success_message = f"""✅ *Напоминание создано!*

📝 Описание: {description}
⏰ Время: {reminder_time.strftime('%d.%m.%Y %H:%M')}
🔄 Повторение: {repeat_text}
"""
        
        # Создаем клавиатуру для действий
        keyboard = InlineKeyboardMarkup()
        keyboard.row(
            InlineKeyboardButton("📝 Все напоминания", callback_data='reminders_list'),
            InlineKeyboardButton("➕ Создать еще", callback_data='reminder_create')
        )
        keyboard.add(InlineKeyboardButton("🔙 В меню", callback_data='reminders_menu'))
        
        await bot.send_message(
            user_id,
            success_message,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Ошибка при создании напоминания: {e}")
        await bot.send_message(
            user_id,
            "❌ Произошла ошибка при создании напоминания. Попробуйте позже."
        )
    finally:
        db.close()
        await state.finish()

# Обработчик для отметки напоминания как выполненного
@dp.callback_query_handler(lambda c: c.data.startswith('reminder_complete_'))
async def complete_reminder(callback_query: types.CallbackQuery):
    """Отметка напоминания как выполненного"""
    reminder_id = int(callback_query.data.split('_')[2])
    
    db: Session = next(get_db())
    try:
        reminder = db.query(Reminder).get(reminder_id)
        if not reminder:
            await bot.answer_callback_query(callback_query.id, "❌ Напоминание не найдено")
            return
            
        # Обновляем статус
        reminder.status = 'completed'
        
        # Проверяем, связано ли напоминание с приемом лекарства
        medication_keywords = ['лекарство', 'таблетка', 'таблетки', 'прием', 'принять', 'выпить', 
                             'лекарства', 'препарат', 'капли', 'сироп', 'антибиотик']
        
        is_medication_reminder = any(keyword in reminder.description.lower() for keyword in medication_keywords)
        
        # Если это напоминание о лекарстве, записываем прием лекарства
        if is_medication_reminder:
            try:
                # Определяем название лекарства из описания напоминания
                # Простая эвристика: берем первое слово после глагола "принять", "выпить" и т.д.
                description_lower = reminder.description.lower()
                medication_name = reminder.description  # По умолчанию всё описание
                dosage = "Из напоминания"
                
                # Ищем ключевые слова и извлекаем название лекарства
                for verb in ['принять', 'выпить', 'дать']:
                    if verb in description_lower:
                        parts = description_lower.split(verb)
                        if len(parts) > 1:
                            # Берем первое слово после глагола
                            medication_name = parts[1].strip().split()[0].capitalize()
                            break
                
                # Ищем дозировку (обычно после названия лекарства)
                dosage_keywords = ['мг', 'мл', 'таблетку', 'таблетки', 'капли', 'ложку', 'ложки']
                for keyword in dosage_keywords:
                    if keyword in description_lower:
                        # Ищем число перед ключевым словом
                        match = re.search(r'(\d+)\s*' + keyword, description_lower)
                        if match:
                            dosage = f"{match.group(1)} {keyword}"
                            break
                
                # Импортируем модель Medication
                from database.models import Medication
                
                # Создаем запись о приеме лекарства
                medication = Medication(
                    child_id=reminder.child_id,
                    medication_name=medication_name,
                    dosage=dosage,
                    timestamp=datetime.now()
                )
                db.add(medication)
                
                # Уведомляем пользователя о записи лекарства
                await bot.send_message(
                    callback_query.from_user.id,
                    f"✅ Прием лекарства '{medication_name}' ({dosage}) автоматически записан"
                )
            except Exception as med_error:
                logger.error(f"Ошибка при записи приема лекарства: {med_error}")
        
        # Если это повторяющееся напоминание, создаем следующее
        if reminder.repeat_type != 'once':
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
        
        db.commit()
        
        await bot.answer_callback_query(callback_query.id, "✅ Напоминание отмечено как выполненное")
        
        # Показываем обновленный список
        await show_reminders_list(callback_query)
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении напоминания: {e}")
        await bot.answer_callback_query(
            callback_query.id,
            "❌ Произошла ошибка при обновлении напоминания"
        )
    finally:
        db.close()

# Обработчик для пропуска напоминания
@dp.callback_query_handler(lambda c: c.data.startswith('reminder_skip_'))
async def skip_reminder(callback_query: types.CallbackQuery):
    """Пропуск напоминания"""
    reminder_id = int(callback_query.data.split('_')[2])
    
    db: Session = next(get_db())
    try:
        reminder = db.query(Reminder).get(reminder_id)
        if not reminder:
            await bot.answer_callback_query(callback_query.id, "❌ Напоминание не найдено")
            return
            
        # Обновляем статус
        reminder.status = 'skipped'
        
        # Если это повторяющееся напоминание, создаем следующее (как и в complete_reminder)
        if reminder.repeat_type != 'once':
            next_time = None
            
            if reminder.repeat_type == 'daily':
                next_time = reminder.reminder_time + timedelta(days=reminder.repeat_interval)
            elif reminder.repeat_type == 'weekly':
                next_time = reminder.reminder_time + timedelta(weeks=reminder.repeat_interval)
            elif reminder.repeat_type == 'monthly':
                next_month = reminder.reminder_time.month + reminder.repeat_interval
                next_year = reminder.reminder_time.year + (next_month - 1) // 12
                next_month = ((next_month - 1) % 12) + 1
                
                next_time = reminder.reminder_time.replace(year=next_year, month=next_month)
            
            if next_time:
                new_reminder = Reminder(
                    child_id=reminder.child_id,
                    description=reminder.description,
                    reminder_time=next_time,
                    status='active',
                    repeat_type=reminder.repeat_type,
                    repeat_interval=reminder.repeat_interval
                )
                db.add(new_reminder)
        
        db.commit()
        
        await bot.answer_callback_query(callback_query.id, "⏭️ Напоминание пропущено")
        
        # Показываем обновленный список
        await show_reminders_list(callback_query)
        
    except Exception as e:
        logger.error(f"Ошибка при пропуске напоминания: {e}")
        await bot.answer_callback_query(
            callback_query.id,
            "❌ Произошла ошибка при пропуске напоминания"
        )
    finally:
        db.close()

# Обработчик для удаления напоминания
@dp.callback_query_handler(lambda c: c.data.startswith('reminder_delete_'))
async def delete_reminder(callback_query: types.CallbackQuery):
    """Удаление напоминания"""
    reminder_id = int(callback_query.data.split('_')[2])
    
    # Запрашиваем подтверждение
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("✅ Да, удалить", callback_data=f'reminder_delete_confirm_{reminder_id}'),
        InlineKeyboardButton("❌ Отмена", callback_data=f'reminder_view_{reminder_id}')
    )
    
    await bot.send_message(
        callback_query.from_user.id,
        "❓ *Вы уверены, что хотите удалить это напоминание?*\n\n"
        "Это действие нельзя отменить.",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

# Обработчик подтверждения удаления
@dp.callback_query_handler(lambda c: c.data.startswith('reminder_delete_confirm_'))
async def confirm_delete_reminder(callback_query: types.CallbackQuery):
    """Подтверждение удаления напоминания"""
    reminder_id = int(callback_query.data.split('_')[3])
    
    db: Session = next(get_db())
    try:
        reminder = db.query(Reminder).get(reminder_id)
        if not reminder:
            await bot.answer_callback_query(callback_query.id, "❌ Напоминание не найдено")
            return
            
        # Удаляем напоминание
        db.delete(reminder)
        db.commit()
        
        await bot.answer_callback_query(callback_query.id, "✅ Напоминание удалено")
        
        # Показываем обновленный список
        await show_reminders_list(callback_query)
        
    except Exception as e:
        logger.error(f"Ошибка при удалении напоминания: {e}")
        await bot.answer_callback_query(
            callback_query.id,
            "❌ Произошла ошибка при удалении напоминания"
        )
    finally:
        db.close()

# Обработчик для редактирования напоминания
@dp.callback_query_handler(lambda c: c.data.startswith('reminder_edit_'))
async def edit_reminder(callback_query: types.CallbackQuery):
    """Редактирование напоминания"""
    reminder_id = int(callback_query.data.split('_')[2])
    
    # Создаем клавиатуру с выбором поля для редактирования
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("📝 Изменить описание", callback_data=f'edit_description_{reminder_id}'),
        InlineKeyboardButton("⏰ Изменить время", callback_data=f'edit_time_{reminder_id}'),
        InlineKeyboardButton("🔄 Изменить тип повторения", callback_data=f'edit_repeat_type_{reminder_id}'),
        InlineKeyboardButton("📊 Изменить интервал повторения", callback_data=f'edit_repeat_interval_{reminder_id}'),
        InlineKeyboardButton("🔙 Назад", callback_data=f'reminder_view_{reminder_id}')
    )
    
    await bot.send_message(
        callback_query.from_user.id,
        "✏️ *Редактирование напоминания*\n\n"
        "Выберите, что хотите изменить:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

# Импортируем функцию для показа списка напоминаний
from bot.bot import show_reminders_list 