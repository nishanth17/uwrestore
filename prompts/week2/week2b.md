# Week 2 Phase 2B — Real Temporal Stability Metric

Read `CLAUDE.md`, `PLAN.md`, `LOG.md`, the current repository, and:

```text
experiments/week2a_flow/FINDINGS.md
```

including the full `@1/@4/@8` lag-study addendum and its generated artifacts.

Do not modify `CLAUDE.md` or `PLAN.md`.

The selected canonical optical-flow backend for this phase is:

```text
SEA-RAFT-M
```

---

# Backend selection context

Phase 2A evaluated:

- SEA-RAFT-M,
- WAFT-a1,
- FlowIt-M,
- VideoFlow-MOF,

on the frozen underwater test set at a common 960×540 evaluation grid, including direct correspondence at lags:

```text
@1
@4
@8
```

SEA-RAFT-M is selected as the **canonical Phase 2B correspondence backend**.

The selection is based on measured project-specific evidence:

- deterministic on the current MPS environment,
- approximately `0.75 s/inference`,
- approximately `2.2 GB` peak MPS allocation,
- remained usable at direct `@4` and `@8`,
- broadly similar aggregate motion-compensated residuals to more expensive models,
- equal-or-better than WAFT in **14/15 clip-lag cells** when both were evaluated on the intersection of their validity masks,
- largest meaningful common-mask advantage at `swimthrough @8`, approximately 100 px displacement:
  - SEA-RAFT: `5.615×`
  - WAFT: `5.043×`
  - approximately 11% advantage.

Known limitation:

SEA-RAFT can conservatively invalidate substantial regions of smooth independently moving subjects such as the eel body.

Mean valid coverage in the lag study fell approximately:

```text
@1   97%
@4   91%
@8   83%
```

Therefore valid coverage is part of the temporal result and must always remain visible.

## Other backends

**WAFT-a1** remains an optional manual cross-check only.

Do not:

- run WAFT automatically during normal scoring,
- average SEA-RAFT and WAFT,
- silently switch to WAFT,
- define a combined-backend metric.

If a specific SEA-RAFT result looks suspicious, WAFT may be run manually as a second opinion.

When comparing backends, score them on the **intersection of their validity masks**, as established in:

```text
experiments/week2a_flow/scripts/common_mask_compare.py
```

because backend-specific residuals computed on different valid pixels are not directly comparable.

**VideoFlow-MOF** remains research-only and `@1`-only for cases such as bubbles/transient non-rigid structure. It is not appropriate as the canonical multi-lag backend: on low-texture `murky_shark`, coverage collapsed from approximately 95% at `@1` to approximately 63% at `@4/@8`.

**FlowIt-M** is dropped:

- non-deterministic on the current MPS environment,
- identical inference changed forward flow by up to `0.858 px`,
- approximately `6.5%` of the FB validity mask could flip,
- approximately 40–50× SEA-RAFT runtime,
- approximately `22.8 GB` peak MPS allocation,
- no meaningful large-displacement advantage at `@8`.

Treat optical-flow backend selection as closed.

Do not reopen it because:

- a newer paper exists,
- a model ranks higher on Sintel,
- another implementation is interesting.

Reopen only if SEA-RAFT causes a **specific observed correctness failure that prevents this metric from functioning**.

The remaining research question is the metric definition.

---

# Goal

Replace Week 1's placeholder temporal-stability metric with a trustworthy motion-aware temporal evaluation suitable for regression testing future restoration stages.

The metric system must answer:

> After accounting for legitimate scene/camera motion and simple illumination/exposure variation already present in the source, did our processing cause the same physical scene content to change unexpectedly over time?

This phase implements **measurement only**.

Do not implement:

- temporal correction,
- output smoothing,
- parameter stabilization,
- frame blending,
- recurrent restoration,
- learned temporal restoration,
- depth,
- backscatter removal,
- attenuation inversion.

Do not begin Week 3.

---

# 1. Metric outputs — preserve raw evidence and define a canonical regression metric

Phase 2A established an important distinction.

A raw motion-compensated photometric residual is useful and interpretable, but it is **not sufficient by itself as the canonical temporal regression metric**.

The artificial-lights clip proves this:

```text
motion-compensation reduction:

@1   ~1.14×
@4   ~1.07×
@8   ~1.02×
```

and this behavior was essentially identical across all tested flow backends.

