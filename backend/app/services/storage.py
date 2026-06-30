"""Object storage service — S3-compatible, backed by MinIO in dev.

All raw FASTQ files, intermediate pipeline outputs, reports, DwC-A
archives, and provenance manifests live here. Postgres holds only the
S3 key (``sample.s3_key``) and a SHA256 digest.

S3-compatibility means the same code runs unchanged against AWS S3,
Cloudflare R2, Backblaze B2, Hetzner Object Storage, etc., simply by
switching ``MINIO_ENDPOINT`` and credentials.
"""
from __future__ import annotations

import hashlib
import io
import tempfile
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, BinaryIO, cast

from minio import Minio
from minio.error import S3Error

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

log = get_logger(__name__)


@dataclass(frozen=True)
class StoredObject:
    """Result of a successful upload."""

    key: str
    sha256: str
    size_bytes: int
    content_type: str


class FileTooLarge(Exception):
    """Raised when an upload stream exceeds the configured byte limit."""


class Storage:
    """Thin wrapper around the :mod:`minio` client with sane defaults.

    Instances are cheap — the underlying HTTP pool is shared via the
    module-level ``_client`` cached by :func:`get_storage`.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = Minio(
            self._settings.MINIO_ENDPOINT,
            access_key=self._settings.MINIO_ACCESS_KEY,
            secret_key=self._settings.MINIO_SECRET_KEY.get_secret_value(),
            secure=self._settings.MINIO_SECURE,
        )

    @property
    def bucket(self) -> str:
        return self._settings.MINIO_BUCKET

    # ─── Lifecycle ─────────────────────────────────────────────────────

    def ensure_bucket(self) -> None:
        """Idempotent — the compose `minio-init` job usually beats us to it."""
        if not self._client.bucket_exists(self.bucket):
            self._client.make_bucket(self.bucket)
            log.info("storage.bucket_created", bucket=self.bucket)

    # ─── Uploads ───────────────────────────────────────────────────────

    def build_sample_key(
        self, *, user_id: uuid.UUID, job_id: uuid.UUID, filename: str
    ) -> str:
        """Deterministic S3 key layout: ``samples/<user>/<job>/<uuid>-<filename>``."""
        safe_name = _sanitize_filename(filename)
        return f"samples/{user_id}/{job_id}/{uuid.uuid4().hex}-{safe_name}"

    def put_bytes(
        self,
        *,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> StoredObject:
        """Upload an in-memory byte buffer. Used for small metadata blobs."""
        stream = io.BytesIO(data)
        sha256 = hashlib.sha256(data).hexdigest()
        size = len(data)
        self._client.put_object(
            self.bucket,
            key,
            stream,
            length=size,
            content_type=content_type,
        )
        return StoredObject(key=key, sha256=sha256, size_bytes=size, content_type=content_type)

    def put_stream(
        self,
        *,
        key: str,
        stream: BinaryIO,
        content_type: str = "application/octet-stream",
        chunk_size: int = 8 * 1024 * 1024,
        max_bytes: int | None = None,
    ) -> StoredObject:
        """Upload a stream, computing SHA256 as it flows.

        Spools to a temporary file (kept in memory up to a small threshold,
        then on disk) so peak RAM stays bounded regardless of upload size —
        the previous version read the whole file into an unbounded BytesIO,
        which let a large upload exhaust memory before any size check ran.

        ``max_bytes`` is enforced *during* the read: an oversized stream is
        rejected the moment it crosses the limit (before it is fully consumed
        and before anything is written to object storage), raising
        :class:`FileTooLarge`.
        """
        hasher = hashlib.sha256()
        size = 0
        with tempfile.SpooledTemporaryFile(max_size=16 * 1024 * 1024) as buffer:
            while True:
                chunk = stream.read(chunk_size)
                if not chunk:
                    break
                size += len(chunk)
                if max_bytes is not None and size > max_bytes:
                    msg = f"Upload exceeds the maximum of {max_bytes} bytes"
                    raise FileTooLarge(msg)
                hasher.update(chunk)
                buffer.write(chunk)

            if size == 0:
                msg = "Refusing to store an empty object"
                raise ValueError(msg)

            buffer.seek(0)
            self._client.put_object(
                self.bucket,
                key,
                cast("BinaryIO", buffer),  # SpooledTemporaryFile satisfies the IO protocol
                length=size,
                content_type=content_type,
            )
        return StoredObject(
            key=key,
            sha256=hasher.hexdigest(),
            size_bytes=size,
            content_type=content_type,
        )

    # ─── Downloads ─────────────────────────────────────────────────────

    def presigned_get_url(
        self, key: str, *, expires: timedelta = timedelta(minutes=15)
    ) -> str:
        """Pre-signed GET URL — the only way clients ever download raw files."""
        return self._client.presigned_get_object(self.bucket, key, expires=expires)

    def stat(self, key: str) -> dict[str, object]:
        """Return object metadata as a plain dict (mostly for /ready & tests)."""
        obj = self._client.stat_object(self.bucket, key)
        return {
            "size": obj.size,
            "etag": obj.etag,
            "content_type": obj.content_type,
            "last_modified": obj.last_modified,
        }

    def delete(self, key: str) -> None:
        try:
            self._client.remove_object(self.bucket, key)
        except S3Error as exc:
            log.warning("storage.delete_failed", key=key, error=str(exc))
            raise

    async def iter_object(self, key: str) -> AsyncIterator[bytes]:
        """Async streaming read for routes that want to pipe through."""
        response = self._client.get_object(self.bucket, key)
        try:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                yield chunk
        finally:
            response.close()
            response.release_conn()


# ─── Filename sanitisation ─────────────────────────────────────────────

_FILENAME_SAFE = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
)


def _sanitize_filename(name: str) -> str:
    """Strip any character that isn't alnum/dot/underscore/dash.

    FASTQ filenames that hit this endpoint can legitimately contain
    dots (``sample_R1.fastq.gz``) but nothing more exotic. Anything else
    is collapsed to ``_`` so S3 keys stay predictable.
    """
    cleaned = "".join(ch if ch in _FILENAME_SAFE else "_" for ch in name)
    return cleaned.lstrip(".") or "unnamed"


# ─── Module-level singleton ────────────────────────────────────────────

_client: Storage | None = None


def get_storage() -> Storage:
    """Return a process-wide Storage singleton."""
    global _client
    if _client is None:
        _client = Storage()
    return _client
