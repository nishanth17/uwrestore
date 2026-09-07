"""Week 4A — the E1 alignment families, one per native representation.

EXPLORATORY. Pure numpy.

WHAT S2 FREEZES IS A POLICY, NOT A TRANSFORM (`MONO_DEPTH_FREEZE.md` §5 S2).
There is no single alignment that is legal for all seven entrants. Fitting one
anyway is the single most common way to make a monocular comparison meaningless:

    Depth Anything V2's ambiguity lives in DISPARITY. Fitting `a*d + b` in
    physical depth is not a stricter version of `a*q + b` in disparity; it is a
    DIFFERENT transform group, and it flatters the model in some scenes and
    destroys it in others.

So this module offers a small closed set of families, each attached to a
representation, and records which one was used and what nuisance parameters it
consumed. The freeze is explicit that the fitted parameters must be EXPOSED
rather than hidden: a model that needs a huge shift to look good has told you
something about itself.

    family              legal for                       parameters
    ------------------  ------------------------------  ----------------
    scale               metric / relative point maps     s
    affine_depth        relative scalar depth            s, t
    affine_disparity    relative inverse depth           a, b
    none                raw metric, no alignment at all  -

FITTING SCOPE. The default scope is CLIP-LEVEL: one fit pooled over every frame
of a clip. Per-frame fitting is available and is a DIAGNOSTIC ONLY — Week 3
already established that renormalising each frame erases temporal scale drift,
which is a real failure mode rather than a nuisance, and FREEZE C7 makes the
distinction load-bearing for S5.

ROBUSTNESS. `scale` uses the median log-ratio, the same estimator Week 3 froze,
so a Week-4 scale and a Week-3 scale mean the same thing. The two-parameter
families use an iteratively reweighted least squares with a Huber-style cut,
because a plain least squares on an underwater range field is dominated by the
far tail and by whatever the model hallucinated in the water column.
"""

from __future__ import annotations

from dataclasses import dataclass, field as _field

import numpy as np

from experiments.week3_geometry.phase3a import geometry as g3

FAMILIES = ("none", "scale", "affine_depth", "affine_disparity",
            "affine_log1p_depth")

#: `affine_log1p_depth` is a ROUND-2 addition, and it exists for exactly one
#: reason: PXDepth's native output is normalised log1p-depth whose documented
#: ambiguity is affine IN THAT SPACE. `pxdepth/model/inference.py` builds
#: `ref_log = log1p(ref_depth)` (:174), solves `ref_log ~= a*pred + b` (:189)
#: and recovers `depth = expm1(a*pred + b)` (:195). Forcing that prediction
#: through `affine_depth` or `affine_disparity` would be fitting the wrong
#: ambiguity and would charge the model for a gauge it never claimed. The
#: POLICY is unchanged -- clip-level scope, Huber IRLS, reference-side
#: conversion done by the caller -- only the SPACE is representation-specific,
#: which is the same rule that already separates depth from disparity above.


@dataclass
class Alignment:
    """A fitted E1 transform, with everything needed to reproduce and judge it."""
    family: str
    params: dict
    n_used: int
    n_offered: int
    scope: str
    #: Robust spread of the log residual AFTER the fit. The transform has
    #: already absorbed everything it can, so what is left is shape error.
    #:
    #: NOT COMPARABLE ACROSS ALL FAMILIES. It is measured in the family's own
    #: fitting space. For `scale`, `affine_depth` and `affine_disparity` that
    #: space is depth- or disparity-like, so this equals the spread of the log
    #: RANGE ratio and the families can be tabulated side by side. For
    #: `affine_log1p_depth` the fitting target is `log1p(z)`, so this is the
    #: spread of `log(log1p(z) / fitted)` -- the log OF a log1p -- which is
    #: systematically smaller and is a different quantity. Putting it in the
    #: same column as the others is a units error, not a result; recompute the
    #: log-range residual for that family instead (see
    #: `round2/outputs/r2_s2/r2_pxdepth_comparable_e1.json`).
    log_residual_mad: float = float("nan")
    notes: list = _field(default_factory=list)

    def to_dict(self) -> dict:
        return {"family": self.family, "params": self.params, "n_used": self.n_used,
                "n_offered": self.n_offered, "scope": self.scope,
                "log_residual_mad": self.log_residual_mad, "notes": self.notes}


def _huber_irls(A: np.ndarray, y: np.ndarray, iters: int = 12, c: float = 1.345):
    """Iteratively reweighted least squares with a Huber weight. Returns coeffs."""
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    for _ in range(iters):
        r = y - A @ coef
        s = 1.4826 * np.median(np.abs(r - np.median(r)))
        if not np.isfinite(s) or s <= 0:
            break
        z = np.abs(r) / (c * s)
        w = np.where(z <= 1.0, 1.0, 1.0 / np.maximum(z, 1e-12))
        Aw = A * w[:, None]
        yw = y * w
        new, *_ = np.linalg.lstsq(Aw, yw, rcond=None)
        if np.allclose(new, coef, rtol=1e-10, atol=1e-12):
            coef = new
            break
        coef = new
    return coef


def fit_scale(pred: np.ndarray, ref: np.ndarray, scope: str = "clip") -> Alignment:
    """One global scalar: `ref ~= s * pred`. Week 3's median-log-ratio estimator."""
    fit = g3.fit_global_scale(np.asarray(pred).ravel(), np.asarray(ref).ravel())
    return Alignment("scale", {"s": fit.scale}, fit.n_used, fit.n_offered, scope,
                     fit.log_residual_mad,
                     ["median log ratio, identical to the Week-3 estimator"])


