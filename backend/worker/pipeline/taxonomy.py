"""Stage 4: Taxonomic assignment via vsearch --usearch_global.

Aligns each ASV centroid against a reference database (SILVA, MitoFish,
or MIDORI2) and extracts the best-hit taxonomy lineage.

The reference DB can be either a raw FASTA or a pre-built UDB index
(faster). The downloader script builds the UDB automatically.

SILVA taxonomy is encoded in FASTA headers as:
  >ACCESSION.start.end TAXONOMY
  e.g. >AB001234.1.1520 Bacteria;Proteobacteria;Gammaproteobacteria;...

The parser splits on ';' and maps positions to standard ranks.

Outputs:
  workspace/taxonomy/taxonomy.tsv — tab-separated: ASV_ID, identity%, lineage fields
"""
from __future__ import annotations

import csv
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from worker import TOOL_VERSIONS
from worker.pipeline import StageError, StageResult, StageTimer, ensure_stage_dir

STANDARD_RANKS = ("kingdom", "phylum", "class", "order", "family", "genus", "species")

# Minimum percent identity to *assign* each rank. A single 90%-identity hit
# should never be reported as a species; the lineage is truncated to the
# deepest rank the best-hit identity actually supports. Conservative,
# marker-agnostic defaults (COI/16S species usually need ~97-99%).
_RANK_MIN_IDENTITY: dict[str, float] = {
    "kingdom": 70.0,
    "phylum": 75.0,
    "class": 80.0,
    "order": 85.0,
    "family": 90.0,
    "genus": 95.0,
    "species": 97.0,
}

# Hits within this many identity-percent of the best hit are pooled for the LCA
# consensus, so a near-tie between two genera collapses to their common family.
_LCA_BAND = 1.0


@dataclass
class TaxonomyParams:
    """Parameters for the taxonomy stage."""

    identity_threshold: float = 0.80   # minimum identity to accept a hit
    max_accepts: int = 5               # top N hits to consider
    max_rejects: int = 64
    threads: int = 2
    reference_db: str = ""             # path to .fasta or .udb — set by orchestrator


def run(
    workspace: Path,
    input_fasta: Path,
    params: TaxonomyParams | None = None,
    logger: Any = None,
) -> StageResult:
    """Assign taxonomy to ASV centroids via vsearch --usearch_global."""
    if params is None:
        params = TaxonomyParams()

    if not params.reference_db:
        raise StageError("taxonomy", "No reference_db path specified in params")

    ref_path = Path(params.reference_db)
    if not ref_path.exists():
        raise StageError(
            "taxonomy",
            f"Reference database not found: {ref_path}. Run 'make download-refs' first.",
        )

    stage_dir = ensure_stage_dir(workspace, "taxonomy")
    blast6_out = stage_dir / "hits.blast6"
    taxonomy_tsv = stage_dir / "taxonomy.tsv"

    cmd = [
        "vsearch",
        "--usearch_global", str(input_fasta),
        "--db", str(ref_path),
        "--blast6out", str(blast6_out),
        "--id", str(params.identity_threshold),
        "--maxaccepts", str(params.max_accepts),
        "--maxrejects", str(params.max_rejects),
        "--threads", str(params.threads),
        # Return the top N hits (not just the single best) so taxonomy can be
        # assigned by LCA consensus rather than one arbitrary best hit.
        "--output_no_hits",
        # Search both strands — without this, ASVs in reverse orientation
        # (common when users upload R2-only, or when the amplicon primer
        # set produces reverse-complement reads) silently miss every hit
        # and come back "unclassified" even when a real match exists.
        "--strand", "both",
    ]

    if logger:
        logger.info(
            "taxonomy.started",
            reference_db=str(ref_path),
            identity=params.identity_threshold,
        )

    with StageTimer() as timer:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

    if result.returncode != 0:
        raise StageError(
            "taxonomy",
            f"vsearch --usearch_global failed (code {result.returncode})",
            stderr=result.stderr[-2000:],
        )

    if not blast6_out.exists():
        raise StageError("taxonomy", "vsearch produced no blast6 output")

    tax_records = _parse_blast6_taxonomy(blast6_out, ref_path)
    _write_taxonomy_tsv(taxonomy_tsv, tax_records)

    assigned = sum(1 for r in tax_records if r.get("kingdom"))
    total = len(tax_records)

    if logger:
        logger.info(
            "taxonomy.completed",
            asvs_total=total,
            asvs_assigned=assigned,
            runtime=round(timer.elapsed, 2),
        )

    return StageResult(
        stage_name="taxonomy",
        tool="vsearch",
        tool_version=TOOL_VERSIONS["vsearch"],
        runtime_seconds=timer.elapsed,
        input_files=[str(input_fasta), str(ref_path)],
        output_files=[str(taxonomy_tsv), str(blast6_out)],
        metrics={
            "asvs_total": total,
            "asvs_assigned": assigned,
            "assignment_rate": round(assigned / max(total, 1), 4),
            "reference_db": ref_path.name,
        },
    )


