"""Cross-backend MC-Warp@1/4/8 comparison table. EXPLORATORY.

Reports, per clip and lag: coverage, the residual reduction ratio (the
quantity comparable across lags), the absolute warp residual, FB error and
flow magnitude. Coverage is printed beside every score, per PLAN.md — an
MC-Warp value without its coverage is incomplete, and at lag 8 coverage
falls far enough that the two must be read together.

As with aggregate.py: no weighted score, no ranking claim.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics as st
import sys

_REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
# FlowIt stays in this list although its wrapper was deleted in Phase 2B:
# these scripts read persisted metrics.json / .npy output and skip any
# backend whose directory is absent, so the historical Phase 2A tables
# still regenerate from what is on disk while a fresh run simply omits it.
BACKENDS = ["searaft", "waft", "flowit", "videoflow_mof"]
LAGS = [1, 4, 8]


def load(root, be):
    p = os.path.join(root, be, "metrics.json")
    return json.load(open(p)) if os.path.exists(p) else None


def mean(vals):
    vals = [v for v in vals if v is not None]
    return st.mean(vals) if vals else None


def f(v, n=3):
    return "n/a" if v is None else f"{v:.{n}f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="outputs/flow_lag_study")
    ap.add_argument("--out", default=None)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    root = os.path.join(_REPO, args.root)
    data = {b: load(root, b) for b in BACKENDS}
    present = [b for b in BACKENDS if data[b]]
    if not present:
        print("no lag-study results found")
        return

    L = []
    L.append("# MC-Warp lag study — @1 / @4 / @8\n")
    L.append("Means over 3 anchors per clip. `cov` = forward/backward valid "
             "coverage %. `red` = residual reduction ratio vs the "
             "uncompensated residual at the same lag (the quantity comparable "
             "across lags). `warpMAE` is linear-light. † = run off the "
             "model's training distribution (MOF at lag>1 uses a "
             "frame-subsampled window).\n")

    clips = [c["clip"] for c in data[present[0]]["clips"]]

    L.append("\n## Coverage by lag — the headline\n")
    L.append("| clip | lag | " + " | ".join(present) + " |")
    L.append("|---|---|" + "---|" * len(present))
    for clip in clips:
        for lag in LAGS:
            row = [clip, f"@{lag}"]
            for b in present:
                c = next((x for x in data[b]["clips"] if x["clip"] == clip), None)
                rs = [r for r in c["results"] if r["lag"] == lag] if c else []
                dagger = "†" if rs and rs[0].get("off_distribution") else ""
                row.append(f(mean([r["fb_valid_coverage_pct"] for r in rs]), 1) + "%" + dagger)
            L.append("| " + " | ".join(row) + " |")

    L.append("\n## Residual reduction ratio by lag (higher = flow explains more)\n")
    L.append("| clip | lag | " + " | ".join(present) + " |")
    L.append("|---|---|" + "---|" * len(present))
    for clip in clips:
        for lag in LAGS:
            row = [clip, f"@{lag}"]
            for b in present:
                c = next((x for x in data[b]["clips"] if x["clip"] == clip), None)
                rs = [r for r in c["results"] if r["lag"] == lag] if c else []
                row.append(f(mean([r["residual_reduction_ratio"] for r in rs]), 2) + "x")
            L.append("| " + " | ".join(row) + " |")

    L.append("\n## Per-clip detail\n")
    for clip in clips:
        L.append(f"\n### {clip}\n")
        L.append("| backend | lag | \\|flow\\| med px | cov % | FB err med px | "
                 "warp MAE (lin) | uncomp MAE | reduction | s/inf |")
        L.append("|---|---|---|---|---|---|---|---|---|")
        for b in present:
            c = next((x for x in data[b]["clips"] if x["clip"] == clip), None)
            if not c:
                continue
            for lag in LAGS:
                rs = [r for r in c["results"] if r["lag"] == lag]
                if not rs:
                    continue
                dagger = "†" if rs[0].get("off_distribution") else ""
                L.append(
                    f"| {b}{dagger} | @{lag} "
                    f"| {f(mean([r['flow_magnitude_px']['median'] for r in rs]), 1)} "
                    f"| {f(mean([r['fb_valid_coverage_pct'] for r in rs]), 1)} "
                    f"| {f(mean([r['fb_error_px_over_evaluable']['median'] for r in rs]), 3)} "
                    f"| {f(mean([r['warp_residual_linear_over_fb_valid']['mae'] for r in rs]), 5)} "
                    f"| {f(mean([r['static_residual_linear_over_fb_valid']['mae'] for r in rs]), 5)} "
                    f"| {f(mean([r['residual_reduction_ratio'] for r in rs]), 2)}x "
                    f"| {f(mean([r['runtime_s_forward'] for r in rs]), 2)} |"
                )

    L.append("\n## Coverage loss from @1 to @8, per backend (mean over clips)\n")
    L.append("| backend | cov @1 | cov @4 | cov @8 | @1→@8 loss |")
    L.append("|---|---|---|---|---|")
    for b in present:
        covs = []
        for lag in LAGS:
            vals = [r["fb_valid_coverage_pct"]
                    for c in data[b]["clips"] for r in c["results"] if r["lag"] == lag]
            covs.append(mean(vals))
        loss = (covs[0] - covs[2]) if None not in covs else None
        L.append(f"| {b} | {f(covs[0],1)}% | {f(covs[1],1)}% | {f(covs[2],1)}% | "
                 f"{f(loss,1)} pts |")

    text = "\n".join(L)
    print(text)
    if args.out:
        p = os.path.join(_REPO, args.out)
        if os.path.exists(p) and not args.overwrite:
            raise FileExistsError(f"{p!r} exists; pass --overwrite")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").write(text + "\n")
        print(f"\nwrote {p}")


if __name__ == "__main__":
    main()
