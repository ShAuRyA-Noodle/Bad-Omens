"""Stage 1: Quality control and adapter trimming via fastp.

Takes the raw uploaded FASTQ, runs fastp to:
  - Trim Illumina adapters (auto-detected)
  - Remove reads below a minimum quality threshold
  - Remove reads shorter than a minimum length
  - Generate a JSON report with QC statistics

Paired-end mode: when a reverse-reads file (R2) is supplied, fastp merges each
overlapping R1/R2 pair into a single, higher-quality consensus read
(``--merge``) after QC. Amplicon reads are expected to overlap, so only the
merged reads flow downstream; non-overlapping pairs are dropped (not written).
Single-end input skips merging entirely.

Outputs:
  workspace/qc/trimmed.fastq   — QC-passed reads (merged reads in paired mode)
  workspace/qc/fastp.json      — machine-readable QC report
  workspace/qc/fastp.html      — human-readable QC report
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from worker import TOOL_VERSIONS
from worker.pipeline import StageError, StageResult, StageTimer, ensure_stage_dir


@dataclass
class QCParams:
    """Parameters for the QC stage."""

    min_quality: int = 20
    min_length: int = 50
    max_length: int = 0            # 0 = no upper bound
    cut_front: bool = True
    cut_tail: bool = True
    cut_window_size: int = 4
    cut_mean_quality: int = 20
    threads: int = 2
    dedup: bool = False            # read-level deduplication (separate from vsearch derep)


def run(
    workspace: Path,
    input_fastq: Path,
    params: QCParams | None = None,
    logger: Any = None,
    input_fastq_r2: Path | None = None,
) -> StageResult:
    """Run fastp on ``input_fastq`` and write trimmed reads to ``workspace/qc/``.

    If ``input_fastq_r2`` is given, run in paired-end merge mode: fastp aligns
    the overlap of each R1/R2 pair and emits a single merged read per pair.
    """
    if params is None:
        params = QCParams()

    stage_dir = ensure_stage_dir(workspace, "qc")
    trimmed = stage_dir / "trimmed.fastq"
    report_json = stage_dir / "fastp.json"
    report_html = stage_dir / "fastp.html"

    paired = input_fastq_r2 is not None

    cmd = [
        "fastp",
        "--in1", str(input_fastq),
        "--json", str(report_json),
        "--html", str(report_html),
        "--qualified_quality_phred", str(params.min_quality),
        "--length_required", str(params.min_length),
        "--thread", str(params.threads),
        "--cut_window_size", str(params.cut_window_size),
        "--cut_mean_quality", str(params.cut_mean_quality),
    ]

    if paired:
        # Merge overlapping pairs into one consensus read; only merged reads are
        # kept (amplicon reads overlap). ``--merged_out`` is the downstream input.
        cmd.extend([
            "--in2", str(input_fastq_r2),
            "--merge",
            "--merged_out", str(trimmed),
        ])
    else:
        cmd.extend(["--out1", str(trimmed)])

    if params.max_length > 0:
        cmd.extend(["--length_limit", str(params.max_length)])
    if params.cut_front:
        cmd.append("--cut_front")
    if params.cut_tail:
        cmd.append("--cut_tail")
    if params.dedup:
        cmd.append("--dedup")

    if logger:
        logger.info("qc.started", cmd=" ".join(cmd), paired=paired)

    with StageTimer() as timer:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

    if result.returncode != 0:
        raise StageError(
            "qc",
            f"fastp exited with code {result.returncode}",
            stderr=result.stderr[-2000:],
        )

    if not trimmed.exists() or trimmed.stat().st_size == 0:
        raise StageError(
            "qc",
            "fastp produced no output — all reads may have been filtered out",
            stderr=result.stderr[-2000:],
        )

    metrics = _parse_fastp_json(report_json)
    metrics["paired_end"] = paired
    if logger:
        logger.info(
            "qc.completed",
            reads_before=metrics.get("reads_before_filtering"),
            reads_after=metrics.get("reads_after_filtering"),
            paired=paired,
            merged_reads=metrics.get("merged_reads"),
            runtime=round(timer.elapsed, 2),
        )

    input_files = [str(input_fastq)]
    if input_fastq_r2 is not None:
        input_files.append(str(input_fastq_r2))

    return StageResult(
        stage_name="qc",
        tool="fastp",
        tool_version=TOOL_VERSIONS["fastp"],
        runtime_seconds=timer.elapsed,
        input_files=input_files,
        output_files=[str(trimmed), str(report_json), str(report_html)],
        metrics=metrics,
    )


def _parse_fastp_json(path: Path) -> dict[str, Any]:
    """Extract key metrics from fastp's JSON report."""
    with open(path) as f:
        data = json.load(f)

    summary = data.get("summary", {})
    before = summary.get("before_filtering", {})
    after = summary.get("after_filtering", {})
    filtering = data.get("filtering_result", {})
    # Present only in paired merge runs; fastp records how many pairs merged.
    merged = data.get("merged_and_filtered", {})

    return {
        "merged_reads": merged.get("total_reads"),
        "reads_before_filtering": before.get("total_reads", 0),
        "reads_after_filtering": after.get("total_reads", 0),
        "bases_before_filtering": before.get("total_bases", 0),
        "bases_after_filtering": after.get("total_bases", 0),
        "q20_rate_before": before.get("q20_rate", 0),
        "q30_rate_before": before.get("q30_rate", 0),
        "q20_rate_after": after.get("q20_rate", 0),
        "q30_rate_after": after.get("q30_rate", 0),
        "gc_content_before": before.get("gc_content", 0),
        "gc_content_after": after.get("gc_content", 0),
        "passed_filter_reads": filtering.get("passed_filter_reads", 0),
        "low_quality_reads": filtering.get("low_quality_reads", 0),
        "too_short_reads": filtering.get("too_short_reads", 0),
        "too_many_N_reads": filtering.get("too_many_N_reads", 0),
    }
