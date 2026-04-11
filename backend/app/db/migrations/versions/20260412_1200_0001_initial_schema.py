"""Initial schema — users, jobs, samples, asvs, taxa, diversity, conservation, provenance

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-04-12 12:00:00.000000
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


USER_ROLE_VALUES = ("user", "admin")
JOB_STATUS_VALUES = ("queued", "running", "succeeded", "failed", "cancelled")
AMPLICON_VALUES = (
    "12S_MiFish",
    "COI_Leray",
    "16S_V4",
    "18S_V9",
    "rbcL",
    "ITS2",
    "other",
)


def upgrade() -> None:
    # ─── Enum types ────────────────────────────────────────────────────
    user_role = postgresql.ENUM(*USER_ROLE_VALUES, name="user_role")
    job_status = postgresql.ENUM(*JOB_STATUS_VALUES, name="job_status")
    amplicon = postgresql.ENUM(*AMPLICON_VALUES, name="amplicon")
    user_role.create(op.get_bind(), checkfirst=True)
    job_status.create(op.get_bind(), checkfirst=True)
    amplicon.create(op.get_bind(), checkfirst=True)

    # ─── users ─────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            postgresql.ENUM(*USER_ROLE_VALUES, name="user_role", create_type=False),
            nullable=False,
            server_default="user",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index("ix_users_email_lower", "users", ["email"], unique=True)

    # ─── refresh_sessions ──────────────────────────────────────────────
    op.create_table(
        "refresh_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_sha256", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_refresh_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_sessions")),
        sa.UniqueConstraint("token_sha256", name=op.f("uq_refresh_sessions_token_sha256")),
    )
    op.create_index(
        op.f("ix_refresh_sessions_user_id"), "refresh_sessions", ["user_id"], unique=False
    )

    # ─── jobs ──────────────────────────────────────────────────────────
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(*JOB_STATUS_VALUES, name="job_status", create_type=False),
            nullable=False,
            server_default="queued",
        ),
        sa.Column(
            "amplicon",
            postgresql.ENUM(*AMPLICON_VALUES, name="amplicon", create_type=False),
            nullable=False,
            server_default="other",
        ),
        sa.Column("parameter_hash", sa.String(length=64), nullable=True),
        sa.Column("pipeline_version", sa.String(length=32), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("rq_job_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_jobs_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
        sa.UniqueConstraint("rq_job_id", name=op.f("uq_jobs_rq_job_id")),
    )
    op.create_index(op.f("ix_jobs_user_id"), "jobs", ["user_id"], unique=False)
    op.create_index(op.f("ix_jobs_status"), "jobs", ["status"], unique=False)

    # ─── samples ───────────────────────────────────────────────────────
    op.create_table(
        "samples",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("s3_key", sa.String(length=512), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("num_reads", sa.Integer(), nullable=True),
        sa.Column("read_length_mean", sa.Float(), nullable=True),
        sa.Column("primer_set", sa.String(length=64), nullable=True),
        sa.Column("dwc_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("size_bytes > 0", name=op.f("ck_samples_size_bytes_positive")),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_samples_job_id_jobs"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_samples")),
        sa.UniqueConstraint("s3_key", name=op.f("uq_samples_s3_key")),
    )
    op.create_index(op.f("ix_samples_job_id"), "samples", ["job_id"], unique=False)
    op.create_index(op.f("ix_samples_sha256"), "samples", ["sha256"], unique=False)

    # ─── asvs ──────────────────────────────────────────────────────────
    op.create_table(
        "asvs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence_sha256", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Text(), nullable=False),
        sa.Column("length", sa.Integer(), nullable=False),
        sa.Column("abundance", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length > 0", name=op.f("ck_asvs_length_positive")),
        sa.CheckConstraint("abundance >= 0", name=op.f("ck_asvs_abundance_non_negative")),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_asvs_job_id_jobs"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_asvs")),
        sa.UniqueConstraint("job_id", "sequence_sha256", name="asvs_job_sequence"),
    )
    op.create_index(op.f("ix_asvs_job_id"), "asvs", ["job_id"], unique=False)
    op.create_index(op.f("ix_asvs_sequence_sha256"), "asvs", ["sequence_sha256"], unique=False)

    # ─── taxa ──────────────────────────────────────────────────────────
    op.create_table(
        "taxa",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asv_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kingdom", sa.String(length=128), nullable=True),
        sa.Column("phylum", sa.String(length=128), nullable=True),
        sa.Column("class", sa.String(length=128), nullable=True),
        sa.Column("order", sa.String(length=128), nullable=True),
        sa.Column("family", sa.String(length=128), nullable=True),
        sa.Column("genus", sa.String(length=128), nullable=True),
        sa.Column("species", sa.String(length=256), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("reference_db", sa.String(length=64), nullable=True),
        sa.Column("reference_db_version", sa.String(length=32), nullable=True),
        sa.Column("reference_accession", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name=op.f("ck_taxa_confidence_bounded"),
        ),
        sa.ForeignKeyConstraint(
            ["asv_id"], ["asvs.id"], name=op.f("fk_taxa_asv_id_asvs"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_taxa")),
        sa.UniqueConstraint("asv_id", name=op.f("uq_taxa_asv_id")),
    )
    op.create_index(op.f("ix_taxa_genus"), "taxa", ["genus"], unique=False)
    op.create_index(op.f("ix_taxa_species"), "taxa", ["species"], unique=False)

    # ─── diversity_metrics ─────────────────────────────────────────────
    op.create_table(
        "diversity_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sample_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("richness", sa.Integer(), nullable=True),
        sa.Column("shannon", sa.Float(), nullable=True),
        sa.Column("simpson", sa.Float(), nullable=True),
        sa.Column("chao1", sa.Float(), nullable=True),
        sa.Column("faith_pd", sa.Float(), nullable=True),
        sa.Column("evenness", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["sample_id"],
            ["samples.id"],
            name=op.f("fk_diversity_metrics_sample_id_samples"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_diversity_metrics")),
        sa.UniqueConstraint("sample_id", name=op.f("uq_diversity_metrics_sample_id")),
    )

    # ─── conservation_cache ────────────────────────────────────────────
    op.create_table(
        "conservation_cache",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("species", sa.String(length=256), nullable=False),
        sa.Column("gbif_key", sa.BigInteger(), nullable=True),
        sa.Column("gbif_occurrence_count", sa.BigInteger(), nullable=True),
        sa.Column("iucn_category", sa.String(length=8), nullable=True),
        sa.Column("iucn_assessment_year", sa.Integer(), nullable=True),
        sa.Column("is_invasive", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("legal_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conservation_cache")),
        sa.UniqueConstraint("species", name="conservation_species"),
    )
    op.create_index(
        op.f("ix_conservation_cache_species"), "conservation_cache", ["species"], unique=False
    )

    # ─── provenance ────────────────────────────────────────────────────
    op.create_table(
        "provenance",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_provenance_job_id_jobs"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_provenance")),
        sa.UniqueConstraint("job_id", name=op.f("uq_provenance_job_id")),
        sa.UniqueConstraint("manifest_sha256", name=op.f("uq_provenance_manifest_sha256")),
    )


def downgrade() -> None:
    op.drop_table("provenance")
    op.drop_table("conservation_cache")
    op.drop_table("diversity_metrics")
    op.drop_table("taxa")
    op.drop_table("asvs")
    op.drop_table("samples")
    op.drop_table("jobs")
    op.drop_table("refresh_sessions")
    op.drop_table("users")

    postgresql.ENUM(name="amplicon").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="job_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="user_role").drop(op.get_bind(), checkfirst=True)
