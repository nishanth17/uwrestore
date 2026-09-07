# Deep literature review: state-of-the-art monocular depth for underwater restoration

Before doing anything, read PLAN.md and LOG.md.

I am building a research-quality underwater image/video restoration pipeline. I need an **extremely extensive, current literature review of monocular depth estimation as of September 2026**, followed by a project-specific synthesis identifying the **absolute best candidates to benchmark for this application**.

This is a **literature/research pass only**.

Do not implement models.
Do not modify code.
Do not write the final Week 4A experimental protocol yet.

The purpose of this pass is to establish the **complete credible option landscape**, understand the important advances through 2026, and derive the smallest scientifically complete candidate set for a later bakeoff.

Do NOT produce a generic monocular-depth leaderboard summary.

I want you to understand the downstream physical-restoration problem, survey the field broadly, challenge the shortlist I already have, identify materially different approaches, verify what is actually released, and then recommend a bounded experimental candidate set.

Use **primary sources wherever possible**:

- original papers,
- CVPR / ICCV / ECCV / NeurIPS / ICLR proceedings,
- arXiv when no proceedings version exists,
- official project pages,
- official GitHub repositories,
- official model cards,
- official checkpoint pages.

Use secondary sources for discovery only. Verify any consequential claim against a primary source.

Search especially aggressively across **2024–September 2026**.

Older work should be included only where it remains:

- an important baseline,
- a conceptual ancestor,
- a specialist alternative,
- a still-competitive model,
- or necessary to understand a modern method.

Every claim about:

- SOTA status,
- release status,
- checkpoint availability,
- license,
- benchmark numbers,
- inference semantics,
- camera assumptions,

must be traceable to a verifiable source.

---

# 1. Project context

The eventual pipeline is physically motivated underwater restoration.

The relevant observation model is approximately:

```text
I_c(x)
    = J_c(x) * exp(-beta_att_c * d(x))
    + B_inf_c * (1 - exp(-beta_bs_c * d(x)))
```

where the range quantity that ultimately matters is the **distance light propagates through water**.

For a central camera this is approximately range along the viewing ray.

For the project's refractive geometry path it may instead be the distance from the water-interface exit point to the scene point.

The project therefore uses the canonical quantity:

```text
water_path_length
```

and explicitly tracks whether a method's native range is:

- measured,
- transformed exactly,
- or approximated.

Do not confuse:

```text
z-depth
Euclidean camera-centre range
range along a viewing ray
inverse depth
disparity
relative depth
3-D point map
ray direction
ray origin
water path length
```

These are not interchangeable.

---

# 2. What Week 3 has already established

Week 3 investigated multi-view range.

Current provisional deployment path:

```text
dense range       MapAnything
cross-check       COLMAP / SIFT
```

This is provisional because an independent controlled metric anchor, called **C2**, has not yet been captured.

Important Week-3 result:

For the ambient attenuation/backscatter model, if coefficients are freely fitted within a clip,

```text
d -> s*d
beta -> beta/s
```

makes a **single global multiplicative range-scale error exactly absorbable**.

Therefore:

> Global metric scale is much less important than spatially varying shape error for Weeks 5–6A.

The dangerous errors are things like:

- near range correct but far range biased,
- spatially varying multiplicative error,
- nonlinear range compression/expansion,
- local range deformation,
- incorrect foreground/background ordering,
- incorrect discontinuities,
- object-edge errors,
- temporal depth breathing,
- local failures hidden by apparently good global scale.

Week 3 also measured downstream restoration sensitivity to range error.

Representative results:

```text
worst-channel restored-radiance error reaches ~5% at approximately:

clear oceanic:
    31% local range error @ 1 m
    12% @ 3 m
    8.5% @ 8 m

coastal:
    9.4% @ 3 m
    6.1% @ 8 m

turbid:
    1.0% @ 8 m
    0.3% @ 12 m
```

