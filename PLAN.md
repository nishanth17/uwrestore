# Underwater Restoration — Plan

Session-based, not calendar-locked.

Skip a session if life happens; do not skip a gate.

A “week” below is a logical phase, not necessarily seven calendar days. One focused session should advance one clearly defined gate. Do not begin the next gate merely because time remains in the session.

The project goal and core invariants live in `CLAUDE.md`. This file is the execution roadmap and sequence of hypotheses, not a duplicate architecture specification.

---

# Operating loop

Every implementation/research session follows the same loop.

## Before changing anything

Run:
```text
uw score
```

against the frozen test set.

Compare the result to the latest applicable `LOG.md` entry.

If the result differs unexpectedly, stop before adding new functionality and determine why:

- code regression,
- dependency/environment change,
- metric-definition change,
- model/checkpoint change,
- test-data change,
- nondeterminism,
- numerical precision change,
- accidental preprocessing difference.

A new experiment is not valid until the previous baseline is reproducible.

## During the session

Make the smallest change needed to test the current hypothesis.

Do not add speculative future-stage infrastructure.

Generate enough visual diagnostics to understand failures rather than relying exclusively on aggregate numbers.

## At the end

Run the frozen evaluation again.

Append to `LOG.md`:

- hypothesis,
- implementation/configuration,
- active pipeline stages,
- data/clip/frame ranges used,
- relevant model/checkpoint,
- evaluation resolution,
- before/after metrics,
- valid-pixel/coverage statistics where relevant,
- out-of-range/clipping statistics where relevant,
- visual observations,
- failure cases,
- surprises,
- next hypothesis.

Do not write “better” without specifying **better by which criterion**.

---

# Evaluation principles

The project evaluates several independent properties. Do not collapse them prematurely into one score.

## Color fidelity

Primary controlled measure:

- chart-referenced CIEDE2000 / ΔE00.

Lower is better.

Use only where a known color reference exists.

## Temporal appearance stability

**Canonical regression values** — the illumination-aware form, fitted on aligned
ORIGINAL frames and frozen before scoring corrected output:

- `illumination-aware MC-Warp@1`
- `illumination-aware MC-Warp@4`
- `illumination-aware MC-Warp@8`

Lower generally indicates greater motion-compensated temporal consistency.

**Always reported separately, never folded into the canonical value:**

- raw MC-Warp@1/@4/@8,
- the alignment-robust companion,
- valid correspondence coverage and status (`low-coverage`,
  `illumination-confounded`, `illumination-identity:<reason>`),
- flow-aligned temporal ΔE00,
- the input baseline (`--method none`).

Exact semantics are frozen in `experiments/week2b_temporal/FINDINGS.md`.
There is no weighted master score.

## Temporal color stability

Use flow-aligned temporal ΔE00 as a separate diagnostic.

This is especially important for:

- red-channel pumping,
- white-balance oscillation,
- green/magenta drift,
- unstable attenuation parameters.

Do not treat temporal ΔE00 as a standardized replacement for MC-Warp.

## Signal recoverability

A correction can produce an attractive output even when the source channel contains little trustworthy information.

Track, where appropriate:

- per-channel clipping/saturation fraction,
- per-channel near-floor fraction,
- robust channel noise/SNR estimates where measurable,
- corrective gain magnitude,
- post-correction out-of-range fraction.

Prefer estimating noise from controlled or locally flat regions rather than global image variance, which confounds texture with noise.

A huge gain on a signal-starved red channel should be flagged as low-confidence even if the output visually improves.

## Spatial fidelity

Temporal metrics can be gamed by blur.

Always visually inspect:

- texture/detail retention,
- edge integrity,
- halos,
- local contrast,
- spatial artifacts.

Later, add PSNR/SSIM or another reference metric only where a legitimate clean reference exists.

## Validity and uncertainty

Never allow a method to obtain a good score merely by masking difficult regions.

Whenever masking is involved, report:

- score,
- valid coverage,
- reason for invalidation.

A score without its coverage is incomplete.

---

# Frozen test set

Maintain a small representative real-world suite rather than a giant collection.

Core categories:

- normal swim-through,
- murky / low visibility,
- suspended particulate,
- moving animal,
- artificial dive lights,
- distance variation,
- strong camera motion,
- clipped / signal-starved channels when available,
- controlled chart footage once captured.

Test media remain local-only.

`data/testset/manifest.json` records what is expected to exist.

Do not silently replace difficult clips with easier ones after seeing results.

Additional controlled footage may be added, but changes to the frozen suite must be explicitly logged.

## Two roles: diagnosis and realism

The existing GoPro clips were captured for restoration and temporal evaluation.
They are genuinely useful and they stay exactly as frozen — but they were not
shot to answer geometry or illumination questions, so a failure on them is hard
to attribute. Week 3 needs to separate bad parallax from bad camera physics from
bad matching from bad scale; Week 6B needs to separate illumination from albedo.
Footage not captured with those questions in mind cannot make those
distinctions.

So the suite gains a second role rather than a replacement:

```text
CONTROLLED (new, purpose-built)   decides WHY methods differ
  week3_geometry     C1   rigid textured reef/rock/wreck, deliberate
                          lateral/arc motion, diffuse light, no torch sweep,
                          minimal animals/vegetation, 20-40 s
  week3_scale        C2   same scene family + known-size target/chart at
                          several measured distances, with target-plane pose
                          constrained; underwater checkerboard if practical
  week6b_illum       L1/L2/L3  ambient control, controlled artificial light,
                          mixed -- specified in Week 6B, captured later

EXISTING FROZEN CLIPS             decide WHETHER THE WINNER SURVIVES real diving
  swimthrough / murky / distance / lights   generalisation check, applied to
                                            the selected method only
```

**New data for diagnosis, existing data for realism.** This is deliberately a
small addition — two controlled acquisitions for Week 3, not a new dataset.
Selection happens on the controlled clips; the existing clips then say whether
the choice holds up on normal footage. A method that wins on C1/C2 and collapses
on `murky` or `swimthrough` has not won.

Register each new acquisition in `data/testset/manifest.json` when captured, log
the addition, and keep the media local-only like everything else. Adding these
does **not** alter any existing clip, any existing metric, or any frozen
Phase 2A/2B result.

---

# Week 1 — Skeleton, color pipeline, and evaluation foundation

## Goal

Build a trustworthy input/output/evaluation substrate before implementing meaningful restoration.

## Deliverables

### Unified data model

Photo and video both use the same `FrameSequence` abstraction.

A photo is conceptually a one-frame sequence.

Frames carry:

- linear-light RGB data,
- source metadata,
- frame index/time,
- frame rate where applicable,
- original transfer-function/profile metadata.

### Explicit transfer functions

Supported source encodings must be explicit.

Initial paths may include:

- standard sRGB,
- validated GoPro Flat / Protune transfer handling,
- externally decoded already-linear RAW data (`raw_linear`).

Do not infer a transfer function from filenames.

Do not claim native RAW support merely because already-linear TIFF/EXR input is accepted.

### Linear-light processing

All restoration/math operates on linear RGB unless a stage explicitly and temporarily enters another representation for a justified reason.

Display/export performs the appropriate encoding afterward.

### Initial baseline

Implement gray-world as a deliberately simplistic global white-balance control.

Purpose:

> Determine what can be gained from one global multiplicative RGB correction before introducing underwater physics.

### Color metric

Implement and validate CIEDE2000:
```text
linear RGB
    ↓
XYZ / D65
    ↓
Lab
    ↓
ΔE00
```

Validate CIEDE2000 with published/reference test vectors.

Chart sampling/layout must be explicit rather than guessed.

### Temporal placeholder

Week 1 may initially contain a simple temporal placeholder only to prove the evaluation plumbing.

It must be clearly labeled inadequate and replaced in Week 2.

### Frozen test-set structure

Create manifest, categories, chart-reference schema, local-output conventions, and `LOG.md`.

---

## Camera-linearization calibration

Treat camera transfer-function inversion as a **calibration problem**, not merely a formula copied from documentation.

Controlled test:

1. capture a RAW still,
2. capture Flat-profile video of the same static scene/settings as closely as practical,
3. externally decode the RAW into a trusted linear representation,
4. reconstruct linear values from the video profile,
5. compare corresponding patches/regions.

Assess:

- tone response,
- channel relationships,
- shadow reconstruction,
- highlight reconstruction,
- clipping,
- noise amplification.

Do not assume inverse transfer functions recover information destroyed by codec quantization or sensor noise.

---

## Channel-information diagnostics

Linearization cannot recover information that was never recorded.

Add diagnostics sufficient to detect cases such as an underwater red channel being:

- clipped,
- near the noise floor,
- heavily quantized,
- amplified by a huge corrective gain.

Track at minimum where practical:

- per-channel near-floor fraction,
- per-channel saturation fraction,
- correction gain,
- output out-of-range fraction.

Add robust SNR/noise estimation once suitable controlled regions exist.

Do not use whole-image RGB variance as “noise variance.”

---

## Gate

Proceed only when:

- `uw score` runs reproducibly on stills and clips,
- linear-light round-trip tests pass,
- ΔE00 implementation is validated,
- gray-world is deterministic/non-mutating,
- source transfer functions are explicit,
- **for the Flat/Protune path specifically:** the calibration experiment either
  passes within documented tolerance or its error is understood, *before that
  profile is used as a foundation for physical restoration or for any claim
  derived from it*. Pending GoPro Flat/RAW calibration is acquisition-dependent
  and does **not** block work on validated `srgb` or declared `raw_linear`
  sources — Weeks 2+ may proceed on those paths,
- signal-clipping/floor behavior is visible rather than hidden,
- frozen baseline results are recorded.

If Flat reconstruction is materially unreliable, fix acquisition/linearization assumptions before building physics on top of it.

---

# Week 2 — Real evaluation rig, optical flow, simple baselines, and ablations

## Goal

Build the measurement system that later stages must beat.

Week 2 intentionally mixes:

### Restoration controls

- gray-world,
- white-patch,
- CLAHE,
- manual DaVinci Resolve reference.

### Measurement instruments

- selected optical-flow backend,
- forward/backward validity,
- MC-Warp,
- temporal ΔE00,
- chart ΔE00,
- signal/range diagnostics.

The sophisticated part of Week 2 is primarily the **measurement system**, not restoration quality.

---

## Phase 2A — Optical-flow backend selection

Evaluate a bounded set of meaningfully different optical-flow approaches on real underwater footage.

Initial candidates:

- SEA-RAFT,
- FlowIt,
- VideoFlow-MOF,
- optionally WAFT if integration remains cheap and it directly challenges the leading choice.

Do not turn this into a leaderboard reproduction project.

Compare on:

- normal swim-through,
- murky water,
- moving animals,
- bubbles/particles,
- artificial lights,
- strong motion,
- textureless areas.

Measure:

- motion-compensated raw-frame residual,
- forward/backward round-trip error,
- valid coverage,
- runtime,
- memory,
- qualitative flow/residual behavior.

Use a common evaluation resolution where possible.

Validate wrapper correctness using known synthetic translation.

Use standardized forward/backward consistency rather than comparing incompatible model-native confidence masks directly.

Stop adding models once additional architectural sophistication no longer materially changes the relevant alignment result.

---

## Phase 2A — result (2026-08-29)

Four backends evaluated at a common 960x540 grid, five clips, lags 1/4/8.
Full record: `experiments/week2a_flow/FINDINGS.md`.

Phase 2A recommended SEA-RAFT-M; **Phase 2B subsequently locked it as the
canonical correspondence backend.** The failure-triggered reopening conditions
below remain valid, but selection is otherwise closed — do not re-run a backend
bakeoff.

- **SEA-RAFT-M** — **canonical backend, frozen.** 0.75 s/inference, 2.2 GB, deterministic,
  and equal-or-better than WAFT on 14 of 15 clip-lag cells when both are
  scored on a common validity mask.
- **WAFT-a1** — retained as an optional manual cross-check, never a default and
  never averaged with SEA-RAFT. 3x the
  runtime, same memory class, best coverage retention across lag, and a
  genuinely different failure mode (depth-foundation trunk vs from-scratch
  flow encoder). Where the two disagree materially, treat that clip's
  MC-Warp as low-confidence.
- **VideoFlow-MOF** — spot-check at `@1` only. MOFNet emits flow between
  *consecutive* window frames, so `@4`/`@8` require a stride-k subsampled
  window that is off its training distribution; coverage collapsed 36 points
  on `murky_shark`. Still the only backend that flags rising bubbles.
- **FlowIt-M** — dropped. Not reproducible: forward flow differs by up to
  0.858 px between identical calls in the same process, flipping 6.5 % of
  the validity mask. No large-displacement advantage to offset it.

### Frozen landscape
```text
canonical        SEA-RAFT-M
optional check   WAFT-a1
research shelf   VideoFlow-MOF   (@1 only)
dropped          FlowIt-M        (not reproducible)

watchlist:
  MEMFOF  -> only if resolution / fine structure becomes a demonstrated problem
  U2Flow  -> only if license + suitable checkpoint + inference path improve
```

Treat this as closed. Adding a fifth backend requires a *named failure* of
the canonical one, not a leaderboard result.

**Determinism is a hard requirement for a measurement instrument.** A
backend that is not bitwise reproducible makes a regression
indistinguishable from noise, which defeats this file's operating loop.
Verify it before adopting any backend, not after.

Motion-compensated warp residual agreed within ~2 % across all four
architectures on every clip. **The backend is not the constraint; the metric
definition is.**

### Models deliberately not integrated

- **MEMFOF** — Spring 1px leader, BSD-3, HF checkpoints, 2.09 GB at native
  1080p. Revisit **only if** Phase 2B leaves residual concentrated in fine
  structure (thin filaments, particle streaks, small-object edges), which is
  the resolution signature. Note it is 3-frame and inherits MOF's
  multi-lag limitation.
- **U2Flow** — unsupervised, joint per-pixel uncertainty, bidirectional
  uncertainty fusion. Closest concept to what Phase 2A actually found
  (validity semantics discriminate more than EPE). Blocked on: no visible
  license, only KITTI/Sintel-finetuned checkpoints, no demo inference path.

  A learned uncertainty head is **potentially**, not strictly, better than
  forward/backward consistency. It can itself be miscalibrated on
  out-of-distribution underwater footage, and unlike FB it is neither
  model-agnostic nor directly inspectable. Replacing FB requires empirical
  evidence of better calibration **on our clips**, not a paper claim.

  Do not import the learned-uncertainty idea into Phase 2B. The existing FB
  mask is sufficient to build the instrument. Only if Phase 2B shows mask
  semantics materially corrupting the temporal score does "learned
  correspondence uncertainty" become a motivated subproject.
- **DPFlow** — only if resolution becomes a demonstrated bottleneck.
- **CFFlow, MemoFlow, FreeFlow-L** — no public implementation as of
  2026-08-29, despite ranking 3rd, 6th and 1st on Sintel Final.

Sintel rank anti-predicted these results: the two highest-ranked candidates
were the two disqualified, and SEA-RAFT does not appear in the Sintel Final
top 15. The board's top is dominated by three-frame methods, which is the
architecture class least suited to a multi-lag metric. Do not use
leaderboard position as an argument for integration.

---

## Phase 2B — Motion-aware temporal metric

### Phase 2B result — COMPLETE AND FROZEN (2026-08-29)

Everything below this block is the **historical design brief** that was written
*before* Phase 2B ran. It is retained for provenance only. **Do not execute it.**
Its "select one", "choose one", "decide this", and "add if" instructions are all
resolved. Re-running them would reopen closed decisions.

The decisions, all frozen — full record in
`experiments/week2b_temporal/FINDINGS.md`:

