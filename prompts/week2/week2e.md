# Bounded Research Session — Long-Duration Temporal Stability Diagnostics

Read first:

```text
CLAUDE.md
PLAN.md
LOG.md
experiments/week2a_flow/FINDINGS.md
experiments/week2b_temporal/FINDINGS.md
```

Also inspect the existing Phase 2B temporal-evaluation implementation only as needed to understand its exact semantics.

This is a **research-only session**.

Do not modify implementation code.

Do not modify:

```text
CLAUDE.md
PLAN.md
LOG.md
```

Do not install models or dependencies.

Do not run a new optical-flow bakeoff.

Do not implement a new metric.

Do not reopen Phase 2B.

Do not begin Phase 2C/2D or Week 3.

The goal is only to answer:

> Does the project have a meaningful temporal-evaluation blind spot that justifies investigating one additional long-duration diagnostic in Week 8?

---

# Context — frozen Phase 2B evaluator

Assume the implemented temporal-evaluation stack is frozen and includes:

## Correspondence

Canonical:

```text
SEA-RAFT-M
```

Optional manual cross-check:

```text
WAFT-a1
```

Research shelf:

```text
VideoFlow-MOF @1 only
```

Dropped:

```text
FlowIt-M
```

Correspondence is estimated from the ORIGINAL input footage, never from corrected output.

---

## Temporal appearance metrics

The project already reports:

```text
raw MC-Warp@1
raw MC-Warp@4
raw MC-Warp@8
```

using linear-light RGB L1 over the valid flow-aligned region.

It also reports:

```text
canonical illumination-aware MC-Warp@1/@4/@8
```

using a bounded global input-derived luminance gain/bias fit.

The illumination transform is fitted only from aligned ORIGINAL frames and frozen before evaluating corrected output.

---

## Existing supporting diagnostics

Also already implemented:

```text
uncompensated residual
motion-reduction ratio
valid correspondence coverage
status / illumination-confound reporting
flow-aligned temporal ΔE00
alignment-robust warp companion
input temporal baseline
```

There is no weighted master score.

Coverage always remains visible.

---

# Phase 2B findings that matter for this research

Treat these as measured project facts.

## 1. Fixed-lag aliasing exists

A periodic oscillation can be invisible when a lag lands on the same oscillation phase.

A synthetic period-2 case demonstrated:

```text
@1  -> visible
@2  -> invisible
@4  -> invisible
```

Therefore:

```text
@1/@4/@8
```

does not mathematically guarantee detection of arbitrary periodic instability.

This is currently a **known mathematical blind spot**, not yet a demonstrated real long-duration restoration failure.

---

## 2. Phase 2B did not test long-duration behavior

Phase 2B used bounded excerpts and a few nearby anchor triples.

It established:

- exact implementation repeatability,
- useful sensitivity to correction changes,
- short-range temporal behavior,
- local sampling variability.

It did NOT establish:

- ~30-second drift,
- slow white-balance pumping,
- low-frequency attenuation/backscatter oscillation,
- gradual parameter drift,
- accumulated estimator error,
- long-period temporal artifacts.

Week 8 is where this will be tested.

---

## 3. Subpixel interpolation can dominate MC-Warp

Using known exact fractional motion, Phase 2B found that the subpixel resampling floor can be a substantial fraction of measured MC-Warp:

```text
lights         ~11%
distance       ~24%
murky_shark    ~26%
swimthrough    ~68%
murky_eel      ~115%
```

The alignment-robust companion was added specifically to expose this.

Do not recommend another metric merely because ordinary MC-Warp contains interpolation error.

The project already knows that.

---

## 4. Blur can game photometric temporal scores

Synthetic blur lowers temporal residual.

Therefore a temporally smooth-but-blurred result must not automatically be considered better.

Any proposed diagnostic must either resist blur gaming or explicitly remain paired with spatial-fidelity inspection.

---

## 5. Legitimate illumination changes exist

The `lights` footage contains camera-mounted illumination changes that are real changes in scene radiance, not geometric mismatch.

The canonical global gain/bias model cannot fully explain spatially local illumination.

Such cases are explicitly labelled:

```text
illumination-confounded
```

Do not recommend a metric that simply calls all illumination variation restoration flicker.

---

## 6. Correspondence masking has semantic blind spots

SEA-RAFT can invalidate an entire smooth moving animal such as the eel body.

FB self-consistency also does not prove correspondence correctness.

A low temporal residual therefore does not establish stability in every semantic region.

Coverage is already reported.

Do not propose solving this by hiding more pixels.

---

# Research objective

Perform a **bounded online literature review** of temporal-stability metrics and diagnostics that might add information genuinely absent from the existing Phase 2B evaluator.