These downstream thresholds matter much more than winning a generic depth benchmark by a small amount.

Metric scale becomes more important when:

- physical coefficients are transferred/shared across clips,
- absolute water properties are interpreted,
- artificial-light modelling introduces distance-dependent falloff,
- camera-to-light geometry is used,
- cross-clip physical parameters are compared.

So raw metric performance matters.

It is simply **not automatically the primary criterion**.

---

# 3. Current Week-3 uncertainty

C2 has not been captured yet.

Current Week-3 evidence includes:

- MapAnything dense range,
- vanilla VGGT,
- Wat3R,
- COLMAP/SIFT,
- various classical perturbations.

But none is independent ground truth.

Important known uncertainty:

- MapAnything has a strong dynamic-subject scale failure on one clip.
- COLMAP becomes under-conditioned on low-feature footage; roughly `<~2000 SIFT observations/image` is currently a warning learned from this dataset, NOT a universal boundary.
- Some large dense-vs-classical disagreements occur exactly where the classical reference is itself poorly identified.
- Refraction is currently **not identified**, largely because C2/metric port geometry is missing and the refractive implementation proved non-reproducible.
- EIS is active in the current GoPro footage and is a documented geometry confound.

Therefore, before C2:

> Cross-method agreement is evidence of consistency, not automatically correctness.

The monocular study must preserve that epistemic distinction.

---

# 4. Week 4 objective

The eventual Week-4 question is:

> Can a strictly single-image depth estimator provide range accurate and stable enough to substitute for multi-view range when video geometry is unavailable?

Use cases:

```text
photo:
    monocular range is the only available geometry

fallback video frame:
    multi-view geometry unavailable/unreliable for a frame,
    so a single-image estimator supplies fallback range
```

For the video case, the model must still be evaluated as a **strictly independent single-frame estimator**.

Absolutely no:

- neighboring-frame context,
- hidden temporal state,
- multi-view inference,
- Week-3 pose input,
- Week-3 depth input,
- cached feature sharing across frames.

If a model supports both monocular and multi-view inference, evaluate only its genuine monocular path.

Known intrinsics/FOV may be supplied **only if the model's documented monocular API legitimately supports them**.

---

# 5. Discover the COMPLETE modern option space first

Do not begin with a predetermined shortlist and search only for evidence supporting it.

Survey the serious modern literature and organize it into **architecturally and conceptually meaningful families**.

At minimum investigate the following families.

## Relative / foundation monocular depth

Examples to investigate, but do not assume these are exhaustive:

- Depth Anything V2
- Depth Anything 3 Mono
- Lotus-2
- any important 2025–2026 successor not listed here

## Metric monocular depth

Investigate:

- UniDepth
- UniDepth V2
- Depth Anything 3 Metric
- Metric3D
- Metric3D v2
- any relevant successors
- ZoeDepth where historically useful
- recent universal / zero-shot metric approaches

## Explicit monocular 3-D / point-map prediction

Investigate:

- MoGe
- MoGe-2
- any newer point-map / ray / metric-3D approach

## General / any-camera geometry

Investigate:

- UniK3D
- UniDAC
- other 2025–2026 arbitrary-camera, fisheye, panoramic, or camera-general depth/3-D approaches.

This matters because the footage comes from a GoPro with wide FOV and an underwater housing.

However:

> Do NOT equate “any camera” with correct modelling of a non-central flat-port refractive camera.

Explicitly distinguish models that handle arbitrary **central** projections from methods capable of representing per-pixel ray-origin shifts or genuinely non-central imaging.

A network predicting different ray **directions** from one common camera origin is still central.

## Generative / diffusion-prior monocular geometry

Investigate:

- Lotus
- Lotus-2
- diffusion/generative monocular-depth approaches that plausibly offer better fine structure or OOD robustness,
- any 2025–2026 successor.

Determine whether their advantages appear geometrically real or primarily benchmark/perceptual.

## Underwater-specific monocular depth

