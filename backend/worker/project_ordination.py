"""Async cross-sample phylogenetic ordination — weighted UniFrac + PERMANOVA.

This is the project-level counterpart to the per-job phylogeny stage. Where
Bray-Curtis PCoA (computed inline in the API) ignores how *related* the ASVs
are, UniFrac weights community differences by the branch length separating
their taxa on a shared tree — the standard phylogenetic beta-diversity metric
(Lozupone & Knight, 2005).

Because it needs one de-novo tree over the union of every sample's ASVs
(MAFFT + FastTree — worker-only binaries), it can't run in the API request
path. The API enqueues this function; it fills the ``project_ordination_results``
row the frontend polls.

Pipeline:
  1. Union every completed sample's ASVs, deduplicated by sequence.
  2. Align the unique sequences (MAFFT, single-threaded → reproducible) and
     build a FastTree GTR+CAT tree.
  3. Weighted UniFrac distance matrix (scikit-bio) over the sample × feature
     abundance table, midpoint-rooted tree.
  4. Classical PCoA on the UniFrac distances (same math as the Bray-Curtis path).
  5. PERMANOVA by collection locality when the metadata supports it (≥2 groups,
     ≥2 samples each) — otherwise recorded as not-applicable, never invented.

Everything is deterministic given identical inputs.
"""
from __future__ import annotations

import contextlib
import math
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.models import ASV, Job, JobStatus, ProjectOrdinationResult, Sample
from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session

from worker.pipeline import phylogeny as phylo

log = get_logger("worker.project_ordination")

METHOD = "weighted_unifrac"
_MIN_SAMPLES = 2
_MIN_FEATURES = 3  # a tree needs >= 3 tips


def _sync_engine() -> Engine:
    settings = get_settings()
    return create_engine(settings.database_url_sync, pool_pre_ping=True, future=True)


def compute_project_unifrac(project_id: str, result_id: str) -> dict[str, str]:
    """RQ entrypoint. Compute weighted UniFrac + PERMANOVA for a project."""
    configure_logging(get_settings().LOG_LEVEL)
    pid = uuid.UUID(project_id)
    rid = uuid.UUID(result_id)
    log.info("project_unifrac.started", project_id=project_id)

    engine = _sync_engine()
    with Session(engine, expire_on_commit=False) as session:
        result_row = session.get(ProjectOrdinationResult, rid)
        if result_row is None:
            log.error("project_unifrac.missing_row", result_id=result_id)
            return {"status": "missing", "result_id": result_id}

        try:
            payload = _json_safe(_compute(session, pid))
            result_row.status = "succeeded"
            result_row.n_samples = int(payload["n_samples"])
            result_row.data = payload
            result_row.error_message = None
            session.commit()
            log.info("project_unifrac.completed", project_id=project_id, n_samples=payload["n_samples"])
            return {"status": "succeeded", "project_id": project_id}
        except _NotEnoughData as exc:
            result_row.status = "succeeded"  # a valid answer: "not enough data yet"
            result_row.n_samples = exc.n_samples
            result_row.data = {"n_samples": exc.n_samples, "points": [], "message": str(exc)}
            result_row.error_message = None
            session.commit()
            log.info("project_unifrac.insufficient", project_id=project_id, reason=str(exc))
            return {"status": "succeeded", "project_id": project_id}
        except Exception as exc:  # noqa: BLE001 — surface the real error, don't fake a result
            session.rollback()
            row = session.get(ProjectOrdinationResult, rid)
            if row is not None:
                row.status = "failed"
                row.error_message = str(exc)[:2000]
                session.commit()
            log.exception("project_unifrac.failed", project_id=project_id)
            return {"status": "failed", "project_id": project_id, "error": str(exc)}


class _NotEnoughData(Exception):
    def __init__(self, message: str, n_samples: int) -> None:
        super().__init__(message)
        self.n_samples = n_samples


