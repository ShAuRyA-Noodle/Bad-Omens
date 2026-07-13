"""Add conservation_results table (per-job conservation snapshot)

Revision ID: 0005_conservation_result
Revises: 0004_ordination
Create Date: 2026-06-30 19:00:00.000000
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0005_conservation_result"
down_revision: str | None = "0004_ordination"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conservation_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"],
            name=op.f("fk_conservation_results_job_id_jobs"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conservation_results")),
        sa.UniqueConstraint("job_id", name=op.f("uq_conservation_results_job_id")),
    )


def downgrade() -> None:
    op.drop_table("conservation_results")
