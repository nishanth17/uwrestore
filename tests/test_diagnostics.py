"""Tests for uw/diagnostics.py — Week 2 Phase 2C/2D signal diagnostics.

These prove the diagnostics mean exactly what their names claim: a
near-floor fraction is a property of the frame it was computed on, a
correction's gain is reported beside it, and nothing here is mislabeled as
SNR/noise (CLAUDE.md Phase 2C/2D explicitly defers real noise
characterization).
"""

import numpy as np
import pytest

from uw.baselines import gray_world, white_patch
from uw.diagnostics import (
    NEAR_FLOOR_THRESHOLD,
    SATURATION_THRESHOLD,
    aggregate_signal_diagnostics,
    correction_gain,
    diagnostics_as_dict,
    out_of_range_fraction,
    signal_diagnostics,
)
from uw.types import Frame


def _flat_frame(r, g, b, h=10, w=10, **meta):
    image = np.empty((h, w, 3), dtype=np.float32)
    image[..., 0] = r
    image[..., 1] = g
    image[..., 2] = b
    return Frame(image=image, metadata=meta)


# ---------------------------------------------------------------------------
# Near-floor fraction
# ---------------------------------------------------------------------------


def test_near_floor_fraction_is_exact_for_a_controlled_frame():
    # Half the pixels below the floor, half comfortably above it.
    image = np.full((10, 10, 3), 0.5, dtype=np.float32)
    image[:5, :, 0] = NEAR_FLOOR_THRESHOLD  # at the threshold: counted "at or below"
    image[5:, :, 0] = NEAR_FLOOR_THRESHOLD * 100
    frame = Frame(image=image, metadata={})
    d = signal_diagnostics(frame)
    assert d.near_floor_fraction["r"] == pytest.approx(0.5)
    assert d.near_floor_fraction["g"] == 0.0
    assert d.near_floor_fraction["b"] == 0.0


def test_near_floor_threshold_is_inclusive():
    frame = _flat_frame(NEAR_FLOOR_THRESHOLD, 0.5, 0.5)
    d = signal_diagnostics(frame)
    assert d.near_floor_fraction["r"] == 1.0


def test_near_floor_reuses_the_illumination_fit_floor_constant():
    """One project-wide threshold: this is NOT a second, independently
    chosen number that merely happens to match Phase 2B's."""
    from uw.metrics import ILLUM_FLOOR_LINEAR

    assert NEAR_FLOOR_THRESHOLD is ILLUM_FLOOR_LINEAR


# ---------------------------------------------------------------------------
# Saturation / upper-bound fraction
# ---------------------------------------------------------------------------


def test_saturation_fraction_is_exact_for_a_controlled_frame():
    image = np.full((10, 10, 3), 0.5, dtype=np.float32)
    image[:3, :, 2] = 1.0
    frame = Frame(image=image, metadata={})
    d = signal_diagnostics(frame)
    assert d.saturation_fraction["b"] == pytest.approx(0.3)
    assert d.saturation_fraction["r"] == 0.0


def test_saturation_threshold_does_not_flag_near_white_values():
    """0.99 is bright but not AT the boundary — must not be reported as
    saturated (the boundary is exact 1.0, not a soft near-ceiling band)."""
    frame = _flat_frame(0.99, 0.99, 0.99)
    d = signal_diagnostics(frame)
    assert d.saturation_fraction == {"r": 0.0, "g": 0.0, "b": 0.0}
    assert SATURATION_THRESHOLD == 1.0


# ---------------------------------------------------------------------------
# Per-channel distinction
# ---------------------------------------------------------------------------


def test_a_weak_channel_shows_much_higher_near_floor_fraction():
    frame = _flat_frame(r=0.001, g=0.4, b=0.4)
    d = signal_diagnostics(frame)
    assert d.near_floor_fraction["r"] == 1.0
    assert d.near_floor_fraction["g"] == 0.0
    assert d.near_floor_fraction["b"] == 0.0


# ---------------------------------------------------------------------------
# Original-versus-corrected semantics (CLAUDE.md Phase 2C/2D §3)
# ---------------------------------------------------------------------------


def test_correction_does_not_overwrite_the_original_near_floor_evidence():
    frame = _flat_frame(r=0.001, g=0.3, b=0.3, transfer_function="srgb")
    original = signal_diagnostics(frame)
    assert original.near_floor_fraction["r"] == 1.0

    corrected = white_patch(frame)
    gain = correction_gain(corrected.metadata, "white_patch")
    assert gain[0] > 1.0  # a real gain was applied to the weak channel

    # The ORIGINAL diagnostic object is unaffected by anything the
    # correction did — it was computed once, on `frame`, and nothing here
    # recomputes or mutates it.
    assert original.near_floor_fraction["r"] == 1.0

    # It is fine to ALSO compute a diagnostic on the corrected frame for
    # descriptive purposes, and it may well differ (the gain moved values
    # away from the floor) — but that is not evidence of recovered signal,
    # only of a multiply. Both facts stay visible; neither is deleted.
    corrected_diag = signal_diagnostics(corrected)
    assert corrected_diag.near_floor_fraction["r"] < original.near_floor_fraction["r"]


