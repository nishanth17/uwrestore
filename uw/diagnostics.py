"""Cheap, deterministic signal-recoverability diagnostics (Week 2 Phase 2C/2D).

These answer three narrow questions, no more:

  - is a source channel already at/near the representable floor or ceiling?
  - how large a gain did a global correction stage apply to that channel?
  - did a correction push meaningful content outside the normal [0, 1] range?

They are NOT sensor noise or SNR estimation. Whole-image variance confounds
texture with noise, and a defensible noise model needs controlled/flat
regions this project does not have yet (see PLAN.md's "signal
recoverability" axis and CLAUDE.md's Week 2 Phase 2C/2D non-goals). Nothing
in this module is labeled SNR or noise variance, and nothing here should be.

`near_floor_fraction` describes the ORIGINAL input signal. A correction can
move values away from zero without recovering any information that was
clipped, quantized away, or buried below useful signal at capture time — see
`correction_gain` and the caller-side convention of always reporting a
stage's original near-floor fraction beside its gain, never letting the
corrected distribution overwrite that evidence (uw/cli.py's report layout).
"""

from dataclasses import asdict, dataclass

import numpy as np

from uw.metrics import ILLUM_FLOOR_LINEAR
from uw.types import Frame

# One project-wide near-floor threshold, reused rather than reinvented: it is
# exactly uw.metrics.ILLUM_FLOOR_LINEAR, Phase 2B's own predeclared floor
# (linear 0.0025 == sRGB code 8/255, where one 8-bit code is a ~12% change —
# see uw/metrics.py's "-- illumination model --" comment block). Using the
# same constant, not a second number that happens to be close, is the point:
# "one project-wide threshold," not a per-module rediscovery of one.
NEAR_FLOOR_THRESHOLD = ILLUM_FLOOR_LINEAR

# The upper bound of this project's [0, 1] linear-light representation.
# Deliberately exact 1.0, not a "near" band like the floor: for an
# 8-bit-quantized source (profile "srgb" or "protune"), code 255 maps through
# srgb_to_linear to EXACTLY 1.0 in floating point (pow(1.0, x) == 1.0), so
# ">= 1.0" precisely identifies pixels sitting at the representation's
# ceiling — no fuzz threshold is needed or wanted.
#
# NAMING/INTERPRETATION, deliberately narrow: this measures the DECODED
# REPRESENTATION's ceiling, which is NOT the same claim as "the sensor
# clipped". Codec range conversion (limited->full), grading applied before
# ingest, and quantisation can all land a value at the ceiling with no
# sensor clipping involved; conversely a "raw_linear" array was never
# quantized through an 8-bit codec by this pipeline at all. Hitting the
# ceiling is necessary but not sufficient evidence of source clipping, and
# the CLI report says so rather than asserting the stronger conclusion.
SATURATION_THRESHOLD = 1.0

# Metadata keys under which each implemented global-gain stage records its
# per-channel (R, G, B) gain. CLAHE has no entry: it is a local/perceptual
# stage with no single global per-channel multiplier to report.
GAIN_METADATA_KEYS = {
    "gray_world": "gray_world_channel_scale",
    "white_patch": "white_patch_channel_gain",
}

_CHANNELS = ("r", "g", "b")


def out_of_range_fraction(image: np.ndarray) -> float:
    """Fraction of values outside [0, 1], the project's post-correction range
    diagnostic. Shared so gray_world/white_patch/clahe/pipeline reporting all
    mean exactly the same thing by the same name.

    Non-finite values count as out of range. `(a < 0) | (a > 1)` alone is
    False for NaN (every NaN comparison is False), so a NaN-bearing image
    would report 0.0 — "no range violation" — for values that are not in
    the range at all. `clahe` deliberately propagates NaN from non-finite
    input, so this is reachable rather than theoretical. +/-Inf already
    counted through the comparisons; this makes NaN consistent with it.
    """
    a = np.asarray(image)
    return float(np.mean(~np.isfinite(a) | (a < 0.0) | (a > 1.0)))


@dataclass
class SignalDiagnostics:
    """Per-channel near-floor / saturation fractions for one Frame.

    `near_floor_fraction` and `saturation_fraction` are {"r", "g", "b"} ->
    float. Both describe the frame exactly as given — for the ORIGINAL
    input this is a source-signal diagnostic; computed on a corrected frame
    it is still well-defined, but see the module docstring before reading a
    lowered corrected-frame near-floor fraction as "recovered" red.
    """

    near_floor_fraction: dict
    saturation_fraction: dict
    near_floor_threshold: float
    saturation_threshold: float
    pixel_count: int
    transfer_function: str | None


def signal_diagnostics(frame: Frame) -> SignalDiagnostics:
    """Near-floor / saturation fractions, per RGB channel, for one Frame."""
    image = np.asarray(frame.image, dtype=np.float64)
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError(f"frame.image must be (H, W, 3), got {image.shape}")
    if image.size == 0:
        # A fraction over zero pixels is undefined, and numpy's answer is a
        # silent NaN (plus two RuntimeWarnings). A NaN that reaches the
        # report reads as a measured value, which is worse than refusing.
        raise ValueError(
            f"frame.image is empty (shape {image.shape}); a per-channel "
            f"fraction is undefined over zero pixels"
        )
    near_floor = {}
    saturation = {}
    for i, ch in enumerate(_CHANNELS):
        channel = image[..., i]
        near_floor[ch] = float(np.mean(channel <= NEAR_FLOOR_THRESHOLD))
        saturation[ch] = float(np.mean(channel >= SATURATION_THRESHOLD))
    return SignalDiagnostics(
        near_floor_fraction=near_floor,
        saturation_fraction=saturation,
        near_floor_threshold=NEAR_FLOOR_THRESHOLD,
        saturation_threshold=SATURATION_THRESHOLD,
        pixel_count=int(image.shape[0] * image.shape[1]),
        transfer_function=frame.metadata.get("transfer_function"),
    )


def aggregate_signal_diagnostics(frames) -> SignalDiagnostics:
    """Pool signal_diagnostics over a sequence of frames, weighted by pixel
    count rather than averaged per-frame fractions — the same lesson as
    uw.metrics.delta_e's patch averaging and evaluate_temporal's per-pair
    pooling: an unweighted average of fractions silently depends on how many
    pixels each frame happens to have."""
    frames = list(frames)
    if not frames:
        raise ValueError("empty sequence")
    floor_counts = {ch: 0.0 for ch in _CHANNELS}
    sat_counts = {ch: 0.0 for ch in _CHANNELS}
    total = 0
    for f in frames:
        d = signal_diagnostics(f)
        n = d.pixel_count
        total += n
        for ch in _CHANNELS:
            floor_counts[ch] += d.near_floor_fraction[ch] * n
            sat_counts[ch] += d.saturation_fraction[ch] * n
    return SignalDiagnostics(
        near_floor_fraction={ch: floor_counts[ch] / total for ch in _CHANNELS},
        saturation_fraction={ch: sat_counts[ch] / total for ch in _CHANNELS},
        near_floor_threshold=NEAR_FLOOR_THRESHOLD,
        saturation_threshold=SATURATION_THRESHOLD,
        pixel_count=total,
        transfer_function=frames[0].metadata.get("transfer_function"),
    )


def correction_gain(metadata: dict, stage: str):
    """The (R, G, B) global gain `stage` applied, or None if it has no
    single global per-channel gain to report (e.g. clahe)."""
    key = GAIN_METADATA_KEYS.get(stage)
    return metadata.get(key) if key else None


def diagnostics_as_dict(d: SignalDiagnostics) -> dict:
    return asdict(d)
