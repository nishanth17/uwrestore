"""Compare two backends on the SAME pixels. EXPLORATORY.

Every per-backend number elsewhere in this study is computed on that
backend's *own* forward/backward validity mask. That makes the residual and
the reduction ratio incomparable between backends whenever their masks
differ, because a backend that excludes more of the difficult region will
score better on what remains — the artefact PLAN.md legislates against
("never allow a method to obtain a good score merely by masking difficult
regions"). The rule has to apply to the backend you like as much as to the
one you don't.

This script removes the confound: it intersects the two backends' validity
masks (and their in-frame masks), then scores both on that common set. Any
difference that survives is a difference in correspondence quality rather
than in masking policy.

Reads the persisted .npy flow fields; runs no inference.

Usage:
  python -m experiments.week2a_flow.scripts.common_mask_compare \
      --a searaft --b waft --root outputs/flow_lag_study
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import cv2
import numpy as np

_REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from experiments.week2a_flow.common import (  # noqa: E402
    downscale_linear, eval_size_for, load_excerpt, write_json,
)
from uw.flow import warp_to_source  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--root", default="outputs/flow_lag_study")
    ap.add_argument("--anchor-local", type=int, default=16,
                    help="local index of the anchor whose .npy was persisted")
    ap.add_argument("--report", default=None)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    root = os.path.join(_REPO, args.root)
    meta = json.load(open(os.path.join(root, args.a, "metrics.json")))
    clips = {c["clip"]: (c["window_start_frame"], c["source"]) for c in meta["clips"]}
    lags = meta.get("lags") or [1, 4, 8]
    if "lags" not in meta:
        lags = sorted({r["lag"] for c in meta["clips"] for r in c["results"]})

    rows, wins = [], {args.a: 0, args.b: 0, "tie": 0}
    hdr = (f"{'clip':<13}{'lag':>4} | {'common':>7} | "
           f"{args.a[:11]+' red':>15} {args.b[:11]+' red':>15} | winner")
    print(hdr); print("-" * len(hdr))

    for clip, (start, src) in clips.items():
        fr = load_excerpt(os.path.join(_REPO, src), start, 41)
        eh, ew = eval_size_for(*fr[0].image.shape[:2])
        fr = downscale_linear(fr, eh, ew)
        a0 = args.anchor_local
        for lag in lags:
            d = {be: glob.glob(os.path.join(root, be, clip, f"lag{lag}_*")) for be in (args.a, args.b)}
            if not all(d.values()):
                continue
            F, M, res, inside = {}, {}, {}, {}
            lt, lt1 = fr[a0].image, fr[a0 + lag].image
            for be in (args.a, args.b):
                F[be] = np.load(os.path.join(d[be][0], "flow_forward.npy"))
                M[be] = cv2.imread(os.path.join(d[be][0], "fb_valid_mask.png"),
                                   cv2.IMREAD_GRAYSCALE) > 127
                w, ins = warp_to_source(lt1, F[be])
                res[be] = np.abs(w - lt).mean(axis=2)
                inside[be] = ins
            common = M[args.a] & M[args.b] & inside[args.a] & inside[args.b]
            if not common.any():
                continue
            static = float(np.abs(lt1 - lt).mean(axis=2)[common].mean())
            r = {be: float(res[be][common].mean()) for be in (args.a, args.b)}
            red = {be: static / r[be] for be in (args.a, args.b)}
            epe = np.sqrt(((F[args.a] - F[args.b]) ** 2).sum(axis=2))
            win = (args.a if red[args.a] > red[args.b] * 1.005
                   else args.b if red[args.b] > red[args.a] * 1.005 else "tie")
            wins[win] += 1
            rows.append({
                "clip": clip, "lag": lag,
                "common_mask_pct": float(100 * common.mean()),
                "own_mask_pct": {be: float(100 * M[be].mean()) for be in (args.a, args.b)},
                "warp_mae_common": r, "reduction_common": red,
                "uncompensated_mae_common": static,
                "flow_epe_between_backends_px": {
                    "median_overall": float(np.median(epe)),
                    "median_in_disputed": float(np.median(epe[M[args.a] ^ M[args.b]]))
                    if (M[args.a] ^ M[args.b]).any() else None,
                },
                "winner": win,
            })
            print(f"{clip:<13}{lag:>4} | {100*common.mean():6.1f}% | "
                  f"{red[args.a]:15.3f} {red[args.b]:15.3f} | {win}")

    print("-" * len(hdr))
    print("cells won on the common mask:", wins)
    print("\nA difference here is a correspondence-quality difference. A "
          "difference in the per-backend tables that vanishes here was a "
          "masking-policy difference.")

    out = {"a": args.a, "b": args.b, "wins": wins, "rows": rows,
           "note": ("Both backends scored on the intersection of their "
                    "validity and in-frame masks, so masking policy cannot "
                    "flatter either. Reduction = uncompensated / warped "
                    "residual on that common set, linear light.")}
    if args.report:
        write_json(os.path.join(_REPO, args.report), out, args.overwrite)
        print(f"\nwrote {args.report}")


if __name__ == "__main__":
    main()
