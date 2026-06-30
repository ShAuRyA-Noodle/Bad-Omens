"""Stage 6: Dimensionality reduction + clustering via UMAP + HDBSCAN.

Computes a 2D embedding of the ASV abundance profile using UMAP
(McInnes et al. 2018), then clusters the embedded points using HDBSCAN
(Campello et al. 2013). The result is used for the interactive
scatter-plot visualization in Phase 6 and the ordination figures in
the research paper.

Input: the ASV centroid FASTA with ;size=N headers.
The k-mer frequency profile (k=5) of each ASV sequence is computed as
the feature vector for embedding.

Outputs:
  workspace/ordination/umap_coords.json    — 2D coordinates per ASV
  workspace/ordination/clusters.json       — cluster labels per ASV
  workspace/ordination/ordination.json     — combined output
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from worker import TOOL_VERSIONS
from worker.pipeline import StageResult, StageTimer, ensure_stage_dir

K = 5
UMAP_N_NEIGHBORS = 15
UMAP_MIN_DIST = 0.1
UMAP_METRIC = "euclidean"
UMAP_RANDOM_STATE = 42
HDBSCAN_MIN_CLUSTER_SIZE = 3
HDBSCAN_MIN_SAMPLES = 2


def run(
    workspace: Path,
    asv_fasta: Path,
    params: Any = None,
    logger: Any = None,
) -> StageResult:
    """Compute UMAP 2D embedding + HDBSCAN clusters from ASV k-mer profiles."""
    stage_dir = ensure_stage_dir(workspace, "ordination")
    output_json = stage_dir / "ordination.json"

    if logger:
        logger.info("ordination.started")

    with StageTimer() as timer:
        sequences = _read_fasta_sequences(asv_fasta)

        if len(sequences) < 3:
            if logger:
                logger.info("ordination.skipped", reason="fewer than 3 ASVs")
            result_data = {
                "skipped": True,
                "reason": "fewer than 3 ASVs — UMAP needs at least 3 data points",
                "n_asvs": len(sequences),
            }
            output_json.write_text(json.dumps(result_data, indent=2) + "\n")
            return StageResult(
                stage_name="ordination",
                tool="umap-learn+hdbscan",
                tool_version=f"umap={TOOL_VERSIONS['umap-learn']},hdbscan={TOOL_VERSIONS['hdbscan']}",
                runtime_seconds=timer.elapsed,
                input_files=[str(asv_fasta)],
                output_files=[str(output_json)],
                metrics={"skipped": True, "n_asvs": len(sequences)},
            )

        kmer_matrix = _build_kmer_matrix(sequences, k=K)

        import umap
        reducer = umap.UMAP(
            n_components=2,
            n_neighbors=min(UMAP_N_NEIGHBORS, len(sequences) - 1),
            min_dist=UMAP_MIN_DIST,
            metric=UMAP_METRIC,
            random_state=UMAP_RANDOM_STATE,
        )
        embedding = reducer.fit_transform(kmer_matrix)

        import hdbscan
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min(HDBSCAN_MIN_CLUSTER_SIZE, max(2, len(sequences) // 2)),
            min_samples=min(HDBSCAN_MIN_SAMPLES, len(sequences)),
            metric="euclidean",
        )
        labels = clusterer.fit_predict(embedding)

    seq_ids = list(sequences.keys())
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = int(np.sum(np.array(labels) == -1))

    result_data = {
        "n_asvs": len(sequences),
        "n_clusters": n_clusters,
        "n_noise_points": n_noise,
        "k": K,
        "umap_params": {
            "n_neighbors": min(UMAP_N_NEIGHBORS, len(sequences) - 1),
            "min_dist": UMAP_MIN_DIST,
            "metric": UMAP_METRIC,
            "random_state": UMAP_RANDOM_STATE,
        },
        "hdbscan_params": {
            "min_cluster_size": min(HDBSCAN_MIN_CLUSTER_SIZE, max(2, len(sequences) // 2)),
            "min_samples": min(HDBSCAN_MIN_SAMPLES, len(sequences)),
        },
        "points": [
            {
                "asv_id": seq_ids[i],
                "x": round(float(embedding[i, 0]), 6),
                "y": round(float(embedding[i, 1]), 6),
                "cluster": int(labels[i]),
            }
            for i in range(len(seq_ids))
        ],
    }

    output_json.write_text(json.dumps(result_data, indent=2) + "\n")

    if logger:
        logger.info(
            "ordination.completed",
            n_asvs=len(sequences),
            n_clusters=n_clusters,
            n_noise=n_noise,
            runtime=round(timer.elapsed, 3),
        )

    return StageResult(
        stage_name="ordination",
        tool="umap-learn+hdbscan",
        tool_version=f"umap={TOOL_VERSIONS['umap-learn']},hdbscan={TOOL_VERSIONS['hdbscan']}",
        runtime_seconds=timer.elapsed,
        input_files=[str(asv_fasta)],
        output_files=[str(output_json)],
        metrics={
            "n_asvs": len(sequences),
            "n_clusters": n_clusters,
            "n_noise_points": n_noise,
        },
    )


def _read_fasta_sequences(path: Path) -> dict[str, str]:
    """Parse a FASTA file into {id: sequence} dict."""
    seqs: dict[str, str] = {}
    current_id = ""
    current_seq: list[str] = []

    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith(">"):
                if current_id:
                    seqs[current_id] = "".join(current_seq)
                current_id = line[1:].split(";")[0].split()[0]
                current_seq = []
            elif current_id:
                current_seq.append(line.upper())

    if current_id:
        seqs[current_id] = "".join(current_seq)

    return seqs


def _build_kmer_matrix(sequences: dict[str, str], k: int = 5) -> np.ndarray:
    """Build a k-mer frequency matrix from DNA sequences.

    Each row is a sequence, each column is one of the 4^k possible k-mers.
    Values are normalized frequencies (sum to 1 per row).
    """
    bases = "ACGT"
    kmers = _generate_kmers(bases, k)
    kmer_to_idx = {km: i for i, km in enumerate(kmers)}
    n_kmers = len(kmers)

    matrix = np.zeros((len(sequences), n_kmers), dtype=np.float64)

    for row, seq in enumerate(sequences.values()):
        seq_clean = "".join(c for c in seq if c in bases)
        for i in range(len(seq_clean) - k + 1):
            kmer = seq_clean[i : i + k]
            if kmer in kmer_to_idx:
                matrix[row, kmer_to_idx[kmer]] += 1

        row_sum = matrix[row].sum()
        if row_sum > 0:
            matrix[row] /= row_sum

    return matrix


def _generate_kmers(bases: str, k: int) -> list[str]:
    """Generate all possible k-mers of given length."""
    if k == 0:
        return [""]
    shorter = _generate_kmers(bases, k - 1)
    return [base + km for base in bases for km in shorter]
