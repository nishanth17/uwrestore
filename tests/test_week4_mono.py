"""Conventions the Week-4A monocular bakeoff depends on, tested in the main venv.

`experiments/week4_mono/` is exploratory scaffolding and most of it needs a model
stack. But a handful of things in it are CONVENTIONS — the source-to-grid map,
the z-depth/range conversion, which alignment family is legal for which
representation, the ordinal and radial metrics — and a convention that is wrong
is wrong silently. Those parts are deliberately pure numpy so they can be tested
here, in the interpreter the project actually maintains, exactly the way Week 3
put `geometry.py` under test while leaving the model runners untested.

Nothing here imports torch, opencv beyond what `uw` already needs, or any model.
"""

from __future__ import annotations

import numpy as np
import pytest

from experiments.week3_geometry.phase3a import geometry as g3
from experiments.week4_mono.round1 import alignment, common, evalgrid, metrics_geom as M, monoio
from experiments.week4_mono.round1.backends import base as bb


# ---------------------------------------------------------------------------
# the evaluation grid and the maps that reach it
# ---------------------------------------------------------------------------

def test_eval_grid_samples_block_centres():
    """Sample k must sit at the centre of its source block, matching scale_intrinsics."""
    uv, hw = evalgrid.eval_grid((720, 1280), downsample=4)
    assert hw == (180, 320)
    assert uv.shape == (180 * 320, 2)
    # first sample: centre of the 4x4 block at the origin
    assert uv[0, 0] == pytest.approx(1.5)
    assert uv[0, 1] == pytest.approx(1.5)
    # spacing is the downsample factor
    assert uv[1, 0] - uv[0, 0] == pytest.approx(4.0)


def test_eval_grid_downsample_one_is_the_source_grid():
    uv, hw = evalgrid.eval_grid((8, 10), downsample=1)
    assert hw == (8, 10)
    assert uv[0].tolist() == [0.0, 0.0]
    assert uv[-1].tolist() == [9.0, 7.0]


def test_gridmap_identity_is_identity():
    gm = evalgrid.GridMap.identity((720, 1280))
    uv = np.array([[0.0, 0.0], [10.5, 3.25]])
    assert np.allclose(gm.apply(uv), uv)


def test_K_source_to_eval_round_trips_a_projection():
    """A point projected with K on the model grid must land at the same place
    when projected with the carried K on the evaluation grid."""
    K = np.array([[300.0, 0.0, 257.0], [0.0, 302.0, 147.0], [0.0, 0.0, 1.0]])
    gm = evalgrid.GridMap(0.4, -2.2, 0.41, -0.65, (294, 518), (720, 1280))
    d = 4
    K_eval = evalgrid.K_source_to_eval(K, gm, downsample=d)
    p = np.array([0.7, -0.3, 5.0])
    u_grid = K[0, 0] * p[0] / p[2] + K[0, 2]
    v_grid = K[1, 1] * p[1] / p[2] + K[1, 2]
    # the same point through the evaluation-grid intrinsics
    j = K_eval[0, 0] * p[0] / p[2] + K_eval[0, 2]
    i = K_eval[1, 1] * p[1] / p[2] + K_eval[1, 2]
    # and back: eval index -> source pixel -> model grid
    u_src = d * j + (d - 1) / 2.0
    v_src = d * i + (d - 1) / 2.0
    assert gm.apply(np.array([[u_src, v_src]]))[0] == pytest.approx([u_grid, v_grid])


# ---------------------------------------------------------------------------
# z-depth vs range — the conversion the freeze says must not be skipped
# ---------------------------------------------------------------------------

def test_ray_range_matches_week3_geometry_exactly():
    """The backend helper and the Week-3 conversion must agree bit for bit.

    They are separate implementations only because the model venvs deliberately
    do not import the Week-3 package. If they ever diverge, every radial
    diagnostic silently acquires a bias.
    """
    K = np.array([[300.0, 0.0, 257.0], [0.0, 302.0, 147.0], [0.0, 0.0, 1.0]])
    rng = np.random.default_rng(0)
    z = rng.uniform(1.0, 12.0, size=(29, 51))
    a = bb.ray_range_from_zdepth(z, K)
    b = g3.zdepth_to_ray_range(z, K)
    assert np.allclose(a, b, rtol=0, atol=1e-5)


