"""Lightweight Redis-backed fixed-window rate limiting.

Applied as a FastAPI dependency to abuse-prone endpoints (auth). Keyed by
client IP. Redis is already part of the stack (job queue + WS pub/sub), so
this adds no new infrastructure and works across multiple API instances.

Fails open: if Redis is unreachable, the request is allowed (a Redis hiccup
must never lock every user out of login) — but the failure is logged so it is
visible.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request, status

from app.api.deps import client_fingerprint
from app.core.logging import get_logger
from app.services.queue import get_redis

log = get_logger(__name__)


def rate_limiter(
    *, name: str, limit: int, window_seconds: int
) -> Callable[[Request], Awaitable[None]]:
    """Build a dependency that allows ``limit`` requests per ``window_seconds``
    per client IP for the bucket ``name``."""

    async def _dependency(request: Request) -> None:
        _ua, ip = client_fingerprint(request)
        bucket = f"ratelimit:{name}:{ip or 'unknown'}"
        try:
            redis = get_redis()
            count = await redis.incr(bucket)
            if count == 1:
                await redis.expire(bucket, window_seconds)
        except Exception as exc:  # noqa: BLE001 — fail open on any Redis error
            log.warning("ratelimit.redis_unavailable", bucket=name, error=str(exc))
            return

        if count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please slow down and try again shortly.",
                headers={"Retry-After": str(window_seconds)},
            )

    return _dependency


__all__ = ["rate_limiter"]
