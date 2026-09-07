# R2 — TRIGGERED THIN-STRUCTURE TEST (§18)

**EPISTEMIC STATUS: PRE-C2.** The Week-3 persisted range product is a
PROVISIONAL MULTI-VIEW HYPOTHESIS, not ground truth. Nothing here declares a
winner. This stage is unusual among the Round-2 stages in one respect: it is
the only one whose reference labels do **not** come from that hypothesis, and
the first result below is that the hypothesis itself fails this test.

Every model arm is strict N=1 single-image inference. `week3_reference` is the
multi-view product and is included as a *subject*, not as truth.

---

## 1. Why the labels come from the image, not from the reference

§18 asks for open-space preservation, false filled surfaces and missing thin
members around the `wreck_07` crane/lattice. Grading that against the Week-3
range product would grade every model against the very failure under test —
multi-view reconstruction is itself weak on thin structure. So the annotation
is photometric, and rests on one physical fact this project already relies on
everywhere else: **underwater veiling is monotone in range.** A patch that has
reached the colour and contrast of the open water column is far; a patch that
has not, is not.

Annotation (`scripts/r2_thin_annotate.py`, six frames of `wreck_07`):

| label | definition |
|---|---|
| `water` | blueness ≥ 0.44, local texture ≤ 0.020 (11 px window), luma ≥ 0.25 |
| `BACKGROUND` | the largest connected `water` component |
| `OPENING` | every other enclosed `water` component, 60–40 000 px |
| `MEMBER(c)` | the structure ring 3–9 px outside opening `c` |
| `LOCAL SEA` | `BACKGROUND` within 60 px of a Tier-A opening |

Openings split by **veiling**, not by size or by distance to the background:

- **Tier A** — the opening is photometrically indistinguishable from the open
  water column (within 0.05 blueness and ≥ 0.75 of background luma). These are
  holes you can see *through*. 6–9 per frame, ~8 000 core px per frame.
- **Tier B** — every other enclosed opening: darker, less blue, i.e. probably
  a recess or a shadowed pocket rather than a through-hole. Recorded and
  reported **separately**, never mixed into the primary number. 14–42 per frame.

An earlier tier rule keyed on distance-to-background was inverted on visual
inspection of `overlay_f000092.png` — encrusted members are 20–40 px thick, so
size-based thresholds selected hull gaps and rejected the actual lattice. A
disk-based thin-member detector was also abandoned: at small radius it fired on
marine snow, at large radius it traced the distant sand slope. Both failures are
recorded in the module's own comments so they are not re-attempted.

## 2. What is measured

Per Tier-A opening, all in metres of *provisional* range after the frozen S2
alignment for that arm:

```
r_sea    median range over LOCAL SEA        (the far anchor)
r_open   median range over the opening core (should ≈ r_sea)
r_mem    median range over the 3..9 px ring (should be near)

fill   = log(r_sea / r_open)   -> 0 is correct; large is a FALSE FILLED SURFACE
member = log(r_sea / r_mem)    -> large is correct; ~0 is a MISSING MEMBER
gap    = log(r_open / r_mem)   = member - fill; the ordinal separation
```

The opening core is eroded by 2, 5 and 8 px to probe **edge displacement**: an
arm whose depth edge sits where the image edge sits gains nothing from erosion;
an arm that smears the edge inward only separates once you move well inside.

Evaluation is at **source resolution (`downsample=1`)** — the frozen stride-4
grid would sample straight past members a few pixels wide. The **alignment is
unchanged**: each arm uses its frozen S2 clip-level fit, refitted exactly as S3
fits it (stride 4, all 48 frames, seed 0). The grid changes; the gauge does not.

No weighted score. The six §18 aspects are reported side by side.

## 3. Results — Tier A, pooled over the six annotated frames, erosion 2 px

