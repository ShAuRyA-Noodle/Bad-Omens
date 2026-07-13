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
import uuid  # noqa: TC003 — runtime-resolved by SQLAlchemy Mapped[]
from datetime import datetime  # noqa: TC003 — runtime-resolved by SQLAlchemy Mapped[]
from typing import Any

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
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM as PgEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamped, UUIDPrimaryKey

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
    projects: Mapped[list[Project]] = relationship(
        "Project",
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


# ─── Projects ───────────────────────────────────────────────────────────


class Project(UUIDPrimaryKey, Timestamped, Base):
    """A study grouping multiple sample-analysis jobs.

    Enables cross-sample analysis (beta-diversity / PCoA, temporal trends) that
    a single job cannot express. Each Job optionally belongs to one Project;
    deleting a project detaches its jobs (project_id -> NULL) rather than
    deleting them.
    """

    __tablename__ = "projects"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship("User", back_populates="projects")
    jobs: Mapped[list[Job]] = relationship("Job", back_populates="project")


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
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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
    project: Mapped[Project | None] = relationship("Project", back_populates="jobs")
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
    integrity_index: Mapped[IntegrityIndex | None] = relationship(
        "IntegrityIndex",
        back_populates="job",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    ordination: Mapped[OrdinationResult | None] = relationship(
        "OrdinationResult",
        back_populates="job",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    conservation_result: Mapped[ConservationResult | None] = relationship(
        "ConservationResult",
        back_populates="job",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        # Hot path: list a user's jobs newest-first. Without this composite
        # index the query sorts on every page load.
        Index("ix_jobs_user_created", "user_id", "created_at"),
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
    dwc_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

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
    legal_flags: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
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
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    # NOT unique: two reproducible runs with identical inputs are *supposed*
    # to produce the same manifest_sha256. A unique constraint here would make
    # the documented byte-reproducibility guarantee crash the second insert.
    # Indexed for lookup/verification instead.
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    job: Mapped[Job] = relationship("Job", back_populates="provenance")


# ─── Ecosystem Integrity Index ──────────────────────────────────────────


class IntegrityIndex(UUIDPrimaryKey, Timestamped, Base):
    """Computed Ecosystem Integrity Index for a job (see docs/methods/eii.md).

    ``score``/``grade`` are nullable: a sample with nothing assessable yields a
    null score and Relict shows "not assessable" rather than a fabricated 0.
    ``components`` is the full, traceable breakdown also written into the signed
    manifest.
    """

    __tablename__ = "integrity_indices"

    job_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    version: Mapped[str] = mapped_column(String(16), nullable=False)
    score: Mapped[float | None] = mapped_column(Float)
    grade: Mapped[str | None] = mapped_column(String(4))
    assessed_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    components: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    job: Mapped[Job] = relationship("Job", back_populates="integrity_index")


# ─── Ordination ─────────────────────────────────────────────────────────


class OrdinationResult(UUIDPrimaryKey, Timestamped, Base):
    """UMAP k-mer composition map + HDBSCAN clusters for a job's ASVs.

    This is a *within-sample sequence-composition map* (UMAP on each ASV's
    k-mer frequency profile), NOT a multi-sample community ordination. It is
    persisted so the computed embedding — which is hashed into the job's signed
    manifest — can be retrieved and plotted, instead of being discarded with
    the workspace. ``data`` holds the full stage output (points + params).
    """

    __tablename__ = "ordination_results"

    job_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    method: Mapped[str] = mapped_column(String(32), nullable=False, default="umap-kmer")
    n_clusters: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    n_noise: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    job: Mapped[Job] = relationship("Job", back_populates="ordination")


# ─── Conservation result (per-job snapshot) ─────────────────────────────


class ConservationResult(UUIDPrimaryKey, Timestamped, Base):
    """Per-job conservation cross-reference snapshot.

    The global ``conservation_cache`` is a species-keyed cache shared across
    all tenants; serving a job's panel from it leaks one user's lookups into
    another's results and makes the panel diverge from the job's own signed
    manifest. This table stores the exact records this job produced, so the
    panel is tenant-isolated and reproducible. ``data`` holds the full
    conservation stage output (counts + per-species records).
    """

    __tablename__ = "conservation_results"

    job_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    job: Mapped[Job] = relationship("Job", back_populates="conservation_result")


# ─── Signing key ────────────────────────────────────────────────────────


class SigningKey(UUIDPrimaryKey, Timestamped, Base):
    """The server's Ed25519 keypair for signing provenance manifests.

    Generated once on first use and stored as a singleton (a partial unique
    index enforces at most one ``is_active`` row). The private key never leaves
    the server; the public key is served at ``GET /public-key`` and embedded in
    every manifest so any third party can verify a result offline.

    ``is_active`` allows future key rotation: a rotated-out key stays in the
    table (is_active=false) so manifests it signed remain verifiable.
    """

    __tablename__ = "signing_keys"

    algorithm: Mapped[str] = mapped_column(String(32), nullable=False, default="ed25519")
    private_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    public_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index(
            "uq_signing_keys_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )


__all__ = [
    "ASV",
    "Amplicon",
    "ConservationCache",
    "ConservationResult",
    "DiversityMetric",
    "IntegrityIndex",
    "Job",
    "JobStatus",
    "OrdinationResult",
    "Project",
    "Provenance",
    "RefreshSession",
    "Sample",
    "SigningKey",
    "Taxon",
    "User",
    "UserRole",
    "amplicon_enum",
    "job_status_enum",
    "user_role_enum",
]
