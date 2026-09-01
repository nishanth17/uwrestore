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
method was run (`experiments/week3_geometry/configs/phase3a_clips.json`):
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
