"""Tests for uw.metrics: the CIEDE2000 formula and the delta_e chart metric.

The CIEDE2000 correctness test uses the published supplementary test data
from Sharma, Wu & Dalal (2005), "The CIEDE2000 Color-Difference Formula:
Implementation Notes, Supplementary Test Data, and Mathematical
Observations", Color Research & Application 30(1):21-30. Those 34 pairs are
not arbitrary samples — they are constructed to exercise exactly the cases a
naive implementation gets wrong (the arctangent quadrant, the mean-hue
discontinuity at 0/360, and the zero-chroma branches), so passing all 34 is
a meaningful check rather than a smoke test.
"""

import numpy as np
import pytest

from uw.colorspace import (
    D50_WHITE_XYZ,
    D65_WHITE_XYZ,
    adapt_lab,
    linear_rgb_to_lab,
)
from uw.metrics import ciede2000, delta_e
from uw.types import Frame

# (L1, a1, b1, L2, a2, b2, expected dE00), published to 4 decimal places.
SHARMA_TEST_DATA = [
    (50.0000, 2.6772, -79.7751, 50.0000, 0.0000, -82.7485, 2.0425),
    (50.0000, 3.1571, -77.2803, 50.0000, 0.0000, -82.7485, 2.8615),
    (50.0000, 2.8361, -74.0200, 50.0000, 0.0000, -82.7485, 3.4412),
    (50.0000, -1.3802, -84.2814, 50.0000, 0.0000, -82.7485, 1.0000),
    (50.0000, -1.1848, -84.8006, 50.0000, 0.0000, -82.7485, 1.0000),
    (50.0000, -0.9009, -85.5211, 50.0000, 0.0000, -82.7485, 1.0000),
    (50.0000, 0.0000, 0.0000, 50.0000, -1.0000, 2.0000, 2.3669),
    (50.0000, -1.0000, 2.0000, 50.0000, 0.0000, 0.0000, 2.3669),
    (50.0000, 2.4900, -0.0010, 50.0000, -2.4900, 0.0009, 7.1792),
    (50.0000, 2.4900, -0.0010, 50.0000, -2.4900, 0.0010, 7.1792),
    (50.0000, 2.4900, -0.0010, 50.0000, -2.4900, 0.0011, 7.2195),
    (50.0000, 2.4900, -0.0010, 50.0000, -2.4900, 0.0012, 7.2195),
    (50.0000, -0.0010, 2.4900, 50.0000, 0.0009, -2.4900, 4.8045),
    (50.0000, -0.0010, 2.4900, 50.0000, 0.0010, -2.4900, 4.8045),
    (50.0000, -0.0010, 2.4900, 50.0000, 0.0011, -2.4900, 4.7461),
    (50.0000, 2.5000, 0.0000, 50.0000, 0.0000, -2.5000, 4.3065),
    (50.0000, 2.5000, 0.0000, 73.0000, 25.0000, -18.0000, 27.1492),
    (50.0000, 2.5000, 0.0000, 61.0000, -5.0000, 29.0000, 22.8977),
    (50.0000, 2.5000, 0.0000, 56.0000, -27.0000, -3.0000, 31.9030),
    (50.0000, 2.5000, 0.0000, 58.0000, 24.0000, 15.0000, 19.4535),
    (50.0000, 2.5000, 0.0000, 50.0000, 3.1736, 0.5854, 1.0000),
    (50.0000, 2.5000, 0.0000, 50.0000, 3.2972, 0.0000, 1.0000),
    (50.0000, 2.5000, 0.0000, 50.0000, 1.8634, 0.5757, 1.0000),
    (50.0000, 2.5000, 0.0000, 50.0000, 3.2592, 0.3350, 1.0000),
    (60.2574, -34.0099, 36.2677, 60.4626, -34.1751, 39.4387, 1.2644),
    (63.0109, -31.0961, -5.8663, 62.8187, -29.7946, -4.0864, 1.2630),
    (61.2901, 3.7196, -5.3901, 61.4292, 2.2480, -4.9620, 1.8731),
    (35.0831, -44.1164, 3.7933, 35.0232, -40.0716, 1.5901, 1.8645),
    (22.7233, 20.0904, -46.6940, 23.0331, 14.9730, -42.5619, 2.0373),
    (36.4612, 47.8580, 18.3852, 36.2715, 50.5065, 21.2231, 1.4146),
    (90.8027, -2.0831, 1.4410, 91.1528, -1.6435, 0.0447, 1.4441),
    (90.9257, -0.5406, -0.9208, 88.6381, -0.8985, -0.7239, 1.5381),
    (6.7747, -0.2908, -2.4247, 5.8714, -0.0985, -2.2286, 0.6377),
    (2.0776, 0.0795, -1.1350, 0.9033, -0.0636, -0.5514, 0.9082),
]

