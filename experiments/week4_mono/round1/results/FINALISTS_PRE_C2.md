# Week 4A — pre-C2 finalists and the full elimination chain

**Every conclusion here is PRE-C2 and provisional.** The reference throughout is
the Week-3 persisted range product, which is a multi-view HYPOTHESIS, not ground
truth. Agreement with it means consistency with that hypothesis. There is no
independent anchor yet, so a monocular-vs-reference disagreement cannot say which
side is wrong, and **there is no objective final Week-4 winner in this document**.

## The sequence as it actually ran

```text
S0 semantics/runtime  -> S1 determinism -> S2 ambiguity -> S3 local geometry
   -> reduce field -> S4 appearance -> S5 temporal -> reduce to finalists
   -> S6 restoration impact
```

Sequential gates stayed sequential: no stage read a later stage's data, and each
reduction used only evidence available at that point.

## S0 — semantics and runtime

Survivors: **7/7**. No model exited.

Two documented expectations were corrected by measurement rather than repaired:
`DA3MONO-LARGE` emits no camera (a single DPT head, `output_dim: 1`; intrinsics,
extrinsics and confidence all `None`), and `Depth-Anything-V2-Small` cannot be
inverted before S2 fixes its disparity-space affine. Both therefore write NO
canonical range, which is the correct answer rather than a gap.

`wat3r_n1` retains only **56.0 %** of the frame area on the portrait source,
losing 10 of 25 FOV markers. Every other entrant retains 98.7-100 %.

## S1 — determinism and noise floor

| model                   | bitwise reproducible | p99 relative floor |
|-------------------------|----------------------|--------------------|
| mapanything_n1          | YES                  | 0.0e+00            |
| dav2_small              | YES                  | 0.0e+00            |
| moge2_vitl              | YES                  | 0.0e+00            |
| metricanything_pointmap | YES                  | 0.0e+00            |
| wat3r_n1                | YES                  | 0.0e+00            |
| da3mono_large           | YES                  | 0.0e+00            |
| foundationgeo_11        | YES                  | 0.0e+00            |

All seven are bitwise reproducible within and across processes on MPS in
float32, so the measured floor is exactly zero and **no downstream delta needs
to be discounted as run-to-run noise**. The binding floor everywhere below is
the REFERENCE's own instability, which Week 3 measured at 2.1-6.5 % median on
`wreck_05` against 0.01 % on `wreck_07`.

## S2 — the frozen alignment policy

| arm                     | native_kind            | E1 family        | convention | scope |
|-------------------------|------------------------|------------------|------------|-------|
| mapanything_n1          | depth_along_ray_metric | scale            | range      | clip  |
| dav2_small              | disparity_relative     | affine_disparity | range      | clip  |
| moge2_vitl              | pointmap_metric        | scale            | range      | clip  |
| metricanything_pointmap | pointmap_metric        | scale            | range      | clip  |
| wat3r_n1                | pointmap               | scale            | range      | clip  |
| da3mono_large           | depth_relative         | affine_depth     | range      | clip  |
| foundationgeo_11        | pointmap_metric        | scale            | range      | clip  |

One policy, not one transform. Clip-level scope for every arm; per-frame fits
are diagnostics only, because renormalising each frame would erase the temporal
scale drift FREEZE C7 makes a first-class failure mode.

## S3 — local geometry, the primary reduction

Full frozen set, 6 clips x 48 frames per arm. Six dimensions, no master score.

| arm                     | M-1 abs-rel | M-2 b | M-3 RelNormal | M-3 normal deg | M-4 boundary | M-5 ordinal | M-6 out/in | coverage |
|-------------------------|-------------|-------|---------------|----------------|--------------|-------------|------------|----------|
| mapanything_n1          | 0.0853      | 0.950 | 6.84          | 7.9            | 0.0028       | 0.0000      | 1.04       | 0.778    |
| dav2_small              | 0.1761      | 0.535 | 27.50         | 36.3           | 0.1022       | 0.1172      | 0.93       | 0.786    |
| moge2_vitl              | 0.2156      | 1.211 | 27.78         | 30.3           | 0.0355       | 0.0676      | 1.01       | 0.801    |
| metricanything_pointmap | 0.1819      | 0.975 | 27.50         | 30.0           | 0.0360       | 0.0665      | 0.94       | 0.782    |
| wat3r_n1                | 0.1840      | 1.223 | 15.62         | 19.9           | 0.0171       | 0.0057      | 0.93       | 0.776    |
| da3mono_large           | 0.1283      | 0.846 | 12.77         | 20.6           | 0.0285       | 0.0037      | 1.01       | 0.808    |
| foundationgeo_11        | 0.1712      | 0.845 | 32.71         | 38.5           | 0.0423       | 0.0862      | 0.79       | 0.806    |

## S4 — appearance invariance