At `@8`, geometric alignment explains only approximately 2% of the frame-to-frame difference because the camera-mounted light changes the radiance of correctly aligned surfaces.

Therefore implement and report separately:

## A. Raw MC-Warp@k

The ordinary validity-masked motion-compensated photometric residual after geometric alignment.

Purpose:

> Show the actual remaining linear-light photometric difference after motion compensation.

This remains a first-class diagnostic.

## B. Canonical illumination-aware MC-Warp@k

A bounded illumination-aware version intended to serve as the temporal **regression metric**.

It must account only for simple legitimate illumination/exposure variation inferred from the **aligned original input frames**.

It must not fit the corrected output.

## C. Uncompensated residual@k

Residual between the two corresponding frames without geometric warping.

## D. Motion-compensation reduction ratio@k

Report:

```text
uncompensated residual / raw MC-Warp
```

for the same pair, lag, resolution, and evaluation domain.

This is descriptive normalization.

It does **not** replace the raw residual or canonical illumination-aware metric.

## E. Valid coverage@k

Coverage is part of the result, not auxiliary metadata.

For every lag, report all relevant values together.

Do not collapse them into one score.

---

# 2. Correspondence estimation

Optical flow must be estimated exclusively from the **original input sequence**.

The corrected/restored output must not influence correspondence.

Conceptually:

```text
original frame t
        +
original frame t+k
        |
        v
     SEA-RAFT-M
        |
        v
direct correspondence t -> t+k
        |
        v
validity / occlusion mask
        |
        +----------------------------+
        |                            |
        v                            v
warp original t+k             warp corrected t+k
into frame-t coords           into frame-t coords
```

SEA-RAFT may internally convert the project's linear-light `Frame` into the temporary encoded model-input representation established in Phase 2A.

That representation exists **only for correspondence estimation**.

All temporal appearance measurements must operate on the project's linear-light image values or established color-science representations derived from them.

Use SEA-RAFT only through the existing Phase 2A optical-flow abstraction.

Do not import the concrete model directly into `uw/metrics.py`.

---

# 3. Raw MC-Warp formulation

Implement an explicit function such as:

```python
temporal_warp_error(...)
```

Do not retain the generic Week 1 `temporal_stability()` name for a specific measurement.

Use a recognizable motion-compensated photometric residual such as:

- L1,
- Charbonnier,

with a clear justification.

Prefer simplicity and interpretability.

Do not silently redefine MC-Warp as:

- SSIM,
- LPIPS,
- census,
- NCC,
- a learned score.

## Requirements

Raw MC-Warp must:

- use direct flow correspondence,
- exclude invalid/occluded pixels,
- normalize over valid pixels only,
- operate consistently across RGB channels,
- compare **linear-light RGB**,
- not use the model-input sRGB representation,
- not silently clip values,
- explicitly handle non-finite values,
- expose insufficient/poor coverage rather than hiding it.

---

# 4. Multi-lag evaluation

Implement:

```text
MC-Warp@1
MC-Warp@4
MC-Warp@8
```

Interpretation:

- `@1`: rapid/high-frequency flicker,
- `@4`: medium-term instability,
- `@8`: slower pumping/drift.

## Direct-flow requirement

For each lag estimate correspondence directly:

```text
@1: t -> t+1
@4: t -> t+4
@8: t -> t+8
```

Do not chain:

```text
t -> t+1 -> t+2 -> ...
```

Chaining contaminates the metric with:

- repeated interpolation,
- accumulated flow error,
- accumulated occlusion error,
- resampling drift.

If direct inference unexpectedly proves unsupported, stop that path and document why rather than silently substituting chained flow.

---

# 5. Coverage semantics and reliability

The lag study demonstrated that coverage falls materially with lag.

Coverage must therefore be treated as part of the measurement result.

For each lag report:

```text
score
coverage
status / interpretation
```

Do not allow:

> lower error because more difficult pixels were excluded

to be interpreted as an improvement.

## Threshold policy

Do not tune a minimum valid-coverage threshold against the frozen real clips to make results look cleaner.

If the implementation requires a hard threshold:

- justify it independently,
- use a conservative predeclared rule or synthetic behavior,
- record it,
- keep the underlying score and coverage available.

Otherwise prefer returning:

```text
value
coverage
reliability/status
```

rather than silently deleting results.

At longer lags, low overlap or large disocclusion may make a numeric value weakly informative without making it mathematically impossible to compute.

Preserve that distinction.

