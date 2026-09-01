"""Stage 4 — configuration D: MapAnything feed-forward dense geometry.

EXPLORATORY. Runs in `experiments/week3_geometry/.venv-mapanything`, NOT the
main project venv. One process per clip: the process boundary is the
authoritative MPS cleanup boundary, and no other heavyweight geometry model is
ever instantiated in this interpreter.

Convention work happens here, once, and is checked numerically rather than
assumed — see `_convention_check`. MapAnything's own field names are adopted as
the Week 3 range convention per `PLAN.md`; this script's job is to map them onto
the project's common representation and to record exactly what was assumed.

Usage:
    experiments/week3_geometry/.venv-mapanything/bin/python \
        -m experiments.week3_geometry.scripts.run_mapanything --clip wreck_07
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import platform
import re
import resource
import sys
import time

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import numpy as np
import torch

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week3_geometry.rangeio import RangeWriter  # noqa: E402

W3 = os.path.join(REPO_ROOT, "experiments", "week3_geometry")
CONFIG = "D_mapanything"
#: Apache-2.0 checkpoint variant. The default `facebook/map-anything` weights are
#: CC-BY-NC-4.0; PLAN.md's licence rule prefers the Apache/BSD path for anything
#: that might outlive the bakeoff, so the Apache checkpoint is what is measured.
CHECKPOINT = "facebook/map-anything-apache"


def frame_index_of(path: str) -> int:
    m = re.search(r"f(\d{6})\.png$", os.path.basename(path))
    if not m:
        raise ValueError(f"unexpected frame filename {path!r}")
    return int(m.group(1))


def _convention_check(pred: dict) -> dict:
    """Verify MapAnything's documented range semantics numerically, per view 0.

    Three things must hold before any number from this model is comparable:
      * `depth_along_ray` really is ||pts3d_cam||, i.e. a Euclidean distance;
      * `depth_z` really is the z COMPONENT of pts3d_cam, i.e. planar;
      * the two differ by the secant factor, so they are NOT interchangeable.
    If the first two hold, the mapping onto our `range_along_ray` is exact and
    the only remaining approximation is the water-path one, which is labelled.
    """
    p3c = pred["pts3d_cam"][0].detach().float().cpu().numpy()          # (H,W,3)
    dar = pred["depth_along_ray"][0].detach().float().cpu().numpy()[..., 0]
    dz = pred["depth_z"][0].detach().float().cpu().numpy()[..., 0]
    m = np.isfinite(p3c).all(axis=-1) & np.isfinite(dar) & np.isfinite(dz) & (dz > 0)
    if not m.any():
        return {"checked": False, "reason": "no finite pixels in view 0"}
    norm = np.linalg.norm(p3c, axis=-1)
    return {
        "checked": True,
        "max_abs_depth_along_ray_minus_norm_pts3d_cam": float(np.abs(norm[m] - dar[m]).max()),
        "max_abs_depth_z_minus_pts3d_cam_z": float(np.abs(p3c[..., 2][m] - dz[m]).max()),
        "median_ratio_along_ray_over_z": float(np.median(dar[m] / dz[m])),
        "max_ratio_along_ray_over_z": float((dar[m] / dz[m]).max()),
        "interpretation": ("depth_along_ray == ||pts3d_cam|| confirms it is a "
                           "Euclidean camera-to-point distance, so it maps onto "
                           "range_along_ray exactly. The ratio to depth_z is the "
                           "secant factor and shows how large an error treating "
                           "z-depth as range would have been."),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clip", required=True)
    ap.add_argument("--frames-root", default=os.path.join(W3, "outputs", "frames"))
    ap.add_argument("--out-root", default=os.path.join(W3, "outputs", "range"))
    ap.add_argument("--max-views", type=int, default=None,
                    help="bring-up/profiling only; the bakeoff uses every frame")
    ap.add_argument("--repeat", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    files = sorted(glob.glob(os.path.join(args.frames_root, args.clip, "f*.png")))
    if not files:
        raise SystemExit(f"no frames under {os.path.join(args.frames_root, args.clip)}")
    if args.max_views:
        idx = np.linspace(0, len(files) - 1, args.max_views).round().astype(int)
        files = [files[i] for i in sorted(set(idx))]

    from mapanything.models import MapAnything
    from mapanything.utils.image import load_images

    t0 = time.time()
    model = MapAnything.from_pretrained(CHECKPOINT).to(device).eval()
    t_load = time.time() - t0

    t0 = time.time()
    views = load_images(files)
    t_prep = time.time() - t0
    in_hw = list(views[0]["img"].shape[-2:])

    t0 = time.time()
    with torch.no_grad():
        preds = model.infer(
            views,
            memory_efficient_inference=True,
            use_amp=False,          # MPS has no bf16 autocast; float32 everywhere
            apply_mask=True,
            mask_edges=True,
            apply_confidence_mask=False,   # keep confidence as DATA, not as a filter
        )
    t_infer = time.time() - t0
    peak_mps_gb = (torch.mps.driver_allocated_memory() / 1e9
                   if device == "mps" else float("nan"))

    conv = _convention_check(preds[0])

    config = CONFIG if args.repeat == 0 else f"{CONFIG}_run{args.repeat}"
    w = RangeWriter(args.out_root, config, args.clip, overwrite=args.overwrite)
    for path, pred in zip(files, preds):
        rng = pred["depth_along_ray"][0].detach().float().cpu().numpy()[..., 0]
        mask = pred["mask"][0].detach().cpu().numpy()
        mask = mask[..., 0] if mask.ndim == 3 else mask
        conf = pred["conf"][0].detach().float().cpu().numpy()
        K = pred["intrinsics"][0].detach().float().cpu().numpy()
        T_wc = pred["camera_poses"][0].detach().float().cpu().numpy()
        extra = {}
        if "non_ambiguous_mask" in pred:
            nam = pred["non_ambiguous_mask"][0].detach().cpu().numpy()
            extra["non_ambiguous_fraction"] = float(np.asarray(nam, bool).mean())
        if "metric_scaling_factor" in pred:
            extra["metric_scaling_factor"] = float(
                pred["metric_scaling_factor"].detach().float().cpu().numpy().ravel()[0])
        w.add_frame(frame_index_of(path), rng, np.asarray(mask, bool),
                    K=K, T_wc=T_wc, conf=conf,
                    path_source="ray_range_approx_water_path", extra=extra)

    rss_gb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9
    w.close(
        provenance={
            "method": "MapAnything",
            "config_letter": "D",
            "role": "general-purpose feed-forward dense geometry (range supplier candidate)",
            "repo": "https://github.com/facebookresearch/map-anything",
            "repo_commit": "3d10cf7a3016fc0f9bb13a071ee66c47b10be0d9",
            "package_version": "1.1.4",
            "code_license": "Apache-2.0",
            "checkpoint": CHECKPOINT,
            "checkpoint_license": "Apache-2.0 (the default facebook/map-anything is CC-BY-NC-4.0)",
            "torch": torch.__version__,
            "device": device,
            "dtype": "float32 (no autocast: MPS has no bf16 autocast path)",
            "seed": args.seed,
            "repeat": args.repeat,
            "platform": platform.platform(),
            "n_views": len(files),
            "input_frames": [os.path.relpath(f, REPO_ROOT) for f in files],
            "source_frame_resolution_hw": [720, 1280],
            "inference_resolution_hw": in_hw,
            "resolution_note": ("MapAnything's load_images 'fixed_mapping' mode resizes "
                                "to its 518 resolution set. Every dense number from this "
                                "model is produced on that grid, NOT at the 1280x720 "
                                "extraction resolution, and must not be described as "
                                "native-resolution geometry."),
            "seconds": {"model_load": round(t_load, 1), "preprocess": round(t_prep, 1),
                        "inference": round(t_infer, 1)},
            "peak_process_rss_gb": round(rss_gb, 2),
            "peak_mps_driver_gb": round(peak_mps_gb, 2),
            "infer_kwargs": {"memory_efficient_inference": True, "use_amp": False,
                             "apply_mask": True, "mask_edges": True,
                             "apply_confidence_mask": False},
        },
        conventions={
            "camera_frame": "OpenCV: +x right, +y down, +z forward",
            "pose": "camera_poses is cam2world (T_wc); its translation is the camera centre",
            "native_range_field": "depth_along_ray (B,H,W,1)",
            "native_z_field": "depth_z (B,H,W,1)",
            "stored_as": "range_along_ray = depth_along_ray, unmodified",
            "path_source": "ray_range_approx_water_path",
            "path_source_note": ("MapAnything is a central pinhole model, so it cannot "
                                 "emit a water path length. Ray range stands in for it; "
                                 "the unmodelled air+glass segment is millimetres against "
                                 "metre-scale scene range."),
            "confidence": "pred['conf'], learned per-pixel; NOT calibrated on underwater data",
            "mask": "pred['mask'] with apply_mask=True and mask_edges=True",
            "convention_check": conv,
        },
        scale_convention="metric-claimed-by-model (NOT independently verified here)",
    )
    print(f"D/{args.clip}: {len(files)} views, inference {t_infer:.0f}s, "
          f"MPS peak {peak_mps_gb:.1f} GB, RSS {rss_gb:.1f} GB, "
          f"grid {in_hw}, "
          f"|along_ray - ||pts3d_cam|||max = "
          f"{conv.get('max_abs_depth_along_ray_minus_norm_pts3d_cam', float('nan')):.2e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
