"""Week 3 Phase 3A — project-owned geometry conventions and conversions.

EXPLORATORY. Scaffolding for one comparison session. Nothing under `uw/`
imports this and it is not installed. If a geometry path is selected it gets
promoted deliberately, the way `uw/flow.py` was in Phase 2B — not by accident.

Runs in the main project venv (numpy only). Tests: `tests/test_week3_geometry.py`.

This module exists because the single largest correctness risk in a
cross-family geometry bakeoff is not any model — it is silently comparing two
different quantities. Every convention this file assumes is stated here, and
every conversion it performs is unit-tested against synthetic geometry with a
known answer.

===========================================================================
CONVENTIONS THIS MODULE USES
===========================================================================

Coordinate frame
    OpenCV / COLMAP camera frame: right-handed, +x right across the image,
    +y DOWN the image, +z FORWARD along the optical axis into the scene.
    Points in front of the camera have z > 0.

Poses
    `T_cw` maps WORLD points to CAMERA points:  X_cam = R_cw @ X_world + t_cw.
        This is COLMAP's native convention (its `images.txt` quaternion and
        translation are exactly R_cw, t_cw), and the camera centre in world
        coordinates is C = -R_cw^T @ t_cw.
    `T_wc` maps CAMERA points to WORLD points and is the inverse. It is what
        most learned feed-forward models emit as "camera_poses"/"extrinsics",
        and its translation column IS the camera centre.
    Both are stored as 4x4 homogeneous matrices. `invert_se3` converts between
    them exactly (using R^T, not a general inverse) and is tested round-trip.

    Nothing in this module guesses which one a third-party file contains. The
    caller states it; the wrapper that reads a third-party format is the place
    that has to be right, and its choice is recorded in the run sidecar.

Range quantities — THE distinction this whole week turns on
    z_depth(u,v)      the +z coordinate of the scene point in the camera
                      frame. Planar. NOT a distance.
    ray_range(u,v)    Euclidean distance from the camera's projection centre
                      to the scene point, ||X_cam||. A distance.

    For a CENTRAL (pinhole) camera these are related exactly by the length of
    the normalised ray through the pixel:

        X_cam = z * K^-1 [u, v, 1]^T          (z is z_depth)
        ray_range = z * || K^-1 [u, v, 1]^T ||

    so `ray_range = z_depth * secant(angle from the optical axis)`. At a GoPro's
    field of view that factor reaches ~1.4 at the frame corners, so calling
    z-depth "range" is a ~40% error at the corners and 0% at the centre — a
    radially structured error, i.e. exactly the signature the refraction test
    looks for. Conflating them would manufacture a fake refraction result.
    `zdepth_to_ray_range` / `ray_range_to_zdepth` are the only sanctioned
    conversion, they require the intrinsics, and they are tested against a
    synthetic camera with an analytically known answer.

    water_path_length the propagation distance through WATER. This is what
                      Beer-Lambert attenuation actually integrates over and it
                      is the canonical quantity in `PLAN.md`'s common output
                      representation. For a central camera it is APPROXIMATED
                      by ray_range; the approximation charges the (millimetre)
                      air-and-glass segment to the water budget. This module
                      never silently substitutes one for the other: it carries
                      a `path_source` label instead (see `PathSource`).

    For a REFRACTIVE flat-port camera there is no single projection centre, so
    `ray_range` is not defined for it in the same sense and this module does
    NOT offer a conversion that pretends otherwise. Refractive geometry is
    compared through its own 3D points and its own observations; see
    `sample_at_observations`, which takes image observations from the
    reconstruction that produced them rather than re-projecting with a pinhole.

Validity
    Every dense field travels with a boolean `valid` mask. Non-finite values
    are never filled, never interpolated across, and never allowed to become
    zeros: they are propagated into the mask. `resize_range_field` and
    `sample_at_observations` both do this, and both are tested for it.

Scale
    `fit_global_scale` fits ONE scalar per (method-pair, clip) over all
    eligible observations pooled across frames — never one per frame. A
    per-frame fit is available separately as `per_frame_scale_trace` and is
    explicitly labelled a drift diagnostic, because per-frame renormalisation
    would hide exactly the temporal scale instability we need to see.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# --------------------------------------------------------------------------
# Labels for what a comparison quantity actually is. Carried in sidecars so a
# reader never has to guess whether a number is measured or approximated.
# --------------------------------------------------------------------------

#: `water_path_length` equals the modelled physical path through water.
PATH_SOURCE_WATER_EXACT = "water_path_exact"
#: `water_path_length` is the central-camera ray range, standing in for the
#: water path. Valid only while the camera-to-interface distance is negligible
#: against scene range (millimetres against metres for a GoPro).
PATH_SOURCE_RAY_RANGE_APPROX = "ray_range_approx_water_path"
#: The quantity is planar z-depth and has NOT been converted. Never comparable.
PATH_SOURCE_Z_DEPTH_RAW = "z_depth_unconverted"

PATH_SOURCES = (PATH_SOURCE_WATER_EXACT, PATH_SOURCE_RAY_RANGE_APPROX,
                PATH_SOURCE_Z_DEPTH_RAW)


# --------------------------------------------------------------------------
# SE(3)
# --------------------------------------------------------------------------

def invert_se3(T: np.ndarray) -> np.ndarray:
    """Exact inverse of a 4x4 rigid transform, using R^T rather than inv(T).

    Converts between the two pose conventions this project uses: given T_cw it
    returns T_wc and vice versa.
    """
    T = np.asarray(T, dtype=np.float64)
    if T.shape != (4, 4):
        raise ValueError(f"expected (4,4), got {T.shape}")
    R = T[:3, :3]
    t = T[:3, 3]
    out = np.eye(4, dtype=np.float64)
    out[:3, :3] = R.T
    out[:3, 3] = -R.T @ t
    return out


def camera_center_from_T_cw(T_cw: np.ndarray) -> np.ndarray:
    """Camera centre in world coordinates from a world->camera transform."""
    T_cw = np.asarray(T_cw, dtype=np.float64)
    return -T_cw[:3, :3].T @ T_cw[:3, 3]


def transform_points(T: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Apply a 4x4 rigid transform to (N,3) points."""
    T = np.asarray(T, dtype=np.float64)
    pts = np.asarray(pts, dtype=np.float64)
    if pts.ndim != 2 or pts.shape[1] != 3:
        raise ValueError(f"expected (N,3) points, got {pts.shape}")
    return pts @ T[:3, :3].T + T[:3, 3]


