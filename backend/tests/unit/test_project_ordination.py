"""Unit tests for project-ordination helpers.

The full UniFrac compute needs a DB + mafft/fasttree and is exercised by the
live end-to-end validation; here we lock down the pure JSON sanitizer that
keeps non-finite floats out of the JSONB column (Postgres rejects Inf/NaN).
"""
from __future__ import annotations

import math

from worker.project_ordination import _json_safe


def test_json_safe_replaces_infinity_and_nan() -> None:
    assert _json_safe(math.inf) is None
    assert _json_safe(-math.inf) is None
    assert _json_safe(math.nan) is None


def test_json_safe_keeps_finite_values() -> None:
    assert _json_safe(1.5) == 1.5
    assert _json_safe(0.0) == 0.0
    assert _json_safe(-3) == -3
    assert _json_safe("locality") == "locality"
    assert _json_safe(None) is None


def test_json_safe_recurses_into_containers() -> None:
    payload = {
        "pseudo_f": math.inf,
        "p_value": 0.04,
        "points": [{"pc1": 1.0, "pc2": math.nan}, {"pc1": -1.0, "pc2": 2.0}],
        "proportion_explained": [1.0, math.inf, 0.0],
    }
    out = _json_safe(payload)
    assert out["pseudo_f"] is None
    assert out["p_value"] == 0.04
    assert out["points"][0]["pc2"] is None
    assert out["points"][1]["pc2"] == 2.0
    assert out["proportion_explained"] == [1.0, None, 0.0]
