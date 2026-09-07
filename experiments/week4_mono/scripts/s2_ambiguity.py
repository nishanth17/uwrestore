"""S2 — native ambiguity measurement, and the frozen alignment policy.

EXPLORATORY. Runs in `.venv-eval`; imports no model stack, only the persisted
prediction products.

WHAT S2 DECIDES (`MONO_DEPTH_FREEZE.md` §5 S2). One common evaluation POLICY,
not one universal transform. For each candidate it establishes, before any
accuracy testing:

    1. the documented native output representation
    2. the documented legal ambiguity / gauge, if any
    3. the E1 oracle transform permitted for THAT representation
    4. the transform-fitting scope
    5. the simpler subgroup(s) worth testing empirically

and it settles the two questions S0 deliberately left open, by measurement:

    * is `da3mono_large`'s native field z-depth or range?
    * what camera lifts a cameraless scalar model into a range field?

THE CONVENTION TEST. Both open questions have the same shape: a model emits a
scalar field of unstated convention, and the two candidate conventions differ by
this camera's secant factor, which spans about 1.00 at the principal point to
1.35 at the corners. That is an enormous signal. So each cameraless model is
fitted TWICE — once treating its field as z-depth (compared against the
reference converted to z-depth through the reference's own K) and once treating
it as range — and whichever hypothesis leaves the smaller residual is the one
the evidence supports. Neither is assumed.

WHAT IS DELIBERATELY NOT INFERRED. Wat3R's native ambiguity is NOT taken from
its released evaluation code's alignment (FREEZE §3.3). It is measured here like
everything else: fit the subgroups, report what each buys.

AFTER S2 the policy — family per representation, fitting scope, and the
conventions resolved here — is FROZEN for S3 to S6 and written to
`results/S2_alignment_policy.json`.

    experiments/week4_mono/.venv-eval/bin/python \\
        -m experiments.week4_mono.scripts.s2_ambiguity --overwrite
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week3_geometry import geometry as g3  # noqa: E402
from experiments.week4_mono import alignment, common, evalgrid, monoio  # noqa: E402

#: Samples drawn per frame for the pooled clip-level fits. 4 000 x 48 frames is
#: ~192 000 pooled samples per clip, which pins a two-parameter fit far more
#: tightly than anything downstream can resolve, while keeping the whole stage
#: inside a bounded memory footprint (CLAUDE.md invariant 9).
SAMPLES_PER_FRAME = 4000

#: Which E1 families are LEGAL for each native representation, and which simpler
#: subgroup is worth testing empirically. This table IS the policy skeleton;
#: S2 fills in the conventions and the measured evidence.
LEGAL_FAMILIES = {
    "depth_along_ray_metric": ["none", "scale"],
    "pointmap_metric": ["none", "scale"],
    "pointmap": ["none", "scale", "affine_depth"],
    "depth_relative": ["affine_depth", "scale"],
    "disparity_relative": ["affine_disparity"],
}

#: Models whose scalar field has an UNSTATED z-vs-range convention, to be
#: settled by measurement here rather than by reading a paper.
CONVENTION_UNRESOLVED = {"da3mono_large", "dav2_small"}


def secant(K_eval: np.ndarray, eval_hw) -> np.ndarray:
    """(H,W) factor with `range = z * factor` for the shared evaluation camera."""
    h, w = eval_hw
    return g3.ray_length_factor(np.asarray(K_eval, dtype=np.float64), h, w)


def gather_clip(model: str, clip: str, root: str, rng_seed: int = 0) -> dict:
    """Pooled paired samples for one model+clip, plus the per-frame index.

    Returns arrays that are all the same length, with a `frame` column, so a
    clip-level fit and a per-frame trajectory come from IDENTICAL samples.
    """
    reader = monoio.MonoReader(root, model, clip)
    ref = evalgrid.ReferenceClip(clip)
    source_hw = common.clip_source_hw(clip)
    gmap = evalgrid.load_model_gridmap(model, source_hw)
    native_kind = reader.native_kind
    is_vector = len(reader.meta["frames"][0]["native_shape"]) == 3

    rng = np.random.default_rng(rng_seed)
    cols = {k: [] for k in ("frame", "pred_native", "pred_range",
                            "ref_range", "ref_z", "sec", "radius")}
    per_frame_cov = []
    for fi in reader.frame_indices:
        if fi not in ref.reader.by_index:
            continue
        r_ref, ok_ref = ref.load(fi)
        K_eval = ref.K_eval(fi)
        sec = secant(K_eval, ref.eval_hw)

        v_pred = np.asarray(reader.load_valid(fi))
        # The model's NATIVE scalar, sampled onto the shared grid. For a point
        # map the scalar of interest is its norm, which is the canonical range.
        nat = reader.load_native(fi)
        if is_vector:
            nat_s = np.linalg.norm(np.asarray(nat, dtype=np.float64), axis=-1)
        else:
            nat_s = np.asarray(nat, dtype=np.float64)
        nv, ok_n = evalgrid.sample(nat_s, v_pred, ref.uv, gmap)

        rng_field = reader.load_range(fi)
        if rng_field is not None:
            rv, ok_r = evalgrid.sample(np.asarray(rng_field), v_pred, ref.uv, gmap)
        else:
            rv, ok_r = np.full_like(nv, np.nan), ok_n

        h, w = ref.eval_hw
        ok = ok_ref.ravel() & ok_n & np.isfinite(nv)
        per_frame_cov.append({"frame": int(fi),
                              "coverage_vs_reference": float(ok.mean()),
                              "reference_coverage": float(ok_ref.mean())})
        idx = np.flatnonzero(ok)
        if idx.size == 0:
            continue
        take = idx if idx.size <= SAMPLES_PER_FRAME else rng.choice(
            idx, size=SAMPLES_PER_FRAME, replace=False)
        cols["frame"].append(np.full(take.size, fi, dtype=np.int64))
        cols["pred_native"].append(nv[take])
        cols["pred_range"].append(rv[take])
        cols["ref_range"].append(r_ref.ravel()[take])
        cols["ref_z"].append(r_ref.ravel()[take] / sec.ravel()[take])
        cols["sec"].append(sec.ravel()[take])
        cols["radius"].append(ref.radius.ravel()[take])

    out = {k: (np.concatenate(v) if v else np.zeros(0)) for k, v in cols.items()}
    out["native_kind"] = native_kind
    out["coverage"] = per_frame_cov
    out["gridmap"] = gmap.to_dict()
    out["reference_gridmap"] = ref.gmap.to_dict()
    return out


def _abs_rel(pred_range, ref_range) -> float:
    e = g3.relative_errors(pred_range, ref_range, 1.0)
    return float(np.nanmedian(np.abs(e)))


def convention_test(data: dict) -> dict:
    """Is the model's scalar field z-depth or range? Decide by residual, not by paper.

    Fits the model's legal family under each hypothesis, converts the aligned
    result to a RANGE field, and scores both against the reference range. The
    hypotheses differ by the secant factor, which on this camera spans 1.00-1.35,
    so a wrong choice is not subtle.
    """
    native = data["pred_native"]
    ref_r = data["ref_range"]
    ref_z = data["ref_z"]
    sec = data["sec"]
    kind = data["native_kind"]
    res = {}

    if kind == "disparity_relative":
        # DA V2's ambiguity is affine in DISPARITY, so BOTH sides go into
        # disparity before the fit; the inversion happens after.
        for hyp, ref_q, back in (("z_depth", alignment.to_disparity(ref_z), sec),
                                 ("range", alignment.to_disparity(ref_r), None)):
            a = alignment.fit_affine(native, ref_q, "affine_disparity")
            q = alignment.apply(a, native)
            d = alignment.to_range(q, "affine_disparity")
            rng_pred = d * back if back is not None else d
            res[hyp] = {"alignment": a.to_dict(),
                        "median_abs_rel_vs_reference_range": _abs_rel(rng_pred, ref_r)}
    else:
        for hyp, ref_side, back in (("z_depth", ref_z, sec), ("range", ref_r, None)):
            a = alignment.fit_affine(native, ref_side, "affine_depth")
            d = alignment.apply(a, native)
            d = alignment.to_range(d, "affine_depth")
            rng_pred = d * back if back is not None else d
            res[hyp] = {"alignment": a.to_dict(),
                        "median_abs_rel_vs_reference_range": _abs_rel(rng_pred, ref_r)}

    zz = res["z_depth"]["median_abs_rel_vs_reference_range"]
    rr = res["range"]["median_abs_rel_vs_reference_range"]
    if not (np.isfinite(zz) and np.isfinite(rr)):
        res["verdict"] = "UNDECIDED"
    elif zz < rr * 0.97:
        res["verdict"] = "z_depth"
    elif rr < zz * 0.97:
        res["verdict"] = "range"
    else:
        res["verdict"] = "INDISTINGUISHABLE"
    res["margin_ratio"] = float(max(zz, rr) / min(zz, rr)) if min(zz, rr) > 0 else float("nan")
    res["_note"] = ("The two hypotheses differ by this camera's secant factor "
                    "(~1.00 at the principal point to ~1.35 at the corners). A verdict "
                    "of INDISTINGUISHABLE would itself be informative: it would mean the "
                    "model's shape error is larger than a 35 % radial term.")
    return res


def family_comparison(data: dict, families: list[str], convention: str) -> dict:
    """Fit each legal family and report what the larger group actually buys.

    This is FREEZE C1's question answered with evidence: DA3 Mono's literature
    ambiguity is affine-in-depth, and S2 may discover the additive term is
    negligible ON THIS DOMAIN — but only from a measured residual gain.
    """
    native = data["pred_native"]
    ref_r = data["ref_range"]
    ref_side = data["ref_z"] if convention == "z_depth" else ref_r
    sec = data["sec"] if convention == "z_depth" else None
    out = {}
    for fam in families:
        if fam == "none":
            rng_pred = data["pred_range"] if np.isfinite(data["pred_range"]).any() else native
            a = alignment.Alignment("none", {}, int(np.isfinite(rng_pred).sum()),
                                    int(rng_pred.size), "clip")
        elif fam == "scale":
            a = alignment.fit_scale(native, ref_side)
            rng_pred = alignment.apply(a, native)
        elif fam == "affine_depth":
            a = alignment.fit_affine(native, ref_side, "affine_depth")
            rng_pred = alignment.to_range(alignment.apply(a, native), "affine_depth")
        elif fam == "affine_disparity":
            ref_q = alignment.to_disparity(ref_side)
            a = alignment.fit_affine(native, ref_q, "affine_disparity")
            rng_pred = alignment.to_range(alignment.apply(a, native), "affine_disparity")
        else:
            raise ValueError(fam)
        if sec is not None and fam != "none":
            rng_pred = rng_pred * sec
        rec = a.to_dict()
        rec["median_abs_rel"] = _abs_rel(rng_pred, ref_r)
        rec["log_residual_mad"] = a.log_residual_mad
        out[fam] = rec
    fitted = [f for f in families if f != "none" and np.isfinite(out[f]["median_abs_rel"])]
    if "scale" in fitted and "affine_depth" in fitted:
        s, af = out["scale"]["median_abs_rel"], out["affine_depth"]["median_abs_rel"]
        out["_subgroup_gain"] = {
            "scale_only_median_abs_rel": s,
            "affine_median_abs_rel": af,
            "relative_gain_from_shift": float((s - af) / s) if s > 0 else float("nan"),
            "meaning": ("fraction of the scale-only error removed by granting the additive "
                        "term. FREEZE C1: only measured evidence may earn an "
                        "'approximately scale-only' description."),
        }
    return out


def trajectories(data: dict, family: str, convention: str) -> dict:
    """PER-FRAME fits — a DRIFT DIAGNOSTIC ONLY, never fed back into a residual.

    FREEZE C7 makes the distinction load-bearing: a CONSTANT global scale bias
    is a benign gauge because the physical coefficients can be refit once
    (`beta' = beta/s`), whereas FRAME-VARYING scale drift would require
    `beta'_t = beta/s_t`, i.e. water properties that change with the estimator.
    So the trajectory is what S5 needs, and it is computed here so the frozen
    policy carries it.
    """
    frames = data["frame"]
    native = data["pred_native"]
    ref_side = data["ref_z"] if convention == "z_depth" else data["ref_range"]
    uniq = np.unique(frames)
    s_t, t_t, n_t = [], [], []
    for f in uniq:
        m = frames == f
        if m.sum() < 8:
            s_t.append(np.nan); t_t.append(np.nan); n_t.append(0)
            continue
        if family == "scale":
            a = alignment.fit_scale(native[m], ref_side[m], scope="frame")
            s_t.append(a.params["s"]); t_t.append(np.nan)
        elif family == "affine_depth":
            a = alignment.fit_affine(native[m], ref_side[m], "affine_depth", scope="frame")
            s_t.append(a.params["s"]); t_t.append(a.params["t"])
        elif family == "affine_disparity":
            a = alignment.fit_affine(native[m], alignment.to_disparity(ref_side[m]),
                                     "affine_disparity", scope="frame")
            s_t.append(a.params["s"]); t_t.append(a.params["t"])
        else:
            s_t.append(np.nan); t_t.append(np.nan)
        n_t.append(int(m.sum()))
    s = np.asarray(s_t, dtype=np.float64)
    t = np.asarray(t_t, dtype=np.float64)
    fin = np.isfinite(s) & (s > 0)
    out = {
        "frames": [int(x) for x in uniq],
        "scale_t": [None if not np.isfinite(x) else float(x) for x in s],
        "shift_t": [None if not np.isfinite(x) else float(x) for x in t],
        "n_samples_t": n_t,
    }
    if fin.sum() >= 2:
        ls = np.log(s[fin])
        out["scale_trajectory"] = {
            "median": float(np.exp(np.median(ls))),
            "log_std": float(np.std(ls)),
            "wander_ratio": float(np.exp(ls.max() - ls.min())),
            "frame_to_frame_log_mad": float(np.median(np.abs(np.diff(ls)))),
        }
    if np.isfinite(t).sum() >= 2:
        tv = t[np.isfinite(t)]
        out["shift_trajectory"] = {
            "median": float(np.median(tv)),
            "iqr": float(np.percentile(tv, 75) - np.percentile(tv, 25)),
            "range": float(tv.max() - tv.min()),
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="*", default=None)
    ap.add_argument("--clips", nargs="*", default=None)
    ap.add_argument("--root", default=os.path.join(common.OUTPUTS, "predictions"))
    ap.add_argument("--out", default=os.path.join(common.OUTPUTS, "s2", "s2_raw.json"))
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    models = args.models or [m for m in common.MODELS
                             if monoio.exists(args.root, m, common.CLIPS[0])]
    clips = args.clips or common.CLIPS

    result = {"models": {}, "samples_per_frame": SAMPLES_PER_FRAME}
    for model in models:
        rec = {"clips": {}}
        for clip in clips:
            if not monoio.exists(args.root, model, clip):
                rec["clips"][clip] = {"status": "missing"}
                continue
            data = gather_clip(model, clip, args.root)
            if data["pred_native"].size == 0:
                rec["clips"][clip] = {"status": "no_overlapping_valid_samples"}
                continue
            kind = data["native_kind"]
            rec["native_kind"] = kind
            entry = {"status": "ok",
                     "n_pooled_samples": int(data["pred_native"].size),
                     "coverage": data["coverage"],
                     "gridmap": data["gridmap"],
                     "reference_gridmap": data["reference_gridmap"]}
            if model in CONVENTION_UNRESOLVED:
                entry["convention_test"] = convention_test(data)
                conv = entry["convention_test"]["verdict"]
                conv = conv if conv in ("z_depth", "range") else "range"
            else:
                conv = "range"
            entry["convention_used"] = conv
            entry["families"] = family_comparison(data, LEGAL_FAMILIES[kind], conv)
            primary = ("affine_disparity" if kind == "disparity_relative"
                       else ("affine_depth" if kind == "depth_relative" else "scale"))
            entry["primary_family"] = primary
            entry["trajectories"] = trajectories(data, primary, conv)
            rec["clips"][clip] = entry
            cov = np.mean([c["coverage_vs_reference"] for c in data["coverage"]])
            print(f"[S2] {model:26s} {clip:15s} n={entry['n_pooled_samples']:7d} "
                  f"cov={cov:.3f} conv={conv:8s} "
                  f"primary_absrel={entry['families'][primary]['median_abs_rel']:.4f}")
        result["models"][model] = rec

    common.write_json(args.out, result, overwrite=args.overwrite)
    print(f"[S2] -> {os.path.relpath(args.out, REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