# --------------------------------------------------------------------------
# Central-camera rays: z-depth <-> ray range
# --------------------------------------------------------------------------

def pixel_grid(h: int, w: int) -> tuple[np.ndarray, np.ndarray]:
    """(u, v) pixel-centre coordinate grids of shape (h, w).

    Pixel centres, i.e. integer (col, row) indices. This matches OpenCV's and
    COLMAP's convention in which the centre of the top-left pixel is (0, 0);
    COLMAP's own principal point defaults sit at (w/2, h/2) under the same
    convention. The bakeoff only ever needs consistency between this grid and
    the intrinsics that came with the same reconstruction, and the half-pixel
    question is far below the effects being measured -- but it is stated here
    rather than left implicit.
    """
    u, v = np.meshgrid(np.arange(w, dtype=np.float64),
                       np.arange(h, dtype=np.float64))
    return u, v


def ray_directions_from_K(K: np.ndarray, h: int, w: int,
                          normalize: bool = True) -> np.ndarray:
    """(h,w,3) camera-frame ray directions for a pinhole camera.

    Returns K^-1 [u,v,1]^T per pixel, unit-normalised by default. With
    `normalize=False` the returned rays have z == 1, which is the form in which
    `ray_range = z_depth * ||ray||` holds directly.
    """
    K = np.asarray(K, dtype=np.float64)
    if K.shape != (3, 3):
        raise ValueError(f"expected (3,3) intrinsics, got {K.shape}")
    u, v = pixel_grid(h, w)
    ones = np.ones_like(u)
    uv1 = np.stack([u, v, ones], axis=-1)          # (h,w,3)
    dirs = uv1 @ np.linalg.inv(K).T                # (h,w,3), z == 1 for a
    if normalize:                                  #   standard upper-triangular K
        n = np.linalg.norm(dirs, axis=-1, keepdims=True)
        dirs = dirs / np.where(n > 0, n, 1.0)
    return dirs