```text
correspondence      SEA-RAFT-M, canonical. Estimated from the ORIGINAL input
                    frames only; corrected output never influences its own
                    correspondence. Direct t -> t+k per lag, never chained.
                    WAFT-a1 = optional manual cross-check, never a default,
                    never averaged. VideoFlow-MOF = research shelf, @1 only.
                    FlowIt-M = dropped (not reproducible).

illumination        A bounded GLOBAL scalar luminance gain + bias, applied
                    identically to R, G and B, fitted EXCLUSIVELY on aligned
                    ORIGINAL frames and FROZEN before the corrected sequence is
                    scored. Estimator: robust start -> LTS concentration ->
                    fixed-scale Huber. Gradient-domain, census and locally
                    normalised correlation were CONSIDERED AND NOT ADOPTED.

guards              Predeclared fit domain; gain sanity range [0.25, 4.0];
                    acceptance test against the input's own residual; fallback
                    to identity, which makes the canonical value EQUAL the raw
                    one and says so in `status`.

reported            raw MC-Warp@1/@4/@8; canonical illumination-aware
                    MC-Warp@1/@4/@8; uncompensated residual; motion-reduction
                    ratio; valid coverage; status; flow-aligned temporal DeltaE00;
                    alignment-robust companion (fixed 1.0 px Gaussian, global,
                    never tuned per clip, never replacing anything);
                    input baseline. No weighted master score.

status semantics    low-coverage (<50%); illumination-confounded (<1.25x);
                    illumination-identity:<reason>. Empty mask returns None,
                    which is NOT the same as zero and NOT the same as low
                    coverage.
```

Reopen only on a demonstrated failure of the instrument itself — not to
re-litigate a choice, and not because a later result is unflattering.

---

### Historical design brief (superseded by the block above)

Select one practical optical-flow backend.

Implement motion-compensated temporal evaluation using correspondence estimated from the **original input frames**.

The restored output must not influence its own correspondence estimation.

Primary metrics:
```text
MC-Warp@1
MC-Warp@4
MC-Warp@8
```

Use direct:
```text
t -> t+k
```

correspondence for each lag rather than chained adjacent flows.

Purpose:

- `@1`: rapid flicker,
- `@4`: medium-term instability,
- `@8`: slower pumping/drift.

Report valid coverage for each lag.

### What success looks like

Phase 2B succeeds when
```text
SEA-RAFT-M  +  canonical MC-Warp@1/4/8  +  input-derived illumination diagnostic
```

produces a **useful, reproducible regression metric** — one that moves when
the pipeline changes and stays put when it does not. If that holds, the
optical-flow investigation has done its job and is finished.

Do not extend the flow work to improve this. Extend the metric.

### Illumination invariance — required, not optional

Camera-mounted dive lights defeat plain MC-Warp. Measured on `lights`, the
residual reduction from motion compensation is:
```text
@1   1.14x
@4   1.07x
@8   1.02x
```

identical across all four backends to three significant figures. The lit
patch of scene travels *with* the camera, so a scene point's radiance
changes between frames. Flow tracks the texture correctly and
forward/backward consistency marks the hotspot **valid**; the illumination
change lands whole in the residual.

At `@8`, motion compensation explains ~2 % of the frame-to-frame change on
artificial-light footage.

Canonical MC-Warp therefore needs an illumination-invariant photometric
term. Candidates, increasing cost:

- per-frame gain/bias fit before differencing,
- gradient-domain or census-transform residual,
- locally normalized cross-correlation.

Choose one, state it, and treat it as canonical rather than as a companion
diagnostic. No optical-flow backend affects this.

Do not read a high MC-Warp on `lights` as pipeline instability until this is
resolved.

### Coverage gating and cross-backend comparison

Valid coverage falls sharply with lag (mean over clips, SEA-RAFT):
```text
@1   ~97%
@4   ~91%
@8   ~83%
```

Consequences:

- an MC-Warp value is not comparable to another unless coverage is
  comparable too,
- two backends' `@4`/`@8` values are **not measured on the same pixels** and
  must not be compared directly,
- when comparing backends, score both on the intersection of their validity
  masks — see
  `experiments/week2a_flow/scripts/common_mask_compare.py`.

A method can obtain a better reduction ratio purely by masking more.
VideoFlow-MOF posts the **highest** reduction on `murky_shark @8` while
discarding 37 % of the frame.

### Normalization

Absolute residual varies ~8x across clips and ~2 % across backends. Report
the reduction ratio against the uncompensated residual at the same lag
beside the absolute value, or the metric will track clip choice more than
pipeline change.

### Validity policy

Backends disagree on what to invalidate around moving objects: SEA-RAFT
marks a whole low-texture moving animal invalid, WAFT and MOF only its
outline. Excluding more is safer and measures less. Decide this from what
the metric is for, state it, and report coverage so the choice stays
visible.

Forward/backward consistency validates *geometry*, not correctness. On
near-static textureless footage all four backends reported 96-99 % valid
while disagreeing with each other by ~22 % of the motion magnitude. Treat
high coverage on low-visibility clips as "nothing contradicted the flow",
not as "the flow is right".

### Alignment sensitivity

Explicitly test integer and fractional-pixel synthetic translations.

If subpixel edge misalignment materially dominates canonical MC-Warp, add at most one separately reported alignment-robust companion diagnostic.

Do not silently redefine MC-Warp.

### Temporal ΔE00

Add flow-aligned temporal color difference.

Purpose:

> Catch color instability specifically rather than general image residual.

### Input baseline

Compute temporal metrics on input footage as context.

Do not blindly subtract input error from restored error and call the result restoration instability.

---

## Phase 2C — White-patch baseline

Implement a robust white-patch/global illuminant baseline.

Use a deterministic bright-region estimator rather than one isolated maximum pixel.

Purpose:

> Test a stronger global-color assumption than gray-world without introducing spatial underwater physics.

Track:

- derived gains,
- clipping,
- out-of-range fraction,
- failure when no plausible bright neutral exists.

---

## Phase 2D — CLAHE baseline

Implement local contrast enhancement on a scalar perceptual lightness representation.

Do not independently equalize RGB channels.

Conceptually:
```text
linear RGB
    ↓
linear luminance
    ↓
perceptual lightness
    ↓
CLAHE
    ↓
inverse lightness mapping
    ↓
luminance-ratio RGB reconstruction
```

Use sufficient integer precision internally, e.g. `uint16`, rather than reducing dark underwater gradients to 8-bit purely for OpenCV convenience.

CLAHE is a **contrast control**, not a color-restoration method.

---

## Pipeline and ablations

Support explicit ordered combinations such as:
```text
gray_world
white_patch
clahe
gray_world -> clahe
white_patch -> clahe
```

Gray-world and white-patch are competing global WB assumptions; do not automatically stack both.

Every actually implemented correction stage receives an ablation switch.

Do **not** add placeholder flags for stages not yet implemented.

Current ablations include only things that exist, e.g.:
```text
--no-gray-world
--no-white-patch
--no-clahe
```

MC-Warp is a metric, not a processing stage, so it does not receive `--no-temporal`.

---

## Human control

Produce a careful chart-based/manual DaVinci Resolve correction on representative controlled footage when available.

Purpose:

> Establish what a competent ordinary grading workflow can accomplish without scene-depth or underwater-physics modeling.

No Resolve automation is required.

---

## Gate

Proceed when the project can answer:

> Given two implemented correction configurations, which differs in color fidelity, local contrast, temporal stability, signal usage, and clipping — and which implemented stage caused the difference?

Required:

- chosen flow backend justified,
- MC-Warp@1/4/8 operational,
- temporal ΔE00 operational,
- valid coverage always reported,
- white-patch operational,
- CLAHE operational,
- ablations operational,
- simple baselines evaluated on the frozen test suite,
- no unexplained metric regressions.

Do not begin depth work while temporal evaluation remains untrustworthy.

---

# Week 3 — Multi-view geometry: range for range-dependent restoration

## Goal

Determine whether video geometry can supply **range that is stable and
accurate enough to improve spatially varying backscatter and
wavelength-dependent attenuation inversion**, and select the approach that
supplies it.

This is not a reconstruction-quality exercise. The deliverable is a persisted
per-frame range product plus a measured error budget, not a point cloud.

Absolute metric depth is useful but is **not** the objective. Two results from
the research pass set the priorities:

- **Global range scale is exactly absorbable.** With `I = J·exp(−β_att·d) +
  B∞·(1 − exp(−β_bs·d))` and freely fitted coefficients, the substitution
  `d → s·d`, `β → β/s` leaves the image unchanged. A wrong global scale costs
  nothing inside one clip. It becomes identifiable, and starts to matter, only
  through external metric evidence, and only where `β` must be physically
  meaningful, is shared across clips, or where Week 6B introduces a light with
  distance-dependent falloff.
- **Spatially varying range error is not absorbable.** Nothing in the model
  compensates a range field that is wrong as a function of position or
  distance.

Week 3 therefore weights **shape error far above scale error**, and treats
metric-scale claims by learned models as a convenience, not a requirement.

Detailed candidate evidence, licences, hardware facts and rejected
alternatives: `experiments/week3_geometry/GEOMETRY_LANDSCAPE.md`. Do not
restate them here.

---

## Why a bounded bakeoff is justified

Phase 2A found that four optical-flow architectures agreed within ~2 % and that
the metric definition, not the backend, was the constraint. Geometry is not
like that. Four **fundamentally different paradigms** now exist — classical
optimisation, explicit refractive physics, feed-forward learned geometry, and
learned-local/classical-global hybrids — and they fail in different places for
different reasons. A single baseline cannot tell us which failure we have.

The bakeoff is bounded by predeclaring the families, tying every extra
candidate to a named observed failure, and stopping (see **Stop rule**).

### Two structural facts the design must respect

**1. Sparse and dense methods do different jobs.** Classical, refractive and
hybrid SfM produce poses plus sparse structure. COLMAP's dense stage
(PatchMatch stereo) is **CUDA-only** and unavailable on this machine. Only the
feed-forward family produces per-pixel range directly. So the two arms have
distinct roles:

```text
geometric cross-check     classical / refractive SfM
                          -> poses, sparse 3D, the physical camera model, and
                             competing geometry HYPOTHESES to compare against

range-supply role         feed-forward models
                          -> the per-pixel range Weeks 5-6 actually consume

absolute reference        independent C2 measurements
                          -> the only evidence not produced by a method under test
```

**Sparse SfM is not the ruler.** The classical geometry is itself under test. If
ordinary COLMAP is systematically wrong and a learned model is approximately
right, scoring the learned model against ordinary COLMAP's points makes the
right answer look wrong. Report every dense method against **three** references
separately:

- ordinary sparse SfM,
- refractive sparse SfM,
- **independent C2 measurements**.

Agreement with both classical variants is informative. **Disagreement between
them is more informative** — and only the independent anchor breaks that tie.
Where C2 evidence is absent, cross-family agreement is a consistency statement,
never a correctness one, and must be reported as such.

The decisive cross-family measurement is dense range evaluated at co-visible
points after one global scale. That is computable without CUDA dense MVS and it
is what the restoration question actually needs.

**2. Reprojection error is disqualified as the master metric.** Refractive
COLMAP's own AUV result: the ordinary pinhole treatment reached **0.277 px**
reprojection error while producing a severely distorted reconstruction with a
curved seafloor; refractive SfM reached 0.199 px *and* correct geometry. A
bundle adjuster minimising reprojection error reports a good number for a
systematically wrong world, and a feed-forward model does not optimise that
objective at all. Report it as a diagnostic for the classical arm only.

---

## Controlled acquisition and calibration

**New data for diagnosis, existing data for realism.** The frozen test set was
captured for restoration and temporal evaluation, not for geometry. It cannot
separate bad parallax from bad camera physics from bad matching from bad scale,
because it was not shot to. Two new controlled acquisitions decide **why**
methods differ; the existing clips then decide **whether the winner survives
normal diving**. Neither substitutes for the other, and the frozen suite is not
modified.

```text
C1, C2   new, controlled     -> selection and diagnosis
C3       optional, difficult -> fires conditional challengers
existing frozen clips        -> generalisation / realism check on the winner only
```

Three acquisitions. The difficult clip **does not replace** the controlled one.

### C1 — geometry clip (primary, mandatory)

Chosen for geometry, not aesthetics:

- rigid static coral / rock / wreck, feature-rich,
- deliberate lateral translation — strafe or arc around the subject, not a
  head-on dolly — to generate real triangulation baseline,
- diffuse ambient illumination; **no dive-light sweep**,
- minimal swaying vegetation, minimal animals, limited particulate,
- 20–40 s, subsampled to 40–80 frames for reconstruction.

### C2 — scale and range anchor (mandatory)

Same scene family, adding:

- the colour chart at **≥ 3 measured camera-to-chart distances** spanning the
  clip's near/mid/far range, distances recorded with a tape or marked rod,
- a rigid known-length scale bar visible in frame,
- **at each measured range, enough constraint on the target-plane pose** to
  derive the water-path distance to each reference corner individually.

**One scalar camera-to-chart distance is not per-pixel range truth.** A known
target size gives metric scale; a measured stand-off gives one distance
constraint. Neither gives the true range of every chart pixel unless the target
plane's orientation relative to the camera is also known. A tilted chart at
"2 m" spans 2.00 m at the near edge and 2.15 m at the far edge — a 7 % spread,
which is the same order as the effects Week 3 is trying to measure.

This needs no motion-capture rig. A rigid planar target of known dimensions,
photographed square-on where practical and with its pose otherwise measured or
solved from its own known geometry, is sufficient; the underwater checkerboard
acquisition below already provides exactly this and should be reused. Record
which corners have derived distances and treat only those as reference points.

C2 is what breaks global scale and, more importantly, provides the independent
reference points for the shape analysis. Without it Week 3 can rank methods
against each other but cannot say any of them is right.

### C3 — difficult clip (optional, diagnostic only)

Low-texture sand or smooth panel, some fish/vegetation, normal swim speed, and
an artificial-light pass. Used **only** to fire conditional challengers and to
hand Week 6B a starting clip. Never used to select the primary method.

### Calibration to acquire

Only what discriminates hypotheses:

- **in-air GoPro intrinsic calibration** (checkerboard, at the exact resolution
  / FOV setting / Protune profile used) — required by Pinax, recommended by the
  refractive workflow, and it pins intrinsics so self-calibration drift does not
  confound the camera-model axis,
- **underwater checkerboard at 2–3 measured distances** — the single
  highest-value item, because it is what produces residual-versus-(radius, range)
  evidence,
- **flat-port geometry**: lens-cover thickness and camera-to-interface distance,
  measured or estimated, **recorded with an explicit uncertainty**. These are
  millimetre-scale on a GoPro,
- refractive indices: air 1.0, port material, water 1.333–1.342 depending on
  salinity and temperature — record the dive's salinity/temperature,
- known object dimensions and the C2 camera-target distances.

Not required: dome-port parameters (the GoPro has a flat cover), and a full
refractive calibration toolbox — deferred unless the shape test fires.

---

## Phase 3A — primary geometry bakeoff

Six configurations spanning four families. Same clips, same subsampling, same
evaluation grid for every one.

### A. COLMAP 4.x · SIFT · incremental — classical control

**Role:** the interpretable baseline and the diagnosis substrate.
**Hypothesis:** ordinary central SfM on underwater footage produces range good
enough to be worth correcting.
**Why included:** it is the only candidate whose every intermediate — matches,
tracks, per-image registration failures, intrinsics, residuals — is inspectable,
so when something fails it can be attributed. Run with a **fixed random seed**;
COLMAP 3.13+ supports reproducible reconstruction and the project's standing
rule is that a non-reproducible measurement instrument is disqualified.

### B. COLMAP 4.x · ALIKED + LightGlue · incremental — correspondence axis

**Role:** identical mapper, identical camera model, learned front end only.
**Hypothesis:** the bottleneck is correspondence, not geometry.
**Why included:** this is the cheapest informative experiment in the whole week —
one flag change on the same binary. If B repairs A, the problem was matching.
If A and B reconstruct the same warped world, the problem is the camera model or
the parallax. Needs a COLMAP build with ONNX enabled.

### C. `colmap_underwater` · refraction OFF vs ON — camera-physics axis

**Role:** the only candidate that models the actual flat-port physics — an
axial, **non-central** camera where refracted rays share an axis rather than a
centre.
**Hypothesis:** flat-port refraction produces range-dependent shape error that
ordinary intrinsics cannot absorb.
**Why included:** it is the only way to answer the refraction question with
evidence instead of theory.

