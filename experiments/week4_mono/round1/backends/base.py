"""Week 4A — the common monocular backend contract.

EXPLORATORY. Imported inside each model venv.

The contract is deliberately narrow, because the ONE invariant Week 4A cannot
bend is strict single-image inference (`MONO_DEPTH_FREEZE.md`, and the task's
STOP condition 3):

    ONE frame in, ONE prediction out.
    No neighbouring images. No temporal state. No Week-3 geometry input.

So `infer()` takes ONE image path and nothing else. There is no batch argument,
no list argument and no sequence argument to get this wrong with. A backend
whose architecture is multi-view — Wat3R and MapAnything both are — hands its
model a one-element view list and asserts the model saw exactly one view.

WHY A PATH RATHER THAN AN ARRAY. Every entrant ships its own preprocessing
(resize rule, patch-size rounding, centre crop, normalisation) and S0's job is
to characterise that preprocessing, not to bypass it. Feeding each model the
file path its own reference loader expects keeps that code path intact.
Appearance perturbations in S4 are therefore written to disk as images before
inference, which also makes every perturbed input a traceable artifact rather
than an in-memory transformation nobody can re-inspect.

`native` is whatever the model actually emits, unmodified. `canonical_range` is
Euclidean camera-centre-to-point distance where the backend can produce one
honestly, and `None` where it cannot (Depth Anything V2 cannot: its affine
disparity ambiguity has to be resolved before an inverse means anything).
"""

from __future__ import annotations

import os
import time

import numpy as np


class MonoBackend:
    """One monocular model, wrapped so that only single-image inference is expressible."""

    key: str = ""
    checkpoint: str = ""
    native_kind: str = ""
    range_rule: str = ""

    def __init__(self, device: str = "mps", **kwargs):
        self.device = device
        self.kwargs = kwargs
        self.model = None
        self.load_seconds = float("nan")

    # -- lifecycle ---------------------------------------------------------

    def load(self) -> None:
        t0 = time.perf_counter()
        self._load()
        self.load_seconds = time.perf_counter() - t0

    def _load(self) -> None:
        raise NotImplementedError

    # -- inference ---------------------------------------------------------

    def infer(self, image_path: str) -> dict:
        """Run the model on exactly one image.

        Returns a dict with at least:
            native  (H,W) or (H,W,3) float32   the model's own output
            valid   (H,W) bool
        and optionally:
            canonical_range (H,W) float32, K (3,3), conf (H,W),
            aux {name: array}, extra {json-serialisable}
        """
        if not isinstance(image_path, (str, os.PathLike)):
            raise TypeError("infer() takes ONE image path; a sequence would break "
                            "the strict single-image invariant")
        t0 = time.perf_counter()
        out = self._infer(str(image_path))
        out.setdefault("extra", {})["infer_seconds"] = time.perf_counter() - t0
        return out

    def _infer(self, image_path: str) -> dict:
        raise NotImplementedError

    # -- description -------------------------------------------------------

    def semantics(self) -> dict:
        """What the output MEANS. Verified in S0, not inherited from a paper."""
        raise NotImplementedError

    def preprocessing(self) -> dict:
        """Crop/resize/letterbox behaviour, recorded from the actual code path."""
        return {}

    def preprocessed_image(self, image_path: str):
        """The image AS THE MODEL SEES IT, on the model's own inference grid.

        Returns (H,W,3) float in whatever range the model's normalisation
        produces, or None if the model exposes no such intermediate.

        This is what makes the S0 FOV audit a MEASUREMENT rather than a reading
        of the documentation: push an image carrying a marker at a known source
        pixel through the model's OWN preprocessing, find where the marker
        landed, and fit the source->grid map. Week 3 established that
        preprocessing can silently discard a third of the frame, and it found
        that by measuring, not by reading resize code.
        """
        return None

    def provenance(self) -> dict:
        raise NotImplementedError


# --------------------------------------------------------------------------
# helpers shared by several backends
# --------------------------------------------------------------------------


def ray_range_from_zdepth(z: np.ndarray, K: np.ndarray) -> np.ndarray:
    """Euclidean camera-centre range from planar z-depth and intrinsics.

    range = z * ||K^-1 [u, v, 1]||. This is the conversion the freeze doc calls
    out as the one that must NOT be skipped: `depth_metric = point[..., 2]` is
    z-depth, and treating it as range is a systematic radial error that grows
    toward the frame corners — exactly where M-6 looks.

    The pixel grid is integer (col, row) indices, i.e. the centre of the
    top-left pixel is (0, 0). That is `experiments/week3_geometry/phase3a/geometry.py`'s
    `pixel_grid` convention, and it is repeated here rather than imported only
    because these model venvs deliberately do not import the Week-3 package.
    Using a different half-pixel convention from the Week-3 reference would put
    a sub-pixel radial bias into every radius-binned residual.
    """
    h, w = z.shape
    K = np.asarray(K, dtype=np.float64)
    u, v = np.meshgrid(np.arange(w, dtype=np.float64),
                       np.arange(h, dtype=np.float64))
    uv1 = np.stack([u, v, np.ones_like(u)], axis=-1)
    dirs = uv1 @ np.linalg.inv(K).T                  # z == 1 for upper-triangular K
    factor = np.linalg.norm(dirs, axis=-1)
    out = z.astype(np.float64) * factor
    return np.where(np.isfinite(z) & (z > 0), out, np.nan).astype(np.float32)


def pixel_K_from_normalized(K_norm: np.ndarray, h: int, w: int) -> np.ndarray:
    """Normalised intrinsics (image spans 0..1) -> pixel intrinsics.

    MoGe and FoundationGeo both build K with `intrinsics_from_focal_center(fx,
    fy, 0.5, 0.5)`, i.e. in normalised image coordinates where the image spans
    [0,1] on each axis. Pixel u covers [u/w, (u+1)/w] and its CENTRE is at
    (u+0.5)/w, so with the integer-index pixel convention used throughout this
    project:

        x_n = (u + 0.5) / w        =>   u = x_n * w - 0.5
        fx_px = fx_n * w                cx_px = cx_n * w - 0.5

    The half pixel matters here for exactly one reason: it is a RADIAL offset of
    the principal point, and M-6 bins error by radius from the principal point.
    Dropping it would write a small radial bias straight into the diagnostic
    that triggers the camera-model challengers.
    """
    K = np.asarray(K_norm, dtype=np.float64).copy()
    K[0, 0] *= w
    K[0, 1] *= w
    K[1, 1] *= h
    K[0, 2] = K[0, 2] * w - 0.5
    K[1, 2] = K[1, 2] * h - 0.5
    return K


def norm_pointmap(points: np.ndarray) -> np.ndarray:
    """||p|| per pixel — the canonical range for every point-map model."""
    return np.linalg.norm(np.asarray(points, dtype=np.float64), axis=-1).astype(np.float32)


def finite_mask(*arrays: np.ndarray) -> np.ndarray:
    """Pixels where every supplied array is finite (last axis reduced for vectors)."""
    m = None
    for a in arrays:
        a = np.asarray(a)
        f = np.isfinite(a)
        if f.ndim == 3:
            f = f.all(axis=-1)
        m = f if m is None else (m & f)
    return m


def torch_device(name: str):
    import torch
    if name == "mps" and not torch.backends.mps.is_available():
        raise SystemExit("mps requested but unavailable")
    return torch.device(name)
