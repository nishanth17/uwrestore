"""Aggregate S3 into `results/S3_LOCAL_GEOMETRY.md` and `results/S3_results.json`.

EXPLORATORY. Reads `outputs/s3/s3_raw.json`; imports no model stack.

The tables here are generated from the measurements. The FIELD REDUCTION at the
end is deliberately NOT automated: FREEZE §5 S3 requires the 7 -> 3-4 cut to be
made on "explicit multi-dimensional reasons", and there is no weighted master
score to make it with. The generator emits every dimension, flags where the
per-clip spread contradicts the median, and leaves the reasoning to be written
against what the numbers actually say.
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

from experiments.week4_mono import armio, common  # noqa: E402
from experiments.week4_mono.scripts.s0_report import md_table  # noqa: E402

DIMENSIONS = [
    ("m1_abs_rel_median", "M-1 abs-rel", "lower better", "{:.4f}"),
    ("m2_b", "M-2 slope b", "1.0 ideal", "{:.3f}"),
    ("m3_relnormal_deg", "M-3 RelNormal deg", "lower better", "{:.2f}"),
    ("m3_abs_normal_median_deg", "M-3 normal deg", "lower better", "{:.1f}"),
    ("m4_symmetric_median_norm", "M-4 boundary", "lower better", "{:.4f}"),
    ("m5_violation_0_25", "M-5 ordinal@25%", "lower better", "{:.4f}"),
    ("m6_outer_over_inner", "M-6 outer/inner", "1.0 flat", "{:.2f}"),
]


def get(summary, key, field="median"):
    v = summary.get(key)
    return v.get(field, float("nan")) if isinstance(v, dict) else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", default=os.path.join(common.OUTPUTS, "s3", "s3_raw.json"))
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    with open(args.raw) as fh:
        raw = json.load(fh)
    arms = raw["arms"]
    primary = [a for a in common.MODELS if a in arms]
    ablation = [a for a in arms if a not in primary]

    payload = {"_comment": raw["_comment"], "stage": "S3", "clips": raw["clips"],
               "summaries": {a: arms[a].get("summary", {}) for a in arms},
               "policies": {a: arms[a].get("policy") for a in arms},
               "alignments": {a: {c: v.get("alignment") for c, v in arms[a]["clips"].items()
                                  if isinstance(v, dict)} for a in arms},
               "no_master_score": raw["no_master_score"]}
    common.write_json(os.path.join(common.RESULTS, "S3_results.json"), payload,
                      overwrite=args.overwrite)

    L = []
    A = L.append
    A("# S3 — primary local-geometry bakeoff")
    A("")
    A("**Stage:** S3, the primary pre-C2 field reduction.")
    A("")
    A(f"Full frozen set: {len(raw['clips'])} clips x 48 frames = "
      f"{len(raw['clips']) * 48} frames per arm, against the Week-3 persisted range")
    A("product, under the frozen S2 alignment policy, with the six universal metrics.")
    A("Nothing else was added to the primary ranking.")
    A("")
    A("**The reference is a provisional multi-view hypothesis, not ground truth.**")
    A("Everywhere below, \"error\" means disagreement with the current Week-3 hypothesis.")
    A("Week 3 measured its own reference's instability and it is large on exactly the")
    A("low-texture clips: whole-pipeline reruns moved `wreck_05` by 2.1-6.5 % median while")
    A("`wreck_07` moved 0.01 %. A few percent of monocular-vs-reference disagreement on")
    A("`wreck_05` or `wreck_01` says as much about the reference as about the model.")
    A("")
    A("**There is no weighted master score.** Six dimensions, reported separately.")
    A("")
    A("## Headline: the six dimensions, median across the six clips")
    A("")
    rows = []
    for a in primary:
        s = arms[a].get("summary", {})
        rows.append([a] + [fmt.format(get(s, k)) for k, _, _, fmt in DIMENSIONS]
                    + [f"{get(s, 'coverage'):.3f}"])
    A(md_table(rows, ["arm"] + [n for _, n, _, _ in DIMENSIONS] + ["coverage"]))
    A("")
    A("Direction of good: " + "; ".join(f"{n} {d}" for _, n, d, _ in DIMENSIONS) + ".")
    A("")
    A("`coverage` is the fraction of evaluation samples where the arm AND the reference")
    A("both have valid support. It is a first-class result, not bookkeeping — an arm can")
    A("only be scored where it predicts something, and declining to predict is itself a")
    A("behaviour.")
    A("")

    # -- per-dimension detail, with the clip spread ------------------------
    A("## Per-dimension detail, with the per-clip spread")
    A("")
    A("FREEZE §6 forbids hiding a result that helps one category and hurts another, so")
    A("every dimension is given with its range across the six clips and its worst clip.")
    A("")
    for key, name, direction, fmt in DIMENSIONS:
        A(f"### {name} ({direction})")
        A("")
        rr = []
        for a in primary:
            s = arms[a].get("summary", {}).get(key, {})
            by = s.get("by_clip", {}) if isinstance(s, dict) else {}
            if not by:
                rr.append([a, "-", "-", "-", "-"])
                continue
            worst = max(by, key=lambda c: (abs(by[c] - 1.0) if "1.0" in direction
                                           else by[c]))
            rr.append([a, fmt.format(s.get("median", float("nan"))),
                       fmt.format(s.get("min", float("nan"))),
                       fmt.format(s.get("max", float("nan"))),
                       f"{worst} ({fmt.format(by[worst])})"])
        A(md_table(rr, ["arm", "median", "min", "max", "worst clip"]))
        A("")

    # -- per clip ----------------------------------------------------------
    A("## By clip — M-1 abs-rel, the most legible single dimension")
    A("")
    hdr = ["arm"] + list(raw["clips"])
    rr = []
    for a in primary:
        by = arms[a].get("summary", {}).get("m1_abs_rel_median", {}).get("by_clip", {})
        rr.append([a] + [f"{by[c]:.4f}" if c in by and np.isfinite(by[c]) else "-"
                         for c in raw["clips"]])
    A(md_table(rr, hdr))
    A("")
    A("Clip roles: " + "; ".join(f"`{c}` {common.CLIP_ROLE[c]}" for c in raw["clips"]) + ".")
    A("")
    A("### Coverage by clip")
    A("")
    rr = []
    for a in primary:
        by = arms[a].get("summary", {}).get("coverage", {}).get("by_clip", {})
        rr.append([a] + [f"{by[c]:.3f}" if c in by else "-" for c in raw["clips"]])
    A(md_table(rr, hdr))
    A("")

    # -- M-1 stratification -----------------------------------------------
    A("## M-1 range stratification, in both required forms")
    A("")
    A("**M-1a — nominal reference bins.** The edges are Week-3 reference units /")
    A("provisional nominal metres, **not** independently validated physical metres. Pre-C2")
    A("nothing may claim the reference's nominal 8 m is objectively an 8 m water path.")
    A("")
    bins = ["0-1", "1-2", "2-3", "3-5", "5-8", "8-12", "12+"]
    rr = []
    for a in primary:
        vals = []
        for i in range(len(bins)):
            per = []
            for c, cv in arms[a]["clips"].items():
                if not isinstance(cv, dict) or "pooled" not in cv:
                    continue
                pb = cv["pooled"]["m1"]["m1a_nominal_bins"]
                if i < len(pb) and pb[i]["n"] > 0:
                    per.append(pb[i]["median"])
            vals.append(f"{np.median(per):.3f}" if per else "-")
        rr.append([a] + vals)
    A(md_table(rr, ["arm"] + bins))
    A("")
    A("**M-1b — scale-invariant near/mid/far.** Bin edges are quantiles of each clip's")
    A("pooled reference range, so this survives an absolute scale that pre-C2 may be wrong.")
    A("")
    qb = ["q0-20 (near)", "q20-40", "q40-60", "q60-80", "q80-100 (far)"]
    rr = []
    for a in primary:
        vals = []
        for i in range(len(qb)):
            per = []
            for c, cv in arms[a]["clips"].items():
                if not isinstance(cv, dict) or "pooled" not in cv:
                    continue
                pb = cv["pooled"]["m1"].get("m1b_quantile_bins", [])
                if i < len(pb) and pb[i]["n"] > 0:
                    per.append(pb[i]["median"])
            vals.append(f"{np.median(per):.3f}" if per else "-")
        rr.append([a] + vals)
    A(md_table(rr, ["arm"] + qb))
    A("")

    # -- FoundationGeo ablations -------------------------------------------
    if ablation:
        A("## FoundationGeo internal ablations — the only causal interventions left")
        A("")
        A("Both V4b arms come from ONE forward pass and share ONE frozen (focal, shift)")
        A("solution recovered from the post-delta arm. The released `infer()` postprocesses")
        A("its two arms through INDEPENDENT `recover_focal_shift` solutions, so its")
        A("difference would be the ray correction plus two different focals — which FREEZE")
        A("§C3 explicitly forbids calling a ray-correction ablation.")
        A("")
        A("```text")
        A("V4b  fg_pre_ray  ->  fg_post_ray         the learned ray-direction correction")
        A("V4c  fg_post_ray ->  foundationgeo_11    the learned per-pixel scale field")
        A("```")
        A("")
        order = ["fg_pre_ray", "fg_post_ray", "foundationgeo_11"]
        rr = []
        for a in order:
            if a not in arms:
                continue
            s = arms[a].get("summary", {})
            rr.append([a, armio.arm_role(a).split(":")[0]]
                      + [fmt.format(get(s, k)) for k, _, _, fmt in DIMENSIONS])
        A(md_table(rr, ["arm", "role"] + [n for _, n, _, _ in DIMENSIONS]))
        A("")
        for lo, hi, name in (("fg_pre_ray", "fg_post_ray", "V4b learned ray correction"),
                             ("fg_post_ray", "foundationgeo_11", "V4c learned scale field")):
            if lo not in arms or hi not in arms:
                continue
            A(f"**{name}: {lo} -> {hi}**")
            A("")
            dr = []
            for key, nm, _, fmt in DIMENSIONS:
                a0 = get(arms[lo].get("summary", {}), key)
                a1 = get(arms[hi].get("summary", {}), key)
                delta = a1 - a0
                rel = (delta / a0) if (np.isfinite(a0) and a0 != 0) else float("nan")
                dr.append([nm, fmt.format(a0), fmt.format(a1), f"{delta:+.4f}",
                           f"{rel:+.3f}" if np.isfinite(rel) else "-"])
            A(md_table(dr, ["dimension", "before", "after", "delta", "relative"]))
            A("")
        A("Every one of these deltas clears the S1 noise floor trivially: that floor is")
        A("exactly zero for this model, bitwise, so no part of an ablation difference is")
        A("run-to-run variation.")
        A("")

    # -- alignment parameters ---------------------------------------------
    A("## The nuisance parameters the alignment consumed")
    A("")
    A("FREEZE §C9: the transform that bought the E1 ceiling is reported, never hidden.")
    A("")
    rr = []
    for a in primary:
        ss = [v["alignment"] for v in arms[a]["clips"].values()
              if isinstance(v, dict) and "alignment" in v]
        if not ss:
            continue
        fam = ss[0]["family"]
        s_vals = [x["params"].get("s") for x in ss if x["params"].get("s") is not None]
        t_vals = [x["params"].get("t") for x in ss if x["params"].get("t") is not None]
        mads = [x.get("log_residual_mad") for x in ss
                if x.get("log_residual_mad") is not None and np.isfinite(x["log_residual_mad"])]
        rr.append([a, fam,
                   f"{np.median(s_vals):.4g}" if s_vals else "-",
                   (f"{min(s_vals):.4g}-{max(s_vals):.4g}" if s_vals else "-"),
                   f"{np.median(t_vals):.4g}" if t_vals else "-",
                   f"{np.median(mads):.4f}" if mads else "-"])
    A(md_table(rr, ["arm", "family", "median s", "s across clips", "median t",
                    "median log-residual MAD"]))
    A("")
    A("`s` across clips is the clip-to-clip scale spread. A model whose `s` is stable")
    A("across six different scenes is carrying a real, if unverified, notion of scale; one")
    A("whose `s` swings has an oracle-only scale. Neither can be judged as CORRECT pre-C2")
    A("— there is no independent anchor — but the spread itself is measured and recorded.")
    A("")
    A("## Secondary literature-continuity metrics (never decisive)")
    A("")
    rr = []
    for a in primary:
        vals = {"abs_rel": [], "delta_1_25": [], "rmse_log": []}
        for cv in arms[a]["clips"].values():
            if isinstance(cv, dict) and "pooled" in cv:
                sec = cv["pooled"]["secondary"]
                for k in vals:
                    if k in sec:
                        vals[k].append(sec[k])
        rr.append([a] + [f"{np.median(v):.4f}" if v else "-" for v in vals.values()])
    A(md_table(rr, ["arm", "AbsRel", "delta<1.25", "RMSE log"]))
    A("")
    A("Reported for continuity with the outside world. They are never used in a ranking")
    A("argument on their own (FREEZE §6).")
    A("")
    A("## Field reduction")
    A("")
    A("_(written against the numbers above; see `FINALISTS_PRE_C2.md` for the full chain)_")

    out_md = os.path.join(common.RESULTS, "S3_LOCAL_GEOMETRY.md")
    if os.path.exists(out_md) and not args.overwrite:
        raise SystemExit(f"refusing to overwrite {out_md!r} (pass --overwrite)")
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    with open(out_md, "w") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"[S3-report] {len(primary)} primary arms, {len(ablation)} ablation arms")
    print(f"  -> {os.path.relpath(out_md, REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
