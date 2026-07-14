"""Stage 5b: Phylogenetic placement + Faith's Phylogenetic Diversity.

Builds a de-novo phylogenetic tree from the sample's ASVs and computes
Faith's PD — the total branch length of the tree spanning every observed
ASV. Unlike the abundance-only alpha metrics (Shannon/Simpson), Faith's PD
rewards a sample for containing *evolutionarily distinct* lineages, not just
many equally-abundant ones. It is the standard phylogenetic alpha-diversity
index (Faith, 1992, Biol. Conserv. 61:1-10).

This stage is what makes the ``diversity_metrics.faith_pd`` column real —
previously it was declared but never written (always NULL).

Pipeline:
  1. Emit a clean FASTA of ASV sequences (IDs stripped of ``;size=`` so the
     tree tip labels match the abundance vector exactly).
  2. Multiple-sequence alignment with MAFFT (``--auto`` picks the algorithm
     by input size).
  3. Approximate-maximum-likelihood tree with FastTree (GTR+CAT, nucleotide).
  4. Faith's PD via scikit-bio against the ASV abundance vector.

Outputs:
  workspace/phylogeny/aligned.fasta — the MSA
  workspace/phylogeny/tree.nwk      — the Newick tree (hashed into the manifest)
  workspace/phylogeny/phylo.json    — {faith_pd, n_tips, tree_newick}

A tree needs at least 3 tips to be meaningful; with fewer ASVs the stage
returns ``faith_pd = None`` and records the reason — it never fabricates a
value.
"""
from __future__ import annotations

import contextlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from worker import TOOL_VERSIONS
from worker.pipeline import StageError, StageResult, StageTimer, ensure_stage_dir

# A phylogenetic tree needs a minimum number of tips before Faith's PD carries
# any signal. FastTree can technically build a tree from 2 leaves, but the
# resulting PD is a trivial single edge. Require 3.
_MIN_TIPS = 3


@dataclass
class PhylogenyParams:
    """Parameters for the phylogeny stage."""

    # MAFFT is run single-threaded on purpose: multi-threaded MAFFT reorders
    # parallel work and yields slightly different alignments run-to-run, which
    # would make the tree — and Faith's PD, and the manifest hash of tree.nwk —
    # non-reproducible. Reproducibility is a core guarantee of this platform, so
    # we trade a little speed (ASV counts are modest) for a deterministic result.
    # FastTree (the single-threaded build, not FastTreeMP) is already deterministic.
    threads: int = 1


def run(
    workspace: Path,
    asv_fasta: Path,
    params: PhylogenyParams | None = None,
    logger: Any = None,
) -> StageResult:
    """Align ASVs, build a tree, compute Faith's PD."""
    if params is None:
        params = PhylogenyParams()

    stage_dir = ensure_stage_dir(workspace, "phylogeny")
    clean_fasta = stage_dir / "asvs_clean.fasta"
    aligned_fasta = stage_dir / "aligned.fasta"
    tree_path = stage_dir / "tree.nwk"
    output_json = stage_dir / "phylo.json"

    if logger:
        logger.info("phylogeny.started")

    with StageTimer() as timer:
        seqs = _read_fasta(asv_fasta)
        n_tips = len(seqs)

        if n_tips < _MIN_TIPS:
            reason = (
                f"Only {n_tips} ASV(s); a phylogenetic tree needs at least "
                f"{_MIN_TIPS} tips. Faith's PD not computed."
            )
            if logger:
                logger.info("phylogeny.skipped", reason=reason, n_tips=n_tips)
            _write_json(output_json, faith_pd=None, n_tips=n_tips, tree_newick=None, note=reason)
            return StageResult(
                stage_name="phylogeny",
                tool="mafft+fasttree",
                tool_version=_tool_version_string(),
                runtime_seconds=timer.elapsed,
                input_files=[str(asv_fasta)],
                output_files=[str(output_json)],
                metrics={"faith_pd": None, "n_tips": n_tips, "note": reason},
            )

        # 1. clean FASTA — tip label = seq_id only (must match the abundance keys)
        _write_clean_fasta(seqs, clean_fasta)

        # 2. MAFFT alignment (writes the MSA to stdout)
        _run_mafft(clean_fasta, aligned_fasta, threads=params.threads, logger=logger)

        # 3. FastTree — GTR+CAT nucleotide ML tree (writes Newick to stdout)
        _run_fasttree(aligned_fasta, tree_path, logger=logger)

        # 4. Faith's PD via scikit-bio
        counts = [size for (_seq, size) in seqs.values()]
        taxa = list(seqs.keys())
        faith = _faith_pd(counts, taxa, tree_path)

    tree_newick = tree_path.read_text().strip() if tree_path.exists() else None
    _write_json(output_json, faith_pd=faith, n_tips=n_tips, tree_newick=tree_newick, note=None)

    if logger:
        logger.info(
            "phylogeny.completed",
            faith_pd=round(faith, 6) if faith is not None else None,
            n_tips=n_tips,
            runtime=round(timer.elapsed, 3),
        )

    return StageResult(
        stage_name="phylogeny",
        tool="mafft+fasttree",
        tool_version=_tool_version_string(),
        runtime_seconds=timer.elapsed,
        input_files=[str(asv_fasta)],
        output_files=[str(output_json), str(tree_path)],
        metrics={
            "faith_pd": round(faith, 6) if faith is not None else None,
            "n_tips": n_tips,
        },
    )


# ─── external tools ─────────────────────────────────────────────────────


