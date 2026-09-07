# Week-4A monocular depth — FROZEN REPAIR PASS

**Frozen 2026-09-06.**

Supersedes `MONO_DEPTH_DELTA.md` and all earlier Week-4A monocular-depth candidate recommendations wherever they conflict.

> **Candidate discovery is closed. Changes after this point require either measured S0–S6 evidence or a newly discovered correctness defect. No further broad literature search is warranted before S0.**

**Net result:** mandatory checkpoints reduced **9 → 7**. Three incorrect claims retracted. Several model comparisons downgraded from causal to model-vs-model. FoundationGeo's two-checkpoint comparison replaced by a stronger same-checkpoint internal ablation. Local-geometry metrics reduced **9 → 6 universal metrics**. Pre-C2 physical-meter interpretation explicitly remains provisional until C2 anchors scale.

---

# 1. Corrections incorporated

## C1 — DA3 Mono ambiguity is Class 3 from literature

Primary-source language from DA3:

> “Unlike DA2, which predicts scale–shift-invariant disparity, our teacher outputs scale–shift-invariant depth.”

The monocular student is trained from those relative-depth targets.

Therefore:

```text
DA3MONO-LARGE
literature ambiguity = affine-in-depth / Class 3
```

It is **not** established as scale-only / Class 2.

The shipped `least_squares_scale_scalar` utility does not change this conclusion. That utility participates in metric/nested-model alignment and is not evidence about the native ambiguity of `DA3MONO-LARGE`.

DA3 Mono remains in the mandatory set because it predicts **depth rather than inverse depth/disparity**, which is materially relevant to a range-driven physical model.

S2 may empirically discover that its additive shift is negligible on this domain. If so, the project may describe the released checkpoint as behaving **approximately scale-only on the tested domain**. That conclusion must be earned from data, not inferred from architecture or utility code.

---

## C2 — DA3 Mono → DA3 Metric is not a controlled global-scale experiment

`DA3MONO-LARGE` and `DA3METRIC-LARGE` share architecture, but the metric model is separately trained using metric supervision and canonical-camera treatment.

The conversion:

```text
metric_depth = depth * focal_length / 300
```

is indeed a global per-image multiplicative factor applied within the metric model's output path.

It does **not** transform the Mono checkpoint into the Metric checkpoint.

Therefore:

```text
DA3 Mono vs DA3 Metric
= model-vs-model comparison
NOT
= isolated global-factor intervention
```

The former variable `V4a global metric factor` is deleted.

`DA3METRIC-LARGE` is moved from mandatory to optional. Pre-C2, its principal advantage—raw metric behavior—cannot be judged objectively against an unanchored reference, and the broader “metric fine-tuning of a fixed architecture” question is already addressed more cleanly by MoGe-2 → MetricAnything.

---

## C3 — FoundationGeo uses one checkpoint and an internal ablation

`FoundationGeo-Base-1.1 → FoundationGeo-1.1` is not a controlled Stage-I→Stage-II experiment because Stage-II training leaves the relative branch unfrozen.

The mandatory experiment therefore uses **`FoundationGeo-1.1` only**.

The model exposes three conceptually distinct products:

```text
raw relative geometry before learned ray correction
        ↓
relative geometry after learned ray correction
        ↓
postprocessed relative geometry × learned per-pixel scale field
```

However, there is an important implementation distinction.

### Ray-correction ablation

The truly causal comparison must be made at the **raw forward-product level**, before the two products are independently passed through focal/shift recovery.

Do **not** compare the separately postprocessed `points_pre_field` and `points` and call the difference “ray correction only,” because separate postprocessing can recover different focal/shift parameters.

For the ray-correction intervention:

```text
SAME image
SAME checkpoint
SAME weights
SAME forward pass

raw points before delta
    vs
raw points after delta
```

or apply one frozen/common postprocessing solution to both.

This identifies the learned ray-direction correction.

### Spatial-scale-field ablation

After one common relative geometry has been established:

```text
points_rel
    →
points_metric = points_rel * scalefield
```

