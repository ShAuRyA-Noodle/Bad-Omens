# Relict — Flagship Transformation Plan

*Lead product architect synthesis of four hypermode audits (dead-inventory, frontend-flagship, backend-endtoend, flagship-strategy). Phase-A honesty pass, Ed25519 provenance, and the EII grade-matrix have already landed. This is the plan to turn a working demo into a defensible, million-dollar product.*

---

## 1. Executive verdict

Relict has a **genuinely class-leading core wrapped in a demo-grade product.** The bioinformatics pipeline (fastp → vsearch/UNOISE3 → taxonomy → diversity), the Ed25519-signed provenance manifests, and the glass-box Ecosystem Integrity Index are real, working, and — taken together — unique in the market. Nobody else ships cryptographically signed, independently re-verifiable eDNA results scored by an open, auditable integrity index.

That moat is **invisible and undermined**, for three compounding reasons:

1. **The product surface still lies.** After the Phase-A truth pass, the app still ships a fabricated API-docs page for a non-existent API (`api.relict.dev`, fake species *Thunnus albacares*), a nav-prominent `/visualize` page that renders "AWAITING DATA" forever, a fake header telemetry strip (`SYS.STATUS: ONLINE`), a fabricated footer event-bus with a made-up `MEM: 24.5 GB / 128 GB` readout, an "Impact" page claiming `BLOCKCHAIN_PROVENANCE` (there is no blockchain — it's Ed25519), and a `faith_pd` metric plumbed end-to-end that is always `null`. This is the exact class of theatre Phase A was meant to purge.

2. **The core science is quietly wrong for most inputs.** There is **no amplicon selector anywhere**, so every job defaults to `Amplicon.OTHER` and is force-aligned against **SILVA 16S** — 12S MiFish fish eDNA, COI, ITS2, 18S, rbcL all hit the wrong reference DB. Taxonomy assigns full species from a single 80%-identity best hit with no LCA. Primer trimming (cutadapt) is pinned, installed, version-reported, and **never executed**. The conservation panel is served from a mutable, cross-tenant global cache, so two identical reruns can render different numbers. A costly UMAP ordination is computed every run, hashed into the signed manifest, then `shutil.rmtree`'d — a "reproducible" result that can never be retrieved.

3. **The product is structurally a single-sample toy.** Every upload creates one Job with exactly one Sample. There is **no Project/Study container**, **no georeferenced metadata capture**, **no map**, **no public verify UI**, **no dashboard**, **no notifications**, **no team/org**, **no settings**. Of the three claimed angles — reproducible research, citizen science, open-data commons — only *reproducible research* is even partially end-to-end, and *citizen science* is effectively unbuilt because there is no data to submit and nothing to plot.

**The gap to flagship:** the engine is a Ferrari; the chassis, dashboard, and steering wheel are cardboard. The transformation is not "add features" — it is **(a) delete every lie, (b) make the science correct per-marker, (c) build the Project data model that unblocks everything, then (d) make the existing moat visible.** Do it in that order or the features sit on sand.

---

## 2. Scorecard

| Dimension | Grade | One-line reason |
|---|---|---|
| Dead / Stub / Redundant / Vaporware | **C−** | Real core, but littered with fabricated docs, dead pages, discarded compute, ~40 dead UI primitives, 4 unused deps, 6 dead settings, 4 never-written columns, 12MB stray PDFs. |
| Frontend Product Quality & Mobile | **C−** | Flagship results pages render in a second, half-broken design system — undefined tokens, invisible progress bars, unloaded fonts, mobile-broken 5-col tabs, dead token refresh, surviving fake telemetry. |
| Backend / Pipeline End-to-End | **C** | Solid auth/provenance/EII scaffolding, but no amplicon selection, discarded ordination, cross-tenant conservation cache, un-run primer trimming, best-hit taxonomy — headline results unreproducible and often wrong. |
| Flagship Strategy & Novelty | **C+** | Core + provenance/EII are class-leading, but wrapped in a single-sample demo with no projects/map/metadata/verify UI — the moat is buried in a tab. |
| **Overall** | **C** | **A world-class engine inside a dishonest demo. Fixable, and the fix is a category-defining product.** |

---

## 3. The Dead List — consolidated, deduped, exhaustive

Every dead / stub / redundant / vaporware item across all four audits, merged. `Src IDs` shows the originating audit IDs (dedup key). Actions: **delete** (remove), **build** (make real), **wire** (persist/connect existing work), **fix** (correct/relabel). Effort: S/M/L/XL.

### 3a. Frontend dead code & orphans

| ID | Location | What it fakes / why dead | Action | Effort | Src IDs |
|---|---|---|---|---|---|
| DL-01 | `src/components/ApiDocumentation.tsx:9-97` | Fabricated API: `api.relict.dev/v1`, `/api/analyze`, `/api/species`, OAuth2, fake fields `biodiversity_index:0.82`, fake species *Thunnus albacares*/*Carcharhinus limbatus*, "Python SDK coming soon". Zero resemblance to real FastAPI backend. | delete (or regen from real OpenAPI) | M | STUB-04, D-2, FE-08 |
| DL-02 | `src/pages/ApiDocs.tsx`; `src/App.tsx:39-48` | Full page importing DL-01 with **no route and no nav link** — unreachable. | delete (or route `/developers` to real ReDoc at `/docs`) | S | DEAD-05, D-2, FE-08 |
| DL-03 | `src/pages/Visualize.tsx`; `Header.tsx:23`; `Footer.tsx:55` | Top-nav "VIEW_LOGS" → a `[ AWAITING DATA ]` shell rendering only two CTA cards. Takes no jobId, fetches nothing, uses undefined `text-emerald`. | delete nav+page (rebuild as project analytics later) | L | STUB-06, FE-07, D-3 |
| DL-04 | `src/components/BiodiversityCharts.tsx:6-27` | "Real taxonomy charts… ordination plots" marketing copy + one icon + "Upload a Sample" button. No chart ever drawn. | delete (rebuild with recharts in dashboard) | M | STUB-07 |
| DL-05 | `src/components/BiodiversityMetrics.tsx:6-19` | One paragraph + "Run an analysis" button. Computes nothing; real metrics already in JobResults OverviewTab. | delete | S | STUB-08 |
| DL-06 | `src/components/RegionSelector.tsx:1-3` | Literal `export const RegionSelector = () => null`. Imported nowhere. | delete | S | DEAD-09, D-1 |
| DL-07 | `src/components/TeamSection.tsx` | 236-line architect/refs block, 0 imports; About.tsx reimplements it with raw icons. | delete | S | DEAD-10, FE-08 |
| DL-08 | `src/components/ThemeToggle.tsx`; `App.tsx:31` | Toggles light/dark via next-themes, imported nowhere; app is dark-locked (`enableSystem={false}`, empty `.dark {}`), no light tokens exist. | delete (+ next-themes) | S | DEAD-11, FE-21 |
| DL-09 | `src/components/ImpactSection.tsx:154`; `Impact.tsx` | 205-line orphan (0 imports); Impact.tsx reimplements it; advertises "one-click submission to GBIF" — unbuilt. Uses broken emerald/glass tokens + dynamic `bg-${color}`. | delete + strip GBIF claim | S | DEAD-12, FE-08 |
| DL-10 | `src/App.css` | Default Vite starter (`#root{max-width:1280px;text-align:center}`, logo-spin). Would break layout if imported. | delete | S | FE-08 |
| DL-11 | `package.json:69` — `recharts ^3.2.0` | Installed, **zero imports** in `src`. | build (use it) — the whole dataviz story depends on it | S | DEAD-13 |
| DL-12 | `package.json:20,56,75` | `@hookform/resolvers`, `zod`, `date-fns` — zero imports anywhere. | delete | S | DEAD-14 |
| DL-13 | `src/components/ui/` (~40 of 48) | accordion, alert(-dialog), aspect-ratio, avatar, breadcrumb, calendar, carousel, checkbox, collapsible, command, context-menu, dialog, drawer, dropdown-menu, form, hover-card, input(-otp), label, menubar, navigation-menu, pagination, popover, progress, radio-group, resizable, scroll-area, select, separator, sheet, sidebar, skeleton, slider, switch, table, textarea, toggle(-group). Only badge/button/card/tabs/tooltip/sonner/toast/toaster are reachable. Their Radix/cmdk/vaul/embla/input-otp/react-day-picker/react-resizable-panels/react-hook-form deps are dead too. | delete unused + orphaned deps | M | DEAD-15 |

### 3b. Backend dead columns, settings, discarded compute

| ID | Location | What it fakes / why dead | Action | Effort | Src IDs |
|---|---|---|---|---|---|
| DL-14 | `results.py:158-186` + `ordination.py` + `run_job.py:266-270,432-437` | `/ordination` **unconditionally returns `skipped:true`** while the worker runs UMAP+HDBSCAN every job, writes `ordination.json`, hashes it into the signed manifest — then `shutil.rmtree` deletes it. No `getOrdination` in api.ts, no tab. Paid-for "reproducible" result that's destroyed. | wire (persist to JSONB/MinIO, serve, render) or delete stage+endpoint+schema | M–L | DEAD-01, DEAD-02, F2 |
| DL-15 | `models.py:322`; `schemas/results.py:60`; `api.ts:131`; `diversity.py:14` | `faith_pd` is a DB column, Alembic column, Pydantic field, TS field — **never computed** ("deferred to Phase 5"). Every response carries `faith_pd:null`. | build real phylo placement (see F-tier) **or** drop column+migration+schema+TS field | L (build) / L (drop) | DEAD-03, F21, F-1 |
| DL-16 | `models.py:221-223` | `Sample.num_reads`, `read_length_mean`, `primer_set` — declared "populated later", never written; always null. | fix (populate from fastp report) or drop | M | DATA-17 |
| DL-17 | `models.py:292-294`; `run_job.py:471-483` | `Taxon.reference_db_version` + `reference_accession` never written (only `reference_db` filename set); accession is in the blast6 TSV. | fix (persist version+accession) | S | DATA-18, F17 |
| DL-18 | `models.py:226`; `samples.py:117-124`; `dwca.py:123-128` | `dwc_metadata` JSONB exists but is **write-only-empty** — no UI captures eventDate/lat/lon/habitat/recordedBy → DwC-A `occurrence.txt` emits blank coords/date; structurally valid, scientifically empty archive. | build metadata capture at upload | M | DATA-16, P0-2 |
| DL-19 | `config.py:108-115` | `GBIF_USERNAME/PASSWORD/EMAIL`, `NCBI_API_KEY/EMAIL`, `ZENODO_SANDBOX_TOKEN` — referenced nowhere (only `IUCN_REDLIST_TOKEN` used). | delete settings + `.env.example` entries (or build consuming features) | S | DEAD-19 |
| DL-20 | `conservation.py:64`; `integrity_index.py:179-183`; `exports.py:331` | `is_invasive` defaults `False`, **never set** — "GISD curated list" doesn't exist — yet exported in CSV/HTML as authoritative; EII `invasive_pressure` (weight 0.15) hardcoded `available=False`. | build (load GISD/GRIIS) or remove field+column+EII weight | M | F5, F-3 |

### 3c. Vaporware claims (marketing vs reality)

| ID | Location | What it fakes | Action | Effort | Src IDs |
|---|---|---|---|---|---|
| DL-21 | `pkg.json:95`; `MASTER_PLAN.md:49,384`; `ImpactSection.tsx:154`; `exports.py:49-118` | "One-click GBIF/citizen-science submission" — reality is a downloadable ZIP; no IPT/registry push. | build real MDT/IPT flow **or** relabel "export for manual GBIF submission" | XL / S | VAPOR-20, F-5, F19 |
| DL-22 | `MASTER_PLAN.md:400,426`; `ARCHITECTURE.md:177` | "Citizen Mode guided wizard" — no such mode; Demo is a single expert form. | build guided mode (see flagship) or strike from docs | XL | VAPOR-21 |
| DL-23 | `MASTER_PLAN.md:493-505` | "QIIME2 `.qza` export + papermill notebooks" — no qza/papermill/qiime code exists. | build or strike from plan | L | VAPOR-22 |
| DL-24 | `MASTER_PLAN.md:334`; `report.py` | "WeasyPrint PDF report" — only self-contained HTML produced; weasyprint not in deps. | fix (add WeasyPrint path) or relabel "print-ready HTML" | S | VAPOR-23 |
| DL-25 | `Impact.tsx:8` | `BLOCKCHAIN_PROVENANCE` / "immutable JSON manifests" — there is **no blockchain**; real mechanism is Ed25519. | fix → rename `SIGNED_PROVENANCE`, describe Ed25519 hash-chained manifests | S | FE-11 |
| DL-26 | `About.tsx:82-83` | "THEORETICAL_FOUNDATIONS: DNABERT-S… AI-Assisted eDNA" — implies ML taxonomy the pipeline explicitly disavows ("no neural network, no black box"). Residue of the purged BERT narrative. | fix → cite real stack (UNOISE3, vsearch, SILVA/MIDORI2, Darwin Core) | S | FE-18 |
| DL-27 | `Header.tsx:31-34` | `SYS.STATUS: ONLINE // ENV: PRODUCTION // BIODIVERSITY_DB: CONNECTED` — hardcoded fake live status. | fix → bind to `/health`+`/ready`+`api_degraded`, or remove | S | FE-10, DI-1 |
| DL-28 | `Footer.tsx:29-50,88-93` | Fabricated timestamped "SYSTEM EVENT BUS" log stream incl. `MEM: 24.5 GB / 128 GB [OK]`, "FETCHING LATEST NCBI_GENBANK…". Synthetic telemetry as live state. | fix → drive from real `/health` or relabel decorative | M | FE-10 |
| DL-29 | HeroSection readouts; `UseCasesSection.tsx:12,21,30` | Fake sensor coordinates / readouts presented as data. | fix → relabel decorative or bind to real data | S | FE-10 |

### 3d. Redundancy & repo hygiene

| ID | Location | What it duplicates | Action | Effort | Src IDs |
|---|---|---|---|---|---|
| DL-30 | `ordination.py:149-169`; `diversity.py:128-142`; `run_job.py:530-556` | Three near-identical hand-rolled FASTA/`;size=` parsers (`_read_fasta_sequences`, `_extract_abundances`, `_read_fasta_with_sizes`). | fix → one shared parser in `worker/pipeline/__init__.py` | S | REDUN-24 |
| DL-31 | `001.pdf` (6.3MB), `002.pdf` (6.0MB), `relict_paper.pdf` (root + `public/`) | 12MB stray/duplicate PDFs, no references. | delete 001/002; de-dupe paper (keep `public/` or `docs/paper/`) | S | DEAD-26 |
| DL-32 | `UseCasesSection.tsx:76`; `ImpactSection.tsx:70-71` | Runtime `'hover:'+trg.borderH`, `bg-${area.color}` — invisible to Tailwind JIT, hover accents never generated. | fix → static full-class lookup map | S | FE-17 |

**Dead List totals:** 32 consolidated items (from ~50 raw findings across audits). ~13 pure deletes (S/M), ~9 fixes, ~4 wires, ~6 builds. Clearing 3a+3d alone removes an entire orphaned design surface, ~40 UI primitives, 4 npm deps, 6 config settings, and 12MB of repo bloat in roughly **2–3 engineer-days**.

---

## 4. Critical vulnerabilities & data-integrity gaps

| ID | Severity | Location | Failure mode | Fix | Effort |
|---|---|---|---|---|---|
| V-01 | **Critical (science)** | `samples.py:94`; `api.ts:231`; `run_job.py:226` | No amplicon captured → `Amplicon.OTHER` → `_detect_reference_db` falls to `16S_V4`. **Every 12S/COI/ITS2/18S/rbcL job aligned against SILVA 16S.** Headline taxonomy is wrong for all non-16S data. | Capture marker at upload; persist on Job; drive DB selection, GBIF kingdom hint, DwC-A `target_gene`. | M |
| V-02 | **High (integrity)** | `results.py:226-243`; `run_job.py:497-525`; `models.py:331-351` | `ConservationCache` keyed globally by `species`; `/conservation` reads whatever rows any tenant last wrote. Two identical reruns render different numbers; panel diverges from the job's own signed manifest and the EII. | Store per-job conservation output (own table or serve from persisted stage/manifest); keep species cache read-only. | M |
| V-03 | **High (integrity)** | `taxonomy.py:36,161-173` | Single max-identity hit at 0.80 promoted to full 7-rank species; ties resolved by file order (non-deterministic); `confidence = identity/100`. An 80% hit stored as a species at 0.80 confidence. | Per-rank identity gating + LCA over top hits; deterministic tie-break; confidence distinct from raw identity. | L |
| V-04 | **High (correctness)** | `qc.py:56-77`; `Dockerfile.worker`; `tool_versions.py` | cutadapt pinned, installed, version-reported, cited in manifest — **never invoked.** Primers ride through denoising & taxonomy; provenance claims a tool that never ran. | Add real per-marker cutadapt primer-trim before dereplication, or drop cutadapt from manifest/docs. | M |
| V-05 | **Med (DoS)** | `storage.py:127-135`; `run_job.py:199-201` | `MAX_UPLOAD_BYTES` (500 MiB) bounds the **compressed** `.gz` only. A small malicious gzip expands to many GB in the worker, filling container disk → worker down. | Stream-decompress with a byte cap; cap workspace usage; fail loudly past limit. | M |
| V-06 | **Med (integrity)** | `conservation.py:250-281` | `_gbif_lookup` hardcodes `kingdom=Animalia` first → plant/fungal/protist markers mis-resolve to animal homonyms (wrong GBIF keys, occurrence counts, IUCN). Compounds V-01. | Drive kingdom hint from amplicon marker, or omit it. | S |
| V-07 | **Med (auth)** | `api.ts:34-52,205-227`; `use-auth.ts` | `refresh_token` stored but **never used**; no `/auth/refresh` call. First 401 after access-token expiry silently logs the user out mid-job. | On 401: call `/auth/refresh`, swap token, retry once; clear+redirect only on refresh failure. | M |
| V-08 | **Low→Med (XSS blast radius)** | `api.ts:18-29,204-216` | Access JWT **and** 14-day refresh token in `localStorage` → any XSS yields persistent account takeover. | Refresh token → HttpOnly/Secure/SameSite cookie (or access-in-memory); add frontend CSP. | M |
| V-09 | **Med (correctness)** | `exports.py:228-242` | BIOM emitted as JSON labeled "2.1.0" — BIOM ≥2.0 is HDF5; QIIME2 `BIOMV210Format` rejects it, contradicting "Standard format for QIIME 2 import". | Label BIOM 1.0.0 (JSON) + round-trip validate via `biom` lib, or emit real HDF5 2.1. | M |
| V-10 | **Med (integrity)** | `jobs.py:76-98`; `run_job.py:188-418` | `cancel_job` sets `CANCELLED` but the running worker has no cooperative checks and unconditionally sets `SUCCEEDED` at line 415, clobbering the cancel. | Re-read `job.status` between stages, abort to CANCELLED; final transition must not overwrite CANCELLED/FAILED. | M |
| V-11 | **Med (perf/DoS)** | `results.py:105-130`; `JobResults.tsx:165-201` | `/asvs` returns every ASV with full sequence, unbounded; ASVsTab renders all into DOM. Tens of thousands of ASVs → multi-MB payload, frozen browser. | Paginate (limit/offset or cursor); virtualize table; truncate sequence in list + detail fetch. | M |
| V-12 | **Med (perf)** | `jobs.py:65-72`; `20260412_..._initial_schema.py:125` | `list_jobs_for_user` filters `user_id` orders `created_at DESC` but only single-column indexes exist → sort on every page load. | Composite index `jobs(user_id, created_at DESC)`. | S |
| V-13 | **Med (resilience)** | `conservation.py:142-163,248-268` | Serial species lookups, `sleep(0.2)`, single httpx call, no retry. One 5xx/timeout sets `api_degraded=True`, suppressing EII health for the whole run; 200 species = minutes of fragile latency. | Bounded retry+backoff, small concurrency pool, degrade only after retries exhausted. | M |

---

## 5. Mobile & responsiveness mandate

The natural device for a field citizen-scientist is a phone, yet the flagship result surface is desktop-only and, in places, broken. Field submission is inherently mobile — this is not optional polish.

### Screens that break on phones (fix exactly this)

| Screen / Component | Break at ~360–390px | Fix |
|---|---|---|
| `JobResults.tsx:108` tab bar (`grid-cols-5`) | 5 icon+label triggers forced to ~72px cells; `whitespace-nowrap` (`tabs.tsx:30`) makes "Conservation"/"Provenance" overflow and collide with icons. | `overflow-x-auto` scrollable tab strip **or** icon-only under `sm` **or** 3-2 grid; 44px tap targets. |
| ASV / taxonomy / conservation tables | Wide multi-column tables overflow or cramp. | Card-per-row under `md` breakpoint; horizontal scroll containers with `min-w-0`. |
| `HeroSection.tsx:106-110` readout row | Inner `flex space-x-8` keeps two long mono strings side-by-side → body horizontal scroll past 100vw. | `flex-col` + `flex-wrap` on mobile; `min-w-0 truncate`. |
| `IntegrityMatrix.tsx` grade ring + bars | Fixed layout; progress fills invisible (undefined `bg-neon-cyan`) — doubly broken on mobile. | Register colors (FE-03), stack ring above bars under `sm`. |
| `BioNetworkBackground.tsx` (1200 instanced particles, per-frame unproject, always mounted) + `CustomCursor.tsx` | Full-screen r3f loop on every route drains battery, janks scroll; custom cursor is dead weight + double-cursor on touch. | Gate behind `useReducedMotion()` + coarse-pointer check; drop particle count or disable on mobile; pause off-screen; `cursor:none` only on `pointer:fine`, skip mounting cursor on coarse pointers. |
| `HeroSection.tsx:20-34` (150ms setState typing) + `Footer.tsx:40-47` interval | Continuous main-thread re-render of 1500-char strings. | Respect `prefers-reduced-motion`; throttle/disable on mobile. |

### Global responsive standard (enforce in review)

- **No horizontal body scroll at 360px.** Every wide element (tables, diagrams, code) scrolls inside its own `overflow-x:auto` container.
- **Breakpoints:** design mobile-first; `sm` 640 / `md` 768 / `lg` 1024. Tables → cards under `md`; tab bars scroll or collapse under `sm`.
- **Tap targets ≥ 44×44px.**
- **Reduced motion:** all decorative animation (3D bg, cursor, marquees, typing, log stream) gated behind `useReducedMotion()` + coarse-pointer; off-screen work paused.
- **WCAG AA text contrast ≥ 4.5:1** on pure black — raise `--muted-foreground` (currently `183 15% 40%` ≈ 3.7:1) and `text-gray-500/600` (≈3.3/2.3:1) to `gray-400`/foreground; reserve dim grays for decorative micro-labels only. Automated contrast check in CI. *(FE-14)*
- **SPA nav only:** replace raw `<a target=_self>` internal links (`Footer.tsx:54-57,106-114`) with `<Link>` to stop full reloads that re-mount the Three.js scene; `rel="noopener noreferrer"` on externals. NotFound uses `<Link>`, not `<a href="/">`. *(FE-13, FE-12)*

---

## 6. Foundation-first plan (Phase 0) — solidify the base before any feature

**No flagship feature ships until Phase 0 is green.** Exit criteria are hard gates.

### 6.1 Resolve the entire Dead List
- **Delete pass** (DL-05,06,07,08,09,10,12,13,31 + delete DL-01/02 if not rewritten): remove orphan components, App.css, unused deps, ~40 UI primitives, stray PDFs, dead config settings (DL-19).
  - Files: `src/components/{ImpactSection,TeamSection,ThemeToggle,RegionSelector,BiodiversityMetrics}.tsx`, `src/App.css`, `src/components/ui/*` (unused), `package.json`, `config.py:108-115`, repo-root PDFs.
  - **Exit:** `npm run build` clean; `depcheck`/`ts-prune` report zero unused; grep finds no reference to deleted symbols; `.env.example` matches `config.py`.
- **Truth pass** (DL-25,26,27,28,29,32): rename `BLOCKCHAIN_PROVENANCE`→`SIGNED_PROVENANCE`; fix DNABERT-S citation; bind header/footer telemetry to `/health` or relabel decorative; static-class hover map.
  - **Exit:** no string in the app asserts a system state, capability, or citation that the codebase does not implement. A reviewer can trace every factual claim to code.
- **Vaporware reconciliation** (DL-21,22,23,24): strike unbuilt GBIF-push/Citizen-wizard/QIIME2-qza/papermill/WeasyPrint from `pkg.json` description, `MASTER_PLAN.md`, `ARCHITECTURE.md`, UI copy — **or** move to the explicit build backlog (Phase 2–3). No doc presents an unbuilt thing as delivered.
- **API docs decision** (DL-01,02): delete both, add `/developers` linking real ReDoc at `/docs`.

### 6.2 Unify the design system *(FE-01,02,03,05; DESIGN-25; DS-1)*
Commit to **one** system. Recommended: a calm, evidence-first editorial palette (Linear/Benchling/NatureMetrics register) for credibility with regulators/ESG buyers — keep one tasteful signature motif, drop the fake HUD. If the terminal aesthetic is retained, apply it end-to-end.
- Define every referenced token in `index.css` (`emerald`, `deep-indigo`, `glacier`, `off-white`, `ink`, `sidebar-*`, `gradient-hero`, `shadow-glass`) **or** delete the phantom tokens and restyle `JobResults`/results components in the real palette. **No class may reference an undefined var.**
- Register `neon-green`/`neon-cyan` as real Tailwind colors (or map to primary/secondary) so IntegrityMatrix bars + grade ring are visible and animate.
- Load Space Grotesk in `index.css` **or** remap `font-display`→`font-heading` (Inter).
- Restyle `JobResults` (metric cards, ASV/conservation rows, provenance, export, tabs) into the single chosen system.
- **Exit:** automated check — zero Tailwind classes resolving to `hsl()` of an undefined var; all headings render an intentionally-loaded font; IntegrityMatrix bars visibly fill; landing→results→report are one visual identity; contrast audit passes AA.

### 6.3 Wire ordination persistence (or delete) *(DL-14 / F2)*
- Add `ordination` JSONB column (or MinIO object keyed to job, covered by the signed manifest); persist `points`+`clusters` **before** `shutil.rmtree`; serve from `/ordination`; add `getOrdination` in `api.ts` and a scatter/cluster tab.
- **Exit:** re-fetching `/ordination` for a succeeded job returns the exact bytes that were hashed into its manifest; the plot renders. *(If deferred to cross-sample PCoA in Phase 2, instead delete the stage+endpoint+`OrdinationResponse` now — do not ship discarded signed compute.)*

### 6.4 Fix conservation integrity *(V-02, V-06, DL-20, V-13)*
- Serve `/conservation` from per-job persisted output/manifest, not the mutable global cache; keep `ConservationCache` as a read-only lookup.
- Add the missing **read-through** cache (`fetched_at > now-30d`) before external calls *(F4)*.
- Drive GBIF kingdom hint from marker; add retry/backoff + concurrency; degrade only after retries.
- Decide `is_invasive`: load GISD/GRIIS **or** remove field+column+EII weight.
- **Exit:** two identical reruns of the same job produce byte-identical conservation panels; panel matches that job's manifest and EII; a repeat species analysis hits cache (0 external calls within 30d).

### 6.5 Core science correctness *(V-01, V-03, V-04)*
- Capture amplicon marker at upload → persist on Job → reference-DB selection + GBIF kingdom + DwC-A `target_gene`.
- Add real cutadapt per-marker primer trim before dereplication (or drop from manifest).
- Per-rank identity gating + LCA + deterministic tie-break; confidence ≠ raw identity.
- **Exit:** a 12S MiFish sample aligns against MIDORI2/MitoFish (not SILVA); manifest reflects cutadapt actually ran; a 82%-identity hit collapses to genus/family, not species; reruns are byte-deterministic.

### 6.6 Platform hardening *(V-05, V-07, V-09, V-10, V-11, V-12)*
- Token refresh retry (V-07); decompressed-size guard (V-05); BIOM relabel/validate (V-09); cooperative cancellation (V-10); `/asvs` pagination + virtualized table (V-11); composite index `jobs(user_id, created_at DESC)` (V-12).
- Data-fetch states on results: HUD/editorial skeletons, error cards with retry, true empty states wired to `isLoading/isError` *(FE-22)*.
- Profile reachability: authed avatar/email menu in Header → Profile + Sign out; link every job row to `/jobs/:id` (not `#`) so failed jobs show `error_message` *(FE-09, FE-20)*.
- Dropzone: accept `.gz` / validate by suffix in `onDrop`; clear rejection message *(FE-19)*.
- **Exit:** session survives access-token expiry; cancel actually cancels; 50k-ASV job renders paginated without freeze; jobs list is index-ordered; every results tab distinguishes loading/error/empty; authed users reach Profile from the header; gzipped FASTQ uploads succeed.

**Phase 0 exit gate (whole phase):** Dead List = 0 open items. One design system, no undefined tokens. Ordination persisted or removed. Conservation reproducible. Non-16S jobs scientifically correct. All Section-4 Critical/High vulns closed. Mobile standard met on JobResults + Hero.

---

## 7. Flagship feature build (phased)

Each feature: **what** it is, **why it matters**, **effort.** Phases are ordered so each builds on the last.

### Phase 1 — The foundation entity + make the moat visible

| Feature | What | Why it matters | Effort |
|---|---|---|---|
| **Project/Study data model** *(P0-1)* | New `Project` owning many `Sample`s across many runs; jobs analyze a project's samples together. Migrate single-sample jobs into single-sample projects. | **Load-bearing for everything** — maps, beta-diversity, trends, portfolio, GBIF publishing are all structurally impossible without it. Matches NatureMetrics "whole portfolio" and GBIF MDT "OTU table = many samples". | XL |
| **Georeferenced metadata capture** *(P0-2, DL-18)* | Guided upload form: site lat/lon, eventDate, habitat, recordedBy, marker/primer set — validated against Darwin Core terms, written to `dwc_metadata`, surfaced in exports + map. | Unblocks the entire citizen-science angle (today there's nothing to submit or plot) and makes DwC-A submission-quality. | L |
| **Public `/verify` page + "reproduce this run" bundle** *(P0-4)* | No-auth page: paste/upload a manifest → green/red Ed25519 verdict (backend `/provenance/verify` already exists). Downloadable bundle: manifest + params + tool/DB versions + one-command re-run. | **The single biggest differentiator, currently invisible** — the Provenance tab just dumps a signature string. This is the falsifiable "independently re-verifiable offline" claim, live. | M |
| **Threatened-species spotlight** *(F-4)* | Promote IUCN category / rarity / invasive flag from a buried table row to a prominent card on results header + dashboard + email, with badges and map pin. | The emotional + commercial "we detected a Critically Endangered species here" moment — the demo-defining wow and the ESG-reporting hook buyers pay for. Data already exists. | S |

### Phase 2 — Dashboard, geospatial, temporal

| Feature | What | Why it matters | Effort |
|---|---|---|---|
| **Authenticated dashboard** *(P0-5)* | Real home: recent projects, EII/biodiversity trends, threatened alerts, map thumbnail, running-job status — replacing the marketing landing for logged-in users. | The daily surface of a real SaaS (Benchling model). Today a logged-in user lands on the same marketing page as anonymous visitors; Profile is just a job table. | L |
| **Geospatial map** *(P0-3)* | MapLibre/deck.gl map of sample sites colored by EII grade / threatened species, with a **GBIF historical-range overlay** ("what we detected vs what's ever been recorded here"). | eDNA is place-based; a biodiversity platform with no map is not competitive. The overlay is a concrete, novel differentiator. | L |
| **Temporal trend view** *(T-6)* | Site-keyed samples → EII / richness / threatened-count over survey dates. | Converts a one-off lab tool into a **monitoring subscription** — the core recurring-revenue value prop. Depends on P0-1/P0-2. | M |
| **Per-job charts** *(DL-11, DL-03,04, FE-07)* | Rebuild the deleted `/visualize` slot as real recharts: taxonomy sunburst, alpha diversity, ordination scatter (from Phase 0 persistence). | recharts is already installed and unused; the app promises charts everywhere and draws none. | M |

### Phase 3 — Deep science (the defensible differentiators)

| Feature | What | Why it matters | Effort |
|---|---|---|---|
| **Phylogenetic placement + real Faith's PD / UniFrac** *(DL-15, F-1)* | Align ASVs, insert into a reference tree (SEPP/pplacer or de-novo FastTree); compute genuine Faith's PD + UniFrac. | Turns always-null schema vaporware into a headline metric OTU-table-only tools (nf-core/ampliseq baseline) don't ship, and makes the EII "distinctness" component defensible. | XL |
| **Cross-sample beta-diversity / PCoA** *(F-2)* | Bray-Curtis + weighted/unweighted UniFrac distance matrices across a project's samples, PCoA/NMDS + PERMANOVA. | The comparative output ecologists actually mean by "ordination" — impossible today because jobs hold one sample. Standard QIIME2/ampliseq deliverable. | L |
| **Complete the EII** *(F-3, F16, DL-20)* | Ship `invasive_pressure` (GISD/GRIIS-weighted abundance) + `sampling_adequacy` (Chao1 coverage / rarefaction) so `assessed_weight` reaches 1.0. | Today the flagship index runs at ≤65% of designed weight (2 of 5 components hardcoded off) and looks unfinished in the matrix UI. | M |
| **Paired-end + multi-file support** *(F8)* | R1+R2 in one job, vsearch `--fastq_mergepairs`; stop silently dropping `samples[1:]`. | Standard Illumina 12S/COI paired reads currently cannot be processed. | L |

### Phase 4 — Operate as a real SaaS + close the network loop

| Feature | What | Why it matters | Effort |
|---|---|---|---|
| **Notifications + transactional email** *(T-1)* | Job complete/failed, threatened-species detected, weekly project digest + in-app notification centre. | Table stakes for async work — today a user who closes the tab learns nothing (WS-only push). | M |
| **Observability** *(T-2)* | Sentry on API+worker; Prometheus `/metrics` (throughput, stage latency, queue depth, `api_degraded`); alerts. | Required to operate a paid product; incidents are currently invisible until a user complains. | M |
| **Settings / account / API keys** *(T-4)* | Password/2FA, session revocation (model exists, unexposed), personal API keys, GDPR export/delete. | The ApiDocs page implies an API story with no key issuance behind it; account controls are absent. | M |
| **Teams / orgs / sharing** *(T-3)* | Organizations, members, project-level roles, shareable read-only result links. | The collaboration substrate institutional buyers (NatureMetrics/Benchling) pay for. | L |
| **Onboarding + demo dataset** *(T-5, FE-23)* | One-click bundled demo run, marker-selection help, first-result checklist, plain-language sublabels/tooltips over the terminal jargon. | Conversion feature for the non-expert citizen-science audience — high drop-off today. | M |
| **GBIF/MDT publishing + open-data commons** *(DL-21, F-5)* | One-click publish via MDT/IPT (or validated MDT package + guided handoff); consented public-dataset commons. | Turns single results into a compounding, network-effect data asset. | L |
| **Backup/DR + retention** *(T-7)* | Postgres PITR, object-store versioning/replication, tested restore runbook, retention policy tied to settings. | Signed provenance is the trust anchor; data loss is catastrophic and currently undefended. | M |
| **Per-result data cards** *(F-6)* | DB name+version+coverage, marker limits, confidence caveats, EII version + component availability — rendered in UI + embedded in the signed manifest. | Reinforces the trust/reproducibility brand at the point of consumption. | S |

---

## 8. Novelty & positioning

**The moat already exists; it is unasserted.** Relict ships the two things no competitor ships *together*: cryptographically signed, independently re-verifiable provenance **and** a glass-box, auditable Ecosystem Integrity Index. Today the product positions itself as "another honest eDNA pipeline" *(POS-1)*, so the moat is invisible — buried in a Provenance tab that prints a raw signature and an EII matrix with invisible bars.

**The falsifiable claim to assert:**

> *"Relict is the only eDNA platform where every biodiversity result is Ed25519-signed and can be independently re-verified by a third party, offline — scored by an open, auditable Ecosystem Integrity Index."*

It is falsifiable (anyone can try to verify a manifest offline and check whether competitors offer the same) and — critically — **true today at the engine level.** The work is to make it *visible and demonstrable.*

**The unforgettable demo (three beats, all backed by real features):**
1. **Reveal** — Upload a field sample; the map lights up a pin and a spotlight card fires: *"Critically Endangered species detected here"* (P0-3 + F-4), against a GBIF historical-range overlay showing what's ever been recorded at that site.
2. **Grade** — The EII grade-matrix renders a traceable A–F biodiversity grade with every sub-score and its assessed weight visible (glass-box, no black box).
3. **Prove** — Hand the manifest to a skeptic. On the public `/verify` page (no login), they get a green cryptographic verdict, and the "reproduce this run" bundle re-runs the analysis with one command to byte-identical output (P0-4).

Reveal → Grade → Prove. That triad is the category-defining story, and every beat is a Phase 0/1 deliverable — not vaporware.

---

## 9. Sequenced roadmap

Ordered so the **base is solid before features**. Each milestone has a hard Definition of Done.

| # | Milestone | Scope | Definition of Done |
|---|---|---|---|
| **M0** | **Purge & Truth** (Phase 0.1) | Dead List deletes + truth pass + vaporware reconciliation (§6.1). ~2–3 days. | Zero open Dead List items in categories dead/redundant. Build clean, `ts-prune`/`depcheck` empty. No string in-app asserts an unimplemented state/capability/citation. Docs contain no undelivered "done" claims. |
| **M1** | **One design system** (Phase 0.2) | Reconcile tokens, register neon colors, fix fonts, restyle JobResults, WCAG AA, mobile tab/hero/motion fixes (§6.2, §5). | No class references an undefined var. IntegrityMatrix bars visibly animate. Landing→results→report one identity. Contrast audit AA-clean. JobResults + Hero pass at 360px; 3D bg/cursor gated behind reduced-motion + coarse-pointer. |
| **M2** | **Correct & reproducible core** (Phase 0.3–0.5) | Amplicon capture + per-marker DB; cutadapt; LCA/per-rank gating; ordination persistence; conservation per-job + read-through cache + kingdom hint + is_invasive decision. | 12S sample hits MIDORI2 not SILVA; manifest shows cutadapt ran; low-identity hits collapse to genus; reruns byte-identical; conservation panel matches manifest+EII; ordination re-fetchable = hashed bytes. |
| **M3** | **Platform hardening** (Phase 0.6) | Token refresh, decompression guard, BIOM fix, real cancellation, /asvs pagination, composite index, fetch states, Profile reachability, dropzone `.gz`. | All Section-4 Critical/High vulns closed with tests. Session survives token expiry; cancel cancels; 50k-ASV job renders; every tab has loading/error/empty states. **Phase 0 gate passed.** |
| **M4** | **Foundation entity + moat visible** (Phase 1) | Project model + migration; georeferenced metadata capture; public `/verify` + reproduce-bundle; threatened-species spotlight. | Existing jobs migrated to projects; upload writes populated `dwc_metadata`; a third party verifies a manifest offline via `/verify`; reproduce-bundle re-runs to identical output; spotlight fires on a real threatened detection. |
| **M5** | **Dashboard + geospatial + temporal** (Phase 2) | Authed dashboard, MapLibre map + GBIF range overlay, temporal trends, per-job recharts. | Logged-in user lands on a real dashboard with trends+map; sites plot by EII grade with historical overlay; a repeat-surveyed site shows an EII time series; charts render from persisted data. **The three-beat demo runs end-to-end.** |
| **M6** | **Deep science** (Phase 3) | Phylo placement + Faith's PD/UniFrac; cross-sample PCoA + PERMANOVA; complete EII (invasive + adequacy); paired-end. | `faith_pd` returns real values covered by the manifest; PCoA plot renders across a project; EII `assessed_weight` = 1.0; paired R1/R2 job merges and completes. |
| **M7** | **Real SaaS + network loop** (Phase 4) | Notifications/email, observability, settings/API keys, teams/orgs, onboarding+demo dataset, GBIF/MDT publishing + commons, backup/DR, data cards. | Job-complete emails fire; Sentry+Prometheus live with alerts; users manage keys/sessions/account-deletion; an org shares a project; one-click demo run works; a dataset publishes to GBIF; restore runbook tested. |

**Guiding rule:** ship nothing from M4+ until M0–M3 are green. A flagship cannot be built on a base that lies about what it does or computes the wrong answer for most inputs. Fix the truth and the science first; the moat is already there — make it solid, then make it visible.