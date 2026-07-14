"""Sample service — upload raw FASTQ, persist metadata, link to a job."""
from __future__ import annotations

from datetime import UTC
from typing import TYPE_CHECKING, Any, BinaryIO

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import Amplicon, Job, JobStatus, Sample, User
from app.services.jobs import enqueue_job
from app.services.queue import publish_job_event
from app.services.storage import FileTooLarge, StoredObject, get_storage

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

log = get_logger(__name__)


class SampleError(Exception):
    """Base class for sample-service errors."""


class UnsupportedSampleFormat(SampleError):
    pass


class EmptySample(SampleError):
    pass


class SampleTooLarge(SampleError):
    pass


class TooManyActiveJobs(SampleError):
    pass


class InvalidAmplicon(SampleError):
    pass


# ─── Validation ─────────────────────────────────────────────────────────


def _parse_amplicon(value: str) -> Amplicon:
    """Validate the caller-supplied marker against the supported set.

    The marker drives reference-DB selection, the GBIF kingdom hint, and the
    DwC-A target_gene — so an unknown value must be rejected, not silently
    defaulted to 16S (which is how every non-16S job was mis-aligned before).
    """
    try:
        return Amplicon(value)
    except ValueError as exc:
        supported = ", ".join(m.value for m in Amplicon if m is not Amplicon.OTHER)
        raise InvalidAmplicon(f"Unknown amplicon marker '{value}'. Supported: {supported}") from exc


_DWC_STRING_KEYS = ("eventDate", "locality", "recordedBy", "habitat", "waterBody", "country")


