"""Detect the *actual* installed versions of every pipeline tool at runtime.

The provenance manifest must record what really ran, not a hardcoded constant
that can silently drift from the installed binary. Python package versions are
read from ``importlib.metadata``; CLI tool versions are parsed from each
binary's ``--version`` output. Results are cached for the life of the process
(versions don't change mid-run).

The hardcoded :data:`worker.TOOL_VERSIONS` remains the *expected* pin (and is
recorded alongside as ``tool_versions_expected``) so the manifest can surface
any drift between the pinned and the installed version.
"""

from __future__ import annotations

import re
import subprocess
from functools import lru_cache
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

# CLI binaries: name -> (argv, regex capturing the version substring).
_CLI_TOOLS: dict[str, tuple[list[str], str]] = {
    "fastp": (["fastp", "--version"], r"fastp\s+v?([0-9][0-9A-Za-z.\-_]*)"),
    "vsearch": (["vsearch", "--version"], r"vsearch\s+v?([0-9][0-9A-Za-z.\-_]*)"),
    "cutadapt": (["cutadapt", "--version"], r"([0-9][0-9A-Za-z.\-_]*)"),
    # MAFFT prints "v7.505 (…)" to stderr; --version exits cleanly.
    "mafft": (["mafft", "--version"], r"v?([0-9][0-9A-Za-z.\-_]*)"),
    # FastTree has no --version; -expert prints "…FastTree 2.1.11…" and exits
    # (running it bare would block on stdin, so never do that).
    "fasttree": (["fasttree", "-expert"], r"FastTree\s+v?(?:ersion\s+)?([0-9][0-9A-Za-z.\-_]*)"),
}

# Python distributions: tool name -> distribution name on PyPI.
_PY_PACKAGES: dict[str, str] = {
    "biopython": "biopython",
    "scikit-bio": "scikit-bio",
    "umap-learn": "umap-learn",
    "hdbscan": "hdbscan",
    "biom-format": "biom-format",
}


def _detect_cli(argv: list[str], pattern: str) -> str:
    """Run ``argv`` and extract the version, or a clear sentinel on failure."""
    try:
        proc = subprocess.run(  # noqa: S603 — trusted, hardcoded argv, no shell, no user input
            argv, capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return "unavailable"
    combined = f"{proc.stdout or ''}\n{proc.stderr or ''}"
    match = re.search(pattern, combined)
    return match.group(1) if match else "unknown"


def _detect_py(distribution: str) -> str:
    try:
        return _pkg_version(distribution)
    except PackageNotFoundError:
        return "unavailable"


@lru_cache(maxsize=1)
def detect_tool_versions() -> dict[str, str]:
    """Return the real installed version of every pipeline tool (cached)."""
    versions: dict[str, str] = {}
    for name, (argv, pattern) in _CLI_TOOLS.items():
        versions[name] = _detect_cli(argv, pattern)
    for name, distribution in _PY_PACKAGES.items():
        versions[name] = _detect_py(distribution)
    return dict(sorted(versions.items()))


__all__ = ["detect_tool_versions"]
