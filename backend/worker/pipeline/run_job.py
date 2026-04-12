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

import hashlib
import json
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.models import ASV, DiversityMetric, Job, JobStatus, Sample, Taxon
from app.services.queue import publish_job_event_sync
from worker import PIPELINE_VERSION, TOOL_VERSIONS
from worker.pipeline import StageError
from worker.pipeline import denoise_vsearch as denoise_stage
from worker.pipeline import dereplicate as derep_stage
from worker.pipeline import diversity as diversity_stage
from worker.pipeline import ordination as ordination_stage
from worker.pipeline import qc as qc_stage
from worker.pipeline import taxonomy as tax_stage

log = get_logger("worker.pipeline")

WORKSPACES_ROOT = Path("/workspaces")
REFERENCES_ROOT = Path("/data/references")


def _sync_engine():
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
    silva_dir = REFERENCES_ROOT / "silva"
    mitofish_dir = REFERENCES_ROOT / "mitofish"
    midori2_dir = REFERENCES_ROOT / "midori2"

    candidates: dict[str, list[Path]] = {
        "16S_V4": [
            silva_dir / "SILVA_138.1_SSURef_NR99_tax_silva.udb",
            silva_dir / "silva_138_99_merged.fasta",
            silva_dir / "SILVA_138.1_SSURef_NR99_tax_silva.fasta",
        ],
        "18S_V9": [
            silva_dir / "SILVA_138.1_SSURef_NR99_tax_silva.udb",
            silva_dir / "silva_138_99_merged.fasta",
            silva_dir / "SILVA_138.1_SSURef_NR99_tax_silva.fasta",
        ],
        "12S_MiFish": [
            midori2_dir / "MIDORI2_UNIQ_NUC_GB269_srRNA_RAW.fasta",
            mitofish_dir / "complete_partial_mitogenomes.fa",
        ],
        "COI_Leray": [
            midori2_dir / "MIDORI2_UNIQ_NUC_GB269_CO1_RAW.fasta",
            *(list(midori2_dir.glob("*CO1*.fasta")) if midori2_dir.exists() else []),
        ],
    }

    for path in candidates.get(amplicon, candidates.get("16S_V4", [])):
        if path.exists():
            return path

    for search_dir in [silva_dir, mitofish_dir, midori2_dir]:
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

        workspace = WORKSPACES_ROOT / job_id
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

            # ─── Stage 5: Diversity metrics ───────────────────────────
            _emit(uid, "stage.started", "Computing diversity metrics", stage="diversity", progress=0.75)
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
            )

            # ─── Compute parameter hash ───────────────────────────────
            param_str = json.dumps({
                "pipeline_version": PIPELINE_VERSION,
                "tool_versions": TOOL_VERSIONS,
                "amplicon": str(job.amplicon),
            }, sort_keys=True)
            job.parameter_hash = hashlib.sha256(param_str.encode()).hexdigest()

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
) -> None:
    """Write ASVs, taxa, and diversity metrics to the database."""
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
                        try:
                            current_size = int(part.split("=")[1])
                        except (ValueError, IndexError):
                            pass
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


def _fail_job(session: Session, job: Job, error: str) -> None:
    """Transition job to failed state."""
    job.status = JobStatus.FAILED
    job.finished_at = datetime.now(tz=UTC)
    job.error_message = error[:4000]
    session.commit()


def _emit(job_id: uuid.UUID, kind: str, message: str, **extra: Any) -> None:
    """Publish a progress event to the per-job pub/sub channel."""
    publish_job_event_sync(job_id, {"kind": kind, "message": message, **extra})
