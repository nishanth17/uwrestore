"""Evaluation metrics.

Two independent families live here and are deliberately never combined into
one score:

* **Colour fidelity** — `delta_e`, chart-referenced CIEDE2000 (CIE 2000
  colour-difference formula). See `delta_e` for the `chart_patches` schema
  and `ciede2000` for the formula itself.
* **Temporal appearance stability** — the Week 2 Phase 2B motion-aware
  metrics: raw MC-Warp@k, the canonical illumination-aware MC-Warp@k, the
  uncompensated residual, the motion-reduction ratio, valid coverage and
  flow-aligned temporal ΔE00. See the section header further down.

This module contains no optical-flow model. It consumes correspondence
through the `uw.flow.OpticalFlowBackend` interface, which the caller
constructs — so importing `uw.metrics` never pulls in torch, and the metric
code cannot quietly acquire a preferred backend.
"""

from dataclasses import asdict, dataclass, field

import cv2
import numpy as np

from uw.colorspace import (
    LINEAR_SRGB_TO_XYZ_D65,
    WHITE_POINTS,
    D65_WHITE_XYZ,
    adapt_lab,
    linear_rgb_to_lab,
)
from uw.flow import forward_backward_consistency, warp_to_source
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
    """DEPRECATED placeholder, superseded by the Phase 2B temporal metrics.

    Week 1's stand-in: the variance (averaged across R/G/B) of each frame's
    mean RGB value across the sequence. It is not a temporal-stability metric
    in any meaningful sense — it is blind to spatial flicker, to structural
    consistency, and to anything that leaves the frame mean unchanged, and it
    cannot tell scene motion from processing instability because it never
    establishes correspondence at all.

    Replaced by `evaluate_temporal` (raw MC-Warp@k, illumination-aware
    MC-Warp@k, uncompensated residual, motion-reduction ratio, valid coverage
    and temporal ΔE00). `uw score` no longer reports this value.

    Retained, unchanged, for exactly one reason: PLAN.md's operating loop
    compares each session's numbers against the previous LOG.md entry, and
    the pre-Phase-2B entries logged this quantity. Deleting it would make
    those entries unreproducible. It is not used by any report and should not
    be used by new code.

    A single-frame FrameSequence (a photo) has no temporal variation by
    definition and returns 0.0.
    """
    means = [np.asarray(frame.image).reshape(-1, 3).mean(axis=0) for frame in frames]
    if len(means) < 2:
        return 0.0
    means = np.stack(means, axis=0)
    per_channel_variance = means.var(axis=0)
    return float(per_channel_variance.mean())


# ===========================================================================
# Week 2 Phase 2B — motion-aware temporal metrics
# ===========================================================================
#
# What this measures, in one sentence:
#
#   After accounting for legitimate scene/camera motion and simple
#   illumination/exposure variation ALREADY PRESENT IN THE SOURCE, did our
#   processing cause the same physical scene content to change unexpectedly
#   over time?
#
# Five numbers are reported per lag and never merged into one score:
#
#   raw MC-Warp@k          validity-masked motion-compensated photometric
#                          residual, linear light, L1. First-class evidence.
#   illum-aware MC-Warp@k  the canonical regression metric: the same residual
#                          after removing a global gain/bias transform fitted
#                          ONLY on the aligned ORIGINAL input frames.
#   uncompensated@k        the same residual with no geometric warping.
#   reduction ratio@k      uncompensated / raw. Descriptive normalisation:
#                          how much of the frame-to-frame change geometry
#                          explains. It does NOT replace either residual.
#   valid coverage@k       fraction of the frame the numbers describe. Part
#                          of the result, not metadata: a lower residual
#                          obtained by excluding harder pixels is not an
#                          improvement (PLAN.md; Phase 2A A5).
#
# ---------------------------------------------------------------------------
# The anti-gaming invariant
# ---------------------------------------------------------------------------
# Correspondence AND illumination parameters are estimated exclusively from
# the ORIGINAL input sequence. The corrected sequence is judged; it never
# defines the judge. Otherwise a restoration could introduce temporal flicker
# and then help the evaluator fit that flicker away.
#
#   original t  +  original t+k
#        -> flow (direct, t -> t+k)  -> validity mask
#        -> aligned original pair    -> fit (gain, bias), then FREEZE
#        -> apply the frozen transform to the warped CORRECTED t+k
#
# ---------------------------------------------------------------------------
# Direct correspondence only
# ---------------------------------------------------------------------------
# Every lag uses one direct inference t -> t+k (and one t+k -> t for the
# forward/backward mask). Chained adjacent flows are never composed: chaining
# accumulates interpolation error, flow error, occlusion error and resampling
# drift, none of which belong in a stability measurement.
# ---------------------------------------------------------------------------

# -- evaluation grid --------------------------------------------------------
# Phase 2A's common grid: long side 960, aspect preserved, never upscaled.
# For the frozen test set (1920x1080 and 1080x1920) this is exactly the
# 960x540 / 540x960 grid every Phase 2A number was measured on.
METRIC_EVAL_LONG_SIDE = 960

# -- illumination model -----------------------------------------------------
# Fit-domain guards. PREDECLARED from the 8-bit sRGB source encoding and from
# identifiability, NOT tuned against the frozen clips.
#
#   highlight: linear 0.95 encodes to sRGB ~0.979 == code value 250/255, so
#              at and above it the source is at or near its clipping point
#              and carries no usable illumination information.
#   floor:     linear 0.0025 encodes to sRGB 0.0323 == code value 8/255,
#              where one 8-bit code is a ~12 % change in value; a gain fitted
#              there measures quantisation, not light.
ILLUM_HIGHLIGHT_LINEAR = 0.95
ILLUM_FLOOR_LINEAR = 0.0025
# Identifiability, not quality: a*x + b cannot be separated into gain and
# bias unless x actually varies, and a handful of pixels cannot constrain
# two parameters against outliers.
# Together these two bound the gain's own uncertainty: sigma_a ~=
# sigma_noise / (sqrt(N) * spread_x). One 8-bit sRGB code near mid-grey is
# ~0.003 in linear light, so N = 4096 and a MAD-based spread of 0.005 give
# sigma_a ~= 1 %, and a real 960x540 frame (N ~ 5e5) does far better. Derived
# from the source encoding, not fitted to any clip.
ILLUM_MIN_FIT_PIXELS = 4096
ILLUM_MIN_LUMA_SPREAD = 0.005          # robust (MAD-based) spread of x
# Huber M-estimator: k = 1.345 * sigma is the published constant giving 95 %
# efficiency at the Gaussian while bounding the influence of outliers
# (bubbles, marine snow, specular hits, a fish crossing the fit domain).
ILLUM_HUBER_K = 1.345
ILLUM_IRLS_ITERS = 10
# Least-trimmed-squares concentration: keep the best-fitting 70 % of the fit
# domain while locating the line, which gives a 30 % breakdown point against
# the HIGH-LEVERAGE contamination this footage produces (a bubble or a lit
# particle is an outlier in both frames of the pair at once, which a plain
# Huber M-estimator does not resist). See _fit_line_robust.
ILLUM_LTS_KEEP = 0.70
ILLUM_LTS_STEPS = 8
# A fitted gain outside this range is not "simple illumination variation";
# it is a failed fit, and the model falls back to identity and says so.
ILLUM_GAIN_SANITY = (0.25, 4.0)
# A fitted transform is kept only if it does not make the INPUT's own
# post-warp residual more than this much worse. See evaluate_temporal_pair.
ILLUM_ACCEPT_MARGIN = 0.01

