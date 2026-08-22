"""Evaluation metrics.

ΔE here is CIEDE2000 (CIE 2000 color-difference formula), computed against
chart-referenced ground truth. See `delta_e` for the `chart_patches` schema
and `ciede2000` for the formula itself.
"""

import numpy as np

from uw.colorspace import (
    WHITE_POINTS,
    D65_WHITE_XYZ,
    adapt_lab,
    linear_rgb_to_lab,
)
from uw.types import Frame, FrameSequence

# The working white point for all ΔE comparisons. Reference Lab values
# declared under a different illuminant are Bradford-adapted to this before
# being compared (see _reference_lab_d65).
WORKING_WHITE = "D65"


def ciede2000(lab1, lab2, k_l: float = 1.0, k_c: float = 1.0, k_h: float = 1.0):
    """CIEDE2000 color difference between two CIELAB colors.

    The standard CIE 2000 formula (CIE 142-2001), not an approximation and
    not CIE76/CIE94. Implemented following the step-by-step formulation in
    Sharma, Wu & Dalal (2005), "The CIEDE2000 Color-Difference Formula:
    Implementation Notes, Supplementary Test Data, and Mathematical
    Observations", which spells out the three cases that naive
    implementations get wrong:

      - the hue-difference branch when either chroma is zero,
      - the mean-hue branch across the 0/360 discontinuity,
      - using atan2 (not atan) so hue lands in the right quadrant.

    Both inputs are (..., 3) arrays of (L*, a*, b*) and must be referenced to
    the same white point — CIEDE2000 has no notion of illuminant, so
    comparing across white points silently measures the mismatch too.

    k_l / k_c / k_h are the parametric weighting factors; they default to 1,
    the reference viewing conditions, which is what the published test data
    assumes.

    Returns a float for a single pair, or an array of shape (...) matching
    the broadcast leading dimensions.
    """
    lab1 = np.asarray(lab1, dtype=np.float64)
    lab2 = np.asarray(lab2, dtype=np.float64)
    if lab1.shape[-1] != 3 or lab2.shape[-1] != 3:
        raise ValueError(
            f"lab1 and lab2 must have shape (..., 3), got {lab1.shape} and {lab2.shape}"
        )

    l1, a1, b1 = lab1[..., 0], lab1[..., 1], lab1[..., 2]
    l2, a2, b2 = lab2[..., 0], lab2[..., 1], lab2[..., 2]

    # Step 1: chroma, and the G factor that rescales a* to compensate for
    # CIELAB's poor handling of near-neutral blues.
    c1 = np.hypot(a1, b1)
    c2 = np.hypot(a2, b2)
    c_bar = (c1 + c2) / 2.0
    c_bar7 = c_bar**7
    g = 0.5 * (1.0 - np.sqrt(c_bar7 / (c_bar7 + 25.0**7)))

    a1p = (1.0 + g) * a1
    a2p = (1.0 + g) * a2
    c1p = np.hypot(a1p, b1)
    c2p = np.hypot(a2p, b2)

    # Hue angles in degrees, in [0, 360). atan2(0, 0) == 0 gives the
    # required h' = 0 when a' and b* are both zero.
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360.0
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360.0

    # Step 2: the differences.
    delta_l = l2 - l1
    delta_c = c2p - c1p

    chroma_product_is_zero = (c1p * c2p) == 0.0
    dh = h2p - h1p
    delta_h_deg = np.where(
        chroma_product_is_zero,
        0.0,
        np.where(
            np.abs(dh) <= 180.0,
            dh,
            np.where(dh > 180.0, dh - 360.0, dh + 360.0),
        ),
    )
    delta_h_upper = 2.0 * np.sqrt(c1p * c2p) * np.sin(np.radians(delta_h_deg) / 2.0)

    # Step 3: the weighting functions.
    l_bar_p = (l1 + l2) / 2.0
    c_bar_p = (c1p + c2p) / 2.0

    h_sum = h1p + h2p
    h_bar_p = np.where(
        chroma_product_is_zero,
        h_sum,
        np.where(
            np.abs(h1p - h2p) <= 180.0,
            h_sum / 2.0,
            np.where(h_sum < 360.0, (h_sum + 360.0) / 2.0, (h_sum - 360.0) / 2.0),
        ),
    )

    t = (
        1.0
        - 0.17 * np.cos(np.radians(h_bar_p - 30.0))
        + 0.24 * np.cos(np.radians(2.0 * h_bar_p))
        + 0.32 * np.cos(np.radians(3.0 * h_bar_p + 6.0))
        - 0.20 * np.cos(np.radians(4.0 * h_bar_p - 63.0))
    )

    delta_theta = 30.0 * np.exp(-(((h_bar_p - 275.0) / 25.0) ** 2))
    c_bar_p7 = c_bar_p**7
    r_c = 2.0 * np.sqrt(c_bar_p7 / (c_bar_p7 + 25.0**7))

    l_offset_sq = (l_bar_p - 50.0) ** 2
    s_l = 1.0 + (0.015 * l_offset_sq) / np.sqrt(20.0 + l_offset_sq)
    s_c = 1.0 + 0.045 * c_bar_p
    s_h = 1.0 + 0.015 * c_bar_p * t
    r_t = -np.sin(np.radians(2.0 * delta_theta)) * r_c

    term_l = delta_l / (k_l * s_l)
    term_c = delta_c / (k_c * s_c)
    term_h = delta_h_upper / (k_h * s_h)

    result = np.sqrt(
        term_l**2 + term_c**2 + term_h**2 + r_t * term_c * term_h
    )
    return float(result) if result.ndim == 0 else result