# The published data carries 4 decimal places, so the true value can differ
# from the tabulated one by up to 5e-5 from rounding alone. 1e-4 is tight
# enough to catch a real formula error and loose enough not to fail on that.
CIEDE2000_TOLERANCE = 1e-4


# ---------------------------------------------------------------------------
# 1. CIEDE2000 formula correctness
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("case", SHARMA_TEST_DATA, ids=lambda c: f"dE00={c[6]}")
def test_ciede2000_matches_sharma_test_data(case):
    l1, a1, b1, l2, a2, b2, expected = case
    computed = ciede2000([l1, a1, b1], [l2, a2, b2])
    assert computed == pytest.approx(expected, abs=CIEDE2000_TOLERANCE)


def test_ciede2000_is_symmetric():
    """dE(A, B) == dE(B, A). Pairs 7/8 and 9-15 of the Sharma data exist
    specifically because asymmetric mean-hue handling breaks this."""
    for l1, a1, b1, l2, a2, b2, _ in SHARMA_TEST_DATA:
        forward = ciede2000([l1, a1, b1], [l2, a2, b2])
        backward = ciede2000([l2, a2, b2], [l1, a1, b1])
        assert forward == pytest.approx(backward, abs=1e-12)


def test_ciede2000_of_identical_colors_is_zero():
    for l1, a1, b1, _, _, _, _ in SHARMA_TEST_DATA:
        assert ciede2000([l1, a1, b1], [l1, a1, b1]) == pytest.approx(0.0, abs=1e-12)


def test_ciede2000_neutral_pair_does_not_produce_nan():
    """Both colors exactly neutral: chroma is zero, so the hue branches must
    take their zero-chroma path instead of dividing by zero."""
    result = ciede2000([50.0, 0.0, 0.0], [60.0, 0.0, 0.0])
    assert np.isfinite(result)
    assert result > 0.0


def test_ciede2000_vectorized_matches_scalar():
    lab1 = np.array([[c[0], c[1], c[2]] for c in SHARMA_TEST_DATA])
    lab2 = np.array([[c[3], c[4], c[5]] for c in SHARMA_TEST_DATA])
    vectorized = ciede2000(lab1, lab2)
    assert vectorized.shape == (len(SHARMA_TEST_DATA),)
    for index, case in enumerate(SHARMA_TEST_DATA):
        assert vectorized[index] == pytest.approx(case[6], abs=CIEDE2000_TOLERANCE)


def test_ciede2000_rejects_non_triplet_input():
    with pytest.raises(ValueError, match=r"\(\.\.\., 3\)"):
        ciede2000([50.0, 0.0], [50.0, 0.0])


# ---------------------------------------------------------------------------
# 2. Linear RGB -> Lab conversion
#
# Reference Lab values for the sRGB primaries and white under D65 are widely
# published (e.g. Bruce Lindbloom's calculator). Note these are the Lab of
# the *linear* values 1.0/0.0 — i.e. sRGB-encoded 255/0 — which is what the
# pipeline's linear working space holds after io.py linearizes on ingest.
# ---------------------------------------------------------------------------

LAB_TOLERANCE = 1e-3


def test_linear_white_maps_to_l100_neutral():
    lab = linear_rgb_to_lab(np.array([1.0, 1.0, 1.0]))
    assert lab[0] == pytest.approx(100.0, abs=1e-4)
    assert lab[1] == pytest.approx(0.0, abs=1e-3)
    assert lab[2] == pytest.approx(0.0, abs=1e-3)


def test_linear_black_maps_to_zero():
    lab = linear_rgb_to_lab(np.array([0.0, 0.0, 0.0]))
    assert np.allclose(lab, [0.0, 0.0, 0.0], atol=1e-12)


