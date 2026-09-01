"""Synthetic tests for the Week 3 Phase 3B analysis primitives.

Phase 3B introduces three quantities Phase 3A never computed — per-point
triangulation angle, baseline/depth ratio and track temporal span — and one new
comparison path (`compare_sparse`, between two arbitrary sparse reconstructions).
The Phase 3A rule is that anything of this kind is tested against synthetic
geometry with an analytically known answer before any conclusion rests on it,
because a silent convention error here would be indistinguishable from a real
effect.

Each test also carries a falsification element: the wrong answer must be
visibly different, not merely absent.

    .venv/bin/python -m pytest tests/test_week3_phase3b.py -q
"""

from __future__ import annotations

import math
import os
import sys

import numpy as np
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week3_geometry.phase3b.scripts.make_schedules import positions
from experiments.week3_geometry.phase3b.scripts.prep_db import (
    CAMERA_MODELS,
    initial_params,
)
from experiments.week3_geometry.phase3b.scripts.sparse_metrics import (
    compare_sparse,
    sparse_structure_metrics,
)


# --------------------------------------------------------------------------
# Synthetic model construction, in exactly the shape the COLMAP TXT parsers emit
# --------------------------------------------------------------------------

def _qvec_from_R(R: np.ndarray) -> list[float]:
    """(w, x, y, z) from a rotation matrix — COLMAP's storage order."""
    t = np.trace(R)
    if t > 0:
        s = math.sqrt(t + 1.0) * 2
        w = 0.25 * s
        x = (R[2, 1] - R[1, 2]) / s
        y = (R[0, 2] - R[2, 0]) / s
        z = (R[1, 0] - R[0, 1]) / s
    else:
        i = int(np.argmax(np.diag(R)))
        j, k = (i + 1) % 3, (i + 2) % 3
        s = math.sqrt(1.0 + R[i, i] - R[j, j] - R[k, k]) * 2
        q = [0.0, 0.0, 0.0]
        q[i] = 0.25 * s
        q[j] = (R[j, i] + R[i, j]) / s
        q[k] = (R[k, i] + R[i, k]) / s
        w = (R[k, j] - R[j, k]) / s
        x, y, z = q
    return [w, x, y, z]


def make_model(centres, points_world, uv_of, *, hw=(720, 1280), frame_step=10):
    """A COLMAP-shaped model with identity rotations and given camera centres.

    `points_world` is (M,3); `uv_of(i, pid)` gives the pixel of point `pid` in
    image `i`. Every point is observed by every image, which keeps the expected
    triangulation angle analytic.
    """
    h, w = hw
    cams = {1: {"model": "SIMPLE_RADIAL", "width": w, "height": h,
                "params": [1000.0, w / 2, h / 2, 0.0],
                "refrac_model": None, "refrac_params": []}}
    pts = {}
    for pid, X in enumerate(points_world):
        pts[pid] = {"xyz": list(map(float, X)), "error": 0.5,
                    "track_len": len(centres)}
    images = {}
    for i, C in enumerate(centres):
        R = np.eye(3)                       # world->camera rotation = identity
        t = -R @ np.asarray(C, dtype=float)  # so that C = -R^T t
        obs = [(float(uv_of(i, pid)[0]), float(uv_of(i, pid)[1]), pid)
               for pid in pts]
        images[i + 1] = {
            "name": f"f{i * frame_step:06d}.png",
            "camera_id": 1,
            "qvec_wxyz_cw": _qvec_from_R(R),
            "tvec_cw": list(map(float, t)),
            "n_observations_2d": len(obs),
            "observations": obs,
        }
    return {"cameras": cams, "images": images, "points": pts}


# --------------------------------------------------------------------------
# Triangulation angle
# --------------------------------------------------------------------------

def test_triangulation_angle_matches_the_analytic_value():
    """Two cameras at +-b/2 viewing a point at depth d subtend 2*atan(b/2d)."""
    b, d = 2.0, 10.0
    centres = [(-b / 2, 0.0, 0.0), (b / 2, 0.0, 0.0)]
    X = np.array([[0.0, 0.0, d]])
    m = make_model(centres, X, lambda i, pid: (640.0, 360.0))
    s = sparse_structure_metrics(m, n_offered=2)
    expected = math.degrees(2 * math.atan((b / 2) / d))
    assert s["triangulation_angle_deg"]["median"] == pytest.approx(expected, abs=1e-6)
    # Falsification: a much shorter baseline must give a much smaller angle,
    # so the metric is not returning something baseline-independent.
    m2 = make_model([(-0.05, 0, 0), (0.05, 0, 0)], X, lambda i, pid: (640.0, 360.0))
    s2 = sparse_structure_metrics(m2, n_offered=2)
    assert s2["triangulation_angle_deg"]["median"] < 0.2 * s["triangulation_angle_deg"]["median"]


