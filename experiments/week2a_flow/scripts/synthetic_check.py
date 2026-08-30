"""Wrapper-correctness test on known synthetic motion. EXPLORATORY.

This checks the WRAPPER, not the model. Passing here means the plumbing
(channel order, flow direction, sign, resize rescaling, warping, finiteness)
is right. It says nothing about whether the model is any good underwater —
that is what the real-footage bakeoff is for.

Every case is built as a FIVE-frame sequence with constant-velocity motion,
not an isolated pair, so multi-frame backends get genuine temporal context
and are tested through exactly the same code path as the pairwise ones. The
evaluated pair is always (2, 3), the middle of the sequence.

Cases, all built from a real underwater frame so the texture statistics are
the ones we actually care about:

  A. Pure translation, built by cropping five offset windows out of the SAME
     full-resolution frame. No resampling, no invented border content, so
     the ground-truth flow is exactly (DX, DY) everywhere. The shift has
     |DX| != |DY| and opposite signs, so an x/y channel swap or a sign flip
     cannot pass.
  B. The same sequence evaluated as (3, 2): backward flow must come out as
     the negative of the forward flow. Catches forward/backward confusion.
  C. Cumulative off-centre zoom: ground truth is (s-1)*(p - c), a spatially
     varying field. Catches spatial flips/transposes a constant field can't.
  D. resize_flow(): the estimated field resampled to half and to 1.5x must
     keep the same *physical* motion, i.e. its mean vector must scale with
     the grid. Also checked against an analytic constant field, independent
     of any model.
  E. warp_to_source(): warping frame 3 by the estimated flow must land it
     back on frame 2, with a residual well below the uncompensated one.
     Measured on LINEAR-LIGHT data.
  F. No NaN / Inf anywhere in the returned flow.

Usage:  python -m experiments.week2a_flow.scripts.synthetic_check --backend searaft
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import cv2
import numpy as np

_REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from experiments.week2a_flow.common import load_excerpt  # noqa: E402
from uw.flow import flow_magnitude, resize_flow, warp_to_source  # noqa: E402
from uw.types import Frame, FrameSequence  # noqa: E402

# A murky frame: real particulate and low contrast, i.e. the hard case, not
# a synthetic checkerboard that every model trivially solves.
SOURCE_CLIP = "data/testset/murky/MURKYEEL.MP4"
SOURCE_FRAME = 300

N_FRAMES = 5
PAIR = (2, 3)

# Per-frame crop-origin step at source resolution. The resulting flow is the
# negative of the step (moving the window right moves the content left).
STEP_X, STEP_Y = -24, 10
DOWNSCALE = 2
CROP_W, CROP_H = 1800, 1000
ORIGIN_X, ORIGIN_Y = 120, 40
DX_EVAL, DY_EVAL = -STEP_X / DOWNSCALE, -STEP_Y / DOWNSCALE   # (12.0, -5.0)

ZOOM = 1.06
ZOOM_CENTER_FRAC = (0.35, 0.60)    # deliberately off-centre

TOL_PX = 1.0                       # wrapper-level pass tolerance
MARGIN = 60                        # interior margin for evaluation


def _frame(img, idx):
    return Frame(image=img.astype(np.float32),
                 metadata={"source_path": "synthetic", "frame_index": idx,
                           "fps": None, "transfer_function": "srgb"})


def build_translation_sequence(full_linear):
    """Five offset crops of one real frame; true eval flow = (DX, DY)/step."""
    frames = []
    ds = (CROP_W // DOWNSCALE, CROP_H // DOWNSCALE)
    for k in range(N_FRAMES):
        x0 = ORIGIN_X + k * STEP_X
        y0 = ORIGIN_Y + k * STEP_Y
        crop = full_linear[y0:y0 + CROP_H, x0:x0 + CROP_W]
        frames.append(cv2.resize(crop, ds, interpolation=cv2.INTER_AREA))
    gt = np.zeros(frames[0].shape[:2] + (2,), np.float32)
    gt[..., 0] = DX_EVAL
    gt[..., 1] = DY_EVAL
    return frames, gt


def build_zoom_sequence(base_linear):
    """Frame k = base zoomed by ZOOM**k about an off-centre point."""
    h, w = base_linear.shape[:2]
    cx, cy = ZOOM_CENTER_FRAC[0] * w, ZOOM_CENTER_FRAC[1] * h
    frames = []
    for k in range(N_FRAMES):
        s = ZOOM ** k
        m = np.array([[s, 0, cx * (1 - s)], [0, s, cy * (1 - s)]], np.float32)
        frames.append(cv2.warpAffine(base_linear, m, (w, h), flags=cv2.INTER_LINEAR,
                                     borderMode=cv2.BORDER_REFLECT101))
    xs, ys = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    gt = np.stack([(ZOOM - 1) * (xs - cx), (ZOOM - 1) * (ys - cy)], axis=-1)
    return frames, gt


def _interior(shape, margin=MARGIN):
    m = np.zeros(shape[:2], bool)
    m[margin:-margin, margin:-margin] = True
    return m


def _epe(flow, gt, mask):
    d = flow - gt
    return float(np.sqrt((d ** 2).sum(axis=2))[mask].mean())


def analytic_resize_check():
    """Model-independent: resize_flow must rescale magnitudes with the grid."""
    f = np.zeros((100, 200, 2), np.float32)
    f[..., 0] = 10.0
    f[..., 1] = -4.0
    half = resize_flow(f, 50, 100)
    up = resize_flow(f, 200, 300)
    return {
        "half_u_expected_5.0": float(half[..., 0].mean()),
        "half_v_expected_-2.0": float(half[..., 1].mean()),
        "up_u_expected_15.0": float(up[..., 0].mean()),
        "up_v_expected_-8.0": float(up[..., 1].mean()),
        "pass": bool(
            abs(half[..., 0].mean() - 5.0) < 1e-4
            and abs(half[..., 1].mean() + 2.0) < 1e-4
            and abs(up[..., 0].mean() - 15.0) < 1e-4
            and abs(up[..., 1].mean() + 8.0) < 1e-4
        ),
    }


def run(backend, report_path=None, overwrite=False):
    clip = os.path.join(_REPO, SOURCE_CLIP)
    full = load_excerpt(clip, SOURCE_FRAME, 1)[0].image

    imgs_t, gt_t = build_translation_sequence(full)
    seq_t = FrameSequence([_frame(im, i) for i, im in enumerate(imgs_t)])
    interior = _interior(imgs_t[0].shape)

    i0, i1 = PAIR
    fwd = backend.estimate(seq_t, i0, i1)
    bwd = backend.estimate(seq_t, i1, i0)

    imgs_z, gt_z = build_zoom_sequence(imgs_t[0])
    seq_z = FrameSequence([_frame(im, i) for i, im in enumerate(imgs_z)])
    fz = backend.estimate(seq_z, i0, i1)

    res = {
        "backend": backend.name,
        "sequence_length": N_FRAMES,
        "evaluated_pair": list(PAIR),
        "eval_grid": list(imgs_t[0].shape[:2]),
        "context_indices_forward": fwd.metadata.get("context_indices"),
        "context_indices_backward": bwd.metadata.get("context_indices"),
        "runtime_s_forward": fwd.metadata.get("runtime_s"),
        "cases": {},
    }

    # --- F: finiteness -----------------------------------------------------
    nonfinite = [int((~np.isfinite(r.flow)).sum()) for r in (fwd, bwd, fz)]
    res["cases"]["F_finite"] = {
        "nonfinite_counts_fwd_bwd_zoom": nonfinite, "pass": bool(sum(nonfinite) == 0)
    }

    # --- A: translation, direction / sign / channel order ------------------
    mu = float(fwd.flow[..., 0][interior].mean())
    mv = float(fwd.flow[..., 1][interior].mean())
    epe_t = _epe(fwd.flow, gt_t, interior)
    swapped_epe = _epe(fwd.flow[..., ::-1], gt_t, interior)
    res["cases"]["A_translation"] = {
        "ground_truth_uv": [DX_EVAL, DY_EVAL],
        "measured_mean_uv": [mu, mv],
        "epe_px": epe_t,
        "epe_px_if_channels_swapped": swapped_epe,
        "flow_shape": list(fwd.flow.shape),
        "pass": bool(
            abs(mu - DX_EVAL) < TOL_PX and abs(mv - DY_EVAL) < TOL_PX
            and mu > 0 and mv < 0                       # signs
            and swapped_epe > 5 * max(epe_t, 1e-3)      # channels not swapped
        ),
    }

    # --- B: forward vs backward -------------------------------------------
    bu = float(bwd.flow[..., 0][interior].mean())
    bv = float(bwd.flow[..., 1][interior].mean())
    res["cases"]["B_backward"] = {
        "expected_mean_uv": [-DX_EVAL, -DY_EVAL],
        "measured_mean_uv": [bu, bv],
        "pass": bool(abs(bu + DX_EVAL) < TOL_PX and abs(bv + DY_EVAL) < TOL_PX),
    }

    # --- C: spatially varying (off-centre zoom) ---------------------------
    epe_z = _epe(fz.flow, gt_z, interior)
    epe_z_fliplr = _epe(fz.flow, gt_z[:, ::-1], interior)
    epe_z_flipud = _epe(fz.flow, gt_z[::-1, :], interior)
    res["cases"]["C_zoom_spatial"] = {
        "zoom_per_frame": ZOOM,
        "gt_max_magnitude_px": float(flow_magnitude(gt_z)[interior].max()),
        "epe_px": epe_z,
        "epe_px_if_gt_flipped_lr": epe_z_fliplr,
        "epe_px_if_gt_flipped_ud": epe_z_flipud,
        "pass": bool(epe_z < 1.5 and epe_z_fliplr > 2 * epe_z and epe_z_flipud > 2 * epe_z),
    }

    # --- D: resize rescaling ----------------------------------------------
    h, w = fwd.flow.shape[:2]
    half = resize_flow(fwd.flow, h // 2, w // 2)
    onepointfive = resize_flow(fwd.flow, int(h * 1.5), int(w * 1.5))
    hi = _interior(half.shape, 30)
    ui = _interior(onepointfive.shape, 90)
    d = {
        "analytic": analytic_resize_check(),
        "half_grid_mean_uv": [float(half[..., 0][hi].mean()), float(half[..., 1][hi].mean())],
        "half_grid_expected_uv": [DX_EVAL / 2, DY_EVAL / 2],
        "1.5x_grid_mean_uv": [float(onepointfive[..., 0][ui].mean()),
                              float(onepointfive[..., 1][ui].mean())],
        "1.5x_grid_expected_uv": [DX_EVAL * 1.5, DY_EVAL * 1.5],
    }
    d["pass"] = bool(
        d["analytic"]["pass"]
        and abs(d["half_grid_mean_uv"][0] - DX_EVAL / 2) < TOL_PX
        and abs(d["half_grid_mean_uv"][1] - DY_EVAL / 2) < TOL_PX
        and abs(d["1.5x_grid_mean_uv"][0] - DX_EVAL * 1.5) < TOL_PX
        and abs(d["1.5x_grid_mean_uv"][1] - DY_EVAL * 1.5) < TOL_PX
    )
    res["cases"]["D_resize"] = d

    # --- E: warping (linear light) ----------------------------------------
    warped, inside = warp_to_source(imgs_t[i1], fwd.flow)
    m = inside & interior
    warp_mae = float(np.abs(warped - imgs_t[i0]).mean(axis=2)[m].mean())
    static_mae = float(np.abs(imgs_t[i1] - imgs_t[i0]).mean(axis=2)[m].mean())
    res["cases"]["E_warp_linear"] = {
        "warp_residual_mae_linear": warp_mae,
        "uncompensated_residual_mae_linear": static_mae,
        "reduction_ratio": float(static_mae / warp_mae) if warp_mae > 0 else None,
        "pass": bool(warp_mae < 0.5 * static_mae),
    }

    res["all_pass"] = bool(all(c["pass"] for c in res["cases"].values()))
    res["environment"] = backend.describe()

    print(json.dumps(res, indent=2, default=str))
    if report_path:
        if os.path.exists(report_path) and not overwrite:
            raise FileExistsError(f"{report_path!r} exists; pass --overwrite")
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w") as f:
            json.dump(res, f, indent=2, default=str)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True, choices=["searaft", "waft", "videoflow_mof"])
    ap.add_argument("--report", default=None)
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--device", default="mps")
    args = ap.parse_args()

    if args.backend == "searaft":
        from uw.searaft import SeaRaftBackend
        be = SeaRaftBackend(device=args.device)
    elif args.backend == "waft":
        from uw.waft import WaftBackend
        be = WaftBackend(device=args.device)
    else:
        from experiments.week2a_flow.backends.videoflow_backend import VideoFlowMOFBackend
        be = VideoFlowMOFBackend(device=args.device)

    res = run(be, args.report, args.overwrite)
    return 0 if res["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