| model                   | median scale bias | worst scale bias | median drift | worst drift | median local deformation | worst local deformation | worst perturbation         |
|-------------------------|-------------------|------------------|--------------|-------------|--------------------------|-------------------------|----------------------------|
| mapanything_n1          | 1.0149            | 1.4156           | 1.1965       | 1.6159      | 0.0200                   | 0.0619                  | channel_neutralize         |
| metricanything_pointmap | 1.0012            | 1.3172           | 1.2103       | 1.8709      | 0.0187                   | 0.1107                  | cue_conflict_inverted_veil |
| wat3r_n1                | 0.9995            | 0.9474           | 1.0613       | 1.2183      | 0.0257                   | 0.1072                  | cue_conflict_inverted_veil |
| da3mono_large           | 1.0095            | 1.1163           | 1.0436       | 1.2951      | 0.0301                   | 0.2487                  | cue_conflict_inverted_veil |

A constant scale bias is a benign gauge. Frame-varying drift and local
deformation are not.

## S5 — temporal stability

| arm                     | scale wander | frame-to-frame log MAD | near/far wander | local instability | boundary jitter px | coverage |
|-------------------------|--------------|------------------------|-----------------|-------------------|--------------------|----------|
| mapanything_n1          | 1.842        | 0.0503                 | 2.89            | 0.0189            | 1.00               | 0.778    |
| dav2_small              | 3.547        | 0.0751                 | 1.38            | 0.0108            | 0.50               | 0.784    |
| moge2_vitl              | 2.429        | 0.0693                 | 3.79            | 0.0232            | 0.00               | 0.801    |
| metricanything_pointmap | 2.286        | 0.0773                 | 6.51            | 0.0197            | 0.00               | 0.782    |
| wat3r_n1                | 2.293        | 0.0391                 | 3.62            | 0.0217            | 0.00               | 0.776    |
| da3mono_large           | 2.036        | 0.0470                 | 2.17            | 0.0096            | 0.00               | 0.808    |
| foundationgeo_11        | 1.948        | 0.0543                 | 3.35            | 0.0230            | 0.00               | 0.806    |

## S6 — restoration impact

| arm            | median dE00 vs reference-driven | worst clip dE00 | colour pumping | median rel radiance error | responsive window |
|----------------|---------------------------------|-----------------|----------------|---------------------------|-------------------|
| mapanything_n1 | 2.629                           | 2.928           | 0.906          | 0.1039                    | 0.678             |
| da3mono_large  | 3.510                           | 7.780           | 0.374          | 0.1128                    | 0.685             |

Every column but the last is measured over the RESPONSIVE WINDOW — pixels
where the inversion can still respond to a change in range. Outside it two
range fields produce the same pixel however much they disagree, so a
full-support number would report agreement that is really saturation.

## Eliminations

Seven entrants, one field, reduced in the frozen order. Nothing was eliminated on a
weighted score; each exit names a stage, a dimension and a number.

**S0 (semantics and runtime) — nobody eliminated.** All 7/7 mandatory checkpoints
ran on MPS in float32; runtime 0.28-2.32 s/frame, peak 2.1-9.6 GB. Two documented
expectations were corrected rather than repaired: `DA3MONO-LARGE` emits no camera
(`intrinsics`, `extrinsics`, `conf` all `None`), so it writes no canonical range —
inventing a focal would manufacture exactly the radial error M-6 exists to detect;
`Depth-Anything-V2-Small` likewise writes none, its ambiguity being affine in
DISPARITY. Both deferred to the frozen S2 policy. The FOV audit found the portrait
trap belongs to Wat3R alone: 10/25 markers lost and 56.0 % of frame area retained
on the 1280x720 portrait source.

**S1 (determinism) — nobody eliminated.** All seven bitwise reproducible; the noise
floor is exactly zero, so every downstream delta is signal.

**S2 (ambiguity) — nobody eliminated; the alignment policy frozen.** Clip-level
scope for every arm. Per-frame fits kept as diagnostics only, because
renormalising each frame would erase the temporal scale drift FREEZE C7 makes a
first-class failure mode.

**S3 (local geometry) — the primary reduction, 7 -> 4.**

- `dav2_small`, on STRUCTURE. M-4 boundary 0.1022 — about 3x the next-worst arm
  and 36x the leader, reaching 0.2749 on the portrait clip — with M-2 slope 0.535
  falling to 0.101 on `wreck_03`, which is severe near/far compression. Boundary
  failure is what a backscatter stage turns into visible haloes.
- `foundationgeo_11`, on SHAPE. Worst surface orientation in the field on both
  forms (32.71 deg RelNormal, 38.5 deg absolute, 47.2 deg worst clip) and the
  worst radial signature (M-6 0.79, reaching 0.54 on `swimthrough_02`). A
  systematic radial term on a wide-FOV underwater camera is the specific failure
  M-6 exists to catch. Its S2 scale is also the least consistent of any metric
  claimant, 0.55-2.51.