Search this area comprehensively.

At minimum investigate:

- WaterMono
- CD-UDepth
- UMono
- UDepthDiff
- any newer 2025–2026 underwater monocular-depth models,
- underwater metric-depth benchmarking/adaptation papers,
- synthetic-underwater fine-tuning of foundation models,
- underwater LoRA/domain-adaptation work where technically credible.

Also search for underwater work that produces single-image geometry but may not prominently call itself “monocular depth.”

## Relevant adjacent work

Search where genuinely relevant:

- foundation-depth adaptation,
- zero-shot OOD depth,
- adverse-weather depth,
- depth under fog/haze/scattering,
- low-texture geometry,
- metric scale recovery,
- confidence/uncertainty calibration,
- camera-model robustness,
- edge/detail preservation,
- depth under severe photometric distortion,
- transparent/scattering-media depth,
- test-time adaptation / inference-time optimization.

Do not pad the review with adjacent work that cannot realistically change candidate selection.

---

# 6. Current shortlist — ATTACK IT

The current tentative shortlist is:

```text
CORE CANDIDATES

1. UniDepth V2-L
2. MoGe-2-L
3. Depth Anything 3 Mono-L
4. Depth Anything 3 Metric-L
5. WaterMono
```

Potential challengers currently known:

```text
UniDAC
UniK3D
Depth Pro
Depth Anything V2
Metric3D v2
Lotus-2
CD-UDepth
UMono
UDepthDiff
other underwater-adapted foundation models
```

Treat this list as **a hypothesis to attack**, not as an answer.

Determine:

- whether any core candidate should be removed,
- whether any belong only as conditional challengers,
- whether DA3 Mono/Metric should be treated as one paired family,
- whether WaterMono is actually the best underwater-specific control,
- whether a substantially better 2025–2026 underwater model exists,
- whether a newer 2026 model supersedes UniDepth V2, MoGe-2, or DA3,
- whether a generative/diffusion family deserves a primary slot,
- whether an any-camera model deserves a primary slot given the GoPro setup,
- whether any model I have not named represents a genuinely missing capability.

Do not privilege famous models.

Do not preserve the shortlist merely because I supplied it.

---

# 7. Verification requirements for EVERY credible candidate

Produce a detailed candidate table.

For every candidate establish the following.

## Identity

```text
model
paper title
authors
publication venue
publication date
stable primary-source identifier
official repository
official checkpoint/model card
latest meaningful released version
```

For every paper provide at least one **verifiable primary-source identifier**, such as:

- arXiv ID,
- DOI,
- CVF/OpenReview/proceedings identifier,
- or another stable primary publication reference.

Do not invent identifiers.

If you cannot independently verify that the cited work exists, mark:

```text
paper_status_unverified
```

rather than treating it as evidence.

For repositories and checkpoints:

- verify the repository actually exists,
- verify the checkpoint/model card actually exists,
- distinguish paper claims from released artifacts.

If a repository cannot be verified live, mark:

```text
code_status_unverified
```

If a checkpoint cannot be verified, mark:

```text
checkpoint_status_unverified
```

Do not infer a release merely because a paper says code “will be released.”

## Availability

```text
code available?
pretrained weights available?
checkpoint downloadable?
license of CODE
license of CHECKPOINT
commercial restrictions?
dataset-derived restrictions?
repo maintained?
```

Be precise.

Code license and checkpoint license may differ.

## Inference semantics

```text
strict one-image inference supported?
native prediction:
    z-depth?
    ray range?
    inverse depth?
    disparity?
    point map?
    ray directions?
    ray origins?
    normals?

metric?
scale-ambiguous?
shift-ambiguous?
affine-invariant?
other?
```

State exactly what ambiguity the model claims.

Do NOT casually write “scale/shift” for every relative model.

Determine the mathematical invariance implied by:

- its training loss,
- output representation,
- and documented evaluation protocol.

In particular, identify whether an affine ambiguity is defined in:

```text
depth
inverse depth
disparity
another transformed representation
```

These are physically different.

## Camera assumptions

```text
pinhole?
known intrinsics optional?
known FOV optional?
intrinsics predicted?
fisheye?
arbitrary central camera?
panorama?
non-central camera possible?
```

Explicitly distinguish ray **direction** from ray **origin** prediction.

## Confidence / uncertainty

```text
confidence map?
uncertainty map?
what exactly does it claim to mean?
aleatoric / epistemic / learned confidence / heuristic?
any calibration evidence?
OOD calibration evidence?
```

Do not equate “model emits confidence” with “confidence is useful underwater.”

## Training and domain

```text
main training datasets
synthetic vs real
indoor/outdoor mix
camera diversity
underwater data?
adverse-condition data?
```

## Underwater evidence

Search specifically for evidence involving:

```text
FLSea
SQUID
Sea-thru
other underwater metric-depth datasets
underwater zero-shot studies
underwater fine-tuning studies
```

For every underwater comparison establish:

- exact model/version/checkpoint,
- raw metric or aligned evaluation,
- depth representation,
- preprocessing/enhancement,
- dataset,
- metrics,
- whether numbers are genuinely comparable to another cited paper,
- protocol differences,
- whether evaluation intrinsically favors one model family.

Do not merge incompatible results into a fake leaderboard.

## Computational properties

Approximate where evidence permits:

```text
parameter count
native/model input resolution
evaluation resolution
runtime
VRAM
CUDA requirement
MPS support or likelihood
CPU possibility
```

Local machine:

```text
Apple M4
24 GB unified memory
```

GPU rental is available for a scientifically compelling model.

Therefore CUDA-only does **not** automatically eliminate a candidate.

But deployment practicality should eventually influence selection.

## Expected project-specific strengths

Assess plausibility for:

```text
relative ordering
near/far shape
local depth discontinuities
thin coral / rope / animal edges
moving animals
textureless water
low-contrast reef
severe blue/green cast
red-starved imagery
murk
backscatter
suspended particles
artificial dive lights
wide FOV
portrait orientation
```

## Expected failure mechanisms

Explain mechanisms, not generic weaknesses.

Possible examples:

- radiometric domain shift,
- semantic-prior dependence,
- attenuation mistaken for distance,
- haze/backscatter mistaken for geometry,
- poor raw metric scale,
- textureless-scene smoothing,
- depth-edge bleeding,
- camera-model mismatch,
- dynamic-object instability,
- temporal scale breathing,
- confidence miscalibration,
- generative structural hallucination,
- crop/FOV preprocessing loss,
- inconsistent metric calibration,
- reliance on training-camera priors.

---

# 8. Deeply review the RECENT ADVANCES, not only model names

Produce a technical synthesis of what materially changed in monocular depth from approximately 2023 → September 2026.

Investigate trends such as:

- large vision-foundation encoders,
- relative-depth foundation models,
- universal metric depth,
- camera-conditioned/camera-general models,
- point maps instead of scalar depth,
- joint ray/intrinsics/depth prediction,
- discriminative vs generative/diffusion approaches,
- synthetic-scale training,
- pseudo-labeling and distillation,
- cross-dataset metric training,
- uncertainty prediction,
- multi-task geometric representations,
- any-camera modelling,
- adapter tuning / LoRA,
- underwater physical simulation/domain adaptation,
- inference-time refinement,
- test-time adaptation.

For every claimed advance, answer:

> Does this plausibly matter to this underwater-restoration problem, or is it primarily an improvement on generic depth benchmarks?

---

# 9. Special underwater question: can degradation become a FALSE DEPTH CUE?

This is a major concern.

Underwater image formation naturally produces:

```text
greater range
    -> greater wavelength-dependent attenuation
    -> more backscatter / haze
    -> lower contrast
    -> different colour
```

A monocular model may exploit those appearance cues.