_SPACE_NAME = {"affine_depth": "depth", "affine_disparity": "disparity",
               "affine_log1p_depth": "log1p-depth"}


def fit_affine(pred: np.ndarray, ref: np.ndarray, family: str,
               scope: str = "clip") -> Alignment:
    """Two parameters: `ref ~= s*pred + t`, fitted in the SPACE `family` names.

    `affine_depth` fits in scalar depth. `affine_disparity` fits in disparity —
    the caller is responsible for having converted BOTH sides into disparity
    first, because doing the conversion here would hide which space the fit
    happened in, and that is the whole point of the distinction.
    """
    p = np.asarray(pred, dtype=np.float64).ravel()
    r = np.asarray(ref, dtype=np.float64).ravel()
    n_offered = p.size
    good = np.isfinite(p) & np.isfinite(r)
    if family == "affine_depth":
        good &= (p > 0) & (r > 0)
    if family == "affine_log1p_depth":
        # `r` is already log1p(reference depth) and may legitimately be 0 at
        # zero range; `p` is a normalised log-depth of unrestricted sign.
        good &= (r >= 0)
    if good.sum() < 2:
        return Alignment(family, {"s": float("nan"), "t": float("nan")},
                         int(good.sum()), n_offered, scope)
    P, R = p[good], r[good]
    A = np.stack([P, np.ones_like(P)], axis=1)
    s, t = _huber_irls(A, R)
    fitted = s * P + t
    mad = float("nan")
    ok = fitted > 0
    if ok.any():
        lr = np.log(np.maximum(R[ok], 1e-12)) - np.log(np.maximum(fitted[ok], 1e-12))
        mad = float(np.median(np.abs(lr - np.median(lr))))
    return Alignment(family, {"s": float(s), "t": float(t)}, int(good.sum()),
                     n_offered, scope, mad,
                     [f"Huber IRLS in {_SPACE_NAME.get(family, family)} space",
                      "t is a NUISANCE parameter and is reported, not hidden: a model "
                      "needing a large shift has told you something about itself"])


def apply(alignment: Alignment, pred: np.ndarray) -> np.ndarray:
    """Apply a fitted transform in ITS OWN space. Returns a new array."""
    p = np.asarray(pred, dtype=np.float64)
    f = alignment.family
    if f == "none":
        return p.copy()
    if f == "scale":
        return alignment.params["s"] * p
    if f in ("affine_depth", "affine_disparity", "affine_log1p_depth"):
        return alignment.params["s"] * p + alignment.params["t"]
    raise ValueError(f"unknown alignment family {f!r}")


def to_range(aligned: np.ndarray, family: str) -> np.ndarray:
    """Convert an aligned quantity into a RANGE-like positive field.

    For `affine_disparity` this is the inversion, and it happens HERE — after
    the fit, once, under the frozen policy — never inside a backend. A
    non-positive aligned disparity has no finite range and becomes NaN rather
    than a huge number: `1/0.0001` is not a 10 km scene point, it is a pixel
    the model had nothing to say about.
    """
    a = np.asarray(aligned, dtype=np.float64)
    if family == "affine_log1p_depth":
        # The aligned quantity is log1p(depth); invert the documented gauge.
        # A negative log1p means the fit put the pixel behind the camera, which
        # is not a near point but an absence of a prediction -> NaN, exactly as
        # a non-positive disparity is treated below.
        with np.errstate(over="ignore", invalid="ignore"):
            out = np.expm1(np.clip(a, -50.0, 50.0))
        return np.where(np.isfinite(out) & (out > 0), out, np.nan)
    if family == "affine_disparity":
        with np.errstate(divide="ignore", invalid="ignore"):
            out = 1.0 / a
        return np.where(np.isfinite(out) & (a > 0), out, np.nan)
    return np.where(np.isfinite(a) & (a > 0), a, np.nan)


def to_log1p(x: np.ndarray) -> np.ndarray:
    """Positive field -> log1p. Used to put the REFERENCE into PXDepth's space."""
    a = np.asarray(x, dtype=np.float64)
    return np.where(np.isfinite(a) & (a > 0), np.log1p(np.maximum(a, 0.0)), np.nan)


def to_disparity(x: np.ndarray) -> np.ndarray:
    """Positive field -> disparity. Used to put the REFERENCE into DA V2's space."""
    a = np.asarray(x, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = 1.0 / a
    return np.where(np.isfinite(out) & (a > 0), out, np.nan)


def compare_families(pred: np.ndarray, ref: np.ndarray,
                     families: list[str], scope: str = "clip") -> dict:
    """Fit several legal families on the same data and report what each buys.

    This is how FREEZE C1's question gets answered with evidence instead of
    architecture: DA3 Mono's literature ambiguity is affine-in-depth, and S2 is
    allowed to discover that the additive term is negligible ON THIS DOMAIN —
    but only from the measured residual gain, never from a utility function's
    name.
    """
    out = {}
    for fam in families:
        if fam == "scale":
            a = fit_scale(pred, ref, scope)
        elif fam in ("affine_depth", "affine_disparity"):
            a = fit_affine(pred, ref, fam, scope)
        elif fam == "none":
            a = Alignment("none", {}, int(np.isfinite(np.asarray(pred)).sum()),
                          int(np.asarray(pred).size), scope)
        else:
            raise ValueError(fam)
        aligned = apply(a, pred)
        rng = to_range(aligned, fam)
        err = g3.relative_errors(rng, np.asarray(ref, dtype=np.float64), 1.0) \
            if fam != "affine_disparity" else None
        rec = a.to_dict()
        if err is not None:
            rec["abs_rel_median"] = float(np.nanmedian(np.abs(err)))
        out[fam] = rec
    return out
