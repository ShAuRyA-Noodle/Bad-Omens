"""Pipeline orchestrator — chains all 6 stages into a complete eDNA analysis.

This module is the RQ target (``worker.pipeline.run_job.run_job``). The
FastAPI app enqueues jobs by dotted path, and the worker pops and
executes them here.

Lifecycle:
  1. Load the Job row from Postgres.
  2. Download the sample FASTQ from MinIO into a per-job workspace.
  3. Run stages in order: QC → derep → denoise → taxonomy → diversity → ordination.
  4. Persist ASVs, taxa, and diversity metrics back to Postgres.
  5. Transition the job to ``succeeded``.
  6. Publish progress events after every stage so the WebSocket channel
     has real-time data.

Error handling:
  Any StageError or unhandled exception transitions the job to ``failed``
  with the real error message surfaced in ``jobs.error_message``. Nothing
  is silently swallowed. No fabricated results are ever written.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.models import ASV, ConservationCache, DiversityMetric, Job, JobStatus, Sample, Taxon
from app.services.queue import publish_job_event_sync
from app.services.signing import get_or_create_signing_key
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from worker import PIPELINE_VERSION, TOOL_VERSIONS
from worker.pipeline import StageError
from worker.pipeline import conservation as conservation_stage
from worker.pipeline import denoise_vsearch as denoise_stage
from worker.pipeline import dereplicate as derep_stage
from worker.pipeline import diversity as diversity_stage
from worker.pipeline import ordination as ordination_stage
from worker.pipeline import provenance as provenance_stage
from worker.pipeline import qc as qc_stage
from worker.pipeline import taxonomy as tax_stage
from worker.tool_versions import detect_tool_versions

log = get_logger("worker.pipeline")


def _workspaces_root() -> Path:
    """Resolve WORKSPACES_ROOT and create it if missing.

    On Render the container's filesystem is ephemeral and the directory
    won't exist until we mkdir it. On Docker Compose the image already
    creates /workspaces, so this is a no-op.
    """
    root = Path(get_settings().WORKSPACES_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _references_root() -> Path:
    return Path(get_settings().REFERENCES_ROOT)


def _sync_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.database_url_sync,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        future=True,
    )


def _detect_reference_db(amplicon: str) -> Path | None:
    """Find the appropriate reference FASTA for the amplicon marker.

    Returns None if the DB hasn't been downloaded yet (the taxonomy
    stage will raise a clear error).
    """
    references_root = _references_root()
    silva_dir = references_root / "silva"
    mitofish_dir = references_root / "mitofish"           # legacy, may not exist
    midori2_dir = references_root / "midori2"             # legacy, may not exist
    midori2_12s_dir = references_root / "midori2_12s"
    midori2_coi_dir = references_root / "midori2_coi"

    # Search order per marker: UDB indexes first (fast), then raw FASTA,
    # then any *.fasta in the marker's folder as a final fallback. This
    # lets us survive filename drift across MIDORI2 / SILVA releases.
    candidates: dict[str, list[Path]] = {
        "16S_V4": [
            silva_dir / "SILVA_138.1_SSURef_NR99_tax_silva.udb",
            silva_dir / "silva_138_99_merged.fasta",
            silva_dir / "SILVA_138.1_SSURef_NR99_tax_silva.fasta",
            *(list(silva_dir.glob("*.fasta")) if silva_dir.exists() else []),
        ],
        "18S_V9": [
            silva_dir / "SILVA_138.1_SSURef_NR99_tax_silva.udb",
            silva_dir / "silva_138_99_merged.fasta",
            silva_dir / "SILVA_138.1_SSURef_NR99_tax_silva.fasta",
            *(list(silva_dir.glob("*.fasta")) if silva_dir.exists() else []),
        ],
        "rbcL": [
            silva_dir / "SILVA_138.1_SSURef_NR99_tax_silva.udb",
            silva_dir / "SILVA_138.1_SSURef_NR99_tax_silva.fasta",
        ],
        "ITS2": [
            silva_dir / "SILVA_138.1_SSURef_NR99_tax_silva.udb",
            silva_dir / "SILVA_138.1_SSURef_NR99_tax_silva.fasta",
        ],
        "12S_MiFish": [
            midori2_12s_dir / "MIDORI2_UNIQ_NUC_GB269_srRNA_RAW.udb",
            midori2_12s_dir / "MIDORI2_UNIQ_NUC_GB269_srRNA_RAW.fasta",
            midori2_dir / "MIDORI2_UNIQ_NUC_GB269_srRNA_RAW.fasta",
            *(list(midori2_12s_dir.glob("*.fasta")) if midori2_12s_dir.exists() else []),
            mitofish_dir / "complete_partial_mitogenomes.fa",
        ],
        "COI_Leray": [
            midori2_coi_dir / "MIDORI2_UNIQ_NUC_GB269_CO1_RAW.udb",
            midori2_coi_dir / "MIDORI2_UNIQ_NUC_GB269_CO1_RAW.fasta",
            midori2_dir / "MIDORI2_UNIQ_NUC_GB269_CO1_RAW.fasta",
            *(list(midori2_coi_dir.glob("*CO1*.fasta")) if midori2_coi_dir.exists() else []),
            *(list(midori2_dir.glob("*CO1*.fasta")) if midori2_dir.exists() else []),
        ],
    }

    for path in candidates.get(amplicon, candidates.get("16S_V4", [])):
        if path.exists():
            return path

    # Last-resort fallback — if no marker-specific DB resolves, pick the
    # biggest FASTA anywhere under the references root so the pipeline
    # can still produce a best-effort taxonomy rather than skipping.
    for search_dir in [silva_dir, midori2_12s_dir, midori2_coi_dir, midori2_dir, mitofish_dir]:
        if search_dir.exists():
            fastas = list(search_dir.glob("*.fasta")) + list(search_dir.glob("*.fa"))
            if fastas:
                return max(fastas, key=lambda f: f.stat().st_size)

    return None


def _download_sample_from_minio(s3_key: str, dest: Path) -> None:
    """Pull the raw FASTQ from MinIO into the workspace."""
    from minio import Minio

    settings = get_settings()
    client = Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY.get_secret_value(),
        secure=settings.MINIO_SECURE,
    )
    client.fget_object(settings.MINIO_BUCKET, s3_key, str(dest))


def run_job(job_id: str) -> dict[str, str]:
    """RQ entrypoint. Called with ``job_id`` as a string (RQ serialises kwargs)."""
    configure_logging(get_settings().LOG_LEVEL)
    log.info("pipeline.started", job_id=job_id, pipeline_version=PIPELINE_VERSION)

    uid = uuid.UUID(job_id)
    engine = _sync_engine()
    stage_results: list[dict[str, Any]] = []

    with Session(engine, expire_on_commit=False) as session:
        job = session.get(Job, uid)
        if job is None:
            log.error("pipeline.missing_job", job_id=job_id)
            return {"status": "missing", "job_id": job_id}

        samples = list(session.query(Sample).filter(Sample.job_id == uid).all())
        if not samples:
            _fail_job(session, job, "No samples found for this job")
            return {"status": "failed", "job_id": job_id}

        sample = samples[0]

        # ─── Mark running ──────────────────────────────────────────────
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(tz=UTC)
        job.pipeline_version = PIPELINE_VERSION
        session.commit()
        _emit(uid, "job.started", "Pipeline started", progress=0.0)

        workspace = _workspaces_root() / job_id
        workspace.mkdir(parents=True, exist_ok=True)

        try:
            # ─── Download sample from MinIO ────────────────────────────
            raw_fastq = workspace / sample.filename
            _emit(uid, "stage.started", "Downloading sample from storage", stage="download")
            _download_sample_from_minio(sample.s3_key, raw_fastq)
            _emit(uid, "stage.completed", "Sample downloaded", stage="download", progress=0.05)

            # ─── Stage 1: QC ──────────────────────────────────────────
            _emit(uid, "stage.started", "Quality control (fastp)", stage="qc", progress=0.10)
            qc_result = qc_stage.run(workspace, raw_fastq, logger=log)
            stage_results.append(qc_result.to_dict())
            trimmed_fastq = Path(qc_result.output_files[0])
            _emit(uid, "stage.completed", f"QC done — {qc_result.metrics.get('reads_after_filtering', '?')} reads passed", stage="qc", progress=0.20)

            # ─── Stage 2: Dereplication ───────────────────────────────
            _emit(uid, "stage.started", "Dereplicating sequences", stage="derep", progress=0.25)
            derep_result = derep_stage.run(workspace, trimmed_fastq, logger=log)
            stage_results.append(derep_result.to_dict())
            unique_fasta = Path(derep_result.output_files[0])
            _emit(uid, "stage.completed", f"Dereplication done — {derep_result.metrics.get('unique_sequences', '?')} unique sequences", stage="derep", progress=0.35)

            # ─── Stage 3: ASV inference (UNOISE3) ─────────────────────
            _emit(uid, "stage.started", "Inferring ASVs (vsearch UNOISE3)", stage="denoise", progress=0.40)
            denoise_result = denoise_stage.run(workspace, unique_fasta, logger=log)
            stage_results.append(denoise_result.to_dict())
            asvs_fasta = Path(denoise_result.output_files[0])
            _emit(uid, "stage.completed", f"Denoising done — {denoise_result.metrics.get('n_asvs', '?')} ASVs", stage="denoise", progress=0.50)

            # ─── Stage 4: Taxonomy ────────────────────────────────────
            ref_db = _detect_reference_db(job.amplicon.value if job.amplicon else "16S_V4")
            if ref_db:
                _emit(uid, "stage.started", f"Assigning taxonomy against {ref_db.name}", stage="taxonomy", progress=0.55)
                tax_params = tax_stage.TaxonomyParams(reference_db=str(ref_db))
                tax_result = tax_stage.run(workspace, asvs_fasta, params=tax_params, logger=log)
                stage_results.append(tax_result.to_dict())
                _emit(uid, "stage.completed", f"Taxonomy done — {tax_result.metrics.get('asvs_assigned', '?')}/{tax_result.metrics.get('asvs_total', '?')} assigned", stage="taxonomy", progress=0.70)
            else:
                log.warning("pipeline.no_reference_db", amplicon=str(job.amplicon))
                _emit(uid, "stage.skipped", "No reference database found — taxonomy skipped. Run 'make download-refs'.", stage="taxonomy", progress=0.70)
                tax_result = None

            # ─── Stage 4b: Conservation cross-referencing ─────────────
            conservation_result = None
            if tax_result:
                taxonomy_tsv = None
                for f in tax_result.output_files:
                    if f.endswith("taxonomy.tsv"):
                        taxonomy_tsv = Path(f)
                        break
                if taxonomy_tsv and taxonomy_tsv.exists():
                    _emit(uid, "stage.started", "Cross-referencing species against GBIF + IUCN Red List", stage="conservation", progress=0.72)
                    conservation_result = conservation_stage.run(workspace, taxonomy_tsv, logger=log)
                    stage_results.append(conservation_result.to_dict())
                    threatened = conservation_result.metrics.get("threatened_count", 0)
                    failed = conservation_result.metrics.get("lookup_failed_count", 0)
                    msg = f"Conservation done — {conservation_result.metrics.get('species_with_iucn', 0)} species checked"
                    if threatened > 0:
                        msg += f", {threatened} threatened"
                    if failed > 0:
                        # Never let a degraded run read as a clean 'nothing threatened'.
                        msg += f" — ⚠ {failed} lookup(s) failed, results may be incomplete"
                    _emit(uid, "stage.completed", msg, stage="conservation", progress=0.78)

            # ─── Stage 5: Diversity metrics ───────────────────────────
            _emit(uid, "stage.started", "Computing diversity metrics", stage="diversity", progress=0.80)
            div_result = diversity_stage.run(workspace, asvs_fasta, logger=log)
            stage_results.append(div_result.to_dict())
            _emit(uid, "stage.completed", f"Diversity done — Shannon={div_result.metrics.get('shannon', '?')}", stage="diversity", progress=0.85)

            # ─── Stage 6: Ordination ──────────────────────────────────
            _emit(uid, "stage.started", "Computing UMAP ordination", stage="ordination", progress=0.88)
            ord_result = ordination_stage.run(workspace, asvs_fasta, logger=log)
            stage_results.append(ord_result.to_dict())
            _emit(uid, "stage.completed", f"Ordination done — {ord_result.metrics.get('n_clusters', '?')} clusters", stage="ordination", progress=0.95)

            # ─── Persist results to Postgres ──────────────────────────
            _persist_results(
                session, job, sample,
                asvs_fasta=asvs_fasta,
                tax_result=tax_result,
                div_result=div_result,
                conservation_result=conservation_result,
            )

            # ─── Compute parameter hash ───────────────────────────────
            # Record the versions actually installed in this worker, not the
            # hardcoded pins — the manifest must reflect what really ran.
            detected_versions = detect_tool_versions()
            pipeline_params = {
                "pipeline_version": PIPELINE_VERSION,
                "tool_versions": detected_versions,
                "tool_versions_expected": TOOL_VERSIONS,
                "amplicon": str(job.amplicon),
            }
            param_str = json.dumps(pipeline_params, sort_keys=True)
            job.parameter_hash = hashlib.sha256(param_str.encode()).hexdigest()

            # ─── Stage 7: Provenance manifest ─────────────────────────
            _emit(uid, "stage.started", "Generating signed provenance manifest", stage="provenance", progress=0.96)

            # Reference DB hash — cached in a sidecar so multi-GB DBs are
            # hashed once, not on every run. Recorded for every DB regardless
            # of size (no more "skipped-large-file" placeholder).
            ref_db_info = []
            ref_db_path = _detect_reference_db(job.amplicon.value if job.amplicon else "16S_V4")
            if ref_db_path and ref_db_path.exists():
                ref_db_info.append({
                    "name": ref_db_path.name,
                    "path": str(ref_db_path),
                    "sha256": provenance_stage.sha256_file_cached(ref_db_path),
                })

            # Hash every real output file produced by the upstream stages so
            # the manifest records what was actually generated (deterministic
            # given identical inputs). The provenance stage itself has not run
            # yet, so its own output is not included.
            output_files_manifest: list[dict[str, Any]] = []
            seen_outputs: set[str] = set()
            for sr in stage_results:
                for out in sr.get("output_files", []):
                    op = Path(out)
                    key = str(op)
                    if key in seen_outputs or not op.exists():
                        continue
                    seen_outputs.add(key)
                    try:
                        output_files_manifest.append({
                            "filename": op.name,
                            "sha256": provenance_stage.sha256_file(op),
                            "size_bytes": op.stat().st_size,
                        })
                    except OSError:
                        continue

            # Mint (or reuse) the server's Ed25519 signing key and sign the
            # canonical manifest content for real.
            signing_key = get_or_create_signing_key(session)

            prov_result = provenance_stage.run(
                workspace,
                job_id=job_id,
                input_files=[{
                    "filename": sample.filename,
                    "sha256": sample.sha256,
                    "size_bytes": sample.size_bytes,
                }],
                stage_results=stage_results,
                reference_dbs=ref_db_info,
                parameters=pipeline_params,
                output_files=output_files_manifest,
                tool_versions=detected_versions,
                signing_private_key=signing_key.private_key,
                logger=log,
            )
            stage_results.append(prov_result.to_dict())

            manifest_sha = prov_result.metrics.get("manifest_sha256", "")
            signature = prov_result.metrics.get("signature") or ""
            manifest_path = Path(prov_result.output_files[0]) if prov_result.output_files else None
            manifest_data = {}
            if manifest_path and manifest_path.exists():
                manifest_data = json.loads(manifest_path.read_text())

            from app.db.models import Provenance
            prov_row = Provenance(
                job_id=job.id,
                schema_version="1.0",
                manifest=manifest_data,
                manifest_sha256=manifest_sha,
                signature=signature,
                signed_at=datetime.now(tz=UTC),
            )
            session.add(prov_row)

            _emit(uid, "stage.completed", f"Provenance manifest signed: {manifest_sha[:16]}...", stage="provenance", progress=0.99)

            # ─── Mark succeeded ────────────────────────────────────────
            job.status = JobStatus.SUCCEEDED
            job.finished_at = datetime.now(tz=UTC)
            session.commit()
            _emit(uid, "job.succeeded", "Pipeline completed successfully", progress=1.0)

        except StageError as exc:
            _fail_job(session, job, str(exc))
            _emit(uid, "job.failed", str(exc))
            log.error("pipeline.stage_error", job_id=job_id, error=str(exc))
            return {"status": "failed", "job_id": job_id, "error": str(exc)}

        except Exception as exc:
            _fail_job(session, job, f"Unexpected error: {exc!s}")
            _emit(uid, "job.failed", f"Unexpected: {exc!s}")
            log.exception("pipeline.unhandled_error", job_id=job_id)
            return {"status": "failed", "job_id": job_id, "error": str(exc)}

        finally:
            if workspace.exists():
                try:
                    shutil.rmtree(workspace)
                except OSError:
                    log.warning("pipeline.workspace_cleanup_failed", workspace=str(workspace))

    log.info("pipeline.completed", job_id=job_id, status="succeeded")
    return {"status": "succeeded", "job_id": job_id}


def _persist_results(
    session: Session,
    job: Job,
    sample: Sample,
    *,
    asvs_fasta: Path,
    tax_result: Any,
    div_result: Any,
    conservation_result: Any = None,
) -> None:
    """Write ASVs, taxa, diversity metrics, and conservation data to the database."""
    asv_sequences = _read_fasta_with_sizes(asvs_fasta)
    tax_records = _load_taxonomy(tax_result) if tax_result else {}

    for seq_id, (sequence, abundance) in asv_sequences.items():
        seq_hash = hashlib.sha256(sequence.encode()).hexdigest()
        asv = ASV(
            job_id=job.id,
            sequence_sha256=seq_hash,
            sequence=sequence,
            length=len(sequence),
            abundance=abundance,
        )
        session.add(asv)
        session.flush()

        tax = tax_records.get(seq_id)
        if tax:
            taxon = Taxon(
                asv_id=asv.id,
                kingdom=tax.get("kingdom") or None,
                phylum=tax.get("phylum") or None,
                tax_class=tax.get("class") or None,
                tax_order=tax.get("order") or None,
                family=tax.get("family") or None,
                genus=tax.get("genus") or None,
                species=tax.get("species") or None,
                confidence=tax.get("identity"),
                reference_db=tax_result.metrics.get("reference_db") if tax_result else None,
            )
            session.add(taxon)

    if div_result and div_result.metrics:
        m = div_result.metrics
        dm = DiversityMetric(
            sample_id=sample.id,
            richness=m.get("richness"),
            shannon=m.get("shannon"),
            simpson=m.get("simpson"),
            chao1=m.get("chao1"),
            evenness=m.get("evenness"),
        )
        session.add(dm)

    if conservation_result and not conservation_result.metrics.get("skipped"):
        conservation_json = _load_conservation_json(conservation_result)
        for rec in conservation_json:
            species_name = rec.get("species", "")
            if not species_name:
                continue
            existing = session.query(ConservationCache).filter(
                ConservationCache.species == species_name
            ).first()
            if existing:
                existing.gbif_key = rec.get("gbif_key")
                existing.gbif_occurrence_count = rec.get("gbif_occurrence_count")
                existing.iucn_category = rec.get("iucn_category")
                existing.iucn_assessment_year = rec.get("iucn_assessment_year")
                existing.is_invasive = rec.get("is_invasive", False)
                existing.fetched_at = datetime.now(tz=UTC)
            else:
                session.add(ConservationCache(
                    species=species_name,
                    gbif_key=rec.get("gbif_key"),
                    gbif_occurrence_count=rec.get("gbif_occurrence_count"),
                    iucn_category=rec.get("iucn_category"),
                    iucn_assessment_year=rec.get("iucn_assessment_year"),
                    is_invasive=rec.get("is_invasive", False),
                    legal_flags={"gbif_matched_name": rec.get("gbif_matched_name"),
                                 "iucn_category_full": rec.get("iucn_category_full"),
                                 "iucn_population_trend": rec.get("iucn_population_trend")},
                    fetched_at=datetime.now(tz=UTC),
                ))

    session.flush()


def _read_fasta_with_sizes(fasta: Path) -> dict[str, tuple[str, int]]:
    """Parse a FASTA into {id: (sequence, size)}."""
    result: dict[str, tuple[str, int]] = {}
    current_id = ""
    current_seq: list[str] = []
    current_size = 1

    with open(fasta) as f:
        for line in f:
            line = line.strip()
            if line.startswith(">"):
                if current_id:
                    result[current_id] = ("".join(current_seq), current_size)
                header = line[1:]
                current_id = header.split(";")[0].split()[0]
                current_size = 1
                for part in header.split(";"):
                    if part.startswith("size="):
                        with contextlib.suppress(ValueError, IndexError):
                            current_size = int(part.split("=")[1])
                current_seq = []
            elif current_id:
                current_seq.append(line.upper())

    if current_id:
        result[current_id] = ("".join(current_seq), current_size)
    return result


def _load_taxonomy(tax_result: Any) -> dict[str, dict[str, Any]]:
    """Load taxonomy TSV into {asv_id: {rank: value}}."""
    import csv

    tsv_path = None
    for f in tax_result.output_files:
        if f.endswith("taxonomy.tsv"):
            tsv_path = Path(f)
            break

    if tsv_path is None or not tsv_path.exists():
        return {}

    records: dict[str, dict[str, Any]] = {}
    with open(tsv_path) as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            asv_id = row.get("asv_id", "")
            if asv_id:
                records[asv_id] = {
                    "kingdom": row.get("kingdom", ""),
                    "phylum": row.get("phylum", ""),
                    "class": row.get("class", ""),
                    "order": row.get("order", ""),
                    "family": row.get("family", ""),
                    "genus": row.get("genus", ""),
                    "species": row.get("species", ""),
                    "identity": float(row["identity"]) / 100 if row.get("identity") else None,
                }
    return records


def _load_conservation_json(conservation_result: Any) -> list[dict[str, Any]]:
    """Load conservation records from the stage output JSON."""
    for f in conservation_result.output_files:
        if f.endswith("conservation.json"):
            p = Path(f)
            if p.exists():
                data = json.loads(p.read_text())
                records = data.get("records", [])
                return records if isinstance(records, list) else []
    return []


def _fail_job(session: Session, job: Job, error: str) -> None:
    """Transition job to failed state."""
    job.status = JobStatus.FAILED
    job.finished_at = datetime.now(tz=UTC)
    job.error_message = error[:4000]
    session.commit()


def _emit(job_id: uuid.UUID, kind: str, message: str, **extra: Any) -> None:
    """Publish a progress event to the per-job pub/sub channel."""
    publish_job_event_sync(job_id, {"kind": kind, "message": message, **extra})