That can help in one water type and catastrophically fail when:

- water properties change,
- artificial lights alter spectra and apparent attenuation,
- color correction is applied,
- visibility changes,
- backscatter varies independently of scene geometry,
- camera exposure/WB changes.

Search for literature relevant to:

- depth under haze/fog/scattering,
- appearance-vs-geometry shortcuts,
- photometric invariance,
- domain invariance,
- underwater depth domain shift,
- depth prediction after image enhancement,
- depth consistency under photometric transformations.

I plan to run controlled appearance-only perturbation tests in Week 4A:

```text
same underlying image geometry

vary:
    white balance
    channel attenuation
    contrast
    haze/backscatter
    brightness
    artificial-light hotspot
```

Then measure geometry change after removing only the ambiguity legitimately allowed for that model.

Evaluate whether the literature supports this experiment.

Suggest a better formulation only if it measures information this design misses.

---

# 10. Alignment semantics are CRITICAL

For every serious candidate, specify exactly how it may be fairly aligned during evaluation.

Possible classes include:

```text
RAW METRIC
    no alignment

SCALE-AMBIGUOUS DEPTH
    one multiplicative scalar in depth space

AFFINE-INVARIANT INVERSE DEPTH / DISPARITY
    affine alignment in THAT NATIVE REPRESENTATION

OTHER
    model-specific and explicitly justified
```

Do not universally use:

```text
d_gt = a*d_pred + b
```

just because it improves a score.

Determine the actual model semantics first.

## Additive shift deserves special scrutiny

A pure global multiplicative scale has the exact invariance established by Week 3.

An additive depth offset does **not** generally share that invariance for the complete physical image-formation model.

For example, if:

```text
d' = s*d + t
```

and attenuation coefficients are rescaled,

the direct transmission term gains an additional constant exponential factor that may sometimes trade against a radiometric scale.

But the backscatter term:

```text
B_inf * (1 - exp(-beta_bs*d))
```

does not in general remain in the same physical family under an arbitrary additive range shift.

More fundamentally:

```text
d = 0
```

has physical meaning: zero water path should produce zero water-column attenuation and backscatter.

An arbitrary offset destroys that boundary condition.

Therefore:

> Treat additive ambiguity as materially more problematic than pure scale ambiguity for this physical application.

However, be precise about **which representation carries the shift**.

Many relative-depth methods are affine invariant in **inverse-depth/disparity space**, not physical depth space.

Do not convert that statement into a fictitious affine ambiguity in metric depth.

For each model, establish the native representation before deciding the legal alignment.

I need three evaluations kept separate:

### Oracle structural evaluation

> If the model's unavoidable global ambiguity were known, is its spatial geometry correct?

### Deployable calibration

> Can one fixed calibration learned from allowed calibration evidence be frozen and reused?

### Raw metric prediction

> Does the model produce useful physical range without GT alignment?

Never collapse these into one result.

---

# 11. Temporal stability matters even though inference is monocular

The fallback-video use case means the selected model will be run independently on each frame.

No temporal depth model is being selected.

I care about:

```text
frame-to-frame global scale breathing
near/far ratio breathing
local range jitter
depth-edge position jitter
confidence jitter
```

A model that looks excellent after **per-frame oracle alignment** but produces:

```text
scale:
0.8, 1.2, 0.7, 1.1, ...
```

can destabilize downstream physical parameter estimation.

Search for literature evaluating temporal consistency of independently applied monocular-depth models.

Determine whether any current model is known to be especially stable or unstable frame-to-frame.

Do not recommend switching to video depth unless clearly separated as future work.

Week 4 explicitly tests the single-image fallback path.

---

# 12. Public underwater datasets and validation

Identify the best public datasets for pre-C2 validation.

For each relevant dataset report:

```text
name
real vs synthetic
camera
environment
GT source
GT density
metric scale?
depth/range definition
coverage
known limitations
license
download availability
common evaluation protocol
```

