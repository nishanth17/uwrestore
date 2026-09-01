"""Stage 6 — cross-family geometry comparison.

EXPLORATORY. Main project venv (numpy only). This is the part of Phase 3A that
actually answers the question, so every choice it makes is one the design
document argued for:

* ONE global scale per (method-pair, clip), fitted over observations POOLED
  across every frame. Per-frame scale fits are computed too, but only as a
  drift diagnostic — never fed back into a residual.
* Dense-vs-sparse correspondence is by IMAGE OBSERVATION, never by 3D nearest
  neighbour between two independently-posed point clouds.
* Source-pixel -> model-grid mapping comes from `outputs/preprocess_maps.json`,
  which was MEASURED by pushing markers through each model's own preprocessing.
* Sparse-vs-sparse correspondence is by 2D proximity within the same image,
  which is again an image observation, not a 3D match.
* No reference is treated as truth. Every dense method is reported separately
  against ordinary SfM and against refractive SfM, and the two are never merged.

Usage:
    .venv/bin/python -m experiments.week3_geometry.scripts.compare \
        --out experiments/week3_geometry/outputs/stage6/comparison.json
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

from experiments.week3_geometry.geometry import (  # noqa: E402
    binned_profile,
    fit_global_scale,
    image_radius,
    relative_errors,
    robust_stats,
    sample_at_observations,
)
from experiments.week3_geometry.rangeio import RangeReader  # noqa: E402
from experiments.week3_geometry.scripts.run_colmap import (  # noqa: E402
    parse_cameras_txt,
    parse_images_txt,
    parse_points3d_txt,
)

W3 = os.path.join(REPO_ROOT, "experiments", "week3_geometry")
COLMAP_ROOT = os.path.join(W3, "outputs", "colmap")
RANGE_ROOT = os.path.join(W3, "outputs", "range")
PREPROC = os.path.join(W3, "outputs", "preprocess_maps.json")

CLASSICAL = ["A", "B", "C_off", "C_on"]
DENSE = {"D_mapanything": "mapanything", "E0_vggt": "vggt", "E_wat3r_ren": "wat3r_ren"}

RADIUS_EDGES = np.linspace(0.0, 1.3, 8)


# --------------------------------------------------------------------------
# Classical reconstruction -> per-image observations with a reference range
# --------------------------------------------------------------------------

def load_classical(config: str, clip: str, repeat: int = 0):
    txt = os.path.join(COLMAP_ROOT, config, clip, f"run{repeat}", "sparse_txt")
    if not os.path.isdir(txt):
        return None
    cams = parse_cameras_txt(os.path.join(txt, "cameras.txt"))
    imgs = parse_images_txt(os.path.join(txt, "images.txt"))
    pts = parse_points3d_txt(os.path.join(txt, "points3D.txt"))
    return {"cameras": cams, "images": imgs, "points": pts}


def _T_cw(qwxyz, t):
    qw, qx, qy, qz = qwxyz
    R = np.array([
        [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)],
        [2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)],
        [2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)],
    ], dtype=np.float64)
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = np.asarray(t, dtype=np.float64)
    return T


def classical_observations(model: dict) -> dict:
    """{frame_index: {'uv': (N,2) source pixels, 'range': (N,), 'track_len': (N,)}}.

    The reference range is ||X_cam||, the Euclidean distance from the
    reconstruction's projection centre to the triangulated point — NOT z-depth.
    For the refractive configuration this is the distance from the model's
    virtual centre; see the water-path bound reported alongside, which is what
    stops that from being quietly called a water path.
    """
    out = {}
    pts = model["points"]
    for img in model["images"].values():
        idx = int(img["name"][1:7])          # f000008.png -> 8
        T = _T_cw(img["qvec_wxyz_cw"], img["tvec_cw"])
        uv, rng, tl = [], [], []
        for (u, v, pid) in img["observations"]:
            p = pts.get(pid)
            if p is None:
                continue
            X = np.asarray(p["xyz"], dtype=np.float64)
            Xc = T[:3, :3] @ X + T[:3, 3]
            if Xc[2] <= 0:
                continue                      # behind the camera: not an observation
            uv.append([u, v])
            rng.append(float(np.linalg.norm(Xc)))
            tl.append(p["track_len"])
        if uv:
            out[idx] = {"uv": np.asarray(uv), "range": np.asarray(rng),
                        "track_len": np.asarray(tl)}
    return out


# --------------------------------------------------------------------------
# Source pixels -> a dense model's inference grid
# --------------------------------------------------------------------------

def load_preprocess_maps() -> dict:
    with open(PREPROC) as fh:
        return json.load(fh)


def map_to_grid(uv: np.ndarray, m: dict) -> np.ndarray:
    """Apply the MEASURED affine source->model-grid map."""
    out = np.empty_like(uv, dtype=np.float64)
    out[:, 0] = m["u_scale"] * uv[:, 0] + m["u_offset"]
    out[:, 1] = m["v_scale"] * uv[:, 1] + m["v_offset"]
    return out


# --------------------------------------------------------------------------
# Dense vs sparse
# --------------------------------------------------------------------------

def dense_vs_sparse(dense_cfg: str, family: str, classical_cfg: str, clip: str,
                    maps: dict, min_track_len: int = 3) -> dict | None:
    model = load_classical(classical_cfg, clip)
    if model is None:
        return None
    try:
        reader = RangeReader(RANGE_ROOT, dense_cfg, clip)
    except FileNotFoundError:
        return None
    obs = classical_observations(model)
    src_hw = None
    for c in model["cameras"].values():
        src_hw = (c["height"], c["width"])
    key = f"{src_hw[0]}x{src_hw[1]}"
    if family not in maps or key not in maps[family]:
        return {"dense": dense_cfg, "reference": classical_cfg, "clip": clip,
                "error": f"no measured preprocess map for {family} {key}"}
    m = maps[family][key]

    est_by_frame, ref_by_frame = {}, {}
    est_all, ref_all, rad_all, conf_all = [], [], [], []
    n_offered = n_used = 0
    for idx in reader.frame_indices:
        o = obs.get(idx)
        if o is None:
            continue
        keep = o["track_len"] >= min_track_len
        uv, ref = o["uv"][keep], o["range"][keep]
        if uv.size == 0:
            continue
        n_offered += len(ref)
        rng, valid, conf = reader.load(idx, want_conf=True)
        rng = np.asarray(rng, dtype=np.float64)
        valid = np.asarray(valid, dtype=bool)
        uvg = map_to_grid(uv, m)
        vals, ok = sample_at_observations(rng, valid, uvg)
        if not ok.any():
            continue
        n_used += int(ok.sum())
        est_by_frame[idx] = vals[ok]
        ref_by_frame[idx] = ref[ok]
        est_all.append(vals[ok])
        ref_all.append(ref[ok])
        rad_all.append(image_radius(uv[ok], src_hw))
        if conf is not None:
            # Sample the model's own confidence at the SAME observations, so
            # "does low confidence predict high error?" is asked pixel-for-pixel
            # rather than frame-for-frame.
            cf = np.asarray(conf, dtype=np.float64)
            cvals, cok = sample_at_observations(cf, np.isfinite(cf), uvg)
            conf_all.append(np.where(ok, cvals, np.nan)[ok])
        else:
            conf_all.append(np.full(int(ok.sum()), np.nan))

    if not est_all:
        return {"dense": dense_cfg, "reference": classical_cfg, "clip": clip,
                "error": "no eligible observations", "n_offered": n_offered}
    est = np.concatenate(est_all)
    ref = np.concatenate(ref_all)
    rad = np.concatenate(rad_all)

    fit = fit_global_scale(est, ref)                 # ONE scale for the whole clip
    err = relative_errors(est, ref, fit.scale)

    # Per-frame scale fits: DIAGNOSTIC ONLY, never used to rescale a residual.
    per_frame = {}
    for k in sorted(est_by_frame):
        f = fit_global_scale(est_by_frame[k], ref_by_frame[k])
        if np.isfinite(f.scale):
            per_frame[k] = f.scale
    scales = np.array(list(per_frame.values())) if per_frame else np.array([])

    ref_edges = np.percentile(ref[np.isfinite(ref)], np.linspace(0, 100, 7))

    # Confidence calibration. A learned confidence trained on other data is not
    # calibrated for underwater input by default -- for vanilla VGGT the input is
    # out of domain by construction -- so this asks whether it carries ANY signal
    # about error on this footage, and reports it as a monotone relationship
    # rather than as a fitted probability.
    conf = np.concatenate(conf_all) if conf_all else np.full(est.size, np.nan)
    calib = {"has_confidence": bool(np.isfinite(conf).any())}
    if calib["has_confidence"]:
        good = np.isfinite(conf) & np.isfinite(err)
        c, e = conf[good], np.abs(err[good])
        if c.size > 100:
            qs = np.percentile(c, [0, 20, 40, 60, 80, 100])
            calib["abs_error_by_confidence_quintile"] = [
                {"conf_lo": float(lo), "conf_hi": float(hi),
                 **robust_stats(e[(c >= lo) & (c < hi)] if hi < qs[-1]
                                else e[(c >= lo) & (c <= hi)])}
                for lo, hi in zip(qs[:-1], qs[1:])]
            lo_q = calib["abs_error_by_confidence_quintile"][0]["median"]
            hi_q = calib["abs_error_by_confidence_quintile"][-1]["median"]
            calib["lowest_over_highest_confidence_median_abs_error"] = (
                float(lo_q / hi_q) if hi_q > 0 else float("nan"))
            calib["verdict_note"] = ("> 1 means the model's low-confidence pixels "
                                     "really are its worse ones; ~1 means the "
                                     "confidence carries no usable error signal on "
                                     "this footage.")
    return {
        "dense": dense_cfg,
        "reference": classical_cfg,
        "clip": clip,
        "n_observations_offered": n_offered,
        "n_observations_used": n_used,
        "coverage_fraction": round(n_used / n_offered, 4) if n_offered else 0.0,
        "min_track_length": min_track_len,
        "global_scale": fit.scale,
        "global_scale_fit": {"method": fit.method, "n_used": fit.n_used,
                             "log_residual_mad": fit.log_residual_mad},
        "relative_error": robust_stats(err),
        "abs_relative_error": robust_stats(np.abs(err)),
        "residual_vs_image_radius": binned_profile(rad, err, RADIUS_EDGES),
        "residual_vs_reference_range": binned_profile(ref, err, ref_edges),
        "reference_range_percentiles": [float(x) for x in ref_edges],
        "confidence_calibration": calib,
        "radius_x_range_interaction": radius_profiles_by_range_bin(rad, ref, err, ref_edges),
        "per_frame_scale_diagnostic": {
            "n_frames": len(per_frame),
            "min": float(scales.min()) if scales.size else float("nan"),
            "max": float(scales.max()) if scales.size else float("nan"),
            "max_over_min": float(scales.max() / scales.min()) if scales.size and scales.min() > 0 else float("nan"),
            "trace": {str(k): float(v) for k, v in per_frame.items()},
            "note": ("DIAGNOSTIC ONLY. These were never used to normalise the "
                     "residuals above; a large max/min means the clip-level scale "
                     "cannot describe the whole clip, i.e. scale drift."),
        },
    }


# --------------------------------------------------------------------------
# Dense vs dense
# --------------------------------------------------------------------------

def dense_vs_dense(cfg_a: str, fam_a: str, cfg_b: str, fam_b: str, clip: str,
                   maps: dict, stride: int = 4) -> dict | None:
    try:
        ra = RangeReader(RANGE_ROOT, cfg_a, clip)
        rb = RangeReader(RANGE_ROOT, cfg_b, clip)
    except FileNotFoundError:
        return None
    common = sorted(set(ra.frame_indices) & set(rb.frame_indices))
    if not common:
        return None
    src_hw = tuple(json.load(open(os.path.join(W3, "outputs", "frames",
                                               "extraction_report.json")))
                   ["clips"][clip]["extracted_shape_hw"])
    key = f"{src_hw[0]}x{src_hw[1]}"
    ma, mb = maps[fam_a][key], maps[fam_b][key]

    a_all, b_all, rad_all = [], [], []
    a_by_frame, b_by_frame = {}, {}
    for idx in common:
        Ra, Va = ra.load(idx)
        Rb, Vb = rb.load(idx)
        ha, wa = np.asarray(Ra).shape
        # Walk A's grid, invert A's map to source pixels, then apply B's map.
        vv, uu = np.meshgrid(np.arange(0, ha, stride, dtype=np.float64),
                             np.arange(0, wa, stride, dtype=np.float64), indexing="ij")
        uv_a = np.stack([uu.ravel(), vv.ravel()], axis=1)
        uv_src = np.empty_like(uv_a)
        uv_src[:, 0] = (uv_a[:, 0] - ma["u_offset"]) / ma["u_scale"]
        uv_src[:, 1] = (uv_a[:, 1] - ma["v_offset"]) / ma["v_scale"]
        uv_b = map_to_grid(uv_src, mb)

        va, oka = sample_at_observations(np.asarray(Ra, np.float64),
                                         np.asarray(Va, bool), uv_a)
        vb, okb = sample_at_observations(np.asarray(Rb, np.float64),
                                         np.asarray(Vb, bool), uv_b)
        ok = oka & okb
        if not ok.any():
            continue
        a_by_frame[idx] = va[ok]
        b_by_frame[idx] = vb[ok]
        a_all.append(va[ok])
        b_all.append(vb[ok])
        rad_all.append(image_radius(uv_src[ok], src_hw))

    if not a_all:
        return {"a": cfg_a, "b": cfg_b, "clip": clip, "error": "no co-valid pixels"}
    a = np.concatenate(a_all)
    b = np.concatenate(b_all)
    rad = np.concatenate(rad_all)
    fit = fit_global_scale(a, b)
    err = relative_errors(a, b, fit.scale)
    per_frame = {}
    for k in sorted(a_by_frame):
        f = fit_global_scale(a_by_frame[k], b_by_frame[k])
        if np.isfinite(f.scale):
            per_frame[k] = f.scale
    scales = np.array(list(per_frame.values())) if per_frame else np.array([])
    b_edges = np.percentile(b[np.isfinite(b)], np.linspace(0, 100, 7))
    return {
        "a": cfg_a, "b": cfg_b, "clip": clip,
        "n_frames": len(a_by_frame),
        "n_pixels": int(a.size),
        "sample_stride_on_a_grid": stride,
        "global_scale_a_to_b": fit.scale,
        "global_scale_fit": {"n_used": fit.n_used, "log_residual_mad": fit.log_residual_mad},
        "relative_error": robust_stats(err),
        "abs_relative_error": robust_stats(np.abs(err)),
        "residual_vs_image_radius": binned_profile(rad, err, RADIUS_EDGES),
        "residual_vs_b_range": binned_profile(b, err, b_edges),
        "per_frame_scale_diagnostic": {
            "min": float(scales.min()) if scales.size else float("nan"),
            "max": float(scales.max()) if scales.size else float("nan"),
            "max_over_min": float(scales.max() / scales.min()) if scales.size and scales.min() > 0 else float("nan"),
            "trace": {str(k): float(v) for k, v in per_frame.items()},
            "note": "DIAGNOSTIC ONLY -- not used to normalise the residuals above.",
        },
    }


# --------------------------------------------------------------------------
# Sparse vs sparse (ordinary vs refractive; and A vs the fork's OFF mode)
# --------------------------------------------------------------------------

def sparse_vs_sparse(cfg_a: str, cfg_b: str, clip: str, rep_a: int = 0, rep_b: int = 0,
                     max_px: float = 1.0) -> dict | None:
    ma, mb = load_classical(cfg_a, clip, rep_a), load_classical(cfg_b, clip, rep_b)
    if ma is None or mb is None:
        return None
    oa, ob = classical_observations(ma), classical_observations(mb)
    common = sorted(set(oa) & set(ob))
    if not common:
        return None
    ra_all, rb_all, rad_all = [], [], []
    a_by_frame, b_by_frame = {}, {}
    src_hw = None
    for c in ma["cameras"].values():
        src_hw = (c["height"], c["width"])
    for idx in common:
        A, B = oa[idx], ob[idx]
        # Correspondence by 2D proximity WITHIN THE SAME IMAGE: an image
        # observation match, not a 3D nearest neighbour between point clouds.
        d = np.linalg.norm(A["uv"][:, None, :] - B["uv"][None, :, :], axis=2)
        j = d.argmin(axis=1)
        ok = d[np.arange(len(j)), j] <= max_px
        if not ok.any():
            continue
        a_by_frame[idx] = A["range"][ok]
        b_by_frame[idx] = B["range"][j[ok]]
        ra_all.append(A["range"][ok])
        rb_all.append(B["range"][j[ok]])
        rad_all.append(image_radius(A["uv"][ok], src_hw))
    if not ra_all:
        return {"a": f"{cfg_a}/run{rep_a}", "b": f"{cfg_b}/run{rep_b}", "clip": clip,
                "error": "no matched observations"}
    a = np.concatenate(ra_all)
    b = np.concatenate(rb_all)
    rad = np.concatenate(rad_all)
    fit = fit_global_scale(a, b)
    err = relative_errors(a, b, fit.scale)
    b_edges = np.percentile(b[np.isfinite(b)], np.linspace(0, 100, 7))
    per_frame = {}
    for k in sorted(a_by_frame):
        f = fit_global_scale(a_by_frame[k], b_by_frame[k])
        if np.isfinite(f.scale):
            per_frame[k] = f.scale
    scales = np.array(list(per_frame.values())) if per_frame else np.array([])
    return {
        "a": f"{cfg_a}/run{rep_a}", "b": f"{cfg_b}/run{rep_b}", "clip": clip,
        "n_frames": len(a_by_frame), "n_matched_observations": int(a.size),
        "match_max_px": max_px,
        "global_scale_a_to_b": fit.scale,
        "relative_error": robust_stats(err),
        "abs_relative_error": robust_stats(np.abs(err)),
        "residual_vs_image_radius": binned_profile(rad, err, RADIUS_EDGES),
        "residual_vs_b_range": binned_profile(b, err, b_edges),
        "radius_x_range_interaction": radius_profiles_by_range_bin(rad, b, err, b_edges),
        "per_frame_scale_diagnostic": {
            "min": float(scales.min()) if scales.size else float("nan"),
            "max": float(scales.max()) if scales.size else float("nan"),
            "max_over_min": float(scales.max() / scales.min()) if scales.size and scales.min() > 0 else float("nan"),
        },
    }



def radius_profiles_by_range_bin(rad, ref, err, ref_edges) -> dict:
    """The refraction discriminator: is the radius profile stable across range?

    `PLAN.md`: flat-port refractive model error is a joint function of image
    radius AND range; ordinary lens distortion is a function of radius alone. So
    bin the residual by radius separately WITHIN each range bin and look at
    whether the radius profile moves. A radius trend that is identical in every
    range bin has been absorbed by the intrinsics; one that changes with range
    has not.
    """
    profiles = []
    for lo, hi in zip(ref_edges[:-1], ref_edges[1:]):
        m = (ref >= lo) & (ref < hi)
        if m.sum() < 200:
            continue
        profiles.append(binned_profile(rad[m], err[m], RADIUS_EDGES))
    inter = radius_range_interaction(profiles)
    inter["profiles"] = profiles
    return inter

def radius_range_interaction(profile_by_range_bin: list) -> dict:
    """Is the radius profile stable across range bins? The refraction signature.

    Pure lens distortion is a function of image radius alone. Flat-port
    refractive error is a joint function of radius AND range. This reports the
    spread of the per-range-bin radius slopes, which is what separates them.
    """
    slopes = []
    for prof in profile_by_range_bin:
        xs = np.array([(p["lo"] + p["hi"]) / 2 for p in prof if p["n"] > 30])
        ys = np.array([p["median"] for p in prof if p["n"] > 30])
        if xs.size >= 3 and np.isfinite(ys).all():
            slopes.append(float(np.polyfit(xs, ys, 1)[0]))
    if len(slopes) < 2:
        return {"n_range_bins_with_a_slope": len(slopes),
                "verdict": "insufficient data to test a radius x range interaction"}
    return {
        "n_range_bins_with_a_slope": len(slopes),
        "radius_slope_per_range_bin": slopes,
        "slope_mean": float(np.mean(slopes)),
        "slope_spread_max_minus_min": float(np.max(slopes) - np.min(slopes)),
    }


# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--clips", nargs="*", default=None)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    if os.path.exists(args.out) and not args.overwrite:
        raise SystemExit(f"refusing to overwrite {args.out!r} (pass --overwrite)")

    spec = json.load(open(os.path.join(W3, "configs", "phase3a_clips.json")))
    clips = args.clips or [c["id"] for c in spec["clips"]]
    maps = load_preprocess_maps()

    out = {
        "_comment": ("Stage 6 cross-family comparison. Every dense method is reported "
                     "SEPARATELY against ordinary sparse SfM and against refractive "
                     "sparse SfM; the two are never merged, and NEITHER is ground "
                     "truth. All residuals use ONE global scale per method-pair per "
                     "clip; per-frame scale fits appear only as drift diagnostics. "
                     "Cross-method agreement here is CONSISTENCY evidence, not "
                     "correctness evidence -- there is no independent C2 measurement."),
        "clips": clips,
        "dense_vs_sparse": [],
        "dense_vs_dense": [],
        "sparse_vs_sparse": [],
        "classical_summary": [],
        "dense_summary": [],
    }

    # ---- classical registration / reproducibility summary ------------------
    for cfg in CLASSICAL:
        for clip in clips:
            for rep in range(3):
                p = os.path.join(COLMAP_ROOT, cfg, clip, f"run{rep}", "run.json")
                if not os.path.exists(p):
                    continue
                r = json.load(open(p))
                row = {"config": cfg, "clip": clip, "repeat": rep,
                       "failed_at": r.get("failed_at"),
                       "seconds": r.get("total_seconds"),
                       "peak_rss_gb": r.get("peak_rss_gb"),
                       # Fragmentation is evidence: a run registering 48 images
                       # across four disjoint sub-models has not reconstructed
                       # the clip. Only the largest is evaluated; all are shown.
                       "submodel_registered_images": r.get("submodel_registered_images")}
                if "result" in r:
                    res = r["result"]
                    cam = next(iter(res["cameras"].values()), {})
                    row.update({
                        "registered": res["registered_images"],
                        "registered_fraction": res["registered_fraction"],
                        "n_points3D": res["n_points3D"],
                        "mean_track_length": round(res["mean_track_length"], 3),
                        "mean_obs_per_image": round(res["mean_observations_per_image"], 1),
                        "mean_reproj_px_DIAGNOSTIC_ONLY": round(
                            res["mean_reprojection_error_px"], 4),
                        "camera_model": cam.get("model"),
                        "focal_px": round(cam.get("params", [float("nan")])[0], 2)
                        if cam.get("params") else None,
                        "refrac_model": cam.get("refrac_model"),
                    })
                out["classical_summary"].append(row)

    # ---- dense coverage / stability summary --------------------------------
    for cfg in DENSE:
        for clip in clips:
            try:
                rd = RangeReader(RANGE_ROOT, cfg, clip)
            except FileNotFoundError:
                continue
            vf = np.array([f["valid_fraction"] for f in rd.meta["frames"]])
            med = np.array([f["range_median"] for f in rd.meta["frames"]])
            p05 = np.array([f["range_p05"] for f in rd.meta["frames"]])
            p95 = np.array([f["range_p95"] for f in rd.meta["frames"]])
            prov = rd.meta["provenance"]
            out["dense_summary"].append({
                "config": cfg, "clip": clip,
                "n_frames": rd.meta["n_frames"],
                "inference_grid_hw": prov.get("inference_resolution_hw"),
                "valid_fraction": {"median": float(np.median(vf)),
                                   "min": float(vf.min()), "max": float(vf.max())},
                "per_frame_median_range": {"median": float(np.nanmedian(med)),
                                           "min": float(np.nanmin(med)),
                                           "max": float(np.nanmax(med))},
                "median_range_frame_to_frame_relative_step": float(
                    np.median(np.abs(np.diff(med)) / med[:-1])) if med.size > 1 else float("nan"),
                "median_range_drift_max_over_min": float(np.nanmax(med) / np.nanmin(med))
                if np.nanmin(med) > 0 else float("nan"),
                "near_far_spread_p95_over_p05": float(np.nanmedian(p95 / p05)),
                "seconds": prov.get("seconds"),
                "peak_mps_driver_gb": prov.get("peak_mps_driver_gb"),
                "scale_convention": rd.meta["scale_convention"],
                "note": ("per_frame_median_range drift and the frame-to-frame step are "
                         "TEMPORAL stability signals on the raw product; no per-frame "
                         "normalisation has been applied anywhere."),
            })

    # ---- dense vs sparse ---------------------------------------------------
    for dcfg, fam in DENSE.items():
        for ccfg in CLASSICAL:
            for clip in clips:
                r = dense_vs_sparse(dcfg, fam, ccfg, clip, maps)
                if r:
                    out["dense_vs_sparse"].append(r)

    # ---- dense vs dense ----------------------------------------------------
    pairs = [("E0_vggt", "vggt", "E_wat3r_ren", "wat3r_ren"),        # the adaptation axis
             ("D_mapanything", "mapanything", "E0_vggt", "vggt"),
             ("D_mapanything", "mapanything", "E_wat3r_ren", "wat3r_ren")]
    for a, fa, b, fb in pairs:
        for clip in clips:
            r = dense_vs_dense(a, fa, b, fb, clip, maps)
            if r:
                out["dense_vs_dense"].append(r)

    # ---- sparse vs sparse --------------------------------------------------
    for a, b in [("C_off", "C_on"), ("A", "C_off"), ("A", "B")]:
        for clip in clips:
            r = sparse_vs_sparse(a, b, clip)
            if r:
                out["sparse_vs_sparse"].append(r)
    # repeat-run spread, the bar any refraction claim must clear
    for cfg in ("C_off", "C_on", "A"):
        for clip in clips:
            for rep in (1, 2):
                r = sparse_vs_sparse(cfg, cfg, clip, rep_a=0, rep_b=rep)
                if r:
                    r["kind"] = "repeat_run_spread"
                    out["sparse_vs_sparse"].append(r)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"wrote {args.out}: "
          f"{len(out['classical_summary'])} classical runs, "
          f"{len(out['dense_summary'])} dense runs, "
          f"{len(out['dense_vs_sparse'])} dense-vs-sparse, "
          f"{len(out['dense_vs_dense'])} dense-vs-dense, "
          f"{len(out['sparse_vs_sparse'])} sparse-vs-sparse")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
