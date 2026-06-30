"""Ecosystem Integrity Index (EII) — a transparent, glass-box composite score.

See ``docs/methods/eii.md`` for the authoritative methodology. This module is a
pure, deterministic implementation of it: every sub-score is computed from a
real signal passed in (diversity metrics + conservation records), no constants
stand in for data, and a sub-score that cannot be computed reliably is marked
``available=False`` and removed from the denominator rather than defaulted to a
flattering value.

The full component breakdown is written into the signed provenance manifest, so
every cell of the UI grade matrix can be traced back to the line that produced
it and independently recomputed.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

EII_VERSION = "0.1"

# Nominal weights — must sum to 1.0. Published in docs/methods/eii.md.
WEIGHTS: dict[str, float] = {
    "evenness": 0.20,
    "conservation_health": 0.25,
    "distinctness": 0.20,
    "invasive_pressure": 0.15,
    "sampling_adequacy": 0.20,
}

# IUCN category -> threat weight for the conservation-health sub-score.
# DD/NE are intentionally absent: they are not counted toward N_assessed.
THREAT_WEIGHTS: dict[str, float] = {
    "CR": 1.0,
    "EN": 0.8,
    "VU": 0.6,
    "NT": 0.3,
    "LC": 0.0,
}

# "common everywhere" reference for the rarity transform (documented constant).
OCC_COMMON = 1_000_000

# (grade, inclusive lower bound on the 0-100 score), highest first.
_GRADE_BANDS: list[tuple[str, float]] = [
    ("A+", 97), ("A", 93), ("A-", 90),
    ("B+", 87), ("B", 83), ("B-", 80),
    ("C+", 77), ("C", 73), ("C-", 70),
    ("D+", 67), ("D", 63), ("D-", 60),
]


def grade_for(score: float) -> str:
    """Map a 0-100 EII score to an A+…F grade (see methodology)."""
    for grade, lower in _GRADE_BANDS:
        if score >= lower:
            return grade
    return "F"


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


@dataclass
class EIIComponent:
    key: str
    name: str
    weight: float
    available: bool
    value: float | None = None
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EIIResult:
    version: str
    score: float | None          # 0-100, or None if nothing assessable
    grade: str | None            # A+…F, or None
    assessed_weight: float       # fraction of total weight that had real data
    components: list[EIIComponent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "score": self.score,
            "grade": self.grade,
            "assessed_weight": round(self.assessed_weight, 4),
            "components": [c.to_dict() for c in self.components],
        }


# ─── Sub-score functions (pure, individually testable) ──────────────────


def _evenness_score(
    *, richness: int | None, shannon: float | None, evenness: float | None
) -> tuple[float | None, str]:
    if richness is None or richness < 2:
        return None, "richness < 2; evenness undefined"
    if evenness is not None:
        return _clamp01(evenness), "Pielou J' (provided)"
    if shannon is not None:
        return _clamp01(shannon / math.log(richness)), "Pielou J' = H'/ln(S)"
    return None, "no Shannon/evenness available"


def _health_score(
    *, records: list[dict[str, Any]], api_degraded: bool
) -> tuple[float | None, str]:
    if api_degraded:
        return None, "conservation lookup degraded; health not assessed"
    assessed = [
        r for r in records
        if (r.get("iucn_category") or "") in THREAT_WEIGHTS
    ]
    if not assessed:
        return None, "no species with an IUCN category"
    total = sum(THREAT_WEIGHTS[r["iucn_category"]] for r in assessed)
    score = 1.0 - total / len(assessed)
    return _clamp01(score), f"1 − Σ threat_weight / {len(assessed)} assessed"


def _rarity(occ: float) -> float:
    return _clamp01(1.0 - math.log10(1.0 + occ) / math.log10(1.0 + OCC_COMMON))


def _distinctness_score(
    *, records: list[dict[str, Any]]
) -> tuple[float | None, str]:
    occs = [
        r["gbif_occurrence_count"]
        for r in records
        if r.get("gbif_occurrence_count") is not None
    ]
    if not occs:
        return None, "no GBIF occurrence counts"
    score = sum(_rarity(o) for o in occs) / len(occs)
    return _clamp01(score), f"mean GBIF rarity over {len(occs)} species"


def compute_eii(
    *,
    richness: int | None,
    shannon: float | None,
    evenness: float | None,
    conservation_records: list[dict[str, Any]] | None,
    api_degraded: bool,
) -> EIIResult:
    """Compute the EII from real per-run signals. Pure & deterministic."""
    records = conservation_records or []

    ev_val, ev_detail = _evenness_score(
        richness=richness, shannon=shannon, evenness=evenness
    )
    he_val, he_detail = _health_score(records=records, api_degraded=api_degraded)
    di_val, di_detail = _distinctness_score(records=records)

    components = [
        EIIComponent(
            key="evenness", name="Community evenness", weight=WEIGHTS["evenness"],
            available=ev_val is not None, value=ev_val, detail=ev_detail,
        ),
        EIIComponent(
            key="conservation_health", name="Threat-weighted health",
            weight=WEIGHTS["conservation_health"],
            available=he_val is not None, value=he_val, detail=he_detail,
        ),
        EIIComponent(
            key="distinctness", name="Biotic distinctness",
            weight=WEIGHTS["distinctness"],
            available=di_val is not None, value=di_val, detail=di_detail,
        ),
        # Pending components — never defaulted; weight is removed from the
        # denominator until they ship (see methodology Limitations).
        EIIComponent(
            key="invasive_pressure", name="Invasive pressure",
            weight=WEIGHTS["invasive_pressure"], available=False,
            detail="not assessed — no curated invasive list loaded yet",
        ),
        EIIComponent(
            key="sampling_adequacy", name="Sampling adequacy",
            weight=WEIGHTS["sampling_adequacy"], available=False,
            detail="not assessed — needs multi-sample / rarefaction",
        ),
    ]

    scored = [
        (c.weight, c.value)
        for c in components
        if c.available and c.value is not None
    ]
    assessed_weight = sum(w for w, _ in scored)

    if assessed_weight <= 0:
        return EIIResult(
            version=EII_VERSION, score=None, grade=None,
            assessed_weight=0.0, components=components,
        )

    weighted = sum(w * v for w, v in scored)
    score = round(100.0 * weighted / assessed_weight, 2)
    return EIIResult(
        version=EII_VERSION,
        score=score,
        grade=grade_for(score),
        assessed_weight=assessed_weight,
        components=components,
    )


__all__ = [
    "EII_VERSION",
    "EIIComponent",
    "EIIResult",
    "OCC_COMMON",
    "THREAT_WEIGHTS",
    "WEIGHTS",
    "compute_eii",
    "grade_for",
]
