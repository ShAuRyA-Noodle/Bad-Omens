"""Add composite index jobs(user_id, created_at) for the jobs-list hot path

Revision ID: 0006_jobs_user_created_index
Revises: 0005_conservation_result
Create Date: 2026-06-30 20:00:00.000000
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0006_jobs_user_created_index"
down_revision: str | None = "0005_conservation_result"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_jobs_user_created", "jobs", ["user_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_jobs_user_created", table_name="jobs")