def test_triangulation_angle_uses_the_widest_pair_not_the_adjacent_one():
    """Three cameras: the reported angle must come from the OUTER pair.

    This is the property that makes the number meaningful for video, where many
    adjacent frames sit almost on top of each other. Taking a mean over pairs, or
    the adjacent pair, would understate conditioning; taking the max is COLMAP's
    own definition.
    """
    d = 10.0
    centres = [(-1.0, 0, 0), (-0.99, 0, 0), (1.0, 0, 0)]
    X = np.array([[0.0, 0.0, d]])
    s = sparse_structure_metrics(make_model(centres, X, lambda i, pid: (640.0, 360.0)),
                                 n_offered=3)
    widest = math.degrees(2 * math.atan(1.0 / d))
    assert s["triangulation_angle_deg"]["median"] == pytest.approx(widest, abs=1e-6)


def test_baseline_over_depth_is_the_max_baseline_over_median_range():
    b, d = 3.0, 12.0
    centres = [(-b / 2, 0, 0), (b / 2, 0, 0)]
    X = np.array([[0.0, 0.0, d]])
    s = sparse_structure_metrics(make_model(centres, X, lambda i, pid: (640.0, 360.0)),
                                 n_offered=2)
    rng = math.hypot(b / 2, d)          # each camera's range to the point
    assert s["baseline_over_depth"]["median"] == pytest.approx(b / rng, rel=1e-9)


# --------------------------------------------------------------------------
# Track temporal span
# --------------------------------------------------------------------------

def test_track_temporal_span_and_survival_use_source_frame_indices():
    """Span is measured in SOURCE frame indices carried by the filename."""
    centres = [(i * 0.5, 0.0, 0.0) for i in range(5)]      # f000000 .. f000040
    X = np.array([[0.0, 0.0, 10.0]])
    s = sparse_structure_metrics(make_model(centres, X, lambda i, pid: (640.0, 360.0),
                                            frame_step=10), n_offered=5)
    ts = s["track_temporal_span_source_frames"]
    assert ts["clip_span_source_frames"] == 40
    assert ts["median"] == pytest.approx(40.0)     # the one track spans everything
    assert ts["frac_tracks_spanning_ge_50pct_of_clip"] == pytest.approx(1.0)


# --------------------------------------------------------------------------
# compare_sparse: the one global scale, and the shape axes
# --------------------------------------------------------------------------

def _two_models_with(scale=1.0, range_bias=0.0, n_pts=400, seed=0):
    """Model B is model A's world scaled by `scale`, optionally with a
    range-dependent radial bias applied about each camera."""
    rng = np.random.default_rng(seed)
    centres = [(-1.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.5, 0.0)]
    X = np.stack([rng.uniform(-4, 4, n_pts),
                  rng.uniform(-3, 3, n_pts),
                  rng.uniform(4, 20, n_pts)], axis=1)
    uv = rng.uniform(50, 600, size=(n_pts, 2))

    def uv_of(_i, pid):
        return uv[pid]

    a = make_model(centres, X, uv_of)
    Xb = X * scale
    if range_bias:
        # Push far points further, proportionally to their range from camera 0:
        # a pure range-dependent shape error, which is what §8 says costs
        # restoration quality.
        C0 = np.asarray(centres[0])
        r = np.linalg.norm(X - C0, axis=1, keepdims=True)
        Xb = Xb * (1.0 + range_bias * (r / r.max()))
    centres_b = [tuple(np.asarray(c) * scale) for c in centres]
    b = make_model(centres_b, Xb, uv_of)
    return a, b


def test_compare_sparse_absorbs_a_pure_global_scale():
    """A pure similarity must leave (almost) no residual after ONE scale."""
    a, b = _two_models_with(scale=3.7)
    r = compare_sparse(a, b, "A", "B")
    assert r["n_matched_observations"] > 1000
    assert r["global_scale_a_to_b"] == pytest.approx(3.7, rel=1e-6)
    assert abs(r["abs_relative_error"]["median"]) < 1e-9
    assert abs(r["range_swing"]) < 1e-9
    assert r["per_frame_scale_diagnostic"]["max_over_min"] == pytest.approx(1.0, abs=1e-9)


def test_compare_sparse_exposes_a_range_dependent_shape_error():
    """A range-dependent bias must survive the global scale and show up as
    range swing — the axis Phase 3A §8 says actually costs restoration quality."""
    a, b = _two_models_with(scale=1.0, range_bias=0.3)
    r = compare_sparse(a, b, "A", "B")
    assert r["range_swing"] > 0.10, "a 30 % near-to-far bias must not be absorbed"
    # And the same distortion must NOT masquerade as a radius effect: it was
    # applied as a function of range only.
    assert abs(r["radius_swing"]) < r["range_swing"]


def test_compare_sparse_never_matches_observations_across_different_pixels():
    """Correspondence is by 2D proximity WITHIN an image. Displace every
    observation in B far enough and nothing may match."""
    a, b = _two_models_with(scale=1.0)
    for img in b["images"].values():
        img["observations"] = [(u + 50.0, v + 50.0, pid)
                               for (u, v, pid) in img["observations"]]
    r = compare_sparse(a, b, "A", "B", max_px=1.0)
    assert r.get("error") == "no matched observations"


