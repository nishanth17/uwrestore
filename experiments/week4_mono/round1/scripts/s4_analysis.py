"""S4 step 3 — decompose each model's response to appearance into the three frozen parts.

EXPLORATORY. Runs in `.venv-eval`.

FREEZE §5 S4 requires every response to be decomposed into exactly three things,
because they have completely different consequences downstream:

    CONSTANT GLOBAL SCALE BIAS      d' = s d, s fixed over the clip
        Reported. Potentially a BENIGN GAUGE: the physical coefficients can be
        refit once as beta' = beta/s, and Week 3 verified that identity
        numerically to floating-point precision.

    FRAME-VARYING GLOBAL SCALE DRIFT   d'_t = s_t d_t
        A FAILURE under one shared clip-level physical model. Absorbing it would
        demand beta'_t = beta/s_t, i.e. water properties that change with the
        estimator.

    LOCAL RANGE DEFORMATION
        Spatially varying within the image. NOT absorbable by any global
        physical parameter transformation. The primary geometric failure.

    "Do not judge a model harshly for a fixed scale gauge. Do judge it if
     changing appearance makes its scale or shift pump over time, or deforms
     local range."

HOW THE DECOMPOSITION IS DONE. For each (model, clip, perturbation), the
perturbed field is compared DIRECTLY against the same model's baseline field on
the same frames — not against the Week-3 reference. That matters: it isolates
the model's response to appearance from the model's standing disagreement with
the reference, and it means the answer does not inherit the reference's own
uncertainty.

    per-frame sigma_t   the scalar that best maps baseline -> perturbed
      median(sigma_t)   the CONSTANT global scale bias
      wander(sigma_t)   the FRAME-VARYING drift the perturbation induced
    residual after removing sigma_t, per frame
                        the LOCAL RANGE DEFORMATION

The third is the one that cannot be argued away, so it is reported as a median
and a p95 of |delta log range|, in the units a restoration error budget speaks.

    experiments/week4_mono/.venv-eval/bin/python \\
        -m experiments.week4_mono.round1.scripts.s4_analysis --overwrite
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import sys

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week3_geometry.phase3a import geometry as g3  # noqa: E402
from experiments.week4_mono.round1 import (armio, common, evalgrid,  # noqa: E402
                                    metrics_geom as M, monoio, policy)


def load_arm_frame(model: str, clip: str, root: str, fi: int, gmap, ref):
    """One frame of one S4 arm, as the model's native scalar on the eval grid."""
    reader = monoio.MonoReader(root, model, clip)
    v = np.asarray(reader.load_valid(fi))
    nat = np.asarray(reader.load_native(fi), dtype=np.float64)
    s = np.linalg.norm(nat, axis=-1) if nat.ndim == 3 else nat
    vals, ok = evalgrid.sample(s, v, ref.uv, gmap)
    h, w = ref.eval_hw
    return np.where(ok, vals, np.nan).reshape(h, w), ok.reshape(h, w)


def fit_baseline_gauge(model: str, clip: str, base_root: str, frames: list[int],
                       pol: policy.Policy):
    """The clip-level alignment fitted ONCE on the BASELINE arm, reused for every
    perturbation of this (model, clip).

    Why this exists. S4's primary decomposition is computed in the model's OWN
    NATIVE quantity, which is the right object for asking "did appearance move
    this model". But it is NOT comparable across models: for a scale-family arm
    native is proportional to range, so a native log-ratio IS a range log-ratio,
    while for an AFFINE-family arm (here `da3mono_large`, family `affine_depth`)
    range is `s*d + t` and a native log-ratio relates to the physical one by

        L_phys ~= L_native * (1 - t/r)

    With this model's fitted `t` that factor is about 0.51 on the frozen clips,
    so reading its native numbers next to three scale-family arms overstates its
    response by roughly 2x. The physical-range decomposition below is therefore
    reported ALONGSIDE the native one -- not instead of it.

    The gauge is fitted on the BASELINE frames only and then held fixed, so no
    oracle ever sees a perturbed field: this is a unit conversion, not an
    alignment that could absorb the effect being measured.
    """
    ref = evalgrid.ReferenceClip(clip)
    gmap = evalgrid.load_model_gridmap(model, common.clip_source_hw(clip))
    nat_s, refr_s, refz_s = [], [], []
    for fi in frames:
        b, ok_b = load_arm_frame(model, clip, base_root, fi, gmap, ref)
        r_ref, ok_r = ref.load(fi)
        sec = g3.ray_length_factor(ref.K_eval(fi), *ref.eval_hw)
        m = ok_b & ok_r & np.isfinite(b) & np.isfinite(r_ref) & (r_ref > 0)
        if m.sum():
            nat_s.append(b[m]); refr_s.append(r_ref[m]); refz_s.append((r_ref / sec)[m])
    if not nat_s:
        return None
    return pol.fit_clip(model, np.concatenate(nat_s), np.concatenate(refr_s),
                        np.concatenate(refz_s))


