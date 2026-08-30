"""Tests for uw/baselines.py's Week 2 Phase 2C/2D additions: white_patch and
clahe. gray_world (Week 1) is exercised incidentally here and directly in
tests/test_diagnostics.py and tests/test_pipeline.py; it is otherwise
unchanged this phase.
"""

import warnings

import cv2
import numpy as np
import pytest

from uw.baselines import (
    CLAHE_NEAR_BLACK_Y,
    WHITE_PATCH_MIN_BRIGHT_PIXELS,
    WHITE_PATCH_TOP_PERCENTILE,
    clahe,
    gray_world,
    white_patch,
)
from uw.colorspace import y_to_lstar
from uw.diagnostics import out_of_range_fraction
from uw.metrics import linear_luminance
from uw.types import Frame


def _cast_frame(h=40, w=40, seed=0):
    """A frame with a blue-green cast and NO plausible bright neutral patch —
    used for tests that don't care about the bright-region content."""
    rng = np.random.default_rng(seed)
    image = np.empty((h, w, 3), dtype=np.float32)
    image[..., 0] = 0.05
    image[..., 1] = 0.30
    image[..., 2] = 0.32
    image += rng.normal(0, 0.01, image.shape).astype(np.float32)
    return Frame(image=np.clip(image, 0, 1).astype(np.float32),
                 metadata={"source_path": "fake.mp4", "transfer_function": "srgb"})


def _cast_frame_with_bright_patch(h=40, w=40, patch=6, seed=0):
    """Same cast, plus a small bright corner that is itself cast-colored —
    i.e. a plausible sunlit reference the estimator should find and correct."""
    frame = _cast_frame(h, w, seed)
    image = frame.image.copy()
    image[:patch, :patch] = [0.35, 0.85, 0.85]
    return Frame(image=image, metadata=frame.metadata)


# ---------------------------------------------------------------------------
# white_patch
# ---------------------------------------------------------------------------


def test_white_patch_does_not_mutate_input():
    frame = _cast_frame_with_bright_patch()
    before = frame.image.copy()
    white_patch(frame)
    np.testing.assert_array_equal(frame.image, before)


def test_white_patch_preserves_existing_metadata():
    frame = _cast_frame_with_bright_patch()
    result = white_patch(frame)
    assert result.metadata["source_path"] == "fake.mp4"
    assert result.metadata["transfer_function"] == "srgb"


def test_white_patch_records_gains_and_range_diagnostics():
    frame = _cast_frame_with_bright_patch()
    result = white_patch(frame)
    assert "white_patch_channel_gain" in result.metadata
    assert len(result.metadata["white_patch_channel_gain"]) == 3
    assert "white_patch_out_of_range_fraction" in result.metadata
    assert result.metadata["white_patch_out_of_range_fraction"] == \
        out_of_range_fraction(result.image)
    assert "white_patch_bright_region_fraction" in result.metadata
    assert "white_patch_reference_rgb" in result.metadata
    assert result.metadata["white_patch_top_percentile"] == WHITE_PATCH_TOP_PERCENTILE


def test_white_patch_moves_the_bright_reference_toward_neutral():
    """Controlled cast: the bright patch is [0.35, 0.85, 0.85] — a 2.43x
    red deficit relative to green/blue. The derived gain must correct
    close to that ratio (median-of-region, so not exact to noise)."""
    frame = _cast_frame_with_bright_patch(seed=1)
    result = white_patch(frame)
    gain = result.metadata["white_patch_channel_gain"]
    r_gain, g_gain, b_gain = gain
    assert r_gain == pytest.approx(0.85 / 0.35, rel=0.15)
    assert g_gain == pytest.approx(1.0, abs=0.05)
    assert b_gain == pytest.approx(1.0, abs=0.05)

    # And directly: applying the gain to the reference patch's own median
    # must land close to neutral (R == G == B).
    reference = np.array(result.metadata["white_patch_reference_rgb"])
    corrected_reference = reference * gain
    assert corrected_reference[0] == pytest.approx(corrected_reference[1], rel=0.05)
    assert corrected_reference[1] == pytest.approx(corrected_reference[2], rel=0.05)


