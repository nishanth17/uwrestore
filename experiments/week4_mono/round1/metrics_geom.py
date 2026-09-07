"""Week 4A — the six universal local-geometry metrics, M-1 to M-6.

EXPLORATORY. Numpy, plus torch only inside M-3 (RelNormal). Runs in `.venv-eval`.

The set is frozen by `MONO_DEPTH_FREEZE.md` §6 and reduced there from nine
metrics to six. Two rules govern the whole module:

  * **AbsRel and delta-1 are secondary literature-continuity metrics and are
    never decisive.** They are computed and reported because the outside world
    speaks in them, and they never appear in a ranking argument on their own.

  * **There is no weighted master score.** Every metric is reported separately
    and a model is reduced on explicit multi-dimensional reasons. Collapsing six
    dimensions into one number would hide exactly the tradeoffs the freeze
    requires be documented.

Everything here is computed AFTER the frozen S2 alignment, on the common
evaluation grid, against the Week-3 persisted range product — which is a
PROVISIONAL MULTI-VIEW HYPOTHESIS, not ground truth. "Error" throughout this
module means "disagreement with the current Week-3 hypothesis".
"""

from __future__ import annotations

import numpy as np

from experiments.week3_geometry.phase3a import geometry as g3

# --------------------------------------------------------------------------
# M-1 — range-stratified relative range error
# --------------------------------------------------------------------------

#: M-1a. NOMINAL/REFERENCE bins, in Week-3 reference units. FREEZE 6 is explicit
#: that these are "Week-3 reference units / provisional nominal metres, not
#: independently validated physical metres". Nothing pre-C2 may claim that the
#: reference's nominal 8 m is objectively an 8 m water path.
NOMINAL_BINS = [0.0, 1.0, 2.0, 3.0, 5.0, 8.0, 12.0, np.inf]

#: M-1b. Scale-invariant stratification: quantiles of the reference range within
#: the clip. This survives the absolute scale being wrong, which pre-C2 it may
#: be, and still detects near/far compression and far-end deterioration.
QUANTILE_EDGES = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]


def relative_error(pred_range: np.ndarray, ref_range: np.ndarray) -> np.ndarray:
    """Signed (pred - ref)/ref, NaN where either side is unusable."""
    return g3.relative_errors(pred_range, ref_range, 1.0)


def m1_stratified(pred_range: np.ndarray, ref_range: np.ndarray,
                  quantile_thresholds: np.ndarray | None = None) -> dict:
    """M-1 in BOTH required forms: nominal reference bins and scale-invariant bins.

    `quantile_thresholds` must be computed once per clip over the pooled
    reference and passed in, so that every frame of a clip uses the SAME near /
    mid / far definition. Recomputing them per frame would renormalise away the
    very range-dependent behaviour M-1b is looking for.
    """
    err = relative_error(pred_range, ref_range)
    ref = np.asarray(ref_range, dtype=np.float64)
    out = {"overall": g3.robust_stats(np.abs(err))}
    out["overall_signed"] = g3.robust_stats(err)

    prof = g3.binned_profile(ref.ravel(), np.abs(err).ravel(), np.asarray(NOMINAL_BINS))
    out["m1a_nominal_bins"] = prof
    out["m1a_note"] = ("Bin edges are Week-3 reference units / provisional nominal metres, "
                       "NOT independently validated physical metres (FREEZE 6, pre-C2).")

    if quantile_thresholds is not None:
        prof_q = g3.binned_profile(ref.ravel(), np.abs(err).ravel(),
                                   np.asarray(quantile_thresholds, dtype=np.float64))
        out["m1b_quantile_bins"] = prof_q
        out["m1b_edges"] = [float(x) for x in quantile_thresholds]
        out["m1b_note"] = ("Scale-invariant near/mid/far stratification: bin edges are "
                           "quantiles of the CLIP's pooled reference range, so the "
                           "stratification survives an absolute scale that pre-C2 may be "
                           "wrong.")
    return out


