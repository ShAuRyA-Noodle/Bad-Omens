"""Unit tests for the Ecosystem Integrity Index (worker.pipeline.integrity_index).

Expected scores are hand-computed from the published methodology
(docs/methods/eii.md) so a change in the formula breaks a test on purpose.
"""
from __future__ import annotations

import math

import pytest
from worker.pipeline import integrity_index as eii


def test_grade_band_boundaries() -> None:
    assert eii.grade_for(97) == "A+"
    assert eii.grade_for(96.99) == "A"
    assert eii.grade_for(60) == "D-"
    assert eii.grade_for(59.99) == "F"


def test_weights_sum_to_one() -> None:
    assert math.isclose(sum(eii.WEIGHTS.values()), 1.0, abs_tol=1e-9)


def test_balanced_least_concern_sample() -> None:
    # evenness=1.0, all-LC health=1.0, distinctness=mean rarity(1000)≈0.4999.
    records = [
        {"species": f"sp{i}", "iucn_category": "LC", "gbif_occurrence_count": 1000}
        for i in range(5)
    ]
    result = eii.compute_eii(
        richness=5, shannon=math.log(5), evenness=1.0,
        conservation_records=records, api_degraded=False,
    )
    # assessed = evenness(0.20) + health(0.25) + distinctness(0.20) = 0.65
    assert result.assessed_weight == pytest.approx(0.65)
    rarity_1000 = 1 - math.log10(1001) / math.log10(1_000_001)
    expected = 100 * (0.20 * 1.0 + 0.25 * 1.0 + 0.20 * rarity_1000) / 0.65
    assert result.score == pytest.approx(round(expected, 2), abs=0.01)
    assert result.grade == "B"
    by_key = {c.key: c for c in result.components}
    assert by_key["invasive_pressure"].available is False
    assert by_key["sampling_adequacy"].available is False


def test_degraded_conservation_excludes_health() -> None:
    records = [{"species": "x", "iucn_category": "EN"}]  # would be threatening
    result = eii.compute_eii(
        richness=3, shannon=math.log(3), evenness=1.0,
        conservation_records=records, api_degraded=True,
    )
    by_key = {c.key: c for c in result.components}
    # Health is NOT assessed on a degraded lookup — never a confident score.
    assert by_key["conservation_health"].available is False
    assert "degraded" in by_key["conservation_health"].detail
    # Only evenness remains assessable here (no occurrence counts present).
    assert result.assessed_weight == pytest.approx(0.20)
    assert result.score == pytest.approx(100.0)


def test_critically_endangered_lowers_score() -> None:
    records = [{"species": "rare", "iucn_category": "CR", "gbif_occurrence_count": 10}]
    result = eii.compute_eii(
        richness=2, shannon=None, evenness=0.5,
        conservation_records=records, api_degraded=False,
    )
    rarity_10 = 1 - math.log10(11) / math.log10(1_000_001)
    expected = 100 * (0.20 * 0.5 + 0.25 * 0.0 + 0.20 * rarity_10) / 0.65
    assert result.score == pytest.approx(round(expected, 2), abs=0.01)
    assert result.grade == "F"  # a CR-dominated sample flags low


def test_nothing_assessable_returns_null() -> None:
    result = eii.compute_eii(
        richness=1, shannon=None, evenness=None,
        conservation_records=[], api_degraded=False,
    )
    assert result.score is None
    assert result.grade is None
    assert result.assessed_weight == 0.0


def test_invasive_pressure_assessed_when_list_loaded() -> None:
    # 1 of 2 screened species is invasive -> pressure sub-score = 1 - 1/2 = 0.5.
    records = [
        {"species": "Native one", "iucn_category": "LC", "gbif_occurrence_count": 1000, "is_invasive": False},
        {"species": "Invasive two", "iucn_category": "LC", "gbif_occurrence_count": 1000, "is_invasive": True},
    ]
    result = eii.compute_eii(
        richness=5, shannon=math.log(5), evenness=1.0,
        conservation_records=records, api_degraded=False, invasive_list_loaded=True,
    )
    by_key = {c.key: c for c in result.components}
    assert by_key["invasive_pressure"].available is True
    assert by_key["invasive_pressure"].value == pytest.approx(0.5)
    # invasive weight (0.15) now counts toward the denominator.
    assert result.assessed_weight == pytest.approx(0.20 + 0.25 + 0.20 + 0.15)


def test_invasive_pressure_unavailable_without_list() -> None:
    records = [{"species": "x", "iucn_category": "LC", "gbif_occurrence_count": 1000, "is_invasive": False}]
    result = eii.compute_eii(
        richness=5, shannon=math.log(5), evenness=1.0,
        conservation_records=records, api_degraded=False, invasive_list_loaded=False,
    )
    by_key = {c.key: c for c in result.components}
    assert by_key["invasive_pressure"].available is False
    assert "no invasive checklist" in by_key["invasive_pressure"].detail


def test_deterministic() -> None:
    records = [{"species": "a", "iucn_category": "VU", "gbif_occurrence_count": 500}]
    a = eii.compute_eii(
        richness=4, shannon=math.log(4), evenness=0.9,
        conservation_records=records, api_degraded=False,
    )
    b = eii.compute_eii(
        richness=4, shannon=math.log(4), evenness=0.9,
        conservation_records=records, api_degraded=False,
    )
    assert a.to_dict() == b.to_dict()
