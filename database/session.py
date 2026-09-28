"""
Database Session & Connection Management
Supports PostgreSQL connection pooling and test fallback mechanisms.
"""

import logging
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError

from apps.api.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

database_url = settings.get_database_url()

# Configure engine with connection pooling
engine_kwargs = {
    "pool_pre_ping": True,
    "echo": False,
}

if database_url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_engine(database_url, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding a database session.
    Automatically closes session upon request completion.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> dict:
    """
    Executes a lightweight query to probe database connectivity and latency.
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar()
            is_alive = (result == 1)
            return {
                "status": "healthy" if is_alive else "unhealthy",
                "database": engine.url.database or "nexus",
                "driver": engine.driver,
                "connected": is_alive
            }
    except OperationalError as err:
        logger.warning(f"Database connection probe failed: {err}")
        return {
            "status": "unhealthy",
            "database": engine.url.database or "nexus",
            "driver": engine.driver,
            "connected": False,
            "error": "Connection refused or unreachable"
        }
    except Exception as err:
        logger.error(f"Unexpected database probe error: {err}")
        return {
            "status": "error",
            "database": engine.url.database or "nexus",
            "driver": engine.driver,
            "connected": False,
            "error": str(err)
        }
