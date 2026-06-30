"""Password hashing and JWT encoding / decoding.

Argon2id is the current OWASP recommendation for password hashing.
JWTs are signed HS256 with the secret from :class:`Settings`. Refresh
tokens are opaque random strings whose SHA256 digest is stored in
``refresh_sessions`` for revocation.
"""
from __future__ import annotations

import contextlib
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings

if TYPE_CHECKING:
    import uuid

# OWASP 2024 recommended minimums. These are conservative; tune higher
# only if benchmarked on the target hardware.
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,   # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


# ─── Password hashing ──────────────────────────────────────────────────


def hash_password(password: str) -> str:
    """Return an argon2id hash string safe to store in the database."""
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Return True iff ``password`` matches ``hashed``.

    Catches the three error classes Argon2 raises so callers get a
    simple boolean. Does not rehash on parameter-mismatch; that's a
    future concern when we bump hashing parameters.
    """
    try:
        return _hasher.verify(hashed, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    """True if ``hashed`` was produced with outdated parameters."""
    return _hasher.check_needs_rehash(hashed)


# Pre-computed argon2id hash used purely to equalize login timing when an
# email does not exist. Without this, "no such user" returns instantly while
# "wrong password" pays the argon2 cost — a timing oracle that lets an attacker
# enumerate registered emails. Computed once at import.
_DUMMY_HASH = _hasher.hash("relict-login-timing-equalizer")  # noqa: S106 — not a credential


def dummy_verify() -> None:
    """Run a throwaway argon2 verify so a missing-user login costs the same
    wall-clock time as a real password check."""
    with contextlib.suppress(VerifyMismatchError, VerificationError, InvalidHashError):
        _hasher.verify(_DUMMY_HASH, "not-the-password")


# ─── JWT access tokens ─────────────────────────────────────────────────


TokenType = Literal["access", "refresh"]


def _now() -> datetime:
    return datetime.now(tz=UTC)


def create_access_token(
    subject: uuid.UUID,
    *,
    extra_claims: dict[str, Any] | None = None,
) -> tuple[str, datetime]:
    """Return ``(token, expires_at)`` for a short-lived access JWT."""
    settings = get_settings()
    expires_at = _now() + timedelta(minutes=settings.JWT_ACCESS_TTL_MINUTES)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(_now().timestamp()),
        "exp": int(expires_at.timestamp()),
        "typ": "access",
        "jti": secrets.token_urlsafe(16),
    }
    if extra_claims:
        payload.update(extra_claims)
    token = jwt.encode(
        payload,
        settings.JWT_SECRET.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )
    return token, expires_at


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT. Raises :class:`jwt.PyJWTError` on failure."""
    settings = get_settings()
    payload: dict[str, Any] = jwt.decode(
        token,
        settings.JWT_SECRET.get_secret_value(),
        algorithms=[settings.JWT_ALGORITHM],
        options={"require": ["sub", "exp", "typ"]},
    )
    if payload.get("typ") != "access":
        msg = "wrong token type"
        raise jwt.InvalidTokenError(msg)
    return payload


# ─── Refresh tokens ────────────────────────────────────────────────────


def create_refresh_token() -> tuple[str, str, datetime]:
    """Return ``(token, token_sha256, expires_at)``.

    The raw ``token`` is handed to the client once; only the SHA256
    digest is persisted so a DB leak cannot be used to forge sessions.
    """
    settings = get_settings()
    token = secrets.token_urlsafe(64)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expires_at = _now() + timedelta(days=settings.JWT_REFRESH_TTL_DAYS)
    return token, token_hash, expires_at


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


__all__ = [
    "TokenType",
    "create_access_token",
    "create_refresh_token",
    "decode_access_token",
    "dummy_verify",
    "hash_password",
    "hash_refresh_token",
    "needs_rehash",
    "verify_password",
]
