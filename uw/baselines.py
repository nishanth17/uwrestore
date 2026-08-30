"""Baseline correction methods.

Week 1: gray-world. Week 2 Phase 2C/2D: white-patch and CLAHE.

Correction stages operate on linear-light RGB and are pure functions of a
Frame (CLAUDE.md invariant 3): they never mutate their input and never hold
hidden state. Every stage returns diagnostics that make its own effect on
the signal visible rather than hidden behind a prettier image — see
uw/diagnostics.py for the shared out-of-range convention these stages use,
and CLAUDE.md's "preserve image truth" invariant.

None of these are underwater restoration. They are deliberately simple
controls: how far can one global-color assumption (gray-world, white-patch)
or one local-contrast operation (CLAHE) go before the physics-based stages
of later weeks are needed at all.
"""

import cv2
import numpy as np

from uw.colorspace import lstar_to_y, y_to_lstar
from uw.diagnostics import NEAR_FLOOR_THRESHOLD, out_of_range_fraction
from uw.metrics import linear_luminance
from uw.types import Frame

# Top-percentile threshold for the white-patch bright-region estimator: the
# brightest ~1% of pixels by linear luminance. Fixed and deterministic,
# frozen before any real clip was inspected (CLAUDE.md Phase 2C brief:
# "choose one simple fixed rule, document it, and freeze it before
# inspecting real-clip results"). 1% is large enough that no single hot
# pixel, bubble glint or specular highlight can dominate the region (see
# test_white_patch_isolated_hot_pixel_does_not_dominate), while small enough
# to track a genuine bright surface rather than the whole frame.
WHITE_PATCH_TOP_PERCENTILE = 99.0

# Well-posedness floor on the bright region, NOT a tuned parameter: on a
# small frame, 1% of the pixels can round down to a SINGLE pixel, at which
# point "median over the bright region" silently degenerates into exactly
# the single-brightest-pixel rule the Phase 2C brief forbids ("do not
# blindly use the single brightest pixel... a single maximum can be
# dominated by noise, hot pixels, specular highlights, bubbles, clipped
# dive lights"). Measured before this guard existed: on a 10x10 frame one
# pathological hot pixel drove the derived gain to 5e7.
#
# 9 is derived from the estimator's own breakdown requirement, not from any
# clip: a median rejects up to floor((n-1)/2) outliers, so n = 9 tolerates 4
# (a ~44% breakdown point) and is the smallest round size that keeps the
# median meaningfully robust rather than nominal. It binds only on frames
# below ~900 px; at 960x540 (the metric grid) 1% is 5184 px and at 1080p it
# is 20736 px, so this changes nothing on any real footage — verified
# bit-identical gains on all five frozen clips.
WHITE_PATCH_MIN_BRIGHT_PIXELS = 9

# Denominator floor for the white-patch gain, purely for zero-safety. Not a
# gain cap: an extreme gain is left visible (via out_of_range_fraction),
# matching gray_world's existing "make range violations visible, don't hide
# them" convention rather than clamping the correction itself.
_WHITE_PATCH_GAIN_EPS = 1e-6


def _require_float_image(frame: Frame, stage: str) -> np.ndarray:
    """Return `frame.image`, refusing a non-floating dtype loudly.

    `Frame` documents "image is floating point" as an invariant that must
    hold everywhere a Frame is constructed, and `uw.io.load` always produces
    float32 — but nothing enforced it, and the failure mode was silent data
    destruction rather than an error. Measured: a uint8 Frame through
    `clahe` returned an **all-zero image** with no exception and no warning
    (the stage computes in float, then `astype(image.dtype)` truncates
    fractional linear values to 0), and through `gray_world` it silently
    truncated every corrected value back to an integer code.

    CLAUDE.md's ingest philosophy is to fail clearly rather than corrupt
    quietly, so this raises instead. No legitimate caller is affected —
    grepped: nothing in `uw/` or `tests/` constructs a non-float Frame.
    """
    image = frame.image
    if not np.issubdtype(image.dtype, np.floating):
        raise TypeError(
            f"{stage} requires a floating-point linear-light Frame, got dtype "
            f"{image.dtype}. Frame's documented invariant is float RGB in [0, 1]; "
            f"an integer image would be silently truncated to zeros by this "
            f"stage. Load through uw.io.load (which linearizes to float32), or "
            f"convert explicitly before correcting."
        )
    return image


