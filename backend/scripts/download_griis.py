#!/usr/bin/env python3
"""Download a GRIIS invasive-species checklist and stage it for Relict.

GRIIS (Global Register of Introduced and Invasive Species) publishes per-country
Darwin Core checklists via GBIF. This script:

  1. Finds the country's GRIIS checklist dataset on GBIF.
  2. Downloads its Darwin Core Archive.
  3. Joins taxon.txt (scientificName) with speciesprofile.txt (isInvasive) and
     keeps only species flagged *invasive* (not merely introduced).
  4. Writes ``<references>/invasive/griis-<country>-invasive.tsv`` — a single
     ``scientificName`` column that the conservation stage loads automatically.

Usage:
    python scripts/download_griis.py                 # India (default)
    python scripts/download_griis.py --country "Sri Lanka"
    python scripts/download_griis.py --dataset-key <gbif-dataset-uuid>

The output is intentionally the *invasive* subset. GRIIS lists many introduced
species that are not invasive; flagging those as invasive pressure would
overstate the signal, so they are excluded.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

REFS_DIR = Path(__file__).resolve().parent.parent / "data" / "references"
INVASIVE_DIR = REFS_DIR / "invasive"
GBIF_DATASET_SEARCH = "https://api.gbif.org/v1/dataset/search"
GBIF_DATASET_ENDPOINT = "https://api.gbif.org/v1/dataset/{key}/endpoint"


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Relict/0.1"})  # noqa: S310
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
        return json.load(resp)


def find_dataset_key(country: str) -> str:
    """Return the GBIF dataset key for the country's GRIIS checklist."""
    q = urllib.parse.urlencode({"q": f"GRIIS {country}", "type": "CHECKLIST", "limit": 20})
    results = _get_json(f"{GBIF_DATASET_SEARCH}?{q}").get("results", [])
    wanted = f"invasive species - {country}".lower()
    for r in results:
        if wanted in r.get("title", "").lower():
            return r["key"]
    # fall back to the first GRIIS result that names the country
    for r in results:
        title = r.get("title", "").lower()
        has_griis = "griis" in title or "introduced and invasive" in title
        if has_griis and country.lower() in title:
            return r["key"]
    msg = f"No GRIIS checklist dataset found for country '{country}'."
    raise SystemExit(msg)


def archive_url(dataset_key: str) -> str:
    for e in _get_json(GBIF_DATASET_ENDPOINT.format(key=dataset_key)):
        if e.get("type") == "DWC_ARCHIVE" and e.get("url"):
            return e["url"]
    msg = f"Dataset {dataset_key} has no Darwin Core Archive endpoint."
    raise SystemExit(msg)


def download_archive(url: str) -> zipfile.ZipFile:
    print(f"  Downloading DwC-A: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "Relict/0.1"})  # noqa: S310
    with urllib.request.urlopen(req, timeout=300) as resp:  # noqa: S310
        data = resp.read()
    print(f"  Downloaded {len(data) / 1024:.0f} KB")
    return zipfile.ZipFile(io.BytesIO(data))


def _read_dwc(zf: zipfile.ZipFile, filename: str) -> list[dict[str, str]]:
    with zf.open(filename) as fh:
        text = io.TextIOWrapper(fh, encoding="utf-8", errors="replace")
        return list(csv.DictReader(text, delimiter="\t"))


def extract_invasive(zf: zipfile.ZipFile) -> list[str]:
    """Join taxon + speciesprofile; return sorted invasive scientific names."""
    taxa = _read_dwc(zf, "taxon.txt")
    profiles = _read_dwc(zf, "speciesprofile.txt")

    id_to_name = {t["id"]: (t.get("scientificName") or "").strip() for t in taxa}
    invasive_ids = {
        p["id"] for p in profiles if (p.get("isInvasive") or "").strip().lower() == "invasive"
    }
    names = {id_to_name[i] for i in invasive_ids if id_to_name.get(i)}
    return sorted(names)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download a GRIIS invasive checklist for Relict")
    parser.add_argument("--country", default="India", help="Country name (default: India)")
    parser.add_argument("--dataset-key", help="GBIF dataset UUID (skips the country search)")
    args = parser.parse_args()

    key = args.dataset_key or find_dataset_key(args.country)
    print(f"  GRIIS dataset: {key}")
    names = extract_invasive(download_archive(archive_url(key)))

    if not names:
        print("  WARNING: no invasive-flagged species found in the archive.")
        return 1

    INVASIVE_DIR.mkdir(parents=True, exist_ok=True)
    slug = args.country.lower().replace(" ", "-")
    out = INVASIVE_DIR / f"griis-{slug}-invasive.tsv"
    with open(out, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t")
        writer.writerow(["scientificName"])
        for name in names:
            writer.writerow([name])

    print(f"  [OK] wrote {len(names)} invasive species -> {out}")
    print("  The conservation stage will screen against it on the next run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
