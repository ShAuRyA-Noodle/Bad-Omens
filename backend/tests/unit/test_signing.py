"""Unit tests for the Ed25519 signing primitives (app.core.signing).

These prove the property the old code faked: a manifest signature is a real
cryptographic signature — it requires the private key to produce, the public
key to verify, and fails if a single byte of the signed message changes.
"""
from __future__ import annotations

from app.core import signing as crypto


def test_sign_then_verify_roundtrip() -> None:
    private, public = crypto.generate_keypair()
    message = b"canonical manifest bytes"
    signature = crypto.sign(private, message)

    assert signature.startswith("ed25519:")
    assert crypto.verify(public, message, signature) is True


def test_verify_rejects_tampered_message() -> None:
    private, public = crypto.generate_keypair()
    signature = crypto.sign(private, b"original content")

    assert crypto.verify(public, b"tampered content", signature) is False


def test_verify_rejects_wrong_key() -> None:
    private_a, _ = crypto.generate_keypair()
    _, public_b = crypto.generate_keypair()
    message = b"signed by A"
    signature = crypto.sign(private_a, message)

    # B's public key must not verify A's signature.
    assert crypto.verify(public_b, message, signature) is False


def test_verify_rejects_malformed_signature() -> None:
    _, public = crypto.generate_keypair()
    message = b"x"

    assert crypto.verify(public, message, "not-a-signature") is False
    assert crypto.verify(public, message, "ed25519:!!!not-base64!!!") is False
    assert crypto.verify(public, message, "ed25519:") is False


def test_sha256_is_not_a_valid_signature() -> None:
    """The old fake form ('sha256:<hex>') must never verify as a signature."""
    import hashlib

    private, public = crypto.generate_keypair()
    message = b"content"
    fake = "sha256:" + hashlib.sha256(message).hexdigest()

    assert crypto.verify(public, message, fake) is False


def test_public_from_private_matches_generated_public() -> None:
    private, public = crypto.generate_keypair()
    assert crypto.public_from_private(private) == public


def test_public_key_pem_and_b64_are_stable() -> None:
    _, public = crypto.generate_keypair()
    pem = crypto.public_key_pem(public)
    b64 = crypto.public_key_b64(public)

    assert pem.startswith("-----BEGIN PUBLIC KEY-----")
    assert "-----END PUBLIC KEY-----" in pem
    # b64 of a raw 32-byte Ed25519 key is 44 chars (with padding).
    assert len(b64) == 44