**Run this as one paired experiment inside one binary.** The refractive fork is
`COLMAP_VERSION 3.10-dev` while mainline is 4.1.x, so comparing the fork against
configuration A would confound the camera model with two years of unrelated
COLMAP change. Toggle `enable_refraction` off and on with the same features,
same images. Configuration A remains the modern-COLMAP reference; C is a
self-contained A/B.

**Do not assume seeded determinism here.** Reproducible reconstruction via a
random seed arrived in COLMAP 3.13; this fork predates it. Set a seed where the
fork supports one, then **repeat the off/on pair enough times to measure
run-to-run variability directly**, and require the refraction effect to exceed
that spread before calling it real. The evaluation protocol already demands
repeat-run consistency; this is where it matters most, because C is the one
configuration whose whole claim rests on a difference between two runs.

**Standing prior, from the research pass:** the Refractive COLMAP authors' own
real-tank experiment with an **underwater GoPro on a calibrated flat port**
found refraction gave no advantage — 2.061 mm model error for the pinhole
treatment versus 2.103 mm refractive — attributed to the small camera-to-interface
distance and small scene. Their refraction advantage is demonstrated at
AUV-survey scale. Ours is diver-held close range. A null result here is a
legitimate, expected and valuable outcome. Do not treat "refraction must matter"
as the hypothesis to confirm.

### D. MapAnything — feed-forward metric dense geometry, and the harness

**Role:** the modern feed-forward frontier, and the common output layer for the
whole learned arm.
**Hypothesis:** learned priors buy robustness where classical SfM degrades, and
supply usable dense per-pixel range directly.
**Why included:** Apache-2.0 code with an Apache-2.0 checkpoint variant; emits
`depth_along_ray`, `depth_z`, `ray_directions`, `camera_poses`, `conf`, `mask`
and `metric_scaling_factor`; accepts optional known intrinsics/poses/depth,
which matters later when we do have calibration and a scale anchor. Its
`mapanything/models/external/` wrappers already normalise DA3, DUSt3R, MASt3R,
MUSt3R, Pi3, MoGe and the VGGT family into one field convention — so swapping
backbones later costs a config line, not a wrapper.

**Use this repository's output convention as the project's Week 3 range format.
Do not invent a schema, and do not promote it to a permanent project API.**

### E. Wat3R — underwater-adapted feed-forward

**Role:** tests whether **underwater domain adaptation** is a separate win from
architecture.
**Hypothesis:** terrestrial-trained feed-forward models degrade underwater
through radiometric domain shift, and adaptation recovers that loss.
**Why included:** ECCV 2026 Oral, Apache-2.0, code + checkpoint + dataset
released; VGGT adapted by semi-supervised training on ~359 k real underwater
frames, reporting double-digit multi-view depth gains over VGGT on Sea-thru and
FLSea. This is the family the original Week 3 plan did not know existed.

**Note what it does *not* do:** like every underwater feed-forward model found,
it assumes a pinhole camera and corrects only the *radiometric* domain shift.
It is complementary to configuration C, not a substitute. If both C and E win
on their own axis, that is the interesting result, not a contradiction.

### F. GLUEMAP — hybrid learned-local / classical-global

**Role:** feed-forward backbone for local geometry, classical global averaging
and bundle adjustment for global consistency.
**Hypothesis:** learned priors fix local robustness while classical
optimisation preserves globally consistent, physically constrained structure —
better than either alone.
**Why included:** CVPR 2026, BSD-3, from the COLMAP authors; its named target
failures (low overlap, repetitive structure, weak texture) are exactly the
underwater ones; has a sequential-video pairing mode.

**Its output is a COLMAP sparse reconstruction — poses and sparse structure, no
dense depth.** Its job here is therefore the *pose and global-consistency*
hypothesis. If GLUEMAP's poses are materially better than A/B/C while
feed-forward per-frame depth is good locally, the practical answer may be
GLUEMAP poses + feed-forward depth rather than any single system.

---

## Phase 3B — conditional challengers

Do not run these by default. Each requires its named failure to be **observed
and documented** first.

```text
TRIGGER                                              -> CHALLENGER

Low texture is the demonstrated failure:
registration collapses or dense range voids over
sand / smooth wreck panel / featureless rock         -> 1. COLMAP LoMa matchers (free, same binary)
                                                        2. Dense-SfM (verify the released repo
                                                           actually ships the track-extension stage)

Low parallax is the demonstrated failure:
COLMAP registers frames but structure is unstable,
triangulation angles are small, repeat runs diverge   -> MP-SfM (Apache-2.0; monocular depth +
                                                        normal priors inside classical SfM)

Central models agree with each other but leave a
residual that is a joint function of image radius
AND range after best global scale alignment           -> escalate refractive geometry:
                                                        1. Pinax pre-correction + ordinary SfM
                                                           (in-air calibration only; its stated
                                                           precondition — millimetre camera-to-port
                                                           distance — is SATISFIED by a GoPro)
                                                        2. refine flat-port parameters inside
                                                           colmap_underwater's bundle adjustment
                                                        3. the fork's refractive_dense_* branches

Dynamic content breaks an otherwise-good
reconstruction on the realistic clip                  -> MegaSaM. Named cost: Python 3.10 +
                                                        CUDA 11.8 + prebuilt linux-64 xformers.
                                                        Linux/CUDA only, frozen stack.

The learned candidates disagree materially
with each other                                       -> swap backbones inside the MapAnything
                                                        harness (Pi3X / VGGT-Ω / DA3). Config
                                                        change, no new integration.

Long-sequence drift on clips beyond ~30 s             -> streaming VGGT variants. Low priority;
                                                        current clips are 10-25 s.
```

**Not challengers, and not substitutes for configuration C.** GenSfM and AnyMap
are both **central** cameras by explicit construction — GenSfM assumes radial
symmetry and maps image radius to opening angle about one centre; AnyMap's
unprojection maps a pixel to a ray *direction* on the unit sphere with every ray
originating at the camera origin. Neither can represent the per-pixel ray-origin
shift that makes flat-port error range-dependent. They can absorb the
directional part of refraction and nothing more. If either is ever run, it
answers "how much can a flexible central model soak up", which is a strictly
weaker claim than configuration C's.

---

## Refractive-geometry experiment

The refraction question reduces to one falsifiable test, available from the C2
and underwater-checkerboard data:

```text
flat-port refraction error   = f(image radius, range)     radius x range coupled
ordinary lens distortion     = f(image radius)            radius only
```

Procedure:

1. compute the scale-aligned range residual (below) for every configuration,
2. bin residual by **image radius** and, independently, by **range decile**,
3. test whether the radius profile is stable across range bins.

Interpretation — stated as an **envelope claim**, never as a claim about the
physics in general:

- no measurable radius × range interaction, **and** the central-model residual
  sits below the restoration-relevance threshold → *"no detectable
  range-dependent refractive residual within the tested C1/C2 operating
  envelope"*, so ordinary geometry is adequate **for this camera, at these
  distances, at this resolution**. Configuration C is not needed. This is the
  null that matters and it is a complete result,
- residual radius × range coupled, and configuration C's refractive mode removes
  it → the camera model was the bottleneck; refractive geometry is required,
- residual coupled but configuration C does not remove it → the refractive
  calibration is wrong, or the error is not refraction. Do not escalate model
  complexity until this is distinguished.

**Do not write "refraction does not matter underwater."** Refraction is real and
non-central; the question is only whether it is detectable and consequential
here. A null may mean the effect is below measurement noise, too small over the
tested distance span, too small at the evaluation resolution, or absorbed by
central distortion **over that restricted regime**. Record the envelope — range
span, image resolution, residual noise floor — alongside the result, so a later
phase working at different distances knows exactly what was and was not tested.
The published GoPro flat-port tank result (2.061 mm pinhole vs 2.103 mm
refractive) is precisely such an envelope-bounded null.

The C-off/C-on pair is the controlled instance of this test.

---

## Common output representation

Minimal, adopted rather than invented. One `.npz` per clip per configuration
plus a JSON sidecar. No abstraction layer, no package code, no `uw/depth/`
subpackage until a method is selected.

**Storage layout follows `CLAUDE.md` invariant 9.** "One `.npz` per clip" is the
logical unit, not necessarily one file: `.npz` cannot be memory-mapped and must
be materialised whole, so per-frame `(H,W)` fields are written as per-frame or
per-chunk shards (plain `.npy`, memory-mappable, plus the sidecar) as each frame
is produced, and read back windowed. The writer must never hold a full-clip
stack of `(H,W)` float32 fields, and neither must any consumer. Keep the
small per-clip quantities in the `.npz`/JSON.

Per frame:

```text
frame_index          index into the source clip (not a re-numbered sequence)
K                    3x3 intrinsics, or ray_directions (H,W,3) where a model
                     emits rays instead
T_wc                 4x4 cam2world, OpenCV convention
water_path_length    (H,W) float32  CANONICAL. Physical propagation distance
                     through WATER, where a refractive model supplies it
range_along_ray      (H,W) float32  central-camera distance from the projection
                     centre. What every central/learned model natively emits
path_source          which of the two above is measured vs approximated,
                     and the approximation's stated bound
valid                (H,W) bool
conf                 (H,W) float32, or absent
```

Optional, refractive configurations only, when cheap to emit:

```text
ray_origin_water     (H,W,3) per-pixel ray origin at the interface exit point
ray_direction_water  (H,W,3) refracted direction in water
```

Per clip:

```text
scale_convention     metric | scale-ambiguous | anchored:<evidence>
global_scale         the fitted scalar s and the evidence used
sparse_points        3D points + track lengths, classical/refractive arms only
provenance           method, repo commit, checkpoint hash, config hash,
                     random seed, device, wall-clock, peak memory
```

**Why water path length, and not simply z-depth or ray range.** Beer–Lambert
attenuation acts over the distance travelled **through water**, and the whole
point of configuration C is that a flat-port camera is not central:

```text
projection centre
    \  air / port glass
     \
      interface exit point
         \
          \   WATER PATH   <- the length attenuation actually integrates over
           \
            scene point
```

Planar z is wrong at a GoPro's field of view. Ray range from the mathematical
projection centre is closer, but it charges the air-and-glass segment to the
water budget and, more importantly, it silently re-imposes a central camera on
the one configuration built to reject it. Defining the canonical quantity as
`range_along_ray` would mean the part of Week 3 designed to test refraction
ends by forcing its answer back into central-camera coordinates.

In practice the two are nearly identical here — the housing offset is
millimetres against metre-scale scenes — so for every central and learned model
`water_path_length ≈ range_along_ray`, and that approximation is recorded in
`path_source` rather than hidden. Refractive configurations emit the real
quantity. The distinction costs one field and keeps the representation honest.

Where a model emits both z and along-ray (MapAnything separates `depth_z` from
`depth_along_ray`), take the along-ray quantity and keep z only as a
convenience.

---

## Evaluation protocol

Common resolution across configurations, as in Phase 2A. Report every number
with its coverage; a score without coverage is incomplete.

**Before any number on our footage is trusted:** validate each wrapper on a
public underwater sequence with ground truth — FLSea or Sea-thru — and check it
reproduces published behaviour. This is the geometry analogue of Phase 2A's
synthetic known-motion check. A wrapper that cannot reproduce a published result
cannot be believed on our clips.

Measured for every configuration:

1. registered / usable frame fraction,
2. dense range coverage (feed-forward arm) or sparse completeness and mean track
   length (classical arm),
3. relative range ordering against C2's measured distances,
4. cross-view range consistency for the same static scene point,
5. camera trajectory plausibility and smoothness,
6. repeated-run consistency — bitwise where achievable, quantified where not,
7. known-distance and known-size error from C2,
8. **residual after the best single global scale** (below), reported
   **separately against each of the three references** — C2, ordinary sparse
   SfM, refractive sparse SfM — never against a merged or averaged one,
9. **spatially varying residual after that scale** (below),
10. localised failure regions, named and visually inspected,
11. confidence calibration where a model emits confidence: does low confidence
    actually predict high error on our footage, or is it out-of-distribution and
    miscalibrated,
12. runtime, peak memory, integration cost.

Metrics that do not apply to a family are **reported as inapplicable, not
forced**. Reprojection error: classical/refractive/hybrid arms only, as a
diagnostic, never as a ranking. Sparse completeness: not meaningful for
feed-forward. Dense coverage: not meaningful for GLUEMAP.

---

## Scale-vs-shape analysis

For each configuration, **separately** against C2's derived reference distances
and against each classical arm's sparse points at co-visible pixels, find the
single scalar `s` minimising a robust residual:

```text
d_aligned(x) = s * d_estimated(x)
```

Then decompose what remains:

- residual versus **range decile** — near/mid/far bias,
- residual versus **image radius** — the refraction/distortion signature,
- residual versus both jointly — the discriminator in the refractive experiment,
- residual spatial autocorrelation — is the error structured or noise-like.

Reading:

- accurate after one scalar → **a scale problem**, which the attenuation fit
  absorbs exactly. Effectively harmless inside one clip,
- near range correct, far range biased → **a shape problem**. Dangerous. This is
  the failure mode the whole week exists to detect,
- residual noise-like and unstructured → a precision problem; check whether
  Weeks 5–6 average it out before spending anything on it.

Report `s` itself as information, not as a score. A method needing `s = 3.2` is
not worse than one needing `s = 1.01` if the residuals match.

**Read the three references against each other before reading any of them as
truth.** Where C2 evidence exists it decides. Where it does not, a method's
residual against ordinary sparse SfM and against refractive sparse SfM are two
independent statements, and the interesting case is when they disagree: that
localises the disagreement to the camera model, not to the method under test.
Never collapse the three into one residual, and never report a
"shape error" without naming which reference produced it.

---

## Restoration-relevance sensitivity test

**Mandatory. This is the judge.** Geometry metrics rank the methods; this
decides whether the ranking matters.

Take a representative range field, propagate it through the provisional
range-dependent restoration calculation, and perturb it deliberately:

```text
global scale          s in {0.7, 0.85, 1.0, 1.18, 1.43}
range-dependent bias  d' = d * (1 + g * d/d_max), g in {-0.3 ... +0.3}
local noise           iid, sigma in {2%, 5%, 10%} of range
missing depth         holes at {5%, 20%, 40%} of pixels
```

Quantify how each changes:

- restored linear radiance per channel,
- near / mid / far consistency,
- corrective gain magnitude, clipping fraction, near-floor fraction,
- chart ΔE00 on C2, where the reference exists.

The output is one reusable number per error type:

> **the range-error magnitude at which restoration degradation exceeds the
> measured geometry spread between configurations.**

If the method-to-method spread sits below that threshold, the methods are
**tied downstream** and selection moves to robustness, determinism and cost.
That is a legitimate and likely outcome — expect the global-scale sweep in
particular to be nearly flat, since scale is exactly absorbable.

Persist these thresholds. Weeks 5–6 need them, and Week 4 needs them to judge
monocular depth on the same footing.

---

## Selection rule

Select the configuration that supplies the **most useful range for
restoration**, judged in this order:

1. smallest *shape* error after global scale alignment, on C1 and C2,
2. restoration sensitivity — does its residual error stay under the measured
   thresholds,
3. coverage and usable-frame fraction on real footage,
4. determinism and repeat-run stability,
5. honest confidence, or at least honest failure regions,
6. integration and runtime cost.

Do not force a single winner. All of these are legitimate outcomes:

- refractive modelling is required, and configuration C wins on shape,
- a feed-forward model gives equivalent restoration-relevant range far more
  robustly, and the classical arm is retained only as a geometric cross-check,
- underwater adaptation (E) beats architecture (D), or does not,
- GLUEMAP poses combined with feed-forward depth beats every single system,
- ordinary COLMAP is adequate once globally scaled,
- refractive error is **measurable but irrelevant** at the precision restoration
  needs — a clean, publishable null result, and the one the GoPro flat-port
  evidence makes most likely,
- several methods are tied downstream despite differing geometry metrics.

If the outcome is a tie, say so, pick on cost and determinism, and record that
the geometry question is closed rather than won.