is a clean same-tensor intervention and identifies the learned per-pixel metric scale field.

Also freeze two wrapper traps:

```text
depth_metric = points_metric[..., 2]
```

is **z-depth**, not ray range.

The project's canonical range must be recomputed as:

```text
range = ||points_metric||
```

And `points_pre_field` is a misleading release name: it originates from geometry before the learned ray correction, not merely before the scale field.

`FoundationGeo-Base-1.1` is removed from the mandatory set.

---

## C4 — Cai & Metzler evaluation remains underspecified

The previous argument that `AbsRel > 1` proves the absence of per-image median alignment is mathematically invalid.

Median alignment constrains a median ratio, not the mean of an unbounded relative-error distribution.

The available paper statement:

> “All predictions are rescaled to match the dataset-specific depth units.”

does not establish whether this means:

- pure unit conversion;
- one dataset-global constant;
- or some other scaling operation.

The unreleased evaluation code prevents a stronger conclusion.

Freeze the classification as:

```text
Cai & Metzler evaluation:
METRIC-ORIENTED
SCALING / ALIGNMENT PROTOCOL UNDERSPECIFIED

Not a clean E1 structural comparison.
Not proven pure E3.
```

No mandatory-model decision depends on treating that benchmark as pure E3.

UniDepth V2 remains optional because its native radial range is not unique within the candidate set and no independently verified aligned-shape underwater result justifies a mandatory slot.

---

## C5 — MetricAnything remains, but the treatment is heterogeneous metric fine-tuning

`metricanything_student_pointmap` is documented as fine-tuned from `MoGe-2 ViT-L`.

Therefore:

```text
MoGe-2 ViT-L
    →
MetricAnything Student-PointMap
```

holds architecture, backbone family and point-map representation substantially fixed.

What changes together includes:

- training data;
- metric supervision;
- camera diversity;
- objectives;
- dataset composition;
- fine-tuning recipe.

The experiment therefore identifies:

```text
V5 — HETEROGENEOUS METRIC FINE-TUNING
```

not camera diversity specifically.

Any improvement may be consistent with camera-diverse training helping, but this comparison cannot attribute the improvement uniquely to that component.

Hugging Face download counts for the bare `.pt` release are treated as **untracked**, not evidence of zero adoption.

The S0 tensor-difference check against stock MoGe-2 remains mandatory because of the project's prior Water-VGGT checkpoint-integrity finding, not because of download statistics.

---

## C6 — Depth Anything V2 Large is optional

Wat3R's published `DAv2` row does not identify the exact Depth Anything V2 size, and its released evaluation code does not provide the baseline loader needed to recover the variant.

Therefore:

```text
Depth-Anything-V2-Small
```

is the mandatory inverse-depth/disparity control.

`Depth-Anything-V2-Large` is optional and is activated only if Small's result makes capacity scientifically relevant.

---

## C7 — Constant scale bias and temporal scale drift are different

Freeze this terminology throughout Week 4:

```text
CONSTANT GLOBAL SCALE BIAS

d' = s d
with s fixed for the clip

BENIGN GAUGE when the corresponding physical coefficients are refit:
beta' = beta / s.

Week 3 verified this numerically to floating-point precision.


FRAME-VARYING GLOBAL SCALE DRIFT

d'_t = s_t d_t
with s_t changing over time

NOT BENIGN under one shared clip-level physical model.

Absorption would require:
beta'_t = beta / s_t

which makes inferred water properties vary with the monocular estimator.


LOCAL RANGE DEFORMATION

Spatially varying within the image.

NOT absorbable by a shared global physical parameter transformation.

Primary geometric failure mode.
```

Therefore S5 must report the **scale trajectory**, not just average scale.

---

## C8 — SurGe/NATTEN/runtime claims are bounded

SurGe remains a conditional local-surface challenger.

Its contributions retained unconditionally are:

- recognition that local surface geometry is poorly measured by conventional metrics;
- `MAE_normal`;
- point-gradient/local-surface reasoning.

NATTEN has prebuilt wheels through its own distribution channel for supported Linux configurations. The earlier blanket statement “no wheels exist” is withdrawn.

