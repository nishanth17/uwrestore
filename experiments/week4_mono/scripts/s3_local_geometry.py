"""S3 — the primary local-geometry bakeoff over the full frozen 288-frame set.

EXPLORATORY. Runs in `.venv-eval`; reads persisted products, loads no model.

THE PRIMARY FIELD REDUCTION (`MONO_DEPTH_FREEZE.md` §5 S3). Every arm is scored
on the SAME 6 clips x 48 frames, against the SAME Week-3 persisted range
product, under the SAME frozen S2 alignment policy, with the SAME six universal
metrics. Nothing else is added to the primary ranking.

    M-1  range-stratified relative range error, in BOTH required forms
    M-2  near/far systematic distortion, log-log slope b
    M-3  local surface geometry: RelNormal, plus absolute normal error
    M-4  boundary localisation
    M-5  foreground/background ordinal violations
    M-6  radial image-position error

AbsRel and delta-1 are computed for literature continuity and are never
decisive. **There is no weighted master score**: collapsing six dimensions into
one number would hide exactly the tradeoffs the freeze requires be documented.

FoundationGeo contributes four arms rather than one, so that its two internal
ablations are scored by the same instrument as everyone else:

    V4b  fg_pre_ray  vs  fg_post_ray     the learned ray-direction correction
    V4c  fg_post_ray vs  foundationgeo_11 the learned per-pixel scale field

Both V4b arms come from ONE forward pass under ONE frozen (focal, shift), which
is what makes their difference attributable to the ray delta rather than to two
independently recovered postprocessing solutions.

MEMORY (CLAUDE.md invariant 9). One frame at a time. Per-frame metrics are
computed and reduced to a small record; only a bounded per-clip sample pool
(4 000 samples x 48 frames) is held for the pooled statistics.

    experiments/week4_mono/.venv-eval/bin/python \\
        -m experiments.week4_mono.scripts.s3_local_geometry --overwrite
"""

from __future__ import annotations

import argparse
import gc
import os
import sys
import time

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week3_geometry import geometry as g3  # noqa: E402
from experiments.week4_mono import (armio, common, evalgrid,  # noqa: E402
                                    metrics_geom as M, monoio, policy)

SAMPLES_PER_FRAME = 4000

#: M-3's RelNormal is the most expensive metric, so `RELNORMAL_STRIDE` exists to
#: compute it on every Nth frame if it ever needs to be. Measured cost at the
#: reduced 2e5-pair budget is ~0.15 s/frame, i.e. about 12 s per (arm, clip) for
#: ALL SIX metrics on all 48 frames, so the default is 1: every frame, no
#: subsampling anywhere in S3.
RELNORMAL_STRIDE = 1


def frame_metrics(arm: armio.Arm, pol: policy.Policy, fit, fd: dict,
                  do_relnormal: bool, edge_threshold: float) -> dict:
    """All per-frame metrics for one frame of one arm."""
    rng_pred = pol.to_range(arm.arm, fd["native"], fit, fd["secant"])
    ok = fd["native_valid"] & fd["ref_valid"] & np.isfinite(rng_pred) & (rng_pred > 0)
    ref = np.where(fd["ref_valid"], fd["ref_range"], np.nan)

    rec = {"frame": fd["frame"], "coverage": fd["coverage"],
           "scored_fraction": float(ok.mean())}
    if ok.sum() < 100:
        rec["status"] = "insufficient_support"
        return rec
    rec["status"] = "ok"

    p = np.where(ok, rng_pred, np.nan)
    r = np.where(ok, ref, np.nan)

    err = M.relative_error(p, r)
    rec["m1_overall_abs_rel_median"] = float(np.nanmedian(np.abs(err)))
    rec["m1_overall_signed_median"] = float(np.nanmedian(err))
    rec["m2"] = M.m2_loglog(p, r)
    rec["m4"] = M.m4_boundary(p, ok, r, ok, edge_threshold)
    rec["m5"] = M.m5_ordinal(p, r, ok, seed=fd["frame"])
    rec["m6"] = M.m6_radial(p, r, fd["radius"])

    # M-3 needs 3D. Both sides are lifted with the SAME evaluation camera, so a
    # difference between two arms is a difference in geometry rather than a
    # difference in whose focal was used to lift it.
    xyz_p = evalgrid.lift_to_xyz(np.nan_to_num(p, nan=1.0), fd["K_eval"], fd["eval_hw"])
    xyz_r = evalgrid.lift_to_xyz(np.nan_to_num(r, nan=1.0), fd["K_eval"], fd["eval_hw"])
    rec["m3_abs_normal"] = M.m3_absolute_normal(xyz_p, ok, xyz_r, ok)
    if do_relnormal:
        rec["m3_relnormal"] = M.m3_relnormal(xyz_p, ok, xyz_r, ok)
    return rec


def pooled_clip_metrics(pool: dict, clip_quantiles) -> dict:
    """M-1, M-2, M-6 and the secondary metrics on the clip's pooled sample."""
    p, r, rad = pool["pred"], pool["ref"], pool["radius"]
    out = {"n_pooled": int(p.size)}
    out["m1"] = M.m1_stratified(p, r, clip_quantiles)
    out["m2"] = M.m2_loglog(p, r)
    out["m6"] = M.m6_radial(p, r, rad)
    out["secondary"] = M.secondary_metrics(p, r)
    return out


