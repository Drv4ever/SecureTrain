"""Database engine, session factory, and initialization for SQLite."""

import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = os.environ.get("DATABASE_PATH", str(BASE_DIR / "trainer.db"))
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency that yields a database session and guarantees cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all database tables."""
    import backend.app.models  # Ensure models are imported before creating tables
    Base.metadata.create_all(bind=engine)
    # Lightweight migration for the existing SQLite database. This intentionally
    # only adds nullable/default-safe columns and never drops user data.
    if engine.url.get_backend_name() == "sqlite":
        additions = {
            "employees": {
                "company_id": "INTEGER",
                "email": "VARCHAR(255)",
                "hashed_password": "VARCHAR(255)",
            },
            "rounds": {
                "feedback_text": "TEXT",
                "classifier_score": "FLOAT",
                "presented_at": "DATETIME",
                "response_time_seconds": "FLOAT",
            },
            "companies": {"settings": "JSON"},
            "sessions": {"assignment_id": "INTEGER"},
            "scenarios": {"source": "VARCHAR(20)"},
        }
        with engine.begin() as conn:
            inspector = inspect(conn)
            for table, columns in additions.items():
                existing = {c["name"] for c in inspector.get_columns(table)}
                for name, sql_type in columns.items():
                    if name not in existing:
                        conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {sql_type}'))