---

## Stop rule

> Once the primary bakeoff spans **classical**, **explicit refractive**,
> **modern feed-forward** (terrestrial and underwater-adapted) and **hybrid**
> geometry, do not add another method unless an observed, documented failure
> identifies a missing capability that the new candidate specifically addresses.

A leaderboard improvement is not a reason to integrate another model. Phase 2A
already established that ranking anti-predicted usefulness on this project's
footage, and the strongest current feed-forward model ships with a self-reported
benchmark-contamination notice on its released checkpoint. Treat published
numbers as candidate discovery only.

Conditional challengers are unlocked by their triggers above, one at a time, and
each one closes again once its named failure is explained.

---

## Named blockers — settle these before acquiring footage

- **No CUDA on this machine (M4, 24 GB unified).** Split the work rather than
  assuming a blanket blocker:

  ```text
  LOCAL FIRST   COLMAP 4.x sparse (A, B)          CPU, fine
                colmap_underwater (C)             CPU, verify the build
                MapAnything (D)                   MPS -- try before renting

  GPU SESSION   GLUEMAP (F)      INSTALL.md: "requires CUDA at runtime --
                                 the GPU PyTorch build is the only supported
                                 configuration"
                Wat3R (E)        CUDA checks + bf16/fp16 autocast
                MegaSaM          conditional; CUDA 11.8 + prebuilt linux-64
                                 xformers, a frozen Linux-only stack
                COLMAP dense     CUDA-only, and only if later justified
  ```

  **MapAnything is no longer a categorical CUDA blocker:** MPS inference support
  landed 2026-03-23 (`facebookresearch/map-anything` #131), though the README
  quickstart still shows the older cuda/cpu device line. Attempt it locally
  first. That may still be slow or memory-constrained at 40–80 views on 24 GB
  shared with the OS — profile it, and fall back to the GPU session on measured
  cost, not on assumption.

  For the GPU-only candidates, **batch them into as few short reproducible
  sessions as practical, each in its own pinned environment or container.** Do
  not assume one session or one environment covers everything: MegaSaM's CUDA
  11.8 / PyTorch 2.0.1 stack and GLUEMAP's CUDA 12.4 / PyTorch 2.4.1 conda
  recipe are mutually incompatible, and total memory need is unknown until
  profiled. Persist every artifact in the common representation so the rest of
  the project stays laptop-local.
- **Does `colmap_underwater` build on macOS ARM?** It claims no dependencies
  beyond COLMAP, but it is 3.10-dev era. Cheap to test; do it first.
- **Is ONNX enabled in the available COLMAP build?** Configuration B needs it;
  a source build with `-DONNX_ENABLED=ON` may be required.
- **Licences.** VGGT-Ω is FAIR Noncommercial with gated checkpoints; MASt3R/
  DUSt3R checkpoints are CC-BY-NC-SA with additional dataset terms; MapAnything's
  best checkpoint is CC-BY-NC while its Apache variant is not. Prefer the
  Apache/BSD path (MapAnything-apache, Wat3R, Pi3, GLUEMAP) for anything that
  might outlive the bakeoff.
- **Missing refractive calibration.** Flat-port thickness and camera-to-interface
  distance are not yet measured. Required only if the shape test fires; record
  the uncertainty either way.

---

## What Week 3 persists for Weeks 5–6

Nothing downstream should ever need to re-run geometry — nor assume the geometry
stack is installed in the same environment, or resident in the same process.
Week 3 runs its heavy models, writes the range product, and exits; Weeks 5–6
consume that product.

- per-frame pose, intrinsics, **water path length** (with `path_source`),
  valid mask and confidence for
  C1 and C2, in the common representation, for **the selected method and one
  runner-up** — so Weeks 5–6 can run their own sensitivity check without
  reopening this week,
- the classical/refractive sparse reconstructions, as geometric cross-checks —
  labelled as competing hypotheses, not as ground truth,
- the C2 derived reference distances and the target-pose evidence behind them,
  which are the only absolute anchor Weeks 5–6 inherit,
- the fitted global scale, the evidence behind it, and the scale convention,
- **the restoration-sensitivity thresholds** — the most reusable artifact of the
  week,
- the scale-vs-shape decomposition per method,
- named failure regions and the conditions that produce them, for Week 7's
  taxonomy,
- full provenance for every artifact.

---

## Gate

Proceed when:

- **C1 and C2 have been captured** and registered in
  `data/testset/manifest.json`. They are the acquisitions this week's
  conclusions rest on; the existing frozen clips cannot substitute, because they
  were not shot to separate parallax from camera physics from matching from
  scale,
- both controlled clips reconstruct, with the registered-frame fraction reported
  for every configuration,
- **the selected method has been run on the existing frozen clips** as a
  realism check, and either survives them or its failure there is documented
  and accepted with reasons,
- relative range ordering is stable and cross-view consistent,
- camera trajectory is plausible and smooth,
- repeat-run behaviour is established — bitwise where achievable, quantified
  where not — for every configuration that produces a number used in selection,
- the **scale-vs-shape decomposition** is computed, and global scale error is
  separated from spatially varying error,
- the **ordinary-vs-refractive comparison has an evidence-backed answer, stated
  as an envelope claim**: either no detectable radius × range interaction with
  the central-model residual below the restoration threshold — *"adequate within
  the tested C1/C2 envelope"*, with the range span, evaluation resolution and
  residual noise floor recorded — or refraction is required and configuration C
  removes it, or the coupling exists and C does not remove it. "Deferred" is
  only acceptable with the radius × range evidence attached,
- known-scale evidence from C2 is used, and the fitted scale is recorded,
- range uncertainty and named failure regions are documented,
- **restoration-sensitivity thresholds are measured**, and the selected method's
  error budget sits under them,
- a persisted range product exists in the common representation for Weeks 5–6.

If the shape residual is radius × range coupled and refractive modelling removes
it, fix geometry before treating any central-camera range as ground truth. If it
is not, record the **envelope-bounded** null and move on — do not spend the week
proving a theoretical concern the measurement did not support, and do not
overclaim it as a general statement about underwater refraction.

---

# Week 4 — Monocular depth for stills and fallback video frames

## Goal

Determine whether a single-image depth estimator is accurate enough to substitute for multi-view range when video geometry is unavailable.

Do not select a model solely from generic depth benchmarks.

Evaluate on frames for which Week 3 provides the best available multi-view reference.

Use Week 3's persisted range product (same common representation, **water path
length**, same clips) as that reference, and judge monocular error against the
**restoration-sensitivity thresholds Week 3 measured** rather than against a
depth leaderboard. Week 3 deliberately did not benchmark single-image depth;
this is where that happens.

---

## Compare

Assess:

- relative ordering,
- local depth discontinuities,
- near/far consistency,
- scale/shift ambiguity,
- moving animals,
- textureless water,
- artificial light,
- severe color cast,
- murk.

Align monocular output to multi-view depth only using clearly documented scale/shift methods.

Do not hide structural errors through overly flexible alignment.

---

## Restore-with-depth test

Run the same provisional range-dependent calculation using:

- multi-view depth,
- monocular depth.

Ask:

> Does the monocular depth error materially change restoration?

The useful quantity is restoration sensitivity, not depth leaderboard score by itself.

---

## Gate

Produce an explicit error budget for:
```text
video path: multi-view/refractive range
photo path: monocular range
```

Document cases where monocular depth is:

- adequate,
- degraded but usable,
- unsafe.

---

# Week 5 — Backscatter estimation

## Goal

Estimate and remove the additive veil caused by underwater backscatter.

Start from the Sea-thru-style physical model.

Use an independent implementation/review path where useful to reduce correlated implementation mistakes.

**Declare the clip scope: ambient / diffuse illumination only.** The
single-path model assumed here is systematically wrong under a camera-mounted
dive light, where the light path and the return path both attenuate over
`d_light + d_cam` (exactly doubling the exponent only in the collocated
limit). Fit and gate on
ambient footage, run `lights/LIGHTNIGHTDIVE.MP4` as a diagnostic, and record its
failure as **expected input to Week 6B**, not as a Week 5 regression.

---

## Backscatter term

Estimate a spatial/range-dependent backscatter contribution.

Validate assumptions against:

- murky footage,
- distant water,
- low-texture regions,
- artificial lights,
- moving particles.

Do not assume darkest pixels automatically represent water/backscatter without validating the estimator's assumptions.

---

## Temporal behavior

Backscatter parameters will fluctuate from estimation noise.

Start with **simple temporal smoothing as a baseline**, applied to estimated physical parameters rather than finished output pixels.

However, do not assume water properties are globally homogeneous over a fixed rolling window.

Real transitions may include:

- particulate cloud,
- thermocline/halocline-associated optical changes,
- changing ambient illumination,
- entering/exiting a lit region.

A fixed temporal average can lag across a real change and cause color/brightness pumping.

---

## Adaptive stabilization

After establishing the unsmoothed and fixed-window baselines, evaluate an edge-preserving/adaptive parameter stabilizer.

Candidate signals may include:

- parameter innovation magnitude,
- confidence/fit residual,
- depth,
- camera velocity,
- scene-change evidence,
- telemetry where available.

Depth/velocity are supporting evidence, not sole determinants of whether the water body changed.

Do not build complicated adaptive filtering unless the fixed-window baseline demonstrates a real failure.

---

## Parameter trace persistence — required, and irreversible if skipped

Persist, **per frame, indexed by frame, unsummarised, for the whole run**:

```text
raw per-frame physical estimate
stabilized estimate
innovation / prediction residual
estimator uncertainty or covariance, where the model provides one
input-derived covariates:
    ORIGINAL footage frame-mean linear luminance
    camera-motion magnitude
    depth / range
```

These four are **different signals and must be stored separately**, because
Week 8 asks a different question of each:

```text
raw estimate    -> did the estimated environment genuinely change?
stabilized      -> did the correction parameters pump?
innovation      -> is the estimator mis-specified or under-modelled?
output          -> did any of that become visible?
```

Do not store only summary statistics. Do not store only the stabilized output.

A physical parameter is **not** expected to be white — water genuinely changes.
It is the innovation of a correctly specified estimator that has a claim to
whiteness. Conflating the two makes Week 8's analysis unsound.

If the parameter is a spatial field rather than a scalar, **persist the full
per-frame field wherever tractable.** A field can oscillate with an essentially
zero global mean — left half `+δ`, right half `−δ`, alternating — and every
global summary statistic will miss it forever. Any low-rank or regional
representation should preferably be *derived later* from the retained field. Only
if full persistence is genuinely impractical may a reduction be stored instead,
and then its definition and the reason for it must be documented **before** the
information is discarded. This is the one irreversible decision in Weeks 5–6.

### Persist by streaming, not by accumulating

"Unsummarised, for the whole run" is a statement about **what reaches disk**, not
about what is held in memory. The two only conflict if the implementation
accumulates. The contract, per `CLAUDE.md` invariant 9:

```text
load a bounded frame window
  -> estimate
  -> append this frame's fields, state and traces to chunked on-disk storage
  -> release the tensors
```

Only the active temporal window, the estimator state and the model currently
running stay resident. A full-clip array of per-frame spatial fields is never
constructed — not for persistence, not for analysis. Week 8 reads the traces back
windowed or memory-mapped; its instruments must be expressible as streaming or
chunked passes, and any analysis that genuinely needs the whole clip at once
operates on a reduction *derived from* the retained fields, not on the fields
themselves held in memory.

Implement the streaming contract first, then profile. On this machine (M4, 24 GB
unified, shared with the OS) the realistic failure is a single oversized
intermediate — a full-clip stack, a float64 promotion, an unreleased decoder
buffer — not steady-state footprint. Do **not** build sliding-window machinery
more elaborate than a measurement justifies. Record peak RSS per stage in
`LOG.md` alongside runtime; that number, not a prediction, decides whether
anything more is needed.

Rationale and the full Week 8 analysis this feeds:
`experiments/week2b_temporal/TEMPORAL_METRIC_LITERATURE.md`.

---

## Synthetic transition test

Create at least:

### Stable environment

Underlying parameter constant + estimator noise.

Expected:

> stabilization suppresses jitter.

### Real parameter transition

Underlying parameter changes sharply.

Expected:

> stabilization follows the new value without excessive lag/overshoot.

This separates “remove estimation noise” from “erase physical reality.”

### Record the step response quantitatively

“Without excessive lag/overshoot” is a control-theory question and has standard
vocabulary. On each synthetic transition, record:

```text
settling time
lag
overshoot
steady-state error
```

These are stabilizer-tuning diagnostics, not another temporal metric. They are
the correct instruments for this test and cost nothing to add.

Where the stabilizer is an explicit probabilistic/state-space model, the
innovation sequence should also be checked for whiteness. Do **not** bolt a
Normalized Innovation Squared (NIS) chi-square test onto an EMA or an ad-hoc
adaptive smoother — NIS is meaningful only when the estimator supplies a
defensible innovation covariance.

---

## Gate

Proceed when:

- murky footage shows a measurable improvement,
- backscatter parameters are physically plausible,
- frame-to-frame estimator noise is controlled,
- genuine synthetic/environmental transitions are not excessively smeared,
- MC-Warp/temporal ΔE do not reveal new pumping,
- valid spatial detail is not removed as “backscatter,”
- **per-frame raw/stabilized/innovation/covariate traces are persisted
  unsummarised**, and the synthetic transitions have recorded settling time,
  lag, overshoot and steady-state error.

---

# Week 6 — Wavelength-dependent attenuation inversion

## Goal

Recover range-dependent scene radiance after accounting for backscatter.

Implement spatially varying wavelength-dependent attenuation correction.

Conceptually, correction depends on:
```text
observed radiance
range
backscatter
attenuation coefficient per wavelength/channel
```

rather than one global RGB multiplier.

This is the phase where the project should first demonstrate a clear capability that global WB cannot replicate.

**Same clip scope as Week 5: ambient / diffuse illumination.** A coefficient
fitted on dive-light footage with this single-path model is biased, not merely
noisy. Keep the artificial-light case as a documented failure and hand it to
Week 6B, which exists to answer what illumination model that case needs.

---

## Attenuation estimation

Estimate channel/wavelength-dependent attenuation parameters.

Track:

- fit confidence,
- physically implausible coefficients,
- extreme gains,
- channel signal floor,
- clipping risk.

Do not attempt to “recover” red detail that is demonstrably absent from the source without explicitly marking that region as low-confidence/unrecoverable.

---

## Temporal stabilization

Use the same philosophy as Week 5:

1. unsmoothed estimate,
2. fixed smoothing baseline,
3. adaptive/edge-preserving stabilization only if needed.

Do not smooth finished frames merely to conceal unstable physical parameter estimation.

**The Week 5 trace-persistence requirement applies here unchanged and in full.**
Follow the complete schema in Week 5 → *Parameter trace persistence* — raw
per-frame estimate, stabilized estimate, innovation/residual, estimator
uncertainty or covariance where meaningful, and the input-derived covariates
(ORIGINAL frame-mean linear luminance, camera-motion magnitude, range) — applied
here to the per-channel attenuation estimates. Do not substitute a shorter list;
"confidence/residual" alone is not adequate, because Week 8 asks a different
question of each signal.

Record settling time, lag, overshoot and steady-state error on the synthetic
transitions.

---

## Distance-consistency test

Within one frame, evaluate:

- foreground,
- middle distance,
- background.

A global correction may fix one distance while ruining another.

The physical model should improve multiple ranges simultaneously.

---

## Depth-sensitivity test

Perturb depth/range intentionally.

Measure how restoration changes under:

- small scale errors,
- local depth errors,
- large range errors.

This determines how much future effort should go into improving geometry.

---

## Gate

Proceed when:

- near/mid/far regions can be corrected simultaneously better than global baselines,
- chart/controlled color metrics improve where available,
- signal-starved regions are flagged rather than hallucinated,
- temporal metrics remain acceptable,
- parameter stabilization does not erase real environmental transitions,
- **the Week 5 parameter-trace persistence schema is satisfied for the
  attenuation estimates**, and the synthetic transitions have recorded settling
  time, lag, overshoot and steady-state error,
