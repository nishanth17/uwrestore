# Round 2 — S5: independent-frame temporal stability

**Status: PRE-C2.** Nothing here is objective temporal error. The reference is
the Week-3 persisted multi-view range product, a *provisional hypothesis*, and
S5 does not even use it as a target — it measures each model against **its own
past frames**. So every number below is *self*-consistency: how much a model's
geometry moves when the scene barely moved. A model can be perfectly
self-consistent and wrong, and a model can wobble because the scene genuinely
changed. No winner is declared here.

**Strict N=1 held throughout.** Every one of the 288 frames was inferred
independently — one image per call, no neighbour, no cached state. The sequence
is used only *after* inference. SEA-RAFT optical flow supplies correspondence
for evaluation only and never reaches a depth model.

- Raw per-frame trajectories: `outputs/r2_s5/r2_s5_raw.json`
- Stage summary (source of truth from here on): `R2_S5_results.json`
- Policy: `R2_S3_policy.json` (corrected DA3 `z_depth`/`affine_depth`, corrected
  MDA `z_depth`, Part-D grid-map repair)
- Footage: the six frozen clips, 48 frames each, 288 frames per arm. Not
  resampled.

## What the columns mean (FREEZE C7)

Under C7 the per-frame scale `s_t` is read as a *gauge*, and a rescaled depth
field `d'_t = s_t · d_t` is physically consistent with the *same* scene under
attenuation coefficients `beta'_t = beta / s_t`. That reading is what makes the
distinction below load-bearing:

- **`log_std`, `wander_ratio`** — the whole-clip excursion of `s_t`. A large
  but *slowly drifting* value can still be a gauge choice.
- **`f2f_log_mad`** — the frame-to-frame part. This is the one C7 calls a real
  failure: absorbing it would require the water's physical properties to change
  from frame to frame *because the estimator changed its mind*, which is not a
  gauge, it is a contradiction.
- **`local_dlog`, `local_p95`** — measured *after* the pairwise global scalar is
  removed. Whatever is left cannot be explained as a gauge at all: it is the
  surface itself deforming between frames.
- **`nf_wander`** — excursion of the near/far ratio, i.e. whether the model's
  *shape* (not just its scale) is breathing.
- **`jitter_px`** — depth-discontinuity displacement, in evaluation-grid pixels.

## Result — median over the six frozen clips

Sorted by `local_dlog`, the quantity that survives removal of the global scalar.
**No weighted score; no ranking is combined across columns.**

| arm | f2f_logMAD | wander | log_std | local_dlog | local_p95 | jitter_px | nf_wander |
|---|---|---|---|---|---|---|---|
| `da3mono_large` (corrected) | 0.0540 | 2.090 | 0.2008 | **0.0119** | **0.0268** | 0.000 | 1.992 |
| `pxdepth` | 0.0596 | 3.338 | 0.3119 | 0.0151 | 0.0308 | n/a | **1.390** |
| `dav2_small` | 0.0543 | 2.840 | 0.2541 | 0.0171 | 0.0346 | 0.000 | 1.467 |
| `mda_mog_sky_l2` | **0.1743** | **11.063** | **0.6560** | 0.0174 | 0.0467 | 0.000 | 5.646 |
| `mapanything_n1` | 0.0503 | 1.842 | 0.1490 | 0.0189 | 0.0420 | 1.000 | 2.889 |
| `metricanything_pointmap` | 0.0604 | 2.292 | 0.1952 | 0.0214 | 0.0373 | 0.000 | 6.982 |
| `wat3r_n1` | **0.0391** | 2.293 | 0.2579 | 0.0217 | 0.0465 | 0.000 | 3.618 |
| `foundationgeo_11` | 0.0501 | 1.901 | **0.1273** | 0.0239 | 0.0408 | 0.000 | 3.118 |
| `moge2_vitl` | 0.0679 | 2.385 | 0.2114 | 0.0245 | 0.0505 | 0.000 | 4.612 |
| `moge3_vitl` (Step 0) | 0.0794 | 2.372 | 0.2223 | 0.0252 | 0.0455 | 0.000 | 7.470 |

