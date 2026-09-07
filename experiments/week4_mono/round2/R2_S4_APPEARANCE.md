# R2-S4 — appearance invariance, recomputed after Parts A–D

**Stage:** S4 (§20). **Everything here is PRE-C2.**

S4 is the one stage that does not touch the provisional Week-3 hypothesis. Each
perturbed field is compared against **the same model's own baseline field on the
same frames**, so what is measured is the model's response to appearance, isolated
from its standing disagreement with the reference and free of the reference's own
uncertainty. The price is that S4 says nothing about correctness: an arm can be
perfectly appearance-invariant about a geometry that is wrong.

## 0. Why this was recomputed, and what was *not* re-run

Both Round-1-invalidating repairs are **post-inference**. Part D's grid-map defect
lives in `evalgrid`, which maps a persisted prediction onto the evaluation grid;
Part A's z-vs-range repair lives in the S2 semantics, applied after the model has
already spoken. Neither touches what the model wrote to disk.

So the **persisted perturbed predictions were not re-run** — 23 712 files, 13
conditions × 6 clips × 16-frame window × 4 models of inference that would otherwise
have been repeated for nothing. Only the analysis was invalid, and only the analysis was
redone, against the corrected policy `R2_S3_policy.json`.

The two network-grid models are the control this predicts: `mapanything_n1` and
`wat3r_n1` come back **numerically identical to Round 1**, to every digit reported
below. The two arms the repairs touch move, and only they.

| arm | local deformation (physical) OLD → CORRECTED | wander OLD → CORRECTED | cause |
|---|---|---|---|
| `mapanything_n1` | 0.0200 → 0.0200 | 1.196 → 1.196 | **unchanged — control** |
| `wat3r_n1` | 0.0257 → 0.0257 | 1.061 → 1.061 | **unchanged — control** |
| `metricanything_pointmap` | 0.0187 → 0.0204 | 1.210 → 1.202 | Part D grid-map repair |
| `da3mono_large` | 0.0122 → 0.0128 | 1.044 → 1.044 | Part A z-depth convention |
| `dav2_small` | *no OLD* → 0.0181 | *no OLD* → 1.071 | **new** — never run in Round 1 |

The corrections are small here — which is itself worth stating plainly, because
they were *not* small in S3 (`dav2_small` M-1 moved enough to overturn its
elimination). S4 compares a model to itself, so a systematic mis-sampling that
shifts both sides of the comparison largely cancels. That cancellation is the
reason S4 survived the defect and S3 did not.

## 1. What is measured, and why it stays decomposed

FREEZE C7, unchanged: `d'_t = s_t·d_t` is physically consistent under
`beta'_t = beta/s_t`, so the three parts have completely different consequences and
are never combined into one number.

- **Constant global scale bias** — `median(sigma_t)` over the clip. Potentially a
  **benign gauge**: the physical coefficients can be refit once as `beta' = beta/s`.
- **Frame-varying scale drift** — `wander(sigma_t)`, the ratio of the scalar's
  spread within one clip. **Not benign.** Absorbing it would demand water properties
  that change with the estimator.
- **Local range deformation** — `|Δ log range|` left after removing the per-frame
  scalar. Spatially varying, so absorbable by no global physical parameter at all.
  **The primary geometric failure.**

Cross-model comparison uses the deformation measured in **physical range** under the
clip-level gauge fitted on the baseline arm and then held fixed, not the native
number: for an affine-family arm the native residual is inflated by the fitted shift
`t`, so comparing native numbers would penalise DA3 for its gauge rather than for
its geometry.

Perturbations are applied in linear light and re-encoded to 8-bit sRGB before
inference, so every number below sits above the PNG quantisation floor, not the
zero S1 floor.

## 2. Result — median over the six frozen clips, over the twelve perturbations

| arm | local Δlog (phys) | worst pert | max over perts | p95 | wander | max wander | max \|log σ\| |
|---|---|---|---|---|---|---|---|
| `da3mono_large` (corrected) | **0.0128** | cue conflict | 0.1205 | 0.0683 | **1.044** | **1.30** | 0.110 |
| `dav2_small` | 0.0181 | cue conflict | 0.0678 | **0.0597** | 1.071 | 1.30 | 0.073 |
| `mapanything_n1` | 0.0200 | channel neutralize | **0.0619** | 0.1055 | 1.196 | 1.62 | **0.348** |
| `metricanything_pointmap` | 0.0204 | cue conflict | 0.1008 | 0.1070 | 1.202 | 1.87 | 0.263 |
| `wat3r_n1` | 0.0257 | cue conflict | 0.1072 | 0.1095 | 1.061 | 1.22 | **0.054** |

Per perturbation, local deformation in physical range (median over clips):

