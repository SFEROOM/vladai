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
            prompt = f"""Распознай напоминание из текста пользователя и верни результат в формате JSON.
            
            Текст пользователя: "{text}"
            
            Формат ответа должен быть JSON со следующими полями:
            - description: описание напоминания
            - time: время напоминания в формате ЧЧ:ММ (если указано)
            - date: дата напоминания в формате ДД.ММ.ГГГГ (если указано, иначе сегодня)
            - repeat_type: тип повторения (once, daily, weekly, monthly)
            - repeat_interval: интервал повторения (число)
            - is_reminder: true если это запрос на создание напоминания, false если нет
            
            Примеры:
            1. "Напомни мне принять лекарство в 13:00" -> {{"description": "принять лекарство", "time": "13:00", "date": "текущая дата", "repeat_type": "once", "repeat_interval": 1, "is_reminder": true}}
            2. "Напоминай мне каждый день в 9:00 делать зарядку" -> {{"description": "делать зарядку", "time": "09:00", "date": "текущая дата", "repeat_type": "daily", "repeat_interval": 1, "is_reminder": true}}
            
            Верни только JSON без дополнительного текста.
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
            
            # Проверяем, является ли это напоминанием
            if reminder_data and reminder_data.get('is_reminder', False):
                # Обрабатываем дату и время
                reminder_data = self._process_datetime(reminder_data)
                return reminder_data
            
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
            'сделай напоминание', 'создай напоминание', 'поставь напоминание'
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
            # Ищем JSON в тексте
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                return json.loads(json_str)
                
            # Если не нашли JSON в формате {...}, пробуем распарсить весь текст
            return json.loads(text)
        except:
            return None
    
    def _process_datetime(self, reminder_data: Dict) -> Dict:
        """Обрабатывает дату и время в данных напоминания"""
        now = datetime.now()
        
        # Обрабатываем дату
        if reminder_data.get('date') in ['текущая дата', 'сегодня', None]:
            reminder_data['date'] = now.strftime('%d.%m.%Y')
        
        # Если время не указано, устанавливаем текущее время + 1 час
        if not reminder_data.get('time'):
            next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            reminder_data['time'] = next_hour.strftime('%H:%M')
        
        return reminder_data 