def secondary_metrics(pred_range: np.ndarray, ref_range: np.ndarray) -> dict:
    """AbsRel and delta thresholds. Literature continuity only. Never decisive."""
    p = np.asarray(pred_range, dtype=np.float64).ravel()
    r = np.asarray(ref_range, dtype=np.float64).ravel()
    m = np.isfinite(p) & np.isfinite(r) & (p > 0) & (r > 0)
    if not m.any():
        return {"n": 0}
    p, r = p[m], r[m]
    ratio = np.maximum(p / r, r / p)
    return {
        "n": int(m.sum()),
        "abs_rel": float(np.mean(np.abs(p - r) / r)),
        "delta_1_25": float(np.mean(ratio < 1.25)),
        "delta_1_25_2": float(np.mean(ratio < 1.25 ** 2)),
        "rmse_log": float(np.sqrt(np.mean((np.log(p) - np.log(r)) ** 2))),
        "_note": "secondary literature-continuity metrics; never decisive (FREEZE 6)",
    }


# --------------------------------------------------------------------------
# M-2 — near/far systematic distortion
# --------------------------------------------------------------------------


def m2_loglog(pred_range: np.ndarray, ref_range: np.ndarray) -> dict:
    """Fit `log(r_hat) = a + b log(r_ref)` on aligned valid geometry.

        b ~= 1   no systematic range-dependent compression or expansion
        b <  1   far-field COMPRESSION
        b >  1   far-field EXPANSION

    `a` is not treated as physical truth pre-C2 — with the alignment already
    fitted it is close to a restatement of the scale gauge. `b` is the
    shape/range-dependent distortion diagnostic, and it is what this metric is
    for.
    """
    p = np.asarray(pred_range, dtype=np.float64).ravel()
    r = np.asarray(ref_range, dtype=np.float64).ravel()
    m = np.isfinite(p) & np.isfinite(r) & (p > 0) & (r > 0)
    if m.sum() < 10:
        return {"n": int(m.sum()), "a": float("nan"), "b": float("nan")}
    x = np.log(r[m])
    y = np.log(p[m])
    A = np.stack([x, np.ones_like(x)], axis=1)
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    b, a = float(coef[0]), float(coef[1])
    resid = y - A @ coef
    xm = x - x.mean()
    r2 = 1.0 - float(np.sum(resid ** 2) / max(np.sum((y - y.mean()) ** 2), 1e-12))
    return {
        "n": int(m.sum()), "a": a, "b": b, "r2": r2,
        "resid_mad": float(np.median(np.abs(resid - np.median(resid)))),
        "b_se": float(np.sqrt(np.sum(resid ** 2) / max(len(x) - 2, 1) /
                              max(np.sum(xm ** 2), 1e-12))),
        "interpretation": ("b<1 far-field compression; b>1 far-field expansion; "
                           "a is not physical truth pre-C2"),
    }


# --------------------------------------------------------------------------
# M-3 — local surface geometry
# --------------------------------------------------------------------------

#: RelNormal sampling budget. EvalMDE's default is 1e6 pairs at scales
#: [1,2,4,8]. On this project's 320x180 evaluation grid that is ~18x
#: oversampling of the 56k available triangles at scale 1 and far more at scale
#: 8, so the budget is reduced. The estimator is a mean over sampled pairs and
#: its standard error at 2e5 samples is already well below every difference this
#: bakeoff reads. Scales and every other config value are EvalMDE's.
RELNORMAL_NUM_SAMPLE = 200_000
RELNORMAL_SCALES = [1, 2, 4, 8]


def triangle_normals(xyz: np.ndarray, valid: np.ndarray):
    """(H-2,W-2,3) normals and validity, EvalMDE's 2-pixel-spacing construction.

    Reimplemented in numpy rather than imported so that the absolute-normal
    metric can be computed without a torch round-trip; `m3_relnormal` still
    calls EvalMDE's own code for RelNormal itself.
    """
    xyz = np.asarray(xyz, dtype=np.float64)
    p0 = xyz[:-2, :-2]
    p1 = xyz[2:, :-2]
    p2 = xyz[:-2, 2:]

    def unit(v):
        n = np.linalg.norm(v, axis=-1, keepdims=True)
        return v / np.where(n > 0, n, 1.0)

    n = np.cross(unit(p1 - p0), unit(p2 - p0))
    mag = np.linalg.norm(n, axis=-1)
    ok = (mag > 1e-5) & valid[:-2, :-2] & valid[2:, :-2] & valid[:-2, 2:]
    n = n / np.where(mag[..., None] > 1e-5, mag[..., None], 1.0)
    return n, ok


