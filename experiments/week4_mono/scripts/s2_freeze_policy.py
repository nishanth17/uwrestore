"""S2 — turn the measured ambiguity evidence into the FROZEN alignment policy.

EXPLORATORY. Runs in `.venv-eval`.

Reads `outputs/s2/s2_raw.json` (the measurements) and writes
`results/S2_alignment_policy.json` (the decision) plus `results/S2_AMBIGUITY.md`.

The split is deliberate. `s2_ambiguity.py` measures and takes no decisions;
this script takes the decisions and records the evidence each one rests on. A
later reader can therefore check whether the policy follows from the numbers,
which is not possible if measurement and decision are the same pass.

DECISION RULES, all fixed before the numbers were seen:

  * `family` is the one FREEZE §3/§5 declares legal for the arm's native
    representation. It is never widened because a larger group scores better —
    the whole point of E1 is to grant the model exactly its documented
    ambiguity and no more.

  * `convention` (z-depth vs range) is decided by measurement for the two models
    that state none, and by the model's own semantics for everyone else. A
    verdict needs a >=3 % residual margin; anything closer is INDISTINGUISHABLE
    and defaults to `range`, the project's canonical quantity, with the tie
    recorded.

  * `scope` is clip-level for every arm. Per-frame fitting is a diagnostic only:
    Week 3 established that renormalising each frame erases temporal scale
    drift, and FREEZE C7 makes that drift a first-class failure mode rather
    than a nuisance.

    experiments/week4_mono/.venv-eval/bin/python \\
        -m experiments.week4_mono.scripts.s2_freeze_policy --overwrite
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week4_mono import armio, common, policy  # noqa: E402
from experiments.week4_mono.scripts.s0_report import md_table  # noqa: E402
from experiments.week4_mono.scripts.s2_ambiguity import LEGAL_FAMILIES  # noqa: E402

#: The one family S3-S6 will actually fit, per native representation. This is
#: the model's DOCUMENTED legal ambiguity, not the best-scoring group.
PRIMARY_FAMILY = {
    "depth_along_ray_metric": "scale",
    "pointmap_metric": "scale",
    "pointmap": "scale",
    "depth_relative": "affine_depth",
    "disparity_relative": "affine_disparity",
}

FAMILY_RATIONALE = {
    "scale": ("The arm emits a point map or a camera-centre range and claims metric "
              "scale. The oracle scale is a DIAGNOSTIC granting the one gauge a "
              "shared clip-level physical model can absorb (FREEZE C7), not a "
              "deployment entitlement; the raw metric output is retained separately "
              "and judged post-C2."),
    "affine_depth": ("Affine-in-depth / Class 3 from the primary source: the DA3 teacher "
                     "outputs scale-shift-invariant DEPTH and the monocular student is "
                     "trained from those targets (FREEZE C1). The scale-only subgroup is "
                     "tested empirically; only measured evidence may earn an "
                     "'approximately scale-only' description."),
    "affine_disparity": ("The ambiguity lives in DISPARITY, so the transform is fitted "
                         "there and inverted afterwards. Fitting a*d+b in physical depth "
                         "would be a DIFFERENT transform group, not a stricter one."),
}


def summarise_convention(model_rec: dict) -> dict:
    """Pool the per-clip convention tests into one verdict for the model."""
    zz, rr, per_clip = [], [], {}
    for clip, e in model_rec["clips"].items():
        ct = e.get("convention_test")
        if not ct:
            continue
        z = ct["z_depth"]["median_abs_rel_vs_reference_range"]
        r = ct["range"]["median_abs_rel_vs_reference_range"]
        zz.append(z)
        rr.append(r)
        per_clip[clip] = {"z_depth_abs_rel": z, "range_abs_rel": r,
                          "verdict": ct["verdict"], "margin_ratio": ct["margin_ratio"]}
    if not zz:
        return {}
    z_med, r_med = float(np.median(zz)), float(np.median(rr))
    if z_med < r_med * 0.97:
        verdict, why = "z_depth", "the z-depth hypothesis leaves the smaller residual"
    elif r_med < z_med * 0.97:
        verdict, why = "range", "the range hypothesis leaves the smaller residual"
    else:
        verdict, why = "range", ("the two hypotheses are indistinguishable at the 3 % "
                                 "margin; defaulted to the project's canonical range, "
                                 "and the tie is recorded")
    return {"verdict": verdict, "why": why,
            "pooled_z_depth_abs_rel": z_med, "pooled_range_abs_rel": r_med,
            "margin_ratio": float(max(z_med, r_med) / min(z_med, r_med)),
            "per_clip": per_clip,
            "n_clips_agreeing": int(sum(1 for v in per_clip.values()
                                        if v["verdict"] == verdict))}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", default=os.path.join(common.OUTPUTS, "s2", "s2_raw.json"))
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    with open(args.raw) as fh:
        raw = json.load(fh)

    entries, evidence = {}, {}
    for model, rec in raw["models"].items():
        kind = rec.get("native_kind")
        if kind is None:
            continue
        fam = PRIMARY_FAMILY[kind]
        conv = summarise_convention(rec)
        convention = conv.get("verdict", "range")
        entries[model] = {
            "native_kind": kind,
            "family": fam,
            "family_rationale": FAMILY_RATIONALE[fam],
            "convention": convention,
            "convention_source": ("MEASURED in S2" if conv else
                                  "the model's own verified semantics (S0)"),
            "scope": "clip",
            "legal_families_considered": LEGAL_FAMILIES[kind],
        }
        ev = {"convention": conv}
        # What the larger group bought, pooled across clips.
        gains = [e["families"].get("_subgroup_gain") for e in rec["clips"].values()
                 if isinstance(e, dict) and "families" in e]
        gains = [g for g in gains if g]
        if gains:
            ev["subgroup_gain"] = {
                "per_clip_relative_gain_from_shift":
                    [g["relative_gain_from_shift"] for g in gains],
                "median_relative_gain_from_shift":
                    float(np.median([g["relative_gain_from_shift"] for g in gains])),
            }
        # Scale trajectories: the C7 quantity S5 will need.
        traj = {}
        for clip, e in rec["clips"].items():
            t = (e.get("trajectories") or {}).get("scale_trajectory")
            if t:
                traj[clip] = t
        if traj:
            ev["scale_trajectory_by_clip"] = traj
            ev["clip_to_clip_scale_spread"] = float(
                max(t["median"] for t in traj.values()) /
                min(t["median"] for t in traj.values()))
        # Raw metric behaviour, RECORDED pre-C2 and judged post-C2.
        raw_absrel, aligned_absrel = {}, {}
        for clip, e in rec["clips"].items():
            f = e.get("families", {})
            if "none" in f:
                raw_absrel[clip] = f["none"]["median_abs_rel"]
            if fam in f:
                aligned_absrel[clip] = f[fam]["median_abs_rel"]
        ev["raw_median_abs_rel_by_clip"] = raw_absrel
        ev["aligned_median_abs_rel_by_clip"] = aligned_absrel
        ev["coverage_by_clip"] = {
            clip: float(np.mean([c["coverage_vs_reference"] for c in e["coverage"]]))
            for clip, e in rec["clips"].items() if isinstance(e, dict) and "coverage" in e}
        evidence[model] = ev

    # FoundationGeo's ablation arms inherit its policy: they are the same
    # representation from the same checkpoint, and giving an ablation arm a
    # different alignment would confound the intervention with the alignment.
    if "foundationgeo_11" in entries:
        base = entries["foundationgeo_11"]
        for arm in armio.FG_ARMS:
            entries[arm] = dict(base)
            entries[arm]["inherits_from"] = "foundationgeo_11"
            entries[arm]["role"] = armio.arm_role(arm)
            entries[arm]["family_rationale"] = (
                base["family_rationale"] +
                " This ablation arm inherits the primary arm's policy unchanged: it is the "
                "same representation from the same checkpoint, and aligning it differently "
                "would confound the intervention with the alignment.")

    pol = policy.Policy(entries, {
        "_comment": ("FROZEN Week-4A alignment policy. One policy, not one transform: the "
                     "legal E1 family depends on the native representation, and fitting a "
                     "single universal transform across representations is the standard way "
                     "to make a monocular comparison meaningless."),
        "stage": "S2",
        "scope": "clip-level for every arm; per-frame fits are DIAGNOSTICS ONLY",
        "scope_rationale": (
            "Week 3 established that renormalising each frame erases temporal scale drift, "
            "and FREEZE C7 makes that drift a first-class failure mode: a CONSTANT global "
            "scale bias is a benign gauge because the physical coefficients can be refit "
            "once (beta' = beta/s), whereas FRAME-VARYING drift would demand "
            "beta'_t = beta/s_t, i.e. water properties that change with the estimator."),
        "reference": common.REFERENCE_CONFIG,
        "reference_status": ("PROVISIONAL MULTI-VIEW HYPOTHESIS, not ground truth. Every "
                             "residual here is disagreement with the current Week-3 "
                             "hypothesis, never objective monocular error."),
        "e1_meaning": ("If the model's documented legal ambiguity were known, how good is "
                       "the remaining shape? The nuisance parameters consumed are reported "
                       "alongside, never hidden (FREEZE C9)."),
        "evidence": evidence,
    })
    out_pol = os.path.join(common.RESULTS, "S2_alignment_policy.json")
    if os.path.exists(out_pol) and not args.overwrite:
        raise SystemExit(f"refusing to overwrite {out_pol!r} (pass --overwrite)")
    pol.save(out_pol)

    # ------------------------------------------------------------------ md
    order = [m for m in common.MODELS if m in entries]
    rows = []
    for m in order:
        e, ev = entries[m], evidence[m]
        rows.append([m, e["native_kind"], e["family"], e["convention"],
                     e["convention_source"].split()[0], e["scope"]])

    L = []
    A = L.append
    A("# S2 — native ambiguity and the frozen alignment policy")
    A("")
    A("**Stage:** S2. **All seven models continue.** The policy written here is FROZEN")
    A("for S3-S6 and lives in `S2_alignment_policy.json`.")
    A("")
    A("What S2 freezes is a **policy, not a transform**. There is no alignment that is")
    A("legal for all seven entrants, and fitting one anyway is the standard way to make a")
    A("monocular comparison meaningless: Depth Anything V2's ambiguity lives in")
    A("*disparity*, and `a*d + b` in physical depth is not a stricter version of")
    A("`a*q + b` in disparity — it is a different group.")
    A("")
    A("Measurement and decision were separated on purpose. `s2_ambiguity.py` measures and")
    A("decides nothing; `s2_freeze_policy.py` decides and records the evidence each")
    A("decision rests on, so a reader can check that the policy follows from the numbers.")
    A("")
    A("## The frozen policy")
    A("")
    A(md_table(rows, ["arm", "native_kind", "E1 family", "convention",
                      "convention from", "scope"]))
    A("")
    A("FoundationGeo's three ablation arms (`fg_pre_ray`, `fg_post_ray`, and its primary")
    A("output as V4c's arm D) inherit this policy unchanged. They are the same")
    A("representation from the same checkpoint, and aligning an ablation arm differently")
    A("would confound the intervention with the alignment.")
    A("")
    A("**Scope is clip-level for every arm.** Per-frame fitting exists here only as a")
    A("diagnostic. Week 3 established that renormalising each frame erases temporal scale")
    A("drift, and FREEZE C7 makes that drift a first-class failure mode rather than a")
    A("nuisance: a *constant* global scale bias is benign, because the physical")
    A("coefficients can be refit once as `beta' = beta/s`; *frame-varying* drift would")
    A("demand `beta'_t = beta/s_t`, i.e. water properties that change with the estimator.")
    A("")

    # --- convention resolutions ---
    A("## The two conventions S0 left open, settled by measurement")
    A("")
    for m in order:
        conv = evidence[m].get("convention")
        if not conv:
            continue
        A(f"### `{m}`")
        A("")
        A(f"- z-depth hypothesis: median abs-rel **{conv['pooled_z_depth_abs_rel']:.4f}**")
        A(f"- range hypothesis:   median abs-rel **{conv['pooled_range_abs_rel']:.4f}**")
        A(f"- margin ratio: **{conv['margin_ratio']:.3f}**, "
          f"agreeing clips: **{conv['n_clips_agreeing']}/{len(conv['per_clip'])}**")
        A(f"- **verdict: `{conv['verdict']}`** — {conv['why']}")
        A("")
    A("Both hypotheses differ by this camera's secant factor, which spans about 1.00 at")
    A("the principal point to 1.35 at the corners — a large, purely radial signal. A")
    A("model whose field is genuinely z-depth should be visibly better explained by the")
    A("z-hypothesis; one whose shape error already exceeds a 35 % radial term will come")
    A("back INDISTINGUISHABLE, and that is itself a finding about the model rather than a")
    A("failure of the test.")
    A("")

    # --- subgroup gain ---
    A("## Does the additive term earn its place? (FREEZE C1)")
    A("")
    any_gain = False
    for m in order:
        g = evidence[m].get("subgroup_gain")
        if not g:
            continue
        any_gain = True
        A(f"- **`{m}`** — median relative gain from granting the shift over scale-only: "
          f"**{g['median_relative_gain_from_shift']:+.3f}** "
          f"(per clip: {', '.join(f'{x:+.3f}' for x in g['per_clip_relative_gain_from_shift'])})")
    if not any_gain:
        A("- no arm had both subgroups fitted")
    A("")
    A("A gain near zero would license describing the checkpoint as behaving")
    A("**approximately scale-only on the tested domain** — a conclusion the freeze allows")
    A("only from data, never from architecture or from the presence of a")
    A("`least_squares_scale_scalar` utility in the release.")
    A("")

    # --- scale trajectories ---
    A("## Scale trajectories and clip-to-clip spread")
    A("")
    trows = []
    for m in order:
        ev = evidence[m]
        tj = ev.get("scale_trajectory_by_clip", {})
        if not tj:
            continue
        wander = [t["wander_ratio"] for t in tj.values()]
        lstd = [t["log_std"] for t in tj.values()]
        f2f = [t["frame_to_frame_log_mad"] for t in tj.values()]
        trows.append([m,
                      f"{ev.get('clip_to_clip_scale_spread', float('nan')):.3f}",
                      f"{np.median(wander):.3f}",
                      f"{max(wander):.3f}",
                      f"{np.median(lstd):.4f}",
                      f"{np.median(f2f):.4f}"])
    if trows:
        A(md_table(trows, ["arm", "clip-to-clip scale spread", "median within-clip wander",
                           "worst wander", "median log-std", "median frame-to-frame log MAD"]))
    A("")
    A("`wander` is the ratio of the largest to the smallest per-frame scale within a clip.")
    A("A value of 1.0 would mean one clip-level scale describes every frame. Anything")
    A("materially above 1.0 is frame-varying scale drift, which under a shared clip-level")
    A("physical model is **not** a benign gauge — S5 is where that gets its full treatment,")
    A("but the quantity is measured here so the frozen policy carries it.")
    A("")
    A("## Raw metric behaviour: RECORDED pre-C2, JUDGED post-C2")
    A("")
    rrows = []
    for m in order:
        ev = evidence[m]
        raws = [v for v in ev["raw_median_abs_rel_by_clip"].values() if np.isfinite(v)]
        algs = [v for v in ev["aligned_median_abs_rel_by_clip"].values() if np.isfinite(v)]
        covs = [v for v in ev["coverage_by_clip"].values() if np.isfinite(v)]
        rrows.append([m,
                      f"{np.median(raws):.4f}" if raws else "-",
                      f"{np.median(algs):.4f}" if algs else "-",
                      f"{np.median(covs):.3f}" if covs else "-"])
    A(md_table(rrows, ["arm", "raw median abs-rel", "E1-aligned median abs-rel",
                       "median coverage vs reference"]))
    A("")
    A("The raw column is the model's own scale against the Week-3 reference's own scale,")
    A("with no alignment at all. Pre-C2 a disagreement there **cannot** be attributed:")
    A("there is no independent anchor to say whether the monocular scale is wrong or the")
    A("Week-3 scale is. It is recorded and left unjudged, per FREEZE §7. The relative-only")
    A("models have no raw column by construction.")
    A("")
    A("## Cross-check: the reference is being read on the grid it was written on")
    A("")
    A("This session's independent S0 FOV measurement of MapAnything's preprocessing and")
    A("Week 3's own `preprocess_maps.json` agree to about 1e-11 in scale and 1e-8 px in")
    A("offset. That matters because every number in S3-S6 is a comparison against the")
    A("persisted Week-3 product, sampled through that map. Two independent measurements of")
    A("the same preprocessing agreeing to floating-point precision is the evidence that the")
    A("comparison is well-posed.")

    out_md = os.path.join(common.RESULTS, "S2_AMBIGUITY.md")
    if os.path.exists(out_md) and not args.overwrite:
        raise SystemExit(f"refusing to overwrite {out_md!r} (pass --overwrite)")
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    with open(out_md, "w") as fh:
        fh.write("\n".join(L) + "\n")

    print(f"[S2-policy] froze {len(entries)} arms")
    for m in order:
        e = entries[m]
        print(f"   {m:26s} {e['family']:18s} convention={e['convention']:8s} "
              f"scope={e['scope']}")
    print(f"  -> {os.path.relpath(out_pol, REPO_ROOT)}")
    print(f"  -> {os.path.relpath(out_md, REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
