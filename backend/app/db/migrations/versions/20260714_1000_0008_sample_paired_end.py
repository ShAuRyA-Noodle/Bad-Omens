"""Add paired-end reverse-reads columns to samples (R2 mate)

Revision ID: 0008_sample_paired_end
Revises: 0007_projects
Create Date: 2026-07-14 10:00:00.000000
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0008_sample_paired_end"
down_revision: str | None = "0007_projects"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("samples", sa.Column("filename_r2", sa.String(length=512), nullable=True))
    op.add_column("samples", sa.Column("s3_key_r2", sa.String(length=512), nullable=True))
    op.add_column("samples", sa.Column("sha256_r2", sa.String(length=64), nullable=True))
    op.add_column("samples", sa.Column("size_bytes_r2", sa.BigInteger(), nullable=True))
    # s3_key_r2 is unique like s3_key (multiple NULLs allowed in Postgres).
    op.create_unique_constraint(op.f("uq_samples_s3_key_r2"), "samples", ["s3_key_r2"])
    op.create_index(op.f("ix_samples_sha256_r2"), "samples", ["sha256_r2"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_samples_sha256_r2"), table_name="samples")
    op.drop_constraint(op.f("uq_samples_s3_key_r2"), "samples", type_="unique")
    op.drop_column("samples", "size_bytes_r2")
    op.drop_column("samples", "sha256_r2")
    op.drop_column("samples", "s3_key_r2")
    op.drop_column("samples", "filename_r2")