def gray_world(frame: Frame) -> Frame:
    """Scale R/G/B channel means toward neutral gray, in linear light.

    Returns a new Frame; does not mutate the input. Values may exceed
    [0, 1] after scaling — this is not clipped here, so downstream
    consumers (e.g. export) see the true, unclipped result and decide how
    to handle it, rather than clipping being silently baked in.
    """
    image = _require_float_image(frame, "gray_world")
    channel_means = image.reshape(-1, 3).mean(axis=0)
    overall_mean = channel_means.mean()

    # Avoid divide-by-zero for a degenerate (e.g. pure black) channel.
    scale = np.where(channel_means > 0, overall_mean / np.where(channel_means == 0, 1, channel_means), 1.0)

    corrected = image * scale.reshape(1, 1, 3)

    clipped_fraction = float(np.mean((corrected < 0) | (corrected > 1)))

    new_metadata = dict(frame.metadata)
    new_metadata["gray_world_channel_scale"] = scale.tolist()
    new_metadata["gray_world_out_of_range_fraction"] = clipped_fraction

    return Frame(image=corrected.astype(image.dtype), metadata=new_metadata)


def white_patch(frame: Frame) -> Frame:
    """Robust white-patch / global-illuminant baseline, in linear light.

    A stronger global-color assumption than gray_world's "the scene averages
    to gray": instead, assume the brightest surface in frame is close to a
    neutral reflector, estimate what color it actually came out as, and
    scale each channel so that estimate moves toward neutral.

    Bright-region estimator (fixed, documented, frozen before any real-clip
    result was inspected):
      1. select the brightest WHITE_PATCH_TOP_PERCENTILE of pixels by linear
         luminance (uw.metrics.linear_luminance — the project's one
         definition of luminance), but never fewer than
         WHITE_PATCH_MIN_BRIGHT_PIXELS, so the region is always large
         enough for a median to actually be robust,
      2. take the per-channel MEDIAN of R, G, B over that region.
    The percentile keeps this from being dominated by a semantic bright
    object (deliberately no chart/highlight/neutral-pixel detection); the
    median keeps it from being dominated by whatever single hot pixel,
    bubble glint or specular speck happens to fall inside that region.
    Neither the percentile nor the statistic is tuned per clip.

    Selection is by exact order statistic (the n-th largest luminance) with
    a `>=` comparison, so pixels tied at the threshold are all included —
    a large clipped/saturated region is kept whole rather than arbitrarily
    truncated at the percentile boundary.

    Gain: each channel is scaled so the bright-region reference moves toward
    the brightest of the three reference channels (a von-Kries-style
    max-white normalization) — gain_c = max(reference) / reference_c. At
    least one channel keeps gain 1; this is not physically-correct
    restoration, it is a baseline, and CLAUDE.md is explicit that a metric
    improvement or a prettier frame does not make it one.

    Never mutates the input. Values may exceed [0, 1] after scaling; this is
    not clipped here (see gray_world's docstring) — out_of_range_fraction is
    recorded instead, consistent with gray_world's own convention.
    """
    image = _require_float_image(frame, "white_patch")
    luminance = linear_luminance(image)

    n_pixels = luminance.size
    n_bright = int(np.ceil(n_pixels * (100.0 - WHITE_PATCH_TOP_PERCENTILE) / 100.0))
    # Never fewer than the robustness floor, and never more than the frame
    # has (a frame smaller than the floor simply uses all of it — there is
    # no honest way to be more robust than the data allows, and saying so
    # via bright_region_fraction == 1.0 beats pretending otherwise).
    n_bright = min(max(n_bright, WHITE_PATCH_MIN_BRIGHT_PIXELS), n_pixels)

    # Exact n-th-largest order statistic rather than an interpolated
    # percentile, so `n_bright` means what it says; `>=` then also admits
    # anything tied at that value.
    flat = luminance.reshape(-1)
    threshold = np.partition(flat, n_pixels - n_bright)[n_pixels - n_bright]
    bright_mask = luminance >= threshold

    bright_pixels = image[bright_mask].reshape(-1, 3).astype(np.float64)
    reference = np.median(bright_pixels, axis=0)

    target = float(reference.max())
    if target <= _WHITE_PATCH_GAIN_EPS:
        # The entire bright region is black, so there is no bright reference
        # to move toward neutral and no illuminant to estimate. Identity is
        # the honest answer. (Without this the formula returns gain 0, which
        # is harmless — such a frame is black everywhere by construction,
        # since this region holds its BRIGHTEST pixels — but records
        # misleading provenance: a reader seeing gain 0.0 would reasonably
        # conclude the stage zeroed the image.)
        gain = np.ones(3, dtype=np.float64)
    else:
        safe_reference = np.maximum(reference, _WHITE_PATCH_GAIN_EPS)
        gain = target / safe_reference

    corrected = image * gain.reshape(1, 1, 3)

    new_metadata = dict(frame.metadata)
    new_metadata["white_patch_channel_gain"] = gain.tolist()
    new_metadata["white_patch_reference_rgb"] = reference.tolist()
    new_metadata["white_patch_bright_region_fraction"] = float(np.mean(bright_mask))
    new_metadata["white_patch_top_percentile"] = WHITE_PATCH_TOP_PERCENTILE
    new_metadata["white_patch_out_of_range_fraction"] = out_of_range_fraction(corrected)

    return Frame(image=corrected.astype(image.dtype), metadata=new_metadata)


