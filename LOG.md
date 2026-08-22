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
