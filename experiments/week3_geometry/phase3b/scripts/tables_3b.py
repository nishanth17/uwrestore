"""Phase 3B — render `analysis.json` as the markdown tables FINDINGS.md quotes.

EXPLORATORY. Main project venv (stdlib only).

The report must not contain hand-copied numbers. This turns the analysis
artifact into the exact tables that go into `FINDINGS.md`, so every figure there
is reproducible with one command.

Usage:
    .venv/bin/python -m experiments.week3_geometry.phase3b.scripts.tables_3b
    .venv/bin/python -m experiments.week3_geometry.phase3b.scripts.tables_3b --only 3B-1
"""

from __future__ import annotations

import argparse
import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
P3B = os.path.join(REPO_ROOT, "experiments", "week3_geometry", "phase3b")
ANALYSIS = os.path.join(P3B, "outputs", "analysis", "analysis.json")


def g(d, *path, default=None):
    for k in path:
        if d is None:
            return default
        d = d.get(k) if isinstance(d, dict) else None
    return default if d is None else d


def f(x, n=2, dash="--"):
    if x is None:
        return dash
    try:
        v = float(x)
    except (TypeError, ValueError):
        return str(x)
    if v != v:
        return dash
    return f"{v:.{n}f}"


def pct(x, n=1, dash="--"):
    if x is None:
        return dash
    try:
        v = float(x)
    except (TypeError, ValueError):
        return dash
    if v != v:
        return dash
    return f"{100 * v:.{n}f} %"


def table(rows: list[list[str]], header: list[str]) -> str:
    out = ["| " + " | ".join(header) + " |",
           "|" + "|".join("---" for _ in header) + "|"]
    for r in rows:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def runs_table(block: dict) -> str:
    rows = []
    for r in sorted(block["runs"], key=lambda x: (x["clip"], x["arm"])):
        s = r.get("structure") or {}
        fe = r.get("frontend") or {}
        ta = s.get("triangulation_angle_deg") or {}
        tl = s.get("track_length") or {}
        subs = r.get("submodel_registered_images") or {}
        rows.append([
            r["clip"], r["arm"],
            f"{s.get('registered_images', '--')}/{r.get('n_images_offered', '--')}",
            ",".join(str(v) for v in sorted(subs.values(), reverse=True)) or "--",
            str(s.get("n_points3D", "--")),
            f(tl.get("mean")), f(tl.get("median"), 0), f(tl.get("p95"), 0),
            f(ta.get("median")), pct(ta.get("frac_below_2deg")), pct(ta.get("frac_below_5deg")),
            f(g(s, "baseline_over_depth", "median"), 3),
            f(g(s, "track_temporal_span_source_frames", "median"), 0),
            pct(g(s, "track_temporal_span_source_frames",
                  "frac_tracks_spanning_ge_25pct_of_clip")),
            f(fe.get("keypoints_per_image"), 0),
            str(fe.get("n_verified_matches", "--")),
            f(fe.get("verified_over_putative_matches"), 3),
            f(s.get("focal_px"), 1),
            (str(g(s, "degeneracy_screen", "n_frames_with_median_range_below_1e-3_of_clip_median"))
             if s.get("degeneracy_screen") else "--"),
            f(r.get("mean_reproj_px_DIAGNOSTIC_ONLY"), 3),
            f(r.get("total_seconds"), 0),
        ])
    return table(rows, ["clip", "arm", "reg", "submodels", "points", "track mean",
                        "track med", "track p95", "tri angle med deg", "tri < 2 deg",
                        "tri < 5 deg", "base/depth med", "span med", "span >= 25 %",
                        "kpts/img", "verified matches", "inlier ratio", "focal px",
                        "degen frames", "reproj px (diag)", "s"])


