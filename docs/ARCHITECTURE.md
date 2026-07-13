# ARCHITECTURE — Relict

> This document describes the **target architecture**. The current state of
> the repository is Phase 0 (docs + scaffolding). See
> [`MASTER_PLAN.md`](./MASTER_PLAN.md) for the phase-by-phase rollout.

---

## 1. Goals the architecture must meet

1. **Reproducibility** — same inputs and same parameters must produce the
   same outputs, bit-for-bit where possible.
2. **Multi-user, concurrent** — two users uploading at the same time must
   never corrupt each other's job state.
3. **Fail loudly, fail visibly** — when a bioinformatics stage fails, the
   user sees the real error in the UI and the full stderr is captured in
   structured logs.
4. **No bioinformatics in the HTTP process** — long-running work runs in a
   worker, never in a request handler.
5. **Replaceable pieces** — object storage, queue, database, and auth can
   each be swapped without rewriting the pipeline.
6. **Honest provenance** — every output ships with a signed manifest
   recording how it was made.

---

## 2. System diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                            User Browser                             │
│  React 18 + TypeScript + Vite + Tailwind + shadcn + React Query     │
└──────────┬──────────────────────────────────────────┬───────────────┘
           │ HTTPS (REST)                             │ WSS
           ▼                                          ▼
