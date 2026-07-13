"""Pydantic models for /jobs/{id}/conservation endpoint."""
from __future__ import annotations

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003
from typing import Any

from pydantic import BaseModel, ConfigDict


class ConservationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    species: str
    gbif_key: int | None
    gbif_occurrence_count: int | None
    iucn_category: str | None
    iucn_assessment_year: int | None
    is_invasive: bool
    legal_flags: dict[str, Any] | None
    fetched_at: datetime


class ConservationSummary(BaseModel):
    job_id: uuid.UUID
    species_queried: int
    species_with_gbif: int
    species_with_iucn: int
    threatened_count: int
    # Fail-loud signals: when a GBIF/IUCN lookup errored, the panel is degraded
    # and a 0 threatened_count must not be presented as authoritative.
    lookup_failed_count: int = 0
    api_degraded: bool = False
    records: list[ConservationPublic]