def _mafft_bin() -> str:
    exe = shutil.which("mafft")
    if exe is None:
        raise StageError("phylogeny", "MAFFT not found on PATH — cannot align ASVs")
    return exe


def _fasttree_bin() -> str:
    # Debian ships the binary lowercase (`fasttree`); upstream ships `FastTree`.
    for name in ("FastTree", "fasttree", "FastTreeMP"):
        exe = shutil.which(name)
        if exe is not None:
            return exe
    raise StageError("phylogeny", "FastTree not found on PATH — cannot build tree")


def _run_mafft(input_fasta: Path, out_fasta: Path, *, threads: int, logger: Any) -> None:
    cmd = [_mafft_bin(), "--auto", "--quiet", "--thread", str(threads), str(input_fasta)]
    if logger:
        logger.info("phylogeny.mafft", cmd=" ".join(cmd))
    with open(out_fasta, "w") as fh:
        result = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE, text=True, check=False)
    if result.returncode != 0 or not out_fasta.exists() or out_fasta.stat().st_size == 0:
        raise StageError(
            "phylogeny",
            f"MAFFT alignment failed (exit {result.returncode})",
            stderr=(result.stderr or "")[-2000:],
        )


def _run_fasttree(aligned_fasta: Path, out_tree: Path, *, logger: Any) -> None:
    # -nt: nucleotide alignment; -gtr: GTR model; -quiet: suppress progress log.
    cmd = [_fasttree_bin(), "-nt", "-gtr", "-quiet", str(aligned_fasta)]
    if logger:
        logger.info("phylogeny.fasttree", cmd=" ".join(cmd))
    with open(out_tree, "w") as fh:
        result = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE, text=True, check=False)
    if result.returncode != 0 or not out_tree.exists() or out_tree.stat().st_size == 0:
        raise StageError(
            "phylogeny",
            f"FastTree failed (exit {result.returncode})",
            stderr=(result.stderr or "")[-2000:],
        )


def _faith_pd(counts: list[int], taxa: list[str], tree_path: Path) -> float:
    """Compute Faith's PD via scikit-bio against the de-novo tree.

    All ASVs are, by definition, observed in this single sample, so every tip
    is present and Faith's PD equals the total spanned branch length.
    """
    from skbio import TreeNode
    from skbio.diversity.alpha import faith_pd

    # ``convert_underscores=False``: the Newick spec turns underscores into
    # spaces, which would rename tips like ``sp0_read0`` → ``sp0 read0`` and
    # break the tip↔abundance match. ASV/centroid ids routinely contain ``_``.
    tree = TreeNode.read(str(tree_path), convert_underscores=False)

    # FastTree emits an *unrooted* tree (trifurcating root); scikit-bio's
    # Faith's PD requires a rooted tree. Midpoint rooting is the standard,
    # reproducible choice for a de-novo tree with no designated outgroup.
    # scikit-bio 0.6.2 emits a FutureWarning about the 0.7 default change; we
    # pin 0.6.2, so the current behaviour is deterministic — silence the noise.
    import warnings

    with contextlib.suppress(Exception), warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        tree = tree.root_at_midpoint()

    # scikit-bio renamed the ``otu_ids`` kwarg to ``taxa`` in 0.6.x; support both.
    try:
        value = faith_pd(counts, taxa=taxa, tree=tree, validate=True)
    except TypeError:
        value = faith_pd(counts, otu_ids=taxa, tree=tree, validate=True)
    return float(value)


# ─── I/O helpers ────────────────────────────────────────────────────────


def _read_fasta(fasta: Path) -> dict[str, tuple[str, int]]:
    """Parse a FASTA into an ordered {seq_id: (sequence, size)} map.

    ``seq_id`` is the header token before the first ``;`` (so ``Asv1;size=5``
    becomes ``Asv1``); ``size`` is read from the ``;size=N`` annotation.
    """
    result: dict[str, tuple[str, int]] = {}
    current_id = ""
    current_seq: list[str] = []
    current_size = 1

    with open(fasta) as f:
        for raw in f:
            line = raw.strip()
            if line.startswith(">"):
                if current_id:
                    result[current_id] = ("".join(current_seq), current_size)
                header = line[1:]
                current_id = header.split(";")[0].split()[0]
                current_size = 1
                for part in header.split(";"):
                    if part.startswith("size="):
                        with contextlib.suppress(ValueError, IndexError):
                            current_size = int(part.split("=")[1])
                current_seq = []
            elif current_id:
                current_seq.append(line.upper())

    if current_id:
        result[current_id] = ("".join(current_seq), current_size)
    return result


def _write_clean_fasta(seqs: dict[str, tuple[str, int]], dest: Path) -> None:
    """Write a FASTA whose headers are bare seq_ids (matching the PD taxa list)."""
    with open(dest, "w") as fh:
        for seq_id, (sequence, _size) in seqs.items():
            fh.write(f">{seq_id}\n{sequence}\n")


def _write_json(
    dest: Path,
    *,
    faith_pd: float | None,
    n_tips: int,
    tree_newick: str | None,
    note: str | None,
) -> None:
    payload: dict[str, Any] = {
        "faith_pd": round(faith_pd, 6) if faith_pd is not None else None,
        "n_tips": n_tips,
        "tree_newick": tree_newick,
    }
    if note:
        payload["note"] = note
    dest.write_text(json.dumps(payload, indent=2) + "\n")


def _tool_version_string() -> str:
    mafft = TOOL_VERSIONS.get("mafft", "?")
    fasttree = TOOL_VERSIONS.get("fasttree", "?")
    return f"mafft {mafft} / fasttree {fasttree}"
