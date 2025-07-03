"""
Миграции для базы данных
"""
import sqlite3
import logging
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DATABASE_URL

logger = logging.getLogger(__name__)

def run_migrations():
    """Запуск миграций для базы данных"""
    # Извлекаем путь к файлу базы данных из DATABASE_URL
    db_path = DATABASE_URL.replace('sqlite:///', '')
    
    # Проверяем существование базы данных
    if not os.path.exists(db_path):
        logger.warning(f"База данных {db_path} не существует. Миграции не требуются.")
        return
    
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        migrations_applied = False
        
        # Проверяем наличие колонок в таблице reminders
        cursor.execute("PRAGMA table_info(reminders)")
        reminder_columns = [column[1] for column in cursor.fetchall()]
        
        # Миграция 1: Добавление колонки repeat_type
        if 'repeat_type' not in reminder_columns:
            logger.info("Применение миграции: добавление колонки repeat_type в таблицу reminders")
            cursor.execute("ALTER TABLE reminders ADD COLUMN repeat_type TEXT DEFAULT 'once'")
            migrations_applied = True
        
        # Миграция 2: Добавление колонки repeat_interval
        if 'repeat_interval' not in reminder_columns:
            logger.info("Применение миграции: добавление колонки repeat_interval в таблицу reminders")
            cursor.execute("ALTER TABLE reminders ADD COLUMN repeat_interval INTEGER DEFAULT 1")
            migrations_applied = True
        
        # Миграция 3: Добавление колонки created_at
        if 'created_at' not in reminder_columns:
            logger.info("Применение миграции: добавление колонки created_at в таблицу reminders")
            cursor.execute("ALTER TABLE reminders ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            migrations_applied = True
        
        # Миграция 4: Добавление колонки updated_at
        if 'updated_at' not in reminder_columns:
            logger.info("Применение миграции: добавление колонки updated_at в таблицу reminders")
            cursor.execute("ALTER TABLE reminders ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            migrations_applied = True
        
        # Проверяем наличие колонки color в таблице stools
        cursor.execute("PRAGMA table_info(stools)")
        stool_columns = [column[1] for column in cursor.fetchall()]
        
        # Миграция 5: Добавление колонки color в таблицу stools
        if 'color' not in stool_columns:
            logger.info("Применение миграции: добавление колонки color в таблицу stools")
            cursor.execute("ALTER TABLE stools ADD COLUMN color TEXT")
            migrations_applied = True
        
        # Проверяем наличие таблицы prescriptions
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='prescriptions'")
        table_exists = cursor.fetchone()
        
        # Миграция 6: Создание таблицы prescriptions, если её нет
        if not table_exists:
            logger.info("Применение миграции: создание таблицы prescriptions")
            cursor.execute("""
                CREATE TABLE prescriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    child_id INTEGER NOT NULL,
                    doctor_name TEXT,
                    medication_name TEXT NOT NULL,
                    dosage TEXT NOT NULL,
                    frequency TEXT NOT NULL,
                    start_date DATE NOT NULL,
                    end_date DATE,
                    notes TEXT,
                    full_text TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (child_id) REFERENCES children (id)
                )
            """)
            migrations_applied = True
        else:
            # Проверяем наличие колонки full_text в таблице prescriptions
            cursor.execute("PRAGMA table_info(prescriptions)")
            prescription_columns = [column[1] for column in cursor.fetchall()]
            
            # Миграция 7: Добавление колонки full_text в таблицу prescriptions
            if 'full_text' not in prescription_columns:
                logger.info("Применение миграции: добавление колонки full_text в таблицу prescriptions")
                cursor.execute("ALTER TABLE prescriptions ADD COLUMN full_text TEXT")
                migrations_applied = True
        
        # Проверяем, есть ли foreign key для appointments
        cursor.execute("PRAGMA foreign_key_list(appointments)")
        has_fk = cursor.fetchone()
        
        # Миграция 8: Обновление таблицы appointments, если нет foreign key
        if not has_fk:
            logger.info("Применение миграции: обновление таблицы appointments")
            # В SQLite нет прямого ALTER TABLE для добавления FOREIGN KEY
            # Поэтому создаем новую таблицу и переносим данные
            cursor.execute("""
                CREATE TABLE appointments_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    child_id INTEGER NOT NULL,
                    description TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    FOREIGN KEY (child_id) REFERENCES children (id)
                )
            """)
            
            # Копируем данные
            cursor.execute("INSERT INTO appointments_new SELECT * FROM appointments")
            
            # Удаляем старую таблицу и переименовываем новую
            cursor.execute("DROP TABLE appointments")
            cursor.execute("ALTER TABLE appointments_new RENAME TO appointments")
            
            migrations_applied = True
        
        # Проверяем наличие таблицы notes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notes'")
        notes_table_exists = cursor.fetchone()
        
        # Миграция 9: Создание таблицы notes, если её нет
        if not notes_table_exists:
            logger.info("Применение миграции: создание таблицы notes")
            cursor.execute("""
                CREATE TABLE notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    child_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (child_id) REFERENCES children (id)
                )
            """)
            migrations_applied = True
        
        # Проверяем наличие таблицы chat_history
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_history'")
        chat_history_table_exists = cursor.fetchone()
        
        # Миграция 10: Создание таблицы chat_history, если её нет
        if not chat_history_table_exists:
            logger.info("Применение миграции: создание таблицы chat_history")
            cursor.execute("""
                CREATE TABLE chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    child_id INTEGER NOT NULL,
                    user_message TEXT NOT NULL,
                    assistant_response TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (child_id) REFERENCES children (id)
                )
            """)
            migrations_applied = True
        
        # Сохраняем изменения
        conn.commit()
        
        if migrations_applied:
            logger.info("Миграции успешно применены")
        else:
            logger.info("Миграции не требуются")
            
    except sqlite3.Error as e:
        logger.error(f"Ошибка при применении миграций: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Запуск миграций
    run_migrations() 