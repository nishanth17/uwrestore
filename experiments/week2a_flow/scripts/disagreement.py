"""Where do the backends disagree? EXPLORATORY.

Aggregate statistics turned out nearly identical across the three backends
(see comparison.md), which by itself proves nothing about whether they are
computing the *same* flow — three fields can share a mean and differ
everywhere. This reads back the raw .npy fields run_bakeoff saved and
measures the disagreement directly.

For each clip/pair it reports, for every backend pair, the endpoint error
between their forward flows:
  * over all pixels,
  * over pixels both backends' common FB mask calls valid — i.e. where both
    claim to be trustworthy, which is where disagreement actually matters.
It also writes a per-pixel map of the largest disagreement between any two
backends, so the regions can be seen rather than inferred.

There is no ground truth here. Disagreement localises the ambiguity; it does
not say who is right.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import sys

import cv2
import numpy as np

_REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from experiments.week2a_flow.common import colorize_scalar, save_rgb, write_json  # noqa: E402

# FlowIt stays in this list although its wrapper was deleted in Phase 2B:
# these scripts read persisted metrics.json / .npy output and skip any
# backend whose directory is absent, so the historical Phase 2A tables
# still regenerate from what is on disk while a fresh run simply omits it.
BACKENDS = ["searaft", "waft", "flowit", "videoflow_mof"]


def stats(a):
    a = a[np.isfinite(a)]
    if a.size == 0:
        return {"mean": None, "median": None, "p95": None, "p99": None, "max": None}
    return {
        "mean": float(a.mean()), "median": float(np.median(a)),
        "p95": float(np.percentile(a, 95)), "p99": float(np.percentile(a, 99)),
        "max": float(a.max()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="outputs/flow_comparison")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    root = os.path.join(_REPO, args.root)
    out_root = os.path.join(root, "_disagreement")

    base = os.path.join(root, BACKENDS[0])
    report = {
        "_comment": (
            "Endpoint error between backends' forward flow fields, in pixels "
            "on the 960x540 evaluation grid. 'both_valid' restricts to pixels "
            "the common forward/backward mask marks valid for BOTH backends. "
            "No ground truth is involved: this localises ambiguity, it does "
            "not rank the backends."
        ),
        "clips": {},
    }

    for clip in sorted(os.listdir(base)):
        if not os.path.isdir(os.path.join(base, clip)):
            continue
        for pd in sorted(os.listdir(os.path.join(base, clip))):
            if not pd.startswith("pair_"):
                continue
            flows, masks = {}, {}
            for be in BACKENDS:
                d = os.path.join(root, be, clip, pd)
                fp = os.path.join(d, "flow_forward.npy")
                if not os.path.exists(fp):
                    continue
                flows[be] = np.load(fp)
                mp = os.path.join(d, "fb_valid_mask.png")
                masks[be] = cv2.imread(mp, cv2.IMREAD_GRAYSCALE) > 127
            if len(flows) < 2:
                continue

            entry = {}
            maps = []
            for a, b in itertools.combinations(sorted(flows), 2):
                epe = np.sqrt(((flows[a] - flows[b]) ** 2).sum(axis=2))
                both = masks[a] & masks[b]
                entry[f"{a}_vs_{b}"] = {
                    "epe_px_all": stats(epe),
                    "epe_px_both_valid": stats(epe[both]),
                    "both_valid_pct": float(100.0 * both.sum() / both.size),
                    "pct_pixels_over_1px": float(100.0 * (epe > 1.0).mean()),
                    "pct_pixels_over_3px": float(100.0 * (epe > 3.0).mean()),
                }
                maps.append(epe)

            worst = np.maximum.reduce(maps)
            entry["max_pairwise_disagreement_px"] = stats(worst)
            out_png = os.path.join(out_root, f"{clip}__{pd}.png")
            # fixed 0-3 px scale so every clip's map is read the same way
            save_rgb(out_png, colorize_scalar(worst, lo=0.0, hi=3.0), args.overwrite)
            entry["map"] = os.path.relpath(out_png, _REPO)
            report["clips"].setdefault(clip, {})[pd] = entry
            print(f"{clip}/{pd}: max-pairwise median "
                  f"{entry['max_pairwise_disagreement_px']['median']:.3f}px  "
                  f"p99 {entry['max_pairwise_disagreement_px']['p99']:.2f}px  "
                  f"max {entry['max_pairwise_disagreement_px']['max']:.1f}px")

    write_json(os.path.join(root, "disagreement.json"), report, args.overwrite)
    print(f"\nwrote {os.path.join(root, 'disagreement.json')}")


if __name__ == "__main__":
    main()