## Backend comparisons

If WAFT is manually used as a cross-check, compare SEA-RAFT and WAFT only on their common valid-mask intersection.

Never rank two backends using residuals computed on different sets of pixels.

---

# 6. Input-baseline reporting

Evaluate the same raw motion-compensated quantities on the unprocessed input sequence.

Report:

```text
input raw MC-Warp@k
corrected raw MC-Warp@k
```

using the same correspondence and validity mask.

Also report the corresponding uncompensated residual and reduction ratio.

The input residual contains a mixture of:

- genuine illumination changes,
- caustics,
- particles,
- moving animals,
- exposure/WB behavior already encoded by the camera,
- imperfect correspondence,
- interpolation error,
- true scene changes.

Therefore:

Do not assume input MC-Warp should be zero.

Do not blindly compute:

```text
corrected - input
```

and label it restoration instability.

Report both first.

---

# 7. Canonical illumination-aware MC-Warp

Phase 2A established that legitimate illumination variation is the largest known confound of raw MC-Warp.

Implement **one bounded illumination-aware formulation** suitable for regression use.

## Critical anti-gaming invariant

Illumination compensation parameters must be inferred only from:

```text
aligned ORIGINAL input frame t
aligned ORIGINAL input frame t+k
```

Never fit illumination parameters using corrected/restored frames.

Otherwise a restoration could generate temporal flicker and then help the evaluator fit that flicker away.

Conceptually:

```text
original t
    +
warped original t+k
        |
        v
infer legitimate illumination/exposure transform
        |
        v
freeze transform parameters
        |
        +-----------------------------+
                                      |
corrected t                           |
    +                                 |
warped corrected t+k -----------------+
        |
        v
canonical illumination-aware residual
```

The corrected sequence is **judged**, never used to define the judge.

---

# 8. Illumination model — bounded search

Start with a robust low-dimensional model.

First candidate:

```text
I_t ≈ a * warped(I_t+k) + b
```

Prefer a luminance/global model unless the data clearly requires another equally low-capacity representation.

Estimate parameters robustly over valid aligned input pixels.

Protect the fit from:

- highlights,
- bubbles,
- marine snow,
- clipping,
- extreme outliers.

Record:

- model type,
- fitted parameters,
- fitting domain,
- robust estimator,
- fraction/domain used,
- reduction of input residual.

## Falsification criteria

Test on:

1. synthetic pure global gain,
2. synthetic gain+bias,
3. corrected-only red-channel flicker,
4. synthetic localized illumination,
5. real `lights` footage.

The model is acceptable only if:

- it removes much of a legitimate simple global illumination change,
- it does **not** fit away corrected-only color flicker,
- its limitations are obvious on localized illumination.

## One alternative allowed

If global/luminance gain-bias fails the `lights` falsification test in a meaningful way, you may investigate **one** alternative bounded photometric formulation, for example:

- gradient-domain residual,
- census-style photometric representation,
- locally normalized correlation/normalization.

Only do this if gain/bias demonstrably fails.

Do not conduct a metric zoo.

Do not implement:

- dense local illumination fields,
- per-pixel gains,
- neural illumination decomposition,
- high-order spatial models,
- learned photometric compensation.

If neither simple approach can adequately model the camera-mounted-light case:

> explicitly mark that clip/region `illumination-confounded`.

That is a valid result.

Do not hide the limitation by escalating complexity.

---

# 9. Raw versus canonical reporting

The canonical illumination-aware metric must not cause the raw photometric evidence to disappear.

For every applicable lag report separately:

```text
Raw MC-Warp
Canonical illum-aware MC-Warp
Uncompensated residual
Motion reduction ratio
Valid coverage
```

The user should be able to see:

> raw appearance changed a lot, but most was explainable by legitimate source illumination

or:

> raw appearance changed a lot and the simple source illumination model could not explain it

or:

> corrected output changed more than the original-derived illumination transform predicts.

Do not merge these into one master number.

---

# 10. Alignment sensitivity

Photometric warping residual is sensitive to small registration errors around:

- coral edges,
- fish boundaries,
- thin ropes,
- chart edges,
- particles,
- high-contrast lighting boundaries.

Explicitly characterize this.

## Fractional-pixel synthetic test

Create known subpixel translation, for example:

```text
x = 0.5 px
y = 0.25 px
```

or another controlled non-integer translation.

Measure residual caused solely by:

