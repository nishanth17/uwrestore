# Underwater Restoration — Project Rules

## Project goal

Not "make underwater images prettier." The goal is:

> Recover the most plausible scene appearance that would have existed without
> underwater degradation, while preserving scene identity, physical
> plausibility, and temporal consistency.

Prioritize physical correctness, temporal stability, and realistic color
relationships over "wow factor" — unless explicitly building an enhancement
mode (a separate, later concern, not the default).

## Core invariants (never violate)

1. **Linear-light processing.** All restoration operations happen in linear
   light. Ingest must explicitly map from the source transfer function into
   linear RGB. Supported source paths may include standard sRGB EOTF, GoPro
   Protune Flat/log-style curves, or RAW sensor linear data — the source
   transfer function and conversion assumptions must be explicit and
   documented, not assumed. All restoration algorithms operate only on
   linear RGB; conversion to the target output color space happens only at
   final export. No restoration operation may be performed directly in
   gamma-encoded image space.

2. **Video-first architecture.** A photo is a video with one frame. Never
   create separate still-image and video pipelines. The core abstraction is
   `FrameSequence`, an iterable interface over ordered Frames — a single
   image is a `FrameSequence` of length one. Implementation may be eager
   (backed by a list) or lazy (streaming decode, windowed buffers) — that's
   an implementation choice, not an invariant. What must never change is
   that callers only ever see the `FrameSequence` interface and never branch
   on whether the underlying data is a photo or a video. Since a full 4K
   clip decoded eagerly into float32 can be large, prefer lazy loading once
   it's needed, but don't treat that as a day-one requirement.

3. **Explicit state only.** Correction stages are deterministic and pure:
   `FrameSequence -> FrameSequence`. Temporal stages may carry state, but it
   must be explicit and threaded through:
   `(FrameSequence, TemporalState) -> (FrameSequence, UpdatedTemporalState)`.
   Never hide state in globals, singletons, or module-level mutable objects.

4. **Ablation support.** Every implemented correction stage needs a
   `--no-<stage>` CLI flag (`--no-white-balance`, `--no-backscatter`,
   `--no-attenuation`, `--no-depth`, `--no-temporal`, ...). Future stages
   must follow this rule when they're implemented — week 1 only requires
   flags for whatever's actually built this session (gray-world), not
   placeholder flags for stages that don't exist yet. The point is
   attribution: if quality improves, we know which stage did it.

5. **Preserve image truth.** Metrics (ΔE, PSNR, SSIM, temporal stability) are
   necessary but not sufficient. Never treat a metric improvement as a
   successful experiment without visually inspecting the output for
   hallucinated detail, broken scene identity, or unnatural color
   relationships. This matters most once the learned residual (week 10+)
   enters the pipeline — it can learn to game a metric while making the
   image less true.

6. **No single-example conclusions.** Never claim an improvement from one
   image or clip. Check every change against the frozen test set's full
   spread: chart/reference, normal reef, difficult/low-visibility, artificial
   light, swim-through video. If a change helps one category and hurts
   another, document the tradeoff — don't hide it.

7. **Data safety.** Never modify or overwrite original source footage.
   Never silently overwrite existing output files either — fail clearly or
   require an explicit `--overwrite` flag. This applies everywhere the
   pipeline writes to disk (corrected exports, depth maps, benchmark
   outputs, everything), not just wherever it was first implemented.
   Generated artifacts should be traceable to source input and pipeline
   version (a filename convention or a line in LOG.md is enough at this
   project's scale — no per-experiment directory scaffold needed yet).
   Test set video/image files stay local-only — never `git add` anything
   under `data/testset/*/` other than READMEs, `.gitkeep`, `chart_refs.json`,
   and `manifest.json`. `manifest.json` documents what footage should exist
   locally (category, path, frame count, notes) without the footage itself
   being tracked.

8. **Lightweight dependencies by default.** Use the standard library and
   already-established project dependencies (numpy, opencv-python) unless
   a stage genuinely requires something heavier. Don't add a dependency
   speculatively or out of habit (e.g. `click`/`typer` for a CLI argparse
   already covers, `torch` before a stage that actually needs it). When a
   later stage does need something heavier — a monocular depth model, the
   learned residual — that's an expected, justified addition at that
   point, not a violation of this rule.

## Current phase

See `PLAN.md` and `LOG.md` for progress. Current phase:

**Week 1: Skeleton + evaluation harness** — unified FrameSequence pipeline,
image/video ingestion, linear-light conversion, baseline methods (gray-world),
scoring pipeline (`uw score`, `uw correct`). ΔE/CIEDE2000 in `metrics.py` is
intentionally stubbed this session — implemented separately.

## Repository layout

```
uw/
  types.py       # Frame and FrameSequence definitions — data abstractions only, no processing logic
  io.py          # video/image loading and saving
  colorspace.py  # sRGB <-> linear conversions
  baselines.py   # gray-world, white-patch, CLAHE
  metrics.py     # delta_e (CIEDE2000), temporal_stability
  cli.py         # uw score <path>, uw correct <path> --method X
data/
  testset/       # FROZEN. Never modify. Footage stays LOCAL ONLY — not
                 # committed to git. Structure, README, chart_refs.json,
                 # and manifest.json (documenting what should exist
                 # locally) are tracked; the actual video/image files
                 # under chart/, distance/, murky/, lights/, swimthrough/
                 # are not.
  chart_refs.json
LOG.md
PLAN.md
```

(`depth/`, `restoration/`, `temporal/` subpackages get added when those weeks
start — don't scaffold them empty now.)

## Evaluation rules

Before touching code: run `uw score` against the frozen test set. If numbers
don't match the last LOG.md entry, stop and figure out why (environment,
regression, metric change, or data change) before adding anything new.

After every session: run `uw score` again, then append to LOG.md — what
changed, before/after ΔE and temporal stability numbers, visual observations,
anything that surprised you, next hypothesis.

## Research discipline

Before implementing a paper-derived algorithm: read it, note its assumptions
and required inputs, identify likely failure modes on underwater GoPro
footage specifically, implement the smallest testable version, compare
against the existing baseline. Don't implement something because it's SOTA
without understanding why it applies here.

## Algorithm development principles

- **Physics before learning.** Prefer interpretable physical models
  (attenuation, backscatter, depth-dependent correction, parameter-level
  temporal smoothing) before learned models.
- **Learned components solve identified failure modes, not replace
  understanding.** Don't train a model to imitate the physics pipeline's own
  output — it will learn the physics model's mistakes too. Train against
  chart-referenced ground truth, targeting the specific failures catalogued
  in the week 7 stress test.

## Model routing

**Opus 5** — architecture decisions, physics equations, restoration
algorithm design, evaluation methodology, interpreting failures, choosing
between competing approaches. Bring in Opus before any major architectural
change.

**Sonnet 5** — scaffolding, CLI, I/O, tests, mechanical implementation of
already-decided designs.