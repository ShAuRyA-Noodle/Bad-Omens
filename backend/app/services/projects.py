"""Project service — create/list/fetch multi-sample studies + attach jobs.

Every query is scoped to the authenticated user so projects and their jobs are
tenant-isolated.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, cast

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.db.models import Job, JobStatus, Project, ProjectOrdinationResult, User

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession

log = get_logger(__name__)

# RQ imports this by dotted path from the worker image.
UNIFRAC_ENTRYPOINT = "worker.project_ordination.compute_project_unifrac"
_UNIFRAC_METHOD = "weighted_unifrac"


async def create_project(
    session: AsyncSession, *, user: User, name: str, description: str | None
) -> Project:
    project = Project(user_id=user.id, name=name.strip(), description=description)
    session.add(project)
    await session.flush()
    return project


async def list_projects_with_counts(
    session: AsyncSession, *, user: User
) -> list[tuple[Project, int, int]]:
    """Return (project, job_count, succeeded_count) for the user's projects."""
    projects = list(
        await session.scalars(
            select(Project).where(Project.user_id == user.id).order_by(Project.created_at.desc())
        )
    )
    if not projects:
        return []

    rows = await session.execute(
        select(
            Job.project_id,
            func.count().label("total"),
            func.count().filter(Job.status == JobStatus.SUCCEEDED).label("succeeded"),
        )
        .where(Job.project_id.in_([p.id for p in projects]))
        .group_by(Job.project_id)
    )
    counts: dict[uuid.UUID, tuple[int, int]] = {
        pid: (total, succeeded) for pid, total, succeeded in rows
    }
    return [(p, *counts.get(p.id, (0, 0))) for p in projects]


async def get_project(
    session: AsyncSession, *, user: User, project_id: uuid.UUID
) -> Project | None:
    """Return the project (with jobs eager-loaded) iff owned by the user."""
    return cast(
        "Project | None",
        await session.scalar(
            select(Project)
            .where(Project.id == project_id, Project.user_id == user.id)
            .options(selectinload(Project.jobs))
        ),
    )


async def attach_job(
    session: AsyncSession, *, user: User, project_id: uuid.UUID, job_id: uuid.UUID
) -> Job | None:
    """Attach a job to a project; both must belong to the user. Returns the job."""
    project = await session.scalar(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if project is None:
        return None
    job = await session.get(Job, job_id)
    if job is None or job.user_id != user.id:
        return None
    job.project_id = project.id
    await session.flush()
    return job


async def get_unifrac_result(
    session: AsyncSession, *, project_id: uuid.UUID
) -> ProjectOrdinationResult | None:
    """Return the project's stored weighted-UniFrac result row, if any."""
    return await session.scalar(
        select(ProjectOrdinationResult).where(
            ProjectOrdinationResult.project_id == project_id,
            ProjectOrdinationResult.method == _UNIFRAC_METHOD,
        )
    )


async def request_unifrac(
    session: AsyncSession, *, user: User, project_id: uuid.UUID
) -> ProjectOrdinationResult | None:
    """Enqueue a weighted-UniFrac computation for the project (idempotent-ish).

    Upserts a single (project, weighted_unifrac) row to ``computing`` and pushes
    the worker job. Returns the row, or None if the project isn't the user's.
    A recompute overwrites the previous result.
    """
    project = await session.scalar(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    if project is None:
        return None

    row = await get_unifrac_result(session, project_id=project_id)
    if row is None:
        row = ProjectOrdinationResult(
            project_id=project_id, method=_UNIFRAC_METHOD, status="computing", n_samples=0,
        )
        session.add(row)
    else:
        row.status = "computing"
        row.error_message = None
    await session.flush()

    from app.services.queue import get_rq_queue

    get_rq_queue().enqueue(
        UNIFRAC_ENTRYPOINT,
        kwargs={"project_id": str(project_id), "result_id": str(row.id)},
        job_timeout="1h",
        result_ttl=86_400,
        failure_ttl=604_800,
    )
    log.info("project.unifrac_enqueued", project_id=str(project_id), result_id=str(row.id))
    return row


__all__ = [
    "attach_job",
    "create_project",
    "get_project",
    "get_unifrac_result",
    "list_projects_with_counts",
    "request_unifrac",
]
