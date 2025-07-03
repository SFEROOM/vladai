import openai
import logging
from typing import Optional, Dict, List
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class MedicalAIAssistant:
    """AI ассистент для медицинских консультаций с памятью контекста и анализом данных"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        openai.api_key = api_key
        self.conversation_history = []
        self.system_prompt = """Ты - опытный семейный медицинский ассистент с глубокими знаниями в педиатрии. 
        Твоя задача - помогать родителям следить за здоровьем детей, анализировать данные и давать персонализированные рекомендации.
        
        Ты помнишь всю историю переписки и используешь эти данные для контекста.
        
        Ты можешь:
        - Давать рекомендации по питанию и уходу за детьми на основе их возраста и особенностей
        - Анализировать динамику веса, роста и других показателей
        - Помогать интерпретировать симптомы (но всегда рекомендовать обращаться к врачу при серьезных симптомах)
        - Напоминать о прививках и визитах к врачу согласно календарю
        - Отвечать на вопросы о развитии ребенка с учетом его индивидуальных особенностей
        - Анализировать режим кормления и давать рекомендации по его оптимизации
        
        Важно: Ты НЕ заменяешь врача. При серьезных симптомах всегда рекомендуй обратиться к специалисту."""
        
        # Кэш данных для быстрого доступа
        self.data_cache = {
            'child_info': None,
            'weight_history': [],
            'feeding_history': [],
            'medication_history': [],
            'stool_history': [],
            'last_updated': None
        }
        
    def update_data_cache(self, db_session):
        """
        Обновляет кэш данных из базы данных
        
        Args:
            db_session: Сессия базы данных
        """
        from database.models import Child, Weight, Feeding, Medication, Stool
        from datetime import datetime, timedelta
        
        try:
            # Получаем информацию о ребенке
            child = db_session.query(Child).first()
            if not child:
                return
                
            # Базовая информация о ребенке
            age_days = (datetime.now().date() - child.birth_date).days
            age_months = age_days // 30
            age_years = age_days // 365
            
            self.data_cache['child_info'] = {
                'id': child.id,
                'name': child.name,
                'birth_date': child.birth_date.strftime('%d.%m.%Y'),
                'gender': child.gender,
                'age_days': age_days,
                'age_months': age_months,
                'age_years': age_years
            }
            
            # История веса (за последние 6 месяцев)
            six_months_ago = datetime.now() - timedelta(days=180)
            weights = db_session.query(Weight).filter(
                Weight.child_id == child.id,
                Weight.timestamp >= six_months_ago
            ).order_by(Weight.timestamp).all()
            
            self.data_cache['weight_history'] = [
                {
                    'weight': w.weight,
                    'date': w.timestamp.strftime('%d.%m.%Y'),
                    'age_days': (w.timestamp.date() - child.birth_date).days
                } for w in weights
            ]
            
            # История кормлений (за последние 7 дней)
            week_ago = datetime.now() - timedelta(days=7)
            feedings = db_session.query(Feeding).filter(
                Feeding.child_id == child.id,
                Feeding.timestamp >= week_ago
            ).order_by(Feeding.timestamp).all()
            
            self.data_cache['feeding_history'] = [
                {
                    'amount': f.amount,
                    'food_type': f.food_type,
                    'date': f.timestamp.strftime('%d.%m.%Y'),
                    'time': f.timestamp.strftime('%H:%M')
                } for f in feedings
            ]
            
            # История лекарств (за последние 30 дней)
            month_ago = datetime.now() - timedelta(days=30)
            medications = db_session.query(Medication).filter(
                Medication.child_id == child.id,
                Medication.timestamp >= month_ago
            ).order_by(Medication.timestamp).all()
            
            self.data_cache['medication_history'] = [
                {
                    'name': m.medication_name,
                    'dosage': m.dosage,
                    'date': m.timestamp.strftime('%d.%m.%Y'),
                    'time': m.timestamp.strftime('%H:%M')
                } for m in medications
            ]
            
            # История стула (за последние 7 дней)
            stools = db_session.query(Stool).filter(
                Stool.child_id == child.id,
                Stool.timestamp >= week_ago
            ).order_by(Stool.timestamp).all()
            
            self.data_cache['stool_history'] = [
                {
                    'description': s.description,
                    'date': s.timestamp.strftime('%d.%m.%Y'),
                    'time': s.timestamp.strftime('%H:%M')
                } for s in stools
            ]
            
            # Обновляем время последнего обновления
            self.data_cache['last_updated'] = datetime.now()
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении кэша данных: {e}")
    
    def get_response(self, text: str, db_session=None):
        """
        Получает ответ от AI с учетом контекста и данных из базы
        
        Args:
            text: Текст запроса пользователя
            db_session: Сессия базы данных
            
        Returns:
            Ответ от AI
        """
        try:
            # Добавляем запрос пользователя в историю
            self.conversation_history.append({"role": "user", "content": text})
            
            # Если есть доступ к базе данных, добавляем контекст из базы
            context = ""
            child = None
            if db_session:
                # Импортируем модели для работы с БД
                from database.models import Child, Weight, Feeding, Stool, Medication, Prescription, Note, ChatHistory
                
                # Получаем данные о ребенке
                child = db_session.query(Child).first()
                if child:
                    # Базовая информация о ребенке
                    age_days = (datetime.now().date() - child.birth_date).days
                    age_months = age_days // 30
                    age_years = age_days // 365
                    
                    if age_years > 0:
                        age_str = f"{age_years} лет"
                        if age_years < 5:
                            age_str += f" {age_months % 12} месяцев"
                    else:
                        age_str = f"{age_months} месяцев"
                    
                    context += f"Информация о ребенке: {child.name}, {age_str}, {child.gender}.\n\n"
                    
                    # Получаем последние данные о весе
                    weights = db_session.query(Weight).filter_by(child_id=child.id).order_by(Weight.timestamp.desc()).limit(5).all()
                    if weights:
                        context += "Последние записи о весе:\n"
                        for weight in weights:
                            context += f"- {weight.weight} кг ({weight.timestamp.strftime('%d.%m.%Y')})\n"
                        context += "\n"
                    
                    # Получаем последние данные о кормлениях
                    feedings = db_session.query(Feeding).filter_by(child_id=child.id).order_by(Feeding.timestamp.desc()).limit(5).all()
                    if feedings:
                        context += "Последние записи о кормлениях:\n"
                        for feeding in feedings:
                            food_type = "грудное молоко"
                            if feeding.food_type == 'formula':
                                food_type = "смесь"
                            elif feeding.food_type == 'food':
                                food_type = "прикорм"
                            context += f"- {feeding.amount} мл {food_type} ({feeding.timestamp.strftime('%d.%m.%Y %H:%M')})\n"
                        context += "\n"
                    
                    # Получаем последние данные о стуле
                    stools = db_session.query(Stool).filter_by(child_id=child.id).order_by(Stool.timestamp.desc()).limit(3).all()
                    if stools:
                        context += "Последние записи о стуле:\n"
                        for stool in stools:
                            color_text = f", цвет: {stool.color}" if stool.color else ""
                            context += f"- {stool.description}{color_text} ({stool.timestamp.strftime('%d.%m.%Y %H:%M')})\n"
                        context += "\n"
                    
                    # Получаем последние данные о лекарствах
                    medications = db_session.query(Medication).filter_by(child_id=child.id).order_by(Medication.timestamp.desc()).limit(5).all()
                    if medications:
                        context += "Последние записи о приеме лекарств:\n"
                        for medication in medications:
                            dosage_text = f", {medication.dosage}" if medication.dosage else ""
                            context += f"- {medication.medication_name}{dosage_text} ({medication.timestamp.strftime('%d.%m.%Y %H:%M')})\n"
                        context += "\n"
                    
                    # Получаем активные назначения
                    prescriptions = db_session.query(Prescription).filter(
                        Prescription.child_id == child.id,
                        Prescription.is_active == 1
                    ).order_by(Prescription.start_date.desc()).all()
                    
                    if prescriptions:
                        context += "Активные назначения врачей:\n"
                        for prescription in prescriptions:
                            if prescription.full_text:
                                context += f"- {prescription.medication_name}: {prescription.full_text}\n"
                            else:
                                end_date_text = f"до {prescription.end_date.strftime('%d.%m.%Y')}" if prescription.end_date else "бессрочно"
                                context += f"- {prescription.medication_name}, {prescription.dosage}, {prescription.frequency}, с {prescription.start_date.strftime('%d.%m.%Y')} {end_date_text}\n"
                        context += "\n"
                    
                    # Получаем заметки о ребенке
                    notes = db_session.query(Note).filter_by(child_id=child.id).order_by(Note.timestamp.desc()).limit(5).all()
                    if notes:
                        context += "Важные заметки о ребенке:\n"
                        for note in notes:
                            context += f"- {note.title}: {note.content}\n"
                        context += "\n"
                    
                    # Получаем последние диалоги из истории
                    chat_history = db_session.query(ChatHistory).filter_by(child_id=child.id).order_by(ChatHistory.timestamp.desc()).limit(10).all()
                    if chat_history:
                        context += "Последние диалоги с ассистентом:\n"
                        for chat in chat_history:
                            context += f"- Вопрос: {chat.user_message}\n  Ответ: {chat.assistant_response}\n\n"
            
            # Создаем сообщения для API
            messages = [
                {"role": "system", "content": self.system_prompt + "\n\nКонтекст о ребенке:\n" + context if context else self.system_prompt}
            ]
            
            # Добавляем историю разговора, но ограничиваем ее последними 10 сообщениями
            messages.extend(self.conversation_history[-10:])
            
            # Получаем ответ от API
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            
            # Извлекаем ответ
            ai_response = response['choices'][0]['message']['content']
            
            # Добавляем ответ в историю
            self.conversation_history.append({"role": "assistant", "content": ai_response})
            
            # Сохраняем диалог в базу данных, если есть доступ к базе и есть информация о ребенке
            if db_session and child:
                from database.models import ChatHistory
                
                # Создаем запись в истории диалогов
                chat_history = ChatHistory(
                    child_id=child.id,
                    user_message=text,
                    assistant_response=ai_response,
                    timestamp=datetime.now()
                )
                
                # Добавляем запись в базу данных
                db_session.add(chat_history)
                db_session.commit()
            
            return ai_response
        except Exception as e:
            logger.error(f"Ошибка при получении ответа от AI: {e}")
            return "Извините, произошла ошибка при обработке вашего запроса."
    
    def _format_context(self, context: Dict) -> str:
        """Форматирование базового контекста для AI"""
        parts = []
        
        if 'child_info' in context:
            child = context['child_info']
            parts.append(f"Ребенок: {child.get('name', 'Не указано')}, "
                        f"возраст: {child.get('age', 'Не указано')}, "
                        f"пол: {child.get('gender', 'Не указано')}")
        
        if 'last_feeding' in context:
            feeding = context['last_feeding']
            parts.append(f"Последнее кормление: {feeding.get('amount', 'Не указано')} мл, "
                        f"{feeding.get('time', 'Не указано')}")
        
        if 'last_weight' in context:
            weight = context['last_weight']
            parts.append(f"Последний вес: {weight.get('value', 'Не указано')} кг, "
                        f"{weight.get('date', 'Не указано')}")
        
        return "; ".join(parts)
        
    def _format_full_context(self, context: Dict) -> str:
        """Форматирование расширенного контекста с данными из БД"""
        sections = []
        
        # Информация о ребенке
        if 'child_info' in context:
            child = context['child_info']
            child_info = (
                f"Информация о ребенке:\n"
                f"Имя: {child.get('name')}\n"
                f"Пол: {child.get('gender')}\n"
                f"Дата рождения: {child.get('birth_date')}\n"
                f"Возраст: {child.get('age_years')} лет {child.get('age_months') % 12} месяцев ({child.get('age_days')} дней)"
            )
            sections.append(child_info)
        
        # Анализ веса
        if 'weight_analysis' in context:
            weight = context['weight_analysis']
            weight_info = (
                f"Анализ веса:\n"
                f"Первое измерение: {weight.get('first_weight')} кг\n"
                f"Последнее измерение: {weight.get('last_weight')} кг\n"
                f"Изменение: {weight.get('change')} кг ({weight.get('trend')})"
            )
            sections.append(weight_info)
            
            # Добавляем историю измерений веса
            if 'weight_history' in context:
                weight_history = "История измерений веса:\n"
                for w in context['weight_history']:
                    weight_history += f"- {w.get('date')}: {w.get('weight')} кг\n"
                sections.append(weight_history)
        
        # Анализ кормлений
        if 'feeding_analysis' in context:
            feeding = context['feeding_analysis']
            feeding_info = (
                f"Анализ кормлений:\n"
                f"Всего кормлений за неделю: {feeding.get('total_feedings')}\n"
                f"Средний объем: {feeding.get('avg_amount'):.1f} мл\n"
                f"Кормления по дням:"
            )
            
            for day in feeding.get('feedings_per_day', []):
                feeding_info += f"\n- {day.get('date')}: {day.get('count')} раз, всего {day.get('total_amount')} мл"
                
            sections.append(feeding_info)
            
            # Добавляем последние кормления
            if 'recent_feedings' in feeding:
                recent_feedings = "Последние кормления:\n"
                for f in feeding['recent_feedings']:
                    recent_feedings += f"- {f.get('date')} {f.get('time')}: {f.get('amount')} мл ({f.get('food_type')})\n"
                sections.append(recent_feedings)
        
        # Добавляем историю стула
        if 'stool_history' in context:
            stool_history = "История стула (последняя неделя):\n"
            for s in context['stool_history'][:5]:  # Последние 5 записей
                stool_history += f"- {s.get('date')} {s.get('time')}: {s.get('description')}\n"
            sections.append(stool_history)
        
        # Добавляем историю лекарств
        if 'medication_history' in context:
            med_history = "История приема лекарств (последний месяц):\n"
            for m in context['medication_history'][:5]:  # Последние 5 записей
                med_history += f"- {m.get('date')} {m.get('time')}: {m.get('name')} ({m.get('dosage')})\n"
            sections.append(med_history)
        
        return "\n\n".join(sections)
    
    def analyze_symptoms(self, symptoms: List[str]) -> Dict:
        """
        Анализ симптомов
        
        Args:
            symptoms: Список симптомов
            
        Returns:
            Словарь с анализом и рекомендациями
        """
        symptoms_str = ", ".join(symptoms)
        prompt = f"""Проанализируй следующие симптомы у ребенка: {symptoms_str}
        
        Дай структурированный ответ в формате JSON со следующими полями:
        - severity: уровень серьезности (низкий/средний/высокий)
        - possible_causes: возможные причины (список)
        - recommendations: рекомендации (список)
        - see_doctor: нужно ли обратиться к врачу (да/нет)
        - urgency: срочность обращения к врачу (если нужно)"""
        
        try:
            response = self.get_response(prompt)
            # Попытка распарсить JSON из ответа
            return self._parse_json_response(response)
        except Exception as e:
            logger.error(f"Ошибка при анализе симптомов: {e}")
            return {
                "error": "Не удалось проанализировать симптомы",
                "recommendation": "Пожалуйста, обратитесь к врачу для консультации"
            }
    
    def _parse_json_response(self, response: str) -> Dict:
        """Парсинг JSON из ответа AI"""
        try:
            # Пытаемся найти JSON в ответе
            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end > start:
                json_str = response[start:end]
                return json.loads(json_str)
        except:
            pass
        
        # Если не удалось распарсить, возвращаем текстовый ответ
        return {"response": response}
    
    def get_feeding_recommendations(self, child_age_months: int, weight_kg: float) -> str:
        """Получить рекомендации по кормлению"""
        prompt = f"""Дай рекомендации по кормлению для ребенка:
        - Возраст: {child_age_months} месяцев
        - Вес: {weight_kg} кг
        
        Включи:
        1. Рекомендуемое количество кормлений в день
        2. Объем одного кормления
        3. Общие советы по питанию для этого возраста"""
        
        return self.get_response(prompt)
    
    def generate_development_summary(self, db_session) -> str:
        """
        Генерирует сводку о развитии ребенка на основе данных из базы
        
        Args:
            db_session: Сессия базы данных
            
        Returns:
            Текстовая сводка о развитии ребенка
        """
        try:
            # Импортируем модели для работы с БД
            from database.models import Child, Weight, Feeding, Stool, Prescription, Note
            
            # Получаем данные о ребенке
            child = db_session.query(Child).first()
            if not child:
                return "Нет данных о ребенке."
            
            # Базовая информация о ребенке
            age_days = (datetime.now().date() - child.birth_date).days
            age_months = age_days // 30
            age_years = age_days // 365
            
            if age_years > 0:
                age_str = f"{age_years} лет"
                if age_years < 5:
                    age_str += f" {age_months % 12} месяцев"
            else:
                age_str = f"{age_months} месяцев"
            
            context = f"Информация о ребенке: {child.name}, {age_str}, {child.gender}.\n\n"
            
            # Получаем последние данные о весе и анализируем динамику
            weights = db_session.query(Weight).filter_by(child_id=child.id).order_by(Weight.timestamp).all()
            if weights:
                first_weight = weights[0].weight
                last_weight = weights[-1].weight
                weight_change = last_weight - first_weight
                
                context += f"Вес: текущий - {last_weight} кг, начальный - {first_weight} кг.\n"
                context += f"Изменение веса: {weight_change:.2f} кг.\n\n"
            
            # Получаем статистику по кормлениям
            feedings = db_session.query(Feeding).filter_by(child_id=child.id).order_by(Feeding.timestamp.desc()).all()
            if feedings:
                # Группируем кормления по дням
                feedings_by_day = {}
                for feeding in feedings:
                    day = feeding.timestamp.date()
                    if day not in feedings_by_day:
                        feedings_by_day[day] = []
                    feedings_by_day[day].append(feeding)
                
                # Вычисляем среднее количество кормлений в день
                avg_feedings_per_day = len(feedings) / len(feedings_by_day) if feedings_by_day else 0
                
                # Вычисляем среднее количество молока в день
                total_amount = sum(feeding.amount for feeding in feedings)
                avg_amount_per_day = total_amount / len(feedings_by_day) if feedings_by_day else 0
                
                context += f"Кормления: в среднем {avg_feedings_per_day:.1f} раз в день.\n"
                context += f"Среднее количество молока: {avg_amount_per_day:.0f} мл в день.\n\n"
            
            # Получаем статистику по стулу
            stools = db_session.query(Stool).filter_by(child_id=child.id).order_by(Stool.timestamp.desc()).all()
            if stools:
                # Группируем стул по дням
                stools_by_day = {}
                for stool in stools:
                    day = stool.timestamp.date()
                    if day not in stools_by_day:
                        stools_by_day[day] = []
                    stools_by_day[day].append(stool)
                
                # Вычисляем среднее количество стула в день
                avg_stools_per_day = len(stools) / len(stools_by_day) if stools_by_day else 0
                
                context += f"Стул: в среднем {avg_stools_per_day:.1f} раз в день.\n\n"
            
            # Получаем активные назначения
            prescriptions = db_session.query(Prescription).filter(
                Prescription.child_id == child.id,
                Prescription.is_active == 1
            ).order_by(Prescription.start_date.desc()).all()
            
            if prescriptions:
                context += "Активные назначения врачей:\n"
                for prescription in prescriptions:
                    if prescription.full_text:
                        context += f"- {prescription.medication_name}: {prescription.full_text}\n"
                    else:
                        end_date_text = f"до {prescription.end_date.strftime('%d.%m.%Y')}" if prescription.end_date else "бессрочно"
                        context += f"- {prescription.medication_name}, {prescription.dosage}, {prescription.frequency}, с {prescription.start_date.strftime('%d.%m.%Y')} {end_date_text}\n"
                context += "\n"
                
            # Получаем заметки о ребенке
            notes = db_session.query(Note).filter_by(child_id=child.id).order_by(Note.timestamp.desc()).limit(5).all()
            if notes:
                context += "Важные заметки о ребенке:\n"
                for note in notes:
                    context += f"- {note.title}: {note.content}\n"
                context += "\n"
            
            # Генерируем сводку с помощью OpenAI
            messages = [
                {"role": "system", "content": """Ты - опытный педиатр, который анализирует данные о развитии ребенка.
                Твоя задача - составить краткую сводку о развитии ребенка на основе предоставленных данных.
                Сводка должна включать анализ веса, питания, пищеварения и текущих назначений.
                Используй профессиональный, но понятный родителям язык.
                Не используй фразы вроде "на основе предоставленных данных" или "согласно информации".
                Просто дай прямую оценку состояния ребенка."""},
                {"role": "user", "content": f"Данные о ребенке:\n\n{context}\n\nСоставь краткую сводку о развитии ребенка."}
            ]
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            
            summary = response['choices'][0]['message']['content']
            return summary
        
        except Exception as e:
            logger.error(f"Ошибка при генерации сводки о развитии: {e}")
            return "Не удалось сгенерировать сводку о развитии ребенка из-за ошибки."
    
    def clear_history(self):
        """Очистить историю разговора"""
        self.conversation_history = []
    
    def parse_feeding(self, text: str) -> dict:
        """
        Распознает запись о кормлении из текста пользователя
        
        Args:
            text: Текст сообщения
            
        Returns:
            Словарь с данными о кормлении или None, если не распознано
        """
        try:
            prompt = f"""Распознай запись о кормлении ребенка из текста пользователя и верни результат в формате JSON.
            
            Текст пользователя: "{text}"
            
            Формат ответа должен быть JSON со следующими полями:
            - amount: количество молока/смеси в мл (число)
            - food_type: тип питания (breast_milk - грудное молоко, formula - смесь, food - прикорм)
            - is_feeding: true если это запись о кормлении, false если нет
            
            Примеры:
            1. "Покормили 80 мл смеси" -> {{"amount": 80, "food_type": "formula", "is_feeding": true}}
            2. "Поели 70 грам молока" -> {{"amount": 70, "food_type": "breast_milk", "is_feeding": true}}
            3. "Дали 100 мл грудного молока" -> {{"amount": 100, "food_type": "breast_milk", "is_feeding": true}}
            4. "Съел 50 грамм пюре" -> {{"amount": 50, "food_type": "food", "is_feeding": true}}
            
            Верни только JSON без дополнительного текста.
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Ты - помощник для распознавания записей о кормлении."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.3
            )
            
            assistant_response = response['choices'][0]['message']['content']
            feeding_data = self._parse_json_response(assistant_response)
            
            if feeding_data and feeding_data.get('is_feeding', False):
                return {
                    'amount': feeding_data.get('amount'),
                    'food_type': feeding_data.get('food_type')
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при распознавании кормления: {e}")
            return None
    
    def parse_stool(self, text: str) -> dict:
        """
        Распознает запись о стуле из текста пользователя
        
        Args:
            text: Текст сообщения
            
        Returns:
            Словарь с данными о стуле или None, если не распознано
        """
        try:
            prompt = f"""Распознай запись о стуле ребенка из текста пользователя и верни результат в формате JSON.
            
            Текст пользователя: "{text}"
            
            Формат ответа должен быть JSON со следующими полями:
            - description: описание стула
            - color: цвет стула (если указан)
            - is_stool: true если это запись о стуле, false если нет
            
            Примеры:
            1. "Был стул, желтый, кашеобразный" -> {{"description": "кашеобразный", "color": "желтый", "is_stool": true}}
            2. "Покакал жидким стулом" -> {{"description": "жидкий", "color": null, "is_stool": true}}
            3. "Был зеленый стул" -> {{"description": "стул", "color": "зеленый", "is_stool": true}}
            
            Верни только JSON без дополнительного текста.
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Ты - помощник для распознавания записей о стуле."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.3
            )
            
            assistant_response = response['choices'][0]['message']['content']
            stool_data = self._parse_json_response(assistant_response)
            
            if stool_data and stool_data.get('is_stool', False):
                return {
                    'description': stool_data.get('description'),
                    'color': stool_data.get('color')
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при распознавании стула: {e}")
            return None
    
    def parse_medication(self, text: str) -> dict:
        """
        Распознает информацию о приеме лекарства из текста
        
        Args:
            text: Текст сообщения
            
        Returns:
            Словарь с информацией о лекарстве или None, если лекарство не распознано
        """
        # Пропускаем запросы на создание заметок
        if text.lower().startswith('добавь заметку') or text.lower().startswith('создай заметку'):
            return None
            
        # Ключевые слова для лекарств
        keywords = [
            'принял', 'приняла', 'дал', 'дала', 'выпил', 'выпила', 'пропил', 'пропила',
            'лекарство', 'таблетку', 'таблетки', 'сироп', 'капли', 'суспензию', 'антибиотик',
            'жаропонижающее', 'парацетамол', 'ибупрофен', 'нурофен', 'панадол', 'эффералган'
        ]
        
        # Проверяем наличие ключевых слов
        has_keyword = False
        for keyword in keywords:
            if keyword in text.lower():
                has_keyword = True
                break
                
        if not has_keyword:
            return None
        
        try:
            # Формируем запрос к ИИ для распознавания лекарства
            prompt = f"""Распознай информацию о приеме лекарства из текста пользователя и верни результат в формате JSON.
            
            Текст пользователя: "{text}"
            
            Формат ответа должен быть JSON со следующими полями:
            - medication_name: название лекарства
            - dosage: дозировка (если указана)
            - is_medication: true если это запись о приеме лекарства, false если нет
            
            Примеры:
            1. "Дала ребенку парацетамол 5 мл" -> {{"medication_name": "парацетамол", "dosage": "5 мл", "is_medication": true}}
            2. "Приняли нурофен" -> {{"medication_name": "нурофен", "dosage": null, "is_medication": true}}
            
            Верни только JSON без дополнительного текста.
            """
            
            # Запрос к OpenAI API (старый интерфейс)
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Ты - помощник для распознавания информации о приеме лекарств."},
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
            medication_data = self._extract_json(assistant_response)
            
            # Проверяем, является ли это записью о лекарстве
            if medication_data and medication_data.get('is_medication', False):
                return {
                    'medication_name': medication_data.get('medication_name', ''),
                    'dosage': medication_data.get('dosage', None)
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при распознавании лекарства: {e}")
            return None
    
    def parse_prescription_reminders_request(self, text: str) -> bool:
        """
        Определяет, является ли текст запросом на создание напоминаний из назначений
        
        Args:
            text: Текст сообщения
            
        Returns:
            True если это запрос на создание напоминаний из назначений, иначе False
        """
        try:
            # Ключевые фразы для запроса на создание напоминаний из назначений
            keywords = [
                'создай напоминания из назначений',
                'сделай напоминания из назначений',
                'создать напоминания из назначений',
                'напоминания по назначениям',
                'напоминания для лекарств',
                'напоминания для приема лекарств',
                'напомни о лекарствах',
                'напомни о назначениях'
            ]
            
            # Приводим текст к нижнему регистру
            text_lower = text.lower()
            
            # Проверяем наличие ключевых фраз
            for keyword in keywords:
                if keyword in text_lower:
                    return True
                
            return False
        except Exception as e:
            logger.error(f"Ошибка при распознавании запроса на создание напоминаний: {e}")
            return False 