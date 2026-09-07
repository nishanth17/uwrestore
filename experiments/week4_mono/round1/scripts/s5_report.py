"""Aggregate S5 into `results/S5_TEMPORAL.md` and `results/S5_results.json`."""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week4_mono.round1 import armio, common  # noqa: E402
from experiments.week4_mono.round1.scripts.s0_report import md_table  # noqa: E402


def per_arm(raw, arm, path, agg=np.median):
    vals = {}
    for clip, r in raw["arms"][arm]["clips"].items():
        if r.get("status") != "ok":
            continue
        cur = r
        for k in path:
            cur = cur.get(k) if isinstance(cur, dict) else None
            if cur is None:
                break
        if isinstance(cur, (int, float)) and np.isfinite(cur):
            vals[clip] = float(cur)
    return vals


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", default=os.path.join(common.OUTPUTS, "s5", "s5_raw.json"))
    ap.add_argument("--flow-summary", default=os.path.join(common.OUTPUTS, "flow",
                                                           "_summary.json"))
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    with open(args.raw) as fh:
        raw = json.load(fh)
    flow = None
    if os.path.exists(args.flow_summary):
        with open(args.flow_summary) as fh:
            flow = json.load(fh)
    arms = [a for a in common.MODELS if a in raw["arms"]] + \
           [a for a in raw["arms"] if a not in common.MODELS]
    clips = raw["clips"]

    FIELDS = {
        "scale_median": ("scale_trajectory", "median"),
        "scale_wander": ("scale_trajectory", "wander_ratio"),
        "scale_log_std": ("scale_trajectory", "log_std"),
        "scale_f2f_log_mad": ("scale_trajectory", "frame_to_frame_log_mad"),
        "near_far_wander": ("near_far_trajectory", "wander_ratio"),
        "local_stability_dlog": ("local_surface_stability", "median_dlog"),
        "boundary_jitter_px": ("boundary_jitter", "median_px"),
        "coverage_median": ("coverage", "median"),
        "coverage_min": ("coverage", "min"),
    }
    payload = {"stage": "S5", "clips": clips, "flow": flow, "arms": {}}
    for a in arms:
        payload["arms"][a] = {k: per_arm(raw, a, p) for k, p in FIELDS.items()}
        payload["arms"][a]["partition"] = {
            clip: r.get("partition") for clip, r in raw["arms"][a]["clips"].items()
            if r.get("status") == "ok"}
    common.write_json(os.path.join(common.RESULTS, "S5_results.json"), payload,
                      overwrite=args.overwrite)

    def med(a, k):
        v = list(payload["arms"][a][k].values())
        return float(np.median(v)) if v else float("nan")

    def worst(a, k, big_is_bad=True):
        d = payload["arms"][a][k]
        if not d:
            return "-", float("nan")
        c = max(d, key=lambda x: d[x]) if big_is_bad else min(d, key=lambda x: d[x])
        return c, d[c]

    L = []
    A = L.append
    A("# S5 — independent-frame temporal stability")
    A("")
    A("**Stage:** S5. Runs on the SAME 288-frame products S3 scored; nothing was")
    A("re-inferred.")
    A("")
    A("Every frame was inferred INDEPENDENTLY — one image in, one prediction out, no")
    A("neighbouring image, no temporal state, no Week-3 geometry input. The sequence is")
    A("used only AFTER inference, to ask what a strictly per-frame estimator does to a")
    A("moving scene.")
    A("")
    A("**SEA-RAFT is used only for evaluation correspondence.** Comparing frame t and")
    A("frame t+1 at the same PIXEL measures scene motion, not estimator instability, so")
    A("flow maps pixels to the same scene point and the comparison happens there. The flow")
    A("never reaches a depth model. It is computed once per clip and shared by every arm,")
    A("so the temporal comparison cannot depend on which model is being scored.")
    A("")
    if flow:
        A("### Correspondence quality")
        A("")
        A(md_table([[c, str(v["n_pairs"]), f"{v['median_valid_fraction']:.3f}",
                     f"{v['median_flow_px']:.2f}"] for c, v in flow["clips"].items()],
                   ["clip", "pairs", "median FB-consistent fraction",
                    "median flow (eval-grid px)"]))
        A("")
        A("Forward-backward consistency uses the published Sundaram/Brox/Keuper constants")
        A("(alpha 0.01, beta 0.5), not re-tuned — the same yardstick Week 2 applied to every")
        A("backend. Pixels that fail it are occlusions and independently moving objects, and")
        A("they are partitioned out rather than counted as geometric instability.")
        A("")
    A("## The physical implication, stated before the numbers")
    A("")
    A("```text")
    A("If   d'_t = s_t d_t")
    A("then absorbing it under ONE shared clip-level physical coefficient would require")
    A("     beta'_t = beta / s_t")
    A("i.e. water properties that change with the estimator.")
    A("```")
    A("")
    A("So frame-varying scale drift is a physical-model inconsistency **even when every")
    A("individual frame looks geometrically fine after oracle alignment**. That is why S5")
    A("reports the trajectory rather than the average scale.")
    A("")
    A("## Headline")
    A("")
    rows = []
    for a in arms:
        rows.append([a,
                     f"{med(a, 'scale_median'):.4f}",
                     f"{med(a, 'scale_wander'):.3f}",
                     f"{med(a, 'scale_f2f_log_mad'):.4f}",
                     f"{med(a, 'near_far_wander'):.2f}",
                     f"{med(a, 'local_stability_dlog'):.4f}",
                     f"{med(a, 'boundary_jitter_px'):.2f}",
                     f"{med(a, 'coverage_median'):.3f}"])
    A(md_table(rows, ["arm", "median s", "scale wander", "frame-to-frame log MAD",
                      "near/far wander", "local instability dlog", "boundary jitter px",
                      "coverage"]))
    A("")
    A("`scale wander` is max/min of the per-frame scale within a clip; 1.000 would mean one")
    A("clip-level scale describes every frame. `local instability` is |delta log range| at")
    A("CORRESPONDING SCENE POINTS after removing the pairwise global scalar — what is left")
    A("cannot be scene motion and cannot be a global gauge.")
    A("")
    A("## Scale wander by clip")
    A("")
    A(md_table([[a] + [f"{payload['arms'][a]['scale_wander'].get(c, float('nan')):.3f}"
                       for c in clips] for a in arms], ["arm"] + clips))
    A("")
    A("## Local instability by clip (|delta log range| at corresponding scene points)")
    A("")
    A(md_table([[a] + [f"{payload['arms'][a]['local_stability_dlog'].get(c, float('nan')):.4f}"
                       for c in clips] for a in arms], ["arm"] + clips))
    A("")
    A("## The frozen epistemic partition")
    A("")
    A("`wreck_03` carries a dynamic diver, and agreement with the Week-3 reference on a")
    A("moving object is **not** ground truth — a multi-view reference is least trustworthy")
    A("exactly where the scene moved. Week 3 also found MapAnything's dynamic failure on")
    A("`wreck_03` to be view-count-independent, so shortening the window is not a")
    A("workaround. Regions are therefore partitioned and reported separately, and")
    A("dynamic-region agreement is never used as a quality claim.")
    A("")
    for key, title in (("static_anchored", "static, flow-consistent, reference has support"),
                       ("static_reference_uncertain", "static, flow-consistent, reference support thin"),
                       ("dynamic", "flow-inconsistent: occlusion or independent motion")):
        A(f"**{key}** — {title}")
        A("")
        rr = []
        for a in arms:
            row = [a]
            for c in clips:
                p = (payload["arms"][a]["partition"].get(c) or {}).get(key, {})
                v = p.get("median_abs_dlog", float("nan"))
                row.append(f"{v:.4f}" if np.isfinite(v) else "-")
            rr.append(row)
        A(md_table(rr, ["arm"] + clips))
        A("")
    A("## Worst clip per arm")
    A("")
    rr = []
    for a in arms:
        cw, vw = worst(a, "scale_wander")
        cl, vl = worst(a, "local_stability_dlog")
        cc, vc = worst(a, "coverage_min", big_is_bad=False)
        rr.append([a, f"{cw} ({vw:.3f})", f"{cl} ({vl:.4f})", f"{cc} ({vc:.3f})"])
    A(md_table(rr, ["arm", "worst scale wander", "worst local instability",
                    "worst coverage"]))
    A("")
    A("## Findings")
    A("")
    A("_(written against the numbers above)_")

    out_md = os.path.join(common.RESULTS, "S5_TEMPORAL.md")
    if os.path.exists(out_md) and not args.overwrite:
        raise SystemExit(f"refusing to overwrite {out_md!r} (pass --overwrite)")
    with open(out_md, "w") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"[S5-report] -> {os.path.relpath(out_md, REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
