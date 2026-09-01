"""Stage 7 — restoration-oriented range-sensitivity proxy.

EXPLORATORY. Main project venv (numpy only). Bounded ANALYTICAL/synthetic study.
It does NOT implement backscatter removal or attenuation inversion — Weeks 5-6
own those. It answers one question:

    what kind and magnitude of range error changes the restored radiance
    enough to matter, and which kinds cost nothing?

Model (the project's standing image-formation model):

    I_c = J_c * exp(-b_att_c * d) + Binf_c * (1 - exp(-b_bs_c * d))

Restoration inverts it with the ESTIMATED range d_hat:

    J_hat_c = (I_c - Binf_c * (1 - exp(-b_bs_c * d_hat))) / exp(-b_att_c * d_hat)

Two results the whole week's priorities rest on, checked here numerically
rather than asserted:

1. A GLOBAL scale error is EXACTLY absorbable while the coefficients are freely
   fitted within a clip: d -> s*d together with b -> b/s leaves I unchanged, so
   the refit recovers J exactly. It stops being free only when b must be
   physically meaningful, is shared across clips, or when Week 6B adds a light
   with distance-dependent falloff.
2. A SPATIALLY VARYING error is not absorbable by anything, and because b_att
   differs per channel the same relative range error produces a different gain
   error per channel — i.e. a COLOUR error, not just a brightness error. That is
   why Week 3 weights shape error far above scale error.

Usage:
    .venv/bin/python -m experiments.week3_geometry.scripts.restoration_sensitivity \
        --out experiments/week3_geometry/outputs/stage7/sensitivity.json
"""

from __future__ import annotations

import argparse
import json
import os

import numpy as np

# Attenuation coefficients, 1/m. Bracketing values from the standard Jerlov
# water-type picture rather than a fit to this project's footage -- Week 6 fits
# the real ones. Three regimes are swept so the conclusion is not an artefact of
# one choice.
WATER_TYPES = {
    "clear_oceanic": {"b_att": [0.35, 0.09, 0.08], "b_bs": [0.30, 0.11, 0.10]},
    "coastal": {"b_att": [0.55, 0.20, 0.19], "b_bs": [0.45, 0.22, 0.22]},
    "turbid_coastal": {"b_att": [0.85, 0.45, 0.48], "b_bs": [0.70, 0.50, 0.55]},
}
RANGES_M = [0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 12.0]
REL_ERRORS = [-0.20, -0.10, -0.05, 0.05, 0.10, 0.20]
CHANNELS = ("R", "G", "B")


def forward(J, b_att, b_bs, Binf, d):
    return J * np.exp(-b_att * d) + Binf * (1.0 - np.exp(-b_bs * d))


def invert(I, b_att, b_bs, Binf, d_hat):
    return (I - Binf * (1.0 - np.exp(-b_bs * d_hat))) / np.exp(-b_att * d_hat)


def relative_J_error(J, b_att, b_bs, Binf, d_true, d_hat):
    I = forward(J, b_att, b_bs, Binf, d_true)
    return invert(I, b_att, b_bs, Binf, d_hat) / J - 1.0


