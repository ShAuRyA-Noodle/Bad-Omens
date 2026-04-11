"""Async SQLAlchemy engine + session factory.

SQLAlchemy 2.0 async API: every request handler that needs the DB
should take ``AsyncSession = Depends(get_session)`` as a parameter.
The session is opened per-request, committed automatically on a clean
exit, rolled back on any exception, and closed when the request ends.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


def _make_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.database_url_async,
        echo=False,                    # SQL echo is extremely noisy; prefer logging
        future=True,
        pool_pre_ping=True,            # detect broken connections
        pool_size=10,
        max_overflow=20,
        pool_recycle=1800,             # recycle after 30 min to survive DB restarts
    )


# Module-level singletons — created once per process, shared across requests.
engine: AsyncEngine = _make_engine()
async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields a transactional session.

    Usage::

        @router.get("/me")
        async def me(session: AsyncSession = Depends(get_session)):
            ...

    The session commits automatically on a clean exit and rolls back on
    any exception bubbling up from the handler.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """Called from the app lifespan on shutdown."""
    await engine.dispose()


__all__ = [
    "AsyncSession",
    "async_session_factory",
    "dispose_engine",
    "engine",
    "get_session",
]

# Silence unused-import linting for symbols re-exported for consumers.
_ = (Any,)
