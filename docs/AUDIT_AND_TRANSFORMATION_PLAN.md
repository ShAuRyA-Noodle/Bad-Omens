# Relict — Hypermode Audit & World-Class Transformation Plan

> Single source of truth for the rebuild. Synthesized from a 13-dimension adversarially-verified audit. Findings whose verification verdict was `refuted` or downgraded to noise are excluded; every severity below reflects the **effective** (post-verification) severity, not the auditor's initial label.

---

## 1. Executive Verdict

Relict is a **competently-plumbed but scientifically-indefensible-and-partly-dishonest eDNA pipeline wrapper wearing a striking cyber-terminal marketing skin**. The good news is real: every pipeline stage genuinely shells out to real, version-pinned tools (fastp, vsearch UNOISE3, scikit-bio), the auth core is solid (argon2id, HS256 with algorithm pinning, airtight per-route tenant isolation), the upload→WebSocket→results flow actually works, and the conservation layer makes live GBIF calls. The bad news is structural and brand-defining: the headline "**signed provenance**" is a SHA256 of the manifest relabeled `sha256:` with **zero cryptography** (no ed25519, no `/public-key`, no private key — confirmed across honesty/reproducibility/bio/novelty/creative dimensions); the science is unpublishable (**no chimera removal**, **no primer trimming despite cutadapt being declared**, **single-end only**, **species reported from a single 80%-identity best hit with no LCA**, **SILVA used for rbcL/ITS2**, and a "single-sample UMAP-on-k-mers" presented as ecological **ordination**); the conservation layer silently renders API failures as "not threatened" and `is_invasive` is structurally always `false`; and a chunk of the marketing/credibility UI plus the docs assert **CI enforcement, ≥80% coverage, a BERT transformer, and live telemetry that do not exist**. Weighted across dimensions (science, honesty, security, novelty weighted highest), the true grade today is **C− / D+** — a strong weekend-architecture portfolio piece, but several *credibility-critical* steps short of the "world-class, most-unique-ever eDNA platform" it markets itself as. The gap is closable: the differentiators are real and the white space (open, reproducible, conservation-aware, FASTQ→DwC-A-in-one-pass) is genuinely unoccupied — but only after the honesty gaps are purged and the science is made defensible.

---

## 2. Scorecard

| Dimension | Grade | One-line verdict |
|---|---|---|
| Security & Auth | **B−** | Competent auth core undermined by memory-exhausting uploads, zero rate limiting, no security headers. |
| Bioinformatics Correctness | **D** | Real tools, indefensible choices: no chimera/primer/paired-end, 80% best-hit species, wrong reference DBs. |
| No-Mock-Data Honesty | **C−** | Real pipeline, but signed-provenance, tool-versions, SRA benchmark, and marketing telemetry are fabricated. |
| Frontend Architecture | **C** | Clean typed API client + working demo flow, but `/visualize` is empty, refresh token is dead code. |
| Design / UX / Polish | **C−** | Striking marketing art direction; results UI is generic shadcn with broken tokens; fabricated credibility section. |
| Reproducibility & Provenance | **D** | Non-deterministic manifest (hashes wall-clock), empty output hashes, fake signature, half the fields don't exist. |
| Conservation Layer | **D** | IUCN token mandated-but-unused, write-only cache, always-false invasive flag, silent false-negative on API failure. |
| Data Model & Migrations | **B−** | Clean normalized schema; cross-tenant conservation cache, missing hot-path index, always-null `faith_pd`. |
| DevOps / CI/CD / Deploy | **D+** | Excellent Docker layer; **zero CI**, no prod migrations, missing download script, unprovisioned storage. |
| Test Coverage | **D** | Auth happy-path only; 2,113-LOC pipeline has **zero tests**; no CI to run anything; coverage claim unverifiable. |
| Docs & Paper Readiness | **C−** | Professional LaTeX, real bibliography; false signing novelty, 1+1 benchmark, overclaims DADA2/MitoFish. |
| Competitive Novelty | **C+** | Each pillar already shipped by a better-resourced incumbent; real white space is narrow but genuine. |
| Creative Differentiators | **C+** | Honest plumbing, but no signature feature exists today; the one "biodiversity score" is hardcoded `+12%`. |

### Overall Weighted Grade: **C− (≈ 2.0 / 4.0)**

Weighting (science 25%, honesty 20%, security 15%, novelty 15%, the rest 25% combined): the two highest-weight axes (science **D**, honesty **C−**) drag an otherwise B−/C engineering effort down. **The ceiling is high (A-territory differentiators are within one focused quarter), but the floor is currently breached by fabricated claims.**

---

## 3. Critical Issues (must-fix)

Every surviving **critical** finding (post-verification). These breach the project's own "no fabricated metrics" promise or produce scientifically wrong output.

