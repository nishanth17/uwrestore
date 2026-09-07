You are executing Week 4A of the `uwrestore` project.

This is an **IMPLEMENTATION + EXPERIMENT EXECUTION task**, not a literature review.

The authoritative experimental specification is:

`experiments/week4_mono/MONO_DEPTH_FREEZE.md`

If any other Week-4 document conflicts with it:

> `MONO_DEPTH_FREEZE.md` WINS.

Read the relevant project `PLAN.md`, `CLAUDE.md`, and `LOG.md` before making changes.

---

# OBJECTIVE

Execute the frozen Week-4A monocular-depth bakeoff autonomously:

```text
S0 semantics/runtime
→ S1 determinism
→ S2 ambiguity
→ S3 local geometry
→ reduce field
→ S4 appearance invariance
→ S5 temporal stability
→ reduce to 2–3 finalists
→ S6 restoration impact
```

Sequential experimental gates MUST remain sequential.

Do not trade scientific correctness for autonomy.

---

# FROZEN VIDEO / FRAME SET

## Primary Week-4A bakeoff set

The **primary Week-4A model bakeoff MUST use the same six Week-3 development clips and the same persisted Week-3 frame extraction/reference products**.

Do NOT select new primary videos.

Do NOT substitute Week-2 stress clips for these six.

Do NOT expand the S3 benchmark merely because more footage exists.

The frozen six clips are:

```text
wreck_07
    high-texture arc
    favorable/high-support geometry case

wreck_05
    lower-texture lateral glide
    stresses weaker feature/geometry support

cenote_01
    widest near/far range variation
    important for range-dependent distortion

swimthrough_02
    ordinary reef / representative normal case

wreck_01
    low-texture, near-planar, portrait-orientation case
    important for preprocessing/FOV/orientation failure

wreck_03
    dynamic diver
    important for moving-object and dynamic-scene failure
```

Each clip uses the existing Week-3 extraction:

```text
48 frames per clip
1280-pixel long-side common extraction
```

Therefore the primary matched bakeoff contains:

```text
6 clips × 48 frames = 288 frames per model
```

Reuse the **existing persisted Week-3 range products for exactly these frames**.

Do NOT regenerate a different frame sample unless the persisted material is actually missing or corrupt.

The reason for freezing these clips is scientific comparability:

> Week 4 is testing monocular depth against the exact footage whose multi-view behavior and uncertainty were already characterized in Week 3.

The Week-3 product remains a **provisional reference / multi-view hypothesis**, not ground truth.

---

# HOW EACH STAGE USES THE FROZEN FOOTAGE

## S0 — semantics/runtime

Do NOT run all 288 frames.

Use only a minimal sanity set:

```text
1 ordinary project underwater frame
1 difficult project underwater frame
1 public/reference image with independently documented semantics
1 portrait/orientation-sensitive project frame
```

Prefer the project frames to come from the frozen six clips.

`wreck_01` should supply or strongly inform the portrait/orientation case because preprocessing already caused substantial FOV loss in the VGGT family during Week 3.

S0 is wrapper validation, not benchmarking.

---

## S1 — determinism/runtime

Use a small representative subset of the frozen Week-3 material.

The purpose is to establish:

```text
repeatability
noise floor
runtime
memory
device/backend
```

Do not burn compute running the full 288-frame benchmark merely to measure determinism.

---

## S2 — ambiguity measurement

Use the **six frozen Week-3 clips**.

This stage needs the sequence structure because it measures:

```text
scale / shift magnitude
clip-to-clip variation
frame-to-frame trajectories
practical ambiguity behavior
```

Inference remains strict one-image-at-a-time.

No neighbouring frame may enter the model.

The sequence is used only for evaluation after independent inference.

---

## S3 — PRIMARY LOCAL-GEOMETRY BAKEOFF

This is the main model comparison.

Run the **full frozen set**:

```text
wreck_07        48 frames
wreck_05        48 frames
cenote_01       48 frames
swimthrough_02  48 frames
wreck_01        48 frames
wreck_03        48 frames

TOTAL           288 frames/model
```

Use the corresponding persisted Week-3 range/reference products.

This is the primary basis for reducing the seven mandatory entrants to approximately 3–4 survivors.

Do NOT add unrelated footage to the primary S3 ranking.

If a clip/frame cannot be evaluated for a specific documented reason, record that explicitly rather than silently changing the benchmark set.

---

## S4 — appearance invariance

Start from the same frozen Week-3 frames.

Generate geometry-preserving appearance perturbations from those frames:

```text
white-balance changes
channel neutralization / color cast
contrast
brightness
attenuation/haze-like changes
artificial-light/hotspot appearance
cue-conflict conditions
other perturbations already frozen in MONO_DEPTH_FREEZE.md
```

The point is:

```text
same underlying image geometry
different appearance
→ measure geometry response
```

Do not acquire or choose a new primary dataset for S4.

Atlantis++ may be used only as a SECONDARY external synthetic appearance-control dataset if its exact matched-geometry structure is verified.

