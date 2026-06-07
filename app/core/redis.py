"""
Async Redis client singleton.

Provides a single ``redis.asyncio.Redis`` instance configured from
:mod:`app.core.config` and a FastAPI-compatible ``get_redis()`` dependency.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings

# ── Connection pool ────────────────────────────────────────────────────────

_pool: ConnectionPool | None = None


def _get_pool() -> ConnectionPool:
    """Return or initialise the global connection pool singleton."""
    global _pool  # noqa: PLW0603
    if _pool is None:
        _pool = ConnectionPool.from_url(
            settings.REDIS_URI,
            decode_responses=True,
            max_connections=20,
        )
    return _pool


# ── Redis client singleton ─────────────────────────────────────────────────

_redis: Redis[Any] | None = None


def get_redis_client() -> Redis[Any]:
    """Return or initialise the global async Redis client singleton."""
    global _redis  # noqa: PLW0603
    if _redis is None:
        _redis = Redis.from_pool(_get_pool())  # type: ignore[arg-type]
    return _redis


# ── FastAPI dependency ─────────────────────────────────────────────────────

async def get_redis() -> AsyncGenerator[Redis[Any], None]:
    """FastAPI dependency that yields the global Redis client.

    Usage::

        from fastapi import Depends
        from app.core.redis import get_redis

        @router.get("/cache/{key}")
        async def get_cache(
            key: str,
            r: Redis[Any] = Depends(get_redis),
        ) -> str | None:
            return await r.get(key)
    """
    yield get_redis_client()


# ── Lifecycle helpers ──────────────────────────────────────────────────────

async def close_redis() -> None:
    """Close the Redis connection pool (call on application shutdown)."""
    global _redis, _pool  # noqa: PLW0603
    if _redis is not None:
        await _redis.aclose()
        _redis = None
    if _pool is not None:
        await _pool.aclose()
        _pool = None