@pytest.mark.parametrize(
    "linear_rgb, expected_lab",
    [
        ([1.0, 0.0, 0.0], [53.2408, 80.0925, 67.2032]),
        ([0.0, 1.0, 0.0], [87.7347, -86.1827, 83.1793]),
        ([0.0, 0.0, 1.0], [32.2970, 79.1875, -107.8602]),
    ],
    ids=["red", "green", "blue"],
)
def test_srgb_primaries_have_published_lab_values(linear_rgb, expected_lab):
    lab = linear_rgb_to_lab(np.array(linear_rgb))
    assert lab == pytest.approx(expected_lab, abs=LAB_TOLERANCE)


def test_mid_linear_gray_has_expected_lightness():
    """L* of 50% linear luminance is 76.0693 — the well-known fact that
    'middle gray' is 18-ish percent in linear, not 50 percent."""
    lab = linear_rgb_to_lab(np.array([0.5, 0.5, 0.5]))
    assert lab[0] == pytest.approx(76.0693, abs=1e-3)


def test_lab_conversion_handles_image_shaped_arrays():
    rng = np.random.default_rng(0)
    image = rng.uniform(0.0, 1.0, size=(4, 5, 3))
    lab_image = linear_rgb_to_lab(image)
    assert lab_image.shape == (4, 5, 3)
    for y in range(4):
        for x in range(5):
            expected = linear_rgb_to_lab(image[y, x])
            assert np.allclose(lab_image[y, x], expected, atol=1e-12)


def test_lab_conversion_does_not_mutate_input():
    array = np.array([0.2, 0.5, 0.8])
    original = array.copy()
    linear_rgb_to_lab(array)
    assert np.array_equal(array, original)


def test_negative_linear_values_do_not_produce_nan():
    """gray_world deliberately does not clip, so out-of-range linear values
    reach the metric. CIELAB is undefined below zero; the conversion must
    clamp rather than emit a NaN that silently poisons a mean."""
    lab = linear_rgb_to_lab(np.array([-0.2, 0.5, 0.3]))
    assert np.all(np.isfinite(lab))


def test_above_range_linear_values_exceed_l100():
    """Values above 1.0 are NOT clamped: an over-range patch should register
    as the error it is."""
    lab = linear_rgb_to_lab(np.array([1.5, 1.5, 1.5]))
    assert lab[0] > 100.0


def test_adapt_lab_between_identical_whites_is_a_noop():
    lab = np.array([42.0, 17.0, -23.0])
    assert np.allclose(adapt_lab(lab, D65_WHITE_XYZ, D65_WHITE_XYZ), lab, atol=1e-10)


def test_adapt_lab_d50_to_d65_round_trips():
    lab_d65 = np.array([55.0, -12.0, 31.0])
    lab_d50 = adapt_lab(lab_d65, D65_WHITE_XYZ, D50_WHITE_XYZ)
    assert not np.allclose(lab_d50, lab_d65, atol=1e-3)  # adaptation did something
    back = adapt_lab(lab_d50, D50_WHITE_XYZ, D65_WHITE_XYZ)
    assert np.allclose(back, lab_d65, atol=1e-9)


def test_adapt_lab_preserves_neutral_white():
    """A perfect white under D50 is still a perfect white under D65 — that is
    what chromatic adaptation means."""
    white_d50 = np.array([100.0, 0.0, 0.0])
    adapted = adapt_lab(white_d50, D50_WHITE_XYZ, D65_WHITE_XYZ)
    assert adapted == pytest.approx([100.0, 0.0, 0.0], abs=1e-9)


# ---------------------------------------------------------------------------
# 3. delta_e integration, against the confirmed chart_patches schema
# ---------------------------------------------------------------------------

# A synthetic 2x3 "chart": six patches laid out in a grid, each a flat block
# of linear RGB. Rows/columns are exact fractions so the normalized regions
# land on pixel boundaries at any frame size.
SYNTHETIC_CHART_COLORS = {
    "patch_00": (0.80, 0.20, 0.15),
    "patch_01": (0.20, 0.60, 0.25),
    "patch_02": (0.10, 0.25, 0.70),
    "patch_10": (0.90, 0.90, 0.90),
    "patch_11": (0.18, 0.18, 0.18),
    "patch_12": (0.05, 0.05, 0.05),
}
CHART_ROWS, CHART_COLUMNS = 2, 3


