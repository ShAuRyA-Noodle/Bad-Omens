# Relict: A reproducible, open-source platform unifying environmental DNA analysis, conservation cross-referencing, and citizen-science data submission

**Shaurya Punj**

Thapar Institute of Engineering and Technology, Patiala, India

ORCID: 0009-0000-7351-0237

**Correspondence:** Shaurya Punj, workwithshaurya10@gmail.com

---

## Abstract

1. Environmental DNA (eDNA) metabarcoding has become a standard tool for non-invasive biodiversity monitoring, yet the analytical workflow between raw sequencing reads and actionable ecological insight remains fragmented. Existing bioinformatics pipelines (QIIME2, DADA2, mothur) are powerful but CLI-only, opaque to non-specialists, and leave conservation interpretation, reproducibility documentation, and data submission to the user. No existing open tool automates the cross-referencing of eDNA detections against global conservation databases or produces signed provenance manifests suitable for supplementary material.

2. Here, we present Relict, an open-source, full-stack web platform that integrates a complete amplicon bioinformatics pipeline (fastp quality control, vsearch UNOISE3 ASV inference, taxonomy assignment against SILVA 138.1 / MIDORI2 GenBank 269) with three novel layers: (a) automated conservation cross-referencing against the Global Biodiversity Information Facility (GBIF) and the IUCN Red List, (b) one-click generation of GBIF-compatible Darwin Core Archives for citizen-science data submission, and (c) signed provenance manifests recording every input hash, tool version, and parameter for reproducible research. The platform supports six amplicon markers (16S V4, 12S MiFish, COI Leray, 18S V9, rbcL, ITS2) with version-pinned reference databases.

3. We validated Relict against a synthetic known-composition dataset (5 bacterial species at equal abundance) and a real published SRA dataset (ERR2283086, 45,204 Illumina MiSeq reads). On the synthetic dataset, all 10 benchmark checks passed with mathematically exact results (Shannon = ln(5) = 1.6094, Simpson = 0.8, evenness = 1.0). On the SRA dataset, Relict detected 51 ASVs across three phyla (Proteobacteria, Firmicutes, Actinobacteriota), assigned taxonomy to 100% of ASVs at 100% SILVA identity, and cross-referenced all detected taxa against GBIF in a total pipeline runtime of 3.6 minutes.

4. Relict addresses three gaps in the current eDNA tooling landscape that no single existing platform covers simultaneously: conservation-status integration, reproducibility guarantees, and citizen-science data publication. The platform is freely available under the MIT licence at https://github.com/ShAuRyA-Noodle/Bad-Omens.

**KEYWORDS:** environmental DNA, eDNA, metabarcoding, bioinformatics pipeline, conservation, reproducible research, GBIF, IUCN Red List, citizen science, amplicon sequence variants

---

## 1. INTRODUCTION

The availability of environmental DNA (eDNA) data has grown rapidly since the technique's first applications in vertebrate monitoring nearly two decades ago (Ficetola et al., 2008). By sequencing genetic material shed by organisms into their environment — water, soil, sediment, or air — researchers can detect species presence without physically capturing or even observing the organisms (Taberlet et al., 2012; Deiner et al., 2017). eDNA metabarcoding has proven effective for monitoring common, endangered, rare, and invasive species across marine, freshwater, and terrestrial ecosystems (Bonfil et al., 2021; Larson et al., 2020; Pfleger et al., 2016).

Software tools for processing eDNA amplicon data have matured considerably. QIIME 2 (Bolyen et al., 2019), DADA2 (Callahan et al., 2016), mothur (Schloss & Westcott, 2011), vsearch (Rognes et al., 2016), OBITools (Boyer et al., 2016), and more recently SimpleMetaPipeline (Williams et al., 2024) provide robust denoising, clustering, and taxonomic assignment capabilities. However, three gaps persist in the current landscape:

**Conservation interpretation.** After obtaining a list of detected taxa, researchers must manually look up each species in the IUCN Red List, GBIF, or national protection schedules to assess conservation significance. No existing open eDNA pipeline automates this cross-referencing step, meaning conservation-relevant findings may be delayed or overlooked entirely (Lee et al., 2024).

