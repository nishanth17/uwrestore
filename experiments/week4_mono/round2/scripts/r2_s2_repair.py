"""Round 2, Parts A and B — the two Round-1 semantic repairs, measured.

EXPLORATORY. Runs in `.venv-eval`; touches no model stack, only persisted
predictions. Writes ONLY under `round2/`. Round-1 deliverables are read, never
modified.

WHAT WAS WRONG. Round 1 settled `da3mono_large`'s z-depth-vs-range convention by
RESIDUAL — it fitted both hypotheses and kept the smaller error — and got
`range` on a 1.11 margin with 3 of 6 clips agreeing. That is not evidence about
what the model emits. The reference implementation says what it emits:

    src/depth_anything_3/utils/geometry.py:271 unproject(coordinates, z, intrinsics)
        ray_directions = K^-1 @ homogenize(coordinates)      # NOT normalised
        return ray_directions * z[..., None]
    src/depth_anything_3/utils/geometry.py:359 pixel_space_to_camera_space(...)
        camera_space_points = (K^-1 @ [u,v,1]) * depth

`K^-1 [u,v,1]` has third component exactly 1, so the scalar that multiplies it is
the CAMERA-AXIS Z COORDINATE. `DA3MONO-LARGE`'s depth is projective z-depth, and
the parameter is even named `z`. Source evidence beats a residual, so the
convention is asserted here from the code and the old residual test is retained
only as a diagnostic showing how badly it misled.

DA V2 gets the same treatment for the same reason: its relative output is
disparity, i.e. inverse DEPTH in the MDE dataset sense (z), so the reference goes
into disparity as `q_ref = 1/z_ref` rather than `1/r_ref`.

THE RAY FIELD. Both repairs need one provisional camera, and it must be the one
already frozen, not a new one:

    rho(x) = || K_eval^-1 [u, v, 1] ||        (evalgrid.K_source_to_eval of the
                                               Week-3 reference K, on the shared
                                               evaluation grid)
    z_ref  = r_ref / rho(x)

`g3.ray_length_factor` IS rho — Week 3's own `range = z * factor`. It is a
provisional CENTRAL-camera approximation pre-C2: no refraction, no port model,
and the reference's K is itself part of the Week-3 hypothesis.

NOTHING NEW IS FITTED HERE THAT S2 DID NOT ALREADY FIT. `policy.Policy` has
carried a `z_depth` convention and applied the secant on the range side since
Round 1; the repair is a CONVENTION CHANGE, not a new code path, which is why
S3-S6 need only be re-run with a different policy file.

    experiments/week4_mono/.venv-eval/bin/python \\
        -m experiments.week4_mono.round2.scripts.r2_s2_repair --overwrite
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week3_geometry.phase3a import geometry as g3  # noqa: E402
from experiments.week4_mono.round1 import alignment, common  # noqa: E402
from experiments.week4_mono.round1.scripts import s2_ambiguity as s2  # noqa: E402

R2 = os.path.join(common.W4, "round2")
R2_OUT = os.path.join(R2, "outputs")

#: The two arms Round 1 read under the wrong convention, and the corrected one,
#: asserted from the released source rather than from a residual.
REPAIRS = {
    "da3mono_large": {
        "corrected_convention": "z_depth",
        "old_convention": "range",
        "evidence": (
            "Depth-Anything-3 src/depth_anything_3/utils/geometry.py:271 "
            "`unproject(coordinates, z, intrinsics)` builds "
            "`ray_directions = K^-1 @ homogenize(coordinates)` WITHOUT normalising "
            "and returns `ray_directions * z`; :359 `pixel_space_to_camera_space` "
            "does the same as `camera_space_points * depth`. `K^-1 [u,v,1]` has "
            "third component 1, so the multiplying scalar is the camera-axis Z "
            "coordinate. The parameter is literally named `z`."),
    },
    "dav2_small": {
        "corrected_convention": "z_depth",
        "old_convention": "range",
        "evidence": (
            "Depth Anything V2 emits relative DISPARITY, i.e. inverse depth in the "
            "monocular-depth dataset sense, where 'depth' is the projective z "
            "coordinate (KITTI/NYU/Hypersim targets are all z). The affine "
            "ambiguity is therefore legal in 1/z, so the reference enters the fit "
            "as q_ref = 1/z_ref, not 1/r_ref. Round 1's residual test returned "
            "INDISTINGUISHABLE here (margin 1.0185), which is itself the finding: "
            "the model's shape error exceeds this camera's 35 % radial term."),
    },
}

#: Predeclared SENSITIVITY diagnostic for DA V2 only (task: "DA V2 FITTING
#: DISCIPLINE"). Equal total weight across near/mid/far reference bands, so a
#: fit dominated by how the scene happens to sample range can be told apart from
#: a fit dominated by the model. It NEVER replaces the primary frozen fit.
SENSITIVITY_BANDS = 3


def _weighted_huber(A, y, w0, iters: int = 12, c: float = 1.345):
    """`_huber_irls` with a fixed prior weight per sample. Same estimator otherwise."""
    sw = np.sqrt(w0)
    coef, *_ = np.linalg.lstsq(A * sw[:, None], y * sw, rcond=None)
    for _ in range(iters):
        r = y - A @ coef
        s = 1.4826 * np.median(np.abs(r - np.median(r)))
        if not np.isfinite(s) or s <= 0:
            break
        z = np.abs(r) / (c * s)
        w = w0 * np.where(z <= 1.0, 1.0, 1.0 / np.maximum(z, 1e-12))
        sw2 = np.sqrt(w)
        new, *_ = np.linalg.lstsq(A * sw2[:, None], y * sw2, rcond=None)
        if np.allclose(new, coef, rtol=1e-10, atol=1e-12):
            coef = new
            break
        coef = new
    return coef


def band_balanced_affine_disparity(q_pred, q_ref, ref_range, n_bands=SENSITIVITY_BANDS):
    """SENSITIVITY ONLY. Range-balanced affine-disparity fit, same objective space.

    The OBJECTIVE is unchanged — still `q_ref ~= a*q_pred + b` in native disparity
    — only the sample weighting changes, so this cannot smuggle in the log-depth
    or z-space objective the task forbids. It answers one question: is the primary
    fit being driven by the model or by how this clip happens to sample range?
    """
    good = np.isfinite(q_pred) & np.isfinite(q_ref) & np.isfinite(ref_range)
    if good.sum() < 8:
        return None
    P, R, RR = q_pred[good], q_ref[good], ref_range[good]
    edges = np.quantile(RR, np.linspace(0, 1, n_bands + 1))
    edges[0] -= 1e-9
    band = np.clip(np.digitize(RR, edges[1:-1]), 0, n_bands - 1)
    w = np.zeros_like(RR)
    for b in range(n_bands):
        m = band == b
        if m.any():
            w[m] = 1.0 / m.sum()
    A = np.stack([P, np.ones_like(P)], axis=1)
    a, bb = _weighted_huber(A, R, w)
    return {"a": float(a), "b": float(bb), "n_used": int(good.sum()),
            "n_bands": n_bands,
            "band_edges_ref_range_m": [float(x) for x in edges],
            "LABEL": "SENSITIVITY ONLY — never replaces the primary frozen S2 fit"}


def scale_only_zfit(z_pred, z_ref):
    """The retained diagnostic `z_ref = s * z_DA3`, so the shift's value is visible."""
    return alignment.fit_scale(z_pred, z_ref, scope="clip")


