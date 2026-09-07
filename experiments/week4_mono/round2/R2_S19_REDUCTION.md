# R2 — §19 REDUCTION AFTER S3

**EPISTEMIC STATUS: PRE-C2.** Everything below classifies arms against a
*provisional multi-view hypothesis*. Nothing here declares an objective winner,
and no classification survives C2 unexamined. Two of the classifications are
explicitly conditional on measurements only C2 can make, and they say so.

Inputs, all frozen and already persisted: `R2_S2_ALIGNMENT.md`,
`R2_S3_LOCAL_GEOMETRY.md`, `R2_THIN_STRUCTURE.md`, `R2_S4_APPEARANCE.md`,
`R2_S5_TEMPORAL.md`, `R2_PARTS_ABC_CORRECTNESS.md`,
`R2_PART_D_GRIDMAP_DEFECT.md`. No stage was re-run to produce this document.

## 1. The bar

§19 advances an arm past S3 only if it

- **(A)** materially improves primary local/range geometry over **both**
  incumbents, or
- **(B)** uniquely fixes the thin-structure failure without large regression, or
- **(C)** reveals a genuinely different robustness property relevant to
  restoration.

**Novelty is not a criterion.** Being new, being larger, being more recently
published, or being non-dominated on some column earns nothing here.

The incumbent bar for (A) is the two Round-1 finalists — `mapanything_n1`
(M-1 0.0853) and corrected `da3mono_large` (M-1 0.1476) — not the third
incumbent `moge2_vitl` (0.1958), because clearing only the weakest incumbent is
not "improving over both".

**One constraint governs criterion (B) and must be stated before any
classification.** §18 F1 established that the provisional Week-3 reference is
*itself* blind to thin structure (`gap = +0.000`, 41 % of members erased). So
**no reference-based metric can reward an arm for resolving the lattice, and
will actively penalise one that does.** M-1 and §18's `gap` are therefore not
independent evidence pulling in the same direction — they are in partial
tension by construction, and an arm that scores well on both has not been
tested twice.

## 2. Classification

| arm | class | advances? | ground |
|---|---|---|---|
| `moge3_vitl` (Step 0) — R2-1 | **NON-DOMINATED** | no | fails A, B and C; §7's actual mechanism was never testable |
| `mda_mog_sky_l2` — R2-6 | **FAILURE** | no | structural M-2, disqualifying S5, and its reason for inclusion dissolved |
| `pxdepth` — R2-4 | **FAILURE** | no | rank inversion with frame-to-frame sign flip on one frozen clip |
| `surge_large` — R2-3 | **UNTESTED** | — | `pending_cuda`. **Not eliminated.** |
| `hyden` — R2-2 | **UNTESTED** | — | `pending_checkpoint`. **Not eliminated.** |
| `pointdit_l_512` — R2-5 | **UNTESTED** | — | `pending_checkpoint`. **Not eliminated.** |
| MoGe-3 Step 3 | **UNTESTED** | — | `pending_cuda`. **Not eliminated.** |
| `dav2_small` — Round 1 | **ELIMINATION WITHDRAWN → RETAINED** | yes, to S4 then S6 | its Round-1 grounds were our own defect; S4 then cleared it (§6.1) |

**Three of the six authorised challengers were never measured.** They are
recorded as untested, with the exact blocker and the exact point in the protocol
where execution stopped. None of them is being called worse than anything. A
Round-2 conclusion drawn from three of six is a conclusion about three of six.

## 3. R2-1 `moge3_vitl` Step 0 — NON-DOMINATED, does not advance

**Not dominated.** No single arm is at least as good on every dimension: it
beats corrected DA3 on M-4 (0.0143 vs 0.0223), M-5@0.25 (0.0024 vs 0.0062),
M-3 abs (18.74° vs 19.54°) and §18 `gap` (+0.542 vs +0.411), while losing M-1,
M-2, M-3 rel, coverage and every S5 column. The DA3 figures here are the ones
after the late S3 convention merge (R2_S3 §4); the margins on M-4 and M-3 abs
narrowed, the non-domination did not change.

**Fails (A).** M-1 0.1694 is worse than both incumbents, not better than either.

**Fails (B).** It does separate the lattice (`gap` +0.542, 9 % members erased,
edge gain 1.32) — but not *uniquely*: corrected `da3mono_large` already does
(+0.411, 4 % erased), and `moge2_vitl` and `metricanything_pointmap` separate
more. §18's own F5 caveat applies to the arms above it, but not in a way that
promotes MoGe-3: it is mid-field on the one dimension where it would need to be
first. Its `fill` of −0.101 is also the wrong sign — it places the opening
*beyond* the sea range, which is over-separation, not acuity.

