import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from init_db import create_initial_users
    
DB_BACKEND = os.getenv("DB_BACKEND", "sqlite")

DATABASE_URL = (
    "postgresql://user:pass@localhost/db"
    if DB_BACKEND == "postgres"
    else "sqlite:///./preductions.db"
)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

def init_data():

    # Create all tables
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        create_initial_users(db)
    finally:
        db.close()