- interpolation,
- subpixel flow approximation,
- resampling,
- edge alignment.

Inspect residual maps.

## Optional alignment-robust companion

If this test demonstrates that canonical/raw MC-Warp is materially dominated by tiny alignment errors around high gradients, add at most **one** separately reported alignment-robust companion.

Potential examples:

- very small fixed low-pass,
- fixed local patch aggregation.

Requirements:

- separately named,
- never replaces raw or illumination-aware MC-Warp,
- parameters fixed globally,
- no per-clip tuning,
- must not make blur look artificially superior.

Do not add one unless the synthetic test justifies it.

---

# 11. Temporal ΔE00

Implement a separate flow-aligned temporal color diagnostic using the existing validated CIEDE2000 implementation.

Use an explicit name such as:

```python
temporal_delta_e(...)
```

Purpose:

> Detect color instability in corresponding scene content.

Important cases include:

- red-channel pumping,
- global WB oscillation,
- green/magenta drift,
- localized color flicker,
- future attenuation-parameter instability.

## Requirements

- use SEA-RAFT correspondence,
- use the same validity/occlusion mask,
- align corresponding content,
- use the existing linear RGB -> Lab path,
- reuse the existing CIEDE2000 implementation,
- handle invalid/non-finite pixels,
- justify any near-black exclusion.

Do not create a second ΔE implementation.

## Illumination caveat

Temporal ΔE00 is also sensitive to legitimate lighting changes.

Report input and corrected temporal ΔE where useful.

Do not claim high temporal ΔE on `lights` automatically implies restoration instability.

Do not create a separate elaborate illumination-invariant ΔE metric during this phase.

---

# 12. Synthetic validation suite

Build controlled tests demonstrating that every metric behaves as intended.

At minimum include:

## A. Stable integer translation

Same appearance, known integer translation.

Expected:

- low raw MC-Warp,
- low illumination-aware MC-Warp.

## B. Stable fractional translation

Same appearance, subpixel translation.

Expected:

- small nonzero error may remain,
- characterize it,
- inspect edge residuals.

## C. Global brightness/gain change

Expected:

- raw MC-Warp rises,
- illumination-aware metric drops substantially if gain is within model capacity.

## D. Global gain + bias

If the selected illumination model supports it:

- raw MC-Warp rises,
- canonical metric should explain most legitimate change.

## E. Corrected-only red-channel flicker

The original input remains temporally stable.

The simulated corrected output alternates red gain.

Expected:

- raw MC-Warp rises,
- temporal ΔE rises,
- input-derived illumination compensation **must not remove the flicker**.

This is a critical anti-gaming test.

## F. One-frame appearance/color spike

Expected:

- clear temporal spike.

## G. Blur

Demonstrate that blur may lower a temporal photometric score.

Do not interpret that as superior restoration.

This validates why spatial fidelity remains a separate evaluation axis.

## H. Occlusion / disocclusion

Create newly visible regions.

Expected:

- invalid regions excluded,
- denominator correct,
- coverage decreases appropriately.

## I. Localized illumination change

Create a moving/local light patch.

Expected:

- raw MC-Warp rises,
- global gain/bias explains only part,
- corrected-only flicker elsewhere remains detectable,
- limitation is surfaced rather than overfit.

## J. Coverage gaming

Construct two masks/results where one produces lower residual solely by excluding the difficult region.

Expected:

- reporting makes clear that the lower score came with reduced coverage,
- no helper function declares it globally superior.

Use synthetic tests to expose limitations.

Do not tune real-data thresholds until every case looks aesthetically nice.

---

# 13. Warping implementation correctness

Use `cv2.remap` for production image warping.

Do not implement production interpolation using:

- Python pixel loops,
- manual NumPy interpolation,
- `scipy.ndimage.map_coordinates`,

unless OpenCV proves unsuitable and the reason is documented.

The normative Phase 2A convention is:

```text
flow[y, x, 0] = u
flow[y, x, 1] = v

source pixel (x,y)
maps to
target (x+u, y+v)
```

`cv2.remap` requires absolute source-coordinate maps.

Derive the correct inverse/backward-sampling map from the documented convention.

Do not guess the sign.

## Requirements

Before `cv2.remap`:

```text
map_x
map_y
```

must be:

- correct shape,
- contiguous,
- `np.float32`.

Test explicitly for:

- sign errors,
- reversed direction,
- x/y swap,
- off-by-one errors,
- incorrect absolute-map construction,
- incorrect flow-vector scaling after resize,
- dtype promotion to float64,
- border behavior.

