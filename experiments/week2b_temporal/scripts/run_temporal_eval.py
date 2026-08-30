"""Phase 2B temporal metric over the frozen test set. EXPLORATORY runner.

Evaluates SEA-RAFT-M + the Phase 2B temporal metrics on the frozen clips, at
the Phase 2A lag-study frame ranges and anchors so the numbers connect
directly to `experiments/week2a_flow/FINDINGS.md`. Everything the metric
computes is written to JSON, and selected residual visualisations are
rendered from the SAME inference the numbers came from (through the
`on_arrays` callback) rather than by re-running the model.

Needs torch — run from the isolated interpreter:

    experiments/week2a_flow/.venv-flow/bin/python \
        -m experiments.week2b_temporal.scripts.run_temporal_eval --overwrite

Outputs land in outputs/temporal_metric/<method>/, which is gitignored: they
are derived from local dive footage and stay local, same rule as the footage.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys

import numpy as np

_REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from experiments.week2a_flow.common import (  # noqa: E402
    colorize_scalar, linear_to_display_u8, residual_to_display_u8,
    save_gray, save_rgb,
)
from uw.baselines import gray_world  # noqa: E402
from uw.io import load  # noqa: E402
from uw.metrics import evaluate_temporal  # noqa: E402
from uw.searaft import SeaRaftBackend  # noqa: E402

# Phase 2A lag-study geometry, reused verbatim so the two studies look at the
# same stretch of footage: a 41-frame window centred on the bakeoff excerpt,
# anchors at local indices 16/18/20, identical across every lag.
WINDOW_FRAMES = 41
WINDOW_OFFSET = 14
ANCHORS = (16, 18, 20)
LAGS = (1, 4, 8)

METHODS = {"gray_world": gray_world, "none": None}


def apply_method(frames, name):
    if name == "none":
        return list(frames)
    return [METHODS[name](f) for f in frames]


class VisualSaver:
    """Renders diagnostics for ONE anchor per lag, from the pair's own arrays.

    Holds nothing: it is handed the payload, writes what it needs and
    returns. The evaluator drops the flow fields immediately afterwards.
    """

    def __init__(self, out_dir, clip, window_start, overwrite, anchor):
        self.out_dir, self.clip = out_dir, clip
        self.window_start, self.overwrite, self.anchor = window_start, overwrite, anchor

    def __call__(self, payload):
        if payload["index_t"] != self.anchor:
            return
        t = self.window_start + payload["index_t"]
        t1 = self.window_start + payload["index_t1"]
        d = os.path.join(self.out_dir, self.clip, f"lag{payload['lag']}_pair_{t}_{t1}")
        ow = self.overwrite

        save_rgb(os.path.join(d, "original_t.png"),
                 linear_to_display_u8(payload["original_t"]), ow)
        save_rgb(os.path.join(d, "corrected_t.png"),
                 linear_to_display_u8(payload["corrected_t"]), ow)
        save_rgb(os.path.join(d, "warped_corrected_t1.png"),
                 linear_to_display_u8(payload["warped_corrected"]), ow)
        save_rgb(os.path.join(d, "residual_input_raw.png"),
                 residual_to_display_u8(payload["warped_original"]
                                        - payload["original_t"]), ow)
        save_rgb(os.path.join(d, "residual_corrected_raw.png"),
                 residual_to_display_u8(payload["warped_corrected"]
                                        - payload["corrected_t"]), ow)
        save_rgb(os.path.join(d, "residual_input_illum_aware.png"),
                 residual_to_display_u8(payload["illum_warped_original"]
                                        - payload["original_t"]), ow)
        save_rgb(os.path.join(d, "residual_corrected_illum_aware.png"),
                 residual_to_display_u8(payload["illum_warped_corrected"]
                                        - payload["corrected_t"]), ow)
        save_rgb(os.path.join(d, "residual_uncompensated.png"),
                 residual_to_display_u8(payload["original_t1"]
                                        - payload["original_t"]), ow)
        save_gray(os.path.join(d, "valid_mask.png"),
                  payload["mask"].astype(np.uint8) * 255, ow)
        # What the illumination model actually removed, on the INPUT — the
        # picture that says whether a global gain can stand in for the light.
        removed = np.abs(payload["illum_warped_original"]
                         - payload["warped_original"]).mean(axis=2)
        save_rgb(os.path.join(d, "illumination_correction_magnitude.png"),
                 colorize_scalar(removed, invalid=~payload["mask"]), ow)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", default="gray_world", choices=sorted(METHODS))
    ap.add_argument("--clips", default=None)
    ap.add_argument("--device", default="mps")
    ap.add_argument("--out-root", default="outputs/temporal_metric")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--no-visuals", action="store_true")
    args = ap.parse_args()

    with open(os.path.join(_REPO, "experiments/week2a_flow/excerpts.json")) as f:
        excerpts = json.load(f)["clips"]
    wanted = args.clips.split(",") if args.clips else list(excerpts)

    out_dir = os.path.join(_REPO, args.out_root, args.method)
    backend = SeaRaftBackend(device=args.device)
    report = {
        "phase": "Week 2 Phase 2B — motion-aware temporal metric",
        "method_under_test": args.method,
        "backend": backend.describe(),
        "lags": list(LAGS),
        "window_frames": WINDOW_FRAMES,
        "anchors_local": list(ANCHORS),
        "geometry_note": (
            "41-frame window centred on the Phase 2A bakeoff excerpt, anchors "
            "at local 16/18/20 — identical to experiments/week2a_flow/scripts/"
            "run_lag_study.py, so these numbers sit beside that study's."
        ),
        "clips": {},
    }

    for name in wanted:
        info = excerpts[name]
        start = max(0, min(int(info["selected_excerpt_start"]) - WINDOW_OFFSET,
                           int(info["frame_count"]) - WINDOW_FRAMES))
        print(f"\n=== {name} ({args.method}) frames "
              f"{start}..{start + WINDOW_FRAMES - 1} ===", flush=True)
        frames = load(os.path.join(_REPO, info["path"]),
                      start=start, count=WINDOW_FRAMES)
        corrected = apply_method(frames, args.method)

        saver = None if args.no_visuals else VisualSaver(
            out_dir, name, start, args.overwrite, ANCHORS[0])
        result = evaluate_temporal(
            list(frames), corrected, backend, lags=LAGS, anchors=ANCHORS,
            alignment_robust=True, on_arrays=saver,
        )
        del frames, corrected

        entry = dataclasses.asdict(result)
        entry["source"] = info["path"]
        entry["frame_range"] = [start, start + WINDOW_FRAMES - 1]
        entry["anchors_global"] = [start + a for a in ANCHORS]
        report["clips"][name] = entry

        for lag in result.lags:
            print(f"  @{lag.lag}: raw {lag.raw_warp:.6f}  "
                  f"illum {lag.illumination_aware_warp:.6f}  "
                  f"uncomp {lag.uncompensated:.6f}  "
                  f"reduction {lag.motion_reduction_ratio:.2f}x  "
                  f"AR {lag.alignment_robust_warp:.6f}  "
                  f"dE {lag.temporal_delta_e:.3f}  "
                  f"cov {lag.valid_fraction:.1%}")
            print(f"       input: raw {lag.input_raw_warp:.6f}  "
                  f"illum {lag.input_illumination_aware_warp:.6f}  "
                  f"uncomp {lag.input_uncompensated:.6f}  "
                  f"reduction {lag.input_motion_reduction_ratio:.2f}x  "
                  f"AR {lag.input_alignment_robust_warp:.6f}  "
                  f"dE {lag.input_temporal_delta_e:.3f}")
            print(f"       illum: gain {lag.illumination.gain:.4f}  "
                  f"bias {lag.illumination.bias:+.5f}  "
                  f"explains {lag.illumination_explained_fraction:.1%} of input "
                  f"post-warp residual  confounded="
                  f"{'YES' if lag.illumination_confounded else 'no'}  "
                  f"[{lag.illumination.status}]")
            print(f"       status: {lag.status}", flush=True)

    path = os.path.join(out_dir, "temporal_metrics.json")
    if os.path.exists(path) and not args.overwrite:
        raise FileExistsError(f"{path!r} exists; pass --overwrite")
    os.makedirs(out_dir, exist_ok=True)
    with open(path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
