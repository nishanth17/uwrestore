"""Tests for the Week 3 Phase 3A project-owned geometry glue.

These test OUR conversions against synthetic geometry with an analytically
known answer. They deliberately do NOT test COLMAP, MapAnything or any other
third-party system — the point is that when a cross-family number looks odd,
the conversion layer is already known-good and the suspicion falls where it
belongs.
"""

import numpy as np
import pytest

from experiments.week3_geometry.geometry import (
    PATH_SOURCES,
    ScaleFit,
    binned_profile,
    camera_center_from_T_cw,
    fit_global_scale,
    image_radius,
    invert_se3,
    per_frame_scale_trace,
    pixel_grid,
    ray_directions_from_K,
    ray_length_factor,
    ray_range_to_zdepth,
    relative_errors,
    resize_range_field,
    robust_stats,
    sample_at_observations,
    scale_intrinsics,
    transform_points,
    zdepth_to_ray_range,
)


def _rot(ax, ay, az):
    ca, sa = np.cos(ax), np.sin(ax)
    cb, sb = np.cos(ay), np.sin(ay)
    cc, sc = np.cos(az), np.sin(az)
    Rx = np.array([[1, 0, 0], [0, ca, -sa], [0, sa, ca]])
    Ry = np.array([[cb, 0, sb], [0, 1, 0], [-sb, 0, cb]])
    Rz = np.array([[cc, -sc, 0], [sc, cc, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def _T(R, t):
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = t
    return T


def _K(fx=800.0, fy=800.0, cx=639.5, cy=359.5):
    return np.array([[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]])


# ---------------------------------------------------------------- SE(3) ----

def test_invert_se3_is_an_exact_involution():
    T = _T(_rot(0.3, -0.7, 1.1), np.array([1.5, -2.0, 0.25]))
    back = invert_se3(invert_se3(T))
    assert np.allclose(back, T, atol=1e-12)
    assert np.allclose(invert_se3(T) @ T, np.eye(4), atol=1e-12)


def test_invert_se3_rejects_wrong_shape():
    with pytest.raises(ValueError):
        invert_se3(np.eye(3))


def test_pose_convention_world_to_camera_vs_camera_to_world():
    """T_cw maps world->camera; its inverse's translation IS the camera centre."""
    R_cw = _rot(0.1, 0.2, -0.3)
    C = np.array([2.0, -1.0, 5.0])          # camera centre in world
    t_cw = -R_cw @ C
    T_cw = _T(R_cw, t_cw)

    assert np.allclose(camera_center_from_T_cw(T_cw), C, atol=1e-12)
    T_wc = invert_se3(T_cw)
    assert np.allclose(T_wc[:3, 3], C, atol=1e-12)

    # A world point at the camera centre maps to the camera origin.
    assert np.allclose(transform_points(T_cw, C[None, :])[0], np.zeros(3), atol=1e-12)


def test_getting_the_pose_convention_backwards_is_detectable():
    """Using T_wc where T_cw is meant does not silently produce sane numbers."""
    R_cw = _rot(0.4, -0.2, 0.9)
    C = np.array([3.0, 1.0, -2.0])
    T_cw = _T(R_cw, -R_cw @ C)
    X_world = np.array([[1.0, 2.0, 3.0]])
    right = transform_points(T_cw, X_world)
    wrong = transform_points(invert_se3(T_cw), X_world)
    assert not np.allclose(right, wrong, atol=1e-6)


# ------------------------------------------------- z-depth vs ray range ----

def test_ray_range_equals_norm_of_the_backprojected_point():
    """The conversion must agree with explicitly unprojecting each pixel."""
    K = _K()
    h, w = 30, 40
    rng = np.random.default_rng(0)
    z = rng.uniform(0.5, 12.0, size=(h, w))

    r = zdepth_to_ray_range(z, K)

    u, v = pixel_grid(h, w)
    Kinv = np.linalg.inv(K)
    uv1 = np.stack([u, v, np.ones_like(u)], axis=-1)
    X = (uv1 @ Kinv.T) * z[..., None]           # camera-frame points
    expected = np.linalg.norm(X, axis=-1)
    assert np.allclose(r, expected, rtol=0, atol=1e-9)
    assert np.allclose(X[..., 2], z, atol=1e-12)   # the z coordinate is z-depth


def test_zdepth_and_ray_range_agree_only_on_the_optical_axis():
    """At the principal point the factor is exactly 1; off-axis it is > 1."""
    K = _K(cx=19.0, cy=14.0)
    f = ray_length_factor(K, 30, 40)
    assert f[14, 19] == pytest.approx(1.0, abs=1e-12)
    assert f[0, 0] > 1.0
    assert f.min() == pytest.approx(1.0, abs=1e-12)


def test_the_conflation_error_is_large_and_radial_at_gopro_field_of_view():
    """Calling z-depth 'range' is a radially structured, tens-of-percent error.

    This is the failure this module exists to prevent: a radial error of this
    size, injected by a units mistake, would look exactly like the refraction
    signature Phase 3A is testing for.
    """
    h, w = 720, 1280
    K = _K(fx=640.0, fy=640.0, cx=(w - 1) / 2, cy=(h - 1) / 2)   # ~90 deg horizontal
    f = ray_length_factor(K, h, w)
    assert f[h // 2, w // 2] == pytest.approx(1.0, abs=1e-3)
    assert f[0, 0] > 1.25          # corner error > 25 %
    # and it is monotone in image radius, i.e. structured, not noise
    uv = np.array([[w / 2, h / 2], [w * 0.75, h / 2], [w - 1, h / 2]])
    rad = image_radius(uv, (h, w))
    fac = [f[int(v), int(u)] for u, v in uv]
    assert rad[0] < rad[1] < rad[2]
    assert fac[0] < fac[1] < fac[2]


def test_zdepth_ray_range_round_trip():
    K = _K()
    rng = np.random.default_rng(1)
    z = rng.uniform(0.3, 20.0, size=(17, 23))
    assert np.allclose(ray_range_to_zdepth(zdepth_to_ray_range(z, K), K), z, atol=1e-9)


def test_range_conversions_propagate_non_finite_and_reject_behind_camera():
    K = _K()
    z = np.array([[1.0, np.nan], [np.inf, -2.0]])
    r = zdepth_to_ray_range(z, K)
    assert np.isfinite(r[0, 0])
    assert np.isnan(r[0, 1]) and np.isnan(r[1, 0]) and np.isnan(r[1, 1])


def test_ray_directions_are_unit_and_forward():
    K = _K()
    d = ray_directions_from_K(K, 12, 16)
    assert np.allclose(np.linalg.norm(d, axis=-1), 1.0, atol=1e-12)
    assert (d[..., 2] > 0).all()          # +z is forward into the scene
    un = ray_directions_from_K(K, 12, 16, normalize=False)
    assert np.allclose(un[..., 2], 1.0, atol=1e-12)


def test_ray_direction_x_increases_to_the_right_and_y_downward():
    """Pins the OpenCV axis convention, not just the magnitudes."""
    K = _K(cx=7.5, cy=5.5)
    d = ray_directions_from_K(K, 12, 16, normalize=False)
    assert d[5, 2, 0] < d[5, 13, 0]       # larger u -> larger x
    assert d[1, 8, 1] < d[10, 8, 1]       # larger v -> larger y (down)


# ------------------------------------------------------- intrinsics rescale ----

def test_scale_intrinsics_agrees_with_resampling_the_ray_field():
    """A K rescaled to a new grid must describe the same physical rays."""
    K = _K(fx=800, fy=800, cx=639.5, cy=359.5)
    src = (720, 1280)
    dst = (360, 640)
    K2 = scale_intrinsics(K, src, dst)
    # centre pixel of each grid must map to the same direction
    d1 = ray_directions_from_K(K, *src)[src[0] // 2, src[1] // 2]
    d2 = ray_directions_from_K(K2, *dst)[dst[0] // 2, dst[1] // 2]
    assert np.allclose(d1, d2, atol=2e-3)
    # a corner too, where an error in the principal-point rule would show
    c1 = ray_directions_from_K(K, *src)[0, 0]
    c2 = ray_directions_from_K(K2, *dst)[0, 0]
    assert np.allclose(c1, c2, atol=2e-3)


def test_scale_intrinsics_identity():
    K = _K()
    assert np.allclose(scale_intrinsics(K, (720, 1280), (720, 1280)), K, atol=1e-12)


# -------------------------------------------------------------- validity ----

def test_resize_keeps_only_values_that_existed_and_propagates_invalidity():
    field = np.array([[1.0, 1.0, 100.0, 100.0],
                      [1.0, 1.0, 100.0, 100.0]])
    valid = np.ones_like(field, dtype=bool)
    out, ok = resize_range_field(field, valid, (1, 2))
    assert ok.all()
    # nearest neighbour: no averaged 50.5 anywhere
    assert set(np.unique(out)) <= {1.0, 100.0}


def test_resize_propagates_invalid_and_nan():
    field = np.array([[1.0, np.nan], [2.0, 3.0]])
    valid = np.array([[True, False], [False, True]])
    out, ok = resize_range_field(field, valid, (2, 2))
    assert ok[0, 0] and ok[1, 1]
    assert not ok[0, 1] and not ok[1, 0]
    assert np.isnan(out[0, 1]) and np.isnan(out[1, 0])


def test_resize_rejects_mismatched_mask():
    with pytest.raises(ValueError):
        resize_range_field(np.zeros((2, 2)), np.ones((3, 3), bool), (1, 1))


# ------------------------------------------------- sampling at observations ----

def test_sampling_reproduces_an_exact_linear_field():
    h, w = 20, 30
    u, v = pixel_grid(h, w)
    field = 2.0 + 0.5 * u - 0.25 * v          # exactly bilinear
    valid = np.ones_like(field, dtype=bool)
    uv = np.array([[0.0, 0.0], [7.3, 11.8], [w - 1.0, h - 1.0]])
    vals, ok = sample_at_observations(field, valid, uv)
    assert ok.all()
    expect = 2.0 + 0.5 * uv[:, 0] - 0.25 * uv[:, 1]
    assert np.allclose(vals, expect, atol=1e-9)


def test_sampling_marks_out_of_bounds_invalid_rather_than_clamping():
    field = np.ones((10, 10))
    valid = np.ones_like(field, dtype=bool)
    uv = np.array([[-0.5, 5.0], [5.0, 9.5], [3.0, 3.0], [np.nan, 1.0]])
    vals, ok = sample_at_observations(field, valid, uv)
    assert list(ok) == [False, False, True, False]
    assert np.isnan(vals[0]) and np.isnan(vals[1]) and np.isnan(vals[3])


def test_sampling_refuses_to_fill_across_an_invalid_neighbour():
    field = np.ones((4, 4))
    valid = np.ones_like(field, dtype=bool)
    valid[1, 1] = False
    vals, ok = sample_at_observations(field, valid, np.array([[0.5, 0.5], [2.5, 2.5]]))
    assert not ok[0]                 # its 2x2 neighbourhood touches the hole
    assert ok[1] and vals[1] == pytest.approx(1.0)


def test_sampling_is_conservative_even_when_the_bad_neighbour_has_zero_weight():
    """Documented conservatism: proximity to a hole invalidates, not just weight.

    An observation landing exactly on a valid pixel whose 2x2 neighbourhood
    includes an invalid one is still rejected. That costs a thin band of
    samples at every hole edge and is the cheap direction to be wrong in.
    """
    field = np.ones((4, 4))
    valid = np.ones_like(field, dtype=bool)
    valid[1, 1] = False
    _, ok = sample_at_observations(field, valid, np.array([[0.0, 0.0]]))
    assert not ok[0]


def test_sampling_rescales_observations_measured_on_another_grid():
    h, w = 8, 8
    u, _ = pixel_grid(h, w)
    field = u.astype(float)
    valid = np.ones_like(field, dtype=bool)
    # same physical point expressed on a 16x16 observation grid
    vals_native, ok_native = sample_at_observations(field, valid, np.array([[3.0, 3.0]]))
    vals_other, ok_other = sample_at_observations(
        field, valid, np.array([[6.5, 6.5]]), field_hw_of_uv=(16, 16))
    assert ok_native[0] and ok_other[0]
    assert vals_other[0] == pytest.approx(vals_native[0], abs=1e-9)


def test_sampling_rejects_bad_shapes():
    with pytest.raises(ValueError):
        sample_at_observations(np.zeros((4, 4)), np.ones((4, 4), bool), np.zeros((3,)))


# ------------------------------------------------------------ scale fit ----

def test_global_scale_recovers_a_known_scalar():
    rng = np.random.default_rng(2)
    ref = rng.uniform(1.0, 10.0, size=5000)
    est = ref / 3.7
    fit = fit_global_scale(est, ref)
    assert fit.scale == pytest.approx(3.7, rel=1e-12)
    assert fit.n_used == 5000
    assert fit.log_residual_mad == pytest.approx(0.0, abs=1e-12)


def test_global_scale_is_robust_to_a_minority_of_gross_outliers():
    rng = np.random.default_rng(3)
    ref = rng.uniform(1.0, 10.0, size=1000)
    est = ref / 2.0
    est[:200] = rng.uniform(100.0, 1000.0, size=200)     # 20 % garbage
    assert fit_global_scale(est, ref).scale == pytest.approx(2.0, rel=0.05)


def test_global_scale_ignores_non_finite_and_non_positive_pairs():
    est = np.array([1.0, 2.0, np.nan, 4.0, -1.0, 0.0])
    ref = np.array([2.0, 4.0, 8.0, np.inf, 2.0, 2.0])
    fit = fit_global_scale(est, ref)
    assert fit.n_used == 2 and fit.n_offered == 6
    assert fit.scale == pytest.approx(2.0)


def test_global_scale_with_no_usable_pairs_returns_nan_not_an_exception():
    fit = fit_global_scale(np.array([np.nan, -1.0]), np.array([1.0, 2.0]))
    assert isinstance(fit, ScaleFit)
    assert np.isnan(fit.scale) and fit.n_used == 0


def test_one_global_scale_does_not_hide_drift_that_per_frame_fits_reveal():
    """The property that makes the primary comparison honest.

    A method whose scale drifts across the clip must still show a large
    residual under ONE clip-level scale, while the per-frame diagnostic shows
    the drift explicitly.
    """
    rng = np.random.default_rng(4)
    est_by_frame, ref_by_frame = {}, {}
    for i in range(10):
        ref = rng.uniform(2.0, 8.0, size=200)
        drift = 1.0 + 0.06 * i                    # scale wanders 1.0 -> 1.54
        est_by_frame[i] = ref / drift
        ref_by_frame[i] = ref

    pooled_est = np.concatenate([est_by_frame[i] for i in range(10)])
    pooled_ref = np.concatenate([ref_by_frame[i] for i in range(10)])
    one = fit_global_scale(pooled_est, pooled_ref)
    err = relative_errors(pooled_est, pooled_ref, one.scale)
    assert robust_stats(err)["p95"] > 0.10        # drift survives as real error

    trace = per_frame_scale_trace(est_by_frame, ref_by_frame)
    scales = [trace[i].scale for i in range(10)]
    assert scales[0] == pytest.approx(1.0, rel=1e-9)
    assert scales[-1] == pytest.approx(1.54, rel=1e-9)
    assert max(scales) / min(scales) > 1.5        # the diagnostic sees it


def test_relative_errors_are_zero_at_the_fitted_scale_for_a_pure_scale_error():
    ref = np.array([1.0, 2.0, 4.0, 8.0])
    est = ref / 2.5
    fit = fit_global_scale(est, ref)
    assert np.allclose(relative_errors(est, ref, fit.scale), 0.0, atol=1e-12)


def test_relative_errors_keep_shape_error_visible_after_scaling():
    """One scalar must not absorb a range-dependent (shape) error."""
    ref = np.linspace(1.0, 10.0, 500)
    est = ref * (1.0 + 0.2 * ref / ref.max())      # +20 % ramp with distance
    fit = fit_global_scale(est, ref)
    err = relative_errors(est, ref, fit.scale)
    assert robust_stats(np.abs(err))["p95"] > 0.05
    prof = binned_profile(ref, err, np.linspace(1.0, 10.0, 5))
    assert prof[0]["median"] < prof[-1]["median"]  # monotone in range: a shape error


# ------------------------------------------------------------- misc ----

def test_image_radius_is_zero_at_centre_and_one_at_the_short_mid_edge():
    h, w = 720, 1280
    cu, cv = (w - 1) / 2, (h - 1) / 2
    r = image_radius(np.array([[cu, cv], [cu, 0.0], [0.0, 0.0]]), (h, w))
    assert r[0] == pytest.approx(0.0, abs=1e-12)
    assert r[1] == pytest.approx(1.0, rel=1e-3)
    assert r[2] > 1.0


def test_robust_stats_on_empty_input_is_nan_not_an_exception():
    st = robust_stats(np.array([np.nan, np.inf]))
    assert st["n"] == 0 and np.isnan(st["median"])


def test_path_source_labels_are_distinct():
    assert len(set(PATH_SOURCES)) == len(PATH_SOURCES)


# ------------------------------------------------- range product on disk ----

def test_range_writer_demotes_bad_values_into_the_mask(tmp_path):
    """A non-finite or non-positive range must never survive as a number."""
    from experiments.week3_geometry.rangeio import RangeReader, RangeWriter

    w = RangeWriter(str(tmp_path), "TEST", "clip")
    rng = np.array([[1.0, np.nan], [-2.0, 4.0]], dtype=np.float32)
    valid = np.ones((2, 2), dtype=bool)
    w.add_frame(7, rng, valid, K=np.eye(3), T_wc=np.eye(4),
                path_source="ray_range_approx_water_path")
    w.close(provenance={"method": "unit-test"}, conventions={"pose": "T_wc"})

    r, v = RangeReader(str(tmp_path), "TEST", "clip").load(7)
    assert np.asarray(v).tolist() == [[True, False], [False, True]]
    assert np.isnan(r[0, 1]) and np.isnan(r[1, 0])
    assert r[0, 0] == pytest.approx(1.0) and r[1, 1] == pytest.approx(4.0)


def test_range_writer_round_trips_conventions_and_refuses_silent_overwrite(tmp_path):
    from experiments.week3_geometry.rangeio import RangeReader, RangeWriter

    w = RangeWriter(str(tmp_path), "TEST", "clip")
    T = np.eye(4)
    T[:3, 3] = [1.0, 2.0, 3.0]
    w.add_frame(3, np.full((2, 3), 2.5, np.float32), np.ones((2, 3), bool),
                K=np.diag([100.0, 100.0, 1.0]), T_wc=T,
                conf=np.full((2, 3), 0.75, np.float32),
                path_source="ray_range_approx_water_path")
    w.close(provenance={"method": "unit-test"}, conventions={"pose": "T_wc"})

    rd = RangeReader(str(tmp_path), "TEST", "clip")
    assert rd.frame_indices == [3]
    rec = rd.by_index[3]
    assert rec["path_source"] == "ray_range_approx_water_path"
    assert rec["valid_fraction"] == pytest.approx(1.0)
    assert np.allclose(rec["T_wc"], T)
    r, v, c = rd.load(3, want_conf=True)
    assert r.shape == (2, 3) and np.asarray(v).all() and c is not None
    assert float(np.asarray(c).mean()) == pytest.approx(0.75)

    with pytest.raises(SystemExit):
        RangeWriter(str(tmp_path), "TEST", "clip")


# ----------------------------------------- flat-port water-path bounding ----

def test_flatport_exit_point_bound_is_the_slab_crossing_length():
    from experiments.week3_geometry.geometry import flatport_exit_point_distance_bound

    # Straight down the optical axis the bound is just the two slab thicknesses.
    assert flatport_exit_point_distance_bound(0.002, 0.001, 0.0) == pytest.approx(0.003)
    # Off axis it grows as 1/cos.
    b = flatport_exit_point_distance_bound(0.002, 0.001, np.deg2rad(60.0))
    assert b == pytest.approx(0.003 / 0.5, rel=1e-9)


def test_flatport_bound_is_negligible_against_metre_scale_scenes():
    """The quantitative claim Phase 3A actually relies on."""
    from experiments.week3_geometry.geometry import flatport_exit_point_distance_bound

    bound = flatport_exit_point_distance_bound(0.002, 0.001, np.deg2rad(55.0))
    assert bound < 0.006                      # under 6 mm
    assert bound / 0.5 < 0.02                 # < 2 % even at a 0.5 m scene point
    assert bound / 3.0 < 0.002                # < 0.2 % at 3 m


def test_flatport_bound_rejects_impossible_inputs():
    from experiments.week3_geometry.geometry import flatport_exit_point_distance_bound

    with pytest.raises(ValueError):
        flatport_exit_point_distance_bound(-1.0, 0.001, 0.0)
    with pytest.raises(ValueError):
        flatport_exit_point_distance_bound(0.002, 0.001, np.pi / 2)


def test_max_half_angle_from_K_matches_the_corner_ray():
    from experiments.week3_geometry.geometry import max_half_angle_from_K

    h, w = 294, 518
    K = np.array([[260.0, 0.0, (w - 1) / 2], [0.0, 260.0, (h - 1) / 2], [0, 0, 1]])
    ang = max_half_angle_from_K(K, h, w)
    corner = np.array([(w - 1) / 2, (h - 1) / 2]) / 260.0
    assert ang == pytest.approx(np.arctan(np.linalg.norm(corner)), abs=1e-9)