Use bilinear interpolation unless another choice is clearly justified.

Validity comes from explicit correspondence/occlusion logic, not from whether a warped pixel happened to contain a plausible value.

Do not accept visual plausibility as proof of warping correctness.

---

# 14. Resolution discipline

Follow Phase 2A's established common evaluation grid.

Default metric evaluation remains approximately:

```text
960×540
```

subject to orientation.

Record:

- source resolution,
- flow inference resolution,
- metric evaluation resolution.

Do not upsample flow to native 4K and imply native-detail correspondence.

If frames are resized:

- use one consistent method,
- keep it identical across pipeline configurations.

If flow is resized:

```text
u *= new_width / old_width
v *= new_height / old_height
```

Use the existing tested helper.

Do not revisit DPFlow/MEMFOF/high-resolution flow in this phase unless the implemented metric shows a concrete resolution-specific failure.

Fine-structure residual alone may be logged as a future trigger; do not expand scope.

---

# 15. Compute reuse

Optical-flow inference is expensive.

For each evaluated frame pair / lag:

- compute forward flow once,
- compute reverse flow once,
- reuse for:
  - FB consistency,
  - validity mask,
  - original-frame warping,
  - corrected-frame warping,
  - raw MC-Warp,
  - illumination-aware MC-Warp,
  - input baseline,
  - temporal ΔE,
  - reduction ratio,
  - residual visualizations,
  - diagnostics.

Do not rerun the flow model separately for each metric.

## Bounded memory

Reuse within the pair/evaluation lifecycle.

Do not retain unbounded flow history.

Do not:

- keep an entire long-video flow tensor set on GPU,
- retain GPU tensors after CPU/NumPy representations suffice,
- duplicate large fields in multiple unnecessary formats.

Release results once no pending metric/visualization needs them.

A small bounded cache or sliding lifecycle is sufficient.

---

# 16. Backend integration into project code

Phase 2A intentionally kept model-specific code under:

```text
experiments/week2a_flow/
```

Phase 2B now requires the selected SEA-RAFT backend to be usable by normal temporal scoring.

Promote only the minimum backend integration required.

Preserve:

- the `OpticalFlowBackend` abstraction,
- isolated heavyweight dependency handling,
- explicit checkpoint/config provenance.

Do not copy all experimental backends into production project code.

Do not make:

- WAFT,
- FlowIt,
- MOF

normal dependencies merely because their wrappers already exist.

The canonical metric path should require SEA-RAFT only.

If the cleanest implementation keeps SEA-RAFT in an optional isolated environment rather than contaminating the core `.venv`, preserve that architecture and document the invocation.

Do not add all optical-flow ML dependencies to the lightweight project core without a strong reason.

---

# 17. API design

Replace/deprecate Week 1's placeholder cleanly.

Prefer a small structured result.

Conceptually:

```python
@dataclass
class TemporalLagMetrics:
    lag: int

    raw_warp: float | None
    illumination_aware_warp: float | None
    uncompensated: float | None
    motion_reduction_ratio: float | None

    temporal_delta_e: float | None

    valid_fraction: float
    status: str | None
```

and perhaps:

```python
@dataclass
class TemporalMetrics:
    lag1: TemporalLagMetrics | None
    lag4: TemporalLagMetrics | None
    lag8: TemporalLagMetrics | None
```

If an alignment-robust diagnostic is justified, add it minimally.

The exact schema is not prescribed.

Do not add:

- generic metric registries,
- plugin frameworks,
- unused future fields,
- unnecessary class hierarchies.

---

# 18. CLI / `uw score`

Update `uw score` so the temporal report is explicit.

Conceptually:

```text
Temporal consistency
--------------------

@1
  Raw MC-Warp:                    ...
  Illum-aware MC-Warp:            ...
  Uncompensated residual:         ...
  Motion reduction:               ...x
  Temporal ΔE00:                  ...
  Valid coverage:                 ...
  Status:                         ...

@4
  Raw MC-Warp:                    ...
  Illum-aware MC-Warp:            ...
  Uncompensated residual:         ...
  Motion reduction:               ...x
  Temporal ΔE00:                  ...
  Valid coverage:                 ...
  Status:                         ...

@8
  Raw MC-Warp:                    ...
  Illum-aware MC-Warp:            ...
  Uncompensated residual:         ...
  Motion reduction:               ...x
  Temporal ΔE00:                  ...
  Valid coverage:                 ...
  Status:                         ...

Input baseline
--------------
...
```

