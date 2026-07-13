"""Project service — create/list/fetch multi-sample studies + attach jobs.

Every query is scoped to the authenticated user so projects and their jobs are
tenant-isolated.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, cast

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.db.models import Job, JobStatus, Project, User

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


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


__all__ = ["attach_job", "create_project", "get_project", "list_projects_with_counts"]