- the first meaningful win over the **implemented global baselines**
  (gray-world, white-patch, CLAHE combinations) is visible and measurable.

Named external products — Dive+, AquaColorFix, Resolve, LUT-style workflows —
belong to the **Week 9 external benchmark**. Do not make Week 6 progress
contingent on third-party tool or footage availability; that gates physics
development on procurement rather than on restoration correctness.

---
# Week 6B — Complex / artificial illumination

## Goal

Determine **what explicit illumination model, if any, is required** when the
scene is lit partly or primarily by a camera-mounted dive light, and select the
simplest model that materially improves held-out restoration.

The question is not *which model produces the lowest error*. It is **which is
the simplest model whose decomposition is actually identifiable from the
evidence we can collect.** Several terms in this observation model can
compensate for one another, so a low error is not by itself evidence that the
recovered parameters mean anything. Staged estimation, the calibration-anchor
ledger and the identifiability gate below exist to keep those two questions
apart.

Evidence, formulations, licences and rejected alternatives:
`experiments/week6_illumination/ILLUMINATION_LANDSCAPE.md`. Do not restate them
here.

**This phase does not touch the Phase 2B temporal evaluator.** That global
luminance affine, fitted on aligned *original* frames, is a deliberately
low-capacity nuisance model for temporal scoring and stays exactly as frozen.
Week 6B concerns the restoration model. Corrected output must never be allowed
to fit its own judge.

---

## Why this phase exists

A global gain/bias cannot represent a beam. If the left side of a reef is at
+80 % illumination and the right side is unchanged, no single scalar pair
describes it. Worse, the restoration model will confuse:

```text
"this region is red because the dive light illuminated it"
"this region retained red because it is close"
"this region should be strongly red-corrected because water removed red"
```

Two physical facts make this a **first-class modelling problem, not a
brightness cleanup**:

**1. Artificial light attenuates over two water paths, not one.** Transmission
for the artificial term is

```text
T_c(x) = exp( −β_c · [ d_light(x) + d_cam(x) ] )
```

A **collocated** camera and light is the special case `d_light = d_cam = d`,
which doubles the direct-path exponent exactly: `exp(−2β_c·d)`. A real
camera-mounted torch is **offset**, so it does not reduce to doubling — the two
paths differ, and their sum varies across the frame with the light's pose and
the point's position. Either way, a dive-light clip fitted with Weeks 5–6's
single-path model recovers a `β` that is **systematically wrong in a predictable
direction** — a bias, not noise. Having Week 3 geometry is what makes the
correct form computable at all.

**2. Point-source `1/r²` falloff is a hypothesis to test, not a given.** A real
torch is an extended source, and at diver working distances we may be in its
near field, where an ideal point-source law can depart materially from
measurement. The best available calibrated model (NeLiS, MIT) replaces `1/r²`
with a Lorentzian `1/(τ + r²)` with `τ` learnable, and reports a better fit
**for the sources it tested** — an empirical result for those camera-light
systems, not a law of dive torches.

So make it an experiment, not an assumption: **fit both `1/r²` and `1/(τ + r²)`
on our own underwater calibration sweep and keep the simpler form unless
held-out data supports the extra parameter.** If our torch is already
effectively far-field at 1–3 m, `τ` buys nothing and disappears. That is a
result worth having.

---

## Prerequisites — gate from Weeks 3–6A

Do not start Week 6B until all of these hold. Every candidate depends on them.

- **Week 3's selected range/geometry exists** for the illumination clips, in the
  common representation, with the measured error budget.
- **Surface normals have been derived and their uncertainty quantified** — as a
  Week 6B preparation step, not retroactively as a Week 3 deliverable. Week 3
  produces range; normals are a derived quantity with their own, worse, error
  behaviour: `d(x,y) → ∇d → n(x,y)`, so modest high-frequency range noise
  becomes much larger normal error. Propagate the Week 3 range error budget
  through the gradient and record the resulting normal uncertainty **before**
  fitting anything that depends on it. Compare at least normals from local dense
  range gradients against normals from reconstructed surface geometry where
  available. This does not reopen Week 3.

  Families B and C both depend on normals — B for `cos θ` response, C because its
  shading compensation divides by `cos θ` — so this uncertainty is a first-class
  input to the geometry-sensitivity analysis below, not a detail.
- **Week 3's restoration-sensitivity thresholds are known.** Without them there
  is no way to tell an illumination win from geometry noise.
- **Week 5 backscatter and Week 6 attenuation exist on ambient footage**, and
  their clip scope is declared. They are the null hypothesis — and, under the
  staged ladder below, the first rung: the medium estimated on L1 is what L2's
  illumination fit holds fixed.
- **The illumination clip has demonstrated camera-to-scene distance variation.**
  This is a hard identifiability precondition, not a preference: medium
  attenuation is only observable if the distance to the scene varies. On a
  constant-distance trajectory, attenuation is constant and **cannot be
  distinguished from object colour**. Verify it from the Week 3 range product
  before fitting anything.

If the last condition fails on a clip, that clip is a stress clip only. It
cannot fit an illumination model and must not be used to select one.

---

## Controlled acquisition

### L1 — ambient / diffuse control (mandatory)

Static rigid geometry, uniform ambient illumination, **light off**. Same scene
family as the artificial-light clip where possible. Purpose: establish the
baseline, and make sure a complex model cannot win merely by fitting easy
footage. This is the clip family A is scored on.

**Shoot L1 and L2 back-to-back at the same site, in the same water.** The staged
ladder below transfers L1's medium estimate into L2's fit and holds it fixed;
that is only sound if the water is the same. Separated by hours, tide or site,
the transfer is unsupported and the medium has to be re-estimated on L2 with a
wide bound — which is exactly the joint fit the staging exists to avoid. This is
an acquisition discipline that buys identifiability for free.

### L2 — controlled artificial light (mandatory, the primary fitting set)

Rigid static scene, **ambient light minimal**, dive light on and rigidly
mounted. Move the camera-light rig so that **the same scene points are observed
under materially different beam incidence and at different ranges**:

- sweep across the subject so points cross the beam centre and beam edge,
- vary camera-to-scene distance across the clip — required by the
  identifiability precondition above,
- vary approach angle so surface normals see different incidence,
- geometry already reconstructable (this is a Week 3-quality scene),
- limited moving animals and vegetation.

This is where illumination disentanglement is actually earned.

### L3 — mixed ambient + artificial (if practical)

The ordinary dive case: daylight and torch coexisting. Tests whether the model
handles an ambient term rather than assuming darkness.

### L4 — difficult real clip (stress only)

Moving beam, normal swimming, particulate, heterogeneous scene. The existing
`lights/LIGHTNIGHTDIVE.MP4` is the natural candidate. **External test, never
the fitting set.**

### Calibration to acquire

Only what discriminates models:

- **camera-to-light rigid offset**, measured. Family B's entire geometry rests
  on it; record it with an uncertainty.
- **Chart at ≥ 3 ranges × ≥ 3 positions in the frame**, light on. The cheapest
  decisive acquisition. The identifiability argument: one observation of a known
  albedo constrains the multiplicative and additive terms only to a *line* in
  their joint plane; two observations of **widely disparate** known albedos
  intersect to a unique solution. That is *why* a chart is the right target and
  why patch contrast matters — pick the most disparate reflectances available.

  **But do not mistake the ideal algebra for the estimator.** A real
  ColorChecker's darkest patch is not a perfect absorber (`ρ ≠ 0`), so it
  *strongly constrains* the additive term rather than measuring it; only in the
  zero-reflectance limit is the measurement direct. Measurement uncertainty also
  turns each clean line into a finite region, so the intersection is a region,
  not a point. Fit **jointly over the known calibrated reflectances of multiple
  patches**, with the uncertainty weighting, smoothness and interpolation the
  published method actually uses — the closed form is the explanation, not the
  algorithm.
- **White/grey planar target sweep**, ~30–40 frames at varied range and angle,
  for beam-profile fitting. Fiducial markers at the corners make the pose
  solvable.
- **A few seconds of open water**, light on. Pure-water frames upper-bound the
  backscatter along every ray, since it increases monotonically with distance.
  Nearly free to capture and a strong regulariser.
- Dive light make/model and any manufacturer beam-angle or spectral data.
- Repeat the white-target sweep at the **start and end** of a dive, to check
  whether one calibration transfers across battery state.

Not required: an underwater goniophotometer, per-LED calibration (there is one
torch), a measured volume scattering function, or a spectrometer.

---

## Staged estimation — fit order is part of the model

The observation model is

```text
observed colour = f( albedo,
                     surface illumination,
                     medium attenuation,
                     ambient backscatter,
                     active backscatter )
```

and several of those terms trade off against one another: a dimmer beam with a
brighter albedo, a stronger `β` with a longer effective path, a light cone
absorbed into ambient backscatter. Handing an optimiser all of them at once, on
RGB frames, is a mathematically hostile inverse problem and invites a decomposition
that renders well and means nothing. **Fit order is therefore a design decision,
not an implementation detail**, and it is the same for every family with
physical parameters:

```text
calibration rig data (measured offset, white-target sweep, chart)
    -> LOCK camera-light extrinsic, beam profile, falloff form

L1 (ambient, light OFF)
    -> ESTIMATE medium: beta_att, beta_bs, B_inf     [Weeks 5-6 machinery]

L2 (artificial, ambient minimal), medium held FIXED
    -> ESTIMATE active illumination: source scaling, ambient level,
       active-backscatter coefficient

only then, staged outputs as initialisation
    -> SMALL joint refinement, tightly bounded around the staged solution
```

Rules:

- **Each stage is fitted on the data that isolates it**, and its result is frozen
  before the next stage runs. A parameter that was measured (the extrinsic), or
  fitted on a clip where it was the only free thing (medium on L1), is not
  re-freed later merely because the joint fit would then score better.
- **The joint refinement is bounded, and the bound is recorded** — set from the
  staged fits' own uncertainty. It exists to absorb small cross-stage
  inconsistency, not to re-solve the problem. If a parameter wants to leave the
  interval carried from its staged fit, that is a reportable failure of a staged
  assumption — most likely that L1 and L2 did not see the same water — not a
  licence to widen the bound.
- **Report staged and refined parameters side by side.** How far the joint step
  moved each one is a direct measure of how well the staging held, and it is the
  cheapest identifiability evidence in the phase.
- The un-staged, everything-free joint fit is worth running **once, as a
  diagnostic**, to quantify how much worse the conditioning actually is. It is
  a measurement, not a candidate.

Families C and D have no staged path for their *appearance* parameters — that is
exactly why their outputs are tagged non-physical. Their *medium* terms still
follow the ladder above; a family-C LUT does not get to re-estimate `β`.

### What each anchor buys — the degrees-of-freedom ledger

The controlled acquisitions are not redundancy. Each removes specific degrees of
freedom **before** anything is jointly fitted, and every degree of freedom removed
here is one the optimiser cannot use to invent a decomposition. Track them
explicitly:

```text
ANCHOR                          WHAT IT REMOVES FROM THE JOINT FIT

known chart albedo              reflectance scale; ties the multiplicative and
                                additive terms to a point rather than a line
L1 ambient clip, light off      medium parameters, measured with the torch
                                absent entirely
open-water frames, light on     active backscatter, with no object return in
                                the signal
white-target sweep              beam profile and falloff, with albedo known
                                and constant
chart at multiple ranges        attenuation, via its range dependence
repeated views of one point     albedo consistency across beam incidence
                                and range
measured camera-light offset    the extrinsic -- otherwise the easiest
                                parameter for a fit to abuse, because small
                                pose errors mimic beam-profile errors
```

If an anchor was not acquired, record that in the fit record: **the missing anchor
names the parameter most likely to come out unidentified**, and that prediction
should be checked against the identifiability gate below rather than discovered
afterwards.

---

## Primary illumination-model bakeoff

Four families. Same clips, same Week 3 geometry, same held-out split.

### A. No explicit illumination model — control

**Role:** the null hypothesis.
**Hypothesis:** the Week 5/6 physics, whose illuminant is already estimated
from image statistics rather than assumed global, is sufficient.
**Inputs:** range only.
**Why it belongs:** if A is not clearly beaten on L2 and L3, nothing here is
needed and the phase closes. Run A on L1 too, to establish that the more
complex families do not *degrade* ambient footage.

### B. Calibrated physical camera-light model

**Role:** the simplest model that is physically correct in form.
**Hypothesis:** a small number of calibrated physical parameters explain most of
the beam's effect, with far less ambiguity than a spatial field.

**Model.** The image is a sum of three terms, not one:

```text
I_c(x) = L_surface_c(x) + B_active_c(x) + B_ambient_c(x)
```

*Surface term* — angular beam profile (radiant intensity as a function of angle
from the light centreline), near-field falloff (`1/r²` vs `1/(τ + r²)`, fitted
and compared), a learnable ambient level so mixed lighting works, the rigid
camera-light extrinsic, Lambertian `cos θ` response from derived normals, and —
the part the published calibrated light models omit — **two-path medium
attenuation** `exp(−β_c·(d_light + d_cam))`.

*Active backscatter term* — **B must model the torch cone from the start; this
is not a conditional extra.** A dive light does not only illuminate the object,
it illuminates the water between camera and object, producing the veiling cone
that dominates the visual impression of torch-lit footage. A low-capacity
ray-integrated form tied to the *same* calibrated beam and the *same* `β` is
enough: integrate the beam's irradiance along the viewing ray, attenuated over
both the light-to-particle and particle-to-camera paths. No radiative transfer,
no volume scattering function, no new free field — it reuses B's existing
parameters.

*Ambient backscatter term* — the Week 5 term, unchanged.

**Why this is not optional.** Both richer families represent active backscatter
by construction: family C stores a spatially varying additive term per voxel,
and family D decomposes object and medium contributions with the illumination
factor affecting both. If B is allowed only a direct-signal model, then C or D
will beat it **because they model an effect B was forbidden to represent**, and
we would wrongly conclude that spatial flexibility was the necessary ingredient.
The comparison is only fair if every family may express the light cone.

The escalation therefore becomes: *simple ray-integrated active backscatter
leaves structured light-cone residual → richer camera-relative volumetric
backscatter.*

**Inputs:** range, normals (with their uncertainty), camera-light offset,
white-target sweep, chart, pure-water frames.
**Why it belongs:** it is the only family whose parameters stay physically
meaningful and transferable to another dive, and an MIT-licensed reference
implementation exists for the beam-profile and falloff part. Its known gaps —
no spectrum beyond per-channel, no shadows, Lambertian only — are the source of
its conditional challengers.

### C. Low-capacity empirical camera-relative field

**Role:** more flexible than B, more interpretable than a neural field.
**Hypothesis:** the beam's effect is stable in the camera frame and can be
tabulated without being physically parameterised.

**Model:** `I = α·I0 + β` on shading-compensated intensity, with `α` and `β`
per colour channel stored per voxel in a **lookup table over the camera viewing
frustum** (frustum sliced into slabs, each slab a plane of voxels). Estimated
from four constraint types: known colour (chart), correspondence, smoothness
over voxel neighbours, and the pure-water upper bound.

**Inputs:** range, normals (with their uncertainty), chart at multiple
ranges/positions, pure-water frames, colour correspondences from **homogeneous
superpixel regions** — not keypoints, which sit on edges where colour is
unreliable.

**Why it belongs:** it is a directly relevant published camera-relative LUT
approach for co-moving artificial underwater illumination — the closest prior
work to our exact problem — and it is cheap to evaluate, since the known-colour
constraint is linear in its two unknowns.

**The caveat that must be carried forward:** `α` and `β` represent the
**combined** effect of lighting *and* water at that position. They do not
separate them. A fitted `α` is not `exp(−β_att·d)` and a fitted `β` is not a
water-type-comparable coefficient. If C wins, its parameters are persisted as an
explicitly **non-physical appearance field alongside**, never instead of, the
Week 5/6 physical state.

**Note:** correspondence constraints alone are underdetermined — four unknowns
per pair, and a unique solution would need four different-coloured objects at
the same camera-frame position. The chart and pure-water constraints are what
make C identifiable at all. Do not attempt C without them.

