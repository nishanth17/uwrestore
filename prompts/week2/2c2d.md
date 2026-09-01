# Week 2 Phase 2C/2D — Baselines, Signal Diagnostics, and Ablation Plumbing

Read `CLAUDE.md`, `PLAN.md`, `LOG.md`, and the current repository first.

Also read:

```text
experiments/week2a_flow/FINDINGS.md
experiments/week2b_temporal/FINDINGS.md
```

and inspect the completed Phase 2A/2B implementation so you understand the now-frozen:

- optical-flow abstraction and SEA-RAFT-M integration,
- raw MC-Warp@1/@4/@8,
- canonical illumination-aware MC-Warp@1/@4/@8,
- uncompensated residual and motion-reduction reporting,
- temporal ΔE00,
- alignment-robust companion if implemented,
- illumination-confound/status behavior,
- validity/coverage semantics,
- Phase 2B thresholds/guards/status bands,
- flow/result reuse and metric-resolution policy,
- existing ΔE00/colorspace implementation.

Do not modify `CLAUDE.md` or `PLAN.md`.

The research-heavy Week 2 temporal-evaluation work is complete.

This phase is the **mechanical closer for Week 2**.

Do not redesign or retune:

- optical flow,
- SEA-RAFT integration,
- raw MC-Warp,
- canonical illumination-aware MC-Warp,
- illumination fitting,
- illumination guards/status thresholds,
- temporal ΔE00,
- alignment-robust metric,
- validity/occlusion methodology,
- coverage semantics,
- ΔE00,
- colorspace architecture.

Do not begin Week 3.

---

# Goal

Implement:

- white-patch global-WB baseline,
- CLAHE local-contrast baseline,
- cheap per-channel signal/clipping diagnostics,
- simple ordered pipeline composition,
- ablation controls,
- tests,
- CLI/scoring integration.

Keep the implementation minimal and consistent with existing Week 1/2 patterns.

The purpose of the new signal diagnostics is not to estimate sophisticated sensor noise yet.

They answer simpler questions:

> Is a source channel already clipped or near the floor?

> Is a global correction applying a huge gain to a channel that contains very little recorded signal?

> Did a correction push substantial image content outside the normal representable range?

Do **not** implement robust SNR/noise estimation in this phase.

That remains acquisition-dependent work for controlled/chart footage later.

---

# 1. White-patch baseline

Implement in `uw/baselines.py`:

```python
white_patch(frame: Frame) -> Frame
```

This is a deliberately simple global white-balance baseline.

Conceptually:

> Estimate a plausible bright reference from the frame and derive global RGB gains that move that bright reference toward neutral/white.

Do not over-engineer illuminant detection.

Before implementing, inspect `gray_world` and match its conventions wherever appropriate.

## Bright-region estimator

Do not blindly use the single brightest pixel.

A single maximum can be dominated by:

- noise,
- hot pixels,
- specular highlights,
- bubbles,
- clipped dive lights.

Use one simple deterministic robust bright-region strategy, for example:

- select a fixed top luminance percentile,
- aggregate RGB over that selected region using a robust/simple statistic.

The exact percentile/statistic may differ if the existing code suggests a cleaner minimal implementation.

Requirements:

- fixed and deterministic,
- documented,
- no semantic object detection,
- no automatic chart detection,
- no per-clip tuning.

Do not add:

- chromaticity clustering,
- neutral-pixel detection,
- semantic highlight rejection,
- learned illuminant estimation,
- sophisticated color-constancy logic.

This is intentionally a **robust bright-patch baseline**, not a general illuminant estimator.

Choose one simple fixed rule, document it, and freeze it **before inspecting real-clip results**.

## White-patch requirements

The function must:

- operate on the project's linear-light RGB `Frame`,
- return a new `Frame`,
- never mutate the input,
- preserve existing metadata,
- explicitly derive global per-channel gains,
- record those gains in metadata,
- avoid division-by-zero / near-zero instability,
- preserve the project's existing philosophy of making range violations visible,
- record `out_of_range_fraction` or equivalent consistently with `gray_world`.

Do not silently clip simply to make the result look cleaner.

If export eventually requires clipping, that remains an output-format concern.

Do not claim white-patch is physically correct underwater restoration.

It is a baseline.

---

# 2. Cheap signal-recoverability diagnostics