Likely candidates include:

- FLSea,
- SQUID,
- Sea-thru,

but search broadly.

Determine which datasets are best for:

- wrapper correctness,
- raw metric accuracy,
- relative shape,
- near/far error,
- underwater domain shift,
- moving subjects,
- low texture,
- severe color degradation.

Do not imply that winning a public dataset proves success on my GoPro footage.

---

# 13. Underwater adaptation and inference-time adaptation

Do a serious review of whether the strongest general models should be adapted rather than replaced by an underwater specialist.

Investigate:

```text
full fine-tuning
LoRA
adapter tuning
decoder-only tuning
pseudo-labeling
synthetic underwater rendering
physics-based augmentation
teacher/student adaptation
self-supervised real-underwater adaptation
```

Also investigate:

```text
test-time adaptation (TTA)
test-time training (TTT)
single-image inference-time optimization
self-consistency-based inference-time refinement
```

But do **not** assume TTA is beneficial merely because it is recent.

Specifically evaluate whether TTA is compatible with this project's requirements:

- strict independent-frame processing,
- reproducibility,
- deterministic regression testing,
- bounded runtime,
- no paired ground truth at inference,
- risk of adapting to misleading underwater attenuation/backscatter cues,
- temporal stability when adaptation is performed independently on adjacent frames.

For continuous-depth prediction, determine what the actual adaptation signal is.

Do not casually import classification-style “entropy minimization” arguments where they do not mathematically apply.

Treat TTA as:

> a candidate adaptation strategy to investigate, not a presumed primary solution.

Especially answer:

> Given that Week 3 eventually provides real underwater RGB plus high-quality multi-view range on my own target distribution, which modern model would be the best adaptation target if zero-shot structure is excellent but underwater radiometry produces systematic failures?

Do NOT make fine-tuning or TTA part of the primary Week 4A bakeoff unless evidence strongly justifies it.

Prefer treating adaptation as a:

```text
conditional challenger
or
Week 4.5 experiment
```

---

# 14. Reduce the literature to DISTINCT HYPOTHESES

After broad discovery, group candidates by what scientific hypothesis they test.

Examples:

```text
"universal metric depth generalizes underwater"

"explicit point-map geometry preserves shape better"

"very large relative-depth foundation model gives the structural ceiling"

"underwater adaptation matters more than architecture"

"camera-general modelling matters for the GoPro"

"generative priors materially improve thin/detail geometry"

"inference-time adaptation can remove water-domain shift without destroying
frame independence"
```

Identify models that are largely redundant.

This is critical:

> Broad literature discovery is encouraged. Broad model integration is not.

---

# 15. Recommend a PRIMARY Week-4A bakeoff

After completing the review, recommend the **smallest scientifically complete primary candidate set**.

Target roughly:

```text
4–6 configurations / model families
```

but do not obey that number mechanically.

If five are required, use five.

If only four are scientifically distinct, use four.

If six are genuinely necessary, justify six.

A paired comparison such as:

```text
DA3 Mono
DA3 Metric
```

may count as one family if it isolates a meaningful variable.

For every primary candidate provide:

```text
exact model/version/checkpoint
role
hypothesis
why this exact model
which candidate/family it challenges
what experimental result would make it win
what result would make it lose
```

Do not select primarily by generic leaderboard rank.

---

# 16. Recommend CONDITIONAL challengers

For every strong model that does not make the primary set, specify an explicit trigger.

Use:

```text
OBSERVED FAILURE
    -> MODEL / FAMILY TO ACTIVATE
    -> WHY IT SPECIFICALLY ADDRESSES THAT FAILURE
```

Examples:

```text
wide-FOV / camera-model error dominates
    -> UniDAC / UniK3D

fine boundaries dominate the failure
    -> Depth Pro or current edge specialist

all discriminative models lose thin structure
    -> Lotus-2 / best current generative candidate

all terrestrial models fail under cast/murk while an underwater specialist survives
    -> underwater adaptation family

zero-shot geometry is structurally excellent but underwater appearance
systematically deforms it
    -> LoRA / decoder adaptation of the leading foundation model

public underwater accuracy is good but independent-frame predictions breathe
    -> investigate a stability-specific challenger before accepting the model

a credible depth-specific TTA method demonstrably repairs the same
radiometric domain failure without harming determinism or temporal stability
    -> activate TTA experiment
```

Do not invent a role merely so every reviewed paper appears useful.

---

# 17. Explicitly reject candidates

Create:

```text
REVIEWED AND NOT SELECTED
```

For every notable candidate reviewed but not selected, state why:

- superseded,
- redundant,
- weaker released version,
- poor underwater evidence,
- no unique capability,
- incompatible output semantics,
- multi-view rather than monocular,
- video-only,
- no weights,
- unverifiable release,
- unusable license,
- excessive compute with no distinct hypothesis,
- benchmark advantage irrelevant downstream,
- non-reproducible,
- etc.

This should prevent the same models being rediscovered and debated later.

---

# 18. Adversarial self-review

After constructing the initial recommendation, perform a second pass whose explicit goal is to **disprove it**.

Ask:

1. Did I overweight benchmark SOTA?
2. Did I overweight raw metric scale despite Week 3's scale invariance?
3. Did I miss a newer 2026 model?
4. Did I miss an underwater specialist?
5. Did I confuse multi-view capability with actual monocular performance?
6. Did I confuse arbitrary central cameras with non-central refractive cameras?
7. Did I compare incompatible benchmark numbers?
8. Did I recommend two models that test essentially the same hypothesis?
9. Did I exclude a candidate mainly because it is inconvenient to run?
10. Did I believe model confidence without OOD calibration evidence?
11. Did I verify the checkpoint rather than only the paper?
12. Did I verify code and checkpoint licenses independently?
13. Did I confuse `depth_z` with ray range?
14. Did I assign affine ambiguity in the wrong representation?
15. Did I assume the paper's best variant is publicly released?
16. Did I rely on secondary summaries where a primary source exists?
17. Did I prime myself to find TTA useful merely because the prompt mentioned it?
18. Did I prime myself to preserve the supplied shortlist?
19. Is there a model or family that could realistically dominate this shortlist for the actual restoration objective that I failed to investigate?
20. Are there contradictory papers or benchmarks I have not reconciled?

Correct the recommendation after this pass.

Clearly distinguish:

```text
initial recommendation
changes after adversarial review
final recommendation
```

---

# 19. Do not solve the C2 question prematurely

C2 has not been captured.

The literature pass may recommend models and experiments, but must distinguish what can be established in Week 4A from what requires Week 4B.

## Week 4A — BEFORE C2

Can establish:

```text
candidate landscape
release/checkpoint/license status
output semantics
legal alignment semantics
public underwater performance
determinism
runtime/memory
relative shape behavior
cross-method consistency on my footage
near/far deformation against provisional references
edge behavior
underwater-domain stress
appearance invariance
independent-frame temporal stability
provisional restoration impact
2–3 finalists
```

Cannot honestly establish:

```text
definitive objective accuracy on my camera
final absolute range error
final metric-scale accuracy on my footage
whether MapAnything or another Week-3 hypothesis is objectively correct
definitive confidence calibration
final adequate/degraded/unsafe operating envelope
final Week-4 winner
```

## Week 4B — AFTER C2

Only the frozen finalists should normally be evaluated against:

```text
independent C2 anchors
final Week-3 selected + runner-up products
fixed calibration transfer
raw metric output
definitive confidence calibration
definitive restoration-sensitivity envelope
```

Do not turn 4B into another literature/model-discovery pass.

---

# 20. Output-length / pacing requirement

This review is intentionally large.

Do **not** compress important analysis merely to force the entire review into one response.

If the required depth exceeds your available output budget:

- complete the current logical section cleanly,
- explicitly mark that the review is incomplete,
- identify the exact next section to continue from,
- continue in subsequent responses when prompted.

Do not:

- stop mid-table,
- stop mid-candidate,
- silently omit later sections,
- drastically shorten the candidate review to fit,
- replace evidence with superficial summaries merely to finish in one response.

Prioritize completeness and evidence quality over single-response compactness.

---

# 21. Required deliverable

Produce a document suitable to save as:

```text
experiments/week4_mono/MONO_DEPTH_LANDSCAPE.md
```

Use approximately this structure:

```text
1. Executive conclusions

2. Project-specific depth requirements

3. What Week 3 already established

4. State of monocular depth through September 2026

5. Major technical advances, 2023–2026

6. Candidate-family taxonomy

7. Comprehensive candidate/release table

8. Relative / foundation depth

9. Metric depth

10. Explicit 3-D / point-map approaches

11. Any-camera models

12. Generative / diffusion approaches

13. Underwater-specific models

14. Underwater benchmark evidence

15. Public datasets relevant to Week 4A

16. Camera-model implications for GoPro / flat-port footage

17. Output semantics and permitted alignment table

18. Confidence / uncertainty evidence

19. Independent-frame temporal consistency evidence

20. Underwater appearance/domain-shift analysis

21. Fine-tuning / adaptation / TTA options

22. Primary Week-4A candidate set

23. Conditional challengers with explicit triggers

24. Reviewed / rejected candidates

25. Proposed acquisition-independent Week-4A measurement categories
    (high level only — do NOT write the full experimental protocol yet)

26. What must wait for C2 / Week 4B

27. Adversarial self-review

28. Final recommendation

29. Source inventory
```

At the top include a concise answer to:

> **If I could integrate only the minimum scientifically complete set of monocular models before C2, which exact models/checkpoints should I run, and why?**

But answer that only **after actually completing the research**, not merely from the shortlist supplied in this prompt.

---

# 22. Source integrity requirements

Maintain a source inventory containing, for every consequential paper/model:

```text
paper title
stable identifier
publication venue/date
official project page if any
official repository
official checkpoint/model card
verification status
```

Where possible distinguish:

```text
PAPER VERIFIED
CODE VERIFIED
CHECKPOINT VERIFIED
LICENSE VERIFIED
```

If something cannot be verified, say so.

Do not fabricate:

- arXiv IDs,
- DOIs,
- GitHub repositories,
- checkpoint names,
- benchmark values,
- model releases,
- publication venues.

A missing fact is preferable to an invented one.

---

# 23. Quality bar

I want this review to be unusually thorough.

Do not:

- stop after finding five famous models,
- rely on an outdated Awesome-Monocular-Depth list,
- equate leaderboard rank with relevance,
- assume “metric” means useful,
- assume “underwater-specific” means better,
- assume “foundation model” means robust,
- assume “any-camera” means non-central,
- assume TTA improves depth,
- invent benchmark comparability,
- hide missing weights,
- hide license problems,
- turn small benchmark deltas into strong recommendations,
- use generic scale+shift alignment without checking model semantics,
- recommend a model merely because integration is easy.

Do:

- search aggressively for recent work,
- follow citation trails,
- inspect official repositories,
- inspect model cards/checkpoints,
- compare publication AND release dates,
- distinguish paper model from released model,
- distinguish code license from checkpoint license,
- verify whether claimed 2026 advances are actually available,
- search for contradictory evidence,
- determine exact prediction semantics,
- identify actual missing capabilities,
- prefer experiments that discriminate hypotheses,
- explicitly state uncertainty where literature cannot answer the question.

The end goal is **not** to declare a literature winner.

The end goal is:

> Build the best possible evidence-backed candidate landscape so Week 4A can run a bounded, scientifically meaningful bakeoff, eliminate weak/redundant approaches, and freeze 2–3 finalists before the C2 acquisition.