def _json_safe(obj: Any) -> Any:
    """Recursively replace non-finite floats (inf/nan) with None so the payload
    is valid JSONB. Postgres rejects Infinity/NaN in a json column."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    return obj


def _compute(session: Session, pid: uuid.UUID) -> dict[str, Any]:
    # ─── Gather the project's completed samples + their ASVs ────────────
    jobs = list(
        session.scalars(
            select(Job).where(Job.project_id == pid, Job.status == JobStatus.SUCCEEDED)
        )
    )
    if len(jobs) < _MIN_SAMPLES:
        raise _NotEnoughData(
            f"At least {_MIN_SAMPLES} completed samples are needed for UniFrac ordination.",
            n_samples=len(jobs),
        )
    job_ids = [j.id for j in jobs]

    asv_rows = session.execute(
        select(ASV.job_id, ASV.sequence_sha256, ASV.sequence, ASV.abundance).where(
            ASV.job_id.in_(job_ids)
        )
    )
    # feature = unique ASV sequence (keyed by its sha); representative sequence kept.
    feature_seq: dict[str, str] = {}
    per_job: dict[uuid.UUID, dict[str, int]] = {jid: {} for jid in job_ids}
    for job_id, sha, sequence, abundance in asv_rows:
        feature_seq.setdefault(sha, sequence)
        per_job[job_id][sha] = per_job[job_id].get(sha, 0) + int(abundance)

    if len(feature_seq) < _MIN_FEATURES:
        raise _NotEnoughData(
            f"Only {len(feature_seq)} distinct ASV(s) across the project; a phylogenetic "
            f"tree needs at least {_MIN_FEATURES}.",
            n_samples=len(jobs),
        )

    # Short, underscore-free tip ids (f0..fN) so the Newick round-trip and the
    # abundance columns line up exactly.
    shas = sorted(feature_seq)
    feature_ids = [f"f{i}" for i in range(len(shas))]
    sha_to_fid = dict(zip(shas, feature_ids, strict=True))

    # ─── Build one tree over the union of ASVs ──────────────────────────
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        clean = ws / "features.fasta"
        aligned = ws / "aligned.fasta"
        tree_path = ws / "tree.nwk"
        with open(clean, "w") as fh:
            for sha in shas:
                fh.write(f">{sha_to_fid[sha]}\n{feature_seq[sha]}\n")

        # single-threaded MAFFT -> deterministic (see phylogeny.py rationale)
        phylo._run_mafft(clean, aligned, threads=1, logger=log)
        phylo._run_fasttree(aligned, tree_path, logger=log)

        # ─── Weighted UniFrac + PCoA ────────────────────────────────────
        import numpy as np
        from app.core.beta_diversity import pcoa
        from skbio import TreeNode
        from skbio.diversity import beta_diversity

        tree = TreeNode.read(str(tree_path), convert_underscores=False)
        # Fall back to the as-read tree if midpoint rooting can't be applied.
        with contextlib.suppress(Exception):
            tree = tree.root_at_midpoint()

        sample_ids = [j.id.hex for j in jobs]
        counts = np.array(
            [[per_job[jid].get(sha, 0) for sha in shas] for jid in job_ids],
            dtype=np.int64,
        )
        dm = beta_diversity(
            "weighted_unifrac", counts, ids=sample_ids, taxa=feature_ids, tree=tree, validate=True
        )
        coords, proportions = pcoa(dm.data, n_components=3)
        ncol = coords.shape[1]

    points = [
        {
            "job_id": str(jobs[i].id),
            "label": jobs[i].id.hex[:8],
            "pc1": float(coords[i, 0]) if ncol > 0 else 0.0,
            "pc2": float(coords[i, 1]) if ncol > 1 else 0.0,
            "pc3": float(coords[i, 2]) if ncol > 2 else 0.0,
        }
        for i in range(len(jobs))
    ]

    permanova_result = _permanova_by_locality(session, jobs, dm, sample_ids)

    return {
        "method": METHOD,
        "n_samples": len(jobs),
        "n_features": len(shas),
        "proportion_explained": [float(p) for p in proportions],
        "points": points,
        "permanova": permanova_result,
        "computed_at": datetime.now(tz=UTC).isoformat(),
    }


def _permanova_by_locality(
    session: Session, jobs: list[Job], dm: Any, sample_ids: list[str]
) -> dict[str, Any]:
    """PERMANOVA testing whether locality explains community structure.

    Returns a not-applicable result (never a fabricated statistic) unless the
    metadata yields ≥2 groups with ≥2 samples each.
    """
    # locality per job, read from the first sample's Darwin Core metadata
    sample_rows = session.execute(
        select(Sample.job_id, Sample.dwc_metadata).where(Sample.job_id.in_([j.id for j in jobs]))
    )
    job_locality: dict[uuid.UUID, str] = {}
    for job_id, dwc in sample_rows:
        if job_id in job_locality:
            continue
        loc = (dwc or {}).get("locality") if isinstance(dwc, dict) else None
        if isinstance(loc, str) and loc.strip():
            job_locality[job_id] = loc.strip()

    grouping = [job_locality.get(j.id, "") for j in jobs]
    groups = [g for g in grouping if g]
    distinct = set(groups)
    counts_per_group = {g: groups.count(g) for g in distinct}
    usable = {g for g, n in counts_per_group.items() if n >= 2}

    if len(usable) < 2 or any(g == "" for g in grouping):
        return {
            "applicable": False,
            "grouping_field": "locality",
            "note": (
                "PERMANOVA needs every sample labelled with a locality and at least "
                "2 localities with ≥2 samples each. Add collection localities to test "
                "whether sites differ significantly."
            ),
        }

    from skbio.stats.distance import permanova

    res = permanova(dm, grouping, permutations=999)
    pseudo_f = float(res["test statistic"])
    note = None
    if not math.isfinite(pseudo_f):
        # Perfect separation: zero within-group variance (e.g. technical
        # replicates that are identical) drives the F ratio to infinity. Report
        # it honestly as null rather than emitting a non-finite number.
        pseudo_f = None  # type: ignore[assignment]
        note = "Perfect group separation (zero within-group variance); pseudo-F is unbounded."
    return {
        "applicable": True,
        "grouping_field": "locality",
        "n_groups": len(distinct),
        "pseudo_f": pseudo_f,
        "p_value": float(res["p-value"]),
        "permutations": int(res["number of permutations"]),
        "note": note,
    }


__all__ = ["compute_project_unifrac"]
