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
