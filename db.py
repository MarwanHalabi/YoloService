import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from init_db import create_initial_users
from base import Base

# Resolve database URL with sensible defaults
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DB_BACKEND = os.getenv("DB_BACKEND", "sqlite").lower()
    if DB_BACKEND == "postgres":
        # Prefer explicit POSTGRES_URL if provided
        DATABASE_URL = os.getenv("POSTGRES_URL", "postgresql+psycopg2://user:pass@localhost/db")
    else:
        DATABASE_URL = "sqlite:///./preductions.db"

# Friendly error if PostgreSQL driver is missing
if DATABASE_URL.startswith("postgresql"):
    try:
        import psycopg2  # noqa: F401
    except Exception as e:
        raise RuntimeError(
            "PostgreSQL backend selected but psycopg2 is not installed. "
            "Add 'psycopg2-binary' to requirements or set DB_BACKEND=sqlite."
        ) from e

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
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

# Backwards-compatible alias expected by app
def init_db():
    init_data()

# setup engine and session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
