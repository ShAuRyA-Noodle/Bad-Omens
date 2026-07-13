"""Add projects table + jobs.project_id (multi-sample grouping)

Revision ID: 0007_projects
Revises: 0006_jobs_user_created_index
Create Date: 2026-07-01 10:00:00.000000
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0007_projects"
down_revision: str | None = "0006_jobs_user_created_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_projects_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
    )
    op.create_index(op.f("ix_projects_user_id"), "projects", ["user_id"], unique=False)

    op.add_column("jobs", sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        op.f("fk_jobs_project_id_projects"), "jobs", "projects",
        ["project_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index(op.f("ix_jobs_project_id"), "jobs", ["project_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_jobs_project_id"), table_name="jobs")
    op.drop_constraint(op.f("fk_jobs_project_id_projects"), "jobs", type_="foreignkey")
    op.drop_column("jobs", "project_id")
    op.drop_index(op.f("ix_projects_user_id"), table_name="projects")
    op.drop_table("projects")