The specific target is:

> Long-duration periodic flicker, slow pumping, or drift that may not be adequately characterized by pairwise MC-Warp@1/@4/@8 and temporal ΔE00.

Prioritize methods that inspect a **temporal trajectory over many frames** rather than adding another pairwise image-distance metric.

Potential research families include, but are not limited to:

- temporal-frequency analysis,
- flicker-energy measures,
- spectral analysis,
- temporal autocorrelation,
- periodicity detection,
- trajectory stability,
- temporal-gradient statistics,
- long-range consistency,
- drift statistics,
- no-reference flicker metrics,
- video-quality temporal diagnostics,
- parameter-trajectory stability measures.

These are search directions only.

Do not assume any should be adopted.

---

# Important distinction — output pixels vs physical parameters

By Week 8 the project should have time-varying estimated physical parameters such as:

- attenuation coefficients,
- backscatter parameters,
- stabilization state,
- possibly depth scale/offset or confidence terms.

A long-duration instability may be easier and more causally meaningful to detect directly in those parameter trajectories than in final image pixels.

Therefore explicitly investigate:

> Is the best future diagnostic actually a generic video metric, or simply temporal/spectral analysis of the project's physical parameter traces?

Prefer the latter if it provides a cleaner causal signal.

Do not add image-space complexity when the unstable state can be observed directly.

---

# Literature search requirements

Use current online sources.

Prioritize:

1. original papers,
2. official project pages,
3. author repositories,
4. respected conference/journal publications.

Use secondary summaries only to locate primary sources.

Check publication dates and distinguish older standard metrics from genuinely newer methods.

Do not infer implementation availability from a paper alone.

Verify whether usable public code actually exists where relevant.

---
# Verification and Hallucination Rule:
You must only evaluate a candidate if you can read and verify its actual mathematical formulation. If a search result provides a title and abstract, but you cannot access the exact methodology, discard it. For every candidate that survives into the final report, you must provide a verified DOI or a direct URL to the official paper or code. Do not hallucinate mathematical mechanics based on abstracts.

---

# Candidate inclusion criteria

Only spend significant analysis on a candidate if it plausibly adds information beyond:

```text
MC-Warp@1/@4/@8
illumination-aware MC-Warp
temporal ΔE00
alignment-robust warp
coverage/status
parameter-trace inspection
```

Do not seriously consider another metric merely because it is widely used.

In particular, another:

- flow-warp photometric error,
- SSIM variant,
- LPIPS variant,
- arbitrary perceptual pairwise distance,
- benchmark optical-flow score,
- extra arbitrary set of fixed lags,

does not qualify unless it solves a demonstrated missing temporal dimension.

---

# For each serious candidate

Report:

## Identity

- metric / method name,
- paper,
- venue,
- year,
- official source.

## Exact measurement

Explain mathematically or algorithmically what it actually measures.

Do not summarize with vague language such as:

> measures temporal consistency.

State the actual signal and operation.

Examples:

- temporal derivative energy,
- spectrum of a temporal signal,
- autocorrelation peak,
- feature-distance trajectory,
- long-range flow cycle,
- learned perceptual video score.

---

## Reference requirements

Classify as:

```text
full-reference
reduced-reference
no-reference / blind
```

State whether it requires:

- clean target video,
- optical flow,
- segmentation,
- pretrained neural networks,
- human training labels,
- long temporal windows.

---

## Temporal behavior

Assess whether it can detect:

- frame-to-frame flicker,
- period-2 oscillation,
- period-4 oscillation,
- arbitrary periodic pumping,
- slow sinusoidal pumping,
- monotonic drift,
- isolated one-frame spikes.

If it cannot, say so.

---

## Interaction with this project's known problems

Analyze:

### Blur gaming

Would spatial blur make the metric improve?

### Legitimate illumination

Would camera-mounted lighting or caustics look like instability?

### Motion

How does it distinguish temporal processing defects from scene/camera motion?

### Correspondence failure

Can aggressive masking or bad flow make it look artificially good?

### Subpixel resampling

Would the metric merely recreate the same interpolation floor already identified in Phase 2B?

### Moving objects

Would it measure moving animals or exclude them?

---

## Computational practicality

Estimate:

- temporal window requirements,
- whether full-resolution video is needed,
- CPU/GPU requirements,
- model/dependency burden,
- whether it is realistic on the project's current Mac/MPS workflow.

Do not reject an excellent Week 8 diagnostic solely because it is not free, but cost must be stated.

---

## Public implementation

State:

```text
available
partial
not found
```

and identify the official implementation if one exists.

Do not integrate or download it during this session.

