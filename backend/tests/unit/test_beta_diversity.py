"""Unit tests for cross-sample Bray-Curtis + PCoA (M6)."""
from __future__ import annotations

import numpy as np
from app.core.beta_diversity import bray_curtis_matrix, pcoa


def test_bray_curtis_identical_is_zero() -> None:
    m = np.array([[10.0, 0.0, 5.0], [10.0, 0.0, 5.0]])
    d = bray_curtis_matrix(m)
    assert d[0, 1] == 0.0
    assert d[1, 0] == 0.0


def test_bray_curtis_disjoint_is_one() -> None:
    m = np.array([[10.0, 0.0], [0.0, 10.0]])
    d = bray_curtis_matrix(m)
    assert abs(d[0, 1] - 1.0) < 1e-9


def test_bray_curtis_known_value() -> None:
    # |1-0|+|1-1|+|0-1| = 2 ; sum = 4 ; BC = 0.5
    m = np.array([[1.0, 1.0, 0.0], [0.0, 1.0, 1.0]])
    d = bray_curtis_matrix(m)
    assert abs(d[0, 1] - 0.5) < 1e-9


def test_bray_curtis_symmetric_zero_diagonal() -> None:
    m = np.array([[3.0, 1.0], [1.0, 4.0], [0.0, 2.0]])
    d = bray_curtis_matrix(m)
    assert np.allclose(d, d.T)
    assert np.allclose(np.diag(d), 0.0)


def test_pcoa_recovers_grouping() -> None:
    # Two pairs of identical samples -> pairs coincide, groups separate on PC1.
    m = np.array([[10.0, 0.0], [10.0, 0.0], [0.0, 10.0], [0.0, 10.0]])
    coords, proportions = pcoa(bray_curtis_matrix(m), n_components=2)
    assert coords.shape[0] == 4
    assert np.allclose(coords[0], coords[1], atol=1e-6)
    assert np.allclose(coords[2], coords[3], atol=1e-6)
    assert abs(coords[0, 0] - coords[2, 0]) > 1e-3
    assert proportions[0] > 0