Add a small deterministic diagnostic path for input and corrected frames.

Do not build a generalized image-quality framework.

The goal is to expose when a correction is attempting to amplify information that may have been poorly represented in the source.

Implement/report, per RGB channel where meaningful:

## Near-floor fraction

Measure the fraction of pixels whose linear-light channel value is at or below one small, fixed, documented threshold.

Purpose:

> Detect source channels containing very little recorded signal.

Use one project-wide threshold or one simple justified convention.

Do not tune it per clip or pipeline.

Call the result something explicit, for example:

```text
near_floor_fraction_r
near_floor_fraction_g
near_floor_fraction_b
```

or a compact structured equivalent.

## Saturation / upper-bound fraction

Report the fraction of values at the upper normal boundary where the source representation meaningfully permits this inference.

Distinguish where possible between:

- source/input upper-bound saturation,
- correction-produced values above the normal range.

Do not pretend every decoded `1.0` necessarily proves sensor-level clipping if the source encoding/codec prevents that conclusion.

Document exactly what is measured.

## Correction gains

For global correction stages such as:

- gray-world,
- white-patch,

report the derived:

```text
R gain
G gain
B gain
```

so later analysis can identify cases such as:

```text
original red near-floor fraction = very high
+
red gain = 7.8x
```

That combination must remain visible even if the corrected image looks attractive.

## Post-correction range

Continue exposing:

- out-of-range fraction,
- clipping risk,

consistent with existing baseline conventions.

Do not silently clip before computing the diagnostic.

---

# 3. Source versus corrected signal semantics

Keep **source-information diagnostics** conceptually distinct from **output-range diagnostics**.

`near_floor_fraction_*` is primarily a property of the ORIGINAL input signal.

A correction can move numerical values away from zero without recovering missing source information.

Therefore, when assessing recoverability, always preserve/report:

```text
ORIGINAL input near-floor fraction
+
applied correction gain
+
resulting output out-of-range/clipping behavior
```

It is acceptable to report near-floor fractions on corrected output for descriptive purposes.

However, do not interpret:

```text
corrected red near-floor fraction decreased
```

as evidence that red information was recovered.

A global multiply cannot recreate source information that was clipped, quantized away, or buried below useful signal.

---

# 4. Explicit signal-diagnostic non-goals

Do **not** implement:

- whole-image RGB variance as noise,
- sophisticated SNR,
- sensor noise modeling,
- denoising,
- noise confidence maps,
- learned recoverability estimators,
- quantization estimators,
- signal reconstruction confidence models.

Real SNR/noise characterization waits for suitable controlled flat/chart regions.

Do not label any simple image statistic as "SNR" or "noise variance" without a defensible noise model.

---

# 5. CLAHE local-contrast baseline

Implement a CLAHE-based local-contrast baseline in `uw/baselines.py`.

Use a `Frame -> Frame` contract consistent with the other baselines.

This is **contrast enhancement**, not underwater color restoration.

Its purpose is:

> Determine how much apparent improvement can be obtained purely by improving local tonal contrast.

## Critical rule — never CLAHE RGB independently

Do **not** independently equalize:

```text
R
G
B
```

Independent per-channel CLAHE creates artificial hue/saturation changes and would confound the experiment.

Instead:

1. derive a scalar luminance/lightness representation,
2. perform CLAHE only on that scalar,
3. reconstruct linear RGB while preserving chromatic relationships as closely as reasonably possible.

---

# 6. CLAHE perceptual-lightness representation

Do not blindly run CLAHE directly on physical linear RGB channels.

Prefer a fixed perceptual-lightness pathway based on the existing color-science code.

Preferred conceptual path:

```text
linear RGB
    ↓
linear luminance Y
    ↓
perceptual lightness, preferably CIE L*
    ↓
CLAHE
    ↓
inverse perceptual transform -> Y'
    ↓
luminance-ratio reconstruction
    ↓
linear RGB'
```

Conceptually:

```python
scale = Y_prime / Y
RGB_prime = RGB * scale
```

with explicit handling for near-zero luminance.

Reuse existing colorspace/color-science helpers where appropriate.

Do not introduce a second conflicting conversion stack.

Do not use an arbitrary hand-tuned gamma.

---

# 7. Near-black CLAHE reconstruction

