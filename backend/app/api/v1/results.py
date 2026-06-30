"""Result routes — ASVs, taxonomy, diversity, ordination for a completed job.

All endpoints are scoped to the authenticated user's own jobs (404 for
cross-user access). Results are only available for jobs with status
``succeeded`` — querying an in-progress or failed job returns 404 with
a clear message.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, SessionDep
from app.db.models import (
    ASV,
    ConservationCache,
    DiversityMetric,
    Job,
    JobStatus,
    Provenance,
    Sample,
)
from app.schemas.conservation import ConservationPublic, ConservationSummary
from app.schemas.provenance import ProvenancePublic
from app.schemas.results import (
    ASVWithTaxon,
    DiversityPublic,
    JobResultsSummary,
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
) -> list[ASVWithTaxon]:
    job = await _get_succeeded_job(session, job_id, user)

    stmt = (
        select(ASV)
        .where(ASV.job_id == job.id)
        .options(selectinload(ASV.taxon))
        .order_by(ASV.abundance.desc())
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
    summary="UMAP 2D coordinates + HDBSCAN cluster labels",
)
async def job_ordination(
    job_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> OrdinationResponse:
    """Return the ordination data from the job's workspace.

    The ordination JSON is stored in MinIO alongside the job's other
    outputs. For Phase 2 we read it from the workspace before cleanup;
    in Phase 5 this will be persisted to object storage + the provenance
    manifest.

    For now, if the job has completed but the ordination wasn't stored
    persistently yet, we return an empty response.
    """
    _ = await _get_succeeded_job(session, job_id, user)

    return OrdinationResponse(
        n_asvs=0,
        n_clusters=0,
        n_noise_points=0,
        skipped=True,
        reason="Ordination data is computed during the pipeline run. Persistent storage lands in Phase 5.",
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

    # Get all species names from the job's ASVs via their taxon assignments
    stmt = (
        select(ASV)
        .where(ASV.job_id == job.id)
        .options(selectinload(ASV.taxon))
    )
    asvs = list(await session.scalars(stmt))

    species_names: set[str] = set()
    for asv in asvs:
        if asv.taxon:
            genus = asv.taxon.genus or ""
            species = asv.taxon.species or ""
            if genus:
                full = f"{genus} {species}".strip() if species else genus
                species_names.add(full)

    # Look up cached conservation records
    records: list[ConservationPublic] = []
    if species_names:
        stmt_cons = select(ConservationCache).where(
            ConservationCache.species.in_(species_names)
        )
        cached = list(await session.scalars(stmt_cons))
        records = [ConservationPublic.model_validate(c) for c in cached]

    return ConservationSummary(
        job_id=job.id,
        species_queried=len(species_names),
        species_with_gbif=sum(1 for r in records if r.gbif_key),
        species_with_iucn=sum(1 for r in records if r.iucn_category),
        threatened_count=sum(
            1 for r in records if r.iucn_category in ("VU", "EN", "CR", "EW", "EX")
        ),
        records=records,
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