| arm | gap | fill | member | frac gap>10% | frac member erased | filled>½ (resolved) | n resolved | edge gain 5/2 | Tier-A coverage | r_sea (m) |
|---|---|---|---|---|---|---|---|---|---|---|
| `week3_reference` (PROVISIONAL) | **+0.000** | +0.054 | +0.070 | 0.05 | 0.41 | 0.94 | 16 | — | 1.000 | 30.7 |
| `mapanything_n1` | **+0.006** | +0.049 | +0.060 | 0.09 | 0.45 | 0.93 | 15 | — | 0.752 | 34.3 |
| `dav2_small` | +0.165 | +0.038 | +0.309 | 0.55 | 0.21 | 0.39 | 23 | 2.51 | 0.464 | 34.4 |
| `mda_mog_sky_l2` | +0.226 | −0.004 | +0.252 | 0.69 | 0.29 | 0.25 | 36 | 1.30 | 0.995 | 33.5 |
| `pxdepth` | +0.240 | +0.022 | +0.262 | 0.64 | 0.18 | 0.28 | 32 | 1.24 | 0.908 | 31.6 |
| `da3mono_large` (CORRECTED) | +0.411 | +0.056 | +0.580 | 0.73 | 0.04 | 0.31 | 42 | 1.55 | 0.995 | 33.7 |
| `wat3r_n1` | +0.446 | +0.239 | +0.928 | 0.69 | 0.04 | 0.45 | 44 | 1.47 | 0.991 | 44.7 |
| `moge3_vitl` (Step 0) | +0.542 | −0.101 | +0.444 | 0.72 | 0.09 | 0.23 | 39 | 1.32 | 0.947 | 36.1 |
| `fg_pre_ray` | +0.970 | +0.136 | +1.028 | 0.72 | 0.00 | 0.30 | 43 | 1.27 | 0.999 | 46.7 |
| `fg_post_ray` | +0.970 | +0.136 | +1.028 | 0.72 | 0.00 | 0.30 | 43 | 1.27 | 0.999 | 46.7 |
| `foundationgeo_11` | +0.983 | +0.137 | +1.020 | 0.72 | 0.00 | 0.30 | 43 | 1.25 | 0.999 | 44.0 |
| `metricanything_pointmap` | +1.333 | +0.127 | +1.140 | 0.71 | 0.00 | 0.31 | 42 | 1.15 | 0.980 | 85.3 |
| `moge2_vitl` | **+1.619** | +0.291 | +1.643 | 0.73 | 0.00 | 0.29 | 45 | 1.12 | 1.000 | 175.3 |

*`frac member erased`* = fraction of openings where the ring is within 5 % of the
sea range, i.e. the member has no depth of its own.
*`filled>½ (resolved)`* is restricted to openings the arm actually separates
(`|member| > log 1.10`); unrestricted it is meaningless for an arm whose entire
separation is at noise level, and it flattered exactly those arms. `n resolved`
says how few openings that leaves for the top two rows.
*`frac gap inverted`* (opening scored **nearer** than its own member by >10 %)
is 0.00 for every arm except `mda_mog_sky_l2` at 0.04.

### Per-frame Tier-A median gap — the ordering is not a one-frame artefact

| arm | f25 | f59 | f92 | f109 | f126 | f143 |
|---|---|---|---|---|---|---|
| `week3_reference` | +0.061 | −0.004 | +0.002 | −0.001 | +0.020 | −0.002 |
| `mapanything_n1` | +0.057 | −0.002 | +0.009 | −0.005 | +0.016 | +0.005 |
| `dav2_small` | +0.456 | +0.084 | +0.027 | +0.010 | +0.271 | +0.086 |
| `mda_mog_sky_l2` | +0.337 | +0.129 | +0.199 | +0.103 | +0.342 | +0.393 |
| `pxdepth` | +0.601 | +0.101 | +0.118 | +0.064 | +0.383 | +0.675 |
| `da3mono_large` | +0.664 | +0.380 | +0.331 | +0.593 | +0.417 | +0.351 |
| `wat3r_n1` | +0.609 | +0.402 | +0.510 | +0.166 | +0.794 | +0.308 |
| `moge3_vitl` | +1.343 | +0.720 | +0.298 | +0.428 | +0.471 | +0.580 |
| `foundationgeo_11` | +1.407 | +1.356 | +0.533 | +1.040 | +0.983 | +0.727 |
| `metricanything_pointmap` | +1.731 | +1.362 | +0.749 | +1.419 | +1.158 | +1.103 |
| `moge2_vitl` | +2.172 | +1.691 | +0.948 | +1.639 | +1.604 | +1.243 |

`week3_reference` and `mapanything_n1` are at zero on **all six** frames.
No arm changes rank band between frames; f92 (smallest median opening, 394 px)
compresses everyone.

### Tier B (recesses, reported separately, never pooled in)