- `moge2_vitl`, on the FAR FIELD, and it loses its own V5 comparison. Far quintile
  1.098 — median relative range error above 100 % in the band where the water path
  is longest. MetricAnything, the same architecture with heterogeneous metric
  fine-tuning, reaches 0.682 there with better M-1 (0.182 vs 0.216) and much
  better M-2 (0.975 vs 1.211). V5 is answered: the fine-tune helps, so carrying
  both forward would carry a control past the point where it controls anything.

**S4 (appearance invariance) — nobody eliminated.** All four survivors advanced;
post-correction the stage held no disqualifying result.

**S5 (temporal stability) — reduction 4 -> 2.**

- `metricanything_pointmap`: last or near-last everywhere. Near/far wander 6.51
  against 2.17-3.62 for the rest — the SHAPE of its depth range, not merely its
  scale, changes sixfold within a clip — worst frame-to-frame MAD 0.0773, and
  7.112 scale wander on `wreck_01`, on top of the worst S3 far quintile (0.682)
  and the worst S4 veil mean (0.0869). Nothing best-in-field anywhere.
- `wat3r_n1`: dominated by `da3mono_large` on every S3 geometry dimension
  (M-1 0.184 vs 0.128, far quintile 0.229 vs 0.129, normals 15.62 vs 12.77 deg),
  and S0's portrait failure stands — 10/25 FOV markers and 44 % of frame area
  lost. For a video pipeline that is a structural failure, not a per-clip one.

**S6 (restoration impact) — nobody eliminated.** Both finalists are DEGRADED
against the Week-3 error budget and neither is ADEQUATE, but they fail in
complementary ways and pre-C2 there is no independent anchor that could declare
either the wrong side of the disagreement.

## Pre-C2 finalists

Two rather than three. The pair spans the design space — a multi-view-trained
metric point map at N=1 against a single-image affine-ambiguous relative-depth
model — and both eliminated S5 arms were dominated rather than merely behind.

### `mapanything_n1` (`facebook/map-anything-apache`, N=1)

Strongest geometry in the field and the most veil-robust model measured. Leads all
six S3 dimensions, several by 2x or more (M-1 0.085, far quintile 0.104, RelNormal
6.84 deg, M-4 0.0028, zero ordinal violations at 25 %, M-6 1.04). Best S4 veil mean
(0.0383, 1.75x the next) and the lowest local deformation under `veil_uniform`
(0.0327) despite the largest global scale response (sigma 1.4156) — a benign gauge.
Tightest S6 arm on five of six clips (windowed median dE00 1.83-2.93).

*What it still has to prove.*

1. **That its S3 lead is geometry and not shared inductive bias.** The reference IS
   MapAnything run multi-view. Two runs of one architecture share systematic
   errors, and a shared systematic error is invisible to a disagreement metric.
   This is the single largest confound in Week 4A and only C2 can break it.
2. **Temporal scale continuity.** Its instability concentrates on `cenote_01`, the
   widest near/far clip: S5 scale wander 5.607 against 1.521-2.477 elsewhere,
   local instability 0.0387 against 0.0157-0.0228. S6 shows the cost — MC-warp
   0.02330 against the reference-driven arm's 0.00983, temporal dE00 6.75 against
   2.82 (input control 2.51). The strongest static model destabilises exactly where
   the scene is deep, which is where the 8.5 %-at-8 m budget is tightest.
3. **That gray-world does not precede it.** `channel_neutralize` — what this
   project's own baseline does — is its WORST S4 wander arm (1.6159).
4. **A scale at inference.** It is metric-claiming but its S2 oracle scale is
   re-fit per clip.

### `da3mono_large` (`depth-anything/DA3MONO-LARGE`)

The most temporally stable model in the field by 2x (S5 local instability 0.0096
against 0.0189 for the next), best on all six clips individually and again on all
six within `static_anchored`, plus best near/far wander (2.17) and best coverage
(0.808). The most appearance-invariant of the four off-veil (S4 non-veil mean
0.0089, 1.5x the next, best on 9 of 12 arms). Strongest arm in the field that is
INDEPENDENT of the reference architecture, and the flattest radial signature
measured (M-6 1.01).

*What it still has to prove.*

1. **That it is not reading geometry off the haze.** Its cue-conflict ratio is
   3.99x, the worst of the four. Its calm and its veil-leaning are one property:
   it is stable exactly as long as the haze cue is honest. If restoration removes
   veil, range-before and range-after are different fields and the pipeline is
   self-referential.
2. **Structure it currently invents.** S6 inspection: it fills the thin crane
   lattice on `wreck_07` with a solid opaque surface where both other arms leave
   holes, and displaces the moving diver on `wreck_03` farther than the reference,
   rendering it visibly redder. These are scene-identity failures, not photometric
   ones.
