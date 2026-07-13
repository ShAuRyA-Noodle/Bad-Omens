"""Add ordination_results table (persist the UMAP composition map)

Revision ID: 0004_ordination
Revises: 0003_integrity_index
Create Date: 2026-06-30 18:00:00.000000
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0004_ordination"
down_revision: str | None = "0003_integrity_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ordination_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("method", sa.String(length=32), nullable=False),
        sa.Column("n_clusters", sa.Integer(), nullable=False),
        sa.Column("n_noise", sa.Integer(), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"],
            name=op.f("fk_ordination_results_job_id_jobs"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ordination_results")),
        sa.UniqueConstraint("job_id", name=op.f("uq_ordination_results_job_id")),
    )


def downgrade() -> None:
    op.drop_table("ordination_results")