### D. Learned illumination field — capacity ceiling, not a pipeline candidate

**Role:** the identifiability oracle. How much of the variation is explainable
at all, and does anything simpler get close?
**Hypothesis:** a field over camera-frame position *and* surface normal captures
beam structure that B and C cannot.

**Model:** an MLP mapping (camera-frame position, camera-frame normal) to a
per-channel illumination factor, multiplying scene albedo, with the medium
represented separately and jointly estimated (attenuation, medium colour,
backscatter). Requires no knowledge of the number, position or profile of the
lights — only that the rig is rigid. Apache-2.0 code and public data exist.

**Why per-channel:** in air one scalar suffices if the lights share a colour; in
a medium the light is already wavelength-dependently attenuated on the way to
the object, so the factor must be per channel.

**Why it is explicitly NOT a candidate pipeline stage.** It is a per-scene
neural field. It restores by **re-rendering the fitted scene**, not by
processing arbitrary frames, so it cannot become a
`FrameSequence -> FrameSequence` stage without violating the project's
video-first invariant. Run it on **L2 only**, treat its held-out numbers as the
ceiling, and if B or C land close to it, take the simpler model and record that
the ceiling was reached.

If D beats B and C by a wide margin on **held-out views**, that is not a
decision to adopt D. It is evidence that a richer camera-relative
representation is warranted, and the correct response is to enrich B or C, not
to import a NeRF.

---

## Conditional challengers

Each requires its named failure to be observed and documented.

```text
TRIGGER                                              -> RESPONSE

Calibrated beam model (B) leaves systematic spatial
residual that REPEATS with camera/light pose          -> escalate B -> C: replace the parametric
                                                        beam with the camera-relative field

Residual varies chromatically in a way a scalar
illumination factor cannot represent                  -> per-channel illumination factor
                                                        (already default in C and D; make it
                                                        explicit in B). Expect a SMALL effect:
                                                        the published ablation found the
                                                        single-vs-three-channel difference
                                                        drowned in real-data noise

Residual correlates with surface orientation
after cos(theta) compensation                         -> normal-aware response: add the normal as
                                                        an input rather than dividing by cos(theta)

Residual concentrates behind occluders /
in cast shadows                                       -> visibility term. Named gap in BOTH leading
                                                        methods; genuinely unsolved. Expect to
                                                        document rather than fix

B's ray-integrated active backscatter leaves
STRUCTURED light-cone residual (B already models
the cone; this fires only if that model is too
simple, not if the cone merely exists)                -> richer camera-relative volumetric
                                                        backscatter, i.e. let the medium term vary
                                                        spatially in the camera frame rather than
                                                        being a function of the calibrated beam

One field fits training views but fails
held-out views                                        -> REJECT OR REGULARISE. Do not increase
                                                        capacity. This is the predicted failure
                                                        mode, observed independently by both
                                                        leading papers

Different initialisations or fit orderings give
similar images but substantially different
physical parameters                                   -> NOT IDENTIFIED. Add an anchor, fix a
                                                        stage, or fall back to a lower-capacity
                                                        family. Never resolved by picking the run
                                                        with the lowest error

Geometry uncertainty dominates illumination
estimation                                            -> STOP. Do not escalate illumination
                                                        complexity. Return to the Week 3 error
                                                        budget and fix or characterise geometry
                                                        first

Multiple lights, or mixed ambient/artificial,
breaks the single-light parameterisation              -> the camera-relative families (C, D) need
                                                        no light count; switch representation
                                                        rather than adding light instances
```

---

## Common output / state representation

Extends the Week 5 parameter-trace schema; does not replace it. Persist per
frame, unsummarised:

```text
T_wc, K                     camera pose and intrinsics (from Week 3)
T_cl                        camera->light rigid transform, and its uncertainty
light_params                beam profile parameters, falloff tau, ambient term,
                            per-channel source scaling      [families B]
illumination_field          the estimated field itself      [families C, D]
predicted_illumination      per-pixel illumination factor at reconstructed points
                            -- ALWAYS persisted, for every family, because it is
                            the one quantity all four can produce
medium_params               beta_att, beta_bs, B_inf per channel, and whether
                            they are PHYSICAL, PHYSICAL-BUT-UNIDENTIFIED or an
                            APPEARANCE FIT
identifiability             per physical parameter: the spread across the
                            multi-start / ordering runs, the tolerance it was
                            judged against, and the verdict
staged_vs_refined           each staged parameter, its bound, and how far the
                            joint refinement moved it
confidence                  per-pixel where available
residual                    post-correction residual map
provenance                  method, config hash, clip, frame range, seed,
                            initialisation and fit ordering
```

Two hard rules:

- **Preserve full spatial fields where tractable.** Never reduce an illumination
  field to a scalar mean; that hides exactly the local failure this phase
  exists to find. Store at the field's native resolution, downsampled only with
  the factor recorded — written per frame to chunked storage as it is produced,
  per `CLAUDE.md` invariant 9, never accumulated into a full-clip array.
- **Tag every medium parameter as physical, physical-but-unidentified, or
  appearance.** A family-C `β` and a family-B `β_att` are not the same quantity
  and must never be averaged, compared or carried into Week 6's physical state as
  if they were. The third tag is not a formality: a parameter that failed the
  identifiability gate travels with the appearance parameters — usable for
  restoration, never quoted as a measurement, never transferred to another dive.

---

## Held-out evaluation protocol

**Nothing is selected on training-view fit.** This is non-negotiable: a
sufficiently flexible illumination field always explains the frames it was
fitted on, and both leading published methods report exactly this failure.

Split L2 by **camera/light pose**, not randomly by frame — adjacent frames see
nearly the same illumination, so a random split leaks. Hold out ≥ 5 test views
spanning beam-centre and beam-edge incidence, and at least one range extreme.

Measured for every family:

### 1. Radiometric consistency — the primary test

For a static scene point `p` observed in views `i` and `j` under different beam
incidence, the recovered scene radiance should agree:

```text
J_hat_i(p) ~= J_hat_j(p)
```

Robust statistics, coverage always reported. This is the measurement that
distinguishes "removed the illumination" from "made the picture look nicer",
and it needs no ground truth.

### 2. Held-out view prediction

Fit on training poses, predict the held-out views, compare. Report the
train/held-out gap explicitly per family — the gap itself is the
overfitting diagnostic.

### 3. Chart accuracy

ΔE00 and per-channel residual on chart patches in held-out views, near / mid /
far separately. Recovered colour is only defined **up to a global scale**, so
align all patches with one least-squares scalar over the full patch set before
scoring, and report that scalar. Do not use per-patch alignment.

### 4. Spatial residual structure — the diagnostic that drives the triggers

After correction, test whether residual still correlates with:

```text
image position          light-to-point range      surface orientation
beam angle              camera-to-point range     distance along the beam axis
```

A correct illumination model **reduces structured, pose-dependent residual**.
Residual that is unstructured is a precision problem, not a model problem. The
correlation that survives names the challenger to activate.

### 5. Temporal behaviour

Score with the **frozen Phase 2B stack, unmodified**: canonical
illumination-aware MC-Warp@1/@4/@8, raw MC-Warp, the alignment-robust
companion, coverage and status. **Do not refit, extend or per-pixel it.**
Separately inspect the physical-state trajectories. A model with excellent
spatial correction and pumping illumination parameters is rejected.

### 6. Recoverability

Extreme gains, clipping fraction, near-floor fraction, noise amplification,
invalid range fraction, confidence where available. A beam model that produces
a beautiful centre and a 40× gain at the beam edge has not solved anything.

### 7. Cost

Fitting time, inference time, memory, integration complexity. Recorded to inform
architecture, never as the primary criterion.

---

## Geometry sensitivity

Illumination estimation sits downstream of Week 3, and a flexible illumination
model will happily absorb geometry error. Perturb deliberately and measure:

```text
global range scale error       (Week 3 showed this is absorbable by beta --
                                check whether it is still absorbable once a
                                light with distance-dependent falloff exists)
local range error              per the Week 3 noise sweep
surface normal error           the quantity families B and C depend on most,
                                and the noisiest thing derived from range
camera pose error
camera-light extrinsic error   the parameter nobody measures carefully
```

For each, report how much of the illumination model's apparent advantage
survives. **If a family's win disappears under plausible geometry perturbation,
it was absorbing geometry error, and that must be written down explicitly
rather than reported as an illumination result.**

Note the interaction worth watching: a camera-mounted light introduces a
distance-dependent falloff term, which may **break** the exact global-scale
invariance that Week 3 established for the pure attenuation model. If so, Week
6B is the phase where metric scale starts to matter, and that finding must be
recorded for Weeks 3 and 5–6.

---

## Medium / illumination identifiability checks

Before believing any separation result:

1. **Distance variation check.** Confirm from the Week 3 range product that
   camera-to-scene distance actually varies across the clip. Without it,
   attenuation and object colour are not separable, full stop.
2. **Beam incidence variation check.** Confirm that held-out points are observed
   at materially different beam angles. Without it, illumination and albedo are
   not separable.
3. **Capacity-steals-illumination check.** Where a family has spare appearance
   capacity (view-dependent colour, per-frame appearance embeddings, free
   albedo), ablate it. If disabling that capacity *improves* the illumination
   estimate, the capacity was absorbing the light — a documented failure of the
   published neural approach, and the reason its authors disable view dependency
   and appearance embeddings.
4. **Swap test.** Apply a model fitted on one clip to a different clip of the
   same scene with the same rig. A genuine camera-relative illumination model
   transfers; a memorised one does not.
5. **Multi-start and ordering sensitivity.** Refit every family that claims
   physical parameters from at least three materially different
   initialisations, and under at least two fit orderings — the staged ladder
   above, plus at least one alternative (medium and active illumination
   swapped, or the un-staged everything-free diagnostic). Record, per run, the
   full recovered parameter vector *and* the held-out image error. Fixed seeds,
   recorded in provenance.
6. **Parameter spread vs. image spread.** Compare the spread of recovered
   parameters across those runs against the spread of held-out image error.
   Similar images from dissimilar parameters is the signature of an
   unidentified model, and it is invisible to every other test in this phase.

### The identifiability gate

> If materially different initialisations or fit orderings produce similar
> rendered and held-out images but substantially different physical
> parameters, **the model is not identified**. Its parameters must not be
> reported, persisted or transferred as physical. Either constrain the model
> further — acquire another anchor, tighten a bound, fix a stage — or fall back
> to a lower-capacity family.

Held-out prediction protects against memorising the training views. It does
**not** protect against several physically different decompositions that predict
held-out views equally well. Concretely,

```text
beta = 0.15    rho = 0.7    L = 1.0
beta = 0.25    rho = 0.9    L = 1.4
```

can explain nearly identical measurements over a limited range span. If both fit
and predict equally well, the conclusion is **not** "run B found the true `β`".
It is "**the data do not identify `β` at this precision**".

"Materially different" and "similar" need numbers, and the project already has
the method for producing them: Week 3's **restoration-relevance sensitivity
test**, applied here to the illumination and medium parameters instead of to
range. Propagate the observed multi-start parameter spread through the
restoration calculation and ask whether the restored output moves by more than
the measured residual noise floor. Two runs whose parameters differ but whose
restored output does not are a *labelling* problem, not a restoration problem —
still unidentified, still not physical, but harmless downstream. Two runs whose
outputs also differ are a live risk to every later stage. Declare both
thresholds before running the sweep, not after seeing the spread.

An unidentified model is an acceptable outcome, not a failure of the phase. A
latent that is stable and produces good restoration is still useful; it simply
is not a measurement. Tag it `PHYSICAL-BUT-UNIDENTIFIED` in the state schema,
and do not compare it to published water-type coefficients, carry it into Week
6's physical state, or transfer it to another dive as if it had been measured.
The honest claim is about the pipeline's output, not about the water.

---

## Temporal / state behaviour

Do not smooth illumination estimates by default. A camera-mounted light
**legitimately** changes what it illuminates as the camera moves; smoothing that
away is a modelling error, not stabilisation.

The rule:

```text
remove estimator jitter
do NOT smooth away real pose-dependent illumination transitions
```

Separate what should be constant from what should vary:

- **should be constant** within a dive: beam profile, falloff `τ`, source
  spectrum/per-channel scaling, camera-light extrinsic, and `β` for a given
  water body. Estimate these globally, or stabilise them with the Week 5
  machinery, and treat drift in them as a fault signal.
- **should vary**: the per-pixel illumination a point receives. Predict it from
  `(camera pose, light pose, geometry)` rather than temporally filtering the
  output image. If illumination is deterministic given state, deriving it from
  state is both more correct and more stable than blurring frames.

Persist raw and stabilised traces for the constant set, per the Week 5 schema.

---

## Restoration-relevance comparison

Same discipline as Week 3: the bakeoff does not end with illumination metrics.

Run each family's output through the full restoration path and measure whether
the differences change anything a viewer or a downstream stage would see:
restored radiance, near/mid/far consistency, chart ΔE00, gain and clipping
behaviour, and the frozen temporal stack.

Then answer the only question that matters:

> Does the difference between families exceed the geometry-induced spread
> measured in Week 3?

If it does not, the families are tied, and A wins by simplicity.

---

## Selection rule

Prefer the **simplest** model that:

1. materially improves **held-out** radiometric consistency and restoration,
2. explains pose-dependent artificial-light variation rather than absorbing it
   into albedo,
3. preserves scene reflectance and colour relationships,
4. does not absorb geometry or medium error indiscriminately (geometry
   sensitivity section),
5. behaves temporally under the frozen evaluator, with stable latent parameters,
6. stays interpretable and debuggable,
7. improves restoration on actual dive-light footage (L4),
8. **is identifiable from the evidence available** — passes the identifiability
   gate, or has its unidentified parameters explicitly demoted to latent
   appearance state before selection, not after.

Criterion 8 changes what a win means. Between two families that restore
comparably, the one whose decomposition survives multi-start and reordering is
preferred **even if its error is slightly higher**, because its parameters are
the ones Weeks 6–8 are allowed to reason about physically.

Do not force a winner. All of these are legitimate:

- **no explicit complex-light model is needed** for the target footage — likely
  if most diving is ambient-lit and the torch is fill light,
- the calibrated physical model B is sufficient, and its parameters transfer
  across dives,
- the empirical field C materially wins, and is adopted as an explicitly
  non-physical appearance layer,
- the learned field D wins on held-out views, which is read as *"enrich B or C"*,
  not *"adopt a NeRF"*,
- a hybrid — physical beam model plus a low-capacity residual field — is best,
- a family restores well but is **not identified**, and is adopted with its
  physical parameters demoted to latent appearance state and that stated
  plainly,
- **geometry quality is the limiting factor**, and illumination-model selection
  is deferred with that stated as the reason.

The last two outcomes are real possibilities and are not failures of this
phase.

---

## Stop rule

> Once the primary bakeoff spans **no-explicit-light baseline**, a **calibrated
> low-capacity physical model**, a **flexible empirical spatial field**, and a
> **modern learned illumination field**, do not add another approach unless an
> observed failure identifies a missing capability that the new method
> specifically addresses.

Benchmark novelty is not sufficient reason. This subfield is young — the
leading published method states there are *virtually no competitor methods to
compare against* — so expect the literature to churn without the underlying
answer changing. Conditional challengers are unlocked by their triggers, one at
a time.

---

## Gate

Proceed to Week 7 when:

- the prerequisites above were satisfied *before* fitting, and the distance- and
  beam-incidence-variation checks passed on the fitting clip,
- all four families were evaluated on **held-out** poses, with the
  train/held-out gap reported per family,
- radiometric consistency across differing beam incidence is measured, with
  coverage,
- spatial residual structure is characterised, and every surviving correlation
  is either explained or attached to an activated challenger,
- **geometry sensitivity is measured**, and any family whose advantage does not
  survive plausible geometry perturbation is documented as absorbing geometry
  error,
- **the staged fit ladder was followed**, with each stage's data, bound, and the
  distance the joint refinement moved each parameter recorded, and the
  un-staged joint fit run once as a conditioning diagnostic,
