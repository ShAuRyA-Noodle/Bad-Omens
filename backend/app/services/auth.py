"""Authentication service — signup, login, refresh, logout.

Separated from the route handlers so the core logic can be tested
without spinning up FastAPI. Every method takes an :class:`AsyncSession`
so the caller controls the transaction boundary.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from app.core.security import (
    create_access_token,
    create_refresh_token,
    dummy_verify,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.db.models import RefreshSession, User, UserRole
from app.schemas.auth import TokenPair

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


class AuthError(Exception):
    """Base for all auth-service errors.

    The HTTP layer maps these to 400/401/409 as appropriate.
    """


class EmailAlreadyRegistered(AuthError):
    pass


class InvalidCredentials(AuthError):
    pass


class InvalidRefreshToken(AuthError):
    pass


class AccountDisabled(AuthError):
    pass


async def signup(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    user_agent: str | None,
    ip_address: str | None,
) -> tuple[User, TokenPair]:
    email = email.strip().lower()
    existing = await session.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise EmailAlreadyRegistered(email)

    user = User(
        email=email,
        password_hash=hash_password(password),
        role=UserRole.USER,
        is_active=True,
    )
    session.add(user)
    await session.flush()

    tokens = await _issue_tokens(
        session,
        user_id=user.id,
        role=user.role.value,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    return user, tokens


async def login(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    user_agent: str | None,
    ip_address: str | None,
) -> tuple[User, TokenPair]:
    email = email.strip().lower()
    user = await session.scalar(select(User).where(User.email == email))
    if user is None:
        # Pay the same argon2 cost as a real verify so timing can't reveal
        # whether the email exists, then return the identical error.
        dummy_verify()
        raise InvalidCredentials()
    if not verify_password(password, user.password_hash):
        # Same error as "no such user" to avoid leaking existence.
        raise InvalidCredentials()

    if not user.is_active:
        raise AccountDisabled()

    tokens = await _issue_tokens(
        session,
        user_id=user.id,
        role=user.role.value,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    return user, tokens


async def refresh(
    session: AsyncSession,
    *,
    refresh_token: str,
    user_agent: str | None,
    ip_address: str | None,
) -> TokenPair:
    token_hash = hash_refresh_token(refresh_token)
    now = datetime.now(tz=UTC)

    row = await session.scalar(
        select(RefreshSession).where(RefreshSession.token_sha256 == token_hash)
    )
    if row is None or row.revoked_at is not None or row.expires_at <= now:
        raise InvalidRefreshToken()

    user = await session.get(User, row.user_id)
    if user is None or not user.is_active:
        raise InvalidRefreshToken()

    # Rotate: revoke the old refresh token and issue a fresh pair.
    row.revoked_at = now
    await session.flush()

    return await _issue_tokens(
        session,
        user_id=user.id,
        role=user.role.value,
        user_agent=user_agent,
        ip_address=ip_address,
    )


async def logout(
    session: AsyncSession,
    *,
    refresh_token: str,
) -> None:
    """Revoke a refresh token. Idempotent — no error if already revoked."""
    token_hash = hash_refresh_token(refresh_token)
    row = await session.scalar(
        select(RefreshSession).where(RefreshSession.token_sha256 == token_hash)
    )
    if row is None:
        return
    if row.revoked_at is None:
        row.revoked_at = datetime.now(tz=UTC)
        await session.flush()


# ─── Internal helpers ─────────────────────────────────────────────────


async def _issue_tokens(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    role: str,
    user_agent: str | None,
    ip_address: str | None,
) -> TokenPair:
    access_token, access_exp = create_access_token(user_id, extra_claims={"role": role})
    refresh_token, refresh_hash, refresh_exp = create_refresh_token()

    session.add(
        RefreshSession(
            user_id=user_id,
            token_sha256=refresh_hash,
            expires_at=refresh_exp,
            user_agent=user_agent,
            ip_address=ip_address,
        )
    )
    await session.flush()

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        access_expires_at=access_exp,
        refresh_expires_at=refresh_exp,
    )