def analyse(model: str, clip: str, root: str) -> dict:
    """Everything Parts A/B ask for, for one arm on one clip, from persisted data."""
    data = s2.gather_clip(model, clip, root)
    if data["pred_native"].size == 0:
        return {"status": "no_overlapping_valid_samples"}
    kind = data["native_kind"]
    corrected = REPAIRS[model]["corrected_convention"]
    old = REPAIRS[model]["old_convention"]

    out = {
        "status": "ok",
        "native_kind": kind,
        "n_pooled_samples": int(data["pred_native"].size),
        "reference_scene_depth": {
            "median_ref_range_m": float(np.nanmedian(data["ref_range"])),
            "median_ref_z_m": float(np.nanmedian(data["ref_z"])),
            "p05_ref_range_m": float(np.nanpercentile(data["ref_range"], 5)),
            "p95_ref_range_m": float(np.nanpercentile(data["ref_range"], 95)),
            "median_rho": float(np.nanmedian(data["sec"])),
            "max_rho": float(np.nanmax(data["sec"])),
        },
        # Round 1's residual-based test, kept so the report can show what it said
        # and how much it mattered. It is NOT what decides the convention now.
        "old_residual_convention_test": s2.convention_test(data),
    }

    fams = s2.LEGAL_FAMILIES[kind]
    out["families_corrected"] = s2.family_comparison(data, fams, corrected)
    out["families_old"] = s2.family_comparison(data, fams, old)
    primary = ("affine_disparity" if kind == "disparity_relative" else "affine_depth")
    out["primary_family"] = primary
    out["trajectories_corrected"] = s2.trajectories(data, primary, corrected)
    out["trajectories_old"] = s2.trajectories(data, primary, old)

    if kind == "depth_relative":
        # Part A2: the corrected fit in NATIVE z-depth, plus the scale-only
        # diagnostic, plus what granting `t` actually bought.
        aff = alignment.fit_affine(data["pred_native"], data["ref_z"], "affine_depth")
        sc = scale_only_zfit(data["pred_native"], data["ref_z"])
        med_z = float(np.nanmedian(data["ref_z"]))
        a_err = out["families_corrected"]["affine_depth"]["median_abs_rel"]
        s_err = out["families_corrected"]["scale"]["median_abs_rel"]
        out["zdepth_fit"] = {
            "affine": aff.to_dict(),
            "scale_only": sc.to_dict(),
            "t_over_representative_scene_zdepth": (
                float(aff.params["t"] / med_z) if med_z > 0 else float("nan")),
            "representative_scene_zdepth_m": med_z,
            "residual_reduction_from_granting_t": (
                float((s_err - a_err) / s_err) if s_err > 0 else float("nan")),
            "scale_only_median_abs_rel": s_err,
            "affine_median_abs_rel": a_err,
        }

    if kind == "disparity_relative":
        q_ref_corr = alignment.to_disparity(data["ref_z"])
        out["sensitivity_band_balanced"] = band_balanced_affine_disparity(
            data["pred_native"], q_ref_corr, data["ref_range"])

    out["coverage_mean"] = float(np.mean([c["coverage_vs_reference"]
                                          for c in data["coverage"]]))
    return out


