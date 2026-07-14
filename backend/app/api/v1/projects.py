"""Project routes — multi-sample studies + cross-sample Bray-Curtis PCoA."""
from __future__ import annotations

import uuid  # noqa: TC003
from collections import defaultdict

import numpy as np
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.core.beta_diversity import bray_curtis_matrix, pcoa
from app.db.models import ASV, DiversityMetric, IntegrityIndex, JobStatus, Sample
from app.schemas.projects import (
    PcoaPoint,
    PermanovaResult,
    ProjectCreate,
    ProjectDetail,
    ProjectJob,
    ProjectOrdination,
    ProjectPublic,
    ProjectTimePoint,
    ProjectTimeSeries,
    ProjectUnifrac,
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


@router.get("/{project_id}/timeseries", response_model=ProjectTimeSeries, summary="Temporal trend across dated samples")
async def project_timeseries(project_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> ProjectTimeSeries:
    """Ecosystem-Integrity + diversity over time for a project's completed samples.

    Each completed job whose sample carries a Darwin Core ``eventDate`` becomes
    one point on the timeline, ordered by date. Samples without an eventDate are
    counted but excluded (a trend needs real collection dates) — never invented.
    """
    project = await projects_service.get_project(session, user=user, project_id=project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    succeeded = [j for j in project.jobs if j.status == JobStatus.SUCCEEDED]
    if not succeeded:
        return ProjectTimeSeries(n_dated=0, n_undated=0, message="No completed samples yet.")

    job_ids = [j.id for j in succeeded]

    # sample (eventDate) per job, diversity per sample, EII per job — three
    # scoped lookups keyed off the project's completed jobs.
    sample_rows = await session.execute(
        select(Sample.job_id, Sample.id, Sample.dwc_metadata).where(Sample.job_id.in_(job_ids))
    )
    job_to_sample: dict[uuid.UUID, uuid.UUID] = {}
    job_to_date: dict[uuid.UUID, str] = {}
    for job_id, sample_id, dwc in sample_rows:
        if job_id in job_to_sample:
            continue  # first sample per job
        job_to_sample[job_id] = sample_id
        event_date = (dwc or {}).get("eventDate") if isinstance(dwc, dict) else None
        if isinstance(event_date, str) and event_date.strip():
            job_to_date[job_id] = event_date.strip()

    sample_ids = list(job_to_sample.values())
    div_rows = await session.execute(
        select(DiversityMetric.sample_id, DiversityMetric.shannon, DiversityMetric.richness, DiversityMetric.faith_pd)
        .where(DiversityMetric.sample_id.in_(sample_ids))
    ) if sample_ids else []
    div_by_sample: dict[uuid.UUID, tuple[float | None, int | None, float | None]] = {
        sid: (sh, rich, fp) for sid, sh, rich, fp in div_rows
    }

    eii_rows = await session.execute(
        select(IntegrityIndex.job_id, IntegrityIndex.score, IntegrityIndex.grade).where(IntegrityIndex.job_id.in_(job_ids))
    )
    eii_by_job: dict[uuid.UUID, tuple[float | None, str | None]] = {
        jid: (score, grade) for jid, score, grade in eii_rows
    }

    points: list[ProjectTimePoint] = []
    for jid in job_ids:
        date = job_to_date.get(jid)
        if date is None:
            continue
        sh, rich, fp = div_by_sample.get(job_to_sample.get(jid), (None, None, None))  # type: ignore[arg-type]
        score, grade = eii_by_job.get(jid, (None, None))
        points.append(ProjectTimePoint(
            job_id=jid, event_date=date, label=jid.hex[:8],
            eii_score=score, eii_grade=grade, shannon=sh, richness=rich, faith_pd=fp,
        ))

    points.sort(key=lambda p: p.event_date)  # ISO dates sort chronologically
    n_undated = len(succeeded) - len(points)
    msg = None
    if not points:
        msg = "No completed samples have a collection date yet. Add an eventDate when uploading to build a trend."
    return ProjectTimeSeries(n_dated=len(points), n_undated=n_undated, points=points, message=msg)


def _unifrac_response(row: object | None) -> ProjectUnifrac:
    """Serialize a stored ProjectOrdinationResult row into the API shape."""
    if row is None:
        return ProjectUnifrac(status="absent")
    status = row.status  # type: ignore[attr-defined]
    if status in ("computing", "failed"):
        return ProjectUnifrac(
            status=status,
            n_samples=row.n_samples,  # type: ignore[attr-defined]
            error_message=row.error_message,  # type: ignore[attr-defined]
        )
    data = row.data or {}  # type: ignore[attr-defined]
    perm = data.get("permanova")
    return ProjectUnifrac(
        status="succeeded",
        method=data.get("method", "weighted_unifrac"),
        n_samples=data.get("n_samples", row.n_samples),  # type: ignore[attr-defined]
        proportion_explained=data.get("proportion_explained", []),
        points=[PcoaPoint(**p) for p in data.get("points", [])],
        permanova=PermanovaResult(**perm) if perm else None,
        message=data.get("message"),
        computed_at=data.get("computed_at"),
    )


@router.post("/{project_id}/unifrac", response_model=ProjectUnifrac, status_code=status.HTTP_202_ACCEPTED, summary="Enqueue weighted-UniFrac ordination")
async def request_unifrac(project_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> ProjectUnifrac:
    """Kick off the async worker that builds a shared tree and computes weighted
    UniFrac + PERMANOVA over the project's completed samples. Poll GET to read it.
    """
    row = await projects_service.request_unifrac(session, user=user, project_id=project_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return _unifrac_response(row)


@router.get("/{project_id}/unifrac", response_model=ProjectUnifrac, summary="Weighted-UniFrac ordination result")
async def get_unifrac(project_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> ProjectUnifrac:
    """Return the stored weighted-UniFrac result (status: absent/computing/succeeded/failed)."""
    project = await projects_service.get_project(session, user=user, project_id=project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    row = await projects_service.get_unifrac_result(session, project_id=project_id)
    return _unifrac_response(row)
