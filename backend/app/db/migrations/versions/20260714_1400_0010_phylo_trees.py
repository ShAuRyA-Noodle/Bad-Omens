"""Add phylo_trees (persist per-job Newick tree for rendering)

Revision ID: 0010_phylo_trees
Revises: 0009_project_ordination_results
Create Date: 2026-07-14 14:00:00.000000
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0010_phylo_trees"
down_revision: str | None = "0009_project_ordination_results"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "phylo_trees",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("method", sa.String(length=32), nullable=False),
        sa.Column("n_tips", sa.Integer(), nullable=False),
        sa.Column("faith_pd", sa.Float(), nullable=True),
        sa.Column("newick", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"],
            name=op.f("fk_phylo_trees_job_id_jobs"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_phylo_trees")),
        sa.UniqueConstraint("job_id", name=op.f("uq_phylo_trees_job_id")),
    )


def downgrade() -> None:
    op.drop_table("phylo_trees")
