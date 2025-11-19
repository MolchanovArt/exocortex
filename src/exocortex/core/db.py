"""Database setup and session management."""

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from exocortex.core.config import config

# SQLite database path (resolved relative to project root)
db_path = config.get_db_path()
db_path.parent.mkdir(parents=True, exist_ok=True)

# Create engine
engine = create_engine(
    f"sqlite:///{db_path}",
    connect_args={"check_same_thread": False},  # Needed for SQLite
    echo=False,  # Set to True for SQL debugging
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for ORM models
Base = declarative_base()


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context manager for database sessions."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)