None of that establishes SurGe MPS compatibility.

More generally, no candidate's local runtime is inferred from literature alone.

S0 records one of:

```text
MPS works
CPU works
CUDA required
reference implementation modifications required
```

from actual project execution.

---

## C9 — RelNormal improves local-shape sensitivity; it does not restore aligned-away information

RelNormal remains mandatory.

Its role is:

> expose curvature/local-surface differences that conventional aligned scalar-depth metrics can miss.

It does **not** turn E1 into a deployability test and is not described as universally invariant to every alignment group.

Freeze the interpretation:

```text
E1 + local-geometry metrics
    If the model's documented legal ambiguity were known,
    how good is the remaining shape?

ambiguity parameters
    What transform had to be removed to obtain that ceiling?

E2 frozen calibration
    Can that transform actually be calibrated once and held fixed?

raw / pre-alignment geometry
    What physical error exists without oracle help?

restoration impact
    Does the deployable range field preserve the downstream physics?
```

RelNormal is computed **after the chosen legal E1 alignment** and measures relative local surface orientation/curvature in that aligned geometry.

---

# 2. Corrected experimental-variable map

## Strictly controlled interventions

### V1 — View count

```text
MapAnything N>1
        →
MapAnything N=1
```

Same checkpoint, representation and wrapper.

The intervention is the number of input views.

This is the cleanest measurement of the literal Week-4 question.

### V4b — FoundationGeo learned ray correction

Use the raw forward-pass geometries:

```text
raw geometry before ray-direction delta
        →
raw geometry after ray-direction delta
```

Same image, weights and forward pass.

Do not introduce independent focal/shift recovery between the two arms.

### V4c — FoundationGeo per-pixel scale field

```text
common post-ray relative geometry
        →
common post-ray relative geometry × scalefield
```

Same geometry and weights.

The intervention is the learned spatial multiplicative field.

### V9 — Known-FOV postprocessing / camera-calibration ablation

Rename the former “intrinsics conditioning” experiment.

For MoGe-2:

```text
same raw model prediction
    +
model-inferred focal/FOV postprocessing
        vs
same raw prediction
    +
supplied measured FOV postprocessing
```

The network itself is not being conditioned on the FOV.

This tests whether supplying known camera calibration to the **postprocessing geometry recovery** materially improves the result.

---

## Partially controlled intervention

### V5 — Heterogeneous metric fine-tuning

```text
MoGe-2 ViT-L
        →
MetricAnything Student-PointMap
```

Architecture and representation are substantially controlled.

Training data, objectives, supervision and camera diversity change together.

The comparison may show that the **fine-tuning treatment** helps; it cannot uniquely establish which component caused the improvement.

---

## Model-vs-model instruments, not causal experiments

```text
DA3 Mono vs DA V2
    representation + architecture + training all change

Wat3R vs terrestrial models
    underwater training + architecture + training regime all change

MoGe-2 vs DA3 Mono
    point-map vs scalar depth is only one of many differences

DA3 Mono vs DA3 Metric
    separate training treatments; optional only

FoundationGeo Base vs FoundationGeo Stage-II
    relative branch also retrained; optional only
```

These comparisons remain useful scientifically but must not be described as isolating a single causal variable.

---

# 3. FROZEN mandatory Week-4A set — 7 checkpoints

## 1. `facebook/map-anything-apache` — N=1

```text
ROLE
    Control: Week-3 incumbent with multi-view information removed.

QUESTION
    What is the cost of reducing the already-selected Week-3 model from N>1 to N=1?

VARIABLE
    V1 view count — controlled.

OUTPUT
    unit ray directions × depth_along_ray → pts3d_cam

CANONICAL RANGE
    ||pts3d_cam|| == depth_along_ray by construction.

AMBIGUITY
    Claims metric.
    N=1 absolute scale is treated as provisional pre-C2.

LICENCE
    Apache-2.0 code / Apache-2.0 weights.

RUNTIME
    VERIFIED by project: MPS, deterministic in Week 3.
```