**Reproducibility documentation.** While workflow managers like Snakemake and Nextflow can record pipeline parameters, no eDNA-specific tool produces a self-contained, signed provenance manifest that records every input file hash, exact tool version, reference database version, and output hash in a format suitable for direct inclusion as supplementary material. The lack of such documentation has been identified as a barrier to reproducibility in metabarcoding studies (Powers & Hampton, 2019; Sandve et al., 2013).

**Citizen-science data submission.** eDNA monitoring is increasingly adopted by non-specialist organisations — schools, NGOs, dive clubs, and environmental agencies (Larson et al., 2020). These users need a guided workflow from sample upload to GBIF-ready Darwin Core Archive, without requiring bioinformatics expertise. Existing tools either require command-line proficiency or do not generate GBIF-compatible outputs directly.

Here, we present Relict, an open-source platform that addresses all three gaps within a single integrated system. Relict wraps established, peer-reviewed bioinformatics tools (fastp, vsearch, scikit-bio) in a full-stack web application with a modern React frontend, a FastAPI backend, and a containerised worker architecture, adding conservation cross-referencing, provenance manifests, and Darwin Core Archive generation as first-class features.

---

## 2. DESIGN PRINCIPLES

Relict is built around eight principles that distinguish it from existing pipelines:

1. **No mock data, ever.** Every number displayed to the user is computed from real input by real tools. The platform contains zero hardcoded placeholder values, fabricated accuracy metrics, or synthetic demonstration data.

2. **Version-pin everything.** Every external tool (fastp 0.24.0, vsearch 2.28.1), Python package (scikit-bio 0.6.2, umap-learn 0.5.7), and reference database (SILVA 138.1, MIDORI2 GenBank 269) is pinned to an exact version recorded in the provenance manifest.

3. **Fail loudly.** When a pipeline stage encounters an error — a missing reference database, a tool crash, an empty input — the system reports the real error message to the user. It never substitutes a placeholder result or silently skips a stage.

4. **Separate concerns.** The web server handles HTTP requests only. All bioinformatics computation runs in a dedicated worker container via a Redis-backed job queue (RQ), ensuring long-running analyses never block the API.

5. **Deterministic stages.** Each pipeline stage is a pure function over its inputs and parameters. Two runs with identical inputs and parameters produce identical outputs and identical provenance hashes.

6. **Conservation as a first-class output.** Every detected taxon is automatically cross-referenced against GBIF and the IUCN Red List during the pipeline run, not as an afterthought.

7. **Reproducibility as a deliverable.** Every run produces a signed JSON manifest that can be attached to a paper as supplementary material and used to independently verify the result.

8. **Citizen-science ready.** Results can be exported as a GBIF-compatible Darwin Core Archive with a single click.

---

## 3. SYSTEM ARCHITECTURE

### 3.1 Overview

Relict is a full-stack web application composed of six services orchestrated via Docker Compose (Figure 1):

- **Frontend:** React 18.3 with TypeScript, Tailwind CSS, shadcn/ui components, React Query for data fetching, and React Router for navigation.
- **API server:** FastAPI (Python 3.11) with Pydantic v2 validation, JWT authentication (argon2id password hashing), and structured JSON logging via structlog.
- **Worker:** A dedicated container with all bioinformatics tools pre-installed (fastp, vsearch, cutadapt, scikit-bio, umap-learn, hdbscan, biopython). Jobs are dispatched via Redis Queue (RQ).
- **Database:** PostgreSQL 16 with 9 tables (users, jobs, samples, ASVs, taxa, diversity_metrics, conservation_cache, provenance, refresh_sessions) managed by Alembic migrations.
- **Object storage:** MinIO (S3-compatible) for raw FASTQ files and pipeline outputs.
- **Cache/queue:** Redis 7 for job queuing and per-job WebSocket event channels.

The entire stack is brought up with a single `docker compose up --build` command.

### 3.2 The bioinformatics pipeline

The pipeline processes each uploaded FASTQ through seven stages (Figure 2):

1. **Quality control** (fastp 0.24.0): Adapter trimming, quality filtering (Q≥20), length filtering (≥50 bp), with a machine-readable JSON report.

2. **Dereplication** (vsearch 2.28.1 `--fastx_uniques`): Collapse identical sequences, recording abundance in FASTA headers (`size=N`). Singletons (size < 2) are discarded.

