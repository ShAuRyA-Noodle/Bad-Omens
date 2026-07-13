"""Unit tests for primer-trim helpers (IUPAC reverse-complement + primer table)."""
from __future__ import annotations

from worker.pipeline.primer_trim import PRIMERS, reverse_complement

_MARKERS = ("16S_V4", "18S_V9", "12S_MiFish", "COI_Leray", "ITS2", "rbcL")


def test_reverse_complement_basic() -> None:
    assert reverse_complement("ACGT") == "ACGT"
    assert reverse_complement("AAAA") == "TTTT"
    assert reverse_complement("GGGG") == "CCCC"


def test_reverse_complement_iupac() -> None:
    assert reverse_complement("R") == "Y"  # R=A/G <-> Y=C/T
    assert reverse_complement("Y") == "R"
    assert reverse_complement("K") == "M"
    assert reverse_complement("M") == "K"
    assert reverse_complement("N") == "N"
    assert reverse_complement("S") == "S"
    assert reverse_complement("W") == "W"


def test_reverse_complement_is_involution() -> None:
    # revcomp(revcomp(x)) == x for every real primer (proves the map is correct).
    for fwd, rev in PRIMERS.values():
        assert reverse_complement(reverse_complement(fwd)) == fwd
        assert reverse_complement(reverse_complement(rev)) == rev


def test_all_markers_have_nonempty_primers() -> None:
    for marker in _MARKERS:
        assert marker in PRIMERS
        fwd, rev = PRIMERS[marker]
        assert fwd and rev
        # only IUPAC nucleotide codes
        assert set(fwd) <= set("ACGTRYSWKMBDHVN")
        assert set(rev) <= set("ACGTRYSWKMBDHVN")
