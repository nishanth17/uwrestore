"""Stage 1 — cheap mechanical inspection of candidate clips for the Week 3
Phase 3A geometry bakeoff.

EXPLORATORY. Scaffolding for one selection decision. Nothing under `uw/`
imports this. Runs in the main project venv (numpy + opencv only).

Deliberately cheap, per the Phase 3A video-inspection budget:

* container/decode metadata comes from the manifest, which already carries
  ffprobe-derived fields;
* per-frame statistics are computed on a sparse, deterministic sample
  (default 10 frames spread across the clip) plus a decimated grayscale
  pass used only for shot-cut detection;
* NO optical flow, NO SfM, NO learned model is run here. Parallax and
  camera-motion character are judged from the contact sheets and the
  manifest notes, and are only *confirmed* later by the bakeoff itself.

Statistics recorded per sampled frame (all on the sRGB-encoded uint8 decode
except where noted, because these are triage proxies, not restoration
measurements):

    lum_mean_linear     mean linear-light luminance (Rec.709 weights).
                        Ingested through uw.colorspace.srgb_to_linear so the
                        one place that defines the transfer function stays
                        the same place (CLAUDE.md invariant 1).
    rms_contrast        std/mean of the linear luminance — a visibility proxy;
                        veiling light raises the mean without raising the std.
    lap_var             variance of the Laplacian on the sRGB gray image, the
                        standard cheap focus/texture score.
    n_features          cv2.goodFeaturesToTrack count at fixed parameters —
                        a direct proxy for "will a corner-based matcher have
                        anything to hold on to".
    feat_cov_frac       fraction of an 8x8 image-grid tessellation containing
                        at least one detected feature: distinguishes "many
                        features in one corner" from "features everywhere",
                        which is what matters for pose conditioning.
    rg_ratio            mean(R)/mean(G) in linear light — how far the water
                        has already eaten the red channel. A visibility /
                        range-severity proxy, not a restoration measurement.

Shot-cut detection compares 32-bin grayscale histograms of every `--cut-step`
frame at 64x36; a correlation below `--cut-threshold` is reported as a
candidate cut. Coarse by construction — it is here so a clip with an obvious
hard cut is *recorded* rather than silently selected around.

Usage:
    .venv/bin/python -m experiments.week3_geometry.scripts.inspect_clips \
        --out experiments/week3_geometry/outputs/stage1/clip_inspection.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import cv2
import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from uw.colorspace import srgb_to_linear  # noqa: E402

MANIFEST = os.path.join(REPO_ROOT, "data", "testset", "manifest.json")

# Fixed detector parameters. Held constant across every clip so the counts are
# comparable; the absolute numbers are meaningless, the ordering is the point.
GFTT_KW = dict(maxCorners=4000, qualityLevel=0.01, minDistance=8, blockSize=7)
GRID = 8


def sample_indices(n_frames: int, k: int) -> list[int]:
    """k deterministic indices spread across [5%, 95%] of the clip.

    The 5% inset avoids the fade-in/exposure-settling frames that GoPro clips
    routinely start with, without searching for favourable frames.
    """
    if n_frames <= 0:
        return []
    k = min(k, n_frames)
    if k == 1:
        return [n_frames // 2]
    fr = np.linspace(0.05, 0.95, k)
    return sorted({int(round(f * (n_frames - 1))) for f in fr})


def _frame_stats(bgr: np.ndarray) -> dict:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    linear = srgb_to_linear(rgb)
    lum = 0.2126 * linear[..., 0] + 0.7152 * linear[..., 1] + 0.0722 * linear[..., 2]
    mean = float(lum.mean())
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    pts = cv2.goodFeaturesToTrack(gray, **GFTT_KW)
    n_features = 0 if pts is None else int(pts.shape[0])
    cov = 0.0
    if pts is not None:
        h, w = gray.shape
        cells = set()
        for (x, y) in pts.reshape(-1, 2):
            cells.add((min(int(y / h * GRID), GRID - 1), min(int(x / w * GRID), GRID - 1)))
        cov = len(cells) / float(GRID * GRID)
    ch = linear.reshape(-1, 3).mean(axis=0)
    return {
        "lum_mean_linear": mean,
        "rms_contrast": float(lum.std() / mean) if mean > 1e-6 else 0.0,
        "lap_var": float(cv2.Laplacian(gray, cv2.CV_64F).var()),
        "n_features": n_features,
        "feat_cov_frac": cov,
        "rg_ratio": float(ch[0] / ch[1]) if ch[1] > 1e-9 else 0.0,
    }


def _cut_scan(path: str, n_frames: int, step: int, threshold: float) -> dict:
    """Decimated histogram-correlation scan. Returns candidate cut indices."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise IOError(f"failed to open {path!r}")
    prev = None
    corrs = []
    idxs = []
    i = 0
    try:
        while True:
            ok = cap.grab()
            if not ok:
                break
            if i % step == 0:
                ok, bgr = cap.retrieve()
                if not ok:
                    break
                small = cv2.cvtColor(cv2.resize(bgr, (64, 36), interpolation=cv2.INTER_AREA),
                                     cv2.COLOR_BGR2GRAY)
                hist = cv2.calcHist([small], [0], None, [32], [0, 256])
                cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
                if prev is not None:
                    corrs.append(float(cv2.compareHist(prev, hist, cv2.HISTCMP_CORREL)))
                    idxs.append(i)
                prev = hist
            i += 1
    finally:
        cap.release()
    corrs_a = np.asarray(corrs, dtype=np.float64)
    cuts = [int(idxs[j]) for j in np.flatnonzero(corrs_a < threshold)] if corrs_a.size else []
    return {
        "scanned_frames": i,
        "step": step,
        "threshold": threshold,
        "min_correlation": float(corrs_a.min()) if corrs_a.size else None,
        "median_correlation": float(np.median(corrs_a)) if corrs_a.size else None,
        "candidate_cut_frames": cuts,
    }


