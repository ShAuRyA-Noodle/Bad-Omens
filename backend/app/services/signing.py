"""Database-backed access to the server's Ed25519 signing key.

The worker (sync SQLAlchemy session) calls :func:`get_or_create_signing_key`
to obtain the private key when it signs a manifest. The API (async session)
calls :func:`get_active_public_key` to serve the public half at
``GET /public-key`` and to verify manifests at ``/provenance/verify``.

The key is a singleton: a partial unique index on ``signing_keys.is_active``
(see :class:`app.db.models.SigningKey`) guarantees at most one active row, so
the first job to run on a fresh database mints the keypair and every
subsequent job reuses it.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core import signing as crypto
from app.db.models import SigningKey


def get_or_create_signing_key(session: Session) -> SigningKey:
    """Return the active signing key, generating one on first use (sync)."""
    existing = session.execute(
        select(SigningKey).where(SigningKey.is_active.is_(True)).limit(1)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    private_raw, public_raw = crypto.generate_keypair()
    key = SigningKey(
        algorithm="ed25519",
        private_key=private_raw,
        public_key=public_raw,
        is_active=True,
    )
    session.add(key)
    try:
        session.flush()
    except IntegrityError:
        # Another worker raced us to create the singleton — roll back our
        # insert and read theirs.
        session.rollback()
        return session.execute(
            select(SigningKey).where(SigningKey.is_active.is_(True)).limit(1)
        ).scalar_one()
    return key


async def get_active_public_key(session: AsyncSession) -> SigningKey | None:
    """Return the active signing key for serving/verifying (async, read-only)."""
    result = await session.execute(
        select(SigningKey).where(SigningKey.is_active.is_(True)).limit(1)
    )
    return result.scalar_one_or_none()


__all__ = ["get_active_public_key", "get_or_create_signing_key"]
