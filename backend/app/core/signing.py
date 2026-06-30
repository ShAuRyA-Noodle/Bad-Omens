"""Ed25519 signing primitives for provenance manifests.

Pure cryptographic helpers — no I/O, no database. The keypair itself is
persisted in the ``signing_keys`` table (:class:`app.db.models.SigningKey`)
and loaded by the worker when it signs a manifest; the public half is served
at ``GET /public-key`` so anyone can verify a manifest offline.

A manifest *signature* is a real Ed25519 signature over the SHA256 of the
manifest's canonical (deterministic) payload, encoded as
``ed25519:<base64-signature>``.

This deliberately replaces the previous behaviour of relabelling the content
hash as a "signature": a SHA256 of the content is **not** tamper-evident —
anyone editing the manifest can recompute it. A real Ed25519 signature
requires the private key to produce and the public key to verify, and fails
if a single byte of the signed content changes.
"""
from __future__ import annotations

import base64
import binascii

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

SIGNATURE_PREFIX = "ed25519:"


def generate_keypair() -> tuple[bytes, bytes]:
    """Return ``(private_raw, public_raw)`` as 32-byte raw Ed25519 keys."""
    private = Ed25519PrivateKey.generate()
    private_raw = private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_raw = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private_raw, public_raw


def public_from_private(private_raw: bytes) -> bytes:
    """Derive the raw public key from a raw private key."""
    private = Ed25519PrivateKey.from_private_bytes(private_raw)
    return private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def sign(private_raw: bytes, message: bytes) -> str:
    """Sign ``message`` and return ``ed25519:<base64 signature>``."""
    private = Ed25519PrivateKey.from_private_bytes(private_raw)
    signature = private.sign(message)
    return SIGNATURE_PREFIX + base64.b64encode(signature).decode("ascii")


def verify(public_raw: bytes, message: bytes, signature: str) -> bool:
    """Return True iff ``signature`` is a valid Ed25519 signature of ``message``.

    Accepts the ``ed25519:<base64>`` form produced by :func:`sign`. Returns
    False (never raises) for a malformed prefix, bad base64, or a signature
    that does not verify — so callers get a clean boolean verdict.
    """
    if not signature.startswith(SIGNATURE_PREFIX):
        return False
    try:
        raw_sig = base64.b64decode(signature[len(SIGNATURE_PREFIX):], validate=True)
    except (ValueError, binascii.Error):
        return False
    try:
        public = Ed25519PublicKey.from_public_bytes(public_raw)
        public.verify(raw_sig, message)
    except (InvalidSignature, ValueError):
        return False
    return True


def public_key_pem(public_raw: bytes) -> str:
    """Serialize a raw public key as a PEM ``SubjectPublicKeyInfo`` block."""
    public = Ed25519PublicKey.from_public_bytes(public_raw)
    pem = public.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return pem.decode("ascii")


def public_key_b64(public_raw: bytes) -> str:
    """Base64-encode the 32-byte raw public key (compact transport form)."""
    return base64.b64encode(public_raw).decode("ascii")


__all__ = [
    "SIGNATURE_PREFIX",
    "generate_keypair",
    "public_from_private",
    "public_key_b64",
    "public_key_pem",
    "sign",
    "verify",
]
