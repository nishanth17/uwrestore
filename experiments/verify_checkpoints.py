"""Verify local checkpoints against `experiments/checkpoint_provenance.json`.

EXPLORATORY. Main project venv (stdlib only).

WHY THIS EXISTS. A SHA-256 in a manifest is provenance, not preservation: it
lets you *recognise* the right artifact, never *recreate* one. This script is the
half that makes provenance useful — it turns "we recorded a hash" into "we can
prove this file is the one the experiments used", which matters most after a
checkpoint has been deleted and re-downloaded, or after an upstream repository
has silently replaced a file behind an unversioned URL.

Run it before trusting a re-obtained checkpoint, and after any cache pruning.

    .venv/bin/python -m experiments.verify_checkpoints            # verify
    .venv/bin/python -m experiments.verify_checkpoints --plan     # what is safe to delete
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MANIFEST = os.path.join(REPO_ROOT, "experiments", "checkpoint_provenance.json")


def resolve(path: str) -> str:
    p = os.path.expanduser(path)
    return p if os.path.isabs(p) else os.path.join(REPO_ROOT, p)


def find_blob(local_path: str, filename: str) -> str | None:
    """Locate the artifact: a direct file, or the file inside an HF cache dir."""
    p = resolve(local_path)
    if os.path.isfile(p):
        return p
    if os.path.isdir(p):
        snaps = os.path.join(p, "snapshots")
        if os.path.isdir(snaps):
            for rev in os.listdir(snaps):
                cand = os.path.join(snaps, rev, filename)
                if os.path.exists(cand):
                    return os.path.realpath(cand)
    return None


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=MANIFEST)
    ap.add_argument("--plan", action="store_true",
                    help="print the retention plan instead of hashing anything")
    args = ap.parse_args()
    with open(args.manifest) as fh:
        man = json.load(fh)

    if args.plan:
        order = ["current_pipeline", "relevant_comparison", "closed_candidate", "deleted"]
        for tier in order:
            rows = [c for c in man["checkpoints"] if c["retention_tier"] == tier]
            if not rows:
                continue
            total = sum(c.get("byte_size") or 0 for c in rows)
            print(f"\n{tier}  ({len(rows)} artifacts, {total / 1e9:.2f} GB)")
            print(f"  {man['_retention_tiers'][tier]}")
            for c in rows:
                sz = (c.get("byte_size") or 0) / 1e9
                frag = "" if c["source_durability"] == "durable" else \
                    f"   [{c['source_durability'].upper()} SOURCE — a hash cannot recover this]"
                print(f"    {sz:6.2f} GB  {c['method'].split(' (')[0]:<22}{frag}")
        print("\nNote: deleting a `closed_candidate` from a FRAGILE source trades "
              "rerunnability for space.\nThe recorded result survives; the ability to "
              "re-inspect the artifact may not.")
        return 0

    ok = missing = mismatch = skipped = 0
    for c in man["checkpoints"]:
        name = c["method"].split(" (")[0]
        if c["retention_tier"] == "deleted":
            print(f"  RECORD-ONLY  {name}  (already deleted; kept in the manifest as a record)")
            skipped += 1
            continue
        want = c.get("sha256")
        if not want or "..." in want:
            print(f"  NO HASH      {name}  (manifest has no usable SHA-256)")
            skipped += 1
            continue
        path = find_blob(c["local_path"], c.get("checkpoint_filename") or "")
        if path is None:
            print(f"  MISSING      {name}  (expected at {c['local_path']})")
            missing += 1
            continue
        got = sha256(path)
        size = os.path.getsize(path)
        if got == want and size == c.get("byte_size"):
            print(f"  OK           {name}  {size / 1e9:.2f} GB")
            ok += 1
        else:
            print(f"  MISMATCH     {name}")
            print(f"      expected {want}  ({c.get('byte_size')} bytes)")
            print(f"      got      {got}  ({size} bytes)")
            mismatch += 1

    print(f"\n{ok} ok, {missing} missing, {mismatch} MISMATCH, {skipped} skipped")
    return 1 if mismatch else 0


if __name__ == "__main__":
    sys.exit(main())