# ---------------------------------------------------------------------------
# CLAHE — local contrast enhancement, NOT color restoration
# ---------------------------------------------------------------------------
#
# One fixed baseline configuration (CLAUDE.md: "do not run a hyperparameter
# sweep... do not tune parameters per clip... this is a control"). Values are
# OpenCV's own commonly-used defaults, not tuned against this project's
# footage.
CLAHE_CLIP_LIMIT = 2.0
CLAHE_TILE_GRID_SIZE = (8, 8)

# The 16-bit domain CLAHE actually operates in (cv2.createCLAHE requires an
# integer single-channel image; 8-bit would flatten dark underwater
# gradients to ~single-digit code steps before any contrast operation runs).
_CLAHE_UINT16_MAX = 65535

# Near-black reconstruction floor: reuses the SAME threshold as the signal
# diagnostics' near-floor fraction (uw.diagnostics.NEAR_FLOOR_THRESHOLD ==
# uw.metrics.ILLUM_FLOOR_LINEAR), rather than inventing a second "near zero"
# number. Below it, luminance-ratio reconstruction (RGB' = RGB * Y'/Y) is not
# used at all — see clahe()'s near-black branch.
CLAHE_NEAR_BLACK_Y = NEAR_FLOOR_THRESHOLD


def clahe(frame: Frame) -> Frame:
    """Local-contrast baseline: CLAHE on perceptual lightness only.

    Never independently equalizes R, G, B (that creates artificial hue/
    saturation shifts and would confound "more contrast" with "different
    color" — CLAUDE.md Phase 2D brief). Instead:

        linear RGB -> linear luminance Y -> CIE L* -> CLAHE (uint16)
            -> L*' -> Y' -> RGB' = RGB * (Y'/Y), luminance-ratio reconstruction

    L* is computed from the REAL (possibly out-of-[0,1]) luminance and is
    never clamped in the returned diagnostics. It IS clamped to CLAHE's
    required [0, 100] domain for the temporary uint16 control signal only —
    that bounding never leaks into the returned Frame, and how much of the
    frame needed it is recorded (`clahe_control_bounded_fraction`), per
    CLAUDE.md's "do not silently rewrite historical diagnostics."

    Near-black policy (Y <= CLAHE_NEAR_BLACK_Y): luminance-ratio
    reconstruction divides by Y, so as Y -> 0 that ratio is arbitrarily
    sensitive to CLAHE's own output — not a correspondence error, just
    ill-conditioned division. Rather than compute an unbounded ratio and
    clip it afterward (which the brief explicitly rules out), those pixels
    take an entirely different, explicit branch: RGB' = RGB, unchanged.

    This is stricter than reusing CLAHE's own Y' for those pixels, and
    deliberately so: OpenCV's CLAHE (like plain histogram equalization) maps
    a genuinely FLAT tile to the maximum output value regardless of the
    input's brightness — verified directly (cv2.createCLAHE().apply() on a
    constant-zero uint16 tile returns 65535, not 0). A perfectly or nearly
    flat near-black region (open water at the edge of frame, a shadow, a
    letterboxed border) is exactly the case this near-black branch exists
    for, so trusting CLAHE's own Y' there would do the opposite of
    "preserve genuinely near-black pixels" — it would relight them toward
    white. Passing the original value through is numerically exact (no
    division, no dependence on CLAHE's degenerate behavior at all), can
    never be NaN/Inf, and leaves genuinely near-black content exactly as
    dark as it was.

    Returns floating linear-light RGB; no perceptual/integer intermediate
    leaks into the public Frame.
    """
    image = np.asarray(_require_float_image(frame, "clahe"), dtype=np.float64)
    y = linear_luminance(image)
    lstar = y_to_lstar(y)

    lstar_control = np.clip(lstar, 0.0, 100.0)
    control_bounded_fraction = float(np.mean(lstar_control != lstar))

    # nan_to_num applies to the TEMPORARY control signal only, never to the
    # returned image: casting a NaN to uint16 is undefined behaviour in
    # numpy (it warns and yields an arbitrary code), which would feed a
    # meaningless value into that tile's histogram. Zeroing it there makes
    # the cast well-defined; the NaN still propagates to the output through
    # the `image * scale` reconstruction below, so a non-finite input pixel
    # stays visibly non-finite rather than being silently repaired.
    # Measured: contamination is local either way — one NaN pixel changes
    # nothing outside its own tile neighbourhood.
    control = np.nan_to_num(lstar_control, nan=0.0, posinf=100.0, neginf=0.0)
    u16 = np.clip(np.round(control / 100.0 * _CLAHE_UINT16_MAX), 0, _CLAHE_UINT16_MAX)
    u16 = u16.astype(np.uint16)

    clahe_op = cv2.createCLAHE(clipLimit=CLAHE_CLIP_LIMIT, tileGridSize=CLAHE_TILE_GRID_SIZE)
    u16_out = clahe_op.apply(u16)

    lstar_prime = u16_out.astype(np.float64) / _CLAHE_UINT16_MAX * 100.0
    y_prime = lstar_to_y(lstar_prime)

    # Two disjoint out-of-domain branches, both PASSTHROUGH rather than
    # reconstruct-from-a-bounded-control:
    #
    #   near_black   Y <= CLAHE_NEAR_BLACK_Y — the Y'/Y ratio is
    #                ill-conditioned (see the docstring).
    #   above_white  L* > 100, i.e. Y > 1.0 — the control signal HAD to be
    #                clamped to reach CLAHE's bounded domain, so Y' for
    #                those pixels is derived from a value the source did
    #                not have. Reconstructing from it silently collapses
    #                every above-white pixel to exactly 1.0 (measured:
    #                a neutral Y = 2.0 frame came back 0.9999999, and every
    #                sample of a 0.01..2.0 gradient above 1.0 mapped to
    #                1.0). That is an implicit clip — the temporary bound
    #                leaking into the returned linear RGB, which §9/§21 of
    #                the brief forbid and which would also misreport a
    #                preceding stage's genuine out-of-range output as
    #                in-range. Passing those pixels through preserves the
    #                real value; `clahe_above_white_fraction` records how
    #                many there were.
    near_black = y <= CLAHE_NEAR_BLACK_Y
    above_white = lstar > 100.0
    passthrough = near_black | above_white

    scale = np.ones_like(y)
    np.divide(y_prime, y, out=scale, where=~passthrough)

    corrected = np.where(
        passthrough[..., None],
        image,
        image * scale[..., None],
    )

    new_metadata = dict(frame.metadata)
    new_metadata["clahe_clip_limit"] = CLAHE_CLIP_LIMIT
    new_metadata["clahe_tile_grid_size"] = list(CLAHE_TILE_GRID_SIZE)
    new_metadata["clahe_near_black_threshold"] = CLAHE_NEAR_BLACK_Y
    new_metadata["clahe_near_black_fraction"] = float(np.mean(near_black))
    new_metadata["clahe_above_white_fraction"] = float(np.mean(above_white))
    new_metadata["clahe_control_bounded_fraction"] = control_bounded_fraction
    new_metadata["clahe_out_of_range_fraction"] = out_of_range_fraction(corrected)

    return Frame(image=corrected.astype(frame.image.dtype), metadata=new_metadata)
