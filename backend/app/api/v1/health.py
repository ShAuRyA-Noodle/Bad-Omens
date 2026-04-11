"""Health and readiness probes.

``/health``
    Liveness — returns 200 as long as the Python process is alive.
    Cheap, no external dependencies. Kubernetes / Docker Compose use
    this to decide whether to kill and restart the container.

``/ready``
    Readiness — verifies Postgres, Redis, and MinIO are reachable.
    Returns 200 with per-component status. This endpoint is fleshed
    out in Phase 1f once the queue + storage services exist.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, status
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str


class ReadinessResponse(BaseModel):
    status: str
    checks: dict[str, dict[str, Any]]


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness probe",
)
async def health() -> HealthResponse:
    """Liveness probe — 200 iff the process is alive."""
    from app import __version__

    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=__version__,
        environment=settings.ENVIRONMENT,
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Readiness probe",
)
async def ready() -> ReadinessResponse:
    """Readiness probe — verifies Postgres (and, in Phase 1f+, Redis + MinIO).

    Always returns HTTP 200 with a per-component status map so dashboards
    can parse it cheaply. Callers should inspect the ``status`` field
    (``ok`` / ``degraded``) rather than the HTTP code.
    """
    checks: dict[str, dict[str, Any]] = {}

    # Postgres
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = {"status": "ok"}
    except Exception as exc:  # noqa: BLE001 — all errors map to a degraded check
        checks["postgres"] = {"status": "fail", "error": str(exc)}

    overall = "ok" if all(c["status"] == "ok" for c in checks.values()) else "degraded"
    return ReadinessResponse(status=overall, checks=checks)
