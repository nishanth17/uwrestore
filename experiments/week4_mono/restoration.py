"""Week 4A — a minimal range-driven restoration, built ONLY as a common instrument.

EXPLORATORY. numpy + the project's `uw.colorspace`.

THIS IS NOT THE PROJECT'S RESTORATION. Weeks 5-6 own backscatter removal and
attenuation inversion, and nothing here is a claim about how they should be
built. S6 needs to answer one question —

    does swapping the Week-3 multi-view range field for a monocular one
    change the restored image, and how?

— and answering it requires *some* stage that consumes range. So this implements
the project's standing image-formation model, exactly as `PLAN.md` states it and
as Week 3's stage-7 sensitivity study used it:

    I_c = J_c * exp(-b_att_c * d) + Binf_c * (1 - exp(-b_bs_c * d))

inverted with the ESTIMATED range:

    J_hat_c = (I_c - Binf_c * (1 - exp(-b_bs_c * d_hat))) / exp(-b_att_c * d_hat)

THE CONTROLLED COMPARISON. `b_att`, `b_bs` and `Binf` are held IDENTICAL across
every range field compared on a clip, and `Binf` is estimated once per clip from
the REFERENCE range. So between two arms the only thing that changes is `d_hat`.
That is what makes the difference attributable to the range field rather than to
a coefficient refit — and it is also what FREEZE §5 S6 means by "use shared
clip-level physical coefficients where the downstream stage expects them".

Holding the coefficients fixed is also what makes temporal scale drift bite. A
CONSTANT global scale error is exactly absorbable by `b -> b/s` (Week 3 verified
that identity to floating-point precision), so a model whose scale is merely
biased loses nothing here. A model whose scale WANDERS cannot be absorbed by any
single `b`, and the consequence shows up as colour pumping — which is precisely
the mechanism S6 exists to expose.

Everything happens in LINEAR light (`CLAUDE.md` invariant 1).
"""

from __future__ import annotations

import numpy as np

#: Attenuation / backscatter coefficients, 1/m, per RGB channel. These are the
#: Jerlov-bracketing values Week 3's stage-7 study swept — NOT a fit to this
#: project's footage, which Week 6 owns. Three regimes are available so a
#: conclusion cannot be an artefact of one choice; `coastal` is the default.
WATER_TYPES = {
    "clear_oceanic": {"b_att": [0.35, 0.09, 0.08], "b_bs": [0.30, 0.11, 0.10]},
    "coastal": {"b_att": [0.55, 0.20, 0.19], "b_bs": [0.45, 0.22, 0.22]},
    "turbid_coastal": {"b_att": [0.85, 0.45, 0.48], "b_bs": [0.70, 0.50, 0.55]},
}
DEFAULT_WATER = "coastal"

#: The restored radiance is clamped before it is looked at. Not to flatter the
#: result: an inversion divides by exp(-b d), which for a large d_hat is a huge
#: gain, so an unclamped J_hat can reach 1e3 on a handful of far pixels and
#: dominate every summary statistic. The clamp is recorded and the clipped
#: fraction is reported as a first-class number, because a model that needs a
#: lot of clamping has failed in a specific, nameable way.
J_CLAMP = 8.0

#: Floor on the per-channel transmission, i.e. a cap on the inversion gain.
#: `1/exp(-b_att d)` is 3.8e3 for red at 15 m in the coastal regime and these
#: clips carry reference ranges out past 50 m, so the raw inversion amplifies
#: the 8-bit source's quantisation step -- linear ~3e-4 near the dark end --
#: into something larger than the restored signal itself. At 20x that step is
#: ~6e-3 against restored medians of 0.2-0.5, which is under a percent; at 50x
#: it is already several percent. So 20x is where amplified quantisation stops
#: being negligible, and beyond it red is simply not recoverable from this
#: footage. Floored pixels are still restored -- under-corrected rather than
#: exploded -- and the floored fraction is reported per channel-set, because a
#: pixel with every channel on the floor no longer responds to `d` at all and
#: therefore cannot carry any information about the range field being tested.
T_FLOOR = 0.05


def estimate_veiling_light(linear_rgb: np.ndarray, ref_range: np.ndarray,
                           valid: np.ndarray, far_quantile: float = 0.90) -> np.ndarray:
    """Per-channel `Binf` from the far field of ONE clip's reference geometry.

    The far field is where `1 - exp(-b_bs d)` has saturated, so the observed
    radiance there is dominated by the veiling light. Estimated once per clip,
    from the REFERENCE range, and then held fixed for every arm — otherwise each
    arm would be restored under its own veiling light and the comparison would
    no longer isolate the range field.
    """
    r = np.asarray(ref_range, dtype=np.float64)
    v = np.asarray(valid, dtype=bool) & np.isfinite(r)
    if not v.any():
        return np.full(3, 0.2)
    thr = np.quantile(r[v], far_quantile)
    far = v & (r >= thr)
    if far.sum() < 50:
        far = v
    px = np.asarray(linear_rgb, dtype=np.float64)[far]
    # A high percentile rather than a max: a single specular highlight or a
    # marine-snow particle is not the water column.
    return np.percentile(px, 90, axis=0)