def m3_absolute_normal(pred_xyz, pred_valid, ref_xyz, ref_valid) -> dict:
    """SurGe-style absolute normal angular error, in degrees.

    Scale-invariant by construction — a surface normal does not change when the
    whole scene is scaled — so it is legitimate under every E1 family here.
    """
    np_pred, ok_p = triangle_normals(pred_xyz, pred_valid)
    np_ref, ok_r = triangle_normals(ref_xyz, ref_valid)
    ok = ok_p & ok_r
    if not ok.any():
        return {"n": 0}
    cos = np.clip((np_pred[ok] * np_ref[ok]).sum(axis=-1), -1.0, 1.0)
    ang = np.degrees(np.arccos(np.abs(cos)))   # orientation-agnostic
    st = g3.robust_stats(ang)
    st["mae_deg"] = float(np.mean(ang))
    st["frac_within_10deg"] = float(np.mean(ang < 10.0))
    st["frac_within_30deg"] = float(np.mean(ang < 30.0))
    st["coverage"] = float(ok.mean())
    st["_note"] = ("angle between triangle normals, |cos| so a flipped normal is not "
                   "counted as a 180 deg error; scale-invariant")
    return st


def m3_relnormal(pred_xyz, pred_valid, ref_xyz, ref_valid,
                 num_sample: int = RELNORMAL_NUM_SAMPLE,
                 scales=None, device: str = "cpu") -> dict:
    """RelNormal via `princeton-vl/EvalMDE`, the freeze's primary M-3 metric.

    RelNormal compares the ANGLE BETWEEN two normals in the prediction against
    the angle between the corresponding two normals in the reference, over
    sampled pixel pairs at several scales. It exposes curvature and local-surface
    differences that aligned scalar-depth metrics can miss.

    FREEZE C9 is explicit about what it is not: it does not turn E1 into a
    deployability test, and it does not restore information the alignment
    deliberately removed. It is computed AFTER the frozen E1 alignment and
    measures relative local surface orientation in that aligned geometry.
    """
    import torch
    from evalmde.metrics.rel_normal import get_multi_scale_rel_normal_err
    scales = list(scales or RELNORMAL_SCALES)
    gx = torch.as_tensor(np.asarray(ref_xyz, dtype=np.float32), device=device)
    gv = torch.as_tensor(np.asarray(ref_valid, dtype=bool), device=device)
    px = torch.as_tensor(np.asarray(pred_xyz, dtype=np.float32), device=device)
    pv = torch.as_tensor(np.asarray(pred_valid, dtype=bool), device=device)
    # `invalid='penalty'` is EvalMDE's default: a pair the reference can measure
    # and the prediction cannot is charged pi rather than skipped, so a model
    # cannot improve its score by declining to predict.
    per_scale = get_multi_scale_rel_normal_err(
        gx, gv, px, pv, scales=scales, num_sample=int(num_sample),
        radius=32, min_radius=3, invalid="penalty")
    return {
        "rel_normal_rad": float(np.mean(per_scale)),
        "rel_normal_deg": float(np.degrees(np.mean(per_scale))),
        "per_scale_rad": [float(x) for x in per_scale],
        "scales": scales,
        "num_sample": int(num_sample),
        "invalid_policy": "penalty (EvalMDE default): unpredicted pairs are charged pi",
    }


# --------------------------------------------------------------------------
# M-4 — boundary localization
# --------------------------------------------------------------------------

#: A geometric boundary is where the LOG range changes fast, which makes the
#: construction invariant to the global scale gauge — the same edge set comes
#: out whether or not the scene has been scaled.
#:
#: THE THRESHOLD IS CALIBRATED PER CLIP, NOT FIXED, and that is a correction
#: forced by measurement. A fixed 0.10 log-unit threshold (a ~10 % range step
#: between neighbouring evaluation samples) found ZERO edges anywhere: on
#: `wreck_07` the Week-3 reference's log-gradient tops out at 0.039, because the
#: reference is a smooth wreck surface produced with `mask_edges=True`. A
#: threshold that fires nowhere measures nothing.
#:
#: So the CONSTRUCTION is frozen — top `EDGE_PERCENTILE` of the log-range
#: gradient — and its numeric value is calibrated once per clip from the
#: REFERENCE, pooled over that clip's frames, then applied unchanged to both
#: sides on every frame. The per-clip step is necessary because the clips
#: genuinely differ in depth relief: a cenote cavern and a flat hull do not
#: share a definition of "sharp". Because the threshold comes from the pooled
#: clip rather than from each frame, both edge fractions are still free to vary
#: frame to frame, so `edge_fraction_pred` vs `edge_fraction_ref` remains a real
#: diagnostic of whether a model invents or suppresses structure.
EDGE_PERCENTILE = 98.0
EDGE_LOG_FLOOR = 5e-3