| perturbation | `mapanything_n1` | `da3mono_large` | `metricanything` | `wat3r_n1` | `dav2_small` |
|---|---|---|---|---|---|
| wb_warm | 0.0079 | 0.0035 | 0.0063 | 0.0070 | 0.0032 |
| wb_cool | 0.0079 | 0.0035 | 0.0046 | 0.0065 | 0.0041 |
| channel_neutralize | **0.0619** | 0.0169 | 0.0256 | 0.0401 | 0.0224 |
| attenuation_red | 0.0124 | 0.0041 | 0.0087 | 0.0093 | 0.0067 |
| contrast_low | 0.0155 | 0.0087 | 0.0152 | 0.0147 | 0.0137 |
| contrast_high | 0.0367 | 0.0177 | 0.0328 | 0.0366 | 0.0224 |
| brightness_down | 0.0048 | 0.0022 | 0.0027 | 0.0052 | 0.0038 |
| brightness_up | 0.0081 | 0.0035 | 0.0041 | 0.0068 | 0.0067 |
| veil_uniform | 0.0327 | 0.0637 | 0.0577 | 0.0552 | 0.0380 |
| hotspot | 0.0383 | 0.0228 | 0.0279 | 0.0570 | 0.0402 |
| **cue_conflict_inverted_veil** | 0.0578 | **0.1205** | 0.1008 | 0.1072 | **0.0678** |
| veil_depth_consistent (control) | 0.0245 | 0.0295 | 0.0787 | 0.0550 | 0.0337 |

## 3. Findings

**F1 — every arm reads veiling as a depth cue, and the cue-conflict control proves
it is the conflict and not the magnitude.** `cue_conflict_inverted_veil` and
`veil_depth_consistent` apply the *same* veil magnitude; only the direction differs.
The deformation ratio between them is 4.1× for `da3mono_large`, 2.4× for
`mapanything_n1`, 2.0× for `dav2_small`, 1.9× for `wat3r_n1`, 1.3× for
`metricanything_pointmap`. **All five arms, across three different native
representations — metric point map, relative z-depth, relative disparity — respond
to the same veil more when its direction is wrong.** The
reference builds the stimulus and never reaches the model, so this is not a
reference artefact. Underwater veiling is monotone in range — that is the physical
basis this whole project rests on — and these models have learned it. It is the
right cue to learn and it is also the cue an underwater restoration pipeline is
about to *remove*. §22 has to take that seriously.

**F2 — MapAnything's metric scale is set by appearance, not only by geometry.** A
uniform veil carrying **no depth information at all** multiplies its whole clip's
range by 1.416 median, and by **2.465** on the worst clip. `veil_depth_consistent`
gives 1.287, `hotspot` 1.161, `contrast_high` 0.886. Across the twelve conditions
its constant scale swings by `max |log σ| = 0.348`, roughly ±40 %, against 0.054 for
`wat3r_n1` on the identical stimuli. Under FREEZE C7 a constant clip-wide scale is
potentially a benign gauge — but this is the arm whose entire pre-C2 standing rests
on producing raw metric scale, and the incumbent whose product the Week-3 reference
was built from. **Pre-C2 this does not say MapAnything's scale is wrong.** It says
that its scale is a function of how the water looked, which is exactly the property
C2 has to measure and exactly the property that cannot be checked against a
reference derived from the same model.

**F3 — and MapAnything's scale does not merely shift, it pumps.** Its wander is the
second highest in the field (1.196 median, 1.62 max on `channel_neutralize`, and
6.61 on one clip under cue conflict), and the frame-varying part is the part FREEZE
C7 says is *not* absorbable. `metricanything_pointmap` is worse still (1.202 median,
1.87 max, 6.50 on one clip under `channel_neutralize`).

**F4 — `channel_neutralize` is the project's own gray-world baseline, and it is the
single worst ordinary perturbation for MapAnything.** 0.0619 local deformation —
three times its `contrast_high` response and eight times its white-balance response
— with wander 1.616. This is not a synthetic stress condition; it is what `uw
correct --method gray_world` does to a frame. Any pipeline ordering that
white-balances before estimating geometry moves the geometry. Recorded here for §22
and §27; the ordering question is a restoration-pipeline decision, not a model
verdict.

The added arm sharpens it rather than softening it: `dav2_small` answers the same
stimulus with 0.0224 deformation and wander 1.085, **2.8× less deformation and a
seventh of the drift**. So the sensitivity is not a property of the perturbation —
gray-world is not intrinsically destabilising — it is a property of MapAnything.

