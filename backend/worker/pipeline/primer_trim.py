"""Stage 1b: per-marker primer trimming with cutadapt.

Runs between QC and dereplication. Amplicon primers must be removed before
denoising/taxonomy — left on, they corrupt dereplication and skew identity
scores. cutadapt was pinned and version-reported but never actually
invoked (the manifest claimed a tool that never ran); this stage makes it real.

Primers are chosen by the sample's amplicon marker. Trimming is **lenient by
default** (``--discard-untrimmed`` off): the forward primer is removed from the
5' end and the reverse-complement of the reverse primer from the 3' end where
present, but reads without a detectable primer are kept rather than dropped —
so a run whose reads are already primer-trimmed is never silently emptied. An
unknown marker is a no-op passthrough.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from worker import TOOL_VERSIONS
from worker.pipeline import StageError, StageResult, StageTimer, ensure_stage_dir

# (forward, reverse) primer per marker. IUPAC ambiguity codes are fine for
# cutadapt; inosine (I) in the classic jgHCO2198 COI primer is written as N.
PRIMERS: dict[str, tuple[str, str]] = {
    "16S_V4": ("GTGYCAGCMGCCGCGGTAA", "GGACTACNVGGGTWTCTAAT"),                    # 515F / 806R
    "18S_V9": ("GTACACACCGCCCGTC", "TGATCCTTCTGCAGGTTCACCTAC"),                   # 1391F / EukBr
    "12S_MiFish": ("GTCGGTAAAACTCGTGCCAGC", "CATAGTGGGGTATCTAATCCCAGTTTG"),       # MiFish-U F/R
    "COI_Leray": ("GGWACWGGWTGAACWGTWTAYCCYCC", "TANACYTCNGGRTGNCCRAARAAYCA"),    # mlCOIintF / jgHCO2198
    "ITS2": ("GTGARTCATCGAATCTTTG", "TCCTCCGCTTATTGATATGC"),                      # fITS7 / ITS4
    "rbcL": ("ATGTCACCACAAACAGAGACTAAAGC", "GTAAAATCAAGTCCACCRCG"),               # rbcLa-F / rbcLa-R
}

# IUPAC-aware complement (A<->T, C<->G, R<->Y, K<->M, B<->V, D<->H, S/W/N self).
_COMPLEMENT = str.maketrans("ACGTRYSWKMBDHVNacgtryswkmbdhvn", "TGCAYRSWMKVHDBNtgcayrswmkvhdbn")


def reverse_complement(seq: str) -> str:
    """Reverse-complement a nucleotide string, preserving IUPAC codes."""
    return seq.translate(_COMPLEMENT)[::-1]


@dataclass
class PrimerTrimParams:
    discard_untrimmed: bool = False  # lenient by default (see module docstring)
    error_rate: float = 0.15         # cutadapt -e; primers are short + degenerate
    threads: int = 2


def run(
    workspace: Path,
    input_fastq: Path,
    marker: str,
    params: PrimerTrimParams | None = None,
    logger: Any = None,
) -> StageResult:
    """Trim the marker's primers from ``input_fastq`` with cutadapt."""
    if params is None:
        params = PrimerTrimParams()

    stage_dir = ensure_stage_dir(workspace, "primer_trim")
    out_fastq = stage_dir / "primer_trimmed.fastq"

    primers = PRIMERS.get(marker)
    if primers is None:
        # Unknown marker -> passthrough (no primers to trim), so the pipeline
        # still runs. Never fabricate a trim.
        shutil.copyfile(input_fastq, out_fastq)
        if logger:
            logger.info("primer_trim.skipped", reason=f"no primers for marker {marker}")
        return StageResult(
            stage_name="primer_trim",
            tool="cutadapt",
            tool_version=TOOL_VERSIONS.get("cutadapt", "unknown"),
            runtime_seconds=0.0,
            input_files=[str(input_fastq)],
            output_files=[str(out_fastq)],
            metrics={"skipped": True, "marker": marker},
        )

    fwd, rev = primers
    rev_rc = reverse_complement(rev)
    cmd = [
        "cutadapt",
        "-g", fwd,          # forward primer at 5'
        "-a", rev_rc,       # reverse-complement of reverse primer at 3'
        "-e", str(params.error_rate),
        "-j", str(params.threads),
        "-o", str(out_fastq),
        str(input_fastq),
    ]
    if params.discard_untrimmed:
        cmd.append("--discard-untrimmed")

    if logger:
        logger.info("primer_trim.started", marker=marker, cmd=" ".join(cmd))

    with StageTimer() as timer:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

    if result.returncode != 0:
        raise StageError(
            "primer_trim",
            f"cutadapt failed (code {result.returncode})",
            stderr=result.stderr[-2000:],
        )
    if not out_fastq.exists() or out_fastq.stat().st_size == 0:
        raise StageError(
            "primer_trim",
            "Primer trimming produced no reads — the primers may not match this marker, "
            "or the reads were empty after QC.",
        )

    reads_out = _count_fastq_reads(out_fastq)
    if logger:
        logger.info("primer_trim.completed", marker=marker, reads_out=reads_out, runtime=round(timer.elapsed, 2))

    return StageResult(
        stage_name="primer_trim",
        tool="cutadapt",
        tool_version=TOOL_VERSIONS.get("cutadapt", "unknown"),
        runtime_seconds=timer.elapsed,
        input_files=[str(input_fastq)],
        output_files=[str(out_fastq)],
        metrics={
            "skipped": False,
            "marker": marker,
            "forward_primer": fwd,
            "reverse_primer": rev,
            "reads_after_trimming": reads_out,
            "discard_untrimmed": params.discard_untrimmed,
        },
    )


def _count_fastq_reads(path: Path) -> int:
    lines = 0
    with open(path) as f:
        for _ in f:
            lines += 1
    return lines // 4
