# Week 4A — ROUND-2 SOTA CHALLENGER BAKEOFF

You are continuing the `uwrestore` Week-4A monocular-depth investigation AFTER the completed seven-model pre-C2 bakeoff.

This task has TWO purposes:

1. repair the small number of correctness defects discovered in the first bakeoff;
2. run a bounded ROUND-2 mini-bakeoff of current/recent SOTA monocular geometry models that attack failure modes actually measured in Round 1.

This is NOT another open-ended literature review.

Do NOT search for arbitrary additional models.

The Round-2 challenger set below is authorized and frozen for this run.

---

# 0. EPISTEMIC STATUS

Everything remains PRE-C2.

The Week-3 persisted range product is:

> a PROVISIONAL MULTI-VIEW HYPOTHESIS, not ground truth.

Therefore:

- agreement with Week 3 means consistency;
- disagreement cannot establish which model is objectively wrong;
- raw metric scale cannot be finally judged;
- absolute metre thresholds remain provisional;
- no objective final Week-4 winner may be declared before C2.

The goal of Round 2 is:

> determine whether newer/specialized monocular geometry methods materially change the pre-C2 conclusion reached by Round 1.

---

# 1. EXISTING ROUND-1 RESULT

Round 1 evaluated:

```text
facebook/map-anything-apache                 N=1
depth-anything/Depth-Anything-V2-Small
lsxi77777/Wat3R                              N=1
Ruicheng/moge-2-vitl
yjh001/metricanything_student_pointmap
depth-anything/DA3MONO-LARGE
mxliu-hku/FoundationGeo-1.1
```

It reduced to two provisional finalists:

```text
mapanything_n1
da3mono_large
```

Both were DEGRADED relative to the provisional Week-3 reference.

Important Round-1 findings:

## MapAnything N=1

Strongest static agreement with Week 3:

```text
M-1       0.0853
M-2 b     0.950
RelNormal 6.84
normal    7.9 deg
boundary  0.0028
ordinal   0.0000
M-6       1.04
```

But:

- the Week-3 reference itself is MapAnything multi-view;
- therefore the static lead has a major shared-architecture / shared-inductive-bias confound;
- temporal scale instability is substantial, especially on `cenote_01`;
- channel-neutralization perturbs scale strongly;
- its metric scale is supplied by the model but is NOT independently validated pre-C2.

Do NOT state that MapAnything “needs scale at inference.”

Correct statement:

> MapAnything produces raw metric-scale output, but its absolute scale is not independently validated pre-C2.

## DA3 Mono

Round 1 found:

- strongest independent-frame local temporal stability;
- strong ordering/local geometry;
- low radial error;
- but severe `wreck_05` restoration disagreement;
- cue-conflict / haze dependence;
- crane-lattice solid-fill hallucination on `wreck_07`;
- moving-diver disagreement on `wreck_03`;
- no confidence output;
- large affine-depth shifts.

HOWEVER:

> Round 1 evaluated DA3 under an incorrect unresolved z-depth-vs-range convention.

That must be repaired BEFORE Round-2 comparisons use DA3.

---

# 2. FROZEN FOOTAGE

The primary benchmark remains EXACTLY the existing Week-3 six-clip set:

```text
wreck_07
wreck_05
cenote_01
swimthrough_02
wreck_01
wreck_03
```

Each:

```text
48 frames
1280-pixel long-side existing Week-3 extraction
```

Total:

```text
288 matched frames per model
```

Reuse the existing persisted Week-3 products and exact frames.

Do NOT resample.

Do NOT add unrelated footage to the primary ranking.

Week-2 stress footage remains secondary only.

---

# 3. PART A — CORRECT DA3 SEMANTICS FIRST

This is a correctness repair, not a new hypothesis.

DA3 defines its point geometry using an UNNORMALIZED camera ray:

```text
P = t + D(u,v) R K^{-1} p
```

For:

```text
p = [u, v, 1]^T
```

the camera-frame vector `K^-1 p` has z component 1.

Therefore:

> `DA3MONO-LARGE` scalar depth `D` is projective/camera-axis Z-DEPTH, not Euclidean ray range.