| ID | Dimension | Issue | Why it's critical | Fix |
|---|---|---|---|---|
| **BIO-01** | Science | **No chimera removal.** `denoise_vsearch.py:70-79` ends at `--cluster_unoise`; grep `uchime\|chimera` = 0 hits. vsearch UNOISE3 (unlike USEARCH) does *not* dechimerize. | Every richness/Chao1/Shannon/`n_asvs` is inflated by uncharacterized chimeras → unpublishable, violates "real metrics". | Add `vsearch --uchime3_denovo asvs.fasta --sizein --nonchimeras asvs_nochim.fasta` after clustering; feed dechimerized file downstream; record chimera count. |
| **BIO-02** | Science | **Primer trimming never runs; cutadapt declared but unused.** `cutadapt==4.9` in `TOOL_VERSIONS` (`worker/__init__.py:18`) + Dockerfile, but zero invocations; `Sample.primer_set` (`models.py:214`) never read. | Primers remain on every ASV → corrupts dereplication, taxonomy identity. Listing cutadapt in the manifest = fabricated provenance. | Add a cutadapt stage using per-marker primers with `--discard-untrimmed` before QC; or remove cutadapt from `TOOL_VERSIONS`. |
| **BIO-03** | Science | **Single-end only.** `qc.py:56-67` uses `--in1/--out1`; no merge; `run_job.py:182` `samples[0]` discards R2. | The dominant real eDNA data type (paired-end Illumina) cannot be ingested correctly; the schema promises paired-end the pipeline can't deliver. | Accept R1+R2, merge (`fastp --merge` / `vsearch --fastq_mergepairs`), record merge rate; reject/flag single-end. |
| **BIO-05** | Science | **rbcL/ITS2 mapped to SILVA SSU; "biggest-FASTA" fallback can route any marker to SILVA.** `run_job.py:108-115, 136-143`. | SILVA is 16S/18S rRNA; rbcL (chloroplast) / ITS2 (nuclear spacer) align meaninglessly → confident taxonomy from a categorically wrong DB. | Strict per-marker DB map (UNITE for ITS, curated rbcL/BOLD); **hard-fail** on missing DB, never substitute. |
| **CONS-05** | Conservation | **API failure → silent "not threatened."** GBIF exception sets `record.error` but the null record is still persisted (error dropped at the JSON→DB hop); `threatened_count` counts only positive IUCN categories. | A GBIF outage/429 silently becomes "no threatened species detected" while the job reports success — the exact conservation-integrity hazard. | Persist per-record `error`; expose `lookup_failed_count`; never show `0 Threatened` when any lookup errored; degrade the stage past an error-rate threshold. |
| **PROV-01 / HON-01 / DOC-01 / NOV-01 / DIFF-02** | Reproducibility / Honesty / Paper / Novelty / Creative | **"Signature" is a relabeled SHA256.** `provenance.py:119` `manifest["signature"] = f"sha256:{manifest_hash}"`; no ed25519, no `/public-key`, no key. Docstring + README + paper + `CITATION.cff` claim cryptographic signing. | The load-bearing trust differentiator is theater — anyone who edits the manifest recomputes the hash. A reviewer reading the code flags it instantly. (Verification downgraded the *security-exploit* severity but kept this **critical for honesty/branding**.) | Implement real Ed25519 (the `cryptography==44.0.0` dep is already present): keypair on startup, sign `compute_manifest_hash()`, serve `GET /public-key`, ship an offline verifier — **or** rename to `manifest_sha256`/`content_hash` everywhere and delete every "signature"/"signed" claim. |
| **PROV-02** | Reproducibility | **Manifest is non-deterministic.** `timestamp_utc` (`provenance.py:49`) is *inside* the hashed payload; `compute_manifest_hash` excludes only `manifest_sha256`+`signature`. | The headline "two identical runs → identical `manifest_sha256`" (MASTER_PLAN:502) is mathematically impossible as coded. (Effective severity high, but it nullifies a critical promise.) | Exclude `timestamp_utc` and per-stage runtimes from the hash; hash only deterministic content; add a CI double-run equality test. |
| **DEPLOY-01** | DevOps | **Production runs no migrations.** No `preDeployCommand`/`alembic` in `render.yaml`; `app/main.py` lifespan creates nothing; `create_all` only in test conftest. | A fresh Render deploy boots against an empty schema; every DB query 500s while `/health` may report healthy → silently dead. | Add `preDeployCommand: alembic upgrade head` to `relict-api` in `render.yaml`. |
| **CI-01 / TEST-03** | DevOps / Tests | **Zero CI exists** (no `.github/`), yet docs claim ruff/mypy/pytest/grep-no-mock/≥80%-coverage are "enforced in CI." | Nothing blocks a commit that adds mock data, breaks `mypy --strict`, or introduces `shell=True`. The central "machine-enforced honesty" claim is false. | Add `.github/workflows/ci.yml` (frontend tsc/eslint/build + backend ruff/mypy/pytest `--cov-fail-under` + repo-wide no-mock/no-`shell=True` greps); make it a required check. Until then, strike every "enforced in CI" claim. |
| **TEST-01** | Tests | **The scientific pipeline (2,113 LOC, 9 stages) has zero tests.** No test imports `run_job`, `_compute_metrics`, fastp, vsearch, skbio. | Every scientific claim is computed by untested code; a silent regression in QC counts / taxonomy parsing / Shannon math ships undetected. | Unit-test pure functions first (`diversity._compute_metrics` against a hand-computed toy vector), then an end-to-end `run_job` test on a ≤5 MB truncated FASTQ fixture. |
| **TEST-02** | Tests | **Promised FASTQ fixtures don't exist; Phase 2.3 e2e test absent.** `backend/tests/fixtures/` is empty. | MASTER_PLAN's stage assertions (QC<input, derep<QC, ≥1 genus, Shannon-in-range) exist only as prose; "Integration tests green in CI" is unmeetable. | Commit a ≤5 MB truncated public 16S V4 SRA subset; write the four stage assertions + one full e2e producing `provenance.json`. |
| **DOC-02** | Paper | **Benchmark suite = 1 synthetic + 1 SRA, no QIIME2/DADA2 comparison.** | MEE/MER methods papers require multi-dataset validation with tolerance bounds vs the de facto standards; current evidence invites desk-reject. | Run ≥4 published datasets through Relict *and* QIIME2/DADA2 on identical inputs; report genus-Jaccard, Shannon Δ within tolerances, wall-time; compare ERR2283086 to its *known* mock composition. |
| **UX-02** | Design | **`/visualize` "Topology Matrix" is empty placeholder cards under `[ INTERACTIVE ]`/`[ LIVE ]` labels.** `BiodiversityCharts.tsx`/`BiodiversityMetrics.tsx` render one icon + a button; recharts installed, never imported. | The top-level nav destination advertising "real-time interactive taxonomy telemetry" delivers nothing — pure theatre on the page reviewers click first. | Build real per-job recharts/treemap/IUCN-donut/ordination views from existing job APIs, **or** remove the nav item and LIVE/INTERACTIVE labels until built. |
| **UX-03 / UX-04** | Design / Honesty | **How-It-Works + Credibility sections fabricate the method and telemetry.** `dna-bert-v2` transformer (real pipeline is vsearch UNOISE3), `node ingest.js`, hardcoded `142,305 reads`, fake DB latencies, `100%` benchmark/provenance rates, `2.4M seqs`. (Also Demo.tsx "BERT transformer array", HON-07/08.) | Implausible `100%` assignment rate (real eDNA: 30–80%) reads as dishonest to any expert, on the pages literally meant to establish credibility. | Rewrite to the real fastp→vsearch→sintax→GBIF/IUCN→manifest stack; replace every hardcoded number with live-from-endpoint or explicitly-labeled "illustrative"; delete the BERT line. |

