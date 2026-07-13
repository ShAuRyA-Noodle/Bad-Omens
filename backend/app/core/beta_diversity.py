"""Cross-sample beta-diversity: Bray-Curtis dissimilarity + PCoA.

Real multi-sample ordination — the scientifically-correct answer to comparing
communities across samples (unlike a single-sample UMAP of one sample's ASVs,
which is not a community ordination). Bray-Curtis is the standard abundance-
based dissimilarity for metabarcoding; PCoA (principal coordinates analysis,
Gower 1966) embeds the distance matrix into Euclidean space via classical
multidimensional scaling.

Pure numpy so it can run in the API process and be unit-tested in isolation.
"""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def bray_curtis_matrix(counts: NDArray[np.float64]) -> NDArray[np.float64]:
    """Pairwise Bray-Curtis dissimilarity for a (n_samples, n_features) matrix.

    BC(i, j) = sum(|x_i - x_j|) / sum(x_i + x_j), in [0, 1]. Two samples with no
    shared abundance -> 1; identical -> 0.
    """
    n = counts.shape[0]
    dist = np.zeros((n, n), dtype=np.float64)
    for i in range(n):
        for j in range(i + 1, n):
            denom = float((counts[i] + counts[j]).sum())
            d = float(np.abs(counts[i] - counts[j]).sum() / denom) if denom > 0 else 0.0
            dist[i, j] = dist[j, i] = d
    return dist


def pcoa(distances: NDArray[np.float64], n_components: int = 3) -> tuple[NDArray[np.float64], list[float]]:
    """Classical MDS / PCoA of a symmetric distance matrix.

    Returns (coordinates [n_samples x k], proportion_explained [k]) where k =
    min(n_components, n_samples). Negative eigenvalues (from a non-Euclidean
    distance) are clipped to zero, per the standard PCoA convention.
    """
    n = distances.shape[0]
    k = max(1, min(n_components, n))

    d2 = distances ** 2
    centering = np.eye(n) - np.ones((n, n)) / n
    gram = -0.5 * centering @ d2 @ centering  # double-centered Gram matrix

    eigvals, eigvecs = np.linalg.eigh(gram)
    order = np.argsort(eigvals)[::-1]
    eigvals = eigvals[order]
    eigvecs = eigvecs[:, order]

    top_vals = np.clip(eigvals[:k], 0.0, None)
    coords = eigvecs[:, :k] * np.sqrt(top_vals)

    positive_total = float(np.clip(eigvals, 0.0, None).sum())
    proportions = (
        [float(v / positive_total) for v in top_vals] if positive_total > 0 else [0.0] * k
    )
    return coords, proportions


__all__ = ["bray_curtis_matrix", "pcoa"]
