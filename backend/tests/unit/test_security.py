"""Unit tests for password hashing and JWT encoding."""
from __future__ import annotations

import uuid

import jwt
import pytest
from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    needs_rehash,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_is_not_plaintext(self) -> None:
        hashed = hash_password("correct horse battery staple")
        assert hashed != "correct horse battery staple"
        assert hashed.startswith("$argon2")

    def test_verify_correct_password(self) -> None:
        hashed = hash_password("correct horse battery staple")
        assert verify_password("correct horse battery staple", hashed) is True

    def test_verify_wrong_password(self) -> None:
        hashed = hash_password("correct horse battery staple")
        assert verify_password("wrong", hashed) is False

    def test_verify_garbage_hash_returns_false(self) -> None:
        assert verify_password("password", "not-a-real-hash") is False

    def test_needs_rehash_false_for_current_params(self) -> None:
        hashed = hash_password("correct horse battery staple")
        assert needs_rehash(hashed) is False


class TestAccessToken:
    def test_round_trip(self) -> None:
        uid = uuid.uuid4()
        token, expires_at = create_access_token(uid, extra_claims={"role": "user"})
        payload = decode_access_token(token)
        assert payload["sub"] == str(uid)
        assert payload["typ"] == "access"
        assert payload["role"] == "user"
        assert expires_at is not None

    def test_rejects_wrong_secret(self) -> None:
        uid = uuid.uuid4()
        token, _ = create_access_token(uid)
        settings = get_settings()
        with pytest.raises(jwt.InvalidSignatureError):
            jwt.decode(
                token,
                # >=32 bytes so PyJWT's InsecureKeyLengthWarning (treated as an
                # error by our filterwarnings) doesn't mask the real assertion.
                "definitely-not-the-real-secret-but-long-enough",
                algorithms=[settings.JWT_ALGORITHM],
            )

    def test_rejects_wrong_token_type(self) -> None:
        settings = get_settings()
        bogus = jwt.encode(
            {
                "sub": str(uuid.uuid4()),
                "exp": 9_999_999_999,
                "typ": "refresh",
            },
            settings.JWT_SECRET.get_secret_value(),
            algorithm=settings.JWT_ALGORITHM,
        )
        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token(bogus)


class TestRefreshToken:
    def test_digest_is_deterministic(self) -> None:
        token, token_hash, _expires = create_refresh_token()
        assert hash_refresh_token(token) == token_hash

    def test_two_tokens_differ(self) -> None:
        a, _, _ = create_refresh_token()
        b, _, _ = create_refresh_token()
        assert a != b