def _reference_lab_d65(patch_name: str, patch: dict, source_white_xyz) -> np.ndarray:
    """Pull a patch's reference Lab and bring it to the D65 working white."""
    for key in ("L", "a", "b"):
        if key not in patch:
            raise ValueError(f"chart patch {patch_name!r} is missing key {key!r}")
    lab = np.array([patch["L"], patch["a"], patch["b"]], dtype=np.float64)
    if np.array_equal(source_white_xyz, D65_WHITE_XYZ):
        return lab
    return adapt_lab(lab, source_white_xyz, D65_WHITE_XYZ)


def _resolve_region(patch_name: str, region, height: int, width: int):
    """Normalized region -> integer pixel slice bounds (y0, y1, x0, x1).

    Regions are normalized fractions of frame width/height so one chart_refs
    entry stays valid across a 4K master and a downscaled proxy of the same
    shot. Rounds to the nearest pixel and guarantees at least a 1x1 sample.
    """
    if not isinstance(region, dict):
        raise ValueError(
            f"chart patch {patch_name!r} region must be a dict with keys "
            f"x, y, w, h, got {type(region).__name__}"
        )
    for key in ("x", "y", "w", "h"):
        if key not in region:
            raise ValueError(f"chart patch {patch_name!r} region is missing key {key!r}")
    x, y, w, h = (float(region[k]) for k in ("x", "y", "w", "h"))

    if w <= 0.0 or h <= 0.0:
        raise ValueError(
            f"chart patch {patch_name!r} region has non-positive size (w={w}, h={h})"
        )
    # A tiny tolerance so a region measured as exactly flush with the right
    # or bottom edge is not rejected for floating-point reasons.
    tolerance = 1e-9
    if x < -tolerance or y < -tolerance or x + w > 1.0 + tolerance or y + h > 1.0 + tolerance:
        raise ValueError(
            f"chart patch {patch_name!r} region {region} is outside the "
            f"normalized [0, 1] frame; regions are fractions of frame size, "
            f"not pixel coordinates"
        )

    x0 = int(round(np.clip(x, 0.0, 1.0) * width))
    y0 = int(round(np.clip(y, 0.0, 1.0) * height))
    x1 = int(round(np.clip(x + w, 0.0, 1.0) * width))
    y1 = int(round(np.clip(y + h, 0.0, 1.0) * height))
    # A patch smaller than a pixel (or rounding to zero extent) still needs
    # to sample something rather than average an empty slice.
    x1 = min(max(x1, x0 + 1), width)
    y1 = min(max(y1, y0 + 1), height)
    x0 = min(x0, x1 - 1)
    y0 = min(y0, y1 - 1)
    return y0, y1, x0, x1


