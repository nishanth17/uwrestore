"""Model-agnostic optical-flow abstraction.

This module defines the *interface*, the normative coordinate convention,
and the model-independent flow maths (resizing, warping, forward/backward
consistency), plus the two pieces of plumbing every wrapper needs: the
temporary sRGB model-input view and the import isolation that lets two
research repositories coexist in one process.

It contains **no backend implementation and no default backend**, and it
imports no model. Concrete wrappers live beside it — `uw/searaft.py` (the
canonical Phase 2B correspondence backend) and `uw/waft.py` (an optional
manual cross-check) — and each imports torch lazily, inside its own
constructor. Importing `uw.flow`, or `uw.metrics`, therefore still costs
nothing, and `uw/metrics.py` receives a backend rather than choosing one.

Dependencies: numpy + opencv only (CLAUDE.md invariant 8). torch is a
concern of the individual wrappers, not of this module or of the package.

-------------------------------------------------------------------------
Coordinate convention (normative for this project)
-------------------------------------------------------------------------
A flow field is a float32 array of shape (H, W, 2):

  flow[y, x, 0] = u  horizontal displacement, +u points toward increasing
                     column index x (image right)
  flow[y, x, 1] = v  vertical displacement,   +v points toward increasing
                     row index y (image down)

Channel order is therefore (u, v) == (x, y), matching the Middlebury/Sintel
/ RAFT convention, *not* numpy's (row, col) axis order.

Direction: `estimate(frames, index_t, index_t1)` returns the flow **from**
`frames[index_t]` (the source) **to** `frames[index_t1]` (the target). A
scene point imaged at pixel (x, y) in the source frame is imaged at
(x + u, y + v) in the target frame. This is source -> target displacement.

Nothing requires index_t1 == index_t + 1. Backward flow is requested by
calling with the indices swapped; that is how this project obtains the
second inference needed for forward/backward consistency.

Units: pixels **at the resolution of the returned flow field**, which is
not necessarily the resolution of the source footage. A backend that runs
inference at a reduced resolution must say so in
`FlowResult.metadata["inference_size"]`, and any resize must go through
`resize_flow()` so the vector magnitudes are rescaled with the grid.
"""

from __future__ import annotations

import contextlib
import os
import sys
from dataclasses import dataclass, field
from typing import Sequence

import cv2
import numpy as np

from uw.colorspace import linear_to_srgb


def model_input_srgb_u8(frame) -> np.ndarray:
    """Temporary, model-only inference view of a linear-light Frame.

    Pretrained flow models are trained on ordinary display-encoded imagery,
    so feeding one a linear-light Frame is a silent domain shift that crushes
    exactly the shadow detail a matcher relies on. This builds an sRGB-encoded
    uint8 RGB view for correspondence estimation ONLY.

    It does not mutate the Frame, is never written back into a Frame, and is
    never used for measurement: every photometric residual in this project is
    computed on `frame.image`, i.e. in linear light.

    Lives here, once, rather than in each backend: it is a convention shared
    by every wrapper, and a convention duplicated per backend is a convention
    that eventually differs per backend.
    """
    srgb = linear_to_srgb(frame.image)  # clips to [0, 1] by definition
    return np.clip(srgb * 255.0 + 0.5, 0, 255).astype(np.uint8)


