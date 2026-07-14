"""Unit tests for paired-end QC (fastp R1/R2 merge).

The merge path needs the fastp binary and is skipped when it is absent
(API image / Windows); it runs for real inside the worker image.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from worker.pipeline import qc

_HAS_FASTP = shutil.which("fastp") is not None

_RC = {"A": "T", "T": "A", "G": "C", "C": "G", "N": "N"}


def _rc(s: str) -> str:
    return "".join(_RC[c] for c in reversed(s))


def _body(seed: int, n: int = 250) -> str:
    out = []
    x = seed * 2654435761 & 0xFFFFFFFF
    for _ in range(n):
        x = (1103515245 * x + 12345) & 0xFFFFFFFF
        out.append("ACGT"[(x >> 16) & 3])
    return "".join(out)


def _write_pair(ws: Path, read_len: int = 180) -> tuple[Path, Path, int]:
    """Write overlapping R1/R2 for 4 pseudo-species; return (r1, r2, amplicon_len)."""
    fwd, revp = "GTGCCAGCAGCCGCGGTAA", "ATTAGATACCCTGGTAGTCC"
    r1, r2 = ws / "R1.fastq", ws / "R2.fastq"
    amp_len = 0
    with open(r1, "w") as f1, open(r2, "w") as f2:
        for sp in range(4):
            amp = fwd + _body(sp + 1) + revp
            amp_len = len(amp)
            read1, read2 = amp[:read_len], _rc(amp[-read_len:])
            for c in range(120):
                f1.write(f"@sp{sp}_{c}/1\n{read1}\n+\n{'I' * len(read1)}\n")
                f2.write(f"@sp{sp}_{c}/2\n{read2}\n+\n{'I' * len(read2)}\n")
    return r1, r2, amp_len


@pytest.mark.skipif(not _HAS_FASTP, reason="fastp not installed")
def test_paired_merge_reconstructs_amplicon(tmp_path: Path) -> None:
    r1, r2, amp_len = _write_pair(tmp_path)
    result = qc.run(tmp_path, r1, logger=None, input_fastq_r2=r2)

    assert result.metrics["paired_end"] is True
    assert result.metrics["merged_reads"] == 480  # every overlapping pair merges
    # both mates are recorded as inputs (covered by the manifest)
    assert str(r2) in result.input_files

    merged = Path(result.output_files[0])
    lines = merged.read_text().splitlines()
    seqs = [lines[i + 1] for i in range(0, len(lines), 4)]
    assert len(seqs) == 480
    # merged read spans the full overlap -> full amplicon length
    assert len(seqs[0]) == amp_len


@pytest.mark.skipif(not _HAS_FASTP, reason="fastp not installed")
def test_single_end_still_works(tmp_path: Path) -> None:
    r1, _r2, _amp = _write_pair(tmp_path)
    result = qc.run(tmp_path, r1, logger=None)  # no R2 -> single-end
    assert result.metrics["paired_end"] is False
    assert result.input_files == [str(r1)]