def log_range_gradient(range_field: np.ndarray, valid: np.ndarray):
    """(magnitude, ok) of the central-difference gradient of log range."""
    r = np.asarray(range_field, dtype=np.float64)
    v = np.asarray(valid, dtype=bool) & np.isfinite(r) & (r > 0)
    lr = np.where(v, np.log(np.where(r > 0, r, 1.0)), np.nan)
    gy = np.full_like(lr, np.nan)
    gx = np.full_like(lr, np.nan)
    gy[1:-1, :] = lr[2:, :] - lr[:-2, :]
    gx[:, 1:-1] = lr[:, 2:] - lr[:, :-2]
    mag = np.sqrt(np.nan_to_num(gy, nan=0.0) ** 2 + np.nan_to_num(gx, nan=0.0) ** 2)
    ok = v & np.isfinite(gy) & np.isfinite(gx)
    return mag, ok


def calibrate_edge_threshold(mags: list, percentile: float = EDGE_PERCENTILE) -> float:
    """One edge threshold for a clip, from the pooled REFERENCE gradient."""
    if not mags:
        return EDGE_LOG_FLOOR
    pool = np.concatenate([np.asarray(m).ravel() for m in mags])
    pool = pool[np.isfinite(pool)]
    if pool.size == 0:
        return EDGE_LOG_FLOOR
    return float(max(np.percentile(pool, percentile), EDGE_LOG_FLOOR))


def geometric_edges(range_field: np.ndarray, valid: np.ndarray,
                    threshold: float) -> np.ndarray:
    """(H,W) bool edge map, from the gradient of log range. Scale-invariant."""
    mag, ok = log_range_gradient(range_field, valid)
    return ok & (mag > threshold)