@contextlib.contextmanager
def isolated_repo_imports(paths: Sequence[str]):
    """Import a research repo's flat top-level packages without leaking them.

    Every one of these repositories ships a top-level `config/`, `utils/` and
    `model/` that has to be on `sys.path` for its own modules to import each
    other. Those names collide: with SEA-RAFT's `core/` on the path first,
    WAFT's `from utils.utils import Padder` resolves to SEA-RAFT's
    `core/utils/utils.py` and raises ImportError. Phase 2A avoided this by
    running one backend per process; a cross-check that wants both in one
    process cannot.

    So each backend imports inside this context, which afterwards restores
    `sys.path` and evicts from `sys.modules` exactly those modules that were
    loaded FROM the given paths. Modules from anywhere else (torch and its
    submodules, most importantly) are left alone — evicting those would make
    a later import build duplicate class objects and quietly break
    `isinstance`.

    An already-constructed model keeps working after eviction, because its
    objects hold direct references to their classes and functions rather than
    looking them up in `sys.modules`. What the eviction buys is that the NEXT
    backend's imports start clean.
    """
    roots = tuple(os.path.abspath(p) for p in paths)
    saved_path = list(sys.path)
    before = set(sys.modules)
    for p in reversed(roots):
        sys.path.insert(0, p)
    try:
        yield
    finally:
        sys.path[:] = saved_path
        # Decide everything BEFORE deleting anything. A namespace package's
        # __path__ is lazy and recomputes itself by looking its parent up in
        # sys.modules, so evicting as we go raises KeyError on the next
        # sibling. Two passes, and every lookup defensive.
        doomed = []
        for name in set(sys.modules) - before:
            module = sys.modules.get(name)
            if module is None:
                continue
            origin = getattr(module, "__file__", None)
            if origin is None:
                try:  # namespace package: judge it by where its search path points
                    origin = next(iter(list(getattr(module, "__path__", []))), None)
                except Exception:
                    origin = None
            if origin and any(
                os.path.abspath(origin).startswith(root + os.sep) for root in roots
            ):
                doomed.append(name)
        for name in doomed:
            sys.modules.pop(name, None)


# Forward/backward consistency thresholds. These are the standard
# Sundaram-Brox-Keuper (2010) values and are applied IDENTICALLY to every
# backend — they are deliberately not tuned per model.
FB_ALPHA = 0.01
FB_BETA = 0.5


@dataclass
class FlowResult:
    """One estimated flow field plus whatever the backend natively exposes.

    flow:        (H, W, 2) float32, (u, v) source -> target — see the module
                 docstring for the full convention.
    valid_mask:  (H, W) bool. The backend's *own* notion of where the flow
                 is usable. Backends differ in what they mean by this, so it
                 is NOT the basis for cross-backend comparison; use
                 forward_backward_consistency() for that. At minimum every
                 backend marks non-finite flow invalid here.
    confidence:  (H, W) float32 or None. Native confidence / uncertainty /
                 occlusion output, in whatever units the model produces.
                 Not comparable across backends; saved for inspection only.
    metadata:    free-form provenance. Keys this project relies on:
                   backend, checkpoint, device,
                   inference_size    (h, w) the network actually saw
                   output_size       (h, w) of `flow` as returned
                   source_size       (h, w) of the Frame images
                   index_t, index_t1
                   context_indices   frame indices used (multi-frame models)
                   runtime_s
    """

    flow: np.ndarray
    valid_mask: np.ndarray
    confidence: np.ndarray | None = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.flow.ndim != 3 or self.flow.shape[2] != 2:
            raise ValueError(f"flow must be (H, W, 2), got {self.flow.shape}")
        if self.valid_mask.shape != self.flow.shape[:2]:
            raise ValueError(
                f"valid_mask shape {self.valid_mask.shape} does not match "
                f"flow spatial shape {self.flow.shape[:2]}"
            )


class OpticalFlowBackend:
    """Interface every flow backend implements.

    Deliberately not pairwise-only: `estimate` receives the whole frame
    sequence plus the two indices of interest, so a pairwise model can use
    just frames[index_t] / frames[index_t1] while a multi-frame model is
    free to read neighbouring frames for temporal context. Which frames a
    multi-frame model actually consumed must be reported back in
    FlowResult.metadata["context_indices"].

    Implementations receive linear-light Frames (the project invariant) and
    are responsible for building their own temporary, model-specific
    inference view (e.g. linear -> sRGB encoding, normalisation, padding,
    resizing). They must not mutate the Frames they are given.
    """

    name: str = "unnamed"

    def describe(self) -> dict:
        """Provenance: model, checkpoint, versions, device, preprocessing."""
        raise NotImplementedError

    def estimate(
        self,
        frames: Sequence,  # Sequence[uw.types.Frame] / FrameSequence
        index_t: int,
        index_t1: int,
    ) -> FlowResult:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Model-independent flow maths
