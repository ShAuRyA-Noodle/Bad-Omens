"""Pydantic models for pipeline result endpoints (/jobs/{id}/asvs, /taxonomy, etc.)."""
from __future__ import annotations

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003
from typing import Any

from pydantic import BaseModel, ConfigDict


class ASVPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    sequence_sha256: str
    sequence: str
    length: int
    abundance: int
    created_at: datetime


class TaxonPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    asv_id: uuid.UUID
    kingdom: str | None
    phylum: str | None
    tax_class: str | None
    tax_order: str | None
    family: str | None
    genus: str | None
    species: str | None
    confidence: float | None
    reference_db: str | None
    reference_db_version: str | None


class ASVWithTaxon(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sequence_sha256: str
    sequence: str
    length: int
    abundance: int
    taxon: TaxonPublic | None = None


class DiversityPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sample_id: uuid.UUID
    richness: int | None
    shannon: float | None
    simpson: float | None
    chao1: float | None
    faith_pd: float | None
    evenness: float | None


class OrdinationPoint(BaseModel):
    asv_id: str
    x: float
    y: float
    cluster: int


class OrdinationResponse(BaseModel):
    n_asvs: int
    n_clusters: int
    n_noise_points: int
    skipped: bool = False
    reason: str | None = None
    points: list[OrdinationPoint] = []
    umap_params: dict[str, Any] | None = None
    hdbscan_params: dict[str, Any] | None = None


class JobResultsSummary(BaseModel):
    job_id: uuid.UUID
    status: str
    pipeline_version: str | None
    parameter_hash: str | None
    n_asvs: int
    n_assigned: int
    diversity: DiversityPublic | None
    amplicon: str
    dwc_metadata: dict[str, Any] | None = None


class EIIComponentPublic(BaseModel):
    key: str
    name: str
    weight: float
    available: bool
    value: float | None = None
    detail: str = ""


class IntegrityIndexPublic(BaseModel):
    """Ecosystem Integrity Index for a job — see docs/methods/eii.md."""

    model_config = ConfigDict(from_attributes=True)

    job_id: uuid.UUID
    version: str
    score: float | None
    grade: str | None
    assessed_weight: float
    components: list[EIIComponentPublic]
