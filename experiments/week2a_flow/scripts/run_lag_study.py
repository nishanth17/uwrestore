"""MC-Warp lag study: does the backend ranking survive @4 and @8? EXPLORATORY.

PLAN.md specifies MC-Warp@1 / @4 / @8. The Phase 1A bakeoff measured only
lag 1, so its conclusions cover a third of the metric. At 3–12 px/frame,
lag 8 means 25–95 px displacements — a different regime, where a ranking
built on lag 1 has no automatic authority.

Design, deliberately parallel to run_bakeoff.py so the numbers are
comparable:

  * same clips, same common 960x540 evaluation grid, same linear-light
    downscale, same temporary sRGB model-input view;
  * same forward/backward consistency mask with the same fixed thresholds;
  * the photometric residual is again measured on LINEAR-LIGHT data;
  * three anchor frames per clip, evaluated at lags 1, 4 and 8, each in both
    directions — so every reported number is two real inferences.

Frame layout: 41 frames are decoded per clip and anchors sit at local
indices 16, 18, 20, so that even at lag 8 a multi-frame backend's
[t-2k, t-k, t, t+k, t+2k] window (0..36) fits without clamping. Anchors are
therefore identical across lags and backends — the only thing that varies is
the lag.

The headline quantity is NOT the absolute residual (which grows with lag for
trivial reasons) but the **reduction ratio** against the uncompensated
residual at the same lag: how much of the frame-to-frame change the flow
actually explains. Coverage is reported alongside every value, per PLAN.md.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

_REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from experiments.week2a_flow.common import (  # noqa: E402
    colorize_scalar, downscale_linear, eval_size_for, flow_to_color,
    linear_to_display_u8, load_excerpt, pair_diagnostics,
    residual_to_display_u8, save_gray, save_rgb, write_json,
)
from experiments.week2a_flow.scripts.run_bakeoff import (  # noqa: E402
    _release_cache, build_backend, mps_allocated_mb, peak_rss_mb,
)
from uw.flow import forward_backward_consistency, warp_to_source  # noqa: E402

WINDOW_FRAMES = 41
ANCHORS = [16, 18, 20]        # local indices; +/-2k fits for k up to 8
LAGS = [1, 4, 8]


def run_clip(backend, clip_name, clip_rel, start, out_dir, overwrite, save_visuals=True):
    path = os.path.join(_REPO, clip_rel)
    frames_full = load_excerpt(path, start, WINDOW_FRAMES)
    src_h, src_w = frames_full[0].image.shape[:2]
    eh, ew = eval_size_for(src_h, src_w)
    frames = downscale_linear(frames_full, eh, ew)

    out = {
        "clip": clip_name, "source": clip_rel,
        "source_size_hw": [src_h, src_w], "eval_size_hw": [eh, ew],
        "window_start_frame": start, "window_frames": WINDOW_FRAMES,
        "anchors_global": [start + a for a in ANCHORS],
        "lags": LAGS, "results": [],
    }
    peak_mps = 0.0

    for lag in LAGS:
        for ai, a in enumerate(ANCHORS):
            b = a + lag
            fwd = backend.estimate(frames, a, b)
            bwd = backend.estimate(frames, b, a)
            m = mps_allocated_mb()
            if m:
                peak_mps = max(peak_mps, m)
            _release_cache()

            lin_t, lin_t1 = frames[a].image, frames[b].image
            d = pair_diagnostics(lin_t, lin_t1, fwd.flow, bwd.flow)
            d["lag"] = lag
            d["anchor_global"] = start + a
            d["pair_global"] = [start + a, start + b]
            d["runtime_s_forward"] = fwd.metadata.get("runtime_s")
            d["runtime_s_backward"] = bwd.metadata.get("runtime_s")
            d["context_indices_global"] = [
                start + i for i in fwd.metadata.get("context_indices", [])
            ]
            d["off_distribution"] = bool(fwd.metadata.get("off_distribution", False))

            wm = d["warp_residual_linear_over_fb_valid"]["mae"]
            sm = d["static_residual_linear_over_fb_valid"]["mae"]
            d["residual_reduction_ratio"] = (sm / wm) if (wm and sm) else None

            if save_visuals and ai == 0:
                pd = os.path.join(out_dir, clip_name, f"lag{lag}_pair_{start + a}_{start + b}")
                save_rgb(os.path.join(pd, "frame_t.png"), linear_to_display_u8(lin_t), overwrite)
                save_rgb(os.path.join(pd, "frame_t1.png"), linear_to_display_u8(lin_t1), overwrite)
                _, mm = flow_to_color(fwd.flow)
                save_rgb(os.path.join(pd, "flow_forward.png"),
                         flow_to_color(fwd.flow, mm)[0], overwrite)
                warped, inside = warp_to_source(lin_t1, fwd.flow)
                save_rgb(os.path.join(pd, "warped_t1_to_t.png"),
                         linear_to_display_u8(warped), overwrite)
                save_rgb(os.path.join(pd, "residual_warped.png"),
                         residual_to_display_u8(warped - lin_t), overwrite)
                save_rgb(os.path.join(pd, "residual_uncompensated.png"),
                         residual_to_display_u8(lin_t1 - lin_t), overwrite)
                valid, fb_err = forward_backward_consistency(fwd.flow, bwd.flow)
                save_gray(os.path.join(pd, "fb_valid_mask.png"),
                          valid.astype(np.uint8) * 255, overwrite)
                save_rgb(os.path.join(pd, "fb_error.png"),
                         colorize_scalar(fb_err, lo=0.0, hi=3.0), overwrite)
                for tag, arr in (("forward", fwd.flow), ("backward", bwd.flow)):
                    fp = os.path.join(pd, f"flow_{tag}.npy")
                    if os.path.exists(fp) and not overwrite:
                        raise FileExistsError(f"{fp!r} exists; pass --overwrite")
                    os.makedirs(pd, exist_ok=True)
                    np.save(fp, arr.astype(np.float32))

            out["results"].append(d)
            print(f"    lag{lag} {start + a}->{start + b}: "
                  f"{d['runtime_s_forward']:.2f}s  "
                  f"cov {d['fb_valid_coverage_pct']:.1f}%  "
                  f"|flow| med {d['flow_magnitude_px']['median']:.1f}px  "
                  f"warpMAE {wm:.5f}  reduction "
                  f"{d['residual_reduction_ratio']:.2f}x", flush=True)

    out["peak_mps_driver_allocated_mb"] = peak_mps or None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True,
                    choices=["searaft", "waft", "videoflow_mof"])
    ap.add_argument("--device", default="mps")
    ap.add_argument("--excerpts", default="experiments/week2a_flow/excerpts.json")
    ap.add_argument("--out-root", default="outputs/flow_lag_study")
    ap.add_argument("--clips", default=None)
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--no-visuals", action="store_true")
    args = ap.parse_args()

    with open(os.path.join(_REPO, args.excerpts)) as f:
        excerpts = json.load(f)

    out_dir = os.path.join(_REPO, args.out_root, args.backend)
    backend = build_backend(args.backend, args.device)

    wanted = args.clips.split(",") if args.clips else list(excerpts["clips"])
    results = []
    for name in wanted:
        info = excerpts["clips"][name]
        n = info["frame_count"]
        # centre the 41-frame window on the bakeoff excerpt where the clip
        # allows it, so the lag study looks at the same stretch of footage
        start = int(info["selected_excerpt_start"]) - 14
        start = max(0, min(start, n - WINDOW_FRAMES))
        print(f"  {args.backend} / {name} (frames {start}..{start + WINDOW_FRAMES - 1})",
              flush=True)
        results.append(run_clip(backend, name, info["path"], start, out_dir,
                                args.overwrite, not args.no_visuals))

    write_json(
        os.path.join(out_dir, "metrics.json"),
        {
            "backend": args.backend,
            "environment": backend.describe(),
            "study": "MC-Warp lag study, lags 1/4/8 (PLAN.md MC-Warp@1/4/8)",
            "note": (
                "Anchors are identical across lags and backends; only the lag "
                "varies. The comparable quantity across lags is the residual "
                "REDUCTION RATIO against the uncompensated residual at the "
                "same lag — absolute residual grows with lag for trivial "
                "reasons. Coverage accompanies every value (PLAN.md). "
                "VideoFlow-MOF at lag>1 is run on a frame-subsampled window, "
                "which is off its training distribution; its rows are flagged "
                "off_distribution=true."
            ),
            "peak_process_rss_mb": peak_rss_mb(),
            "clips": results,
        },
        args.overwrite,
    )
    print(f"\nwrote {out_dir}")


if __name__ == "__main__":
    main()
