"""Aggregate S6 into `results/S6_RESTORATION.md` and `results/S6_results.json`."""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week4_mono.round1 import common, restoration  # noqa: E402
from experiments.week4_mono.round1.scripts.s0_report import md_table  # noqa: E402


#: ROUND-1 DEFAULT. Written after actually viewing the sheets and worst-disagreement
#: crops listed in `outputs/s6/inspect/manifest.json` (CLAUDE.md invariant 5), for the
#: Round-1 two-arm run with the PRE-repair DA3 convention. A run with a different arm
#: set or corrected semantics must pass `--inspection-notes`. Frames viewed:
#: cenote_01 f000200 (sheet + worst crops 4,6 and 0,9), wreck_05 f000113,
#: wreck_07 f000109 (sheet + crops 1,2 and 0,8), wreck_03 f000317,
#: swimthrough_02 f000089, wreck_01 f001855.
INSPECTION_NOTES = """
**No hallucinated texture, by construction -- but hallucinated GEOMETRY arrives as
hallucinated colour.** The instrument is a per-pixel gain and offset; it cannot
invent detail, and scene identity survives intact in every restored frame. What a
range field CAN invent is structure, and one arm does. On `wreck_07` f000109
`da3mono_large` fills the thin lattice of the crane and rigging with a solid opaque
surface exactly where both the reference and `mapanything_n1` leave holes -- so
water seen THROUGH the lattice is restored as though it sat at the lattice's range.
That is the thin-structure failure mode expressed photometrically rather than as
texture, and it is the one finding here that touches scene identity.

**The worst disagreements sit where the image carries no evidence.** Both arms'
worst-disagreement crops on `cenote_01` land in the unlit cave void -- source tiles
that are essentially black. The reference places the void far; MapAnything and DA3
both pull it much nearer (crops 4,6 and 0,9). No monocular model can do better
there, and the reference is not obviously right either. What matters is that the
guess is UNSTABLE, and this is precisely the clip where MapAnything's temporal
delta E00 blows up (6.748 against an unprocessed-input control of 2.506) while
DA3's does not (2.806). A wandering guess in a black void still costs colour,
because the void's gain is where the inversion is most sensitive.

**On the near-planar clip the two error SHAPES are categorically different.**
`wreck_01` f001855: MapAnything's signed disagreement is a near-uniform field over
the entire frame -- a global offset, the benign gauge of FREEZE C7, absorbable by
`b -> b/s`. DA3's is a large smooth blob, neutral along the top edge and strongly
positive through the lower centre -- a genuine low-frequency deformation of the same
scene. The two restorations look nearly identical to the eye (both dark teal, both
with a red bloom in the far bottom-left corner), which is why the delta E00
separation on this clip is modest; the shapes say the errors are not the same kind
of thing.

**The dynamic subject.** `wreck_03` f000317, the diver. MapAnything reproduces the
silhouette and its range; its disagreement map is near-neutral across the whole
body. DA3 renders the diver as a solid strongly-positive region -- it places the
moving subject substantially farther than the reference -- and its restoration
shows the diver visibly warmer and redder than both the reference and MapAnything.
The one object a viewer actually looks at is the object DA3 displaces.

**Far-field over-gain is visible, not merely numerical.** `swimthrough_02` f000089:
DA3 puts the central swim-through channel much deeper than the reference, and the
restoration blows that channel out to a bright cyan while the reference and
MapAnything keep it continuous with the surrounding water. On the same frame the
reference range is riddled with holes tracing the fine coral branches while both
monocular arms are dense there -- so on reef footage a large part of what the
comparison CANNOT see is the reference's own missing data, excluded from the common
support rather than counted against anyone.

**Colour relationships are unnatural in EVERY arm, the reference included.** All
coastal restorations sit orange-brown against a green-blue source (red
over-corrected at around 7 m), and `wreck_01`'s far corner blooms red. That is the
fixed Jerlov-bracketing coefficients, not any range field -- Week 6 owns the
coefficients. It is recorded here so the S6 tables are not misread as a claim that
this restoration looks right. It is a differencing instrument, not a deliverable.

**Black regions in the restored panels are reference-invalid pixels and depth-edge
over-subtraction, not model output.** They are excluded from every number above.
"""