def test_white_patch_isolated_hot_pixel_does_not_dominate():
    """A single pathological maximum (a hot pixel / bubble glint / clipped
    dive-light speck) must not defeat the percentile+median estimator."""
    frame = _cast_frame_with_bright_patch(seed=2)
    without_hot_pixel = white_patch(frame)

    with_hot_pixel_image = frame.image.copy()
    with_hot_pixel_image[0, 0] = [50.0, 0.0, 50.0]  # absurd, isolated, magenta
    with_hot_pixel = white_patch(Frame(image=with_hot_pixel_image, metadata=frame.metadata))

    gain_a = np.array(without_hot_pixel.metadata["white_patch_channel_gain"])
    gain_b = np.array(with_hot_pixel.metadata["white_patch_channel_gain"])
    # One outlier pixel among 1600 must not move the gain by orders of
    # magnitude; it may move it a little (it does enter the top-percentile
    # luminance mask, but the median rejects it).
    np.testing.assert_allclose(gain_a, gain_b, rtol=0.1)


def test_white_patch_bright_region_never_collapses_to_one_pixel():
    """REGRESSION. Before the WHITE_PATCH_MIN_BRIGHT_PIXELS floor existed,
    a small frame's top-1% rounded down to exactly ONE pixel, silently
    turning the "robust median over a region" estimator into precisely the
    single-brightest-pixel rule the Phase 2C brief forbids. The 40x40
    frames used elsewhere in this file are large enough to hide it."""
    for h, w in [(10, 10), (8, 8), (5, 5), (4, 4), (3, 3)]:
        rng = np.random.default_rng(0)
        image = np.clip(
            np.full((h, w, 3), 0.3, np.float32)
            + rng.normal(0, 0.01, (h, w, 3)).astype(np.float32),
            0, None,
        )
        result = white_patch(Frame(image=image, metadata={}))
        n_selected = round(result.metadata["white_patch_bright_region_fraction"] * h * w)
        assert n_selected >= min(WHITE_PATCH_MIN_BRIGHT_PIXELS, h * w), (
            f"{h}x{w} selected only {n_selected} px"
        )


def test_white_patch_hot_pixel_does_not_dominate_a_SMALL_frame():
    """REGRESSION for the same bug, stated as the property that actually
    matters. Measured before the fix: one pathological hot pixel on a 10x10
    frame drove the derived gain to 5e7x."""
    h = w = 10
    rng = np.random.default_rng(1)
    image = np.clip(
        np.full((h, w, 3), 0.3, np.float32)
        + rng.normal(0, 0.01, (h, w, 3)).astype(np.float32),
        0, None,
    )
    clean = white_patch(Frame(image=image, metadata={}))
    hot = image.copy()
    hot[0, 0] = [50.0, 0.0, 50.0]
    dirty = white_patch(Frame(image=hot, metadata={}))

    gain_clean = np.array(clean.metadata["white_patch_channel_gain"])
    gain_dirty = np.array(dirty.metadata["white_patch_channel_gain"])
    np.testing.assert_allclose(gain_clean, gain_dirty, rtol=0.05)


def test_white_patch_selection_includes_pixels_tied_at_the_threshold():
    """A large clipped/saturated plateau must be kept whole, not truncated
    at an arbitrary percentile boundary inside the tie."""
    image = np.full((20, 20, 3), 0.2, dtype=np.float32)
    image[:5, :] = 1.0  # 25% of the frame tied at the ceiling
    result = white_patch(Frame(image=image, metadata={}))
    # All 100 tied pixels are selected, not just the top-1% count of 4.
    assert result.metadata["white_patch_bright_region_fraction"] == pytest.approx(0.25)


def test_white_patch_all_black_frame_reports_identity_not_zero_gain():
    """An all-black frame has no bright reference and no illuminant to
    estimate; identity is the honest record. A gain of 0.0 would be
    harmless numerically but misleading provenance."""
    result = white_patch(Frame(image=np.zeros((10, 10, 3), np.float32), metadata={}))
    assert result.metadata["white_patch_channel_gain"] == [1.0, 1.0, 1.0]
    np.testing.assert_array_equal(result.image, np.zeros((10, 10, 3), np.float32))