`jitter_px` is quantised by the evaluation grid (`EVAL_DOWNSAMPLE = 4`); the
0.000 entries mean *below one grid pixel*, not zero, and the column separates
nothing here. It is reported because Round 1 reported it, not because it
discriminates. `pxdepth`'s entry is `n/a` because its `cenote_01` clip yielded
no valid discontinuity measurement — the same clip whose S3 boundary metric is
also undefined (see Finding 4) — so the median over six clips is undefined
rather than zero.

**The `pxdepth` median is not a summary of `pxdepth`.** Five of its six clips
sit at or better than the median arm; `cenote_01` is off the scale (`f2f`
1.9542, `wander` 65.9). Reading its median row without Finding 4 would be
reading an average across a working model and a broken one.

## OLD vs CORRECTED (§3 A3 — every load-bearing metric)

Round-1 S5 medians against the same quantity recomputed under the Round-2
policy. Two independent repairs are in play and they land on disjoint arms,
which is what makes the attribution clean:

| arm | f2f_logMAD | local_dlog | cause of change |
|---|---|---|---|
| `mapanything_n1` | 0.0503 → 0.0503 | 0.0189 → 0.0189 | **unchanged — control** |
| `wat3r_n1` | 0.0391 → 0.0391 | 0.0217 → 0.0217 | **unchanged — control** |
| `da3mono_large` | 0.0470 → 0.0540 | 0.0096 → **0.0119** | Part A: DA3 is z-depth, fitted `s·z+t`, converted by `r = z·rho` |
| `dav2_small` | 0.0751 → **0.0543** | 0.0108 → 0.0171 | Part D: grid-map repair |
| `foundationgeo_11` | 0.0543 → 0.0501 | 0.0230 → 0.0239 | Part D: grid-map repair |
| `metricanything_pointmap` | 0.0773 → **0.0604** | 0.0197 → 0.0214 | Part D: grid-map repair |
| `moge2_vitl` | 0.0693 → 0.0679 | 0.0232 → 0.0245 | Part D: grid-map repair |
| `moge3_vitl` | — | — | new in Round 2 |
| `mda_mog_sky_l2` | — | — | new in Round 2 |
| `pxdepth` | — | — | new in Round 2 |

The two arms on the network grid are bitwise unchanged, exactly as in S2 and
S3. That is the control: neither repair touched anything it should not have.

DA3's corrected temporal numbers are slightly *worse* than its Round-1 ones —
`local_dlog` 0.0096 → 0.0119, `f2f_logMAD` 0.0470 → 0.0540. The repair was not
performed to improve DA3 and did not. It still leaves DA3 with the **lowest
`local_dlog` and lowest `local_p95` of all nine arms**, i.e. the most
frame-to-frame-stable *surface* once the global scalar is removed — and that
conclusion now rests on the correct semantics rather than on a fit that was
silently absorbing a radial secant term.

## Finding 1 — MDA's instability is frame-varying, which is the not-benign kind

`mda_mog_sky_l2` is the extreme arm and the extremity is confined to one place:

| | MDA | next worst | median arm |
|---|---|---|---|
| `f2f_log_mad` | **0.1743** | 0.0794 (`moge3_vitl`) | 0.0543 |
| `wander_ratio` | **11.06** | 2.84 (`dav2_small`) | 2.29 |
| `log_std` | **0.6560** | 0.2579 (`wat3r_n1`) | 0.2114 |
| `local_dlog` | 0.0174 | — | 0.0214 (**MDA is 3rd best**) |

Per clip its `f2f_log_mad` is 0.118 / 0.197 / 0.318 / 0.095 / 0.162 / 0.187 —
worst on every one of the six, and worst by a wide margin on `cenote_01`.

So MDA's *local surface* is among the steadier ones, and its *global scale*
moves by a factor of 11 across a 48-frame clip and by ~19 % between adjacent
frames. Under C7 this is the failure mode that cannot be waved away: a constant
clip-wide offset would be absorbed by `beta' = beta/s`, but a scale that jumps
frame to frame would demand water whose attenuation changes every 1/30 s in
step with the estimator. For a restoration pipeline that reads range into a
physical attenuation model, this is disqualifying on its own.

