"""Shared pytest fixtures.

Unit tests use the ``app_factory`` fixture to get a fresh FastAPI app
with overridden dependencies. Integration tests use the
``postgres_url`` / ``redis_client`` / ``minio_client`` fixtures which
spin up real containers via ``testcontainers`` (marked ``integration``).
"""
from __future__ import annotations

import os

import pytest

# Make sure tests never see the developer's real .env — strip any
# pre-existing env vars that Settings() would otherwise pick up.
for _var in (
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "REDIS_HOST",
    "REDIS_PORT",
    "MINIO_ENDPOINT",
    "MINIO_ACCESS_KEY",
    "MINIO_SECRET_KEY",
    "MINIO_BUCKET",
    "MINIO_SECURE",
    "JWT_SECRET",
    "IUCN_REDLIST_TOKEN",
    "ENVIRONMENT",
    "LOG_LEVEL",
):
    os.environ.pop(_var, None)


# Provide a minimal, valid Settings input for unit tests so Settings()
# doesn't error on missing required fields.
_UNIT_TEST_DEFAULTS = {
    "POSTGRES_PASSWORD": "unit-test-password",
    "MINIO_ACCESS_KEY": "unittestkey",
    "MINIO_SECRET_KEY": "unittestsecretkey",
    "JWT_SECRET": "unit-test-jwt-secret-long-enough-to-satisfy-validator",
    "ENVIRONMENT": "test",
    "LOG_LEVEL": "WARNING",
}
for _k, _v in _UNIT_TEST_DEFAULTS.items():
    os.environ.setdefault(_k, _v)


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    """Make every test start with a fresh Settings singleton."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
