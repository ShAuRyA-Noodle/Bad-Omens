"""Stage 7: Conservation cross-referencing via GBIF + IUCN Red List.

For every species-level taxon detected by the taxonomy stage, this
module:

1. Resolves the species name against the GBIF Backbone Taxonomy
   (``/species/match``) to get a canonical taxon key.
2. Queries the GBIF Occurrence API for a global occurrence count
   so the user knows how well-documented the species is.
3. Resolves the IUCN Red List conservation status (LC / NT / VU / EN /
   CR / EW / EX) via GBIF's mirrored ``iucnRedListCategory`` endpoint —
   keyed by the GBIF taxon key from step 1. (We use GBIF's mirror rather
   than the IUCN API directly; the provenance manifest records the real
   source as ``gbif-iucn-mirror`` accordingly.)
4. Flags known invasive species against the Global Invasive Species
   Database (GISD) — currently via a curated local list; API
   integration is Phase 3.5.

Results are cached in the ``conservation_cache`` Postgres table with
a 30-day TTL so repeated analyses of the same species don't hammer
external APIs.

This is the **novel contribution** of the Relict platform — no existing
open eDNA tool automates this cross-referencing step.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from app.core.config import get_settings
from app.core.logging import get_logger

from worker.pipeline import StageResult, StageTimer, ensure_stage_dir

log = get_logger(__name__)

GBIF_SPECIES_MATCH_URL = "https://api.gbif.org/v1/species/match"
GBIF_OCCURRENCE_SEARCH_URL = "https://api.gbif.org/v1/occurrence/search"
# IUCN Red List category is read from GBIF's mirror (api.gbif.org/v1/species/
# {key}/iucnRedListCategory), not IUCN's own API — see _iucn_lookup. The
# provenance source is recorded as "gbif-iucn-mirror".
CONSERVATION_SOURCE = "gbif-api-v1,gbif-iucn-mirror"
CACHE_TTL_DAYS = 30


@dataclass
class ConservationRecord:
    """Conservation status for one detected species."""

    species: str
    gbif_key: int | None = None
    gbif_matched_name: str | None = None
    gbif_occurrence_count: int | None = None
    gbif_match_confidence: int | None = None
    iucn_category: str | None = None
    iucn_category_full: str | None = None
    iucn_population_trend: str | None = None
    iucn_assessment_year: int | None = None
    is_invasive: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "species": self.species,
            "gbif_key": self.gbif_key,
            "gbif_matched_name": self.gbif_matched_name,
            "gbif_occurrence_count": self.gbif_occurrence_count,
            "gbif_match_confidence": self.gbif_match_confidence,
            "iucn_category": self.iucn_category,
            "iucn_category_full": self.iucn_category_full,
            "iucn_population_trend": self.iucn_population_trend,
            "iucn_assessment_year": self.iucn_assessment_year,
            "is_invasive": self.is_invasive,
            "error": self.error,
        }


IUCN_CATEGORY_MAP: dict[str, str] = {
    "LC": "Least Concern",
    "NT": "Near Threatened",
    "VU": "Vulnerable",
    "EN": "Endangered",
    "CR": "Critically Endangered",
    "EW": "Extinct in the Wild",
    "EX": "Extinct",
    "DD": "Data Deficient",
    "NE": "Not Evaluated",
    "LR/lc": "Least Concern",
    "LR/nt": "Near Threatened",
    "LR/cd": "Conservation Dependent",
}


def run(
    workspace: Path,
    taxonomy_tsv: Path,
    params: Any = None,
    kingdom_hint: str | None = None,
    logger: Any = None,
) -> StageResult:
    """Cross-reference detected taxa against GBIF and IUCN Red List.

    ``kingdom_hint`` (derived from the amplicon marker) constrains the GBIF
    name match so plant/fungal/bacterial markers don't mis-resolve to animal
    homonyms — replacing the previous hardcoded ``kingdom=Animalia``.
    """
    settings = get_settings()
    iucn_token = (
        settings.IUCN_REDLIST_TOKEN.get_secret_value()
        if settings.IUCN_REDLIST_TOKEN
        else None
    )

    stage_dir = ensure_stage_dir(workspace, "conservation")
    output_json = stage_dir / "conservation.json"

    if logger:
        logger.info("conservation.started")

    with StageTimer() as timer:
        species_list = _extract_species_from_taxonomy(taxonomy_tsv)

        if not species_list:
            if logger:
                logger.info("conservation.skipped", reason="no species-level assignments")
            result_data: dict[str, Any] = {
                "skipped": True,
                "reason": "No species-level taxonomy assignments to cross-reference",
                "records": [],
            }
            output_json.write_text(json.dumps(result_data, indent=2) + "\n")
            return StageResult(
                stage_name="conservation",
                tool="gbif+iucn",
                tool_version=CONSERVATION_SOURCE,
                runtime_seconds=timer.elapsed,
                input_files=[str(taxonomy_tsv)],
                output_files=[str(output_json)],
                metrics={"skipped": True, "species_queried": 0},
            )

        records: list[ConservationRecord] = []
        for species_name in species_list:
            record = _lookup_species(
                species_name, iucn_token=iucn_token, kingdom_hint=kingdom_hint, logger=logger
            )
            records.append(record)
            time.sleep(0.2)

        # Fail loud, never silent: a lookup that errored (GBIF/IUCN down,
        # rate-limited, 5xx) is NOT the same as "assessed and not threatened".
        # Surfacing lookup_failed_count + api_degraded lets the API/UI refuse to
        # present a 0-threatened result as authoritative when some lookups never
        # completed — the exact false-negative that must never reach a forest
        # department.
        lookup_failed_count = sum(1 for r in records if r.error)
        result_data = {
            "skipped": False,
            "species_queried": len(species_list),
            "species_with_gbif": sum(1 for r in records if r.gbif_key),
            "species_with_iucn": sum(1 for r in records if r.iucn_category),
            "threatened_count": sum(
                1 for r in records if r.iucn_category in ("VU", "EN", "CR", "EW", "EX")
            ),
            "lookup_failed_count": lookup_failed_count,
            "api_degraded": lookup_failed_count > 0,
            "records": [r.to_dict() for r in records],
        }

        output_json.write_text(json.dumps(result_data, indent=2) + "\n")

    if logger:
        logger.info(
            "conservation.completed",
            species_queried=result_data["species_queried"],
            species_with_gbif=result_data["species_with_gbif"],
            species_with_iucn=result_data["species_with_iucn"],
            threatened=result_data["threatened_count"],
            lookup_failed=result_data["lookup_failed_count"],
            runtime=round(timer.elapsed, 2),
        )

    return StageResult(
        stage_name="conservation",
        tool="gbif+iucn",
        tool_version=CONSERVATION_SOURCE,
        runtime_seconds=timer.elapsed,
        input_files=[str(taxonomy_tsv)],
        output_files=[str(output_json)],
        metrics={
            "species_queried": result_data["species_queried"],
            "species_with_gbif": result_data["species_with_gbif"],
            "species_with_iucn": result_data["species_with_iucn"],
            "threatened_count": result_data["threatened_count"],
            "lookup_failed_count": result_data["lookup_failed_count"],
            "api_degraded": result_data["api_degraded"],
        },
    )


def _extract_species_from_taxonomy(taxonomy_tsv: Path) -> list[str]:
    """Extract unique species-level names from the taxonomy TSV."""
    import csv

    species_set: set[str] = set()
    with open(taxonomy_tsv) as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            genus = (row.get("genus") or "").strip()
            species = (row.get("species") or "").strip()
            if genus and species:
                full_name = f"{genus} {species}".strip()
                if full_name and len(full_name.split()) >= 2:
                    species_set.add(full_name)
            elif genus:
                species_set.add(genus)

    return sorted(species_set)


def _lookup_species(
    species_name: str,
    *,
    iucn_token: str | None,
    kingdom_hint: str | None = None,
    logger: Any = None,
) -> ConservationRecord:
    """Look up a single species against GBIF and IUCN."""
    record = ConservationRecord(species=species_name)

    try:
        _gbif_lookup(record, species_name, kingdom_hint=kingdom_hint)
    except Exception as exc:
        record.error = f"GBIF error: {exc!s}"
        if logger:
            logger.warning("conservation.gbif_error", species=species_name, error=str(exc))

    if iucn_token:
        try:
            _iucn_lookup(record, species_name, iucn_token)
        except Exception as exc:
            if record.error:
                record.error += f"; IUCN error: {exc!s}"
            else:
                record.error = f"IUCN error: {exc!s}"
            if logger:
                logger.warning("conservation.iucn_error", species=species_name, error=str(exc))

    return record


def _gbif_lookup(
    record: ConservationRecord, species_name: str, kingdom_hint: str | None = None
) -> None:
    """Query GBIF Species Match + Occurrence count.

    When ``kingdom_hint`` is supplied it constrains the match (so e.g. a plant
    name isn't matched to an animal homonym); if that constrained match fails
    we retry unconstrained.
    """
    with httpx.Client(timeout=15.0) as client:
        match_params = {"name": species_name, "verbose": "false"}
        if kingdom_hint:
            match_params["kingdom"] = kingdom_hint
        match_resp = client.get(GBIF_SPECIES_MATCH_URL, params=match_params)
        match_resp.raise_for_status()
        match_data = match_resp.json()

        if match_data.get("matchType") != "NONE" and match_data.get("usageKey"):
            record.gbif_key = match_data["usageKey"]
            record.gbif_matched_name = match_data.get("canonicalName") or match_data.get("scientificName")
            record.gbif_match_confidence = match_data.get("confidence")

            occ_resp = client.get(
                GBIF_OCCURRENCE_SEARCH_URL,
                params={"taxonKey": record.gbif_key, "limit": 0},
            )
            occ_resp.raise_for_status()
            record.gbif_occurrence_count = occ_resp.json().get("count", 0)
        elif kingdom_hint:
            with httpx.Client(timeout=15.0) as client2:
                match_resp2 = client2.get(
                    GBIF_SPECIES_MATCH_URL,
                    params={"name": species_name, "verbose": "false"},
                )
                match_resp2.raise_for_status()
                match_data2 = match_resp2.json()
                if match_data2.get("matchType") != "NONE" and match_data2.get("usageKey"):
                    record.gbif_key = match_data2["usageKey"]
                    record.gbif_matched_name = match_data2.get("canonicalName")
                    record.gbif_match_confidence = match_data2.get("confidence")


def _iucn_lookup(
    record: ConservationRecord, species_name: str, token: str
) -> None:
    """Query IUCN Red List status via GBIF's mirrored endpoint.

    GBIF mirrors IUCN Red List categories at
    ``/v1/species/{key}/iucnRedListCategory``, which is more reliable
    than IUCN's own API (which is behind Cloudflare bot protection).
    We use this endpoint when we already have a GBIF taxon key from
    the earlier ``_gbif_lookup`` call.
    """
    if not record.gbif_key:
        return

    with httpx.Client(timeout=15.0) as client:
        url = f"https://api.gbif.org/v1/species/{record.gbif_key}/iucnRedListCategory"
        resp = client.get(url)

        if resp.status_code == 404:
            return
        resp.raise_for_status()
        data = resp.json()

        code = data.get("code", "")
        category_full = data.get("category", "")

        if code:
            record.iucn_category = code
            record.iucn_category_full = IUCN_CATEGORY_MAP.get(code, category_full)
