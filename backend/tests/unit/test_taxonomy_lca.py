"""Unit tests for LCA consensus + per-rank identity gating (taxonomy V-03).

Proves the pipeline no longer reports a full 7-rank species from a single
low-identity best hit: near-tie hits collapse to their common ancestor, and the
lineage is truncated to the deepest rank the identity actually supports.
"""
from __future__ import annotations

from worker.pipeline.taxonomy import _gate_by_identity, _lca_lineage

_FULL = ["Animalia", "Chordata", "Actinopteri", "Cypriniformes", "Cyprinidae", "Tor", "Tor putitora"]


def test_lca_identical_lineages_kept_whole() -> None:
    assert _lca_lineage([_FULL, _FULL]) == _FULL


def test_lca_diverging_genus_collapses_to_family() -> None:
    a = _FULL
    b = ["Animalia", "Chordata", "Actinopteri", "Cypriniformes", "Cyprinidae", "Labeo", "Labeo rohita"]
    assert _lca_lineage([a, b]) == ["Animalia", "Chordata", "Actinopteri", "Cypriniformes", "Cyprinidae"]


def test_lca_diverging_phylum_collapses_to_kingdom() -> None:
    a = ["Animalia", "Chordata", "Actinopteri"]
    b = ["Animalia", "Arthropoda", "Insecta"]
    assert _lca_lineage([a, b]) == ["Animalia"]


def test_lca_empty() -> None:
    assert _lca_lineage([]) == []


def test_gate_high_identity_keeps_species() -> None:
    assert _gate_by_identity(_FULL, 99.0) == _FULL


def test_gate_90pct_truncates_to_family() -> None:
    # species needs 97, genus 95 -> dropped; family needs 90 -> kept.
    assert _gate_by_identity(_FULL, 90.0) == _FULL[:5]


def test_gate_96pct_keeps_genus_not_species() -> None:
    assert _gate_by_identity(_FULL, 96.0) == _FULL[:6]


def test_gate_low_identity_kingdom_only() -> None:
    # phylum needs 75; 72 supports only kingdom (>=70).
    assert _gate_by_identity(_FULL, 72.0) == ["Animalia"]
