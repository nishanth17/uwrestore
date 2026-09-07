"""S6 — restoration impact: Week-3 multi-view range vs each monocular finalist.

EXPLORATORY. Runs in `.venv-eval`.

FREEZE §5 S6. Only survivors run. The same six frozen clips are restored twice —
once driven by the Week-3 multi-view range, once by each finalist's monocular
range — so the comparison is apples-to-apples on identical frames.

    Restoration is at SOURCE resolution, not on the evaluation grid. Each arm's
    native field is sampled directly at every source pixel through its own
    measured preprocessing map, so nothing is upsampled from a downsampled
    field. The alignment is the clip-level fit the frozen S2 policy specifies,
    computed on the evaluation grid exactly as S3 computed it.

    The physical coefficients are SHARED and FIXED across arms, and the veiling
    light is estimated once per clip from the REFERENCE. Between two arms the
    only thing that changes is d_hat. That is what makes temporal scale drift
    bite here: a CONSTANT scale error is exactly absorbable by b -> b/s, so a
    merely-biased model loses nothing, while a model whose scale WANDERS cannot
    be absorbed by any single b and pays for it in colour.

Restored frames are written to disk so that the mandatory visual inspection and
the frozen Week-2 temporal evaluation both run on the same artifacts.

    experiments/week4_mono/.venv-eval/bin/python \\
        -m experiments.week4_mono.scripts.s6_restoration --arms moge2_vitl --overwrite
"""

from __future__ import annotations

import argparse
import gc
import os
import sys

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week3_geometry import geometry as g3  # noqa: E402
from experiments.week4_mono import (armio, common, evalgrid,  # noqa: E402
                                    monoio, policy, restoration)
from uw.colorspace import linear_to_srgb, srgb_to_linear  # noqa: E402

REFERENCE_ARM = "week3_reference"


def _med(vals):
    """Median over the frames where the quantity was actually measurable."""
    v = [x for x in vals if np.isfinite(x)]
    return float(np.median(v)) if v else float("nan")


def _mad(vals):
    """Frame-to-frame MAD over the measurable frames, in their original order."""
    v = np.asarray([x for x in vals if np.isfinite(x)], dtype=float)
    return float(np.median(np.abs(np.diff(v)))) if v.size > 1 else float("nan")


def source_range(arm: armio.Arm, fi: int, pol: policy.Policy, fit, source_hw):
    """The arm's aligned range at FULL SOURCE resolution."""
    uv, _ = evalgrid.eval_grid(source_hw, downsample=1)
    s_nat, v_pred = arm.native_scalar(fi)
    vals, ok = evalgrid.sample(s_nat, v_pred, uv, arm.gmap)
    h, w = source_hw
    native = np.where(ok, vals, np.nan).reshape(h, w)
    ok = ok.reshape(h, w)
    K_src = _K_source(arm, fi, source_hw)
    sec = g3.ray_length_factor(K_src, h, w)
    r = pol.to_range(arm.arm, native, fit, sec)
    return r, ok & np.isfinite(r) & (r > 0)


def _K_source(arm: armio.Arm, fi: int, source_hw):
    """The reference camera carried onto the SOURCE grid (downsample=1)."""
    K = np.asarray(arm.ref.reader.by_index[fi]["K"], dtype=np.float64)
    return evalgrid.K_source_to_eval(K, arm.ref.gmap, downsample=1)


def reference_source_range(clip: str, fi: int, source_hw):
    """The Week-3 persisted range at FULL SOURCE resolution."""
    from experiments.week3_geometry.rangeio import RangeReader
    reader = RangeReader(common.W3_RANGE_ROOT, common.REFERENCE_CONFIG, clip)
    gmap = evalgrid.load_reference_gridmap(source_hw)
    uv, _ = evalgrid.eval_grid(source_hw, downsample=1)
    r, v = reader.load(fi)
    vals, ok = evalgrid.sample(np.asarray(r), np.asarray(v), uv, gmap)
    h, w = source_hw
    return (np.where(ok, vals, np.nan).reshape(h, w),
            ok.reshape(h, w) & np.isfinite(vals.reshape(h, w)))


