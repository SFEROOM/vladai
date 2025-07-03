from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from .models import Base

DATABASE_URL = 'sqlite:///./family_assistant.db'

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 