def _lca_lineage(lineages: list[list[str]]) -> list[str]:
    """Lowest-common-ancestor: the common rank prefix across all lineages.

    Stops at the first rank where the lineages disagree, so two hits that share
    a family but differ in genus collapse to the family.
    """
    if not lineages:
        return []
    lca: list[str] = []
    for i in range(len(STANDARD_RANKS)):
        values = {lin[i] for lin in lineages if i < len(lin) and lin[i]}
        if len(values) == 1 and all(i < len(lin) and lin[i] for lin in lineages):
            lca.append(next(iter(values)))
        else:
            break
    return lca


def _gate_by_identity(lineage: list[str], identity_pct: float) -> list[str]:
    """Truncate a lineage to the deepest rank the identity supports."""
    gated: list[str] = []
    for i, rank in enumerate(STANDARD_RANKS):
        if i >= len(lineage) or not lineage[i]:
            break
        if identity_pct < _RANK_MIN_IDENTITY[rank]:
            break
        gated.append(lineage[i])
    return gated


def _parse_blast6_taxonomy(
    blast6: Path, ref_db: Path
) -> list[dict[str, Any]]:
    """Parse vsearch blast6 output into LCA-consensus, identity-gated taxonomy.

    blast6 columns: 0 query 1 target 2 identity 3 alnlen … . For each ASV we
    pool the hits within ``_LCA_BAND`` of the best identity, take their LCA
    consensus lineage, then truncate it to the deepest rank the best-hit
    identity supports (``_gate_by_identity``). This replaces reporting a full
    7-rank species from a single low-identity best hit.
    """
    per_query: dict[str, list[tuple[float, list[str], str]]] = {}

    with open(blast6) as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 2:
                continue
            query_id = parts[0].split(";")[0]
            per_query.setdefault(query_id, [])
            target_id = parts[1]
            if target_id == "*" or len(parts) < 12:  # no-hit sentinel
                continue
            identity = float(parts[2])
            lineage = _extract_lineage_from_target(target_id, ref_db)
            per_query[query_id].append((identity, lineage, target_id))

    records: list[dict[str, Any]] = []
    for query_id, hits in per_query.items():
        record: dict[str, Any] = {"asv_id": query_id, "target": "", "identity": 0.0}
        for rank in STANDARD_RANKS:
            record[rank] = ""

        if hits:
            best_id = max(h[0] for h in hits)
            band = [h for h in hits if h[0] >= best_id - _LCA_BAND]
            lca = _lca_lineage([h[1] for h in band])
            gated = _gate_by_identity(lca, best_id)
            record["identity"] = best_id
            record["target"] = max(hits, key=lambda h: h[0])[2]
            for i, rank in enumerate(STANDARD_RANKS):
                record[rank] = gated[i] if i < len(gated) else ""

        records.append(record)

    return records


_ref_header_cache: dict[str, dict[str, str]] = {}


def _extract_lineage_from_target(target_id: str, ref_db: Path) -> list[str]:
    """Extract the taxonomy string from the reference FASTA header.

    This searches the reference DB for the target accession and parses
    the taxonomy from the description. For SILVA the header format is:
      >ACCESSION.start.end Taxonomy;fields;separated;by;semicolons

    We cache the full header index on first call so subsequent lookups
    are O(1).
    """
    db_key = str(ref_db)
    if db_key not in _ref_header_cache:
        _ref_header_cache[db_key] = _index_ref_headers(ref_db)

    header_map = _ref_header_cache[db_key]
    desc = header_map.get(target_id, "")
    if not desc:
        return []

    return [p.strip() for p in desc.split(";") if p.strip()]


def _index_ref_headers(ref_db: Path) -> dict[str, str]:
    """Build {accession: taxonomy_string} from a reference FASTA.

    Only reads headers (lines starting with '>'), so this is fast even
    for multi-GB databases. The full sequence content is never loaded.
    """
    index: dict[str, str] = {}
    with open(ref_db) as f:
        for line in f:
            if line.startswith(">"):
                header = line[1:].strip()
                parts = header.split(None, 1)
                accession = parts[0]
                taxonomy = parts[1] if len(parts) > 1 else ""
                index[accession] = taxonomy
    return index


def _write_taxonomy_tsv(path: Path, records: list[dict[str, Any]]) -> None:
    """Write taxonomy assignments as a TSV file."""
    fieldnames = ["asv_id", "target", "identity", *STANDARD_RANKS]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