The old statement:

> “DA3 z-vs-range remains unresolved”

is incorrect.

---

## A1. Reuse the frozen provisional camera model

Do NOT invent another K.

Find the exact provisional camera/intrinsics/ray construction already frozen in the Week-3/Week-4 experiment.

Respect:

- resize;
- crop;
- orientation;
- principal point;
- processed pixel mapping.

Define:

```text
rho(x) = || K^-1 p(x) ||
```

Then from Week-3 reference ray range:

```text
z_ref(x) = r_ref(x) / rho(x)
```

This remains a provisional central-camera approximation pre-C2.

Record its provenance exactly.

---

## A2. Fit DA3 in native Z-depth

At the already frozen CLIP-LEVEL scope:

```text
z_ref = s * z_DA3 + t
```

Also retain the diagnostic scale-only fit:

```text
z_ref = s * z_DA3
```

Report:

```text
s
t
t / representative scene depth
residual reduction from granting t
clip-to-clip variation
per-frame diagnostic s_t and t_t
```

Then construct canonical ray range:

```text
z_hat = s*z_DA3 + t
r_hat = z_hat * rho
```

Use this corrected `r_hat` for all DA3 S3-S6 metrics.

---

## A3. Reuse native predictions

Do NOT rerun DA3 inference if the saved native predictions are sufficient.

Recompute:

```text
S2
S3
S4
S5
S6
```

from the persisted DA3 output.

Write OLD vs CORRECTED values for every load-bearing metric.

Specifically inspect whether correction changes:

```text
M-2 near/far
M-3 surface geometry
M-4 boundaries
M-6 radial error
temporal scale/shift
cue conflict
wreck_05 restoration
wreck_07 crane lattice
wreck_03 diver
```

Re-decide DA3 finalist status from the corrected results.

---

# 4. PART B — BOUNDED DA V2 SEMANTIC REPAIR

DA V2's relative output is disparity/inverse-depth-like.

Using the same provisional ray field:

```text
z_ref = r_ref / rho
q_ref = 1 / z_ref
```

Fit its affine ambiguity in NATIVE disparity space:

```text
q_ref = a*q_DAv2 + b
```

Then:

```text
z_hat = 1 / (a*q_DAv2 + b)
r_hat = z_hat * rho
```

Use appropriate numerical guards.

Recompute only:

```text
S2
S3
```

for DA V2 Small.

If it remains clearly eliminated under the existing S3 criteria:

> STOP.

Do not rerun S4-S6 merely for completeness.

Only advance it if correcting the semantics materially reverses its original elimination.

---

# 5. PART C — FOUNDATIONGEO MECHANISM CHECK

FoundationGeo was included because it exposes a same-checkpoint mechanism test.

Verify that the persisted Round-1 results explicitly contain both:

## C1 — learned ray correction

Compare:

```text
raw pre-delta geometry
vs
raw post-delta geometry
```

under ONE common coordinate/postprocessing treatment.

Do NOT independently recover focal/shift for each arm and call the difference causal.

Report delta in:

```text
M-1
M-2
M-3
M-4
M-5
M-6
```

## C2 — per-pixel scale field

Using common post-ray geometry:

```text
points_rel
vs
points_rel * scalefield
```

Report the same six metrics.

If already present, surface the results clearly.

If intermediates were saved but summary omitted them, calculate them.

Do NOT rerun full inference unnecessarily.

---

# 6. ROUND-2 NEW CHALLENGERS

Exactly SIX automatically authorized challengers:

```text
R2-1  Ruicheng/moge-3-vitl
R2-2  facebook/hyden-mogev2-metric-point
R2-3  karimknaebel/surge-large
R2-4  PXDepth official released checkpoint
R2-5  PointDiT-L 512
R2-6  MDA mda_mog_sky_l2
```

Do NOT automatically add a seventh model.

Each has a distinct hypothesis.

---

# 7. R2-1 — MOGE-3 VIT-L

Checkpoint:

```text
Ruicheng/moge-3-vitl
```

Role:

> current fine-grained MoGe-family challenger.

Hypothesis:

> explicit sparse 3-D refinement may improve thin/local geometry without sacrificing global geometry.

The official checkpoint is ViT-L.

Do NOT run ViT-G unless a later measured capacity question specifically warrants it.

---

## MoGe-3 same-checkpoint refinement ablation

Run:

```text
refine_steps = 0
refine_steps = 3
```

under identical conditions.

This is a SAME-MODEL mechanism test, not two model families.

S0 must verify what exactly `refine_steps=0` and `3` change in the current code.

Report:

```text
Step0 -> Step3 M-1
Step0 -> Step3 M-2
Step0 -> Step3 M-3
Step0 -> Step3 M-4
Step0 -> Step3 M-5
Step0 -> Step3 M-6
coverage
runtime
memory
```

If Step 3 improves static detail but worsens temporal behavior later, preserve that trade-off rather than selecting a preferred mode early.

---

# 8. R2-2 — HYDEN-MOGEV2 METRIC POINT

Exact checkpoint:

```text
facebook/hyden-mogev2-metric-point
```

Use the official MetaDepth implementation.

It outputs:

```text
metric XYZ point map
```

Role:

> HIGH-RESOLUTION geometry challenger.

Scientific question:

> Is the project's 1280-long-side workflow losing fine geometry because conventional ViT-style models encode global geometry at too coarse a spatial resolution?

HyDen combines:

```text
low-resolution ViT global branch
+
full-resolution CNN detail branch
```

which makes it scientifically distinct from simply scaling MoGe-2.

Weights are FAIR Noncommercial Research License.

Treat it as a research candidate.

---

## HyDen resolution experiment

Do NOT blindly force everything to 518×518 if the released model supports higher-resolution inference.

During S0 inspect the actual HyDen-MoGe preprocessing path.

Run a BOUNDED resolution sanity ablation on a small representative subset BEFORE full S3:

```text
official/default inference configuration
vs
highest practical configuration that preserves the frozen image aspect/FOV
and meaningfully exercises HyDen's high-resolution branch
```

Do NOT:

- stretch aspect ratio merely to obtain more pixels;
- change crop;
- compare different FOVs;
- create a giant resolution sweep.

The question is simply:

> does high-resolution execution materially improve the exact local failures that motivated HyDen?

Freeze one Round-2 HyDen configuration after that small check.

Then use that configuration for the 288-frame S3.

---

# 9. R2-3 — SURGE LARGE

Checkpoint:

```text
karimknaebel/surge-large
```

Role:

> specialist LOCAL-SURFACE geometry challenger.

Scientific question:

> Can a model explicitly optimized for local point-map surface geometry beat the current field on the quantity this restoration pipeline actually cares about?

The released model produces:

```text
points
depth
intrinsics
```

and is trained with local point-gradient/surface objectives plus Neighborhood Attention.

Weights are:

```text
CC BY-NC 4.0
```

so this is research-only for current purposes.

Use the official recommended/reference inference path unless S0 establishes a project-compatible alternative.

Do not penalize it merely for being non-deployable; its role is a falsification target:

> if even SurGe cannot improve meaningful underwater local surface geometry, that is useful evidence.

---

# 10. R2-4 — PXDEPTH

Use the current official PXDepth repository and released checkpoint.

Role:

> structure-preserving pixel-space depth challenger.

Scientific question:

> Can retaining high-resolution pixel-space geometry fix the boundary/thin-structure failures seen in conventional large-patch ViT depth predictors?

PXDepth specifically targets:

```text
fine structures
sharp boundaries
local geometry
```

while retaining a global context encoder.

---

## CRITICAL PXDEPTH ATTRIBUTION RULE

The released repository also loads MoGe-2 to recover metric scale for point-cloud reconstruction.

That is NOT allowed for the primary Round-2 geometry comparison.

If PXDepth's native checkpoint predicts a relative depth field:

> preserve and evaluate that native prediction under its documented legal ambiguity.

Do NOT use MoGe-2 to turn PXDepth into a metric output in the primary result.

Otherwise the experiment becomes:

```text
PXDepth geometry
+
MoGe-2 scaling/camera prior
```

and the attribution is contaminated.

The MoGe-assisted metric reconstruction may be recorded separately as an OPTIONAL deployment-style diagnostic, but never replace the native PXDepth result.

---

## PXDepth S0 must resolve

Before accuracy evaluation determine from code:

```text
native scalar semantics
native ambiguity
output resolution
preprocessing
FOV/aspect handling
whether model-native point geometry exists independently of MoGe-2
license status of code and checkpoint
```

If the license remains undeclared, record that explicitly and treat the model as research-only.

Do not invent a licence.

---

# 11. R2-5 — POINTDIT-L 512

Use the official:

```text
PointDiT-L
512×512 checkpoint/config
```

Do NOT default to Huge merely because it has the best aggregate paper number.

The purpose is testing the representation/mechanism, not capacity.

Role:

> pixel-space generative POINT-MAP challenger.

Scientific question:

> Does point-map flow/diffusion modeling preserve ambiguous local geometry better than ordinary deterministic regression?

---

## Primary deterministic configuration

PointDiT literature reports that one-step inference can use:

```text
all-zero initial noise
```

with performance essentially matching random-noise initialization.

Therefore use as the PRIMARY configuration:

```text
single-step
all-zero initialization
```

after verifying this path in the official code.

This provides a deterministic strict-mono output and keeps compute bounded.

---

## Bounded PointDiT refinement ablation

On a SMALL representative subset:

```text
one-step all-zero
vs
the paper/release recommended multi-step quality configuration
```

Measure primarily:

```text
M-3 local normals/surface
M-4 boundary
thin-structure diagnostic
runtime
determinism
```

Do NOT perform a huge sampler/step sweep.

If multistep does not materially improve the project's relevant geometry, freeze one-step for full S3.

If it materially does, carry the better configuration but preserve the compute/temporal trade-off.

---

## PointDiT semantic requirement

Preserve the native point-map output.

Determine the model's documented normalization / affine point-map gauge from source.

Do NOT blindly treat its depth channel as metric range.

Do NOT import MoGe scale unless explicitly evaluating a separate hybrid diagnostic.

---

# 12. R2-6 — MDA / MODELING DEPTH AMBIGUITY

Use:

```text
model_name = mda_mog_sky_l2
checkpoint = official DA3_MOG_Sky_LogL2 checkpoint
```

This is the official primary DA3-backed MDA model.

Do NOT add the VGGT variant automatically.

Role:

> MULTI-HYPOTHESIS depth ambiguity challenger.

This model is included because Round 1 observed an actual failure that its representation is designed to attack:

```text
DA3 fills the open wreck_07 crane lattice with a solid surface
```

MDA replaces one depth hypothesis per pixel with multiple hypotheses and probabilities.

Scientific question:

> Does explicitly representing foreground/background ambiguity prevent DA3-family flying-point / solid-fill boundary failures underwater?

---

## Strict N=1 check

The official demo supports single-image inference, but S0 must independently verify:

```text
ONE image enters the model
NO hidden neighbouring views
NO cached multi-view state
NO sequence geometry
```

If its DA3-backed checkpoint requires an internal multi-view path even for one image, document exactly what occurs.

Strict Week-4 N=1 remains mandatory.

---

## MDA confidence/ambiguity diagnostic

This is a unique opportunity.

Persist:

```text
mixture component depths
mixture probabilities
chosen component
entropy where meaningful
top-1 vs top-2 probability margin
component separation
```

especially around:

```text
wreck_07 crane lattice
wreck_03 moving diver
marine snow / particulate regions
strong depth boundaries
cue-conflict appearance perturbations
```

Do NOT immediately call these quantities “calibrated confidence.”

Instead ask:

> do low-margin / high-entropy mixture predictions correlate with the failures that DA3 could not signal?

This is exploratory failure-signalling evidence pre-C2.

True confidence calibration remains post-C2.

---

# 13. INCUMBENTS FOR ROUND 2

Do not unnecessarily re-infer these.

Use persisted/corrected products:

```text
I1  MapAnything N=1
I2  corrected DA3 Mono
I3  MoGe-2 ViT-L
```

Roles:

```text
MapAnything
    Round-1 static leader / shared-reference-family control

corrected DA3
    Round-1 independent temporal finalist

MoGe-2
    family baseline for MoGe-3 / HyDen comparisons
```

If saved native outputs are complete, reuse them.

Do not waste compute rerunning incumbents just to create matching timestamps.

---

# 14. ROUND-2 S0 — SEMANTICS / RUNTIME GATE

Run for all six new challengers.

For each establish:

```text
strict N=1
native representation
coordinate frame
legal ambiguity / gauge
canonical range conversion if possible
preprocessing
orientation handling
FOV retention
mask semantics
device/backend
precision
runtime
memory
reference modifications required
licence status
```

No model enters S3 while its representation semantics remain unresolved.

Do NOT repeat the Round-1 DA3 mistake of deciding z-depth-vs-range by residual.

Semantic source/code evidence wins.

---

# 15. ROUND-2 S1 — DETERMINISM

Measure:

```text
bitwise reproducibility
numeric reproducibility
stochastic variation where applicable
runtime
memory
```

For stochastic-capable models separately characterize the selected deterministic configuration.

PointDiT:

```text
one-step all-zero
```

must be tested directly.

MDA mixture outputs must themselves be checked for repeatability.

No downstream delta smaller than the complete evaluation/noise floor should be overinterpreted.

---

# 16. ROUND-2 S2 — REPRESENTATION-AWARE ALIGNMENT

Use the SAME frozen alignment philosophy as Round 1:

> common POLICY, representation-specific transform.

Never one universal `a*d+b`.

For each challenger:

1. determine its documented native representation;
2. determine the legal alignment/gauge from source;
3. preserve raw output;
4. freeze clip-level fitting for E1;
5. keep per-frame fitting diagnostic only.

Metric models:

```text
raw metric result
+
clip-level scale E1 diagnostic
```

Relative scalar models:

fit in their actual native depth/disparity representation.

Affine point maps:

fit the documented point-map gauge.

Do not use an external helper model's scale in the primary E1 result.

---

# 17. ROUND-2 S3 — FULL 288-FRAME MINI-BAKEOFF

Run all six S0/S1/S2 survivors on EXACTLY:

```text
wreck_07
wreck_05
cenote_01
swimthrough_02
wreck_01
wreck_03
```

48 frozen frames each.

Score the same universal dimensions:

```text
M-1 range-stratified error
M-2 near/far distortion
M-3 RelNormal + normal geometry
M-4 boundary localization
M-5 ordinal violations
M-6 radial-position error
coverage
```

No weighted score.

Use both:

```text
provisional Week-3 reference-range bins
and
scale-invariant near/mid/far bins
```

Absolute metre interpretation remains provisional before C2.

---

# 18. TRIGGERED THIN-STRUCTURE TEST — NOW MANDATORY IN ROUND 2

The Round-1 visual finding:

> DA3 fills the open `wreck_07` crane lattice with a solid surface

has fired the previously conditional thin-structure diagnostic.

Create a SMALL targeted annotation/evaluation around the known crane/lattice region.

Do NOT create a new benchmark.

At minimum compare:

```text
Week-3 reference
MapAnything N=1
corrected DA3
MoGe-2
MoGe-3 Step 0
MoGe-3 Step 3
HyDen
SurGe
PXDepth
PointDiT
MDA
```

Evaluate:

```text
open-space preservation
false filled surfaces
missing thin members
foreground/background leakage
edge displacement
ordinal correctness across openings
```

Visual inspection is mandatory.

MDA additionally reports its mixture ambiguity signal in this region.

---

# 19. ROUND-2 REDUCTION AFTER S3

Do not carry every challenger forward.

Classify each challenger:

```text
DOMINATED
NON-DOMINATED
SPECIALIST WIN
FAILURE
```

A challenger advances only if it does at least one of:

```text
A. materially improves primary local/range geometry over both incumbents;
B. uniquely fixes the triggered thin-structure failure without a large regression elsewhere;
C. reveals a genuinely different robustness property relevant to restoration.
```

Novelty alone is not enough.

Expected:

```text
6 challengers
→ approximately 2–3 new survivors
```

Incumbents remain:

```text
MapAnything
corrected DA3
```

unless the corrected DA3 result eliminates it.

---

# 20. ROUND-2 S4 — APPEARANCE INVARIANCE

Run only Round-2 survivors plus incumbent finalists.

Use exactly the frozen perturbation battery from Round 1.

Decompose:

```text
constant global scale bias
frame-varying scale drift
local range deformation
```

Constant clip-wide scale may be benign.

Temporal scale drift is NOT benign.

Explicitly inspect:

```text
channel neutralization
veil/haze cue conflict
artificial light/hotspot
color casts
brightness/contrast
```

MDA:

also measure whether ambiguity probability responds usefully to cue conflict.

---

# 21. ROUND-2 S5 — TEMPORAL STABILITY

Each frame is still inferred independently.

No temporal information enters any model.

Use the exact Round-1 evaluation:

```text
scale trajectory s_t
shift trajectory where legal
near/far wander
local instability
boundary jitter
coverage
confidence/ambiguity trajectory if available
```

For variable scale:

```text
d'_t = s_t*d_t
```

interpret under shared physical coefficients:

```text
beta'_t = beta/s_t
```

Frame-varying scale therefore remains a physical-consistency failure.

For MoGe-3:

compare Step 0 vs Step 3.

For PointDiT:

compare chosen one-/multi-step configuration only if S3 justified retaining both.

For MDA:

inspect ambiguity trajectories, but do not call them calibrated uncertainty.

---

# 22. ROUND-2 S6 — RESTORATION IMPACT

Only run a new challenger through S6 if it remains genuinely finalist-worthy after S5.

Use identical Round-1 S6 machinery:

```text
responsive-window evaluation
shared clip-level physical coefficients
existing Week-2 temporal metrics
mandatory visuals
```

Compare against:

```text
Week-3 reference-driven restoration
MapAnything N=1
corrected DA3 if still alive
each genuinely surviving Round-2 challenger
```

Inspect:

```text
wreck_05 low-texture failure
wreck_07 lattice/thin structure
wreck_03 diver
cenote_01 far-range/temporal behavior
marine snow/backscatter
caustics
artificial light
color pumping
```

Classify:

```text
ADEQUATE
DEGRADED
UNSAFE
```

relative to the provisional reference.

Remain PRE-C2.

---

# 23. OPTIONAL ROUND-2B MODELS — DO NOT RUN AUTOMATICALLY

These models have been researched but are not in the automatic six.

## InfiniDepth

Use only if, after HyDen + PXDepth + MoGe-3:

```text
high-resolution/fine-detail behavior remains unresolved
```

Reason:

> arbitrary-resolution neural implicit depth is its unique hypothesis.

Do NOT use MoGe-2 metric-scale recovery in its primary relative-depth evaluation.

---

## UniDAC

Use only if corrected results show:

```text
M-6 radial error grows materially toward image edge
AND
known-camera/FOV postprocessing does not fix it
```

Then the any-camera hypothesis has been earned.

---

## GeoNeXt

Use only if:

```text
PointDiT demonstrates a meaningful generative-prior advantage
AND
you want to test whether a substantially different current generative geometry prior generalizes that result.
```

Do not add it simply because it is extremely recent.

---

## OptiGeo

Do not run unless an official reproducible code/checkpoint release is verified.

---

# 24. WHAT NOT TO DO

Do NOT:

- rerun the whole Round-1 zoo;
- add random SOTA models after starting;
- run ViT-G variants simply because they are larger;
- use a helper MoGe prediction to set another model's primary scale;
- silently crop portrait frames;
- fit each frame independently in the primary temporal evaluation;
- convert every native representation to generic “depth” before S2;
- compare models using different frame sets;
- create a weighted leaderboard;
- treat the Week-3 reference as truth;
- claim C2 conclusions before C2;
- launch another broad literature review.