# ---------------------------------------------------------------------------


def resize_flow(flow: np.ndarray, out_h: int, out_w: int) -> np.ndarray:
    """Resample a flow field to (out_h, out_w), rescaling vector magnitudes.

    A flow vector is a displacement measured in pixels of its own grid, so
    changing the grid must change the numbers: halving the width halves
    every horizontal displacement. Resampling the array without rescaling
    the vectors is the single most common flow bug, hence one function that
    always does both.
    """
    flow = np.asarray(flow, dtype=np.float32)
    in_h, in_w = flow.shape[:2]
    if (in_h, in_w) == (out_h, out_w):
        return flow.copy()
    # INTER_LINEAR both ways: flow fields are smooth almost everywhere and
    # area-averaging a field with occlusion discontinuities is no better.
    resized = cv2.resize(flow, (out_w, out_h), interpolation=cv2.INTER_LINEAR)
    resized = resized.astype(np.float32, copy=False).reshape(out_h, out_w, 2)
    scaled = resized.copy()
    scaled[..., 0] *= float(out_w) / float(in_w)  # u scales with width
    scaled[..., 1] *= float(out_h) / float(in_h)  # v scales with height
    return scaled


def resize_mask(mask: np.ndarray, out_h: int, out_w: int) -> np.ndarray:
    """Nearest-neighbour resample of a boolean mask (no interpolation)."""
    mask = np.asarray(mask)
    if mask.shape[:2] == (out_h, out_w):
        return mask.astype(bool).copy()
    resized = cv2.resize(
        mask.astype(np.uint8), (out_w, out_h), interpolation=cv2.INTER_NEAREST
    )
    return resized.astype(bool)


def _coord_grid(h: int, w: int):
    xs, ys = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    return xs, ys


