"""Run one flow backend over the test-set excerpts and write diagnostics.

EXPLORATORY — Week 2 Phase 1A. One backend per process invocation, because
SEA-RAFT, FlowIt and VideoFlow each ship a flat top-level `core.utils` and
VideoFlow needs its own interpreter (timm==0.4.12) anyway.

Layout written:

    outputs/flow_comparison/<backend>/environment.json
    outputs/flow_comparison/<backend>/metrics.json
    outputs/flow_comparison/<backend>/<clip>/pair_<t>_<t1>/*.png|meta.json

Every evaluated pair costs exactly two inferences (forward and backward);
both FlowResults are held and reused for every metric and every image, so
nothing is recomputed per-visualisation.

All diagnostics are computed at the common evaluation resolution. Nothing is
upsampled back to source resolution: an upsampled 960x540 flow field does
not contain 1080p correspondence detail and printing it at 1080p would only
imply that it does.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import sys

import numpy as np

_REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from experiments.week2a_flow.common import (  # noqa: E402
    colorize_scalar,
    downscale_linear,
    eval_size_for,
    flow_to_color,
    linear_to_display_u8,
    load_excerpt,
    pair_diagnostics,
    residual_to_display_u8,
    save_gray,
    save_rgb,
    write_json,
)
from uw.flow import warp_to_source  # noqa: E402

EXCERPT_FRAMES = 12                       # frames decoded per clip
PAIR_OFFSETS = [(4, 5), (6, 7), (8, 9)]   # local indices; MOF's +/-2 fits


def peak_rss_mb() -> float:
    # macOS reports ru_maxrss in bytes (Linux reports kB) — this project only
    # runs on macOS, but guard anyway rather than print a number 1000x wrong.
    v = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return float(v) / (1024 ** 2) if sys.platform == "darwin" else float(v) / 1024


def _release_cache():
    import gc
    gc.collect()
    try:
        import torch
        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
    except Exception:
        pass


def mps_allocated_mb():
    try:
        import torch
        if torch.backends.mps.is_available():
            return float(torch.mps.driver_allocated_memory()) / (1024 ** 2)
    except Exception:
        pass
    return None


def build_backend(name: str, device: str):
    # SEA-RAFT and WAFT were promoted to uw/ in Phase 2B and their
    # exploratory duplicates deleted; this study now drives the same classes
    # the metric does, which is what keeps its numbers reproducible.
    if name == "searaft":
        from uw.searaft import SeaRaftBackend
        return SeaRaftBackend(device=device)
    if name == "waft":
        from uw.waft import WaftBackend
        return WaftBackend(device=device)
    if name == "videoflow_mof":
        from experiments.week2a_flow.backends.videoflow_backend import VideoFlowMOFBackend
        return VideoFlowMOFBackend(device=device)
    raise ValueError(name)


def run_clip(backend, clip_name, clip_rel, start, out_dir, overwrite, save_flow=True):
    path = os.path.join(_REPO, clip_rel)
    frames_full = load_excerpt(path, start, EXCERPT_FRAMES)
    src_h, src_w = frames_full[0].image.shape[:2]
    eh, ew = eval_size_for(src_h, src_w)
    frames = downscale_linear(frames_full, eh, ew)

    clip_out = {
        "clip": clip_name,
        "source": clip_rel,
        "source_size_hw": [src_h, src_w],
        "eval_size_hw": [eh, ew],
        "excerpt_start_frame": start,
        "excerpt_frames": EXCERPT_FRAMES,
        "pairs": [],
    }
    peak_mps = 0.0

    for (li, lj) in PAIR_OFFSETS:
        gt, gt1 = start + li, start + lj
        pair_dir = os.path.join(out_dir, clip_name, f"pair_{gt}_{gt1}")

        fwd = backend.estimate(frames, li, lj)
        bwd = backend.estimate(frames, lj, li)
        m = mps_allocated_mb()
        if m:
            peak_mps = max(peak_mps, m)
        # A backend with a large transient (FlowIt holds a global HxWxHxW cost
        # volume) otherwise leaves the MPS allocator fragmented and pushes a
        # 24 GB machine into swap on the next pair. Measurement hygiene only:
        # it frees cached blocks between pairs, it does not change any result.
        _release_cache()

        lin_t = frames[li].image
        lin_t1 = frames[lj].image

        diag = pair_diagnostics(lin_t, lin_t1, fwd.flow, bwd.flow)
        diag["runtime_s_forward"] = fwd.metadata.get("runtime_s")
        diag["runtime_s_backward"] = bwd.metadata.get("runtime_s")
        diag["inference_size_hw"] = list(fwd.metadata.get("inference_size", ()))
        diag["output_size_hw"] = list(fwd.metadata.get("output_size", ()))
        diag["context_indices_forward_global"] = [
            start + i for i in fwd.metadata.get("context_indices", [])
        ]
        diag["context_indices_backward_global"] = [
            start + i for i in bwd.metadata.get("context_indices", [])
        ]

        # --- images (all on the evaluation grid) --------------------------
        save_rgb(os.path.join(pair_dir, "frame_t.png"),
                 linear_to_display_u8(lin_t), overwrite)
        save_rgb(os.path.join(pair_dir, "frame_t1.png"),
                 linear_to_display_u8(lin_t1), overwrite)

        # One shared magnitude scale for the forward and backward colour
        # wheels of this pair, so the two are directly comparable by eye.
        _, mm = flow_to_color(fwd.flow)
        fwd_rgb, _ = flow_to_color(fwd.flow, mm)
        bwd_rgb, _ = flow_to_color(bwd.flow, mm)
        save_rgb(os.path.join(pair_dir, "flow_forward.png"), fwd_rgb, overwrite)
        save_rgb(os.path.join(pair_dir, "flow_backward.png"), bwd_rgb, overwrite)
        diag["flow_viz_max_magnitude_px"] = float(mm)

        warped, inside = warp_to_source(lin_t1, fwd.flow)
        save_rgb(os.path.join(pair_dir, "warped_t1_to_t.png"),
                 linear_to_display_u8(warped), overwrite)
        save_rgb(os.path.join(pair_dir, "residual_warped.png"),
                 residual_to_display_u8(warped - lin_t), overwrite)
        save_rgb(os.path.join(pair_dir, "residual_uncompensated.png"),
                 residual_to_display_u8(lin_t1 - lin_t), overwrite)

        valid_from_diag, fb_err = _fb(fwd.flow, bwd.flow)
        save_gray(os.path.join(pair_dir, "fb_valid_mask.png"),
                  (valid_from_diag.astype(np.uint8) * 255), overwrite)
        save_rgb(os.path.join(pair_dir, "fb_error.png"),
                 colorize_scalar(fb_err, lo=0.0, hi=3.0), overwrite)

        if fwd.confidence is not None:
            save_rgb(os.path.join(pair_dir, "native_confidence_forward.png"),
                     colorize_scalar(fwd.confidence), overwrite)
        occ = fwd.metadata.get("native_occlusion")
        if occ is not None:
            save_rgb(os.path.join(pair_dir, "native_occlusion_forward.png"),
                     colorize_scalar(np.asarray(occ)), overwrite)

        if save_flow:
            # Raw fields, at the evaluation resolution, in the project's
            # (u, v) source->target convention. Saved so Phase 1B — and the
            # cross-backend disagreement analysis — can work from these
            # without paying for inference again. Not a visualisation:
            # float32, no scaling, no clipping.
            for tag, arr in (("forward", fwd.flow), ("backward", bwd.flow)):
                fp = os.path.join(pair_dir, f"flow_{tag}.npy")
                if os.path.exists(fp) and not overwrite:
                    raise FileExistsError(f"{fp!r} exists; pass --overwrite")
                os.makedirs(pair_dir, exist_ok=True)
                np.save(fp, arr.astype(np.float32))

        meta = {k: v for k, v in fwd.metadata.items() if k != "native_occlusion"}
        write_json(os.path.join(pair_dir, "meta.json"),
                   {"forward_metadata": meta, "diagnostics": diag}, overwrite)

        diag["pair"] = [gt, gt1]
        diag["output_dir"] = os.path.relpath(pair_dir, _REPO)
        clip_out["pairs"].append(diag)
        print(f"    pair {gt}->{gt1}: "
              f"fwd {diag['runtime_s_forward']:.2f}s  "
              f"fb_valid {diag['fb_valid_coverage_pct']:.1f}%  "
              f"|flow| med {diag['flow_magnitude_px']['median']:.2f}px",
              flush=True)

    clip_out["peak_mps_driver_allocated_mb"] = peak_mps or None
    return clip_out


def _fb(fwd, bwd):
    from uw.flow import forward_backward_consistency
    return forward_backward_consistency(fwd, bwd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True,
                    choices=["searaft", "waft", "videoflow_mof"])
    ap.add_argument("--device", default="mps")
    ap.add_argument("--excerpts", default="experiments/week2a_flow/excerpts.json")
    ap.add_argument("--out-root", default="outputs/flow_comparison")
    ap.add_argument("--clips", default=None, help="comma-separated subset")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--no-save-flow", action="store_true",
                    help="skip writing the raw .npy flow fields")
    args = ap.parse_args()

    with open(os.path.join(_REPO, args.excerpts)) as f:
        excerpts = json.load(f)

    out_dir = os.path.join(_REPO, args.out_root, args.backend)
    backend = build_backend(args.backend, args.device)

    write_json(os.path.join(out_dir, "environment.json"),
               backend.describe(), args.overwrite)

    wanted = args.clips.split(",") if args.clips else list(excerpts["clips"])
    results = []
    for name in wanted:
        info = excerpts["clips"][name]
        start = int(info["selected_excerpt_start"])
        start = max(0, min(start, info["frame_count"] - EXCERPT_FRAMES))
        print(f"  {args.backend} / {name} (frames {start}..{start + EXCERPT_FRAMES - 1})",
              flush=True)
        results.append(run_clip(backend, name, info["path"], start,
                                out_dir, args.overwrite, not args.no_save_flow))

    write_json(
        os.path.join(out_dir, "metrics.json"),
        {
            "backend": args.backend,
            "environment": backend.describe(),
            "eval_resolution_note": (
                "All flow and all diagnostics are at the common evaluation "
                "resolution (960x540, or 540x960 for portrait-decoding clips). "
                "Source frames are downscaled IN LINEAR LIGHT before the sRGB "
                "model-input view is built, so the model and the photometric "
                "residual see the same scene data. Nothing is upsampled back "
                "to source resolution."
            ),
            "fb_consistency": (
                "Sundaram-Brox-Keuper: valid <=> |w+w'|^2 <= 0.01*(|w|^2+|w'|^2) "
                "+ 0.5, w' bilinearly sampled from the backward flow at p+w. "
                "Pixels whose p+w leaves the frame are marked invalid and their "
                "error left NaN. Identical thresholds for every backend."
            ),
            "peak_process_rss_mb": peak_rss_mb(),
            "peak_process_rss_note": (
                "whole-process peak RSS for this backend's entire run "
                "(model + 12 decoded frames + all inferences), not per-inference"
            ),
            "clips": results,
        },
        args.overwrite,
    )
    print(f"\nwrote {out_dir}")


if __name__ == "__main__":
    main()