It is also consistent with what S0 and the ambiguity analysis already found:
MDA's mixture *does not commit* (median entropy 1.21–1.25 against a maximum of
ln 4 = 1.386; 67–85 % of pixels select a pairwise midpoint rather than an
expert), and the mixture's own confidence quantities do **not** track its
errors — Spearman against per-frame M-1: entropy −0.222, top-1-minus-top-2
margin +0.116, both pointing the *wrong* way. A model that re-picks among
non-committed hypotheses each frame is expected to produce exactly this
signature. These remain **ambiguity quantities, not calibrated confidence.**

## Finding 2 — MoGe-3 Step 0 does not inherit MoGe-2's temporal behaviour, and is worse

MoGe-3 was the challenger that improved on MoGe-2 in S3 (M-1 0.1694 vs 0.1958,
M-4 0.0143 vs 0.0320, M-6 0.98 vs 1.07). That improvement does **not** carry
into temporal stability — it reverses:

| | `moge2_vitl` | `moge3_vitl` Step 0 |
|---|---|---|
| `f2f_log_mad` median | 0.0679 | **0.0794** |
| worst clip | 0.1420 (`wreck_01`) | **0.2476** (`wreck_01`) |
| `cenote_01` | 0.2009 | 0.1747 |
| `local_dlog` | 0.0245 | 0.0252 |
| `nf_wander` | 4.61 | **7.47** |

The local surface is a tie (0.0245 vs 0.0252, well inside the clip spread). The
difference is entirely in the global scale trajectory and in `nf_wander`, i.e.
MoGe-3's *shape* breathes more across a clip than MoGe-2's. Two clips carry it:
`wreck_01` (0.1420 → 0.2476) and `wreck_03` (0.0784 → 0.1023).

This is a genuine trade-off and is recorded as one rather than resolved: MoGe-3
Step 0 buys per-frame local geometry and boundary behaviour at the cost of
per-clip scale steadiness. Whether the SSR refinement steps change it is a
Step-3 question that S5 has not answered, because only Step 0 was run through
S5; the Step-0/Step-3 comparison lives in S0/S3 and is not extrapolated here.

## Finding 3 — the global-scale and local-surface orderings are close to independent

The two orderings barely agree. `wat3r_n1` has the *best* `f2f_log_mad`
(0.0391) and a middling `local_dlog` (0.0217); `da3mono_large` has the *best*
`local_dlog` (0.0119) and a middling `f2f_log_mad` (0.0540); MDA is worst on one
and third-best on the other. `mapanything_n1`, the S3 leader by a wide margin,
is 4th on `local_dlog` and 2nd on `f2f_log_mad` — good, not dominant.

`pxdepth` sharpens the point: it holds the **2nd-best `local_dlog` (0.0151)**,
the **2nd-best `local_p95` (0.0308)** and the **best `nf_wander` (1.390)** of all
ten arms, and it is simultaneously the arm with the worst single-clip failure in
the stage by a factor of six (Finding 4). Column-wise it looks like a
near-incumbent; clip-wise it contains a collapse.

This matters for §19 reduction: "temporally stable" is not one property, and an
arm cannot be eliminated or retained on a single S5 column — nor on a median
across clips. The two columns
answer different questions — *does the gauge drift* and *does the surface
deform* — and the C7 reading says only the second is unambiguously a defect,
with the frame-to-frame part of the first joining it.

## Finding 4 — `pxdepth` is stable on five clips and collapses on `cenote_01`

Per clip, `f2f_log_mad` / `wander_ratio`:

| clip | `pxdepth` f2f | wander | fitted `s` median | coverage |
|---|---|---|---|---|
| `wreck_07` | 0.0322 | 1.97 | 1.678 | 0.747 |
| `wreck_05` | 0.0394 | 1.92 | 2.059 | 0.711 |
| `cenote_01` | **1.9542** | **65.93** | **0.258** | 0.942 |
| `swimthrough_02` | 0.0489 | 1.62 | 2.143 | 0.752 |
| `wreck_01` | 0.0704 | 4.71 | 0.393 | 0.991 |
| `wreck_03` | 0.1430 | 9.42 | 1.184 | 0.779 |

