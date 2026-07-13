"""Project routes — multi-sample studies + cross-sample Bray-Curtis PCoA."""
from __future__ import annotations

import uuid  # noqa: TC003
from collections import defaultdict

import numpy as np
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.core.beta_diversity import bray_curtis_matrix, pcoa
from app.db.models import ASV, JobStatus
from app.schemas.projects import (
    PcoaPoint,
    ProjectCreate,
    ProjectDetail,
    ProjectJob,
    ProjectOrdination,
    ProjectPublic,
)
from app.services import projects as projects_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectPublic, status_code=status.HTTP_201_CREATED, summary="Create a project")
async def create_project(payload: ProjectCreate, user: CurrentUser, session: SessionDep) -> ProjectPublic:
    project = await projects_service.create_project(
        session, user=user, name=payload.name, description=payload.description
    )
    return ProjectPublic(
        id=project.id, name=project.name, description=project.description,
        job_count=0, succeeded_count=0, created_at=project.created_at,
    )


@router.get("", response_model=list[ProjectPublic], summary="List the caller's projects")
async def list_projects(user: CurrentUser, session: SessionDep) -> list[ProjectPublic]:
    rows = await projects_service.list_projects_with_counts(session, user=user)
    return [
        ProjectPublic(
            id=p.id, name=p.name, description=p.description,
            job_count=total, succeeded_count=succeeded, created_at=p.created_at,
        )
        for p, total, succeeded in rows
    ]


@router.get("/{project_id}", response_model=ProjectDetail, summary="Project detail with its jobs")
async def get_project(project_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> ProjectDetail:
    project = await projects_service.get_project(session, user=user, project_id=project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    jobs = sorted(project.jobs, key=lambda j: j.created_at, reverse=True)
    succeeded = sum(1 for j in jobs if j.status == JobStatus.SUCCEEDED)
    return ProjectDetail(
        id=project.id, name=project.name, description=project.description,
        job_count=len(jobs), succeeded_count=succeeded, created_at=project.created_at,
        jobs=[
            ProjectJob(id=j.id, status=j.status.value, amplicon=j.amplicon.value, created_at=j.created_at)
            for j in jobs
        ],
    )


@router.post("/{project_id}/jobs/{job_id}", response_model=ProjectDetail, summary="Attach a job to a project")
async def attach_job(project_id: uuid.UUID, job_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> ProjectDetail:
    job = await projects_service.attach_job(session, user=user, project_id=project_id, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project or job not found")
    return await get_project(project_id, user, session)


@router.get("/{project_id}/ordination", response_model=ProjectOrdination, summary="Cross-sample Bray-Curtis PCoA")
async def project_ordination(project_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> ProjectOrdination:
    """Bray-Curtis dissimilarity + PCoA over the project's completed samples.

    Each completed job is one sample; ASVs are matched across samples by
    sequence hash. Real community ordination (needs >= 2 samples).
    """
    project = await projects_service.get_project(session, user=user, project_id=project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    succeeded = [j for j in project.jobs if j.status == JobStatus.SUCCEEDED]
    if len(succeeded) < 2:
        return ProjectOrdination(
            n_samples=len(succeeded),
            message="At least 2 completed samples are needed for cross-sample ordination.",
        )

    job_ids = [j.id for j in succeeded]
    rows = await session.execute(
        select(ASV.job_id, ASV.sequence_sha256, ASV.abundance).where(ASV.job_id.in_(job_ids))
    )
    per_job: dict[uuid.UUID, dict[str, int]] = defaultdict(dict)
    features: set[str] = set()
    for job_id, sha, abundance in rows:
        per_job[job_id][sha] = per_job[job_id].get(sha, 0) + int(abundance)
        features.add(sha)

    if not features:
        return ProjectOrdination(n_samples=len(succeeded), message="No ASVs to compare across samples.")

    feature_list = sorted(features)
    matrix = np.array(
        [[per_job[jid].get(f, 0) for f in feature_list] for jid in job_ids], dtype=np.float64
    )
    dist = bray_curtis_matrix(matrix)
    coords, proportions = pcoa(dist, n_components=3)
    ncol = coords.shape[1]

    points = [
        PcoaPoint(
            job_id=jid,
            label=jid.hex[:8],
            pc1=float(coords[i, 0]) if ncol > 0 else 0.0,
            pc2=float(coords[i, 1]) if ncol > 1 else 0.0,
            pc3=float(coords[i, 2]) if ncol > 2 else 0.0,
        )
        for i, jid in enumerate(job_ids)
    ]
    return ProjectOrdination(
        n_samples=len(succeeded),
        proportion_explained=proportions,
        points=points,
    )