def delta_e(frame: Frame, chart_patches: dict) -> float:
    """Mean CIEDE2000 between a frame's chart patches and their references.

    `chart_patches` schema (see data/chart_refs.json)::

        {
          "chart": "x-rite-classic-24",        # optional, provenance only
          "reference_illuminant": "D65",       # REQUIRED: "D65" or "D50"
          "patches": {
            "<patch name>": {
              "L": 37.99, "a": 13.56, "b": 14.06,
              "region": {"x": 0.41, "y": 0.28, "w": 0.02, "h": 0.04}
            },
            ...
          }
        }

    `reference_illuminant` is required rather than assumed, because the
    published X-Rite ColorChecker tables are D50-referenced while this
    pipeline works in D65. Declaring D50 triggers a Bradford adaptation to
    D65 so the returned ΔE measures the pipeline's error and not a
    white-point mismatch the pipeline never made. An undeclared or unknown
    illuminant is an error, not a default.

    `region` is a normalized [0, 1] fraction of frame width/height with the
    origin at the top-left, matching the image array's own layout. Normalized
    rather than absolute pixels so one entry stays valid across a 4K master
    and a downscaled proxy of the same shot.

    How the observed color is measured:

      - The patch's pixels are averaged in LINEAR light and the single mean
        RGB is then converted to Lab. Averaging must happen in linear light
        (CLAUDE.md invariant 1); averaging in Lab, or in gamma-encoded space,
        would bias the result. This is also why the Frame is required to be
        linear on the way in — see uw/colorspace.py for the full conversion
        assumptions (sRGB/Rec.709 primaries, D65, exact CIE constants).
      - Linear RGB below 0 is clamped by the Lab conversion, since CIELAB is
        undefined for negative tristimulus values. Values above 1 are kept:
        gray_world deliberately does not clip, and an over-range patch should
        register as the error it is rather than be quietly pulled back into
        range.

    Returns the mean ΔE00 across all patches — one number, per the signature.
    Mean rather than max because a single blown patch (a specular hit on the
    chart, a particulate in front of it) should not dominate the score;
    per-patch inspection is a separate concern from this metric.
    """
    if not isinstance(chart_patches, dict):
        raise ValueError(
            f"chart_patches must be a dict, got {type(chart_patches).__name__}"
        )

    illuminant = chart_patches.get("reference_illuminant")
    if illuminant is None:
        raise ValueError(
            "chart_patches is missing required key 'reference_illuminant'; "
            f"declare the illuminant the reference Lab values are relative to "
            f"(one of {sorted(WHITE_POINTS)}) — it is never assumed, because "
            f"published ColorChecker data is D50 while this pipeline works in "
            f"{WORKING_WHITE}"
        )
    if illuminant not in WHITE_POINTS:
        raise ValueError(
            f"unknown reference_illuminant {illuminant!r}; supported: "
            f"{sorted(WHITE_POINTS)}"
        )
    source_white_xyz = WHITE_POINTS[illuminant]

    patches = chart_patches.get("patches")
    if not isinstance(patches, dict):
        raise ValueError(
            "chart_patches must contain a 'patches' dict mapping patch name "
            "to {L, a, b, region}"
        )
    if not patches:
        raise ValueError("chart_patches['patches'] is empty; nothing to measure")

    image = np.asarray(frame.image)
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError(f"frame.image must have shape (H, W, 3), got {image.shape}")
    height, width = image.shape[:2]

    differences = []
    for patch_name, patch in patches.items():
        if not isinstance(patch, dict):
            raise ValueError(
                f"chart patch {patch_name!r} must be a dict with keys "
                f"L, a, b, region, got {type(patch).__name__}"
            )
        if "region" not in patch:
            raise ValueError(
                f"chart patch {patch_name!r} is missing key 'region'; delta_e "
                f"samples the frame itself and needs to know where the patch is"
            )
        y0, y1, x0, x1 = _resolve_region(patch_name, patch["region"], height, width)
        # Accumulate in float64: frames are float32, and summing thousands
        # of float32 pixels in float32 makes the measured patch color depend
        # on how many pixels the region happens to cover — i.e. on frame
        # resolution. A metric should not drift with proxy size.
        observed_linear_rgb = image[y0:y1, x0:x1].reshape(-1, 3).mean(
            axis=0, dtype=np.float64
        )
        observed_lab = linear_rgb_to_lab(observed_linear_rgb)
        reference_lab = _reference_lab_d65(patch_name, patch, source_white_xyz)
        differences.append(ciede2000(reference_lab, observed_lab))

    return float(np.mean(differences))


def temporal_stability(frames: FrameSequence) -> float:
    """Placeholder proxy for temporal stability. NOT the final video-quality
    metric — this only tracks how much per-frame mean RGB wobbles across a
    sequence, which says nothing about spatial flicker, structural
    consistency, or perceptual quality. Real temporal metrics are future
    work (see PLAN.md Week 2 / Week 8).

    Computed as the variance (averaged across R/G/B) of each frame's mean
    RGB value across the sequence. A single-frame FrameSequence (a photo)
    has no temporal variation by definition and returns 0.0.
    """
    means = [np.asarray(frame.image).reshape(-1, 3).mean(axis=0) for frame in frames]
    if len(means) < 2:
        return 0.0
    means = np.stack(means, axis=0)
    per_channel_variance = means.var(axis=0)
    return float(per_channel_variance.mean())