def agg(records: list[dict], path, stat: str = "median") -> float:
    """Median across frames of a per-frame scalar reached by a key path.

    The path is a TUPLE of keys, not a dotted string: M-5's margins are keyed by
    their numeric value ("0.25"), and splitting on "." would silently look for a
    key "0" and then "25" and return NaN for the metric that matters most.
    """
    keys = (path,) if isinstance(path, str) else tuple(path)
    vals = []
    for rec in records:
        cur = rec
        for k in keys:
            if not isinstance(cur, dict) or k not in cur:
                cur = None
                break
            cur = cur[k]
        if isinstance(cur, (int, float)) and np.isfinite(cur):
            vals.append(float(cur))
    if not vals:
        return float("nan")
    return float(np.median(vals) if stat == "median" else np.mean(vals))


def score_arm(arm_key: str, pol: policy.Policy, root: str, clips: list[str],
              relnormal_stride: int) -> dict:
    out = {"arm": arm_key, "model": armio.arm_model(arm_key),
           "role": armio.arm_role(arm_key),
           "policy": pol.entry(arm_key), "clips": {}}
    for clip in clips:
        if not monoio.exists(root, armio.arm_model(arm_key), clip):
            out["clips"][clip] = {"status": "missing"}
            continue
        t0 = time.perf_counter()
        a = armio.Arm(arm_key, clip, root)
        frames = a.frames
        rng = np.random.default_rng(0)

        # --- pass 1: the clip-level alignment fit, on pooled samples --------
        nat_s, refr_s, refz_s, rad_s, sec_s = [], [], [], [], []
        # The M-4 edge threshold is calibrated from the REFERENCE only, pooled
        # over the clip, so it is identical for every arm scored on this clip.
        # Deriving it per arm would let a smooth model define its own idea of a
        # boundary and then be graded against it.
        ref_grad = []
        for fi in frames:
            fd = a.frame(fi)
            ok = fd["native_valid"] & fd["ref_valid"]
            mg, mok = M.log_range_gradient(fd["ref_range"], fd["ref_valid"])
            if mok.any():
                ref_grad.append(mg[mok])
            idx = np.flatnonzero(ok.ravel())
            if idx.size == 0:
                continue
            take = idx if idx.size <= SAMPLES_PER_FRAME else rng.choice(
                idx, size=SAMPLES_PER_FRAME, replace=False)
            nat_s.append(fd["native"].ravel()[take])
            refr_s.append(fd["ref_range"].ravel()[take])
            refz_s.append(fd["ref_z"].ravel()[take])
            rad_s.append(fd["radius"].ravel()[take])
            sec_s.append(fd["secant"].ravel()[take])
            del fd
        if not nat_s:
            out["clips"][clip] = {"status": "no_overlapping_valid_samples"}
            continue
        nat = np.concatenate(nat_s); refr = np.concatenate(refr_s)
        refz = np.concatenate(refz_s); rad = np.concatenate(rad_s)
        sec = np.concatenate(sec_s)
        del nat_s, refr_s, refz_s, rad_s, sec_s
        edge_threshold = M.calibrate_edge_threshold(ref_grad)
        del ref_grad
        fit = pol.fit_clip(arm_key, nat, refr, refz)
        pred_pooled = pol.to_range(arm_key, nat, fit, sec)

        # Scale-invariant near/mid/far edges: quantiles of the CLIP's pooled
        # reference, so every frame of the clip uses ONE definition of "far".
        good = np.isfinite(refr) & (refr > 0)
        q = (np.quantile(refr[good], M.QUANTILE_EDGES) if good.any()
             else np.array(M.QUANTILE_EDGES))

        pooled = pooled_clip_metrics({"pred": pred_pooled, "ref": refr, "radius": rad}, q)

        # --- pass 2: per-frame metrics, under that frozen fit ---------------
        per_frame = []
        for n, fi in enumerate(frames):
            fd = a.frame(fi)
            per_frame.append(frame_metrics(
                a, pol, fit, fd, do_relnormal=(n % relnormal_stride == 0),
                edge_threshold=edge_threshold))
            del fd
            gc.collect()

        ok_frames = [f for f in per_frame if f.get("status") == "ok"]
        out["clips"][clip] = {
            "status": "ok" if ok_frames else "no_scored_frames",
            "n_frames": len(frames),
            "n_scored_frames": len(ok_frames),
            "alignment": fit.to_dict(),
            "edge_threshold_log": edge_threshold,
            "pooled": pooled,
            "coverage_median": float(np.median([f["coverage"] for f in per_frame])),
            "coverage_min": float(np.min([f["coverage"] for f in per_frame])),
            "per_frame_aggregates": {
                "m1_abs_rel_median": agg(ok_frames, "m1_overall_abs_rel_median"),
                "m2_b": agg(ok_frames, ("m2", "b")),
                "m3_relnormal_deg": agg(ok_frames, ("m3_relnormal", "rel_normal_deg")),
                "m3_abs_normal_median_deg": agg(ok_frames, ("m3_abs_normal", "median")),
                "m3_abs_normal_frac_within_30deg":
                    agg(ok_frames, ("m3_abs_normal", "frac_within_30deg")),
                "m4_symmetric_median_norm": agg(ok_frames, ("m4", "symmetric_median_norm")),
                "m4_edge_fraction_pred": agg(ok_frames, ("m4", "edge_fraction_pred")),
                "m4_edge_fraction_ref": agg(ok_frames, ("m4", "edge_fraction_ref")),
                "m5_violation_0_10": agg(ok_frames, ("m5", "margins", "0.1", "violation_rate")),
                "m5_violation_0_25": agg(ok_frames, ("m5", "margins", "0.25", "violation_rate")),
                "m5_violation_0_50": agg(ok_frames, ("m5", "margins", "0.5", "violation_rate")),
                "m6_outer_over_inner": agg(ok_frames, ("m6", "outer_over_inner")),
                "n_relnormal_frames": sum(1 for f in ok_frames if "m3_relnormal" in f),
            },
            "per_frame": per_frame,
            "seconds": round(time.perf_counter() - t0, 1),
        }
        pfa = out["clips"][clip]["per_frame_aggregates"]
        print(f"[S3] {arm_key:22s} {clip:15s} "
              f"absrel={pfa['m1_abs_rel_median']:.4f} b={pfa['m2_b']:.3f} "
              f"relnorm={pfa['m3_relnormal_deg']:.2f}deg "
              f"norm50={pfa['m3_abs_normal_median_deg']:.1f}deg "
              f"bnd={pfa['m4_symmetric_median_norm']:.4f} "
              f"ord25={pfa['m5_violation_0_25']:.4f} "
              f"m6={pfa['m6_outer_over_inner']:.2f} "
              f"cov={out['clips'][clip]['coverage_median']:.3f} "
              f"({out['clips'][clip]['seconds']}s)")
        del a, per_frame, nat, refr, refz, rad, sec, pred_pooled
        gc.collect()

    # ---- across-clip summary. Median across clips, and the SPREAD, because
    # FREEZE 6 forbids hiding a change that helps one category and hurts another.
    ok_clips = {c: v for c, v in out["clips"].items() if v.get("status") == "ok"}
    if ok_clips:
        keys = list(next(iter(ok_clips.values()))["per_frame_aggregates"].keys())
        summary = {}
        for k in keys:
            vals = [v["per_frame_aggregates"][k] for v in ok_clips.values()
                    if np.isfinite(v["per_frame_aggregates"][k])]
            if vals:
                summary[k] = {"median": float(np.median(vals)),
                              "min": float(np.min(vals)), "max": float(np.max(vals)),
                              "by_clip": {c: v["per_frame_aggregates"][k]
                                          for c, v in ok_clips.items()}}
        summary["coverage"] = {
            "median": float(np.median([v["coverage_median"] for v in ok_clips.values()])),
            "min": float(np.min([v["coverage_min"] for v in ok_clips.values()])),
            "by_clip": {c: v["coverage_median"] for c, v in ok_clips.items()},
        }
        summary["n_clips_scored"] = len(ok_clips)
        out["summary"] = summary
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arms", nargs="*", default=None)
    ap.add_argument("--clips", nargs="*", default=None)
    ap.add_argument("--root", default=os.path.join(common.OUTPUTS, "predictions"))
    ap.add_argument("--policy", default=os.path.join(common.RESULTS,
                                                     "S2_alignment_policy.json"))
    ap.add_argument("--out", default=os.path.join(common.OUTPUTS, "s3", "s3_raw.json"))
    ap.add_argument("--relnormal-stride", type=int, default=RELNORMAL_STRIDE)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    pol = policy.Policy.load(args.policy)
    clips = args.clips or common.CLIPS
    models = [m for m in common.MODELS if monoio.exists(args.root, m, clips[0])]
    arms = args.arms or armio.arm_keys(models)

    result = {
        "_comment": ("S3 — primary local-geometry bakeoff. Full frozen set: "
                     "6 clips x 48 frames. Reference is the Week-3 persisted range "
                     "product, a PROVISIONAL MULTI-VIEW HYPOTHESIS. 'Error' means "
                     "disagreement with that hypothesis, never objective error."),
        "stage": "S3",
        "clips": clips,
        "arms": {},
        "relnormal_stride": args.relnormal_stride,
        "samples_per_frame": SAMPLES_PER_FRAME,
        "no_master_score": ("FREEZE 6: no weighted master score. Six dimensions are "
                            "reported separately and reduction is by explicit "
                            "multi-dimensional reasons."),
    }
    for arm in arms:
        t0 = time.perf_counter()
        result["arms"][arm] = score_arm(arm, pol, args.root, clips, args.relnormal_stride)
        print(f"[S3] {arm}: done in {time.perf_counter() - t0:.0f}s")
        common.write_json(args.out, result, overwrite=True)
    common.write_json(args.out, result, overwrite=True)
    print(f"[S3] -> {os.path.relpath(args.out, REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