def test_white_patch_is_deterministic():
    frame = _cast_frame_with_bright_patch(seed=3)
    a = white_patch(frame)
    b = white_patch(frame)
    np.testing.assert_array_equal(a.image, b.image)
    assert a.metadata["white_patch_channel_gain"] == b.metadata["white_patch_channel_gain"]


def test_white_patch_handles_a_fully_black_frame_safely():
    frame = Frame(image=np.zeros((10, 10, 3), dtype=np.float32), metadata={})
    result = white_patch(frame)
    assert np.isfinite(result.image).all()
    assert np.isfinite(result.metadata["white_patch_channel_gain"]).all() if isinstance(
        result.metadata["white_patch_channel_gain"], np.ndarray
    ) else all(np.isfinite(g) for g in result.metadata["white_patch_channel_gain"])


def test_white_patch_gain_is_finite_even_with_an_extreme_channel_deficit():
    """A channel effectively absent from the bright region (near zero) must
    not produce NaN/Inf — a large finite gain is acceptable and visible via
    out_of_range_fraction, matching gray_world's no-clamp convention."""
    image = np.zeros((10, 10, 3), dtype=np.float32)
    image[..., 0] = 1e-9  # ~absent
    image[..., 1] = 0.5
    image[..., 2] = 0.5
    result = white_patch(Frame(image=image, metadata={}))
    gain = result.metadata["white_patch_channel_gain"]
    assert all(np.isfinite(g) for g in gain)
    assert np.isfinite(result.image).all()


def test_white_patch_surfaces_out_of_range_output():
    """gain_c = max(reference) / reference_c never pushes the reference
    region itself out of range (the max channel keeps gain 1) — but a
    pixel ELSEWHERE that already sits close to the ceiling in a boosted
    channel can be pushed past 1.0, and that must stay visible rather than
    silently clipped."""
    frame = _cast_frame_with_bright_patch(seed=4)
    image = frame.image.copy()
    # Low-luminance (so it is NOT selected into the bright reference region)
    # but already bright in the channel that will be boosted.
    image[-1, -1] = [0.6, 0.0, 0.0]
    frame = Frame(image=image, metadata=frame.metadata)

    result = white_patch(frame)
    assert result.metadata["white_patch_out_of_range_fraction"] > 0.0
    assert (result.image > 1.0).any()  # not silently clipped


# ---------------------------------------------------------------------------
# Frame-contract enforcement (shared by all three stages)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("stage", [gray_world, white_patch, clahe])
def test_stages_reject_integer_dtype_instead_of_silently_zeroing(stage):
    """REGRESSION. Frame documents "image is floating point", but nothing
    enforced it and the failure was silent DATA DESTRUCTION, not an error:
    a uint8 Frame through `clahe` returned an all-zero image with no
    exception and no warning, and through `gray_world` silently truncated
    every corrected value back to an integer code."""
    frame = Frame(image=np.full((16, 16, 3), 128, dtype=np.uint8), metadata={})
    with pytest.raises(TypeError, match="floating-point"):
        stage(frame)


@pytest.mark.parametrize("stage", [gray_world, white_patch, clahe])
def test_stages_accept_float64_not_only_float32(stage):
    """The invariant is "floating", not "float32" — float64 must pass."""
    result = stage(Frame(image=np.full((16, 16, 3), 0.3, dtype=np.float64), metadata={}))
    assert np.issubdtype(result.image.dtype, np.floating)


# ---------------------------------------------------------------------------
# clahe
# ---------------------------------------------------------------------------


