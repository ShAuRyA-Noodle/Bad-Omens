"""FastAPI application factory.

All app construction happens in :func:`create_app`. The module-level
``app`` variable is what ``uvicorn app.main:app`` loads.
"""
from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api import public
from app.api.v1 import auth, exports, health, jobs, projects, results, samples, ws
from app.core.config import get_settings
from app.core.logging import (
    bind_request_context,
    clear_request_context,
    configure_logging,
    get_logger,
)
from app.db.session import dispose_engine
from app.services.queue import close_redis

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Run startup / shutdown hooks.

    The engine is created eagerly at import time in ``app.db.session`` so
    there is nothing to spin up here yet. On shutdown we dispose the
    connection pool cleanly so Postgres doesn't see dangling connections.
    """
    settings = get_settings()
    log.info(
        "application.startup",
        project=settings.PROJECT_NAME,
        version=__version__,
        environment=settings.ENVIRONMENT,
    )
    try:
        yield
    finally:
        log.info("application.shutdown")
        await close_redis()
        await dispose_engine()


def create_app() -> FastAPI:
    """Construct the FastAPI app.

    Kept as a factory so tests can build isolated apps with overridden
    dependencies without touching the module-level singleton.
    """
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=__version__,
        description=(
            "Reproducible environmental DNA analysis platform. "
            "Open source, no mock data, no fabricated metrics."
        ),
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ─── CORS ──────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    # ─── Request-ID / structured-log middleware ────────────────────────
    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        started = time.perf_counter()

        bind_request_context(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        log.info("request.started")
        try:
            response = await call_next(request)
        except Exception:
            log.exception("request.unhandled_error")
            raise
        else:
            elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
            log.info(
                "request.completed",
                status_code=response.status_code,
                elapsed_ms=elapsed_ms,
            )
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            clear_request_context()

    # ─── Security headers ──────────────────────────────────────────────
    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        # HSTS only in production (TLS terminates at the edge). No CSP is set
        # here: the only HTML this API serves is Swagger UI at /docs, which
        # loads assets from a CDN, so a strict CSP would break it. The frontend
        # (separate origin) carries its own CSP.
        if settings.ENVIRONMENT == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains"
            )
        return response

    # ─── Exception handlers ────────────────────────────────────────────
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"message": exc.detail, "code": exc.status_code}},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        _request: Request, exc: Exception
    ) -> JSONResponse:
        # The structlog middleware already logged the traceback — here we
        # return a sanitized payload so the client never sees stack details.
        log.error("unhandled_exception", exc_type=type(exc).__name__, detail=str(exc))
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "message": "Internal server error",
                    "code": 500,
                },
            },
        )

    # ─── Routes ────────────────────────────────────────────────────────
    # `/health`, `/ready`, and `/ws/*` live at the root so infra probes
    # and browser WebSocket clients don't need to know the v1 prefix.
    app.include_router(health.router)
    app.include_router(ws.router)
    # Public provenance verification (/public-key, /provenance/verify) — no
    # auth, no v1 prefix, so anyone can verify a manifest's signature.
    app.include_router(public.router)

    # REST resources are namespaced under /api/v1/…
    app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
    app.include_router(samples.router, prefix=settings.API_V1_PREFIX)
    app.include_router(jobs.router, prefix=settings.API_V1_PREFIX)
    app.include_router(projects.router, prefix=settings.API_V1_PREFIX)
    app.include_router(results.router, prefix=settings.API_V1_PREFIX)
    app.include_router(exports.router, prefix=settings.API_V1_PREFIX)

    return app


app: FastAPI = create_app()
