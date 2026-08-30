"""Shared helpers for the Week 2 Phase 1A optical-flow bakeoff.

EXPLORATORY. This file, and everything else under experiments/week2a_flow/,
is scaffolding for one comparison session. It is not part of the uwrestore
package, is not installed, and nothing under uw/ imports it. Only the
abstraction it targets (uw/flow.py) is permanent.

Runs in the isolated interpreter experiments/week2a_flow/.venv-flow
(Python 3.13 + torch), not the main project venv.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass

import cv2
import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from uw.colorspace import linear_to_srgb, srgb_to_linear  # noqa: E402
from uw.flow import (  # noqa: E402
    model_input_srgb_u8 as _model_input_srgb_u8,
    flow_magnitude,
    forward_backward_consistency,
    resize_flow,
    warp_to_source,
)
from uw.types import Frame, FrameSequence  # noqa: E402

VENDOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor")
CHECKPOINTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "checkpoints")

# Common evaluation resolution. 960x540 is half of 1920x1080 in each
# dimension, is the trained image_size of the SEA-RAFT and FlowIt
# checkpoints used here and close to VideoFlow's 432x960, and keeps a
# 5-clip x 3-pair x 2-direction x N-backend sweep tractable on an M4 CPU/MPS.
# Portrait-decoding clips get the transpose (540x960) so every clip is
# compared at the same pixel count and the same downscale factor.
EVAL_LONG_SIDE = 960
EVAL_SHORT_SIDE = 540


def eval_size_for(src_h: int, src_w: int) -> tuple[int, int]:
    """(h, w) evaluation grid for a source frame size, preserving orientation."""
    if src_w >= src_h:
        return EVAL_SHORT_SIDE, EVAL_LONG_SIDE
    return EVAL_LONG_SIDE, EVAL_SHORT_SIDE


# ---------------------------------------------------------------------------
# Ingest: short excerpts, without decoding a whole clip
# ---------------------------------------------------------------------------


def load_excerpt(path: str, start: int, count: int, profile: str = "srgb") -> FrameSequence:
    """Decode frames [start, start+count) of a video into linear-light Frames.

    uw.io.load() decodes an entire clip eagerly, which is fine for `uw score`
    but wasteful here (we need 8 frames out of 756). This reads only the
    range, applying the same ingest contract: RGB, float32, [0, 1], linear
    light, with the source transfer function stated explicitly.
    """
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise IOError(f"failed to open video {path!r}")
    fps = cap.get(cv2.CAP_PROP_FPS) or None
    frames = []
    try:
        for _ in range(start):
            if not cap.grab():
                raise IOError(f"{path!r}: ran out of frames before start index {start}")
        for i in range(count):
            ok, bgr = cap.read()
            if not ok:
                raise IOError(f"{path!r}: ran out of frames at index {start + i}")
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            if profile != "srgb":
                raise ValueError("this exploratory loader only handles the srgb profile")
            linear = srgb_to_linear(rgb).astype(np.float32)
            frames.append(
                Frame(
                    image=linear,
                    metadata={
                        "source_path": os.path.abspath(path),
                        "frame_index": start + i,
                        "fps": fps,
                        "transfer_function": "srgb",
                    },
                )
            )
    finally:
        cap.release()
    return FrameSequence(frames)


def downscale_linear(frames: FrameSequence, out_h: int, out_w: int) -> FrameSequence:
    """Resample Frames to the evaluation grid, IN LINEAR LIGHT.

    Area-averaging is only physically meaningful on linear radiance values,
    so the downscale happens here, before any sRGB encoding. Everything
    downstream — the model input view and the photometric residual — is then
    derived from this one linear image, so the model and the residual are
    looking at the same scene data.
    """
    out = []
    for f in frames:
        img = cv2.resize(f.image, (out_w, out_h), interpolation=cv2.INTER_AREA)
        meta = dict(f.metadata)
        meta["eval_resized_from"] = tuple(f.image.shape[:2])
        out.append(Frame(image=img.astype(np.float32), metadata=meta))
    return FrameSequence(out)


# Promoted to uw/flow.py in Phase 2B, when a second backend needed it too.
# Re-exported here so this study's scripts keep working and so there is
# exactly ONE definition of the temporary linear -> sRGB model-input view.
model_input_srgb_u8 = _model_input_srgb_u8


# ---------------------------------------------------------------------------
# Visualisation
# ---------------------------------------------------------------------------


def _color_wheel() -> np.ndarray:
    RY, YG, GC, CB, BM, MR = 15, 6, 4, 11, 13, 6
    ncols = RY + YG + GC + CB + BM + MR
    wheel = np.zeros((ncols, 3), dtype=np.float32)
    c = 0
    wheel[c:c+RY, 0] = 255; wheel[c:c+RY, 1] = np.floor(255 * np.arange(RY) / RY); c += RY
    wheel[c:c+YG, 0] = 255 - np.floor(255 * np.arange(YG) / YG); wheel[c:c+YG, 1] = 255; c += YG
    wheel[c:c+GC, 1] = 255; wheel[c:c+GC, 2] = np.floor(255 * np.arange(GC) / GC); c += GC
    wheel[c:c+CB, 1] = 255 - np.floor(255 * np.arange(CB) / CB); wheel[c:c+CB, 2] = 255; c += CB
    wheel[c:c+BM, 2] = 255; wheel[c:c+BM, 0] = np.floor(255 * np.arange(BM) / BM); c += BM
    wheel[c:c+MR, 2] = 255 - np.floor(255 * np.arange(MR) / MR); wheel[c:c+MR, 0] = 255
    return wheel


_WHEEL = _color_wheel()


def flow_to_color(flow: np.ndarray, max_mag: float | None = None) -> tuple[np.ndarray, float]:
    """Middlebury colour-wheel visualisation. Returns (rgb_uint8, max_mag).

    Hue = flow direction, saturation/value = magnitude normalised by
    `max_mag`. Pass an explicit `max_mag` to make two visualisations
    directly comparable; otherwise the 99th percentile of the finite
    magnitudes is used and returned so it can be recorded.
    """
    flow = np.asarray(flow, dtype=np.float32)
    finite = np.isfinite(flow).all(axis=2)
    u = np.where(finite, flow[..., 0], 0.0)
    v = np.where(finite, flow[..., 1], 0.0)
    mag = np.sqrt(u ** 2 + v ** 2)
    if max_mag is None:
        max_mag = float(np.percentile(mag[finite], 99)) if finite.any() else 1.0
    max_mag = max(float(max_mag), 1e-6)
    u_n, v_n = u / max_mag, v / max_mag
    rad = np.sqrt(u_n ** 2 + v_n ** 2)
    a = np.arctan2(-v_n, -u_n) / np.pi
    ncols = _WHEEL.shape[0]
    fk = (a + 1) / 2 * (ncols - 1)
    k0 = np.floor(fk).astype(np.int32)
    k1 = (k0 + 1) % ncols
    f = fk - k0
    img = np.zeros(flow.shape[:2] + (3,), dtype=np.float32)
    for ch in range(3):
        col0 = _WHEEL[k0, ch] / 255.0
        col1 = _WHEEL[k1, ch] / 255.0
        col = (1 - f) * col0 + f * col1
        idx = rad <= 1
        col = np.where(idx, 1 - rad * (1 - col), col * 0.75)
        img[..., ch] = np.clip(col, 0, 1) * 255
    img[~finite] = np.array([255, 0, 255])  # magenta = non-finite flow
    return img.astype(np.uint8), max_mag


def linear_to_display_u8(linear_rgb: np.ndarray) -> np.ndarray:
    """Linear-light RGB -> sRGB-encoded uint8, for saving a PNG a human reads."""
    return np.clip(linear_to_srgb(linear_rgb) * 255.0 + 0.5, 0, 255).astype(np.uint8)


def residual_to_display_u8(residual_linear: np.ndarray, gain: float = 8.0) -> np.ndarray:
    """Signed linear residual -> a viewable map.

    Absolute residual, gained up (underwater residuals are small in linear
    light) and encoded through the sRGB curve so mid-tones are visible.
    `gain` is fixed across every backend so the images are comparable.
    """
    mag = np.abs(residual_linear).mean(axis=2) if residual_linear.ndim == 3 else np.abs(residual_linear)
    scaled = np.clip(mag * gain, 0.0, 1.0)
    disp = linear_to_srgb(scaled)
    u8 = np.clip(disp * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return cv2.applyColorMap(u8, cv2.COLORMAP_INFERNO)[:, :, ::-1]  # BGR->RGB


def save_rgb(path: str, rgb_u8: np.ndarray, overwrite: bool = False) -> None:
    if os.path.exists(path) and not overwrite:
        raise FileExistsError(f"{path!r} exists; pass --overwrite to replace")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ok = cv2.imwrite(path, cv2.cvtColor(rgb_u8, cv2.COLOR_RGB2BGR))
    if not ok:
        raise IOError(f"failed to write {path!r}")


def save_gray(path: str, gray_u8: np.ndarray, overwrite: bool = False) -> None:
    if os.path.exists(path) and not overwrite:
        raise FileExistsError(f"{path!r} exists; pass --overwrite to replace")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ok = cv2.imwrite(path, gray_u8)
    if not ok:
        raise IOError(f"failed to write {path!r}")


def colorize_scalar(values: np.ndarray, invalid: np.ndarray | None = None,
                    lo: float | None = None, hi: float | None = None) -> np.ndarray:
    """Scalar map -> VIRIDIS RGB, invalid pixels magenta. Returns uint8 RGB."""
    v = np.asarray(values, dtype=np.float32)
    bad = ~np.isfinite(v) if invalid is None else (invalid | ~np.isfinite(v))
    good = ~bad
    if good.any():
        lo = float(np.percentile(v[good], 1)) if lo is None else lo
        hi = float(np.percentile(v[good], 99)) if hi is None else hi
    else:
        lo, hi = 0.0, 1.0
    if hi <= lo:
        hi = lo + 1e-6
    norm = np.clip((np.where(good, v, lo) - lo) / (hi - lo), 0, 1)
    u8 = (norm * 255).astype(np.uint8)
    rgb = cv2.applyColorMap(u8, cv2.COLORMAP_VIRIDIS)[:, :, ::-1].copy()
    rgb[bad] = np.array([255, 0, 255], dtype=np.uint8)
    return rgb


# ---------------------------------------------------------------------------
# Quantitative diagnostics
# ---------------------------------------------------------------------------


def _stats(arr: np.ndarray) -> dict:
    a = np.asarray(arr, dtype=np.float64)
    a = a[np.isfinite(a)]
    if a.size == 0:
        return {"mean": None, "median": None, "p95": None, "max": None}
    return {
        "mean": float(a.mean()),
        "median": float(np.median(a)),
        "p95": float(np.percentile(a, 95)),
        "max": float(a.max()),
    }


def pair_diagnostics(
    linear_t: np.ndarray,
    linear_t1: np.ndarray,
    flow_fwd: np.ndarray,
    flow_bwd: np.ndarray,
) -> dict:
    """All quantitative diagnostics for one (t, t+1) pair, one backend.

    Everything here is computed at the common evaluation resolution — no
    upsampling to source resolution, which would only add interpolation
    artefacts to numbers meant to compare models.

    The photometric residual is measured on LINEAR-LIGHT data (linear_t,
    linear_t1), never on the sRGB view built for the model.
    """
    valid, fb_err = forward_backward_consistency(flow_fwd, flow_bwd)
    warped, inside = warp_to_source(linear_t1, flow_fwd)

    finite_fwd = np.isfinite(flow_fwd).all(axis=2)
    finite_bwd = np.isfinite(flow_bwd).all(axis=2)
    n = float(flow_fwd.shape[0] * flow_fwd.shape[1])

    residual = warped - linear_t
    abs_res = np.abs(residual).mean(axis=2)

    # Uncompensated baseline: what the residual would be with zero flow.
    # Without it a "low residual" number is unreadable — a static shot has a
    # low residual no matter how bad the flow is.
    static_res = np.abs(linear_t1 - linear_t).mean(axis=2)

    def _res(mask):
        if not mask.any():
            return {"mae": None, "rmse": None, "coverage_pct": 0.0}
        return {
            "mae": float(abs_res[mask].mean()),
            "rmse": float(np.sqrt((residual[mask] ** 2).mean())),
            "coverage_pct": float(100.0 * mask.sum() / n),
        }

    mag = flow_magnitude(flow_fwd)
    mag = np.where(finite_fwd, mag, np.nan)

    return {
        "nonfinite_flow_pct_fwd": float(100.0 * (~finite_fwd).sum() / n),
        "nonfinite_flow_pct_bwd": float(100.0 * (~finite_bwd).sum() / n),
        "fb_valid_coverage_pct": float(100.0 * valid.sum() / n),
        "fb_evaluable_pct": float(100.0 * np.isfinite(fb_err).sum() / n),
        "fb_error_px_over_evaluable": _stats(fb_err),
        "fb_error_px_over_valid": _stats(np.where(valid, fb_err, np.nan)),
        "warp_residual_linear_over_fb_valid": _res(valid & inside),
        "warp_residual_linear_over_inside": _res(inside),
        "static_residual_linear_over_fb_valid": (
            {"mae": float(static_res[valid & inside].mean())}
            if (valid & inside).any() else {"mae": None}
        ),
        "static_residual_linear_all": {"mae": float(static_res.mean())},
        "flow_magnitude_px": _stats(mag),
        "warp_inside_pct": float(100.0 * inside.sum() / n),
    }


@dataclass
class Timer:
    label: str = ""
    seconds: float = 0.0

    def __enter__(self):
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.seconds = time.perf_counter() - self._t0
        return False


def write_json(path: str, obj, overwrite: bool = False) -> None:
    if os.path.exists(path) and not overwrite:
        raise FileExistsError(f"{path!r} exists; pass --overwrite to replace")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, sort_keys=False)
