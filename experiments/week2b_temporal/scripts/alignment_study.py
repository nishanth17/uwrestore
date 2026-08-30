"""Alignment sensitivity of MC-Warp: how much residual is interpolation alone?

EXPLORATORY (Week 2 Phase 2B). Runs in the ORDINARY project venv — no torch,
no flow model. That is the point: a real backend would contribute its own
correspondence error, and this study is about the error that remains when the
correspondence is exactly right.

Method
------
Take a real frame from the frozen test set, put it on the metric's evaluation
grid in linear light, translate it by a known amount with bilinear
resampling, then measure MC-Warp with the exactly-correct constant flow
field. For an integer translation the resampling is a pure copy and the
residual is ~0. For a fractional one, everything that remains comes from:

  * bilinear interpolation smoothing the shifted frame,
  * bilinear interpolation smoothing it back,
  * the two not being inverses of each other,

i.e. the floor that a perfect optical-flow backend could not beat. The
question this answers is whether that floor is a material fraction of the
MC-Warp values measured on real footage, and whether it is concentrated on
high-gradient structure (coral edges, the thin rope, chart borders) as
expected.

Also reports the alignment-robust companion (one fixed 1 px Gaussian) on the
same cases, so the decision to keep or drop that companion rests on measured
numbers rather than on the idea that blur helps.

Writes JSON plus residual maps under outputs/temporal_metric/alignment/.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import cv2
import numpy as np

_REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from uw.io import load  # noqa: E402
from uw.metrics import (  # noqa: E402
    ALIGNMENT_ROBUST_SIGMA_PX,
    alignment_robust_warp_error,
    linear_luminance,
    metric_eval_size,
    resize_linear,
    temporal_warp_error,
    warp_with_support,
)

# Sub-pixel offsets to characterise. (0, 0) and (1, 0) are the controls: they
# must come out at the numerical floor, because bilinear resampling at an
# integer offset is a copy.
OFFSETS = [(0.0, 0.0), (1.0, 0.0), (0.25, 0.0), (0.5, 0.0),
           (0.5, 0.25), (0.5, 0.5), (0.75, 0.4)]

# Ignore a border of this many pixels: a synthetic translation has to invent
# content at the leading edge, and no metric should be judged on invented
# pixels. Real evaluations exclude the same region through the flow's own
# out-of-frame test.
BORDER_PX = 24


def shift(image, dx, dy):
    """Translate content by (dx, dy) px with bilinear resampling."""
    h, w = image.shape[:2]
    xs, ys = np.meshgrid(np.arange(w, dtype=np.float32),
                         np.arange(h, dtype=np.float32))
    return cv2.remap(np.asarray(image, np.float32),
                     (xs - dx).astype(np.float32), (ys - dy).astype(np.float32),
                     interpolation=cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_REFLECT_101)


def constant_flow(h, w, u, v):
    f = np.zeros((h, w, 2), np.float32)
    f[..., 0], f[..., 1] = u, v
    return f


def gradient_magnitude(image):
    """Sobel gradient magnitude of linear luminance, in per-pixel units."""
    y = linear_luminance(image).astype(np.float32)
    gx = cv2.Sobel(y, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    gy = cv2.Sobel(y, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    return np.hypot(gx, gy)


def residual_map(reference, target, flow, mask):
    warped, ok = warp_with_support(target, flow)
    res = np.abs(warped.astype(np.float64) - reference.astype(np.float64)).mean(axis=2)
    res[~(ok & mask)] = np.nan
    return res


def study_frame(image, tag):
    h, w = image.shape[:2]
    mask = np.zeros((h, w), bool)
    mask[BORDER_PX:-BORDER_PX, BORDER_PX:-BORDER_PX] = True

    grad = gradient_magnitude(image)
    # Decile edges of the gradient over the measured region, so "high
    # gradient" means high for THIS frame rather than an absolute threshold.
    edges = np.percentile(grad[mask], [50, 90, 99])

    rows = []
    maps = {}
    for dx, dy in OFFSETS:
        shifted = shift(image, dx, dy)
        flow = constant_flow(h, w, dx, dy)
        raw, cov = temporal_warp_error(image, shifted, flow, mask)
        robust, _ = alignment_robust_warp_error(image, shifted, flow, mask)
        res = residual_map(image, shifted, flow, mask)

        finite = np.isfinite(res)
        bands = {}
        for name, sel in (
            ("bottom_50pct_gradient", finite & (grad <= edges[0])),
            ("p50_p90_gradient", finite & (grad > edges[0]) & (grad <= edges[1])),
            ("p90_p99_gradient", finite & (grad > edges[1]) & (grad <= edges[2])),
            ("top_1pct_gradient", finite & (grad > edges[2])),
        ):
            bands[name] = float(res[sel].mean()) if sel.any() else None
        share_top1 = (
            float(np.nansum(res[finite & (grad > edges[2])]) / np.nansum(res[finite]))
            if np.nansum(res[finite]) > 0 else None
        )

        rows.append({
            "offset_px": [dx, dy],
            "raw_mc_warp": raw,
            "alignment_robust_mc_warp": robust,
            "coverage": cov,
            "residual_by_gradient_band": bands,
            "share_of_total_residual_in_top_1pct_gradient": share_top1,
        })
        maps[f"{tag}_dx{dx}_dy{dy}"] = res
        top = bands["top_1pct_gradient"]
        print(f"    offset ({dx:+.2f}, {dy:+.2f})  raw {raw:.6f}  "
              f"robust {robust:.6f}  "
              f"top-1%-grad {'n/a' if top is None else f'{top:.6f}'}  "
              f"share {'n/a' if share_top1 is None else f'{share_top1:.1%}'}")
    return rows, maps, {"gradient_p50": float(edges[0]),
                        "gradient_p90": float(edges[1]),
                        "gradient_p99": float(edges[2])}


def save_residual_map(path, res, hi, overwrite):
    if os.path.exists(path) and not overwrite:
        raise FileExistsError(f"{path!r} exists; pass --overwrite")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    norm = np.clip(np.nan_to_num(res, nan=0.0) / max(hi, 1e-9), 0, 1)
    u8 = (norm * 255).astype(np.uint8)
    cv2.imwrite(path, cv2.applyColorMap(u8, cv2.COLORMAP_INFERNO))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", default=None, help="comma-separated clip names")
    ap.add_argument("--out", default="outputs/temporal_metric/alignment")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    with open(os.path.join(_REPO, "experiments/week2a_flow/excerpts.json")) as f:
        excerpts = json.load(f)["clips"]
    wanted = args.clips.split(",") if args.clips else list(excerpts)

    out_dir = os.path.join(_REPO, args.out)
    report = {
        "study": "sub-pixel alignment sensitivity of MC-Warp",
        "method": (
            "known bilinear translation of one real frame, warped back with "
            "the exactly-correct constant flow; the residual is interpolation "
            "and resampling only, with no correspondence error"
        ),
        "border_excluded_px": BORDER_PX,
        "alignment_robust_sigma_px": ALIGNMENT_ROBUST_SIGMA_PX,
        "clips": {},
    }
    for name in wanted:
        info = excerpts[name]
        frame_index = int(info["selected_excerpt_start"])
        frames = load(os.path.join(_REPO, info["path"]), start=frame_index, count=1)
        src_h, src_w = frames[0].image.shape[:2]
        eh, ew = metric_eval_size(src_h, src_w)
        image = resize_linear(frames[0].image, eh, ew)
        print(f"  {name} frame {frame_index} ({src_h}x{src_w} -> {eh}x{ew})")
        rows, maps, grad = study_frame(image, name)
        report["clips"][name] = {
            "source": info["path"], "frame_index": frame_index,
            "source_size_hw": [src_h, src_w], "metric_size_hw": [eh, ew],
            "gradient_percentiles": grad,
            "offsets": rows,
        }
        # One shared scale across the offsets so the maps are comparable.
        hi = max(np.nanpercentile(m, 99.5) for m in maps.values())
        for key, res in maps.items():
            save_residual_map(os.path.join(out_dir, f"{key}.png"), res, hi, args.overwrite)
        report["clips"][name]["residual_map_display_max"] = float(hi)

    path = os.path.join(out_dir, "alignment_study.json")
    if os.path.exists(path) and not args.overwrite:
        raise FileExistsError(f"{path!r} exists; pass --overwrite")
    os.makedirs(out_dir, exist_ok=True)
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
