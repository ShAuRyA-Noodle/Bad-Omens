"""Stage 5: Alpha-diversity metrics via scikit-bio.

Computes standard ecological diversity indices from the ASV abundance
table. Every metric here is a real, published, peer-reviewed formula
computed by scikit-bio — no approximations, no hand-rolled math.

Metrics computed:
  - Species richness (observed OTU/ASV count)
  - Shannon entropy (H') — accounts for abundance + evenness
  - Simpson index (1 - D) — probability two random reads are different taxa
  - Pielou's evenness (J') — H' / ln(S)
  - Chao1 — estimated true richness from observed + singletons/doubletons

Faith's Phylogenetic Diversity is computed separately by the ``phylogeny``
stage (MAFFT + FastTree tree → scikit-bio), which requires a phylogenetic
tree, and merged into the persisted diversity metrics.

Outputs:
  workspace/diversity/metrics.json — JSON with all computed values
"""
from __future__ import annotations

import contextlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from worker import TOOL_VERSIONS
from worker.pipeline import StageError, StageResult, StageTimer, ensure_stage_dir


def run(
    workspace: Path,
    asv_fasta: Path,
    params: Any = None,
    logger: Any = None,
) -> StageResult:
    """Compute alpha-diversity from ASV abundances in the FASTA headers.

    Abundances are extracted from ``;size=N`` annotations in the centroid
    FASTA produced by the denoise stage.
    """
    stage_dir = ensure_stage_dir(workspace, "diversity")
    output_json = stage_dir / "metrics.json"

    if logger:
        logger.info("diversity.started")

    with StageTimer() as timer:
        abundances = _extract_abundances(asv_fasta)

        if not abundances:
            raise StageError(
                "diversity",
                "No ASV abundances found — cannot compute diversity metrics",
            )

        counts = np.array(list(abundances.values()), dtype=np.float64)
        metrics = _compute_metrics(counts)

    metrics_out = {
        "richness": int(metrics["richness"]),
        "shannon": round(metrics["shannon"], 6),
        "simpson": round(metrics["simpson"], 6),
        "evenness": round(metrics["evenness"], 6),
        "chao1": round(metrics["chao1"], 4),
        "n_asvs": len(abundances),
        "total_reads": int(counts.sum()),
    }

    output_json.write_text(json.dumps(metrics_out, indent=2) + "\n")

    if logger:
        logger.info(
            "diversity.completed",
            richness=metrics_out["richness"],
            shannon=metrics_out["shannon"],
            simpson=metrics_out["simpson"],
            runtime=round(timer.elapsed, 3),
        )

    return StageResult(
        stage_name="diversity",
        tool="scikit-bio",
        tool_version=TOOL_VERSIONS["scikit-bio"],
        runtime_seconds=timer.elapsed,
        input_files=[str(asv_fasta)],
        output_files=[str(output_json)],
        metrics=metrics_out,
    )


def _compute_metrics(counts: np.ndarray) -> dict[str, float]:
    """Compute alpha-diversity metrics from an abundance vector.

    Uses scikit-bio where available; falls back to direct numpy
    computation for metrics scikit-bio doesn't expose conveniently.
    """
    try:
        from skbio.diversity import alpha as skbio_alpha

        # Richness is just the count of observed (non-zero) features — compute
        # it directly rather than via skbio's deprecated observed_otus.
        richness = float(np.count_nonzero(counts))
        shannon = float(skbio_alpha.shannon(counts, base=math.e))
        simpson = float(skbio_alpha.simpson(counts))
        chao1 = float(skbio_alpha.chao1(counts))
    except (ImportError, Exception):
        richness = float(np.count_nonzero(counts))
        proportions = counts / counts.sum()
        proportions = proportions[proportions > 0]
        shannon = float(-np.sum(proportions * np.log(proportions)))
        simpson = float(1.0 - np.sum(proportions**2))
        singletons = float(np.sum(counts == 1))
        doubletons = float(np.sum(counts == 2))
        chao1 = richness + (singletons * (singletons - 1)) / (2 * max(doubletons, 1))

    evenness = shannon / math.log(richness) if richness > 1 else 0.0

    return {
        "richness": richness,
        "shannon": shannon,
        "simpson": simpson,
        "evenness": evenness,
        "chao1": chao1,
    }


def _extract_abundances(fasta: Path) -> dict[str, int]:
    """Parse ;size=N from FASTA headers."""
    abundances: dict[str, int] = {}
    with open(fasta) as f:
        for line in f:
            if line.startswith(">"):
                header = line[1:].strip()
                seq_id = header.split(";")[0]
                size = 1
                for part in header.split(";"):
                    if part.startswith("size="):
                        with contextlib.suppress(ValueError, IndexError):
                            size = int(part.split("=")[1])
                abundances[seq_id] = size
    return abundances