#: ROUND-1 DEFAULT, same caveat as INSPECTION_NOTES: pass `--classification` for any
#: other arm set.
CLASSIFICATION = """
Judged against the Week-3 error budget (LOG.md): the local relative range error at
which the worst channel's restored radiance error reaches 5% is 9.4% at 3 m and
6.1% at 8 m in the coastal regime, 12% and 8.5% clear oceanic. The directly
comparable measurement is the responsive-window median |relative radiance error|.

- `mapanything_n1`: **DEGRADED.** 3.9-19.0% radiance error in the responsive window
  across the six clips (median about 10%), roughly twice the 5% criterion. Colour
  difference is bounded and similar on every clip -- windowed median delta E00
  1.83-2.93, under the threshold at which most observers see a difference at all --
  and on the near-planar clip its disagreement is close to a pure global gauge,
  which is benign. Its one real hazard is temporal, not static: its responsive-window
  colour pumping is the higher of the two arms on five of six clips (1.72 on
  `wreck_05`, 1.11 and 1.09 on `wreck_01` and `swimthrough_02`), and on `cenote_01`
  it more than doubles the motion-compensated warp error against the reference-driven
  arm (0.02330 vs 0.00983) and lifts temporal delta E00 from 2.82 to 6.75. That is
  frame-varying scale drift, which no single fixed `b` can absorb.

- `da3mono_large`: **DEGRADED, and approaching UNSAFE on low-texture lateral
  footage.** 6.4-33.3% radiance error, up to six times the criterion. `wreck_05` is
  the failure: windowed median delta E00 7.78 with a p95 of 16.1 and 33% radiance
  error, which the sheet shows as a large smoothly-growing disagreement over the
  whole lower-right and a markedly bluer restoration. Two of its failures are
  scene-identity failures rather than photometric ones -- the thin lattice filled
  solid on `wreck_07`, the dynamic diver displaced on `wreck_03`. Counter-evidence,
  stated rather than buried: DA3 is the MORE temporally stable arm. Lower colour
  pumping on five of six clips, the only arm that does not degrade `cenote_01`
  relative to the reference, and on `wreck_01` its warp error at lag 8 (0.00710)
  beats the reference-driven arm's (0.00848).

Neither finalist is ADEQUATE against the Week-3 budget on this footage.

Three limits on how far that verdict travels:

1. **Pre-C2 the reference is a hypothesis, not ground truth.** The reference's own
   restoration health is worst on exactly the clips where disagreement is worst --
   responsive fraction 0.41 on `wreck_05` and `wreck_03`, with the inversion asking
   for p99 gains of 1e8. DEGRADED is a statement about the magnitude of
   disagreement relative to the budget, not a proof that the monocular side is the
   side that is wrong.

2. **Every arm, reference included, makes the footage temporally worse than its own
   unprocessed input** at lag 1 on five of six clips (reference ratios 1.17-3.73).
   A range-driven inversion with fixed coefficients amplifies per-frame range noise
   into colour. That is a property of the instrument, and it means the temporal
   rows should be read as arm-vs-reference, never as arm-vs-nothing.

3. **`turbid_coastal` is not measurable on this footage and its row above should not
   be used.** The transmission floor swallows the frame: every channel is floored on
   100% of pixels for four of six clips under `da3mono_large` and two under
   `mapanything_n1`, and the surviving windowed medians rest on a handful of frames
   with slivers of window (`wreck_03`/MapAnything reports 2.94 from a median window
   fraction of 0.000). The measurable regimes here are `coastal` and
   `clear_oceanic`; both rank the arms the same way.
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", default=os.path.join(common.OUTPUTS, "s6", "s6_raw.json"))
    ap.add_argument("--temporal", default=os.path.join(common.OUTPUTS, "s6",
                                                       "s6_temporal.json"))
    ap.add_argument("--inspect", default=os.path.join(common.OUTPUTS, "s6", "inspect",
                                                      "manifest.json"))
    ap.add_argument("--out-md", default=os.path.join(common.RESULTS, "S6_RESTORATION.md"),
                    help="Round 2 must point this away from the Round-1 report; the "
                         "default writes the Round-1 path.")
    ap.add_argument("--out-json", default=os.path.join(common.RESULTS, "S6_results.json"),
                    help="likewise for the machine-readable summary")
    ap.add_argument("--stage-note", default="Only the S5 finalists run.",
                    help="the one-line scope statement under the title; Round 2 runs a "
                         "different arm set and must say so")
    ap.add_argument("--inspection-notes", default=None,
                    help="path to a markdown fragment replacing INSPECTION_NOTES. The "
                         "default constant records what was seen in the ROUND-1 sheets "
                         "for the ROUND-1 arms; any other arm set must supply its own, "
                         "written after actually viewing that run's sheets.")
    ap.add_argument("--classification", default=None,
                    help="path to a markdown fragment replacing CLASSIFICATION, likewise "
                         "per arm set")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    notes = (open(args.inspection_notes).read() if args.inspection_notes
             else INSPECTION_NOTES)
    classification = (open(args.classification).read() if args.classification
                      else CLASSIFICATION)
    with open(args.raw) as fh:
        raw = json.load(fh)
    temporal = json.load(open(args.temporal)) if os.path.exists(args.temporal) else None
    inspect = json.load(open(args.inspect)) if os.path.exists(args.inspect) else None

    arms = raw["arms"]
    clips = list(raw["clips"])
    wt = raw["primary_water_type"]
    waters = list(raw["water_types"])

    def cell(clip, arm, water, key):
        v = raw["clips"][clip]["arms"].get(arm, {}).get(water, {})
        return v.get(key, float("nan"))

    payload = {"stage": "S6", "raw": raw, "temporal": temporal,
               "inspection_manifest": inspect}
    common.write_json(args.out_json, payload, overwrite=args.overwrite)

    L = []
    A = L.append
    A("# S6 — restoration impact")
    A("")
    A(f"**Stage:** S6. {args.stage_note}")
    A("")
    A(f"Each of the {len(clips)} frozen clips is restored {len(arms) + 1} times — once")
    A("driven by the Week-3 multi-view range, once by each arm's monocular range — on")
    A("identical frames at SOURCE resolution.")
    A("")
    A("## What the instrument is, and what it is not")
    A("")
    A("**This is not the project's restoration.** Weeks 5-6 own backscatter removal and")
    A("attenuation inversion. S6 needs *some* stage that consumes range in order to answer")
    A("whether swapping the range field changes the restored image, so this implements the")
    A("project's standing image-formation model exactly as `PLAN.md` states it and as Week")
    A("3's stage-7 sensitivity study used it:")
    A("")
    A("```text")
    A("I_c     = J_c * exp(-b_att_c * d) + Binf_c * (1 - exp(-b_bs_c * d))")
    A("J_hat_c = (I_c - Binf_c * (1 - exp(-b_bs_c * d_hat))) / exp(-b_att_c * d_hat)")
    A("```")
    A("")
    A("**The coefficients are SHARED and FIXED across arms**, and the veiling light `Binf`")
    A("is estimated once per clip from the REFERENCE range. Between any two arms the only")
    A("thing that changes is `d_hat`.")
    A("")
    A("### Two admissibility corrections the first run made necessary")
    A("")
    A("The instrument as first configured produced numbers that could not be read, and")
    A("the reason is worth stating because it is a property of this footage, not a coding")
    A("slip. Both corrections were applied identically to every arm.")
    A("")
    A("**1. The veiling light has to be one the image can carry.** `Binf` was estimated as")
    A("the p90 of the far field under the reference range. On `wreck_07` and `wreck_03`")
    A("the water column is CLIPPED in the source — 10.7% and 14.4% of pixels at code 254+")
    A("— so that estimator returns `Binf_B = 1.0`, and `1.0 * (1 - exp(-0.22 * 7 m)) =")
    A("0.79` exceeds the observed blue at essentially every pixel that is not far away.")
    A("The inversion then subtracts more than the image contains. Measured: **99% of")
    A("pixels had at least one channel driven to zero**, restored medians were a pure red")
    A("`[0.75, 0, 0]`, and 50-84% of the common support was BIT-IDENTICAL between the two")
    A("arms. The resulting median delta E00 of 0.000 on four of six clips was two")
    A("saturations agreeing, not two range fields agreeing.")
    A("")
    A("The model itself says what the bound is: `J >= 0` requires")
    A("`Binf_c <= min_p I_c(p) / (1 - exp(-b_bs_c d(p)))`, whose minimising pixels are the")
    A("darkest ones AT THEIR OWN RANGE — the dark-channel estimator, made exact by knowing")
    A("`d`. `Binf` is now the p90 far-field estimate capped by that bound (1st percentile,")
    A("not the hard minimum). Because the bound involves `b_bs` it is per water type;")
    A("within a water type all arms still share one `Binf`.")
    A("")
    A("**2. The inversion gain has to be finite.** These clips carry reference ranges out")
    A("past 50 m, where `1/exp(-0.55 * d)` for red is 1e12. The 8-bit source's")
    A("quantisation step is ~3e-4 in linear light near the dark end, so past roughly 20x")
    A("the amplified step stops being negligible against restored medians of 0.2-0.5.")
    A(f"Transmission is therefore floored at `t_floor = {raw.get('t_floor', 0.05)}`, per")
    A("channel: red stops responding beyond ~5.4 m in the coastal regime while green and")
    A("blue keep responding past 15 m, which is the physically honest statement about")
    A("which channel carries range information how far.")
    A("")
    A("**3. Metrics are reported twice.** Once over the full common support, and once over")
    A("the RESPONSIVE WINDOW: pixels not floored in every channel and not pinned at either")
    A("end of the clamp in either arm. Outside that window two range fields produce the")
    A("same pixel however much they disagree. The window fraction is reported alongside,")
    A("because a number from a 10% window is a different claim from one from a 90% window.")
    A("")
    A("That is what makes temporal scale drift bite here. A CONSTANT global scale error is")
    A("exactly absorbable by `b -> b/s` — Week 3 verified that identity to floating-point")
    A("precision — so a merely-biased model loses nothing. A model whose scale WANDERS")
    A("cannot be absorbed by any single `b`, and pays for it in colour.")
    A("")
    A(f"Primary water type: `{wt}` "
      f"(b_att {restoration.WATER_TYPES[wt]['b_att']}, b_bs {restoration.WATER_TYPES[wt]['b_bs']}, "
      f"1/m). These are the Jerlov-bracketing values Week 3 swept, NOT a fit to this")
    A("project's footage, which Week 6 owns.")
    A("")
    A("Per-clip veiling light estimated from the reference, and what the uncorrected")
    A("far-field estimator would have used:")
    A("")

    def _binf(c, w):
        v = raw["clips"][c]["Binf_linear_rgb"]
        v = v[w] if isinstance(v, dict) else v
        return ", ".join(f"{x:.4f}" for x in v)

    A(md_table([[c, _binf(c, wt),
                 ", ".join(f"{x:.4f}" for x in raw["clips"][c].get("Binf_far_field_p90", []))]
                for c in clips],
               ["clip", f"Binf used ({wt})", "far-field p90 (inadmissible)"]))
    A("")
    A("## Colour difference against the reference-driven restoration")
    A("")
    A("CIEDE2000, computed after normalising BOTH restorations to the same median")
    A("exposure, so a pure brightness difference does not present as a colour difference.")
    A("The exposure ratio is reported separately.")
    A("")
    for key, title, fmt in (
            ("delta_e00_median", "median delta E00 per frame", "{:.3f}"),
            ("delta_e00_p95", "p95 delta E00 within frame", "{:.3f}"),
            ("delta_e00_frame_to_frame_mad", "COLOUR PUMPING: frame-to-frame MAD of delta E00", "{:.3f}"),
            ("radiance_abs_rel_median", "median |relative radiance error|", "{:.4f}"),
            ("delta_e00_median_window", "RESPONSIVE WINDOW: median delta E00 per frame", "{:.3f}"),
            ("delta_e00_p95_window", "RESPONSIVE WINDOW: p95 delta E00 within frame", "{:.3f}"),
            ("delta_e00_frame_to_frame_mad_window",
             "RESPONSIVE WINDOW: colour pumping", "{:.3f}"),
            ("radiance_abs_rel_median_window",
             "RESPONSIVE WINDOW: median |relative radiance error|", "{:.4f}"),
            ("window_fraction_median", "responsive window as a fraction of common support", "{:.3f}"),
            ("exposure_ratio_median", "exposure ratio vs reference", "{:.3f}"),
            ("clipped_high_fraction_median", "fraction of restored pixels clamped high", "{:.4f}"),
            ("floored_fraction_all_median",
             "fraction with EVERY channel on the transmission floor", "{:.4f}")):
        A(f"### {title}")
        A("")
        A(md_table([[a] + [fmt.format(cell(c, a, wt, key)) for c in clips] for a in arms],
                   ["arm"] + clips))
        A("")
    A("The pumping row is the one that connects S5 to a visible artifact: a steady colour")
    A("offset is a bias a downstream stage could in principle absorb, whereas a colour")
    A("difference that MOVES frame to frame is the artifact the project's temporal")
    A("invariant exists to prevent.")
    A("")
    A("For scale, the reference-driven restoration's own behaviour:")
    A("")
    def _rs(c, k):
        return raw["clips"][c]["reference_restoration_stats"][wt].get(k, float("nan"))

    A(md_table([[c, f"{_rs(c, 'clipped_high_fraction_median'):.4f}",
                 f"{_rs(c, 'negative_fraction_median'):.4f}",
                 f"{_rs(c, 'floored_fraction_all_median'):.4f}",
                 f"{_rs(c, 'responsive_fraction_median'):.4f}",
                 f"{_rs(c, 'gain_p99_uncapped_median'):.3g}"]
                for c in clips],
               ["clip", "clamped high", "driven negative", "fully floored",
                "responsive", "p99 gain the inversion ASKED for"]))
    A("")
    if len(waters) > 1:
        A("## Robustness across water regimes")
        A("")
        A("The same comparison under all three Jerlov-bracketing coefficient sets. A")
        A("conclusion that only holds for one regime is a conclusion about the coefficients.")
        A("")
        rr = []
        for a in arms:
            for w in waters:
                vals = [cell(c, a, w, "delta_e00_median_window") for c in clips]
                vals = [v for v in vals if np.isfinite(v)]
                rr.append([a, w, f"{np.median(vals):.3f}" if vals else "-"])
        A(md_table(rr, ["arm", "water type", "median delta E00"]))
        A("")
    if temporal:
        A("## Frozen Week-2 temporal metrics on the restored sequences")
        A("")
        A("The Phase-2B machinery, unchanged: motion-compensated warp error in linear light")
        A("with SEA-RAFT correspondence, at lags 1/4/8, plus temporal delta E00.")
        A("")
        rows = []
        for arm, rec in temporal.get("arms", {}).items():
            for clip, m in rec.get("clips", {}).items():
                if m.get("status") != "ok":
                    continue
                rows.append([arm, clip,
                             f"{m.get('mcwarp_lag1', float('nan')):.5f}",
                             f"{m.get('mcwarp_input_lag1', float('nan')):.5f}",
                             f"{m.get('mcwarp_lag4', float('nan')):.5f}",
                             f"{m.get('mcwarp_lag8', float('nan')):.5f}",
                             f"{m.get('temporal_delta_e_lag1', float('nan')):.3f}",
                             f"{m.get('temporal_delta_e_input_lag1', float('nan')):.3f}",
                             f"{m.get('coverage_lag1', float('nan')):.3f}"])
        if rows:
            A(md_table(rows, ["arm", "clip", "MC-warp @1", "input @1", "@4", "@8",
                              "temporal dE00 @1", "input dE00 @1", "coverage @1"]))
            A("")
            A("`input` columns are the UNPROCESSED sequence measured on the same")
            A("correspondence and the same mask. A restoration that is less stable than its")
            A("own input has made the footage worse in the project's own frozen terms, and")
            A("the comparison that matters is each arm against the reference-driven row on")
            A("the same clip.")
        A("")
    if inspect:
        A("## Mandatory visual inspection")
        A("")
        A("`CLAUDE.md` invariant 5: a metric improvement is not a successful experiment")
        A("until the output has been looked at for hallucinated detail, broken scene")
        A("identity and unnatural colour relationships. Two kinds of render:")
        A("")
        A("- **sheets** — one row per arm over three frames per clip: source, the arm's")
        A("  range on a colour scale SHARED with the reference, its signed disagreement, and")
        A("  the restoration it drives;")
        A("- **worst-disagreement crops** — the tiles where the arm and the reference")
        A("  disagree most, magnified. Chosen by the data, so it cannot be a flattering crop.")
        A("")
        n_sheets = sum(len(v["sheets"]) for v in inspect["clips"].values())
        n_crops = sum(len(v["crops"]) for v in inspect["clips"].values())
        A(f"{n_sheets} sheets and {n_crops} crops under `outputs/s6/inspect/`.")
        A("")
        A("Looked for specifically: " + "; ".join(inspect["what_to_look_for"]) + ".")
        A("")
        A("### What the inspection actually showed")
        A("")
        for _ln in notes.strip("\n").split("\n"):
            A(_ln)
        A("")
    A("## Provisional classification")
    A("")
    A("```text")
    A("ADEQUATE / DEGRADED / UNSAFE")
    A("relative to the CURRENT WEEK-3 HYPOTHESIS")
    A("```")
    A("")
    for _ln in classification.strip("\n").split("\n"):
        A(_ln)
    A("")
    A("S6 does not produce the final objective Week-4 winner. Pre-C2 there is no")
    A("independent anchor, so a monocular-vs-reference disagreement cannot say which side")
    A("is wrong.")

    out_md = args.out_md
    if os.path.exists(out_md) and not args.overwrite:
        raise SystemExit(f"refusing to overwrite {out_md!r} (pass --overwrite)")
    with open(out_md, "w") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"[S6-report] -> {os.path.relpath(out_md, REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
