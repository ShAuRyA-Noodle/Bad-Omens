# Ecosystem Integrity Index (EII) — Methodology

> **Version 0.1.** This document is the single, authoritative specification of
> how Relict computes the EII. The exact formula, weights, and data sources
> below are emitted verbatim into every job's Ed25519-signed provenance
> manifest, so any EII shown in the UI can be recomputed and verified from the
> manifest alone.

## What the EII is — and is not

The EII is a **transparent, reproducible composite summary** of one eDNA
sample, expressed as a 0–100 score and an A+…F grade. Its purpose is
**communication and triage**: to give a non-specialist a single, honest,
traceable headline number, and to flag samples that deserve expert attention.

The EII is **not** a peer-reviewed, validated ecological-integrity metric, and
Relict never presents it as one. It is a glass box, not an oracle:

- Every sub-score is computed from a **real signal in this run** — never a
  constant, never a fabricated number.
- The exact transform and weight of every sub-score is published here.
- Sub-scores that **cannot be computed reliably** for a given sample are marked
  *not assessed* and their weight is removed from the denominator, rather than
  being silently defaulted to a flattering value.
- The score carries an explicit **`assessed_weight`** (the fraction of the
  index that had real data) so a partial assessment can never masquerade as a
  complete one.

This honesty is the point. A biodiversity score that hides its assumptions is
exactly the kind of fabricated metric this project exists to refute.

## The formula

```
              Σ_{i ∈ available} wᵢ · sᵢ
EII = 100 × ─────────────────────────────        (0 ≤ EII ≤ 100)
                Σ_{i ∈ available} wᵢ

each sᵢ ∈ [0, 1]   ;   Σ_all wᵢ = 1
assessed_weight = Σ_{i ∈ available} wᵢ
```

If no component is available (e.g. a sample with a single ASV and a fully
degraded conservation lookup), the EII is `null` — Relict shows "not assessable",
never 0.

## The components

| key | name | nominal weight | signal (real input) | available when |
|---|---|---|---|---|
| `evenness` | Community evenness | 0.20 | Pielou's J′ (already computed by scikit-bio) | richness ≥ 2 |
| `conservation_health` | Threat-weighted health | 0.25 | IUCN Red List category per detected species | ≥1 species has an IUCN category **and** the conservation lookup was **not degraded** |
| `distinctness` | Biotic distinctness | 0.20 | GBIF global occurrence count per species | ≥1 species resolved to a GBIF occurrence count |
| `invasive_pressure` | Invasive pressure | 0.15 | mounted GRIIS/GISD invasive checklist | a GRIIS/GISD list is mounted **and** ≥1 species was screened |
| `sampling_adequacy` | Sampling adequacy | 0.20 | Good's coverage `C = 1 − F1/N` on the trimmed reads | read counts available (computed every run) |

### 1. Community evenness — `evenness`

```
s_evenness = J′ = H′ / ln(S)
```

where `H′` is the Shannon index and `S` the observed ASV richness (both already
produced by the diversity stage). `J′ ∈ [0, 1]` by construction; a value near 1
means abundance is spread evenly across taxa (no single dominant organism), a
hallmark of a balanced community. Pielou (1966). *Not available* for `S < 2`
(evenness is undefined for a single taxon).

### 2. Threat-weighted health — `conservation_health`

```
s_health = 1 − ( Σ_species threat_weight(category) ) / N_assessed

threat_weight:  CR=1.0  EN=0.8  VU=0.6  NT=0.3  LC=0.0  (DD/NE excluded)
N_assessed = number of detected species with an IUCN category in the set above
```

A community composed of Least-Concern taxa scores 1.0; a community dominated by
Critically-Endangered / Endangered taxa scores lower, flagging a sample whose
constituent species are themselves at risk. This is a *conservation-concern*
reading: the presence of many threatened taxa lowers the headline so the sample
surfaces for review.

