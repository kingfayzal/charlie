"""
PrimeOps Agentic OS — Database Session Management
Async SQLAlchemy engine and session factory for FastAPI dependency injection.
Supports both PostgreSQL (production) and SQLite (local dev).
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator

from app.config import get_settings


# ---------------------------------------------------------------------------
# Base class for all ORM models
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    """Declarative base for all SQLAlchemy models."""
    pass


# ---------------------------------------------------------------------------
# Engine & Session Factory
# ---------------------------------------------------------------------------
settings = get_settings()

# SQLite needs special handling: no pool_size, no pool_pre_ping
_is_sqlite = settings.database_url.startswith("sqlite")

_engine_kwargs = {
    "echo": settings.debug,
}

if not _is_sqlite:
    _engine_kwargs.update({
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 10,
    })

engine = create_async_engine(settings.database_url, **_engine_kwargs)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# FastAPI Dependency
# ---------------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session for each request, auto-close on exit."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# Startup: Create all tables
# ---------------------------------------------------------------------------
async def init_db() -> None:
    """Create all tables defined in Base.metadata. Idempotent."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
