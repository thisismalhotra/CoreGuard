"""
Database connection and session management for Core-Guard MVP.
Uses SQLite for local development simplicity.
"""

from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from .models import Base

# DB file lives alongside the backend code
DB_PATH = Path(__file__).resolve().parent.parent / "coreguard.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},  # Required for SQLite + FastAPI
    echo=False,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable WAL journal mode and busy timeout to prevent 'database is locked' errors
    during concurrent access (e.g., simultaneous API requests hitting /simulate/reset)."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    """Create all tables. Safe to call multiple times (no-op if tables exist)."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency — yields a session and ensures cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