3. **Low-texture lateral footage.** `wreck_05` is its worst case by a wide margin:
   windowed median dE00 7.78, p95 16.1, 33.3 % relative radiance error — six times
   the Week-3 budget. That single clip is what keeps it from a clean DEGRADED.
4. **A shift as well as a scale.** It is `affine_depth` with a fitted
   t = 1.78-11.56 m against median scene ranges of 6.4-22.5 m. Two unknowns at
   inference, not one, and neither is available without an oracle.
5. **Any way to signal its own failure.** Coverage is exactly unchanged across all
   twelve S4 perturbation arms and it emits no confidence. That is silence, not
   stability.

## What Week 4A could NOT establish

```text
definitive objective accuracy on this GoPro/housing configuration
final absolute water-path / range error
whether the Week-3 MapAnything hypothesis is objectively correct
final raw metric-scale ranking
definitive confidence calibration
final adequate / degraded / unsafe envelope
THE FINAL WEEK-4 WINNER
```

Raw metric behaviour is therefore RECORDED pre-C2 and JUDGED post-C2.

## C2 measurements required next

- controlled chart/reference geometry at several known ranges;
- an explicit distinction between z-depth, ray range and the intended water-path
  convention, captured rather than assumed;
- at least two water/visibility conditions;
- with and without dive lights where practical;
- matched EIS/HyperSmooth-off acquisition where practical;
- measured camera-interface distance and port information for the refractive
  hypothesis;
- **far-range support: at least one supported scene reaching roughly the far end of
  the intended operating envelope, ideally 10-15 m where visibility permits.** A C2
  restricted to near ranges would fail to test the far-field deformation that both
  the restoration sensitivity study and the external metric-depth literature suggest
  may be the most consequential.

## Unresolved questions carried forward

**1. The reference-architecture confound is unbroken.** MapAnything N=1 leads every
S3 dimension against a reference that is MapAnything multi-view. Nothing pre-C2
separates "better geometry" from "the same errors as the reference".

**2. Nobody can supply scale at inference.** MapAnything needs a clip-level scale;
da3mono needs a clip-level (s, t) with t of 1.78-11.56 m. Neither is available
without an oracle, and S2 measured every arm's scale to be scene-dependent (5.2-28.2x
across clips for wat3r; 0.52-2.54 for FoundationGeo). S6 measures restoration impact
UNDER the frozen oracle and therefore does not establish deployability.

**3. Nobody is temporally stable in absolute terms.** S5 scale wander is 1.84-2.29
for all four survivors — the scalar relating output to reference moves by 2x or more
inside a 48-frame clip. Absorbing that under one clip-level coefficient would need
water properties that change with the estimator. Week 5-6's temporal stage must own
scale continuity regardless of which model is chosen.

**4. Neither finalist meets the Week-3 error budget, and the reference may not
either.** Windowed relative radiance error is 3.9-19.0 % for MapAnything and
6.4-33.3 % for da3mono against a 5 %-radiance criterion at 6.1-9.4 % range error.
But the reference's own restoration health is worst on exactly the clips where
disagreement is worst — responsive fraction 0.41 on `wreck_05` and `wreck_03`,
inversion p99 gains of 1e8. Which side is wrong is a C2 question.

**5. Restoration itself degrades temporal stability on this footage, in every arm.**
Reference-driven MC-warp at lag 1 is 1.17-3.73x the unprocessed input on five of six
clips. A fixed-coefficient range-driven inversion amplifies per-frame range noise
into colour. Whether that survives Week 6's fitted coefficients and Week 5's temporal
stage is untested.

**6. The self-referential loop is named but not closed.** If a model draws geometry
from veil and restoration removes veil, the two are coupled. The cue-conflict ratio
measures how tight the loop is, and it is tightest (3.99x) for the model that
otherwise looks steadiest.

**7. Two conventions were settled by residual rather than by evidence that is
clean.** `dav2_small` pooled to a margin ratio of 1.0185 — INDISTINGUISHABLE, inside
the 3 % threshold — and `da3mono_large` to 1.1109 in favour of range with only 3 of 6
clips agreeing. An INDISTINGUISHABLE verdict means the model's shape error exceeds
this camera's 35 % radial secant term, which is itself a finding about the model.

**8. `turbid_coastal` is outside the S6 instrument's measurable range on this
footage.** Every channel is on the transmission floor for 100 % of pixels on four of
six clips under `da3mono_large`. Whether the ranking holds in genuinely turbid water
is untested, not answered.

**9. DA3 Mono's native z-vs-range question stays open.** Because the checkpoint emits
no camera, the reference implementation's own `unproject_depth` is never reached, so
what its depth field means geometrically is inferred from residuals rather than read
off the code.
