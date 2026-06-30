"""Authentication routes — /auth/signup, /auth/login, /auth/refresh, /auth/logout, /auth/me."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import CurrentUser, SessionDep, client_fingerprint
from app.api.ratelimit import rate_limiter
from app.core.config import get_settings
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    SignupRequest,
    TokenPair,
    UserPublic,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

# IP rate limit on the credential endpoints to blunt brute force / stuffing.
_auth_rate_limit = rate_limiter(
    name="auth",
    limit=get_settings().RATE_LIMIT_AUTH_PER_MINUTE,
    window_seconds=60,
)


@router.post(
    "/signup",
    response_model=TokenPair,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new account",
    dependencies=[Depends(_auth_rate_limit)],
)
async def signup(
    payload: SignupRequest,
    request: Request,
    session: SessionDep,
) -> TokenPair:
    user_agent, ip = client_fingerprint(request)
    try:
        _user, tokens = await auth_service.signup(
            session,
            email=payload.email,
            password=payload.password,
            user_agent=user_agent,
            ip_address=ip,
        )
    except auth_service.EmailAlreadyRegistered as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        ) from exc
    return tokens


@router.post(
    "/login",
    response_model=TokenPair,
    summary="Exchange email + password for a token pair",
    dependencies=[Depends(_auth_rate_limit)],
)
async def login(
    payload: LoginRequest,
    request: Request,
    session: SessionDep,
) -> TokenPair:
    user_agent, ip = client_fingerprint(request)
    try:
        _user, tokens = await auth_service.login(
            session,
            email=payload.email,
            password=payload.password,
            user_agent=user_agent,
            ip_address=ip,
        )
    except auth_service.InvalidCredentials as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        ) from exc
    except auth_service.AccountDisabled as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled",
        ) from exc
    return tokens


@router.post(
    "/refresh",
    response_model=TokenPair,
    summary="Exchange a refresh token for a new token pair (old one is revoked)",
)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    session: SessionDep,
) -> TokenPair:
    user_agent, ip = client_fingerprint(request)
    try:
        return await auth_service.refresh(
            session,
            refresh_token=payload.refresh_token,
            user_agent=user_agent,
            ip_address=ip,
        )
    except auth_service.InvalidRefreshToken as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from exc


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Revoke a refresh token",
)
async def logout(
    payload: LogoutRequest,
    session: SessionDep,
) -> MessageResponse:
    await auth_service.logout(session, refresh_token=payload.refresh_token)
    return MessageResponse(message="Refresh token revoked")


@router.get(
    "/me",
    response_model=UserPublic,
    summary="Return the authenticated user",
)
async def me(user: CurrentUser) -> UserPublic:
    return UserPublic.model_validate(user)