def _synthetic_chart_frame(size=64, colors=None):
    """A Frame holding the synthetic chart, tiled across the whole image."""
    colors = colors or SYNTHETIC_CHART_COLORS
    image = np.zeros((size, size, 3), dtype=np.float32)
    for name, rgb in colors.items():
        row, column = int(name[-2]), int(name[-1])
        y0 = round(size * row / CHART_ROWS)
        y1 = round(size * (row + 1) / CHART_ROWS)
        x0 = round(size * column / CHART_COLUMNS)
        x1 = round(size * (column + 1) / CHART_COLUMNS)
        image[y0:y1, x0:x1] = rgb
    return Frame(image=image, metadata={"transfer_function": "raw_linear"})


def _synthetic_chart_patches(colors=None, illuminant="D65", inset=0.02):
    """chart_patches whose reference Lab is exactly the synthetic colors.

    Regions are inset slightly from each patch's edges, the way real chart
    sampling avoids patch borders and bevels.
    """
    colors = colors or SYNTHETIC_CHART_COLORS
    patches = {}
    for name, rgb in colors.items():
        row, column = int(name[-2]), int(name[-1])
        lab = linear_rgb_to_lab(np.array(rgb, dtype=np.float64))
        if illuminant == "D50":
            lab = adapt_lab(lab, D65_WHITE_XYZ, D50_WHITE_XYZ)
        patches[name] = {
            "L": float(lab[0]),
            "a": float(lab[1]),
            "b": float(lab[2]),
            "region": {
                "x": column / CHART_COLUMNS + inset,
                "y": row / CHART_ROWS + inset,
                "w": 1.0 / CHART_COLUMNS - 2 * inset,
                "h": 1.0 / CHART_ROWS - 2 * inset,
            },
        }
    return {
        "chart": "synthetic-2x3",
        "reference_illuminant": illuminant,
        "patches": patches,
    }


def test_delta_e_is_zero_for_an_exact_match():
    frame = _synthetic_chart_frame()
    patches = _synthetic_chart_patches()
    # Non-zero floor comes only from the frame being float32 while the
    # reference Lab is float64.
    assert delta_e(frame, patches) == pytest.approx(0.0, abs=1e-3)


def test_delta_e_detects_a_color_cast():
    """A blue-green cast — the underwater failure mode this metric exists to
    measure — must produce a clearly non-zero score."""
    cast = {
        name: (r * 0.4, g * 0.9, b * 1.0)
        for name, (r, g, b) in SYNTHETIC_CHART_COLORS.items()
    }
    frame = _synthetic_chart_frame(colors=cast)
    assert delta_e(frame, _synthetic_chart_patches()) > 5.0


def test_delta_e_grows_with_the_size_of_the_error():
    patches = _synthetic_chart_patches()
    scores = []
    for red_scale in (1.0, 0.9, 0.7, 0.4):
        shifted = {
            name: (r * red_scale, g, b)
            for name, (r, g, b) in SYNTHETIC_CHART_COLORS.items()
        }
        scores.append(delta_e(_synthetic_chart_frame(colors=shifted), patches))
    assert scores == sorted(scores)
    assert scores[0] < scores[-1]


def test_delta_e_equals_the_mean_of_per_patch_ciede2000():
    """The aggregate is a plain mean over patches — pinned so a future change
    to max/RMS is a deliberate decision and not a silent one."""
    cast = {
        name: (r * 0.5, g * 0.95, b)
        for name, (r, g, b) in SYNTHETIC_CHART_COLORS.items()
    }
    frame = _synthetic_chart_frame(colors=cast)
    patches = _synthetic_chart_patches()
    per_patch = [
        ciede2000(
            [patches["patches"][name]["L"], patches["patches"][name]["a"], patches["patches"][name]["b"]],
            linear_rgb_to_lab(np.array(cast[name], dtype=np.float64)),
        )
        for name in SYNTHETIC_CHART_COLORS
    ]
    assert delta_e(frame, patches) == pytest.approx(float(np.mean(per_patch)), abs=1e-3)


def test_delta_e_is_resolution_independent():
    """The point of normalized regions: one chart_refs entry works on a 4K
    master and a downscaled proxy of the same shot. Checked on a frame with a
    real cast, so the assertion compares meaningful scores rather than three
    different flavors of floating-point zero."""
    patches = _synthetic_chart_patches()
    cast = {
        name: (r * 0.45, g * 0.92, b)
        for name, (r, g, b) in SYNTHETIC_CHART_COLORS.items()
    }
    scores = [
        delta_e(_synthetic_chart_frame(size=size, colors=cast), patches)
        for size in (48, 96, 240)
    ]
    assert scores[0] > 5.0  # the cast is actually being measured
    for score in scores[1:]:
        assert score == pytest.approx(scores[0], rel=1e-4)