Also expose illumination fitting information where useful:

```text
Illumination model:
  type: ...
  gain: ...
  bias: ...
  input residual explained: ...
  illumination-confounded: yes/no
```

If alignment-robust MC-Warp was justified, report it separately.

Do not produce:

```text
overall temporal score = ...
```

or any weighted combination.

Keep clearly distinct:

- raw MC-Warp,
- canonical illumination-aware MC-Warp,
- reduction ratio,
- temporal ΔE,
- valid coverage,
- chart ΔE.

---

# 19. Real test-set evaluation

After synthetic tests pass, evaluate representative frozen footage.

At minimum include:

- `swimthrough`,
- `murky_eel` or equivalent particulate/moving-animal case,
- `murky_shark`,
- `lights`,
- `distance`.

Keep excerpts bounded.

Reuse the Phase 2A selected ranges where appropriate so interpretation is connected to the existing findings.

For every evaluated clip record:

- frame range,
- source resolution,
- inference resolution,
- metric resolution,
- backend,
- raw MC-Warp@1/4/8,
- canonical illumination-aware MC-Warp@1/4/8,
- uncompensated residual@1/4/8,
- reduction ratios,
- valid coverage,
- temporal ΔE,
- input values,
- fitted illumination parameters,
- confound status.

Generate selected residual visualizations.

Inspect rather than trusting aggregate numbers.

---

# 20. Required `lights` analysis

The artificial-light case is a mandatory falsification target.

Phase 2A measured:

```text
raw motion-reduction:

@1   1.14×
@4   1.07×
@8   1.02×
```

The result was backend-independent.

Evaluate whether the selected simple illumination model changes the interpretation.

Determine explicitly:

## Case A — simple model works

If input-derived global/luminance gain-bias substantially explains the legitimate source variation without suppressing synthetic corrected-only flicker:

- retain it as the canonical illumination-aware formulation,
- report raw and canonical values separately.

## Case B — simple model fails because illumination is spatially local

Exercise the one allowed alternative bounded photometric representation.

## Case C — bounded approaches still fail

Label:

```text
illumination-confounded
```

Do not escalate further in Week 2.

A canonical metric is allowed to say:

> unreliable for this clip because local source illumination violates its model.

That is preferable to a deceptively clean number.

---

# 21. Near-static murky analysis

`murky_shark` deserves explicit inspection because Phase 2A found:

- very little frame-to-frame camera motion,
- high FB self-consistency,
- substantial cross-backend disagreement relative to motion magnitude.

At `@1`, warping provides little benefit.

At longer lag it becomes more meaningful.

Verify that the final metric does not produce a misleading confidence story merely because FB coverage is high.

Document:

> FB consistency means the field is self-consistent, not proven correct.

Do not add another flow model merely because this ambiguity exists.

---

# 22. No temporal correction

Do not add:

```text
--no-temporal
```

because no temporal correction stage exists.

Do not implement:

- EMA,
- smoothing,
- parameter stabilization,
- temporal frame blending,
- optical-flow-guided output modification,
- recurrent correction,
- learned temporal modules.

This phase only builds the evaluator.

---

# 23. LOG.md

Update `LOG.md` after completion.

Record:

## Backend

- SEA-RAFT-M,
- exact checkpoint/config,
- evaluation resolution,
- known limitations.

## Raw MC-Warp

- residual formulation,
- masking,
- direction,
- lags.

## Canonical illumination-aware metric

- exact model/formulation,
- fitting procedure,
- robust estimation method,
- anti-gaming rule,
- falsification results.

## Normalization

- uncompensated residual,
- reduction-ratio definition,
- interpretation limitations.

## Coverage

- per-lag coverage,
- status/reliability behavior,
- no coverage gaming.

## Alignment

- fractional-pixel result,
- whether robust companion was required.

## Temporal ΔE

- definition,
- masks,
- interpretation.

## Synthetic validation

Record all cases and measured results.

## Real clips

Record all metrics and qualitative observations.

Explicitly distinguish:

```text
correspondence uncertainty
vs
legitimate illumination variation
vs
restoration-induced instability
```

Document what remains ambiguous.

---

# 24. Repository discipline

Do not:

- modify `CLAUDE.md`,
- modify `PLAN.md`,
- reopen optical-flow research,
- integrate more flow models,
- add a generic metric framework,
- build a spatial illumination-estimation system,
- implement robust sensor/SNR work,
- begin Week 3 depth,
- begin Sea-thru,
- implement temporal correction,
- commit local footage,
- silently overwrite diagnostic outputs.

Preserve the project's existing data-safety rules.

---

# Before finishing

Run all relevant tests and verify:

- all Week 1 tests pass,
- all Phase 2A flow tests pass,
- SEA-RAFT integration preserves the normative coordinate convention,
- integer-motion synthetic sequence has low raw MC-Warp,
- fractional-pixel behavior is explicitly characterized,
- pure brightness/gain change raises raw MC-Warp,
- legitimate input-derived gain/bias is reduced by the canonical illumination-aware formulation,
- corrected-only red flicker remains detectable,
- input-derived illumination fitting does not use corrected frames,
- one-frame spike is detected,
- localized illumination is not falsely solved by a global model,
- the one-alternative limit was respected if gain/bias failed,
- occlusion/disocclusion masks behave correctly,
- coverage gaming is exposed,
- blur is not declared a superior restoration,
- original input drives correspondence,
- original input drives illumination estimation,
- corrected frames are used only for evaluation,
- linear-light RGB is used for photometric residuals,
- temporal ΔE reuses the existing validated CIEDE2000 path,
- `@4` and `@8` use direct flow,
- no adjacent-flow chaining exists,
- coverage is reported at every lag,
- raw residual remains visible alongside canonical illumination-aware residual,
- uncompensated residual is reported,
- reduction ratio is reported,
- no cross-backend residual comparison uses differing masks,
- `cv2.remap` mapping is explicitly tested,
- remap coordinate arrays are contiguous `np.float32`,
- resized flow vectors scale correctly,
- inference is reused,
- cache/memory use is bounded,
- no weighted overall score exists,
- no temporal correction or `--no-temporal` was added,
- `CLAUDE.md` and `PLAN.md` remain unchanged,
- no local footage is staged/committed.

---

# Final summary

Provide a detailed summary with:

## 1. Backend integration

- SEA-RAFT-M integration path,
- checkpoint/config,
- dependency/environment handling,
- runtime/memory where observed,
- known correspondence limitations.

## 2. Raw MC-Warp

- exact formula,
- residual type,
- flow/warp direction,
- mask,
- resolution,
- coverage semantics.

## 3. Canonical illumination-aware MC-Warp

- exact formulation,
- illumination model,
- fitting procedure,
- robust estimator,
- why it was chosen,
- anti-gaming behavior,
- whether a second bounded formulation was required.

## 4. Normalized/context metrics

For each lag explain:

- uncompensated residual,
- raw MC-Warp,
- motion-reduction ratio,
- canonical illumination-aware MC-Warp,
- coverage.

Explain what each does and does not mean.

## 5. Alignment sensitivity

- fractional-pixel results,
- residual-map observations,
- whether an alignment-robust companion was justified.

## 6. Temporal color

- temporal ΔE00 definition,
- input versus corrected interpretation,
- illumination caveat.

## 7. Synthetic tests

Report results for:

- integer translation,
- fractional translation,
- global gain,
- gain+bias,
- corrected-only red flicker,
- one-frame spike,
- blur,
- occlusion/disocclusion,
- localized illumination,
- coverage gaming.

## 8. Real footage

For each clip:

- raw input MC-Warp@1/4/8,
- raw corrected MC-Warp@1/4/8,
- canonical illumination-aware values,
- uncompensated residual,
- motion-reduction ratio,
- temporal ΔE,
- valid coverage,
- illumination-fit parameters,
- illumination-confounded status,
- qualitative residual observations.

Explicitly discuss:

- `lights`,
- `murky_shark`,
- bubbles/particles,
- moving animals,
- long-lag coverage.

## 9. Known limitations

Be explicit about:

- FB self-consistency not implying correctness,
- low-texture ambiguity,
- moving particles,
- bubbles,
- smooth moving subjects,
- subpixel interpolation,
- localized illumination,
- camera exposure/WB changes,
- long-lag overlap,
- blur gaming,
- resolution limits,
- anything the bounded illumination model cannot explain.

## 10. Repository changes

- files created,
- files modified,
- tests added,
- diagnostic artifacts generated.

Do not begin Phase 2C/2D.

Do not begin Week 3.