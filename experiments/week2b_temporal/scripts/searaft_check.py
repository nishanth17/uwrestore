"""Does the PRODUCTION SEA-RAFT wrapper still obey the coordinate convention?

EXPLORATORY (Week 2 Phase 2B). Phase 2A validated the *experimental* wrapper
under experiments/week2a_flow/backends/. Phase 2B promoted a wrapper into
`uw/searaft.py`, and a promoted copy is a new opportunity for a sign flip or
a channel swap, so the same known-motion test is re-run against the thing the
metric actually calls — and this time the pass criterion is the metric
itself, not just endpoint error.

Construction (unchanged from Phase 2A so the numbers are comparable): a
five-frame constant-velocity sequence made from five offset CROPS of one real
1080p underwater frame, so the ground-truth motion is exact, no pixel is
resampled and no border content is invented. Ground truth is (+12, -5) px at
the source scale; |dx| != |dy| with opposite signs, so a sign flip or an x/y
swap cannot hide.

Counterfactuals are reported beside the actual values: what the endpoint
error WOULD have been with the channels swapped, and what MC-Warp WOULD have
been with the flow negated. A test that cannot fail is not a test.

Needs torch — run from the isolated interpreter:

    experiments/week2a_flow/.venv-flow/bin/python \
        -m experiments.week2b_temporal.scripts.searaft_check --overwrite
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

_REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from uw.flow import forward_backward_consistency  # noqa: E402
from uw.io import load  # noqa: E402
from uw.metrics import (  # noqa: E402
    evaluate_temporal, metric_eval_size, resize_linear, temporal_warp_error,
)
from uw.searaft import SeaRaftBackend  # noqa: E402
from uw.types import Frame  # noqa: E402

CLIP = "data/testset/murky/MURKYEEL.MP4"
FRAME = 650
DX, DY = 12, -5          # ground truth at SOURCE scale, before the 2x downscale
N_FRAMES = 5


def build_sequence():
    """Five crops of one real frame, each offset by (DX, DY) from the last.

    Cropping rather than resampling means the ground truth is exact to the
    pixel: frame i is the same photons as frame 0, just read from a different
    window. Anything the metric reports is therefore the model's error plus
    the metric's own resampling of a fractional flow estimate.
    """
    frames = load(os.path.join(_REPO, CLIP), start=FRAME, count=1)
    full = frames[0].image
    h, w = full.shape[:2]
    pad = 2 * N_FRAMES * max(abs(DX), abs(DY))
    ch, cw = h - pad, w - pad
    seq = []
    for i in range(N_FRAMES):
        # The crop ORIGIN moves by (-DX, -DY), so the CONTENT moves by
        # (+DX, +DY) between consecutive frames — which is the direction the
        # flow convention describes. Getting this backwards is exactly the
        # mistake this test exists to catch, so the sign lives here once,
        # with its reason, rather than being applied to the expected value
        # afterwards where it could be quietly flipped to match a result.
        y0 = pad // 2 - i * DY
        x0 = pad // 2 - i * DX
        seq.append(full[y0:y0 + ch, x0:x0 + cw])
    return seq, (ch, cw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="mps")
    ap.add_argument("--out", default="outputs/temporal_metric/searaft_check.json")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    crops, (ch, cw) = build_sequence()
    eh, ew = metric_eval_size(ch, cw)
    scale_x, scale_y = ew / cw, eh / ch
    gt_u, gt_v = DX * scale_x, DY * scale_y
    frames = [Frame(image=resize_linear(c, eh, ew), metadata={"frame_index": i})
              for i, c in enumerate(crops)]

    backend = SeaRaftBackend(device=args.device)
    report = {
        "purpose": "coordinate-convention check of the promoted uw/searaft.py",
        "clip": CLIP, "source_frame": FRAME,
        "crop_size_hw": [ch, cw], "metric_size_hw": [eh, ew],
        "ground_truth_uv_source_px": [DX, DY],
        "ground_truth_uv_metric_px": [gt_u, gt_v],
        "backend": backend.describe(),
        "lags": {},
    }

    for lag in (1, 2):
        fwd = backend.estimate(frames, 1, 1 + lag)
        bwd = backend.estimate(frames, 1 + lag, 1)
        gt = np.zeros_like(fwd.flow)
        gt[..., 0], gt[..., 1] = gt_u * lag, gt_v * lag

        epe = float(np.sqrt(((fwd.flow - gt) ** 2).sum(axis=2)).mean())
        swapped = gt[..., ::-1]
        epe_if_swapped = float(np.sqrt(((fwd.flow - swapped) ** 2).sum(axis=2)).mean())
        epe_backward = float(np.sqrt(((bwd.flow + gt) ** 2).sum(axis=2)).mean())

        valid, _ = forward_backward_consistency(fwd.flow, bwd.flow)
        img_t, img_t1 = frames[1].image, frames[1 + lag].image
        actual, cov = temporal_warp_error(img_t, img_t1, fwd.flow, valid)
        negated, _ = temporal_warp_error(img_t, img_t1, -fwd.flow, valid)
        uncompensated, _ = temporal_warp_error(
            img_t, img_t1, np.zeros_like(fwd.flow), valid)

        report["lags"][f"@{lag}"] = {
            "mean_flow_uv": [float(fwd.flow[..., 0].mean()),
                             float(fwd.flow[..., 1].mean())],
            "expected_uv": [gt_u * lag, gt_v * lag],
            "endpoint_error_px": epe,
            "endpoint_error_if_channels_swapped_px": epe_if_swapped,
            "backward_endpoint_error_px": epe_backward,
            "nonfinite_flow_fraction": float((~np.isfinite(fwd.flow)).mean()),
            "fb_valid_coverage": float(valid.mean()),
            "raw_mc_warp": actual,
            "raw_mc_warp_if_flow_negated": negated,
            "uncompensated_residual": uncompensated,
            "mc_warp_coverage": cov,
            "runtime_s": fwd.metadata.get("runtime_s"),
            "inference_size_hw": list(fwd.metadata.get("inference_size", ())),
        }
        print(f"@{lag}: flow ({fwd.flow[..., 0].mean():+.3f}, "
              f"{fwd.flow[..., 1].mean():+.3f}) vs expected "
              f"({gt_u * lag:+.3f}, {gt_v * lag:+.3f})  EPE {epe:.4f} px "
              f"(swapped would be {epe_if_swapped:.2f})")
        print(f"      MC-Warp {actual:.6f}  negated-flow {negated:.6f}  "
              f"uncompensated {uncompensated:.6f}  coverage {cov:.1%}")

    # And the same thing through the real API, so the whole path is exercised.
    result = evaluate_temporal(frames, frames, backend, lags=(1, 2),
                               anchors=(1,), eval_long_side=None)
    report["through_evaluate_temporal"] = [
        {"lag": lag.lag, "raw_warp": lag.raw_warp,
         "illumination_aware_warp": lag.illumination_aware_warp,
         "uncompensated": lag.uncompensated,
         "motion_reduction_ratio": lag.motion_reduction_ratio,
         "temporal_delta_e": lag.temporal_delta_e,
         "valid_fraction": lag.valid_fraction,
         "illumination_gain": lag.illumination.gain,
         "illumination_bias": lag.illumination.bias,
         "illumination_status": lag.illumination.status,
         "status": lag.status}
        for lag in result.lags
    ]
    for row in report["through_evaluate_temporal"]:
        print(f"evaluate_temporal @{row['lag']}: raw {row['raw_warp']:.6f}  "
              f"illum {row['illumination_aware_warp']:.6f}  "
              f"reduction {row['motion_reduction_ratio']:.2f}x  "
              f"coverage {row['valid_fraction']:.1%}  {row['status']}")

    path = os.path.join(_REPO, args.out)
    if os.path.exists(path) and not args.overwrite:
        raise FileExistsError(f"{path!r} exists; pass --overwrite")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
