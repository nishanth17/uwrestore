"""Week 4A — the frozen S4 appearance perturbations.

EXPLORATORY. numpy + opencv + the project's own `uw.colorspace`.

THE POINT (`MONO_DEPTH_FREEZE.md` §5 S4):

    same underlying image geometry
    different appearance
    -> measure the geometry response

Every perturbation here is a PER-PIXEL INTENSITY operation. Nothing is warped,
resampled, rotated or cropped, so the scene geometry behind the image is
identical by construction and any change in a model's predicted geometry is a
response to appearance alone.

LINEAR LIGHT, because `CLAUDE.md` invariant 1 is not suspended for an
experiment. The frozen frames are 8-bit sRGB PNGs, so each perturbation decodes
through `uw.colorspace.srgb_to_linear`, operates on linear RGB, and re-encodes
with `linear_to_srgb`. A white-balance gain or a veiling light applied directly
to gamma-encoded values is not the physical operation it is named after.

Perturbed frames are WRITTEN TO DISK before inference. That costs an 8-bit
quantisation round trip, which is a real floor and is reported rather than
hidden — but it buys two things worth more: every model sees its own
preprocessing path exactly as it would in deployment, and every perturbed input
is a traceable artifact somebody can open and look at.

ONE CUE-CONFLICT CASE USES THE REFERENCE RANGE, and it is worth being explicit
about why that is not cheating. `cue_conflict_inverted_veil` builds a veiling
light whose strength runs OPPOSITE to the Week-3 reference depth, so the image
says "far" exactly where the geometry says "near". The reference is used to
BUILD THE STIMULUS; it never reaches the model, which still sees one ordinary
8-bit image and nothing else.
"""

from __future__ import annotations

import numpy as np

from uw.colorspace import linear_to_srgb, srgb_to_linear

#: A plausible underwater veiling-light colour in linear RGB: blue-green
#: dominant, red almost gone. Used by every veil/haze perturbation so they
#: differ in geometry-relevant structure, not in hue.
VEIL_RGB = np.array([0.06, 0.32, 0.42], dtype=np.float64)

#: Frozen perturbation set. Each entry is (name, kind, params, what it probes).
SPEC = [
    ("wb_warm", "channel_gain", {"gain": [1.25, 1.00, 0.80]},
     "white balance pushed warm; a pure per-channel gain in linear light"),
    ("wb_cool", "channel_gain", {"gain": [0.80, 1.00, 1.25]},
     "white balance pushed cool, the opposite gain"),
    ("channel_neutralize", "gray_world", {},
     "channel neutralisation: each linear channel scaled to a common mean, "
     "i.e. the colour cast removed the way the project's gray-world baseline does"),
    ("attenuation_red", "channel_gain", {"gain": [0.45, 0.90, 1.00]},
     "stronger Beer-Lambert-like red loss, uniform over the frame so it changes "
     "appearance WITHOUT encoding depth"),
    ("contrast_low", "contrast", {"factor": 0.70},
     "contrast reduced about the frame's linear mean"),
    ("contrast_high", "contrast", {"factor": 1.40},
     "contrast increased about the frame's linear mean"),
    ("brightness_down", "gain", {"factor": 0.60},
     "exposure down; a pure scalar on linear radiance"),
    ("brightness_up", "gain", {"factor": 1.60},
     "exposure up"),
    ("veil_uniform", "veil", {"t": 0.60},
     "uniform veiling light: x -> t*x + (1-t)*A. Haze-LIKE appearance with NO "
     "depth dependence, so the geometry cue is unchanged"),
    ("hotspot", "hotspot", {"strength": 0.55, "sigma_frac": 0.22},
     "artificial dive light: a bright radial falloff added in linear light, the "
     "illumination structure a torch or video light produces"),
    ("cue_conflict_inverted_veil", "veil_depth", {"t_near": 0.45, "t_far": 0.95},
     "CUE CONFLICT: veil strength runs OPPOSITE to the reference depth, so the "
     "image says 'far' where the geometry says 'near'. The reference builds the "
     "stimulus and never reaches the model"),
    ("veil_depth_consistent", "veil_depth", {"t_near": 0.95, "t_far": 0.45},
     "the CONTROL for the cue-conflict case: the same veil magnitude applied in "
     "the physically correct direction"),
]