**Fails (C).** Its distinguishing property against its own incumbent
`moge2_vitl` is real and was recorded (M-1 0.169 vs 0.196, M-4 0.0143 vs 0.0320,
M-6 0.985 vs 1.072, far-field q4 0.357 vs 1.196). But that is a *within-family
generational improvement in geometry*, not a different robustness property, and
it comes with a measured regression: S5 `f2f_log_mad` 0.0794 vs 0.0679, the
worst of the nine non-MDA arms, and `nf_wander` 7.47 vs 4.61. Improving on the
weakest of the three incumbents while regressing temporally is not criterion C.

**The load-bearing caveat: this is not a verdict on MoGe-3 as published.** §7's
entire reason for testing it was the Step 0 → Step 3 SSR refinement ablation.
S0 established what `refine_steps` changes in the current code and confirmed
Step 0 never executes the refiner. Step 3 requires the sparse-UNet / `flex_gemm`
CUDA path: `pending_cuda`. **The model was evaluated with its distinguishing
mechanism disabled.** Recorded as `step3_status = pending_cuda`, not
approximated, not substituted, not extrapolated from Step 0.

## 4. R2-6 `mda_mog_sky_l2` — FAILURE

Three independent grounds, any one of which would be enough:

1. **M-2 `b` = 0.473 is structural, not a gauge.** It compresses the range field
   by roughly a factor of two against the reference. A slope is not a gauge: no
   clip-level scale, and no member of its legal `affine_depth` family, can
   remove it. Every other arm sits in 0.75–1.37.
2. **S5 fails the one criterion FREEZE C7 calls non-benign.** `f2f_log_mad`
   0.1743 — worst on all six clips, 2.2× the next worst — and `wander_ratio`
   11.06. Under C7 a clip-constant scale offset is absorbable by
   `beta' = beta/s`; a scale that moves ~19 % between adjacent frames would
   require the water's attenuation to change every 1/30 s in step with the
   estimator. For a pipeline that reads range into a physical attenuation model
   this is disqualifying on its own.
3. **Its reason for inclusion dissolved.** §12 admitted MDA specifically because
   Round 1 observed that "DA3 fills the open wreck_07 crane lattice with a solid
   surface". §3 Part A showed that observation was an artefact of *our* wrong
   z-vs-range convention and wrong fitting family. Corrected DA3 resolves the
   lattice (`gap` +0.411, 4 % members erased) and does so **better than MDA**
   (+0.226, 29 % erased). The failure MDA was brought in to fix was ours, it is
   fixed, and MDA does not fix it better.

**Why this is FAILURE and not SPECIALIST WIN.** MDA has two genuinely good
properties and neither is a specialist win. Its `fill` of −0.004 is the best of
any arm — *no false filled surface*. But it achieves that by not committing: it
erases 29 % of members and is **the only arm that inverts openings** (4 %
scored nearer than their own member). "Does not fill the hole" is not a win when
paired with "does not find the strut, and sometimes reverses them." Its
local-surface stability (S5 `local_dlog` 0.0174, 3rd of ten) is real and is
recorded, but a locally smooth surface under a globally wrong and drifting range
map is not usable geometry.

**Its multi-hypothesis mechanism does not do what it was tested for.** §12 asked
whether the mixture fixes flying points / solid fill and whether mixture
probabilities correlate with actual failure. The mixture **does not commit**
(median entropy 1.21–1.25 against a maximum of ln 4 = 1.386; 67–85 % of pixels
select a pairwise midpoint rather than an expert), and its confidence-like
quantities point the **wrong way** against per-frame M-1 — pooled Spearman
−0.222 for entropy, +0.116 for the top-1/top-2 margin, with the sign flipping
clip to clip, failing the predeclared criterion in
`outputs/r2_mda_ambiguity.json`. Per §12 these remain **ambiguity quantities,
not calibrated confidence**, and that is now a measured statement rather than a
caution.

## 5. R2-4 `pxdepth` — FAILURE

Not on its medians, which are mid-pack and in places good: M-4 0.0221 places
boundaries better than `moge2_vitl` (0.0320) and level with corrected DA3
(0.0223), S5 `local_dlog` 0.0151 is second-best of ten and `nf_wander` 1.390 is
the best of ten.