def test_range_exceeds_zdepth_everywhere_and_most_at_the_corner():
    K = np.array([[300.0, 0.0, 257.0], [0.0, 302.0, 147.0], [0.0, 0.0, 1.0]])
    z = np.ones((295, 519))
    r = bb.ray_range_from_zdepth(z, K)
    assert (r >= 1.0 - 1e-6).all()
    assert r[0, 0] > r[147, 257]          # corner secant exceeds the principal point
    assert r[147, 257] == pytest.approx(1.0, abs=1e-3)


def test_norm_pointmap_is_the_norm_not_the_z_component():
    pts = np.array([[[3.0, 4.0, 12.0]]])
    assert bb.norm_pointmap(pts)[0, 0] == pytest.approx(13.0)


def test_pixel_K_from_normalized_puts_the_centre_at_half_pixel_convention():
    K_norm = np.array([[0.5, 0.0, 0.5], [0.0, 0.9, 0.5], [0.0, 0.0, 1.0]])
    K = bb.pixel_K_from_normalized(K_norm, 720, 1280)
    assert K[0, 0] == pytest.approx(0.5 * 1280)
    assert K[1, 1] == pytest.approx(0.9 * 720)
    # the image centre under the integer-index convention is (w-1)/2, (h-1)/2
    assert K[0, 2] == pytest.approx((1280 - 1) / 2.0)
    assert K[1, 2] == pytest.approx((720 - 1) / 2.0)


# ---------------------------------------------------------------------------
# alignment families
# ---------------------------------------------------------------------------

def test_scale_family_recovers_a_pure_scale():
    rng = np.random.default_rng(1)
    ref = rng.uniform(1.0, 10.0, 5000)
    pred = ref / 2.5
    fit = alignment.fit_scale(pred, ref)
    assert fit.params["s"] == pytest.approx(2.5, rel=1e-9)
    assert np.allclose(alignment.apply(fit, pred), ref)


def test_affine_depth_recovers_scale_and_shift():
    rng = np.random.default_rng(2)
    pred = rng.uniform(0.5, 5.0, 8000)
    ref = 1.7 * pred + 0.9
    fit = alignment.fit_affine(pred, ref, "affine_depth")
    assert fit.params["s"] == pytest.approx(1.7, rel=1e-6)
    assert fit.params["t"] == pytest.approx(0.9, abs=1e-5)


def test_affine_disparity_is_fitted_in_disparity_then_inverted():
    """The whole point of the disparity family: a*q+b in disparity is NOT a*d+b
    in depth, and fitting in the wrong space must not accidentally work."""
    rng = np.random.default_rng(3)
    depth = rng.uniform(1.0, 12.0, 8000)
    q_true = 1.0 / depth
    q_pred = (q_true - 0.03) / 2.0            # an affine disparity the model emits
    fit = alignment.fit_affine(q_pred, q_true, "affine_disparity")
    back = alignment.to_range(alignment.apply(fit, q_pred), "affine_disparity")
    assert np.nanmedian(np.abs(back - depth) / depth) < 1e-6
    # the same data fitted in DEPTH space does not recover it
    wrong = alignment.fit_affine(q_pred, depth, "affine_depth")
    wrong_back = alignment.to_range(alignment.apply(wrong, q_pred), "affine_depth")
    assert np.nanmedian(np.abs(wrong_back - depth) / depth) > 0.1


def test_affine_log1p_depth_recovers_pxdepths_native_gauge():
    """PXDepth emits normalised log1p-depth. Its documented ambiguity is affine
    in THAT space (inference.py:174/189/195), so the reference must be converted
    with to_log1p and the result inverted with expm1 -- not squeezed through the
    depth or disparity family, which would charge the model for the wrong gauge."""
    rng = np.random.default_rng(11)
    depth = rng.uniform(0.4, 30.0, 8000)
    native = (np.log1p(depth) - 0.35) / 1.9        # a=1.9, b=0.35 exactly
    fit = alignment.fit_affine(native, alignment.to_log1p(depth), "affine_log1p_depth")
    assert fit.params["s"] == pytest.approx(1.9, rel=1e-6)
    assert fit.params["t"] == pytest.approx(0.35, abs=1e-5)
    back = alignment.to_range(alignment.apply(fit, native), "affine_log1p_depth")
    assert np.nanmedian(np.abs(back - depth) / depth) < 1e-9
    # the same prediction fitted in plain depth space does not recover it
    wrong = alignment.fit_affine(native, depth, "affine_depth")
    wrong_back = alignment.to_range(alignment.apply(wrong, native), "affine_depth")
    assert np.nanmedian(np.abs(wrong_back - depth) / depth) > 0.1


