"""Does the metric stay put when nothing changes? EXPLORATORY (Phase 2B).

A regression metric has to do two things, and the rest of this phase only
tested one of them. `run_temporal_eval.py` shows the numbers MOVING when the
pipeline changes (gray-world raises raw MC-Warp 2–3x on four of five clips).
This script tests the other half:

  1. **Repeat**   — same clip, same window, same anchors, run twice. Anything
                    other than an exact match is nondeterminism, and Phase 2A
                    disqualified a backend for exactly that.
  2. **Anchors**  — the same clip and window measured from three different
                    anchor triples. The spread across them is the metric's own
                    sampling noise, and it is the number that says how large a
                    pipeline change has to be before it means anything.

Without (2), "gray-world raises MC-Warp 2.23x" has no error bar.

    experiments/week2a_flow/.venv-flow/bin/python \
        -m experiments.week2b_temporal.scripts.stability_check --overwrite
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

_REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from uw.baselines import gray_world  # noqa: E402
from uw.io import load  # noqa: E402
from uw.metrics import evaluate_temporal  # noqa: E402
from uw.searaft import SeaRaftBackend  # noqa: E402

WINDOW_FRAMES = 41
WINDOW_OFFSET = 14
ANCHOR_SETS = {"A": (16, 18, 20), "B": (15, 17, 19), "C": (17, 19, 21)}
LAGS = (1, 4, 8)
TRACKED = ("raw_warp", "illumination_aware_warp", "uncompensated",
           "motion_reduction_ratio", "temporal_delta_e", "valid_fraction")


def snapshot(result):
    return {lag.lag: {k: getattr(lag, k) for k in TRACKED} for lag in result.lags}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="mps")
    ap.add_argument("--out", default="outputs/temporal_metric/stability_check.json")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    with open(os.path.join(_REPO, "experiments/week2a_flow/excerpts.json")) as f:
        excerpts = json.load(f)["clips"]

    backend = SeaRaftBackend(device=args.device)
    report = {"backend": backend.describe(), "anchor_sets": ANCHOR_SETS,
              "lags": list(LAGS), "clips": {}}
    all_repeat_exact = True

    for name, info in excerpts.items():
        start = max(0, min(int(info["selected_excerpt_start"]) - WINDOW_OFFSET,
                           int(info["frame_count"]) - WINDOW_FRAMES))
        frames = list(load(os.path.join(_REPO, info["path"]),
                           start=start, count=WINDOW_FRAMES))
        corrected = [gray_world(f) for f in frames]
        print(f"\n=== {name} frames {start}..{start + WINDOW_FRAMES - 1} ===")

        runs = {}
        for tag, anchors in ANCHOR_SETS.items():
            runs[tag] = snapshot(evaluate_temporal(
                frames, corrected, backend, lags=LAGS, anchors=anchors))
        repeat = snapshot(evaluate_temporal(
            frames, corrected, backend, lags=LAGS, anchors=ANCHOR_SETS["A"]))
        del frames, corrected

        exact = repeat == runs["A"]
        all_repeat_exact &= exact
        print(f"  repeat of anchor set A is exact: {exact}")

        spread = {}
        for lag in LAGS:
            spread[lag] = {}
            for key in TRACKED:
                vals = [runs[t][lag][key] for t in ANCHOR_SETS]
                if any(v is None for v in vals):
                    spread[lag][key] = None
                    continue
                mean = float(np.mean(vals))
                spread[lag][key] = {
                    "values": [float(v) for v in vals],
                    "mean": mean,
                    "spread_pct_of_mean": float(
                        100.0 * (max(vals) - min(vals)) / mean) if mean else None,
                }
            row = spread[lag]
            print(f"  @{lag}: anchor-set spread — raw "
                  f"{row['raw_warp']['spread_pct_of_mean']:.1f}%  "
                  f"illum {row['illumination_aware_warp']['spread_pct_of_mean']:.1f}%  "
                  f"reduction {row['motion_reduction_ratio']['spread_pct_of_mean']:.1f}%  "
                  f"dE {row['temporal_delta_e']['spread_pct_of_mean']:.1f}%  "
                  f"coverage {row['valid_fraction']['spread_pct_of_mean']:.1f}%")

        report["clips"][name] = {
            "frame_range": [start, start + WINDOW_FRAMES - 1],
            "repeat_of_anchor_set_A_is_exact": exact,
            "anchor_set_spread": {str(k): v for k, v in spread.items()},
        }

    report["all_repeats_exact"] = all_repeat_exact
    print(f"\nall repeats exact across every clip and lag: {all_repeat_exact}")

    path = os.path.join(_REPO, args.out)
    if os.path.exists(path) and not args.overwrite:
        raise FileExistsError(f"{path!r} exists; pass --overwrite")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