def main() -> int:
    import cv2
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arms", nargs="*", required=True,
                    help="the S5 finalists; the Week-3 reference arm is always included")
    ap.add_argument("--clips", nargs="*", default=None)
    ap.add_argument("--root", default=os.path.join(common.OUTPUTS, "predictions"))
    ap.add_argument("--policy", default=os.path.join(common.RESULTS,
                                                     "S2_alignment_policy.json"))
    ap.add_argument("--water", default=restoration.DEFAULT_WATER,
                    choices=sorted(restoration.WATER_TYPES))
    ap.add_argument("--sweep-water", action="store_true",
                    help="also report the two other Jerlov regimes, as a robustness check")
    ap.add_argument("--out-root", default=os.path.join(common.OUTPUTS, "s6"))
    ap.add_argument("--save-frames", action="store_true", default=True)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    pol = policy.Policy.load(args.policy)
    clips = args.clips or common.CLIPS
    waters = ([args.water] + [w for w in restoration.WATER_TYPES if w != args.water]
              if args.sweep_water else [args.water])

    result = {
        "_comment": ("S6 — restoration impact. The physical coefficients and the veiling "
                     "light are SHARED and FIXED across arms; between two arms the only "
                     "thing that changes is the range field. This restoration is a common "
                     "INSTRUMENT built for this comparison, not the project's restoration "
                     "— Weeks 5-6 own that."),
        "stage": "S6",
        "reference_arm": REFERENCE_ARM,
        "water_types": {w: restoration.WATER_TYPES[w] for w in waters},
        "primary_water_type": args.water,
        "j_clamp": restoration.J_CLAMP,
        "t_floor": restoration.T_FLOOR,
        "veiling_light_policy": (
            "per channel, min(far-field p90 under the REFERENCE range, the "
            "model-admissible dark-channel bound for this water type). The "
            "far-field estimator alone is not admissible on footage whose water "
            "column is clipped in the source and drives the inversion negative "
            "almost everywhere; see restoration.admissible_veiling_light."),
        "arms": args.arms,
        "clips": {},
    }

    for clip in clips:
        source_hw = common.clip_source_hw(clip)
        h, w = source_hw
        frames = common.frame_indices(clip)
        crec = {"source_hw": list(source_hw), "n_frames": len(frames), "arms": {}}

        # --- the reference arm, and the coefficients everyone shares --------
        # Binf comes from the REFERENCE geometry on the clip's middle frame and
        # is then frozen: restoring each arm under its own veiling light would
        # stop the comparison isolating the range field.
        mid = frames[len(frames) // 2]
        bgr = cv2.imread(common.frame_path(clip, mid))
        lin_mid = srgb_to_linear(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float64) / 255.0)
        r_mid, ok_mid = reference_source_range(clip, mid, source_hw)
        far = restoration.estimate_veiling_light(lin_mid, r_mid, ok_mid)
        Binf = {}
        for wt in waters:
            adm = restoration.admissible_veiling_light(
                lin_mid, r_mid, ok_mid, restoration.WATER_TYPES[wt]["b_bs"])
            Binf[wt] = np.minimum(far, adm)
        crec["Binf_far_field_p90"] = [float(x) for x in far]
        crec["Binf_linear_rgb"] = {wt: [float(x) for x in Binf[wt]] for wt in waters}
        crec["Binf_source"] = ("estimated once from the clip's middle frame under the "
                               "REFERENCE range and then held fixed for every arm: the "
                               "far-field p90 capped by the model-admissible dark-channel "
                               "bound. The cap depends on b_bs, so it is per water type; "
                               "within a water type every arm still shares one Binf, which "
                               "is what keeps the range field the only thing that varies")
        del lin_mid, r_mid, ok_mid

        # --- clip-level alignment fits, on the evaluation grid --------------
        fits = {}
        for arm_key in args.arms:
            a = armio.Arm(arm_key, clip, args.root)
            rngen = np.random.default_rng(0)
            nat_s, refr_s, refz_s = [], [], []
            for fi in a.frames:
                fd = a.frame(fi)
                ok = fd["native_valid"] & fd["ref_valid"]
                idx = np.flatnonzero(ok.ravel())
                if idx.size:
                    take = idx if idx.size <= 4000 else rngen.choice(idx, 4000, replace=False)
                    nat_s.append(fd["native"].ravel()[take])
                    refr_s.append(fd["ref_range"].ravel()[take])
                    refz_s.append(fd["ref_z"].ravel()[take])
                del fd
            fits[arm_key] = pol.fit_clip(arm_key, np.concatenate(nat_s),
                                         np.concatenate(refr_s), np.concatenate(refz_s))
            crec["arms"].setdefault(arm_key, {})["alignment"] = fits[arm_key].to_dict()
            del a, nat_s, refr_s, refz_s
            gc.collect()

        # --- restore, frame by frame ----------------------------------------
        per_arm = {k: {wt: [] for wt in waters} for k in args.arms}
        rstats = {k: {wt: [] for wt in waters} for k in [REFERENCE_ARM] + list(args.arms)}
        arms_open = {k: armio.Arm(k, clip, args.root) for k in args.arms}
        for fi in frames:
            bgr = cv2.imread(common.frame_path(clip, fi))
            lin = srgb_to_linear(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float64) / 255.0)
            d_ref, ok_ref = reference_source_range(clip, fi, source_hw)
            fields = {REFERENCE_ARM: (d_ref, ok_ref)}
            for arm_key in args.arms:
                fields[arm_key] = source_range(arms_open[arm_key], fi, pol,
                                               fits[arm_key], source_hw)
            for wt in waters:
                c = restoration.WATER_TYPES[wt]
                J = {}
                for name, (d, okd) in fields.items():
                    Jn, okn, st, resp = restoration.restore(
                        lin, d, okd, c["b_att"], c["b_bs"], Binf[wt])
                    J[name] = (Jn, okn, resp)
                    rstats[name][wt].append(st)
                    if args.save_frames and wt == args.water:
                        od = os.path.join(args.out_root, "restored", clip, name)
                        os.makedirs(od, exist_ok=True)
                        dst = os.path.join(od, f"f{fi:06d}.png")
                        img = (np.clip(linear_to_srgb(np.clip(Jn / restoration.J_CLAMP, 0, 1)),
                                       0, 1) * 255.0 + 0.5).astype(np.uint8)
                        cv2.imwrite(dst, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
                Jr, okr, rr = J[REFERENCE_ARM]
                for arm_key in args.arms:
                    Jt, okt, rt = J[arm_key]
                    per_arm[arm_key][wt].append(
                        restoration.compare_restorations(Jr, Jt, okr & okt,
                                                         window=rr & rt))
                del J
            del lin, fields, d_ref, ok_ref
            gc.collect()

        for arm_key in args.arms:
            rec = crec["arms"][arm_key]
            for wt in waters:
                allrows = per_arm[arm_key][wt]
                # A frame counts for colour if delta E was actually computable
                # on it, and for radiance if the reference restoration had a
                # usable denominator. Those two sets are not always the same,
                # so both counts are reported rather than one standing in for
                # the other.
                rows = [r for r in allrows
                        if np.isfinite(r.get("delta_e00_median", np.nan))]
                radrows = [r for r in rows
                           if np.isfinite(r.get("radiance_abs_rel_median", np.nan))]
                if not rows:
                    rec[wt] = {"status": "no_common_support",
                               "n_frames_attempted": len(allrows)}
                    continue
                de = [r["delta_e00_median"] for r in rows]
                rec[wt] = {
                    "n_frames": len(rows),
                    "n_frames_attempted": len(allrows),
                    "n_frames_dropped_insufficient_support": len(allrows) - len(rows),
                    "n_frames_radiance": len(radrows),
                    "delta_e00_median": float(np.median(de)),
                    "delta_e00_p95": float(np.median([r["delta_e00_p95"] for r in rows])),
                    "delta_e00_frame_max": float(np.max(de)),
                    "radiance_abs_rel_median":
                        float(np.median([r["radiance_abs_rel_median"] for r in radrows]))
                        if radrows else float("nan"),
                    "radiance_abs_rel_p95":
                        float(np.median([r["radiance_abs_rel_p95"] for r in radrows]))
                        if radrows else float("nan"),
                    "exposure_ratio_median":
                        float(np.median([r["exposure_ratio"] for r in rows])),
                    # The same two numbers over the RESPONSIVE window only --
                    # the subset where a pixel can still react to the range
                    # field at all. These are the ones that carry information.
                    "window_fraction_median":
                        float(np.median([r["window_fraction"] for r in rows])),
                    "delta_e00_median_window":
                        _med([r["delta_e00_median_window"] for r in rows]),
                    "delta_e00_p95_window":
                        _med([r["delta_e00_p95_window"] for r in rows]),
                    "radiance_abs_rel_median_window":
                        _med([r["radiance_abs_rel_median_window"] for r in rows]),
                    "delta_e00_frame_to_frame_mad_window":
                        _mad([r["delta_e00_median_window"] for r in rows]),
                    # Colour PUMPING: how much the frame-to-frame colour difference
                    # itself moves. A steady offset is a bias; a moving one is pumping.
                    "delta_e00_frame_to_frame_mad":
                        float(np.median(np.abs(np.diff(de)))) if len(de) > 1
                        else float("nan"),
                    "clipped_high_fraction_median":
                        float(np.median([s["clipped_high_fraction"]
                                         for s in rstats[arm_key][wt]])),
                    "gain_p99_median":
                        float(np.median([s["gain_p99"] for s in rstats[arm_key][wt]])),
                    "gain_p99_uncapped_median":
                        float(np.median([s["gain_p99_uncapped"]
                                         for s in rstats[arm_key][wt]])),
                    "floored_fraction_all_median":
                        float(np.median([s["floored_fraction_all"]
                                         for s in rstats[arm_key][wt]])),
                    "negative_fraction_median":
                        float(np.median([s["negative_fraction"]
                                         for s in rstats[arm_key][wt]])),
                }
                r = rec[wt]
                print(f"[S6] {clip:15s} {arm_key:24s} {wt:15s} "
                      f"dE00={r['delta_e00_median']:.3f} p95={r['delta_e00_p95']:.3f} "
                      f"pump={r['delta_e00_frame_to_frame_mad']:.3f} "
                      f"radrel={r['radiance_abs_rel_median']:.4f} "
                      f"clip={r['clipped_high_fraction_median']:.4f} "
                      f"nf={r['n_frames']}/{r['n_frames_attempted']} "
                      f"nrad={r['n_frames_radiance']} "
                      f"| WINDOW frac={r['window_fraction_median']:.3f} "
                      f"dE00={r['delta_e00_median_window']:.3f} "
                      f"radrel={r['radiance_abs_rel_median_window']:.4f}")
        crec["reference_restoration_stats"] = {
            wt: {k + "_median": float(np.median([s[k] for s in rstats[REFERENCE_ARM][wt]]))
                 for k in ("clipped_high_fraction", "negative_fraction", "gain_p99",
                           "gain_p99_uncapped", "floored_fraction_all",
                           "responsive_fraction")}
            for wt in waters}
        result["clips"][clip] = crec
        del arms_open, per_arm, rstats
        gc.collect()
        common.write_json(os.path.join(args.out_root, "s6_raw.json"), result, overwrite=True)

    common.write_json(os.path.join(args.out_root, "s6_raw.json"), result, overwrite=True)
    print(f"[S6] -> {os.path.relpath(os.path.join(args.out_root, 's6_raw.json'), REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
