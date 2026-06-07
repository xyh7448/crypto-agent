"""
Async SQLAlchemy engine, session factory, and declarative base.

Supports the pgvector extension for vector similarity search. Provides a
FastAPI-compatible ``get_db()`` async generator dependency.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import settings

# ── Async engine ───────────────────────────────────────────────────────────

engine = create_async_engine(
    settings.POSTGRES_URI,
    echo=False,
    poolclass=NullPool,  # connection-per-session for serverless-friendliness
    future=True,
)


@event.listens_for(engine.sync_engine, "connect")
def _enable_pgvector(dbapi_connection: object, _connection_record: object) -> None:
    """Enable pgvector extension on every new raw connection.

    SQLAlchemy event listener attached to the sync underlying engine so it
    fires once per checkout.
    """
    cursor = dbapi_connection.cursor()  # type: ignore[union-attr]
    cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
    cursor.close()


# ── Session factory ────────────────────────────────────────────────────────

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# ── Declarative base ───────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""

    pass


# ── FastAPI dependency ─────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an :class:`AsyncSession`.

    Usage::

        from fastapi import Depends
        from app.core.database import get_db

        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)) -> ...:
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