On three of the six clips `pxdepth`'s `f2f_log_mad` sits below the median arm's
median (0.057), and on `wreck_07` (0.0322) below *every* arm's median. On
`cenote_01` its per-frame gauge moves by a factor of 66 across the 48 frames and
by ~×7 between adjacent frames (`exp(1.9542) = 7.06`) — six times
`mda_mog_sky_l2`'s worst clip (0.318), which was the previous extreme of the
stage.

This is not an alignment artefact — but the reason is not the residual. The
clip's per-frame `log_residual_mad` is an ordinary 0.070, and that number is
**not** evidence of a good fit here: S3 established that on this clip PXDepth's
field is rank-*inverted* against the reference (median Spearman −0.298, sign
flipping frame to frame between −0.871 and +0.811), so the frozen clip fit went
to a negative slope `s = −0.2701` and the aligned field is close to degenerate.
A near-flat prediction against a reference whose own log1p spread is only 0.68
produces a small residual by construction. What the trajectory measures is the
gauge being re-solved from scratch every frame against a field whose order keeps
reversing. The mechanism is in S3 §3 R2-4, measured without any alignment at
all, and the same clip is the failure in both stages.

It is the same clip that carried `pxdepth`'s S3 pathology (clip-level `b` 0.118
against 0.39–1.01 elsewhere, ordinal-25 0.347, M-6 2.05, boundary metric
undefined). Two independent stages, one clip, one failure. `cenote_01` is the
frozen set's cave/cenote clip: large uniform-texture volumes, few surfaces at
mid-range, strong near-field walls. A pixel-space affine-invariant predictor with
no metric anchor has the least to hold onto exactly there.

Under FREEZE C7 this is the disqualifying kind of instability, not the benign
kind: a clip-constant offset would be absorbed by `beta' = beta/s`, but a gauge
that jumps ×7 between adjacent frames would require the water's attenuation to
change every 1/30 s in step with the estimator. On five clips `pxdepth` would
pass that test comfortably; on the sixth it fails it outright. §19 has to
classify it on both facts, and the failure is not rescued by the median.

## Alignment used

Per §16, one common **policy** (clip scope, Huber IRLS, caller converts the
reference side), representation-specific **space**. Families actually fitted
here: `scale` for the metric point-map arms (`mapanything_n1`, `wat3r_n1`,
`moge2_vitl`, `moge3_vitl`, `foundationgeo_11`, `metricanything_pointmap`),
`affine_depth` for `da3mono_large` and `mda_mog_sky_l2` (both z-depth by source
code), `affine_disparity` for `dav2_small`, `affine_log1p_depth` for `pxdepth`
(frozen in `R2_S3_policy.json`; z-depth by source code). No universal `a·d+b`
was applied. Median clip-level `log_residual_mad`: 0.102 (`mapanything_n1`) to
0.215 (`moge2_vitl`); `pxdepth` 0.058–0.125, its largest on `wreck_01`. Its
`cenote_01` value (0.070) must **not** be read as a good fit: see Finding 4.

## Not in this stage

- `surge_large` — `pending_cuda`, measured OOM kill, evidence in
  `R2_S0_SEMANTICS_RUNTIME.md`. Excluded, not failed.
- `hyden`, `pointdit` — `pending_checkpoint` (gated repositories / released
  checkpoint omits its encoder by design). Excluded, not failed.
- MoGe-3 Step 3 — S3-scope ablation; not run through S5.

## Pre-C2 reading

No Round-2 challenger improves temporal stability over the incumbents.
`mda_mog_sky_l2` fails the frame-varying criterion outright and by a large
margin; `moge3_vitl` Step 0 is temporally *worse* than the MoGe-2 incumbent it
was meant to supersede, while being better in S3 local geometry; `pxdepth`
matches the best incumbent on the local-surface columns on five clips and then
fails the frame-varying criterion on the sixth by the largest margin measured in
this stage. The Round-1 pre-C2 conclusion is unchanged by S5. Whether MDA's scale trajectory is a defect
*of the model* or of a monocular estimator meeting genuinely ambiguous
underwater scenes cannot be settled here — that is a C2 measurement.
