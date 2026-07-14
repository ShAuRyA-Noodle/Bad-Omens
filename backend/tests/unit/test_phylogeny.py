"""Unit tests for the phylogeny stage (MAFFT + FastTree → Faith's PD).

The pure-Python paths (FASTA parsing, the <3-tips guard) run everywhere.
The full alignment→tree→PD path needs the mafft + fasttree binaries and is
skipped automatically when they are absent (i.e. on the API image / Windows);
it runs for real inside the worker image.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from worker.pipeline import StageError
from worker.pipeline import phylogeny as phylo

_HAS_TOOLS = shutil.which("mafft") is not None and (
    shutil.which("fasttree") is not None or shutil.which("FastTree") is not None
)

# Four short, deliberately divergent 16S-like sequences: two similar pairs so
# the tree has real internal structure (non-trivial branch lengths).
_ASVS = {
    "Asv1": ("ACGTACGTACGTACGTACGTACGTACGTACGTACGTACGT", 100),
    "Asv2": ("ACGTACGTACGTACGTTCGTACGTACGTACGTACGTACGT", 80),
    "Asv3": ("TTGGCCAATTGGCCAATTGGCCAATTGGCCAATTGGCCAA", 60),
    "Asv4": ("TTGGCCAATTGGCCAATAGGCCAATTGGCCAATTGGCCAA", 40),
}


def _write_fasta(path: Path, seqs: dict[str, tuple[str, int]]) -> None:
    with open(path, "w") as fh:
        for sid, (seq, size) in seqs.items():
            fh.write(f">{sid};size={size}\n{seq}\n")


def test_read_fasta_strips_size_and_orders(tmp_path: Path) -> None:
    fasta = tmp_path / "asvs.fasta"
    _write_fasta(fasta, _ASVS)
    parsed = phylo._read_fasta(fasta)
    assert list(parsed.keys()) == ["Asv1", "Asv2", "Asv3", "Asv4"]
    assert parsed["Asv1"] == (_ASVS["Asv1"][0], 100)


def test_too_few_tips_returns_null_faith_pd(tmp_path: Path) -> None:
    """Fewer than 3 ASVs → faith_pd is None with a recorded reason, never faked."""
    fasta = tmp_path / "asvs.fasta"
    _write_fasta(fasta, {k: _ASVS[k] for k in ("Asv1", "Asv2")})
    result = phylo.run(tmp_path, fasta)
    assert result.metrics["faith_pd"] is None
    assert result.metrics["n_tips"] == 2
    assert "at least" in result.metrics["note"]
    out = json.loads((tmp_path / "phylogeny" / "phylo.json").read_text())
    assert out["faith_pd"] is None


@pytest.mark.skipif(not _HAS_TOOLS, reason="mafft/fasttree not installed")
def test_real_faith_pd_is_positive(tmp_path: Path) -> None:
    fasta = tmp_path / "asvs.fasta"
    _write_fasta(fasta, _ASVS)
    result = phylo.run(tmp_path, fasta)

    faith = result.metrics["faith_pd"]
    assert faith is not None
    assert faith > 0.0  # a real tree over divergent seqs has positive total branch length
    assert result.metrics["n_tips"] == 4

    # tree + MSA were actually written and the tree is valid Newick
    tree_path = tmp_path / "phylogeny" / "tree.nwk"
    assert tree_path.exists() and tree_path.stat().st_size > 0
    newick = tree_path.read_text()
    assert newick.strip().endswith(";")
    for sid in _ASVS:
        assert sid in newick  # every ASV is a tip


@pytest.mark.skipif(not _HAS_TOOLS, reason="mafft/fasttree not installed")
def test_faith_pd_deterministic(tmp_path: Path) -> None:
    """Same input → same PD (FastTree is deterministic for a fixed alignment)."""
    f1, f2 = tmp_path / "a.fasta", tmp_path / "b.fasta"
    _write_fasta(f1, _ASVS)
    _write_fasta(f2, _ASVS)
    w1, w2 = tmp_path / "w1", tmp_path / "w2"
    w1.mkdir()
    w2.mkdir()
    r1 = phylo.run(w1, f1)
    r2 = phylo.run(w2, f2)
    assert r1.metrics["faith_pd"] == pytest.approx(r2.metrics["faith_pd"])


def test_missing_binary_raises_stage_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing tool must raise StageError (surfaced + logged), not fake a value."""
    monkeypatch.setattr(phylo.shutil, "which", lambda _name: None)
    fasta = tmp_path / "asvs.fasta"
    _write_fasta(fasta, _ASVS)
    with pytest.raises(StageError):
        phylo.run(tmp_path, fasta)