def admissible_veiling_light(linear_rgb: np.ndarray, ref_range: np.ndarray,
                            valid: np.ndarray, b_bs, quantile: float = 1.0) -> np.ndarray:
    """The largest per-channel `Binf` this image can actually carry.

    The model demands `J >= 0`, so at EVERY pixel

        I_c(p) >= Binf_c * (1 - exp(-b_bs_c * d(p)))   =>
        Binf_c <= min_p  I_c(p) / (1 - exp(-b_bs_c * d(p))).

    The pixels attaining that bound are the darkest ones AT THEIR OWN RANGE,
    where the scene contributes almost nothing and the observation essentially
    IS the backscatter. That makes this the dark-channel veiling-light
    estimator, made exact by knowing `d` instead of assuming a range for the
    dark pixels. A low quantile rather than the hard minimum, because a single
    dead-black sensor pixel is not evidence about the water column.

    This exists because the far-field estimator alone is NOT admissible on this
    footage. On the two clips whose water column is clipped in the source
    (`wreck_07`, `wreck_03` blow out blue at 10-14% of pixels), it returns
    `Binf_B = 1.0`, and `1.0 * (1 - exp(-0.22 * 7 m)) = 0.79` exceeds the
    observed blue at essentially every non-far pixel. The inversion then
    subtracts more than the image contains and clips to zero: measured over the
    frozen clips, 99% of pixels had at least one channel driven to zero, and the
    restored median was a pure red `[0.75, 0, 0]`. Two arms compared under that
    instrument agree perfectly because both are pinned, not because they agree.
    """
    r = np.asarray(ref_range, dtype=np.float64)
    v = np.asarray(valid, dtype=bool) & np.isfinite(r) & (r > 0)
    if not v.any():
        return np.full(3, 0.2)
    b = np.asarray(b_bs, dtype=np.float64)[None, :]
    build = 1.0 - np.exp(-b * r[v][:, None])
    ratio = np.asarray(linear_rgb, dtype=np.float64)[v] / np.maximum(build, 1e-6)
    return np.percentile(ratio, quantile, axis=0)


def restore(linear_rgb: np.ndarray, d_hat: np.ndarray, valid: np.ndarray,
            b_att, b_bs, Binf, clamp: float = J_CLAMP, t_floor: float = T_FLOOR):
    """Invert the image-formation model with `d_hat`.

    Returns `(J_hat, ok, stats, responsive)`. `responsive` marks the pixels that
    can still say anything about `d_hat`: not on the transmission floor in every
    channel, and not pinned at either end of the clamp. Everywhere else two
    different range fields produce the same pixel for reasons that have nothing
    to do with whether they agree.
    """
    I = np.asarray(linear_rgb, dtype=np.float64)
    d = np.asarray(d_hat, dtype=np.float64)[..., None]
    b_att = np.asarray(b_att, dtype=np.float64)[None, None, :]
    b_bs = np.asarray(b_bs, dtype=np.float64)[None, None, :]
    Binf = np.asarray(Binf, dtype=np.float64)[None, None, :]

    ok = np.asarray(valid, dtype=bool) & np.isfinite(d[..., 0]) & (d[..., 0] > 0)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        trans_raw = np.exp(-b_att * d)
        trans = np.maximum(trans_raw, t_floor)
        back = Binf * (1.0 - np.exp(-b_bs * d))
        J = (I - back) / trans
    floored = trans_raw <= t_floor
    finite = np.isfinite(J).all(axis=-1)
    ok = ok & finite
    gain = 1.0 / trans
    stats = {
        "clipped_high_fraction": float((J > clamp)[ok].mean()) if ok.any() else float("nan"),
        "negative_fraction": float((J < 0)[ok].mean()) if ok.any() else float("nan"),
        "gain_median": float(np.median(gain[ok])) if ok.any() else float("nan"),
        "gain_p99": float(np.percentile(gain[ok], 99)) if ok.any() else float("nan"),
        # What the inversion WOULD have asked for without the floor. A clip whose
        # uncapped gain runs to 1e3+ is telling you its far field is past the
        # range this instrument can speak about at all.
        "gain_p99_uncapped": (float(np.percentile((1.0 / np.maximum(trans_raw, 1e-8))[ok], 99))
                              if ok.any() else float("nan")),
        "floored_fraction_any": float(floored.any(-1)[ok].mean()) if ok.any() else float("nan"),
        "floored_fraction_all": float(floored.all(-1)[ok].mean()) if ok.any() else float("nan"),
    }
    J = np.clip(np.nan_to_num(J, nan=0.0, posinf=clamp, neginf=0.0), 0.0, clamp)
    responsive = (ok & ~floored.all(-1)
                  & (J > 0.0).all(-1) & (J < clamp).all(-1))
    stats["responsive_fraction"] = float(responsive[ok].mean()) if ok.any() else float("nan")
    return J, ok, stats, responsive