**F5 — corrected `da3mono_large` is the most appearance-stable arm on ordinary
appearance change, and the most fooled by cue conflict.** It is best on 8 of the 12
conditions, has the lowest wander (1.044) and the lowest p95 (0.0683), and its
constant scale barely moves outside the veil conditions. Then `cue_conflict` gives
it the *highest* deformation of any arm (0.1205, p95 0.398). Both halves are the
same fact about the model: it is a strongly appearance-driven monocular prior, so it
is quiet when appearance is quiet and it goes where the appearance cue points when
that cue is made to lie. Together with §18 — where the corrected DA3 resolves the
crane lattice that MapAnything and the reference both miss — this is a coherent
picture of an arm that reads the image hard.

**F6 — `wat3r_n1` is the scale-stability winner and nothing else.** `max |log σ|` =
0.054 and wander 1.061, both best in the field by a wide margin, on the same twelve
stimuli that move MapAnything by 40 %. It is simultaneously last on local
deformation (0.0257) and second-worst in S3 (M-1 0.184). Appearance invariance and
geometric agreement are close to independent here, which is why §17 forbids a
weighted score: a single number would have hidden both facts.

**F7 — `dav2_small`, added after the §19 reduction, is the second most
appearance-stable arm in the field, and it is stable in the place MapAnything is
not.** It is 2nd of 5 on median local deformation (0.0181), has the **lowest p95**
(0.0597) and the **second-lowest worst case** (0.0678, behind MapAnything's 0.0619),
and its constant scale moves by `max |log σ| = 0.073` against MapAnything's 0.348 on
the identical stimuli. Under `veil_uniform` — the condition that multiplies
MapAnything's whole clip by 1.416 — its delivered range moves by 0.985.

That comparison needs one qualification stated before it is used, because the two
numbers are not the same claim. MapAnything's σ is a change in **the model's own
metric assertion**. DA v2 asserts no metric scale at all: its σ measures whether the
affine disparity gauge `(a, b)`, fitted once on the clean clip and then **held
frozen**, still delivers the same ranges when the water changes. That is a real and
directly useful property for this pipeline — it is exactly the failure mode a
per-clip calibration has to survive — but it is not evidence that DA v2 knows the
scale, and it must not be reported as if it were. The arm that makes no metric claim
cannot have its metric claim disturbed.

**F8 — where DA v2's frozen gauge *does* fail is where the fitted offset dominates
the fit, which is a testable mechanism rather than a clip idiosyncrasy.** Its median
σ hides a wide per-clip spread under the veil family: 0.656 on `wreck_01` and 0.720
on `cenote_01` under cue conflict, with wander 2.39 and 1.86; `veil_depth_consistent`
puts `cenote_01` at wander 2.733. Those two clips are also the two whose baseline
disparity fit is most offset-dominated — `t/s` = 3.50 and 4.93 against 1.18–1.37 for
the three well-behaved clips:

| clip | `s` | `t` | `t/s` | wander (veil_dc) | wander (cue conflict) |
|---|---|---|---|---|---|
| `wreck_05` | 0.0166 | 0.0196 | 1.18 | 1.206 | 1.263 |
| `wreck_07` | 0.0284 | 0.0360 | 1.27 | 1.087 | 1.189 |
| `swimthrough_02` | 0.0228 | 0.0313 | 1.37 | 1.124 | 1.101 |
| `wreck_03` | 0.0135 | 0.0338 | 2.51 | 1.312 | 1.341 |
| `wreck_01` | 0.0319 | 0.1117 | **3.50** | 1.464 | **2.391** |
| `cenote_01` | 0.0228 | 0.1127 | **4.93** | **2.733** | 1.857 |

The mechanism this is consistent with is elementary: delivered range is
`1 / (a·q + b)`, so when the fitted offset dominates the fitted slope, a given
appearance-driven change in native disparity `q` moves the delivered range further,
and the frozen gauge stops protecting the arm. Spearman over clips is +0.83
(`veil_depth_consistent`), +0.71 (`veil_uniform`, `hotspot`, cue conflict), +0.09
(`channel_neutralize`).

**This is a hypothesis, not a finding, and the sample size is the reason.** n = 6
clips: ρ = 0.83 at n = 6 is p ≈ 0.06 two-sided, and `channel_neutralize` — a
perturbation that is not veil-like — shows nothing. It is recorded because it is
cheap to falsify at C2 and because it predicts *which* footage a frozen per-clip DA
v2 calibration would fail on, which no aggregate number does.

**F9 — the boundary-jitter metric discriminates only MapAnything, and that is a
property of the metric.** It reads 0.000 for `da3mono_large`, `dav2_small`,
`metricanything_pointmap` and `wat3r_n1` on all twelve conditions, and is non-zero
only for `mapanything_n1` (up to 3.05 px under cue conflict, 2.28 under
`contrast_high`). Four arms reading exactly zero is not four arms with perfectly
stable depth boundaries; it is a metric that is quantised at the evaluation grid and
saturates below one sample for everything except the one arm whose boundaries move
by pixels. Do not read the zeros as a result. The one number that *is* a result is
MapAnything's, and it agrees with F2 and F3.

## 4. What is not in this stage

Five arms, not the whole field. `moge2_vitl` (incumbent I3), `foundationgeo_11` and
the Round-2 challengers have no persisted perturbation set. §20 restricts S4 to
survivors plus incumbent finalists, and no Round-2 challenger advanced, so no
challenger perturbation set was generated. The cost would be 1 248 inferences per
arm (13 conditions × 6 clips × 16 frames): ~43 min for `moge2_vitl`, ~85 min for
`moge3_vitl` at its measured S1 rate.

`dav2_small` is the one arm added after the fact, and the reason is recorded in
§19: its Round-1 elimination was **withdrawn** because the grounds for it were our
own Part D grid defect, and S4 was the single stage it had never been measured on.
Its 1 248 inferences (13 conditions × 6 clips × 16-frame window = 78 products) took
312 s, 0.250 s/frame, peak RSS 0.69 GB — the only S4 inference run in Round 2.
Everything else in this stage is re-analysis of Round-1 predictions.

Nothing here ranks the arms overall and nothing here is a C2 conclusion.

## 5. Pre-C2 reading

The stage's own instruction — "do not judge a model harshly for a fixed scale gauge;
do judge it if changing appearance makes its scale or shift pump over time, or
deforms local range" — cuts cleanly across this field. On the benign axis the field
is fine. On the two axes that are not benign it splits, and it splits the *opposite
way* from S3: the S3 leader is the arm whose metric scale is most appearance-driven,
and the arm that is quietest under appearance change is the one S3 ranks fourth.

The one thing S4 can say about the pre-C2 question in §27 is negative and firm: a
uniform veil that carries no range information moves the incumbent's metric scale by
up to 2.5×. Whatever C2 measures, it must measure scale under *varying water
appearance*, not on one clean clip — otherwise it will validate a scale that
appearance happened to set.

The fifth arm does not change that reading and does not overturn the split; it
widens it. The two arms that make **no** metric claim, `dav2_small` and `wat3r_n1`,
are the two whose delivered scale is steadiest under changing water, and the two
that make the strongest metric claim, `mapanything_n1` and `metricanything_pointmap`,
are the two whose scale moves most. Pre-C2 that correlation is not evidence about
which scale is right — an arm with no scale to disturb cannot have it disturbed, and
that is F7's qualification, not a point in DA v2's favour. What it does establish is
that appearance-driven scale movement is concentrated in exactly the arms whose
scale C2 will be asked to validate.

On the §19 question S4 was run to answer — whether `dav2_small`, restored to the
field after its elimination was withdrawn, holds up on the one stage it had never
been measured on — the answer is that it does, on this stage, and comfortably: 2nd
of 5 on local deformation, lowest p95, second-lowest worst case, and no
disqualifying behaviour on any of the twelve conditions. The disparity model that
Round 1 discarded is more appearance-stable than the incumbent whose product the
whole reference was built from. That is not a C2 conclusion and it is not a claim
that DA v2 is more correct; S4 measures invariance, and an arm can be perfectly
invariant about the wrong geometry.

## Artifacts

- `outputs/s4/r2_s4_raw.json` — full per-clip, per-perturbation record for the four
  Round-1 arms (supersedes the partial `outputs/s4/s4_corrected_raw.json` from the
  Part A/B repair).
- `outputs/s4/r2_s4_dav2_small.json` — the same record for `dav2_small`, kept in a
  separate raw so no frozen arm's digest is disturbed.
- `R2_S4_results.json` — persisted stage summary, including the OLD aggregate for
  every arm.
- Perturbed inputs: `outputs/perturbed/manifest.json` (unchanged, frozen).

## Reproduce

```
experiments/week4_mono/.venv-eval/bin/python -u \
  -m experiments.week4_mono.round1.scripts.s4_analysis \
  --policy experiments/week4_mono/round2/R2_S3_policy.json \
  --out experiments/week4_mono/round2/outputs/s4/r2_s4_raw.json --overwrite
```

`dav2_small` (inference, then analysis, then insertion into the frozen summary):

```
experiments/week4_mono/.venv-mono/bin/python -u \
  -m experiments.week4_mono.round1.scripts.s4_run --model dav2_small --skip-existing

experiments/week4_mono/.venv-eval/bin/python -u \
  -m experiments.week4_mono.round1.scripts.s4_analysis --models dav2_small \
  --policy experiments/week4_mono/round2/R2_S3_policy.json \
  --out experiments/week4_mono/round2/outputs/s4/r2_s4_dav2_small.json --overwrite
```