---

## 2. `depth-anything/Depth-Anything-V2-Small`

```text
ROLE
    Cheap inverse-depth/disparity control.

QUESTION
    How damaging is affine disparity ambiguity over the project's working range?

OUTPUT
    Relative inverse depth / disparity.

LEGAL REPRESENTATION
    Affine ambiguity must be fitted in disparity space:
        q' = a q + b
    then converted to range/depth.

    Do NOT universally fit a*d+b in physical depth.

LICENCE
    Apache-2.0 / Apache-2.0.

RUNTIME
    UNVERIFIED in this project; first-party MPS support is documented.
    S0 decides.
```

The published Wat3R table provides useful context that DAv2 is highly competitive on its zero-shot underwater columns, but the exact variant used there is unrecoverable and is not a reproduction target.

---

## 3. `lsxi77777/Wat3R` — N=1

```text
ROLE
    Sole underwater-specialization control.

QUESTION
    Does an explicitly underwater-trained modern geometry model help on water
    regimes outside its training distribution, or does specialization increase fragility?

INPUT
    Strict N=1 path verified in the release.

TRAINING CAVEAT
    The model was not trained with single-image supervision.
    FLSea occurs in its training pool, although evaluation scenes are held out.

AMBIGUITY
    Do NOT infer native ambiguity solely from the released evaluation alignment.
    S0/S2 establish model semantics and the appropriate project alignment policy.

LICENCE
    Apache-2.0 / Apache-2.0.

RUNTIME
    VERIFIED by this project for the Wat3R/VGGT-family Week-3 path on MPS.
    N=1 path reconfirmed in S0.
```

Important interpretation:

Wat3R's published monocular and multi-view Sea-thru numbers are **not directly comparable**.

They differ in at least:

- inference view count / operating mode;
- alignment scope;
- potentially sampling/evaluation scope.

Therefore the published `0.090 vs 0.167` gap is **not** attributed to alignment alone and is **not** interpreted as a view-count effect.

Its only protocol lesson for this project is that Week 4 must impose one internally consistent evaluation policy.

---

## 4. `Ruicheng/moge-2-vitl`

```text
ROLE
    Strong monocular metric point-map baseline.

QUESTION
    How good is a modern monocular point-map representation on this underwater domain?

OUTPUT
    Point map in camera coordinates.

CANONICAL RANGE
    ||points||

AMBIGUITY
    Claims metric.
    Raw metric output is preserved separately.
    Oracle alignment is an E1 diagnostic, not a deployment entitlement.

LICENCE
    MIT / MIT.

RUNTIME
    UNVERIFIED in this project. S0 decides.
```

Also hosts the free **V9 known-FOV postprocessing ablation**.

---

## 5. `yjh001/metricanything_student_pointmap`

```text
ROLE
    Fine-tuned treatment arm against MoGe-2.

QUESTION
    Does heterogeneous metric fine-tuning materially improve the fixed MoGe-2
    architecture/representation on this OOD underwater problem?

VARIABLE
    V5 heterogeneous metric fine-tuning.

WHAT IS CONTROLLED
    Starting architecture / representation / backbone family.

WHAT REMAINS CONFOUNDED
    data volume
    dataset composition
    camera diversity
    supervision
    objective
    fine-tuning recipe

OUTPUT
    Metric point map.

CANONICAL RANGE
    ||points||

LICENCE
    Apache-2.0 / Apache-2.0.

RUNTIME
    UNVERIFIED. S0 decides.

S0 INTEGRITY CHECK
    Tensor-level comparison against stock MoGe-2 checkpoint.
```

---

## 6. `depth-anything/DA3MONO-LARGE`

```text
ROLE
    Modern direct-depth relative model.

QUESTION
    How good is direct-depth relative geometry, and how large/stable is its
    additive depth ambiguity on this domain?

OUTPUT
    Relative depth, with exponential-depth parameterisation.

AMBIGUITY
    Literature: Class 3 / affine-in-depth.

    E1 legal family:
        d' = s d + t

    S2 additionally tests whether the simpler subgroup:
        d' = s d
    performs indistinguishably on the project's domain.

    Only measured evidence may earn an approximately scale-only characterization.

LICENCE
    Apache-2.0 / Apache-2.0.

RUNTIME
    UNVERIFIED. Budget CUDA if needed; S0 decides.
```