def test_to_range_declines_nonpositive_log1p_depth():
    """A negative aligned log1p is an absent prediction, not a near point."""
    out = alignment.to_range(np.array([np.log1p(3.0), 0.0, -0.5]), "affine_log1p_depth")
    assert out[0] == pytest.approx(3.0)
    assert np.isnan(out[1]) and np.isnan(out[2])


def test_to_range_declines_nonpositive_disparity():
    out = alignment.to_range(np.array([1.0, 0.0, -0.5, 0.25]), "affine_disparity")
    assert out[0] == pytest.approx(1.0)
    assert np.isnan(out[1]) and np.isnan(out[2])
    assert out[3] == pytest.approx(4.0)


def test_affine_fit_is_robust_to_a_minority_of_outliers():
    rng = np.random.default_rng(4)
    pred = rng.uniform(1.0, 8.0, 6000)
    ref = 2.0 * pred + 0.5
    ref[:400] = 500.0                          # a wild far-field tail
    fit = alignment.fit_affine(pred, ref, "affine_depth")
    assert fit.params["s"] == pytest.approx(2.0, rel=0.05)


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------

def test_m2_slope_detects_far_field_compression_and_expansion():
    rng = np.random.default_rng(5)
    ref = rng.uniform(1.0, 20.0, 20000)
    assert M.m2_loglog(ref, ref)["b"] == pytest.approx(1.0, abs=1e-6)
    assert M.m2_loglog(ref ** 0.7, ref)["b"] == pytest.approx(0.7, abs=1e-6)
    assert M.m2_loglog(ref ** 1.3, ref)["b"] == pytest.approx(1.3, abs=1e-6)


def test_m5_ordinal_is_invariant_to_any_monotone_transform():
    """No scale, shift or consistent inversion can change an ordering, which is
    what makes M-5 the ambiguity-resistant check."""
    rng = np.random.default_rng(6)
    ref = rng.uniform(1.0, 10.0, (60, 80))
    valid = np.ones_like(ref, dtype=bool)
    for pred in (ref, 3.0 * ref, 3.0 * ref + 1.0, ref ** 1.5):
        r = M.m5_ordinal(pred, ref, valid, seed=0)
        assert r["margins"]["0.25"]["violation_rate"] == pytest.approx(0.0)


def test_m5_ordinal_catches_a_genuine_inversion():
    rng = np.random.default_rng(7)
    ref = rng.uniform(1.0, 10.0, (60, 80))
    valid = np.ones_like(ref, dtype=bool)
    r = M.m5_ordinal(1.0 / ref, ref, valid, seed=0)   # order fully reversed
    assert r["margins"]["0.25"]["violation_rate"] == pytest.approx(1.0)


def test_m5_ignores_pairs_the_reference_cannot_order():
    """A pair inside the margin is not counted, because the reference itself
    cannot be trusted to order it."""
    ref = np.full((40, 40), 5.0)
    ref[:, 20:] = 5.01                                 # a 0.2 % step
    valid = np.ones_like(ref, dtype=bool)
    r = M.m5_ordinal(ref[::-1], ref, valid, seed=0)
    assert r["margins"]["0.25"]["n"] == 0
    assert np.isnan(r["margins"]["0.25"]["violation_rate"])


def test_geometric_edges_are_invariant_to_a_global_scale():
    rng = np.random.default_rng(8)
    r = rng.uniform(2.0, 6.0, (40, 60))
    r[:, 30:] *= 3.0                                   # a real depth step
    valid = np.ones_like(r, dtype=bool)
    mags, ok = M.log_range_gradient(r, valid)
    thr = M.calibrate_edge_threshold([mags[ok]])
    a = M.geometric_edges(r, valid, thr)
    b = M.geometric_edges(7.3 * r, valid, thr)
    assert np.array_equal(a, b)
    assert a.any()


def test_calibrate_edge_threshold_uses_the_pooled_distribution():
    mags = [np.linspace(0.0, 1.0, 1001)]
    thr = M.calibrate_edge_threshold(mags, percentile=98.0)
    assert thr == pytest.approx(0.98, abs=1e-3)