Do not divide by an arbitrarily tiny `Y` and then simply clamp an enormous scale afterward.

For:

```text
Y ≈ 0
```

use an explicit, documented near-black branch / epsilon policy.

Requirements:

- numerically stable,
- no NaN,
- no Inf,
- no huge RGB amplification caused purely by ill-conditioned `Y_prime / Y`,
- sensible preservation of genuinely near-black pixels.

Document the exact policy.

---

# 8. OpenCV CLAHE precision

`cv2.createCLAHE().apply()` requires an integer single-channel representation.

Use `uint16`, **not `uint8`**.

Conceptually:

```text
normalized perceptual lightness [0,1]
                ↓
scale to [0,65535]
                ↓
np.uint16
                ↓
CLAHE
                ↓
float / 65535
                ↓
inverse perceptual-lightness transform
                ↓
linear RGB reconstruction
```

Requirements:

- explicitly convert to `np.uint16`,
- use the full 16-bit range,
- convert back to floating point,
- return a normal project `Frame` containing floating linear-light RGB.

Do not reduce dark underwater gradients to 8-bit merely because OpenCV examples commonly do.

---

# 9. CLAHE range handling

CLAHE requires a bounded scalar control signal.

If a preceding correction stage produces luminance/lightness outside the nominal range:

- expose that fact through diagnostics,
- preserve the actual floating project state,
- bound only the **temporary CLAHE control representation** where mathematically required,
- do not silently rewrite historical diagnostics,
- do not imply the source/correction was actually in range.

The public `Frame` contract remains:

```text
input  = floating linear RGB
output = floating linear RGB
```

---

# 10. CLAHE parameters

Use one fixed baseline configuration.

Document:

- `clipLimit`,
- `tileGridSize`,
- lightness representation,
- linear-luminance definition,
- perceptual transform,
- uint16 quantization pathway,
- near-black reconstruction rule,
- final RGB reconstruction method.

Do not run a hyperparameter sweep.

Do not tune parameters per clip.

Do not adjust CLAHE after inspecting which setting gives the prettiest footage.

This is a control.

---

# 11. Pipeline composition

Week 1 used a single-method command shape similar to:

```bash
uw correct <path> --method gray_world
```

Week 2 now needs explicit ordered composition.

Introduce the smallest mechanism required to support:

```bash
uw correct <path> --pipeline white_patch clahe
```

Do not build:

- plugin discovery,
- dependency injection,
- processing DAGs,
- generic pipeline frameworks,
- stage registries intended for hypothetical future work.

A simple known-stage mapping plus ordered list is sufficient.

---

# 12. Backward compatibility

Do not unnecessarily break Week 1 behavior.

Prefer retaining:

```bash
--method gray_world
```

as a backward-compatible single-stage alias equivalent to:

```bash
--pipeline gray_world
```

If both:

```text
--method
--pipeline
```

are supplied:

> fail clearly.

Do not silently prefer one.

---

# 13. No misleading default pipeline

Gray-world and white-patch are primarily **competing global white-balance baselines**.

Do not automatically define:

```text
gray_world -> white_patch -> clahe
```

or any other stacked default.

Explicitly support comparisons such as:

```text
none
gray_world
white_patch
clahe
gray_world -> clahe
white_patch -> clahe
```

Preserve existing default behavior where practical.

Do not infer that more stages means a better pipeline.

---

# 14. Ablation controls

Every actually implemented **correction stage** must have an ablation control.

Support:

```text
--no-gray-world
--no-white-patch
--no-clahe
```

These flags skip matching stages from the requested pipeline.

Example:

```bash
uw correct clip.mp4 \
    --pipeline white_patch clahe \
    --no-clahe
```

must execute only:

```text
white_patch
```

Keep behavior simple and deterministic.

Do not add:

```text
--no-depth
--no-backscatter
--no-attenuation
--no-temporal
```

Those correction stages do not exist.

MC-Warp, temporal ΔE00, and the illumination-aware temporal metric are measurements, not correction stages.

---

# 15. Pipeline execution and metadata

Keep execution conceptually simple:

```python
result = frame

for stage in active_stages:
    result = stage(result)
```

Each stage remains:

```text
Frame -> Frame
```

and must obey:

- no mutation,
- metadata preservation,
- explicit range behavior.

Record enough information to recover:

- requested stages,
- actual executed stages,
- execution order,
- ablations applied,
- per-stage global gains where relevant,
- per-stage out-of-range behavior where relevant.

Do not accidentally overwrite prior-stage metadata.

If metadata keys could collide, use a small explicit per-stage structure rather than inventing a general provenance framework.

---

# 16. CLI / scoring integration

Update `uw correct` and `uw score` minimally.

Support:

- gray-world,
- white-patch,
- CLAHE,
- explicit ordered pipelines,
- implemented-stage ablations.

Scoring must use the **already-established Phase 2B evaluator unchanged**.

Do not redefine or retune:

- raw MC-Warp,
- canonical illumination-aware MC-Warp,
- uncompensated residual,
- motion-reduction ratio,
- temporal ΔE00,
- alignment-robust companion if Phase 2B implemented one,
- illumination fit/model/guards,
- illumination-confound/status behavior,
- validity masks,
- coverage rules,
- evaluation resolution.

Do not add new sophisticated metrics.

---

# 17. Scoring/reporting output

For each correction run/configuration report enough information to know:

```text
Pipeline:
  white_patch
  clahe

Ablated:
  none
```

Also report cheap signal diagnostics.

Example:

```text
Signal diagnostics:

  Original input:
    near-floor RGB: ...
    upper-bound RGB: ...

Correction gains:
    white_patch:
      R = ...
      G = ...
      B = ...

Post-correction:
    out-of-range fraction: ...
```

Continue reporting the established evaluation separately.

Conceptually:

```text
Color:
  chart ΔE00

Temporal:
  Raw MC-Warp@1
  Raw MC-Warp@4
  Raw MC-Warp@8

  Canonical illum-aware MC-Warp@1
  Canonical illum-aware MC-Warp@4
  Canonical illum-aware MC-Warp@8

  Alignment-robust warp, if Phase 2B implemented it
  Uncompensated residual
  Motion-reduction ratio
  Temporal ΔE00
  Valid coverage
  Status/confound information
```

Do not combine these into one quality score.

Both **raw MC-Warp** and **canonical illumination-aware MC-Warp** must remain visible.

---

# 18. Temporal-evaluation reuse across correction configurations

Optical-flow correspondence is derived from the **original input footage** and must not change when the correction pipeline changes.

When evaluating multiple correction configurations on the same clip/frame range:

- compute or load Phase 2B correspondence once,
- reuse the exact same flow and validity information for every correction configuration,
- do not rerun SEA-RAFT independently for `none`, `gray_world`, `white_patch`, `clahe`, or their combinations merely because the corrected pixels differ.

Likewise:

Any Phase 2B illumination transform defined solely from the aligned original input pair must be reused for every correction configuration on that same pair.

This is required for two reasons:

1. efficiency,
2. experimental fairness.

Differences between pipeline configurations must come from the correction, not a different realization of the evaluator.

Preserve Phase 2B bounded-memory behavior.

Reuse may be:

- pair-local,
- through the existing bounded cache,
- through already-generated reusable artifacts if that is the established implementation.

Do not retain an entire long clip's GPU state merely to avoid recomputation.

Do not change the frozen evaluator merely to make reuse easier.

---

# 19. White-patch tests

Follow existing test style.

Add focused tests for:

## Non-mutation

Input `Frame` remains unchanged.

## Metadata

Existing metadata survives.

Derived gains and range diagnostics are recorded.

## Controlled cast

Construct a synthetic linear-RGB case with known cast.

Verify the selected bright reference moves toward neutrality as intended.

## Robust bright-region estimate

Ensure one isolated pathological maximum/hot pixel does not dominate if the chosen estimator is intended to reject single maxima.

## Determinism

Same frame gives identical gains and identical output.

## Near-zero safety

No:

- division by zero,
- NaN,
- Inf,
- uncontrolled gain explosion.

## Out-of-range behavior

Verify correction-created range violations are surfaced rather than silently hidden.

---

# 20. Signal-diagnostic tests

Add focused tests proving the diagnostics mean exactly what their names claim.

At minimum:

## Near-floor fraction

Controlled channel values produce the exact expected fraction.

## Upper-bound fraction

Controlled values produce the expected reporting.

## Per-channel distinction

A deliberately weak red channel must show a much higher red near-floor fraction than green/blue.

