"""Unit tests for the sampling-adequacy (Good's coverage) stage.

The size parser is pure; the full stage needs vsearch and is skipped when the
binary is absent (runs for real in the worker image).
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from worker.pipeline import coverage

_HAS_VSEARCH = shutil.which("vsearch") is not None


def test_read_sizes_parses_size_annotation(tmp_path: Path) -> None:
    fasta = tmp_path / "u.fasta"
    fasta.write_text(">a;size=5\nACGT\n>b;size=1\nTTTT\n>c;size=1\nGGGG\n")
    assert sorted(coverage._read_sizes(fasta)) == [1, 1, 5]


def test_read_sizes_missing_file_is_empty(tmp_path: Path) -> None:
    assert coverage._read_sizes(tmp_path / "nope.fasta") == []


@pytest.mark.skipif(not _HAS_VSEARCH, reason="vsearch not installed")
def test_goods_coverage_on_reads(tmp_path: Path) -> None:
    # 3 identical copies of one sequence + 1 unique singleton => N=4, F1=1.
    # Good's coverage = 1 - 1/4 = 0.75.
    reads = tmp_path / "reads.fastq"
    common = "ACGTACGTACGTACGTACGTACGTACGTACGT"
    uniq = "TTTTAAAACCCCGGGGTTTTAAAACCCCGGGG"
    q = "I" * len(common)
    lines = []
    for i in range(3):
        lines.append(f"@c{i}\n{common}\n+\n{q}\n")
    lines.append(f"@u0\n{uniq}\n+\n{q}\n")
    reads.write_text("".join(lines))

    result = coverage.run(tmp_path, reads, logger=None)
    m = result.metrics
    assert m["n_reads"] == 4
    assert m["n_singletons"] == 1
    assert m["goods_coverage"] == pytest.approx(0.75)
