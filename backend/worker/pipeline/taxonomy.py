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
        "--top_hits_only",
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


def _parse_blast6_taxonomy(
    blast6: Path, ref_db: Path
) -> list[dict[str, Any]]:
    """Parse vsearch blast6 output and extract taxonomy from the reference.

    The blast6 format columns:
    0: query  1: target  2: identity  3: alnlen  4: mism  5: opens
    6: qlo    7: qhi     8: tlo       9: thi     10: evalue  11: bits

    Taxonomy is extracted from the target (subject) header in the
    reference DB. For SILVA, headers are:
      ACCESSION.start.end Kingdom;Phylum;Class;Order;Family;Genus;Species

    For MitoFish/MIDORI2, headers vary but generally use ';' as delimiter.
    """
    hits: dict[str, dict[str, Any]] = {}

    with open(blast6) as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 12:
                continue
            query_id = parts[0].split(";")[0]
            target_id = parts[1]
            identity = float(parts[2])

            if query_id in hits and hits[query_id].get("identity", 0) >= identity:
                continue

            lineage = _extract_lineage_from_target(target_id, ref_db)
            record: dict[str, Any] = {
                "asv_id": query_id,
                "target": target_id,
                "identity": identity,
            }
            for i, rank in enumerate(STANDARD_RANKS):
                record[rank] = lineage[i] if i < len(lineage) else ""

            hits[query_id] = record

    return list(hits.values())


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
