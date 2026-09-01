# Week 2 Phase 1A — Optical Flow Backend Exploration

Read `CLAUDE.md`, `PLAN.md`, `LOG.md`, and the current repository first.

Do not modify `CLAUDE.md` or `PLAN.md`.

This is a deliberately scoped research exception to the project's lightweight-dependencies rule. Optical-flow evaluation may require PyTorch and pretrained research models. Treat that exception as applying only to this exploratory phase; do not interpret it as permission to broadly add heavyweight dependencies elsewhere.

## Goal

Determine which optical-flow backend is most trustworthy on **our actual underwater footage** for later use by the temporal-stability metric.

This is an exploration session, not a productionization session.

Do not implement the final temporal-stability metric yet.

Do not pick or wire in a permanent default backend yet.

Implement only enough infrastructure to compare the candidate models rigorously and produce outputs I can inspect.

---

## 1. Flow abstraction

Add a small optical-flow abstraction that supports both pairwise and multi-frame models.

Do not force every backend into a pairwise-only API.

Use something conceptually like:

```python
@dataclass
class FlowResult:
    flow: np.ndarray             # H x W x 2, pixel displacement
    valid_mask: np.ndarray       # H x W bool
    confidence: np.ndarray | None
    metadata: dict


class OpticalFlowBackend:
    def estimate(
        self,
        frames: Sequence[Frame],
        index_t: int,
        index_t1: int,
    ) -> FlowResult:
        ...
```

The exact implementation may differ if there is a simpler clean design.

Requirements:

- Flow-consuming project code must not import a specific model directly.
- Pairwise models may simply use `frames[index_t]` and `frames[index_t1]`.
- Multi-frame models may use neighboring temporal context.
- Document the coordinate convention explicitly:
  - flow direction,
  - channel ordering,
  - whether flow represents source -> target displacement.
- Do not create a large framework.

### Resolution / memory discipline

Do not naively run inference on full-resolution 4K/1080p footage if the model's expected operating scale or available memory makes that unreasonable.

- Choose and document a common, model-appropriate evaluation resolution for the bakeoff where feasible, for example around `960x540`, subject to each model's stride/input constraints.
- Prefer comparing backends at the same effective resolution so resolution itself does not confound the comparison.
- Wrappers may resize inputs for inference.
- Whenever a flow field is resized:
  - resize the spatial dimensions correctly,
  - scale the horizontal and vertical flow-vector magnitudes correctly.
- Explicitly validate resize/vector-scaling behavior in the synthetic known-motion test.
- If a flow field is later upsampled to source resolution for visualization, record its native inference resolution.
- Do not imply that an upsampled low-resolution flow field contains native 4K correspondence detail.
- For Phase 1A quantitative diagnostics, prefer computing warping/error diagnostics at the common evaluation resolution rather than introducing unnecessary upsampling artifacts.

### Model input representation

`Frame` obeys the `uwrestore` invariant of linear-light RGB.

Pretrained optical-flow models generally expect conventional encoded RGB imagery rather than physically linear-light values.

Therefore the flow wrapper must create a **temporary model-specific inference view** without changing the underlying `Frame`:

- convert linear RGB -> standard sRGB encoding for optical-flow inference,
- then apply whatever numeric range, normalization, padding, or resizing the specific pretrained model officially expects,
- document preprocessing separately for every backend.

This conversion exists **only for correspondence estimation**.

Do not mutate `Frame`.

Do not weaken or reinterpret the project's linear-light invariant.

Any photometric warping/residual evaluation must operate on the original linear-light image data, not on the temporary sRGB/model-input representation.

---

## 2. Candidate backends

Attempt to evaluate:

1. **SEA-RAFT**
   - mature, strong baseline

2. **FlowIt**
   - modern pairwise frontier candidate

3. **VideoFlow-MOF**
   - multi-frame/video-specific candidate

If one is genuinely impractical because of:

- broken or unmaintained code,
- incompatible dependencies,
- CUDA-only assumptions that cannot reasonably be satisfied,
- unavailable checkpoints,
- unclear or undocumented inference path,
- substantial reimplementation,

