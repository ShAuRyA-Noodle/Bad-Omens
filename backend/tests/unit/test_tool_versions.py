"""Unit tests for runtime tool-version detection.

The contract: detection must record a value for every tool and must never
raise, even when a binary or package is missing (it returns a clear sentinel
like ``unavailable``/``unknown`` instead). This keeps provenance honest — the
manifest reports what was actually found, not a hardcoded constant.
"""

from __future__ import annotations

from worker.tool_versions import detect_tool_versions

_EXPECTED_TOOLS = (
    "fastp",
    "vsearch",
    "cutadapt",
    "biopython",
    "scikit-bio",
    "umap-learn",
    "hdbscan",
    "biom-format",
)


def test_detect_returns_a_value_for_every_tool_without_raising() -> None:
    versions = detect_tool_versions()
    for tool in _EXPECTED_TOOLS:
        assert tool in versions, f"missing tool in detected versions: {tool}"
        assert isinstance(versions[tool], str)
        assert versions[tool], f"empty version string for {tool}"


def test_detect_is_cached() -> None:
    # lru_cache means the same object is returned — cheap and stable per run.
    assert detect_tool_versions() is detect_tool_versions()
