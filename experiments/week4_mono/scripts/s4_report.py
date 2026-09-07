"""Aggregate S4 into `results/S4_APPEARANCE.md` and `results/S4_results.json`."""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week4_mono import common  # noqa: E402
from experiments.week4_mono.scripts.s0_report import md_table  # noqa: E402


def collect(raw, model, field_path):
    """Median across clips of one number, per perturbation."""
    out = {}
    for clip, crec in raw["models"][model]["clips"].items():
        for pname, r in crec["perturbations"].items():
            if r.get("status") != "ok":
                continue
            cur = r
            for k in field_path:
                cur = cur.get(k) if isinstance(cur, dict) else None
                if cur is None:
                    break
            if isinstance(cur, (int, float)) and np.isfinite(cur):
                out.setdefault(pname, []).append(float(cur))
    return {k: float(np.median(v)) for k, v in out.items()}


def worst_clip(raw, model, pname, field_path):
    best, bc = float("-inf"), None
    for clip, crec in raw["models"][model]["clips"].items():
        r = crec["perturbations"].get(pname, {})
        if r.get("status") != "ok":
            continue
        cur = r
        for k in field_path:
            cur = cur.get(k) if isinstance(cur, dict) else None
            if cur is None:
                break
        if isinstance(cur, (int, float)) and np.isfinite(cur) and cur > best:
            best, bc = float(cur), clip
    return bc, best


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", default=os.path.join(common.OUTPUTS, "s4", "s4_raw.json"))
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    with open(args.raw) as fh:
        raw = json.load(fh)
    models = [m for m in common.MODELS if m in raw["models"]]
    perts = [p["name"] for p in raw["perturbations"]]

    BIAS = ("constant_global_scale_bias", "median_sigma")
    DRIFT = ("frame_varying_scale_drift", "wander_ratio")
    F2F = ("frame_varying_scale_drift", "frame_to_frame_log_mad")
    LOCAL = ("local_range_deformation", "median_abs_dlog")
    LOCAL95 = ("local_range_deformation", "p95_abs_dlog")
    LOCALR = ("local_range_deformation_physical", "median_abs_dlog")
    LOCALR95 = ("local_range_deformation_physical", "p95_abs_dlog")
    COVB = ("coverage", "baseline_median")
    COVP = ("coverage", "perturbed_median")

    payload = {"stage": "S4", "perturbations": raw["perturbations"],
               "window": raw["window"], "models": {}}
    for m in models:
        payload["models"][m] = {
            "constant_global_scale_bias": collect(raw, m, BIAS),
            "frame_varying_scale_drift": collect(raw, m, DRIFT),
            "frame_to_frame_log_mad": collect(raw, m, F2F),
            "local_range_deformation": collect(raw, m, LOCAL),
            "local_range_deformation_p95": collect(raw, m, LOCAL95),
            "local_range_deformation_physical": collect(raw, m, LOCALR),
            "local_range_deformation_physical_p95": collect(raw, m, LOCALR95),
            "coverage_baseline": collect(raw, m, COVB),
            "coverage_perturbed": collect(raw, m, COVP),
            "boundary_jitter_px": collect(raw, m, ("boundary_jitter_px",)),
        }
    common.write_json(os.path.join(common.RESULTS, "S4_results.json"), payload,
                      overwrite=args.overwrite)

    L = []
    A = L.append
    A("# S4 — appearance invariance")
    A("")
    A("**Stage:** S4. Only S3 survivors run.")
    A("")
    A("Same underlying image geometry, different appearance, measure the geometry")
    A("response. Every perturbation is a per-pixel intensity operation applied in LINEAR")
    A("light and re-encoded to 8-bit sRGB; nothing is warped, resampled or cropped, so the")
    A("scene geometry behind the image is identical by construction.")
    A("")
    A(f"Frames: a CONTIGUOUS window of {raw['window']} frames from each clip's middle. S4 has")
    A("to be able to see frame-to-frame scale drift, and a strided sample would destroy")
    A("exactly that structure.")
    A("")
    A("**Each perturbed field is compared against the SAME model's baseline field**, not")
    A("against the Week-3 reference. That isolates the response to appearance from the")
    A("model's standing disagreement with the reference, and means the answer does not")
    A("inherit the reference's own uncertainty.")
    A("")
    A("## The frozen perturbations")
    A("")
    A(md_table([[p["name"], p["kind"], p["probes"]] for p in raw["perturbations"]],
               ["perturbation", "kind", "what it probes"]))
    A("")
    A("The last two are a matched pair. `cue_conflict_inverted_veil` builds a veiling")
    A("light whose strength runs OPPOSITE to the reference depth, so the image says \"far\"")
    A("exactly where the geometry says \"near\"; `veil_depth_consistent` applies the same")
    A("veil magnitude in the physically correct direction. The reference is used to BUILD")
    A("THE STIMULUS and never reaches the model, which still sees one ordinary 8-bit image.")
    A("")
    A("## The three-way decomposition")
    A("")
    A("```text")
    A("CONSTANT GLOBAL SCALE BIAS      d' = s d, s fixed over the clip")
    A("    Potentially a BENIGN GAUGE: refit beta' = beta/s once. Week 3 verified that")
    A("    identity numerically to floating-point precision. Do NOT judge a model")
    A("    harshly for a fixed scale gauge.")
    A("")
    A("FRAME-VARYING GLOBAL SCALE DRIFT   d'_t = s_t d_t")
    A("    A FAILURE under one shared clip-level physical model: absorbing it would")
    A("    demand beta'_t = beta/s_t, i.e. water properties that change with the estimator.")
    A("")
    A("LOCAL RANGE DEFORMATION")
    A("    Spatially varying within the image. NOT absorbable by any global physical")
    A("    parameter transformation. The primary geometric failure.")
    A("```")
    A("")

    A("### 1. Constant global scale bias — sigma (1.000 = no change)")
    A("")
    A(md_table([[p] + [f"{payload['models'][m]['constant_global_scale_bias'].get(p, float('nan')):.4f}"
                       for m in models] for p in perts],
               ["perturbation"] + models))
    A("")
    A("### 2. Frame-varying scale drift — wander ratio (1.000 = the bias is constant)")
    A("")
    A(md_table([[p] + [f"{payload['models'][m]['frame_varying_scale_drift'].get(p, float('nan')):.4f}"
                       for m in models] for p in perts],
               ["perturbation"] + models))
    A("")
    A("Wander is max/min of the per-frame sigma within the window. This is the row that")
    A("matters more than row 1: a constant bias is a gauge, a wandering one is not.")
    A("")
    A("### 3. Local range deformation — median |delta log range| after removing sigma_t")
    A("")
    A(md_table([[p] + [f"{payload['models'][m]['local_range_deformation'].get(p, float('nan')):.4f}"
                       for m in models] for p in perts],
               ["perturbation"] + models))
    A("")
    A("This is the number no argument can remove. `0.010` is about a 1 % local range")
    A("deformation; Week 3's restoration sensitivity budget is 31 % at 1 m, 12 % at 3 m and")
    A("8.5 % at 8 m, so these can be read against that budget under the current provisional")
    A("scale hypothesis — but not as an objective physical-metre acceptance test, which")
    A("waits for C2.")
    A("")
    A("### 3b. Local range deformation — p95, the tail rather than the median")
    A("")
    A(md_table([[p] + [f"{payload['models'][m]['local_range_deformation_p95'].get(p, float('nan')):.4f}"
                       for m in models] for p in perts],
               ["perturbation"] + models))
    A("")
    A("### 3c. Local range deformation in PHYSICAL RANGE — the cross-model row")
    A("")
    A("Rows 3 and 3b are in each model's OWN NATIVE quantity. That is the right object")
    A("for asking \"did appearance move this model\", but it is NOT comparable across")
    A("models. For a scale-family arm native is proportional to range, so a native log")
    A("ratio IS a range log ratio and this table repeats row 3 exactly. For an")
    A("AFFINE-family arm range is `s*d + t`, and the two differ by")
    A("")
    A("```text")
    A("    L_phys  ~=  L_native * (1 - t/r)")
    A("```")
    A("")
    A("`da3mono_large` is the only survivor with an affine family, and its fitted shift")
    A("is large (t = 1.78 to 11.56 m against median scene ranges of 6.4 to 22.5 m), so")
    A("reading its native numbers beside three scale-family arms overstates its response")
    A("by roughly a factor of two. The gauge here is fitted on the BASELINE arm alone and")
    A("then held fixed, so no oracle sees a perturbed field: this is a unit conversion,")
    A("not an alignment that could absorb the effect being measured.")
    A("")
    A(md_table([[p] + [f"{payload['models'][m]['local_range_deformation_physical'].get(p, float('nan')):.4f}"
                       for m in models] for p in perts],
               ["perturbation"] + models))
    A("")
    A("p95, physical range:")
    A("")
    A(md_table([[p] + [f"{payload['models'][m]['local_range_deformation_physical_p95'].get(p, float('nan')):.4f}"
                       for m in models] for p in perts],
               ["perturbation"] + models))
    A("")
    A("That the scale-family columns reproduce row 3 to four decimals is the check that")
    A("this conversion is implemented correctly.")
    A("")
    A("### 4. Validity — does the perturbation make the model stop predicting?")
    A("")
    rr = []
    for p in perts:
        row = [p]
        for m in models:
            b = payload["models"][m]["coverage_baseline"].get(p, float("nan"))
            q = payload["models"][m]["coverage_perturbed"].get(p, float("nan"))
            row.append(f"{b:.3f}->{q:.3f}")
        rr.append(row)
    A(md_table(rr, ["perturbation"] + models))
    A("")
    A("### 5. Boundary jitter under perturbation (evaluation-grid pixels)")
    A("")
    A(md_table([[p] + [f"{payload['models'][m]['boundary_jitter_px'].get(p, float('nan')):.2f}"
                       for m in models] for p in perts],
               ["perturbation"] + models))
    A("")
    A("## Worst clip per model, on the dimension that matters most")
    A("")
    rr = []
    for m in models:
        for p in perts:
            c, v = worst_clip(raw, m, p, LOCAL)
            if c:
                rr.append([m, p, c, f"{v:.4f}"])
    rr.sort(key=lambda r: -float(r[3]))
    A(md_table(rr[:15], ["model", "perturbation", "worst clip", "local deformation"]))
    A("")
    A("## Findings")
    A("")
    A("_(written against the numbers above)_")

    out_md = os.path.join(common.RESULTS, "S4_APPEARANCE.md")
    if os.path.exists(out_md) and not args.overwrite:
        raise SystemExit(f"refusing to overwrite {out_md!r} (pass --overwrite)")
    with open(out_md, "w") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"[S4-report] -> {os.path.relpath(out_md, REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
