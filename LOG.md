# Log

Format for each entry:

- **Date**
- **Change made**
- **ΔE before/after**
- **Temporal stability before/after**
- **Visual observations**
- **Surprises/failures**
- **Next hypothesis**

---

## 2026-08-22 — Week 1 skeleton

**Change made:** Built the Week 1 skeleton — `uw/types.py` (`Frame`,
`FrameSequence`), `uw/io.py` (`load`/`save` with explicit per-source
transfer-function handling), `uw/colorspace.py` (sRGB EOTF conversions),
`uw/baselines.py` (`gray_world`), `uw/metrics.py` (`temporal_stability`
placeholder; `delta_e` stubbed), `uw/cli.py` (`uw score`, `uw correct`),
`data/testset/` structure + README, `data/chart_refs.json` placeholder,
tests for colorspace and io.

**ΔE before/after:** N/A — not implemented this session
(`NotImplementedError("implemented separately — see week 1 notes")`, as
specified). No prior baseline exists to compare against.

**Temporal stability before/after:** No prior baseline (first session).
On synthetic fixtures generated for this session only (not the frozen
test set, which has no footage yet):
- synthetic still image (64x64, solid color): `0.0` (single frame, no
  temporal variation by definition).
- synthetic 10-frame clip (64x64, stepped brightness ramp):
  `0.021221274510025978`.

These numbers are meaningless as quality signals — they only confirm the
pipeline runs end-to-end. Real numbers start once `data/testset/` has
actual footage.

**Visual observations:** Not evaluated — no real footage in the frozen
test set yet. Only ran against synthetic solid-color/ramp fixtures to
verify the pipeline (RGB ordering, linear-light range, gray-world
scaling) behaves as expected.

**Surprises/failures:**
- GoPro Protune Flat -> linear is **stubbed**, not approximated. No
  verified formula was available this session; per project rules,
  fabricating an unvalidated curve was judged worse than failing loudly.
  `uw/colorspace.py::protune_flat_to_linear` raises `NotImplementedError`
  with a TODO pointing at the PLAN.md Week 1 calibration check as the
  validation path.
- RAW support this session is intentionally narrow: `load(path,
  profile="raw_linear")` skips EOTF conversion and trusts the input array
  is already linear, but does not decode native RAW files (no `.dng`/
  `.gpr` support, no `rawpy` dependency added). The expected workflow is
  to externally export RAW stills to a linear TIFF/EXR (e.g. via Resolve)
  and load that with `--profile raw_linear`. This was an explicit scoping
  decision, not a bug.
- Editable install (`pip install -e .`) initially broke the installed
  `uw` console script under Python 3.14: site.py now skips PEP 660
  editable `.pth` files whose name contains an extra dot
  (`__editable__.uw-0.1.0.pth`), logging "Skipping hidden .pth file" and
  leaving `uw` unimportable from the script shim even though `import uw`
  worked fine interactively. Worked around with `pip install -e .
  --config-settings editable_mode=compat`. Environment/tooling quirk, not
  a project code issue — noting here in case it resurfaces.
- `gray_world` does not clip output back to `[0, 1]`; out-of-range values
  are left as-is and the out-of-range fraction is recorded in
  `Frame.metadata["gray_world_out_of_range_fraction"]` instead, so
  clipping behavior is visible rather than silently baked in. Export
  (`save`) does clip when converting to 8-bit sRGB, since a file format
  requires it.

**Next hypothesis:** Populate `data/testset/` with real chart, distance,
murky, lights, and swimthrough footage so `uw score` produces meaningful
numbers instead of synthetic-fixture placeholders. Week 1's gate
(calibration check: RAW photo + Protune-profile video frame of the same
static scene, compared against RAW-derived reference) is still open —
it depends on real footage and on `delta_e` being implemented, both
outside this session's scope.

## 2026-08-22 — First real-footage test run (gray-world baseline)

**Change:** Added first real GoPro footage to data/testset/ (murky eel clip,
~10s, 292 frames). Ran `uw score` and `uw correct --method gray_world` on it
for the first time — previous testing was synthetic fixtures only.

**Metrics:**
- temporal_stability (placeholder proxy): 3.244860636186786e-05
  (no baseline to compare against yet — first real data point)
- ΔE: not yet implemented

**Visual observations (gray_world output vs. original):**
- Coral appears redder — expected, gray-world boosts red to counter the
  blue-green cast, and coral is genuinely red under white light.
- Overall image looks "grayer" / desaturated — expected, gray-world
  flattens toward neutral and doesn't distinguish "water tint to remove"
  from "actual scene color," so it mutes real color along with the cast.
- Visible frame-to-frame flicker — expected in part, since gray-world
  recomputes its correction independently per frame with no temporal
  smoothing (that's weeks 5–6/8's job). Not yet distinguished from
  possible camera-side auto-exposure/auto-WB variance already baked into
  the source footage — worth a closer look once real correction methods
  exist to compare against.

**Read:** This matches the expected profile for gray-world as a floor
baseline — plausible-but-ugly, not broken. Confirms the "beat this" bar
for weeks 5–6 rather than indicating a pipeline bug.

**Environment note:** Console script (`uw` bare command) now working after
fixing the pip install-e / opencv-python dependency gap from earlier.

**Still open:**
- chart/, lights/ test-set folders still empty
- RAW/Flat linearization calibration check not yet performed

**Next hypothesis:** White-patch and CLAHE (week 2) should look different
from gray-world but not necessarily "better" without a real metric —
ΔE is the actual tiebreaker once it exists.
## 2026-08-22 — ΔE / CIEDE2000 implemented

**Change made:** Implemented `uw/metrics.py::delta_e` (chart-referenced
CIEDE2000) and the color-science conversions it needs. Specifically:

- `uw/colorspace.py`: added linear RGB ↔ XYZ ↔ CIELAB and Bradford
  chromatic adaptation (`linear_rgb_to_xyz`, `xyz_to_linear_rgb`,
  `xyz_to_lab`, `lab_to_xyz`, `linear_rgb_to_lab`,
  `bradford_adaptation_matrix`, `adapt_xyz`, `adapt_lab`), plus D65/D50
  white points and the linear-sRGB→XYZ matrix. All conversion assumptions
  are written out in a comment block at the top of that section rather than
  left implicit. Existing sRGB EOTF functions untouched.
- `uw/metrics.py`: added `ciede2000(lab1, lab2)` (full CIE 142-2001
  formula, vectorized) and implemented `delta_e(frame, chart_patches)`.
  `temporal_stability` unchanged.
- `data/chart_refs.json`: rewritten into the confirmed schema (still a
  placeholder — no measured values).

**Schema decision (was ambiguous, resolved before writing code):** the old
placeholder was Lab-only, which the two-argument signature cannot support —
there was no channel for patch locations, and nothing in the repo supplied
them. Settled on: `delta_e` samples the Frame itself, and `chart_patches`
carries reference Lab *and* a normalized region per patch, under a top-level
`patches` key with a required `reference_illuminant` sibling. Regions are
normalized [0,1] fractions of frame size, not pixels, so one entry survives a
proxy/downscale of the same shot.

**ΔE before/after:** no before — this is the first implementation. `uw score`
still prints "ΔE: not yet implemented"; `delta_e` is **not wired into the CLI
yet**, because that needs real chart footage (`data/testset/chart/` is still
empty) and per-shot patch regions, neither of which exists. Wiring it is the
next concrete step, not a missing piece of this change.

Measured behavior on a real frame (MURKYSHARK.MP4, frame 100), three 10%
regions scored against an equal-lightness neutral to isolate pure chroma
error: **mean ΔE00 = 19.74**. Per-region linear RGB shows red at 0.005–0.011
against green/blue at 0.11–0.22, with a* ≈ −28…−11 and b* ≈ −22…−1. That is
the textbook blue-green cast, and the magnitude is plausible rather than
suspicious.

**Temporal stability before/after:** unchanged, and verified rather than
assumed — `uw score data/testset/murky/MURKYSHARK.MP4` reproduces
`3.244860636186786e-05` bit-for-bit against the previous entry. Nothing in
this change touches `temporal_stability` or the `uw score` path.

**Surprises/failures:**

- **The previous LOG entry names the wrong file.** It reports "murky eel
  clip, ~10s, 292 frames" — but MURKYEEL.MP4 is 756 frames / 25.2s, while
  MURKYSHARK.MP4 is 292 frames / 9.7s, and the gray-world output left on
  disk (`MURKYSHARK_corrected.mp4`) is also 292 frames. The logged number
  is from the **shark** clip, not the eel clip. The per-session `uw score`
  gate caught this exactly as intended: the numbers didn't match, work
  stopped, and the cause turned out to be bookkeeping, not a regression.
  For the record, current frame counts: distance 353, lights 307, murky-eel
  756, murky-shark 292, swimthrough 313.
- **Averaging patch pixels in float32 made the metric resolution-dependent.**
  The first version accumulated the region mean in the frame's native
  float32. The exact-match ΔE floor then drifted from 2e-4 to 1.4e-3 purely
  as a function of how many pixels a region covered — i.e. the same chart on
  a 4K master and a proxy scored differently for no physical reason.
  Accumulating in float64 pins the floor at 5.6e-7 identically at 48px
  through 960px. Caught by the resolution-independence test, which is the
  one thing normalized regions are supposed to guarantee.
- **The D50/D65 question is worth ~1.0 ΔE.** Published X-Rite ColorChecker
  reference data is D50-referenced; this pipeline works in D65. Feeding D50
  values in while claiming D65 produces ≈0.999 ΔE of pure white-point
  bookkeeping error — right at the just-noticeable-difference threshold, and
  the same order as the improvements weeks 5–6 will be chasing. Hence
  `reference_illuminant` is required rather than defaulted, and D50 is
  Bradford-adapted rather than accepted as-is.
- **OpenCV decodes MURKYSHARK.MP4 to a portrait array.** The container
  reports 1920x1080, but the decoded numpy frame is `(1920, 1080, 3)` —
  H=1920, W=1080 — so rotation metadata is being applied at decode. Harmless
  for `delta_e` (normalized regions are relative to the decoded array, so
  it is self-consistent), but it will matter when chart regions are measured
  off a player that shows the un-rotated orientation. Flagging before it
  bites.

**Tests:** 88 passing (was 22). `tests/test_metrics.py` added — all 34
published Sharma/Wu/Dalal (2005) CIEDE2000 test vectors pass to within 1e-4,
plus symmetry, zero-chroma, and vectorization checks; RGB→Lab against the
published sRGB primary Lab values; and `delta_e` integration on a synthetic
chart covering resolution independence, linear-vs-Lab averaging, D50
adaptation, out-of-range values, and schema validation.

**Next hypothesis:** ΔE is now the tiebreaker the last entry said was
missing, but it cannot rank gray-world against white-patch/CLAHE until
`data/testset/chart/` has footage with a chart in frame and its patch regions
are measured into `chart_refs.json`. That is the blocking item for the Week 1
gate and for week 2's baseline comparison — everything else in the metric
path is done and verified.

## 2026-08-29 — Week 2 Phase 1A: optical-flow backend bakeoff (exploration)

**Hypothesis:** one of the current optical-flow backends is trustworthy
enough on *our* footage to underpin the `MC-Warp@1/4/8` temporal metric, and
a short structured bakeoff can identify which.

**Change made:** Compared **four** pretrained optical-flow backends —
SEA-RAFT-M, WAFT-a1, FlowIt-M, VideoFlow-MOF — on five frozen test-set
excerpts. Exploration only: **no backend was selected, none is wired into
`uw/metrics.py`, MC-Warp was not implemented, and no temporal correction was
added.** That is Phase 1B.

Added `uw/flow.py` (permanent): `FlowResult`, the `OpticalFlowBackend`
interface, the project's normative flow coordinate convention, and the
model-independent maths — `resize_flow` (rescales `u` by the width ratio and
`v` by the height ratio, so a resize can never silently keep stale vector
magnitudes), `warp_to_source`, `forward_backward_consistency`, `sample_flow`,
`flow_magnitude`. numpy + opencv only; **no backend and no default inside
it**, and nothing else under `uw/` imports it yet. `tests/test_flow.py` adds
26 analytic tests of the conventions (108 tests total, all passing; was 88).

Everything model-specific is quarantined under `experiments/week2a_flow/`
(four wrappers, two isolated venvs, vendored repos, run scripts) — not
installed, not a dependency, `pyproject.toml` untouched. Full writeup:
`experiments/week2a_flow/FINDINGS.md`. Diagnostics — including 120 raw
`.npy` flow fields so Phase 1B can prototype metric variants without
re-running inference — in `outputs/flow_comparison/`, gitignored.

**Active pipeline stages:** none. No correction was applied; this session
measured correspondence quality only.

**Data / frame ranges:** five clips, 12 frames decoded each, 3 evaluated
pairs each, excerpt start chosen by rule (highest ~1 s moving-average
Farneback motion — a proxy deliberately *not* one of the candidates).
swimthrough 195–206, murky_eel 650–661, murky_shark 2–13, lights 85–96,
distance 260–271. Recorded in `experiments/week2a_flow/excerpts.json`.

**Models / checkpoints:** SEA-RAFT-M `Tartan-C-T-TSKH-spring540x960-M`;
WAFT-a1 `tar-c-t.pth`; FlowIt-M `C-T-TSKH_Flowit-M.pth`; VideoFlow-MOF
`MOF_sintel.pth`. All four are general-purpose / zero-shot-generalisation
checkpoints, matched on training recipe rather than leaderboard rank.

**Evaluation resolution:** 960×540 for every backend (540×960 for the two
portrait-decoding clips). Source frames downscaled **in linear light**
(`cv2.INTER_AREA`) before the temporary sRGB model-input view is built, so
the network and the photometric residual see the same scene data. Nothing
upsampled back to source resolution.

**ΔE before/after:** unchanged — not touched this session.
`data/testset/chart/` is still empty, so ΔE remains unwired from `uw score`.

**Temporal stability before/after:** unchanged and verified rather than
assumed. `uw score data/testset/murky/MURKYSHARK.MP4` reproduces
`3.244860636186786e-05` bit-for-bit against the last entry, before and after
this session. Nothing here touches `temporal_stability` — this phase was
about deciding what a *real* temporal metric could be built on.

**Coverage statistics (FB-valid %, mean over 3 pairs):**

| clip | SEA-RAFT | WAFT | FlowIt | MOF |
|---|---|---|---|---|
| swimthrough | 96.8 | 96.8 | 96.9 | 96.9 |
| murky_eel | 96.8 | 97.5 | 97.3 | 97.2 |
| murky_shark | 96.5 | 99.4 | 91.3 | 99.2 |
| lights | 98.3 | 99.2 | 96.2 | 98.1 |
| distance | 97.8 | 98.1 | 98.0 | 97.5 |

**Cost:** 0.73–0.80 s/inference (SEA-RAFT), 2.0–3.0 s (WAFT), 16–21 s (MOF),
38–52 s (FlowIt). Peak MPS driver allocation 2.2 / 2.4 / 8.9 / 22.8 GB.

**Visual observations:**

- **All four produce near-identical aggregate numbers.** Warp residual MAE
  agrees within ~2 % on four of five clips (8 % on `distance`, WAFT-driven),
  and reduction ratios agree to two decimal places. Motion-compensated
  warping residual **does not discriminate between these backends on our
  footage** — it measures the scene, not the model.
- **Moving animals separate cleanly** from camera motion in all four — the
  eel's silhouette is crisply cut out of the background field. But they
  disagree on what to do about it: SEA-RAFT marks the whole eel body invalid,
  the others only its outline.
- **Bubbles are the largest structured residual** on `distance`. SEA-RAFT,
  FlowIt and MOF render the plume as distinct motion; **WAFT does not
  represent it at all**. **Only MOF flags it** in the FB mask.
- **SEA-RAFT admits much larger extreme displacements** (max 22–26 px on
  1–3 px-median clips vs 5–17 px for the others). Inspecting them: individual
  suspended particles, which its own FB mask then flags as invalid specks.
  The others smooth them away at the flow stage.
- **WAFT has the best coverage and the tightest FB error tail of the four —
  by being the smoothest.** It is the consensus centre where texture is
  absent and the outlier where texture is present, does not represent the
  bubble plume, and has the worst warp residual on the clip with the most
  independent motion. Those are the same fact, not three.

**Failure cases / surprises:**

- **The `lights` clip is a structural problem for any MC-Warp metric, not a
  flow problem.** Warping cuts the residual 4.6–4.8× on `murky_eel` and
  `swimthrough` but only **1.19×** on `lights` — identically for all four.
  The dive light is *camera-mounted*, so the lit patch of sand travels with
  the camera and a scene point's radiance changes between frames. That is
  photometric, not geometric: flow tracks the texture correctly and the FB
  mask marks the hotspot **valid**, so the illumination change lands whole in
  the residual. A naive MC-Warp metric would score artificial-light footage
  as unstable no matter how good the flow or the restoration. Needs handling
  in Phase 1B design, not tuning.
- **The backends agree least exactly where they are most self-consistent.**
  On `murky_shark` (near-static, 0.03 px/frame, almost textureless) all four
  report 96–99 % FB-valid while disagreeing *with each other* by ~22 % of the
  motion magnitude (0.23–0.42 px median cross-backend EPE on 1.6 px median
  motion). Compare ~0.8 % on `murky_eel`. FB coverage measures
  self-consistency, not correctness: on textureless water a smooth field is
  trivially self-consistent in both directions while still being wrong.
- **FlowIt is not deterministic.** Two full bakeoff runs disagreed on its
  numbers, so this was measured under control (`determinism_check.py`, three
  `estimate()` calls on the identical pair in the identical process):
  SEA-RAFT, WAFT and MOF return **bitwise-identical** flow every time;
  FlowIt's forward flow differed by up to **0.858 px** (mean 0.149 px)
  between two identical calls, flipping **6.5 % of the FB-validity mask**
  (98.35 % → 91.81 %). Intermittent — the third run reproduced the first.
  **This corrects an earlier reading in this session:** run 1 showed FlowIt
  at 71.5 % on `MURKYSHARK` 8→9, which looked like a clean "collapses on
  textureless murk" story; run 2 put that pair at 99.3 % and degraded two
  others instead. The property is not *where* it fails but that it is not
  reproducible. Per this file's own operating loop, that makes "did the
  pipeline regress?" unanswerable, which is disqualifying for a metric
  backend independently of accuracy.
- **MOF's multi-frame context did not visibly help the swim-through** — the
  case it should most favour. Its flow, warp, residual and mask are
  indistinguishable from the pairwise models there. Where it *did* differ was
  the near-static murky clip and the bubble column, i.e. temporal ambiguity,
  not fast camera motion.
- **FlowIt's memory is quadratic in pixel count.** Its global ¼-resolution
  cost volume is ~4.3 GB at 960×540 before Sinkhorn temporaries; peak MPS
  allocation 22.8 GB. The first run fragmented the allocator, pushed the
  machine ~11 GB into swap and stalled until `gc.collect()` +
  `torch.mps.empty_cache()` between pairs was added to the runner. 1080p is
  not "slower" for FlowIt on this machine, it is out of reach — and a smaller
  FlowIt would not help, since the cost volume scales with pixels, not
  parameters.
- **WAFT is ~3× slower than SEA-RAFT here, not faster.** Its paper's "up to
  4.1× faster" is relative to methods of comparable accuracy; on MPS its
  DepthAnythingV2 ViT-S trunk runs plain PyTorch attention, since xformers is
  CUDA-only (and optional — it sits behind a `try/except ImportError`).
- **A wrapper bug the synthetic check caught before any real run:**
  VideoFlow's `InputPadder.pad()` takes one tensor and returns a tensor,
  while SEA-RAFT's and FlowIt's identically-named class (all three copied
  from RAFT) is variadic and returns a list. Indexing `[0]` sliced off the
  batch dimension. Exactly why the known-motion test exists.
- **No candidate was dropped or substituted, and only one used its one-fix
  allowance.** All four ran on their documented paths; no CUDA extension was
  built, no third-party source edited, no dependency downgrade chain. The one
  fix was WAFT's documented DepthAnythingV2-Small prerequisite (95 MB from
  HuggingFace), functionally redundant since the WAFT checkpoint already
  carries all 239 `da_feature.*` tensors.
- **Environment quirk:** the installed `uw` console script has a stale
  shebang (`~/Documents/code/uwrestore/.venv/...`) from before the repo
  moved. `python -m uw.cli` works; the script needs a reinstall. Not a code
  issue, noted so it isn't rediscovered.

**Next hypothesis (opinion, not a decision — the selection is deliberately
left open for Phase 1B):**

The backend choice is the *less* important half of what this session found.
The `lights` result says a plain MC-Warp residual measures camera-mounted
illumination change more than temporal instability, and no backend fixes
that — so **an illumination-invariant photometric term (per-frame gain/bias
fit, or a gradient/census-domain residual) should be settled before the
backend matters much.** Second, since the residual varies 8× across clips and
~2 % across backends, `MC-Warp@k` probably needs to report a *reduction
ratio* against the uncompensated residual rather than an absolute number.

