"""Cross-backend quantitative comparison table. EXPLORATORY.

Reads each backend's metrics.json and prints one markdown table per clip.
Deliberately does NOT combine the columns into a single score: these are
five different failure modes measured on five short excerpts, and a weighted
sum would hide exactly the disagreements this phase exists to find.
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


def load(root, be):
    p = os.path.join(root, be, "metrics.json")
    return json.load(open(p)) if os.path.exists(p) else None


def agg(pairs, path, stat="mean"):
    vals = []
    for p in pairs:
        v = p
        for k in path:
            v = v[k] if isinstance(v, dict) else None
            if v is None:
                break
        if v is not None:
            vals.append(float(v))
    if not vals:
        return None
    return st.mean(vals) if stat == "mean" else max(vals)


def fmt(v, n=3):
    return "n/a" if v is None else f"{v:.{n}f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="outputs/flow_comparison")
    ap.add_argument("--out", default=None, help="write markdown here as well")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    root = os.path.join(_REPO, args.root)

    data = {be: load(root, be) for be in BACKENDS}
    present = [be for be in BACKENDS if data[be]]
    lines = []

    lines.append("Per-backend environment\n")
    lines.append("| backend | model | checkpoint | device | inference res | native confidence |")
    lines.append("|---|---|---|---|---|---|")
    for be in present:
        e = data[be]["environment"]
        infres = data[be]["clips"][0]["pairs"][0].get("inference_size_hw")
        lines.append(
            f"| {be} | {e['model']} | {e['checkpoint']} | {e['device_requested']} | "
            f"{infres} (landscape) | {'yes' if 'none' not in e['native_confidence'] else 'none'} |"
        )
    lines.append("")

    clips = [c["clip"] for c in data[present[0]]["clips"]]
    for clip in clips:
        info = next(c for c in data[present[0]]["clips"] if c["clip"] == clip)
        lines.append(f"\n### {clip}  (frames {info['excerpt_start_frame']}"
                     f"..{info['excerpt_start_frame'] + info['excerpt_frames'] - 1}, "
                     f"source {info['source_size_hw']}, eval {info['eval_size_hw']})\n")
        lines.append("| backend | s/inf | non-finite % | FB valid % | FB err med px | FB err p95 px "
                     "| warp MAE (lin) | uncomp MAE (lin) | reduction | \\|flow\\| med px | \\|flow\\| p95 | \\|flow\\| max |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for be in present:
            c = next((x for x in data[be]["clips"] if x["clip"] == clip), None)
            if not c:
                continue
            pr = c["pairs"]
            rt = agg(pr, ["runtime_s_forward"])
            nf = agg(pr, ["nonfinite_flow_pct_fwd"])
            fv = agg(pr, ["fb_valid_coverage_pct"])
            fe = agg(pr, ["fb_error_px_over_evaluable", "median"])
            f9 = agg(pr, ["fb_error_px_over_evaluable", "p95"])
            wm = agg(pr, ["warp_residual_linear_over_fb_valid", "mae"])
            sm = agg(pr, ["static_residual_linear_over_fb_valid", "mae"])
            mm = agg(pr, ["flow_magnitude_px", "median"])
            m9 = agg(pr, ["flow_magnitude_px", "p95"])
            mx = agg(pr, ["flow_magnitude_px", "max"], "max")
            red = (sm / wm) if (wm and sm) else None
            lines.append(
                f"| {be} | {fmt(rt,2)} | {fmt(nf,3)} | {fmt(fv,1)} | {fmt(fe,3)} | {fmt(f9,2)} "
                f"| {fmt(wm,5)} | {fmt(sm,5)} | {fmt(red,2)}x | {fmt(mm,2)} | {fmt(m9,2)} | {fmt(mx,1)} |"
            )

    lines.append("\n### Memory / whole-run cost\n")
    lines.append("| backend | peak process RSS MB | peak MPS driver alloc MB |")
    lines.append("|---|---|---|")
    for be in present:
        mps = max((c.get("peak_mps_driver_allocated_mb") or 0) for c in data[be]["clips"])
        lines.append(f"| {be} | {data[be]['peak_process_rss_mb']:.0f} | "
                     f"{mps:.0f} |" if mps else
                     f"| {be} | {data[be]['peak_process_rss_mb']:.0f} | unavailable |")

    text = "\n".join(lines)
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