# -- status bands -----------------------------------------------------------
# Predeclared, round, and stated before any real clip was scored. They label
# a result; they never delete one. The score and its coverage are always
# returned so a reader can disagree with the label.
#
#   coverage < 50 %: the value describes less than half the frame, so the
#   excluded region could plausibly dominate what it claims to summarise.
COVERAGE_LOW_FRACTION = 0.50
#   illumination-confounded: geometry AND the fitted global illumination
#   model TOGETHER explain less than 20 % of the input's frame-to-frame
#   change (uncompensated / illum-aware < 1.25). Phase 2A measured
#   1.14x/1.07x/1.02x on `lights` with geometry alone, so this is the
#   quantity that decides whether a bounded global model rescues that clip.
ILLUM_CONFOUNDED_REDUCTION = 1.25

# -- temporal delta-E -------------------------------------------------------
# Same floor as the illumination fit, for the same reason: below code value
# 8/255 a single 8-bit code moves CIEDE2000 by several units, so the metric
# would report quantisation noise as colour instability. Excluded pixels are
# counted and reported, never silently dropped.
DELTA_E_FLOOR_LINEAR = ILLUM_FLOOR_LINEAR

# -- alignment-robust companion --------------------------------------------
# One fixed low-pass, globally fixed, never per-clip tuned. Only reported
# when explicitly requested; it never replaces raw or illum-aware MC-Warp.
ALIGNMENT_ROBUST_SIGMA_PX = 1.0

# Rec.709 / sRGB luminance weights — the Y row of the project's own
# linear-RGB -> XYZ matrix, so there is exactly one definition of luminance
# in the codebase.
_LUMA_WEIGHTS = LINEAR_SRGB_TO_XYZ_D65[1].astype(np.float64)


def linear_luminance(image: np.ndarray) -> np.ndarray:
    """Linear-light RGB -> linear relative luminance Y (float64).

    Not clipped: gray-world and later stages deliberately produce values
    outside [0, 1], and a metric must see them as they are.
    """
    a = np.asarray(image, dtype=np.float64)
    if a.ndim != 3 or a.shape[2] != 3:
        raise ValueError(f"image must be (H, W, 3), got {a.shape}")
    return a @ _LUMA_WEIGHTS


# ---------------------------------------------------------------------------
# Evaluation grid
# ---------------------------------------------------------------------------


def metric_eval_size(src_h: int, src_w: int, long_side: int = METRIC_EVAL_LONG_SIDE):
    """(h, w) of the metric's evaluation grid for a source frame size.

    Aspect-preserving, orientation-preserving, and never upscaling. 1920x1080
    -> 960x540 and 1080x1920 -> 540x960, i.e. exactly Phase 2A's grid for the
    frozen test set, so Phase 2B numbers stay comparable to the lag study.
    """
    if src_h <= 0 or src_w <= 0:
        raise ValueError(f"invalid source size {(src_h, src_w)}")
    longest = max(src_h, src_w)
    if longest <= long_side:
        return int(src_h), int(src_w)
    scale = long_side / float(longest)
    return max(1, int(round(src_h * scale))), max(1, int(round(src_w * scale)))


def resize_linear(image: np.ndarray, out_h: int, out_w: int) -> np.ndarray:
    """Resample a linear-light image to (out_h, out_w) with INTER_AREA.

    Area-averaging is only physically meaningful on linear radiance, which is
    why this takes linear data and why the downscale happens before anything
    encodes an image for a model. One method, used identically for the input
    and the corrected sequence, so a pipeline comparison never turns into a
    resampling comparison.
    """
    image = np.asarray(image, dtype=np.float32)
    if image.shape[:2] == (out_h, out_w):
        return image.copy()
    out = cv2.resize(image, (out_w, out_h), interpolation=cv2.INTER_AREA)
    return out.reshape(out_h, out_w, -1).astype(np.float32)


def resize_sequence_linear(frames, out_h: int, out_w: int):
    """Resize every Frame in a sequence onto the evaluation grid."""
    resized = []
    for f in frames:
        meta = dict(f.metadata)
        meta["metric_resized_from"] = tuple(int(x) for x in f.image.shape[:2])
        resized.append(Frame(image=resize_linear(f.image, out_h, out_w), metadata=meta))
    return resized


# ---------------------------------------------------------------------------
# Warping and masked residuals
# ---------------------------------------------------------------------------


def warp_with_support(target_image: np.ndarray, flow: np.ndarray):
    """Warp `target_image` into the source grid and report where it is usable.

    Wraps uw.flow.warp_to_source (cv2.remap, bilinear, absolute float32
    source-coordinate maps derived from the normative (u, v) convention) and
    adds explicit non-finite handling: a NaN/Inf pixel is zeroed before
    resampling and its whole bilinear 2x2 support is marked unusable, rather
    than being allowed to poison its neighbours or be silently interpolated
    over.

    Returns (warped, ok). `ok` is False outside the target frame, where the
    flow was non-finite, wherever the resampling support was not finite, and
    wherever the warped value came out non-finite anyway. Validity comes from
    this explicit correspondence/support logic — never from whether a warped
    pixel happened to contain a plausible-looking value.
    """
    target_image = np.asarray(target_image, dtype=np.float32)
    is_rgb = target_image.ndim == 3
    finite = np.isfinite(target_image)
    if is_rgb:
        finite = finite.all(axis=2)
    clean = np.where(finite[..., None] if is_rgb else finite, target_image, 0.0)
    warped, inside = warp_to_source(clean.astype(np.float32), flow)
    support, _ = warp_to_source(finite.astype(np.float32), flow)
    warped_finite = np.isfinite(warped).all(axis=2) if is_rgb else np.isfinite(warped)
    ok = inside & (support >= 1.0 - 1e-6) & warped_finite
    return warped, ok


def _masked_l1_sum(a: np.ndarray, b: np.ndarray, mask: np.ndarray):
    """(sum of per-pixel channel-mean |a - b|, count) over `mask`.

    float64 throughout: summing hundreds of thousands of float32 values in
    float32 makes the answer depend on how many pixels the frame happens to
    have, i.e. on evaluation resolution. Same lesson as `delta_e`'s patch
    averaging. Non-finite differences are excluded and are not counted, so
    they cannot be laundered into the denominator.
    """
    if not mask.any():
        return 0.0, 0
    d = np.abs(np.asarray(a, dtype=np.float64)[mask] - np.asarray(b, dtype=np.float64)[mask])
    if d.ndim == 2:
        d = d.mean(axis=1)
    finite = np.isfinite(d)
    if not finite.any():
        return 0.0, 0
    return float(d[finite].sum()), int(finite.sum())


def _ratio(numerator, denominator):
    """numerator / denominator, or None when it is not defined."""
    if numerator is None or denominator is None:
        return None
    if not np.isfinite(numerator) or not np.isfinite(denominator) or denominator <= 0.0:
        return None
    return float(numerator / denominator)


def temporal_warp_error(
    reference: np.ndarray,
    target: np.ndarray,
    flow: np.ndarray,
    valid_mask: np.ndarray | None = None,
):
    """Raw MC-Warp: the motion-compensated photometric residual, one pair.

    Formula, stated exactly::

        warped = W(target, flow)                # cv2.remap, bilinear
        M      = valid_mask & warp_support      # see warp_with_support
        MC-Warp = ( 1/|M| ) * sum_{p in M} ( 1/3 ) * sum_c | warped(p)_c - reference(p)_c |

    * `reference` is frame t, `target` is frame t+k, and `flow` is the DIRECT
      t -> t+k field, so `warped` is "frame t+k as it would look if nothing
      had moved" and is directly comparable to frame t.
    * Both images must be LINEAR-LIGHT RGB. The sRGB view a flow model needs
      for its own input never reaches here.
    * L1, not L2/Charbonnier/SSIM/census/LPIPS. L1 because (a) it stays in
      the units of the image, so the number is readable as "mean linear-light
      difference per channel" and is directly comparable to Phase 2A's warp
      MAE; (b) it is far less dominated by the handful of pixels — bubbles,
      marine snow, a thin rope, an occlusion edge — that Phase 2A showed
      dominate an underwater residual; and (c) Charbonnier's only advantage
      over L1 is differentiability at zero, which a measurement does not
      need. Nothing here is clipped, and non-finite pixels are excluded
      rather than replaced.

    Returns (value, valid_fraction). `value` is None only when the mask is
    empty — a mathematically undefined result, which is a different thing
    from a poorly-supported one.
    """
    reference = np.asarray(reference)
    warped, ok = warp_with_support(target, flow)
    mask = ok & np.isfinite(reference).all(axis=2)
    if valid_mask is not None:
        mask = mask & np.asarray(valid_mask, dtype=bool)
    total = float(reference.shape[0] * reference.shape[1])
    s, n = _masked_l1_sum(reference, warped, mask)
    return (float(s / n) if n else None), (n / total if total else 0.0)