## Original-versus-corrected semantics

Construct:

```text
input red near floor
+
large red global gain
```

Verify reporting retains:

- the original red near-floor fraction,
- the correction gain,
- output range behavior.

Do not let the corrected red distribution overwrite the source recoverability evidence.

## Gain reporting

Known gray-world / white-patch synthetic cases report the expected gains.

## No fake SNR

No value is introduced or labeled as SNR/noise variance.

---

# 21. CLAHE tests

Add focused tests for:

## Non-mutation

Input unchanged.

## Metadata preservation

Existing metadata remains available.

## Linear-light public contract

Input/output remain ordinary project linear-RGB `Frame`s.

Temporary representations such as:

- luminance,
- L*,
- uint16,

must not leak into the public frame representation.

## Neutral preservation

For a neutral ramp:

```text
R = G = B
```

the result remains neutral within numerical tolerance.

## Low-contrast improvement

Construct a spatial low-contrast pattern.

Verify local tonal separation increases meaningfully.

Do not test against a subjective aesthetic target.

## Dark-gradient precision

Use a smooth dark gradient representative of underwater shadows.

Verify the implementation:

- actually uses uint16,
- does not accidentally reduce the signal to 8-bit,
- does not create gross quantization/banding.

## Near-black reconstruction

For:

```text
Y ≈ 0
```

verify:

- stable output,
- no huge gain,
- no NaN,
- no Inf.

## Chromatic preservation

On controlled colored regions, CLAHE should primarily alter luminance rather than create large unintended hue shifts.

Do not demand mathematically exact chromaticity preservation if temporary control-domain bounding makes that impossible; establish a sensible tolerance.

## Range behavior

Temporary and final out-of-range behavior remains visible/understood.

---

# 22. Pipeline / ablation tests

Keep this bounded.

Verify:

## Ordering

```text
--pipeline white_patch clahe
```

executes:

```text
white_patch
then
clahe
```

## Ablation

```text
--pipeline white_patch clahe --no-clahe
```

executes white-patch only.

## Gray-world ablation

Verify `--no-gray-world` skips an explicitly requested gray-world stage.

## White-patch ablation

Verify `--no-white-patch`.

## CLAHE ablation

Verify `--no-clahe`.

## Backward compatibility

```text
--method gray_world
```

behaves like the equivalent single-stage pipeline.

## Ambiguous CLI

Supplying both:

```text
--method ...
--pipeline ...
```

fails clearly.

## Metadata order

Per-stage metadata remains attributable to the correct stage after composition.

Do not create a huge combinatorial CLI test matrix.

---

# 23. Resolve control

DaVinci Resolve grading remains a manual human reference outside the codebase.

Do not implement:

- Resolve scripting,
- Resolve APIs,
- LUT generation,
- automatic Resolve integration.

If controlled chart footage / Resolve reference is not yet available, record:

```text
Resolve control: pending acquisition/reference
```

in `LOG.md`.

This does not block completing the Week 2 code gate.

---

# 24. Frozen test-set evaluation

After unit/synthetic tests pass, evaluate representative configurations on the existing frozen local footage.

At minimum, where runtime is reasonable:

```text
input / none
gray_world
white_patch
clahe
gray_world -> clahe
white_patch -> clahe
```

Do not assume more stages means better output.

---

# 25. Evaluation scope stop rule

This phase is **not another broad empirical study**.

Run enough frozen real-footage evaluation to:

- verify every pipeline configuration executes correctly,
- expose obvious white-patch failure modes,
- expose obvious CLAHE failure modes,
- confirm the frozen Phase 2B temporal evaluator behaves unchanged across correction configurations,
- populate one useful Week 2 baseline comparison,
- verify flow/illumination evaluator reuse across configurations.

Do not respond to mediocre baseline results by:

- expanding frame ranges,
- adding more clips,
- changing white-patch percentile/statistics,
- tuning CLAHE,
- introducing new baseline algorithms,
- repeating parameter sweeps,
- reopening optical flow,
- inventing new metrics,
- modifying Phase 2B thresholds/status semantics.

These are controls.

They are expected to be limited.

---

# 26. Record per configuration

Where applicable, record:

- active pipeline,
- ablated stages,
- original per-channel near-floor fractions,
- original per-channel upper-bound fractions,
- gray-world / white-patch gains,
- post-correction out-of-range fraction,
- chart ΔE00 if actual chart reference exists,
- raw MC-Warp@1,
- raw MC-Warp@4,
- raw MC-Warp@8,
- canonical illumination-aware MC-Warp@1,
- canonical illumination-aware MC-Warp@4,
- canonical illumination-aware MC-Warp@8,
- alignment-robust companion if present,
- uncompensated residual,
- motion-reduction ratio,
- temporal ΔE00,
- valid coverage,
- Phase 2B confound/status output.

If chart footage remains unavailable:

> report chart ΔE00 as unavailable/pending.

Do not fabricate proxy color ground truth.

---

# 27. Visual inspection

## White-patch

Inspect for:

- extreme red gain,
- clipping/range violations,
- failure when no plausible bright neutral reference exists,
- near/far inconsistency,
- amplification of a source red channel that was near the floor,
- domination by specular/bubble/light regions.

## CLAHE

Inspect for:

- noise amplification,
- marine-snow/particle exaggeration,
- halos,
- excessive local contrast,
- shadow artifacts,
- banding,
- hue shifts,
- saturation changes,
- tile-boundary artifacts.

## Combined pipelines

Inspect whether CLAHE merely makes a flawed color correction look punchier.

Do not call that improved restoration automatically.

Keep:

```text
contrast improvement
```

distinct from:

```text
color fidelity / physical restoration
```

---

# 28. LOG.md

Update `LOG.md`.

Record:

## White-patch

- exact bright-region estimator,
- percentile/selection rule,
- aggregation statistic,
- gain calculation,
- zero-safety behavior,
- out-of-range behavior,
- observed failures.

## CLAHE

- luminance definition,
- perceptual lightness representation,
- inverse transform,
- uint16 pathway,
- clip limit,
- tile grid,
- near-black policy,
- RGB reconstruction method,
- range handling.

## Signal diagnostics

- near-floor threshold,
- upper-bound/saturation definition,
- original-versus-corrected interpretation,
- what the values do and do not mean.

Explicitly record:

> No robust SNR/noise estimate is implemented yet; this remains deferred until suitable controlled flat/chart regions exist.

## Pipeline

- ordered composition behavior,
- ablations,
- backward compatibility,
- metadata handling.

## Evaluation reuse

Record that:

- optical flow is derived from original input,
- the same correspondence is reused across correction configurations,
- original-derived illumination transforms are reused where applicable,
- correction variants do not change the evaluator.

## Evaluation

For each configuration record:

- active stages,
- signal diagnostics,
- gains,
- range behavior,
- established temporal/color metrics,
- visual observations,
- surprises.

Do not declare one global winner from one clip.

---

# 29. Repository discipline

Do not:

- modify `CLAUDE.md`,
- modify `PLAN.md`,
- redesign Phase 2A optical flow,
- redesign Phase 2B metrics,
- alter illumination-aware metric semantics,
- alter Phase 2B estimator/guards/status bands,
- alter validity/coverage semantics,
- implement sophisticated SNR estimation,
- implement denoising,
- implement depth,
- implement refractive geometry,
- implement backscatter,
- implement attenuation,
- implement temporal correction,
- add learned models,
- add placeholder future CLI flags,
- build a generic image-processing framework,
- run white-patch parameter sweeps,
- run CLAHE hyperparameter sweeps,
- commit local footage,
- silently overwrite source media or prior experiment outputs.

Keep this phase mechanical and bounded.

---

# Before finishing

Run all relevant tests and verify:

- Week 1 tests pass,
- Phase 2A tests pass,
- Phase 2B tests pass,

## White-patch

- white-patch does not mutate input,
- metadata survives,
- gains are recorded,
- estimator is deterministic,
- isolated pathological maxima do not defeat the intended robust rule,
- zero/near-zero estimates are handled safely,
- range violations remain visible,

## Signal diagnostics

- per-channel near-floor fractions are correct,
- per-channel upper-bound fractions are correct,
- original/source near-floor information is retained after correction,
- correction gains are reported,
- post-correction out-of-range behavior is reported,
- no bogus SNR/noise metric exists,

## CLAHE