**Integrity-critical guard:** if the conservation stage reported
`api_degraded` (any GBIF/IUCN lookup failed, see the conservation fail-loud
behaviour), this component is marked **not assessed** — a degraded lookup must
never produce a confident "healthy" score. This sub-score also inherits the
reliability of the taxonomy: per-rank identity gating + LCA (Phase B) tightens
the species calls it depends on.

### 3. Biotic distinctness — `distinctness`

```
s_distinctness = mean_species rarity(occ)
rarity(occ) = 1 − min(1, log10(1 + occ) / log10(1 + OCC_COMMON))
OCC_COMMON = 1_000_000   (documented "common everywhere" reference)
```

Globally rare taxa (low GBIF occurrence) raise the score; cosmopolitan taxa
(occurrence approaching `OCC_COMMON`) contribute ~0. This rewards samples that
detect biotically distinct / under-documented organisms. The reference
`OCC_COMMON` is an explicit, tunable constant, not a hidden magic number.

### 4. Invasive pressure — `invasive_pressure`

```
s_invasive = 1 − (invasive_detections / N_species_screened)
```

Screened against a mounted GRIIS/GISD checklist (Darwin Core CSV or a plain
species list under `<REFERENCES_ROOT>/invasive/`; provision with
`make download-invasive`). When no list is mounted the component is *not
assessed* (weight removed from the denominator) — Relict will not pretend
"0 invasives" when it has not actually checked. When a list is mounted, each
detected species is matched by canonical binomial (also against its GBIF
canonical name) and the fraction flagged invasive drives the sub-score.

### 5. Sampling adequacy — `sampling_adequacy`

```
C = 1 − F1 / N     (Good's coverage)
```

`F1` = reads observed exactly once (singletons), `N` = total reads. Computed
every run by a **separate, singleton-preserving dereplication** of the QC +
primer-trimmed reads (`coverage.py`) — the ASV-inference dereplication drops
singletons (`--minuniquesize 2`), which would make any coverage estimator on
the ASV table degenerate, so this runs as its own pass and never perturbs ASV
calling. High `C` means the sample was sequenced deeply enough that few taxa
were seen only once.

## Score → grade

A standard academic scale, published so the cut-points are not a black box:

| grade | EII | grade | EII |
|---|---|---|---|
| A+ | ≥ 97 | C+ | ≥ 77 |
| A  | ≥ 93 | C  | ≥ 73 |
| A− | ≥ 90 | C− | ≥ 70 |
| B+ | ≥ 87 | D+ | ≥ 67 |
| B  | ≥ 83 | D  | ≥ 63 |
| B− | ≥ 80 | D− | ≥ 60 |
|    |      | F  | < 60 |

## Determinism & provenance

The EII is a pure function of values already in the signed manifest (diversity
metrics + conservation records). Identical inputs → identical EII. The full
component breakdown (each sub-score, its weight, its `available` flag, and the
`assessed_weight`) is written into the manifest, so every cell of the grade
matrix in the UI links back to the exact manifest line that produced it.

## Limitations (stated up front)

- `conservation_health` is only as good as the taxonomy feeding it (LCA
  gating) and the IUCN coverage of the detected taxa. It needs
  `IUCN_REDLIST_TOKEN` set; otherwise it is *not assessed*.
- `invasive_pressure` needs a mounted GRIIS/GISD checklist; otherwise *not
  assessed* (never a false "0 invasives").
- `sampling_adequacy` uses Good's coverage on the trimmed reads — a
  single-sample depth-completeness estimate, not a multi-sample rarefaction
  extrapolation.
- The weights are a defensible **default**, not an empirically optimised set;
  they are exposed precisely so they can be scrutinised and tuned.

## References

- Pielou, E.C. (1966). The measurement of diversity in different types of
  biological collections. *Journal of Theoretical Biology* 13: 131–144.
- IUCN (2024). The IUCN Red List of Threatened Species, categories & criteria.
- GBIF.org occurrence counts (global), via the GBIF Occurrence API.
