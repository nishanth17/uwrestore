"""Pure colorspace conversion functions. No I/O.

All restoration processing happens in linear-light RGB (see CLAUDE.md
invariant 1). These functions map between an encoded transfer function and
linear light and back; they never touch disk.
"""

import numpy as np


def srgb_to_linear(array: np.ndarray) -> np.ndarray:
    """Standard sRGB EOTF: encoded sRGB [0,1] -> linear light [0,1].

    Does not mutate the input array; returns a new array.
    """
    a = np.asarray(array, dtype=np.float64)
    linear = np.where(
        a <= 0.04045,
        a / 12.92,
        ((a + 0.055) / 1.055) ** 2.4,
    )
    return linear.astype(array.dtype if np.issubdtype(array.dtype, np.floating) else np.float32)


def linear_to_srgb(array: np.ndarray) -> np.ndarray:
    """Inverse sRGB EOTF: linear light [0,1] -> encoded sRGB [0,1].

    Does not mutate the input array; returns a new array.
    """
    a = np.asarray(array, dtype=np.float64)
    a = np.clip(a, 0.0, 1.0)
    encoded = np.where(
        a <= 0.0031308,
        a * 12.92,
        1.055 * (a ** (1.0 / 2.4)) - 0.055,
    )
    return encoded.astype(array.dtype if np.issubdtype(array.dtype, np.floating) else np.float32)


def protune_flat_to_linear(array: np.ndarray) -> np.ndarray:
    """GoPro Protune Flat -> linear light.

    STUBBED, not implemented. Protune Flat is a log-style curve, not a
    simple gamma function, and GoPro has not published an exact formula.
    Implementing an unverified approximation risks silently corrupting
    color for every Protune-sourced input, which is worse than failing
    loudly. See CLAUDE.md invariant 1 and PLAN.md's Week 1 calibration
    check.

    TODO: implement and validate against the RAW-vs-Protune calibration
    check described in PLAN.md before this is used for real ingest.
    """
    raise NotImplementedError(
        "Protune Flat -> linear mapping is stubbed this session — "
        "not validated, see uw/colorspace.py TODO"
    )


# ---------------------------------------------------------------------------
# CIE XYZ / CIELAB
#
# Conversion assumptions, stated explicitly rather than implied (CLAUDE.md
# invariant 1):
#
# 1. Input RGB is LINEAR light, not gamma-encoded. These functions apply no
#    EOTF; feeding them sRGB-encoded data produces silently wrong Lab values.
#    Callers convert with srgb_to_linear() first — or, in this pipeline, the
#    data is already linear because uw/io.py linearizes on ingest.
# 2. Linear RGB is assumed to use the sRGB / Rec.709 primaries with a D65
#    white point. This is the pipeline's working space: uw/io.py ingests
#    sRGB-encoded sources and only removes the transfer function, so the
#    primaries stay sRGB's. RAW-linear inputs are assumed to have been
#    converted to these primaries before load() (see LOG.md on the
#    raw_linear path).
# 3. The RGB -> XYZ matrix below is the standard sRGB matrix (IEC 61966-2-1),
#    which is already D65-relative, so no chromatic adaptation is needed on
#    the RGB -> XYZ -> Lab path. Adaptation is only needed to compare against
#    reference data published under a different illuminant (D50 ColorChecker
#    tables) — see bradford_adaptation_matrix() / adapt_lab().
# 4. CIELAB uses the exact rational CIE constants (epsilon = 216/24389,
#    kappa = 24389/27), not the rounded 0.008856 / 903.3 forms.
# 5. All of these compute in float64 and return float64. Frames are float32,
#    but ΔE is a measurement — rounding the conversion to float32 would put
#    error into the metric itself.
#
# Tristimulus values are Y-normalized (Y = 1.0 for the white point), so a
# linear RGB of (1, 1, 1) maps to the white point exactly and L* = 100.
# ---------------------------------------------------------------------------

# CIE standard illuminant white points, 2-degree observer, Y normalized to 1.
D65_WHITE_XYZ = np.array([0.95047, 1.00000, 1.08883], dtype=np.float64)
D50_WHITE_XYZ = np.array([0.96422, 1.00000, 0.82521], dtype=np.float64)

WHITE_POINTS = {
    "D65": D65_WHITE_XYZ,
    "D50": D50_WHITE_XYZ,
}

# Linear sRGB (Rec.709 primaries, D65) -> CIE XYZ.
LINEAR_SRGB_TO_XYZ_D65 = np.array(
    [
        [0.4124564, 0.3575761, 0.1804375],
        [0.2126729, 0.7151522, 0.0721750],
        [0.0193339, 0.1191920, 0.9503041],
    ],
    dtype=np.float64,
)

# Bradford cone response matrix, used for chromatic adaptation between
# illuminants. The inverse is computed rather than transcribed, so there is
# only one place a typo could hide.
_BRADFORD = np.array(
    [
        [0.8951, 0.2664, -0.1614],
        [-0.7502, 1.7135, 0.0367],
        [0.0389, -0.0685, 1.0296],
    ],
    dtype=np.float64,
)
_BRADFORD_INV = np.linalg.inv(_BRADFORD)

# Exact CIE constants (rational forms, not the rounded published decimals).
_LAB_EPSILON = 216.0 / 24389.0
_LAB_KAPPA = 24389.0 / 27.0


def _as_triplet_array(array: np.ndarray, name: str) -> np.ndarray:
    """Validate a (..., 3) array and return it as float64. Never mutates."""
    a = np.asarray(array, dtype=np.float64)
    if a.ndim == 0 or a.shape[-1] != 3:
        raise ValueError(f"{name} must have shape (..., 3), got {a.shape}")
    return a