---

## 7. `mxliu-hku/FoundationGeo-1.1`

```text
ROLE
    Point-map candidate plus same-checkpoint geometry-calibration ablation.

QUESTION
    What do learned ray correction and spatial metric calibration actually do
    to local geometry?

OUTPUTS OF INTEREST
    raw point map before learned ray delta
    raw point map after learned ray delta
    postprocessed relative point map
    metric point map
    scalefield
    delta

CANONICAL RANGE
    always ||point||

    Do NOT use `depth_metric` as range:
        depth_metric = point[..., 2]
    is z-depth.

RAY ABLATION — V4b
    Compare raw pre-delta vs raw post-delta geometry,
    BEFORE independent focal/shift recovery,
    or apply one common frozen postprocessing transform to both.

SCALE-FIELD ABLATION — V4c
    Compare common post-ray relative geometry vs:
        points_metric = points_rel * scalefield

    This is the clean spatial-scale intervention.

AMBIGUITY
    Relative point-map representation is handled according to its documented
    point-map gauge, not blindly as scalar d → s*d+t.

LICENCE
    MIT / MIT.

RUNTIME
    UNVERIFIED. S0 decides.

KNOWN FACTS
    scalefield is spatial/per-pixel;
    ray-direction correction is capped at approximately 3 degrees.
```

---

# 4. Conditional challengers

No conditional model is run merely because time is available.

## Depth Anything V2 Large

Activate only if:

- Small is within the S3 noise/uncertainty envelope of the leaders; or
- a failure appears plausibly capacity-limited.

Purpose: capacity diagnostic.

Not a mandatory finalist because of noncommercial weight licensing.

---

## DA3METRIC-LARGE

Activate post-C2 if:

- E3/raw metric accuracy becomes a primary criterion; and
- DA3 Mono remains a serious finalist.

Purpose:

> model-vs-model read on what separately trained metric supervision does to the same architecture.

Not a causal Mono→Metric factor ablation.

---

## FoundationGeo-Base-1.1

Activate only if FoundationGeo-1.1's **raw relative branch** is itself unexpectedly poor.

Question:

> Did Stage-II training degrade/change the relative geometry compared with the Stage-I checkpoint?

Interpret as model-vs-model only.

---

## SurGe

Activate if **all mandatory candidates** show materially poor local-surface geometry under M-3 / normal metrics.

Question then changes from:

> Which existing model has adequate local surface geometry?

to:

> Does explicitly training for local surface geometry solve the shared failure?

Research-only/noncommercial weights are acceptable for this falsification role.

---

## MoGe-3 ViT-L

Activate if thin/fine geometry becomes the deciding failure among finalists and reference CUDA execution is already justified.

Do not activate ViT-G merely for model scaling.

---

## UniDepth V2-L

Activate post-C2 if:

- E3/raw metric behavior becomes primary; and
- camera-model/calibration experiments indicate that first-class camera handling is materially relevant.

Its underwater benchmark result remains protocol-underspecified.

---

## UniDAC

Activate only if:

1. M-6 shows a strong radial-position-dependent failure; and
2. supplying known FOV/calibration during MoGe postprocessing does not resolve it.

This is a measured camera-model trigger, not a generic “wide FOV” trigger.

---

# 5. Frozen S0–S6 sequence

## S0 — Semantics, preprocessing and runtime gate

All seven candidates.

Establish empirically:

```text
MPS works
CPU works
CUDA required
reference modifications required
```

Do not inherit runtime claims from literature.

Verify for each model:

- strict N=1 invariant;
- output semantic;
- preprocessing/crop/letterbox behavior;
- valid mask semantics;
- conversion to camera-centre range;
- no accidental use of z-depth where range is required.

Specific wrapper traps:

