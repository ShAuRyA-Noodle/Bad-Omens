"""ORM models for the Relict platform.

Phase 1 tables:
    users                 — accounts
    refresh_sessions      — JWT refresh tokens for revocation
    jobs                  — one per analysis run
    samples               — one per uploaded FASTQ (paired-end = 2 rows)
    asvs                  — one per unique amplicon sequence variant
    taxa                  — taxonomy assignment for each ASV
    diversity_metrics     — per-sample alpha-diversity snapshot
    conservation_cache    — cached IUCN / GBIF lookups (filled in Phase 3)
    provenance            — signed pipeline manifests (filled in Phase 5)

All rows are keyed by UUIDv4 and carry created_at / updated_at. Every
foreign key is declared with ``ondelete="CASCADE"`` where a child row
has no meaning without its parent, and with ``RESTRICT`` otherwise.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamped, UUIDPrimaryKey

if TYPE_CHECKING:
    pass


# ─── Enums ──────────────────────────────────────────────────────────────


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Amplicon(str, enum.Enum):
    """Supported amplicon markers. New ones are opt-in per release."""

    MARKER_12S_MIFISH = "12S_MiFish"
    MARKER_COI_LERAY = "COI_Leray"
    MARKER_16S_V4 = "16S_V4"
    MARKER_18S_V9 = "18S_V9"
    MARKER_RBCL = "rbcL"
    MARKER_ITS2 = "ITS2"
    OTHER = "other"


# Postgres-native enum types. Using PgEnum keeps the constraint in the
# database so bad values can't slip in via raw SQL.
user_role_enum = PgEnum(
    UserRole, name="user_role", create_type=False, values_callable=lambda e: [v.value for v in e]
)
job_status_enum = PgEnum(
    JobStatus, name="job_status", create_type=False, values_callable=lambda e: [v.value for v in e]
)
amplicon_enum = PgEnum(
    Amplicon, name="amplicon", create_type=False, values_callable=lambda e: [v.value for v in e]
)


# ─── User + RefreshSession ──────────────────────────────────────────────


class User(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        user_role_enum, nullable=False, default=UserRole.USER
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    jobs: Mapped[list[Job]] = relationship(
        "Job",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    refresh_sessions: Mapped[list[RefreshSession]] = relationship(
        "RefreshSession",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_users_email_lower", "email", unique=True),
    )


class RefreshSession(UUIDPrimaryKey, Timestamped, Base):
    """A single JWT refresh token, persisted so we can revoke it.

    The token itself is not stored — only a SHA256 digest, so a DB leak
    cannot be used to forge sessions.
    """

    __tablename__ = "refresh_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    ip_address: Mapped[str | None] = mapped_column(String(45))  # IPv6-safe

    user: Mapped[User] = relationship("User", back_populates="refresh_sessions")


# ─── Jobs + Samples ─────────────────────────────────────────────────────


class Job(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "jobs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[JobStatus] = mapped_column(
        job_status_enum, nullable=False, default=JobStatus.QUEUED, index=True
    )
    amplicon: Mapped[Amplicon] = mapped_column(
        amplicon_enum, nullable=False, default=Amplicon.OTHER
    )

    # Parameter hash allows two runs with the same inputs + params to be
    # detected as equivalent. Used by the provenance manifest.
    parameter_hash: Mapped[str | None] = mapped_column(String(64))
    pipeline_version: Mapped[str | None] = mapped_column(String(32))

    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    # Opaque RQ job id so the worker side can be correlated to the DB row.
    rq_job_id: Mapped[str | None] = mapped_column(String(64), unique=True)

    user: Mapped[User] = relationship("User", back_populates="jobs")
    samples: Mapped[list[Sample]] = relationship(
        "Sample",
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    asvs: Mapped[list[ASV]] = relationship(
        "ASV",
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    provenance: Mapped[Provenance | None] = relationship(
        "Provenance",
        back_populates="job",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Sample(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "samples"

    job_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    s3_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)

    # Bioinformatics metadata populated in later phases.
    num_reads: Mapped[int | None] = mapped_column(Integer)
    read_length_mean: Mapped[float | None] = mapped_column(Float)
    primer_set: Mapped[str | None] = mapped_column(String(64))

    # Darwin Core–compatible sample metadata for citizen-science submissions.
    dwc_metadata: Mapped[dict | None] = mapped_column(JSONB)

    job: Mapped[Job] = relationship("Job", back_populates="samples")
    diversity_metric: Mapped[DiversityMetric | None] = relationship(
        "DiversityMetric",
        back_populates="sample",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint("size_bytes > 0", name="size_bytes_positive"),
    )


# ─── ASVs + Taxa ────────────────────────────────────────────────────────


class ASV(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "asvs"

    job_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sequence: Mapped[str] = mapped_column(Text, nullable=False)
    length: Mapped[int] = mapped_column(Integer, nullable=False)
    abundance: Mapped[int] = mapped_column(Integer, nullable=False)

    job: Mapped[Job] = relationship("Job", back_populates="asvs")
    taxon: Mapped[Taxon | None] = relationship(
        "Taxon",
        back_populates="asv",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("job_id", "sequence_sha256", name="asvs_job_sequence"),
        CheckConstraint("length > 0", name="length_positive"),
        CheckConstraint("abundance >= 0", name="abundance_non_negative"),
    )


class Taxon(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "taxa"

    asv_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("asvs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    kingdom: Mapped[str | None] = mapped_column(String(128))
    phylum: Mapped[str | None] = mapped_column(String(128))
    tax_class: Mapped[str | None] = mapped_column("class", String(128))
    tax_order: Mapped[str | None] = mapped_column("order", String(128))
    family: Mapped[str | None] = mapped_column(String(128))
    genus: Mapped[str | None] = mapped_column(String(128), index=True)
    species: Mapped[str | None] = mapped_column(String(256), index=True)
    confidence: Mapped[float | None] = mapped_column(Float)
    reference_db: Mapped[str | None] = mapped_column(String(64))
    reference_db_version: Mapped[str | None] = mapped_column(String(32))
    reference_accession: Mapped[str | None] = mapped_column(String(128))

    asv: Mapped[ASV] = relationship("ASV", back_populates="taxon")

    __table_args__ = (
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="confidence_bounded",
        ),
    )


# ─── Diversity metrics ──────────────────────────────────────────────────


class DiversityMetric(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "diversity_metrics"

    sample_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("samples.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    richness: Mapped[int | None] = mapped_column(Integer)
    shannon: Mapped[float | None] = mapped_column(Float)
    simpson: Mapped[float | None] = mapped_column(Float)
    chao1: Mapped[float | None] = mapped_column(Float)
    faith_pd: Mapped[float | None] = mapped_column(Float)
    evenness: Mapped[float | None] = mapped_column(Float)

    sample: Mapped[Sample] = relationship("Sample", back_populates="diversity_metric")


# ─── Conservation cache ─────────────────────────────────────────────────


class ConservationCache(UUIDPrimaryKey, Timestamped, Base):
    """Cached per-species lookups from GBIF / IUCN / invasive lists.

    Populated in Phase 3. TTL of 30 days is enforced at query time by
    checking ``fetched_at`` against ``now() - interval '30 days'``.
    """

    __tablename__ = "conservation_cache"

    species: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    gbif_key: Mapped[int | None] = mapped_column(BigInteger)
    gbif_occurrence_count: Mapped[int | None] = mapped_column(BigInteger)
    iucn_category: Mapped[str | None] = mapped_column(String(8))
    iucn_assessment_year: Mapped[int | None] = mapped_column(Integer)
    is_invasive: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    legal_flags: Mapped[dict | None] = mapped_column(JSONB)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("species", name="conservation_species"),
    )


# ─── Provenance ─────────────────────────────────────────────────────────


class Provenance(UUIDPrimaryKey, Timestamped, Base):
    """Signed manifest of a completed pipeline run.

    Populated in Phase 5. For Phase 1 we only need the schema in place
    so ``jobs.provenance`` can be serialized from the API.
    """

    __tablename__ = "provenance"

    job_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    manifest: Mapped[dict] = mapped_column(JSON, nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    job: Mapped[Job] = relationship("Job", back_populates="provenance")


__all__ = [
    "ASV",
    "Amplicon",
    "ConservationCache",
    "DiversityMetric",
    "Job",
    "JobStatus",
    "Provenance",
    "RefreshSession",
    "Sample",
    "Taxon",
    "User",
    "UserRole",
    "amplicon_enum",
    "job_status_enum",
    "user_role_enum",
]
