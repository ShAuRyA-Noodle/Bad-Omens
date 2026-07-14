"""Stage 2b: Sampling adequacy via Good's coverage.

Answers "was this sample sequenced deeply enough to have seen most of what's
there?" — the sampling-adequacy signal the EII needs. It is computed on the
QC + primer-trimmed reads by a *full* dereplication that KEEPS singletons
(unlike the ASV-inference dereplication, which drops them with
``--minuniquesize 2``). That singleton information is exactly what Good's
estimator needs, so this runs as its own pass and never perturbs ASV calling.

Good's coverage:  C = 1 − F1 / N
  F1 = number of sequences observed exactly once (singletons)
  N  = total reads
C → 1 means nearly every read represents an already-seen sequence (well
sampled); a large singleton fraction means many taxa were seen once and more
sequencing would likely reveal more (under-sampled).

Outputs:
  workspace/coverage/full_uniques.fasta — every unique sequence with ;size=N
  workspace/coverage/coverage.json      — {goods_coverage, n_reads, ...}
"""
from __future__ import annotations

import contextlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from worker import TOOL_VERSIONS
from worker.pipeline import StageError, StageResult, StageTimer, ensure_stage_dir


@dataclass
class CoverageParams:
    threads: int = 2


def run(
    workspace: Path,
    input_fastq: Path,
    params: CoverageParams | None = None,
    logger: Any = None,
) -> StageResult:
    """Compute Good's coverage from a singleton-preserving dereplication."""
    if params is None:
        params = CoverageParams()

    stage_dir = ensure_stage_dir(workspace, "coverage")
    full_uniques = stage_dir / "full_uniques.fasta"
    output_json = stage_dir / "coverage.json"

    # Full dereplication — no --minuniquesize, so singletons are retained.
    cmd = [
        "vsearch",
        "--fastx_uniques", str(input_fastq),
        "--fastaout", str(full_uniques),
        "--sizeout",
        "--threads", str(params.threads),
        "--fasta_width", "0",
    ]

    if logger:
        logger.info("coverage.started", cmd=" ".join(cmd))

    with StageTimer() as timer:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            raise StageError(
                "coverage",
                f"vsearch --fastx_uniques exited with code {result.returncode}",
                stderr=result.stderr[-2000:],
            )

        sizes = _read_sizes(full_uniques)
        n_reads = sum(sizes)
        n_unique = len(sizes)
        n_singletons = sum(1 for s in sizes if s == 1)
        n_doubletons = sum(1 for s in sizes if s == 2)

        goods_coverage = (1.0 - n_singletons / n_reads) if n_reads > 0 else None

    metrics = {
        "goods_coverage": round(goods_coverage, 6) if goods_coverage is not None else None,
        "n_reads": n_reads,
        "n_unique": n_unique,
        "n_singletons": n_singletons,
        "n_doubletons": n_doubletons,
    }
    output_json.write_text(json.dumps(metrics, indent=2) + "\n")

    if logger:
        logger.info(
            "coverage.completed",
            goods_coverage=metrics["goods_coverage"],
            n_reads=n_reads,
            n_singletons=n_singletons,
            runtime=round(timer.elapsed, 3),
        )

    return StageResult(
        stage_name="coverage",
        tool="vsearch",
        tool_version=TOOL_VERSIONS["vsearch"],
        runtime_seconds=timer.elapsed,
        input_files=[str(input_fastq)],
        output_files=[str(output_json)],
        metrics=metrics,
    )


def _read_sizes(fasta: Path) -> list[int]:
    """Extract the ;size=N abundances from a dereplicated FASTA's headers."""
    sizes: list[int] = []
    if not fasta.exists():
        return sizes
    with open(fasta) as f:
        for line in f:
            if line.startswith(">"):
                size = 1
                for part in line[1:].strip().split(";"):
                    if part.startswith("size="):
                        with contextlib.suppress(ValueError, IndexError):
                            size = int(part.split("=")[1])
                sizes.append(size)
    return sizes