def alignment_robust_warp_error(
    reference: np.ndarray,
    target: np.ndarray,
    flow: np.ndarray,
    valid_mask: np.ndarray | None = None,
    sigma_px: float = ALIGNMENT_ROBUST_SIGMA_PX,
):
    """MC-Warp after one fixed low-pass on both images. SEPARATE diagnostic.

    Reported beside raw and illumination-aware MC-Warp, never instead of
    them. `sigma_px` is fixed globally and is never tuned per clip. Read it
    only as "how much of the residual survives a 1-pixel blur" — a blurred
    restoration scores better here too, which is exactly why it cannot be the
    canonical metric (see the blur case in tests/test_temporal.py).
    """
    reference = np.asarray(reference, dtype=np.float32)
    warped, ok = warp_with_support(target, flow)
    mask = ok & np.isfinite(reference).all(axis=2)
    if valid_mask is not None:
        mask = mask & np.asarray(valid_mask, dtype=bool)
    ref_lp = _gaussian_lowpass(reference, sigma_px)
    warp_lp = _gaussian_lowpass(warped, sigma_px)
    total = float(reference.shape[0] * reference.shape[1])
    s, n = _masked_l1_sum(ref_lp, warp_lp, mask)
    return (float(s / n) if n else None), (n / total if total else 0.0)


def _gaussian_lowpass(image: np.ndarray, sigma_px: float) -> np.ndarray:
    if sigma_px <= 0:
        return np.asarray(image, dtype=np.float32)
    ksize = int(2 * round(3.0 * sigma_px) + 1)
    return cv2.GaussianBlur(
        np.asarray(image, dtype=np.float32), (ksize, ksize), sigma_px,
        borderType=cv2.BORDER_REPLICATE,
    )


# ---------------------------------------------------------------------------
# Illumination model — global gain + bias, fitted on the ORIGINAL frames only
# ---------------------------------------------------------------------------


@dataclass
class IlluminationFit:
    """A frozen, input-derived illumination transform.

    model:      identifier of the functional form.
    gain, bias: the transform I_t ~= gain * W(I_t+k) + bias, applied
                identically to all three linear RGB channels.
    estimator:  how the parameters were estimated.
    fit_domain: what pixels were eligible.
    fit_pixels / fit_fraction: how many, and as a fraction of the valid mask.
    status:     "fitted", or "identity:<reason>" when the model declined to
                fit and fell back to the identity transform (gain 1, bias 0),
                which makes the illumination-aware residual equal the raw one.
    """

    model: str = "global_gain_bias_luminance"
    gain: float = 1.0
    bias: float = 0.0
    estimator: str = (
        f"robust MAD-ratio/median start -> LTS concentration "
        f"(keep {ILLUM_LTS_KEEP:.0%}, {ILLUM_LTS_STEPS} steps) -> Huber IRLS "
        f"(k={ILLUM_HUBER_K}, {ILLUM_IRLS_ITERS} iters, MAD scale)"
    )
    fit_domain: str = (
        f"FB-valid & warp-supported & {ILLUM_FLOOR_LINEAR} < Y < "
        f"{ILLUM_HIGHLIGHT_LINEAR} in BOTH aligned original frames"
    )
    fit_pixels: int = 0
    fit_fraction: float = 0.0
    status: str = "fitted"

    @property
    def is_identity(self) -> bool:
        return self.status != "fitted"


def _robust_line_init(y: np.ndarray, x: np.ndarray):
    """Starting point for the fit, from robust moments alone.

        a = MAD(y) / MAD(x)          b = median(y) - a * median(x)

    Median and MAD each have a 50 % breakdown point in their own variable, so
    unlike an ordinary least-squares start this one is not thrown across the
    plane by a cluster of contaminated pixels. It is only a start — it uses
    no information about which x goes with which y — but it is close enough
    for the concentration steps below to find the right subset.

    Returns None when either robust scale is degenerate.
    """
    mad_x = float(np.median(np.abs(x - np.median(x))))
    mad_y = float(np.median(np.abs(y - np.median(y))))
    if not np.isfinite(mad_x) or not np.isfinite(mad_y) or mad_x <= 0:
        return None
    a = mad_y / mad_x
    return a, float(np.median(y) - a * np.median(x))


def _weighted_line(y, x, w):
    """Weighted least-squares line y ~= a*x + b, or None if degenerate."""
    sw = float(w.sum())
    if not np.isfinite(sw) or sw <= 0:
        return None
    mx = float((w * x).sum() / sw)
    my = float((w * y).sum() / sw)
    dx = x - mx
    vxx = float((w * dx * dx).sum())
    if not np.isfinite(vxx) or vxx <= 0:
        return None
    a = float((w * dx * (y - my)).sum() / vxx)
    b = my - a * mx
    if not (np.isfinite(a) and np.isfinite(b)):
        return None
    return a, b