---

# 25. OUTPUTS

Persist under:

```text
experiments/week4_mono/round2/
```

At minimum:

```text
R2_S0_SEMANTICS_RUNTIME.md
R2_S0_results.json

R2_S1_DETERMINISM.md
R2_S1_results.json

R2_S2_ALIGNMENT.md
R2_S2_alignment_policy.json

R2_S3_LOCAL_GEOMETRY.md
R2_S3_results.json

R2_THIN_STRUCTURE.md
R2_thin_structure_results.json

R2_S4_APPEARANCE.md
R2_S4_results.json

R2_S5_TEMPORAL.md
R2_S5_results.json

R2_S6_RESTORATION.md
R2_S6_results.json

WEEK4A_POST_R2_FINAL.md
```

Also append concise reproducible stage summaries to `LOG.md`.

Persist native outputs so semantic corrections do not require re-inference.

---

# 26. FINAL REPORT

`WEEK4A_POST_R2_FINAL.md` must answer:

## Correctness repairs

1. What changed after correcting DA3 from ray-range interpretation to native z-depth?
2. Did DA3 remain a finalist?
3. Did corrected DA V2 remain eliminated?
4. What did FoundationGeo's actual ray correction do?
5. What did FoundationGeo's per-pixel scale field do?

## Round-2 results

For each challenger:

```text
why it was tested
native representation
runtime/device
determinism
S3 strengths
S3 weaknesses
thin-structure result
S4 result if advanced
S5 result if advanced
S6 result if advanced
elimination/retention reason
```

Explicitly answer the mechanism questions:

```text
MoGe-3:
    did SSR Step 0 -> Step 3 actually improve underwater geometry?

HyDen:
    did its high-resolution dual path matter at this project's resolution?

SurGe:
    did explicit local-surface training beat generic models on local surfaces?

PXDepth:
    did pixel-space prediction actually fix boundaries/thin structures?

PointDiT:
    did generative point-map inference improve local geometry,
    and was one-step deterministic inference sufficient?

MDA:
    did multi-hypothesis depth fix DA3-family flying-point/solid-fill failures,
    and did its mixture probabilities correlate with actual failure?
```

## Final pre-C2 set

Produce:

```text
FINAL PRE-C2 FINALISTS: 2–3 maximum
```

Do NOT preserve an incumbent merely because it won Round 1.

Do NOT preserve a challenger merely because it is SOTA.

Every finalist must remain non-dominated for this restoration use case.

---

# 27. FINAL SCIENTIFIC QUESTION

The report must end by answering:

> After correcting Round-1 semantics and challenging the incumbents with current 2026 SOTA/fine-geometry models, is STRICT SINGLE-IMAGE DEPTH demonstrated ADEQUATE, DEGRADED, or UNSAFE as the fallback geometry source for this underwater-restoration pipeline relative to the provisional Week-3 hypothesis?

Then state:

> What exact C2 measurements are required to convert the remaining pre-C2 hypotheses into objective conclusions?

No further model-search recommendation unless Round 2 exposes a specific measured failure whose already-defined optional trigger fires.

---

# 28. AUTONOMY AND COST DISCIPLINE

Proceed autonomously.

Do not ask for routine confirmation.

Use CUDA/rented GPU when a model's official reference path genuinely requires it rather than spending hours forcing unsupported MPS execution.

Reuse persisted outputs whenever possible.

Do not rerun inference just to simplify coding.

Persist results after every stage.

Keep conversational context compact; write detailed results to disk.

Do not have subagents repeatedly ingest the entire repository/history.

Use expensive reasoning primarily for:

```text
semantic validation
S3 reduction
S5 finalist reduction
final causal interpretation
```

STOP only if:

```text
1. a native representation cannot be resolved without guessing;
2. strict N=1 would be violated;
3. a required official checkpoint cannot be obtained;
4. a newly discovered correctness defect invalidates the comparison;
5. the available compute environment makes the reference implementation impossible.
```

A single challenger failure does not stop the rest of Round 2.

The objective is:

> a bounded current-SOTA challenge to the Round-1 conclusion, not another model zoo.


CUDA EXECUTION POLICY

Do not attempt to provision, purchase, configure, or authenticate to a cloud GPU service.

If this repository already contains a documented, authenticated remote-CUDA
execution path, you may use ONLY that existing path and record the exact command.

Otherwise, if an official/reference implementation genuinely requires CUDA and
cannot execute correctly on MPS/CPU:

    status = pending_cuda

Persist:
- exact checkpoint
- environment requirements
- command/configuration required
- estimated artifacts needed
- point in the protocol where execution stopped

Then continue with the remaining challengers.

Do not port CUDA-specific kernels to MPS merely to make the model run.
Do not substitute an unofficial implementation.
Do not fabricate results.

DA V2 FITTING DISCIPLINE

The PRIMARY S2 alignment remains the frozen legal affine transform in native
inverse-z / disparity space:

    q_ref ~= a*q_pred + b

Do not change the primary objective to log-depth or z-space merely to improve
far-range restoration error; doing so would optimize away a failure the
experiment is intended to measure.

Before fitting:
- use only the frozen valid-mask support;
- reject non-finite / invalid values;
- use numerically stable linear algebra;
- normalize variables for conditioning if necessary without changing the
  objective;
- apply frozen denominator/positivity guards before inversion.

After fitting, explicitly inspect the consequences in ray-range space through
the already frozen:
    M-1 range-stratified error
    M-2 near/far distortion
    far-quintile error

OPTIONAL SENSITIVITY DIAGNOSTIC:
If naive native-space least squares appears dominated by range sampling,
compute ONE secondary predeclared range-balanced/robust affine-disparity fit
(e.g. equal total weight across near/mid/far reference quantile bands).

Label this SENSITIVITY ONLY.
It must not silently replace the primary frozen S2 fit or be chosen based on
which produces the better model score.

CONTEXT / RESULT-FILE DISCIPLINE

This is one continuous experiment. Do NOT intentionally reset the session
between S0-S6.

Auto-compaction is already configured; rely on it rather than attempting to
invoke session-management slash commands autonomously.

More importantly:

1. Persist every stage's raw measurements to machine-readable files.

2. Persist a SMALL stage summary containing only:
   - configuration / semantic decisions
   - aggregate metrics
   - gate decision
   - surviving models
   - unresolved correctness issues
   - paths to detailed artifacts

3. After a stage is finalized, treat that summary as the conversational source
   of truth for subsequent reasoning.

4. NEVER reread a giant JSON/NPZ/result directory merely to "check the work."

5. When information from a large result file is needed, use a script/query to
   compute the specific aggregate or retrieve only the required subset.

6. Do not print per-frame results into conversational context.

7. Do not paste subprocess logs into context unless diagnosing a failure.
   Store full logs on disk and inspect targeted sections.

8. For the 288-frame evaluations, compute reductions programmatically and read
   compact summary tables, not the full per-frame dataset.

9. Before each major reduction (S3 and S5), explicitly reload only:
   - the frozen protocol requirements;
   - the previous stage's compact summary;
   - the aggregate metrics required for that decision.

10. If context nevertheless becomes problematic, persist a concise handoff
    state before compaction containing:
        current stage
        completed models
        frozen semantic decisions
        artifact paths
        outstanding work
        stop condition
REFERENCE-IMPLEMENTATION INTEGRITY

For every challenger, record whether inference used:

    A. exact official/reference implementation;
    B. mechanically adapted official implementation with unchanged model math;
    C. unofficial/reimplementation.

Primary Round-2 results require A or B.

Category B modifications must be enumerated and limited to execution mechanics
such as device placement, dependency compatibility, file paths, or tensor I/O.

Do NOT silently:
- replace unsupported operators with approximate alternatives;
- change interpolation modes;
- change model input resolution merely to make memory fit;
- substitute checkpoints;
- remove refinement stages;
- change attention implementations when numerically non-equivalent;
- use helper models not authorized by the protocol.

If correctness-equivalent execution cannot be established:

    pending_runtime

rather than inventing a runnable approximation.