Every arm returns a Tier-B median gap of +0.001 to +0.004 — indistinguishable
from zero, for all thirteen arms including the ones that separate Tier A
strongly. That is the expected result and it is a useful control: the Tier-A
signal is not an artefact of the ring/core construction, because the identical
construction on non-through-holes produces nothing.

## 4. Findings

**F1 — the provisional Week-3 reference is itself blind to thin structure.**
`gap = +0.000`, 41 % of members erased, and on the 16 openings it does resolve
the hole is more than half filled toward the member 94 % of the time. The crane
head renders as one solid mass. This is a statement about the *reference*, and
it retroactively justifies §18's insistence on annotating from the image. It
also bounds every other Round-2 stage: **any S2/S3/S5 metric computed against
this reference cannot reward an arm for resolving the lattice, and will
actively penalise one that does.** That has to be carried into §19.

**F2 — `mapanything_n1` reproduces the reference's blindness exactly.**
`gap = +0.006`, 45 % members erased, Tier-A coverage only 0.752 (it declines to
predict on a quarter of the annotated open area). This is expected rather than
surprising — the Week-3 product is a MapAnything-based multi-view
reconstruction — but it is load-bearing: the S3 leader and the reference share
the failure, so S3's ranking of `mapanything_n1` is partly measuring agreement
with its own family. Not a disqualification pre-C2; a caveat that must appear
in the final report.

**F3 — MapAnything's failure mode is a MISSING MEMBER, not a FALSE SURFACE.**
`fill` is small (+0.049) *and* `member` is small (+0.060). The hole is not
filled up to the member; the member is smoothed away down to the background.
The distinction matters for restoration: a false surface puts near-range
attenuation on far water (over-correction, colour blow-out); an erased member
puts far-range attenuation on a near strut (under-correction, the strut stays
veiled). §22 must check for the latter, not the former, on this arm.

**F4 — CORRECTED `da3mono_large` is materially better at the lattice than
MapAnything, reversing the Round-1 verdict.** `gap = +0.411`, `member = +0.580`,
only 4 % of members erased, coverage 0.995, and `fill = +0.056` — it separates
the lattice *without* filling the openings. Round-1 S6 recorded that
"`da3mono_large` fills the thin lattice of the crane and rigging with a solid
opaque surface" (`results/S6_RESTORATION.md:250-275`, frame f000109). That
observation was produced under the wrong z-vs-range convention **and** the wrong
fitting family; §3 Part A corrected both. On the same frame, corrected DA3 now
scores `gap = +0.593` — its second-best frame — and the visual (below) shows
resolved struts. **This is a §26 correctness-repair headline: a Round-1
elimination-grade finding was an artefact of our own semantics, not of the
model.**

**F5 — the specialist winners are `moge2_vitl` (+1.619) and
`metricanything_pointmap` (+1.333), with a stated caveat.** Both erase 0 % of
members and have the best edge localisation (`edge gain 5/2` of 1.12 and 1.15 —
their depth edge is essentially on the image edge, versus 2.51 for `dav2_small`,
which only separates once you erode 5 px in). But `moge2_vitl`'s `r_sea` is
175 m and `metricanything_pointmap`'s is 85 m, against ~31–34 m for the
reference and the well-calibrated arms. A large part of their margin is
far-field expansion, not lattice acuity: the far anchor itself is pushed out, so
`log(r_sea/r_mem)` grows. Pre-C2 we cannot say which of the two is right about
absolute scale, and this test cannot separate "resolves the lattice better" from
"expands the far field more". Both readings are consistent with the data; the
resolution requires C2.

**F6 — FoundationGeo's ray correction does nothing here.** `fg_pre_ray` and
`fg_post_ray` are identical to three decimals on every frame under the common
coordinate/postprocessing treatment required by §5 C1. Their fitted scales agree to seven
digits (1.7350344 vs 1.7350343; the shipped `foundationgeo_11` path fits
2.2526 because it carries different postprocessing), and the *geometry* at the
lattice is identical. Consistent with the §5 C1 finding, and independent
corroboration of it on a hard region: the ray correction is not what separates
the arms here.

**F7 — `mda_mog_sky_l2` is the only arm with inverted openings** (4 % of Tier-A
openings scored nearer than their own member). Its `fill` is −0.004, i.e. no
false surface, and its `member` is only +0.252 with 29 % erased. Per §12 this is
reported as an observation about the mixture output; it is **not** described as
calibrated confidence, and whether the mixture probabilities correlate with
these inversions is a §26 question this stage does not answer.