def inspect(clip: dict, n_samples: int, cut_step: int, cut_threshold: float) -> dict:
    path = os.path.join(REPO_ROOT, clip["local_path"])
    if not os.path.exists(path):
        return {"id": clip["id"], "error": f"missing local file: {clip['local_path']}"}
    t0 = time.time()
    n = int(clip["frame_count"])
    idxs = sample_indices(n, n_samples)
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise IOError(f"failed to open {path!r}")
    per_frame = []
    try:
        want = set(idxs)
        i = 0
        got = 0
        while got < len(idxs):
            ok = cap.grab()
            if not ok:
                break
            if i in want:
                ok, bgr = cap.retrieve()
                if not ok:
                    break
                st = _frame_stats(bgr)
                st["frame_index"] = i
                st["decoded_shape"] = list(bgr.shape[:2])
                per_frame.append(st)
                got += 1
            i += 1
    finally:
        cap.release()

    def col(key):
        return np.asarray([f[key] for f in per_frame], dtype=np.float64)

    summary = {}
    for key in ("lum_mean_linear", "rms_contrast", "lap_var", "n_features",
                "feat_cov_frac", "rg_ratio"):
        v = col(key)
        summary[key] = {"median": float(np.median(v)), "min": float(v.min()),
                        "max": float(v.max())}
    # Illumination variation across the sampled span, in stops. Large values
    # mean a moving light source or an exposure ramp -- both are radiometric
    # confounds for a feed-forward model and for photometric matching.
    lum = col("lum_mean_linear")
    summary["lum_range_stops"] = float(np.log2(lum.max() / max(lum.min(), 1e-9)))

    return {
        "id": clip["id"],
        "category": clip["category"],
        "role": clip["role"],
        "local_path": clip["local_path"],
        "frame_count": n,
        "fps": clip["fps"],
        "duration_seconds": clip["duration_seconds"],
        "decoded_size": [clip["decoded_width"], clip["decoded_height"]],
        "tags": clip.get("tags", []),
        "sampled_frames": idxs,
        "per_frame": per_frame,
        "summary": summary,
        "cut_scan": _cut_scan(path, n, cut_step, cut_threshold),
        "manifest_notes": clip.get("notes", ""),
        "inspect_seconds": round(time.time() - t0, 2),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, help="output JSON path")
    ap.add_argument("--roles", nargs="+", default=["dev"],
                    help="manifest roles to inspect (default: dev only)")
    ap.add_argument("--samples", type=int, default=10,
                    help="frames sampled per clip (Phase 3A budget: 6-12)")
    ap.add_argument("--cut-step", type=int, default=5)
    ap.add_argument("--cut-threshold", type=float, default=0.5)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    if os.path.exists(args.out) and not args.overwrite:
        raise SystemExit(f"refusing to overwrite {args.out!r} (pass --overwrite)")

    with open(MANIFEST) as fh:
        manifest = json.load(fh)
    clips = [c for c in manifest["clips"] if c["role"] in args.roles]

    results = []
    for c in clips:
        print(f"inspecting {c['id']} ...", flush=True)
        results.append(inspect(c, args.samples, args.cut_step, args.cut_threshold))

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    payload = {
        "_comment": ("Stage 1 mechanical clip inspection for the Week 3 Phase 3A "
                     "geometry bakeoff. Sparse deterministic sampling; no optical "
                     "flow, SfM or learned model was run. Texture/visibility/"
                     "illumination figures are triage proxies for clip selection, "
                     "not measured geometry results."),
        "manifest_path": os.path.relpath(MANIFEST, REPO_ROOT),
        "roles": args.roles,
        "samples_per_clip": args.samples,
        "gftt_params": GFTT_KW,
        "grid": GRID,
        "opencv_version": cv2.__version__,
        "numpy_version": np.__version__,
        "clips": results,
    }
    with open(args.out, "w") as fh:
        json.dump(payload, fh, indent=2)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
