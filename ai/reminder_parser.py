"""
Модуль для распознавания напоминаний из текста с помощью ИИ
"""
import logging
import re
from datetime import datetime, timedelta
import openai
from typing import Dict, Optional, Tuple
import json

logger = logging.getLogger(__name__)

class ReminderParser:
    """Класс для распознавания напоминаний из текста"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        
    def parse_reminder(self, text: str) -> Optional[Dict]:
        """
        Распознает напоминание из текста
        
        Args:
            text: Текст сообщения
            
        Returns:
            Словарь с параметрами напоминания или None, если напоминание не распознано
        """
        try:
            # Проверяем, похоже ли это на запрос о напоминании
            if not self._is_reminder_request(text):
                return None
                
            # Формируем запрос к ИИ для распознавания напоминания
            prompt = f"""Распознай напоминания из текста пользователя и верни результат в формате JSON.
            
            Текст пользователя: "{text}"
            
            ВАЖНО: Если в тексте упоминается несколько разных действий или времени, создай ОТДЕЛЬНОЕ напоминание для каждого.
            
            Формат ответа должен быть JSON массив напоминаний:
            [
              {{
                "description": "описание напоминания (что нужно сделать)",
                "time": "время напоминания в формате ЧЧ:ММ",
                "date": "дата напоминания в формате ДД.ММ.ГГГГ (если указано, иначе сегодня)",
                "repeat_type": "тип повторения (once, daily, weekly, monthly)",
                "repeat_interval": "интервал повторения (число)",
                "is_reminder": true
              }}
            ]
            
            Правила распознавания:
            1. Если пользователь говорит "каждый день", "ежедневно" - repeat_type: "daily"
            2. Если пользователь говорит "каждую неделю", "еженедельно" - repeat_type: "weekly"
            3. Если пользователь говорит "каждый месяц", "ежемесячно" - repeat_type: "monthly"
            4. Если не указано повторение - repeat_type: "once"
            5. Время указывается в 24-часовом формате (13:00, не 1:00 PM)
            6. Если время указано как "в 13" или "в 13 часов" - преобразуй в "13:00"
            7. Для кастомных интервалов (например, "каждые 2 дня", "каждые 3 часа") - используй соответствующий repeat_type и repeat_interval
            8. "Утром" = "08:00", "Днем" = "14:00", "Вечером" = "20:00", "Ночью" = "22:00"
            9. ВАЖНО: Разделяй разные лекарства/действия на отдельные напоминания
            
            Примеры:
            1. "Напомни мне принять лекарство в 13:00" -> [{{"description": "принять лекарство", "time": "13:00", "date": "текущая дата", "repeat_type": "once", "repeat_interval": 1, "is_reminder": true}}]
            2. "Напоминай мне каждый день в 9:00 делать зарядку" -> [{{"description": "делать зарядку", "time": "09:00", "date": "текущая дата", "repeat_type": "daily", "repeat_interval": 1, "is_reminder": true}}]
            3. "напоминай мне каждый день в 13 пить лекарство" -> [{{"description": "пить лекарство", "time": "13:00", "date": "текущая дата", "repeat_type": "daily", "repeat_interval": 1, "is_reminder": true}}]
            4. "напоминай каждый день пить элькар в 13, витамин д в 14" -> [
                {{"description": "пить элькар", "time": "13:00", "date": "текущая дата", "repeat_type": "daily", "repeat_interval": 1, "is_reminder": true}},
                {{"description": "пить витамин д", "time": "14:00", "date": "текущая дата", "repeat_type": "daily", "repeat_interval": 1, "is_reminder": true}}
              ]
            
            Верни только JSON массив без дополнительного текста. Если это не запрос на напоминание, верни пустой массив [].
            """
            
            # Запрос к OpenAI API (старый интерфейс)
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Ты - помощник для распознавания напоминаний из текста."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.3,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0
            )
            
            # Получаем ответ
            assistant_response = response['choices'][0]['message']['content']
            
            # Извлекаем JSON из ответа
            reminder_data = self._extract_json(assistant_response)
            
            # Проверяем, что получили напоминания
            if reminder_data and 'reminders' in reminder_data:
                reminders = reminder_data['reminders']
                # Обрабатываем дату и время для каждого напоминания
                processed_reminders = []
                for reminder in reminders:
                    if reminder.get('is_reminder', False):
                        processed_reminder = self._process_datetime(reminder)
                        processed_reminders.append(processed_reminder)
                
                return processed_reminders if processed_reminders else None
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при распознавании напоминания: {e}")
            return None
    
    def _is_reminder_request(self, text: str) -> bool:
        """Проверяет, похоже ли сообщение на запрос о напоминании"""
        # Ключевые слова для напоминаний
        keywords = [
            'напомни', 'напоминай', 'напоминание', 'уведомление', 'уведомлять',
            'каждый день', 'каждую неделю', 'каждый месяц', 'ежедневно', 'еженедельно', 'ежемесячно',
            'сделай напоминание', 'создай напоминание', 'поставь напоминание',
            'не забыть', 'не забудь', 'через час', 'через минут', 'завтра',
            'послезавтра', 'в понедельник', 'во вторник', 'в среду', 'в четверг',
            'в пятницу', 'в субботу', 'в воскресенье', 'утром', 'днем', 'вечером',
            'сегодня в', 'завтра в', 'каждое утро', 'каждый вечер'
        ]
        
        # Приводим текст к нижнему регистру
        text_lower = text.lower()
        
        # Проверяем наличие ключевых слов
        for keyword in keywords:
            if keyword in text_lower:
                return True
                
        return False
    
    def _extract_json(self, text: str) -> Optional[Dict]:
        """Извлекает JSON из текста"""
        try:
            # Ищем JSON массив в тексте
            json_match = re.search(r'\[.*\]', text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                reminders_array = json.loads(json_str)
                # Возвращаем массив напоминаний
                return {'reminders': reminders_array} if reminders_array else None
                
            # Если не нашли массив, ищем одиночный объект для обратной совместимости
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                reminder_obj = json.loads(json_str)
                # Оборачиваем в массив для единообразия
                return {'reminders': [reminder_obj]} if reminder_obj.get('is_reminder', False) else None
                
            # Если не нашли JSON, пробуем распарсить весь текст
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return {'reminders': parsed} if parsed else None
            elif isinstance(parsed, dict) and parsed.get('is_reminder', False):
                return {'reminders': [parsed]}
            
            return None
        except:
            return None
    
    def _process_datetime(self, reminder_data: Dict) -> Dict:
        """Обрабатывает дату и время в данных напоминания"""
        now = datetime.now()
        
        # Обрабатываем дату
        date_str = reminder_data.get('date', '')
        
        if date_str in ['текущая дата', 'сегодня', None]:
            reminder_data['date'] = now.strftime('%d.%m.%Y')
        elif 'завтра' in date_str.lower():
            tomorrow = now + timedelta(days=1)
            reminder_data['date'] = tomorrow.strftime('%d.%m.%Y')
        elif 'послезавтра' in date_str.lower():
            after_tomorrow = now + timedelta(days=2)
            reminder_data['date'] = after_tomorrow.strftime('%d.%m.%Y')
        elif not date_str:
            reminder_data['date'] = now.strftime('%d.%m.%Y')
        
        # Обрабатываем время
        time_str = reminder_data.get('time', '')
        
        # Проверяем относительное время
        if 'через' in time_str.lower():
            # Извлекаем числа из строки
            numbers = re.findall(r'\d+', time_str)
            if numbers:
                # Определяем единицу времени
                if 'час' in time_str.lower():
                    hours = int(numbers[0])
                    minutes = int(numbers[1]) if len(numbers) > 1 else 0
                    future_time = now + timedelta(hours=hours, minutes=minutes)
                elif 'минут' in time_str.lower():
                    minutes = int(numbers[0])
                    future_time = now + timedelta(minutes=minutes)
                else:
                    # По умолчанию считаем часы
                    hours = int(numbers[0])
                    future_time = now + timedelta(hours=hours)
                
                reminder_data['time'] = future_time.strftime('%H:%M')
                reminder_data['date'] = future_time.strftime('%d.%m.%Y')
        elif 'текущее время' in time_str.lower():
            # Для напоминаний типа "каждые N часов"
            reminder_data['time'] = now.strftime('%H:%M')
        elif not reminder_data.get('time'):
            # Если время не указано, устанавливаем текущее время + 1 час
            next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            reminder_data['time'] = next_hour.strftime('%H:%M')
        
        return reminder_data 