---

## 4. High-Priority Issues

| ID | Dimension | Issue | Fix (condensed) |
|---|---|---|---|
| **SEC-01** | Security | Upload buffers whole file into `io.BytesIO` (`storage.py:114-123`), size-checked only *after* (`samples.py:88`); no Content-Length pre-check → RAM-exhaustion DoS on starter plan. | Enforce `MAX_UPLOAD_BYTES` inside the read loop; reject by Content-Length at proxy; stream to spooled temp / MinIO multipart. |
| **SEC-02** | Security | Zero rate limiting anywhere; argon2id login is itself a CPU-DoS vector. | slowapi/edge throttle on `/auth/*`; per-user job/upload caps; login backoff. |
| **BIO-04 / DIFF-04** | Science | "Ordination" UMAPs k-mer profiles of **one sample's ASVs** (`ordination.py:172-196`); abundance (`;size=`) is stripped — pure compositional clustering presented as community ordination. | Relabel honestly as sequence-composition map, or build true multi-sample Bray-Curtis/PCoA. Remove from paper until real. |
| **BIO-06** | Science | Single best hit at ≥80% identity → species + raw identity stored as `confidence` (`taxonomy.py:36,161-173`; `run_job.py:393-394`); fabricated species names flow unfiltered into conservation. | Per-rank identity gating (species ≥97–98%) + LCA/SINTAX consensus; rename `confidence`→`percent_identity`. |
| **BIO-08** | Science | No marker-specific params; `QC/Derep/Denoise` always use defaults (`min_length=50`, `max_length=0`, `id=0.80`) across six markers. | Per-marker param table keyed by `Amplicon` enum threaded through every stage. |
| **BIO-09** | Science | Chao1 computed on denoised, singleton-purged data → invalid estimator; no rarefaction. | Drop Chao1 on denoised data; add rarefaction/normalization; document single-sample limits. |
| **BIO-10** | Science | Silent "biggest-FASTA-anywhere" reference fallback (`run_job.py:136-143`). | Remove fallback; hard-fail naming the missing DB. |
| **CONS-01** | Conservation | IUCN token mandated + gates lookup but **never sent** to any IUCN API (`conservation.py:217,266-294` hits GBIF mirror, no auth); `tool_version="iucn-api-v3"` fabricated. | Either call IUCN v4 with the token, or drop the gate, relabel source `gbif-iucn-mirror`, fix docs/`tool_version`. |
| **CONS-03** | Conservation | 30-day cache is write-only; never read before API calls; `models.py:325` docstring claims a TTL that no code enforces. | Read-through SELECT `WHERE fetched_at > now()-30d` before any HTTP call. |
| **CONS-04** | Conservation | `is_invasive` structurally always `false`; no GISD list on disk; field exported as authoritative. | Ship versioned `invasive_species.json`, match detected names, record version in provenance; until then surface `null`/"not assessed". |
| **HON-04** | Honesty | SRA ERR2283086 benchmark has **no generating script, no raw artifact** — numbers hand-written; phylum table uses `~` approximations (HON-05). | Add SRA function to `benchmark.py` that downloads, runs, emits machine-readable JSON+log; regenerate the `.md` from it. |
| **DB-01** | Database | `conservation_cache` is global, keyed only by `species` (`models.py:329-342`); `results.py:217-220` serves a job's panel from rows other tenants filled → cross-tenant leak + non-reproducible. | Per-job `conservation_results` snapshot written at run time; serve from that, not the global table. |
| **DB-02** | Database | Primary list query `ORDER BY jobs.created_at DESC` (`jobs.py:68`) has no index. | Add composite `Index("ix_jobs_user_created","user_id","created_at")` + migration. |
| **DB-03** | Database | `faith_pd` exposed in API but never written → always NULL (fabricated-field inverse). | Compute it (needs a tree, see DIFF-05) or remove from model/migration/schema. |
| **FE-01** | Frontend | `/visualize` dead; recharts installed, never imported (mirrors UX-02). | Build or delete-and-redirect per MASTER_PLAN:547. |
| **FE-02** | Frontend | Refresh token stored but never exchanged; backend `/auth/refresh` exists unused; access-token expiry → silent logout. | 401-retry interceptor in `apiFetch` POSTing the stored refresh token. |
| **DEPLOY-03** | DevOps | `MINIO_*` required (no default in `config.py`) but never provisioned; upload entry point has no FS fallback. | Document concrete R2/B2 setup; fail fast at startup with an actionable error if `MINIO_*` missing. |
| **UX-05** | Design | Body text `--foreground: 183 30% 80%` + `gray-400/500` on black fails WCAG 4.5:1. | Raise foreground to near-white; promote body copy to ≥4.5:1. |
| **DOC-03** | Paper | `CITATION.cff:7` + README advertise DADA2 + MitoFish that are unimplemented. | Strip from canonical metadata; keep only as "planned" in limitations. |
| **DOC-05 / TEST-07** | Paper / Tests | "Byte-identical reproducibility" claimed with no determinism test and a timestamp-bearing manifest. | Add a double-run regression test asserting equal hashes on the deterministic core. |
| **TEST-05** | Tests | Auth tested only at service layer; **no cross-tenant 403/404 test** for jobs/results/exports/ws. | TestClient suite: unauth→401, user-B→user-A's resource→404, expired/typed-token rejection at the route. |