- **multi-start and fit-ordering sensitivity is measured** for every family
  claiming physical parameters, with the parameter-spread and image-spread
  thresholds declared beforehand, and an identifiability verdict recorded per
  parameter,
- medium parameters are explicitly tagged physical, physical-but-unidentified,
  or appearance, and neither an appearance fit nor an unidentified parameter has
  leaked into Week 6's physical state,
- the frozen Phase 2B temporal stack is unchanged and its numbers are acceptable,
  with physical-state trajectories separately inspected,
- restoration-relevance is compared against the Week 3 geometry-induced spread,
- a selection is recorded **with its evidence**, including "no explicit model
  needed" or "deferred pending geometry" as legitimate outcomes,
- the persisted state satisfies the schema above, with full spatial fields
  retained.

If the answer is that no explicit illumination model is warranted for this
footage, record it and move on. Week 7 will stress the selected configuration —
including the null one — against moving beams, multiple lights, shadows, mixed
lighting and extrapolation beyond the calibrated beam profile.

---

# Week 7 — Stress test and failure taxonomy

## Goal

Stop optimizing on friendly footage.

Run the pipeline on the ugliest real footage available.

Include:

- clipped red channel,
- very low red SNR,
- heavy particulate,
- bubbles,
- artificial lights,
- moving light beams,
- low visibility,
- surge,
- fast camera motion,
- moving animals,
- large textureless regions,
- depth failure,
- severe backscatter,
- strong color casts.

The artificial-light entries here stress **whatever Week 6B selected** —
including the null selection. Week 6B answers the architectural question (what
illumination model, if any); Week 7 stresses that answer against moving beams,
multiple lights, shadows, mixed ambient/artificial lighting, and extrapolation
beyond the calibrated beam profile. Do not relitigate the model choice here.

---

## Categorize failures

Do not merely record “bad result.”

Classify failures into causes such as:

### Information-theoretic / unrecoverable

- clipped channel,
- channel below useful SNR,
- complete occlusion,
- severe compression.

### Geometry

- incorrect depth,
- refractive reconstruction error,
- monocular depth failure,
- moving object mismatch.

### Optical model

- backscatter-model mismatch,
- attenuation-model mismatch,
- heterogeneous water,
- local illumination.

### Temporal

- parameter jitter,
- estimator lag,
- illumination transitions,
- flow/correspondence failures.

### Acquisition

- bad filter choice,
- auto-WB/exposure changes,
- insufficient light,
- codec limitation.

### Algorithmic

- clipping,
- halos,
- excessive gain,
- chromatic artifacts,
- contrast over-amplification.

---

## Gate

Produce a prioritized written failure list containing:

- frequency,
- severity,
- root-cause hypothesis,
- whether more physics can plausibly solve it,
- whether additional acquisition metadata would help,
- whether a learned residual is justified.

This becomes the specification for later learned components.

Do not introduce ML merely because Week 7 looks ugly.

---

# Week 8 — Residual temporal consistency and long-duration stability

## Goal

Fix temporal defects that remain after Weeks 5–6 already stabilize estimated physical parameters.

This is **not** “add temporal consistency from scratch.”

Phase 2B already established the short-range temporal measurement stack:

- raw MC-Warp@1/@4/@8,
- canonical illumination-aware MC-Warp@1/@4/@8,
- alignment-robust warp companion,
- temporal ΔE00,
- valid coverage/status,
- input baselines,
- illumination-confound reporting.

Do not casually add more pairwise temporal metrics.

Start by identifying **which physical or appearance variable is unstable**.

---

## Known Phase 2B limitations to revisit here

Phase 2B deliberately stopped short of long-duration temporal evaluation.

The following limitations are known and must be revisited on continuous footage.

### Fixed-lag aliasing

A temporal oscillation can disappear at a lag that is an integer multiple of its period.

Phase 2B measured this directly on synthetic flicker.

For example:

```text
period-2 oscillation:
@1  visible
@2  invisible
@4  invisible
```

More generally, a fixed lag can be blind when two frames land on the same phase of a periodic oscillation.

Therefore:

> MC-Warp@1/@4/@8 provides several useful temporal scales, but it is not a complete detector of arbitrary periodic pumping.

Do not respond by simply adding many arbitrary fixed lags.

Use the long-duration experiment below to determine whether this mathematical blind spot corresponds to an actual restoration failure.

### Short-window sampling

Phase 2B evaluated short excerpts and a small number of nearby anchor triples.

It established:

- exact implementation repeatability,
- measurable local scene/anchor variability,
- sensitivity to injected restoration flicker,

but it did **not** establish:

- 30-second drift,
- low-frequency pumping,
- periodic parameter oscillation,
- accumulation of small estimation errors,
- delayed adaptation following genuine environmental changes.

### Subpixel / resampling floor

Phase 2B showed that a substantial fraction of raw MC-Warp on textured clips can come from subpixel resampling even when correspondence is correct.

The alignment-robust companion exists to expose that sensitivity.

Do not silently subtract an estimated interpolation floor from MC-Warp.

Treat:

- raw MC-Warp,
- alignment-robust warp,
- residual maps,

as complementary evidence.

### Correspondence blind spots

Continue to remember:

- FB self-consistency is not proof of correctness,
- smooth moving animals may be entirely excluded,
- bubbles/particles remain difficult,
- long-lag coverage is incomplete,
- localized illumination can remain confounded.

Do not interpret a clean temporal score as proof that every semantic region was stable.

---

## Order of attack

### 1. Physical parameter stabilization

First inspect and improve stabilization of estimated physical parameters such as:

- backscatter parameters,
- attenuation coefficients,
- applicable depth scale/offset terms.

If visible output flicker comes directly from parameter jitter, fix the estimator/state first.

Prefer stabilizing the causal physical variable over finished image pixels.

Do not smooth finished pixels to conceal unstable parameter estimation.

---

### 2. Change-point behavior

Ensure genuine environmental changes are followed rather than suppressed.

Examples:

- entering/exiting a particulate cloud,
- changing water body,
- thermocline/halocline-associated optical changes,
- moving between ambient and artificially lit regions,
- material scene/illumination transitions.

A stabilizer that produces excellent temporal metrics by lagging behind a real transition is incorrect.

Use the Week 5/6 synthetic-transition framework to verify:

```text
constant underlying parameter + estimator noise
    -> suppress jitter

true parameter step/change
    -> follow change without excessive delay or overshoot
```

---

### 3. Long-duration residual analysis

Run at least one continuous approximately **30-second swim-through** through the current full physical pipeline.

Prefer a representative clip containing enough scene motion and depth variation to stress the system without being dominated by a known pathological confound.

Also include a difficult clip if useful, but do not substitute only pathological footage for the representative run.

Record over the full interval:

- raw MC-Warp@1/@4/@8,
- canonical illumination-aware MC-Warp@1/@4/@8,
- alignment-robust companion,
- temporal ΔE00,
- valid coverage,
- illumination-confound/status,
- relevant physical-parameter trajectories,
- correction gains/range diagnostics where applicable.

Preserve the frozen Phase 2B metric definitions.

Do not retune Phase 2B:

- flow configuration,
- validity thresholds,
- illumination-fit model,
- illumination guards,
- confound/status thresholds,
- alignment-robust parameters,

merely because long-duration footage produces less flattering results.

---

### 4. Parameter-trace inspection

Plot or otherwise inspect important estimated parameters over time.

Look explicitly for:

- high-frequency jitter,
- period-2 / period-3 / period-4 oscillation,
- slower periodic pumping,
- monotonic drift,
- estimator lag,
- overshoot,
- correlated oscillation between channels,
- abrupt changes unsupported by the scene.

Where possible, compare parameter motion with:

- camera motion,
- depth/range changes,
- estimator confidence/residual,
- illumination changes,
- known scene transitions.

The objective is to identify **cause**, not merely detect visible flicker.

Prefer a parameter-level diagnosis when the unstable variable is available.

---

### 5. Fixed-lag aliasing falsification

Use the long-duration run to ask:

> Is there visible or parameter-level periodic instability that MC-Warp@1/@4/@8 and temporal ΔE00 fail to expose clearly?

Do not assume the answer is yes.

Construct controlled/synthetic traces with known temporal behavior to characterize the existing metric stack.

Include representative cases such as:

```text
period 2
period 3
period 4
period 5 or another period not aligned with 1/4/8
slow sinusoidal pumping
slow monotonic drift
```

The goal is to understand blind spots, not optimize lag selection.

Do not add a dense bank of MC-Warp lags to the reported metric set.

A one-off MC-Warp@k-versus-k sweep as a *characterisation* is permitted — an
ideal periodic signal produces minima at multiples of its period, and the cost is
roughly 12 anchors × 30 lags × 2 inferences ≈ 8.5 minutes. But it is a
**contingency, not a required measurement**: it walks straight back into coverage
decay, correspondence error, the resampling floor, and lag-dependent visible
regions — the four confounds parameter-space analysis exists to escape. Use it
only to demonstrate an appearance-space signature for a periodicity the parameter
traces have already found, or when parameter-space and image-space evidence
disagree.

---

## Conditional long-duration flicker / pumping diagnostic

A new temporal diagnostic is **not automatically required**.

Research or implement one only if the long-duration experiment demonstrates a concrete failure such as:

> Visible or parameter-level pumping exists, but the frozen Phase 2B metric stack does not expose it reliably.

If no such failure is demonstrated:

> add nothing.

### Desired diagnostic class if needed

Prefer a diagnostic that measures information genuinely absent from pairwise MC-Warp.

The leading class to investigate is a **long-duration temporal trajectory / frequency diagnostic**, for example:

- temporal-frequency energy,
- spectral power in non-DC parameter variation,
- detrended temporal trajectory energy,
- periodicity/autocorrelation analysis,
- explicit long-window drift statistics.

Prefer applying this first to **estimated physical parameters** when the causal variable is available.

Examples:

```text
attenuation coefficient trajectory
backscatter parameter trajectory
depth scale/offset trajectory
global correction parameter trajectory
```

A periodic instability in a physical parameter should preferably be detected at the parameter level rather than inferred indirectly from finished pixels.

If parameter-level analysis is insufficient, a motion-aligned appearance trajectory may be considered.

### Requirements for any added diagnostic

Any new diagnostic must:

- address a demonstrated blind spot,
- operate over a meaningfully longer temporal window than MC-Warp@1/@4/@8,
- add information rather than duplicate another pairwise residual,
- remain separate from the frozen Phase 2B metrics,
- expose its own assumptions,
- avoid rewarding blur,
- account for or explicitly caveat legitimate illumination variation,
- not hide correspondence coverage,
- not require a nonexistent clean reference video,
- have a synthetic falsification test.

Do not add a metric merely because it is common in the literature.

Do not add:

- another arbitrary SSIM variant,
- another LPIPS-like pairwise score,
- another collection of fixed MC-Warp lags,
- a weighted master temporal score.

---

## Bounded literature pass — DONE, do not repeat

The literature review this section called for has been performed and is recorded
in:

```text
experiments/week2b_temporal/TEMPORAL_METRIC_LITERATURE.md
```

Seven passes, fourteen literatures, formulations verified from primary sources,
an adversarial re-review, and an independent check that corrected six factual
errors. **Do not re-run this search.** Its rejections, with reasons, exist
precisely so the same ground is not covered again.

### What it concluded

```text
Phase 2B stays frozen.
No new image-space flicker or video metric is added.
Week 8 carries ONE conditional family:
    periodicity / whiteness / trend analysis of physical-parameter trajectories,
    in parameter space, as a DECISION TREE, not a precommitted single test.
```

### What it established about the field

No-reference video flicker metrics **do** exist — Guthier, CTI, FDI, VBench
temporal flickering, WCS Flicker Penalty, BG-Flicker, per-pixel temporal
variance. Each handles camera motion in one of three ways: ignores it, excludes
it (static scenes only), or compensates it with optical flow and takes a pairwise
photometric residual. The third is MC-Warp, which we already have — with
coverage, an illumination model, a resampling floor and an error bar that none of
them carry.

Among the methods reviewed, none is simultaneously: no-reference, robust to
substantial camera motion, genuinely long-window, able to separate drift from
pumping from spikes, **and** calibrated with a statistical null.

### Standing rejections — do not reopen without new evidence

```text
require a pristine reference video
    tOF/tLP (supervised form), RWE, MABD, PSPTNR, TAE, FS-MOVIE, MOVIE,
    T-SSIM/T-PSNR, ST-RRED, VQA-SIAT, SR-3DVQA, ColorVideoVDP,
    H.264/HEVC intra-flicker metrics

presuppose a static or near-static scene
    VBench temporal flickering, per-pixel temporal variance, EVM

are correction methods, not measures
    van Roosmalen alpha/beta, Boitard, motion-compensated temporal filtering

calibrated for a stimulus or window we do not have
    IEC 61000-4-15 flickermeter (10-minute window; filament-lamp calibration)
    JEITA (subsumed), VESA FMA / percent flicker (conflates drift/spike/oscillation)

sign-inverted or subsumed
    video-stabilization stability score (scores slow drift as "stable")
    trajectory curvature, TRAJAN, DFA/Hurst, RQA, spectral kurtosis
    OMIQ / coding efficiency (blur-gamed by its authors' own admission)
    learned NR-VQA (FAST-VQA, DOVER, StableVQA, ReVQ)
```

Specifically do **not** re-propose a spatially varying gain/bias field to fix the
`lights` confound. Phase 2B chose a single global scalar because it is
structurally incapable of absorbing chroma flicker; a smooth spatial field has
enough freedom to absorb the very failure the metric exists to catch.

---

## Week 8 analysis design — decision tree, not one instrument

Derived from the literature pass. Do **not** precommit to a statistical test
before looking at the data.

### Default, before any test is chosen

```text
plot the trajectories
robust effect sizes, always in the parameter's own physical units
spike statistics: robust z on max |delta p|
ACF, PSD, drift
the frozen Phase 2B per-pair appearance trajectory
per-frame log-average brightness trace, input AND corrected (see below)
characterise the background spectrum -- do NOT assume it
```

### Branches

```text
approximately stationary, phase-coherent pumping
    -> validated noise continuum + multitaper / periodogram significance
       (Thomson harmonic F-test; Vaughan red-noise test IF a power-law
        continuum genuinely fits)

transient, bursty, or frequency-wandering pumping
    -> time-localised wavelet power with a validated background
       (Torrence & Compo; respect the cone of influence -- on a 30 s record
        it removes real estate exactly where slow pumping lives)

attribution to motion / illumination / range is ambiguous
    -> cross-wavelet transform and wavelet coherence against covariates
       (phase statistics; Monte Carlo significance)
       significant coherence + stable phase STRENGTHENS evidence of coupling;
       it does not establish causality -- a common driver produces both

traces are outlier- or trend-contaminated, or carry several periods
    -> RobustPeriod

null-model choice becomes the limiting uncertainty
    -> Bayesian spectral analysis; GP quasi-periodic-vs-red-noise comparison

output flickers while every physical trace is clean
    -> flow-aligned appearance trajectories (the contingency below)
```

### Adoption preconditions — all six required

These are six *conditions*, not six instruments. The inventory of instruments
carried is §16.1 of the literature artifact.

1. **Declared spatial reduction** for any parameter field, with sensitivity
   checks across several reductions.
2. **Effect size beside every p-value.** Significance without amplitude is not a
   finding.
3. **Background spectrum characterised and its adequacy tested** before any
   periodicity test; PSD always plotted.
4. **Autocorrelation-aware trend testing** — prewhitened or variance-corrected
   Mann–Kendall, or a GLS/state-space trend test — with Sen's slope as the robust
   effect size. Plain Mann–Kendall is invalid on serially dependent traces.
5. **Multiplicity is controlled at every level it exists.**

   ```text
   within one trace   Vaughan-style trials correction over scanned frequencies
   across the t-f plane   pointwise wavelet significance is NOT sufficient;
                          predeclare the searched region, or calibrate a global
                          false-positive rate by null simulation / max-statistic
   above the trace    5 clips x several parameters x several reductions
                      x several diagnostics -- predeclare a small confirmatory
                      family, or correct; label everything else EXPLORATORY
   ```