- CLAHE does not independently equalize RGB,
- CLAHE uses a documented scalar perceptual-lightness representation,
- CLAHE uses uint16 rather than uint8 internally,
- CLAHE returns floating linear RGB,
- temporary bounded control representations do not leak into the public `Frame`,
- neutral inputs remain neutral,
- low-contrast separation increases,
- dark-gradient tests detect gross quantization loss,
- near-black reconstruction is safe,
- chromatic shifts remain bounded,
- range behavior remains visible,

## Pipeline

- stages execute in requested order,
- `--no-gray-world` works,
- `--no-white-patch` works,
- `--no-clahe` works,
- old `--method` behavior remains backward-compatible,
- `--method` and `--pipeline` cannot ambiguously coexist,
- gray-world and white-patch are not automatically stacked,
- stage metadata remains attributable,

## Frozen evaluator

- Phase 2B metric definitions are unchanged,
- Phase 2B thresholds/guards/status semantics are unchanged,
- raw MC-Warp remains visible,
- canonical illumination-aware MC-Warp remains visible,
- alignment-robust companion remains unchanged if present,
- uncompensated residual remains visible,
- motion-reduction ratio remains visible,
- temporal ΔE00 semantics are unchanged,
- coverage/status semantics are unchanged,
- illumination-confounded footage remains identified according to Phase 2B behavior,
- optical flow is not recomputed separately for each correction configuration when the same original pair is being evaluated,
- original-derived illumination transforms are reused across correction configurations where applicable,

## Scope

- no `--no-temporal` exists,
- no future-stage flags were added,
- no Week 3 code exists,
- no SNR/noise estimator was invented,
- `CLAUDE.md` and `PLAN.md` remain unchanged,
- local footage is not staged.

---

# Final summary

Provide:

## 1. White-patch

- exact bright-region estimator,
- selected percentile/region rule,
- aggregation statistic,
- gain formula,
- numerical safeguards,
- metadata,
- range behavior,
- known limitations.

## 2. Signal diagnostics

- near-floor definition and threshold,
- upper-bound/saturation definition,
- source-versus-corrected interpretation,
- correction-gain reporting,
- out-of-range reporting,
- example interaction between source near-floor signal and large gain,
- explicit statement that robust SNR/noise characterization remains deferred.

## 3. CLAHE

- luminance definition,
- perceptual lightness transform,
- uint16 pathway,
- clip limit,
- tile-grid size,
- inverse transform,
- near-black policy,
- RGB reconstruction,
- range handling,
- known limitations.

## 4. CLI / pipeline

- `--pipeline`,
- `--method` compatibility,
- ablation behavior,
- execution ordering,
- active-stage reporting,
- metadata behavior.

## 5. Evaluation reuse

Explain exactly how:

- flow derived from original input is reused across correction configurations,
- validity masks are reused,
- input-derived illumination transforms are reused where applicable,
- this prevents both wasted inference and evaluator drift between pipelines.

## 6. Tests

- tests added,
- total test result,
- important numerical assumptions/tolerances,
- any edge case that required special handling.

## 7. Frozen test-set evaluation

For each evaluated configuration report:

- active pipeline,
- ablations,
- original signal diagnostics,
- gains,
- post-correction range behavior,
- chart ΔE00 if available,
- raw MC-Warp@1/@4/@8,
- canonical illumination-aware MC-Warp@1/@4/@8,
- alignment-robust companion if present,
- uncompensated residual,
- motion-reduction ratio,
- temporal ΔE00,
- valid coverage/status,
- illumination-confound interpretation,
- visual observations.

Do not declare a global winner unless the evidence actually supports one.

The goal is to understand what each simple baseline buys and what it breaks.

## 8. Repository changes

- files created,
- files modified,
- tests added,
- diagnostic artifacts generated.

## 9. Pending acquisition-dependent work

Explicitly record, if still unavailable:

- GoPro Flat/RAW calibration,
- controlled Keldan/chart footage,
- robust SNR/noise characterization,
- DaVinci Resolve chart control.

These acquisition-dependent tasks do **not** justify:

- inventing proxy ground truth,
- building speculative code,
- blocking completion of the Week 2 engineering gate.

---

This completes Week 2 when the project can answer:

> Given two implemented correction configurations, how do they differ in color behavior, local contrast, temporal stability, source-signal usage, clipping/range behavior, and attributable stage contribution?

Do not begin Week 3.