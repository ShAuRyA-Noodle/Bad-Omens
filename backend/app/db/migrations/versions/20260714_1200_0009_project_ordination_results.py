"""Add project_ordination_results (async cross-sample UniFrac)

Revision ID: 0009_project_ordination_results
Revises: 0008_sample_paired_end
Create Date: 2026-07-14 12:00:00.000000
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0009_project_ordination_results"
down_revision: str | None = "0008_sample_paired_end"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_ordination_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("method", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("n_samples", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"],
            name=op.f("fk_project_ordination_results_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_ordination_results")),
        sa.UniqueConstraint("project_id", "method", name="uq_project_ordination_method"),
    )
    op.create_index(
        op.f("ix_project_ordination_results_project_id"),
        "project_ordination_results", ["project_id"], unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_project_ordination_results_project_id"),
        table_name="project_ordination_results",
    )
    op.drop_table("project_ordination_results")
