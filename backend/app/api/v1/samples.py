"""Sample routes — upload, inspect, delete."""
from __future__ import annotations

import uuid  # noqa: TC003 — FastAPI uses this for path param introspection
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request, UploadFile, status

from app.api.deps import CurrentUser, SessionDep
from app.core.config import get_settings
from app.schemas.samples import SamplePublic, SampleUploadResponse
from app.services import samples as samples_service
from app.services.storage import get_storage

router = APIRouter(prefix="/samples", tags=["samples"])


@router.post(
    "/upload",
    response_model=SampleUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a FASTQ / FASTA file and create a queued job",
)
async def upload_sample(
    request: Request,
    file: UploadFile,
    user: CurrentUser,
    session: SessionDep,
) -> SampleUploadResponse:
    if file.filename is None or file.filename.strip() == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload must include a filename",
        )

    # Cheap early reject: refuse an obviously-oversized request by its declared
    # Content-Length before reading the body at all. The authoritative limit is
    # still enforced mid-stream in the service (the header can be spoofed).
    max_upload = get_settings().MAX_UPLOAD_BYTES
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared = int(content_length)
        except ValueError:
            declared = 0
        if declared > max_upload + (1 << 20):  # 1 MiB slack for multipart overhead
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Upload too large (declared {declared} bytes, max {max_upload})",
            )

    try:
        _job, sample, _stored = await samples_service.upload_sample(
            session,
            user=user,
            filename=file.filename,
            stream=file.file,
            content_type=file.content_type or "application/octet-stream",
        )
    except samples_service.UnsupportedSampleFormat as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        ) from exc
    except samples_service.EmptySample as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except samples_service.SampleTooLarge as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        ) from exc
    except samples_service.TooManyActiveJobs as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        ) from exc

    storage = get_storage()
    url = storage.presigned_get_url(sample.s3_key, expires=timedelta(minutes=15))

    return SampleUploadResponse(
        sample=SamplePublic.model_validate(sample),
        download_url=url,
    )


@router.get(
    "/{sample_id}",
    response_model=SamplePublic,
    summary="Return a sample owned by the caller",
)
async def get_sample(
    sample_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> SamplePublic:
    sample = await samples_service.get_sample_for_user(
        session, sample_id=sample_id, user=user
    )
    if sample is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sample not found",
        )
    return SamplePublic.model_validate(sample)


@router.get(
    "/{sample_id}/download-url",
    summary="Return a fresh 15-minute pre-signed download URL",
)
async def presigned_download(
    sample_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> dict[str, str]:
    sample = await samples_service.get_sample_for_user(
        session, sample_id=sample_id, user=user
    )
    if sample is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sample not found",
        )
    url = get_storage().presigned_get_url(sample.s3_key, expires=timedelta(minutes=15))
    return {"download_url": url}
