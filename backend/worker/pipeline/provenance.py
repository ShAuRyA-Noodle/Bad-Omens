"""Stage 8: Ed25519-signed provenance manifest.

Every pipeline run produces a JSON manifest recording exactly how the result
was produced — input file hashes, tool versions, reference-database hashes,
all parameters, output file hashes — and a real **Ed25519 signature** over
the manifest's canonical (deterministic) content.

This is what makes Relict results reproducible and auditable:

- Attach the manifest to a paper as supplementary material.
- Re-run the pipeline with identical inputs and verify you get the same
  ``manifest_sha256`` (the hash covers only deterministic content — not
  wall-clock timestamps or runtimes; see :mod:`app.core.manifest`).
- Verify the Ed25519 signature against the public key served at
  ``GET /public-key`` (or the copy embedded in the manifest) to confirm the
  manifest was produced by this server and has not been tampered with.

The keypair is generated on first use and stored in the ``signing_keys``
table. The private key never leaves the server; the public key is served at
a public endpoint and embedded in every manifest so anyone can verify offline
(see ``backend/scripts/verify_manifest.py``).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core import signing as crypto
from app.core.manifest import (
    canonical_bytes,
    compute_manifest_hash,
    sha256_file,
    sha256_file_cached,
)

from worker import PIPELINE_VERSION, TOOL_VERSIONS
from worker.pipeline import StageResult, StageTimer, ensure_stage_dir

# Re-exported so callers can ``provenance_stage.sha256_file(...)`` without
# reaching into app.core directly.
__all__ = [
    "compute_manifest_hash",
    "generate_manifest",
    "run",
    "sha256_file",
    "sha256_file_cached",
]


def generate_manifest(
    *,
    job_id: str,
    input_files: list[dict[str, Any]],
    stage_results: list[dict[str, Any]],
    reference_dbs: list[dict[str, Any]],
    parameters: dict[str, Any],
    output_files: list[dict[str, Any]] | None = None,
    tool_versions: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build the provenance manifest dict (content only — unsigned).

    Pure function: no I/O, no signing. ``timestamp_utc`` is informational and
    is intentionally excluded from the canonical hash so the manifest stays
    reproducible across runs (see :mod:`app.core.manifest`).

    ``tool_versions`` should be the *detected* runtime versions
    (:func:`worker.tool_versions.detect_tool_versions`). When omitted (unit
    tests) it falls back to the pinned :data:`worker.TOOL_VERSIONS`. The pinned
    baseline is always recorded as ``tool_versions_expected`` so the manifest
    surfaces any drift between what was pinned and what actually ran.
    """
    detected = tool_versions if tool_versions is not None else TOOL_VERSIONS
    return {
        "schema_version": "1.0",
        "job_id": job_id,
        "timestamp_utc": datetime.now(tz=UTC).isoformat(),
        "pipeline": {
            "name": "Relict",
            "version": PIPELINE_VERSION,
            "tool_versions": detected,
            "tool_versions_expected": TOOL_VERSIONS,
        },
        "inputs": input_files,
        "parameters": parameters,
        "reference_databases": reference_dbs,
        "stages": stage_results,
        "outputs": output_files or [],
    }


def run(
    workspace: Path,
    *,
    job_id: str,
    input_files: list[dict[str, Any]],
    stage_results: list[dict[str, Any]],
    reference_dbs: list[dict[str, Any]],
    parameters: dict[str, Any],
    output_files: list[dict[str, Any]] | None = None,
    tool_versions: dict[str, str] | None = None,
    signing_private_key: bytes | None = None,
    logger: Any = None,
) -> StageResult:
    """Generate, sign, and write the provenance manifest.

    ``signing_private_key`` is the raw 32-byte Ed25519 private key from the
    ``signing_keys`` table. When provided, the manifest carries a real
    signature and the corresponding public key. It is only ``None`` in unit
    tests that exercise the unsigned path; the worker always supplies a key.
    """
    stage_dir = ensure_stage_dir(workspace, "provenance")
    manifest_path = stage_dir / "provenance.json"

    if logger:
        logger.info("provenance.started", signed=signing_private_key is not None)

    with StageTimer() as timer:
        manifest = generate_manifest(
            job_id=job_id,
            input_files=input_files,
            stage_results=stage_results,
            reference_dbs=reference_dbs,
            parameters=parameters,
            output_files=output_files,
            tool_versions=tool_versions,
        )

        # Hash + sign the canonical (deterministic) content, not the whole
        # dict — so wall-clock fields never enter the signed payload.
        canonical = canonical_bytes(manifest)
        manifest_hash = hashlib.sha256(canonical).hexdigest()
        manifest["manifest_sha256"] = manifest_hash

        if signing_private_key is not None:
            manifest["signature"] = crypto.sign(signing_private_key, canonical)
            manifest["public_key"] = {
                "algorithm": "ed25519",
                "key_b64": crypto.public_key_b64(crypto.public_from_private(signing_private_key)),
            }
        else:
            # Never relabel the hash as a signature. Unsigned means unsigned.
            manifest["signature"] = None
            manifest["public_key"] = None

        manifest["signed_at"] = datetime.now(tz=UTC).isoformat()
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    if logger:
        logger.info(
            "provenance.completed",
            manifest_sha256=manifest_hash[:16],
            signed=signing_private_key is not None,
            runtime=round(timer.elapsed, 3),
        )

    return StageResult(
        stage_name="provenance",
        tool="relict-provenance",
        tool_version=PIPELINE_VERSION,
        runtime_seconds=timer.elapsed,
        input_files=[],
        output_files=[str(manifest_path)],
        metrics={
            "manifest_sha256": manifest_hash,
            "signature": manifest["signature"],
            "signed": signing_private_key is not None,
            "schema_version": "1.0",
        },
    )