┌──────────────────────────────────┐   ┌──────────────────────────────┐
│        FastAPI Application       │   │  WebSocket (per-job channel) │
│  uvicorn + Pydantic v2 + JWT     │◀──│  Progress events, stage logs │
│  app/main.py                     │   └──────────────────────────────┘
└────┬─────┬───────────┬───────┬───┘
     │     │           │       │
     │     │           │       │ enqueue
     │     │           │       ▼
     │     │           │    ┌──────────────┐
     │     │           │    │    Redis     │
     │     │           │    │  (RQ queue + │
     │     │           │    │   pub/sub)   │
     │     │           │    └──────┬───────┘
     │     │           │           │ pop
     │     │           │           ▼
     │     │           │    ┌────────────────────────────────────────┐
     │     │           │    │          RQ Worker Container           │
     │     │           │    │  Python 3.11 +                         │
     │     │           │    │    fastp, vsearch, R + DADA2,          │
     │     │           │    │    BioPython, scikit-bio,              │
     │     │           │    │    umap-learn, hdbscan, cutadapt       │
     │     │           │    │                                        │
     │     │           │    │  backend/worker/pipeline/*.py          │
     │     │           │    └──┬─────────────────────────┬───────────┘
     │     │           │       │                         │
     │     ▼           ▼       ▼                         ▼
     │  ┌───────────────────────────┐        ┌───────────────────────┐
     │  │        PostgreSQL         │        │   MinIO (S3-compat)   │
     │  │  users, jobs, samples,    │◀──────▶│  Raw FASTQs           │
     │  │  asvs, taxa, diversity_   │        │  Trimmed FASTQs       │
     │  │  metrics, conservation_   │        │  ASV FASTAs           │
     │  │  cache, provenance,       │        │  Reports (PDF)        │
     │  │  sessions                 │        │  DwC-A archives       │
     │  └───────────────────────────┘        │  Provenance manifests │
     │                                        └───────────────────────┘
     │
     │ outbound (cached)
     ▼
┌─────────────────────────────────────────────────────────┐
│                   External APIs                         │
│   GBIF Species & Occurrence    https://api.gbif.org     │
│   IUCN Red List                https://apiv3.iucnredlist.org│
│   NCBI Entrez (optional)       https://eutils.ncbi.nlm.nih.gov│
└─────────────────────────────────────────────────────────┘
```

---

## 3. Components

### 3.1 FastAPI application (`backend/app/`)

Responsibility: HTTP + WebSocket API only. **Never** runs bioinformatics
itself.

- **Entrypoint:** `app/main.py` → `create_app()` factory with lifespan
  hooks that verify Redis + Postgres + MinIO connectivity on startup.
- **Config:** `app/core/config.py` using Pydantic Settings with all secrets
  loaded from env vars defined in `.env.example`.
- **Auth:** JWT access + refresh, argon2id password hashing, roles
  `{user, admin}`. Rate limiting via `slowapi`.
- **Schemas:** all request and response bodies are Pydantic v2 models with
  strict validation. Uploads have a hard size limit (configurable,
  default 500 MB) and a MIME-sniff check.
- **Routes (v1):**
  - `POST /auth/signup`, `POST /auth/login`, `POST /auth/refresh`
  - `POST /samples/upload` — multipart, streams to MinIO
  - `POST /jobs` — enqueue a job for one or more uploaded samples
  - `GET /jobs/{id}` — job status + stage breakdown
  - `GET /jobs/{id}/asvs`, `/diversity`, `/ordination`, `/conservation`,
    `/integrity` (Ecosystem Integrity Index), `/provenance`,
    `/export/report` (HTML), `/export/biom` (JSON), `/export/csv`,
    `/export/dwca`
  - `POST /provenance/verify` — verify a manifest's Ed25519 signature
  - `DELETE /jobs/{id}` — cancel / delete
  - `WS /ws/jobs/{id}` — live progress
  - `GET /public-key` — ed25519 public key for provenance verification
  - `GET /health`, `GET /metrics` (Prometheus)
- **Logging:** structlog JSON logs with job_id / request_id correlation.

### 3.2 RQ Worker (`backend/worker/`)

Responsibility: the actual bioinformatics. Runs as a separate container
image with all tools preinstalled.

- **Entrypoint:** `worker/main.py` starts an RQ worker bound to the
  `edna_jobs` queue.
- **Job handler:** `worker/run_job.py` loads the job from Postgres, creates
  a workspace directory under `/workspaces/{job_id}/`, downloads the
  sample(s) from MinIO, and runs pipeline stages in order.
- **Pipeline stages:** pure-ish functions in `worker/pipeline/*.py`, each
  with the same signature `run(workspace, params, logger) -> StageResult`.
- **Error handling:** a stage that fails raises `StageError(stage_name,
  returncode, stderr_tail)`. The worker marks the job `failed`, writes the
  error to the DB, and publishes a final error event to the WebSocket
  channel.
- **Idempotency:** re-running a job on the same inputs with the same
  parameters produces the same outputs (same hashes, same manifest).

### 3.3 PostgreSQL

Responsibility: all structured state. Schema is defined by Alembic
migrations from day one.

Key tables (see `MASTER_PLAN.md` §1.2 for the v1 schema):

- `users`, `jobs`, `samples`, `asvs`, `taxa`, `diversity_metrics`,
  `conservation_cache`, `provenance`, `sessions`, `api_keys`.

Full-text search indexes on species names. `pgvector` optional for
future embedding-based similarity search.

### 3.4 MinIO (S3-compatible object storage)

Responsibility: all large binaries — raw FASTQs, trimmed FASTQs, ASV
FASTAs, reports, exports, provenance manifests. Addressed by S3 keys
stored in Postgres rows.

In production, MinIO can be swapped for any S3-compatible service
(AWS S3, Cloudflare R2, Backblaze B2, Hetzner Object Storage) without
code changes — the client is abstracted behind `app/services/storage.py`.

### 3.5 Redis

Responsibilities:
1. RQ queue backend.
2. Pub/sub channel for per-job progress events (fed into the WebSocket).
3. Short-lived rate-limit counters.

### 3.6 External APIs (cached)

GBIF, IUCN Red List, and optional NCBI Entrez calls go through
`app/services/external/` with:

- Pinned API versions in the client code.
- On-disk + Postgres cache with a 30-day TTL.
- Every response's SHA256 and `fetched_at` recorded in the provenance
  manifest for reproducibility.

---

## 4. Request lifecycle — "upload a sample, get a conservation report"

1. **Browser** — user drops a FASTQ into `DemoUpload.tsx` or the citizen
   wizard.
2. **Frontend** — `POST /samples/upload` with multipart body. Request
   is streamed directly to MinIO without buffering in memory.
3. **FastAPI** — validates MIME, writes `samples` row, returns `sample_id`.
4. **Frontend** — `POST /jobs` with `{sample_ids, amplicon_preset, params}`.
5. **FastAPI** — inserts `jobs` row with status `queued`, enqueues the
   job ID into RQ, opens a WebSocket, returns `job_id`.
6. **Worker** — pops the job, sets status `running`, creates workspace,
   downloads sample from MinIO.
7. **Worker** — runs pipeline stages in order. After each stage, publishes
   a progress event (`qc: done, asvs: running, …`) to Redis pub/sub.
8. **FastAPI** (WebSocket) — relays events to the browser in real time.
9. **Worker** — when all stages pass, writes results back to Postgres
   (ASVs, taxa, diversity, conservation) and uploads outputs (PDF,
   BIOM, DwC-A, manifest) to MinIO.
10. **Worker** — signs the provenance manifest and marks the job
    `succeeded`. Publishes the final event.
11. **Browser** — transitions to the job detail page and renders real data
    fetched from `/jobs/{id}/*` endpoints.
12. **User** — can download the PDF, BIOM, DwC-A, and manifest from buttons
    wired directly to MinIO (pre-signed URLs).

No stage of this flow contains mock data. Any failure at any step
produces a structured error visible in the UI and in the logs.

---

## 5. Security model

- **AuthN:** JWT access (15 min) + refresh (14 days), argon2id.
- **AuthZ:** a user can only see their own jobs. Admin role exists but is
  not required for normal operation.
- **Upload safety:** size limit, MIME sniff, filename sanitization,
  per-user quota.
- **Subprocess safety:** list-arg subprocess calls only. All user-provided
  strings that reach a subprocess are validated at the schema layer first.
- **Database safety:** SQLAlchemy with parameter binding — no raw SQL
  composition.
- **Secrets:** never committed. Only loaded from env vars via Pydantic
  Settings. `.env.example` is the canonical template.
- **TLS:** in production, a reverse proxy (Caddy or Traefik) terminates
  TLS in front of FastAPI.
- **Rate limits:** per-IP and per-user, configurable via env.
- **CSRF:** not applicable (stateless JWT, no cookies for API) but the
  refresh token cookie (if used) gets `SameSite=Strict`.

---

## 6. Development workflow

```bash
# One-time
git clone <repo>
cd Bad-Omens
cp backend/.env.example backend/.env
make download-dbs     # Phase 2+

# Frontend
npm install
npm run dev           # http://localhost:5173

# Backend (Phase 1+)
cd backend
docker compose up --build
# API:    http://localhost:8000/docs
# MinIO:  http://localhost:9001
# DB UI:  http://localhost:8080 (Adminer)

# Run a real benchmark (Phase 7+)
python scripts/benchmark_mifish_fish_study.py
```

---

## 7. CI/CD

GitHub Actions workflows:

- **`ci.yml`** on every PR:
  - Frontend: `npm ci`, `tsc --noEmit`, `eslint`, `npm run build`
  - Backend: `uv sync`, `ruff check`, `mypy --strict`, `pytest -x --cov`
  - Repo-wide: `grep -rn 'mock\|TODO.*backend\|FIXME' src/ backend/` must
    be empty
  - Benchmark smoke test on a tiny real public dataset
- **`release.yml`** (planned — not yet implemented) on tag `v*`:
  - Build + push Docker images for API and worker
  - Create a GitHub release with auto-generated changelog
  - Trigger Zenodo webhook for a new DOI

---

## 8. What this architecture intentionally does *not* include

- **Kubernetes.** Docker Compose is enough for solo deployments and is what
  the target user (individual researchers) will run.
- **Microservices.** The API and worker are the only processes. Splitting
  further adds operational cost for no benefit at this scale.
- **A "demo mode" that fakes a backend.** The frontend always talks to a
  real API. If you want to evaluate without Docker, run the backend in
  CI mode against a tiny pinned dataset.
- **Its own sequence aligner or classifier.** Aligners and classifiers
  are a solved problem. We use the best-in-class open tools and focus our
  work on the layers above (conservation, reproducibility, citizen
  workflows) — which is where real scientific value is missing today.
