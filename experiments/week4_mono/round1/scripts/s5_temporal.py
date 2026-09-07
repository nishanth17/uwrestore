"""S5 — independent-frame temporal stability, over the full frozen 288-frame set.

EXPLORATORY. Runs in `.venv-eval`. Uses the products S3 already scored; no model
is loaded and no frame is re-inferred.

THE INVARIANT S5 IS ABOUT. Every frame was inferred INDEPENDENTLY — one image
in, one prediction out, no neighbouring image, no temporal state, no Week-3
geometry input. The sequence is used only AFTER inference, to ask what a
strictly per-frame estimator does to a moving scene.

    s_t          scale trajectory
    t_t          shift trajectory where the alignment family has one
    near/far     the aligned field's own near/far ratio, frame by frame
    local        local-surface stability AT CORRESPONDING SCENE POINTS
    boundary     edge jitter at corresponding scene points
    coverage     validity trajectory
    confidence   where the model emits one

WHY CORRESPONDENCE IS REQUIRED, AND WHY IT IS ONLY EVALUATION. Comparing frame t
and frame t+1 at the same PIXEL measures scene motion, not estimator
instability. So SEA-RAFT flow (computed once per clip by `s5_flow.py`) maps
pixels to the same scene point, and the comparison happens there. The flow never
reaches a depth model.

THE PHYSICAL IMPLICATION, STATED EXPLICITLY (FREEZE C7). If

    d'_t = s_t d_t

then under ONE shared clip-level physical coefficient, absorbing that would
require `beta'_t = beta / s_t` — water properties that change with the
estimator. So frame-varying scale drift is a physical-model inconsistency even
when every individual frame looks geometrically fine after oracle alignment.
That is why S5 reports the TRAJECTORY, not just the average scale.

THE FROZEN EPISTEMIC PARTITION. `wreck_03` carries a dynamic diver, and
agreement with the Week-3 reference on a moving object is NOT ground truth —
the multi-view reference is least trustworthy exactly where the scene moved.
Regions are therefore partitioned and reported separately:

    static_anchored        flow-consistent AND the reference has support
    static_reference_uncertain  flow-consistent, reference support thin
    dynamic                flow-inconsistent: occlusion or independent motion

Dynamic-region agreement is reported and never used as a quality claim.

MEMORY. One clip's evaluation-grid fields are held resident while that clip is
analysed — about 180 MB. That is deliberate and is what `CLAUDE.md` invariant 9
calls the ACTIVE TEMPORAL WINDOW: a temporal metric needs frame t and frame t+1
simultaneously, and the window here is one clip, released before the next. What
is never resident is a full-clip array at NATIVE resolution; the native fields
stay memory-mapped on disk and are sampled one frame at a time.

    experiments/week4_mono/.venv-eval/bin/python \\
        -m experiments.week4_mono.round1.scripts.s5_temporal --overwrite
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

SAMPLES_PER_FRAME = 4000


def warp_to_t(field_t1: np.ndarray, flow: np.ndarray):
    """Sample frame t+1's field at where each frame-t pixel went. Returns (vals, ok).

    Bilinear, with the same all-four-neighbours-valid rule the rest of the
    project uses, so a sample straddling an occlusion boundary is declined
    rather than filled from the visible side.
    """
    h, w = field_t1.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
    u = xx + flow[..., 0]
    v = yy + flow[..., 1]
    uv = np.stack([u.ravel(), v.ravel()], axis=1)
    valid = np.isfinite(field_t1)
    vals, ok = g3.sample_at_observations(field_t1, valid, uv)
    return vals.reshape(h, w), ok.reshape(h, w)


def analyse(arm_key: str, clip: str, root: str, flow_root: str,
            pol: policy.Policy) -> dict:
    a = armio.Arm(arm_key, clip, root)
    ref = a.ref
    frames = a.frames
    model = armio.arm_model(arm_key)
    reader = monoio.MonoReader(root, model, clip)
    has_conf = bool(reader.meta["frames"][0].get("has_conf"))

    # --- clip-level frozen fit, exactly as S3 does it --------------------
    rng_sample = np.random.default_rng(0)
    nat_s, refr_s, refz_s, grads = [], [], [], []
    cache = {}
    for fi in frames:
        fd = a.frame(fi)
        cache[fi] = fd
        ok = fd["native_valid"] & fd["ref_valid"]
        idx = np.flatnonzero(ok.ravel())
        if idx.size:
            take = idx if idx.size <= SAMPLES_PER_FRAME else rng_sample.choice(
                idx, size=SAMPLES_PER_FRAME, replace=False)
            nat_s.append(fd["native"].ravel()[take])
            refr_s.append(fd["ref_range"].ravel()[take])
            refz_s.append(fd["ref_z"].ravel()[take])
        mg, mok = M.log_range_gradient(fd["ref_range"], fd["ref_valid"])
        if mok.any():
            grads.append(mg[mok])
    if not nat_s:
        return {"status": "no_overlapping_valid_samples"}
    fit = pol.fit_clip(arm_key, np.concatenate(nat_s), np.concatenate(refr_s),
                       np.concatenate(refz_s))
    thr = M.calibrate_edge_threshold(grads)
    del nat_s, refr_s, refz_s, grads

    # --- per-frame trajectories -------------------------------------------
    s_t, t_t, near_far, cov, conf_t, p05_t, p95_t = [], [], [], [], [], [], []
    ranges = {}
    for fi in frames:
        fd = cache[fi]
        ok = fd["native_valid"] & fd["ref_valid"]
        r = pol.to_range(arm_key, fd["native"], fit, fd["secant"])
        ranges[fi] = (r, fd["native_valid"] & np.isfinite(r) & (r > 0))
        cov.append(float((ranges[fi][1] & fd["ref_valid"]).mean()))
        m = ok & np.isfinite(r) & (r > 0)
        if m.sum() >= 8:
            one = pol.fit_clip(arm_key, fd["native"][m], fd["ref_range"][m], fd["ref_z"][m])
            s_t.append(one.params.get("s", np.nan))
            t_t.append(one.params.get("t", np.nan))
        else:
            s_t.append(np.nan); t_t.append(np.nan)
        rv = r[ranges[fi][1]]
        if rv.size:
            p05, p95 = np.percentile(rv, [5, 95])
            p05_t.append(float(p05)); p95_t.append(float(p95))
            near_far.append(float(p95 / p05) if p05 > 0 else np.nan)
        else:
            p05_t.append(np.nan); p95_t.append(np.nan); near_far.append(np.nan)
        if has_conf:
            c = reader.load_conf(fi)
            conf_t.append(float(np.nanmedian(np.asarray(c))) if c is not None else np.nan)

    # --- correspondence-based stability -----------------------------------
    fmeta_path = os.path.join(flow_root, clip, "flow.json")
    pairs, local, jitter, partition = [], [], [], {"static_anchored": [],
                                                   "static_reference_uncertain": [],
                                                   "dynamic": []}
    if os.path.exists(fmeta_path):
        for k in range(len(frames) - 1):
            t, t1 = frames[k], frames[k + 1]
            stem = os.path.join(flow_root, clip, f"p{t:06d}_{t1:06d}")
            if not os.path.exists(stem + "_flow.npy"):
                continue
            flow = np.load(stem + "_flow.npy")
            fvalid = np.load(stem + "_valid.npy")
            r_t, ok_t = ranges[t]
            r_t1, ok_t1 = ranges[t1]
            warped, ok_w = warp_to_t(np.where(ok_t1, r_t1, np.nan), flow)
            m = ok_t & ok_w & fvalid & np.isfinite(warped) & (warped > 0) & (r_t > 0)
            rec = {"t": int(t), "t1": int(t1), "n": int(m.sum())}
            if m.sum() >= 200:
                lr = np.log(warped[m]) - np.log(r_t[m])
                sigma = float(np.exp(np.median(lr)))
                resid = np.abs(lr - np.median(lr))
                rec["pairwise_scale_step"] = sigma
                rec["local_instability_median_dlog"] = float(np.median(resid))
                rec["local_instability_p95_dlog"] = float(np.percentile(resid, 95))
                local.append(rec["local_instability_median_dlog"])
                # boundary jitter at corresponding scene points
                e_t = M.geometric_edges(np.where(m, r_t, np.nan), m, thr)
                e_w = M.geometric_edges(np.where(m, warped, np.nan), m, thr)
                if e_t.any() and e_w.any():
                    from scipy import ndimage
                    d = ndimage.distance_transform_edt(~e_t)
                    rec["boundary_jitter_px"] = float(np.median(d[e_w]))
                    jitter.append(rec["boundary_jitter_px"])
                # the frozen epistemic partition
                ref_ok = cache[t]["ref_valid"]
                anch = fvalid & ref_ok & ok_t & ok_w
                unc = fvalid & (~ref_ok) & ok_t & ok_w
                dyn = (~fvalid) & ok_t & ok_w
                for key, sel in (("static_anchored", anch),
                                 ("static_reference_uncertain", unc),
                                 ("dynamic", dyn)):
                    if sel.sum() >= 200:
                        l2 = np.log(warped[sel]) - np.log(r_t[sel])
                        partition[key].append(
                            {"t": int(t), "n": int(sel.sum()),
                             "median_abs_dlog": float(np.median(np.abs(l2 - np.median(l2))))})
            pairs.append(rec)
            del flow, fvalid, warped
            gc.collect()

    s = np.asarray(s_t, dtype=np.float64)
    fin = np.isfinite(s) & (s > 0)
    out = {
        "status": "ok",
        "n_frames": len(frames),
        "alignment": fit.to_dict(),
        "edge_threshold_log": thr,
        "scale_t": [None if not np.isfinite(x) else float(x) for x in s],
        "shift_t": [None if not np.isfinite(x) else float(x) for x in t_t],
        "near_far_ratio_t": [None if not np.isfinite(x) else float(x) for x in near_far],
        "range_p05_t": p05_t, "range_p95_t": p95_t,
        "coverage_t": cov,
        "confidence_t": conf_t if has_conf else None,
        "pairs": pairs,
        "partition": {k: {"n_pairs": len(v),
                          "median_abs_dlog": (float(np.median([x["median_abs_dlog"] for x in v]))
                                              if v else float("nan"))}
                      for k, v in partition.items()},
    }
    if fin.sum() >= 2:
        ls = np.log(s[fin])
        out["scale_trajectory"] = {
            "median": float(np.exp(np.median(ls))),
            "log_std": float(np.std(ls)),
            "wander_ratio": float(np.exp(ls.max() - ls.min())),
            "frame_to_frame_log_mad": float(np.median(np.abs(np.diff(ls)))),
            "physical_implication": (
                "under ONE shared clip-level physical coefficient, absorbing s_t would "
                "require beta'_t = beta/s_t, i.e. water properties that change with the "
                "estimator. A wander_ratio materially above 1.0 is therefore a "
                "physical-model inconsistency, not a gauge."),
        }
    tv = np.asarray([x for x in t_t if x is not None and np.isfinite(x)], dtype=np.float64)
    if tv.size >= 2:
        out["shift_trajectory"] = {"median": float(np.median(tv)),
                                   "iqr": float(np.percentile(tv, 75) - np.percentile(tv, 25)),
                                   "range": float(tv.max() - tv.min())}
    nf = np.asarray([x for x in near_far if x is not None and np.isfinite(x)])
    if nf.size:
        out["near_far_trajectory"] = {"median": float(np.median(nf)),
                                      "min": float(nf.min()), "max": float(nf.max()),
                                      "wander_ratio": float(nf.max() / nf.min())
                                      if nf.min() > 0 else float("nan")}
    out["local_surface_stability"] = {
        "median_dlog": float(np.median(local)) if local else float("nan"),
        "p95_over_pairs": float(np.percentile(local, 95)) if local else float("nan"),
        "n_pairs": len(local),
        "meaning": ("|delta log range| at CORRESPONDING SCENE POINTS after removing the "
                    "pairwise global scalar; what is left cannot be scene motion and "
                    "cannot be a global gauge"),
    }
    out["boundary_jitter"] = {
        "median_px": float(np.median(jitter)) if jitter else float("nan"),
        "n_pairs": len(jitter),
    }
    out["coverage"] = {"median": float(np.median(cov)), "min": float(np.min(cov))}
    if has_conf and conf_t:
        c = np.asarray([x for x in conf_t if np.isfinite(x)])
        if c.size:
            out["confidence_trajectory"] = {"median": float(np.median(c)),
                                            "min": float(c.min()), "max": float(c.max())}
    del cache, ranges
    gc.collect()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arms", nargs="*", default=None)
    ap.add_argument("--clips", nargs="*", default=None)
    ap.add_argument("--root", default=os.path.join(common.OUTPUTS, "predictions"))
    ap.add_argument("--flow-root", default=os.path.join(common.OUTPUTS, "flow"))
    ap.add_argument("--policy", default=os.path.join(common.RESULTS,
                                                     "S2_alignment_policy.json"))
    ap.add_argument("--out", default=os.path.join(common.OUTPUTS, "s5", "s5_raw.json"))
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    pol = policy.Policy.load(args.policy)
    clips = args.clips or common.CLIPS
    models = [m for m in common.MODELS if monoio.exists(args.root, m, clips[0])]
    arms = args.arms or models

    result = {
        "_comment": ("S5 — independent-frame temporal stability. Every frame was inferred "
                     "independently; the sequence is used only after inference. SEA-RAFT "
                     "flow supplies correspondence for evaluation ONLY and never reaches a "
                     "depth model."),
        "stage": "S5", "clips": clips, "arms": {},
    }
    for arm in arms:
        rec = {"arm": arm, "role": armio.arm_role(arm), "clips": {}}
        for clip in clips:
            if not monoio.exists(args.root, armio.arm_model(arm), clip):
                rec["clips"][clip] = {"status": "missing"}
                continue
            r = analyse(arm, clip, args.root, args.flow_root, pol)
            rec["clips"][clip] = r
            if r.get("status") == "ok":
                st = r.get("scale_trajectory", {})
                print(f"[S5] {arm:22s} {clip:15s} "
                      f"s_med={st.get('median', float('nan')):.4f} "
                      f"wander={st.get('wander_ratio', float('nan')):.3f} "
                      f"f2f={st.get('frame_to_frame_log_mad', float('nan')):.4f} "
                      f"local={r['local_surface_stability']['median_dlog']:.4f} "
                      f"jit={r['boundary_jitter']['median_px']:.2f}px "
                      f"nf={r.get('near_far_trajectory', {}).get('wander_ratio', float('nan')):.2f} "
                      f"cov={r['coverage']['median']:.3f}")
        result["arms"][arm] = rec
        common.write_json(args.out, result, overwrite=True)
    common.write_json(args.out, result, overwrite=True)
    print(f"[S5] -> {os.path.relpath(args.out, REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