def test_m6_reports_a_growing_radial_error_as_outer_over_inner_above_one():
    hw = (60, 80)
    rad = evalgrid.radius_map(hw)
    ref = np.full(hw, 5.0)
    pred = ref * (1.0 + 0.3 * rad)                     # error grows toward the edge
    out = M.m6_radial(pred, ref, rad)
    assert out["outer_over_inner"] > 1.5


def test_m3_absolute_normal_is_invariant_to_global_scale():
    rng = np.random.default_rng(9)
    xyz = rng.normal(size=(30, 40, 3)) + np.array([0.0, 0.0, 5.0])
    valid = np.ones(xyz.shape[:2], dtype=bool)
    a = M.m3_absolute_normal(xyz, valid, 4.2 * xyz, valid)
    # Not exactly zero: arccos near 1 is ill-conditioned in float, so the
    # residual is ~1e-7 degrees. The point is that it is orders of magnitude
    # below anything this bakeoff reads, not that it is bitwise zero.
    assert a["mae_deg"] == pytest.approx(0.0, abs=1e-5)


def test_triangle_normals_of_a_plane_are_constant():
    yy, xx = np.mgrid[0:20, 0:25].astype(float)
    xyz = np.stack([xx, yy, 3.0 + 0.1 * xx + 0.2 * yy], axis=-1)
    n, ok = M.triangle_normals(xyz, np.ones((20, 25), dtype=bool))
    assert ok.all()
    assert np.allclose(n, n[0, 0], atol=1e-9)


# ---------------------------------------------------------------------------
# the on-disk product
# ---------------------------------------------------------------------------

def test_monoio_refuses_an_unknown_native_kind(tmp_path):
    w = monoio.MonoWriter(str(tmp_path), "m", "c")
    w.add_frame(0, native=np.ones((4, 5)), valid=np.ones((4, 5), bool))
    with pytest.raises(ValueError, match="unknown native_kind"):
        w.close(native_kind="depth", range_rule="norm_pointmap", semantics={},
                provenance={}, preprocessing={})


def test_monoio_demotes_nonpositive_range_into_the_mask(tmp_path):
    """A zero range must never come back as a number: a consumer would read it
    as the camera touching the scene."""
    w = monoio.MonoWriter(str(tmp_path), "m", "c")
    rng = np.array([[1.0, 0.0], [np.inf, 3.0]])
    w.add_frame(0, native=rng, valid=np.ones((2, 2), bool), canonical_range=rng)
    w.close(native_kind="depth_along_ray_metric", range_rule="identity_depth_along_ray",
            semantics={}, provenance={}, preprocessing={})
    r = monoio.MonoReader(str(tmp_path), "m", "c")
    got = np.asarray(r.load_range(0))
    valid = np.asarray(r.load_valid(0))
    assert valid.tolist() == [[True, False], [False, True]]
    assert np.isnan(got[0, 1]) and np.isnan(got[1, 0])


def test_every_declared_native_kind_is_in_the_closed_set():
    """The freeze's declared representation for each model must be writable.

    `MonoWriter.close` validates `native_kind` against a closed set, and it
    validates at CLOSE — after 48 frames of inference have already been paid
    for. A model whose declared kind is missing from the set therefore fails
    only at the end of its clip, which is exactly what happened to `wat3r_n1`
    on the first full sweep. Catching it here costs nothing.
    """
    for model, kind in common.DECLARED_NATIVE.items():
        assert kind in monoio.NATIVE_KINDS, f"{model} declares unknown native_kind {kind!r}"


def test_monoio_refuses_to_clobber(tmp_path):
    w = monoio.MonoWriter(str(tmp_path), "m", "c")
    w.add_frame(0, native=np.ones((2, 2)), valid=np.ones((2, 2), bool))
    w.close(native_kind="depth_relative", range_rule="unresolved", semantics={},
            provenance={}, preprocessing={})
    with pytest.raises(SystemExit, match="refusing to overwrite"):
        monoio.MonoWriter(str(tmp_path), "m", "c")
    monoio.MonoWriter(str(tmp_path), "m", "c", overwrite=True)      # allowed