def _textured_frame(h=64, w=64, low=0.15, high=0.45, seed=0):
    """A spatial low-contrast pattern: alternating soft blocks around a
    narrow luminance band, plus texture so CLAHE tiles are not flat."""
    rng = np.random.default_rng(seed)
    base = np.full((h, w), (low + high) / 2, dtype=np.float64)
    block = 8
    for by in range(0, h, block):
        for bx in range(0, w, block):
            if ((by // block) + (bx // block)) % 2 == 0:
                base[by:by + block, bx:bx + block] = low
            else:
                base[by:by + block, bx:bx + block] = high
    base += rng.normal(0, 0.01, base.shape)
    image = np.stack([base, base, base], axis=-1).astype(np.float32)
    return Frame(image=np.clip(image, 0, 1), metadata={"note": "keep-me"})


def test_clahe_does_not_mutate_input():
    frame = _textured_frame()
    before = frame.image.copy()
    clahe(frame)
    np.testing.assert_array_equal(frame.image, before)


def test_clahe_preserves_existing_metadata():
    frame = _textured_frame()
    result = clahe(frame)
    assert result.metadata["note"] == "keep-me"


def test_clahe_records_range_and_config_diagnostics():
    frame = _textured_frame()
    result = clahe(frame)
    for key in (
        "clahe_clip_limit", "clahe_tile_grid_size", "clahe_near_black_threshold",
        "clahe_near_black_fraction", "clahe_control_bounded_fraction",
        "clahe_out_of_range_fraction",
    ):
        assert key in result.metadata
    assert result.metadata["clahe_out_of_range_fraction"] == out_of_range_fraction(result.image)


def test_clahe_control_bounded_fraction_is_exact_not_just_present():
    """The key existing is not enough — it must actually report how much of
    the frame needed the [0, 100] L* clamp, not always 0. Half the frame at
    Y=2.0 (L* ≈ 130, verified > 100) and half at Y=0.3 (L* well within
    range) must report exactly 0.5, matching the known fraction, not a
    placeholder or an always-zero value."""
    image = np.zeros((10, 10, 3), dtype=np.float32)
    image[:5] = 2.0
    image[5:] = 0.3
    result = clahe(Frame(image=image, metadata={}))
    assert result.metadata["clahe_control_bounded_fraction"] == pytest.approx(0.5)


def test_clahe_control_bounded_fraction_is_zero_when_nothing_needed_clamping():
    frame = Frame(image=np.full((10, 10, 3), 0.3, dtype=np.float32), metadata={})
    result = clahe(frame)
    assert result.metadata["clahe_control_bounded_fraction"] == 0.0


def test_clahe_public_contract_is_linear_rgb_float():
    frame = _textured_frame()
    result = clahe(frame)
    assert result.image.dtype == frame.image.dtype
    assert result.image.shape == frame.image.shape
    assert np.issubdtype(result.image.dtype, np.floating)


def test_clahe_does_not_leak_lstar_or_uint16_VALUES_not_just_dtype():
    """Checking dtype alone is not enough to catch a leaked intermediate: an
    L* array is float32 with the right shape and would sail through a
    dtype-only assertion. This pins the VALUE RANGE instead.

    The fixture's own L* spans roughly 45..90, and the uint16 control domain
    spans 0..65535 — both far outside plausible linear-light RGB, so a leak
    of either representation is unambiguous.
    """
    frame = _textured_frame()
    lstar = y_to_lstar(linear_luminance(frame.image))
    assert lstar.max() > 20.0  # the fixture really would expose an L* leak

    result = clahe(frame)
    # Linear-light RGB from a [0,1] input stays O(1); it may exceed 1.0
    # (deliberately unclipped) but cannot reach the L* or uint16 domains.
    assert result.image.max() < 5.0
    assert result.image.min() > -1.0


def test_clahe_uses_uint16_not_uint8(monkeypatch):
    captured = {}
    real_create_clahe = cv2.createCLAHE

    class _SpyClahe:
        def __init__(self, *a, **kw):
            self._inner = real_create_clahe(*a, **kw)

        def apply(self, arr):
            captured["dtype"] = arr.dtype
            captured["max_value"] = int(arr.max())
            return self._inner.apply(arr)

    monkeypatch.setattr(cv2, "createCLAHE", lambda *a, **kw: _SpyClahe(*a, **kw))
    clahe(_textured_frame())
    assert captured["dtype"] == np.uint16
    # A real uint8 accident would have capped this at 255 well before this
    # point; confirm the pipeline actually used the wider range.
    assert captured["max_value"] > 255


def test_clahe_neutral_ramp_stays_neutral():
    h, w = 32, 32
    ramp = np.linspace(0.05, 0.9, w, dtype=np.float32)
    image = np.tile(ramp, (h, 1))
    frame = Frame(image=np.stack([image, image, image], axis=-1), metadata={})
    result = clahe(frame)
    r, g, b = result.image[..., 0], result.image[..., 1], result.image[..., 2]
    np.testing.assert_allclose(r, g, atol=1e-5)
    np.testing.assert_allclose(g, b, atol=1e-5)


def test_clahe_increases_local_contrast_on_a_low_contrast_pattern():
    frame = _textured_frame(low=0.20, high=0.24)  # subtle difference
    result = clahe(frame)
    before_diff = abs(
        frame.image[:8, :8, 0].mean() - frame.image[:8, 8:16, 0].mean()
    )
    after_diff = abs(
        result.image[:8, :8, 0].mean() - result.image[:8, 8:16, 0].mean()
    )
    assert after_diff > before_diff


def test_clahe_dark_gradient_does_not_collapse_to_8bit_precision():
    """A smooth dark gradient (representative of underwater shadow detail)
    must keep far more than 256 distinct output levels."""
    h, w = 4, 2000
    gradient = np.linspace(0.003, 0.05, w, dtype=np.float64)
    image = np.tile(gradient, (h, 1))
    frame = Frame(image=np.stack([image, image, image], axis=-1).astype(np.float32),
                  metadata={})
    result = clahe(frame)
    unique_levels = len(np.unique(np.round(result.image[..., 0], 6)))
    assert unique_levels > 256


def test_clahe_near_black_reconstruction_is_stable_and_unchanged():
    frame = Frame(image=np.zeros((16, 16, 3), dtype=np.float32), metadata={})
    result = clahe(frame)
    assert np.isfinite(result.image).all()
    assert not np.isnan(result.image).any()
    assert not np.isinf(result.image).any()
    # Preservation, not just stability: genuinely near-black content stays
    # near-black rather than being relit toward CLAHE's flat-tile ceiling.
    np.testing.assert_allclose(result.image, 0.0, atol=1e-6)
    assert result.metadata["clahe_near_black_fraction"] == 1.0


def test_clahe_near_black_threshold_matches_diagnostics_floor():
    from uw.diagnostics import NEAR_FLOOR_THRESHOLD

    assert CLAHE_NEAR_BLACK_Y == NEAR_FLOOR_THRESHOLD


def test_clahe_mixed_frame_keeps_near_black_region_dark():
    image = np.zeros((16, 16, 3), dtype=np.float32)
    image[8:] = 0.5
    result = clahe(Frame(image=image, metadata={}))
    assert np.allclose(result.image[:8], 0.0, atol=1e-6)


def test_clahe_preserves_chromaticity_away_from_near_black():
    """CLAHE scales R, G, B by the SAME per-pixel scalar (luminance-ratio
    reconstruction), so channel ratios must be preserved away from the
    near-black branch and any range clipping (there is none here)."""
    h, w = 32, 32
    rng = np.random.default_rng(5)
    base = 0.3 + 0.05 * rng.standard_normal((h, w))
    r = base * 1.0
    g = base * 0.5
    b = base * 0.2
    image = np.clip(np.stack([r, g, b], axis=-1), 0.05, None).astype(np.float32)
    frame = Frame(image=image, metadata={})
    result = clahe(frame)

    orig_ratio_rg = frame.image[..., 0] / frame.image[..., 1]
    corr_ratio_rg = result.image[..., 0] / result.image[..., 1]
    np.testing.assert_allclose(orig_ratio_rg, corr_ratio_rg, rtol=1e-4)

    orig_ratio_gb = frame.image[..., 1] / frame.image[..., 2]
    corr_ratio_gb = result.image[..., 1] / result.image[..., 2]
    np.testing.assert_allclose(orig_ratio_gb, corr_ratio_gb, rtol=1e-4)


def test_clahe_amplification_above_the_near_black_guard_is_bounded_and_stable():
    """Section-7 property, stated precisely. Just ABOVE the near-black
    threshold the luminance-ratio branch is active and CAN apply a large
    scale (measured up to ~34x on a dark region beside a bright one). That
    is CLAHE legitimately lifting shadows, not ill-conditioning, and the
    distinction is testable:

      * BOUNDED — the guard caps the denominator, so the scale can never
        exceed 1.0 / CLAHE_NEAR_BLACK_Y = 400x by construction;
      * WELL-CONDITIONED — perturbing the input luminance by 1e-9..1e-5
        must not swing the output, which is what "ill-conditioned" would
        actually mean.
    """
    def dark_region_output(y_dark):
        image = np.zeros((64, 64, 3), dtype=np.float32)
        image[:, :32] = y_dark
        image[:, 32:] = 0.8
        return clahe(Frame(image=image, metadata={})).image[:, :32].mean()

    base = CLAHE_NEAR_BLACK_Y + 1e-4
    reference = dark_region_output(base)
    for eps in (1e-9, 1e-7, 1e-5):
        assert dark_region_output(base + eps) == pytest.approx(reference, rel=1e-3)

    assert reference / base < 1.0 / CLAHE_NEAR_BLACK_Y  # the 400x hard bound


def test_clahe_nan_input_stays_local_and_casts_without_undefined_behaviour():
    """A NaN pixel must (a) not trigger numpy's undefined float->uint16 cast
    (which warns and yields an arbitrary code fed into that tile's
    histogram), and (b) still propagate to the output rather than being
    silently repaired. Measured: contamination is local either way — one
    NaN changes nothing outside its own tile neighbourhood."""
    rng = np.random.default_rng(0)
    clean = np.clip(rng.uniform(0.1, 0.6, (64, 64, 3)), 0, None).astype(np.float32)
    dirty = clean.copy()
    dirty[0, 0] = np.nan

    with warnings.catch_warnings():
        warnings.simplefilter("error")  # any RuntimeWarning fails the test
        out_dirty = clahe(Frame(image=dirty, metadata={})).image

    out_clean = clahe(Frame(image=clean, metadata={})).image
    assert (~np.isfinite(out_dirty)).sum() == 3  # NaN propagates, not repaired

    difference = np.abs(np.nan_to_num(out_clean) - np.nan_to_num(out_dirty))
    difference[:16, :16] = 0.0  # the corrupted pixel's own tile neighbourhood
    assert difference.max() == 0.0


def test_clahe_flat_region_pathology_is_isolated_to_non_near_black_tiles():
    """Documents a real, verified property of cv2's CLAHE (not this
    project's algorithm): a perfectly FLAT tile maps to the tile's maximum
    output value regardless of brightness. The near-black branch protects
    genuinely dark content from it; a flat MID-brightness tile is not
    near-black and is not specially protected — this is a known CLAHE
    limitation, recorded rather than silently worked around."""
    image = np.full((16, 16, 3), 0.5, dtype=np.float32)
    result = clahe(Frame(image=image, metadata={}))
    assert result.image.max() > 0.9  # pushed toward the ceiling, as expected
    assert np.isfinite(result.image).all()


def test_clahe_does_not_collapse_above_white_content():
    """AR-02 REGRESSION. Bounding L* to [0,100] for CLAHE's control signal
    is supposed to be TEMPORARY, but the bounded result was inverted and
    used in Y'/Y, which silently clipped every above-white pixel to exactly
    1.0 — the temporary bound leaking into the returned linear RGB, and a
    misreport of a preceding stage's genuine out-of-range output as
    in-range. Measured before the fix: a neutral Y=2.0 frame came back
    0.9999999, and every sample of a 0.01..2.0 gradient above 1.0 mapped to
    1.0."""
    image = np.full((64, 64, 3), 2.0, dtype=np.float32)
    result = clahe(Frame(image=image, metadata={}))
    np.testing.assert_allclose(result.image, 2.0, rtol=1e-6)
    assert result.metadata["clahe_above_white_fraction"] == pytest.approx(1.0)

    ramp = np.linspace(0.01, 2.0, 512, dtype=np.float32)
    gradient = np.stack([np.tile(ramp, (64, 1))] * 3, axis=-1)
    out = clahe(Frame(image=gradient, metadata={})).image
    above = ramp > 1.0
    # Above-white samples are preserved, not flattened onto the ceiling.
    np.testing.assert_allclose(out[0, above, 0], ramp[above], rtol=1e-5)
    assert out[0, above, 0].max() > 1.9


def test_clahe_above_white_fraction_is_reported():
    image = np.full((10, 10, 3), 0.3, dtype=np.float32)
    image[:2] = 1.5
    result = clahe(Frame(image=image, metadata={}))
    assert result.metadata["clahe_above_white_fraction"] == pytest.approx(0.2)
