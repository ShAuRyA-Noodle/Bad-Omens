"""Relict worker package — bioinformatics pipeline stages + RQ entrypoint.

TOOL_VERSIONS is the canonical record of every external binary and
Python package that the pipeline calls. Every pipeline run records
these versions in the provenance manifest (Phase 5) and in the
``jobs.pipeline_version`` DB field (Phase 1+).

Changing any version here **requires** a corresponding change in
``Dockerfile.worker`` and a re-build of the worker image.
"""
from __future__ import annotations

PIPELINE_VERSION = "0.2.0"

TOOL_VERSIONS: dict[str, str] = {
    "fastp": "0.24.0",
    "vsearch": "2.28.1",
    "cutadapt": "4.9",
    "biopython": "1.84",
    "scikit-bio": "0.6.2",
    "umap-learn": "0.5.7",
    "hdbscan": "0.8.40",
    "biom-format": "2.1.16",
    "mafft": "7.505",
    "fasttree": "2.1.11",
}

__all__ = ["PIPELINE_VERSION", "TOOL_VERSIONS"]
