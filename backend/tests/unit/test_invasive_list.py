"""Unit tests for the GRIIS/GISD invasive-list loader + flagging.

Pure filesystem/string logic — no network, runs everywhere.
"""
from __future__ import annotations

from pathlib import Path

from worker.pipeline.conservation import (
    ConservationRecord,
    _canonical_binomial,
    _flag_invasive,
    _load_invasive_set,
)


def test_canonical_binomial_takes_first_two_tokens_lowercased() -> None:
    assert _canonical_binomial("Pterygoplichthys pardalis (Castelnau, 1855)") == "pterygoplichthys pardalis"
    assert _canonical_binomial("  Lantana   camara  ") == "lantana camara"
    assert _canonical_binomial("Genus") == "genus"


def test_load_absent_directory_returns_empty(tmp_path: Path) -> None:
    names, source = _load_invasive_set.__wrapped__(str(tmp_path))  # bypass lru_cache
    assert names == frozenset()
    assert source is None


def test_load_griis_csv(tmp_path: Path) -> None:
    inv = tmp_path / "invasive"
    inv.mkdir()
    (inv / "griis_india.csv").write_text(
        "scientificName,canonicalName,establishmentMeans\n"
        "Lantana camara L.,Lantana camara,introduced\n"
        "Pterygoplichthys pardalis (Castelnau),Pterygoplichthys pardalis,introduced\n"
    )
    names, source = _load_invasive_set.__wrapped__(str(tmp_path))
    assert source == "griis_india.csv"
    assert "lantana camara" in names
    assert "pterygoplichthys pardalis" in names


def test_load_plain_species_list(tmp_path: Path) -> None:
    inv = tmp_path / "invasive"
    inv.mkdir()
    (inv / "gisd.txt").write_text("# header comment\nLantana camara\nEichhornia crassipes\n")
    names, source = _load_invasive_set.__wrapped__(str(tmp_path))
    assert source == "gisd.txt"
    assert "lantana camara" in names
    assert "eichhornia crassipes" in names


def test_flag_invasive_matches_species_and_gbif_name() -> None:
    invasive = frozenset({"lantana camara"})
    r1 = ConservationRecord(species="Lantana camara")
    _flag_invasive(r1, invasive)
    assert r1.is_invasive is True

    r2 = ConservationRecord(species="Some name", gbif_matched_name="Lantana camara")
    _flag_invasive(r2, invasive)
    assert r2.is_invasive is True

    r3 = ConservationRecord(species="Panthera tigris")
    _flag_invasive(r3, invasive)
    assert r3.is_invasive is False