def test_monoio_round_trips_native_and_aux(tmp_path):
    w = monoio.MonoWriter(str(tmp_path), "m", "c")
    native = np.arange(24, dtype=np.float32).reshape(2, 4, 3)
    aux = {"scalefield": np.ones((2, 4), dtype=np.float32) * 0.84}
    w.add_frame(7, native=native, valid=np.ones((2, 4), bool),
                canonical_range=np.linalg.norm(native, axis=-1), aux=aux)
    w.close(native_kind="pointmap_metric", range_rule="norm_pointmap", semantics={},
            provenance={}, preprocessing={})
    r = monoio.MonoReader(str(tmp_path), "m", "c")
    assert r.frame_indices == [7]
    assert np.array_equal(np.asarray(r.load_native(7)), native)
    assert np.allclose(np.asarray(r.load_aux(7, "scalefield")), 0.84)
    assert r.native_kind == "pointmap_metric"


# ---------------------------------------------------------------------------
# the S4 perturbations really are geometry-preserving
# ---------------------------------------------------------------------------

def test_every_perturbation_preserves_shape_and_dtype():
    from experiments.week4_mono.round1 import perturb
    rng = np.random.default_rng(10)
    img = rng.integers(0, 256, (24, 32, 3), dtype=np.uint8)
    ref = rng.uniform(1.0, 9.0, (24, 32))
    for name, kind, params, _ in perturb.SPEC:
        out = perturb.apply_perturbation(img, kind, params, ref_range=ref)
        assert out.shape == img.shape, name
        assert out.dtype == np.uint8, name


def test_a_unit_channel_gain_is_a_no_op_through_the_linear_round_trip():
    """If this drifts, every S4 response carries an unmeasured baseline offset."""
    from experiments.week4_mono.round1 import perturb
    rng = np.random.default_rng(11)
    img = rng.integers(0, 256, (16, 20, 3), dtype=np.uint8)
    out = perturb.apply_perturbation(img, "channel_gain", {"gain": [1.0, 1.0, 1.0]})
    assert np.abs(out.astype(int) - img.astype(int)).max() <= 1


def test_no_two_perturbation_arms_are_the_same_stimulus():
    """Distinct arm names must be distinct stimuli.

    `cue_conflict_inverted_veil` and `veil_depth_consistent` each expressed
    their direction TWICE -- swapped `t_near`/`t_far` AND an `invert` flag --
    so the double negation cancelled and the cue-conflict arm was a bit-exact
    copy of its own control. Four models times six clips of inference measured
    the control a second time and reported it as the cue conflict. The bug is
    invisible per-arm and obvious pairwise, so test it pairwise.
    """
    from experiments.week4_mono.round1 import perturb
    rng = np.random.default_rng(12)
    img = rng.integers(0, 256, (24, 32, 3), dtype=np.uint8)
    # a reference range with real near/far structure, so depth-shaped arms
    # cannot coincide merely because the stimulus is flat
    ref = np.linspace(1.0, 9.0, 24)[:, None] * np.ones((1, 32))
    outs = {name: perturb.apply_perturbation(img, kind, params, ref_range=ref)
            for name, kind, params, _ in perturb.SPEC}
    names = list(outs)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert not np.array_equal(outs[a], outs[b]), f"{a} and {b} are the same stimulus"


def test_the_depth_veils_run_in_opposite_directions():
    """The cue conflict must veil the NEAR field; its control must veil the FAR field.

    This is the claim S4's cue-conflict arm actually rests on, so it is asserted
    on the stimulus rather than inferred from the parameter names.
    """
    from experiments.week4_mono.round1 import perturb
    img = np.full((24, 32, 3), 200, dtype=np.uint8)
    ref = np.linspace(1.0, 9.0, 24)[:, None] * np.ones((1, 32))  # row 0 near, row -1 far
    spec = {name: params for name, kind, params, _ in perturb.SPEC if kind == "veil_depth"}
    conflict = perturb.apply_perturbation(img, "veil_depth", spec["cue_conflict_inverted_veil"],
                                          ref_range=ref)
    control = perturb.apply_perturbation(img, "veil_depth", spec["veil_depth_consistent"],
                                         ref_range=ref)
    # the veil pulls a bright frame TOWARDS the dark blue-green veiling light,
    # so "more veiled" means "darker in red"
    red = lambda x: float(x[..., 0].mean())
    assert red(control[0]) > red(control[-1]), "control must veil the far field, not the near"
    assert red(conflict[0]) < red(conflict[-1]), "cue conflict must veil the near field"


