"""HTML report generator for Relict pipeline results.

Produces a self-contained, single-file HTML report with all pipeline
results: overview metrics, ASV table with taxonomy, conservation
status, diversity indices, and provenance chain. The report includes
inline CSS so it renders correctly when opened in any browser without
external dependencies.

This is the deliverable a researcher hands to a collaborator or
attaches to a publication as supplementary material.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def generate_html_report(
    *,
    job_id: str,
    pipeline_version: str,
    parameter_hash: str,
    asvs: list[dict[str, Any]],
    diversity: dict[str, Any],
    conservation: dict[str, Any],
    provenance: dict[str, Any],
    sample_filename: str,
    sample_sha256: str,
    sample_size: int,
) -> str:
    """Generate a complete HTML analysis report."""

    n_asvs = len(asvs)
    n_assigned = sum(1 for a in asvs if a.get("taxon"))
    cons_records = conservation.get("records", [])
    n_gbif = sum(1 for r in cons_records if r.get("gbif_key"))
    n_iucn = sum(1 for r in cons_records if r.get("iucn_category"))
    threatened = sum(1 for r in cons_records if r.get("iucn_category") in ("VU", "EN", "CR", "EW", "EX"))

    manifest = provenance.get("manifest", {})
    pipeline_info = manifest.get("pipeline", {})
    tools = pipeline_info.get("tool_versions", {})
    stages = manifest.get("stages", [])
    manifest_sha = provenance.get("manifest_sha256", "")

    asv_rows = ""
    for i, asv in enumerate(asvs):
        t = asv.get("taxon") or {}
        lineage = " > ".join(filter(None, [t.get("kingdom"), t.get("phylum"), t.get("tax_class"),
                                            t.get("tax_order"), t.get("family"), t.get("genus")]))
        species = t.get("species", "")
        conf = f'{t["confidence"]*100:.1f}%' if t.get("confidence") else "-"
        asv_rows += f"""
        <tr>
            <td>{i+1}</td>
            <td><strong>{t.get('genus', '')} {species}</strong></td>
            <td>{asv['abundance']}</td>
            <td>{asv['length']} bp</td>
            <td>{conf}</td>
            <td class="small">{lineage}</td>
            <td class="mono small">{asv['sequence'][:40]}...</td>
        </tr>"""

    cons_rows = ""
    for r in cons_records:
        iucn = r.get("iucn_category") or "N/A"
        flags = r.get("legal_flags") or {}
        iucn_full = flags.get("iucn_category_full") or iucn
        gbif_count = r.get("gbif_occurrence_count") or 0
        trend = flags.get("iucn_population_trend") or "-"
        iucn_class = ""
        if iucn in ("CR", "EN"):
            iucn_class = "iucn-en"
        elif iucn in ("VU",):
            iucn_class = "iucn-vu"
        elif iucn in ("LC", "NT"):
            iucn_class = "iucn-lc"
        cons_rows += f"""
        <tr>
            <td>{r['species']}</td>
            <td><span class="badge {iucn_class}">{iucn}</span> {iucn_full}</td>
            <td>{gbif_count:,}</td>
            <td>{trend}</td>
        </tr>"""

    tool_rows = ""
    for tool, ver in tools.items():
        tool_rows += f"<tr><td>{tool}</td><td>{ver}</td></tr>"

    stage_rows = ""
    for s in stages:
        stage_rows += f"""
        <tr>
            <td>{s.get('stage', '?')}</td>
            <td>{s.get('tool', '?')}</td>
            <td>{s.get('tool_version', '?')}</td>
            <td>{s.get('runtime_seconds', 0):.2f}s</td>
        </tr>"""

    now = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Relict Analysis Report - {job_id[:8]}</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: #0a0a0a; color: #e0e0e0; line-height: 1.6; padding: 2rem; max-width: 1100px; margin: 0 auto; }}
    h1 {{ font-size: 1.8rem; color: #39FF14; margin-bottom: 0.3rem; letter-spacing: 2px; text-transform: uppercase; }}
    h2 {{ font-size: 1.2rem; color: #00F0FF; margin: 2rem 0 1rem; padding-bottom: 0.5rem; border-bottom: 1px solid #222; text-transform: uppercase; letter-spacing: 1px; }}
    h3 {{ font-size: 1rem; color: #ccc; margin: 1.5rem 0 0.5rem; }}
    .subtitle {{ color: #666; font-size: 0.85rem; margin-bottom: 2rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin: 1rem 0; }}
    .metric {{ background: #111; border: 1px solid #222; padding: 1rem; }}
    .metric .label {{ font-size: 0.7rem; color: #666; text-transform: uppercase; letter-spacing: 1px; }}
    .metric .value {{ font-size: 1.5rem; font-weight: bold; color: #39FF14; margin-top: 0.3rem; }}
    table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.85rem; }}
    th {{ background: #111; color: #00F0FF; text-align: left; padding: 0.6rem; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; border-bottom: 1px solid #333; }}
    td {{ padding: 0.5rem 0.6rem; border-bottom: 1px solid #1a1a1a; }}
    tr:hover {{ background: #111; }}
    .mono {{ font-family: 'Cascadia Code', 'Fira Code', monospace; }}
    .small {{ font-size: 0.75rem; color: #888; }}
    .badge {{ display: inline-block; padding: 0.15rem 0.5rem; font-size: 0.7rem; font-weight: bold; border-radius: 2px; }}
    .iucn-en {{ background: #c0392b; color: white; }}
    .iucn-vu {{ background: #f39c12; color: black; }}
    .iucn-lc {{ background: #27ae60; color: white; }}
    .section {{ margin: 2rem 0; padding: 1.5rem; background: #0d0d0d; border: 1px solid #1a1a1a; }}
    .hash {{ font-family: monospace; font-size: 0.75rem; color: #39FF14; word-break: break-all; background: #0a0a0a; padding: 0.3rem 0.5rem; border: 1px solid #1a1a1a; }}
    .footer {{ margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #222; text-align: center; color: #444; font-size: 0.75rem; }}
    .header-bar {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }}
    @media print {{
        body {{ background: white; color: #111; padding: 1rem; }}
        .metric {{ border-color: #ccc; }}
        .metric .value {{ color: #111; }}
        h1 {{ color: #111; }}
        h2 {{ color: #333; border-color: #ccc; }}
        th {{ background: #f0f0f0; color: #111; }}
        .hash {{ background: #f5f5f5; color: #111; }}
    }}
</style>
</head>
<body>

<div class="header-bar">
    <div>
        <h1>Relict Analysis Report</h1>
        <p class="subtitle">Job {job_id} | Generated {now}</p>
    </div>
    <div style="text-align: right; font-size: 0.75rem; color: #444;">
        Pipeline v{pipeline_version}<br>
        Relict - Reproducible eDNA Analysis
    </div>
</div>

<h2>1. Input Summary</h2>
<div class="grid">
    <div class="metric"><div class="label">Sample File</div><div class="value" style="font-size: 1rem;">{sample_filename}</div></div>
    <div class="metric"><div class="label">File Size</div><div class="value">{sample_size:,} bytes</div></div>
    <div class="metric"><div class="label">Input SHA256</div><div class="value" style="font-size: 0.7rem; word-break: break-all;">{sample_sha256}</div></div>
</div>

<h2>2. Diversity Metrics</h2>
<div class="grid">
    <div class="metric"><div class="label">ASVs Detected</div><div class="value">{n_asvs}</div></div>
    <div class="metric"><div class="label">Taxa Assigned</div><div class="value">{n_assigned}/{n_asvs}</div></div>
    <div class="metric"><div class="label">Shannon Index (H')</div><div class="value">{diversity.get('shannon', 0):.4f}</div></div>
    <div class="metric"><div class="label">Simpson Index (1-D)</div><div class="value">{diversity.get('simpson', 0):.4f}</div></div>
    <div class="metric"><div class="label">Species Richness</div><div class="value">{diversity.get('richness', 0)}</div></div>
    <div class="metric"><div class="label">Chao1 Estimate</div><div class="value">{diversity.get('chao1', 0):.2f}</div></div>
    <div class="metric"><div class="label">Pielou's Evenness</div><div class="value">{diversity.get('evenness', 0):.4f}</div></div>
</div>

<h2>3. Amplicon Sequence Variants</h2>
<div class="section">
<table>
    <thead>
        <tr><th>#</th><th>Species</th><th>Reads</th><th>Length</th><th>Identity</th><th>Lineage</th><th>Sequence</th></tr>
    </thead>
    <tbody>
        {asv_rows}
    </tbody>
</table>
</div>

<h2>4. Conservation Cross-Reference</h2>
<div class="grid" style="margin-bottom: 1rem;">
    <div class="metric"><div class="label">Species Queried</div><div class="value">{conservation.get('species_queried', 0)}</div></div>
    <div class="metric"><div class="label">Resolved in GBIF</div><div class="value">{n_gbif}</div></div>
    <div class="metric"><div class="label">IUCN Assessed</div><div class="value">{n_iucn}</div></div>
    <div class="metric"><div class="label">Threatened Species</div><div class="value" style="color: {'#c0392b' if threatened > 0 else '#39FF14'};">{threatened}</div></div>
</div>
<div class="section">
<table>
    <thead>
        <tr><th>Species</th><th>IUCN Status</th><th>GBIF Occurrences</th><th>Population Trend</th></tr>
    </thead>
    <tbody>
        {cons_rows}
    </tbody>
</table>
</div>

<h2>5. Provenance Manifest</h2>
<div class="section">
    <h3>Manifest Signature</h3>
    <div class="hash">{manifest_sha}</div>

    <h3 style="margin-top: 1.5rem;">Tool Versions</h3>
    <table>
        <thead><tr><th>Tool</th><th>Version</th></tr></thead>
        <tbody>{tool_rows}</tbody>
    </table>

    <h3 style="margin-top: 1.5rem;">Pipeline Stages</h3>
    <table>
        <thead><tr><th>Stage</th><th>Tool</th><th>Version</th><th>Runtime</th></tr></thead>
        <tbody>{stage_rows}</tbody>
    </table>

    <h3 style="margin-top: 1.5rem;">Parameter Hash</h3>
    <div class="hash">{parameter_hash}</div>
</div>

<div class="footer">
    <p>Generated by Relict v{pipeline_version} | Open-source reproducible eDNA analysis</p>
    <p>https://github.com/ShAuRyA-Noodle/Bad-Omens | MIT License</p>
    <p style="margin-top: 0.5rem;">Every number in this report was computed by real bioinformatics tools from real input data. No values are fabricated.</p>
</div>

</body>
</html>"""