**The ground is a rank inversion, and it is reference-independent.** On
`cenote_01` the frozen clip fit came out at `s = −0.2701`. Measured before any
alignment — per-frame Spearman between the untouched native field and the
reference, which no monotone gauge can move — that clip returns **−0.298 median,
negative on 79 % of frames, with the sign flipping between −0.871 and +0.811**,
against +0.938…+0.996 on the other five clips through the identical code path
and grid map. It is not a harness defect: a mis-sampling does not spare five
clips and invert the sixth.

Pre-C2, the *disagreement* cannot be attributed — a cave interior is exactly
where a multi-view product is weakest. **The instability can.** A multi-view
product over a continuous 48-frame shot does not reverse its own depth ordering
between adjacent frames. Whatever share of the disagreement belongs to the
reference, the frame-to-frame sign flip is PXDepth's, and it produces the
largest single-clip temporal failure in S5 (`wander` 65.9, `f2f` 1.954 — ×7
between adjacent frames, six times MDA's worst clip).

**One of the six frozen clips is one sixth of the frozen set, not an outlier to
be dropped.** CLAUDE.md invariant 6 forbids concluding from the categories that
happened to work. Excluding `cenote_01` PXDepth's M-6 goes to exactly 1.000 and
it looks like a competent structure-preserving predictor; both rows are reported
in S3 and the six-clip row is the frozen result. A geometry source that inverts
depth order on cave/swim-through footage cannot be a restoration fallback for
this project, whose frozen test set is substantially cave and swim-through.

Two further facts are recorded but are **not** the ground for this
classification, because neither is about geometry: its licence is **UNDECLARED**
(research-only, none inferred, §10) and it is the slowest arm in Round 2 by an
order of magnitude (CPU, 22.25–23.68 s/frame).

## 6. `dav2_small` — ELIMINATION WITHDRAWN, then RETAINED on S4

This is the uncomfortable one and it gets the same treatment DA3 got.

Round 1 eliminated `dav2_small` on numbers that **Part D proved were our
defect**, not the model's: M-1 0.1761 → **0.1094**, M-3 rel 27.50° → **12.65°**,
M-4 0.1022 → **0.0164**, M-5@0.25 0.1172 → **0.0052** — ordinal violations fell
95 %. (Those figures fold in the later §4 convention repair as well as Part D;
the grid repair alone gave 0.1092 / 12.72° / 0.0167 / 0.0057, so essentially all
of the movement is Part D.) It now sits **second of twelve on M-1, ahead of
corrected DA3 (0.1476)**,
second-best M-3 rel, and third-best M-4. §4 said "if it remains clearly
eliminated: STOP." **It did not remain clearly eliminated**, so the stop
condition was not met and the elimination cannot simply be restated.

Applying to DA v2 the same standard applied to DA3 in §3 Part A: a Round-1
verdict produced by our own broken harness is withdrawn, not defended.

**Why it is not simply promoted either.** Its weakness is concentrated where the
reference cannot see it, which is exactly the situation §18 exists for:

- **Tier-A coverage 0.464** — it declines to predict on **more than half** the
  annotated open area, the worst of all thirteen arms by a wide margin.
- **Edge gain 5/2 = 2.51**, also the worst: its depth edge is displaced several
  pixels inward, and it only separates an opening once you erode 5 px into it.
- The §18 visual is explicit — a "smooth blob" at the crane head, with
  `gap` +0.165, third-worst.
- Near field is its worst band (2–3 m bin 0.487), which is the expensive end for
  attenuation and backscatter.

And the tension named in §1 applies to it directly: `dav2_small` scores well on
M-1 *and* badly at the lattice, and F1 says those are not two independent
results. Some of its M-1 standing may be agreement with a reference that is
itself blind there.

**What it has never been measured on: S4.** Appearance invariance was run for
four arms and `dav2_small` was not one of them — it had been eliminated. That is
the single largest gap in the evidence, and it is the measurement most likely to
be decisive: DA v2 is a *disparity* model, §20 F1 found every measured arm reads
veiling as a depth cue, and the project's own gray-world baseline
(`channel_neutralize`) is already MapAnything's worst ordinary perturbation.
1 248 inferences at 0.196 s/frame is ~4 minutes. Refusing to spend four minutes
and instead restating a withdrawn elimination would be exactly the Round-1
mistake.

**Advances to S4 as a measured candidate, not as a finalist.** The S4 result
decides it.

### 6.1 The S4 result — RETAINED, advances to S6

S4 was run (1 248 inferences, 312 s, peak RSS 0.69 GB) and it does not disqualify
the arm. It comes second of five on median local deformation under appearance
change (0.0181, against corrected `da3mono_large` 0.0128 and `mapanything_n1`
0.0200), holds the **lowest p95 in the field** (0.0597) and the second-lowest
worst case (0.0678), and its constant scale moves by `max |log σ| = 0.073` where
the incumbent's moves by 0.348. On `channel_neutralize` — the project's own
gray-world baseline, and MapAnything's worst ordinary perturbation — it deforms
2.8× less (0.0224 vs 0.0619) and drifts a seventh as much (wander 1.085 vs
1.616). It shows the same cue-conflict sensitivity as every other arm (2.0×
against the depth-consistent control, §20 F1) at the second-smallest absolute
magnitude in the field.

Two things this is **not**. It is not evidence that DA v2's geometry is better:
S4 measures a model against itself, and an arm can be perfectly invariant about
the wrong geometry — its S3 M-1 is 0.109 against MapAnything's 0.085. And its σ
stability is not the same claim as the incumbent's σ instability, because DA v2
asserts no metric scale at all; what stayed steady is a frozen affine gauge, not
a metric assertion (§20 F7). The one place that gauge does move is where the
fitted offset dominates the fitted slope — `cenote_01` and `wreck_01`, wander
2.73 and 2.39 (§20 F8).

**Verdict: RETAINED. Advances to S6 (§22) as the third arm.** The grounds are
narrow and worth stating as such: it is retained because its elimination was
invalid, it is the only arm besides the two incumbents with a complete S2–S5
record, and on §18 it does separate open space from lattice members where the
incumbent does not (`gap` +0.165 against `mapanything_n1`'s +0.006 and the blind
reference's +0.000) — while separating far less than corrected DA3 (+0.411) and
erasing 21 % of members against DA3's 4 %. It is **not** retained on a claim of
superiority over either incumbent, and S6 is where the three are compared on the
only thing the project actually needs from them.

## 7. What did NOT advance, and the honest headline

**No Round-2 challenger advances.** Zero of the three that produced primary
results clear A, B or C; three of six were never measured.

§6 set the goal of Round 2 as determining "whether newer/specialized monocular
geometry methods materially change the pre-C2 conclusion reached by Round 1."
On the evidence obtained: **they do not.** The Round-1 pre-C2 conclusion is
unchanged by MoGe-3 Step 0, MDA and PXDepth.

**The materially changed conclusions in Week 4A came from repairing our own
work, not from any new model:**

1. Part A's DA3 z-depth repair reversed an elimination-grade Round-1 finding —
   corrected DA3 resolves the crane lattice it was recorded as filling.
2. Part D's grid-map repair removed a harness artefact that Round 1 had read as
   a property of four models, and withdrew `dav2_small`'s elimination.
3. §18 established that the provisional reference is blind to thin structure and
   that the S3 leader inherits that blindness.

That is the §26 headline and it should not be softened: **the largest source of
error found in Week 4A was Week 4A.**

## 8. Carried forward

| | |
|---|---|
| **To S4 (§20)** | `dav2_small` — **run, cleared** (§6.1). Incumbent finalists `mapanything_n1` and corrected `da3mono_large` already measured; `wat3r_n1` and `metricanything_pointmap` measured and retained as context. |
| **To S6 (§22)** | `mapanything_n1`, corrected `da3mono_large` and `dav2_small`. Round-1 S6 covered only the first two and DA3's is convention-affected, so it must be recomputed; `dav2_small` cleared S4 (§6.1) and has never had S6 run at all. |
| **Not carried** | `moge3_vitl`, `mda_mog_sky_l2`, `pxdepth`, `moge2_vitl`, `metricanything_pointmap`, `wat3r_n1`, `foundationgeo_11` and its two ablation arms. |
| **Untested, never eliminated** | `surge_large`, `hyden`, `pointdit_l_512`, MoGe-3 Step 3. |
| **Open for C2, not resolvable here** | whether `moge2_vitl` / `metricanything_pointmap`'s large §18 `gap` is lattice acuity or far-field expansion (`r_sea` 175 m / 85 m vs ~31–34 m); whether MapAnything's appearance-driven metric scale is right; whether `cenote_01`'s reference or PXDepth is at fault for their disagreement (the sign flip is PXDepth's either way). |