```text
DA V2
    preserve disparity-space ambiguity before inversion.

FoundationGeo
    depth_metric is z-depth, not range.
    points_pre_field naming is misleading.
    causal ray ablation must occur before independently fitted postprocessing.

MapAnything
    verify N=1 produces the same declared representation.

MetricAnything
    tensor-diff checkpoint against stock MoGe-2.
```

Audit FOV loss explicitly. Week 3 already established that preprocessing can silently discard substantial image area.

Run initial sanity cases on public/reference material with known semantics.

**S0 fail → candidate exits.**

---

## S1 — Determinism and numerical noise floor

Repeat identical inference under fixed conditions.

Record:

- bitwise reproducibility where obtainable;
- otherwise numerical variation distribution;
- device/backend;
- precision.

A non-deterministic candidate is not automatically eliminated, but no downstream delta smaller than its measured noise floor may be interpreted as scientific signal.

---

## S2 — Native ambiguity measurement and frozen alignment policy

Freeze **one common evaluation policy**, not one universal transform family.

For each candidate, establish before accuracy testing:

```text
1. documented native output representation
2. documented legal ambiguity / gauge, if any
3. the E1 oracle transform permitted for that representation
4. the transform-fitting scope
5. the simpler subgroup(s) worth testing empirically
```

Examples:

```text
DA3 Mono:
    affine in scalar depth
    d' = s d + t

    also test whether scale-only suffices empirically.


DA V2:
    affine in disparity
    q' = a q + b

    fit there, then invert.


FoundationGeo relative point map:
    use the documented point-map gauge / transform,
    not a scalar depth-space fit pasted onto it.


Metric models:
    retain RAW metric output separately.
    Any oracle E1 alignment is explicitly diagnostic,
    not part of deployment semantics.
```

For all models, expose the fitted nuisance parameters rather than hiding them.

Temporal outputs must include:

- scale trajectory where meaningful;
- shift trajectory where meaningful;
- clip-to-clip variation;
- frame-to-frame variation;
- residual gain from granting the larger legal group.

After S2:

> the alignment **policy, transform family per representation, and fitting scope are frozen** for S3–S6.

---

## S3 — Local geometry / E1

Primary pre-C2 geometry stage.

All seven candidates.

Reference:

> Week-3 persisted range product.

Interpretation:

> agreement = consistency with the current multi-view hypothesis, not objective truth.

Run the six universal metrics from §6.

### FoundationGeo internal ablation

Within `FoundationGeo-1.1`:

```text
A. raw pre-ray-correction geometry
B. raw post-ray-correction geometry

score A vs B under one common representation/postprocessing convention
→ V4b ray-correction effect

then:

C. common post-ray relative geometry
D. C × scalefield

score C vs D
→ V4c spatial-scale-field effect
```

Do not use independently recovered focal/shift parameters to create the apparent A→B difference.

S3 is the primary field reduction:

```text
7 candidates → approximately 3–4
```

---

## S4 — Appearance invariance

Each frame remains strict single-image inference.

Perturb geometry-preservingly:

- white balance;
- channel balance;
- contrast;
- attenuation/color cast;
- haze;
- brightness;
- hotspot/artificial-light appearance;
- physically generated underwater perturbations;
- cue-conflict cases.

Decompose every response into:

```text
constant global scale bias
    reported; potentially benign gauge

frame-varying global scale drift
    failure under a shared clip-level physical model

post-fit local geometry deformation
    primary failure
```

Do not judge a model harshly for a fixed scale gauge.

Do judge it if changing appearance makes its scale or shift **pump over time** or deforms local range.

Atlantis++ may be used as an additional synthetic controlled appearance test only if the exact matched-geometry structure becomes verifiable.

It is not C2 and is not independent real underwater truth.

---

## S5 — Independent-frame temporal stability

Every frame inferred independently.

No temporal model context.

Use SEA-RAFT only for evaluation correspondence.

Primary temporal products:

```text
scale trajectory s_t
shift trajectory t_t where legal
near/far ratio trajectory
local surface / boundary stability
edge jitter
coverage / validity
confidence trajectory where available
```