def _clean_metadata(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Whitelist + validate Darwin Core sample metadata from the client.

    Coordinates are coerced to float and range-checked; string fields are
    trimmed and length-capped. Anything invalid or unknown is dropped, so the
    stored dwc_metadata is always clean and safe to emit into a DwC-A.
    """
    if not raw:
        return {}
    out: dict[str, Any] = {}
    for key, lo, hi in (("decimalLatitude", -90.0, 90.0), ("decimalLongitude", -180.0, 180.0)):
        val = raw.get(key)
        if val is None or str(val).strip() == "":
            continue
        try:
            num = float(val)
        except (TypeError, ValueError):
            continue
        if lo <= num <= hi:
            out[key] = num
    for key in _DWC_STRING_KEYS:
        val = raw.get(key)
        if isinstance(val, str) and val.strip():
            out[key] = val.strip()[:500]
    return out


def _check_filename(filename: str) -> None:
    settings = get_settings()
    lower = filename.lower()
    if not any(lower.endswith(suffix) for suffix in settings.ALLOWED_UPLOAD_SUFFIXES):
        allowed = ", ".join(settings.ALLOWED_UPLOAD_SUFFIXES)
        msg = f"Unsupported file extension. Allowed: {allowed}"
        raise UnsupportedSampleFormat(msg)


# ─── Orchestration ──────────────────────────────────────────────────────


async def upload_sample(
    session: AsyncSession,
    *,
    user: User,
    filename: str,
    stream: BinaryIO,
    content_type: str,
    amplicon: str,
    metadata: dict[str, Any] | None = None,
    filename_r2: str | None = None,
    stream_r2: BinaryIO | None = None,
    content_type_r2: str | None = None,
) -> tuple[Job, Sample, StoredObject]:
    """Create a job + sample row and stream the bytes to object storage.

    A new Job is created in the ``queued`` state for every upload so
    that each upload is independently trackable. In Phase 1f the job
    is enqueued to RQ; for now the Job row exists but nothing will pop
    it until the worker is wired up.

    ``filename_r2`` / ``stream_r2`` are the optional reverse-reads (R2) mate for
    paired-end input; when present it is stored alongside R1 and the QC stage
    merges the pair.
    """
    _check_filename(filename)
    paired = stream_r2 is not None and filename_r2 is not None
    if paired:
        _check_filename(filename_r2)  # type: ignore[arg-type]  # guarded by `paired`
    marker = _parse_amplicon(amplicon)
    settings = get_settings()

    # Per-user concurrency cap: one account cannot flood the worker queue.
    active_jobs = await session.scalar(
        select(func.count())
        .select_from(Job)
        .where(
            Job.user_id == user.id,
            Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
        )
    )
    if active_jobs is not None and active_jobs >= settings.MAX_CONCURRENT_JOBS_PER_USER:
        msg = (
            f"You already have {active_jobs} job(s) queued or running "
            f"(limit {settings.MAX_CONCURRENT_JOBS_PER_USER}). "
            "Wait for one to finish before uploading another."
        )
        raise TooManyActiveJobs(msg)

    job = Job(user_id=user.id, status=JobStatus.QUEUED, amplicon=marker)
    session.add(job)
    await session.flush()  # populate job.id for the S3 key

    storage = get_storage()
    key = storage.build_sample_key(user_id=user.id, job_id=job.id, filename=filename)

    try:
        # The limit is enforced *inside* put_stream, mid-read, so an oversized
        # upload never gets fully buffered or written to storage.
        stored = storage.put_stream(
            key=key,
            stream=stream,
            content_type=content_type or "application/octet-stream",
            max_bytes=settings.MAX_UPLOAD_BYTES,
        )
    except FileTooLarge as exc:
        msg = f"Upload exceeds the maximum of {settings.MAX_UPLOAD_BYTES} bytes"
        raise SampleTooLarge(msg) from exc
    except ValueError as exc:
        # put_stream refuses zero-byte uploads.
        raise EmptySample("Uploaded file was empty") from exc

    # Optional R2 mate — stored under its own key; failures roll back the whole
    # upload (the R1 object is left, but the job/sample rows are never committed
    # without a complete pair, so a half-written pair can't be processed).
    stored_r2: StoredObject | None = None
    if paired:
        key_r2 = storage.build_sample_key(user_id=user.id, job_id=job.id, filename=filename_r2)  # type: ignore[arg-type]
        try:
            stored_r2 = storage.put_stream(
                key=key_r2,
                stream=stream_r2,  # type: ignore[arg-type]  # guarded by `paired`
                content_type=content_type_r2 or "application/octet-stream",
                max_bytes=settings.MAX_UPLOAD_BYTES,
            )
        except FileTooLarge as exc:
            msg = f"R2 upload exceeds the maximum of {settings.MAX_UPLOAD_BYTES} bytes"
            raise SampleTooLarge(msg) from exc
        except ValueError as exc:
            raise EmptySample("Uploaded R2 file was empty") from exc

    sample = Sample(
        job_id=job.id,
        filename=filename,
        s3_key=stored.key,
        sha256=stored.sha256,
        size_bytes=stored.size_bytes,
        content_type=stored.content_type,
        filename_r2=filename_r2 if paired else None,
        s3_key_r2=stored_r2.key if stored_r2 else None,
        sha256_r2=stored_r2.sha256 if stored_r2 else None,
        size_bytes_r2=stored_r2.size_bytes if stored_r2 else None,
        dwc_metadata=_clean_metadata(metadata),
    )
    session.add(sample)
    await session.flush()

    log.info(
        "sample.uploaded",
        user_id=str(user.id),
        job_id=str(job.id),
        sample_id=str(sample.id),
        size_bytes=sample.size_bytes,
        sha256=sample.sha256,
    )

    # Enqueue the Phase 1 no-op pipeline so /ws/jobs/{id} sees events.
    from datetime import datetime

    await enqueue_job(session, job=job)
    job.queued_at = datetime.now(tz=UTC)
    await publish_job_event(
        job.id,
        {
            "kind": "job.queued",
            "message": "Upload received; job waiting for worker",
            "progress": 0.0,
        },
    )

    return job, sample, stored


async def get_sample_for_user(
    session: AsyncSession,
    *,
    sample_id: uuid.UUID,
    user: User,
) -> Sample | None:
    """Return the sample iff it belongs to ``user``."""
    sample = await session.get(Sample, sample_id)
    if sample is None:
        return None
    # Walk via the parent job's user_id so we never leak another user's
    # rows.
    job = await session.get(Job, sample.job_id)
    if job is None or job.user_id != user.id:
        return None
    return sample