NAMES = [s[0] for s in SPEC]


def _clip01(x):
    return np.clip(x, 0.0, 1.0)


def apply_perturbation(rgb_u8: np.ndarray, kind: str, params: dict,
                       ref_range: np.ndarray | None = None) -> np.ndarray:
    """One perturbation, applied in LINEAR light, returned as 8-bit sRGB RGB.

    `ref_range` is only consulted by the depth-structured veils, and only to
    shape the stimulus.
    """
    lin = srgb_to_linear(np.asarray(rgb_u8, dtype=np.float64) / 255.0)

    if kind == "channel_gain":
        out = lin * np.asarray(params["gain"], dtype=np.float64)[None, None, :]

    elif kind == "gray_world":
        means = lin.reshape(-1, 3).mean(axis=0)
        target = float(means.mean())
        gain = np.where(means > 1e-8, target / np.maximum(means, 1e-8), 1.0)
        out = lin * gain[None, None, :]

    elif kind == "gain":
        out = lin * float(params["factor"])

    elif kind == "contrast":
        m = float(lin.mean())
        out = (lin - m) * float(params["factor"]) + m

    elif kind == "veil":
        t = float(params["t"])
        out = t * lin + (1.0 - t) * VEIL_RGB[None, None, :]

    elif kind == "veil_depth":
        if ref_range is None:
            raise ValueError("veil_depth needs the reference range to shape the stimulus")
        r = np.asarray(ref_range, dtype=np.float64)
        fin = np.isfinite(r)
        if not fin.any():
            raise ValueError("reference range has no finite pixels")
        lo, hi = np.percentile(r[fin], [5, 95])
        u = np.clip((r - lo) / max(hi - lo, 1e-9), 0.0, 1.0)
        u = np.where(fin, u, 0.5)
        # Direction is expressed ONCE, by the endpoints. An `invert` flag used
        # to live here as a second way to say the same thing, and the two
        # depth-structured arms each said it twice -- swapped endpoints AND
        # invert=True -- so the double negation cancelled and the cue-conflict
        # arm was a bit-identical copy of its own control. `t_near` and `t_far`
        # now mean literally the transmission at the near and far ends.
        t = float(params["t_near"]) + u * (float(params["t_far"]) - float(params["t_near"]))
        t = t[..., None]
        out = t * lin + (1.0 - t) * VEIL_RGB[None, None, :]

    elif kind == "hotspot":
        h, w = lin.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float64)
        cy, cx = (h - 1) / 2.0, (w - 1) / 2.0
        s = float(params["sigma_frac"]) * min(h, w)
        g = np.exp(-(((yy - cy) ** 2 + (xx - cx) ** 2) / (2.0 * s * s)))
        out = lin + float(params["strength"]) * g[..., None]

    else:
        raise ValueError(f"unknown perturbation kind {kind!r}")

    return (_clip01(linear_to_srgb(_clip01(out))) * 255.0 + 0.5).astype(np.uint8)


def perturbation_summary(rgb_u8: np.ndarray, out_u8: np.ndarray) -> dict:
    """How much the APPEARANCE moved, so a geometry response has a denominator."""
    a = srgb_to_linear(np.asarray(rgb_u8, dtype=np.float64) / 255.0)
    b = srgb_to_linear(np.asarray(out_u8, dtype=np.float64) / 255.0)
    d = np.abs(b - a)
    return {
        "linear_mean_before": [float(x) for x in a.reshape(-1, 3).mean(axis=0)],
        "linear_mean_after": [float(x) for x in b.reshape(-1, 3).mean(axis=0)],
        "linear_abs_diff_median": float(np.median(d)),
        "linear_abs_diff_p95": float(np.percentile(d, 95)),
        "clipped_high_fraction": float((out_u8 == 255).mean()),
        "clipped_low_fraction": float((out_u8 == 0).mean()),
    }