def test_delta_e_exact_match_is_negligible_at_every_resolution():
    """Companion to the above: the exact-match floor must stay at
    float32-rounding level regardless of how many pixels a region covers.
    Before patch means were accumulated in float64, this floor grew with
    frame size."""
    patches = _synthetic_chart_patches()
    for size in (48, 96, 240, 480):
        assert delta_e(_synthetic_chart_frame(size=size), patches) < 1e-3


def test_delta_e_handles_non_square_frames():
    patches = _synthetic_chart_patches()
    image = np.zeros((60, 120, 3), dtype=np.float32)
    for name, rgb in SYNTHETIC_CHART_COLORS.items():
        row, column = int(name[-2]), int(name[-1])
        image[
            round(60 * row / CHART_ROWS) : round(60 * (row + 1) / CHART_ROWS),
            round(120 * column / CHART_COLUMNS) : round(120 * (column + 1) / CHART_COLUMNS),
        ] = rgb
    frame = Frame(image=image, metadata={})
    assert delta_e(frame, patches) == pytest.approx(0.0, abs=1e-3)


def test_delta_e_bradford_adapts_d50_references():
    """D50-referenced refs describing the same physical colors must score the
    same as their D65 equivalents — the adaptation cancels out."""
    frame = _synthetic_chart_frame()
    d65_score = delta_e(frame, _synthetic_chart_patches(illuminant="D65"))
    d50_score = delta_e(frame, _synthetic_chart_patches(illuminant="D50"))
    assert d50_score == pytest.approx(d65_score, abs=1e-3)


def test_delta_e_without_adaptation_would_be_wrong():
    """Guards the reason reference_illuminant is required: feeding D50 Lab
    values while claiming D65 produces a large bogus error. If this ever
    stops failing, the adaptation has been silently disabled."""
    frame = _synthetic_chart_frame()
    correct = delta_e(frame, _synthetic_chart_patches(illuminant="D50"))
    mislabelled = _synthetic_chart_patches(illuminant="D50")
    mislabelled["reference_illuminant"] = "D65"
    # Compared against the correctly-adapted score rather than an arbitrary
    # constant: the claim is "orders of magnitude worse", not "above 1.0".
    assert delta_e(frame, mislabelled) > 100 * max(correct, 1e-6)


def test_delta_e_samples_only_the_declared_region():
    """Corrupting pixels outside every patch region must not move the score."""
    patches = _synthetic_chart_patches(inset=0.05)
    frame = _synthetic_chart_frame(size=120)
    clean_score = delta_e(frame, patches)
    corrupted = _synthetic_chart_frame(size=120)
    corrupted.image[0, :] = 1.0  # top edge, outside every inset region
    corrupted.image[:, 0] = 0.0  # left edge, likewise
    assert delta_e(corrupted, patches) == pytest.approx(clean_score, abs=1e-9)


def test_delta_e_averages_in_linear_light_not_lab():
    """A patch region spanning two very different luminances must average the
    linear values, then convert once. Averaging in Lab would give a
    noticeably different (and wrong) answer."""
    image = np.zeros((10, 10, 3), dtype=np.float64)
    image[:5, :] = 0.9
    image[5:, :] = 0.1
    frame = Frame(image=image, metadata={})
    expected_lab = linear_rgb_to_lab(np.array([0.5, 0.5, 0.5]))
    patches = {
        "reference_illuminant": "D65",
        "patches": {
            "split": {
                "L": float(expected_lab[0]),
                "a": float(expected_lab[1]),
                "b": float(expected_lab[2]),
                "region": {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0},
            }
        },
    }
    assert delta_e(frame, patches) == pytest.approx(0.0, abs=1e-9)

    lab_mean = (linear_rgb_to_lab(np.full(3, 0.9)) + linear_rgb_to_lab(np.full(3, 0.1))) / 2
    assert not np.allclose(lab_mean, expected_lab, atol=1.0)