Explicitly report the physical implication of scale drift.

If:

```text
d'_t = s_t d_t
```

then under one shared physical coefficient:

```text
beta'_t = beta / s_t
```

would be required.

Therefore frame-varying scale drift is a physical-model inconsistency, even when each individual frame looks geometrically good after oracle alignment.

DyFN is motivation for this decomposition only. Its particular model result is not generalized to the whole field.

S4–S5 reduce:

```text
3–4 candidates → 2–3 frozen finalists
```

---

## S6 — Restoration impact

Run only survivors.

Compare restoration using:

- Week-3 multi-view range;
- each surviving monocular range field.

Use **shared clip-level physical coefficients** where the downstream stage expects them.

This is where temporal scale drift becomes directly consequential.

Required outputs:

- frozen Week-2 temporal metrics;
- restoration radiance/color differences;
- range-error decomposition;
- mandatory visual inspection.

Specifically inspect for:

- backscatter/particles turned into depth structure;
- marine snow;
- caustics;
- animal boundaries;
- artificial-light regions;
- far-field range collapse;
- color pumping caused by temporal range drift.

S6 produces the provisional:

```text
adequate / degraded / unsafe
```

classification against the **current Week-3 reference**.

It does not produce the final objective Week-4 winner before C2.

---

# 6. Frozen metric set

AbsRel and δ₁ remain secondary literature-continuity metrics.

They are never decisive.

## M-1 — Range-stratified relative range error

Pre-C2, report this in **two forms**.

### M-1a — provisional Week-3 reference-range bins

For interpretability:

```text
nominal/reference bins:
0–1
1–2
2–3
3–5
5–8
8–12
12+
```

These are explicitly:

> **Week-3 reference units / provisional nominal metres, not independently validated physical metres.**

Do **not** claim that the current reference's nominal `8 m` is objectively an 8 m water path before C2.

### M-1b — scale-invariant near/mid/far stratification

Also report quantile/normalized-reference bins that do not rely on absolute metric scale.

This preserves pre-C2 ability to detect:

- near/far compression;
- errors concentrated at the far end;
- shape deterioration with range.

### Physical restoration thresholds

Week-3 sensitivity results such as:

```text
31% @ 1 m
12% @ 3 m
8.5% @ 8 m
...
```

remain the downstream physical budget.

Pre-C2 they may be used for **sensitivity analysis under the current provisional scale hypothesis**, but not as an objective acceptance threshold tied to independently known metres.

Direct physical-meter acceptance occurs in **4B after C2 anchors the range axis**.

---

## M-2 — Near/far systematic distortion

Fit, on aligned valid geometry:

```text
log(r_hat) = a + b log(r_ref)
```

Interpret:

```text
b ≈ 1
    no systematic range-dependent compression/expansion

b < 1
    far-field compression

b > 1
    far-field expansion
```

`a` is not treated as physical truth pre-C2.

M-2 is primarily a **shape/range-dependent distortion diagnostic**.

---

## M-3 — Local surface geometry

Primary:

**RelNormal** via `princeton-vl/EvalMDE`.

Also report SurGe-style absolute normal angular error where convenient.

RelNormal is:

> computed after the candidate's frozen legal E1 alignment and used to expose relative local surface-orientation/curvature errors that conventional scalar-depth metrics may miss.

Do not describe it as restoring ambiguity information deliberately removed by E1.

---

## M-4 — Boundary localization

Compare geometric boundaries between prediction and reference using a frozen edge/boundary construction.

Report distance in normalized/image-space units as well as any geometry-space interpretation.

Also reuse the same construction for temporal edge jitter in S5.

---

## M-5 — Foreground/background ordinal violations

Sample pixel pairs separated by a meaningful reference-range margin.

Report the fraction whose predicted order is inverted.

Use multiple margins.

This provides a highly ambiguity-resistant check of foreground/background ordering.

---

## M-6 — Radial image-position error

Recompute the primary shape/error diagnostics as a function of normalized radius from the principal point.

Purpose:

detect errors that grow toward the frame boundary and may indicate:

- wide-FOV projection mismatch;
- flat-port/noncentral-camera mismatch;
- z-depth/range confusion;
- calibration/postprocessing error.

M-6 is the trigger for camera-model challengers.

---

## Failure-triggered diagnostics

### T-1 — Range-gradient error

Trigger when M-3 is poor but the source of local geometry failure is unclear.

### T-2 — Planarity / curvature patches

Trigger when M-3 shows failure on surfaces expected to be locally simple:

- sand;
- wreck plating;
- chart board;
- other verified approximately planar supports.

### T-3 — Thin-structure retention

Trigger when boundaries/fine details separate finalists.

Hand-label only targeted supports such as:

- coral branches;
- rope;
- fish fins;
- thin wreck structures.

Also inspect false positive thin geometry created from backscatter or particulate texture.

---

# 7. What remains unknowable until C2

Week 4A cannot establish:

```text
definitive objective accuracy on this GoPro/housing configuration

final absolute water-path/range error

whether the Week-3 MapAnything hypothesis is objectively correct

final raw metric-scale ranking

definitive confidence calibration

final adequate / degraded / unsafe envelope

THE FINAL WEEK-4 WINNER
```

Pre-C2:

> the Week-3 range product is a provisional reference.

Therefore:

```text
monocular vs Week-3 disagreement
```

means disagreement with the current multi-view hypothesis, not objective monocular error.

Likewise, raw metric disagreement cannot determine whether:

```text
monocular metric scale is wrong
or
Week-3 reference scale is wrong
```

without an independent anchor.

E3/raw metric behavior is therefore:

```text
RECORDED pre-C2
JUDGED post-C2
```

C2 remains the required independent anchor.

---

# 8. C2 requirements carried forward

C2 must include:

- controlled chart/reference geometry at several known ranges;
- explicit distinction between z-depth, ray range and intended water-path convention;
- at least two water/visibility conditions;
- with and without dive lights where practical;
- matched EIS/HyperSmooth-off acquisition where practical;
- measured camera-interface distance / port information needed for the refractive hypothesis;
- far-range support.

In particular:

> capture at least one supported scene reaching approximately the far end of the intended operating envelope, ideally 10–15 m where visibility permits.

A C2 restricted to near ranges would fail to test the far-field deformation that both the restoration sensitivity study and external metric-depth literature suggest may be most consequential.

---

# 9. FINAL FREEZE

## YES — freeze and begin S0.

Mandatory checkpoints:

```text
1  facebook/map-anything-apache                 N=1
2  depth-anything/Depth-Anything-V2-Small
3  lsxi77777/Wat3R                              N=1
4  Ruicheng/moge-2-vitl
5  yjh001/metricanything_student_pointmap
6  depth-anything/DA3MONO-LARGE
7  mxliu-hku/FoundationGeo-1.1
```

Evaluation additions:

```text
princeton-vl/EvalMDE / RelNormal
SurGe-style MAE_normal
```

Mandatory model questions:

```text
MapAnything N=1
    What does losing multi-view information cost?

DA V2 Small
    How damaging is affine disparity ambiguity in practice?

Wat3R N=1
    Does underwater specialization help OOD underwater footage?

MoGe-2
    How good is a strong metric point-map baseline?

MetricAnything
    Does heterogeneous metric fine-tuning improve that fixed representation?

DA3 Mono
    How good is modern direct-depth relative geometry, and how large/stable
    is its additive ambiguity?

FoundationGeo-1.1
    What do learned ray correction and spatial scale calibration do to local geometry?
```

No mandatory entrant exists merely for category coverage.

No optional entrant activates without a measured trigger.

No further broad literature search is warranted before S0.

The remaining uncertainties are experimental:

```text
S0  semantics/runtime
S1  determinism
S2  actual ambiguity behavior
S3  local geometry
S4  appearance invariance
S5  temporal stability
S6  restoration consequence
```

Those questions are now better answered by running the frozen models than by reading additional papers.

**FROZEN 2026-09-06 — candidate discovery closed.**