def ray_length_factor(K: np.ndarray, h: int, w: int) -> np.ndarray:
    """(h,w) secant factor: ray_range = z_depth * factor, for a pinhole camera."""
    return np.linalg.norm(ray_directions_from_K(K, h, w, normalize=False), axis=-1)


def zdepth_to_ray_range(z_depth: np.ndarray, K: np.ndarray) -> np.ndarray:
    """Planar z-depth -> Euclidean camera-to-point distance, for a CENTRAL camera.

    Non-finite and non-positive z are propagated as NaN rather than converted:
    a z <= 0 is a point behind the camera, which has no meaningful range.
    """
    z = np.asarray(z_depth, dtype=np.float64)
    if z.ndim != 2:
        raise ValueError(f"expected (H,W) z-depth, got {z.shape}")
    f = ray_length_factor(K, z.shape[0], z.shape[1])
    out = z * f
    return np.where(np.isfinite(z) & (z > 0), out, np.nan)


def ray_range_to_zdepth(ray_range: np.ndarray, K: np.ndarray) -> np.ndarray:
    """Euclidean camera-to-point distance -> planar z-depth, for a CENTRAL camera."""
    r = np.asarray(ray_range, dtype=np.float64)
    if r.ndim != 2:
        raise ValueError(f"expected (H,W) ray range, got {r.shape}")
    f = ray_length_factor(K, r.shape[0], r.shape[1])
    out = r / f
    return np.where(np.isfinite(r) & (r > 0), out, np.nan)


def scale_intrinsics(K: np.ndarray, src_hw: tuple[int, int],
                     dst_hw: tuple[int, int]) -> np.ndarray:
    """Rescale a pinhole K from one image grid to another.

    Uses the pixel-index convention of `pixel_grid`: a resize by factor s maps
    index i to s*i + (s-1)/2, so the principal point transforms as
    c' = s*c + (s-1)/2 while focal lengths scale by s. Getting this wrong puts a
    sub-pixel radial bias into every radius-binned residual, which is the one
    place this bakeoff cannot afford one.
    """
    K = np.asarray(K, dtype=np.float64).copy()
    sh, sw = src_hw
    dh, dw = dst_hw
    sy, sx = dh / float(sh), dw / float(sw)
    K[0, 0] *= sx
    K[1, 1] *= sy
    K[0, 1] *= sx
    K[0, 2] = sx * K[0, 2] + (sx - 1.0) / 2.0
    K[1, 2] = sy * K[1, 2] + (sy - 1.0) / 2.0
    return K


# --------------------------------------------------------------------------
# Dense field handling: resize, validity, sampling at observations
# --------------------------------------------------------------------------