def test_delta_e_tolerates_out_of_range_linear_values():
    """gray_world output can exceed 1.0 and go below 0.0; the metric must
    return a finite number rather than NaN."""
    image = np.full((8, 8, 3), 1.4, dtype=np.float32)
    image[:4] = -0.1
    frame = Frame(image=image, metadata={})
    patches = {
        "reference_illuminant": "D65",
        "patches": {
            "whole": {
                "L": 50.0,
                "a": 0.0,
                "b": 0.0,
                "region": {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0},
            }
        },
    }
    assert np.isfinite(delta_e(frame, patches))


# --- schema validation ------------------------------------------------------


def test_delta_e_requires_reference_illuminant():
    patches = _synthetic_chart_patches()
    del patches["reference_illuminant"]
    with pytest.raises(ValueError, match="reference_illuminant"):
        delta_e(_synthetic_chart_frame(), patches)


def test_delta_e_rejects_unknown_illuminant():
    patches = _synthetic_chart_patches()
    patches["reference_illuminant"] = "tungsten"
    with pytest.raises(ValueError, match="unknown reference_illuminant"):
        delta_e(_synthetic_chart_frame(), patches)


def test_delta_e_requires_a_patches_dict():
    with pytest.raises(ValueError, match="'patches'"):
        delta_e(_synthetic_chart_frame(), {"reference_illuminant": "D65"})


def test_delta_e_rejects_empty_patches():
    with pytest.raises(ValueError, match="empty"):
        delta_e(
            _synthetic_chart_frame(),
            {"reference_illuminant": "D65", "patches": {}},
        )


def test_delta_e_requires_a_region_per_patch():
    patches = _synthetic_chart_patches()
    del patches["patches"]["patch_00"]["region"]
    with pytest.raises(ValueError, match="region"):
        delta_e(_synthetic_chart_frame(), patches)


def test_delta_e_requires_lab_values_per_patch():
    patches = _synthetic_chart_patches()
    del patches["patches"]["patch_00"]["a"]
    with pytest.raises(ValueError, match="missing key 'a'"):
        delta_e(_synthetic_chart_frame(), patches)


def test_delta_e_rejects_pixel_coordinates_mistaken_for_normalized():
    """The most likely authoring mistake: pasting pixel coordinates into a
    normalized field. It must fail loudly, not sample the top-left corner."""
    patches = _synthetic_chart_patches()
    patches["patches"]["patch_00"]["region"] = {"x": 120, "y": 88, "w": 24, "h": 24}
    with pytest.raises(ValueError, match="normalized"):
        delta_e(_synthetic_chart_frame(), patches)


def test_delta_e_rejects_non_positive_region_size():
    patches = _synthetic_chart_patches()
    patches["patches"]["patch_00"]["region"] = {"x": 0.1, "y": 0.1, "w": 0.0, "h": 0.2}
    with pytest.raises(ValueError, match="non-positive"):
        delta_e(_synthetic_chart_frame(), patches)


def test_delta_e_accepts_a_region_flush_with_the_frame_edge():
    patches = _synthetic_chart_patches(inset=0.0)
    assert delta_e(_synthetic_chart_frame(size=120), patches) == pytest.approx(0.0, abs=1e-3)


def test_delta_e_handles_a_sub_pixel_region():
    """A tiny region must still sample at least one pixel rather than
    averaging an empty slice into a NaN."""
    patches = {
        "reference_illuminant": "D65",
        "patches": {
            "tiny": {
                "L": 50.0,
                "a": 0.0,
                "b": 0.0,
                "region": {"x": 0.5, "y": 0.5, "w": 1e-6, "h": 1e-6},
            }
        },
    }
    assert np.isfinite(delta_e(_synthetic_chart_frame(), patches))


def test_delta_e_rejects_a_non_rgb_frame():
    frame = Frame(image=np.zeros((8, 8), dtype=np.float32), metadata={})
    with pytest.raises(ValueError, match=r"\(H, W, 3\)"):
        delta_e(frame, _synthetic_chart_patches())


def test_delta_e_does_not_mutate_the_frame_or_the_schema():
    frame = _synthetic_chart_frame()
    patches = _synthetic_chart_patches()
    image_before = frame.image.copy()
    import copy

    patches_before = copy.deepcopy(patches)
    delta_e(frame, patches)
    assert np.array_equal(frame.image, image_before)
    assert patches == patches_before
