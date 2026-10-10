"""Async PostgreSQL session for the scraped property comparables database.

Reuses the same DATABASE_URL as the rest of the app (app.services.db,
app.services.property_db) - those use a sync psycopg engine; this module
normalises the same URL to the asyncpg driver instead of requiring a
second env var. Lazily initialised and tolerant of a missing/unreachable
database, matching the rest of the project's "degrade, don't crash"
pattern: with no DATABASE_URL configured, get_comparables() (see
app.tools.comparables_db) simply returns no comparables instead of
raising at import time.
"""
from __future__ import annotations

import os

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None
_last_url: str | None = None


def _normalise_async_url(raw: str) -> str:
    """Accepts plain postgresql://, postgresql+psycopg://, or
    postgresql+asyncpg:// and returns the asyncpg form."""
    url = make_url(raw.strip())
    if url.get_backend_name() != "postgresql":
        raise ValueError(f"DATABASE_URL must be a PostgreSQL URL, got '{url.get_backend_name()}'")
    return str(url.set(drivername="postgresql+asyncpg"))


def get_session_factory() -> async_sessionmaker | None:
    """Returns the async session factory, or None if DATABASE_URL is unset
    or invalid. Never raises - callers treat None the same as "no data"."""
    global _engine, _session_factory, _last_url

    raw = os.getenv("DATABASE_URL", "").strip()
    if not raw:
        return None

    if _session_factory is not None and raw == _last_url:
        return _session_factory

    try:
        engine = create_async_engine(
            _normalise_async_url(raw),
            echo=False,
            pool_pre_ping=True,
            poolclass=NullPool,
        )
    except Exception:
        return None

    _engine = engine
    _last_url = raw
    _session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    return _session_factory


class _NoSessionFactory:
    """AsyncSessionLocal() call-site compatibility shim for callers that
    still do `async with AsyncSessionLocal() as session`."""

    def __call__(self):
        factory = get_session_factory()
        if factory is None:
            raise RuntimeError("DATABASE_URL is not configured")
        return factory()


AsyncSessionLocal = _NoSessionFactory()


async def init_db() -> None:
    factory = get_session_factory()
    if factory is None:
        return
    from property_data.database.models import Base

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session():
    factory = get_session_factory()
    if factory is None:
        return
    async with factory() as session:
        yield session