On the backend itself: FlowIt is out on reproducibility alone. Of the rest,
SEA-RAFT is 3× faster than WAFT and ~25× faster than MOF, is deterministic,
and its conservative masking and visible particle-tracking make its failures
legible; WAFT has better coverage and a tighter error tail but achieves it by
smoothing over the motion that matters; MOF is the only one that flags
bubbles, at ~4× SEA-RAFT's amortised cost. My reading is **SEA-RAFT-M as the
working default, with MOF retained behind the `OpticalFlowBackend` interface
for spot-checks** — but the deciding experiment has not been run. That
experiment is the 30-second drift test (Week 8's actual gate): ~23 min for
SEA-RAFT, ~65 min for WAFT, ~95 min for MOF amortised. Everything measured
here is 3-frame excerpts, which say nothing about accumulation.

### Addendum (same session) — MC-Warp lag study @1/@4/@8, and WAFT

Two follow-ups, both prompted by review rather than by the original brief.

**WAFT-a1 added as a fourth backend.** SEA-RAFT's own README points at WAFT
as the same lab's "new efficient state-of-the-art" method — a direct
challenge to the axis the provisional recommendation rested on. It
integrated with **zero config changes** (`config/a1/tar-c-t.json` is already
`scale: 0`) and passed every synthetic check. One fix used: its documented
DepthAnythingV2-Small prerequisite (95 MB, HuggingFace). xformers not
installed — optional, behind `try/except ImportError`, CUDA-only.

Result: ~3× slower than SEA-RAFT (2.0–3.0 s vs 0.75), same memory class
(2.4 vs 2.2 GB), deterministic, **best FB coverage and tightest error tail of
the four**. But scored on a **common validity mask**
(`scripts/common_mask_compare.py`), SEA-RAFT is equal-or-better in **14 of 15**
clip-lag cells — so WAFT's advantage is masking policy, not correspondence
quality. Largest real gap: `swimthrough` @8, 5.615× vs 5.043× (11 %).

**Lag study, lags 1/4/8, 4 backends × 5 clips × 3 anchors × 2 directions.**

- **Coverage decays sharply with lag** (SEA-RAFT 97.0 → 90.8 → 83.4 %). An
  MC-Warp value is unreadable without its coverage, and two backends' @4/@8
  values are not measured on the same pixels.
- **`lights` degrades monotonically: 1.14× → 1.07× → 1.02×**, identical
  across all four to three significant figures. At @8 motion compensation
  explains ~2 % of the frame-to-frame change. The strongest result of the
  session, and entirely a metric-design problem.
- **The lags are not redundant.** `murky_shark` runs the other way — 1.37× →
  2.33× → 2.43× — because at @1 there is too little motion for warping to
  help at all.
- **VideoFlow-MOF cannot serve a multi-lag metric.** It emits flow between
  consecutive window frames, so lag-k needs a stride-k subsampled window,
  off its training distribution: coverage collapsed 36 points on
  `murky_shark` (95.1 → 63.1 %) with a visibly skewed warp. It then posts the
  *highest* reduction ratio on that clip (2.88×) by discarding 37 % of the
  frame — a live example of PLAN.md's "no scoring well by masking" rule.
- **FlowIt has no large-displacement advantage**, which was the last reason
  to revisit dropping it: mid-pack at every lag, 39.7 s/inference, 22.8 GB.

**Two readings I stated before checking, and had to correct:**
1. "WAFT doesn't detect independent motion" — overstated. It misses the
   low-contrast shark at `murky_shark` @8 but detects the high-contrast diver
   at `distance` @8 exactly like the others.
2. "WAFT silently includes regions where its own flow failed" — not
   supported. In the disputed 7.16 % band its residual is *lower* than
   SEA-RAFT's (0.00794 vs 0.00866). The region is simply harder for everyone.

Both were the same mistake: inferring a mechanism from a visualisation
before quantifying it. `common_mask_compare.py` was written in response and
should gate any future backend comparison.

**Leaderboard survey (Sintel/Spring/RobustSpring, and the papers behind
them):** nothing further is worth integrating. Sintel Final rank
**anti-predicted** these results — VideoFlow-MOF is 4th and FlowIt-XL 14th
(both disqualified here), while SEA-RAFT is absent from the top 15 and won
the common-mask test. The board's top is dominated by three-frame methods,
the class least suited to a multi-lag metric, and of its top six entries only
VideoFlow-MOF has a usable public release. MEMFOF and U2Flow are on a
watchlist in PLAN.md with explicit triggers; CFFlow, MemoFlow and FreeFlow-L
have no public implementation.

**Standing (recorded in PLAN.md, Phase 2A — result):** canonical SEA-RAFT-M;
optional cross-check WAFT-a1; research shelf VideoFlow-MOF at @1 only;
FlowIt dropped. Still a recommendation, not a selection.

**Next hypothesis (unchanged, and now better evidenced):** the backend was
never the constraint — four architectures agreed on warp residual within
~2 % on every clip. Phase 2B succeeds or fails on whether
`SEA-RAFT-M + canonical MC-Warp@1/4/8 + an input-derived illumination
diagnostic` yields a metric that moves when the pipeline changes and stays
put when it does not. Extend the metric, not the flow work.

---

## 2026-08-29 — Week 2 Phase 2B: real temporal-stability metric

**Hypothesis:** `SEA-RAFT-M + canonical MC-Warp@1/4/8 + an input-derived
illumination diagnostic` yields a temporal metric that moves when the pipeline
changes and stays put when it does not. Measurement only — no temporal
correction, no `--no-temporal`, no Week 3 work.

**Implementation.** The metric lives in `uw/metrics.py` (numpy + opencv only,
imports no flow model); the backend in `uw/searaft.py` (the only module in
`uw/` that touches torch, imported lazily); the report in `uw score
--temporal`. `uw/io.py` gained `load(..., start=, count=)` for a bounded
decode — a 756-frame 1080p clip in float32 is ~18 GB and a temporal metric
only needs a window. `pyproject.toml` is unchanged and the core venv still has
only numpy + opencv; temporal scoring runs from the Phase 2A `.venv-flow`
interpreter, which already has torch. Full writeup:
`experiments/week2b_temporal/FINDINGS.md`.

**Active pipeline stages:** ingest (sRGB EOTF → linear), gray-world, export.
Unchanged. This session built the evaluator, not a stage.

**Backend:** SEA-RAFT-M, princeton-vl/SEA-RAFT @ `9137517`, checkpoint
`MemorySlices/Tartan-C-T-TSKH-spring540x960-M`, `config/eval/spring-M.json`
with `scale=0`, MPS, torch 2.13.0. **The promoted wrapper returns bitwise
identical flow to the Phase 2A experimental one** (`np.array_equal`, max abs
diff 0.0), so no Phase 2A conclusion is disturbed by the move. 0.711 s median
per inference over 90 inferences; 2.42 GB peak MPS with two models loaded;
bitwise deterministic over repeat calls and at direct lag 3. Known limitation
carried forward: it invalidates smooth low-texture moving subjects as solid
blobs — the whole eel body — which is why coverage is part of every result.

**Data:** frozen test set, Phase 2A lag-study geometry reused verbatim —
41-frame window centred on the bakeoff excerpt, anchors at local 16/18/20,
identical across lags. swimthrough 181–221, murky_eel 636–676, murky_shark
0–40, lights 71–111, distance 246–286. Source 1920×1080 (1080×1920 decoded
for two clips); flow inference 960×544; **metric evaluation 960×540**
(540×960 portrait), linear-light `INTER_AREA`.

**Metrics before/after — the Week 1 placeholder is replaced, not moved.**
`temporal_stability()` (variance of per-frame mean RGB) is deprecated: it
establishes no correspondence, so it cannot tell scene motion from processing
instability. It is kept in `uw/metrics.py`, marked DEPRECATED, purely so the
pre-Phase-2B entries above stay reproducible — verified **both before and
after** this session's changes to `uw/metrics.py` and `uw/io.py`:
`temporal_stability(gray_world(f) for f in load('data/testset/murky/
MURKYSHARK.MP4'))` still returns `3.244860636186786e-05` bit-for-bit. `uw score` no longer
reports it. **There is therefore no before/after on a shared number; the
before is a different measurement.** From here the baseline is the table
below.

**Reproduces Phase 2A.** Motion-reduction ratio on unprocessed input, Phase 2A
lag study / this session: swimthrough 4.39/**4.33**, 5.37/**5.35**,
5.67/**5.67**; murky_eel 4.52/**4.51**, 5.11/**5.11**, 4.98/**4.98**;
murky_shark 1.37/**1.37**, 2.33/**2.33**, 2.43/**2.45**; lights
1.14/**1.12**, 1.07/**1.07**, 1.02/**1.02**; distance 2.66/**2.66**,
3.74/**3.74**, 3.79/**3.78**. Mean coverage 97.0/90.8/**83.3** % against
97.0/90.8/83.4 %. The two deliberate differences: the mask now also requires
finite resampling support, and pairs pool by valid-pixel count instead of
averaging per-pair means.

**New baseline — raw MC-Warp (linear-light L1), input → gray-world:**

| clip | @1 | @4 | @8 | coverage @1/@4/@8 | temporal ΔE00 @1 |
|---|---|---|---|---|---|
| murky_shark | 0.00409 → 0.01118 (**2.73×**) | 2.66× | 2.58× | 96.3 / 90.9 / 89.7 % | 1.04 → 3.47 |
| murky_eel | 0.02016 → 0.05229 (**2.59×**) | 2.46× | 2.27× | 97.1 / 89.0 / 78.4 % | 2.88 → 8.95 |
| swimthrough | 0.00932 → 0.02076 (**2.23×**) | 2.07× | 2.05× | 97.0 / 88.4 / 77.0 % | 2.55 → 5.08 |
| distance | 0.01525 → 0.02005 (**1.31×**) | 1.22× | 1.19× | 97.8 / 90.6 / 82.2 % | 2.39 → 3.58 |
| lights | 0.04119 → 0.04119 (**1.00×**) | 0.99× | 0.99× | 97.0 / 95.1 / 89.4 % | 5.04 → 5.14 |

**ΔE (chart) before/after:** unchanged, not touched. `data/testset/chart/` is
still empty, so chart ΔE remains unwired from `uw score`.

**Metric definitions, recorded so a future entry can tell a metric change from
a regression.**

- *Raw MC-Warp@k*: validity-masked, motion-compensated photometric residual.
  `MC-Warp = mean over M of (1/3)·Σ_c |W(I_{t+k})_c − I_t(p)_c|`, linear-light
  RGB, **L1** (stays in image units, comparable to Phase 2A's warp MAE, and
  far less dominated by bubbles/snow/thin structures than L2; Charbonnier's
  only edge over L1 is differentiability, which a measurement does not need).
  `M` = forward/backward-consistent (α = 0.01, β = 0.5, unchanged) ∧ inside
  the target ∧ finite bilinear support ∧ finite reference. Nothing clipped;
  non-finite excluded explicitly. Direct flow at every lag — `t → t+k` in one
  inference, never a composition of adjacent fields (asserted by test).
- *Canonical illumination-aware MC-Warp@k*: `Y_t ≈ gain·Y_W(t+k) + bias`, one
  scalar gain and one scalar bias on linear luminance applied identically to
  R/G/B, **fitted only on the aligned ORIGINAL frames**, frozen, then applied
  to the warped corrected frame. Chosen as the lowest-capacity form that can
  represent auto-exposure/ambient change and is *structurally incapable* of
  representing a red-only change — corrected-only chroma flicker survives it
  by construction, not by luck.
- *Estimator*: robust MAD-ratio/median start → FAST-LTS concentration (keep
  70 %, 8 steps) → fixed-scale Huber M-step (k = 1.345, 10 iters). Both extra
  stages were forced by measurement, not taste: plain Huber-from-least-squares
  took an exact 1.2500 gain to **0.04** on a 15 % high-leverage cluster (a
  bubble is an outlier in *both* frames at once), and re-estimating the Huber
  scale each iteration walked a converged 1.2500 back out to **1.1603**.
  Breakdown 30 %; measured gain at 0/5/15/40 % contamination: 1.2500 / 1.2500
  / 1.2396 / rejected.
- *Fit domain* (predeclared from the 8-bit sRGB source, never tuned on the
  clips): 0.0025 < Y < 0.95 linear (codes 8/255 and 250/255) in both aligned
  originals, ≥ 4096 px, MAD spread ≥ 0.005 (σ_a ≈ 1 %). On the frozen clips
  this excludes essentially nothing — the fit domain is 100.0 % of valid
  everywhere.
- *Two guards, both measured on the input alone*: gain outside [0.25, 4.0] is
  rejected; a transform that makes the input's own post-warp residual >1 %
  worse is rejected. Rejection falls back to identity, which makes the
  canonical value **equal** the raw one — strictly more conservative — and
  says so in `status`.
- *Uncompensated residual@k*: same L1, no warping, same mask/pair/lag/grid.
  *Motion-reduction ratio@k* = uncompensated / raw — descriptive context, not
  a replacement.
- *Temporal ΔE00*: same flow, same mask, existing `linear_rgb_to_lab` →
  `ciede2000` path, no second ΔE implementation. Near-black exclusion below
  Y = 0.0025 (one 8-bit code moves ΔE by several units there); on real
  footage this removes **0.02–0.05 %, and only on `lights`**.
- *Status bands* (predeclared): `low-coverage` below 50 %;
  `illumination-confounded` when uncompensated / illumination-aware < 1.25,
  i.e. geometry **and** the fitted model together explain under 20 % of the
  frame-to-frame change. A label never deletes a value; a score is `None`
  only when the mask is empty.
- **No weighted overall score exists**, and a test asserts no result field is
  named `overall`/`combined`/`score`.

**Coverage/validity statistics:** in the tables above; reported at every lag
beside every value, with a separate ΔE coverage. Coverage decays 97 → 89–95 →
77–90 % from @1 to @8, matching Phase 2A.

**Out-of-range statistics:** nothing is clipped anywhere in the metric, and a
test pins that gray-world's above-1.0 linear values are measured as they are.
The gray-world red-channel scale over these windows is **28.4× on murky_eel**,
17.1× murky_shark, 15.8× swimthrough, 3.8× distance, **0.91× lights**.

**Synthetic validation — 47 tests, ordinary venv, analytic flow backend.**
Integer translation @1/4/8: raw and illumination-aware **0.000000**.
Fractional (0.5, 0.25): 0.001334. Global gain 1.10: raw 0.041579 →
illumination-aware **0.000000**, fitted gain 0.9091 = 1/1.10 exactly.
Gain 1.08 + bias 0.03: raw 0.062065 → **0.000000**. **Corrected-only red
flicker: raw 0.034508, illumination-aware 0.034508 — identical to six
decimals** with input raw exactly 0 and fitted gain 1.0000/bias 0.00000.
One-frame spike: per-pair raw {0, 0, **0.100, 0.100**, 0}, ΔE {0, 0, **17.6,
17.6**, 0}. Blur: 0.001134 → 0.000413. Disocclusion: coverage 75.0 % with the
excluded change not leaking in, 100 % / 0.100000 with it included. Localised
light: global model explains **2.4 %**, status `illumination-confounded`.
Coverage gaming: 0.281250 @ 100 % vs **0.000000 @ 43.8 % with status
`low-coverage`**. Plus: exactly two inferences per pair; call sequence
`[(0,1),(1,0),(0,4),(4,0),(0,8),(8,0)]`; illumination fit byte-identical
across three wildly different corrected sequences; the returned result holds
no ndarray; residuals scale linearly with the data (which no gamma-domain or
clipping metric could).

**Alignment sensitivity — the companion is justified.** With a model-free
study (translate a real frame a known sub-pixel amount, warp back with the
exactly correct flow), integer offsets return **0.000000** and the half-pixel
floor is 0.0011–0.0232 — i.e. **11 % (lights), 24 % (distance), 26 %
(murky_shark), 68 % (swimthrough) and 115 % (murky_eel)** of the MC-Warp
actually measured on those clips. It concentrates on gradient structure (top
1 % of Sobel gradient carries 3–40× the bottom half's residual) and the maps
show coral edges and the thin rope, with open water at exactly zero. One fixed
1.0 px Gaussian companion, `alignment_robust_warp`, is therefore reported
**separately** — never replacing raw or canonical. It cuts the synthetic floor
3.3–4.5× and cleanly separates the two causes on real footage: murky_eel
44 % of raw (resampling-dominated) vs lights 98 % (illumination, not
alignment).

**`lights` — the mandatory falsification: Case C.** The bounded global
gain/bias model explains **0.3 % / 1.8 % / 12.3 %** of the input's post-warp
residual at @1/@4/@8; combined geometry+illumination reaches only 1.16× at @8,
below the predeclared 1.25×, so the clip is labelled **illumination-confounded
at all three lags**. At @8 the fit reaches gain 0.3243, bias +0.073, with one
of three pairs rejected as out-of-range — far outside anything describing
light, for 12 %. **The one allowed alternative was not exercised**, and the
reason is in the data: the failure is *spatial locality*, not functional form
(the synthetic localised-light case reproduces it exactly with the mechanism
isolated), and gradient/census/LNC are equally global recipes that would also
discard the low-frequency intensity information a restoration's most visible
failures live in.

**Surprises / things I got wrong and had to correct:**

- **"The metric is blind on `lights`" — asserted, then measured, then
  withdrawn.** Gray-world's real instability is invisible there (1.00×), and
  the first reading was that the illumination floor swamps it. Injecting a
  known corrected-only red flicker (`lights_falsification.py`) says otherwise:
  at 20 % amplitude, `lights` raw rises **1.179×** and its ΔE **2.031×**
  against `murky_shark`'s 1.154× and 1.163×. Relative sensitivity on the
  confounded clip is *as good or better* — artificial white light makes red
  bright, so a red perturbation is large in absolute terms. Gray-world's null
  result is gray-world's gains being ≈1 there, not the metric failing to see.
  Same mistake and same remedy as Phase 2A §A7: inferring a mechanism before
  quantifying it. The label's correct meaning is narrower — the *absolute*
  residual is not comparable across clips, the reduction ratio is
  uninformative (1.02–1.12×), and raw ≈ canonical.
- **A period-2 oscillation is invisible at every even lag.** Found because the
  injected flicker *lowered* MC-Warp@8: frames t and t+8 sit on the same phase
  and carry the identical gain. Confirmed synthetically (0.046289 @1,
  **0.000000 @2 and @4**) and pinned by a test. It is the concrete argument
  for reporting three lags — and it means the @1/@4/@8 set is blind to
  period-4 pumping at two of its three lags.
- **The sub-pixel resampling floor is the largest single component of MC-Warp
  on the textured clips**, and it is not correspondence error: the promoted
  wrapper measures 0.013 px endpoint error on a sequence of *identical
  content* and still reports MC-Warp 0.0133, because the true motion at the
  metric grid is fractional and must be resampled.
- **Plain Huber IRLS is not robust to the outliers this footage produces.** A
  bubble or a lit particle is an outlier in both frames at once, i.e.
  high-leverage, and an M-estimator that only bounds residual influence walks
  straight into it. Cost: two extra estimator stages, both forced by a
  measured failure.
- **My own known-motion test had the ground-truth sign backwards** (the crop
  origin moves opposite to the content), reporting 13.86 px EPE. The metric
  was right and the test was wrong — MC-Warp already read 0.0134 against
  0.1046 with the flow negated. The counterfactual is what caught it.
- **The eel body is not measured at all.** SEA-RAFT cuts it out as a solid
  blob; the moving animal a restoration is most likely to damage is exactly
  the region excluded. Coverage says how much, not what.

**Repeatability and the metric's error bar.** Repeating an identical
evaluation is **exact on every clip and lag**. Measuring the same window from
three anchor triples (16/18/20, 15/17/19, 17/19/21) gives an anchor spread of
1–6 % on most cells, with two outliers: murky_eel @1 at 17.4 % and **lights @1
at 39.1 %** — the latter enough on its own to make that cell unusable,
agreeing with the illumination-confounded label and pointing at the same cause
(three anchors, three positions of a moving beam). Gray-world's 2.05–2.73× on
four clips is an order of magnitude clear of this; `distance`'s 1.19–1.31×
against 4.8–6.1 % is smaller but still clear. Three overlapping triples in one
41-frame window is a small correlated sample — read it as a floor on
variability, not an estimate.

**Next hypothesis.** The instrument works: it reproduces Phase 2A, repeats
exactly, moves 2–3× under a pipeline change on four of five clips, refuses to
be fooled by input-derived illumination fitting, and says so out loud when it
cannot be trusted. Phase 2A's open question 2 is half-answered — the reduction
ratio is often the steadier statistic (6.4 % vs raw's 39.1 % on lights @1)
but not always (distance @1: 9.6 % vs 4.8 %), so it stays beside the absolute
residual rather than replacing it.

The next thing worth measuring is **the sub-pixel floor as a per-clip reported
quantity**. It is 68 % of the value on swimthrough and 115 % on murky_eel; it
is a property of the footage and the evaluation grid, not of the pipeline; and
it is the single reason two clips' absolute MC-Warp numbers are not comparable
today. Reporting it beside the score would fix that without redefining the
metric — and any *subtraction* would be a redefinition and must not happen
quietly. After that, the 30-second drift test (Week 8's actual gate, ~23 min
of SEA-RAFT per clip) is still the most informative unrun experiment in the
project; nothing measured so far says anything about accumulation.

### Addendum (same session) — WAFT promoted as a cross-check; experiments tree pruned

Both at the user's request, after the Phase 2B work above.

**`uw/waft.py` — WAFT-a1 promoted.** PLAN.md keeps it as "a periodic
cross-check, not a default. Where the two disagree materially, treat that
clip's MC-Warp as low-confidence", and that is easier to honour when a second
opinion is one command away rather than only reachable from the experiments
tree. Same contract as `uw/searaft.py`: torch imported lazily inside
`__init__`, `pyproject.toml` untouched, never a default, never run
automatically during scoring, never averaged with SEA-RAFT. `uw score
--temporal --flow-backend waft` works and prints a warning that its values are
not comparable to a SEA-RAFT run value-for-value.

**A collision Phase 2A could not have found, because it ran one backend per
process.** SEA-RAFT and WAFT both ship top-level `config/`, `model/` and
`utils/` packages. With SEA-RAFT's `core/` on `sys.path` first, WAFT's
`from utils.utils import Padder` resolves to SEA-RAFT's `core/utils/utils.py`
and raises `ImportError`. Both wrappers now import inside
`uw.flow.isolated_repo_imports`, which restores `sys.path` and evicts from
`sys.modules` exactly those modules loaded from the given checkout — and
nothing else, because evicting a torch submodule would make a later import
build duplicate classes and quietly break `isinstance`. Verified: either
construction order works, WAFT is deterministic, and constructing WAFT leaves
an already-constructed SEA-RAFT bitwise unchanged. 3.48 GB peak MPS with both
resident; WAFT ~1.7–3.0 s/inference against SEA-RAFT's 0.71.

**`compare_backends_common_mask` / `uw crosscheck`.** Promoting WAFT without
this would have exposed the wrong way to use it. Two backends' residuals are
computed over *different* valid pixels, so comparing them directly measures
masking policy; PLAN.md and Phase 2A §A6 both say to score on the
intersection. The function takes only the ORIGINAL sequence (a correspondence
question — no corrected output takes part), costs four inferences per
(anchor, lag), uses a 0.5 % tie band, and reports a **tally of cells, not an
aggregate score**.

Reproduces Phase 2A on real footage:

| clip | lag | searaft cov | waft cov | searaft red | waft red | winner |
|---|---|---|---|---|---|---|
| swimthrough | @1 | 97.0 % | 97.0 % | 4.338 | 4.298 | searaft |
| swimthrough | @4 | 88.4 % | 88.6 % | 5.357 | 5.150 | searaft |
| swimthrough | @8 | 77.0 % | 77.4 % | **5.671** | 5.187 | searaft |
| murky_shark | @1 | 96.3 % | 96.1 % | 1.374 | 1.368 | tie |
| murky_shark | @4 | 90.9 % | **97.8 %** | 2.331 | 2.340 | **tie** |
| murky_shark | @8 | 89.7 % | **96.8 %** | 2.458 | 2.469 | **tie** |

Phase 2A's headline cell (`swimthrough @8`, single anchor) was 5.615 vs 5.043;
pooling three anchors gives 5.671 vs 5.187 — same result, same magnitude. And
`murky_shark` is the demonstration of why the common mask matters at all: WAFT
measures **7 points more of the frame** at @4/@8, which on its own mask reads
as an advantage, and on the pixels both accept the two are indistinguishable.

Cross-backend disagreement is reported beside every verdict and grows with
lag — `swimthrough` median 0.145 / 0.427 / 0.971 px at @1/@4/@8, rising to
0.770 / 2.265 / 4.569 px inside the band where the two masks disagree. Where
the masks disagree, so does the flow, by 3–5×. **No threshold for "materially"
is hard-coded:** what counts as material depends on the clip's own motion
magnitude, and a number tuned against the frozen clips is what PLAN.md
forbids. The command prints the disagreement and the rule.

**Experiments tree pruned.** `backends/searaft_backend.py` and
`waft_backend.py` deleted — they were now duplicates, and two copies of a
wrapper are two copies that can drift. `backends/flowit_backend.py` deleted:
FlowIt was disqualified on reproducibility (Phase 2A §5) and §A8 removed the
last reason to revisit it. `backends/videoflow_backend.py` (MOF) **kept** — it
is the only backend that flagged the `distance` bubble column, which is a
named future use, and it runs in its own `.venv-videoflow` where the collision
above cannot arise.

**Phase 2A remains fully reproducible.** `build_backend()` now constructs the
promoted classes; `synthetic_check` passes for both (`all_pass: true`); the
aggregation scripts already skipped absent backends, so the historical FlowIt
columns still regenerate from the persisted output on disk while a fresh run
simply omits them. `common.model_input_srgb_u8` is now a re-export of the one
definition in `uw/flow.py`.

Not reclaimed, and worth a decision later: `vendor/FlowIt` (680 KB) and
`checkpoints/flowit` (345 MB) are still on disk. The README's `gdown` command
reinstates them.

**Tests: 176 pass** (108 Week 1 + Phase 2A, 52 temporal, 16 backend plumbing).
The new backend tests need no torch: lazy-import behaviour, missing
checkout/checkpoint errors naming the fix, each repo's padding arithmetic,
`isolated_repo_imports` (including that unrelated modules survive and that
state is restored when the body raises), and that WAFT is never a CLI default.

---

## 2026-08-29 — Week 2 Phase 2C/2D: white-patch, CLAHE, signal diagnostics, pipeline/ablations

**Hypothesis:** none stated in advance — this is the mechanical closer for
Week 2, not a new experiment. Goal: implement the two remaining baselines
(white-patch, CLAHE), cheap signal-recoverability diagnostics, ordered
pipeline composition with per-stage ablations, and reuse flow/illumination
across correction configurations, then run all of it once against the
frozen test set. Does not touch flow, MC-Warp definitions, illumination
fitting/guards, or ΔE00 — all frozen and reused unchanged.

**Active pipeline stages added:** `white_patch`, `clahe` (`uw/baselines.py`).
`gray_world` unchanged. Composable via `--pipeline stage1 stage2 ...` or the
backward-compatible `--method <stage>` alias, with `--no-<stage>` ablations
for every implemented stage (`--no-gray-world`, `--no-white-patch`,
`--no-clahe`) — see "Pipeline" below.

### White-patch

**Bright-region estimator**, frozen before any real clip was inspected:
top `WHITE_PATCH_TOP_PERCENTILE = 99.0` (brightest ~1%) of pixels by
`uw.metrics.linear_luminance` (the project's one luminance definition,
reused rather than redefined), then the per-channel **median** RGB over
that region. The percentile keeps a semantic bright object or the whole
frame from mattering; the median keeps one hot pixel/bubble glint/specular
speck inside that region from dominating (confirmed:
`test_white_patch_isolated_hot_pixel_does_not_dominate` — a single 50.0
magenta pixel among 1600 moves the gain by <10%).

**A real robustness bug in this estimator, found by adversarial testing
after the evaluation had already been run and logged.** The percentile rule
above is correct on real footage but was silently degenerate on small
frames: `ceil(n_pixels * 1%)` rounds down to **exactly one pixel** for any
frame under ~100 px, at which point "median over the bright region"
*becomes* the single-brightest-pixel rule the Phase 2C brief explicitly
forbids. Measured before the fix: on a 10x10 frame, one pathological hot
pixel drove the derived gain to **5e7×**. The existing hot-pixel test did
not catch it because it used a 40x40 frame (16 pixels selected) — a test
that passed while the property it named was false.

Fixed with `WHITE_PATCH_MIN_BRIGHT_PIXELS = 9`, a well-posedness floor on
the region size, modeled on the codebase's existing `ILLUM_MIN_FIT_PIXELS`
identifiability guard rather than being a tuned parameter: a median rejects
up to `floor((n-1)/2)` outliers, so n = 9 tolerates 4 (~44% breakdown) and
is the smallest round size at which the median is meaningfully robust
rather than nominal. Selection also moved from an interpolated
`np.percentile` to the exact n-th-largest order statistic, so `n_bright`
means what it says, with `>=` still admitting everything tied at the
threshold (a clipped/saturated plateau is kept whole). **The floor binds
only below ~900 px; at the 960x540 metric grid 1% is 5184 px and at 1080p
20736 px, so it changes nothing on real footage — verified by recomputing
all 205 per-frame gains on all five frozen clips and confirming they are
bitwise identical to the logged run, before and after the fix.** Post-fix,
the same hot pixel moves the gain by 0.15% instead of 5e7×.

**Gain**: `gain_c = max(reference) / reference_c` — a von-Kries "max-white"
normalization, so at least one channel keeps gain 1 (the reference doesn't
get globally darkened to hit a channel that's already dim). Denominator
floored at `1e-6` purely for zero-safety, not as a gain cap — an extreme
finite gain is left visible (`white_patch_out_of_range_fraction`), matching
`gray_world`'s existing no-clamp convention. When the entire bright region
is black (`target <= 1e-6`) there is no illuminant to estimate at all, and
the gain is recorded as **identity** rather than the 0.0 the formula would
otherwise produce — numerically equivalent on such a frame (it is black
everywhere by construction, since that region holds its brightest pixels)
but honest provenance, since a reader seeing gain 0.0 would reasonably
conclude the stage had zeroed the image. Metadata recorded:
`white_patch_channel_gain`, `white_patch_reference_rgb`,
`white_patch_bright_region_fraction`, `white_patch_top_percentile`,
`white_patch_out_of_range_fraction`. Deterministic (bit-identical on
repeat), never mutates input.

**Not physically correct restoration** — a baseline, same status as
gray-world.

### CLAHE

Pathway: linear RGB → `linear_luminance` (Y, reused) → `y_to_lstar` (new,
`uw/colorspace.py` — the scalar special case of `xyz_to_lab`'s L* branch,
sharing its exact epsilon/kappa constants and un-clamped for the same
reason: L* > 100 is meaningful for out-of-range Y) → uint16 quantization →
`cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))` (fixed OpenCV
defaults, not tuned) → `lstar_to_y` (exact inverse, mirroring
`lab_to_xyz`'s `yr` branch) → `RGB' = RGB * (Y'/Y)` luminance-ratio
reconstruction. Never independently equalizes R/G/B. Public contract stays
floating linear RGB — no uint16/L* intermediate leaks into the returned
`Frame`.

**Range handling**: L* is computed unclamped and reported as such; it is
clamped to `[0, 100]` **only** for the temporary uint16 control signal
(`clahe_control_bounded_fraction` records how much of the frame needed
that), never for the returned diagnostics or image.

**Near-black policy — found and fixed a real bug during implementation.**
The brief's own concern ("do not divide by an arbitrarily tiny Y and then
clip the result") was addressed with an explicit branch: below
`CLAHE_NEAR_BLACK_Y` (== `uw.metrics.ILLUM_FLOOR_LINEAR`, the same
project-wide floor used everywhere else, not a fourth invented number),
luminance-ratio division is skipped entirely. The first version of that
branch output CLAHE's own `Y'` directly for near-black pixels, on the
reasoning that division was the only danger. It wasn't: verified directly
that `cv2.createCLAHE().apply()` on a perfectly flat uint16 tile — any
value, not just zero — returns the tile's **maximum** representable value
(`65535`, confirmed with `np.unique`), a textbook histogram-equalization
degeneracy. A pure-black 8x8 test frame therefore came out **pure white**
(`[1,1,1]` per pixel) under the first implementation — the exact opposite
of "preserve genuinely near-black pixels." Fixed by having the near-black
branch pass the original pixel through **unchanged** instead: numerically
exact, no dependence on CLAHE's degenerate behavior at all, and a flat
near-black region (frame edge, shadow, letterbox) stays exactly as dark as
it was. `test_clahe_near_black_reconstruction_is_stable_and_unchanged` and
`test_clahe_flat_region_pathology_is_isolated_to_non_near_black_tiles`
pin both the fix and the underlying OpenCV property so it can't silently
regress or be mistaken for a bug report later.

**Chromatic preservation is exact**, not merely bounded: since every
non-near-black pixel is scaled by the same per-pixel scalar on R, G and B,
channel ratios are unchanged to floating-point precision (`rtol=1e-4` in
`test_clahe_preserves_chromaticity_away_from_near_black`) — there is no
clipping anywhere in this stage to break that.

**Amplification just above the near-black guard — adversarially probed, and
it is legitimate rather than a §7 violation.** The guard only protects
`Y <= 0.0025`; immediately above it the luminance-ratio branch is live and
can apply a large scale (measured up to ~34× on a dark region sitting
beside a bright one). Section 7 forbids "huge RGB amplification caused
purely by *ill-conditioned* `Y_prime / Y`", so the distinction had to be
measured rather than assumed, and it is testable in two parts:
*bounded* — the guard caps the denominator, so the scale can never exceed
`1.0 / 0.0025 = 400×` by construction; and *well-conditioned* — perturbing
the input luminance by 1e-9 through 1e-5 leaves the output identical to
1e-3 relative, which is what ill-conditioning would actually have shown up
as. So the large scale is CLAHE genuinely lifting shadows, deterministic
and reproducible, not numerical instability. Both properties are now pinned
by `test_clahe_amplification_above_the_near_black_guard_is_bounded_and_stable`.
The real consequence worth recording is a §27 one, not a §7 one: a ~34×
lift on near-floor content amplifies whatever is there, and at those levels
that is substantially sensor/codec noise — chroma-preserving amplification
of shadow noise is exactly the "noise amplification" CLAHE inspection is
supposed to look for.

**Known limitation, not fixed, on purpose**: the flat-tile-to-maximum
property above is not unique to near-black. A perfectly or nearly flat
MID-brightness tile (e.g. distant open water) is pushed toward the tile
ceiling too and is NOT protected by the near-black branch — confirmed
(`test_clahe_flat_region_pathology_is_isolated_to_non_near_black_tiles`: a
flat 0.5 frame comes out with `max > 0.9`). This is standard CLAHE/HE
behavior, not a bug in this implementation, and CLAUDE.md forbids tuning
CLAHE after inspecting results — recorded as a limitation rather than
patched.

### Frame-contract enforcement — a silent data-destruction bug

`Frame` documents "image is floating point" as an invariant, and
`uw.io.load` always produces float32, but **nothing enforced it and the
failure mode was silent destruction rather than an error**. Measured: a
uint8 `Frame` through `clahe` returned an **all-zero image** — no
exception, no warning — because every stage computes in float and then
does `corrected.astype(image.dtype)`, which truncates fractional linear
values to 0. `gray_world` had the same latent bug, silently truncating each
corrected value back to an integer code (128 -> 133 instead of 133.4).

All three stages now go through `_require_float_image`, which raises a
`TypeError` naming the fix. This is the one place this session touches
Week 1 behaviour, and deliberately: the input it now rejects already
violated `Frame`'s documented invariant, no legitimate caller produces it
(grepped — nothing in `uw/` or `tests/` constructs a non-float Frame), and
CLAUDE.md's whole ingest philosophy is to fail clearly rather than corrupt
quietly. `float64` still passes; the invariant is "floating", not
"float32".

Also fixed alongside it: casting a NaN to uint16 is undefined behaviour in
numpy (it warns and produces an arbitrary code, which then enters that
tile's CLAHE histogram). The temporary control signal is now
`nan_to_num`-sanitised **before** the cast — the returned image is
untouched, so a non-finite input pixel still propagates to a non-finite
output pixel rather than being silently repaired. Contamination was
measured to be local either way: one NaN changes nothing outside its own
tile neighbourhood (asserted exactly, `difference.max() == 0.0`).

Two smaller edge cases closed in the same pass: a zero-size frame produced
a silent `NaN` near-floor fraction (plus two RuntimeWarnings) and a
`ZeroDivisionError` in the aggregate path — both now raise clearly, because
a NaN reaching the report reads as a measured value; and `"pipeline"` is
documented as a RESERVED metadata key, since `apply_pipeline` writes it
unconditionally (namespacing it against arbitrary caller keys would mean
the general provenance framework the brief rules out).

### Signal diagnostics (`uw/diagnostics.py`, new module)

Per RGB channel: `near_floor_fraction` (≤ `NEAR_FLOOR_THRESHOLD`) and
`saturation_fraction` (≥ `SATURATION_THRESHOLD`).

- `NEAR_FLOOR_THRESHOLD` **is** `uw.metrics.ILLUM_FLOOR_LINEAR` (0.0025,
  linear ≈ sRGB code 8/255) — the literal same object, not a second number
  chosen to match it (`test_near_floor_reuses_the_illumination_fit_floor_constant`
  asserts `is`, not `==`). One project-wide threshold, as CLAUDE.md asked.
- `SATURATION_THRESHOLD = 1.0` exactly, not a "near" band like the floor:
  for an 8-bit-quantized source (`transfer_function` `srgb`/`protune`),
  code 255 maps through `srgb_to_linear` to floating-point-exact 1.0
  (`pow(1.0, x) == 1.0`), so `>= 1.0` precisely identifies source clipping
  on those profiles. For `raw_linear` that equality carries no such
  guarantee, and the report says so next to the number rather than
  asserting a conclusion the source encoding doesn't support.
- `out_of_range_fraction` factored out of `gray_world`'s inline computation
  into a shared helper, used identically by `gray_world`, `white_patch`,
  `clahe`, and the pipeline-level "Post-correction range" report.
- `correction_gain(metadata, stage)` looks up a stage's own
  `<stage>_channel_*` key; returns `None` for `clahe` (no single global
  per-channel gain — explicitly not padded with a fake one).
- **Original-versus-corrected semantics, verified, not just asserted**:
  `test_correction_does_not_overwrite_the_original_near_floor_evidence`
  computes `signal_diagnostics` once on the original frame, applies
  `white_patch`, and confirms the original object's near-floor fraction is
  unaffected — while the corrected frame's own (separately computed)
  near-floor fraction is lower, demonstrating exactly the trap CLAUDE.md
  warns about: a lower corrected-frame near-floor fraction is a fact about
  the multiply, not evidence of recovered signal.
- **No SNR/noise metric exists.** `test_no_field_is_labeled_snr_or_noise`
  greps every diagnostics/metadata key produced by this session's code for
  "snr"/"noise", case-insensitive. Real SNR/noise characterization remains
  deferred until controlled flat/chart regions exist, per CLAUDE.md — not
  attempted this session.

### Pipeline (`uw/cli.py`)

`STAGES = {gray_world, white_patch, clahe}`, `ABLATION_DEST` maps each to
its own `--no-<stage>` flag — no placeholder flags for unimplemented
stages. `apply_pipeline(frames, requested_stages, ablated_stages)` runs
`result = stage(result)` in order, with a top-level `pipeline` key
recording `requested`/`executed`/`ablated`/`stages`/`out_of_range_fraction`.
`--pipeline` and `--method` are mutually
exclusive, checked (and reported) **before** any frame is decoded.
`--method <stage>` remains a backward-compatible single-stage alias;
`--method none` (or an empty pipeline) is identity. Stages are never
auto-stacked — requesting `gray_world` alone never pulls in `white_patch`.

**A real argparse bug found and fixed while writing the CLI wiring.**
`score`'s historical default was `--method gray_world`; the first
implementation kept that as argparse's own `default="gray_world"`. That
meant `uw score clip.mp4 --pipeline white_patch clahe` (no `--method` typed
at all) parsed with `args.method == "gray_world"` **and**
`args.pipeline == [...]` simultaneously, which `_resolve_stage_list`
correctly read as an explicit, ambiguous `--method`+`--pipeline` and
rejected — a real user typing only `--pipeline` would have hit "mutually
exclusive" with no `--method` visible anywhere in their own command.
Fixed by making argparse's own default **always** `None` on `--method` for
every subcommand, and moving the "apply `gray_world` if the user genuinely
passed neither flag" default into `_resolve_stage_list` itself (a
`default_method` parameter, applied only when `method is None` reached that
point on its own). `test_score_pipeline_only_is_not_treated_as_ambiguous`
pins the fix; `test_score_rejects_ambiguous_method_and_pipeline_before_touching_the_file`
confirms the genuine ambiguous case still fails, and fails before decoding
anything.

**A metadata-collision bug, found adversarially by asking what happens when
the same stage appears twice.** Different stages namespace their own keys
(`gray_world_*` / `white_patch_*` / `clahe_*`) and provably never collide —
verified by computing the three key-sets and intersecting them. But
`--pipeline white_patch white_patch` is legal, and the second application's
flat keys simply **overwrote the first's**: measured, the pipeline recorded
gain 1.0× (the second, near-identity re-application) and silently lost the
first's real 2.43× correction. That is precisely the "do not accidentally
overwrite prior-stage metadata" case in §15, and §15 also prescribes the
remedy — "use a small explicit per-stage structure rather than inventing a
general provenance framework."

So `pipeline["stages"]` is now an **ordered list, one entry per executed
stage**, each holding exactly the metadata that stage added or changed plus
its own post-stage out-of-range fraction. Nothing is lost to a repeated
stage, and per-stage gains are attributable to a *position in the order*
rather than to a key name. The flat `<stage>_*` keys are still written
(last-writer-wins) so existing readers keep working. The delta computation
is deliberately defensive about `!=` on numpy-valued metadata (a Frame's
metadata is caller-controlled; `uw.metrics`' own `metric_resized_from` is
array-ish), treating an ambiguous comparison as "changed" so it
over-reports rather than silently dropping a diagnostic.

### Evaluation reuse across correction configurations (`uw/flow.py`)

`CachingFlowBackend` wraps any `OpticalFlowBackend` and memoizes
`estimate()`. **A second real bug, found the same way** — by actually
running the multi-configuration batch evaluation rather than trusting the
design: the first implementation keyed the cache on `id(frames)` (the
sequence container). `uw.metrics.evaluate_temporal` does
`original = list(original)` unconditionally on entry — frozen, unmodified
code — which builds a **new** list object on every single call, even for
the exact same underlying data. `id(frames)` therefore missed on every
call: a live run reported `0 hits / 108 misses` where reuse should have
given `90 hits / 18 misses`. Fixed by keying on
`(id(frames[index_t]), id(frames[index_t1]))` instead — `list(x)` copies
references, not the `Frame` objects themselves, so the objects actually
being compared keep stable identity across the rewrap even though their
container doesn't. Both bugs were caught by exercising the actual batch
harness once and reading the reported hit/miss counters against the
predicted `18 misses (first config) + 90 hits (remaining five)`, not by
inspecting the code — the same "run it, don't just reason about it" lesson
Phase 2A/2B logged repeatedly.

Confirmed **bit-identical** to the ordinary (non-cached, per-call resize)
path before trusting any cached number: `raw_warp`, `illumination_aware_warp`,
`valid_fraction` and the fitted illumination `gain` compare exactly equal at
every lag between a batch-harness run and an independent `evaluate_temporal`
call with `eval_long_side=960` (`experiments/week2c2d_baselines/scripts/
run_baseline_eval.py::_verify_reuse_is_lossless`, run automatically before
every full evaluation unless `--no-verify`). `uw.metrics.evaluate_temporal`
/ `evaluate_temporal_pair` are byte-identical to before this session — the
reuse mechanism lives entirely on the `OpticalFlowBackend` side of the
interface, exactly as required.

**Superseded by the review fixes below.** The first implementation cached
only the FLOW and let each configuration recompute the FB mask, the warped
original and the illumination fit. That measured 90 cache hits / 18 misses
per clip and I argued in this entry that recomputation was sufficient
because it is deterministic. An external review rejected that argument, and
was right to: the brief asks for the *validity information* and the
*illumination transform* to be reused, not just the flow, and — because of
AR-01 below — recomputation was not even guaranteed to be identical, since
the mask a variant was fitted on could depend on that variant's own output.

`uw/metrics.py` now exposes `PreparedPair` / `prepare_temporal_pair` /
`prepare_temporal_pairs`: all ORIGINAL-derived state (both flow fields, the
FB validity mask, the warped original, and the accepted illumination
transform including its guard) is computed **once per (anchor, lag)** and
handed to every configuration via `evaluate_temporal(...,
prepared_pairs=...)`. Measured after the change: **18 inferences per clip,
full stop** — not 108 requests served by a cache, but 18 real calls and
zero further backend traffic, with the mask and fit provably identical
across all six configurations because they are the same objects.

**AR-01 — corrected output could shrink its own evaluation domain.** The
mask included `ok_corr` and the corrected frame's own finiteness, and that
mask was then passed to `fit_illumination`. A correction emitting
non-finite output therefore excluded exactly the pixels it had damaged and
perturbed the supposedly original-only fit. Reproduced: corrected-only NaN
moved coverage **1.0000 → 0.5333**. The mask is now
`fb_valid & ok_orig & isfinite(original)` — correction-independent by
construction — and non-finite corrected output is REPORTED via a new
`corrected_nonfinite_fraction` rather than masked away. None of this
phase's three stages can produce non-finite output from finite input, so
no logged number was affected, but the evaluator no longer permits it.

Both fixes touch frozen Phase 2B code, which this phase's brief forbade;
they were made only after explicit authorisation to modify any phase's
code. All 52 Phase 2B synthetic tests still pass unchanged, and the `none`
and `gray_world` rows still reproduce the Phase 2B table exactly.

### Frozen test-set evaluation

Six configurations — `none`, `gray_world`, `white_patch`, `clahe`,
`gray_world→clahe`, `white_patch→clahe` — on all five frozen clips, at
**Phase 2B's exact geometry** (same clip, same start index, same 41-frame
window, same anchors 16/18/20, same 960-long-side grid) so this table sits
directly beside the Phase 2B one rather than being a new, incomparable
measurement. Chart ΔE00: **still unavailable** — `data/testset/chart/` is
still empty; not fabricated.

**Validation before trusting any of it**: `none`'s and `gray_world`'s raw
MC-Warp numbers reproduce Phase 2B's real-footage table **exactly** —
distance 0.01525→0.02005, lights 0.04119→0.04119, murky_eel
0.02016→0.05229, murky_shark 0.00409→0.01118, swimthrough 0.00932→0.02076,
all six figures matching to 5 decimal places — and `gray_world`'s mean
red-channel gain over the window matches Phase 2B's reported figures on
all five clips (28.43× murky_eel vs 28.4× logged, 17.07× murky_shark vs
17.1×, 15.85× swimthrough vs 15.8×, 3.84× distance vs 3.8×, 0.91× lights vs
0.91×). This session's pipeline plumbing and the caching backend introduce
zero numerical drift relative to the frozen Phase 2B path.

**Raw MC-Warp@1 / reduction / coverage, all six configurations:**

| clip | none | gray_world | white_patch | clahe | gray_world→clahe | white_patch→clahe |
|---|---|---|---|---|---|---|
| swimthrough (cov 97.0%) | 0.00932 (4.33×) | 0.02076 (2.83×) | 0.09292 (2.33×) | 0.01944 (3.75×) | 0.03807 (2.54×) | 0.13298 (2.06×) |
| murky_eel (cov 97.1%) | 0.02016 (4.51×) | 0.05229 (2.59×) | 0.07035 (2.66×) | 0.03669 (3.93×) | 0.08008 (2.57×) | 0.09058 (2.62×) |
| murky_shark (cov 96.3%) | 0.00409 (1.37×) | 0.01118 (1.10×) | **1.43496 (1.01×)** | 0.00590 (1.45×) | 0.01521 (1.12×) | **1.43110 (1.01×)** |
| lights (cov 97.0%, confounded) | 0.04119 (1.12×) | 0.04119 (1.12×) | 0.04762 (1.10×) | 0.04640 (1.22×) | 0.04832 (1.21×) | 0.05507 (1.18×) |
| distance (cov 97.8%) | 0.01525 (2.66×) | 0.02005 (2.31×) | 0.02083 (2.42×) | 0.02858 (2.38×) | 0.03496 (2.17×) | 0.03469 (2.25×) |

**Complete per-configuration record.** The quick-glance table above is @1
only; CLAUDE.md Phase 2C/2D §26 and the final-summary format ask for
raw/illumination-aware/alignment-robust MC-Warp, the uncompensated
residual, motion-reduction ratio, temporal ΔE00, valid coverage and status
at every lag, for every configuration — recorded in full below rather than
left only in the (gitignored, local-only) JSON. Original per-channel
near-floor/saturation fractions are a property of the source, so they are
listed once per clip, not once per configuration; out-of-range fraction and
gains DO vary per configuration and are tabulated per configuration.

**Original input signal diagnostics** (per clip, constant across
configurations):

| clip | near-floor R | near-floor G | near-floor B | ceiling R | ceiling G | ceiling B |
|---|---|---|---|---|---|---|
| swimthrough | 0.3604 | 0.0000 | 0.0000 | 0.0000 | 0.0023 | 0.0087 |
| murky_eel | 0.2901 | 0.0000 | 0.0001 | 0.0000 | 0.0072 | 0.0208 |
| murky_shark | 0.1525 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| lights | 0.0000 | 0.0010 | 0.0005 | 0.0113 | 0.0111 | 0.0062 |
| distance | 0.0334 | 0.0000 | 0.0000 | 0.0000 | 0.0064 | 0.0156 |

**Post-correction out-of-range fraction, all six configurations:**

| clip | none | gray_world | white_patch | clahe | gray_world→clahe | white_patch→clahe |
|---|---|---|---|---|---|---|
| swimthrough | 0.00% | 0.60% | 7.70% | 2.51% | 1.20% | 11.83% |
| murky_eel | 0.00% | 0.97% | 2.66% | 5.90% | 2.41% | 6.02% |
| murky_shark | 0.00% | 0.00% | 31.87% | 0.00% | 0.00% | 31.94% |
| lights | 0.00% | 0.46% | 0.11% | 0.62% | 0.86% | 0.75% |
| distance | 0.00% | 0.79% | 0.48% | 4.70% | 2.77% | 4.66% |

**`swimthrough`** (source 1080x1920, frames 181-221):

| config | lag | raw | illum-aware | AR | uncomp | reduction | ΔE00 | coverage | status |
|---|---|---|---|---|---|---|---|---|---|
| none | @1 | 0.00932 | 0.00933 | 0.00643 | 0.04037 | 4.33x | 2.554 | 97.0% | ok |
| none | @4 | 0.01268 | 0.01271 | 0.00947 | 0.06788 | 5.35x | 3.191 | 88.4% | ok |
| none | @8 | 0.01434 | 0.01426 | 0.01193 | 0.08134 | 5.67x | 3.571 | 77.0% | ok |
| gray_world | @1 | 0.02076 | 0.02076 | 0.01501 | 0.05872 | 2.83x | 5.081 | 97.0% | ok |
| gray_world | @4 | 0.02620 | 0.02619 | 0.01999 | 0.08895 | 3.39x | 6.297 | 88.4% | ok |
| gray_world | @8 | 0.02940 | 0.02910 | 0.02441 | 0.10318 | 3.51x | 7.351 | 77.0% | ok |
| white_patch | @1 | 0.09292 | 0.09279 | 0.07110 | 0.21606 | 2.33x | 7.350 | 97.0% | ok |
| white_patch | @4 | 0.11995 | 0.11890 | 0.09674 | 0.31134 | 2.60x | 9.044 | 88.4% | ok |
| white_patch | @8 | 0.14662 | 0.15376 | 0.12494 | 0.39008 | 2.66x | 9.230 | 77.0% | ok |
| clahe | @1 | 0.01944 | 0.01949 | 0.01521 | 0.07287 | 3.75x | 3.316 | 97.0% | ok |
| clahe | @4 | 0.02735 | 0.02759 | 0.02275 | 0.11602 | 4.24x | 4.267 | 88.4% | ok |
| clahe | @8 | 0.02783 | 0.02839 | 0.02383 | 0.13209 | 4.75x | 4.541 | 77.0% | ok |
| gray_world_clahe | @1 | 0.03807 | 0.03812 | 0.02901 | 0.09684 | 2.54x | 6.177 | 97.0% | ok |
| gray_world_clahe | @4 | 0.04748 | 0.04765 | 0.03787 | 0.14047 | 2.96x | 7.612 | 88.4% | ok |
| gray_world_clahe | @8 | 0.04848 | 0.04908 | 0.04013 | 0.15618 | 3.22x | 8.515 | 77.0% | ok |
| white_patch_clahe | @1 | 0.13298 | 0.13293 | 0.10351 | 0.27369 | 2.06x | 8.725 | 97.0% | ok |
| white_patch_clahe | @4 | 0.16757 | 0.16677 | 0.13711 | 0.37990 | 2.27x | 10.763 | 88.4% | ok |
| white_patch_clahe | @8 | 0.19291 | 0.20076 | 0.16299 | 0.45941 | 2.38x | 10.790 | 77.0% | ok |

**`murky_eel`** (source 1080x1920, frames 636-676):

| config | lag | raw | illum-aware | AR | uncomp | reduction | ΔE00 | coverage | status |
|---|---|---|---|---|---|---|---|---|---|
| none | @1 | 0.02016 | 0.02024 | 0.00888 | 0.09102 | 4.51x | 2.881 | 97.1% | illumination-fitted(2/3 pairs); identity:no-input-residual-reduction |
| none | @4 | 0.02510 | 0.02507 | 0.01273 | 0.12818 | 5.11x | 3.665 | 89.0% | ok |
| none | @8 | 0.02945 | 0.02925 | 0.01684 | 0.14653 | 4.98x | 4.215 | 78.4% | ok |
| gray_world | @1 | 0.05229 | 0.05230 | 0.02704 | 0.13568 | 2.59x | 8.945 | 97.1% | illumination-fitted(2/3 pairs); identity:no-input-residual-reduction |
| gray_world | @4 | 0.06173 | 0.06158 | 0.03355 | 0.16279 | 2.64x | 10.546 | 89.0% | ok |
| gray_world | @8 | 0.06679 | 0.06629 | 0.03758 | 0.17291 | 2.59x | 11.287 | 78.4% | ok |
| white_patch | @1 | 0.07035 | 0.07034 | 0.03666 | 0.18726 | 2.66x | 9.211 | 97.1% | illumination-fitted(2/3 pairs); identity:no-input-residual-reduction |
| white_patch | @4 | 0.08937 | 0.08902 | 0.05192 | 0.23503 | 2.63x | 11.497 | 89.0% | ok |
| white_patch | @8 | 0.10976 | 0.10821 | 0.07304 | 0.26357 | 2.40x | 13.665 | 78.4% | ok |
| clahe | @1 | 0.03669 | 0.03673 | 0.02155 | 0.14414 | 3.93x | 4.005 | 97.1% | illumination-fitted(2/3 pairs); identity:no-input-residual-reduction |
| clahe | @4 | 0.04687 | 0.04676 | 0.03196 | 0.19924 | 4.25x | 5.078 | 89.0% | ok |
| clahe | @8 | 0.05123 | 0.05074 | 0.03456 | 0.21857 | 4.27x | 5.604 | 78.4% | ok |
| gray_world_clahe | @1 | 0.08008 | 0.08005 | 0.04258 | 0.20603 | 2.57x | 10.235 | 97.1% | illumination-fitted(2/3 pairs); identity:no-input-residual-reduction |
| gray_world_clahe | @4 | 0.09714 | 0.09688 | 0.05745 | 0.24827 | 2.56x | 12.096 | 89.0% | ok |
| gray_world_clahe | @8 | 0.10500 | 0.10396 | 0.06250 | 0.26034 | 2.48x | 12.946 | 78.4% | ok |
| white_patch_clahe | @1 | 0.09058 | 0.09054 | 0.04921 | 0.23754 | 2.62x | 10.249 | 97.1% | illumination-fitted(2/3 pairs); identity:no-input-residual-reduction |
| white_patch_clahe | @4 | 0.11440 | 0.11405 | 0.07029 | 0.29542 | 2.58x | 12.693 | 89.0% | ok |
| white_patch_clahe | @8 | 0.13366 | 0.13252 | 0.08760 | 0.32214 | 2.41x | 14.785 | 78.4% | ok |

**`murky_shark`** (source 1920x1080, frames 0-40):

| config | lag | raw | illum-aware | AR | uncomp | reduction | ΔE00 | coverage | status |
|---|---|---|---|---|---|---|---|---|---|
| none | @1 | 0.00409 | 0.00410 | 0.00312 | 0.00560 | 1.37x | 1.035 | 96.3% | ok |
| none | @4 | 0.00484 | 0.00468 | 0.00398 | 0.01128 | 2.33x | 1.186 | 90.9% | ok |
| none | @8 | 0.00539 | 0.00509 | 0.00460 | 0.01322 | 2.45x | 1.277 | 89.7% | ok |
| gray_world | @1 | 0.01118 | 0.01117 | 0.00926 | 0.01230 | 1.10x | 3.474 | 96.3% | ok |
| gray_world | @4 | 0.01286 | 0.01274 | 0.01106 | 0.01802 | 1.40x | 3.911 | 90.9% | ok |
| gray_world | @8 | 0.01389 | 0.01364 | 0.01210 | 0.02026 | 1.46x | 4.142 | 89.7% | ok |
| white_patch | @1 | 1.43496 | 1.43023 | 1.34475 | 1.44231 | 1.01x | 9.970 | 96.3% | ok |
| white_patch | @4 | 2.03969 | 2.06168 | 1.96114 | 2.09198 | 1.03x | 12.756 | 90.9% | ok |
| white_patch | @8 | 1.83927 | 1.85772 | 1.75693 | 1.91377 | 1.04x | 11.999 | 89.7% | ok |
| clahe | @1 | 0.00590 | 0.00588 | 0.00447 | 0.00857 | 1.45x | 1.181 | 96.3% | ok |
| clahe | @4 | 0.00657 | 0.00653 | 0.00522 | 0.01769 | 2.69x | 1.324 | 90.9% | ok |
| clahe | @8 | 0.00712 | 0.00713 | 0.00581 | 0.02069 | 2.91x | 1.415 | 89.7% | ok |
| gray_world_clahe | @1 | 0.01521 | 0.01519 | 0.01244 | 0.01711 | 1.12x | 3.744 | 96.3% | ok |
| gray_world_clahe | @4 | 0.01713 | 0.01713 | 0.01443 | 0.02544 | 1.49x | 4.200 | 90.9% | ok |
| gray_world_clahe | @8 | 0.01834 | 0.01839 | 0.01561 | 0.02859 | 1.56x | 4.445 | 89.7% | ok |
| white_patch_clahe | @1 | 1.43110 | 1.42639 | 1.34085 | 1.43837 | 1.01x | 9.810 | 96.3% | ok |
| white_patch_clahe | @4 | 2.03559 | 2.05743 | 1.95686 | 2.08763 | 1.03x | 12.585 | 90.9% | ok |
| white_patch_clahe | @8 | 1.83619 | 1.85457 | 1.75368 | 1.91050 | 1.04x | 11.846 | 89.7% | ok |

**`lights`** (source 1920x1080, frames 71-111):

| config | lag | raw | illum-aware | AR | uncomp | reduction | ΔE00 | coverage | status |
|---|---|---|---|---|---|---|---|---|---|
| none | @1 | 0.04119 | 0.04108 | 0.04021 | 0.04626 | 1.12x | 5.036 | 97.0% | illumination-confounded |
| none | @4 | 0.09304 | 0.09137 | 0.09251 | 0.09936 | 1.07x | 12.060 | 95.1% | illumination-confounded; illumination-fitted(2/3 pairs); identity:no-input-residual-reduction |
| none | @8 | 0.14420 | 0.12647 | 0.14346 | 0.14665 | 1.02x | 16.690 | 89.4% | illumination-confounded; illumination-fitted(2/3 pairs); identity:gain-out-of-range |
| gray_world | @1 | 0.04119 | 0.04106 | 0.04019 | 0.04624 | 1.12x | 5.144 | 97.0% | illumination-confounded |
| gray_world | @4 | 0.09209 | 0.09038 | 0.09153 | 0.09838 | 1.07x | 12.104 | 95.1% | illumination-confounded; illumination-fitted(2/3 pairs); identity:no-input-residual-reduction |
| gray_world | @8 | 0.14300 | 0.12594 | 0.14224 | 0.14538 | 1.02x | 16.624 | 89.4% | illumination-confounded; illumination-fitted(2/3 pairs); identity:gain-out-of-range |
| white_patch | @1 | 0.04762 | 0.04762 | 0.04675 | 0.05240 | 1.10x | 7.233 | 97.0% | illumination-confounded |
| white_patch | @4 | 0.10515 | 0.09692 | 0.10468 | 0.11160 | 1.06x | 15.426 | 95.1% | illumination-confounded; illumination-fitted(2/3 pairs); identity:no-input-residual-reduction |
| white_patch | @8 | 0.14658 | 0.12622 | 0.14578 | 0.14943 | 1.02x | 17.839 | 89.4% | illumination-confounded; illumination-fitted(2/3 pairs); identity:gain-out-of-range |
| clahe | @1 | 0.04640 | 0.04633 | 0.04444 | 0.05683 | 1.22x | 5.393 | 97.0% | illumination-confounded |
| clahe | @4 | 0.11214 | 0.11034 | 0.11095 | 0.12516 | 1.12x | 12.994 | 95.1% | illumination-confounded; illumination-fitted(2/3 pairs); identity:no-input-residual-reduction |
| clahe | @8 | 0.17118 | 0.15418 | 0.16958 | 0.18245 | 1.07x | 17.350 | 89.4% | illumination-confounded; illumination-fitted(2/3 pairs); identity:gain-out-of-range |
| gray_world_clahe | @1 | 0.04832 | 0.04845 | 0.04635 | 0.05863 | 1.21x | 5.578 | 97.0% | illumination-confounded |
| gray_world_clahe | @4 | 0.11384 | 0.11176 | 0.11264 | 0.12688 | 1.11x | 13.176 | 95.1% | illumination-confounded; illumination-fitted(2/3 pairs); identity:no-input-residual-reduction |
| gray_world_clahe | @8 | 0.17268 | 0.15530 | 0.17102 | 0.18407 | 1.07x | 17.396 | 89.4% | illumination-confounded; illumination-fitted(2/3 pairs); identity:gain-out-of-range |
| white_patch_clahe | @1 | 0.05507 | 0.05514 | 0.05328 | 0.06501 | 1.18x | 7.709 | 97.0% | illumination-confounded |
| white_patch_clahe | @4 | 0.12674 | 0.11621 | 0.12570 | 0.13968 | 1.10x | 16.452 | 95.1% | illumination-confounded; illumination-fitted(2/3 pairs); identity:no-input-residual-reduction |
| white_patch_clahe | @8 | 0.17325 | 0.15301 | 0.17152 | 0.18490 | 1.07x | 18.572 | 89.4% | illumination-confounded; illumination-fitted(2/3 pairs); identity:gain-out-of-range |

**`distance`** (source 1080x1920, frames 246-286):

| config | lag | raw | illum-aware | AR | uncomp | reduction | ΔE00 | coverage | status |
|---|---|---|---|---|---|---|---|---|---|
| none | @1 | 0.01525 | 0.01507 | 0.01090 | 0.04058 | 2.66x | 2.387 | 97.8% | ok |
| none | @4 | 0.02057 | 0.01892 | 0.01718 | 0.07691 | 3.74x | 3.105 | 90.6% | ok |
| none | @8 | 0.02894 | 0.02490 | 0.02604 | 0.10948 | 3.78x | 4.068 | 82.2% | ok |
| gray_world | @1 | 0.02005 | 0.01979 | 0.01442 | 0.04627 | 2.31x | 3.584 | 97.8% | ok |
| gray_world | @4 | 0.02507 | 0.02306 | 0.02042 | 0.08383 | 3.34x | 4.349 | 90.6% | ok |
| gray_world | @8 | 0.03431 | 0.02869 | 0.03024 | 0.11859 | 3.46x | 5.668 | 82.2% | ok |
| white_patch | @1 | 0.02083 | 0.02054 | 0.01505 | 0.05040 | 2.42x | 3.187 | 97.8% | ok |
| white_patch | @4 | 0.02688 | 0.02466 | 0.02229 | 0.09298 | 3.46x | 3.913 | 90.6% | ok |
| white_patch | @8 | 0.03781 | 0.03143 | 0.03391 | 0.13246 | 3.50x | 5.206 | 82.2% | ok |
| clahe | @1 | 0.02858 | 0.02840 | 0.02264 | 0.06789 | 2.38x | 3.102 | 97.8% | ok |
| clahe | @4 | 0.04212 | 0.04063 | 0.03794 | 0.12440 | 2.95x | 4.299 | 90.6% | ok |
| clahe | @8 | 0.05053 | 0.04653 | 0.04644 | 0.16631 | 3.29x | 5.326 | 82.2% | ok |
| gray_world_clahe | @1 | 0.03496 | 0.03466 | 0.02712 | 0.07587 | 2.17x | 4.287 | 97.8% | ok |
| gray_world_clahe | @4 | 0.04881 | 0.04710 | 0.04297 | 0.13465 | 2.76x | 5.555 | 90.6% | ok |
| gray_world_clahe | @8 | 0.05913 | 0.05416 | 0.05359 | 0.17798 | 3.01x | 6.926 | 82.2% | ok |
| white_patch_clahe | @1 | 0.03469 | 0.03444 | 0.02706 | 0.07821 | 2.25x | 3.824 | 97.8% | ok |
| white_patch_clahe | @4 | 0.05017 | 0.04833 | 0.04469 | 0.14065 | 2.80x | 5.061 | 90.6% | ok |
| white_patch_clahe | @8 | 0.06137 | 0.05572 | 0.05621 | 0.18790 | 3.06x | 6.405 | 82.2% | ok |

Raw JSON (every field, every pair, per-frame gain lists) remains at
`outputs/week2c2d_baselines/results.json` (gitignored, local artifact) for
anyone who wants finer granularity than the tables above.

**White-patch's dominant, clip-dependent gain — and a catastrophic failure
mode found and visually confirmed.** Mean red-channel gain over the window:
distance 2.69×, lights 1.00×, murky_eel 44.70×, swimthrough 113.16×,
**murky_shark 113,098× (range 481× to 577,580×)**. Frame-by-frame,
murky_shark's gain sits at 481–1945× for most of the window, then jumps
discretely to ~571–578 **thousand**× for the last 8 of 41 frames — the
signature of the reference red channel's median hitting the `1e-6`
zero-safety floor exactly (target ÷ epsilon), not a gradual drift.
**Visually confirmed** (`/tmp/uw_visual`, not committed — reproducible by
running `uw correct` on the clip): murky_shark under white-patch turns
**flat pink/red**, essentially destroying the scene; murky_shark under
gray-world is a milder but still severe red cast; murky_shark under CLAHE
is visually near-identical to the input (contrast-only, as designed).
Out-of-range fraction on murky_shark/white_patch: **31.87–31.94%** of the
frame — a full third of the image pushed outside [0, 1], not silently
clipped, visible in the report. `distance`, where the scene genuinely
contains red content (coral, a diver), stays a plausible-looking, modest
correction (2.42× reduction, 0.48% out-of-range) — **white-patch's failure
mode is specifically "no plausible bright neutral reference exists,"
exactly as CLAUDE.md's §27 asked to inspect for, not a general defect of
the algorithm.**

**A second, distinct white-patch failure mode, also from §27's checklist:
domination by a specular/bubble region — found by rendering the actual
bright-region mask, not by inspecting the code.** On `distance`, overlaying
the selected top-1%-luminance mask on the source frame shows it sitting
almost entirely on the diver's **rising bubble column and white air
tank** — not on coral, the chart, or any stable reflective surface. The
median reference's G and B channels read **exactly 1.0** on every one of
12 consecutive frames checked (260–271) — source clipping, consistent with
a bubble/tank highlight rather than a textured surface — while the
reference **red** channel (and therefore `gain_R`) swings from 3.10 down to
2.33 and back to 2.88 across those same 12 frames, a ~33% range, purely
because which bubbles/glints happen to fall in the top percentile changes
frame to frame. Bubbles are the largest structured residual in exactly this
clip per Phase 2A (§7's "distance" section) precisely because they are
non-rigid and appear/disappear — so a bright-region estimator keyed to them
inherits that instability directly. This is a plausible, mechanistic
contributor to why `distance`'s white-patch reduction ratio (2.42–3.50×,
the table above) sits well below its gray-world counterpart despite a much
smaller mean gain: gray-world's whole-frame mean is comparatively insensitive
to a few hundred bubble pixels, but white-patch's estimator is defined by
almost nothing else there. No fix applied — CLAUDE.md forbids adding
semantic bubble/highlight rejection to the estimator, and this is recorded
as a limitation, not patched.

**CLAHE — checked specifically for tile-boundary artifacts and halos, found
none at this resolution.** A per-pixel |corrected − original| difference
map for `swimthrough` frame 200 (both full-frame and an 8x zoomed 200x200
crop centered on a coral edge) shows a smooth field that tracks scene
texture edges (the coral outline, the thin rope Phase 2A flagged) with no
visible 8x8 grid periodicity or blocking at the `CLAHE_TILE_GRID_SIZE`
boundaries, and no ringing/halo band around high-contrast edges. OpenCV's
CLAHE performs its own bilinear interpolation between adjacent tiles'
histograms specifically to avoid blocking, and this is a case where that
worked; it is not something this implementation adds or could remove, and
is only reported at this one clip/resolution, not asserted in general.

**CLAHE increases every clip's raw MC-Warp relative to `none`, by 1.13× to
2.16×** across all five clips and three lags (recomputed directly from the
table above — clahe/none per clip at @1: swimthrough 2.09×, murky_eel
1.82×, murky_shark 1.44×, lights 1.13×, distance 1.87×). It is the
**mildest of the three single-stage corrections on 3 of 5 clips**
(swimthrough, murky_eel, murky_shark — precisely the clips where
gray-world's and white-patch's own gains are large), but **not** on the
other two: on `lights`, gray-world is mildest (1.00× — its gain there is
≈1, so it barely perturbs anything) with clahe second (1.13×); on
`distance`, CLAHE is actually the **worst of the three single-stage
corrections** at every lag (1.87×/2.05×/1.75× vs gray-world's
1.31×/1.22×/1.19× and white-patch's 1.37×/1.31×/1.31×) — though still below
both `→clahe` combinations there. CLAHE responds to each frame's own local
content, and on a clip with a diver and a moving bubble column that local
content itself moves frame-to-frame more than a global multiplier does —
a genuinely different failure mode from a bad global gain, not a smaller
version of the same one; it is not automatically the gentler choice.
Visually, CLAHE's output is close to indistinguishable from the input at a
glance on swimthrough — matching its design intent (local contrast, not
color restoration) and Phase 2C/2D §27's instruction to keep "contrast
improvement" distinct from "color fidelity."

**Combined pipelines: a headline conclusion from the first write-up was
WRONG, and an external review caught it.** The original entry read:

> `white_patch→clahe` on murky_shark (0.12944) is dramatically **better**
> than `white_patch` alone (1.43496) — because CLAHE's tile-local histogram
> equalization partially compresses the astronomical dynamic range
> white-patch's gain introduced.

That was an artefact of the AR-02 clipping bug, not a property of CLAHE.
CLAHE was silently collapsing every above-white pixel to exactly 1.0, and
on a clip where white-patch pushes 32 % of the frame out of range, that
clamp — not histogram equalisation — produced the apparent rescue. With
the leak fixed and the evaluation rerun, the same cell reads **1.43110
against white_patch's 1.43496**: CLAHE does **not** rescue a broken colour
correction, it leaves it essentially untouched. The corrected reading is
the boring one, and it is the right one: a local-contrast operator cannot
repair a global-gain failure, and the number that said otherwise was
measuring an implicit clip.

Recorded at length because the failure mode is the one CLAUDE.md warns
about most directly — a metric improving for a reason that has nothing to
do with the restoration getting better — and because the first write-up
stated the mechanism ("tile-local histogram equalization") confidently
without testing it, which is the same error Phase 2A §A7 and Phase 2B
logged. The remaining `→clahe` deltas are small and in the expected
direction (e.g. swimthrough `white_patch→clahe` 0.11816 → 0.13298,
murky_eel 0.08952 → 0.09058): with the clamp gone, out-of-range content is
carried honestly into the residual instead of being flattened.

**`lights` remains `illumination-confounded` at every lag for every
configuration** including `none` and `clahe`, unchanged from Phase 2B — the
camera-mounted-light problem is orthogonal to which correction runs.
`white_patch`'s gain there is 1.00× (the scene is already near-neutral
under artificial white light), consistent with `gray_world`'s 0.91–1.07×
finding in Phase 2B.

**No global winner.** `gray_world` and `white_patch` are worse than `none`
on every clip's raw temporal residual by design (neither has a temporal
term) — exactly Phase 2B's expected floor-baseline signature, now
reproduced for two baselines instead of one. `clahe` alone is the mildest
temporal destabilizer of the three single stages on 4/5 clips but the
worst on `distance`. `white_patch` is unusable as-is on signal-starved deep
water and merely modest where the scene contains real red content — this
is a signal-recoverability finding (near-floor fraction was 0.0334 on
distance vs 0.1525/0.2901/0.3604 on murky_shark/murky_eel/swimthrough), not
a bug to fix inside this phase.

### Tests

**98 tests added this session (274 collected: 273 pass + 1 environment-
dependent skip; was 176)** — 39 baselines + 20 diagnostics + 27 pipeline
+ 9 added to test_flow + 3 added to test_temporal, each count taken from
`pytest --collect-only -q` on that file rather than transcribed.

Coverage by area: white-patch robustness (hot pixels, small frames, ties,
zero-safety, determinism, non-mutation, dtype), CLAHE (uint16 not uint8,
neutral preservation, contrast increase, dark-gradient precision,
near-black reconstruction, chromaticity, above-white preservation, NaN
locality, documented flat-tile limitation), diagnostics (exact fractions,
per-channel distinction, source-vs-corrected semantics, non-finite range
counting, no-fake-SNR), pipeline (order, duplicates, per-stage
attribution, every ablation, backward compatibility, CLI wiring), flow
(conventions plus the caching wrapper's identity/bounds/id-reuse
behaviour), and temporal (the 52 frozen Phase 2B tests plus three new ones
for evaluation-domain independence and prepared-state reuse).

**Twenty-one of these tests exist because successive adversarial passes,
and then an external review, broke the code after the evaluation had
already been run and written up.** Named regressions:
`test_white_patch_hot_pixel_does_not_dominate_a_SMALL_frame`,
`test_white_patch_bright_region_never_collapses_to_one_pixel` (5e7x
single-pixel degeneracy);
`test_repeated_stage_keeps_both_applications_attributable` (same-stage
metadata overwrite);
`test_clahe_does_not_leak_lstar_or_uint16_VALUES_not_just_dtype` (the
original leak test asserted only dtype);
`test_clahe_amplification_above_the_near_black_guard_is_bounded_and_stable`;
`test_white_patch_all_black_frame_reports_identity_not_zero_gain`;
`test_stages_reject_integer_dtype_instead_of_silently_zeroing` (uint8
all-zero destruction, parametrised over all three stages);
`test_clahe_nan_input_stays_local_and_casts_without_undefined_behaviour`;
`test_zero_size_frame_is_refused_rather_than_reported_as_nan`;
and from the external review:
`test_clahe_does_not_collapse_above_white_content` (AR-02, the one that
overturned a published conclusion),
`test_corrected_output_cannot_shrink_the_evaluation_domain` (AR-01),
`test_prepared_pair_is_reused_not_recomputed_across_configurations` and
`test_prepare_temporal_pairs_is_bounded_to_anchor_times_lag` (AR-03),
`test_caching_backend_survives_object_id_reuse` (AR-05, skips if the
interpreter will not reuse an address in 500 allocations),
`test_out_of_range_fraction_counts_non_finite_values` (AR-06).

**Numerical tolerances/edge cases that needed special handling**: the
white-patch hot-pixel test uses `rtol=0.1` (one outlier pixel among 1600
can move the gain a little, just not by orders of magnitude); the CLAHE
chroma-preservation test uses `rtol=1e-4` (float32 round-trip through
uint16 quantization); the dark-gradient test asserts `>256` distinct output
levels on a 2000-pixel-wide gradient specifically to catch an accidental
uint8 path; `test_caching_backend_misses_on_a_different_frames_object`
(now `test_caching_backend_misses_on_genuinely_different_frame_objects`)
had to keep its two throwaway container objects in named variables — an
anonymous `["clip_a"]` / `["clip_b"]` pair can be garbage-collected and
have its memory address reused by CPython before the second one is
constructed, which silently made two "different" lists compare `id()`-equal
and defeated the test until fixed.

### Repository changes

**Created**: `uw/diagnostics.py`, `tests/test_baselines.py`,
`tests/test_diagnostics.py`, `tests/test_pipeline.py`,
`experiments/week2c2d_baselines/` (`__init__.py`, `README.md`,
`scripts/run_baseline_eval.py`).

**Modified**: `uw/baselines.py` (+`white_patch`, +`clahe`), `uw/colorspace.py`
(+`y_to_lstar`, +`lstar_to_y`), `uw/flow.py` (+`CachingFlowBackend`),
`uw/cli.py` (`--pipeline`, `--no-<stage>` ablations, pipeline/diagnostics/
gains report, mutual-exclusivity fix), `tests/test_flow.py` (+caching
tests). `uw/metrics.py`, `uw/searaft.py`, `uw/waft.py`, `uw/io.py`,
`uw/types.py` byte-identical to before this session — nothing about the
frozen Phase 2A/2B evaluator changed.

**Generated diagnostics** (gitignored, local): `outputs/week2c2d_baselines/
results.json` (every number, per clip/configuration/lag); `/tmp/uw_visual/`
(not committed, reproducible via `uw correct`) — before/after PNGs used for
the visual-inspection findings above.

### External review — findings and disposition

An external review of the completed work raised nine findings (AR-01..09).
All nine were reproduced before acting on any of them; the dispositions:

| ID | Verdict | Action |
|---|---|---|
| AR-01 corrected output influences its own mask/fit | **Confirmed** | Fixed in `uw/metrics.py` (mask is now correction-independent; damage reported, not masked). Frozen Phase 2B code, changed only under explicit authorisation. |
| AR-02 CLAHE's temporary L* bound leaks as an implicit clip | **Confirmed** | Fixed (above-white passthrough). **Overturned a published conclusion** — see "Combined pipelines" above. Full evaluation rerun. |
| AR-03 only flow reused, not mask/fit | **Confirmed** | Fixed via `prepare_temporal_pairs`; 18 inferences per clip and provably identical domain across configurations. |
| AR-04 clipLimit/uint16 geometry dependence | **Partly confirmed; severity overstated** | Reproduced on FLAT input (0.24244 vs 0.18174 at 540x960 vs 541x959) — that is the already-documented flat-tile degeneracy. On TEXTURED input, which is what real footage is, the same comparison gives 0.29662 vs 0.29682, a 0.07 % difference: not "materially resolution-dependent". Not changed: the brief forbids retuning CLAHE parameters, and the evidence does not support a correctness fix. Recorded as a limitation. |
| AR-05 cache id() reuse can cause a false hit | **Confirmed** | Fixed: entries hold strong frame references and are identity-checked. |
| AR-06 `out_of_range_fraction` ignores NaN | **Confirmed** | Fixed: non-finite counts as out of range. |
| AR-07 "saturation / SOURCE clipping" overstates the measurement | **Confirmed** | Fixed: renamed to representation-ceiling in the report, with an explicit statement that it is necessary but not sufficient evidence of sensor clipping. |
| AR-08 experiment runner overwrites `--json` silently | **Confirmed** | Fixed: refuses without `--overwrite`, matching CLAUDE.md invariant 7 ("benchmark outputs, everything"). |
| AR-09 stale flat stage keys on reprocessing | **Confirmed, low** | Not changed: the nested per-stage record is already authoritative and the flat keys are documented last-writer-wins. Left as a known wart. |

Two review claims about repository state are worth recording as accurate:
Phase 2A, 2B and 2C/2D are all uncommitted on top of a Week 1 `HEAD`, so
git cannot independently prove which files each phase touched — the
byte-identity claims in this file rest on in-session verification, not on
a commit boundary. And `data/testset/murky/MURKYSHARK_corrected.mp4` is a
generated artefact sitting in the source-footage tree (gitignored, so not
commit-visible); it predates this session and should be moved.

### Pending acquisition-dependent work (unchanged from prior sessions)

- GoPro Flat/RAW calibration — still not performed.
- Controlled Keldan/chart footage — `data/testset/chart/` still empty;
  chart ΔE00 remains unavailable, not fabricated.
- Robust SNR/noise characterization — still deferred; nothing in this
  session's diagnostics claims to measure it (see `test_no_field_is_
  labeled_snr_or_noise`).
- DaVinci Resolve chart control — **Resolve control: pending
  acquisition/reference.**

None of these block this session's gate. `CLAUDE.md` and `PLAN.md` are
unchanged; no Week 3 code exists; no `--no-temporal`/`--no-depth`/
`--no-backscatter`/`--no-attenuation` flags were added; no new metric was
introduced; Phase 2A/2B's flow, illumination fitting/guards, MC-Warp
definitions, status bands, and ΔE00 are byte-identical to before this
session.

**Next hypothesis:** white-patch's failure mode (no plausible bright
neutral on signal-starved footage) and CLAHE's clip-dependent temporal
cost (worst on the highest-motion, richest-parallax clip rather than the
murkiest one) are both now measured rather than assumed — Week 3 can begin
once reviewed. The single most informative unrun experiment in the project
remains the 30-second drift test (Week 8's actual gate); nothing this
session changes that.

---

## 2026-08-31 — Week 3 Phase 3A: multi-view geometry bakeoff

Durable conclusions only. Full report: `experiments/week3_geometry/FINDINGS.md`.

**Representative dataset.** Six development clips, frozen before any geometry
method was run (`experiments/week3_geometry/phase3a/configs/phase3a_clips.json`):
`wreck_07` (anchor, high-texture arc), `wreck_05` (lower-texture lateral glide),
`cenote_01` (ambient-lit cavern, widest near/far span), `swimthrough_02`
(ordinary reef swim-through), `wreck_01` (low-texture near-planar, portrait),
`wreck_03` (dynamic diver). 48 frames each, one shared extraction at a 1280 px
long side, resampled in linear light. The `frozen_eval` suite was not touched and
**the selected method has not yet been run against it** — that realism check is
outstanding.

**Candidates tested.** Executed: A COLMAP·SIFT, B COLMAP·ALIKED_N32+LightGlue,
C_off/C_on `colmap_underwater` refraction off/on, D MapAnything, E0 vanilla VGGT,
E Wat3R-Ren. Not executed: F GLUEMAP and G AMB3R (`pending_cuda`, no CUDA on this
machine); H SeaVGGT, I Water-VGGT, J WAT3R-Xu (`paper_only / not_released` — see
`configs/underwater_challengers.json` for the per-candidate evidence). One is worth
knowing beyond this week: Water-VGGT is better classified **`release_incomplete`**
than not-released — code and an official checkpoint ARE published, and both were
inspected. The advertised "pretrained Water-VGGT model" has a **model state
bitwise identical, tensor for tensor, to `facebook/VGGT-1B`** (1797/1797 tensors,
max abs difference 0.0, zero Water-VGGT-specific modules). The *files* are not
byte-identical - different containers - and its released pipeline preprocesses
pixels before VGGT, so its output would not equal our E0 control; what is
established is that its geometry model carries no underwater adaptation.

**Selected range path (provisional): MapAnything.** Chosen on licence, validity
signalling, memory cost and verified output semantics — **not** on geometric
accuracy, where vanilla VGGT edges it on four of six clips. It is the only dense
candidate with Apache-2.0 code *and* an Apache-2.0 checkpoint, the only one
emitting an explicit mask, the cheapest in memory (10.3–10.8 GB), and its
`depth_along_ray == ‖pts3d_cam‖` was verified to 1.1e-5 so the conversion to the
project's canonical range quantity is exact. **Named condition:** its scale
collapses on dynamic content (6.6× per-frame scale wander, 130 % range swing on
`wreck_03`); Week 5 must guard against that.

**Selected cross-check: configuration A, ordinary COLMAP with SIFT.** It
registered 48/48 on four clips and ≥46/48 on the other two, at 37–252 s per clip
on CPU. **Configuration B is retired as a default, with a caveat worth keeping.** On the
high-texture wreck it agrees with A to 0.95 % and buys nothing; on the
*low-texture* wreck it yields 40 % longer tracks (8.25 vs 5.91) and 11 % more
points, both still registering 48/48. So correspondence is not the classical
bottleneck, but a learned matcher does measurably improve triangulation
conditioning where SIFT is starved — at an 18-28x CPU runtime penalty. Reopen it
only on an observed weak-triangulation failure (the Phase 3B trigger).

**Refraction conclusion — not a null, a non-identifiability.** Three findings,
each attributed by measurement rather than assumed. The third alone is decisive:
**C_on is not a reproducible instrument** — identical seed and settings give
44, 16, 44 registered frames across three runs of one clip, and a 22x point-count
spread on another. PLAN.md requires a refraction effect to exceed run-to-run
spread; nothing here comes close, so no refraction claim is admissible from this
data whatever the physics. (A, by contrast, is stable to <=4%; C_off to 1-25%.)
The other two findings: (1) the
refractive fork fails to initialise on 3 of 6 clips **even with the refractive
indices set to 1.0**, i.e. with refraction physically disabled — so that failure
is the implementation's initialisation, not flat-port physics; (2) where it does
reconstruct, with the port parameters *fixed*, bundle adjustment drives the scene
to ~10⁶ times the port stand-off, where the modelled refraction is numerically
negligible. The fitted off/on scale ratio ranges over 0.08 to 197 across clips.
**Refractive geometry is retired as a cross-check** and the refraction question is
reclassified as blocked on metric scale.

**Underwater adaptation (VGGT → Wat3R-Ren): condition-specific, no material
win.** Better on one wreck (3.5 % vs 4.8 %), tied on a second and on the reef
swim-through, and **clearly worse on the cenote** (20.1 % vs 13.1 %, the worst
dense result anywhere). Per the standing rule this is not a reason to look for
another underwater-adapted model.

**Determinism.** All three dense models (MapAnything, VGGT, Wat3R-Ren) are
**bitwise reproducible** across repeat runs on MPS float32 with a fixed seed —
zero run-to-run spread, identical validity masks. So every dense-vs-dense
difference reported is method difference with no noise floor to clear, and the
standing "differences must exceed run-to-run variability" rule is satisfied
trivially for the learned arm.

**Important failure modes.** Dynamic foreground subject breaks MapAnything's
scale far more than the VGGT family's. Low SIFT contrast is a real footage
property, not a method failure — `wreck_05` yields ~1 100 features/frame against
`wreck_07`'s ~4 400 on the same camera. VGGT and Wat3R-Ren **discard ~44 % of the
vertical field of view on portrait clips** (measured, not read from source), so
they and MapAnything are not seeing the same scene there. Confidence is close to
uncalibrated: MapAnything's low-confidence pixels are only 1.07× worse than its
high-confidence ones.

**Key error-budget result (the most reusable artifact).** With coefficients
freely fitted in-clip, a global range scale error is absorbed **exactly**
(max |ΔJ/J| = 4.5e-13 over a sweep to s = 3.2) and costs nothing. A *local*
error is not: the local relative range error at which worst-channel restored
radiance error reaches 5 % is 31 % @1 m, 12 % @3 m and 8.5 % @8 m in clear
oceanic water; 9.4 % @3 m and 6.1 % @8 m coastal; and collapses to 1.0 % @8 m and
0.3 % @12 m in turbid water. Because β differs per channel, a local range error
is a **spatially varying colour error**, not a brightness offset.

**Is controlled acquisition required? C2 yes, C1 no — but it does not block
downstream work.** Phase 3A selects MapAnything + COLMAP/SIFT as the provisional
integration path; Weeks 5-6 can proceed on it now. Independent C2 data is
required before claiming objective geometry accuracy or resolving refraction, but
is **not** a blocker for pipeline development. C1 is not justified as a separate
acquisition — reconstruction is not what is failing — but note that registration
success does not establish well-conditioned parallax, so C2 should be shot with
deliberate lateral/arc motion and subsume C1's role. C2 must also **measure** the
camera-to-interface distance and port thickness rather than assuming them: a 25x
change in the assumed stand-off moves the refractive reconstruction's implied
scale 172x and its recovered focal 3x, so the refraction answer is currently
dominated by an unmeasured parameter. Adding another geometry model, or renting
CUDA for F/G, buys more disagreement between unanchored hypotheses and should
wait.

**Deployable path.** MapAnything on MPS plus a COLMAP/SIFT cross-check, both
fully local (~4 min and ~1 min per 48-frame clip), Apache-2.0 / BSD, no CUDA.
Nothing observed justifies making CUDA a permanent project requirement.

**Two configuration errors of mine, both caught and both corrected before they
reached a conclusion.** Forcing `Mapper.multiple_models=0` makes COLMAP break out
of its initialisation loop after one trial, turning each run into a lottery on
the initial image pair (config B gave 48/48 and 3/48 on byte-identical reruns);
and the pose falsification control was initially a no-op because VGGT anchors its
world frame to camera 0. `scripts/check_completeness.py` now separates "a run
died", "a run used superseded settings" and "a method failed".

---

## Week 3 Phase 3B — targeted geometry failure analysis (2026-08-31)

**Six pre-registered hypotheses** (`experiments/week3_geometry/phase3b/PHASE3B.md`,
written before any run), full report in `phase3b/FINDINGS.md`.

**Answer: NO. Phase 3B does not change the Phase 3A architecture.** MapAnything
(dense range) + COLMAP/SIFT (sparse cross-check) is frozen as the provisional
integration path. Nothing was simultaneously large, repeatable, attributable,
restoration-relevant and deployable.

**Camera metadata, read for the first time.** All six clips are one GoPro HERO9
Black, one lens serial, one firmware. Five share an identical capture mode (Wide,
digital zoom off, HyperSmooth Boost, ZFOV 105.383°); only `cenote_01` differs.
`wreck_01`'s portrait decode is `OREN = R` — a rotation flag with identical FOV —
so the 44 % vertical FOV loss Phase 3A found there is a **VGGT-family
preprocessing artefact, not a footage property**, and the classical arm has no
FOV confound on that clip. **EIS is on in every clip** (`EISE = Y`) with output
projection `PRJT = GPRO`: a real, previously unrecorded confound for every Phase
3A geometry number, now documented but not resolved.

**The load-bearing result: within these six clips, instability tracks SIFT
observation density much more closely than the tested parallax proxies.** Four independent perturbations
— matcher, mapper, central camera model, frame schedule — agree about which clips
are stable. `swimthrough_02` has the *lowest* median triangulation angle in the
set (5.23°) and is the most stable under all of them (mapper 0.0 %, camera model
0.4-0.5 %); `wreck_01` has the *largest* baseline/depth ratio (0.276) and moves
~9 % under every one. Stable clips carry 4 358-14 440 observations/image;
unstable ones 1 099-2 099. This is consistent with an under-constrained /
self-calibration regime; it does **not** establish observation density as the
causal variable, and a global median triangulation angle cannot exclude a local
parallax-topology failure within a clip. Under the one perturbation family applied
identically to four clips (the four central camera models), the two
high-observation clips hold their focal to **1.026x** and **1.056x** while the two
low-texture clips *from the same camera and capture mode* spread **1.113x** and
**1.294x**; across all Phase 3B arms `wreck_05` spans 1 236-1 780 px and
`wreck_01` 1 104-1 430 px, and imposing `wreck_07`'s intrinsics on either costs no
registration and lengthens its tracks. **So a large
part of Phase 3A's cross-family disagreement on the low-texture clips is the
classical reference's own ill-conditioning, not only the dense candidates.**

**Noise floors, measured in the units that decide things.** Mapper-only runs on a
fixed database and Any4D on MPS are *exactly* reproducible (0.00 %, bitwise).
Whole-pipeline reruns are not: `wreck_07` 0.01 %, but `wreck_05` 2.1-6.5 % median
/ 6.7-19.1 % range swing, and 10.2-32.9 % at reduced frame counts. Mechanism
identified — identical 52 745 keypoints, **29 differing verified matches out of
65 756 (0.04 %)** move `wreck_05`'s range field 3.3 % median. This completes Phase
3A limitation #8 and reframes its `wreck_05` column.

**Per-hypothesis.** 3B-1 `interesting_but_not_material`: the A→B track gain is
**the matcher (LightGlue), not ALIKED** — +51.5 %/+41.3 % at fixed features,
−7.9 %/−16.9 % at fixed matcher, and ALIKED+brute-force collapses registration to
32/48 and 26/48. 3B-2 `failure_not_repaired`: global SfM is identical to
incremental on high-texture footage (0.0 %) and differs 9-14 % on low-texture;
`view_graph_calibrator` upgraded 0/391 pairs and produced 15 degenerate frames on
`wreck_03` while reporting the *best* reprojection error. 3B-3
`failure_not_repaired`: well-conditioned clips are stable to every central camera
model (≤1.5 %), weak clips move 8-24 %; the equal-capacity fisheye changes
`wreck_05` by 0.8 %, so it is **capacity, not projection family**. 3B-4
`failure_not_repaired`/`not_identifiable`: `cenote_01` reconstructs the same world
from 13 frames as from 48 (1.0-1.1 %, at its own noise) — weak temporal baseline
does **not** explain the Phase 3A disagreement. 3B-5 `not_triggered` on the
pre-registered rule. 3B-6A Any4D `interesting_but_not_material`: at matched view
count it cuts MapAnything's scale wander 7.05×→2.57× and range swing
129.5 %→72.8 % — real and view-count-controlled — but stays far outside the
restoration budget, is worse than every arm on the easy control, costs 10.8× the
runtime and 3.4× the memory, cannot process 48
views (62 GB attention buffer), emits no usable validity signal, and its
checkpoint states no licence — and the comparison is Any4D vs MapAnything, not
MapAnything ± a dynamic head, so the mechanism is not isolated. 3B-6B VGGT-SLAM
2.0 `not_practical_local`. LoMa `not_practical` **for Phase 3B as executed** —
absent from the frozen Homebrew 4.1.1_3 environment. (Correction at finalisation:
upstream COLMAP **4.2.0** shipped 2026-09-01 *with* LoMa (`LOMA_B`, `LOMA_B128`)
and the first official `colmap-arm64-macos.zip`; Homebrew stable is still
4.1.1_3. Changing COLMAP mid-phase would have created a new environment, so the
decision stands, but LoMa is testable by a future phase that adopts 4.2.0. An
earlier claim that no prebuilt macOS ARM binary existed was wrong — Homebrew
arm64 bottles are how this project's COLMAP was installed.) MP-SfM
`not_practical_local` had it triggered.

**New operational guards for Weeks 5-6.** (1) `< ~2 000 SIFT observations/image`
is a **heuristic warning trigger learned from this dataset, not a validity
boundary** — below it, the classical geometry on these clips stopped being
identified, so treat it as a flag to check and do not use configuration A as a
structural cross-check on a flagged clip without the check in (2). (2) The
detector is one extra `global_mapper` run on the same database (seconds;
disagreement is 0.0 % exactly when the clip is well conditioned). (3)
MapAnything's dynamic failure on `wreck_03` is **view-count-independent** (16
views reproduces it: 25.0 % vs 25.2 % median, 7.05× vs 6.30× scale wander), so
shortening the window is not a workaround. Two conditional fallbacks, neither on
by default: SIFT+LightGlue as a *correspondence-strengthening* option when
ordinary SIFT matching is specifically diagnosed as weak (it is **not** a
registration-failure fallback — the large rescues in this phase belong to the
ALIKED cell), and
`global_mapper` as a second opinion — `view_graph_calibrator` explicitly not
adopted.

**C2 unchanged and reinforced:** required for definitive objective geometry
validation and for resolving refraction, **not** a blocker to downstream pipeline
development. Phase 3B shows an independent metric anchor would resolve both sides
of the Phase 3A disagreement at once, since the reference itself is unidentified
on exactly the clips where that disagreement was largest.

## 2026-09-06 — Week 4A monocular depth bakeoff: execution start + S0 gate

**Baseline safety check, before any Week-4 code.** `uw score
data/testset/murky/MURKYSHARK.MP4` runs clean (292 frames, gray-world gains R
3.940–25.752 / G 0.669–0.837 / B 0.619–0.691, out-of-range 0.0000, ΔE still
unwired because `data/testset/chart/` is still empty). The deprecated Week-1
number that every prior entry pins against —
`temporal_stability(gray_world(f) for f in load('data/testset/murky/
MURKYSHARK.MP4'))` — still returns `3.244860636186786e-05` **bit-for-bit**.
`pytest tests/` is 323 passed, 1 skipped. No baseline change, so Week 4 proceeds.

**Frozen material verified before, not after.** `verify_frozen_set --hash`
re-hashes all 288 frames: six clips × 48, every `frame_set_sha256` matching
Week 3's `extraction_report.json`, and the persisted `D_mapanything` reference
product present at 48 frames for each. The primary bakeoff runs on exactly the
footage Week 3 characterised — nothing regenerated, nothing substituted.
`wreck_01` is the one portrait clip (1280×720), which matters below.

**What was built.** `experiments/week4_mono/` — `common.py` (the frozen
experiment definition), `monoio.py` (a per-model product that stores the NATIVE
output alongside a derived canonical range, because unlike Week 3 the seven
entrants do not share a representation), `backends/` (one module per model,
each in its own venv, `infer()` taking ONE image path so a batch is not
expressible), and `scripts/`. Three new venvs: `.venv-mono` (numpy<2: DA V2,
DA3 Mono, FoundationGeo), `.venv-moge` (numpy≥2: MoGe-2, MetricAnything),
`.venv-eval` (analysis only, so a model venv change cannot silently alter the
measuring instrument). MapAnything and Wat3R reuse the Week-3 venvs unchanged.

**S0 result: all 7/7 mandatory checkpoints PASS. Nobody exits at S0.** Every one
runs on MPS in float32; nothing needs CUDA; five of seven also run on CPU.
Runtime per frame 0.28–2.32 s, load 0.9–15.5 s, peak 2.1–9.6 GB.

**Two documented expectations were corrected by measurement rather than
repaired.** (1) **`DA3MONO-LARGE` emits no camera.** Its config is a DINOv2
ViT-L with a single DPT head of `output_dim: 1`; the returned `Prediction`
carries `depth` and `sky` and nothing else — `intrinsics`, `extrinsics` and
`conf` are all `None`. Range needs a camera, so this backend writes **no**
canonical range; inventing a focal would manufacture exactly the radial error
M-6 exists to detect. It also leaves the z-vs-range question about its native
field genuinely open, since the reference implementation's own `unproject_depth`
is never reached for this checkpoint. (2) **`Depth-Anything-V2-Small` likewise
writes no range**, because its ambiguity is affine in *disparity* and inverting
before S2 fixes `(a,b)` produces a number that looks like a range and is not
one. Both deferred to the frozen S2 policy.

**The z-vs-range mistake is worth 11–19 % median and up to 59 % at the corners
on this camera.** Measured `median_ratio_range_over_z` per model on the ordinary
frame: MapAnything 1.113, MoGe-2 1.193, MetricAnything 1.109, FoundationGeo
1.117; corner maxima 1.35–1.59. Every conversion that *was* available is
verified numerically per frame, not assumed — MapAnything's
`depth_along_ray == ||pts3d_cam||` re-verified at N=1 to **7.6e-06**, so the
Week-3 range identity survives the view-count change.

**FOV audit, 25 markers per orientation through each model's own
preprocessing.** The portrait trap is real and it is **Wat3R's alone**: on the
1280×720 portrait source it loses **10/25 markers and retains 56.0 % of the
frame area** (short side resized to 518, long side centre-cropped to 518),
reproducing Week 3's VGGT-family finding exactly. Every other entrant retains
98.7–100 % at both orientations; all affine residuals sub-pixel. Consequence:
Wat3R's `wreck_01` column is a *different, smaller field of view*, not a
like-for-like result, and S3 must read it that way.

**Checkpoint integrity — MetricAnything vs stock MoGe-2: LINEAGE_CONSISTENT.**
Mandated by FREEZE C5 because of the Week-3 Water-VGGT finding, not download
statistics. Identical `model_config`, identical 483-tensor key set, zero shape
mismatches, global relative L2 **0.0096**. It is a decoder-heavy fine-tune and
the split says so: encoder median rel-L2 **0.0002** over 352 tensors, versus
neck 0.033, points head 0.027, mask head 0.019, scale head 0.044. V5's premise —
architecture and representation genuinely controlled — holds. It still does not
unconfound *which* part of the fine-tuning treatment causes any later difference.

**Surprising, and a pre-S3 flag.** On the same frame MoGe-2 and MetricAnything
recover materially different cameras: normalised fx **0.465 vs 0.611**. Both
models' metric scale is coupled to the recovered focal, so their absolute scales
should be expected to disagree — which is exactly what V9's known-FOV
*postprocessing* ablation is for. Separately, FoundationGeo's learned ray
correction turns rays by a median of **0.044°** (p95 0.11°, max 0.78°), an order
of magnitude under its own 3° cap, and its "per-pixel spatial" `scalefield` sits
at 0.84 with a 0.82–0.85 spread — behaving almost like a global scalar. Both are
one-frame observations, not conclusions; S3 runs the ablations properly.

**Reference-implementation modifications required:** exactly one model needed
any. DA3 — `requires-python` widened to install on CPython 3.13.5, and the
pycolmap-backed COLMAP *export* import made optional (importing pycolmap
alongside torch aborts on macOS with a duplicate libomp). FoundationGeo needed a
hard-coded `device='cuda'` moved off a CUDA-less host, where it only chooses
where uninitialised parameters land before a strict `load_state_dict` overwrites
every one. Patches in `experiments/week4_mono/round1/patches/`. None touches weights,
structure or any numerical path.

**Deliberate non-modifications, each replacing an easy wrong patch.** `moge` is
put on `sys.path` explicitly rather than pip-installed — both the MetricAnything
release and upstream microsoft/MoGe ship a package literally named `moge`, an
installed one would silently win, and V5 would stop being controlled without any
error. And FoundationGeo's `infer()` is **not** called: it postprocesses its two
ray-correction arms through *independent* `recover_focal_shift` solutions, so
their difference is the ray correction plus whatever focal and shift each
recovered separately. The backend calls `forward()` and applies one frozen
solution to both arms, which is what FREEZE C3 requires.

**Artifacts:** `experiments/week4_mono/round1/results/S0_SEMANTICS_RUNTIME.md`,
`S0_results.json`; raw per-model records in `outputs/s0/`.

**Next:** S1 determinism and noise floor. No downstream delta smaller than the
floor S1 measures may be read as signal.

## 2026-09-06 — Week 4A: S1 determinism, the 288-frame sweep, S2 ambiguity gate

**S1 — all seven bitwise reproducible, floor exactly zero.** Repeated inference
on identical input, both within one process and across separate processes,
returns bit-identical arrays for every entrant. The measured p99 relative
noise floor is therefore `0.0` across the board, and no downstream delta in
S3–S6 has to be discounted as run-to-run noise.

That result is manufactured, not lucky: MoGe-2's and FoundationGeo's
`use_fp16=True` defaults are explicitly overridden to float32 with autocast off
everywhere. Half precision on MPS would have put a stochastic floor under every
difference the later stages are built to read.

What S1 does **not** license: the binding floor on this whole comparison is not
model noise but the *reference's* own instability, which Week 3 measured at
2.1–6.5 % median on `wreck_05` against 0.01 % on `wreck_07`.

**The 288-frame sweep.** Seven models × 6 clips × 48 frames, one model per
process in the freeze's integration order, `mapanything_n1 → dav2_small →
moge2_vitl → metricanything_pointmap → wat3r_n1 → da3mono_large →
foundationgeo_11`. All 2016 predictions persisted (26 GB under
`outputs/predictions/`, gitignored). Runtime per model over 288 frames:
MapAnything 347 s (peak RSS 9.58 GB), DA V2 72 s (0.7 GB), MoGe-2 724 s
(2.8 GB), MetricAnything 746 s (2.8 GB), Wat3R 438 s (9.17 GB), DA3 Mono 117 s
(2.89 GB), FoundationGeo 535 s (2.7 GB).

**A real defect, caught by a guard doing its job.** `wat3r_n1` failed all six
clips on the first pass with `unknown native_kind 'pointmap'`.
`monoio.NATIVE_KINDS` is a closed set precisely so a backend cannot invent a
representation string, and `common.DECLARED_NATIVE` declared one that had never
been added. The analysis side already treated `"pointmap"` as its own third kind
— `LEGAL_FAMILIES["pointmap"] = ["none", "scale", "affine_depth"]`, the widest
set of any entrant — so only the writer's set was missing it.

Resolved as a distinct kind rather than folded into `pointmap_metric` or
`pointmap_relative`, because that choice is a scientific claim: FREEZE §3.3
forbids inferring Wat3R's native ambiguity from its released evaluation code's
alignment, and declaring it either way here would be exactly that inheritance.
`pointmap` now means *camera-frame point map whose scale claim the release does
not state*, and the question is settled by measurement in S2. The validation
fires at `close()`, i.e. after 48 frames of inference are already paid for, so a
test now asserts every `DECLARED_NATIVE` value is writable.

**S2 — the frozen alignment policy.** 9 arms (7 models + FoundationGeo's two ray
arms, which inherit). Clip-level scope for every arm; per-frame fits are kept as
diagnostics only, because renormalising each frame would erase the temporal
scale drift FREEZE C7 makes a first-class failure mode.

| arm | native | E1 family | convention | source |
|---|---|---|---|---|
| `mapanything_n1` | depth_along_ray_metric | scale | range | S0 semantics |
| `dav2_small` | disparity_relative | affine_disparity | range | MEASURED |
| `moge2_vitl` | pointmap_metric | scale | range | S0 semantics |
| `metricanything_pointmap` | pointmap_metric | scale | range | S0 semantics |
| `wat3r_n1` | pointmap | scale | range | S0 semantics |
| `da3mono_large` | depth_relative | affine_depth | range | MEASURED |
| `foundationgeo_11` | pointmap_metric | scale | range | S0 semantics |

**The two open conventions, settled by residual rather than by paper.** Neither
came back clean, and both are recorded as what they are. `dav2_small` pools to a
margin ratio of **1.0185** — inside the 3 % threshold, so INDISTINGUISHABLE,
defaulted to the project's canonical range with the tie recorded (per-clip: 1
z-depth, 2 range, 3 indistinguishable). `da3mono_large` pools to **1.1109** in
favour of range (0.1358 vs 0.1509), with 3 of 6 clips agreeing. A verdict of
INDISTINGUISHABLE is itself informative here: it means the model's shape error is
larger than this camera's 35 % radial secant term.

**The additive term earns its place for DA3 Mono.** Granting the shift over
scale-only removes a median **38.3 %** of the error (per clip up to +55.6 %).
FREEZE C1 allows "approximately scale-only" only from measured evidence; this
measurement denies it. For `wat3r_n1` the gain is a median +11.1 % and is
*negative* on one clip.

**Raw metric behaviour — recorded pre-C2, judged post-C2.**

| arm | raw abs-rel | E1-aligned | oracle scale by clip | clip-to-clip spread |
|---|---|---|---|---|
| `mapanything_n1` | 0.1158 | 0.1019 | 0.93–1.12 | 1.200 |
| `foundationgeo_11` | 0.5793 | 0.1869 | 0.52–2.54 | 4.860 |
| `metricanything_pointmap` | 0.6297 | 0.1943 | 1.66–2.93 | 1.759 |
| `moge2_vitl` | 0.6447 | 0.2189 | 1.94–3.03 | 1.559 |
| `wat3r_n1` | 0.9354 | 0.2021 | 5.21–28.2 | 5.412 |
| `da3mono_large` | — | 0.1331 | 2.76–8.99 | 3.259 |
| `dav2_small` | — | 0.1739 | 0.009–0.037 | 4.594 |

Three things worth carrying forward. **Wat3R's metric claim does not survive
contact with the data** — an oracle scale between 5× and 28× across six clips is
not a metric field with a bias, and this is the measured answer to the question
the freeze forbade inheriting from its eval code. **MoGe-2 and MetricAnything are
consistently ~2–3× off but internally consistent** (spread 1.56 / 1.76), which is
the signature of a global gauge error rather than scene-dependent scale.
**FoundationGeo is the metric claimant with the least consistent scale**
(0.52 on `cenote_01` against 2.54 on `wreck_05`, spread 4.86) — and a scale that
depends on the scene is a different and worse problem than a scale that is
uniformly wrong, because only the latter is absorbable by `b → b/s`.

Clip-to-clip spread is a diagnostic of the metric *claim*, not a C7 failure — the
frozen policy re-fits per clip, and different clips are different scenes. The C7
quantity is within-clip drift, and it is already visible: median within-clip
scale wander runs 1.84–3.17 for every arm including MapAnything N=1, worst case
17.4 for DA V2. That is the S5 question, measured here so the policy carries it.

**One confound to state before S3 reads a single ranking.** `mapanything_n1`
scores roughly half everyone else's aligned error, and the reference *is*
MapAnything run multi-view. Agreement with one's own family's multi-view solution
is weaker evidence than agreement from an independent architecture, and S3 must
not read it as a quality ranking.

**Cross-check.** This session's independent S0 measurement of MapAnything's
preprocessing agrees with Week 3's persisted `preprocess_maps.json` to ~1e-11 in
scale and ~1e-8 px in offset — evidence the reference is being sampled on the
grid it was written on.

**Artifacts:** `results/S1_DETERMINISM.md`, `S1_results.json`,
`S2_AMBIGUITY.md`, `S2_alignment_policy.json`; raw measurements in
`outputs/s1/`, `outputs/s2/s2_raw.json`.

**Next:** S3 local geometry over all 288 frames × 10 arms — the primary
reduction from 7 candidates to ~3–4.

## 2026-09-06 — Week 4A: S3 local geometry, the primary reduction (7 → 4)

Nine arms (7 candidates + FoundationGeo's two causal ablation arms) over the full
frozen set: 6 clips × 48 frames, six dimensions, no weighted master score. The
dimensions disagree about the ordering, which is exactly why FREEZE §6 forbids
collapsing them.

| arm | M-1 abs-rel | M-2 b | M-3 RelNormal | M-3 normal | M-4 boundary | M-5 ord@25% | M-6 out/in | coverage |
|---|---|---|---|---|---|---|---|---|
| `mapanything_n1` | 0.085 | 0.950 | 6.84° | 7.9° | 0.0028 | 0.0000 | 1.04 | 0.778 |
| `da3mono_large` | 0.128 | 0.846 | 12.77° | 20.6° | 0.0285 | 0.0037 | 1.01 | 0.808 |
| `foundationgeo_11` | 0.171 | 0.845 | 32.71° | 38.5° | 0.0423 | 0.0862 | 0.79 | 0.806 |
| `dav2_small` | 0.176 | 0.535 | 27.50° | 36.3° | 0.1022 | 0.1172 | 0.93 | 0.786 |
| `metricanything_pointmap` | 0.182 | 0.975 | 27.50° | 30.0° | 0.0360 | 0.0665 | 0.94 | 0.782 |
| `wat3r_n1` | 0.184 | 1.223 | 15.62° | 19.9° | 0.0171 | 0.0057 | 0.93 | 0.776 |
| `moge2_vitl` | 0.216 | 1.211 | 27.78° | 30.3° | 0.0355 | 0.0676 | 1.01 | 0.801 |

**The confound, stated before the ranking.** `mapanything_n1` leads all six
dimensions, several by 2× or more — and the reference *is* MapAnything run
multi-view. Two runs of one architecture share inductive biases and therefore
share systematic errors, and a shared systematic error is invisible to a
disagreement metric. Pre-C2 nothing here can separate "better geometry" from
"the same errors as the reference". It advances because the fallback question is
literally whether this architecture keeps usable geometry at N=1 — not as the
objective best.

**Scale-invariant far field (M-1b, q80–100) is the most decision-relevant
column**, because that is the band where the water path is longest and where
attenuation inversion is most sensitive: MapAnything 0.104, DA3 Mono 0.129,
Wat3R 0.229, DA V2 0.333, FoundationGeo 0.336, MetricAnything **0.682**,
MoGe-2 **1.098**.

**Eliminated at S3, each on a named dimension.**

*`dav2_small` — structure.* M-4 boundary 0.1022 is ~3× the next-worst arm and 36×
the leader (0.2749 on the portrait clip); M-2 slope 0.535, falling to 0.101 on
`wreck_03`, is severe near/far compression. Boundary failure is what a
backscatter stage turns into visible haloes. Its 0.2 s/frame cost is real but
does not buy this.

*`foundationgeo_11` — shape.* Worst surface orientation in the field on both
forms (32.71° RelNormal, 38.5° absolute, 47.2° worst clip) and the worst radial
signature (M-6 0.79, reaching 0.54 on `swimthrough_02`) — a systematic radial
term on a wide-FOV underwater camera is the specific failure M-6 exists to catch.
Its S2 scale is also the least consistent of any metric claimant (0.55–2.51).

*`moge2_vitl` — far field, and it loses its own V5 comparison.* Far quintile
**1.098**, i.e. median relative range error above 100 % in the most consequential
band. MetricAnything — same architecture, heterogeneous metric fine-tuning —
reaches 0.682 there with better M-1 (0.182 vs 0.216) and much better M-2 (0.975
vs 1.211). **V5's question is answered: the fine-tune helps.** Carrying both
forward would carry a control past the point where it controls anything.

**The two FoundationGeo interventions, measured causally under one frozen
(focal, shift) from one forward pass.**

*V4b (learned ray correction) is null on this footage.* All six dimensions move
by less than printing precision. Not an artefact and not the arms being the same
data — the point maps differ by a mean relative 1.1e-03. The mechanism is in the
raw fields: the correction turns each ray by a median **0.044°** (p99 0.21°, max
0.78°) against its own **3° cap**, and rotating a ray changes bearing while
leaving length nearly untouched — the induced change in *range* is a median
relative **2.3e-07** (p99 3.8e-06). This project consumes range, not bearing, so
V4b is irrelevant to it by construction. That the learned delta uses ~1.5 % of
its permitted capacity is itself the finding.

*V4c (learned per-pixel scale field) makes agreement worse.* +7.3 % on M-1
(0.1596 → 0.1712), +6.1 % on absolute normal error, +1.8 % on RelNormal, buying
back only −2.4 % on M-4 and −1.5 % on M-6. And it is barely per-pixel: median
0.840, p01–p99 0.803–0.872 — a global 0.84 scalar with a ±4 % ripple. The E1
policy already grants a clip-level scale, so the global part is absorbed and only
the ripple is scored; the ripple is a net loss. Both deltas clear the S1 floor
trivially, that floor being exactly zero.

**Advancing to S4 — four arms, deliberately four different *kinds*:**
`mapanything_n1` (the reference's own architecture at N=1 — the fallback question
itself), `da3mono_large` (strongest arm independent of the reference; flattest
radial signature at M-6 1.01 and best coverage 0.808, but relative-only so it
brings no scale), `wat3r_n1` (the underwater-specialisation control, 2nd best on
both M-4 and M-5, but **loses 44 % of the portrait frame** at coverage 0.562 and
carries an oracle-only 5.2–28.2× scale), `metricanything_pointmap` (best
metric-claimed point-map model on M-1/M-2/far-field, but 0.682 in the far
quintile and 0.365 on the portrait clip).

Keeping the four best M-1 values would have discarded every architecture capable
of disagreeing with the reference for an interesting reason.

**Artifacts:** `results/S3_LOCAL_GEOMETRY.md`, `S3_results.json`;
`outputs/s3/s3_raw.json`.

**Next:** S4 appearance invariance — 12 geometry-preserving perturbations in
linear light, decomposed into constant scale bias / frame-varying drift / local
range deformation.


## 2026-09-06 — Week 4A: S4 appearance invariance (all four survivors advance)

**Ran.** 4 S3 survivors x 13 arms x 6 clips x 16 frames = 312 (arm,clip) products,
34 GB, one model per process, strictly N=1.

```
bash experiments/week4_mono/round1/scripts/run_s4_survivors.sh
PYTHONPATH=$PWD experiments/week4_mono/.venv-eval/bin/python \
  -m experiments.week4_mono.round1.scripts.s4_analysis --overwrite
PYTHONPATH=$PWD experiments/week4_mono/.venv-eval/bin/python \
  -m experiments.week4_mono.round1.scripts.s4_report --overwrite
```

Runtimes: mapanything 1920 s, da3mono 517 s, wat3r 2673 s, metricanything 4668 s.

**Two defects found in this stage, both fixed before conclusions were drawn.**

*(a) The cue conflict was measuring its own control.* `cue_conflict_inverted_veil`
and `veil_depth_consistent` came out bit-identical: each stated its direction twice
— swapped `t_near`/`t_far` AND an `invert` flag — and the double negation cancelled.
Caught because the two agreed to four decimals on every model and clip. `invert`
removed from `perturb.py`; arm regenerated (96 frames changed, other 11 arms
byte-identical by hash); that arm re-inferred on the four survivors (799 s). Two
tests added — pairwise, no two arms may be the same stimulus; and on the stimulus,
the control must veil the far field and the conflict the near. 31 tests pass.
Blast radius contained to S4: only `s4_make_perturbations` and `s4_run` read the
perturbed frames, so S0–S3 stand and S5/S6 do not use them.

*(b) The cross-model table was comparing different units — and this one reversed the
stage's conclusion.* Rows 3/3b are in each model's NATIVE quantity. Three survivors
are scale-family, where native is proportional to range, so native == physical. But
`da3mono_large` is `affine_depth`, range = `s*d + t`, with a large fitted shift
(t = 1.78–11.56 m against median scene ranges 6.4–22.5 m), so its native log-ratios
are inflated ~2x: `L_phys ~= L_native * (1 - t/r)`, factor ~0.51 here. Added row 3c,
the same residual in physical range under a gauge fitted on the BASELINE arm alone
and then frozen (a unit conversion; no oracle sees a perturbed field). The
scale-family columns reproduce row 3 to four decimals — the check that it is right.

Read natively, da3mono looked like the worst model in the stage by a wide margin and
the obvious elimination. Read in range it is the most appearance-invariant of the
four. Recording this because the native-unit table was not obviously wrong to look
at; it took asking why the one affine-family arm was an outlier.

**Findings (all on physical range).**

- Colour and exposure are geometrically inert: `wb_*`/`brightness_*` 0.0022–0.0081
  for all four, at the 8-bit floor. `attenuation_red` 0.0041–0.0124.
- The response is essentially all veil, and two different models win the two halves:

  | model | non-veil mean (9 arms) | veil mean (3 arms) | all 12 |
  |---|---|---|---|
  | mapanything_n1 | 0.0215 | **0.0383** | 0.0257 |
  | metricanything_pointmap | 0.0130 | 0.0869 | 0.0315 |
  | wat3r_n1 | 0.0204 | 0.0725 | 0.0334 |
  | da3mono_large | **0.0089** | 0.0670 | **0.0234** |

  da3mono is steadiest under everything that is not haze (1.5x the next, best on 9 of
  12 arms); mapanything is steadiest under haze (1.75x the next, best on all three).
  For underwater the veil column is the one that matters — haze is the permanent
  condition of the medium and covaries with the quantity being estimated.
- Cue conflict vs its matched control (same veil magnitude, direction reversed) —
  the ratio is unaffected by defect (b) since both terms carry the same factor:
  mapanything 0.0578/0.0245 = 2.36x, metricanything 0.1107/0.0742 = 1.49x,
  wat3r 0.1072/0.0550 = 1.95x, **da3mono 0.1128/0.0283 = 3.99x**.
  da3mono's calm and its veil-leaning are the same fact: it is stable exactly as long
  as the haze cue is honest. metricanything's low ratio is not robustness — its
  control response is the worst of the four, so it is already deformed under a
  correct veil.
  Caveat kept explicit: real footage has veil running WITH depth (the control column,
  0.0245–0.0742, inside the 12 %-at-3 m budget). The inverted arm probes mechanism,
  not deployment.
- FREEZE C7 earns its keep again: mapanything has the LARGEST global scale response
  to `veil_uniform` (sigma 1.4156) and the SMALLEST local deformation (0.0327);
  da3mono 1.0941 / 0.0598. Constant global scale is a benign gauge absorbed by
  `beta' = beta/s`; local deformation is not absorbable. Ranking on sigma would have
  inverted the ranking that matters. Two separate ways this stage would have ranked
  the field backwards on a naive robustness number.
- Scale wander: da3mono 1.01–1.30 and wat3r 1.03–1.22 hold far steadier than
  mapanything 1.06–1.62 and metricanything 1.06–1.87. Pipeline consequence:
  `channel_neutralize` — gray-world, what our own baseline does — is mapanything's
  WORST wander arm (1.6159). Gray-world before monocular inference is not neutral.
- wat3r and da3mono cannot signal their own failure: coverage exactly unchanged on
  all twelve arms, neither emits confidence. Not stability — silence.
- Boundary jitter is floor-saturated (median NN distance, 0.00 for three models) and
  ranks only mapanything. Reported, not used.

**Gate: all four advance to S5.** Reduction to 2–3 finalists comes after S5; post
correction this stage holds no disqualifying result. metricanything_pointmap is now
the weakest of the four here, not da3mono_large.

**Carried into S6 as a named question.** If a model draws geometry from veil and
restoration removes veil, then range-before and range-after restoration are different
fields and the pipeline is self-referential. The cue-conflict ratio measures how tight
that loop is — tightest for the model that otherwise looks steadiest.

Persisted: `results/S4_APPEARANCE.md`, `results/S4_results.json`.

## 2026-09-06 — Week 4A: S5 temporal stability, reduction to 2 finalists

**Ran.** All 9 arms x 6 clips, independent per-frame inference from the main sweep,
SEA-RAFT correspondence computed once per clip, frozen epistemic partition.

```
PYTHONPATH=$PWD experiments/week4_mono/.venv-eval/bin/python \
  -m experiments.week4_mono.round1.scripts.s5_temporal --overwrite
PYTHONPATH=$PWD experiments/week4_mono/.venv-eval/bin/python \
  -m experiments.week4_mono.round1.scripts.s5_report --overwrite
```

S5 applies the frozen S2 policy before measuring, so it is already in physical range
and the S4 unit defect does not apply here.

**Findings.**

- `da3mono_large` is the most temporally stable model in the field: local instability
  0.0096 vs mapanything 0.0189, metricanything 0.0197, wat3r 0.0217 — 2.0x the next,
  and better on all six clips individually (0.0066–0.0128). In `static_anchored`, the
  only partition where the reference may arbitrate, it wins all six again
  (0.0059–0.0119). Also best near/far wander (2.17) and best coverage (0.808).
- S4 and S5 agree and for one reason. A single-image relative-depth model with a
  strong layout prior returns the same layout for similar-looking frames — that is
  the stability. The same prior is keyed on appearance including haze — that is the
  3.99x cue-conflict ratio. One property, two sides.
- `metricanything_pointmap` is last or near-last everywhere: near/far wander 6.51 vs
  2.17–3.62 (the SHAPE of its depth range, not just scale, changes 6x within a clip),
  worst f2f MAD 0.0773, 7.112 scale wander on wreck_01 — on top of the worst S3 far
  quintile (0.682) and the worst S4 veil mean.
- `mapanything_n1`'s instability is concentrated on `cenote_01`: scale wander 5.607
  (vs 1.521–2.477 elsewhere), local instability 0.0387 (vs 0.0157–0.0228). The widest
  near/far clip in the set. The strongest S3 model destabilises specifically where
  the scene is deep — exactly where the 8.5 %-at-8 m budget is tightest.
- `wat3r_n1` degrades most from `static_anchored` (0.0116–0.0274) to
  `static_reference_uncertain` (0.0312–0.0429): it is least reliable where it is
  least checkable.
- **Nobody is temporally stable in absolute terms.** Scale wander is 1.84–2.29 for
  all four — the scalar relating output to reference moves by 2x or more inside a
  48-frame clip. Absorbing that under one clip-level coefficient needs
  `beta'_t = beta/s_t`, water properties that change with the estimator. No monocular
  candidate can supply temporally coherent scale on its own; Week 5–6's temporal
  stage must own scale continuity regardless of which model is chosen.
- Dynamic-region numbers recorded, not used as a quality claim (freeze).

**Reduction 4 -> 2.**

- Eliminated `metricanything_pointmap`: last or near-last in S3, S4 and S5; nothing
  best-in-field.
- Eliminated `wat3r_n1`: dominated by da3mono on every S3 geometry dimension
  (M-1 0.184 vs 0.128, far 0.229 vs 0.129, normals 15.62° vs 12.77°), and S0's
  portrait failure stands — 10/25 FOV markers and 44 % of frame area lost, a
  structural failure for a video pipeline.
- **Finalists: `mapanything_n1` (best geometry, most veil-robust) and
  `da3mono_large` (most temporally stable, most appearance-invariant off-veil).**
  Two rather than three: the pair spans the design space (multi-view-trained metric
  point map vs single-image affine-ambiguous relative depth) and both eliminated arms
  are dominated rather than merely behind.

**Shared unresolved question.** da3mono needs a fitted affine (s,t) with t = 1.78–11.56 m;
mapanything needs a scale. Neither is available at inference without an oracle. S6
measures restoration impact UNDER the frozen oracle alignment and does not establish
deployability without one. That is C2's question.

Persisted: `results/S5_TEMPORAL.md`, `results/S5_results.json`.

## 2026-09-06 — Week 4A: S6 restoration impact (both finalists DEGRADED), and two instrument defects

**Commands.**

```
PYTHONPATH=$PWD experiments/week4_mono/.venv-eval/bin/python \
  -m experiments.week4_mono.round1.scripts.s6_restoration --overwrite
PYTHONPATH=$PWD experiments/week4_mono/.venv-eval/bin/python \
  -m experiments.week4_mono.round1.scripts.s6_temporal --overwrite
PYTHONPATH=$PWD experiments/week4_mono/.venv-eval/bin/python \
  -m experiments.week4_mono.round1.scripts.s6_inspect --overwrite
PYTHONPATH=$PWD .venv/bin/python \
  -m experiments.week4_mono.round1.scripts.s6_report --overwrite
```

**Config.** Arms `week3_reference` (Week-3 persisted multi-view range) vs
`mapanything_n1` (`facebook/map-anything-apache`, N=1) vs `da3mono_large`
(`depth-anything/DA3MONO-LARGE`), same six frozen clips, 48 frames each, SOURCE
resolution, frozen S2 oracle alignment. Image-formation coefficients are the
Jerlov-bracketing sets Week 3 swept: coastal (primary) `b_att` [0.55, 0.20, 0.19]
/ `b_bs` [0.45, 0.22, 0.22]; clear_oceanic [0.35, 0.09, 0.08] / [0.30, 0.11, 0.10];
turbid_coastal [0.85, 0.45, 0.48] / [0.70, 0.50, 0.55]. `J_CLAMP` 8.0,
`T_FLOOR` 0.05. Coefficients and `Binf` are SHARED and FIXED across arms —
`d_hat` is the only thing that varies. Temporal metrics are the unchanged
Phase-2B machinery (SEA-RAFT, MC-warp at lags 1/4/8, temporal ΔE00), plus an
`mcwarp_input_lagN` control measured on the UNPROCESSED sequence with the same
correspondence and mask.

**Two defects in the instrument, found and fixed before any number was read.**

The first full run reported median ΔE00 = 0.000 on four of six clips. It was not
agreement. Restored frames were monochrome red (median `[0.75, 0, 0]`), 99 % of
pixels had at least one channel driven negative and clipped, and 50–84 % of the
common support was BIT-IDENTICAL between arms. Two saturations agreeing.

1. **The veiling light was not one the image could carry.** `Binf` as the p90 of
   the far field is inadmissible on footage whose water column is CLIPPED in the
   source: `wreck_07` and `wreck_03` blow out blue at 10.7 % / 14.4 % of pixels at
   code 254+, giving `Binf_B = 1.0`, and `1.0·(1−exp(−0.22·7 m)) = 0.79` exceeds
   the observed blue nearly everywhere not far away. Exactly the four clips
   reporting 0.000 are the four with inadmissible `Binf`. The model states its own
   bound: `J ≥ 0` requires `Binf_c ≤ min_p I_c(p)/(1−exp(−b_bs_c·d(p)))`, whose
   minimising pixels are the darkest ones AT THEIR OWN RANGE — the dark-channel
   estimator made exact by knowing `d`. `Binf` is now that far-field p90 capped by
   the bound at its 1st percentile (`restoration.admissible_veiling_light`).
2. **The inversion gain was unbounded.** Reference ranges run past 50 m where
   `1/exp(−0.55 d)` is 1e12; the 8-bit source's linear quantisation step is ~3e-4,
   so past ~20× the amplified step stops being negligible against restored medians
   of 0.2–0.5. Transmission is floored at `T_FLOOR = 0.05` per channel — red stops
   responding beyond ~5.4 m coastal while green and blue respond past 15 m.

Consequence for reporting: every metric is now given twice, over the full common
support and over the RESPONSIVE WINDOW (pixels not floored in every channel and
not pinned at either clamp end in either arm), with the window fraction alongside.
Outside that window two range fields produce the same pixel however much they
disagree. `compare_restorations` now returns a total key set with NaN and a
`status` where a quantity is undefined, and the aggregator counts colour frames
and radiance frames separately.

**Findings (responsive window, coastal; window fraction in brackets).**

- Windowed median ΔE00, mapanything / da3mono: wreck_07 2.13/3.18 [0.59/0.64],
  wreck_05 2.56/**7.78** [0.39/0.38], cenote_01 1.83/**1.59** [0.96/0.97],
  swimthrough_02 2.72/3.49 [0.76/0.73], wreck_01 2.70/3.53 [0.99/0.99],
  wreck_03 2.93/4.28 [0.34/0.19]. MapAnything is the tighter arm on five of six.
- Windowed median |relative radiance error| — the quantity directly comparable to
  the Week-3 budget (5 % worst-channel radiance error at 9.4 % range error @3 m,
  6.1 % @8 m coastal): mapanything 0.039–0.190 (median ≈ 0.10), da3mono
  0.064–0.333. **Neither finalist meets the budget.** MapAnything misses by ≈2×,
  da3mono by up to 6×.
- The ranking is the same in `clear_oceanic` (mapanything windowed ΔE00
  1.10–2.64, da3mono 1.84–5.83). `turbid_coastal` is UNMEASURABLE on this footage
  — every channel floored on 100 % of pixels for four of six clips under da3mono
  and two under mapanything — and its row must not be used.
- **The failure modes are opposite.** MapAnything's static disagreement is small
  and often close to a pure global gauge (`wreck_01`'s signed disagreement is a
  near-uniform field, benign per FREEZE C7 and absorbable by `b → b/s`), but it is
  the temporally worse arm: higher windowed colour pumping on five of six clips
  (1.72 on `wreck_05`), and on `cenote_01` it more than DOUBLES MC-warp against the
  reference-driven arm (0.02330 vs 0.00983) and lifts temporal ΔE00 from 2.82 to
  6.75 (input control 2.51). da3mono is the more stable arm — lower pumping on
  five of six, the only arm not degrading `cenote_01`, and better than the
  reference at lag 8 on `wreck_01` (0.00710 vs 0.00848) — but its static errors are
  structured deformations, not gauges.
- **Every arm, the reference included, makes the footage temporally WORSE than its
  own unprocessed input** at lag 1 on five of six clips (reference ratios
  1.17–3.73). A fixed-coefficient range-driven inversion amplifies per-frame range
  noise into colour. The temporal rows are therefore only readable as
  arm-vs-reference, never arm-vs-nothing.
- Reference-restoration health is worst on exactly the clips where disagreement is
  worst: responsive fraction 0.41 on `wreck_05` and `wreck_03`, p99 gains asked for
  reaching 1e8. Pre-C2 that is a limit on the verdict, not a point for either arm.

**Visual inspection (CLAUDE.md invariant 5).** 18 sheets and 144
worst-disagreement crops under `outputs/s6/inspect/`; six frames viewed across
five clips. No hallucinated texture — the instrument is a per-pixel gain and
cannot invent detail, and scene identity survives in every arm. Hallucinated
GEOMETRY does show up as hallucinated colour: on `wreck_07` da3mono fills the thin
crane lattice with a solid opaque surface where reference and mapanything leave
holes, so water seen THROUGH the lattice is restored at the lattice's range; on
`wreck_03` it displaces the diver — the moving subject — farther and renders it
visibly redder; on `swimthrough_02` it puts the central channel much deeper and
blows it out to bright cyan. Both arms' worst crops on `cenote_01` land in the
unlit cave void, where the source is black and no monocular model can do better —
the cost there is instability, not error. Every arm including the reference
produces unnatural orange-brown colour under the fixed coastal coefficients; that
is the coefficients, which Week 6 owns, and it is why S6 is a differencing
instrument and not a deliverable.

**Classification: both finalists DEGRADED relative to the current Week-3
hypothesis**, `da3mono_large` approaching UNSAFE on low-texture lateral footage
(`wreck_05`: windowed ΔE00 7.78, p95 16.1, 33 % radiance error) and on
scene-identity grounds (thin structure, dynamic subject). Neither is ADEQUATE.
Neither is eliminated: pre-C2 there is no independent anchor, so a
monocular-vs-reference disagreement cannot say which side is wrong, and the two
arms fail in complementary ways.

Persisted: `results/S6_RESTORATION.md`, `results/S6_results.json`,
`outputs/s6/{s6_raw.json, s6_temporal.json, inspect/}`. Tests: 34 passing
(`.venv/bin/python -m pytest tests/test_week4_mono.py`), three new ones covering
the total key set, the admissible veiling light, and the transmission floor.

### Week 4A close-out (same session)

`FINALISTS_PRE_C2.md` written: full elimination chain with the stage, dimension and
number behind each exit; the two pre-C2 finalists with what each still has to
prove; nine unresolved questions carried into C2. **No weighted master score and no
objective Week-4 winner** — pre-C2 the reference is a hypothesis, so raw metric
behaviour is RECORDED here and JUDGED after C2.

Baseline re-checked after the session, unchanged bit-for-bit:
`temporal_stability(gray_world(f) for f in load('data/testset/murky/
MURKYSHARK.MP4'))` = `3.244860636186786e-05`. `pytest tests/` 357 passed, 1
skipped (323 + 34 Week-4).

**Next: C2 acquisition.** Every remaining Week-4 question is blocked on it — the
reference-architecture confound, scale at inference, and whether either finalist's
range error is inside the restoration budget in absolute rather than relative terms.

---

## Week 4A — ROUND 2: correctness repair + bounded SOTA challenger bakeoff

Still **PRE-C2**. The Week-3 range product remains a provisional multi-view
hypothesis; disagreement with it is not error, and no objective Week-4 winner is
declared here. Same frozen footage as Round 1 (`wreck_07, wreck_05, cenote_01,
swimthrough_02, wreck_01, wreck_03`, 48 frames each, 288 per model, no
resampling). All artifacts under `experiments/week4_mono/round2/`.

### R2 Parts A–C — correctness repair (`R2_PARTS_ABC_CORRECTNESS.md`)

**A.** DA3 defines `P = t + D·R·K⁻¹p`, and `K⁻¹[u,v,1]ᵀ` has z-component 1, so
`da3mono_large`'s scalar `D` is **camera-axis z-depth, not ray range** — the
Round-1 "unresolved" verdict was wrong, and it was wrong because it was decided
by residual instead of by source. Refit in native z with the frozen camera model
(`ρ = ‖K⁻¹p‖`, `z_ref = r_ref/ρ`), affine `z_ref = s·z_DA3 + t` at the frozen
clip-level scope. **B.** DA v2 refit in native disparity (`q_ref = a·q_DAv2 + b`);
still clearly eliminated, so stopped there per §4. **C.** FoundationGeo C1/C2
mechanism check under one common coordinate treatment.

### R2 Part D — grid-map defect (`R2_PART_D_GRIDMAP_DEFECT.md`)

Source-grid and network-input-grid models were being mapped through the same
transform. Repaired for the four source-grid arms (`dav2_small`,
`foundationgeo_11`, `metricanything_pointmap`, `moge2_vitl`); the three
network-grid arms (`mapanything_n1`, `wat3r_n1`, `da3mono_large`) are bitwise
unchanged and serve as controls. Every load-bearing Round-1 number affected by
A or D is republished OLD vs CORRECTED.

### R2 S0 / S2 (`R2_S0_SEMANTICS_RUNTIME.md`, `R2_S2_alignment_policy.json`)

S0 gate resolved native representation, gauge, N=1 strictness and licence per
challenger from source, not from residuals. S2 keeps the frozen policy — common
policy, representation-specific transform, never one universal `a·d+b`;
clip-level fit for E1, per-frame fit diagnostic only, no helper model's scale.
`surge_large` = `pending_cuda`; `hyden`, `pointdit_l_512` = `pending_checkpoint`.

### R2 S5 temporal (`R2_S5_TEMPORAL.md`, `R2_S5_results.json`)

Nine arms, each frame still inferred independently, read under FREEZE C7
(`d'_t = s_t·d_t` is consistent under `β'_t = β/s_t`, so constant clip-wide scale
may be benign; frame-varying scale is not). `mda_mog_sky_l2` fails exactly the
non-absorbable part: `f2f_log_mad` 0.174 vs 0.079 next-worst, wander 11.1 vs 2.8,
while its local surface stability (0.0174) is third best. MoGe-3 Step 0 is
temporally **worse** than MoGe-2 (0.0794 vs 0.0679) despite winning S3 — recorded
as a trade-off, not resolved. Corrected DA3 has the best local stability of all
nine (0.0119 / p95 0.0268).

### R2 thin-structure test, §18 triggered (`R2_THIN_STRUCTURE.md`, `R2_thin_structure_results.json`)

Six `wreck_07` frames, annotation from the **image** (veiling is monotone in
range) rather than from the reference, because grading thin structure against a
multi-view product would grade every model against the failure under test. Tier A
= openings photometrically indistinguishable from the water column; Tier B
recesses reported separately (all arms ≈ 0 there — a clean control). Evaluated at
source resolution with the frozen S2 gauge; no inference re-run.

- The **provisional reference is itself blind to thin structure** (gap +0.000,
  41 % of members erased), and `mapanything_n1` reproduces that blindness exactly
  (+0.006, 45 % erased, Tier-A coverage 0.752). Its failure mode is a *missing
  member*, not a false surface. Any metric computed against the reference is
  therefore blind in this region — carried into the §19 reduction.
- **Corrected `da3mono_large` (+0.411, 4 % erased) is materially better at the
  lattice than MapAnything**, reversing Round-1 S6's "fills the lattice with a
  solid opaque surface" — that observation was an artefact of our own z-vs-range
  convention and fitting family, not of the model. A §26 correctness-repair
  headline.
- `moge2_vitl` (+1.619) and `metricanything_pointmap` (+1.333) separate the
  lattice most strongly, erase no members and have the best edge localisation —
  but place the far anchor at 175 m and 85 m against ~31 m. How much of the
  margin is acuity and how much is far-field expansion **cannot be settled
  pre-C2**; a C2 range measurement on the water column beside the crane would.

Visual inspection performed and mandatory (CLAUDE.md invariant 5):
`outputs/thin/{overlay_f*.png, ranges_f000059.png, ranges_f000109.png,
crane_f000109.png}`. It corrected one numeric reading — `wat3r_n1`'s +0.446 is
large-scale near/far separation, not lattice acuity; the crop shows a smooth blob.

`armio.Arm` gained an optional `downsample` (default unchanged at
`EVAL_DOWNSAMPLE = 4`) so this stage could sample at stride 1; every primary
stage still uses the frozen grid. `pytest tests/` 359 passed, 1 skipped.

### Round 2 — S1 determinism, runtime, memory (§15)

`R2_S1_DETERMINISM.md` + `R2_S1_results.json`. Frozen Round-1 protocol, unchanged:
same four frames (`wreck_07/f000105`, `wreck_05/f000109`, `cenote_01/f000193`,
`wreck_01/f001845` — the portrait trap), three within-process repeats plus an
independent fresh process, compared on `canonical_range` where emitted and on the
native field otherwise.

Both runnable challengers are **bitwise reproducible within and across processes**,
`p99_rel = 0.000e+00`, valid masks identical, on all four frames — matching all
seven Round-1 arms. MoGe-3 Step 0: 4.10 s/frame median (4.05–4.86), 9.1 s load,
3.06 GB peak RSS, source grid 1280×720 with its own deterministic mask (coverage
0.913/0.767/1.000/1.000). MDA: 2.82 s/frame (1.80–3.30), 14.6 s load, **10.35 GB
peak RSS** — the largest footprint of any arm run in this project, above both
ViT-G-class multi-view models, while predicting on the *smallest* grid (504×280).
MDA's §12 mixture record (component depths, probabilities, chosen component,
entropy, margin) reproduces bitwise with the depth; per §12 that is not called
calibrated confidence.

MoGe-3 Step 0 is the slowest arm in the bakeoff (2.0× MoGe-2, 14× DA v2) while
doing strictly less work than its released configuration — Step 3 adds to that.

Four arms never reached S1, recorded rather than omitted: `pointdit_l512`
`pending_checkpoint` (released checkpoint ships without the gated DINOv3 encoder)
— which **blocks** §15's explicit requirement to test the single-step all-zero path
directly, the one place a nonzero floor was plausible; `hyden_mogev2_metric`
`pending_checkpoint` (gated repo, 401); `surge_large` `pending_cuda` (NATTEN 0.21.6
refuses MPS and refuses compiled flex on two gates; the sanctioned CPU path needed
~138 GB and was OS-killed at 931 s); `moge3_vitl` Step 3 `pending_cuda` (Triton has
no macOS distribution). `pxdepth` S1 is queued behind its own 288-frame CPU
inference rather than run concurrently. §19 must report these as *untested*, not
eliminated.

### Round 2 — S4 appearance invariance, recomputed after Parts A–D (§20)

`R2_S4_APPEARANCE.md` + `R2_S4_results.json`. Part D's grid-map defect and Part A's
z-vs-range repair are both **post-inference**, so the 23 712 persisted perturbed
prediction files were reused and only the *analysis* re-run against
`R2_S3_policy.json` — 4 992 inferences avoided. The two network-grid arms
(`mapanything_n1`, `wat3r_n1`) come back numerically identical to Round 1, the
predicted control; only `metricanything_pointmap` (0.0187 → 0.0204 local Δlog) and
`da3mono_large` (0.0122 → 0.0128) move. The corrections are small here and were
large in S3 because S4 compares a model to itself, so a systematic mis-sampling
cancels on both sides.

Median over six clips and twelve perturbations, local range deformation in physical
range / wander / max |log σ|: `da3mono_large` **0.0128 / 1.044 / 0.110**;
`mapanything_n1` 0.0200 / 1.196 / **0.348**; `metricanything_pointmap` 0.0204 /
1.202 / 0.263; `wat3r_n1` 0.0257 / **1.061 / 0.054**.

- **Every arm reads veiling as a depth cue.** `cue_conflict_inverted_veil` vs its
  same-magnitude `veil_depth_consistent` control: 4.1× worse for `da3mono_large`,
  2.4× MapAnything, 1.9× `wat3r_n1`, 1.3× `metricanything_pointmap`. The reference
  builds the stimulus and never reaches the model.
- **MapAnything's metric scale is set by appearance.** A uniform veil carrying no
  depth information multiplies its clip range by 1.416 median, **2.465** worst clip;
  scale swings ±40 % across the battery vs 5 % for `wat3r_n1`. Pre-C2 this does not
  say the scale is wrong — it says appearance sets it, which is the property C2 must
  measure and the one a reference derived from the same model cannot check.
- **`channel_neutralize` — the project's own gray-world baseline — is MapAnything's
  worst ordinary perturbation** (0.0619, wander 1.616). White-balancing before
  estimating geometry moves the geometry. Carried to §22/§27 as a pipeline-ordering
  question, not a model verdict.
- Corrected `da3mono_large` is the most appearance-stable arm on ordinary change
  (best on 8/12) *and* the most fooled by cue conflict (0.1205) — the same fact
  about a strongly appearance-driven prior, coherent with its §18 lattice result.
- S3 and S4 order the field oppositely, which is why §17 forbids a weighted score.

Covers 4 arms only; `moge2_vitl` and the challengers have no perturbation set and
are generated after the §19 reduction decides survivors (1 248 inferences per arm).

## Round 2 — PXDepth (R2-4) through S2/S3/S5, and one repo defect (§10, §16, §17, §21)

PXDepth completes the set of Round-2 challengers that produced primary results:
three of six (`moge3_vitl` Step 0, `mda_mog_sky_l2`, `pxdepth`); the other three
remain `pending_cuda` / `pending_checkpoint`, recorded not failed.

**Execution.** 288 frames, CPU, 22.25–23.68 s/frame, 6 847 s total, peak RSS
5.68 GB — the slowest arm in Round 2 by an order of magnitude. Implementation
**category B**, and the adaptation is the largest of any arm, so it is
enumerated: the released `scripts/infer.py` is broken as published (line 74
imports three names from `pxdepth.inference`, a module that does not exist), so
the *entry script* was reimplemented around the unmodified model at the repo's
**own** documented policy — `--input-size 1022×770`, `--resize-by-area`,
source aspect preserved. Model math, checkpoint, operators, resolution
unchanged. **Licence UNDECLARED** → research-only; none was inferred. The
released repo's MoGe-2-assisted metric path is inadmissible for the primary
comparison per §10 and **was never run** — no helper model's scale enters any
number.

**S2.** Native `log1p_depth_affine_invariant`, family `affine_log1p_depth`,
convention **`z_depth` from source code** (`scripts/infer.py:121` back-projects
with `utils3d.pt.depth_map_to_point_map`, which multiplies unnormalised `K^-1`
rays by the scalar). The residual test disagreed again — pooled `range` at a
margin ratio of 1.0031, and three different answers across six clips of one
camera. Source wins per §14; that is now the third arm where it has, and the
residual instrument keeps failing the same way.

**S3** (median over six clips): M-1 0.1589, M-2 b 0.746, M-3 rel 15.42°,
M-4 **0.0221** — better boundary placement than corrected DA3 (0.0285) and
MoGe-2 (0.0320), which is what a structure-preserving pixel-space method is
supposed to buy — M-5@0.25 0.0035, M-6 1.097, coverage 0.765.

**One clip carries almost all of its bad numbers, and it is a sign inversion.**
The frozen `cenote_01` fit came out at **s = −0.2701** against +1.72…+1.93 on
three others. Before reporting that, the raw pre-alignment order agreement was
measured directly — per-frame Spearman between the untouched native field and
the reference, which no monotone gauge can move: **−0.298 median on `cenote_01`,
negative on 79 % of frames, sign flipping between −0.871 and +0.811**, against
+0.938…+0.996 on the other five through the identical code path and grid map.
Not a harness defect. Pre-C2 the disagreement itself cannot be attributed — a
cave interior is where a multi-view product is weakest — but the frame-to-frame
*sign flip* is not something a multi-view product over a continuous shot can do,
so the instability is PXDepth's. Excluding that clip, M-6 goes to **1.000** and
M-2 to 0.781; both rows are reported and the six-clip row is the frozen result.
`wreck_01`'s small fit (`s` = +0.274) is by contrast correct, not degraded: its
rank agreement is the highest of the six (+0.996) and the reference's own log1p
spread there is only 0.35.

**S5.** Median over clips f2f 0.0596 / wander 3.338 / **local Δlog 0.0151** /
local p95 **0.0308** / nf_wander **1.390** — second-best local surface and best
near/far stability of ten arms. And `cenote_01` collapses: wander **65.9**, f2f
**1.954** (×7 between adjacent frames), six times MDA's worst clip, the largest
single-clip failure in the stage. Under FREEZE C7 that is the disqualifying
frame-varying kind. Same clip, same mechanism, two stages.

**Repo defect found and fixed** — `s2_freeze_policy.py` crashed with
`KeyError: 'fg_pre_ray'` in MD generation whenever a FoundationGeo ablation arm
was present, *after* `pol.save()` had already written the policy, so a partial
success looked like a total failure. Added an `ev_of()` helper that lets an
ablation arm report its primary arm's evidence. Tests 359 passed, 1 skipped.

**Near-miss worth recording.** Extending the frozen policy by *rebuilding* it
silently dropped the two Part-A/B-repaired arms (the Round-1 raw still carries
pre-repair records) and moved two challengers; the crash above meant the
equivalence guard never ran. Recovered from a backup. **A frozen policy is
extended, never re-derived** — PXDepth was frozen alone through the same code
path and *inserted*, with an assertion that every other arm stayed
byte-identical.

**Comparability defect recorded, no primary metric affected.**
`Alignment.log_residual_mad` is measured in each family's own fitting space. For
`scale`/`affine_depth`/`affine_disparity` that is the spread of the log range
ratio, so the S2 column is comparable; for `affine_log1p_depth` it is the spread
of `log(log1p(z)/fitted)` — the log *of* a log1p — systematically smaller.
Reporting PXDepth's stored 0.0581 next to MapAnything's 0.1021 would have been a
units error, and would have put PXDepth top of the table. Recomputed as the
pooled log-range residual it is **0.1618**, between corrected DA3 and MoGe-3.
The caveat is now in `alignment.py`'s docstring so it cannot recur silently.

**§18 provisional entry confirmed, not assumed.** The thin-structure stage ran
before PXDepth's S2 finished. The frozen `wreck_07` clip fit came out identical
to the provisional one to machine precision, so no §18 number changes;
`provisional_policy` is now `false` in the JSON.

Artifacts: `R2_S2_ALIGNMENT.md`, `R2_S3_LOCAL_GEOMETRY.md`, `R2_S5_TEMPORAL.md`,
`R2_S3_results.json`, `R2_S5_results.json`,
`outputs/r2_s3/r2_pxdepth_rank_diagnostic.json`,
`outputs/r2_s2/r2_pxdepth_comparable_e1.json`.

## Round 2 — S4 for `dav2_small`, and the §19 decision it settles (§20, §19)

`R2_S19_REDUCTION.md` withdrew `dav2_small`'s Round-1 elimination — the numbers it
was eliminated on were the Part D grid defect, not the model — and sent it to S4,
the one stage it had never been measured on, with the decision explicitly deferred
to the measurement. This entry records the measurement and the decision.

**Inference.** `s4_run --model dav2_small --skip-existing` in `.venv-mono`: 78
(arm, clip) products = 13 conditions × 6 clips × 16-frame window = 1 248 inferences,
312 s (0.250 s/frame), peak RSS 0.69 GB. The only S4 inference run in Round 2;
every other arm in the stage is re-analysis of Round-1 predictions against the
corrected policy.

**Analysis.** `s4_analysis --models dav2_small --policy round2/R2_S3_policy.json`
into a *separate* raw, `round2/outputs/s4/r2_s4_dav2_small.json`, then inserted into
the frozen `R2_S4_results.json` by a guarded merge that asserts the arm is absent and
that the perturbation battery and window match. Extend, never rebuild — the same
discipline adopted after the `R2_S3_policy.json` near-miss. `dav2_small` appears in
`corrected` and deliberately **not** in `old`: Round 1 never ran S4 for it, so there
is no prior value to correct and inventing one would be a fabrication.

**Result.** Median local deformation in physical range 0.0181 — 2nd of 5, between
corrected `da3mono_large` (0.0128) and `mapanything_n1` (0.0200). Lowest p95 in the
field (0.0597), second-lowest worst case (0.0678). `max |log σ| = 0.073` against the
incumbent's 0.348 on identical stimuli; under `veil_uniform`, which multiplies
MapAnything's whole clip by 1.416, its delivered range moves by 0.985. On
`channel_neutralize` — the project's own gray-world baseline — 0.0224 deformation and
wander 1.085, against MapAnything's 0.0619 and 1.616.

Three things were written down as qualifications rather than left implicit:

- **σ is not the same claim for the two arms.** MapAnything's σ is a change in its
  own metric assertion; DA v2 asserts no metric scale, so its σ measures whether a
  frozen affine gauge still delivers the same ranges when the water changes. Useful,
  and not evidence that DA v2 knows the scale.
- **Where the frozen gauge does fail is offset-dominated clips.** `cenote_01` and
  `wreck_01` have `t/s` 4.93 and 3.50 against 1.18–1.37 elsewhere, and they are the
  two clips with wander 2.73 and 2.39 under the veil family. Spearman over clips
  +0.83 / +0.71. Recorded as a **hypothesis, not a finding** — n = 6 clips, and
  `channel_neutralize` shows nothing.
- **The boundary-jitter metric reads 0.000 for four of five arms.** That is the
  metric saturating below one evaluation sample, not four arms with stable
  boundaries. Only MapAnything's number (up to 3.05 px) is a result.

**Decision: RETAINED, advances to S6 as the third arm.** Not on a claim of
superiority — its S3 M-1 is 0.109 against MapAnything's 0.085, and S4 measures a
model against itself, so an arm can be invariant about the wrong geometry. It is
retained because the elimination was invalid, because it is now the only arm besides
the two incumbents with a complete S2–S5 record, and because §18 shows it separating
open space from lattice members (`gap` +0.165) where MapAnything does not (+0.006) —
while separating far less than corrected DA3 (+0.411).

Artifacts: `round2/outputs/s4/r2_s4_dav2_small.json`, `round2/R2_S4_results.json`
(five arms), `round2/R2_S4_APPEARANCE.md` (F7–F9 added),
`round2/R2_S19_REDUCTION.md` §6.1.

## Round 2 — S6 restoration impact for the three surviving arms (§22)

Ran the §22 restoration-impact stage for `mapanything_n1`, the Part-A-CORRECTED
`da3mono_large` and `dav2_small`, entirely into Round-2 paths. Round-1's
`results/S6_RESTORATION.md` / `S6_results.json` are untouched.

**Two mechanical obstacles, both recorded because they will recur.**

1. `s6_report.py` hard-coded the Round-1 output paths, so running it would have
   silently overwritten the Round-1 report (CLAUDE.md invariant 7). Added `--out-md`
   and `--out-json`. It also hard-coded the Round-1 *narrative* — the inspection notes
   and the ADEQUATE/DEGRADED/UNSAFE classification are module constants written for
   two arms under the pre-repair DA3 convention, and they would have regenerated
   verbatim into the Round-2 file. Added `--stage-note`, `--inspection-notes` and
   `--classification` (file paths; the constants remain the documented Round-1
   defaults), and the arm/clip counts in the header are now computed. Round-2
   narrative lives in `round2/narrative/s6_{inspection_notes,classification}.md`, so
   the report is generated, never hand-edited. 359 passed, 1 skipped.
2. `s6_temporal` cannot run from `.venv-eval`: `huggingface_hub` is absent, and after
   installing it SEA-RAFT's `extractor.py` needs `torchvision`, which `.venv-eval`
   deliberately does not have. Rather than keep patching the eval venv, ran it from
   `experiments/week2a_flow/.venv-flow` — the project's own documented Phase-2A flow
   interpreter — with `PYTHONPATH=$PWD`. Verified programmatically that the resulting
   `backend` provenance dict is IDENTICAL to Round 1's (same repo commit
   9137517b, same checkpoint, same config, `modifications_to_third_party_code: none`),
   so the temporal rows are comparable across rounds.

**The control worked.** `mapanything_n1`'s Round-2 raw is bit-identical to Round 1's
on every clip and every water type — 0 differing scalars by direct comparison. Every
DA3 movement below is the convention repair and nothing else.

**Result on the criterion metric** (responsive-window median |relative radiance
error|, against the Week-3 budget of 5 %): `mapanything_n1` **0.104**, `dav2_small`
**0.134**, `da3mono_large` **0.162**. All three **DEGRADED**; none ADEQUATE. The
temporal metric orders them the other way (windowed colour-pumping medians 0.906 /
0.492 / 0.336), and pre-C2 that split is not resolvable — there is no anchor that says
whether static agreement with a MapAnything-derived reference or temporal steadiness is
the better evidence. One arm/clip combination meets the 5 % budget: MapAnything on
`wreck_07` at 3.9 %.

**Round 1's "DA3 approaching UNSAFE" is WITHDRAWN.** It rested entirely on `wreck_05`,
which the repair moves from 33.3 % radiance error / windowed ΔE00 7.78 / p95 16.1 to
15.5 % / 7.05 / 14.9. Reported straight because it cuts both ways: the repair
*redistributed* rather than improved. OLD → CORRECTED windowed radiance error —
wreck_07 0.134→0.168, wreck_05 0.333→0.155, cenote_01 0.064→0.072, swimthrough_02
0.092→0.097, wreck_01 0.224→0.222, wreck_03 0.089→0.204; median 0.113→**0.162**. DA3's
corrected median is worse than its uncorrected median while its worst case is far
better. The corrected numbers are the valid ones — the old fit was absorbing the
z-vs-range convention error into `s` and `t` — but "the repair helped DA3" is not what
the data says.

**Two Round-1 scene-identity charges against DA3 do not survive the mandatory visual
inspection (invariant 5).**

- **RETRACTED: the crane-lattice fill.** §18's corrected measurement gives DA3
  `fill` **+0.056** against the reference's own +0.054 and MapAnything's +0.049; the
  arms that actually fill are `moge2_vitl` (+0.291) and `wat3r_n1` (+0.239), neither
  in this run. The sheet shows why the Round-1 reading went wrong: the lattice is
  BLACK in all four range panels including the reference's — those pixels have no
  multi-view support, sit outside the common support, and are excluded from every S6
  number. Round 1 mistook the reference's missing data for resolved open water. S6
  masks to the reference and therefore *cannot see* through-lattice behaviour at all;
  §18 is the only measurement in this round that can.
- **The `wreck_03` diver displacement is confirmed but NOT unique to DA3** —
  `dav2_small` displaces it the same way with the same sign. With a second monocular
  arm in the run it reads as strict-single-image geometry mishandling an
  independently moving subject, and MapAnything's clean body is partly circular.

Two further findings from the sheets. `wreck_05` is a **shared** failure: both
monocular arms replace the reference's near-flat lateral field with a smooth
corner-to-corner ramp and both restore it visibly cyan, while the metrics rank them
in opposite directions (DA3 worse ΔE00 7.05 vs 4.79, dav2 worse radiance 0.213 vs
0.155). And on `wreck_01` MapAnything's residual is a spatially uniform single-signed
field *after* a clip-level gauge fit — so it is the frame-varying part of the scale,
not FREEZE C7's benign constant, which Round 1 called it; its windowed colour pumping
on that clip is 1.11 against 0.38 and 0.53.

`turbid_coastal` remains unmeasurable on this footage (all channels floored on four of
six clips under DA3, three under dav2, two under MapAnything) and its rows must not be
used. Every arm including the reference makes the footage temporally worse than its own
unprocessed input at lag 1 on five of six clips — the temporal rows are
arm-vs-reference comparisons, never arm-vs-nothing.

Reproduce:

```
experiments/week4_mono/.venv-eval/bin/python -m experiments.week4_mono.round1.scripts.s6_restoration \
  --arms mapanything_n1 da3mono_large dav2_small \
  --policy experiments/week4_mono/round2/R2_S3_policy.json --sweep-water \
  --out-root experiments/week4_mono/round2/outputs/s6
PYTHONPATH=$PWD experiments/week2a_flow/.venv-flow/bin/python -m experiments.week4_mono.round1.scripts.s6_temporal \
  --arms mapanything_n1 da3mono_large dav2_small \
  --restored-root experiments/week4_mono/round2/outputs/s6/restored \
  --out experiments/week4_mono/round2/outputs/s6/s6_temporal.json
experiments/week4_mono/.venv-eval/bin/python experiments/week4_mono/round1/scripts/s6_report.py \
  --raw  experiments/week4_mono/round2/outputs/s6/s6_raw.json \
  --temporal experiments/week4_mono/round2/outputs/s6/s6_temporal.json \
  --inspect  experiments/week4_mono/round2/outputs/s6/inspect/manifest.json \
  --out-md   experiments/week4_mono/round2/R2_S6_RESTORATION.md \
  --out-json experiments/week4_mono/round2/R2_S6_results.json \
  --stage-note "..." \
  --inspection-notes experiments/week4_mono/round2/narrative/s6_inspection_notes.md \
  --classification   experiments/week4_mono/round2/narrative/s6_classification.md --overwrite
```

Artifacts: `round2/outputs/s6/` (`s6_raw.json`, `restored/` 1.5 GB, `s6_temporal.json`,
`inspect/` 18 sheets + 216 crops), `round2/R2_S6_RESTORATION.md`,
`round2/R2_S6_results.json`, `round2/narrative/s6_*.md`.

## Round 2 — late-found S3 convention defect, and its bounded repair

Found while assembling the final report, not by a test. `round2/R2_S3_results.json`
labelled its `da3mono_large` row "incumbent I2 (CORRECTED)" while printing numbers
byte-identical to the committed Round-1 `results/S3_results.json`.

Root cause: the S3 summariser sources incumbent rows from
`experiments/week4_mono/round1/results/S3_results.json`. That file was regenerated for the
Part D grid repair, but under the **Round-1** policy `results/S2_alignment_policy.json`,
where `da3mono_large` and `dav2_small` still carry
`convention: "range", convention_source: "MEASURED in S2"`. The §3/§4 convention repair
— DA3's scalar is projective z-depth, established from `P = t + D·R·K^-1 p`, not from a
residual — lives in `round2/R2_S3_policy.json`
(`convention: "z_depth", convention_source: "SOURCE CODE (Round-2 Part A/B repair)"`).
Every stage that reads the R2 policy got the repair; the S3 *summary* did not.

Confirmed three ways before touching anything: the stored DA3 row equals
`git show HEAD:experiments/week4_mono/round1/results/S3_results.json`'s DA3 row exactly; the
two policy files differ only for those two arms and only in `('range' → 'z_depth')`;
re-running the stage under the frozen R2 policy reproduces the
`R2_PARTS_ABC_CORRECTNESS.md` §A3 table to four decimals.

**Blast radius is S3 only.** §18 (`R2_thin_structure_results.json`, DA3 alignment
`s=5.9868, t=5.5356`), S5 (`outputs/r2_s5/r2_s5_raw.json`), S4 and S6 all store the
corrected parameters — verified by reading each stage's persisted alignment, not
assumed.

| | M-1 | M-2 b | M-3 rel° | M-3 abs° | M-4 | M-5@.25 | M-6 | coverage |
|---|---|---|---|---|---|---|---|---|
| `da3mono_large` | 0.1283 → **0.1476** | 0.846 → 0.856 | 12.77 → 13.35 | 20.58 → **19.54** | 0.0285 → **0.0223** | 0.0037 → 0.0062 | 1.014 → 1.136 | 0.808 (same) |
| `dav2_small` | 0.1092 → 0.1094 | 0.908 → 0.994 | 12.72 → 12.65 | 20.77 → **18.64** | 0.0167 → 0.0164 | 0.0057 → 0.0052 | 0.939 → 1.013 | 0.761 (same) |

DA v2 barely moves (its native disparity already inverted to something close to
z-depth); DA3 moves materially and, as in Part A, *both ways* — worse agreement in the
mean, better boundaries and better absolute normals.

Two downstream statements changed, both re-checked rather than assumed:
`R2_S19_REDUCTION.md`'s incumbent bar (0.1283 → 0.1476; the conclusion that no
challenger clears both incumbents survives) and the PXDepth finding that its
"boundary placement (M-4 0.0221) is better than corrected DA3 (0.0285)" — at the true
0.0223 that is a **tie**, and it is now stated as one. The MoGe-3 non-domination
argument keeps its direction with narrower margins.

Applied as an extend-never-rebuild patch that asserts the other ten arms are
byte-identical before and after; recompute persisted at
`round2/outputs/r2_s3/r2_s3_convention_fix.json`. Round-1's `results/` artifacts are
deliberately untouched — they are the Round-1 record under the Round-1 policy.

Reproduce:

```
experiments/week4_mono/.venv-eval/bin/python -m experiments.week4_mono.round1.scripts.s3_local_geometry \
  --arms da3mono_large dav2_small \
  --policy experiments/week4_mono/round2/R2_S3_policy.json \
  --out experiments/week4_mono/round2/outputs/r2_s3/r2_s3_convention_fix.json
```

## Week 4A — post-Round-2 final report (§26, §27)

`experiments/week4_mono/round2/WEEK4A_POST_R2_FINAL.md`. Synthesis only — no new
inference, no new stage. Every number in it is quoted from a persisted stage summary
and was re-checked against that summary rather than from memory.

**§26 correctness repairs.** Five asked, six answered; the sixth is the late S3
convention defect above, recorded because §28 stop-condition 4 requires a newly found
correctness defect to be reported even when it does not invalidate the comparison.
The DA3 z-depth repair is written as a **redistribution** — S3 M-1 0.1283 → 0.1476
and S6 median 0.113 → 0.162 both worse, M-4 0.0285 → 0.0223 and `wreck_05` S6
0.333 → 0.155 both much better — not as an improvement, because that is what the data
says. Two Round-1 verdicts are withdrawn on its strength ("DA3 fills the crane
lattice", "DA3 approaching UNSAFE"). DA v2's elimination answer is **No**: Part B
confirmed it and Part D then invalidated the numbers Part B confirmed it on.
FoundationGeo's ray correction turns rays by median 0.044° and changes range by
2.3e-07 relative — inert; its scale field is a near-uniform 0.840 that S2 refits away
while costing 9.5 %/13.7 % on relative/absolute normals.

**§26 mechanism questions.** Answered: PXDepth (partly — boundaries tie corrected
DA3, thin structure `gap` +0.240 loses to it) and MDA (no to both halves — the
solid-fill premise was our own artefact, and the mixture does not commit: 67–85 % of
pixels take a pairwise midpoint, entropy-vs-M-1 Spearman −0.222 with the sign
flipping clip to clip). Unanswerable and recorded as such: MoGe-3 Step 3
(`pending_cuda`, Triton has no macOS distribution), HyDen and PointDiT
(`pending_checkpoint`), SurGe (`pending_cuda`, measured at 148.5 GB peak on a 24 GB
machine). SurGe is the one that matters most — it was the designed falsification
target for the local-surface hypothesis, so that hypothesis stands untested.

**FINAL PRE-C2 FINALISTS: 3** — `mapanything_n1`, corrected `da3mono_large`,
`dav2_small`. Each is non-dominated on an axis where neither other is at least as
good (native metric + best reference agreement + best S6; thin structure + local
temporal stability + ordinary-perturbation invariance; cost + gauge steadiness +
better S6 than DA3), and the report states for each the exact C2 measurement that
would remove it. `moge2_vitl` is dropped — its §18 `gap` is confounded with
far-field expansion (`r_sea` 175 m) and it never earned an S6 run.

**§27 verdict: DEGRADED.** Not ADEQUATE — exactly one arm/clip pair in the study
meets the Week-3 budget (`mapanything_n1` on `wreck_07`, 3.9 %) against medians of
10.4 / 13.4 / 16.2 %. Not UNSAFE for the retained set — bounded, attributable,
sign-stable — but UNSAFE behaviour exists in the class and the finalist set is what
excludes it: PXDepth's reference-independent rank inversion with a frame-to-frame
sign flip on `cenote_01`, and MDA's ~19 %-per-frame scale drift.

Seven C2 measurements are specified, led by **absolute range under ≥3 distinct
visibility conditions on the same scene** — required by S4 F2, where a veil carrying
no range information multiplies MapAnything's clip scale by up to 2.465×, so a scale
validated on one clean clip would be a scale that appearance happened to set. No
further model search is recommended and §23's Round-2B set stays unrun; the next
model-side effort belongs to the three challengers that were blocked, each of which
needs exactly one thing.

Baseline safety check unchanged: `uw score data/testset/murky/MURKYSHARK.MP4` runs
clean at 292 frames with out-of-range 0.0000, the deprecated Week-1 pin still returns
`3.244860636186786e-05` bit-for-bit, and `pytest tests/` is 359 passed, 1 skipped.

**S1 gap closed after the fact.** PXDepth's determinism had been recorded as `queued`
— it runs on CPU and its S1 was deliberately held behind its own 288-frame S3
inference so the two runtime measurements would not corrupt each other, and the queue
was never drained. §26 asks for determinism per challenger, so it was run: **bitwise
reproducible**, p99 relative floor `0.0e+00`, within and across processes, identical
valid masks on all four subset frames, median **16.45 s/frame** (min–max 15.40–17.09),
load 3.9 s, peak RSS 5.69 GB, torch 2.11.0 on CPU. The S3 stage's 22.25–23.68 s/frame
remains the figure to quote for S3 — it was measured under that stage's own load —
and the difference is machine contention, not a model difference. All three runnable
Round-2 challengers are now measured and all three are bitwise deterministic, so no
Round-2 difference is at risk of being instrument noise. `R2_S1_DETERMINISM.md`,
`R2_S1_results.json` (the arm moved out of `pending`) and the final report updated.
