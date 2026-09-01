"""Phase 3B — structure, conditioning and shape metrics for a classical run.

EXPLORATORY. Main project venv (numpy only).

Phase 3A's `run.json` already reports registration, point count, mean track
length and observations per image. Phase 3B's hypotheses all turn on quantities
it does NOT report:

* **triangulation angle** per 3D point — the actual conditioning of the depth
  estimate. Registration says the cameras can be related to each other; it says
  nothing about whether depth is observable. This is the number 3B-1 and 3B-4
  are really about.
* **temporal span** per track, and long-baseline track survival — a track seen in
  20 consecutive frames of a 60 fps clip is not the same evidence as a track seen
  across the whole sweep.
* **track-length distribution**, not just the mean. Phase 3A's "+17-75 % mean
  track length" could be a shifted body or a heavier tail, and those imply
  different things.
* **front-end yield** from the database: features, putative matches, verified
  matches, inlier ratio.

Plus the one comparison that decides whether any of it matters: the scale-aligned
sparse-vs-sparse **shape** residual at co-visible image observations, with the
residual profiled against range and against image radius.

Everything obeys the Phase 3A comparison invariants: exactly one global scale per
pair per clip, correspondence by image observation within the same image (never a
3D nearest neighbour between independently-posed clouds), per-frame scale fits as
a drift diagnostic only, and no reference treated as truth.

This is a library plus a small CLI; it is imported by `analyze.py`.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week3_geometry.geometry import (  # noqa: E402
    binned_profile,
    fit_global_scale,
    image_radius,
    relative_errors,
    robust_stats,
)
from experiments.week3_geometry.scripts.compare import (  # noqa: E402
    _T_cw,
    classical_observations,
    radius_profiles_by_range_bin,
)
from experiments.week3_geometry.scripts.run_colmap import (  # noqa: E402
    parse_cameras_txt,
    parse_images_txt,
    parse_points3d_txt,
)

RADIUS_EDGES = np.linspace(0.0, 1.3, 8)
# Track temporal span is measured in SOURCE frame indices, which is what the
# extracted filenames carry, so a span means the same thing on a 29.97 fps clip
# and a 59.94 fps one only after dividing by fps. Both are reported.
SPAN_FRACTIONS = (0.10, 0.25, 0.50)


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

def load_model_dir(txt_dir: str) -> dict | None:
    """Load a COLMAP model from a `sparse_txt`-style directory."""
    if not os.path.isdir(txt_dir):
        return None
    need = ["cameras.txt", "images.txt", "points3D.txt"]
    if not all(os.path.exists(os.path.join(txt_dir, n)) for n in need):
        return None
    return {
        "cameras": parse_cameras_txt(os.path.join(txt_dir, "cameras.txt")),
        "images": parse_images_txt(os.path.join(txt_dir, "images.txt")),
        "points": parse_points3d_txt(os.path.join(txt_dir, "points3D.txt")),
    }


def load_run(run_dir: str) -> dict | None:
    """Load a run directory: `run.json` plus the model in `sparse_txt/`."""
    rj = os.path.join(run_dir, "run.json")
    if not os.path.exists(rj):
        return None
    with open(rj) as fh:
        report = json.load(fh)
    return {"run_dir": run_dir, "report": report,
            "model": load_model_dir(os.path.join(run_dir, "sparse_txt")),
            "database": os.path.join(run_dir, "database.db")}


# --------------------------------------------------------------------------
# Front-end yield, read from the database
# --------------------------------------------------------------------------

def database_metrics(db_path: str) -> dict:
    """Features, putative matches, verified matches, inlier ratio.

    Read-only, on whatever database the run actually used. `matches` holds the
    putative correspondences; `two_view_geometries` holds the ones that survived
    geometric verification, so their ratio is the front end's inlier rate.
    """
    if not os.path.exists(db_path):
        return {"available": False}
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        n_images = con.execute("SELECT COUNT(*) FROM images").fetchone()[0]
        kp = con.execute("SELECT COUNT(*), SUM(rows) FROM keypoints").fetchone()
        mt = con.execute("SELECT COUNT(*), SUM(rows) FROM matches WHERE rows > 0").fetchone()
        tv = con.execute("SELECT COUNT(*), SUM(rows) FROM two_view_geometries "
                         "WHERE rows > 0").fetchone()
        cams = con.execute("SELECT camera_id, model, width, height, params, "
                           "prior_focal_length FROM cameras").fetchall()
    finally:
        con.close()
    n_match_pairs, n_matches = (mt[0] or 0), (mt[1] or 0)
    n_ver_pairs, n_inliers = (tv[0] or 0), (tv[1] or 0)
    cam_rows = []
    for cid, model, w, h, blob, prior in cams:
        vals = list(struct_unpack_doubles(blob))
        cam_rows.append({"camera_id": cid, "model_id": model, "width": w, "height": h,
                         "params": vals, "prior_focal_length": bool(prior)})
    return {
        "available": True,
        "n_images": n_images,
        "n_images_with_keypoints": kp[0] or 0,
        "n_keypoints_total": kp[1] or 0,
        "keypoints_per_image": round((kp[1] or 0) / n_images, 1) if n_images else 0.0,
        "n_pairs_with_putative_matches": n_match_pairs,
        "n_putative_matches": n_matches,
        "n_pairs_geometrically_verified": n_ver_pairs,
        "n_verified_matches": n_inliers,
        "verified_over_putative_matches": (round(n_inliers / n_matches, 4)
                                           if n_matches else float("nan")),
        "verified_over_putative_pairs": (round(n_ver_pairs / n_match_pairs, 4)
                                         if n_match_pairs else float("nan")),
        "database_cameras_at_initialisation": cam_rows,
        "note": ("verified_over_putative_* is the front end's own inlier rate: COLMAP's "
                 "`matches` table holds putative correspondences and `two_view_geometries` "
                 "holds the ones that survived geometric verification. It is a "
                 "correspondence-quality signal, NOT a geometry-quality signal."),
    }


def struct_unpack_doubles(blob) -> tuple:
    import struct
    if blob is None:
        return ()
    return struct.unpack("<%dd" % (len(blob) // 8), blob)


# --------------------------------------------------------------------------
# Structure and conditioning
# --------------------------------------------------------------------------

def _camera_centres(model: dict) -> dict:
    """image_id -> camera centre in world coordinates, C = -R_cw^T t_cw."""
    out = {}
    for img_id, img in model["images"].items():
        T = _T_cw(img["qvec_wxyz_cw"], img["tvec_cw"])
        R, t = T[:3, :3], T[:3, 3]
        out[img_id] = -R.T @ t
    return out


def _frame_index(name: str) -> int:
    """`f000008.png` -> 8. The SOURCE frame index, preserved by extraction."""
    return int(name[1:7])


def sparse_structure_metrics(model: dict, n_offered: int | None = None) -> dict:
    """Track statistics, triangulation angles and temporal-span statistics.

    The triangulation angle of a 3D point is the LARGEST angle subtended at that
    point by any two of the cameras that observe it. That is COLMAP's own
    definition and it is the honest conditioning number: a point seen by forty
    cameras that are all in nearly the same place is one observation, however
    long its track.
    """
    pts = model["points"]
    imgs = model["images"]
    centres = _camera_centres(model)
    frame_of = {i: _frame_index(im["name"]) for i, im in imgs.items()}

    # point_id -> list of observing image ids (points3D.txt track, re-read here
    # because parse_points3d_txt keeps only the length).
    track_imgs: dict[int, list[int]] = {pid: [] for pid in pts}
    for img_id, img in imgs.items():
        for (_u, _v, pid) in img["observations"]:
            if pid in track_imgs:
                track_imgs[pid].append(img_id)

    track_len, tri_ang, span_frames, base_over_depth = [], [], [], []
    for pid, p in pts.items():
        obs = track_imgs[pid]
        if len(obs) < 2:
            continue
        X = np.asarray(p["xyz"], dtype=np.float64)
        C = np.array([centres[i] for i in obs], dtype=np.float64)
        V = X[None, :] - C
        n = np.linalg.norm(V, axis=1)
        good = n > 1e-12
        if good.sum() < 2:
            continue
        U = V[good] / n[good][:, None]
        cos = np.clip(U @ U.T, -1.0, 1.0)
        ang = float(np.degrees(np.arccos(cos.min())))
        tri_ang.append(ang)
        track_len.append(len(obs))
        fr = [frame_of[i] for i in obs]
        span_frames.append(max(fr) - min(fr))
        # Baseline / depth: the same conditioning fact in a linear unit.
        # 2 * sin(theta/2) is exact for the max-baseline pair at equal ranges;
        # the direct max pairwise baseline over median range is used instead so
        # it stays interpretable when ranges differ across the track.
        Cg = C[good]
        d = np.linalg.norm(Cg[:, None, :] - Cg[None, :, :], axis=2)
        base_over_depth.append(float(d.max() / np.median(n[good])))

    track_len = np.asarray(track_len, dtype=np.float64)
    tri_ang = np.asarray(tri_ang, dtype=np.float64)
    span_frames = np.asarray(span_frames, dtype=np.float64)
    bod = np.asarray(base_over_depth, dtype=np.float64)

    frames = sorted(frame_of.values())
    clip_span = (max(frames) - min(frames)) if frames else 0
    survival = {}
    for f in SPAN_FRACTIONS:
        thr = f * clip_span
        survival[f"frac_tracks_spanning_ge_{int(f * 100)}pct_of_clip"] = (
            float((span_frames >= thr).mean()) if span_frames.size else float("nan"))

    def pcts(a, qs=(5, 25, 50, 75, 90, 95, 99)):
        if a.size == 0:
            return {}
        return {f"p{q}": float(np.percentile(a, q)) for q in qs}

    cam = next(iter(model["cameras"].values()), {})
    obs_per_img = np.array([im["n_observations_2d"] for im in imgs.values()], dtype=np.float64)

    # Degeneracy screen. A reconstruction can "succeed" -- register every frame,
    # report a fine reprojection error -- while placing cameras on top of the
    # structure, which shows up as observation ranges orders of magnitude below
    # the clip median. That corrupts every shape statistic downstream while
    # leaving the MEDIAN residual looking healthy, so it has to be measured
    # rather than noticed by accident.
    from experiments.week3_geometry.scripts.compare import classical_observations as _obs
    o = _obs(model)
    if o:
        allr = np.concatenate([v["range"] for v in o.values()])
        med_all = float(np.median(allr))
        per_frame_med = np.array([float(np.median(v["range"])) for v in o.values()])
        degen = {
            "median_observation_range": med_all,
            "min_observation_range": float(allr.min()),
            "frac_observations_below_1e-3_of_median": float((allr < 1e-3 * med_all).mean()),
            "per_frame_median_range_min": float(per_frame_med.min()),
            "per_frame_median_range_max": float(per_frame_med.max()),
            "per_frame_median_range_max_over_min": (
                float(per_frame_med.max() / per_frame_med.min())
                if per_frame_med.min() > 0 else float("inf")),
            "n_frames_with_median_range_below_1e-3_of_clip_median": int(
                (per_frame_med < 1e-3 * med_all).sum()),
            "note": ("A non-zero count here means cameras were placed coincident with scene "
                     "structure. Shape statistics for such a reconstruction are not "
                     "meaningful, however healthy its median residual looks."),
        }
    else:
        degen = {"note": "no observations"}

    return {
        "registered_images": len(imgs),
        "registered_fraction": (round(len(imgs) / n_offered, 4) if n_offered else None),
        "n_points3D": len(pts),
        "n_points_with_track_ge2": int(track_len.size),
        "mean_observations_per_image": float(obs_per_img.mean()) if obs_per_img.size else 0.0,
        "track_length": {"mean": float(track_len.mean()) if track_len.size else 0.0,
                         "median": float(np.median(track_len)) if track_len.size else 0.0,
                         **pcts(track_len),
                         "histogram_edges": [2, 3, 4, 5, 6, 8, 10, 15, 20, 30, 49],
                         "histogram": np.histogram(
                             track_len, bins=[2, 3, 4, 5, 6, 8, 10, 15, 20, 30, 49])[0].tolist()
                         if track_len.size else []},
        "triangulation_angle_deg": {"mean": float(tri_ang.mean()) if tri_ang.size else float("nan"),
                                    "median": float(np.median(tri_ang)) if tri_ang.size else float("nan"),
                                    **pcts(tri_ang),
                                    "frac_below_1deg": float((tri_ang < 1.0).mean()) if tri_ang.size else float("nan"),
                                    "frac_below_2deg": float((tri_ang < 2.0).mean()) if tri_ang.size else float("nan"),
                                    "frac_below_5deg": float((tri_ang < 5.0).mean()) if tri_ang.size else float("nan"),
                                    "definition": ("largest angle subtended at the 3D point by any "
                                                   "two observing camera centres")},
        "baseline_over_depth": {"median": float(np.median(bod)) if bod.size else float("nan"),
                                **pcts(bod)},
        "track_temporal_span_source_frames": {
            "clip_span_source_frames": clip_span,
            "median": float(np.median(span_frames)) if span_frames.size else float("nan"),
            **pcts(span_frames), **survival},
        "degeneracy_screen": degen,
        "camera": {"model": cam.get("model"), "params": cam.get("params"),
                   "width": cam.get("width"), "height": cam.get("height"),
                   "refrac_model": cam.get("refrac_model")},
        "focal_px": (cam.get("params") or [None])[0],
    }


# --------------------------------------------------------------------------
# Sparse vs sparse shape
# --------------------------------------------------------------------------

def compare_sparse(model_a: dict, model_b: dict, label_a: str, label_b: str,
                   max_px: float = 1.0) -> dict:
    """Scale-aligned range-shape comparison at co-visible image observations.

    Correspondence is by 2D proximity WITHIN THE SAME IMAGE -- an image
    observation match, never a 3D nearest neighbour between two independently
    posed clouds, which share no coordinate system at all.

    Exactly ONE global scale is fitted per pair, over observations pooled across
    every frame. The per-frame scale fits are a DRIFT DIAGNOSTIC and are never
    fed back into the residual.
    """
    oa, ob = classical_observations(model_a), classical_observations(model_b)
    common = sorted(set(oa) & set(ob))
    if not common:
        return {"a": label_a, "b": label_b, "error": "no shared frames"}
    src_hw = None
    for c in model_a["cameras"].values():
        src_hw = (c["height"], c["width"])
    ra, rb, rad = [], [], []
    a_by_frame, b_by_frame = {}, {}
    for idx in common:
        A, B = oa[idx], ob[idx]
        d = np.linalg.norm(A["uv"][:, None, :] - B["uv"][None, :, :], axis=2)
        j = d.argmin(axis=1)
        ok = d[np.arange(len(j)), j] <= max_px
        if not ok.any():
            continue
        a_by_frame[idx] = A["range"][ok]
        b_by_frame[idx] = B["range"][j[ok]]
        ra.append(A["range"][ok])
        rb.append(B["range"][j[ok]])
        rad.append(image_radius(A["uv"][ok], src_hw))
    if not ra:
        return {"a": label_a, "b": label_b, "n_shared_frames": len(common),
                "error": "no matched observations"}
    a = np.concatenate(ra)
    b = np.concatenate(rb)
    rr = np.concatenate(rad)
    fit = fit_global_scale(a, b)
    err = relative_errors(a, b, fit.scale)
    b_edges = np.percentile(b[np.isfinite(b)], np.linspace(0, 100, 7))
    per_frame = {}
    for k in sorted(a_by_frame):
        f = fit_global_scale(a_by_frame[k], b_by_frame[k])
        if np.isfinite(f.scale):
            per_frame[k] = f.scale
    s = np.array(list(per_frame.values())) if per_frame else np.array([])

    rng_prof = binned_profile(b, err, b_edges)
    rad_prof = binned_profile(rr, err, RADIUS_EDGES)
    return {
        "a": label_a, "b": label_b,
        "n_shared_frames": len(a_by_frame),
        "n_matched_observations": int(a.size),
        "match_max_px": max_px,
        "global_scale_a_to_b": fit.scale,
        "global_scale_fit": {"n_used": fit.n_used, "log_residual_mad": fit.log_residual_mad},
        "relative_error": robust_stats(err),
        "abs_relative_error": robust_stats(np.abs(err)),
        "residual_vs_b_range": rng_prof,
        "residual_vs_image_radius": rad_prof,
        "range_swing": _swing(rng_prof),
        "radius_swing": _swing(rad_prof),
        "radius_x_range_interaction": radius_profiles_by_range_bin(rr, b, err, b_edges),
        "per_frame_scale_diagnostic": {
            "n_frames": len(per_frame),
            "min": float(s.min()) if s.size else float("nan"),
            "max": float(s.max()) if s.size else float("nan"),
            "max_over_min": (float(s.max() / s.min()) if s.size and s.min() > 0 else float("nan")),
            "note": "DIAGNOSTIC ONLY -- never used to normalise the residuals above.",
        },
    }


def compare_trajectories(model_a: dict, model_b: dict, label_a: str, label_b: str) -> dict:
    """Camera-trajectory agreement between two reconstructions, up to a similarity.

    3B-2 asks whether a global mapper changes the *poses*. Two reconstructions of
    the same clip carry independent similarity gauges, so the only meaningful
    comparison aligns them with ONE rotation, ONE translation and ONE scale
    (Umeyama) over the camera centres of the frames both registered — which is
    the trajectory analogue of this project's one-global-scale rule, not an extra
    degree of freedom smuggled in.

    The residual is reported **relative to the trajectory's own extent**, because
    an absolute number in an arbitrary gauge means nothing. A method that
    registers a different subset of frames is compared only on the intersection,
    and the intersection size is reported so a flattering comparison over three
    frames cannot pass as agreement.
    """
    ca = {_frame_index(im["name"]): c
          for im, c in zip(model_a["images"].values(), _camera_centres(model_a).values())}
    cb = {_frame_index(im["name"]): c
          for im, c in zip(model_b["images"].values(), _camera_centres(model_b).values())}
    common = sorted(set(ca) & set(cb))
    if len(common) < 3:
        return {"a": label_a, "b": label_b, "n_common_frames": len(common),
                "error": "fewer than 3 shared registered frames"}
    A = np.array([ca[k] for k in common], dtype=np.float64)
    B = np.array([cb[k] for k in common], dtype=np.float64)
    mu_a, mu_b = A.mean(axis=0), B.mean(axis=0)
    Ac, Bc = A - mu_a, B - mu_b
    H = (Ac.T @ Bc) / len(common)
    U, D, Vt = np.linalg.svd(H)
    S = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        S[2, 2] = -1.0
    R = Vt.T @ S @ U.T
    var_a = (Ac ** 2).sum() / len(common)
    s = float(np.trace(np.diag(D) @ S) / var_a) if var_a > 0 else float("nan")
    t = mu_b - s * (R @ mu_a)
    resid = np.linalg.norm((s * (A @ R.T) + t) - B, axis=1)
    extent = float(np.linalg.norm(Bc, axis=1).max())
    return {
        "a": label_a, "b": label_b,
        "n_common_frames": len(common),
        "n_frames_a": len(ca), "n_frames_b": len(cb),
        "similarity_scale_a_to_b": s,
        "trajectory_extent_b": extent,
        "residual_over_extent": {
            "rmse": float(np.sqrt((resid ** 2).mean()) / extent) if extent > 0 else float("nan"),
            "median": float(np.median(resid) / extent) if extent > 0 else float("nan"),
            "max": float(resid.max() / extent) if extent > 0 else float("nan"),
        },
        "note": ("Aligned with ONE similarity (rotation, translation, scale) over the "
                 "camera centres of the shared frames. The residual is normalised by the "
                 "trajectory's own extent because the gauge is arbitrary. Agreement here "
                 "is consistency between two hypotheses, not evidence that either "
                 "trajectory is correct."),
    }


def _swing(profile: list) -> float:
    """max - min of the binned residual median: the shape axis Phase 3A §8 costs."""
    meds = [p["median"] for p in profile if p.get("n", 0) > 30 and np.isfinite(p["median"])]
    return float(max(meds) - min(meds)) if len(meds) >= 2 else float("nan")


def summarise_run(run: dict, n_offered: int = 48) -> dict:
    """One row: provenance + structure + conditioning + front-end yield."""
    rep = run["report"]
    row = {
        "run_dir": os.path.relpath(run["run_dir"], REPO_ROOT),
        "config": rep.get("config"),
        "clip": rep.get("clip"),
        "repeat": rep.get("repeat"),
        "extractor": rep.get("extractor"),
        "matcher_type": rep.get("matcher_type"),
        "binary_version": rep.get("binary_version"),
        "seed": rep.get("seed"),
        "n_images_offered": rep.get("n_images_offered", n_offered),
        "failed_at": rep.get("failed_at"),
        "submodel_registered_images": rep.get("submodel_registered_images"),
        "n_submodels": rep.get("n_submodels"),
        "total_seconds": rep.get("total_seconds"),
        "peak_rss_gb": rep.get("peak_rss_gb"),
        "stage_seconds": {k: v.get("seconds") for k, v in (rep.get("stages") or {}).items()},
    }
    if rep.get("result"):
        row["mean_reproj_px_DIAGNOSTIC_ONLY"] = round(
            rep["result"]["mean_reprojection_error_px"], 4)
    if run["model"] is not None:
        row["structure"] = sparse_structure_metrics(
            run["model"], n_offered=row["n_images_offered"])
    row["frontend"] = database_metrics(run["database"])
    return row


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Summarise one classical run directory.")
    ap.add_argument("run_dir")
    args = ap.parse_args()
    run = load_run(args.run_dir)
    if run is None:
        raise SystemExit(f"no run.json in {args.run_dir!r}")
    print(json.dumps(summarise_run(run), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