def global_scale_is_absorbable(J=0.4, Binf=0.25) -> dict:
    """Numerically confirm result 1 above, and show what it costs without a refit."""
    rows = []
    for wname, w in WATER_TYPES.items():
        for c, (ba, bb) in enumerate(zip(w["b_att"], w["b_bs"])):
            for d in RANGES_M:
                for s in (0.7, 0.85, 1.18, 1.43, 3.2):
                    I = forward(J, ba, bb, Binf, d)
                    # (a) coefficients refitted inside the clip: b -> b/s
                    J_refit = invert(I, ba / s, bb / s, Binf, s * d)
                    # (b) coefficients NOT refitted (transferred / physical b)
                    J_norefit = invert(I, ba, bb, Binf, s * d)
                    rows.append({
                        "water": wname, "channel": CHANNELS[c], "range_m": d, "scale": s,
                        "rel_error_with_coefficient_refit": float(J_refit / J - 1.0),
                        "rel_error_without_refit": float(J_norefit / J - 1.0),
                    })
    refit = np.array([abs(r["rel_error_with_coefficient_refit"]) for r in rows])
    norefit = np.array([abs(r["rel_error_without_refit"]) for r in rows])
    return {
        "max_abs_relative_error_with_refit": float(refit.max()),
        "median_abs_relative_error_without_refit": float(np.median(norefit)),
        "max_abs_relative_error_without_refit": float(norefit.max()),
        "max_without_refit_is_a_divergence_not_a_number": (
            "The 'max' above is dominated by the inversion's own exponential "
            "divergence: with the coefficients unrefitted, the corrective gain is "
            "exp(+b_att * s * d), which at s=3.2 and d=12 m in turbid water is "
            "e^32 -- the restored value is meaningless rather than merely wrong. "
            "Read the MEDIAN as the representative figure, and read the max as a "
            "reminder that unbounded corrective gain is itself a failure mode that "
            "Weeks 5-6 will have to clamp."),
        "verdict": ("A global range scale error is absorbed EXACTLY (to numerical "
                    "precision) when the attenuation and backscatter coefficients are "
                    "refitted within the clip, and is NOT absorbed at all when they "
                    "are transferred or required to be physically meaningful. This is "
                    "why Phase 3A does not rank methods on scale, and why a metric "
                    "anchor only becomes valuable once beta must mean something."),
        "rows": rows,
    }


def local_shape_sensitivity(J=0.4, Binf=0.25) -> list:
    """Relative restored-radiance error from a LOCAL relative range error."""
    rows = []
    for wname, w in WATER_TYPES.items():
        for d in RANGES_M:
            for eps in REL_ERRORS:
                per_c = {}
                for c, (ba, bb) in enumerate(zip(w["b_att"], w["b_bs"])):
                    e = relative_J_error(J, ba, bb, Binf, d, d * (1.0 + eps))
                    per_c[CHANNELS[c]] = float(e)
                # A range error that hit every channel equally would only change
                # brightness. What actually damages a restoration is the SPREAD
                # between channels, which is a colour error and is what a
                # white-balance stage cannot undo without also being wrong.
                vals = np.array(list(per_c.values()))
                rows.append({
                    "water": wname, "range_m": d, "range_rel_error": eps,
                    "rel_J_error": per_c,
                    "channel_spread_max_minus_min": float(vals.max() - vals.min()),
                    "red_over_blue_gain_error": float(
                        (1 + per_c["R"]) / (1 + per_c["B"]) - 1.0),
                    "worst_channel_abs": float(np.abs(vals).max()),
                })
    return rows


def error_budget(rows: list, thresholds=(0.02, 0.05, 0.10)) -> dict:
    """The reusable output: what range error is negligible / tolerable / dangerous.

    For each water type and range, the smallest |relative range error| whose
    worst-channel restored-radiance error crosses each threshold, found by
    solving on a fine grid rather than interpolating the coarse sweep.
    """
    out = {}
    eps_grid = np.linspace(0.001, 0.60, 600)
    for wname, w in WATER_TYPES.items():
        for d in RANGES_M:
            worst = np.zeros_like(eps_grid)
            for c, (ba, bb) in enumerate(zip(w["b_att"], w["b_bs"])):
                e = np.array([abs(relative_J_error(0.4, ba, bb, 0.25, d, d * (1 + x)))
                              for x in eps_grid])
                worst = np.maximum(worst, e)
            entry = {}
            for t in thresholds:
                hit = np.flatnonzero(worst >= t)
                entry[f"range_error_reaching_{int(t*100)}pct_radiance_error"] = (
                    float(eps_grid[hit[0]]) if hit.size else None)
            out[f"{wname}@{d}m"] = entry
    return out