do not burn the session forcing it.

Instead:

1. explain exactly why it is impractical,
2. preserve useful failure notes,
3. optionally substitute one of:
   - WAFT / WAFT-DINOv3
   - DPFlow
   - RAFT-large

but only if the substitute is materially easier to evaluate.

Do not integrate models merely to reach the number three.

### Integration stop rule

Do not engage in prolonged C++/CUDA extension compilation or dependency debugging.

For each candidate:

1. attempt the documented installation/inference path,
2. allow at most **one straightforward dependency/environment fix**.

If the model still requires:

- CUDA-extension surgery,
- source-level compatibility patches,
- dependency downgrade chains,
- custom-kernel debugging,
- rewriting setup/build scripts,
- substantial third-party code modification,

**stop immediately**.

Record:

- the documented path/command attempted,
- the concrete failure,
- the single fix attempted,
- why the backend was dropped.

Then move to the next candidate or approved substitute.

Do not spend Phase 1A repairing third-party research code.

If an official slower/non-extension inference path exists, prefer that over compiling an optional acceleration extension during this bakeoff.

---

## 3. Environment isolation

Do **not** force mutually incompatible research-model dependency stacks into the main `uwrestore` environment.

Exploratory backends may run in:

- isolated Python environments,
- model-specific environments,
- minimally isolated scripts,

if necessary.

Only the backend selected after this bakeoff should later become a normal project dependency.

Do not gratuitously modify the main `pyproject.toml` with every experimental model's dependency tree.

For each backend record:

- model name/version,
- repository/source,
- checkpoint used,
- license,
- Python version,
- PyTorch version,
- CUDA/MPS/CPU requirements,
- actual hardware/backend used,
- native inference resolution,
- model preprocessing,
- any modifications required to run it.

Do not silently modify third-party model inference semantics.

---

## 4. Fair comparison mask

Different models may expose different notions of:

- confidence,
- uncertainty,
- occlusion,
- validity.

Do not directly compare their native masks as though they mean the same thing.

For every backend, derive a **common validity/occlusion diagnostic using forward-backward flow consistency**.

That common mask is the basis for fair cross-backend diagnostics.

Native confidence/uncertainty/occlusion outputs may also be saved separately.

Document:

- forward/backward consistency formula,
- threshold,
- boundary handling,
- invalid-region handling.

Do not optimize the threshold independently per model merely to make one look better.

---

## 5. Synthetic correctness sanity test

Before trusting real-footage results, test every wrapper on at least one known-motion synthetic case.

For example:

1. take an underwater test frame,
2. create a translated version with known motion,
3. estimate flow,
4. verify direction and approximate magnitude.

Include enough checks to catch:

- x/y swapped,
- sign/direction reversed,
- forward vs backward flow confusion,
- incorrect resizing,
- flow-vector magnitudes not rescaled after image resizing,
- coordinate convention errors,
- obvious NaN/Inf outputs.

This is a wrapper correctness test only.

Do not treat success here as evidence that a model is good underwater.

---

## 6. Real-footage evaluation

Use the local test footage documented by `data/testset/manifest.json`.

Evaluate representative excerpts from:

- `swimthrough`
- `murky`
- `lights`
- `distance`
- whichever available clip has the strongest camera motion

Do not modify or commit test footage.

Keep excerpts short enough that all candidate backends can be compared without turning this into a large benchmark run.

Use comparable frame ranges across models where feasible.

For each backend x clip, generate diagnostics under:

```text
outputs/flow_comparison/<backend>/<clip>/
```

At minimum save:

- frame `t`
- frame `t+1`
- optical-flow visualization
- frame `t+1` warped into frame-`t` coordinates
- warped-frame residual visualization
- common forward/backward validity/occlusion mask
- native confidence/uncertainty/occlusion map if available

For VideoFlow-MOF, make clear which surrounding frames were used as temporal context.

Outputs are local artifacts.

Do not silently overwrite existing diagnostic outputs.

---

## 7. Quantitative diagnostics