---

## Incremental information

Answer explicitly:

> What fact would this tell us that the existing Phase 2B stack would not?

If the answer is unclear, discard the candidate.

---

# Specifically investigate parameter-trajectory diagnostics

Separately evaluate the simplest signal-processing route.

For a physical parameter sequence:

```text
p(t)
```

consider whether Week 8 could directly inspect quantities such as:

- mean / variance after detrending,
- first-difference energy,
- low-frequency drift,
- power spectral density,
- dominant non-DC frequency,
- autocorrelation,
- periodicity strength,
- change-point behavior.

Do NOT design the final implementation yet.

The research question is:

> Would one of these simple parameter-level diagnostics address the known long-duration blind spot more cleanly than importing a specialized video metric?

Compare this route explicitly against literature metrics.

---

# Required falsification perspective

For every surviving candidate ask:

> What synthetic sequence would prove this metric is NOT useful to us?

At minimum reason about:

### A. Stable sequence

No restoration instability.

Metric should remain quiet.

### B. Period-2 pumping

Must detect if periodic detection is claimed.

### C. Period-4 pumping

Must detect if periodic detection is claimed.

### D. Slow sinusoidal drift

Must detect if slow-drift detection is claimed.

### E. Monotonic drift

Determine whether this should be detected and how.

### F. One-frame spike

Should not be averaged away invisibly.

### G. Spatial blur only

Should not declare temporal improvement without caveat.

### H. Legitimate moving dive-light illumination

Should not be blindly interpreted as restoration instability.

### I. Real scene transition

A true parameter step must not automatically be labelled pathological pumping.

---

# Scope limits

This is deliberately one bounded pass.

Do not:

- build a giant bibliography,
- enumerate every temporal metric ever proposed,
- research another optical-flow backend,
- investigate restoration models,
- investigate temporal correction architectures,
- propose recurrent networks,
- propose video transformers,
- redesign Phase 2B,
- invent a weighted score,
- implement anything,
- change repository architecture.

Research only enough candidates to answer the decision.

Stop once the answer is clear.

---

# Acceptance bar

The default decision is:

```text
add nothing
```

A candidate survives only if it addresses a **demonstrated or strongly motivated missing temporal dimension** and adds information not already available from the existing stack.

The fact that fixed-lag aliasing exists mathematically is not by itself sufficient to justify a new metric.

Week 8 must still demonstrate that the blind spot matters on the actual physical pipeline.

---

# Required final output

Produce a concise research artifact with the following structure.

## 1. Executive conclusion

Choose exactly one:

### A. No additional metric justified

Explain why the existing Phase 2B evaluator plus future long-duration parameter traces is sufficient unless Week 8 demonstrates a real failure.

or:

### B. One candidate worth carrying into Week 8

Name exactly **one** candidate/diagnostic family.

Do not recommend multiple additions.

---

## 2. What the current evaluator already covers

Briefly state which temporal failure modes are already adequately measured.

---

## 3. Actual remaining blind spot

State the missing information precisely.

Distinguish:

```text
known mathematical limitation
```

from:

```text
demonstrated real pipeline failure
```

---

## 4. Candidate comparison

Include only the serious finalists.

For each show:

- definition,
- reference requirement,
- periodic-flicker sensitivity,
- slow-drift sensitivity,
- blur vulnerability,
- illumination vulnerability,
- motion/correspondence assumptions,
- cost,
- public implementation,
- incremental value.

---

## 5. Parameter-trace alternative

Answer:

> Would direct trajectory/spectral analysis of attenuation/backscatter/etc. be simpler and more informative than another image-space video metric?

Make a clear recommendation.

---

## 6. Week 8 recommendation

If adding nothing:

State exactly what Week 8 should measure before reconsidering.

If carrying one candidate:

State:

- why it is worth carrying,
- whether it belongs in parameter space or image space,
- the minimum experiment required,
- the criterion that would cause us to reject it.

---

## 7. Things explicitly rejected

Briefly name serious-looking approaches that were rejected and why.

This is important so the same metric search is not repeated later.

---

# Output file

Write the research result to:

```text
experiments/week2b_temporal/TEMPORAL_METRIC_LITERATURE.md
```

Do not modify the existing Phase 2B `FINDINGS.md`.

Do not update `PLAN.md` or `LOG.md`.

The artifact is advisory research only.

---

# Final decision rule

The preferred outcome is not:

> find another temporal metric.

The preferred outcome is:

> determine whether another temporal diagnostic earns its complexity.

If the literature does not reveal a clearly additive tool, conclude:

```text
No additional metric justified before Week 8 long-duration validation.
```

That is a successful result.