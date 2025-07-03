"""
Модуль для работы с Google Sheets API
"""
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import logging
from datetime import datetime
import os
import sys
from typing import List, Dict, Any, Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import GOOGLE_SHEETS_CREDENTIALS, GOOGLE_SHEETS_SPREADSHEET_ID, GOOGLE_SHEETS_ENABLED

logger = logging.getLogger(__name__)

class GoogleSheetsManager:
    """Класс для управления данными в Google Sheets"""
    
    def __init__(self):
        """Инициализация менеджера Google Sheets"""
        self.enabled = GOOGLE_SHEETS_ENABLED
        self.spreadsheet_id = GOOGLE_SHEETS_SPREADSHEET_ID
        self.client = None
        self.spreadsheet = None
        
        if not self.enabled:
            logger.info("Google Sheets интеграция отключена")
            return
            
        if not os.path.exists(GOOGLE_SHEETS_CREDENTIALS):
            logger.error(f"Файл с учетными данными Google Sheets не найден: {GOOGLE_SHEETS_CREDENTIALS}")
            self.enabled = False
            return
            
        if not self.spreadsheet_id:
            logger.error("ID таблицы Google Sheets не указан")
            self.enabled = False
            return
            
        try:
            # Определение области доступа
            scope = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # Авторизация
            credentials = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_CREDENTIALS, scope)
            self.client = gspread.authorize(credentials)
            
            # Открытие таблицы по ID
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            
            # Проверка наличия необходимых листов
            self._ensure_sheets_exist()
            
            logger.info("Google Sheets интеграция успешно инициализирована")
        except Exception as e:
            logger.error(f"Ошибка при инициализации Google Sheets: {e}")
            self.enabled = False
    
    def _ensure_sheets_exist(self):
        """Проверка наличия необходимых листов и их создание при необходимости"""
        if not self.enabled or not self.spreadsheet:
            return
            
        required_sheets = {
            "Напоминания": ["ID", "Описание", "Время", "Статус", "Тип повторения", "Интервал", "Создано", "Обновлено"],
            "Лекарства": ["ID", "Название", "Дозировка", "Время приема", "Ребенок"],
            "Кормления": ["ID", "Количество", "Тип", "Время", "Ребенок"],
            "Стул": ["ID", "Описание", "Цвет", "Время", "Ребенок"],
            "Вес": ["ID", "Вес (кг)", "Время", "Ребенок"],
            "Назначения": ["ID", "Врач", "Лекарство", "Дозировка", "Частота", "Начало", "Окончание", "Примечания", "Активно"]
        }
        
        # Получаем список существующих листов
        existing_sheets = [worksheet.title for worksheet in self.spreadsheet.worksheets()]
        
        # Создаем отсутствующие листы
        for sheet_name, headers in required_sheets.items():
            if sheet_name not in existing_sheets:
                logger.info(f"Создание листа '{sheet_name}'")
                worksheet = self.spreadsheet.add_worksheet(title=sheet_name, rows=1, cols=len(headers))
                worksheet.append_row(headers)
            else:
                # Проверяем заголовки
                worksheet = self.spreadsheet.worksheet(sheet_name)
                existing_headers = worksheet.row_values(1)
                if existing_headers != headers:
                    logger.warning(f"Заголовки листа '{sheet_name}' отличаются от ожидаемых")
    
    def sync_reminders(self, reminders: List[Dict[str, Any]]) -> bool:
        """
        Синхронизация напоминаний с Google Sheets
        
        Args:
            reminders: Список словарей с данными о напоминаниях
            
        Returns:
            bool: True, если синхронизация прошла успешно, иначе False
        """
        if not self.enabled or not self.spreadsheet:
            return False
            
        try:
            worksheet = self.spreadsheet.worksheet("Напоминания")
            
            # Очищаем лист, оставляя только заголовки
            if worksheet.row_count > 1:
                worksheet.delete_rows(2, worksheet.row_count)
            
            # Добавляем данные
            rows = []
            for reminder in reminders:
                rows.append([
                    reminder.get('id', ''),
                    reminder.get('description', ''),
                    reminder.get('reminder_time', ''),
                    reminder.get('status', ''),
                    reminder.get('repeat_type', ''),
                    reminder.get('repeat_interval', ''),
                    reminder.get('created_at', ''),
                    reminder.get('updated_at', '')
                ])
            
            if rows:
                worksheet.append_rows(rows)
                
            logger.info(f"Синхронизировано {len(rows)} напоминаний с Google Sheets")
            return True
        except Exception as e:
            logger.error(f"Ошибка при синхронизации напоминаний с Google Sheets: {e}")
            return False
    
    def sync_medications(self, medications: List[Dict[str, Any]]) -> bool:
        """
        Синхронизация приемов лекарств с Google Sheets
        
        Args:
            medications: Список словарей с данными о приемах лекарств
            
        Returns:
            bool: True, если синхронизация прошла успешно, иначе False
        """
        if not self.enabled or not self.spreadsheet:
            return False
            
        try:
            worksheet = self.spreadsheet.worksheet("Лекарства")
            
            # Очищаем лист, оставляя только заголовки
            if worksheet.row_count > 1:
                worksheet.delete_rows(2, worksheet.row_count)
            
            # Добавляем данные
            rows = []
            for medication in medications:
                rows.append([
                    medication.get('id', ''),
                    medication.get('medication_name', ''),
                    medication.get('dosage', ''),
                    medication.get('timestamp', ''),
                    medication.get('child_name', '')
                ])
            
            if rows:
                worksheet.append_rows(rows)
                
            logger.info(f"Синхронизировано {len(rows)} приемов лекарств с Google Sheets")
            return True
        except Exception as e:
            logger.error(f"Ошибка при синхронизации приемов лекарств с Google Sheets: {e}")
            return False
    
    def sync_feedings(self, feedings: List[Dict[str, Any]]) -> bool:
        """
        Синхронизация кормлений с Google Sheets
        
        Args:
            feedings: Список словарей с данными о кормлениях
            
        Returns:
            bool: True, если синхронизация прошла успешно, иначе False
        """
        if not self.enabled or not self.spreadsheet:
            return False
            
        try:
            worksheet = self.spreadsheet.worksheet("Кормления")
            
            # Очищаем лист, оставляя только заголовки
            if worksheet.row_count > 1:
                worksheet.delete_rows(2, worksheet.row_count)
            
            # Добавляем данные
            rows = []
            for feeding in feedings:
                rows.append([
                    feeding.get('id', ''),
                    feeding.get('amount', ''),
                    feeding.get('food_type', ''),
                    feeding.get('timestamp', ''),
                    feeding.get('child_name', '')
                ])
            
            if rows:
                worksheet.append_rows(rows)
                
            logger.info(f"Синхронизировано {len(rows)} кормлений с Google Sheets")
            return True
        except Exception as e:
            logger.error(f"Ошибка при синхронизации кормлений с Google Sheets: {e}")
            return False
    
    def sync_stools(self, stools: List[Dict[str, Any]]) -> bool:
        """
        Синхронизация данных о стуле с Google Sheets
        
        Args:
            stools: Список словарей с данными о стуле
            
        Returns:
            bool: True, если синхронизация прошла успешно, иначе False
        """
        if not self.enabled or not self.spreadsheet:
            return False
            
        try:
            worksheet = self.spreadsheet.worksheet("Стул")
            
            # Очищаем лист, оставляя только заголовки
            if worksheet.row_count > 1:
                worksheet.delete_rows(2, worksheet.row_count)
            
            # Добавляем данные
            rows = []
            for stool in stools:
                rows.append([
                    stool.get('id', ''),
                    stool.get('description', ''),
                    stool.get('color', ''),
                    stool.get('timestamp', ''),
                    stool.get('child_name', '')
                ])
            
            if rows:
                worksheet.append_rows(rows)
                
            logger.info(f"Синхронизировано {len(rows)} записей о стуле с Google Sheets")
            return True
        except Exception as e:
            logger.error(f"Ошибка при синхронизации данных о стуле с Google Sheets: {e}")
            return False
    
    def sync_weights(self, weights: List[Dict[str, Any]]) -> bool:
        """
        Синхронизация данных о весе с Google Sheets
        
        Args:
            weights: Список словарей с данными о весе
            
        Returns:
            bool: True, если синхронизация прошла успешно, иначе False
        """
        if not self.enabled or not self.spreadsheet:
            return False
            
        try:
            worksheet = self.spreadsheet.worksheet("Вес")
            
            # Очищаем лист, оставляя только заголовки
            if worksheet.row_count > 1:
                worksheet.delete_rows(2, worksheet.row_count)
            
            # Добавляем данные
            rows = []
            for weight in weights:
                rows.append([
                    weight.get('id', ''),
                    weight.get('weight', ''),
                    weight.get('timestamp', ''),
                    weight.get('child_name', '')
                ])
            
            if rows:
                worksheet.append_rows(rows)
                
            logger.info(f"Синхронизировано {len(rows)} записей о весе с Google Sheets")
            return True
        except Exception as e:
            logger.error(f"Ошибка при синхронизации данных о весе с Google Sheets: {e}")
            return False
    
    def sync_prescriptions(self, prescriptions: List[Dict[str, Any]]) -> bool:
        """
        Синхронизация назначений с Google Sheets
        
        Args:
            prescriptions: Список словарей с данными о назначениях
            
        Returns:
            bool: True, если синхронизация прошла успешно, иначе False
        """
        if not self.enabled or not self.spreadsheet:
            return False
            
        try:
            worksheet = self.spreadsheet.worksheet("Назначения")
            
            # Очищаем лист, оставляя только заголовки
            if worksheet.row_count > 1:
                worksheet.delete_rows(2, worksheet.row_count)
            
            # Добавляем данные
            rows = []
            for prescription in prescriptions:
                rows.append([
                    prescription.get('id', ''),
                    prescription.get('doctor_name', ''),
                    prescription.get('medication_name', ''),
                    prescription.get('dosage', ''),
                    prescription.get('frequency', ''),
                    prescription.get('start_date', ''),
                    prescription.get('end_date', ''),
                    prescription.get('notes', ''),
                    'Да' if prescription.get('is_active') else 'Нет'
                ])
            
            if rows:
                worksheet.append_rows(rows)
                
            logger.info(f"Синхронизировано {len(rows)} назначений с Google Sheets")
            return True
        except Exception as e:
            logger.error(f"Ошибка при синхронизации назначений с Google Sheets: {e}")
            return False
    
    def sync_all_data(self, db_session) -> bool:
        """
        Синхронизация всех данных с Google Sheets
        
        Args:
            db_session: Сессия базы данных
            
        Returns:
            bool: True, если синхронизация прошла успешно, иначе False
        """
        if not self.enabled or not self.spreadsheet:
            return False
            
        try:
            from database.models import Child, Reminder, Medication, Feeding, Stool, Weight, Prescription
            
            # Получаем данные из базы
            reminders = []
            for reminder in db_session.query(Reminder).all():
                child = db_session.query(Child).get(reminder.child_id)
                reminders.append({
                    'id': reminder.id,
                    'description': reminder.description,
                    'reminder_time': reminder.reminder_time.strftime('%d.%m.%Y %H:%M'),
                    'status': reminder.status,
                    'repeat_type': reminder.repeat_type,
                    'repeat_interval': reminder.repeat_interval,
                    'created_at': reminder.created_at.strftime('%d.%m.%Y %H:%M') if reminder.created_at else '',
                    'updated_at': reminder.updated_at.strftime('%d.%m.%Y %H:%M') if reminder.updated_at else '',
                    'child_name': child.name if child else ''
                })
            
            medications = []
            for medication in db_session.query(Medication).all():
                child = db_session.query(Child).get(medication.child_id)
                medications.append({
                    'id': medication.id,
                    'medication_name': medication.medication_name,
                    'dosage': medication.dosage,
                    'timestamp': medication.timestamp.strftime('%d.%m.%Y %H:%M'),
                    'child_name': child.name if child else ''
                })
            
            feedings = []
            for feeding in db_session.query(Feeding).all():
                child = db_session.query(Child).get(feeding.child_id)
                feedings.append({
                    'id': feeding.id,
                    'amount': feeding.amount,
                    'food_type': feeding.food_type,
                    'timestamp': feeding.timestamp.strftime('%d.%m.%Y %H:%M'),
                    'child_name': child.name if child else ''
                })
            
            stools = []
            for stool in db_session.query(Stool).all():
                child = db_session.query(Child).get(stool.child_id)
                stools.append({
                    'id': stool.id,
                    'description': stool.description,
                    'color': stool.color or '',
                    'timestamp': stool.timestamp.strftime('%d.%m.%Y %H:%M'),
                    'child_name': child.name if child else ''
                })
            
            weights = []
            for weight in db_session.query(Weight).all():
                child = db_session.query(Child).get(weight.child_id)
                weights.append({
                    'id': weight.id,
                    'weight': weight.weight,
                    'timestamp': weight.timestamp.strftime('%d.%m.%Y %H:%M'),
                    'child_name': child.name if child else ''
                })
            
            prescriptions = []
            for prescription in db_session.query(Prescription).all():
                child = db_session.query(Child).get(prescription.child_id)
                prescriptions.append({
                    'id': prescription.id,
                    'doctor_name': prescription.doctor_name or '',
                    'medication_name': prescription.medication_name,
                    'dosage': prescription.dosage,
                    'frequency': prescription.frequency,
                    'start_date': prescription.start_date.strftime('%d.%m.%Y'),
                    'end_date': prescription.end_date.strftime('%d.%m.%Y') if prescription.end_date else '',
                    'notes': prescription.notes or '',
                    'is_active': prescription.is_active == 1,
                    'child_name': child.name if child else ''
                })
            
            # Синхронизируем данные
            self.sync_reminders(reminders)
            self.sync_medications(medications)
            self.sync_feedings(feedings)
            self.sync_stools(stools)
            self.sync_weights(weights)
            self.sync_prescriptions(prescriptions)
            
            logger.info("Все данные успешно синхронизированы с Google Sheets")
            return True
        except Exception as e:
            logger.error(f"Ошибка при синхронизации данных с Google Sheets: {e}")
            return False

# Создаем глобальный экземпляр менеджера Google Sheets
sheets_manager = GoogleSheetsManager() 