def warp_to_source(target_image: np.ndarray, flow: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Warp the target frame into the source frame's pixel grid.

    Given `flow` = source -> target (the convention above), the source-grid
    pixel (x, y) samples the target at (x + u, y + v). The result is
    therefore "frame t+1 as it would look if the camera/scene had not moved
    between t and t+1", directly comparable to frame t.

    Returns (warped, inside_mask). `inside_mask` is False where the sample
    location fell outside the target image or the flow was non-finite;
    `warped` is zero there.

    Operates on whatever image data it is handed. In this project that is
    LINEAR-LIGHT data for any photometric residual measurement — the sRGB
    view built for a model's input never comes back here.
    """
    target_image = np.asarray(target_image, dtype=np.float32)
    h, w = flow.shape[:2]
    if target_image.shape[:2] != (h, w):
        raise ValueError(
            f"target image {target_image.shape[:2]} and flow {(h, w)} must be "
            f"on the same grid; resize the flow with resize_flow() first"
        )
    xs, ys = _coord_grid(h, w)
    finite = np.isfinite(flow).all(axis=2)
    u = np.where(finite, flow[..., 0], 0.0).astype(np.float32)
    v = np.where(finite, flow[..., 1], 0.0).astype(np.float32)
    map_x = xs + u
    map_y = ys + v
    inside = (
        finite
        & (map_x >= 0)
        & (map_x <= w - 1)
        & (map_y >= 0)
        & (map_y <= h - 1)
    )
    warped = cv2.remap(
        target_image,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0.0,
    )
    if warped.ndim == 2:
        warped = warped[..., None]
    warped = warped.reshape(h, w, -1)
    warped[~inside] = 0.0
    if target_image.ndim == 2:
        warped = warped[..., 0]
    return warped, inside


def sample_flow(flow: np.ndarray, map_x: np.ndarray, map_y: np.ndarray) -> np.ndarray:
    """Bilinearly sample a flow field at arbitrary (sub-pixel) locations."""
    sampled = cv2.remap(
        np.asarray(flow, dtype=np.float32),
        map_x.astype(np.float32),
        map_y.astype(np.float32),
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0.0,
    )
    return sampled.reshape(map_x.shape[0], map_x.shape[1], 2)


def forward_backward_consistency(
    flow_fwd: np.ndarray,
    flow_bwd: np.ndarray,
    alpha: float = FB_ALPHA,
    beta: float = FB_BETA,
) -> tuple[np.ndarray, np.ndarray]:
    """The common cross-backend validity / occlusion diagnostic.

    Different models expose different, incomparable native notions of
    confidence, uncertainty and occlusion. This function derives one
    diagnostic that means the same thing for all of them, from flow alone.

    Formula (Sundaram, Brox & Keuper 2010, eq. 6). For each pixel p on the
    source grid:

        w  = flow_fwd(p)                       # source -> target
        p' = p + w                             # its location in the target
        w' = flow_bwd(p')                      # target -> source, bilinear
        e  = || w + w' ||                      # round-trip error, pixels

        valid  <=>  e^2  <=  alpha * (||w||^2 + ||w'||^2) + beta

    alpha = 0.01, beta = 0.5 — the published values, applied identically to
    every backend. They are NOT re-tuned per model: the point is a shared
    yardstick, not the flattering one for each contender.

    Boundary handling: a pixel whose p' falls outside the target image has
    no round-trip to check, so it is marked INVALID and its error is set to
    NaN rather than to a fabricated finite number. Same for pixels where
    either flow field is non-finite. Note this makes the mask conservative
    at frame edges under strong camera motion, identically for all backends.

    Returns (valid_mask (H, W) bool, fb_error (H, W) float32, NaN where the
    round trip could not be evaluated).
    """
    flow_fwd = np.asarray(flow_fwd, dtype=np.float32)
    flow_bwd = np.asarray(flow_bwd, dtype=np.float32)
    if flow_fwd.shape != flow_bwd.shape:
        raise ValueError(
            f"forward {flow_fwd.shape} and backward {flow_bwd.shape} flow must "
            f"be on the same grid"
        )
    h, w = flow_fwd.shape[:2]
    xs, ys = _coord_grid(h, w)

    finite_fwd = np.isfinite(flow_fwd).all(axis=2)
    u = np.where(finite_fwd, flow_fwd[..., 0], 0.0).astype(np.float32)
    v = np.where(finite_fwd, flow_fwd[..., 1], 0.0).astype(np.float32)
    map_x = xs + u
    map_y = ys + v
    inside = (map_x >= 0) & (map_x <= w - 1) & (map_y >= 0) & (map_y <= h - 1)

    # Non-finite backward flow would poison the bilinear samples of its
    # finite neighbours, so zero it out and track where it was. The finite
    # mask is eroded by one pixel first: a bilinear sample at (x, y) reads
    # the four pixels around it, so a source pixel is only trustworthy if
    # the whole 2x2 support was finite, not just the nearest neighbour.
    finite_bwd = np.isfinite(flow_bwd).all(axis=2)
    bwd_clean = np.where(finite_bwd[..., None], flow_bwd, 0.0).astype(np.float32)
    finite_bwd_support = cv2.erode(
        finite_bwd.astype(np.uint8), np.ones((3, 3), np.uint8), borderValue=1
    ).astype(np.float32)
    bwd_finite_at = cv2.remap(
        finite_bwd_support,
        map_x, map_y,
        interpolation=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT, borderValue=0.0,
    ) > 0.5

    w_back = sample_flow(bwd_clean, map_x, map_y)

    round_trip = np.stack([u + w_back[..., 0], v + w_back[..., 1]], axis=-1)
    err_sq = (round_trip ** 2).sum(axis=2)
    mag_sq = (u ** 2 + v ** 2) + (w_back ** 2).sum(axis=2)

    evaluable = finite_fwd & inside & bwd_finite_at
    valid = evaluable & (err_sq <= alpha * mag_sq + beta)

    fb_error = np.sqrt(err_sq).astype(np.float32)
    fb_error[~evaluable] = np.nan
    return valid, fb_error


def flow_magnitude(flow: np.ndarray) -> np.ndarray:
    """Per-pixel |flow| in pixels of the flow field's own grid."""
    flow = np.asarray(flow, dtype=np.float32)
    return np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)


