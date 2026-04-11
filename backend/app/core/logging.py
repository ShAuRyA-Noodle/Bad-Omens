"""Structured JSON logging via structlog.

Every log line is a JSON object with a consistent shape so that logs
can be ingested into Loki / CloudWatch / Datadog without a parser. The
:func:`bind_request_context` helper adds per-request fields so an
entire request can be traced by filtering on ``request_id``.
"""
from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor


def _add_severity(
    _logger: logging.Logger, _method: str, event_dict: EventDict
) -> EventDict:
    """Emit a `severity` field alongside `level` for GCP compatibility."""
    if level := event_dict.get("level"):
        event_dict["severity"] = str(level).upper()
    return event_dict


def _drop_color_message(
    _logger: logging.Logger, _method: str, event_dict: EventDict
) -> EventDict:
    """Strip uvicorn's `color_message` duplicate field."""
    event_dict.pop("color_message", None)
    return event_dict


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog and the stdlib logging bridge.

    Call this exactly once at process startup. Subsequent calls are idempotent
    but unnecessary.
    """
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        _add_severity,
        _drop_color_message,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        timestamper,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(log_level)
        ),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(sort_keys=True),
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)

    # Quiet noisy libraries that are chatty at INFO.
    for noisy in ("uvicorn.access", "httpx", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> Any:
    """Return a bound structlog logger."""
    return structlog.get_logger(name)


def bind_request_context(**kwargs: Any) -> None:
    """Bind values to the current request's log context.

    Usage inside a FastAPI middleware::

        bind_request_context(request_id=req_id, path=request.url.path)
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_request_context() -> None:
    structlog.contextvars.clear_contextvars()