def test_gray_world_reports_a_large_gain_beside_the_original_floor_evidence():
    frame = _flat_frame(r=0.01, g=0.4, b=0.4)
    original = signal_diagnostics(frame)
    corrected = gray_world(frame)
    gain = correction_gain(corrected.metadata, "gray_world")
    assert gain[0] > 5.0  # red was far below the other channels
    assert original.near_floor_fraction["r"] == 0.0  # 0.01 > 0.0025, not at the floor
    # But a MUCH weaker red demonstrates the floor+gain combination directly:
    weak = _flat_frame(r=0.0001, g=0.4, b=0.4)
    weak_original = signal_diagnostics(weak)
    weak_corrected = gray_world(weak)
    weak_gain = correction_gain(weak_corrected.metadata, "gray_world")
    assert weak_original.near_floor_fraction["r"] == 1.0
    assert weak_gain[0] > 100.0


# ---------------------------------------------------------------------------
# Gain reporting
# ---------------------------------------------------------------------------


def test_gray_world_gain_lookup_matches_its_own_metadata():
    frame = _flat_frame(0.1, 0.3, 0.5)
    corrected = gray_world(frame)
    assert correction_gain(corrected.metadata, "gray_world") == \
        corrected.metadata["gray_world_channel_scale"]


def test_white_patch_gain_lookup_matches_its_own_metadata():
    frame = _flat_frame(0.1, 0.3, 0.5)
    corrected = white_patch(frame)
    assert correction_gain(corrected.metadata, "white_patch") == \
        corrected.metadata["white_patch_channel_gain"]


def test_clahe_has_no_global_gain_to_report():
    frame = _flat_frame(0.1, 0.3, 0.5)
    assert correction_gain(frame.metadata, "clahe") is None


def test_unknown_stage_has_no_gain_key():
    assert correction_gain({"anything": 1}, "not_a_stage") is None


# ---------------------------------------------------------------------------
# Aggregation across a sequence
# ---------------------------------------------------------------------------


def test_aggregate_pools_by_pixel_count_not_naive_average():
    small = _flat_frame(NEAR_FLOOR_THRESHOLD, 0.5, 0.5, h=2, w=2)  # 4 px, all near-floor
    large = _flat_frame(0.5, 0.5, 0.5, h=100, w=100)  # 10000 px, none near-floor
    agg = aggregate_signal_diagnostics([small, large])
    # Naive per-frame averaging would give 0.5; pixel-weighted must be tiny.
    assert agg.near_floor_fraction["r"] < 0.01
    assert agg.pixel_count == 4 + 100 * 100


def test_aggregate_rejects_empty_sequence():
    with pytest.raises(ValueError):
        aggregate_signal_diagnostics([])


def test_zero_size_frame_is_refused_rather_than_reported_as_nan():
    """REGRESSION. A fraction over zero pixels is undefined, and numpy's
    answer was a silent NaN plus two RuntimeWarnings — which would reach the
    report looking like a measured value. The aggregate path additionally
    raised ZeroDivisionError. Both now fail clearly at the source."""
    empty = Frame(image=np.zeros((0, 0, 3), dtype=np.float32), metadata={})
    with pytest.raises(ValueError, match="empty"):
        signal_diagnostics(empty)
    with pytest.raises(ValueError, match="empty"):
        aggregate_signal_diagnostics([empty])


def test_signal_diagnostics_rejects_non_rgb_shapes():
    for bad in (np.zeros((8, 8), np.float32), np.zeros((8, 8, 4), np.float32)):
        with pytest.raises(ValueError, match=r"\(H, W, 3\)"):
            signal_diagnostics(Frame(image=bad, metadata={}))


# ---------------------------------------------------------------------------
# Out-of-range fraction
# ---------------------------------------------------------------------------


def test_out_of_range_fraction_counts_both_directions():
    image = np.zeros((10, 10, 3), dtype=np.float32)
    image[0, 0] = -0.1
    image[0, 1] = 1.5
    assert out_of_range_fraction(image) == pytest.approx(2 / 100)


def test_out_of_range_fraction_is_zero_in_range():
    image = np.full((5, 5, 3), 0.5, dtype=np.float32)
    assert out_of_range_fraction(image) == 0.0


# ---------------------------------------------------------------------------
# No fake SNR/noise metric
# ---------------------------------------------------------------------------


def test_no_field_is_labeled_snr_or_noise():
    frame = _flat_frame(0.1, 0.3, 0.5)
    d = diagnostics_as_dict(signal_diagnostics(frame))
    corrected = gray_world(frame)
    keys = set(d.keys()) | set(corrected.metadata.keys())
    for key in keys:
        low = str(key).lower()
        assert "snr" not in low
        assert "noise" not in low


def test_out_of_range_fraction_counts_non_finite_values():
    """AR-06 REGRESSION. `(a<0)|(a>1)` is False for NaN, so a NaN-bearing
    image reported 0.0 — "no range violation" — for values that are not in
    the range at all. clahe deliberately propagates NaN, so this is
    reachable."""
    assert out_of_range_fraction(np.array([np.nan], np.float32)) == 1.0
    assert out_of_range_fraction(np.array([np.inf], np.float32)) == 1.0
    assert out_of_range_fraction(np.array([-np.inf], np.float32)) == 1.0
    image = np.full((10, 10, 3), 0.5, dtype=np.float32)
    image[0, 0, 0] = np.nan
    assert out_of_range_fraction(image) == pytest.approx(1 / 300)