def linear_rgb_to_xyz(rgb: np.ndarray) -> np.ndarray:
    """Linear sRGB/Rec.709 (D65 primaries) -> CIE XYZ (D65-relative).

    Accepts any shape ending in 3: (3,), (N, 3), (H, W, 3). Purely a matrix
    multiply, so it is defined for values outside [0, 1] — out-of-range
    linear values (e.g. gray-world output, which deliberately does not clip)
    pass through without being silently clamped here.
    """
    a = _as_triplet_array(rgb, "rgb")
    return a @ LINEAR_SRGB_TO_XYZ_D65.T


def xyz_to_linear_rgb(xyz: np.ndarray) -> np.ndarray:
    """CIE XYZ (D65-relative) -> linear sRGB/Rec.709. Inverse of the above."""
    a = _as_triplet_array(xyz, "xyz")
    return a @ np.linalg.inv(LINEAR_SRGB_TO_XYZ_D65).T


def xyz_to_lab(xyz: np.ndarray, white_xyz: np.ndarray = D65_WHITE_XYZ) -> np.ndarray:
    """CIE XYZ -> CIELAB, relative to `white_xyz`.

    Ratios are not clamped: since `_LAB_EPSILON` is positive, any negative
    ratio falls into the linear branch `(kappa*t + 16) / 116`, which is
    finite and well-defined for negative t (no NaN risk). Clamping negative
    ratios to 0 would collapse distinct invalid/out-of-gamut inputs to the
    same Lab coordinates, masking their magnitude and direction. Values
    above the white point are NOT clamped either — L* > 100 is meaningful
    for highlights.
    """
    a = _as_triplet_array(xyz, "xyz")
    white = _as_triplet_array(white_xyz, "white_xyz")
    ratio = a / white
    f = np.where(
        ratio > _LAB_EPSILON,
        np.cbrt(ratio),
        (_LAB_KAPPA * ratio + 16.0) / 116.0,
    )
    fx, fy, fz = f[..., 0], f[..., 1], f[..., 2]
    return np.stack(
        [116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz)],
        axis=-1,
    )


def lab_to_xyz(lab: np.ndarray, white_xyz: np.ndarray = D65_WHITE_XYZ) -> np.ndarray:
    """CIELAB -> CIE XYZ, relative to `white_xyz`. Inverse of xyz_to_lab."""
    a = _as_triplet_array(lab, "lab")
    white = _as_triplet_array(white_xyz, "white_xyz")
    L, a_star, b_star = a[..., 0], a[..., 1], a[..., 2]
    fy = (L + 16.0) / 116.0
    fx = fy + a_star / 500.0
    fz = fy - b_star / 200.0
    xr = np.where(fx**3 > _LAB_EPSILON, fx**3, (116.0 * fx - 16.0) / _LAB_KAPPA)
    yr = np.where(L > _LAB_KAPPA * _LAB_EPSILON, fy**3, L / _LAB_KAPPA)
    zr = np.where(fz**3 > _LAB_EPSILON, fz**3, (116.0 * fz - 16.0) / _LAB_KAPPA)
    return np.stack([xr, yr, zr], axis=-1) * white


def linear_rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """Linear sRGB/Rec.709 -> CIELAB (D65). The pipeline's normal path.

    Note the input must already be linear light — see the assumptions block
    above. This is the conversion `uw.metrics.delta_e` uses, which is why it
    goes through XYZ rather than starting from gamma-encoded sRGB.
    """
    return xyz_to_lab(linear_rgb_to_xyz(rgb), D65_WHITE_XYZ)


def bradford_adaptation_matrix(
    source_white_xyz: np.ndarray, dest_white_xyz: np.ndarray
) -> np.ndarray:
    """3x3 Bradford chromatic adaptation matrix, source white -> dest white.

    Used to bring reference data published under one illuminant (e.g. the
    D50-referenced X-Rite ColorChecker tables) into the pipeline's D65
    working white, so ΔE measures the pipeline's error and not a white-point
    mismatch the pipeline never made.
    """
    source = _as_triplet_array(source_white_xyz, "source_white_xyz")
    dest = _as_triplet_array(dest_white_xyz, "dest_white_xyz")
    source_cone = _BRADFORD @ source
    dest_cone = _BRADFORD @ dest
    return _BRADFORD_INV @ np.diag(dest_cone / source_cone) @ _BRADFORD


def adapt_xyz(
    xyz: np.ndarray, source_white_xyz: np.ndarray, dest_white_xyz: np.ndarray
) -> np.ndarray:
    """Chromatically adapt XYZ from one reference white to another (Bradford)."""
    a = _as_triplet_array(xyz, "xyz")
    return a @ bradford_adaptation_matrix(source_white_xyz, dest_white_xyz).T


def adapt_lab(
    lab: np.ndarray, source_white_xyz: np.ndarray, dest_white_xyz: np.ndarray
) -> np.ndarray:
    """Re-reference CIELAB values from one illuminant to another.

    Lab(source) -> XYZ(source) -> Bradford -> XYZ(dest) -> Lab(dest).
    A no-op (to floating point) when the two white points are equal.
    """
    xyz_source = lab_to_xyz(lab, source_white_xyz)
    xyz_dest = adapt_xyz(xyz_source, source_white_xyz, dest_white_xyz)
    return xyz_to_lab(xyz_dest, dest_white_xyz)
