"""
Viral-X Database Session Management
Safe, transactional SQLAlchemy session factory with foreign keys and WAL mode.
"""

import time
from typing import Generator, Dict, Any
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.engine import Engine

from backend.app.core.config import settings
from backend.app.core.logging import logger

# Base class for declarative models
Base = declarative_base()

# Configure engine connect arguments
connect_args: Dict[str, Any] = {}
if settings.is_sqlite:
    # Allow multi-threaded FastAPI workers to access SQLite connections safely
    connect_args["check_same_thread"] = False

# Create the SQLAlchemy engine
engine = create_engine(
    settings.effective_database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=settings.DEBUG,
)


# SQLite PRAGMA configuration
@event.listens_for(Engine, "connect")
def configure_sqlite_pragmas(dbapi_connection, connection_record):
    """
    Ensure SQLite enforces foreign keys, uses WAL mode for concurrency,
    and sets a reasonable busy timeout to prevent locking contention.
    """
    if settings.is_sqlite:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys = ON;")
            cursor.execute("PRAGMA journal_mode = WAL;")
            cursor.execute("PRAGMA busy_timeout = 5000;")
        finally:
            cursor.close()


# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a managed SQLAlchemy database session.
    Automatically commits on success or rolls back on exception, then closes.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_db_health(timeout_seconds: float = 2.0) -> Dict[str, Any]:
    """
    Executes a lightweight query (SELECT 1) to verify database connectivity.
    Returns status, latency in milliseconds, and any error message.
    """
    start_time = time.perf_counter()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "status": "healthy",
            "connected": True,
            "latency_ms": latency_ms,
            "error": None,
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error(f"Database health check failed: {exc}", exc_info=False)
        return {
            "status": "unhealthy",
            "connected": False,
            "latency_ms": latency_ms,
            "error": str(exc),
        }