def compare_arm(model: str, clip: str, base_root: str, pert_root: str,
                frames: list[int], pol: policy.Policy, edge_threshold: float,
                gauge=None) -> dict:
    """The three-way decomposition for one (model, clip, perturbation)."""
    ref = evalgrid.ReferenceClip(clip)
    gmap = evalgrid.load_model_gridmap(model, common.clip_source_hw(clip))
    K_by_frame = {}
    sigma_t, resid_med, resid_p95, cov_b, cov_p, edge_jit = [], [], [], [], [], []
    resid_med_r, resid_p95_r = [], []   # the same residual, in PHYSICAL RANGE
    ref_absrel_base, ref_absrel_pert = [], []
    normal_base, normal_pert = [], []

    for fi in frames:
        b, ok_b = load_arm_frame(model, clip, base_root, fi, gmap, ref)
        p, ok_p = load_arm_frame(model, clip, pert_root, fi, gmap, ref)
        r_ref, ok_r = ref.load(fi)
        K = ref.K_eval(fi)
        K_by_frame[fi] = K
        sec = g3.ray_length_factor(K, *ref.eval_hw)

        cov_b.append(float((ok_b & ok_r).mean()))
        cov_p.append(float((ok_p & ok_r).mean()))

        m = ok_b & ok_p & np.isfinite(b) & np.isfinite(p) & (b > 0) & (p > 0)
        if m.sum() < 200:
            sigma_t.append(np.nan); resid_med.append(np.nan); resid_p95.append(np.nan)
            edge_jit.append(np.nan)
            continue

        # sigma_t: the ONE scalar that best maps baseline onto perturbed, in the
        # model's own native quantity. Median log ratio, the project's estimator.
        lr = np.log(p[m]) - np.log(b[m])
        sigma = float(np.exp(np.median(lr)))
        sigma_t.append(sigma)

        # What is LEFT after that scalar is removed is, by construction, the part
        # no global physical parameter transformation can absorb.
        resid = lr - np.median(lr)
        resid_med.append(float(np.median(np.abs(resid))))
        resid_p95.append(float(np.percentile(np.abs(resid), 95)))

        # The SAME quantity in physical range, so the four arms are on one
        # scale. Identical to the native number for a scale-family arm; it is
        # the affine-family arm this exists for. See `fit_baseline_gauge`.
        if gauge is not None:
            rb = pol.to_range(model, b, gauge, sec)
            rp = pol.to_range(model, p, gauge, sec)
            mr = m & np.isfinite(rb) & np.isfinite(rp) & (rb > 0) & (rp > 0)
            if mr.sum() >= 200:
                lrr = np.log(rp[mr]) - np.log(rb[mr])
                rr = np.abs(lrr - np.median(lrr))
                resid_med_r.append(float(np.median(rr)))
                resid_p95_r.append(float(np.percentile(rr, 95)))

        # And the same question asked about boundaries rather than about range.
        eb = M.geometric_edges(np.where(m, b, np.nan), m, edge_threshold)
        ep = M.geometric_edges(np.where(m, p, np.nan), m, edge_threshold)
        if eb.any() and ep.any():
            from scipy import ndimage
            d = ndimage.distance_transform_edt(~eb)
            edge_jit.append(float(np.median(d[ep])))
        else:
            edge_jit.append(np.nan)

        # Quality against the Week-3 reference, before and after. Reported as
        # context, NOT as the decomposition: the reference carries its own
        # uncertainty and the decomposition above deliberately avoids it.
        for src, ok_src, sink_absrel, sink_norm in ((b, ok_b, ref_absrel_base, normal_base),
                                                    (p, ok_p, ref_absrel_pert, normal_pert)):
            fit = pol.fit_clip(model, src[ok_src & ok_r], r_ref[ok_src & ok_r],
                               (r_ref / sec)[ok_src & ok_r])
            rng = pol.to_range(model, src, fit, sec)
            good = ok_src & ok_r & np.isfinite(rng) & (rng > 0)
            e = g3.relative_errors(np.where(good, rng, np.nan),
                                   np.where(good, r_ref, np.nan), 1.0)
            sink_absrel.append(float(np.nanmedian(np.abs(e))))
            xyz_p = evalgrid.lift_to_xyz(np.nan_to_num(np.where(good, rng, np.nan), nan=1.0),
                                         K, ref.eval_hw)
            xyz_r = evalgrid.lift_to_xyz(np.nan_to_num(np.where(good, r_ref, np.nan), nan=1.0),
                                         K, ref.eval_hw)
            st = M.m3_absolute_normal(xyz_p, good, xyz_r, good)
            sink_norm.append(st.get("median", np.nan))
        del b, p, r_ref
        gc.collect()

    s = np.asarray(sigma_t, dtype=np.float64)
    fin = np.isfinite(s) & (s > 0)
    out = {"n_frames": len(frames), "sigma_t": [None if not np.isfinite(x) else float(x)
                                                for x in s]}
    if fin.sum() >= 2:
        ls = np.log(s[fin])
        out["constant_global_scale_bias"] = {
            "median_sigma": float(np.exp(np.median(ls))),
            "meaning": ("the one scalar the perturbation multiplied the whole clip by. "
                        "Potentially a BENIGN GAUGE: refit beta' = beta/s once."),
        }
        out["frame_varying_scale_drift"] = {
            "wander_ratio": float(np.exp(ls.max() - ls.min())),
            "log_std": float(np.std(ls)),
            "frame_to_frame_log_mad": float(np.median(np.abs(np.diff(ls)))),
            "meaning": ("how much that scalar CHANGED across the clip under the "
                        "perturbation. NOT benign under one shared clip-level physical "
                        "model: absorbing it would require beta'_t = beta/s_t."),
        }
    out["local_range_deformation"] = {
        "median_abs_dlog": float(np.nanmedian(resid_med)) if resid_med else float("nan"),
        "p95_abs_dlog": float(np.nanmedian(resid_p95)) if resid_p95 else float("nan"),
        "meaning": ("|delta log range| left AFTER removing the per-frame global scalar. "
                    "Spatially varying, so NOT absorbable by any global physical "
                    "parameter transformation. The primary geometric failure."),
    }
    out["local_range_deformation_physical"] = {
        "median_abs_dlog": (float(np.nanmedian(resid_med_r))
                            if resid_med_r else float("nan")),
        "p95_abs_dlog": (float(np.nanmedian(resid_p95_r))
                         if resid_p95_r else float("nan")),
        "meaning": ("the same residual measured in PHYSICAL RANGE, under the clip-level "
                    "gauge fitted on the BASELINE arm alone and then held fixed. Equal to "
                    "the native number for a scale-family arm; smaller for an affine-family "
                    "arm by ~(1 - t/r). This is the row that is comparable ACROSS models."),
    }
    out["boundary_jitter_px"] = (float(np.nanmedian(edge_jit))
                                 if np.isfinite(edge_jit).any() else float("nan"))
    out["coverage"] = {
        "baseline_median": float(np.median(cov_b)) if cov_b else float("nan"),
        "perturbed_median": float(np.median(cov_p)) if cov_p else float("nan"),
    }
    out["vs_reference"] = {
        "abs_rel_baseline": float(np.nanmedian(ref_absrel_base)) if ref_absrel_base else float("nan"),
        "abs_rel_perturbed": float(np.nanmedian(ref_absrel_pert)) if ref_absrel_pert else float("nan"),
        "normal_deg_baseline": float(np.nanmedian(normal_base)) if normal_base else float("nan"),
        "normal_deg_perturbed": float(np.nanmedian(normal_pert)) if normal_pert else float("nan"),
        "_note": ("context only. The decomposition above deliberately compares the model "
                  "against ITSELF, so it does not inherit the reference's uncertainty."),
    }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="*", default=None)
    ap.add_argument("--clips", nargs="*", default=None)
    ap.add_argument("--root", default=os.path.join(common.OUTPUTS, "s4_predictions"))
    ap.add_argument("--perturbed-root", default=os.path.join(common.OUTPUTS, "perturbed"))
    ap.add_argument("--policy", default=os.path.join(common.RESULTS,
                                                     "S2_alignment_policy.json"))
    ap.add_argument("--out", default=os.path.join(common.OUTPUTS, "s4", "s4_raw.json"))
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    pol = policy.Policy.load(args.policy)
    with open(os.path.join(args.perturbed_root, "manifest.json")) as fh:
        man = json.load(fh)
    perts = [p["name"] for p in man["perturbations"]]
    clips = args.clips or [c for c in common.CLIPS if c in man["clips"]]
    base_root = os.path.join(args.root, "baseline")
    models = args.models or [m for m in common.MODELS
                             if monoio.exists(base_root, m, clips[0])]

    result = {
        "_comment": ("S4 — appearance invariance. Each perturbed field is compared "
                     "against the SAME model's baseline field on the same frames, so the "
                     "response to appearance is isolated from the model's standing "
                     "disagreement with the Week-3 reference."),
        "stage": "S4",
        "perturbations": man["perturbations"],
        "window": man["window"],
        "models": {},
    }
    for model in models:
        rec = {"clips": {}}
        for clip in clips:
            frames = man["clips"][clip]["frames"]
            # The M-4 edge threshold is the same per-clip reference-derived
            # constant S3 used, so a jitter number here and a boundary number
            # there are on the same scale.
            ref = evalgrid.ReferenceClip(clip)
            grads = []
            for fi in frames:
                r, ok = ref.load(fi)
                mg, mok = M.log_range_gradient(r, ok)
                if mok.any():
                    grads.append(mg[mok])
            thr = M.calibrate_edge_threshold(grads)
            del grads
            gauge = fit_baseline_gauge(model, clip, base_root, frames, pol)
            crec = {"edge_threshold_log": thr,
                    "baseline_gauge": gauge.to_dict() if gauge is not None else None,
                    "perturbations": {}}
            for pname in perts:
                proot = os.path.join(args.root, pname)
                if not (monoio.exists(base_root, model, clip)
                        and monoio.exists(proot, model, clip)):
                    crec["perturbations"][pname] = {"status": "missing"}
                    continue
                r = compare_arm(model, clip, base_root, proot, frames, pol, thr,
                                gauge=gauge)
                r["status"] = "ok"
                crec["perturbations"][pname] = r
                cb = r.get("constant_global_scale_bias", {}).get("median_sigma", float("nan"))
                dr = r.get("frame_varying_scale_drift", {}).get("wander_ratio", float("nan"))
                ld = r["local_range_deformation"]["median_abs_dlog"]
                ldr = r["local_range_deformation_physical"]["median_abs_dlog"]
                print(f"[S4] {model:24s} {clip:15s} {pname:28s} "
                      f"sigma={cb:.4f} wander={dr:.4f} local_dlog={ld:.4f} "
                      f"phys={ldr:.4f} "
                      f"cov {r['coverage']['baseline_median']:.3f}->"
                      f"{r['coverage']['perturbed_median']:.3f}")
            rec["clips"][clip] = crec
        result["models"][model] = rec
        common.write_json(args.out, result, overwrite=True)

    common.write_json(args.out, result, overwrite=True)
    print(f"[S4] -> {os.path.relpath(args.out, REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
