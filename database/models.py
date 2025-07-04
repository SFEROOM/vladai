from sqlalchemy import Column, Integer, String, Date, DateTime, Float, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Integer, default=1)  # 1 - активен, 0 - неактивен

class Medication(Base):
    __tablename__ = 'medications'

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(Integer, ForeignKey('children.id'))
    medication_name = Column(String)
    dosage = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

    child = relationship("Child", back_populates="medications")

class Feeding(Base):
    __tablename__ = 'feedings'

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(Integer, ForeignKey('children.id'))
    amount = Column(Float)
    food_type = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

    child = relationship("Child", back_populates="feedings")

class Stool(Base):
    __tablename__ = 'stools'

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(Integer, ForeignKey('children.id'))
    description = Column(String)
    color = Column(String, nullable=True)  # Поле color с возможностью NULL
    timestamp = Column(DateTime, default=datetime.utcnow)

    child = relationship("Child", back_populates="stools")

class Weight(Base):
    __tablename__ = 'weights'

    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(Integer, ForeignKey('children.id'))
    weight = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)

    child = relationship("Child", back_populates="weights")

class Note(Base):
    __tablename__ = 'notes'
    
    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(Integer, ForeignKey('children.id'))
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    child = relationship("Child", back_populates="notes")

class ChatHistory(Base):
    __tablename__ = 'chat_history'
    
    id = Column(Integer, primary_key=True, index=True)
    child_id = Column(Integer, ForeignKey('children.id'))
    user_message = Column(Text, nullable=False)
    assistant_response = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    child = relationship("Child", back_populates="chat_history")

class Child(Base):
    __tablename__ = 'children'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    birth_date = Column(Date, nullable=False)
    gender = Column(String, nullable=False) 

    feedings = relationship("Feeding", order_by=Feeding.id, back_populates="child")
    stools = relationship("Stool", order_by=Stool.id, back_populates="child")
    weights = relationship("Weight", order_by=Weight.id, back_populates="child")
    medications = relationship("Medication", order_by=Medication.id, back_populates="child")
    # Определяем отношение к напоминаниям без прямой ссылки на класс
    reminders = relationship("Reminder", back_populates="child")
    prescriptions = relationship("Prescription", back_populates="child")
    appointments = relationship("Appointment", back_populates="child")
    notes = relationship("Note", order_by=Note.id, back_populates="child")
    chat_history = relationship("ChatHistory", order_by=ChatHistory.id, back_populates="child")

class Appointment(Base):
    __tablename__ = 'appointments'

    id = Column(Integer, primary_key=True)
    child_id = Column(Integer, ForeignKey('children.id'), nullable=False)
    description = Column(String, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    
    child = relationship("Child", back_populates="appointments")

class Prescription(Base):
    __tablename__ = 'prescriptions'
    
    id = Column(Integer, primary_key=True)
    child_id = Column(Integer, ForeignKey('children.id'), nullable=False)
    doctor_name = Column(String, nullable=True)
    medication_name = Column(String, nullable=False)
    dosage = Column(String, nullable=False)
    frequency = Column(String, nullable=False)  # например: "2 раза в день", "каждое утро"
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)  # может быть NULL, если назначение бессрочное
    notes = Column(String, nullable=True)  # дополнительные заметки
    full_text = Column(String, nullable=True)  # полный текст назначения
    is_active = Column(Integer, default=1)  # 1 - активно, 0 - неактивно
    created_at = Column(DateTime, default=datetime.utcnow)
    
    child = relationship("Child", back_populates="prescriptions")

class Reminder(Base):
    __tablename__ = 'reminders'

    id = Column(Integer, primary_key=True)
    child_id = Column(Integer, ForeignKey('children.id'), nullable=False)
    description = Column(String, nullable=False)
    reminder_time = Column(DateTime, nullable=False)
    status = Column(String, nullable=False, default='active')  # active, completed, skipped
    repeat_type = Column(String, default='once')  # once, daily, weekly, monthly
    repeat_interval = Column(Integer, default=1)  # каждые N дней/недель/месяцев
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    child = relationship("Child", back_populates="reminders")