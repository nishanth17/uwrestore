"""Render the Stage 3/4/6/7 JSON results as the markdown tables FINDINGS.md uses.

EXPLORATORY. Main project venv. Read-only over `outputs/`; writes nothing.
Kept separate from `compare.py` so the numbers and their presentation cannot
drift apart — there is exactly one computation and one renderer.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
W3 = os.path.join(REPO_ROOT, "experiments", "week3_geometry")

CLIP_ORDER = ["wreck_07", "wreck_05", "cenote_01", "swimthrough_02", "wreck_01", "wreck_03"]


def _o(c):
    return CLIP_ORDER.index(c) if c in CLIP_ORDER else 99


def classical(d):
    print("\n### Classical arm — registration and diagnostics\n")
    print("| config | clip | run | registered | sub-models | 3D points | mean track | "
          "obs/img | focal px | reproj px (diag) | s | GB |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in sorted(d["classical_summary"], key=lambda x: (_o(x["clip"]), x["config"], x["repeat"])):
        if r.get("failed_at"):
            print(f"| {r['config']} | {r['clip']} | {r['repeat']} | **FAILED at "
                  f"{r['failed_at']}** | | | | | | | {r.get('seconds')} | |")
            continue
        sub = r.get("submodel_registered_images") or {}
        subs = "+".join(str(v) for v in sorted(sub.values(), reverse=True)) if sub else "?"
        print(f"| {r['config']} | {r['clip']} | {r['repeat']} | "
              f"{r['registered']}/48 ({r['registered_fraction']:.0%}) | {subs} | "
              f"{r['n_points3D']} | {r['mean_track_length']:.2f} | "
              f"{r['mean_obs_per_image']:.0f} | {r.get('focal_px')} | "
              f"{r['mean_reproj_px_DIAGNOSTIC_ONLY']:.3f} | {r.get('seconds')} | "
              f"{r.get('peak_rss_gb')} |")


def dense(d):
    print("\n### Learned dense arm — coverage, stability, cost\n")
    print("| config | clip | grid | valid frac (med/min) | per-frame median range "
          "(min..max) | drift max/min | frame-to-frame step | near/far p95/p05 | "
          "infer s | MPS GB |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for r in sorted(d["dense_summary"], key=lambda x: (_o(x["clip"]), x["config"])):
        v, m = r["valid_fraction"], r["per_frame_median_range"]
        g = r.get("inference_grid_hw")
        print(f"| {r['config']} | {r['clip']} | {g[0]}x{g[1]} | "
              f"{v['median']:.2f}/{v['min']:.2f} | "
              f"{m['median']:.2f} ({m['min']:.2f}..{m['max']:.2f}) | "
              f"{r['median_range_drift_max_over_min']:.2f} | "
              f"{r['median_range_frame_to_frame_relative_step']:.3f} | "
              f"{r['near_far_spread_p95_over_p05']:.1f} | "
              f"{r['seconds']['inference']:.0f} | {r.get('peak_mps_driver_gb')} |")


def dvs(d, refs=("A", "C_off")):
    for ref in refs:
        rows = [r for r in d["dense_vs_sparse"]
                if r.get("reference") == ref and "error" not in r]
        if not rows:
            continue
        print(f"\n### Dense vs sparse — reference: **{ref}** "
              f"(a competing hypothesis, NOT truth)\n")
        print("| dense | clip | obs used | coverage | fitted s | |rel err| med | p95 | "
              "radius swing | range swing | per-frame s max/min |")
        print("|---|---|---|---|---|---|---|---|---|---|")
        for r in sorted(rows, key=lambda x: (_o(x["clip"]), x["dense"])):
            rad = [p["median"] for p in r["residual_vs_image_radius"] if p["n"] > 50]
            rng = [p["median"] for p in r["residual_vs_reference_range"] if p["n"] > 50]
            rs = f"{100*(max(rad)-min(rad)):.1f}%" if len(rad) > 1 else "-"
            gs = f"{100*(max(rng)-min(rng)):.1f}%" if len(rng) > 1 else "-"
            print(f"| {r['dense']} | {r['clip']} | {r['n_observations_used']} | "
                  f"{r['coverage_fraction']:.2f} | {r['global_scale']:.3f} | "
                  f"{r['abs_relative_error']['median']:.3f} | "
                  f"{r['abs_relative_error']['p95']:.3f} | {rs} | {gs} | "
                  f"{r['per_frame_scale_diagnostic']['max_over_min']:.2f} |")


def dvd(d):
    print("\n### Dense vs dense — consistency, not correctness\n")
    print("| pair | clip | px | fitted s(a->b) | |rel err| med | p95 | radius swing | "
          "range swing | per-frame s max/min |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in sorted(d["dense_vs_dense"], key=lambda x: (x["a"], x["b"], _o(x["clip"]))):
        if "error" in r:
            print(f"| {r['a']} vs {r['b']} | {r['clip']} | — | — | — | — | — | — | "
                  f"**{r['error']}** |")
            continue
        rad = [p["median"] for p in r["residual_vs_image_radius"] if p["n"] > 50]
        rng = [p["median"] for p in r["residual_vs_b_range"] if p["n"] > 50]
        rs = f"{100*(max(rad)-min(rad)):.1f}%" if len(rad) > 1 else "-"
        gs = f"{100*(max(rng)-min(rng)):.1f}%" if len(rng) > 1 else "-"
        print(f"| {r['a']} vs {r['b']} | {r['clip']} | {r['n_pixels']} | "
              f"{r['global_scale_a_to_b']:.3f} | "
              f"{r['abs_relative_error']['median']:.3f} | "
              f"{r['abs_relative_error']['p95']:.3f} | {rs} | {gs} | "
              f"{r['per_frame_scale_diagnostic']['max_over_min']:.2f} |")


def svs(d):
    print("\n### Sparse vs sparse — repeatability and the ordinary/refractive pair\n")
    print("| a | b | clip | matched obs | s(a->b) | |rel err| med | p95 | kind |")
    print("|---|---|---|---|---|---|---|---|")
    for r in sorted(d["sparse_vs_sparse"],
                    key=lambda x: (x.get("kind", ""), _o(x.get("clip", "")), x.get("a", ""))):
        if "error" in r:
            print(f"| {r.get('a','?')} | {r.get('b','?')} | {r.get('clip','?')} | "
                  f"— | — | — | — | **{r['error']}** |")
            continue
        print(f"| {r['a']} | {r['b']} | {r['clip']} | {r['n_matched_observations']} | "
              f"{r['global_scale_a_to_b']:.4f} | "
              f"{r['abs_relative_error']['median']:.4f} | "
              f"{r['abs_relative_error']['p95']:.4f} | "
              f"{r.get('kind', 'cross-config')} |")


def interaction(d):
    print("\n### Radius x range interaction — the refraction discriminator\n")
    print("Radius-profile slope of the scale-aligned residual, computed SEPARATELY "
          "within each range bin. A slope that is the same in every range bin is "
          "radius-only (absorbed by the intrinsics); a slope that moves with range "
          "is the flat-port signature.\n")
    print("| comparison | clip | range bins | slope mean | slope spread (max-min) |")
    print("|---|---|---|---|---|")
    for key, label in (("dense_vs_sparse", None), ("dense_vs_dense", None)):
        for r in sorted(d[key], key=lambda x: _o(x["clip"])):
            it = r.get("radius_x_range_interaction")
            if not it or "slope_mean" not in it:
                continue
            name = (f"{r['dense']} vs {r['reference']}" if key == "dense_vs_sparse"
                    else f"{r['a']} vs {r['b']}")
            print(f"| {name} | {r['clip']} | {it['n_range_bins_with_a_slope']} | "
                  f"{it['slope_mean']:+.4f} | {it['slope_spread_max_minus_min']:.4f} |")


def sensitivity():
    p = os.path.join(W3, "outputs", "stage7", "sensitivity.json")
    if not os.path.exists(p):
        return
    s = json.load(open(p))
    print("\n### Restoration error budget\n")
    print("Local (unabsorbable) relative range error -> worst-channel relative error "
          "in restored linear radiance.\n")
    errs = [-0.20, -0.10, -0.05, 0.05, 0.10, 0.20]
    print("| water | range | " + " | ".join(f"{e:+.0%}" for e in errs) + " |")
    print("|---|---|" + "---|" * len(errs))
    for w in s["water_types"]:
        for dm in (1.0, 3.0, 8.0):
            cells = []
            for e in errs:
                row = next(r for r in s["local_shape_sensitivity"]
                           if r["water"] == w and r["range_m"] == dm
                           and r["range_rel_error"] == e)
                cells.append(f"{row['worst_channel_abs']:.1%}")
            print(f"| {w} | {dm:.0f} m | " + " | ".join(cells) + " |")
    print("\n| regime | range error reaching 2% | 5% | 10% radiance error |")
    print("|---|---|---|---|")
    for k, v in s["error_budget"].items():
        def f(t):
            x = v[f"range_error_reaching_{t}pct_radiance_error"]
            return f"{100*x:.1f}%" if x else ">60%"
        print(f"| {k} | {f(2)} | {f(5)} | {f(10)} |")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--comparison",
                    default=os.path.join(W3, "outputs", "stage6", "comparison.json"))
    ap.add_argument("--sections", nargs="*",
                    default=["classical", "dense", "dvs", "dvd", "svs",
                             "interaction", "sensitivity"])
    args = ap.parse_args()
    d = json.load(open(args.comparison)) if os.path.exists(args.comparison) else None
    fns = {"classical": classical, "dense": dense, "dvs": dvs, "dvd": dvd,
           "svs": svs, "interaction": interaction}
    for name in args.sections:
        if name == "sensitivity":
            sensitivity()
        elif d is not None:
            fns[name](d)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