*(Verification-downgraded items now excluded or demoted: HON-06 "CI claims" → low/noise for MASTER_PLAN's unchecked `[ ]` boxes (but README/UI claims stand, see CI-01); SUP-01/SUP-02 supply-chain → medium; PROV-05 unique-constraint → medium; TEST-04/06, HON-03 → medium.)*

---

## 5. The Honesty Ledger

The section the owner cares most about. Each row: **what is CLAIMED** vs **what the code actually DOES**, with file evidence. This is the gap that must close to zero before any "no fabricated metrics" claim is defensible.

| Claim (where) | Reality (code) | Verdict |
|---|---|---|
| **"Signed provenance manifest" / "ed25519 signature" / "verify against `/public-key`"** (README, paper abstract, `pyproject` description, `CITATION.cff`, `provenance.py:12-17` docstring) | `provenance.py:119` `signature = f"sha256:{manifest_hash}"` — the hash of the content, relabeled. No keypair, no signing code (`grep ed25519\|nacl` = docstrings only), no `/public-key` endpoint. | **FABRICATED.** Note the *API* docstring (`results.py:251`) is honest ("recompute the hash yourself") — the project lies in some places and tells the truth in others. |
| **Recorded "tool versions" = what actually ran** (provenance purpose; manifest `pipeline.tool_versions`) | `worker/__init__.py:15-24` is a hardcoded dict written verbatim into the manifest; no stage runs `--version`. Can silently drift from the binary. | **ASSERTED, NOT MEASURED.** |
| **"cutadapt 4.9 — primer trimming"** (`TOOL_VERSIONS`, Dockerfile.worker:8 comment) | Zero cutadapt invocations anywhere; `primer_set` never read. | **DECLARED, NEVER EXECUTED.** |
| **"iucn-api-v3" data source** (`tool_version` strings, paper Methods) | Code hits GBIF's IUCN mirror with no token; the v3 URL constant (`conservation.py:42`) is dead/unused; v3 is being retired. | **FALSE PROVENANCE.** |
| **"Real SRA benchmark: 51 ASVs, 215.4s, Shannon 2.585"** (README:124-130, paper) | No generating script (`benchmark.py` has only `run_16s_known_composition`); no raw artifact/log; phylum table uses `~25`, `~22,000` round numbers. | **HAND-WRITTEN, UNREPRODUCIBLE.** |
| **"Quality gates enforced in CI", "grep-verified in CI", "≥80% coverage"** (README, ARCHITECTURE.md:254-265, `pyproject.toml:83`) | No `.github/` dir, ever (git history empty). Configured gate is `--cov-fail-under=75`, and `worker/` (2,113 LOC) sits in the coverage source set at 0%, so the blended ceiling is ~65% — the gate is **unattainable** while worker is untested. Only `make ci` (local, manual) exists. | **FALSE / UNVERIFIABLE.** (MASTER_PLAN's own `[ ]` checkboxes are honestly unchecked — the lie lives in README/ARCHITECTURE/UI, not the plan.) |
| **"BERT transformer array" / "dna-bert-v2"** (Demo.tsx:22, HowItWorksSection.tsx:17) | No ML/transformer anywhere; real stack is fastp→vsearch→scikit-bio. "dna-bert + vsearch UNOISE3" is self-contradictory to any domain reviewer. | **FABRICATED METHOD.** |
| **CredibilitySection: live DB latencies (12/24/45/112 ms), `100%` BENCHMARK_ASSIGNMENT_RATE, `100%` PROVENANCE_HASH_MATCH, `2.4M` seqs, "SYNCING" status** (`CredibilitySection.tsx:5-11`) | All hardcoded literals animated by a `Counter` under `PERF_MONITOR` / `root@relict-node-01:~#` framing. `100%` assignment is biologically implausible. | **FABRICATED TELEMETRY.** |
| **`/visualize` "VISUALIZATION_ENGINE_V2 [ INTERACTIVE ] [ LIVE ]"** (Visualize.tsx) | Renders empty placeholder cards with one lucide icon + a button. | **EMPTY THEATRE.** |
| **BiodiversityBadge "biodiversity score" + "+12% from baseline"** (`BiodiversityBadge.tsx:16,173`) | `score` prop never wired to data; `+12%` hardcoded. | **FABRICATED METRIC.** |
| **`is_invasive` (exported, typed `bool` in schema + frontend)** | Structurally always `false`; no list loaded; column `server_default=false`. | **UNCONDITIONAL FALSE NEGATIVE.** |
| **`faith_pd` in `DiversityPublic`** | Never computed/written → always `null`. | **ADVERTISED-BUT-EMPTY.** |
| **`iucn_assessment_year` / `iucn_population_trend` (schema + UI)** | Never populated by the GBIF mirror. | **ALWAYS NULL.** |
| **"Two runs → identical `manifest_sha256`" (byte-reproducible)** (MASTER_PLAN:502, paper §5) | Manifest hashes `timestamp_utc` + runtimes → always differs. No determinism test. `manifest_sha256` column is `UNIQUE`, so true reproducibility would *crash* the second insert (PROV-05). | **SELF-CONTRADICTORY.** |
| **"Passes GBIF DwC-A validator" / "GBIF-compatible"** (RESEARCH_PAPER_PLAN:35) | Exporter exists (`dwca.py`) but no validator run, no archived report, no test. | **UNVERIFIED.** |
| **"QIIME2 `.qza` + papermill notebook export"** (MASTER_PLAN:493-498) | `grep qza\|papermill\|qiime` = nothing; only dwca/csv/biom/report implemented. | **VAPORWARE.** |
| **"submission to GBIF" (citizen science)** (package.json:95) | `exports.py:104-109` returns a ZIP attachment; no IPT/registry call. | **DOWNLOAD-ONLY (overstated).** |

**Ledger directive:** every one of these must be made true, relabeled honest, or deleted. There is no fourth option for a project whose brand is "no fabricated metrics."

---

## 6. Scientific Defensibility

What must change for results to survive peer review (MEE/MER) and be trusted by a forest department.

1. **Chimera removal (BIO-01)** — mandatory `vsearch --uchime3_denovo` pass after UNOISE3. Without it, every richness/diversity number is inflated. *This is the single biggest scientific bleeder.*
2. **Primer trimming (BIO-02)** — actually run cutadapt with per-marker forward/reverse primers and `--discard-untrimmed` before QC. Primers on ASVs corrupt dereplication and taxonomy.
3. **Paired-end support (BIO-03)** — ingest R1+R2, merge (`fastp --merge`/`vsearch --fastq_mergepairs`), record merge rate. The dominant real data type is currently unanalyzable correctly.
4. **Taxonomy: per-rank gating + LCA (BIO-06)** — stop reporting species from a single 80% best hit. Apply marker-specific identity floors (species ≥97–98% for COI/16S), compute an LCA/SINTAX consensus over `maxaccepts`, emit an "unassigned/ambiguous" state, and truncate the lineage when support is insufficient. Rename stored `confidence`→`percent_identity`. **This directly de-risks the conservation flags downstream.**
5. **Marker-aware references, hard-fail on miss (BIO-05, BIO-10)** — strict per-marker DB map (SILVA/PR2 for 16S/18S, MIDORI2 for COI/12S, UNITE for ITS2, curated rbcL); delete the SILVA-for-rbcL/ITS2 mapping and the "biggest-FASTA" fallback; fail loudly when the correct DB is absent.
6. **Per-marker parameters (BIO-08)** — length windows + identity thresholds keyed by amplicon, threaded through every stage.
7. **The single-sample "ordination" problem (BIO-04)** — it is *not* ordination; it is k-mer composition clustering of one sample with abundance stripped. Either relabel it honestly or replace with real multi-sample Bray-Curtis/Jaccard/UniFrac PCoA. Remove the misleading figure from the paper until real.
8. **Statistics hygiene (BIO-09)** — drop Chao1 on denoised data; add rarefaction/normalization; document single-sample limitations explicitly.
9. **Controls & contamination (BIO-11, DIFF-03)** — add a sample `role` (sample/negative/positive), implement decontam-style negative-control subtraction, and auto-score the **mock control FASTQs already shipping unused** (`Mock_S280`, `HMP_MOCK`) against expected composition. This turns eDNA's false-positive critique into a strength.
10. **Multi-dataset benchmark vs QIIME2/DADA2 (DOC-02)** — ≥4 published datasets, identical inputs, genus-Jaccard + Shannon Δ within preregistered tolerances + wall-time. Compare ERR2283086 to its known mock composition, not just internal self-consistency.

---

## 7. The Signature Differentiators

The boldest, genuinely-novel, **implementable-on-real-data** features that would make Relict the most unique open eDNA platform. Pulled from the creative + novelty dimensions, ranked by differentiation-per-effort.

### ⭐ Flagship — Ecosystem Integrity Index (EII): a transparent biodiversity grade matrix (DIFF-01)

A single scientifically-defensible **0–100 score rendered as an A+…F grade matrix**, where *every sub-score traces to a real computed input* and the exact formula is emitted into the (now-real) signed manifest. This is the screenshot-able, citable artifact no open eDNA tool has — but **only if it is glass-box, never a black box.**

**Methodology sketch (publish as `docs/methods/eii.md` with citations + confidence bounds):**

```
EII = 100 × Σ wᵢ · sᵢ ,  Σ wᵢ = 1,  each sᵢ ∈ [0,1]

s₁  Richness completeness   = observed_richness / Chao1_estimate     (sampling adequacy)   w≈0.20
s₂  Evenness                = Pielou J' (already computed)            (community balance)   w≈0.20
s₃  Threat-weighted health  = 1 − Σ(IUCN_weight·detected)/N,
                              CR=1.0 EN=0.8 VU=0.6 NT=0.3 LC=0       (conservation signal)  w≈0.25
s₄  Invasive penalty        = 1 − (invasive_detections / N)          (needs real GISD list) w≈0.15
s₅  Taxonomic distinctness  = f(GBIF rarity: low occurrence = high signal)                  w≈0.20
```

- Sub-scores `s₃`/`s₄` depend on **first fixing CONS-04 (real invasive list) and BIO-06 (defensible species calls)** — the EII must not launder over-confident taxonomy.
- Render each grade-matrix cell as a click-through to its source metric + the manifest line that produced it.
- **Immediately delete** the fake `+12% from baseline` / decorative `BiodiversityBadge` — every visible number must trace to a real input or the central promise breaks.
- New file: `backend/worker/pipeline/integrity_index.py`. Effort **M**.

### ⭐ Cryptographically real, publicly verifiable provenance + one-click reproduce (DIFF-02 / NOV-01)

Make the *existing* trust pillar actually true: Ed25519 keypair on startup → sign `compute_manifest_hash()` → serve `GET /public-key` → a **public, no-auth `/verify` page** (paste a manifest, get PASS/FAIL on content-hash *and* signature) → a **"Reproduce this run"** button emitting a container-pinned `docker run` bundle (pinned tool versions, reference-DB SHA256s, params) that regenerates the identical `manifest_sha256`. Optionally anchor the hash to a public transparency log (Sigstore/Rekor). This would make Relict the **only** eDNA platform with tamper-evident, third-party-verifiable results. Effort **M**. *Scaffolding already records inputs/versions/DBs/params (`provenance.py:46-65`), so this is a small delta — not a rewrite.*

### ⭐ Control-aware, contamination-flagged, LCA-confident detections (DIFF-03)

Negative-control subtraction (decontam prevalence/frequency), positive-mock validation badge ("controls passed"), and LCA/consensus taxonomy with explicit confidence + ambiguity flags — using the **mock control FASTQs already in the repo**. Makes every detection defensible against eDNA's core false-positive critique, and is *more rigorous than most published pipelines*. Effort **L**.

### Geospatial + temporal + GBIF historical-range overlay (DIFF-04)

Add Darwin Core `decimalLatitude/decimalLongitude/eventDate` columns to `Sample`; real cross-sample Bray-Curtis/PCoA; pull GBIF occurrence *coordinates* (not just counts) and overlay "your detection vs known range" on a map + timeline, **auto-flagging range-expansion candidates**. Effort **L**.

### Phylogenetic placement + Faith's PD / UniFrac (DIFF-05)

The code already admits this is deferred (`diversity.py:14`). Add mafft+FastTree (or EPA-ng/SEPP placement onto a reference tree) → Faith's PD + UniFrac via scikit-bio; render an interactive tree with detected taxa colored by IUCN status; place unassigned ASVs so "unclassified" becomes "novel lineage near X." Effort **L** — and it finally makes `faith_pd` (DB-03) real instead of always-null.

---

## 8. Competitive White Space

Where Relict *genuinely* beats the incumbents — and where it must stop pretending.

| Vs | They have | Relict's real edge (defensible) | Where Relict currently overclaims |
|---|---|---|---|
| **nf-core/ampliseq, eDNAFlow, PEMA** | DADA2 ASVs, QIIME2 integration, phylo placement, multi-region, community-tested releases; CLI-only | A **web app + job queue + WebSocket progress** lowering the barrier for non-bioinformaticians/citizen-science (NOV-04) | Pipeline rigor is *bettered* by them; Relict is "an interpretation/provenance layer on top of standard denoising," not a denoising competitor. Missing chimera removal is a glaring deficit vs ampliseq. |
| **GBIF Metabarcoding Data Toolkit (MDT)** | A GBIF-built web app that converts ASV tables to DwC-A **and publishes directly to GBIF** | Relict produces DwC-A **from raw FASTQ in the same run**; MDT starts from a pre-made OTU/BIOM table (NOV-02) | "Submission to GBIF" — Relict only returns a ZIP; MDT does true publishing. Reframe to "FASTQ→DwC-A in one pass," link MDT as the downstream publisher. |
| **Pest Alert Tool (PMC10320087)** | Peer-reviewed web tool flagging species-of-concern in metabarcoding | Relict flags **IUCN Red List category + GBIF occurrence inline per species-level ASV within the same run** (NOV-03) | `conservation.py:22` "no existing open tool automates this" is too strong — narrow the claim and cite Pest Alert + GBIF taxon-match as related work. |
| **NatureMetrics, Jonah Ventures (JonahInsight)** | Commercial eDNA→conservation dashboards used by WWF/RSPB; TNFD/SBTN reporting (NOV-05) | **Open-source, self-hostable, MIT, verifiable provenance, no lock-in** | "Conservation dashboard" is not novel at the product level — lead with *open + reproducible + auditable*, treat conservation flagging as transparent table-stakes. |
| **SLIM (PMC6381720), ranacapa (PMC6305237)** | Browser-based metabarcoding GUIs since 2019 (NOV-06) | The **integrated conservation + (real) provenance + DwC-A end-to-end from FASTQ** combination SLIM does not do | "Browser-based eDNA" is not itself novel — acknowledge SLIM/ranacapa as prior art. |

**Precise, falsifiable novelty claim to lead with:**
> *"The only open-source, self-hostable, reproducible pipeline that attaches IUCN Red List category + GBIF occurrence to every species-level ASV within a single FASTQ→DwC-A run, with cryptographically verifiable provenance."*

Add a related-work comparison table (Relict vs QIIME2 vs Anacapa vs PEMA vs MetaWorks vs MGnify vs GBIF MDT vs NatureMetrics) so reviewers don't catch the omission first (DOC-06).

---

## 9. Phased Transformation Roadmap

### Phase A — Truth & Safety (weeks 1–3) — *do this before anything else*

Restore the "no fabricated metrics" promise + close the exploitable security/deploy holes + stand up CI.

| Task | Files | Effort | Maps to |
|---|---|---|---|
| Decide signing: implement Ed25519 **or** rename to `manifest_sha256`/`content_hash` everywhere | `provenance.py`, `run_job.py:321`, `report.py:204`, README, `CITATION.cff`, `pyproject`, paper, UI | M | PROV-01, HON-01, DOC-01 |
| Strip fabricated UI: delete `+12%` badge, BERT lines, fake telemetry; wire CredibilitySection to `/health` + real benchmark or label "illustrative" | `BiodiversityBadge.tsx:173`, `Demo.tsx:22`, `HowItWorksSection.tsx`, `CredibilitySection.tsx`, `Visualize.tsx` labels | S–M | HON-07/08/09, UX-03/04, DIFF-01 |
| Capture real tool versions (`--version` at runtime); fix `iucn-api-v3` provenance string | `worker/__init__.py`, `qc/denoise/taxonomy/diversity.py`, `conservation.py:129` | S | HON-03, PROV-06, CONS-01/02 |
| Make manifest deterministic; drop `UNIQUE` on `manifest_sha256`; record output hashes + ref-DB hashes regardless of size | `provenance.py:49,74,119`, `run_job.py:291,294`, `models.py:365`, migration | S–M | PROV-02/03/05/07 |
| Conservation fail-loud: persist per-record `error`, expose `lookup_failed_count`, never `0 Threatened` on error; read-through cache + TTL | `conservation.py`, `run_job.py:411-439`, `results.py:217`, `schemas/conservation.py`, `JobResults.tsx:208` | M | CONS-05/03 |
| `is_invasive` → `null`/"not assessed" until a real GISD list ships | `conservation.py`, `schemas/conservation.py:19`, `api.ts:142`, `JobResults.tsx` | S | CONS-04 |
| Streaming bounded uploads + Content-Length pre-check + decompression-bomb guard | `storage.py:114-123`, `samples.py:88`, new middleware, `qc.py` | M | SEC-01, SEC-08 |
| Rate limiting on `/auth/*` + per-user job/upload caps; security-headers middleware (HSTS/CSP/nosniff/frame-deny); dummy-hash on missing-user login | `main.py`, `auth.py:94-98`, `deps.py:45-49` | M | SEC-02/03/04/07 |
| `.github/workflows/ci.yml`: frontend tsc/eslint/build + backend ruff/mypy/pytest `--cov` + repo-wide no-mock & no-`shell=True` greps; make required | new | M | CI-01, TEST-03 |
| `preDeployCommand: alembic upgrade head`; fix `render.yaml` `download_references.sh`→`.py`; fail-fast on missing `MINIO_*` | `render.yaml`, `config.py` | S | DEPLOY-01/02/03 |

**Exit criteria:** zero rows remaining in the Honesty Ledger (each made-true, relabeled, or deleted); CI green and required on a PR; a fresh `render.yaml` deploy reaches a healthy end-to-end state; no unauthenticated/cheap RAM-DoS; manifest is deterministic and double-run-equal in a CI test.

### Phase B — Scientific Rigor (weeks 4–8)

| Task | Files | Effort | Maps to |
|---|---|---|---|
| Chimera removal stage (`--uchime3_denovo`) | `denoise_vsearch.py`, `run_job.py` | S | BIO-01 |
| Primer trimming (cutadapt, per-marker) before QC | new `cutadapt.py` stage, `run_job.py`, `Sample.primer_set` | M | BIO-02 |
| Paired-end ingest + merge + merge-rate metric | `qc.py`, `run_job.py:182`, `dereplicate.py` | L | BIO-03 |
| Per-rank identity gating + LCA/SINTAX consensus; `confidence`→`percent_identity` | `taxonomy.py:36,161-173`, `run_job.py:393`, models/migration | L | BIO-06 |
| Strict per-marker DB map; remove SILVA-for-rbcL/ITS2 + biggest-FASTA fallback; hard-fail on miss | `run_job.py:108-143` | M | BIO-05, BIO-10 |
| Per-marker param table keyed by `Amplicon` | `run_job.py`, all stage param dataclasses | M | BIO-08 |
| Drop Chao1 on denoised data; add rarefaction; relabel/replace single-sample "ordination" | `diversity.py`, `ordination.py`, paper | M | BIO-09, BIO-04 |
| Controls + decontam + mock validation (uses existing mock FASTQs) | new `decontam.py`, `Sample.role`, `run_job.py` | L | BIO-11, DIFF-03 |
| Pipeline test suite: `_compute_metrics` unit tests + ≤5 MB FASTQ fixture + e2e `run_job` + determinism + cross-tenant 403/404 + Alembic-path integration | `backend/tests/`, `fixtures/` | L | TEST-01/02/05/07/08 |

**Exit criteria:** dechimerized, primer-trimmed, paired-end ASVs; no species call without per-rank support + LCA; wrong-DB requests fail loudly; pipeline coverage real and `--cov-fail-under` honestly met; controls badge passes on mock data.

### Phase C — Signature Differentiators + Design (weeks 9–14)

| Task | Files | Effort | Maps to |
|---|---|---|---|
| Ecosystem Integrity Index + glass-box methodology doc + grade matrix UI | new `integrity_index.py`, `docs/methods/eii.md`, new React grade-matrix | M | DIFF-01 |
| Real `/verify` page + `/public-key` + "Reproduce this run" bundle | `provenance.py`, new endpoint, new public page | M | DIFF-02 |
| Build real `/visualize` + JobResults charts (recharts treemap, rarefaction, IUCN donut, true ordination) from existing APIs | `Visualize.tsx`, `BiodiversityCharts/Metrics.tsx`, `JobResults.tsx` | L | UX-02, FE-01 |
| Geospatial/temporal + GBIF range overlay; phylo placement + Faith's PD/UniFrac | `Sample` model+migration, `conservation.py`, new tree stage, `diversity.py:14` | L | DIFF-04/05, DB-03 |
| Unify design system (kill orphan tokens, extend cyber-terminal to results, raise contrast); token refresh + error boundaries + skeletons; prune 40 unused shadcn primitives; accessibility pass | `index.css`, `tailwind.config.ts`, `JobResults.tsx`, `api.ts`, `App.tsx`, `src/components/ui/` | L | UX-01/05/06/08, FE-02/03/04/05/06 |
| DB hot-path indexes + per-job conservation snapshot + paginate `/asvs` + DB-side COUNT | `models.py`, `jobs.py:68`, `results.py`, migrations | M | DB-01/02/04 |

**Exit criteria:** EII computed and fully traceable; provenance independently verifiable by a third party; `/visualize` renders real per-job charts; one coherent design system; every API-exposed field is real or explicitly optional-with-reason.

### Phase D — Validation & Paper (weeks 15–20)

| Task | Files | Effort | Maps to |
|---|---|---|---|
| Multi-dataset benchmark vs QIIME2/DADA2 (≥4 datasets, tolerance bounds, wall-time) + committed scripts/artifacts | `benchmark.py`, new comparison scripts, `docs/benchmarks/` | XL | DOC-02, NOV-04 |
| Reproducible SRA benchmark (download→run→machine-readable JSON+log; regenerate `.md`) | `benchmark.py`, `docs/benchmarks/sra_*.md` | M | HON-04/05/10 |
| GBIF DwC-A validator run + archived report + structure test | `dwca.py`, `backend/tests/`, `docs/` | S | DOC-07 |
| Purge unimplemented-feature claims; related-work comparison table; funding/COI/ethics statements; reconcile affiliation/version/commit | `CITATION.cff`, README, paper | S–M | DOC-03/04/06/08 |
| Observability (sentry-sdk on API + RQ worker, log drain); hash-pinned lockfile + digest-pinned base images | `pyproject`, Dockerfiles, `render.yaml` | M | OBS-01, SUP-03, DOCKER-01 |

**Exit criteria:** every paper claim backed by a committed, regenerable artifact; DwC-A validator pass archived; canonical metadata free of unimplemented tools; submission-complete front matter; production observable.

---

## 10. What Shaurya Must Provide

Consolidated, deduped. Without these, specific tasks above are blocked.

| What | Where to get it | Why / which task it unblocks |
|---|---|---|
| **IUCN Red List API token — v4, NOT v3** | `api.iucnredlist.org/api/v4` (request via the IUCN Red List API portal; v3 `apiv3.iucnredlist.org` is being retired). 1–3 business days. | Either populate real IUCN category/year/trend directly (CONS-01/08), or confirm the decision to use the GBIF mirror and drop the token gate. Fixes `iucn_assessment_year`/`iucn_population_trend` always-null. |
| **GBIF — no key needed (confirm)** | `api.gbif.org/v1` species/match + occurrence/search are free/unauthenticated. | Confirms no credential needed for conservation + the DIFF-04 coordinate overlay. For *true publishing* (NOV-02) you'd need a **GBIF organization + IPT/registry OAuth** — decide if in scope. |
| **NCBI / Entrez API key (optional)** | NCBI account → API key (raises rate limit to 10 req/s). | Only if reference-DB download fallbacks (`download_references.py`) hit NCBI; otherwise skippable. |
| **Multi-dataset benchmark inputs (≥4)** + their **published ASV/OTU tables** | Specific real, downloadable accessions: **ERR2283086** (already in repo — needs its published mock composition for ground-truth); plus e.g. **Stoeckle 2017** (Hudson River 12S), **Leray 2013** (COI), **EMP 16S subset**, **MGnify 18S** study. Pull from ENA/SRA + the papers' supplementary tables. | DOC-02 / NOV "honest head-to-head benchmark" — required for any methods-paper submission. Without the *expected* compositions, you can only show self-consistency, which desk-rejects. |
| **Curated reference DBs for non-rRNA markers** | **UNITE** (ITS, unite.ut.ee), a **curated rbcL set** (e.g. BCDB/BOLD-derived), **MIDORI2** COI/12S (already partially present), **PR2** (18S). | BIO-05 strict per-marker mapping — currently rbcL/ITS2 wrongly hit SILVA. |
| **GISD / region-specific invasive-species list** | GISD (Global Invasive Species Database) export, or a region list (e.g. CABI), versioned with source+date. | CONS-04 — ships `invasive_species.json` so `is_invasive` becomes real instead of always-false. |
| **Object storage (S3-compatible)** | **Cloudflare R2** or **Backblaze B2** (cheapest viable); create bucket + access/secret keys. | DEPLOY-03 — FASTQ upload (the platform entry point) is dead without it; `MINIO_*` are required env vars with no defaults. |
| **Reference-DB disk + provider checksums** | Render persistent disk (≥20 GB, already in `render.yaml`) + **provider-published SHA256s** (SILVA/NCBI publish `.md5`/`.sha`; pin a known-good MIDORI2 digest in-repo). | SUP-01 — converts trust-on-first-use into real verification; hard-fail on first-download mismatch. |
| **Zenodo account** | zenodo.org (free) → mint a DOI for the benchmarked release. | DOC-08 / DIFF-06 — DOI-able method cards + a citable pinned commit for the paper. |
| **Decision: Ed25519 signing — implement or relabel?** | — | PROV-01/HON-01 — the single biggest credibility fork. Implementing preserves the novelty pillar; relabeling is honest but weakens the pitch. Pick one *now*. |
| **Decision: scope of GBIF publishing** | — | NOV-02 — "FASTQ→DwC-A in one pass + link MDT as downstream publisher" (cheap, honest) vs full IPT/registry OAuth integration (L effort, true first). |
| **Decision: DADA2 engine — build or remove claim?** | — | DOC-03/BIO core — either add DADA2 as an inference option (closes the rigor gap vs ampliseq) or strip it from `CITATION.cff`/README until shipped. |
| **Single contact email + reconciled affiliation/version** | — | DOC-08 — paper says "Thapar Institute" + `workwithshaurya10@`, README says "Independent", versions drift 0.1.0-dev vs 0.2.0. Pick one of each. |

---

*End of source-of-truth document. Phase A is non-negotiable and ordered first: a platform branded "no fabricated metrics" cannot ship a single fabricated metric, signature, or telemetry value. Everything else builds on that restored credibility.*