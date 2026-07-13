"""Unit tests for amplicon-marker capture + strict reference-DB resolution.

The critical correctness fix (V-01/BIO-05/BIO-10): a marker must resolve only
to a database appropriate for that gene. SILVA (small-subunit rRNA) is valid
for 16S/18S ONLY — it must never be substituted for COI/12S/ITS2/rbcL, and an
unknown/unmapped marker must never silently fall through to 16S.
"""
from __future__ import annotations

import pytest


def test_detect_reference_db_is_strict(tmp_path, monkeypatch) -> None:
    from worker.pipeline import run_job

    silva = tmp_path / "silva"
    silva.mkdir()
    (silva / "SILVA_138.1_SSURef_NR99_tax_silva.fasta").write_text(">x\nACGT\n")
    monkeypatch.setattr(run_job, "_references_root", lambda: tmp_path)

    # SILVA present -> 16S/18S resolve to it.
    assert run_job._detect_reference_db("16S_V4") is not None
    assert run_job._detect_reference_db("18S_V9") is not None

    # SILVA must NEVER be used for these markers, and no wrong-DB substitution:
    assert run_job._detect_reference_db("COI_Leray") is None
    assert run_job._detect_reference_db("12S_MiFish") is None
    assert run_job._detect_reference_db("rbcL") is None
    assert run_job._detect_reference_db("ITS2") is None
    # An unmapped marker must not fall through to 16S.
    assert run_job._detect_reference_db("other") is None


def test_parse_amplicon() -> None:
    from app.db.models import Amplicon
    from app.services import samples

    assert samples._parse_amplicon("12S_MiFish") is Amplicon.MARKER_12S_MIFISH
    assert samples._parse_amplicon("16S_V4") is Amplicon.MARKER_16S_V4
    with pytest.raises(samples.InvalidAmplicon):
        samples._parse_amplicon("not_a_marker")