def compare_restorations(J_ref: np.ndarray, J_test: np.ndarray, ok: np.ndarray,
                         window: np.ndarray | None = None) -> dict:
    """How two restorations of the SAME frame differ. Radiance and colour.

    Colour is measured as CIEDE2000 between the two restored images in CIELAB,
    which is what makes "the colour changed" a statement with a magnitude rather
    than an impression. Both sides are normalised by the same exposure before
    the Lab conversion, because a pure exposure difference is a brightness
    result and would otherwise masquerade as a colour result.

    `window` is the RESPONSIVE subset: pixels where neither restoration sits on
    the transmission floor in every channel and neither is pinned at an end of
    the clamp. Outside it, two range fields produce the same pixel no matter how
    much they disagree, so an average over the full mask reads a saturation as
    an agreement. Both are reported -- the full-mask number for continuity, the
    windowed number as the one that carries information -- along with the
    window's size, because a conclusion drawn from a 5% window is a different
    kind of claim from one drawn from a 90% window.
    """
    from uw.colorspace import linear_rgb_to_lab
    from uw.metrics import ciede2000

    m = np.asarray(ok, dtype=bool)
    wnd = m if window is None else (m & np.asarray(window, dtype=bool))
    nan = float("nan")
    # Every key this function can ever produce exists on every row, NaN where
    # the quantity is undefined for this frame, so a caller aggregating rows
    # never has to guess whether a missing key means "zero" or "not measured".
    out = {
        "n": int(m.sum()),
        "n_radiance": 0,
        "status": "ok",
        "radiance_rel_median_per_channel": [nan, nan, nan],
        "radiance_abs_rel_median": nan,
        "radiance_abs_rel_p95": nan,
        "delta_e00_median": nan,
        "delta_e00_p95": nan,
        "exposure_ratio": nan,
        "n_window": int(wnd.sum()),
        "window_fraction": float(wnd.sum() / m.sum()) if m.sum() else nan,
        "delta_e00_median_window": nan,
        "delta_e00_p95_window": nan,
        "radiance_abs_rel_median_window": nan,
    }
    if m.sum() < 50:
        # Not a silent discard. The row survives carrying its own pixel count,
        # so the aggregator can say how many frames had too little common
        # support instead of quietly averaging over a smaller set than claimed.
        out["status"] = "insufficient_common_support"
        return out
    a = np.asarray(J_ref, dtype=np.float64)
    b = np.asarray(J_test, dtype=np.float64)

    with np.errstate(divide="ignore", invalid="ignore"):
        rel = (b[m] - a[m]) / np.where(a[m] > 1e-6, a[m], np.nan)
    rel = rel[np.isfinite(rel).all(axis=-1)] if rel.ndim == 2 else rel
    out["n_radiance"] = int(rel.shape[0]) if rel.size else 0
    if rel.size:
        out["radiance_rel_median_per_channel"] = [float(x) for x in np.median(rel, axis=0)]
        out["radiance_abs_rel_median"] = float(np.median(np.abs(rel)))
        out["radiance_abs_rel_p95"] = float(np.percentile(np.abs(rel), 95))
    else:
        # The REFERENCE restoration is at or below 1e-6 radiance everywhere the
        # two arms overlap, so a RELATIVE radiance difference has no denominator.
        # Colour is still measurable, so the frame is kept rather than dropped.
        out["status"] = "reference_radiance_degenerate"

    # Exposure-normalised colour comparison.
    sa = float(np.median(a[m])) or 1.0
    sb = float(np.median(b[m])) or 1.0
    la = linear_rgb_to_lab(np.clip(a[m] / sa * 0.18, 0.0, 1.0))
    lb = linear_rgb_to_lab(np.clip(b[m] / sb * 0.18, 0.0, 1.0))
    de = ciede2000(la, lb)
    out["delta_e00_median"] = float(np.median(de))
    out["delta_e00_p95"] = float(np.percentile(de, 95))
    out["exposure_ratio"] = float(sb / sa) if sa else float("nan")

    # The same two measurements again, restricted to the responsive window.
    if wnd.sum() >= 50:
        with np.errstate(divide="ignore", invalid="ignore"):
            relw = (b[wnd] - a[wnd]) / np.where(a[wnd] > 1e-6, a[wnd], np.nan)
        relw = relw[np.isfinite(relw).all(axis=-1)]
        if relw.size:
            out["radiance_abs_rel_median_window"] = float(np.median(np.abs(relw)))
        sa_w = float(np.median(a[wnd])) or 1.0
        sb_w = float(np.median(b[wnd])) or 1.0
        dew = ciede2000(linear_rgb_to_lab(np.clip(a[wnd] / sa_w * 0.18, 0.0, 1.0)),
                        linear_rgb_to_lab(np.clip(b[wnd] / sb_w * 0.18, 0.0, 1.0)))
        out["delta_e00_median_window"] = float(np.median(dew))
        out["delta_e00_p95_window"] = float(np.percentile(dew, 95))
    out["_note"] = ("delta E00 is computed after normalising BOTH restorations to the same "
                    "median exposure, so a pure brightness difference does not present as a "
                    "colour difference; the exposure ratio itself is reported separately")
    return out
