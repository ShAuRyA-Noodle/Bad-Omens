"""Unit tests for canonical (deterministic) manifest hashing.

The headline reproducibility guarantee is: two runs with identical inputs and
parameters produce the same ``manifest_sha256``. That can only hold if the
hash ignores wall-clock timestamps, per-stage runtimes, and the random
job-id-bearing absolute paths. These tests pin that behaviour, plus the
sign/verify integration over the canonical bytes.
"""
from __future__ import annotations

import copy

from app.core import manifest as manifest_core
from app.core import signing as crypto


def _manifest(*, timestamp: str, runtime: float, job_id: str) -> dict:
    """A manifest whose deterministic content is fixed but whose volatile
    fields (timestamp, runtime, absolute paths) vary by argument."""
    return {
        "schema_version": "1.0",
        "job_id": job_id,
        "timestamp_utc": timestamp,
        "pipeline": {"name": "Relict", "version": "0.2.0", "tool_versions": {"vsearch": "2.28.1"}},
        "inputs": [{"filename": "sample_R1.fastq.gz", "sha256": "a" * 64, "size_bytes": 1234}],
        "parameters": {"amplicon": "16S_V4"},
        "reference_databases": [{"name": "SILVA_138.1", "path": f"/data/{job_id}/silva.udb", "sha256": "b" * 64}],
        "stages": [
            {
                "stage": "qc",
                "tool": "fastp",
                "tool_version": "0.24.0",
                "runtime_seconds": runtime,
                "input_files": [f"/workspaces/{job_id}/raw.fastq"],
                "output_files": [f"/workspaces/{job_id}/qc/trimmed.fastq"],
                "metrics": {"reads_after_filtering": 42000},
            },
        ],
        "outputs": [{"filename": f"/workspaces/{job_id}/qc/trimmed.fastq", "sha256": "c" * 64}],
    }


def test_hash_ignores_timestamp_runtime_and_paths() -> None:
    a = _manifest(timestamp="2026-06-30T10:00:00Z", runtime=12.5, job_id="job-aaaa")
    b = _manifest(timestamp="2026-06-30T23:59:59Z", runtime=88.1, job_id="job-bbbb")

    # Same deterministic content, different volatile fields → identical hash.
    assert manifest_core.compute_manifest_hash(a) == manifest_core.compute_manifest_hash(b)


def test_hash_changes_when_input_hash_changes() -> None:
    a = _manifest(timestamp="t", runtime=1.0, job_id="j")
    b = copy.deepcopy(a)
    b["inputs"][0]["sha256"] = "d" * 64

    assert manifest_core.compute_manifest_hash(a) != manifest_core.compute_manifest_hash(b)


def test_hash_changes_when_output_hash_changes() -> None:
    a = _manifest(timestamp="t", runtime=1.0, job_id="j")
    b = copy.deepcopy(a)
    b["outputs"][0]["sha256"] = "e" * 64

    assert manifest_core.compute_manifest_hash(a) != manifest_core.compute_manifest_hash(b)


def test_hash_changes_when_stage_metric_changes() -> None:
    a = _manifest(timestamp="t", runtime=1.0, job_id="j")
    b = copy.deepcopy(a)
    b["stages"][0]["metrics"]["reads_after_filtering"] = 9999

    assert manifest_core.compute_manifest_hash(a) != manifest_core.compute_manifest_hash(b)


def test_canonical_bytes_are_order_independent() -> None:
    a = _manifest(timestamp="t", runtime=1.0, job_id="j")
    a["inputs"].append({"filename": "sample_R2.fastq.gz", "sha256": "f" * 64, "size_bytes": 5})
    b = copy.deepcopy(a)
    b["inputs"].reverse()  # same set, different order

    assert manifest_core.compute_manifest_hash(a) == manifest_core.compute_manifest_hash(b)


def test_sign_and_verify_canonical_manifest() -> None:
    private, public = crypto.generate_keypair()
    m = _manifest(timestamp="t", runtime=1.0, job_id="j")

    canonical = manifest_core.canonical_bytes(m)
    signature = crypto.sign(private, canonical)

    # A verifier reconstructs the canonical bytes from the stored manifest.
    assert crypto.verify(public, manifest_core.canonical_bytes(m), signature) is True

    # Tampering with signed content invalidates the signature.
    tampered = copy.deepcopy(m)
    tampered["inputs"][0]["sha256"] = "0" * 64
    assert crypto.verify(public, manifest_core.canonical_bytes(tampered), signature) is False