def test_compare_restorations_always_reports_the_same_keys():
    """A row that could not be measured must still say so in the same shape.

    The S6 aggregator reads these keys off every row it keeps. When the
    function used to omit them -- too few common pixels, or a reference
    restoration with no usable denominator -- the aggregator raised KeyError
    on the third water regime of the first clip.
    """
    from experiments.week4_mono.round1 import restoration

    rng = np.random.default_rng(3)
    h, w = 16, 16
    a = rng.random((h, w, 3)) * 0.4 + 0.05
    b = a * 1.1
    full = np.ones((h, w), dtype=bool)

    good = restoration.compare_restorations(a, b, full)
    thin = restoration.compare_restorations(a, b, np.zeros((h, w), dtype=bool))
    # Reference restored to black everywhere: relative radiance has no
    # denominator, but colour is still defined.
    degenerate = restoration.compare_restorations(np.zeros_like(a), b, full)

    for row in (thin, degenerate):
        assert set(row) >= set(good) - {"_note"}, "a row dropped keys the aggregator reads"
    assert good["status"] == "ok"
    assert thin["status"] == "insufficient_common_support"
    assert thin["n"] == 0
    assert degenerate["status"] == "reference_radiance_degenerate"
    assert degenerate["n_radiance"] == 0
    assert not np.isfinite(degenerate["radiance_abs_rel_median"])
    assert np.isfinite(degenerate["delta_e00_median"]), "colour survives a dead denominator"
    assert good["n_radiance"] == h * w


def test_the_veiling_light_must_be_one_the_image_can_actually_carry():
    """Synthesise a scene the far-field estimator gets wrong, the way the footage does.

    The water column is clipped at 1.0 in blue, so the far-field p90 reports
    Binf_B = 1.0 and the inversion subtracts more blue than the mid-field
    contains. The admissible bound is what stops that.
    """
    from experiments.week4_mono.round1 import restoration

    h, w = 64, 64
    d = np.full((h, w), 6.0)
    d[:8] = 40.0                       # a far band: the water column
    b_bs = restoration.WATER_TYPES["coastal"]["b_bs"]
    b_att = restoration.WATER_TYPES["coastal"]["b_att"]
    I = np.zeros((h, w, 3))
    I[..., 0], I[..., 1], I[..., 2] = 0.02, 0.10, 0.14
    I[24:48] = [0.06, 0.22, 0.30]      # a brighter mid-field object
    I[:8] = [0.09, 0.46, 1.0]          # clipped blue in the far band
    ok = np.ones((h, w), dtype=bool)

    far = restoration.estimate_veiling_light(I, d, ok)
    adm = restoration.admissible_veiling_light(I, d, ok, b_bs)
    assert far[2] > 0.9, "the far-field estimator should read the clipped column as ~1"
    assert adm[2] < far[2], "the admissible bound must be tighter than the far field here"

    _, ok_far, st_far, _ = restoration.restore(I, d, ok, b_att, b_bs, far)
    _, ok_adm, st_adm, resp = restoration.restore(I, d, ok, b_att, b_bs,
                                                  np.minimum(far, adm))
    assert st_far["negative_fraction"] > 0.5, "the inadmissible Binf should over-subtract"
    assert st_adm["negative_fraction"] < 0.05, "the admissible Binf should not"
    assert resp.sum() > 0


def test_the_transmission_floor_caps_the_inversion_gain():
    from experiments.week4_mono.round1 import restoration

    d = np.full((16, 16), 40.0)        # far past where red is recoverable
    I = np.full((16, 16, 3), 0.05)
    ok = np.ones((16, 16), dtype=bool)
    c = restoration.WATER_TYPES["coastal"]
    _, _, st, resp = restoration.restore(I, d, ok, c["b_att"], c["b_bs"],
                                         np.array([0.01, 0.02, 0.03]))
    assert st["gain_p99"] <= 1.0 / restoration.T_FLOOR + 1e-6
    assert st["gain_p99_uncapped"] > 1e3, "the raw inversion really does ask for that much"
    assert st["floored_fraction_all"] == 1.0
    assert resp.sum() == 0, "a fully floored pixel cannot report on the range field"
