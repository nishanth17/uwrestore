"""Confirm the frozen Week-4A footage and the Week-3 reference product are intact.

EXPLORATORY. Runs in the main project venv (pure numpy).

`MONO_DEPTH_FREEZE.md` freezes the primary bakeoff to the SAME six Week-3
development clips and the SAME persisted Week-3 extraction — 6 x 48 = 288
frames — so that Week 4 tests monocular depth against exactly the footage whose
multi-view behaviour Week 3 characterised. Regenerating a different frame
sample would silently destroy that comparability, so this script checks and
reports rather than repairing: a frozen-baseline change is a STOP condition,
not something to fix in passing.

    .venv/bin/python -m experiments.week4_mono.scripts.verify_frozen_set
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week4_mono import common  # noqa: E402


def frame_set_sha256(clip: str) -> str:
    """Hash of the clip's frame bytes, in frame-index order.

    Reproduces the construction `extract_frames.py` recorded in
    `extraction_report.json`, so a mismatch means the PIXELS changed, not just
    the file listing.
    """
    h = hashlib.sha256()
    for i in common.frame_indices(clip):
        with open(common.frame_path(clip, i), "rb") as fh:
            h.update(fh.read())
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(common.OUTPUTS, "frozen_set_check.json"))
    ap.add_argument("--hash", action="store_true",
                    help="also re-hash every frame (slower, but proves the pixels)")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    report = common.verify_frozen_frames()
    report["reference_config"] = common.REFERENCE_CONFIG
    report["reference_status"] = (
        "PROVISIONAL MULTI-VIEW HYPOTHESIS, not ground truth. Agreement with it means "
        "consistency with the current Week-3 hypothesis, never objective correctness "
        "(MONO_DEPTH_FREEZE.md 7).")

    with open(os.path.join(common.FRAMES_ROOT, "extraction_report.json")) as fh:
        extraction = json.load(fh)

    if args.hash:
        for clip in common.CLIPS:
            got = frame_set_sha256(clip)
            want = extraction["clips"][clip]["frame_set_sha256"]
            report["clips"][clip]["frame_set_sha256"] = got
            report["clips"][clip]["frame_set_sha256_expected"] = want
            match = (got == want)
            report["clips"][clip]["frame_set_sha256_match"] = match
            report["clips"][clip]["ok"] = report["clips"][clip]["ok"] and match
            report["ok"] = report["ok"] and match

    total = sum(c["n_frames_present"] for c in report["clips"].values())
    report["total_frames"] = total
    report["expected_total_frames"] = len(common.CLIPS) * common.N_FRAMES_PER_CLIP

    common.write_json(args.out, report, overwrite=args.overwrite or True)

    print(f"[frozen-set] ok={report['ok']}  frames={total}/{report['expected_total_frames']}")
    for clip in common.CLIPS:
        c = report["clips"][clip]
        extra = ""
        if "frame_set_sha256_match" in c:
            extra = f" sha={'MATCH' if c['frame_set_sha256_match'] else 'MISMATCH'}"
        print(f"  {clip:16s} {c['n_frames_present']:2d} frames  {c['orientation']:9s} "
              f"{c['extracted_shape_hw']}  ref={c['reference_product_present']}"
              f"/{c['reference_n_frames']}{extra}  ok={c['ok']}")
    if not report["ok"]:
        print("[frozen-set] STOP: the frozen material does not match its report.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