def _fit_line_robust(y: np.ndarray, x: np.ndarray):
    """Robust fit of y ~= a*x + b. Deterministic; no sampling, no RANSAC.

    Three stages, each answering a specific failure this footage produces:

    1. **Robust start** (`_robust_line_init`) — medians and MADs, so a
       contaminated minority cannot choose the starting point.
    2. **Concentration steps** (FAST-LTS C-steps, Rousseeuw & Van Driessen
       1999): repeatedly keep the ``ILLUM_LTS_KEEP`` fraction of pixels with
       the smallest absolute residual and refit least squares on them. This
       is the stage that actually matters here. A bubble, a rising bubble
       column, marine snow lit by a dive light or a specular glint is an
       outlier in BOTH frames of the pair at once, i.e. a HIGH-LEVERAGE
       outlier — and an M-estimator that only bounds the influence of large
       residuals (plain Huber IRLS) does not resist those: measured on a
       synthetic 15 % leverage cluster it converged to a gain of 0.04
       against a true 1.25. Trimming by residual rank does, with a breakdown
       point of 1 - ILLUM_LTS_KEEP.
    3. **Huber reweighting** on ALL pixels, from the trimmed solution and at
       a FIXED scale taken from it (an MM-estimator, Yohai 1987), to recover
       the efficiency that hard trimming costs and to remove the selection
       bias the trim introduces — without giving the breakdown point back.

    Returns (a, b), or None if the design is degenerate.
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    start = _robust_line_init(y, x)
    if start is None:
        return None
    a, b = start

    keep = max(2, int(round(ILLUM_LTS_KEEP * x.size)))
    for _ in range(ILLUM_LTS_STEPS):
        resid = np.abs(y - (a * x + b))
        if not np.isfinite(resid).all():
            return None
        if keep < x.size:
            cutoff = np.partition(resid, keep - 1)[keep - 1]
            subset = resid <= cutoff
        else:
            subset = np.ones_like(resid, dtype=bool)
        fitted = _weighted_line(y[subset], x[subset], np.ones(int(subset.sum())))
        if fitted is None:
            break
        if fitted == (a, b):
            break
        a, b = fitted

    # MM-style M-step: the scale is taken ONCE from the high-breakdown fit
    # and then held FIXED (Yohai 1987), which is what preserves the breakdown
    # point through the efficiency step. Re-estimating the scale each
    # iteration instead makes this stage run away in exactly the case the LTS
    # step just solved: the leverage cluster nudges the line, the residual
    # MAD grows, the larger scale readmits the cluster, and the fit walks off.
    # Measured on the 15 % synthetic leverage cluster, that loop carried an
    # exact 1.2500 gain out to 1.1603 over ten iterations.
    r0 = y - (a * x + b)
    scale = 1.4826 * float(np.median(np.abs(r0 - np.median(r0))))
    if np.isfinite(scale) and scale > 0:
        for _ in range(ILLUM_IRLS_ITERS):
            r = y - (a * x + b)
            u = np.abs(r) / (ILLUM_HUBER_K * scale)
            fitted = _weighted_line(
                y, x, np.where(u <= 1.0, 1.0, 1.0 / np.maximum(u, 1e-12)))
            if fitted is None:
                return None
            if fitted == (a, b):
                break
            a, b = fitted
    return float(a), float(b)


def fit_illumination(
    reference_rgb: np.ndarray,
    warped_target_rgb: np.ndarray,
    mask: np.ndarray,
) -> IlluminationFit:
    """Fit the canonical illumination transform on ALIGNED ORIGINAL frames.

    THIS FUNCTION MUST ONLY EVER BE CALLED WITH ORIGINAL INPUT FRAMES. The
    corrected/restored sequence is what the resulting transform is used to
    judge; letting it influence the fit would let a restoration flicker and
    then have the evaluator fit its own flicker away.

    Model: one scalar gain and one scalar bias on linear relative luminance,
    applied identically to R, G and B::

        Y_t  ~=  gain * Y_warped(t+k)  +  bias

    Chosen as the lowest-capacity form that can represent the legitimate
    variation actually present in this footage — camera auto-exposure steps,
    a global ambient-light change, a whole-scene brightening as the camera
    rises — and, just as importantly, the lowest-capacity form that is
    STRUCTURALLY INCAPABLE of absorbing the failure this metric exists to
    catch. A scalar applied to all channels cannot represent a red-only
    change at all, so corrected-only chroma flicker survives it by
    construction rather than by luck. Per-channel gains would have three
    times the freedom and no such guarantee.

    Fit domain (all predeclared, see the constants above): the supplied mask,
    minus highlights, minus near-black, in BOTH aligned original frames.
    Estimator: Huber IRLS. Declines to fit — falling back to the identity
    transform and saying so in `status` — when the domain is too small, when
    the luminance has too little spread for gain and bias to be separable, or
    when the fitted gain is outside a sanity range.
    """
    y_ref = linear_luminance(reference_rgb)
    y_tgt = linear_luminance(warped_target_rgb)
    valid_n = int(np.asarray(mask, dtype=bool).sum())

    domain = (
        np.asarray(mask, dtype=bool)
        & np.isfinite(y_ref) & np.isfinite(y_tgt)
        & (y_ref > ILLUM_FLOOR_LINEAR) & (y_ref < ILLUM_HIGHLIGHT_LINEAR)
        & (y_tgt > ILLUM_FLOOR_LINEAR) & (y_tgt < ILLUM_HIGHLIGHT_LINEAR)
    )
    n = int(domain.sum())
    frac = (n / valid_n) if valid_n else 0.0
    if n < ILLUM_MIN_FIT_PIXELS:
        return IlluminationFit(
            fit_pixels=n, fit_fraction=frac,
            status=f"identity:fit-domain-too-small({n}<{ILLUM_MIN_FIT_PIXELS})",
        )

    x = y_tgt[domain]
    y = y_ref[domain]
    spread = 1.4826 * float(np.median(np.abs(x - np.median(x))))
    if not np.isfinite(spread) or spread < ILLUM_MIN_LUMA_SPREAD:
        return IlluminationFit(
            fit_pixels=n, fit_fraction=frac,
            status=f"identity:luminance-spread-too-small({spread:.5f}<{ILLUM_MIN_LUMA_SPREAD})",
        )

    fitted = _fit_line_robust(y, x)
    if fitted is None:
        return IlluminationFit(fit_pixels=n, fit_fraction=frac,
                               status="identity:degenerate-fit")
    a, b = fitted
    lo, hi = ILLUM_GAIN_SANITY
    if not (lo <= a <= hi):
        return IlluminationFit(
            fit_pixels=n, fit_fraction=frac,
            status=f"identity:gain-out-of-range({a:.3f} not in [{lo}, {hi}])",
        )
    return IlluminationFit(gain=a, bias=b, fit_pixels=n, fit_fraction=frac,
                           status="fitted")


def apply_illumination(image: np.ndarray, fit: IlluminationFit) -> np.ndarray:
    """Apply a frozen illumination transform to linear RGB. No clipping.

    The same scalar gain and bias are applied to all three channels, so the
    transform is chroma-preserving up to the gain — it can brighten or darken
    the scene, and it cannot recolour it.

    The parameters are applied to the corrected sequence exactly as fitted on
    the original, with nothing re-estimated. If a restoration rescales the
    image substantially, its own gain also rescales what `bias` should have
    been, and the transform will under-remove the legitimate illumination
    change. That error can only ever INFLATE the corrected residual, never
    flatter it — the safe direction for a regression metric — and `bias` is
    reported so an unusually large one is visible.
    """
    a = np.asarray(image, dtype=np.float64)
    return (a * fit.gain + fit.bias).astype(np.float64)


# ---------------------------------------------------------------------------
# Flow-aligned temporal CIEDE2000
# ---------------------------------------------------------------------------


def _temporal_delta_e_sum(reference_rgb, warped_target_rgb, mask):
    """(sum of per-pixel ΔE00, count) over the near-black-excluded mask."""
    ref = np.asarray(reference_rgb, dtype=np.float64)
    tgt = np.asarray(warped_target_rgb, dtype=np.float64)
    m = np.asarray(mask, dtype=bool)

    y_ref = linear_luminance(ref)
    y_tgt = linear_luminance(tgt)
    m = (
        m
        & np.isfinite(ref).all(axis=2) & np.isfinite(tgt).all(axis=2)
        & (y_ref > DELTA_E_FLOOR_LINEAR) & (y_tgt > DELTA_E_FLOOR_LINEAR)
    )
    if not m.any():
        return 0.0, 0
    de = np.asarray(ciede2000(linear_rgb_to_lab(ref[m]), linear_rgb_to_lab(tgt[m])),
                    dtype=np.float64)
    finite = np.isfinite(de)
    if not finite.any():
        return 0.0, 0
    return float(de[finite].sum()), int(finite.sum())


def temporal_delta_e(
    reference_rgb: np.ndarray,
    warped_target_rgb: np.ndarray,
    mask: np.ndarray,
):
    """Mean flow-aligned CIEDE2000 between corresponding scene content.

    Answers a different question from MC-Warp: not "did the picture change"
    but "did the COLOUR of the same physical surface change" — red-channel
    pumping, white-balance oscillation, green/magenta drift, and later an
    unstable attenuation parameter, all of which can move ΔE a lot while
    barely moving an L1 photometric residual.

    `reference_rgb` is frame t and `warped_target_rgb` is frame t+k already
    aligned into t's grid by the SAME flow and masked by the SAME validity
    mask as MC-Warp, so the two metrics describe the same pixels.

    Uses the project's existing, validated path — `linear_rgb_to_lab` then
    `ciede2000` — with no second ΔE implementation anywhere.

    Near-black exclusion: pixels whose linear luminance is at or below
    DELTA_E_FLOOR_LINEAR (code value 8/255 in the 8-bit sRGB source) in
    EITHER frame are dropped, because there a single 8-bit code moves ΔE00 by
    several units and the metric would be reporting quantisation as colour
    instability. The resulting coverage is returned so the exclusion stays
    visible rather than silently shrinking the denominator.

    ILLUMINATION CAVEAT: this is at least as sensitive to legitimate lighting
    change as MC-Warp is, and it carries no illumination compensation. A high
    temporal ΔE on artificial-light footage is not by itself evidence of
    restoration instability — read it against the input baseline.

    Returns (mean ΔE00 or None, valid_fraction).
    """
    total = float(np.asarray(reference_rgb).shape[0] * np.asarray(reference_rgb).shape[1])
    s, n = _temporal_delta_e_sum(reference_rgb, warped_target_rgb, mask)
    if not n:
        return None, 0.0
    return float(s / n), float(n / total) if total else 0.0


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


@dataclass
class TemporalLagMetrics:
    """Everything measured at one lag, pooled over the evaluated pairs.

    Five quantities, deliberately not merged. There is no weighted overall
    temporal score anywhere in this module, by design.
    """

    lag: int
    n_pairs: int
    valid_fraction: float

    # The sequence under test.
    raw_warp: float | None = None
    illumination_aware_warp: float | None = None
    uncompensated: float | None = None
    motion_reduction_ratio: float | None = None
    temporal_delta_e: float | None = None
    alignment_robust_warp: float | None = None

    # The unprocessed input, on the SAME correspondence and the SAME mask.
    input_raw_warp: float | None = None
    input_illumination_aware_warp: float | None = None
    input_uncompensated: float | None = None
    input_motion_reduction_ratio: float | None = None
    input_temporal_delta_e: float | None = None
    input_alignment_robust_warp: float | None = None

    # The illumination transform, fitted on the ORIGINAL frames only.
    illumination: IlluminationFit = field(default_factory=IlluminationFit)
    illumination_explained_fraction: float | None = None
    illumination_confounded: bool = False

    delta_e_valid_fraction: float = 0.0
    status: str = "ok"
    pairs: list = field(default_factory=list)


@dataclass
class TemporalMetrics:
    """A temporal evaluation: one TemporalLagMetrics per lag, plus provenance."""

    lags: tuple = ()
    backend: str = ""
    backend_description: dict = field(default_factory=dict)
    source_size_hw: tuple = ()
    flow_inference_size_hw: tuple = ()
    metric_size_hw: tuple = ()
    anchors: tuple = ()
    correspondence_source: str = "original input sequence (never the corrected output)"
    illumination_fit_source: str = "aligned original input frames (never the corrected output)"

    def lag(self, k: int):
        for entry in self.lags:
            if entry.lag == k:
                return entry
        return None


# ---------------------------------------------------------------------------
# Pair evaluation — two inferences, everything derived from them
# ---------------------------------------------------------------------------


def _resolve_anchors(anchors, n_anchors: int, n_frames: int, max_lag: int):
    """Anchor indices, shared across every lag so a lag comparison varies only
    the lag (Phase 2A's convention). Explicit anchors are validated, not
    silently clamped — a clamped anchor would make a LOG.md frame range name
    footage it did not measure."""
    usable = n_frames - 1 - max_lag
    if usable < 0:
        raise ValueError(
            f"sequence of {n_frames} frames is too short for lag {max_lag}; "
            f"need at least {max_lag + 1}"
        )
    if anchors is not None:
        anchors = tuple(int(a) for a in anchors)
        for a in anchors:
            if a < 0 or a + max_lag >= n_frames:
                raise ValueError(
                    f"anchor {a} + max lag {max_lag} falls outside the "
                    f"{n_frames}-frame sequence"
                )
        return anchors
    if n_anchors <= 1 or usable == 0:
        return (0,) if usable == 0 else (usable // 2,)
    step = usable / float(n_anchors - 1)
    return tuple(sorted({int(round(i * step)) for i in range(n_anchors)}))


@dataclass
class PreparedPair:
    """Everything the evaluator derives from the ORIGINAL sequence for one
    (t, t+k) pair — correction-independent by construction.

    Built once per (anchor, lag) and reused across every correction
    configuration scored on that pair, which is what makes a multi-variant
    comparison a comparison of CORRECTIONS rather than of six independently
    realised evaluators. Nothing here is a function of any corrected output:
    the flow comes from `backend.estimate(original, ...)`, the mask from
    forward/backward consistency plus the original's own warp support, and
    the illumination fit (including its acceptance guard) from the aligned
    original pair alone.
    """

    index_t: int
    index_t1: int
    lag: int
    flow_forward: np.ndarray
    flow_backward: np.ndarray
    fb_valid: np.ndarray
    mask: np.ndarray
    original_t: np.ndarray
    original_t1: np.ndarray
    warped_original: np.ndarray
    illumination: "IlluminationFit"
    flow_inference_size_hw: tuple
    flow_runtime_s: list


def prepare_temporal_pair(original, backend, index_t: int, lag: int) -> PreparedPair:
    """Original-derived evaluation state for one (t, t+k) pair.

    Exactly two inferences, both on `original`. Separated out so that the
    state can be computed once and reused verbatim across correction
    configurations (Phase 2C/2D "evaluation reuse"), and so that it is
    structurally impossible for a corrected sequence to influence the mask
    or the illumination fit.
    """
    index_t1 = index_t + lag
    fwd = backend.estimate(original, index_t, index_t1)
    bwd = backend.estimate(original, index_t1, index_t)
    fb_valid, _fb_err = forward_backward_consistency(fwd.flow, bwd.flow)

    orig_t = np.asarray(original[index_t].image, dtype=np.float32)
    orig_t1 = np.asarray(original[index_t1].image, dtype=np.float32)
    warped_orig, ok_orig = warp_with_support(orig_t1, fwd.flow)

    mask = fb_valid & ok_orig & np.isfinite(orig_t).all(axis=2)

    fit = fit_illumination(orig_t, warped_orig, mask)
    # Acceptance rule, evaluated ONLY on the input: a transform fitted to
    # explain the input's own post-warp residual is kept only if it does not
    # make that residual more than ILLUM_ACCEPT_MARGIN worse. Rejection
    # falls back to identity, making the canonical metric equal the raw one
    # — strictly more conservative — and says so in `status`.
    raw_sum = _masked_l1_sum(orig_t, warped_orig, mask)
    if not fit.is_identity:
        illum_sum = _masked_l1_sum(orig_t, apply_illumination(warped_orig, fit), mask)
        if illum_sum[1] and raw_sum[1]:
            if (illum_sum[0] / illum_sum[1]) > (1.0 + ILLUM_ACCEPT_MARGIN) * (
                raw_sum[0] / raw_sum[1]
            ):
                fit = IlluminationFit(
                    fit_pixels=fit.fit_pixels, fit_fraction=fit.fit_fraction,
                    status="identity:no-input-residual-reduction",
                )

    return PreparedPair(
        index_t=int(index_t), index_t1=int(index_t1), lag=int(lag),
        flow_forward=fwd.flow, flow_backward=bwd.flow, fb_valid=fb_valid, mask=mask,
        original_t=orig_t, original_t1=orig_t1, warped_original=warped_orig,
        illumination=fit,
        flow_inference_size_hw=tuple(fwd.metadata.get("inference_size", ())),
        flow_runtime_s=[fwd.metadata.get("runtime_s"), bwd.metadata.get("runtime_s")],
    )


def evaluate_temporal_pair(
    original,
    corrected,
    backend,
    index_t: int,
    lag: int,
    alignment_robust: bool = False,
    on_arrays=None,
    prepared: "PreparedPair | None" = None,
):
    """Every temporal quantity for one (t, t+k) pair. Exactly two inferences.

    The forward and backward flow are each estimated ONCE, from the original
    input frames, and are then reused for the FB validity mask, the warped
    original, the warped corrected, the raw and illumination-aware residuals,
    the uncompensated residual, the reduction ratios, temporal ΔE and any
    visualisation the caller asks for through `on_arrays`. Nothing re-runs
    the model per metric.

    Memory is bounded to this pair: the flow fields and warped images are
    local, and the only thing that leaves is a dict of scalars (plus, if
    `on_arrays` is given, a borrowed view the caller must not retain).
    """
    if lag <= 0:
        raise ValueError(f"lag must be positive, got {lag}")
    index_t1 = index_t + lag
    if index_t < 0 or index_t1 >= len(original):
        raise IndexError(
            f"pair (t={index_t}, t+{lag}={index_t1}) is outside the "
            f"{len(original)}-frame sequence"
        )
    if len(corrected) != len(original):
        raise ValueError(
            f"corrected sequence has {len(corrected)} frames, original has "
            f"{len(original)} — they must be frame-aligned"
        )

    # --- correspondence + evaluation domain, from the ORIGINAL only ---------
    # `prepared` carries the whole original-derived state (flow, mask, warped
    # original, illumination fit). Passing one in is how several correction
    # configurations are scored on the BYTE-IDENTICAL evaluation domain
    # rather than on six independently recomputed ones.
    if prepared is None:
        prepared = prepare_temporal_pair(original, backend, index_t, lag)
    fwd_flow = prepared.flow_forward
    fb_valid = prepared.fb_valid
    orig_t = prepared.original_t
    orig_t1 = prepared.original_t1
    warped_orig = prepared.warped_original
    mask = prepared.mask

    corr_t = np.asarray(corrected[index_t].image, dtype=np.float32)
    corr_t1 = np.asarray(corrected[index_t1].image, dtype=np.float32)
    warped_corr, _ok_corr = warp_with_support(corr_t1, fwd_flow)

    h, w = mask.shape
    total = float(h * w)
    n_valid = int(mask.sum())

    # The corrected sequence does NOT get to shrink the evaluation domain.
    # It used to: the mask included `ok_corr` and the corrected frame's own
    # finiteness, so a correction emitting non-finite output silently
    # excluded exactly the pixels it had damaged AND changed the
    # "original-only" illumination fit through the mask it was fitted on
    # (measured: corrected-only NaN moved coverage 1.0000 -> 0.5333).
    # Non-finite corrected output is now REPORTED instead of masked away.
    corrected_finite = (
        np.isfinite(corr_t).all(axis=2) & np.isfinite(warped_corr).all(axis=2)
    )
    n_corr_nonfinite = int((mask & ~corrected_finite).sum())

    # --- illumination transform: fitted on the ORIGINALS, then frozen -------
    fit = prepared.illumination
    sums = {}
    sums["input_raw"] = _masked_l1_sum(orig_t, warped_orig, mask)
    illum_orig = apply_illumination(warped_orig, fit)
    sums["input_illum"] = _masked_l1_sum(orig_t, illum_orig, mask)

    illum_corr = apply_illumination(warped_corr, fit)

    # --- residuals ----------------------------------------------------------
    sums["raw"] = _masked_l1_sum(corr_t, warped_corr, mask)
    sums["illum"] = _masked_l1_sum(corr_t, illum_corr, mask)
    sums["uncomp"] = _masked_l1_sum(corr_t, corr_t1, mask)
    sums["input_uncomp"] = _masked_l1_sum(orig_t, orig_t1, mask)
    if alignment_robust:
        sigma = ALIGNMENT_ROBUST_SIGMA_PX
        sums["ar"] = _masked_l1_sum(
            _gaussian_lowpass(corr_t, sigma), _gaussian_lowpass(warped_corr, sigma), mask)
        sums["input_ar"] = _masked_l1_sum(
            _gaussian_lowpass(orig_t, sigma), _gaussian_lowpass(warped_orig, sigma), mask)

    de_corr = _temporal_delta_e_sum(corr_t, warped_corr, mask)
    de_orig = _temporal_delta_e_sum(orig_t, warped_orig, mask)

    def mean_of(key):
        s, n = sums.get(key, (0.0, 0))
        return (float(s / n) if n else None)

    result = {
        "index_t": int(index_t),
        "index_t1": int(index_t1),
        "lag": int(lag),
        "valid_pixels": n_valid,
        "valid_fraction": float(n_valid / total) if total else 0.0,
        "raw_warp": mean_of("raw"),
        "illumination_aware_warp": mean_of("illum"),
        "uncompensated": mean_of("uncomp"),
        "input_raw_warp": mean_of("input_raw"),
        "input_illumination_aware_warp": mean_of("input_illum"),
        "input_uncompensated": mean_of("input_uncomp"),
        "alignment_robust_warp": mean_of("ar") if alignment_robust else None,
        "input_alignment_robust_warp": mean_of("input_ar") if alignment_robust else None,
        "temporal_delta_e": (float(de_corr[0] / de_corr[1]) if de_corr[1] else None),
        "input_temporal_delta_e": (float(de_orig[0] / de_orig[1]) if de_orig[1] else None),
        "delta_e_valid_fraction": float(de_corr[1] / total) if total else 0.0,
        "illumination": asdict(fit),
        "corrected_nonfinite_pixels": n_corr_nonfinite,
        "corrected_nonfinite_fraction": (
            float(n_corr_nonfinite / n_valid) if n_valid else 0.0),
        "flow_inference_size_hw": tuple(prepared.flow_inference_size_hw),
        "flow_runtime_s": list(prepared.flow_runtime_s),
        "_sums": sums,
        "_delta_e_sums": {"corrected": de_corr, "input": de_orig},
    }
    result["motion_reduction_ratio"] = _ratio(result["uncompensated"], result["raw_warp"])
    result["input_motion_reduction_ratio"] = _ratio(
        result["input_uncompensated"], result["input_raw_warp"])

    if on_arrays is not None:
        on_arrays({
            "index_t": index_t, "index_t1": index_t1, "lag": lag,
            "flow_forward": fwd_flow, "flow_backward": prepared.flow_backward,
            "fb_valid": fb_valid, "mask": mask,
            "original_t": orig_t, "original_t1": orig_t1,
            "corrected_t": corr_t, "corrected_t1": corr_t1,
            "warped_original": warped_orig, "warped_corrected": warped_corr,
            "illum_warped_original": illum_orig, "illum_warped_corrected": illum_corr,
            "illumination": fit, "diagnostics": result,
        })

    # Nothing beyond this scope keeps the flow fields or the warped images.
    del warped_corr, illum_orig, illum_corr
    return result


def _aggregate_fit_status(fitted_n: int, n_pairs: int, decline_reasons) -> str:
    """One status line for a lag's illumination fits, keeping every reason.

    A per-pair reason is never dropped in aggregation: if some or all pairs
    declined to fit, the reader has to be able to see WHY without opening the
    per-pair records.
    """
    if fitted_n == n_pairs:
        return "fitted"
    reasons = "; ".join(sorted(set(decline_reasons)))
    if fitted_n == 0:
        return reasons or "identity:unknown"
    return f"fitted({fitted_n}/{n_pairs} pairs); {reasons}"


def _status_for(valid_fraction: float, confounded: bool, fit: IlluminationFit) -> str:
    parts = []
    if valid_fraction < COVERAGE_LOW_FRACTION:
        parts.append("low-coverage")
    if confounded:
        parts.append("illumination-confounded")
    if fit.is_identity:
        parts.append(f"illumination-{fit.status}")
    return "; ".join(parts) if parts else "ok"


def evaluate_temporal(
    original,
    corrected,
    backend,
    lags=(1, 4, 8),
    anchors=None,
    n_anchors: int = 3,
    eval_long_side: int | None = METRIC_EVAL_LONG_SIDE,
    alignment_robust: bool = False,
    on_arrays=None,
    prepared_pairs=None,
) -> TemporalMetrics:
    """Motion-aware temporal evaluation of `corrected` against its `original`.

    `original` is the unprocessed input sequence and is the ONLY thing that
    drives correspondence and the illumination fit. `corrected` is the output
    of whatever pipeline configuration is being tested, frame-aligned with
    `original`; it is measured and never used to define the measurement.

    Both sequences are put on the metric's evaluation grid with the same
    linear-light INTER_AREA downscale, so a pipeline comparison can never
    turn into a resampling comparison. The source, flow-inference and metric
    resolutions are all recorded.

    Anchors are shared across every lag (Phase 2A's convention), so a lag
    comparison varies only the lag. Each (anchor, lag) costs exactly two
    direct inferences; results are pooled over anchors by valid-pixel count.
    """
    original = list(original)
    corrected = list(corrected)
    if len(original) != len(corrected):
        raise ValueError(
            f"original ({len(original)}) and corrected ({len(corrected)}) "
            f"sequences must be frame-aligned"
        )
    if not original:
        raise ValueError("empty sequence")

    src_h, src_w = original[0].image.shape[:2]
    if eval_long_side is None:
        eh, ew = src_h, src_w
        eval_orig, eval_corr = original, corrected
    else:
        eh, ew = metric_eval_size(src_h, src_w, eval_long_side)
        eval_orig = resize_sequence_linear(original, eh, ew)
        eval_corr = resize_sequence_linear(corrected, eh, ew)

    lags = tuple(int(k) for k in lags)
    max_lag = max(lags)
    anchors = _resolve_anchors(anchors, n_anchors, len(eval_orig), max_lag)

    lag_results = []
    inference_size = ()
    for k in lags:
        pooled = {}
        de_pool = {"corrected": [0.0, 0], "input": [0.0, 0]}
        valid_pixels = 0
        total_pixels = 0
        gains, biases, fit_fracs, fit_px, fitted_n = [], [], [], 0, 0
        decline_reasons = []
        pairs = []
        for a in anchors:
            prepared = None if prepared_pairs is None else prepared_pairs.get((a, k))
            pair = evaluate_temporal_pair(
                eval_orig, eval_corr, backend, a, k,
                alignment_robust=alignment_robust, on_arrays=on_arrays,
                prepared=prepared,
            )
            for key, (s, n) in pair.pop("_sums").items():
                acc = pooled.setdefault(key, [0.0, 0])
                acc[0] += s
                acc[1] += n
            for key, (s, n) in pair.pop("_delta_e_sums").items():
                de_pool[key][0] += s
                de_pool[key][1] += n
            valid_pixels += pair["valid_pixels"]
            total_pixels += eh * ew
            fit = pair["illumination"]
            if fit["status"] == "fitted":
                gains.append(fit["gain"])
                biases.append(fit["bias"])
                fitted_n += 1
            else:
                # keep the reason, drop the pair-specific numbers in it
                decline_reasons.append(fit["status"].split("(")[0])
            fit_fracs.append(fit["fit_fraction"])
            fit_px += fit["fit_pixels"]
            if not inference_size:
                inference_size = tuple(pair.get("flow_inference_size_hw") or ())
            pairs.append(pair)

        def pooled_mean(key):
            s, n = pooled.get(key, (0.0, 0))
            return (float(s / n) if n else None)

        agg_fit = IlluminationFit(
            gain=float(np.mean(gains)) if gains else 1.0,
            bias=float(np.mean(biases)) if biases else 0.0,
            fit_pixels=fit_px,
            fit_fraction=float(np.mean(fit_fracs)) if fit_fracs else 0.0,
            status=_aggregate_fit_status(fitted_n, len(anchors), decline_reasons),
        )

        input_raw = pooled_mean("input_raw")
        input_illum = pooled_mean("input_illum")
        input_uncomp = pooled_mean("input_uncomp")
        # How much of the INPUT's post-warp residual the global illumination
        # model removed. This is the model's own report card, measured where
        # it was fitted, and is what decides `illumination_confounded`.
        explained = None
        if input_raw and input_illum is not None and input_raw > 0:
            explained = float(1.0 - input_illum / input_raw)
        combined_reduction = _ratio(input_uncomp, input_illum)
        confounded = (
            combined_reduction is not None
            and combined_reduction < ILLUM_CONFOUNDED_REDUCTION
        )
        valid_fraction = float(valid_pixels / total_pixels) if total_pixels else 0.0
        de_c = de_pool["corrected"]
        de_i = de_pool["input"]

        lag_results.append(TemporalLagMetrics(
            lag=k,
            n_pairs=len(anchors),
            valid_fraction=valid_fraction,
            raw_warp=pooled_mean("raw"),
            illumination_aware_warp=pooled_mean("illum"),
            uncompensated=pooled_mean("uncomp"),
            motion_reduction_ratio=_ratio(pooled_mean("uncomp"), pooled_mean("raw")),
            temporal_delta_e=(float(de_c[0] / de_c[1]) if de_c[1] else None),
            alignment_robust_warp=pooled_mean("ar") if alignment_robust else None,
            input_raw_warp=input_raw,
            input_illumination_aware_warp=input_illum,
            input_uncompensated=input_uncomp,
            input_motion_reduction_ratio=_ratio(input_uncomp, input_raw),
            input_temporal_delta_e=(float(de_i[0] / de_i[1]) if de_i[1] else None),
            input_alignment_robust_warp=pooled_mean("input_ar") if alignment_robust else None,
            illumination=agg_fit,
            illumination_explained_fraction=explained,
            illumination_confounded=bool(confounded),
            delta_e_valid_fraction=(float(de_c[1] / total_pixels) if total_pixels else 0.0),
            status=_status_for(valid_fraction, bool(confounded), agg_fit),
            pairs=pairs,
        ))

    try:
        description = backend.describe()
    except Exception:  # a stub/analytic backend need not describe itself
        description = {}

    return TemporalMetrics(
        lags=tuple(lag_results),
        backend=getattr(backend, "name", "unknown"),
        backend_description=description,
        source_size_hw=(int(src_h), int(src_w)),
        flow_inference_size_hw=inference_size,
        metric_size_hw=(int(eh), int(ew)),
        anchors=tuple(anchors),
    )


def prepare_temporal_pairs(original, backend, lags=(1, 4, 8), anchors=None,
                           n_anchors: int = 3):
    """Build the reusable original-derived state for every (anchor, lag).

    The whole point of Phase 2C/2D's "evaluation reuse across correction
    configurations": compute correspondence, the validity mask, the warped
    original and the illumination transform ONCE per pair, then score every
    correction configuration against that identical, frozen evaluation
    domain. Without it, six configurations rebuild six evaluators and any
    difference between them is only as trustworthy as the claim that the
    rebuilds were identical.

    Bounded exactly as before: one entry per (anchor, lag) — 9 for the
    default 3 anchors x 3 lags — each holding two flow fields, a mask and
    one warped frame, all CPU numpy. No GPU state is retained.
    """
    original = list(original)
    lags = tuple(int(k) for k in lags)
    anchors = _resolve_anchors(anchors, n_anchors, len(original), max(lags))
    return {
        (a, k): prepare_temporal_pair(original, backend, a, k)
        for k in lags for a in anchors
    }


# ---------------------------------------------------------------------------
# Cross-backend comparison — only ever on the intersection of the two masks
# ---------------------------------------------------------------------------
#
# Every per-backend number elsewhere in this module is computed on that
# backend's OWN forward/backward validity mask. That makes two backends'
# residuals and reduction ratios incomparable whenever their masks differ,
# because whichever one excludes more of the difficult region scores better on
# what remains — the artefact PLAN.md legislates against, and the rule has to
# apply to the backend we like as much as to the one we don't.
#
# Phase 2A measured exactly this trap twice: VideoFlow-MOF posts the HIGHEST
# reduction ratio on `murky_shark @8` while discarding 37 % of the frame, and
# WAFT's apparent advantage over SEA-RAFT evaporated on a common mask
# (SEA-RAFT equal-or-better in 14 of 15 clip-lag cells).
#
# This is the promoted form of experiments/week2a_flow/scripts/
# common_mask_compare.py. It answers a correspondence-quality question, so it
# takes only the ORIGINAL sequence — no corrected output is involved.

# A cell is called for a backend only if its reduction ratio beats the other's
# by more than this. Below it, the two are reported as a tie rather than
# ranked on noise.
BACKEND_TIE_MARGIN = 0.005


@dataclass
class BackendComparisonCell:
    """One clip-lag cell, both backends scored on the same pixels."""

    lag: int
    n_pairs: int
    backend_a: str
    backend_b: str
    common_fraction: float
    disputed_fraction: float
    own_fraction: dict = field(default_factory=dict)
    raw_warp: dict = field(default_factory=dict)
    motion_reduction_ratio: dict = field(default_factory=dict)
    uncompensated: float | None = None
    flow_epe_px: dict = field(default_factory=dict)
    verdict: str = "tie"


@dataclass
class BackendComparison:
    """A cross-check run. `tally` counts cells, and is not a score.

    There is deliberately no aggregate number here. The cells describe
    different footage and different displacement regimes; summing or
    averaging them would hide exactly the disagreements a cross-check exists
    to find.
    """

    cells: tuple = ()
    tally: dict = field(default_factory=dict)
    backend_a: str = ""
    backend_b: str = ""
    backend_a_description: dict = field(default_factory=dict)
    backend_b_description: dict = field(default_factory=dict)
    source_size_hw: tuple = ()
    metric_size_hw: tuple = ()
    anchors: tuple = ()
    scored_on: str = (
        "the intersection of both backends' FB-validity and warp-support masks"
    )


def compare_backends_common_mask(
    original,
    backend_a,
    backend_b,
    lags=(1, 4, 8),
    anchors=None,
    n_anchors: int = 3,
    eval_long_side: int | None = METRIC_EVAL_LONG_SIDE,
    tie_margin: float = BACKEND_TIE_MARGIN,
) -> BackendComparison:
    """Score two flow backends on the pixels they BOTH call valid.

    Anything that survives here is a difference in correspondence quality.
    Anything that shows up in the two backends' own per-backend numbers but
    vanishes here was a difference in masking policy, not in accuracy.

    Costs four inferences per (anchor, lag) — one forward and one backward
    per backend — and retains nothing beyond each cell's scalars.

    `original` is the unprocessed input sequence. No corrected output takes
    part: this measures correspondence, not a pipeline.
    """
    original = list(original)
    if not original:
        raise ValueError("empty sequence")
    src_h, src_w = original[0].image.shape[:2]
    if eval_long_side is None:
        eh, ew = src_h, src_w
        frames = original
    else:
        eh, ew = metric_eval_size(src_h, src_w, eval_long_side)
        frames = resize_sequence_linear(original, eh, ew)

    lags = tuple(int(k) for k in lags)
    anchors = _resolve_anchors(anchors, n_anchors, len(frames), max(lags))

    name_a = getattr(backend_a, "name", "a")
    name_b = getattr(backend_b, "name", "b")
    if name_a == name_b:
        raise ValueError(
            f"both backends report the name {name_a!r}; a comparison needs two "
            f"distinguishable backends"
        )

    cells, tally = [], {name_a: 0, name_b: 0, "tie": 0}
    for lag in lags:
        pooled = {name_a: [0.0, 0], name_b: [0.0, 0], "uncomp": [0.0, 0]}
        common_px = own_px = disputed_px = total_px = 0
        own = {name_a: 0, name_b: 0}
        epe_all, epe_disputed = [], []

        for anchor in anchors:
            target = anchor + lag
            fields, valid, ok, warped = {}, {}, {}, {}
            for name, backend in ((name_a, backend_a), (name_b, backend_b)):
                fwd = backend.estimate(frames, anchor, target)
                bwd = backend.estimate(frames, target, anchor)
                valid[name], _ = forward_backward_consistency(fwd.flow, bwd.flow)
                warped[name], ok[name] = warp_with_support(
                    frames[target].image, fwd.flow)
                fields[name] = fwd.flow
                del fwd, bwd

            reference = np.asarray(frames[anchor].image, dtype=np.float32)
            finite = np.isfinite(reference).all(axis=2)
            common = (
                valid[name_a] & ok[name_a] & valid[name_b] & ok[name_b] & finite
            )
            disputed = valid[name_a] ^ valid[name_b]

            for name in (name_a, name_b):
                s, n = _masked_l1_sum(reference, warped[name], common)
                pooled[name][0] += s
                pooled[name][1] += n
                own[name] += int((valid[name] & ok[name]).sum())
            s, n = _masked_l1_sum(reference, frames[target].image, common)
            pooled["uncomp"][0] += s
            pooled["uncomp"][1] += n

            epe = np.sqrt(((fields[name_a] - fields[name_b]) ** 2).sum(axis=2))
            epe_all.append(float(np.median(epe[np.isfinite(epe)]))
                           if np.isfinite(epe).any() else np.nan)
            if disputed.any():
                d = epe[disputed]
                d = d[np.isfinite(d)]
                if d.size:
                    epe_disputed.append(float(np.median(d)))

            common_px += int(common.sum())
            disputed_px += int(disputed.sum())
            total_px += eh * ew
            del fields, valid, ok, warped

        def mean_of(key):
            s, n = pooled[key]
            return (float(s / n) if n else None)

        uncomp = mean_of("uncomp")
        raw = {n: mean_of(n) for n in (name_a, name_b)}
        reduction = {n: _ratio(uncomp, raw[n]) for n in (name_a, name_b)}

        verdict = "tie"
        ra, rb = reduction[name_a], reduction[name_b]
        if ra is not None and rb is not None:
            if ra > rb * (1.0 + tie_margin):
                verdict = name_a
            elif rb > ra * (1.0 + tie_margin):
                verdict = name_b
        tally[verdict] += 1

        cells.append(BackendComparisonCell(
            lag=lag,
            n_pairs=len(anchors),
            backend_a=name_a,
            backend_b=name_b,
            common_fraction=float(common_px / total_px) if total_px else 0.0,
            disputed_fraction=float(disputed_px / total_px) if total_px else 0.0,
            own_fraction={n: float(own[n] / total_px) if total_px else 0.0
                          for n in (name_a, name_b)},
            raw_warp=raw,
            motion_reduction_ratio=reduction,
            uncompensated=uncomp,
            flow_epe_px={
                "median_overall": float(np.nanmean(epe_all)) if epe_all else None,
                "median_in_disputed_band": (float(np.mean(epe_disputed))
                                            if epe_disputed else None),
            },
            verdict=verdict,
        ))

    def describe(backend):
        try:
            return backend.describe()
        except Exception:
            return {}

    return BackendComparison(
        cells=tuple(cells),
        tally=tally,
        backend_a=name_a,
        backend_b=name_b,
        backend_a_description=describe(backend_a),
        backend_b_description=describe(backend_b),
        source_size_hw=(int(src_h), int(src_w)),
        metric_size_hw=(int(eh), int(ew)),
        anchors=tuple(anchors),
    )
