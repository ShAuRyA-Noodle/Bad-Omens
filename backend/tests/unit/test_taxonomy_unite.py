"""Unit tests for UNITE (fungal ITS) reference-header parsing.

UNITE headers have no whitespace and encode the lineage with Greengenes-style
rank prefixes after the last '|':
  >Genus_species|ACC|SH…|reps|k__Fungi;p__…;g__Genus;s__Genus_species
These tests pin that parsing and confirm SILVA/MIDORI headers are untouched.
"""
from __future__ import annotations

from pathlib import Path

from worker.pipeline.taxonomy import (
    _clean_rank_value,
    _extract_lineage_from_target,
    _index_ref_headers,
)

_UNITE = (
    ">Gyroporus_purpurinus|KX389110|SH0879786.10FU|reps|"
    "k__Fungi;p__Basidiomycota;c__Agaricomycetes;o__Boletales;"
    "f__Gyroporaceae;g__Gyroporus;s__Gyroporus_purpurinus\n"
    "ACGTACGTACGT\n"
)
_SILVA = ">AB001234.1.1520 Bacteria;Proteobacteria;Gammaproteobacteria\nACGT\n"


def test_clean_rank_value_strips_prefix_and_underscores() -> None:
    assert _clean_rank_value("k__Fungi") == "Fungi"
    assert _clean_rank_value("s__Gyroporus_purpurinus") == "Gyroporus purpurinus"
    # non-prefixed (SILVA/MIDORI) values are returned unchanged
    assert _clean_rank_value("Bacteria") == "Bacteria"
    assert _clean_rank_value("Gammaproteobacteria") == "Gammaproteobacteria"


def test_unite_header_lineage(tmp_path: Path) -> None:
    fasta = tmp_path / "unite.fasta"
    fasta.write_text(_UNITE)
    idx = _index_ref_headers(fasta)
    target = next(iter(idx))  # the full header (no whitespace)
    lineage = _extract_lineage_from_target(target, fasta)
    assert lineage == [
        "Fungi", "Basidiomycota", "Agaricomycetes", "Boletales",
        "Gyroporaceae", "Gyroporus", "purpurinus",  # species reduced to epithet
    ]


def test_silva_header_unaffected(tmp_path: Path) -> None:
    fasta = tmp_path / "silva.fasta"
    fasta.write_text(_SILVA)
    # SILVA accession is the first whitespace token; _extract_lineage_from_target
    # indexes the FASTA on first call.
    lineage = _extract_lineage_from_target("AB001234.1.1520", fasta)
    assert lineage == ["Bacteria", "Proteobacteria", "Gammaproteobacteria"]
