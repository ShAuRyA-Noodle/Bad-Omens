"""Unit tests for bounded, memory-safe uploads (SEC-01).

put_stream must reject an oversized stream *during* the read — before the
whole thing is buffered and before anything is written to object storage — so
a large upload cannot exhaust the API's memory.
"""
from __future__ import annotations

import io

import pytest
from app.services.storage import FileTooLarge, Storage


def _bare_storage() -> Storage:
    # Bypass __init__ so no MinIO client / settings are needed: the size
    # checks raise before any storage call is reached.
    return Storage.__new__(Storage)


def test_put_stream_rejects_oversized_before_touching_storage() -> None:
    storage = _bare_storage()
    stream = io.BytesIO(b"A" * 5000)
    with pytest.raises(FileTooLarge):
        storage.put_stream(key="k", stream=stream, max_bytes=1000)


def test_put_stream_rejects_empty_upload() -> None:
    storage = _bare_storage()
    stream = io.BytesIO(b"")
    with pytest.raises(ValueError, match="empty"):
        storage.put_stream(key="k", stream=stream, max_bytes=1000)
