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

# Week 3 — Multi-view depth / range from video

## Goal

Determine whether video geometry can provide sufficiently stable **range information** for spatially varying underwater restoration.

Absolute metric depth is useful, but not automatically the primary objective.

---

## Controlled reconstruction clip

Use a scene chosen for geometry rather than aesthetics:

- static,
- feature-rich,
- rigid coral/wreck/rock,
- minimal swaying vegetation,
- limited particulate,
- limited moving animals,
- preferably below strong moving caustics or under diffuse illumination.

A failed gate should diagnose:

- bad scene choice,
- camera model failure,
- insufficient parallax,
- feature matching failure,

rather than lump everything together as “SfM doesn't work.”

---

## Ordinary SfM baseline

Run ordinary COLMAP/pinhole-style reconstruction as a baseline.

Measure:

- reconstruction completeness,
- reprojection error,
- camera trajectory stability,
- relative depth ordering,
- repeated reconstruction consistency.

Do not assume its recovered geometry is physically correct underwater.

---

## Refractive geometry

Flat-port underwater imaging is not merely an air camera with focal length multiplied by `1.333`.

Refraction through:

- housing port,
- glass/acrylic,
- water,

can violate the ordinary central/pinhole camera model and introduce systematic geometry error.

Treat refractive geometry as a first-class design question.

Evaluate, where feasible:

- underwater calibration,
- known housing/port geometry,
- a refractive camera model / refractive SfM approach,
- Refractive COLMAP or equivalent.

Compare refractive and ordinary reconstruction on a controlled clip rather than assuming a theoretical correction is sufficient.

---

## Scale anchoring

Known-size objects or the Keldan/chart setup may provide global scale evidence.

However:

> A global scale anchor corrects global scale ambiguity; it does not automatically repair spatially varying refractive shape distortion.

Separate:

- global scale error,
- relative range-ordering error,
- spatially varying geometric distortion.

---

## Restoration-relevance test

The real question is not:

> “Did we reconstruct perfect metric 3D?”

It is:

> “Is recovered range sufficiently stable and accurate to improve range-dependent restoration?”

If attenuation parameters are jointly fitted, some uniform scale ambiguity may be absorbed by those coefficients.

Nonuniform/range-dependent geometry error is more dangerous.

Test restoration sensitivity to controlled perturbations in recovered range.

---

## Gate

Proceed when:

- relative depth/range ordering is stable,
- camera trajectory is plausible,
- failure regions are identified,
- ordinary vs refractive modeling difference is measured or explicitly deferred with evidence,
- known-scale evidence is used where possible,
- range uncertainty is documented,
- depth is demonstrably usable by the restoration model.

If refractive error dominates, address it before treating COLMAP range as ground truth.

---

# Week 4 — Monocular depth for stills and fallback video frames

## Goal

Determine whether a single-image depth estimator is accurate enough to substitute for multi-view range when video geometry is unavailable.

Do not select a model solely from generic depth benchmarks.

Evaluate on frames for which Week 3 provides the best available multi-view reference.

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