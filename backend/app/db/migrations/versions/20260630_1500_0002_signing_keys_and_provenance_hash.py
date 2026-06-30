"""Add signing_keys table; drop UNIQUE on provenance.manifest_sha256

Two reproducible runs with identical inputs are supposed to produce the same
manifest_sha256, so a UNIQUE constraint on it would crash the second insert.
We replace it with a plain index. We also add the singleton signing_keys
table that holds the server's Ed25519 keypair used to sign manifests.

Revision ID: 0002_signing_keys
Revises: 0001_initial_schema
Create Date: 2026-06-30 15:00:00.000000
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0002_signing_keys"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ─── signing_keys ──────────────────────────────────────────────────
    op.create_table(
        "signing_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("algorithm", sa.String(length=32), nullable=False),
        sa.Column("private_key", sa.LargeBinary(), nullable=False),
        sa.Column("public_key", sa.LargeBinary(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_signing_keys")),
    )
    # At most one active key (singleton). Partial unique index so rotated-out
    # keys (is_active=false) can coexist for verifying older manifests.
    op.create_index(
        "uq_signing_keys_active",
        "signing_keys",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    # ─── provenance.manifest_sha256: UNIQUE → indexed ──────────────────
    op.drop_constraint(
        op.f("uq_provenance_manifest_sha256"), "provenance", type_="unique"
    )
    op.create_index(
        op.f("ix_provenance_manifest_sha256"),
        "provenance",
        ["manifest_sha256"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_provenance_manifest_sha256"), table_name="provenance")
    op.create_unique_constraint(
        op.f("uq_provenance_manifest_sha256"), "provenance", ["manifest_sha256"]
    )
    op.drop_index("uq_signing_keys_active", table_name="signing_keys")
    op.drop_table("signing_keys")