class CachingFlowBackend(OpticalFlowBackend):
    """Wraps another backend and memoizes estimate() by the IDENTITY of the
    two Frame objects actually being compared, not by the identity of the
    sequence container they came from.

    Why this exists (Week 2 Phase 2C/2D, "evaluation reuse across correction
    configurations"): `uw.metrics.evaluate_temporal_pair` always calls
    `backend.estimate(original, ...)` — never the corrected sequence — so
    correspondence for a given original clip is identical no matter which
    correction configuration is being scored. Scoring several configurations
    (none, gray_world, white_patch, clahe, ...) on the same clip in one
    session should not pay for SEA-RAFT inference once per configuration.

    Why the key is `(id(frames[index_t]), id(frames[index_t1]))` and NOT
    `id(frames)`: `uw.metrics.evaluate_temporal` does `original =
    list(original)` unconditionally on entry (a deliberate, frozen part of
    that function — not something this wrapper may change), which builds a
    brand-new list object on every call even when the caller passed the
    exact same sequence. `id(frames)` would therefore miss on every single
    call, defeating the whole point. `list(x)` copies references, not the
    Frame objects themselves, so `id(frames[i])` for each element IS stable
    across that rewrap — keying on the elements actually being compared,
    rather than on whatever container currently holds them, is what makes
    reuse work through evaluate_temporal's own preprocessing.

    Still deliberately identity-based, pair-local caching, not a
    general-purpose content cache: the caller must pass a sequence
    containing the literal SAME Frame objects on every call for a hit to
    occur — which is exactly what a batch evaluation loop naturally does
    when it resizes the original sequence to the metric grid ONCE (one call
    to resize_sequence_linear, which builds each Frame exactly once) and
    reuses that same list of Frames across configurations (see
    experiments/week2c2d_baselines/). A different clip, or a second,
    independent call to resize_sequence_linear on pixel-identical data,
    builds NEW Frame objects and is correctly a miss — this is pair-local
    reuse within one evaluation run, not a content-addressed cache that
    would need to hash frame pixels to be correct.

    Explicit instance state, not a module-level global (CLAUDE.md invariant
    3: no hidden state in globals/singletons): the cache lives and dies with
    one CachingFlowBackend instance, i.e. with one evaluation run. It never
    touches uw.metrics — evaluate_temporal / evaluate_temporal_pair are
    unmodified and unaware this wrapper exists; reuse happens entirely on
    this side of the OpticalFlowBackend interface.

    Bounded by construction, not by an eviction policy: for one clip's
    evaluation window the number of distinct (index_t, index_t1) pairs
    requested is small (anchors x lags x 2 directions), so an unbounded dict
    stays small. A backend that streams a much larger window should not
    reach for this wrapper without adding one.
    """

    def __init__(self, inner: OpticalFlowBackend):
        self._inner = inner
        self._cache: dict = {}
        self.hits = 0
        self.misses = 0
        self.name = getattr(inner, "name", "cached")

    def describe(self) -> dict:
        d = dict(self._inner.describe())
        d["cache_hits"] = self.hits
        d["cache_misses"] = self.misses
        return d

    def estimate(self, frames, index_t: int, index_t1: int) -> FlowResult:
        source, target = frames[index_t], frames[index_t1]
        key = (id(source), id(target))
        entry = self._cache.get(key)
        # The entry keeps STRONG references to the two Frames the key was
        # built from, and they are re-checked by identity here. Without
        # that, a Frame could be garbage-collected and CPython could hand
        # its address to an unrelated object, turning a genuine miss into a
        # false hit that returns stale flow — reproduced directly: after
        # caching one pair and freeing an element, a replacement object
        # reused the id within 200 allocations and the cache returned the
        # previous FlowResult without calling the backend. Holding the
        # references also makes reuse mean what it says: an entry is live
        # exactly as long as the frames it describes.
        if entry is not None:
            cached_source, cached_target, result = entry
            if cached_source is source and cached_target is target:
                self.hits += 1
                return result
        self.misses += 1
        result = self._inner.estimate(frames, index_t, index_t1)
        self._cache[key] = (source, target, result)
        return result
