"""Result routes — ASVs, taxonomy, diversity, ordination for a completed job.

All endpoints are scoped to the authenticated user's own jobs (404 for
cross-user access). Results are only available for jobs with status
``succeeded`` — querying an in-progress or failed job returns 404 with
a clear message.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, SessionDep
from app.db.models import (
    ASV,
    ConservationCache,
    ConservationResult,
    DiversityMetric,
    IntegrityIndex,
    Job,
    JobStatus,
    OrdinationResult,
    Provenance,
    Sample,
)
from app.schemas.conservation import ConservationPublic, ConservationSummary
from app.schemas.provenance import ProvenancePublic
from app.schemas.results import (
    ASVWithTaxon,
    DiversityPublic,
    EIIComponentPublic,
    IntegrityIndexPublic,
    JobResultsSummary,
    OrdinationPoint,
    OrdinationResponse,
    TaxonPublic,
)

router = APIRouter(prefix="/jobs/{job_id}", tags=["results"])


async def _get_succeeded_job(
    session: SessionDep, job_id: uuid.UUID, user: CurrentUser
) -> Job:
    """Helper that validates ownership and succeeded status."""
    job = await session.get(Job, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status != JobStatus.SUCCEEDED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job is not complete (status: {job.status.value}). Results are only available for succeeded jobs.",
        )
    return job


@router.get(
    "/summary",
    response_model=JobResultsSummary,
    summary="High-level result summary for a completed job",
)
async def job_summary(
    job_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> JobResultsSummary:
    job = await _get_succeeded_job(session, job_id, user)

    stmt = (
        select(ASV)
        .where(ASV.job_id == job.id)
        .options(selectinload(ASV.taxon))
    )
    asvs_with_tax = list(await session.scalars(stmt))
    n_assigned = sum(1 for a in asvs_with_tax if a.taxon is not None)

    samples_result = await session.scalars(select(Sample).where(Sample.job_id == job.id))
    sample = list(samples_result)[0] if samples_result else None

    diversity = None
    if sample:
        diversity_row = await session.scalar(
            select(DiversityMetric).where(DiversityMetric.sample_id == sample.id)
        )
        if diversity_row:
            diversity = DiversityPublic.model_validate(diversity_row)

    return JobResultsSummary(
        job_id=job.id,
        status=job.status.value,
        pipeline_version=job.pipeline_version,
        parameter_hash=job.parameter_hash,
        n_asvs=len(asvs_with_tax),
        n_assigned=n_assigned,
        diversity=diversity,
        amplicon=job.amplicon.value,
        dwc_metadata=sample.dwc_metadata if sample else None,
    )


@router.get(
    "/asvs",
    response_model=list[ASVWithTaxon],
    summary="All ASVs with their taxonomy assignments",
)
async def job_asvs(
    job_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    limit: int = Query(500, ge=1, le=2000, description="Max ASVs to return (abundance-desc)."),
    offset: int = Query(0, ge=0),
) -> list[ASVWithTaxon]:
    """Return this job's ASVs (most abundant first), bounded + paginated.

    A single sample can yield tens of thousands of ASVs; returning them all with
    full sequences is a multi-MB payload that freezes the browser, so the result
    is capped (default 500) and paginated with limit/offset.
    """
    job = await _get_succeeded_job(session, job_id, user)

    stmt = (
        select(ASV)
        .where(ASV.job_id == job.id)
        .options(selectinload(ASV.taxon))
        .order_by(ASV.abundance.desc())
        .limit(limit)
        .offset(offset)
    )
    asvs = list(await session.scalars(stmt))

    return [
        ASVWithTaxon(
            id=asv.id,
            sequence_sha256=asv.sequence_sha256,
            sequence=asv.sequence,
            length=asv.length,
            abundance=asv.abundance,
            taxon=TaxonPublic.model_validate(asv.taxon) if asv.taxon else None,
        )
        for asv in asvs
    ]


@router.get(
    "/diversity",
    response_model=DiversityPublic | None,
    summary="Alpha-diversity metrics for the first sample in this job",
)
async def job_diversity(
    job_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> DiversityPublic | None:
    job = await _get_succeeded_job(session, job_id, user)

    sample = await session.scalar(select(Sample).where(Sample.job_id == job.id))
    if sample is None:
        return None

    dm = await session.scalar(
        select(DiversityMetric).where(DiversityMetric.sample_id == sample.id)
    )
    if dm is None:
        return None

    return DiversityPublic.model_validate(dm)


@router.get(
    "/ordination",
    response_model=OrdinationResponse,
    summary="ASV composition map (UMAP on k-mer profiles) + HDBSCAN clusters",
)
async def job_ordination(
    job_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> OrdinationResponse:
    """Return the persisted UMAP composition map for this job's ASVs.

    Note: this is a *within-sample* sequence-composition map (UMAP on each
    ASV's k-mer frequency), not a multi-sample community ordination. The
    embedding is the exact one hashed into the job's signed manifest.
    """
    job = await _get_succeeded_job(session, job_id, user)

    row = await session.scalar(
        select(OrdinationResult).where(OrdinationResult.job_id == job.id)
    )
    if row is None:
        return OrdinationResponse(
            n_asvs=0,
            n_clusters=0,
            n_noise_points=0,
            skipped=True,
            reason="No composition map — UMAP needs at least 3 ASVs.",
        )

    data = row.data
    points = [OrdinationPoint(**p) for p in data.get("points", [])]
    return OrdinationResponse(
        n_asvs=len(points),
        n_clusters=row.n_clusters,
        n_noise_points=row.n_noise,
        skipped=False,
        points=points,
        umap_params=data.get("umap_params"),
        hdbscan_params=data.get("hdbscan_params"),
    )


@router.get(
    "/conservation",
    response_model=ConservationSummary,
    summary="Conservation status cross-reference (GBIF + IUCN Red List)",
)
async def job_conservation(
    job_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> ConservationSummary:
    """Return per-species conservation data from GBIF + IUCN Red List.

    This is the novel contribution of Relict — no existing open eDNA
    tool automates this cross-referencing step. Each detected species
    is looked up against the GBIF backbone taxonomy for occurrence
    counts and the IUCN Red List for conservation status.
    """
    job = await _get_succeeded_job(session, job_id, user)

    # Prefer the tenant-isolated per-job snapshot. Serving from the shared,
    # species-keyed cache leaked other users' lookups into this panel and let it
    # diverge from the job's own signed manifest (V-02).
    snap = await session.scalar(
        select(ConservationResult).where(ConservationResult.job_id == job.id)
    )
    if snap is not None:
        data = snap.data
        records = [
            ConservationPublic(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, f"{job.id}:{r.get('species', '')}"),
                species=str(r.get("species", "")),
                gbif_key=r.get("gbif_key"),
                gbif_occurrence_count=r.get("gbif_occurrence_count"),
                iucn_category=r.get("iucn_category"),
                iucn_assessment_year=r.get("iucn_assessment_year"),
                is_invasive=bool(r.get("is_invasive") or False),
                legal_flags={
                    "gbif_matched_name": r.get("gbif_matched_name"),
                    "iucn_category_full": r.get("iucn_category_full"),
                    "iucn_population_trend": r.get("iucn_population_trend"),
                    "error": r.get("error"),
                },
                fetched_at=snap.created_at,
            )
            for r in data.get("records", [])
        ]
        return ConservationSummary(
            job_id=job.id,
            species_queried=int(data.get("species_queried", len(records))),
            species_with_gbif=int(data.get("species_with_gbif", 0)),
            species_with_iucn=int(data.get("species_with_iucn", 0)),
            threatened_count=int(data.get("threatened_count", 0)),
            lookup_failed_count=int(data.get("lookup_failed_count", 0)),
            api_degraded=bool(data.get("api_degraded", False)),
            records=records,
        )

    # Fallback for jobs run before per-job snapshots existed: reconstruct from
    # the shared cache (only for historical jobs; new jobs always snapshot).
    stmt = select(ASV).where(ASV.job_id == job.id).options(selectinload(ASV.taxon))
    asvs = list(await session.scalars(stmt))
    species_names: set[str] = set()
    for asv in asvs:
        if asv.taxon:
            genus = asv.taxon.genus or ""
            species = asv.taxon.species or ""
            if genus:
                full = f"{genus} {species}".strip() if species else genus
                species_names.add(full)

    legacy_records: list[ConservationPublic] = []
    if species_names:
        cached = list(
            await session.scalars(
                select(ConservationCache).where(ConservationCache.species.in_(species_names))
            )
        )
        legacy_records = [ConservationPublic.model_validate(c) for c in cached]

    return ConservationSummary(
        job_id=job.id,
        species_queried=len(species_names),
        species_with_gbif=sum(1 for r in legacy_records if r.gbif_key),
        species_with_iucn=sum(1 for r in legacy_records if r.iucn_category),
        threatened_count=sum(
            1 for r in legacy_records if r.iucn_category in ("VU", "EN", "CR", "EW", "EX")
        ),
        records=legacy_records,
    )


@router.get(
    "/provenance",
    response_model=ProvenancePublic,
    summary="Signed provenance manifest — reproducibility receipt for this run",
)
async def job_provenance(
    job_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> ProvenancePublic:
    """Return the signed provenance manifest for a completed job.

    The manifest records every input hash, tool version, reference
    database version, parameter, and output hash — so the entire
    analysis can be independently reproduced and verified.

    The ``signature`` field is a SHA256 hash of the canonical manifest
    JSON. Verify it by recomputing the hash yourself.
    """
    job = await _get_succeeded_job(session, job_id, user)

    prov = await session.scalar(
        select(Provenance).where(Provenance.job_id == job.id)
    )
    if prov is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No provenance manifest found for this job. The job may have been run before Phase 5.",
        )

    return ProvenancePublic.model_validate(prov)


@router.get(
    "/integrity",
    response_model=IntegrityIndexPublic,
    summary="Ecosystem Integrity Index for a completed job",
)
async def job_integrity(
    job_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> IntegrityIndexPublic:
    """Return the job's EII with its full, traceable component breakdown."""
    job = await _get_succeeded_job(session, job_id, user)
    row = await session.scalar(
        select(IntegrityIndex).where(IntegrityIndex.job_id == job.id)
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No integrity index computed for this job.",
        )
    raw_components = row.components.get("components", []) if isinstance(row.components, dict) else []
    return IntegrityIndexPublic(
        job_id=job.id,
        version=row.version,
        score=row.score,
        grade=row.grade,
        assessed_weight=row.assessed_weight,
        components=[EIIComponentPublic(**c) for c in raw_components],
    )
