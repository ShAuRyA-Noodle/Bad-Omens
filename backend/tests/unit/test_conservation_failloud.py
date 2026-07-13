"""Unit tests for conservation fail-loud behavior.

The integrity hazard: when a GBIF/IUCN lookup fails (API down, rate-limited,
5xx), the species must be reported as *lookup failed*, never silently folded
into a clean "0 threatened" result. These tests pin that the stage surfaces
``lookup_failed_count`` / ``api_degraded`` and keeps the per-record error.
"""
from __future__ import annotations

import json

from worker.pipeline import conservation as cons


class _StubSettings:
    IUCN_REDLIST_TOKEN = None


def _write_taxonomy(tmp_path):
    tsv = tmp_path / "taxonomy.tsv"
    tsv.write_text(
        "asv_id\tgenus\tspecies\n"
        "A1\tTor\tputitora\n"
        "A2\tCyprinus\tcarpio\n"
    )
    return tsv


def test_failed_lookup_is_reported_not_hidden(tmp_path, monkeypatch) -> None:
    tsv = _write_taxonomy(tmp_path)

    def fake_lookup(name: str, *, iucn_token=None, kingdom_hint=None, logger=None) -> cons.ConservationRecord:
        rec = cons.ConservationRecord(species=name)
        if name == "Tor putitora":
            rec.error = "GBIF error: 503 Service Unavailable"  # lookup genuinely failed
        else:
            rec.gbif_key = 123
            rec.iucn_category = "LC"  # assessed, not threatened
        return rec

    monkeypatch.setattr(cons, "get_settings", lambda: _StubSettings())
    monkeypatch.setattr(cons, "_lookup_species", fake_lookup)
    monkeypatch.setattr(cons.time, "sleep", lambda *_: None)

    result = cons.run(tmp_path, tsv, logger=None)

    # The failure is surfaced, not swallowed.
    assert result.metrics["lookup_failed_count"] == 1
    assert result.metrics["api_degraded"] is True
    # And 0-threatened is NOT presented as authoritative on its own.
    assert result.metrics["threatened_count"] == 0

    data = json.loads((tmp_path / "conservation" / "conservation.json").read_text())
    assert data["lookup_failed_count"] == 1
    assert data["api_degraded"] is True
    assert any(r.get("error") for r in data["records"])


def test_clean_run_is_not_flagged_degraded(tmp_path, monkeypatch) -> None:
    tsv = _write_taxonomy(tmp_path)

    def fake_lookup(name: str, *, iucn_token=None, kingdom_hint=None, logger=None) -> cons.ConservationRecord:
        rec = cons.ConservationRecord(species=name)
        rec.gbif_key = 1
        rec.iucn_category = "EN" if name == "Tor putitora" else "LC"
        return rec

    monkeypatch.setattr(cons, "get_settings", lambda: _StubSettings())
    monkeypatch.setattr(cons, "_lookup_species", fake_lookup)
    monkeypatch.setattr(cons.time, "sleep", lambda *_: None)

    result = cons.run(tmp_path, tsv, logger=None)

    assert result.metrics["lookup_failed_count"] == 0
    assert result.metrics["api_degraded"] is False
    assert result.metrics["threatened_count"] == 1  # the EN species