# --------------------------------------------------------------------------
# 3B-4 schedules and 3B-3 camera-model initialisation
# --------------------------------------------------------------------------

def test_schedules_are_nested_and_preserve_both_endpoints():
    n = 48
    s48 = list(range(n))
    s25 = positions(n, 2)
    s13 = positions(n, 4)
    assert len(s25) == 25 and len(s13) == 13
    assert set(s13) <= set(s25) <= set(s48)
    for s in (s25, s13):
        assert s[0] == 0 and s[-1] == n - 1


def test_camera_model_initial_params_have_the_right_shape():
    """Every Phase 3B camera model starts from the SAME focal and principal
    point, with distortion zero — COLMAP's own initialisation. If an arm started
    from a different guess, a difference between arms would not be the model."""
    f0, cx, cy = 1536.0, 640.0, 360.0
    for name, (_mid, nf, npp, nex) in CAMERA_MODELS.items():
        p = initial_params(name, f0, cx, cy)
        assert len(p) == nf + npp + nex, name
        assert all(v == f0 for v in p[:nf]), name
        assert p[nf:nf + 2] == [cx, cy], name
        assert all(v == 0.0 for v in p[nf + 2:]), name
    # The two models Phase 3B compares as a projection-family test must have the
    # SAME parameter count, so the comparison is not confounded by capacity.
    assert len(initial_params("SIMPLE_RADIAL", f0, cx, cy)) == \
           len(initial_params("SIMPLE_RADIAL_FISHEYE", f0, cx, cy))


# --------------------------------------------------------------------------
# Trajectory comparison (3B-2): ONE similarity, residual relative to extent
# --------------------------------------------------------------------------

def test_compare_trajectories_absorbs_a_pure_similarity():
    """Two reconstructions of the same trajectory in different gauges must
    agree to numerical precision after ONE rotation, translation and scale."""
    from experiments.week3_geometry.phase3b.scripts.sparse_metrics import compare_trajectories
    rng = np.random.default_rng(3)
    centres = [(math.cos(a), math.sin(a), 0.3 * a) for a in np.linspace(0, 2.0, 12)]
    X = np.array([[0.0, 0.0, 10.0]])
    a = make_model(centres, X, lambda i, pid: (640.0, 360.0))

    # A different gauge: scale 4.2, a real rotation, a translation.
    th = 0.7
    R = np.array([[math.cos(th), -math.sin(th), 0],
                  [math.sin(th), math.cos(th), 0],
                  [0, 0, 1.0]])
    s, t = 4.2, np.array([3.0, -1.0, 2.0])
    centres_b = [tuple(s * (R @ np.asarray(c)) + t) for c in centres]
    b = make_model(centres_b, X, lambda i, pid: (640.0, 360.0))

    r = compare_trajectories(a, b, "A", "B")
    assert r["n_common_frames"] == 12
    assert r["similarity_scale_a_to_b"] == pytest.approx(s, rel=1e-9)
    assert r["residual_over_extent"]["max"] < 1e-9

    # Falsification: bend the trajectory and the residual must become visible.
    bent = [tuple(np.asarray(c) + np.array([0.0, 0.0, 0.4 * i ** 2 / 100])) for i, c in enumerate(centres_b)]
    b2 = make_model(bent, X, lambda i, pid: (640.0, 360.0))
    r2 = compare_trajectories(a, b2, "A", "B2")
    assert r2["residual_over_extent"]["rmse"] > 1e-3


def test_compare_trajectories_only_uses_shared_frames_and_reports_the_count():
    """A method that registers a different subset is compared on the
    intersection, and the intersection size is reported so a flattering
    three-frame agreement cannot pass unnoticed."""
    from experiments.week3_geometry.phase3b.scripts.sparse_metrics import compare_trajectories
    centres = [(0.4 * i, 0.0, 0.0) for i in range(10)]
    X = np.array([[0.0, 0.0, 10.0]])
    a = make_model(centres, X, lambda i, pid: (640.0, 360.0))
    b = make_model(centres, X, lambda i, pid: (640.0, 360.0))
    # b registers only frames 0, 10, 20, 30 (positions 0..3)
    keep = {1, 2, 3, 4}
    b["images"] = {k: v for k, v in b["images"].items() if k in keep}
    r = compare_trajectories(a, b, "A", "B")
    assert r["n_common_frames"] == 4
    assert r["n_frames_a"] == 10 and r["n_frames_b"] == 4


def test_compare_trajectories_refuses_a_two_frame_comparison():
    from experiments.week3_geometry.phase3b.scripts.sparse_metrics import compare_trajectories
    centres = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
    X = np.array([[0.0, 0.0, 10.0]])
    m = make_model(centres, X, lambda i, pid: (640.0, 360.0))
    r = compare_trajectories(m, m, "A", "A")
    assert "error" in r
