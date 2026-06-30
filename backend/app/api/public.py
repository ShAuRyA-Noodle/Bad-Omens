"""Public, unauthenticated provenance endpoints.

``GET /public-key``
    Returns the server's active Ed25519 public key (PEM + raw base64) so any
    third party can verify a manifest's signature offline.

``POST /provenance/verify``
    Recomputes the canonical hash of a submitted manifest and verifies its
    Ed25519 signature against the server's public key. Needs no secret, so it
    is intentionally public — verification is meant to be reproducible by
    anyone.

Both are mounted at the application root (no ``/api/v1`` prefix) so the
public key has a stable, memorable URL that the offline verifier and the
research paper can cite.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core import manifest as manifest_core
from app.core import signing as crypto
from app.db.session import async_session_factory
from app.services.signing import get_active_public_key

router = APIRouter(tags=["provenance"])


class PublicKeyResponse(BaseModel):
    algorithm: str
    public_key_b64: str
    public_key_pem: str


class VerifyRequest(BaseModel):
    manifest: dict[str, Any] = Field(..., description="A full provenance manifest JSON object.")


class VerifyResponse(BaseModel):
    verified: bool
    content_hash_ok: bool
    signature_ok: bool
    computed_sha256: str
    claimed_sha256: str | None
    algorithm: str
    detail: str


@router.get(
    "/public-key",
    response_model=PublicKeyResponse,
    summary="Server Ed25519 public key for verifying provenance manifests",
)
async def public_key() -> PublicKeyResponse:
    async with async_session_factory() as session:
        key = await get_active_public_key(session)
    if key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No signing key exists yet — run a job to mint one.",
        )
    return PublicKeyResponse(
        algorithm=key.algorithm,
        public_key_b64=crypto.public_key_b64(key.public_key),
        public_key_pem=crypto.public_key_pem(key.public_key),
    )


@router.post(
    "/provenance/verify",
    response_model=VerifyResponse,
    summary="Verify a provenance manifest's content hash and Ed25519 signature",
)
async def verify_manifest(body: VerifyRequest) -> VerifyResponse:
    manifest = body.manifest

    computed = manifest_core.compute_manifest_hash(manifest)
    claimed = manifest.get("manifest_sha256")
    content_hash_ok = bool(claimed) and computed == claimed

    signature = manifest.get("signature")
    async with async_session_factory() as session:
        key = await get_active_public_key(session)

    if key is None:
        signature_ok = False
        detail = "No server signing key available to verify the signature."
    elif not signature:
        signature_ok = False
        detail = "Manifest carries no signature."
    else:
        signature_ok = crypto.verify(
            key.public_key, manifest_core.canonical_bytes(manifest), signature
        )
        detail = (
            "Signature valid."
            if signature_ok
            else "Signature does not verify against the server key."
        )

    if content_hash_ok and not signature_ok and key is not None and signature:
        detail = "Content hash matches but the signature is invalid — possible tampering."
    elif not content_hash_ok:
        detail = f"Content hash mismatch (computed {computed[:16]}…). {detail}"

    return VerifyResponse(
        verified=content_hash_ok and signature_ok,
        content_hash_ok=content_hash_ok,
        signature_ok=signature_ok,
        computed_sha256=computed,
        claimed_sha256=claimed,
        algorithm="ed25519",
        detail=detail,
    )