## 5. Visual inspection (§18 mandatory; CLAUDE.md invariant 5)

Three sheets under `outputs/thin/`, log-scaled per arm between its own 2nd/98th
percentile *inside the crop* — deliberately, because a shared absolute colour
scale would make every arm whose far field differs from the reference's look
uniformly wrong and hide the only thing these crops are about.

- `overlay_f*.png` (six) — the annotation itself. Inspected on f59, f109, f126;
  Tier A lands on the crane-lattice through-holes, Tier B on recesses.
- `ranges_f000059.png`, `ranges_f000109.png` — 12 panels, crop y 540–1280.
  `week3_reference` and `mapanything_n1` render the crane head as one solid
  orange mass with the lattice unresolved. `wat3r_n1` and `dav2_small` are
  smooth blobs despite `wat3r_n1`'s respectable +0.446 — its gap comes from
  large-scale near/far separation, not from resolving individual struts.
- `crane_f000109.png` — zoom on the crane head (y 140–420, x 900–1220).
  `da3mono_large`, `moge2_vitl`, `moge3_vitl` and `mda_mog_sky_l2` resolve
  individual struts with visible open gaps between them. `pxdepth` is soft with
  blocky artifacts at the right edge.

The visual and the numbers agree on every arm, with one refinement the numbers
alone would have got wrong: `wat3r_n1`'s gap is real but is not lattice acuity.

## 6. What is not here

| arm | status |
|---|---|
| MoGe-3 Step 3 | `pending_cuda` — `refine_steps > 0` is unsupported on this backend, so no Step-3 arm exists to compare. §7's Step 0 → Step 3 question is unanswered at the lattice. |
| `surge_large` | `pending_cuda` |
| `hyden` (`facebook/hyden-mogev2-metric-point`), `pointdit_l_512` | `pending_checkpoint` |
| `pxdepth` | scored before its S2 finished, under a provisional policy entry (family `affine_log1p_depth`, convention `z_depth` from source). **Now confirmed**: the frozen `wreck_07` clip fit in `R2_S3_policy.json` came out identical to the provisional one to machine precision (`s` = 1.7267100387401935, `t` = 1.879891790727995), so no number in this stage changes. Checked, not assumed; `provisional_policy` is now `false` in the JSON. |

## 7. Pre-C2 reading

Three things are established, none of which is a winner declaration:

1. The provisional multi-view reference cannot adjudicate thin structure, and
   the incumbent that most closely tracks it inherits that limitation.
   Ranking against the reference is therefore blind in exactly the region §18
   was triggered to examine.
2. The Round-1 claim that corrected DA3 fills the lattice was our own semantic
   defect. Under the corrected z-depth convention and affine-depth fit, DA3 is
   among the better arms at the lattice.
3. Two arms (`moge2_vitl`, `metricanything_pointmap`) separate the lattice far
   more strongly than anything else while erasing no members, but they also
   place the far field 2.5–5× further out than the reference. **Which of those
   two facts is causing the other cannot be determined pre-C2.** A C2
   measurement of absolute range on `wreck_07` at 20–60 m — specifically, on
   the open water column adjacent to the crane — would separate them.

### Artifacts

- `R2_thin_structure_results.json` — this stage's summary (source of truth).
- `outputs/thin/r2_thin_raw.json` — per-opening, per-erosion raw record.
- `outputs/thin/annotation.json`, `labels_f*.npz` — the annotation.
- `outputs/thin/overlay_f*.png`, `ranges_f*.png`, `crane_f000109.png` — visuals.

### Reproduce

```
.venv-eval/bin/python -m experiments.week4_mono.round2.scripts.r2_thin_annotate --overwrite
.venv-eval/bin/python -m experiments.week4_mono.round2.scripts.r2_thin_structure --overwrite
.venv-eval/bin/python -m experiments.week4_mono.round2.scripts.r2_thin_visual --overwrite
.venv-eval/bin/python -m experiments.week4_mono.round2.scripts.r2_thin_visual --overwrite \
  --frames 109 --crop 140 420 900 1220 --tile 420 --tag crane \
  --arms mapanything_n1 da3mono_large moge2_vitl moge3_vitl mda_mog_sky_l2 pxdepth
```

Reference-implementation integrity: every arm's predictions are the persisted
Round-1/Round-2 native outputs; this stage runs **no inference at all**, only
re-reads them at `downsample=1`.