def resize_range_field(field: np.ndarray, valid: np.ndarray,
                       dst_hw: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    """Nearest-neighbour resize of a range field and its validity mask.

    Nearest neighbour, deliberately. Averaging range across a depth
    discontinuity invents a surface that is in neither the near nor the far
    object, and those invented values sit exactly at the object boundaries
    where a restoration error would be most visible. A resize must not create
    range values that no method produced.

    Invalid pixels never contribute: the mask is resized with the same
    nearest-neighbour map, and any sample landing on an invalid or non-finite
    source pixel comes back invalid with a NaN value.
    """
    field = np.asarray(field, dtype=np.float64)
    valid = np.asarray(valid, dtype=bool)
    if field.shape != valid.shape:
        raise ValueError(f"field {field.shape} and valid {valid.shape} differ")
    sh, sw = field.shape
    dh, dw = dst_hw
    if dh < 1 or dw < 1:
        raise ValueError(f"bad destination size {dst_hw}")
    rows = np.clip(((np.arange(dh) + 0.5) * sh / dh).astype(int), 0, sh - 1)
    cols = np.clip(((np.arange(dw) + 0.5) * sw / dw).astype(int), 0, sw - 1)
    out = field[np.ix_(rows, cols)]
    out_valid = valid[np.ix_(rows, cols)] & np.isfinite(out)
    return np.where(out_valid, out, np.nan), out_valid


def sample_at_observations(field: np.ndarray, valid: np.ndarray,
                           uv: np.ndarray,
                           field_hw_of_uv: tuple[int, int] | None = None
                           ) -> tuple[np.ndarray, np.ndarray]:
    """Sample a dense range field at (N,2) image observations `uv = (u, v)`.

    This is the *only* sanctioned dense-vs-sparse correspondence in Phase 3A.
    `uv` must be the image observation recorded by the reconstruction that owns
    the sparse point -- the pixel where that 3D point was actually seen -- not
    a re-projection invented here, and never a nearest neighbour in some other
    method's world coordinates. Two independently-scaled, independently-posed
    point clouds have no shared world frame, so a 3D nearest-neighbour match
    between them is not a correspondence at all.

    `field_hw_of_uv` is the image size the observations were measured in, if it
    differs from the field's own grid; the observations are rescaled with the
    same pixel-index convention as `scale_intrinsics`.

    Bilinear interpolation, but only where all four neighbours are valid and
    finite -- including a neighbour whose bilinear weight happens to be zero.
    A sample whose 2x2 neighbourhood touches an invalid pixel comes back
    invalid rather than being quietly filled from the valid side: filling would
    smear the far side of an occlusion boundary into the near side, and an
    observation sitting on a depth discontinuity is exactly the one whose range
    we should decline to assert. The cost is losing a thin band of samples at
    every hole edge, which is the cheap direction to be wrong in.

    Returns (values, ok) where `values` is NaN wherever `ok` is False.
    """
    field = np.asarray(field, dtype=np.float64)
    valid = np.asarray(valid, dtype=bool)
    uv = np.asarray(uv, dtype=np.float64)
    if field.shape != valid.shape:
        raise ValueError(f"field {field.shape} and valid {valid.shape} differ")
    if uv.ndim != 2 or uv.shape[1] != 2:
        raise ValueError(f"expected (N,2) observations, got {uv.shape}")
    h, w = field.shape
    u = uv[:, 0].copy()
    v = uv[:, 1].copy()
    if field_hw_of_uv is not None:
        oh, ow = field_hw_of_uv
        sx, sy = w / float(ow), h / float(oh)
        u = sx * u + (sx - 1.0) / 2.0
        v = sy * v + (sy - 1.0) / 2.0

    n = uv.shape[0]
    out = np.full(n, np.nan, dtype=np.float64)
    ok = np.zeros(n, dtype=bool)

    # Points must lie inside the grid with a full 2x2 neighbourhood available.
    inside = np.isfinite(u) & np.isfinite(v) & (u >= 0) & (v >= 0) & \
        (u <= w - 1) & (v <= h - 1)
    if not inside.any():
        return out, ok
    ui, vi = u[inside], v[inside]
    u0 = np.clip(np.floor(ui).astype(int), 0, w - 2) if w >= 2 else np.zeros(ui.shape, int)
    v0 = np.clip(np.floor(vi).astype(int), 0, h - 2) if h >= 2 else np.zeros(vi.shape, int)
    u1 = np.minimum(u0 + 1, w - 1)
    v1 = np.minimum(v0 + 1, h - 1)
    fu = ui - u0
    fv = vi - v0

    q00, q01 = field[v0, u0], field[v0, u1]
    q10, q11 = field[v1, u0], field[v1, u1]
    m = (valid[v0, u0] & valid[v0, u1] & valid[v1, u0] & valid[v1, u1] &
         np.isfinite(q00) & np.isfinite(q01) & np.isfinite(q10) & np.isfinite(q11))
    vals = ((1 - fv) * ((1 - fu) * q00 + fu * q01) +
            fv * ((1 - fu) * q10 + fu * q11))

    idx = np.flatnonzero(inside)
    out[idx[m]] = vals[m]
    ok[idx[m]] = True
    return out, ok


# --------------------------------------------------------------------------
# Scale
# --------------------------------------------------------------------------

@dataclass
class ScaleFit:
    """Result of a single clip-level global-scale fit."""
    scale: float
    n_used: int
    n_offered: int
    method: str
    #: log-ratio residual spread AFTER the fit; a shape/noise statistic, since
    #: the one scalar has already absorbed everything a scale can absorb.
    log_residual_mad: float


def fit_global_scale(estimate: np.ndarray, reference: np.ndarray,
                     method: str = "median_log_ratio") -> ScaleFit:
    """Fit ONE scalar s minimising a robust residual of `s * estimate` vs `reference`.

    Pool observations from every frame of the clip and call this once per
    (method-pair, clip). Phase 3A's primary comparison forbids a per-frame fit,
    because renormalising each frame would erase temporal scale drift -- which
    is a real failure mode, not a nuisance. Use `per_frame_scale_trace` when you
    want to *see* that drift.

    `median_log_ratio` (default) is the median of log(reference/estimate),
    exponentiated: the scale-space analogue of a median, invariant to which of
    the two arguments is called the estimate, and unaffected by a minority of
    wildly wrong points. Only strictly positive, finite pairs are eligible.
    """
    est = np.asarray(estimate, dtype=np.float64).ravel()
    ref = np.asarray(reference, dtype=np.float64).ravel()
    if est.shape != ref.shape:
        raise ValueError(f"estimate {est.shape} and reference {ref.shape} differ")
    n_offered = est.size
    good = np.isfinite(est) & np.isfinite(ref) & (est > 0) & (ref > 0)
    if good.sum() < 1:
        return ScaleFit(float("nan"), 0, n_offered, method, float("nan"))
    e, r = est[good], ref[good]
    if method == "median_log_ratio":
        lr = np.log(r) - np.log(e)
        s = float(np.exp(np.median(lr)))
        resid = lr - np.median(lr)
    elif method == "median_ratio":
        s = float(np.median(r / e))
        resid = np.log(r) - np.log(s * e)
    else:
        raise ValueError(f"unknown scale-fit method {method!r}")
    mad = float(np.median(np.abs(resid - np.median(resid))))
    return ScaleFit(s, int(good.sum()), n_offered, method, mad)


def per_frame_scale_trace(estimate_by_frame: dict, reference_by_frame: dict,
                          method: str = "median_log_ratio") -> dict:
    """Per-frame scale fits -- A DRIFT DIAGNOSTIC ONLY.

    Never feed these back into a residual. Their whole purpose is to show
    whether one clip-level scale is enough, i.e. whether a method's scale
    wanders over the clip. Returns {frame_index: ScaleFit}.
    """
    out = {}
    for k in sorted(set(estimate_by_frame) & set(reference_by_frame)):
        out[k] = fit_global_scale(estimate_by_frame[k], reference_by_frame[k], method)
    return out


def relative_errors(estimate: np.ndarray, reference: np.ndarray,
                    scale: float) -> np.ndarray:
    """Signed relative error (s*est - ref)/ref, NaN where either side is unusable."""
    est = np.asarray(estimate, dtype=np.float64)
    ref = np.asarray(reference, dtype=np.float64)
    good = np.isfinite(est) & np.isfinite(ref) & (ref > 0) & (est > 0)
    with np.errstate(invalid="ignore", divide="ignore"):
        err = (scale * est - ref) / ref
    return np.where(good, err, np.nan)


def robust_stats(values: np.ndarray) -> dict:
    """Median / MAD / percentile summary over the finite entries of `values`."""
    v = np.asarray(values, dtype=np.float64).ravel()
    v = v[np.isfinite(v)]
    if v.size == 0:
        return {"n": 0, "median": float("nan"), "mad": float("nan"),
                "p05": float("nan"), "p25": float("nan"), "p75": float("nan"),
                "p95": float("nan"), "abs_median": float("nan")}
    med = float(np.median(v))
    return {
        "n": int(v.size),
        "median": med,
        "mad": float(np.median(np.abs(v - med))),
        "p05": float(np.percentile(v, 5)),
        "p25": float(np.percentile(v, 25)),
        "p75": float(np.percentile(v, 75)),
        "p95": float(np.percentile(v, 95)),
        "abs_median": float(np.median(np.abs(v))),
    }


def image_radius(uv: np.ndarray, hw: tuple[int, int]) -> np.ndarray:
    """Normalised distance of each (u,v) from the image centre.

    Exactly 1.0 at the mid-edge pixel centre of the shorter axis; the corners
    exceed 1. Used to bin residuals by radius for the refraction / distortion
    signature test. The normaliser is half the SHORT side so the same number
    means roughly the same off-axis angle regardless of clip orientation (this
    subset mixes landscape and portrait decodes), and it uses (min-1)/2 to stay
    consistent with `pixel_grid`'s pixel-index convention.
    """
    uv = np.asarray(uv, dtype=np.float64)
    h, w = hw
    cu, cv = (w - 1) / 2.0, (h - 1) / 2.0
    norm = (min(h, w) - 1) / 2.0
    return np.sqrt((uv[:, 0] - cu) ** 2 + (uv[:, 1] - cv) ** 2) / norm


def binned_profile(x: np.ndarray, y: np.ndarray, edges: np.ndarray) -> list[dict]:
    """Median/robust profile of `y` within bins of `x` -- residual vs radius/range."""
    x = np.asarray(x, dtype=np.float64).ravel()
    y = np.asarray(y, dtype=np.float64).ravel()
    good = np.isfinite(x) & np.isfinite(y)
    x, y = x[good], y[good]
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (x >= lo) & (x < hi)
        st = robust_stats(y[m])
        st.update({"lo": float(lo), "hi": float(hi)})
        out.append(st)
    return out


# --------------------------------------------------------------------------
# Flat-port refractive geometry: bounding the water-path approximation
# --------------------------------------------------------------------------

def flatport_exit_point_distance_bound(int_dist: float, int_thick: float,
                                       max_half_angle_rad: float) -> float:
    """Upper bound on how far the water-ray's origin sits from the camera centre.

    Behind a flat port a ray leaves the camera centre, crosses the inner glass
    face at distance `int_dist` along the interface normal, traverses
    `int_thick` of glass, and only then enters the water. The point where it
    enters the water — the exit point P2 — is where the physically meaningful
    WATER PATH starts, and it is not the camera centre. So for any scene point
    X in the camera frame:

        | water_path_length - ||X|| |  <=  ||P2||        (triangle inequality)

    and ||P2|| is bounded by the two slab crossings at the steepest ray in the
    field of view:

        ||P2||  <=  int_dist / cos(theta)  +  int_thick / cos(theta_glass)
                <=  (int_dist + int_thick) / cos(theta_max)

    using cos(theta_glass) >= cos(theta_max), which holds because refraction into
    a denser medium bends the ray TOWARD the normal.

    This is why Phase 3A does not implement a full refractive unprojection to
    compare ranges. The refractive camera's DIRECTIONAL effect is already
    carried inside the reconstructed 3D points; the only quantity a central
    treatment gets wrong is this path-length offset, and it is bounded here in
    closed form instead of being assumed negligible. Returns metres if the
    inputs are metres.
    """
    if int_dist < 0 or int_thick < 0:
        raise ValueError("interface distance and thickness must be non-negative")
    if not (0.0 <= max_half_angle_rad < np.pi / 2):
        raise ValueError("max_half_angle_rad must be in [0, pi/2)")
    return float((int_dist + int_thick) / np.cos(max_half_angle_rad))


def max_half_angle_from_K(K: np.ndarray, h: int, w: int) -> float:
    """Largest angle from the optical axis over the image, for a pinhole K."""
    d = ray_directions_from_K(K, h, w, normalize=True)
    return float(np.arccos(np.clip(d[..., 2].min(), -1.0, 1.0)))
