"""End-to-end pipeline smoke test on a synthetic FASTQ.

Runs the real bioinformatics stages against generated reads to certify the
actual binaries (fastp, cutadapt, vsearch) and the stage code execute together:
QC -> primer trim (cutadapt) -> dereplicate -> denoise+chimera (vsearch UNOISE3
+ uchime3) -> diversity (scikit-bio) -> phylogeny (MAFFT + FastTree -> Faith's
PD) -> Ecosystem Integrity Index.

Taxonomy/conservation are skipped (no reference DB). This is not a scientific
benchmark — it proves the pipeline runs cleanly on real tools and that the new
cutadapt + chimera stages don't break the flow.

Run inside the worker image:
    docker compose run --rm worker python scripts/smoke_pipeline.py
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from worker.pipeline import coverage as coverage_stage
from worker.pipeline import denoise_vsearch as denoise_stage
from worker.pipeline import dereplicate as derep_stage
from worker.pipeline import diversity as diversity_stage
from worker.pipeline import phylogeny as phylo_stage
from worker.pipeline import primer_trim as primer_stage
from worker.pipeline import qc as qc_stage
from worker.pipeline.integrity_index import compute_eii

# Concrete 16S V4 primers (ambiguity resolved) to embed in the synthetic reads;
# the stage passes the IUPAC forms to cutadapt, which matches these.
FWD = "GTGCCAGCAGCCGCGGTAA"          # 515F, resolved
REV_RC = "ATTAGATACCCTGGTAGTCC"      # revcomp of 806R (GGACTAC...), resolved

_BASES = "ACGT"


def _make_body(seed: int, length: int = 200) -> str:
    # Deterministic pseudo-random body per "species" (no RNG — reproducible).
    out = []
    x = seed * 2654435761 & 0xFFFFFFFF
    for _ in range(length):
        x = (1103515245 * x + 12345) & 0xFFFFFFFF
        out.append(_BASES[(x >> 16) & 3])
    return "".join(out)


def _write_synthetic_fastq(path: Path, n_species: int = 4, copies: int = 120) -> int:
    qual = "I"  # Phred 40
    reads = 0
    with open(path, "w") as f:
        for sp in range(n_species):
            body = _make_body(sp + 1)
            read = FWD + body + REV_RC
            for c in range(copies):
                f.write(f"@sp{sp}_read{c}\n{read}\n+\n{qual * len(read)}\n")
                reads += 1
    return reads


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp)
        raw = ws / "reads.fastq"
        n_reads = _write_synthetic_fastq(raw)
        print(f"[smoke] generated {n_reads} reads")

        qc = qc_stage.run(ws, raw, logger=None)
        print(f"[smoke] QC: {qc.metrics}")
        trimmed = Path(qc.output_files[0])

        pt = primer_stage.run(ws, trimmed, "16S_V4", logger=None)
        print(f"[smoke] primer_trim: reads_after={pt.metrics.get('reads_after_trimming')}")
        primer_fastq = Path(pt.output_files[0])

        cov = coverage_stage.run(ws, primer_fastq, logger=None)
        print(f"[smoke] coverage: goods_coverage={cov.metrics.get('goods_coverage')} "
              f"singletons={cov.metrics.get('n_singletons')}/{cov.metrics.get('n_reads')}")

        dr = derep_stage.run(ws, primer_fastq, logger=None)
        print(f"[smoke] derep: {dr.metrics}")
        unique = Path(dr.output_files[0])

        dn = denoise_stage.run(ws, unique, logger=None)
        print(f"[smoke] denoise: n_asvs={dn.metrics.get('n_asvs')} "
              f"chimeras={dn.metrics.get('n_chimeras_removed')}")
        asvs = Path(dn.output_files[0])

        dv = diversity_stage.run(ws, asvs, logger=None)
        print(f"[smoke] diversity: {dv.metrics}")

        ph = phylo_stage.run(ws, asvs, logger=None)
        print(f"[smoke] phylogeny: faith_pd={ph.metrics.get('faith_pd')} "
              f"n_tips={ph.metrics.get('n_tips')} tool={ph.tool_version}")
        dv.metrics["faith_pd"] = ph.metrics.get("faith_pd")

        eii = compute_eii(
            richness=dv.metrics.get("richness"),
            shannon=dv.metrics.get("shannon"),
            evenness=dv.metrics.get("evenness"),
            conservation_records=[],
            api_degraded=False,
            goods_coverage=cov.metrics.get("goods_coverage"),
        )
        print(f"[smoke] EII: grade={eii.grade} score={eii.score} assessed_weight={eii.assessed_weight}")

        assert dn.metrics.get("n_asvs", 0) >= 1, "expected at least one ASV"
        n_tips = ph.metrics.get("n_tips", 0)
        if n_tips >= 3:
            assert ph.metrics.get("faith_pd") is not None, "expected real Faith's PD with >=3 ASVs"
        print("[smoke] OK — pipeline ran end-to-end on real tools")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