def _chamfer(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """Median and 95th-percentile nearest-neighbour distance from set a to set b.

    `a` and `b` are BOOLEAN edge maps, so emptiness is `.any()`, not `.size` —
    a frame with no detected edge on either side is a real outcome (a flat sand
    plane has no geometric boundary) and comes back NaN rather than 0.
    """
    if not a.any() or not b.any():
        return float("nan"), float("nan")
    # Distance transform of b, evaluated at a. Done with a simple BFS-free
    # approach: scipy is available in .venv-eval and its EDT is exact.
    from scipy import ndimage
    d = ndimage.distance_transform_edt(~b)
    vals = d[a]
    return float(np.median(vals)), float(np.percentile(vals, 95))


def m4_boundary(pred_range, pred_valid, ref_range, ref_valid,
                threshold: float) -> dict:
    """Symmetric boundary-localisation distance, in evaluation-grid pixels.

    Reported in normalised image units too (fraction of the short side), so the
    number means the same thing on a landscape and a portrait clip.
    """
    ep = geometric_edges(pred_range, pred_valid, threshold)
    er = geometric_edges(ref_range, ref_valid, threshold)
    h, w = ep.shape
    short = float(min(h, w))
    p2r_med, p2r_p95 = _chamfer(ep, er)
    r2p_med, r2p_p95 = _chamfer(er, ep)
    out = {
        "edge_fraction_pred": float(ep.mean()),
        "edge_fraction_ref": float(er.mean()),
        "pred_to_ref_median_px": p2r_med, "pred_to_ref_p95_px": p2r_p95,
        "ref_to_pred_median_px": r2p_med, "ref_to_pred_p95_px": r2p_p95,
        "threshold_log": threshold,
        "grid_hw": [h, w],
    }
    both = [x for x in (p2r_med, r2p_med) if np.isfinite(x)]
    sym = float(np.mean(both)) if both else float("nan")
    out["symmetric_median_px"] = sym
    out["symmetric_median_norm"] = float(sym / short) if short else float("nan")
    out["_note"] = ("edges are the thresholded gradient of LOG range, so the "
                    "construction is invariant to the global scale gauge; the threshold is "
                    "calibrated once per clip from the pooled REFERENCE gradient and then "
                    "applied unchanged to both sides; distances are exact Euclidean "
                    "distance transforms on the evaluation grid")
    return out


# --------------------------------------------------------------------------
# M-5 — foreground/background ordinal violations
# --------------------------------------------------------------------------

#: Relative margins at which the reference asserts a real ordering. A pair whose
#: reference ranges differ by less than the margin is NOT counted, because the
#: reference itself cannot be trusted to order it.
ORDINAL_MARGINS = [0.05, 0.10, 0.25, 0.50]
ORDINAL_PAIRS = 200_000


def m5_ordinal(pred_range, ref_range, valid,
               margins=None, n_pairs: int = ORDINAL_PAIRS, seed: int = 0) -> dict:
    """Fraction of ordered reference pairs whose predicted order is INVERTED.

    Highly ambiguity-resistant: no monotone transform of the prediction — no
    scale, no shift, no inversion done consistently — can change an ordering, so
    this measures something no alignment could have supplied.

    Pairs are drawn from a seeded RNG so the sample is reproducible frame to
    frame and model to model.
    """
    margins = list(margins or ORDINAL_MARGINS)
    p = np.asarray(pred_range, dtype=np.float64).ravel()
    r = np.asarray(ref_range, dtype=np.float64).ravel()
    v = np.asarray(valid, dtype=bool).ravel() & np.isfinite(p) & np.isfinite(r) \
        & (p > 0) & (r > 0)
    idx = np.flatnonzero(v)
    if idx.size < 2:
        return {"n_valid": int(idx.size), "margins": {}}
    rng = np.random.default_rng(seed)
    i = rng.choice(idx, size=n_pairs, replace=True)
    j = rng.choice(idx, size=n_pairs, replace=True)
    keep = i != j
    i, j = i[keep], j[keep]
    ri, rj = r[i], r[j]
    pi, pj = p[i], p[j]
    rel = np.abs(ri - rj) / np.minimum(ri, rj)
    out = {"n_valid": int(idx.size), "n_pairs_drawn": int(i.size), "margins": {}}
    for m in margins:
        sel = rel >= m
        n = int(sel.sum())
        if n == 0:
            out["margins"][str(m)] = {"n": 0, "violation_rate": float("nan")}
            continue
        ref_order = np.sign(ri[sel] - rj[sel])
        pred_order = np.sign(pi[sel] - pj[sel])
        out["margins"][str(m)] = {
            "n": n,
            "violation_rate": float(np.mean(pred_order != ref_order)),
        }
    out["_note"] = ("pairs whose reference ranges differ by less than the margin are NOT "
                    "counted: the reference cannot be trusted to order them")
    return out


# --------------------------------------------------------------------------
# M-6 — radial image-position error
# --------------------------------------------------------------------------

RADIAL_EDGES = np.array([0.0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.5])


def m6_radial(pred_range, ref_range, radius: np.ndarray,
              edges: np.ndarray | None = None) -> dict:
    """Relative range error as a function of normalised radius from the principal point.

    Purpose (FREEZE 6): detect error that GROWS toward the frame boundary, which
    is the signature of a wide-FOV projection mismatch, a flat-port/noncentral
    camera mismatch, a z-depth/range confusion, or a calibration/postprocessing
    error. M-6 is the trigger for the camera-model challengers, so it is
    reported as a profile and as an explicit inner-to-outer ratio rather than as
    a single number.
    """
    edges = RADIAL_EDGES if edges is None else np.asarray(edges)
    err = np.abs(relative_error(pred_range, ref_range)).ravel()
    rad = np.asarray(radius, dtype=np.float64).ravel()
    prof = g3.binned_profile(rad, err, edges)
    inner = [b for b in prof if b["hi"] <= 0.4 and b["n"] > 0]
    outer = [b for b in prof if b["lo"] >= 0.8 and b["n"] > 0]
    def pooled(bins):
        if not bins:
            return float("nan")
        num = sum(b["median"] * b["n"] for b in bins)
        den = sum(b["n"] for b in bins)
        return float(num / den) if den else float("nan")
    i_med, o_med = pooled(inner), pooled(outer)
    return {
        "profile": prof,
        "edges": [float(x) for x in edges],
        "inner_median_abs_rel": i_med,
        "outer_median_abs_rel": o_med,
        "outer_over_inner": float(o_med / i_med) if (np.isfinite(i_med) and i_med > 0)
                            else float("nan"),
        "_note": ("radius is normalised by half the SHORT side, so the same number means "
                  "roughly the same off-axis angle on landscape and portrait clips; "
                  "corners exceed 1.0"),
    }