It never replaces the frozen six clips.

---

## S5 — independent-frame temporal stability

Use the **same six Week-3 clips as sequences**.

Every frame must still be inferred independently:

```text
ONE frame in
ONE prediction out
NO neighbouring images
NO temporal state
NO Week-3 geometry input
```

Sequence information is used only after inference to evaluate:

```text
scale trajectory
shift trajectory
near/far trajectory
boundary jitter
local geometry stability
validity / confidence stability
```

`wreck_03` is especially important because it contains the dynamic diver.

Do not omit it merely because static-reference interpretation is harder.

Respect the frozen epistemic partition:

```text
static anchored / higher-confidence regions
static reference-uncertain regions
dynamic-object regions
```

Dynamic-object agreement with Week-3 is not ground truth.

---

## S6 — restoration impact

Run only the surviving 2–3 finalists.

Use the same frozen six clips so that:

```text
Week-3 multi-view range
vs
monocular finalist range
```

is an apples-to-apples comparison on identical frames.

Run the existing restoration and frozen Week-2 temporal evaluation machinery as specified.

---

# WEEK-2 STRESS FOOTAGE — SECONDARY ONLY

The project also has older Week-2 frozen stress footage covering cases such as:

```text
murk
particulates / marine snow
moving animal
artificial lights
strong motion
distance variation
signal-starved / clipped channels
severe color cast
```

These clips are **NOT part of the primary S3 model ranking by default**.

Use them only as a secondary stress extension in S4/S5/S6 when:

- the frozen six clips do not adequately expose a specific already-defined failure mode; or
- a surviving model needs stress characterization for a frozen criterion.

If Week-2 stress footage is used:

1. keep its results separate from the primary six-clip S3 ranking;
2. label it `secondary_stress`;
3. do not change candidate ranking solely because one model saw a different footage set;
4. document exactly why each added clip was activated.

Do NOT turn the existence of more footage into an open-ended benchmark expansion.

---

# CANDIDATE SET

The mandatory set is frozen:

```text
1  facebook/map-anything-apache                 N=1
2  depth-anything/Depth-Anything-V2-Small
3  lsxi77777/Wat3R                              N=1
4  Ruicheng/moge-2-vitl
5  yjh001/metricanything_student_pointmap
6  depth-anything/DA3MONO-LARGE
7  mxliu-hku/FoundationGeo-1.1
```

Do NOT add another model.

Do NOT activate conditional challengers unless their exact measured trigger in `MONO_DEPTH_FREEZE.md` fires.

---

# BASELINE SAFETY

Before Week-4 implementation:

1. Run:

```text
uw score
```

2. Compare with the expected baseline in `LOG.md`.

Unexpected baseline change:

> STOP and diagnose before running Week 4.

If stable, append a Week-4A execution-start entry to `LOG.md`.

---

# IMPLEMENTATION PRINCIPLE

Build the smallest common monocular inference/evaluation harness necessary.

Preserve native representations.

At minimum retain:

```text
model
checkpoint
native_representation
native_output
canonical_range
valid_mask
confidence optional
preprocessing metadata
input/output dimensions
device/backend
precision
runtime
memory if available
semantic notes
```

Do not prematurely reduce everything to generic “depth”.

Model-specific diagnostics remain accessible, especially FoundationGeo intermediates.

---

# INTEGRATION ORDER

Unless a hard dependency requires otherwise:

```text
1. MapAnything N=1
2. Depth Anything V2 Small
3. MoGe-2 ViT-L
4. MetricAnything Student-PointMap
5. Wat3R N=1
6. DA3MONO-LARGE
7. FoundationGeo-1.1
```

This order minimizes integration risk and does NOT imply model ranking.

---

# S0 — SEMANTICS + RUNTIME GATE

For every model establish empirically:

```text
MPS works
CPU works
CUDA required
reference implementation modifications required
```

Verify:

- strict N=1;
- exact native representation;
- coordinate system;
- range conversion;
- masks;
- preprocessing;
- crop/resize/letterbox;
- orientation;
- FOV retention;
- input/output pixel correspondence;
- no hidden temporal/multi-view state;
- units where claimed.

Known traps:

```text
MapAnything
    canonical range = depth_along_ray = ||pts3d_cam||

DA V2
    preserve disparity
    do not align blindly in physical depth

MoGe-2
    canonical range = ||points||
    known-FOV experiment is POSTPROCESSING/CALIBRATION, not neural conditioning

MetricAnything
    tensor-level checkpoint diff against stock MoGe-2

Wat3R
    strict N=1
    do not infer native ambiguity merely from eval alignment code

DA3 Mono
    preserve native relative depth
    literature ambiguity = affine-in-depth / Class 3

FoundationGeo
    canonical range = ||point||
    depth_metric is z-depth, NOT range
    preserve raw pre/post-ray geometry and scalefield
```

FoundationGeo causal ablations:

```text
ray correction:
    compare raw pre-delta vs raw post-delta geometry
    BEFORE independent focal/shift recovery
    OR apply one common frozen postprocessing solution

scale field:
    common points_rel
    vs
    points_rel * scalefield
```

If one model fails semantics:

- one bounded repair attempt;
- never invent semantics;
- record failure;
- drop/block only that model when scientifically valid;
- continue others.

---

# S1 — DETERMINISM + NOISE FLOOR

Run identical inference repeatedly.

Record:

```text
device
precision
runtime
peak memory where available
bitwise reproducibility
maximum output delta
median output delta
stochasticity source
```

No downstream delta smaller than the measured numerical/noise floor may be interpreted as signal.

---

# S2 — NATIVE AMBIGUITY

Freeze a common **alignment policy**, not one universal transform.

For each model record:

```text
native representation
documented native ambiguity/gauge
E1 diagnostic alignment family
fit scope
raw output
simpler subgroup tested
```

Examples:

```text
DA3 Mono:
    d_ref ≈ s*d_pred
    vs
    d_ref ≈ s*d_pred + t

DA V2:
    fit affine transform in disparity, then invert

relative point maps:
    use documented point-map gauge

metric models:
    retain raw metric output
    oracle E1 alignment is diagnostic only
```

Persist the final policy machine-readably.

All downstream stages use the frozen policy.

---

# S3 — LOCAL GEOMETRY

Run the full 288-frame frozen six-clip benchmark.

Universal metrics:

```text
M-1 range-stratified relative range error
M-2 near/far systematic distortion
M-3 RelNormal + local normal error
M-4 boundary localization
M-5 ordinal violations
M-6 radial image-position error
```

AbsRel / delta metrics are secondary only.

No weighted master score.

Pre-C2 M-1 must include:

```text
provisional Week-3 nominal/reference range bins
AND
scale-invariant near/mid/far quantiles
```

Do not interpret nominal metres as independently verified physical metres before C2.

Reduce approximately:

```text
7 → 3–4
```

using explicit multi-dimensional reasons.

---

# S4 — APPEARANCE INVARIANCE

Run only S3 survivors.

Use the frozen Week-3 images as the base geometry.

Decompose changes into:

```text
constant global scale bias
frame-varying global scale drift
local range deformation
```

Only the first may be treated as a benign gauge.

---

# S5 — TEMPORAL STABILITY

Run S4 survivors over the six frozen clips as sequences, with independent per-frame model inference.

Report:

```text
s_t
shift_t where legal
near/far trajectories
local-surface stability
boundary jitter
coverage
confidence trajectory if available
```

Frame-varying scale is not benign under shared clip-level physical coefficients.

Reduce to 2–3 finalists.

---

# S6 — RESTORATION IMPACT

Run only finalists on the same six clips.

Compare:

```text
Week-3 multi-view range
vs
each monocular finalist
```

Run the project's frozen restoration and Week-2 temporal evaluation machinery.

Mandatory inspection includes:

```text
marine snow
backscatter
caustics
moving animals
artificial lights
thin structures
far-field behavior
color pumping
particulate texture turned into geometry
```

Produce provisional:

```text
ADEQUATE
DEGRADED
UNSAFE
```

relative to the current Week-3 hypothesis.

No objective final winner before C2.

---

# OUTPUT ORGANIZATION

Persist:

```text
experiments/week4_mono/round1/results/
    S0_SEMANTICS_RUNTIME.md
    S0_results.json

    S1_DETERMINISM.md
    S1_results.json

    S2_AMBIGUITY.md
    S2_alignment_policy.json

    S3_LOCAL_GEOMETRY.md
    S3_results.json

    S4_APPEARANCE.md
    S4_results.json

    S5_TEMPORAL.md
    S5_results.json

    S6_RESTORATION.md
    S6_results.json

    FINALISTS_PRE_C2.md
```

After each stage:

1. persist results;
2. append concise findings to `LOG.md`;
3. record exact commands/checkpoints/config;
4. continue automatically if the gate is satisfied.

Do not keep giant raw outputs only in conversational context.

---

# AUTONOMY

Proceed without asking me for routine confirmation.

STOP only for:

```text
1. unexpected frozen-baseline change
2. required semantics cannot be resolved without guessing
3. strict single-image invariant would be violated
4. mandatory remaining model is impossible on available compute
5. frozen protocol contains a newly discovered correctness defect
```

A failure of one model alone does not stop the whole bakeoff when the remaining experiment remains scientifically valid.

---

# FINAL DELIVERABLE

Return a concise final summary with:

```text
S0 survivors
S1 determinism findings
S2 frozen ambiguity policy
S3 geometry findings by dimension
S4 appearance failures
S5 temporal failures
2–3 pre-C2 finalists
S6 restoration classification
every eliminated model + reason
unresolved pre-C2 questions
C2 measurements required next
```

No weighted master score.

No broad literature sweep.

No objective final winner before C2.

The goal is to determine whether strict monocular depth is adequate for the underwater-restoration fallback path, using the **same six Week-3 clips and 288 matched frames** as the primary bakeoff.