def build_corrected_policy(src_path: str) -> dict:
    """The Round-1 frozen policy with ONLY the two conventions repaired."""
    with open(src_path) as fh:
        pol = json.load(fh)
    out = copy.deepcopy(pol)
    out["_comment"] = (
        "ROUND-2 CORRECTED alignment policy. Identical to the frozen Round-1 policy "
        "except that two conventions decided by RESIDUAL in Round 1 are now asserted "
        "from the released SOURCE CODE. Nothing else moved: same families, same "
        "clip-level scope, same reference. S3-S6 differ from Round 1 for these two "
        "arms and are byte-identical for every other arm.")
    out["stage"] = "R2-S2"
    out["derived_from"] = os.path.relpath(src_path, REPO_ROOT)
    out["repairs"] = {}
    for arm, spec in REPAIRS.items():
        e = out["arms"][arm]
        out["repairs"][arm] = {
            "old_convention": e["convention"],
            "old_convention_source": e["convention_source"],
            "new_convention": spec["corrected_convention"],
            "new_convention_source": "the released reference implementation's own source",
            "evidence": spec["evidence"],
        }
        e["convention"] = spec["corrected_convention"]
        e["convention_source"] = "SOURCE CODE (Round-2 Part A/B repair)"
        e["convention_evidence"] = spec["evidence"]
        e["ray_field"] = ("rho(x) = ||K_eval^-1 [u,v,1]||, K_eval = the Week-3 "
                          "reference K carried onto the shared evaluation grid by "
                          "evalgrid.K_source_to_eval. z_ref = r_ref / rho. "
                          "PROVISIONAL central-camera approximation pre-C2.")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="*", default=list(REPAIRS))
    ap.add_argument("--clips", nargs="*", default=None)
    ap.add_argument("--root", default=os.path.join(common.OUTPUTS, "predictions"))
    ap.add_argument("--source-policy",
                    default=os.path.join(common.RESULTS, "S2_alignment_policy.json"))
    ap.add_argument("--out", default=os.path.join(R2_OUT, "r2_s2", "r2_s2_raw.json"))
    ap.add_argument("--policy-out",
                    default=os.path.join(R2, "R2_S2_alignment_policy.json"))
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    clips = args.clips or common.CLIPS
    result = {"stage": "R2-S2 (Parts A and B)",
              "reference": common.REFERENCE_CONFIG,
              "reference_status": ("PROVISIONAL MULTI-VIEW HYPOTHESIS, not ground truth"),
              "ray_field": ("rho = ||K_eval^-1 [u,v,1]|| = g3.ray_length_factor(K_eval); "
                            "z_ref = r_ref / rho; PROVISIONAL central-camera "
                            "approximation, no refraction/port model"),
              "repairs": {k: dict(v) for k, v in REPAIRS.items()},
              "models": {}}
    for model in args.models:
        rec = {"clips": {}}
        for clip in clips:
            rec["clips"][clip] = analyse(model, clip, args.root)
            e = rec["clips"][clip]
            if e.get("status") == "ok":
                pf = e["primary_family"]
                print(f"[R2-S2] {model:16s} {clip:15s} "
                      f"corrected={e['families_corrected'][pf]['median_abs_rel']:.4f} "
                      f"old={e['families_old'][pf]['median_abs_rel']:.4f} "
                      f"(old residual verdict "
                      f"{e['old_residual_convention_test']['verdict']})")
        result["models"][model] = rec

    common.write_json(args.out, result, overwrite=args.overwrite)
    pol = build_corrected_policy(args.source_policy)
    common.write_json(args.policy_out, pol, overwrite=args.overwrite)
    print(f"[R2-S2] -> {os.path.relpath(args.out, REPO_ROOT)}")
    print(f"[R2-S2] -> {os.path.relpath(args.policy_out, REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
