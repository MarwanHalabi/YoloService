import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from init_db import create_initial_users
from base import Base

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

def init_data():

    # Create all tables
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        create_initial_users(db)
    finally:
        db.close()

# setup engine and session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()