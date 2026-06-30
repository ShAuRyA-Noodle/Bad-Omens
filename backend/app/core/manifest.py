"""Canonical, deterministic provenance-manifest hashing.

Shared by the worker (which builds and signs manifests) and the API (which
verifies them at ``/provenance/verify``). Lives in ``app.core`` — not in the
worker package — so the API never has to import the bioinformatics worker.

Why a *canonical* payload rather than hashing the whole manifest:

The stored manifest carries fields that legitimately vary between two
otherwise-identical runs — a wall-clock ``timestamp_utc``, per-stage
``runtime_seconds``, and absolute workspace paths containing the random
job id. Hashing those would make the documented guarantee — *two runs with
identical inputs and parameters produce identical ``manifest_sha256``* —
mathematically impossible.

:func:`canonical_payload` therefore projects the manifest down to only the
content that is reproducible by construction: the schema version, pipeline +
tool versions, input file hashes, parameters, reference-DB hashes, per-stage
tool/metrics, and output file hashes (by basename, not absolute path). Lists
are sorted by a stable key so element order can't change the hash. The SHA256
of this payload is what gets signed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

# Top-level manifest keys deliberately excluded from the signed payload
# because they are non-deterministic across otherwise-identical runs.
VOLATILE_KEYS = frozenset({"manifest_sha256", "signature", "signed_at", "timestamp_utc"})


def _basename(path: str) -> str:
    """Return the final path component, tolerating both / and \\ separators."""
    if not path:
        return ""
    return PureWindowsPath(PurePosixPath(path).name).name


def canonical_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    """Project a manifest to its deterministic, signable content."""
    pipeline = manifest.get("pipeline") or {}

    inputs = sorted(
        (
            {
                "filename": _basename(str(i.get("filename", ""))),
                "sha256": i.get("sha256"),
                "size_bytes": i.get("size_bytes"),
            }
            for i in manifest.get("inputs", []) or []
        ),
        key=lambda d: (d["filename"], d["sha256"] or ""),
    )

    references = sorted(
        (
            {"name": r.get("name"), "sha256": r.get("sha256")}
            for r in manifest.get("reference_databases", []) or []
        ),
        key=lambda d: (d["name"] or "", d["sha256"] or ""),
    )

    stages = sorted(
        (
            {
                "stage": s.get("stage"),
                "tool": s.get("tool"),
                "tool_version": s.get("tool_version"),
                "metrics": s.get("metrics", {}),
            }
            for s in manifest.get("stages", []) or []
        ),
        key=lambda d: str(d["stage"]),
    )

    outputs = sorted(
        (
            {"filename": _basename(str(o.get("filename", ""))), "sha256": o.get("sha256")}
            for o in manifest.get("outputs", []) or []
        ),
        key=lambda d: (d["filename"], d["sha256"] or ""),
    )

    return {
        "schema_version": manifest.get("schema_version"),
        "pipeline": {
            "name": pipeline.get("name"),
            "version": pipeline.get("version"),
            "tool_versions": pipeline.get("tool_versions", {}),
        },
        "inputs": inputs,
        "parameters": manifest.get("parameters", {}),
        "reference_databases": references,
        "stages": stages,
        "outputs": outputs,
    }


def canonical_bytes(manifest: dict[str, Any]) -> bytes:
    """Deterministic UTF-8 JSON encoding of the canonical payload."""
    payload = canonical_payload(manifest)
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_manifest_hash(manifest: dict[str, Any]) -> str:
    """SHA256 (hex) of the canonical payload — the value that gets signed."""
    return hashlib.sha256(canonical_bytes(manifest)).hexdigest()


def sha256_file(path: Any, chunk_size: int = 8 * 1024 * 1024) -> str:
    """Stream a file through SHA256 without loading it into memory."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def sha256_file_cached(path: Any) -> str:
    """SHA256 of a (possibly multi-GB) file, cached in a ``<name>.sha256`` sidecar.

    Reference databases are large and immutable once downloaded, so re-hashing
    them on every job is wasteful. We compute the digest once and store it next
    to the file; subsequent runs reuse it as long as the sidecar is at least as
    new as the file it describes. This lets the manifest record a real
    reference-DB hash for *every* DB regardless of size — replacing the old
    "skipped-large-file" placeholder.
    """
    from pathlib import Path

    p = Path(path)
    sidecar = p.with_name(p.name + ".sha256")
    try:
        if sidecar.exists() and sidecar.stat().st_mtime >= p.stat().st_mtime:
            cached = sidecar.read_text().split()[0].strip()
            if len(cached) == 64:
                return cached
    except OSError:
        pass

    digest = sha256_file(p)
    try:
        sidecar.write_text(digest + "\n")
    except OSError:
        pass
    return digest


__all__ = [
    "VOLATILE_KEYS",
    "canonical_bytes",
    "canonical_payload",
    "compute_manifest_hash",
    "sha256_file",
    "sha256_file_cached",
]
