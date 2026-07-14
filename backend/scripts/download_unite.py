#!/usr/bin/env python3
"""Download the UNITE fungal ITS reference database for Relict.

UNITE publishes its "general FASTA release" via a stable DOI on PlutoF. This
script resolves the DOI to the current S3 archive, downloads it, extracts the
main dynamic-clustering FASTA (not the *_dev.fasta developer file), and places
it at ``<references>/unite/`` where the taxonomy stage finds it for ITS2.

Default DOI: 10.15156/BIO/2959332 — "UNITE general FASTA release for Fungi".

Usage:
    python scripts/download_unite.py
    python scripts/download_unite.py --doi 10.15156/BIO/2959330   # all eukaryotes

The raw FASTA is used directly (no vsearch UDB): the taxonomy stage indexes
reference headers by reading the FASTA as text, and UNITE's lineage lives in
those headers — a binary UDB would hide them.
"""
from __future__ import annotations

import argparse
import io
import re
import sys
import tarfile
import urllib.request
from pathlib import Path

REFS_DIR = Path(__file__).resolve().parent.parent / "data" / "references"
UNITE_DIR = REFS_DIR / "unite"
PLUTOF_DOI_API = "https://api.plutof.ut.ee/v1/public/dois/?identifier={doi}"
DEFAULT_DOI = "10.15156/BIO/2959332"


def _get(url: str, *, binary: bool = False) -> bytes | str:
    req = urllib.request.Request(url, headers={"User-Agent": "Relict/0.1"})  # noqa: S310
    with urllib.request.urlopen(req, timeout=300) as resp:  # noqa: S310
        data = resp.read()
    return data if binary else data.decode("utf-8", "replace")


def resolve_archive_url(doi: str) -> str:
    """Read the PlutoF DOI record and return the .tgz S3 URL."""
    body = _get(PLUTOF_DOI_API.format(doi=doi))
    urls = re.findall(r"https?://[^\"\s]+\.tgz", body)
    if not urls:
        msg = f"No .tgz archive URL found for DOI {doi}."
        raise SystemExit(msg)
    return urls[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Download the UNITE ITS reference DB")
    parser.add_argument("--doi", default=DEFAULT_DOI, help=f"UNITE PlutoF DOI (default: {DEFAULT_DOI})")
    args = parser.parse_args()

    url = resolve_archive_url(args.doi)
    print(f"  UNITE archive: {url}")
    print("  Downloading (~25 MB)…")
    archive = _get(url, binary=True)
    assert isinstance(archive, bytes)

    UNITE_DIR.mkdir(parents=True, exist_ok=True)
    main_fasta: Path | None = None
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tf:
        for member in tf.getmembers():
            name = Path(member.name).name
            # keep the main dynamic FASTA only (skip the *_dev.fasta developer file)
            if name.endswith(".fasta") and "_dev" not in name:
                extracted = tf.extractfile(member)
                if extracted is None:
                    continue
                dest = UNITE_DIR / name
                dest.write_bytes(extracted.read())
                main_fasta = dest
                print(f"  Extracted {name} ({dest.stat().st_size / 1024 / 1024:.0f} MB)")

    if main_fasta is None:
        print("  ERROR: no dynamic FASTA found in the UNITE archive.")
        return 1

    print(f"  [OK] UNITE ready at {main_fasta}")
    print("  ITS2 taxonomy will use it on the next run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
