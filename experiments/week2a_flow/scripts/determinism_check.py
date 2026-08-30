"""Is a backend reproducible run-to-run? EXPLORATORY.

PLAN.md's operating loop requires ruling out nondeterminism before treating a
changed number as a regression. A flow backend that returns a different field
for the same input makes any metric built on it a noisy signal, so this is a
property worth measuring rather than assuming.

Runs estimate() twice on the identical pair in the identical process and
reports the max/mean absolute difference between the two flow fields, plus
what that does to the derived FB validity mask — which is the quantity that
actually feeds a metric, and which sits near a threshold and so amplifies
small numerical differences.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

_REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from experiments.week2a_flow.common import downscale_linear, eval_size_for, load_excerpt  # noqa: E402
from experiments.week2a_flow.scripts.run_bakeoff import build_backend  # noqa: E402
from uw.flow import forward_backward_consistency  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True,
                    choices=["searaft", "waft", "videoflow_mof"])
    ap.add_argument("--device", default="mps")
    ap.add_argument("--clip", default="data/testset/murky/MURKYSHARK.MP4")
    ap.add_argument("--start", type=int, default=2)
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--report", default=None)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    frames_full = load_excerpt(os.path.join(_REPO, args.clip), args.start, 12)
    h, w = frames_full[0].image.shape[:2]
    eh, ew = eval_size_for(h, w)
    frames = downscale_linear(frames_full, eh, ew)

    be = build_backend(args.backend, args.device)
    runs = []
    for r in range(args.repeats):
        fwd = be.estimate(frames, 4, 5)
        bwd = be.estimate(frames, 5, 4)
        valid, _ = forward_backward_consistency(fwd.flow, bwd.flow)
        runs.append((fwd.flow, bwd.flow, valid))
        print(f"  run {r}: fb_valid {100.0 * valid.mean():.2f}%", flush=True)

    f0, b0, v0 = runs[0]
    out = {"backend": args.backend, "clip": args.clip, "pair": [args.start + 4, args.start + 5],
           "repeats": args.repeats, "comparisons": []}
    for r in range(1, args.repeats):
        f1, b1, v1 = runs[r]
        c = {
            "run": r,
            "forward_max_abs_diff_px": float(np.abs(f0 - f1).max()),
            "forward_mean_abs_diff_px": float(np.abs(f0 - f1).mean()),
            "backward_max_abs_diff_px": float(np.abs(b0 - b1).max()),
            "fb_valid_pct_run0": float(100.0 * v0.mean()),
            "fb_valid_pct_run": float(100.0 * v1.mean()),
            "fb_valid_pixels_flipped_pct": float(100.0 * (v0 != v1).mean()),
            "bitwise_identical": bool(np.array_equal(f0, f1) and np.array_equal(b0, b1)),
        }
        out["comparisons"].append(c)
        print(json.dumps(c, indent=2))

    if args.report:
        p = os.path.join(_REPO, args.report)
        if os.path.exists(p) and not args.overwrite:
            raise FileExistsError(f"{p!r} exists; pass --overwrite")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        json.dump(out, open(p, "w"), indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