3. **ASV inference** (vsearch 2.28.1 `--cluster_unoise`, UNOISE3 algorithm; Edgar, 2016): Denoise the dereplicated sequences to produce amplicon sequence variants — biologically real sequences cleaned of PCR and sequencing errors.

4. **Taxonomy assignment** (vsearch 2.28.1 `--usearch_global`): Align each ASV centroid against a version-pinned reference database. Supported databases: SILVA 138.1 SSU NR99 (Quast et al., 2013) for 16S/18S, MIDORI2 GenBank 269 (Leray et al., 2022) for COI and 12S. Taxonomy is extracted from reference FASTA headers at seven standard ranks (kingdom through species).

5. **Conservation cross-referencing** (GBIF API v1 + IUCN via GBIF): For each species-level assignment, resolve the name against the GBIF backbone taxonomy, query global occurrence counts, and fetch the IUCN Red List conservation category (LC/NT/VU/EN/CR/EW/EX). Results are cached in PostgreSQL with a 30-day TTL.

6. **Diversity metrics** (scikit-bio 0.6.2): Compute Shannon entropy (H'), Simpson index (1-D), Chao1 estimated richness, observed richness, and Pielou's evenness from the ASV abundance vector.

7. **Provenance manifest:** Generate a signed JSON manifest recording every input file SHA256, tool version, reference database identity, pipeline parameters, stage runtimes, and a SHA256 signature over the canonical manifest JSON.

### 3.3 Amplicon marker support

Relict ships with YAML preset configurations for six common amplicon markers (Table 1), each defining primer sequences, expected amplicon length ranges, QC parameters, and the recommended reference database.

**Table 1.** Supported amplicon markers and their configurations.

| Marker | Primers | Amplicon (bp) | Reference DB | Target |
|---|---|---|---|---|
| 16S V4 | 515F / 806R | 200–350 | SILVA 138.1 | Bacteria, Archaea |
| 12S MiFish | MiFish-U-F / MiFish-U-R | 163–185 | MIDORI2 srRNA GB269 | Fish, vertebrates |
| COI Leray | mlCOIintF / jgHCO2198 | 280–340 | MIDORI2 CO1 GB269 | Invertebrates |
| 18S V9 | 1391F / EukBr | 100–200 | SILVA 138.1 | Eukaryotes |
| rbcL | rbcLa-F / rbcLa-R | 500–600 | SILVA 138.1 | Plants |
| ITS2 | fITS7 / ITS4 | 200–450 | SILVA 138.1 | Fungi |

### 3.4 Outputs and exports

For each completed analysis, Relict provides:

- **Interactive web dashboard** with five tabs: overview metrics, ASV table with taxonomy, conservation status with IUCN badges, provenance manifest viewer, and export downloads.
- **Darwin Core Archive (DwC-A):** A ZIP file conforming to the GBIF DNA-derived data standard (GBIF Secretariat, 2023), containing `occurrence.txt`, `dna-derived-data.txt`, `eml.xml`, and `meta.xml`.
- **CSV export:** Flat table with ASV sequences, abundances, taxonomy, and confidence.
- **BIOM 2.1.0 JSON:** Compatible with QIIME 2 and phyloseq (McMurdie & Holmes, 2013).
- **Signed provenance manifest:** JSON with input hashes, tool versions, stage timings, and SHA256 signature.

---

## 4. BENCHMARKING

### 4.1 Synthetic known-composition benchmark

We validated Relict using a synthetic dataset of 100 reads from five known bacterial species (*Escherichia coli*, *Bacillus subtilis*, *Staphylococcus aureus*, *Pseudomonas aeruginosa*, *Lactobacillus rhamnosus*) at equal abundance (20 reads each). Sequences were real 16S V4 amplicon regions from GenBank accessions.

All 10 benchmark checks passed with mathematically exact results (Table 2).

**Table 2.** Synthetic benchmark results (10/10 passed).

| Check | Expected | Actual | Status |
|---|---|---|---|
| ASV count | 5 | 5 | Pass |
| Taxonomy assignment | 5/5 (100%) | 5/5 | Pass |
| Known genera detected | ≥3 of 4 | 4/4 | Pass |
| Shannon index | 1.609438 (ln 5) | 1.609438 | Pass |
| Simpson index | 0.800000 | 0.800000 | Pass |
| Pielou's evenness | 1.000000 | 1.000000 | Pass |
| Species richness | 5 | 5 | Pass |
| Chao1 | 5.0000 | 5.0000 | Pass |
| GBIF resolution | ≥3/5 | 5/5 | Pass |
| Provenance manifest | Valid SHA256 | Valid | Pass |

### 4.2 Real SRA dataset benchmark

We further validated the pipeline on ERR2283086, a published mock community dataset from the European Nucleotide Archive (45,204 Illumina MiSeq reads, 151 bp). The pipeline completed in 215 seconds (3.6 minutes), detecting 51 ASVs with 100% taxonomy assignment against SILVA 138.1 (Table 3).

**Table 3.** SRA benchmark results (ERR2283086).

| Metric | Value |
|---|---|
| Input reads | 45,204 |
| ASVs detected | 51 |
| Taxonomy assigned | 51/51 (100%) |
| Shannon (H') | 2.585 |
| Simpson (1-D) | 0.888 |
| Chao1 | 51.0 |
| Evenness (J') | 0.657 |
| Pipeline runtime | 215 s |
| Phyla detected | 3 (Proteobacteria, Firmicutes, Actinobacteriota) |
| Top genus | *Acinetobacter* (7,266 reads) |

The recovered community included genera from three phyla with ecologically plausible abundance distributions. All taxonomy assignments achieved 100% identity against SILVA 138.1 reference sequences, and all detected species were successfully resolved against GBIF.

---

## 5. ASSUMPTIONS AND LIMITATIONS

Relict inherits the well-documented limitations of eDNA metabarcoding itself: primer bias, PCR amplification artefacts, reference database incompleteness, and the inability to distinguish live from dead organisms (Taberlet et al., 2012). The platform does not address these biological limitations; it aims to make them more transparent through provenance documentation.

The conservation cross-referencing layer depends on GBIF and IUCN API availability and data currency. External API responses are cached with a 30-day TTL, and the provenance manifest records the `fetched_at` timestamp for every conservation record so users can assess data staleness.

The current implementation uses vsearch for ASV inference (UNOISE3 algorithm). While DADA2 is considered the gold standard for Illumina error correction (Callahan et al., 2016), vsearch provides comparable accuracy at significantly higher speed and with simpler deployment requirements. DADA2 integration is planned for a future release.

Taxonomy assignment quality depends on the completeness and accuracy of the reference database. Species-level assignments for underrepresented taxa should be interpreted with appropriate caution, particularly for markers with lower taxonomic resolution (e.g., 16S V4 for closely related species).

---

## 6. SOFTWARE AVAILABILITY

Relict is freely available under the MIT licence. The source code, documentation, benchmark scripts, and amplicon preset configurations are available at https://github.com/ShAuRyA-Noodle/Bad-Omens. The platform requires Docker and Docker Compose for deployment. Reference databases (SILVA 138.1, MIDORI2 GenBank 269) are downloaded via a version-pinned script with SHA256 verification. A `CITATION.cff` file is provided for software citation.

---

## AUTHOR CONTRIBUTIONS

Shaurya Punj conceived the project, designed and implemented the platform, conducted the benchmarking, and wrote the manuscript.

---

## DATA AVAILABILITY STATEMENT

The synthetic benchmark dataset is included in the repository. The SRA benchmark dataset (ERR2283086) is publicly available from the European Nucleotide Archive at https://www.ebi.ac.uk/ena/browser/view/ERR2283086. All benchmark results, including provenance manifests, are available in the `docs/benchmarks/` directory of the repository.

---

## ORCID

Shaurya Punj https://orcid.org/0009-0000-7351-0237

---

## REFERENCES

Bolyen, E., Rideout, J. R., Dillon, M. R., Bokulich, N. A., Abnet, C. C., et al. (2019). Reproducible, interactive, scalable and extensible microbiome data science using QIIME 2. *Nature Biotechnology*, 37, 852–857.

Bonfil, R., Palacios-Barreto, P., Vargas, O. U. M., Ricaño-Soriano, M., & Díaz-Jaimes, P. (2021). Detection of critically endangered marine species with dwindling populations using eDNA. *Marine Biology*, 168(5), 1–12.

Boyer, F., Mercier, C., Bonin, A., Le Bras, Y., Taberlet, P., & Coissac, E. (2016). obitools: a unix-inspired software package for DNA metabarcoding. *Molecular Ecology Resources*, 16(1), 176–182.

Callahan, B. J., McMurdie, P. J., Rosen, M. J., Han, A. W., Johnson, A. J. A., & Holmes, S. P. (2016). DADA2: High-resolution sample inference from Illumina amplicon data. *Nature Methods*, 13(7), 581–583.

Deiner, K., Bik, H. M., Mächler, E., Seymour, M., Lacoursière-Roussel, A., et al. (2017). Environmental DNA metabarcoding: Transforming how we survey animal and plant communities. *Molecular Ecology*, 26(21), 5872–5895.

Edgar, R. C. (2016). UNOISE2: improved error-correction for Illumina 16S and ITS amplicon sequencing. *bioRxiv*, 081257.

Ficetola, G. F., Miaud, C., Pompanon, F., & Taberlet, P. (2008). Species detection using environmental DNA from water samples. *Biology Letters*, 4(4), 423–425.

GBIF Secretariat. (2023). Publishing DNA-derived data through biodiversity data platforms. https://docs.gbif.org/publishing-dna-derived-data/en/

Larson, E. R., Graham, B. M., Achury, R., Coon, J. J., Daniels, M. K., et al. (2020). From eDNA to citizen science: Emerging tools for the early detection of invasive species. *Frontiers in Ecology and the Environment*, 18(4), 194–202.

Lee, K. N., Kelly, R. P., Demir-Hilton, E., Laschever, E., & Allan, E. A. (2024). Adoption of environmental DNA in public agency practice. *Environmental DNA*, 6(1), 1–14.

Leray, M., Knowlton, N., & Machida, R. J. (2022). MIDORI2: A collection of quality-controlled, preformatted, and regularly updated reference databases for taxonomic assignment of eukaryotic mitochondrial sequences. *Environmental DNA*, 4(4), 894–907.

McMurdie, P. J., & Holmes, S. (2013). phyloseq: An R package for reproducible interactive analysis and graphics of microbiome census data. *PLoS ONE*, 8(4), e61217.

Pfleger, M. O., Rider, S. J., Johnston, C. E., & Janosik, A. M. (2016). Saving the doomed: Using eDNA to aid in detection of rare sturgeon for conservation. *Global Ecology and Conservation*, 8, 99–107.

Powers, S. M., & Hampton, S. E. (2019). Open science, reproducibility, and transparency in ecology. *Ecological Applications*, 29(1), e01822.

Quast, C., Pruesse, E., Yilmaz, P., Gerken, J., Schweer, T., Yarza, P., Peplies, J., & Glöckner, F. O. (2013). The SILVA ribosomal RNA gene database project: Improved data processing and web-based tools. *Nucleic Acids Research*, 41(D1), D590–D596.

Rognes, T., Flouri, T., Nichols, B., Quince, C., & Mahé, F. (2016). VSEARCH: A versatile open source tool for metagenomics. *PeerJ*, 4, e2584.

Sandve, G. K., Nekrutenko, A., Taylor, J., & Hovig, E. (2013). Ten simple rules for reproducible computational research. *PLoS Computational Biology*, 9(10), e1003285.

Schloss, P. D., & Westcott, S. L. (2011). Assessing and improving methods used in operational taxonomic unit-based approaches for 16S rRNA gene sequence analysis. *Applied and Environmental Microbiology*, 77, 3219–3226.

Taberlet, P., Coissac, E., Hajibabaei, M., & Rieseberg, L. H. (2012). Environmental DNA. *Molecular Ecology*, 21(8), 1789–1793.

Williams, J., Pettorelli, N., Dowell, R., Macdonald, K., Meyer, C., Steyaert, M., Tweedt, S., & Ransome, E. (2024). SimpleMetaPipeline: Breaking the bioinformatics bottleneck in metabarcoding. *Methods in Ecology and Evolution*, 15, 1949–1957.
