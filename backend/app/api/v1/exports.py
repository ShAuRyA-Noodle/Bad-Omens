"""Export routes — DwC-A, CSV, and future BIOM/QIIME2 exports.

These endpoints let users download their pipeline results in standard
formats that can be submitted to data portals (GBIF via DwC-A) or
analyzed in downstream tools (phyloseq, QIIME2).
"""
from __future__ import annotations

import csv
import io
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
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
from app.services.dwca import generate_dwca
from app.services.report import generate_html_report

router = APIRouter(prefix="/jobs/{job_id}/export", tags=["exports"])


async def _get_succeeded_job(
    session: SessionDep, job_id: uuid.UUID, user: CurrentUser
) -> Job:
    job = await session.get(Job, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.status != JobStatus.SUCCEEDED:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job status is {job.status.value}. Exports are only available for succeeded jobs.",
        )
    return job


@router.get(
    "/dwca",
    summary="Download a Darwin Core Archive (ZIP) for GBIF submission",
    response_class=Response,
)
async def export_dwca(
    job_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> Response:
    """Generate and download a GBIF-compatible Darwin Core Archive.

    The archive contains:
    - ``occurrence.txt`` — one row per ASV with Darwin Core terms
    - ``dna-derived-data.txt`` — eDNA-specific extension fields
    - ``eml.xml`` — dataset-level metadata
    - ``meta.xml`` — DwC-A descriptor

    This file can be submitted directly to a GBIF IPT or any other
    DwC-A-compatible data portal.
    """
    job = await _get_succeeded_job(session, job_id, user)

    stmt = (
        select(ASV)
        .where(ASV.job_id == job.id)
        .options(selectinload(ASV.taxon))
        .order_by(ASV.abundance.desc())
    )
    asvs = list(await session.scalars(stmt))

    sample = await session.scalar(select(Sample).where(Sample.job_id == job.id))
    sample_metadata = {}
    if sample and sample.dwc_metadata:
        sample_metadata = sample.dwc_metadata

    asv_dicts = []
    for asv in asvs:
        d = {
            "sequence": asv.sequence,
            "abundance": asv.abundance,
            "length": asv.length,
            "sequence_sha256": asv.sequence_sha256,
        }
        if asv.taxon:
            d["taxon"] = {
                "kingdom": asv.taxon.kingdom,
                "phylum": asv.taxon.phylum,
                "tax_class": asv.taxon.tax_class,
                "tax_order": asv.taxon.tax_order,
                "family": asv.taxon.family,
                "genus": asv.taxon.genus,
                "species": asv.taxon.species,
            }
        asv_dicts.append(d)

    archive_bytes = generate_dwca(
        job_id=job.id,
        asvs=asv_dicts,
        sample_metadata=sample_metadata,
        pipeline_version=job.pipeline_version or "unknown",
        parameter_hash=job.parameter_hash,
    )

    filename = f"relict_dwca_{job.id}.zip"
    return Response(
        content=archive_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/csv",
    summary="Download ASVs + taxonomy as a simple CSV",
    response_class=Response,
)
async def export_csv(
    job_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> Response:
    """Download a flat CSV with one row per ASV, including taxonomy."""
    job = await _get_succeeded_job(session, job_id, user)

    stmt = (
        select(ASV)
        .where(ASV.job_id == job.id)
        .options(selectinload(ASV.taxon))
        .order_by(ASV.abundance.desc())
    )
    asvs = list(await session.scalars(stmt))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "asv_id", "sequence_sha256", "sequence", "length", "abundance",
        "kingdom", "phylum", "class", "order", "family", "genus", "species",
        "confidence", "reference_db",
    ])

    for asv in asvs:
        tax = asv.taxon
        writer.writerow([
            str(asv.id),
            asv.sequence_sha256,
            asv.sequence,
            asv.length,
            asv.abundance,
            tax.kingdom if tax else "",
            tax.phylum if tax else "",
            tax.tax_class if tax else "",
            tax.tax_order if tax else "",
            tax.family if tax else "",
            tax.genus if tax else "",
            tax.species if tax else "",
            tax.confidence if tax else "",
            tax.reference_db if tax else "",
        ])

    csv_bytes = output.getvalue().encode("utf-8")
    filename = f"relict_asvs_{job.id}.csv"
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/biom",
    summary="Download ASV table as BIOM format (for QIIME2 / phyloseq)",
    response_class=Response,
)
async def export_biom(
    job_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> Response:
    """Download the ASV abundance table in BIOM 2.1 JSON format.

    BIOM (Biological Observation Matrix) is the standard interchange
    format for microbiome data. The exported file can be imported into
    QIIME2, phyloseq, or any other BIOM-compatible tool.
    """
    import json as json_mod

    job = await _get_succeeded_job(session, job_id, user)

    stmt = (
        select(ASV)
        .where(ASV.job_id == job.id)
        .options(selectinload(ASV.taxon))
        .order_by(ASV.abundance.desc())
    )
    asvs = list(await session.scalars(stmt))

    sample_obj = await session.scalar(select(Sample).where(Sample.job_id == job.id))
    sample_id = sample_obj.filename if sample_obj else str(job.id)

    rows = []
    for _i, asv in enumerate(asvs):
        tax = asv.taxon
        lineage = ""
        if tax:
            parts = [
                f"k__{tax.kingdom or ''}", f"p__{tax.phylum or ''}",
                f"c__{tax.tax_class or ''}", f"o__{tax.tax_order or ''}",
                f"f__{tax.family or ''}", f"g__{tax.genus or ''}",
                f"s__{tax.species or ''}",
            ]
            lineage = "; ".join(parts)

        rows.append({
            "id": asv.sequence_sha256[:16],
            "metadata": {"taxonomy": lineage, "sequence": asv.sequence},
            "data": [asv.abundance],
        })

    biom_data = {
        "id": str(job.id),
        "format": "Biological Observation Matrix 2.1.0",
        "format_url": "http://biom-format.org",
        "generated_by": f"Relict v{job.pipeline_version or 'unknown'}",
        "type": "OTU table",
        "matrix_type": "dense",
        "matrix_element_type": "int",
        "shape": [len(rows), 1],
        "rows": [{"id": r["id"], "metadata": r["metadata"]} for r in rows],
        "columns": [{"id": sample_id, "metadata": None}],
        "data": [r["data"] for r in rows],
    }

    biom_bytes = json_mod.dumps(biom_data, indent=2).encode("utf-8")
    filename = f"relict_biom_{job.id}.json"
    return Response(
        content=biom_bytes,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/report",
    summary="Download a comprehensive HTML analysis report",
    response_class=Response,
)
async def export_report(
    job_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> Response:
    """Generate a self-contained HTML report with all pipeline results.

    The report includes input summary, diversity metrics, ASV table with
    taxonomy, conservation cross-reference with IUCN badges, and the full
    provenance manifest. It renders in any browser and prints cleanly.
    """
    job = await _get_succeeded_job(session, job_id, user)

    stmt = (
        select(ASV)
        .where(ASV.job_id == job.id)
        .options(selectinload(ASV.taxon))
        .order_by(ASV.abundance.desc())
    )
    asvs_db = list(await session.scalars(stmt))

    sample = await session.scalar(select(Sample).where(Sample.job_id == job.id))

    div_row = None
    if sample:
        div_row = await session.scalar(
            select(DiversityMetric).where(DiversityMetric.sample_id == sample.id)
        )

    prov_row = await session.scalar(
        select(Provenance).where(Provenance.job_id == job.id)
    )

    species_names: set[str] = set()
    asv_dicts = []
    for asv in asvs_db:
        d: dict[str, Any] = {
            "sequence": asv.sequence,
            "abundance": asv.abundance,
            "length": asv.length,
            "sequence_sha256": asv.sequence_sha256,
        }
        if asv.taxon:
            d["taxon"] = {
                "kingdom": asv.taxon.kingdom,
                "phylum": asv.taxon.phylum,
                "tax_class": asv.taxon.tax_class,
                "tax_order": asv.taxon.tax_order,
                "family": asv.taxon.family,
                "genus": asv.taxon.genus,
                "species": asv.taxon.species,
                "confidence": asv.taxon.confidence,
            }
            g = asv.taxon.genus or ""
            s = asv.taxon.species or ""
            if g:
                species_names.add(f"{g} {s}".strip() if s else g)
        asv_dicts.append(d)

    cons_data: dict[str, Any] = {"species_queried": 0, "species_with_gbif": 0, "species_with_iucn": 0, "threatened_count": 0, "records": []}
    if species_names:
        cached = list(await session.scalars(
            select(ConservationCache).where(ConservationCache.species.in_(species_names))
        ))
        cons_data["species_queried"] = len(species_names)
        cons_data["species_with_gbif"] = sum(1 for c in cached if c.gbif_key)
        cons_data["species_with_iucn"] = sum(1 for c in cached if c.iucn_category)
        cons_data["threatened_count"] = sum(1 for c in cached if c.iucn_category in ("VU", "EN", "CR", "EW", "EX"))
        cons_data["records"] = [
            {
                "species": c.species,
                "gbif_key": c.gbif_key,
                "gbif_occurrence_count": c.gbif_occurrence_count,
                "iucn_category": c.iucn_category,
                "is_invasive": c.is_invasive,
                "legal_flags": c.legal_flags,
            }
            for c in cached
        ]

    html = generate_html_report(
        job_id=str(job.id),
        pipeline_version=job.pipeline_version or "unknown",
        parameter_hash=job.parameter_hash or "",
        asvs=asv_dicts,
        diversity={
            "shannon": div_row.shannon if div_row else None,
            "simpson": div_row.simpson if div_row else None,
            "richness": div_row.richness if div_row else None,
            "chao1": div_row.chao1 if div_row else None,
            "evenness": div_row.evenness if div_row else None,
        },
        conservation=cons_data,
        provenance={
            "manifest": prov_row.manifest if prov_row else {},
            "manifest_sha256": prov_row.manifest_sha256 if prov_row else "",
        },
        sample_filename=sample.filename if sample else "unknown",
        sample_sha256=sample.sha256 if sample else "",
        sample_size=sample.size_bytes if sample else 0,
    )

    filename = f"relict_report_{job.id}.html"
    return Response(
        content=html.encode("utf-8"),
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