def shape_table(comparisons: list, title: str) -> str:
    rows = []
    for c in comparisons:
        if c.get("error"):
            rows.append([c.get("clip", "--"), f"{c['a']} vs {c['b']}", "--", "--",
                         c["error"], "--", "--", "--", "--"])
            continue
        rows.append([
            c.get("clip", "--"), f"{c['a']} vs {c['b']}",
            str(c.get("n_shared_frames", "--")),
            str(c.get("n_matched_observations", "--")),
            f(c.get("global_scale_a_to_b"), 4),
            pct(g(c, "abs_relative_error", "median")),
            pct(g(c, "abs_relative_error", "p95")),
            pct(c.get("range_swing")),
            pct(c.get("radius_swing")),
            f(g(c, "per_frame_scale_diagnostic", "max_over_min")),
        ])
    return f"**{title}**\n\n" + table(
        rows, ["clip", "pair", "frames", "matched obs", "fitted s",
               "|rel err| med", "p95", "range swing", "radius swing",
               "per-frame s max/min"])


def traj_table(rows_in: list) -> str:
    rows = []
    for c in rows_in:
        if c.get("error"):
            rows.append([c.get("clip", "--"), f"{c['a']} vs {c['b']}",
                         str(c.get("n_common_frames", "--")), c["error"], "--", "--", "--"])
            continue
        rows.append([
            c.get("clip", "--"), f"{c['a']} vs {c['b']}",
            f"{c.get('n_common_frames')} ({c.get('n_frames_a')}/{c.get('n_frames_b')})",
            f(c.get("similarity_scale_a_to_b"), 4),
            pct(g(c, "residual_over_extent", "rmse"), 2),
            pct(g(c, "residual_over_extent", "median"), 2),
            pct(g(c, "residual_over_extent", "max"), 2),
        ])
    return table(rows, ["clip", "pair", "shared frames (a/b)", "similarity scale",
                        "traj RMSE / extent", "median", "max"])


def dense_table(rows_in: list) -> str:
    rows = []
    for c in rows_in:
        if c.get("error"):
            rows.append([c.get("clip", "--"), c.get("dense", "--"),
                         c.get("reference_arm", "--"), c["error"], "--", "--", "--"])
            continue
        prof = c.get("residual_vs_reference_range") or []
        meds = [p["median"] for p in prof if p.get("n", 0) > 30
                and p["median"] == p["median"]]
        swing = (max(meds) - min(meds)) if len(meds) >= 2 else float("nan")
        rows.append([
            c.get("clip", "--"), c.get("dense", "--"), c.get("reference_arm", "--"),
            pct(c.get("coverage_fraction")),
            f(c.get("global_scale"), 3),
            pct(g(c, "abs_relative_error", "median")),
            pct(swing),
            f(g(c, "per_frame_scale_diagnostic", "max_over_min")),
        ])
    return table(rows, ["clip", "dense", "reference", "coverage", "fitted s",
                        "|rel err| med", "range swing", "per-frame s max/min"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--analysis", default=ANALYSIS)
    ap.add_argument("--only", nargs="*", default=None)
    args = ap.parse_args()
    with open(args.analysis) as fh:
        data = json.load(fh)

    for hid, block in data["hypotheses"].items():
        if args.only and hid not in args.only:
            continue
        print(f"\n\n# {hid}\n\n{block['question']}\n")
        if block.get("missing"):
            print("_missing arms:_ " + ", ".join(
                f"{m['arm']}/{m['clip']}" for m in block["missing"]) + "\n")
        print("**Runs**\n")
        print(runs_table(block))
        if block.get("shape_comparisons"):
            print()
            print(shape_table(block["shape_comparisons"],
                              "Scale-aligned sparse-vs-sparse shape "
                              "(ONE global scale per pair per clip)"))
        if block.get("trajectory_comparisons"):
            print("\n**Camera-trajectory agreement (ONE similarity: rotation, translation, "
                  "scale; residual normalised by trajectory extent)**\n")
            print(traj_table(block["trajectory_comparisons"]))
        if block.get("repeat_spread"):
            print()
            print(shape_table(block["repeat_spread"],
                              "Repeat-run spread -- the noise floor any claimed "
                              "effect must clear"))
            for r in block["repeat_spread"]:
                print(f"\n  {r['clip']} {r['a']} vs {r['b']}: "
                      f"registered {r.get('registered')}, points {r.get('n_points3D')}")
        if block.get("dense_vs_reference"):
            print("\n**Phase 3A dense products re-measured against this reference**\n")
            print(dense_table(block["dense_vs_reference"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