def spatial_error_forms(J=0.4, Binf=0.25) -> list:
    """Named spatially structured error forms, not just iid noise.

    Each is evaluated across the frame's range span, because the thing that
    makes these dangerous is precisely that they do NOT average out.
    """
    d = np.array([0.5, 1.0, 2.0, 3.0, 5.0, 8.0, 12.0])
    forms = {
        "range_dependent_bias_g=+0.3": lambda x: x * (1 + 0.3 * x / x.max()),
        "range_dependent_bias_g=-0.3": lambda x: x * (1 - 0.3 * x / x.max()),
        "radial_bias_+10pct_at_edge": lambda x: x * 1.10,   # evaluated as the edge case
        "uniform_+10pct": lambda x: x * 1.10,
    }
    rows = []
    for wname, w in WATER_TYPES.items():
        for fname, f in forms.items():
            dh = f(d)
            per_c = {}
            for c, (ba, bb) in enumerate(zip(w["b_att"], w["b_bs"])):
                e = relative_J_error(J, ba, bb, Binf, d, dh)
                per_c[CHANNELS[c]] = {"median": float(np.median(e)),
                                      "max_abs": float(np.abs(e).max()),
                                      "near_0.5m": float(e[0]),
                                      "far_12m": float(e[-1])}
            rows.append({"water": wname, "form": fname, "rel_J_error": per_c,
                         "near_to_far_swing_R": float(per_c["R"]["far_12m"]
                                                      - per_c["R"]["near_0.5m"])})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    if os.path.exists(args.out) and not args.overwrite:
        raise SystemExit(f"refusing to overwrite {args.out!r} (pass --overwrite)")

    local = local_shape_sensitivity()
    payload = {
        "_comment": ("Week 3 Stage 7 restoration-relevance sensitivity proxy. Analytical/"
                     "synthetic only: NO backscatter estimation and NO attenuation "
                     "inversion was performed on real footage. Coefficients are "
                     "bracketing Jerlov-style water types, not fits to this project's "
                     "clips -- the point is the SHAPE of the sensitivity, not the "
                     "numbers' provenance."),
        "model": "I = J*exp(-b_att*d) + Binf*(1 - exp(-b_bs*d))",
        "assumed_J": 0.4,
        "assumed_Binf": 0.25,
        "water_types": WATER_TYPES,
        "global_scale": global_scale_is_absorbable(),
        "local_shape_sensitivity": local,
        "error_budget": error_budget(local),
        "spatial_error_forms": spatial_error_forms(),
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(payload, fh, indent=2)

    g = payload["global_scale"]
    print(f"global scale, WITH coefficient refit: max |dJ/J| = "
          f"{g['max_abs_relative_error_with_refit']:.2e}  (i.e. free)")
    print(f"global scale, WITHOUT refit:          median |dJ/J| = "
          f"{g['median_abs_relative_error_without_refit']:.2%}, "
          f"max {g['max_abs_relative_error_without_refit']:.2%}")
    print("\nlocal (unabsorbable) range error -> worst-channel restored-radiance error:")
    print(f"{'water':<16}{'range':>7}", end="")
    for e in REL_ERRORS:
        print(f"{e:+.0%}".rjust(9), end="")
    print()
    for wname in WATER_TYPES:
        for d in (1.0, 3.0, 8.0):
            print(f"{wname:<16}{d:>6.1f}m", end="")
            for e in REL_ERRORS:
                row = next(r for r in local if r["water"] == wname
                           and r["range_m"] == d and r["range_rel_error"] == e)
                print(f"{row['worst_channel_abs']:>8.1%} ", end="")
            print()
    print("\nrange error at which worst-channel radiance error reaches 5%:")
    for k, v in payload["error_budget"].items():
        val = v["range_error_reaching_5pct_radiance_error"]
        print(f"  {k:<28} {('%.1f%%' % (100*val)) if val else '>60%'}")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