For every backend x clip record:

- runtime per inference,
- resolution actually used,
- percentage of invalid/non-finite flow,
- common forward/backward valid-mask coverage,
- forward/backward consistency error,
- raw-frame motion-compensated warping residual,
- flow-magnitude summary statistics,
- peak memory if reasonably measurable.

If a value cannot be measured reliably, report it as unavailable rather than inventing or estimating it.

Do not collapse these metrics into one weighted score.

Do not claim benchmark-style ranking from this small test set.

---

## 8. Qualitative analysis

The visual analysis is a first-class deliverable.

Actually inspect the generated diagnostics.

For each backend, describe concretely:

- Are suspended particles/bubbles interpreted as object motion?
- Do murky low-contrast regions produce noisy, unstable, or implausible flow?
- Are there systematic errors near GoPro/fisheye frame edges?
- Do moving animals separate plausibly from camera motion?
- Does artificial lighting create false correspondence or motion artifacts?
- Are bright localized lights or moving beams problematic?
- Does VideoFlow-MOF's multi-frame context visibly help the swim-through clip versus pairwise methods?
- Are there regions where the backends disagree strongly?
- Does one backend produce visibly cleaner warps despite similar aggregate statistics?
- Does any model fail specifically in distant low-detail water regions?
- Are occlusion boundaries handled plausibly?

Do not reduce the writeup to:

> backend X is best

I want the actual observed differences and failure modes.

---

## 9. Do not choose the permanent default

End Phase 1A with:

- implementation status,
- diagnostic outputs,
- quantitative comparison,
- qualitative observations,
- failure notes,
- unresolved questions.

Do **not**:

- wire a chosen model into `uw/metrics.py`,
- implement MC-Warp as the permanent temporal metric,
- choose a project-wide default flow backend,
- add temporal correction/smoothing.

I will review the generated outputs and comparison before Phase 1B.

---

## 10. Repository discipline

Keep exploratory code contained.

Do not:

- add future depth/restoration scaffolding,
- create a generic ML-model registry,
- create a plugin system,
- restructure unrelated Week 1 code,
- edit `CLAUDE.md`,
- edit `PLAN.md`,
- commit local footage,
- begin Week 3 work.

If exploratory environments/scripts should not remain in the permanent project, keep that distinction explicit.

Update `LOG.md` with the Phase 1A experiment and observations.



---

## Before finishing

Run relevant tests and verify:

- existing Week 1 tests still pass,
- `CLAUDE.md` and `PLAN.md` were not modified,
- local test footage was not staged or committed,
- synthetic known-motion sanity checks pass for every successfully integrated backend,
- flow coordinate/direction conventions are documented,
- resizing correctly rescales vector magnitudes,
- linear-light `Frame` objects are not fed directly into pretrained models unless a specific model explicitly requires that representation,
- photometric residual diagnostics operate on linear-light data,
- no specific optical-flow implementation is imported directly by eventual metric-facing project code,
- no prolonged CUDA/C++ debugging was undertaken.

## Final summary

At the end, provide a detailed comparison containing:

### Successfully evaluated
- backend
- model/checkpoint
- environment
- hardware
- inference resolution
- preprocessing

### Dropped/substituted
- backend
- exact reason
- error/failure encountered
- one fix attempted
- substitute if any

### Quantitative comparison
Per backend and clip:
- runtime
- valid coverage
- forward/backward consistency
- warping residual
- flow magnitude sanity
- memory if available

Forward/backward consistency requires two flow inferences per evaluated pair. This additional compute is intentional. Keep the evaluated excerpts short rather than dropping backward flow or weakening the common consistency mask. Reuse/cache computed forward and backward flows across diagnostics where possible; do not recompute them separately for each visualization or metric.

### Qualitative comparison
Describe the actual observed behavior on:
- swim-through
- murky/particulate
- artificial lights
- distance footage
- strong camera motion

### Repository changes
- files created
- files modified
- isolated environments/dependencies created
- generated diagnostic locations

### Open questions

Do not make the final backend selection for me.

Do not implement Phase 1B.