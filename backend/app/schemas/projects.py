"""Pydantic models for project (multi-sample study) endpoints."""
from __future__ import annotations

import uuid  # noqa: TC003
from datetime import datetime  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=5000)


class ProjectPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    job_count: int = 0
    succeeded_count: int = 0
    created_at: datetime


class ProjectJob(BaseModel):
    """A job as it appears inside a project listing."""

    id: uuid.UUID
    status: str
    amplicon: str
    created_at: datetime


class ProjectDetail(ProjectPublic):
    jobs: list[ProjectJob] = []


class PcoaPoint(BaseModel):
    job_id: uuid.UUID
    label: str
    pc1: float
    pc2: float
    pc3: float


class ProjectOrdination(BaseModel):
    """Cross-sample Bray-Curtis PCoA over a project's completed samples."""

    n_samples: int
    proportion_explained: list[float] = []
    points: list[PcoaPoint] = []
    message: str | None = None


class ProjectTimePoint(BaseModel):
    """One dated sample in a project's temporal trend."""

    job_id: uuid.UUID
    event_date: str            # ISO date from the sample's Darwin Core metadata
    label: str
    eii_score: float | None = None
    eii_grade: str | None = None
    shannon: float | None = None
    richness: int | None = None
    faith_pd: float | None = None


class ProjectTimeSeries(BaseModel):
    """Ecosystem-Integrity / diversity trend across a project's dated samples."""

    n_dated: int
    n_undated: int
    points: list[ProjectTimePoint] = []
    message: str | None = None


class PermanovaResult(BaseModel):
    """PERMANOVA test of whether a grouping explains community structure."""

    applicable: bool
    grouping_field: str
    note: str | None = None
    n_groups: int | None = None
    pseudo_f: float | None = None
    p_value: float | None = None
    permutations: int | None = None


class ProjectUnifrac(BaseModel):
    """Async weighted-UniFrac ordination (+ PERMANOVA) for a project.

    ``status`` is one of: ``absent`` (never requested), ``computing`` (worker
    running), ``succeeded``, ``failed``.
    """

    status: str
    method: str = "weighted_unifrac"
    n_samples: int = 0
    proportion_explained: list[float] = []
    points: list[PcoaPoint] = []
    permanova: PermanovaResult | None = None
    message: str | None = None
    error_message: str | None = None
    computed_at: str | None = None