6. **The background fit is predeclared, or the whole procedure is calibrated.**
   Identifying peaks from the data, removing them, refitting a lower continuum
   and then applying a significance formula that assumes an independently fixed
   continuum is selection bias. Either use a predeclared robust fitting
   procedure, or calibrate the **entire fit → exclusion → test pipeline** under
   the null by simulation or posterior predictive checking.

### Kill criterion

Drop parameter-space trajectory analysis **as the detector for that specific
observed failure mode** — do not elaborate it there — if Week 8 shows flicker
visible or measurable in MC-Warp@1 **while every relevant physical trace is
quiet**. That means the instability is spatially localised or lives in a stage
with no exposed state, so escalate *that failure* to the flow-aligned
appearance-trajectory branch.

This does not retire the family. Parameter-space analysis may still be the right
detector for other clips, other parameters, or other failure modes; judge it per
failure, not globally.

---

## Free instruments to add in Week 8 — no new metric, no new dependency

### Per-frame log-average brightness trace

```text
I_bar(t) = exp( (1/n) * sum_j log( I_j(t) + delta ) )
```

Computed on the **input** and on the **corrected output** separately, every
frame. Geometric rather than arithmetic mean: resists outliers and better matches
perceived brightness. No optical flow, no warp, no mask, no resampling, no
inference — it is available before any physical estimator exists.

Feed it to the same analysis as the parameter traces. Read it only in comparison,
corrected against input, exactly as `--method none` is used today.

This is a **covariate, not an addition to the frozen Phase 2B metrics.**

Adopt the signal; do **not** adopt the source's consecutive-frame JND detector,
which has no motion compensation and would reward a stabilizer that lags a real
transition.

### Spatio-temporal slice

One scanline stacked over the whole run into an x–t image. Periodic pumping shows
as horizontal banding, drift as a gradient. One numpy slice, no inference.

---

## Conditional instruments — valid on `murky_shark` only

`murky_shark` is the project's **static-scene probe**: 0.03 px/frame at @1,
motion-reduction ratio only 1.37× at @1, and coverage 96.3 / 90.9 / 89.7 % — the
least lag decay of any clip, because almost nothing leaves the frame.

Several methods that fail on a swim-through fail *because of camera motion*, and
therefore hold on this clip:

```text
long-range / anchor warp error
    fails elsewhere because the valid mask empties over hundreds of frames
    holds here because coverage is nearly flat with lag
    -> a genuine long-range appearance comparison using FROZEN machinery only

Eulerian Video Magnification
    fails elsewhere because it amplifies parallax
    holds here because the static-camera assumption approximately applies
    -> a visualisation that reveals sub-threshold pumping

deliberate static-scene flicker probing (VBench's design)
    we already have the asset; this clip IS the least motion-confounded probe
```

Use these **on `murky_shark` only**, and say so whenever a number from them is
reported. Do not generalise a result from this clip to the moving categories —
`CLAUDE.md` invariant 6 applies to instruments as well as to pipeline changes.

Once a period has been established, the **flicker index** (area above the mean /
total area, per cycle) is a cheap waveform-shape descriptor separating a smooth
sinusoid from a spiky sawtooth at equal amplitude. It cannot be used as a
detector, because it presupposes the period.

---

## Interpretation rules — adopt, cost nothing

### Motion silencing

Local flicker visibility is measurably suppressed by large coherent motion.
Therefore, all else equal, the same local flicker **may** be more visible in
low-motion content (`murky_shark`) than in high-motion content (`swimthrough`).

Do not rank clips by measured residual and treat that as a ranking of severity.
Do not dismiss a smaller measured instability on a static clip as less important
than a larger one on a moving clip.

This is a tendency, **not** a correction factor — visibility also depends on
eccentricity, texture, frequency, luminance, spatial extent and display. Never
convert it into a numerical adjustment between clips.

### Never conflate the three

```text
statistical significance | physical amplitude | perceptual visibility
```

A p-value says a component is not noise. It says nothing about whether the
amplitude matters, and nothing about whether anyone can see it.

### The perceptual question comes last

Only after detection has fired, and never before:

```text
temporal-edge perceptual models (Ebelin et al. 2024)
CIE TN 006 visibility measure + elaTCSF   -- validate the transfer first
ColorVideoVDP in a well-posed A/B:
    same clip, dynamic parameters vs parameters frozen at the clip median
    read as "is the difference between two pipeline variants visible"
    never as "is the restoration correct"
```

Validating the transfer means: render the corrected sequence with and without the
detected oscillation, measure the actual on-screen modulation it produces, and
apply the sensitivity curve to that measured modulation — not to the raw
parameter amplitude. Note also that these curves come from static full-field
stimuli: applying a static-stimulus visibility model without motion masking can
**overestimate** local-flicker visibility under strong coherent motion, by an
amount that is content- and viewing-dependent.

---

### 6. Residual flow-aligned appearance analysis

After parameter stabilization and long-duration parameter analysis, use the frozen Phase 2B flow-aligned diagnostics to locate remaining appearance instability.

Inspect:

- raw MC-Warp,
- canonical illumination-aware MC-Warp,
- alignment-robust warp,
- temporal ΔE00,
- residual maps,
- valid masks,
- coverage.

Distinguish:

```text
physical-parameter instability
vs
correspondence error
vs
subpixel/resampling floor
vs
legitimate source illumination
vs
actual output-space appearance instability
```

Do not fix one category with a mechanism intended for another.

---

### 7. Output-space temporal processing

Only if upstream parameter stabilization cannot solve a remaining **visible, measured** defect should restrained output-space temporal processing be investigated.

Possible approaches must remain conservative.

Do not:

- blur frames merely to improve MC-Warp,
- introduce ghosting,
- smear moving animals,
- suppress genuine illumination transitions,
- erase scene detail.

Any output-space method must be compared against:

```text
physical pipeline only
physical pipeline + output temporal method
```

with spatial fidelity inspected separately.

---

## Long-duration validation

Run at least one approximately **30-second continuous swim-through**.

Evaluate over the full sequence.

### Frozen appearance metrics

- raw MC-Warp@1,
- raw MC-Warp@4,
- raw MC-Warp@8,
- canonical illumination-aware MC-Warp@1/@4/@8,
- alignment-robust companion,
- temporal ΔE00,
- valid coverage,
- illumination-confound/status.

### Physical parameter traces

Use the **complete Week 5 persistence schema** — see Week 5 → *Parameter trace
persistence*. For each physical quantity (attenuation coefficients, backscatter
parameters, depth-scale/offset estimates) Week 8 needs, **separately**:

```text
raw per-frame estimate
stabilized estimate
innovation / prediction residual
estimator uncertainty or covariance, where the model provides one
input-derived covariates: ORIGINAL frame-mean linear luminance,
                          camera-motion magnitude, range
```

A generic "confidence/residual" is not an adequate substitute: the four signals
answer four different questions (§ Week 8 analysis design), and a physical
parameter is not expected to be white while an innovation is.

### Long-duration behavior

Explicitly inspect:

- visible pumping,
- periodic flicker,
- low-frequency drift,
- parameter oscillation,
- estimator lag,
- accumulation,
- abrupt unsupported jumps.

Do not reduce the result to one aggregate average.

A 30-second trace containing one objectionable periodic failure is not “good” merely because its mean temporal error is small.

---

## Gate

Proceed only when representative long-duration footage has:

- no objectionable visible pumping,
- no unexplained parameter oscillation,
- no material slow drift caused by restoration,
- acceptable MC-Warp@1/@4/@8 behavior,
- acceptable temporal ΔE behavior,
- adequate and reported correspondence coverage,
- genuine environmental transitions followed without excessive lag,
- preserved spatial detail,
- no ghosting,
- no temporal smoothing used merely to game the metric.

Additionally:

### If the frozen Phase 2B stack detects every important observed temporal failure

Do **not** add another flicker metric. The literature pass is complete and its
rejections stand.

### If a demonstrated long-duration periodic/drift failure escapes the frozen metrics

Add at most **one conditional analysis family** — the parameter-trajectory
family of the decision tree above — not one isolated test. In practice that
means the default views (effect sizes, ACF, PSD, drift, spikes), the companions,
and **the single applicable branch**, chosen after characterising the noise
rather than precommitted. All six adoption preconditions must be met, the family
must be validated synthetically, and its incremental information documented.

Do not reduce this to one diagnostic — that recreates the superseded
single-test formulation.

The Week 8 goal is stable restoration over time, not maximal metric count.

---

# Week 9 — External benchmark

## Goal

Measure what the project actually buys relative to existing workflows.

Two task-preservation diagnostics deferred here from the Week 8 literature pass:

- **tOF** — optical flow estimated on the corrected output versus on the input.
  Asks whether restoration perturbs estimated correspondence. SEA-RAFT is already
  wired in, so the cost is inference only.
- **tLP** — consecutive-frame perceptual change in the output versus in the
  input. Usable without ground truth via TecoGAN's input-as-reference variant.
  Introduces LPIPS, so treat it as a secondary perceptual check, not a physical
  measure.

Neither is a temporal-stability metric; both ask whether the restoration damages
downstream usability.

Compare against:

- unprocessed input,
- gray-world,
- white-patch,
- CLAHE combinations,
- DaVinci Resolve manual/chart control,
- Dive+,
- AquaColorFix,
- plain Sea-thru or faithful implementation where practical,
- current full pipeline.

Use still and video cases.

---

## Benchmark dimensions

### Controlled color

- chart ΔE00.

### Temporal

- MC-Warp@1/4/8,
- temporal ΔE00,
- valid coverage.

### Signal/range behavior

- clipping,
- extreme gain,
- near/far consistency.

### Spatial quality

Visual inspection for:

- detail,
- noise,
- halos,
- artifacts,
- unnatural saturation.

### Human preference

Use blinded human comparison where feasible.

Keep:
```text
physical/color fidelity
```

separate from:
```text
aesthetic preference
```

A visually punchier grade is not automatically a more accurate restoration.

---

## Gate

Produce a measured answer to:

- where does the pipeline win?
- where does it tie?
- where does it lose?
- why?
- which improvement comes from which stage?
- what failures remain?

The result should survive removal of any one flattering example.

---

# Week 10+ — Learned residual

## Entry condition

Do not begin this phase because neural networks are interesting.

Begin only if Week 7/9 identifies repeatable errors that:

- matter perceptually or physically,
- survive improvements to the physics model,
- have a plausible learnable structure,
- have adequate training/evaluation data.

---

## Role

The learned model corrects **residual failures of the physics pipeline**.

It does not replace the physical model by default.

Potential targets:

- residual color bias,
- localized model mismatch,
- difficult lighting,
- texture-aware corrections,
- known depth/model failure patterns.

---

## Training sources

Use multiple sources where possible:

### Controlled real data

- Keldan/chart-referenced underwater footage,
- varied distance/depth/filter/light configurations.

### Synthetic degradation

Generate underwater degradation from clean RGB-D imagery using varied:

- attenuation,
- backscatter,
- noise,
- illumination,
- depth.

### Real paired datasets

Use only when acquisition/ground-truth assumptions are understood.

Do not train solely on:
```text
physics pipeline output -> manually preferred target
```

because the residual model may simply learn and entrench the physics pipeline's systematic mistakes.

---

## Constraints

Prefer a small residual model.

Physics output remains an explicit input/baseline.

Require ablation:
```text
physics only
physics + learned residual
```

Evaluate on held-out real controlled footage.

Do not trust training loss alone.

---

## Gate

The learned residual survives only if it improves:

- fidelity,
- relevant objective metrics,
- actual Week 7 failure cases,
- temporal behavior,

without introducing:

- hallucinated content,
- scene-identity changes,
- unstable detail,
- aesthetic bias masquerading as restoration.

Otherwise reject it.

---

# Architecture decision points

Stop and evaluate before adding complexity.

## Physics vs. learned

Is the physics model still producing measurable gains?

If yes:

> continue improving the physical model.

If no:

> investigate model assumptions, acquisition limits, geometry, and implementation before reaching for a learned component.

---

## Depth value

Does improved depth materially improve final restoration?

Measure this directly.

Do not optimize metric depth accuracy indefinitely if restoration is insensitive to the remaining error.

Conversely, if depth errors dominate distant-color reconstruction, geometry deserves more investment.

---

## Refractive modeling value

Does a refractive camera model materially improve:

- recovered range,
- consistency,
- final restoration?

If yes, keep it.

If ordinary SfM produces equivalent restoration despite imperfect geometry, do not maintain expensive geometric sophistication solely for theoretical purity.

---

## Temporal sophistication

Does a more complicated temporal method improve long-duration stability beyond physical-parameter stabilization?

Test this first on approximately 30-second continuous footage.

The frozen Phase 2B pairwise metric stack is intentionally **not** assumed to detect every possible periodic or slow instability.

In particular, fixed-lag metrics can alias periodic behavior when the evaluated frames land on the same phase of an oscillation.

However:

> a mathematical blind spot alone does not justify adding another metric.

First determine whether long-duration validation demonstrates a visible or parameter-level instability that:

- MC-Warp@1/@4/@8,
- temporal ΔE00,
- the alignment-robust companion,
- parameter-trace inspection,

fail to expose adequately.

If no demonstrated blind spot exists:

> add nothing.

If a demonstrated blind spot exists, consider at most one additional long-window trajectory/frequency diagnostic.

Prefer detecting oscillation directly in estimated physical parameters before adding another output-image metric.

Likewise, investigate more sophisticated temporal **correction** only if physical-parameter stabilization leaves a visible measured defect.

If not, reject it.

Do not add:

- recurrent/video models,
- extra lag banks,
- spectral machinery,
- output smoothing,
- temporal metric complexity,

merely because such methods exist in the literature.

Complexity must answer a measured failure.

---

## Optical-flow backend

Do not chase new optical-flow SOTA continuously.

Revisit backend selection only if the chosen backend causes a **specific observed evaluation failure**, for example:

- unacceptable valid-coverage loss,
- failure on smooth moving subjects,
- high-resolution correspondence becoming necessary.

---

## Learned residual value

Keep a learned component only if it improves:

- visual fidelity,
- objective evidence,
- targeted failure cases,

without harming physical plausibility or temporal consistency.

---

# Acquisition experiments

When new dive opportunities occur, prioritize controlled data that answers project questions.

With the underwater color chart, capture combinations of:

- multiple camera-to-chart distances,
- multiple depths,
- red filter / no filter,
- fixed WB settings,
- ambient only,
- dive lights where appropriate,
- static shots,
- controlled slow swim-throughs.

Record metadata including:

- camera,
- profile,
- resolution/frame rate,
- WB,
- filter,
- approximate depth,
- approximate camera-target range,
- lighting configuration.

Do not delay current algorithm development waiting for perfect new footage; existing real clips remain valuable stress tests.

---

# Non-goals for now

- No generative image replacement.
- No invented scene content.
- No “make it cinematic” enhancement mode during restoration development.
- No arbitrary saturation/vibrance boost disguised as recovery.
- No chasing every new SOTA model.
- No native RAW decoder unless it becomes necessary.
- No giant ML training infrastructure before a failure mode demands it.
- No generic pipeline/plugin framework beyond what current stages require.
- No per-experiment directory bureaucracy until reproducible ML experiments make it useful.
- No optimizing benchmarks while ignoring visible failure.
- No hiding poor correspondence through aggressive masks.
- No hiding instability through blur.
- No claiming recovery of information known to be clipped or below usable signal.

---

# Project completion criterion

The project succeeds when it can take difficult real underwater footage and produce a result that is demonstrably better than simple/global correction approaches because it models the underlying scene degradation.

Success means evidence across several axes:

- more plausible / accurate color,
- simultaneous correction across different ranges,
- reduced backscatter,
- preserved spatial detail,
- stable video,
- explicit handling of uncertainty/unrecoverable regions,
- measurable advantage over strong existing workflows,
- understandable failure modes.

The project earns complexity through measured improvement, not by default.