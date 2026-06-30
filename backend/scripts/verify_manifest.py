"""Offline verifier for a Relict provenance manifest.

Verifies a manifest WITHOUT contacting the server, so a reviewer or a third
party can independently confirm a published result. It checks two things:

1. **Content hash** — recomputes the canonical SHA256 and compares it to the
   ``manifest_sha256`` recorded in the file. Detects any edit to the signed
   content.
2. **Ed25519 signature** — verifies ``signature`` against a public key.

The public key can come from (in priority order): ``--public-key-b64``,
``--public-key-url`` (e.g. the server's ``/public-key`` endpoint), or — as a
last resort — the copy embedded in the manifest. The embedded key only proves
the manifest is internally consistent; to prove it was signed by a *specific*
server, pass that server's key explicitly.

Usage::

    python -m scripts.verify_manifest provenance.json
    python -m scripts.verify_manifest provenance.json --public-key-url https://relict-api.onrender.com/public-key

Exit code 0 = verified, 1 = verification failed.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

from app.core import manifest as manifest_core
from app.core import signing as crypto


def _load_public_key(args: argparse.Namespace, manifest: dict[str, Any]) -> tuple[bytes | None, str]:
    """Return (public_key_raw, source_description)."""
    if args.public_key_b64:
        return base64.b64decode(args.public_key_b64), "command line"
    if args.public_key_url:
        with urllib.request.urlopen(args.public_key_url, timeout=15) as resp:  # noqa: S310 — operator-supplied URL
            data = json.load(resp)
        return base64.b64decode(data["public_key_b64"]), f"URL {args.public_key_url}"
    embedded = manifest.get("public_key")
    if isinstance(embedded, dict) and embedded.get("key_b64"):
        return base64.b64decode(embedded["key_b64"]), "manifest (embedded — not independently trusted)"
    return None, "none"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a Relict provenance manifest offline.")
    parser.add_argument("manifest", type=Path, help="Path to provenance.json")
    parser.add_argument("--public-key-b64", help="Raw Ed25519 public key, base64")
    parser.add_argument("--public-key-url", help="URL returning {public_key_b64: ...} (e.g. /public-key)")
    args = parser.parse_args(argv)

    manifest = json.loads(args.manifest.read_text())

    computed = manifest_core.compute_manifest_hash(manifest)
    claimed = manifest.get("manifest_sha256")
    content_ok = bool(claimed) and computed == claimed

    public_key, source = _load_public_key(args, manifest)
    signature = manifest.get("signature")
    if public_key is None:
        sig_ok = False
    elif not signature:
        sig_ok = False
    else:
        sig_ok = crypto.verify(public_key, manifest_core.canonical_bytes(manifest), signature)

    print(f"manifest:        {args.manifest}")
    print(f"content hash:    {'OK' if content_ok else 'MISMATCH'}  (computed {computed[:16]}…, claimed {str(claimed)[:16]}…)")
    print(f"public key:      {source}")
    print(f"signature:       {'OK' if sig_ok else 'INVALID/MISSING'}")
    verified = content_ok and sig_ok
    print(f"\nRESULT:          {'VERIFIED' if verified else 'NOT VERIFIED'}")
    if source.startswith("manifest") and verified:
        print("NOTE: verified against the manifest's embedded key. Re-run with "
              "--public-key-url to confirm it was signed by the expected server.")
    return 0 if verified else 1


if __name__ == "__main__":
    sys.exit(main())
