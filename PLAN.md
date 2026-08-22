# Underwater Restoration — Plan

Session-based, not calendar-locked. Skip a session if life happens — just
don't skip a gate. One session = one gate below; don't start the next gate
early even if there's time left. Project goal and core invariants live in
CLAUDE.md — this file is the roadmap, not a second copy of the rules.

Every session: run `uw score` against the frozen test set first and confirm
it matches the last LOG.md entry — if not, stop and figure out why
(environment, regression, metric change, or data change) before adding
anything new. Do the work. Run `uw score` again. Append a LOG.md entry: what
changed, before/after ΔE and temporal stability, visual observations, any
surprises, next hypothesis.

---

## Week 1 — Skeleton + eval harness

Video and photo ingestion through the same `FrameSequence` abstraction,
linear-light conversion, gray-world baseline, ΔE metric (stubbed this
session — implemented separately), temporal-stability placeholder, frozen
test set structure, LOG.md started.

Treat camera linearization as a calibration problem, not just a colorspace
conversion — support validated camera profiles where possible (GoPro
Flat/log).

**Calibration check:** shoot a RAW photo + a Flat-profile video frame of the
same static scene back-to-back; compare reconstructed-linear values against
the RAW-derived reference. Validates camera linearization and transfer-
function handling specifically, not stills-in-general.

**Gate:** `uw score` runs on a still and a clip, baseline numbers logged;
calibration check passes within tolerance.

## Week 2 — More baselines + ablation flags

White-patch, CLAHE, DaVinci Resolve chart-based export as the human control,
real temporal stability metric, every stage behind a `--no-<stage>` flag
(`--no-white-balance`, `--no-depth`, `--no-backscatter`, `--no-attenuation`,
`--no-temporal`, ...).

**Gate:** any future gain can be traced to a specific stage.

## Week 3 — Depth from video

Multi-view reconstruction (COLMAP) on a controlled clip: static, feature-
rich scene (wreck or solid coral head), overcast or below the caustic zone —
no dappled sunlight, no swaying kelp, no midwater particulate. A failed gate
should mean "bad clip choice," not "reconstruction doesn't work."

Prioritize relative depth ordering and reconstruction stability over
absolute metric accuracy — measure scale where possible via a known-size
object or the chart, but don't let imperfect absolute scale block progress.

**Gate:** depth reconstruction is stable enough to support range-dependent
restoration. Document where it works, where it fails, and the uncertainty.

## Week 4 — Depth from a single image

Monocular depth model on frames that already have video-derived depth;
compare relative ordering, range consistency, and failure modes between the
two.

**Gate:** known error budget for the photo path vs. the video path.

## Week 5 — Backscatter estimation

Sea-thru backscatter term. Codex implements an independent version from the
same paper; diff outputs, assumptions, and failure cases.

Apply rolling-window smoothing to the estimated backscatter *parameters*
(not the output image) before they feed the inverse.

**Gate:** backscatter removal improves the murky test footage; estimated
parameters stay stable across frames.

## Week 6 — Attenuation inverse

Spatially varying correction using range (Beer-Lambert, wavelength-
dependent). Same principle as week 5: smooth the estimated attenuation
parameters, not the output frames.

**Gate:** foreground, middle-distance, and background are all corrected
correctly in the same frame — first real test against global-correction
tools (Dive+, AquaColorFix, LUT workflows).

## Week 7 — Stress test

Run the ugly real footage: clipped red channel, heavy particulates,
artificial dive lights, surge/motion, low visibility. Catalogue failures —
missing color information, bad depth, lighting ambiguity, severe
backscatter, moving objects, genuinely unrecoverable cases.

**Gate:** a written failure list. This becomes the spec for the learned
residual layer.

## Week 8 — Residual temporal consistency

Not "add temporal consistency from scratch" — weeks 5–6 already estimate
smoothed parameters. This stage catches what's left: residual flicker,
remaining parameter jumps, inconsistent reconstruction. Start with
parameter-smoothing refinements; only then investigate optical-flow /
flow-warped consistency.

**Gate:** no visible pumping on a 30-second swim-through, without damaging
spatial quality.

## Week 9 — Benchmark

Head-to-head: this pipeline vs. Dive+ vs. AquaColorFix vs. DaVinci Resolve
(chart-based) vs. plain Sea-thru, on stills and video, against the frozen
test set with chart-referenced ground truth plus human visual comparison.

**Gate:** a measured result, not a vibe — where it wins, where it loses,
why.

## Week 10+ — Learned residual

Small residual model, trained to correct what the physics model can't
explain — not to replace it. Sources: chart-referenced controlled footage,
synthetic degradation from clean scenes, real paired datasets where
available. Avoid training only on `physics output -> target`, since the
model can learn the physics pipeline's own mistakes. Target specifically
the week 7 failure list. Evaluate against real chart-referenced data and
human visual preference, not loss curves alone.

---

## Architecture decision points

Stop and evaluate before adding complexity, not after:

- **Physics vs. learned:** still getting measurable gains from the physics
  model? If yes, keep improving it. If no, investigate assumptions and
  implementation before reaching for a learned component.
- **Learned residual value:** does it improve visual fidelity, metrics,
  *and* failure cases — not just one? If not, reject it, even if it's
  technically interesting.
- **Depth importance:** does better absolute depth materially improve
  restoration, or is relative ordering enough? Don't optimize a quantity
  that doesn't move the final result.

## Non-goals for now

- No enhancement mode (AI-invented prettiness) — restoration only, until
  explicitly decided otherwise.
- No generative image replacement.
- No chasing SOTA architectures before the physics baseline is solid and
  measured.
- No large training infrastructure before a clear failure mode requires it.
- No per-experiment directory scaffolding (`experiments/YYYY-MM-DD_name/`)
  until the learned-residual stage actually needs reproducible run
  tracking.

The project earns complexity through measured improvement, not by default.