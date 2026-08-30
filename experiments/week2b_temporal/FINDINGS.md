# Week 2 Phase 2B — motion-aware temporal metric: findings

**Status: the instrument is built and validated; no temporal correction
exists and none was added.** `uw score --temporal` reports raw MC-Warp@1/4/8,
a canonical illumination-aware MC-Warp@1/4/8, the uncompensated residual, the
motion-reduction ratio, valid coverage, flow-aligned temporal ΔE00 and a
separately-named alignment-robust companion — never a single combined score.

Week 1's `temporal_stability()` placeholder is deprecated and no longer
reported.

---

## 1. What was built

| file | status | what |
|---|---|---|
| `uw/metrics.py` | **permanent** | the whole temporal metric: `temporal_warp_error`, `alignment_robust_warp_error`, `fit_illumination` / `apply_illumination`, `temporal_delta_e`, `warp_with_support`, `evaluate_temporal_pair`, `evaluate_temporal`, and the `IlluminationFit` / `TemporalLagMetrics` / `TemporalMetrics` results. numpy + opencv only; **imports no flow model** |
| `uw/searaft.py` | **permanent** | SEA-RAFT-M behind `uw.flow.OpticalFlowBackend`, torch imported lazily inside `__init__` |
| `uw/waft.py` | **permanent** | WAFT-a1, the optional manual cross-check. Not a default, not run automatically, not averaged with SEA-RAFT |
| `uw/flow.py` | modified | gained `model_input_srgb_u8` (one definition of the model-input view, now shared by two wrappers) and `isolated_repo_imports` |
| `uw/cli.py` | modified | `uw score --temporal`, the report layout, `--method none`, `--start/--frames`, `--alignment-robust`, `--json` |
| `uw/io.py` | modified | `load(..., start=, count=)` — a bounded decode, because a 756-frame 1080p clip in float32 is ~18 GB and a temporal metric only needs a window |
| `tests/test_temporal.py` | permanent | 52 synthetic validation tests against an analytic flow backend, in the ordinary venv |
| `tests/test_backends.py` | permanent | 16 tests of the wrappers' plumbing, no torch needed |
| `experiments/week2b_temporal/**` | exploratory | four run scripts and this document |

`uw/types.py`, `uw/colorspace.py`, `uw/baselines.py`, `CLAUDE.md` and
`pyproject.toml` are unchanged. The core venv still has only numpy + opencv.

---

## 2. Backend integration

**SEA-RAFT-M**, promoted from `experiments/week2a_flow/backends/` into
`uw/searaft.py`. Selection was closed in Phase 2A and was not reopened.

| | |
|---|---|
| repository | princeton-vl/SEA-RAFT @ `9137517ba24e628442aec097d3afe71d03503b75` (BSD-3-Clause), unedited |
| checkpoint | HuggingFace `MemorySlices/Tartan-C-T-TSKH-spring540x960-M` |
| config | `config/eval/spring-M.json` with `scale = 0` — the single documented deviation, unchanged from Phase 2A |
| device | MPS (Apple M4, 24 GB), torch 2.13.0, Python 3.13.5 |
| runtime | **0.711 s median** per inference over the 90 inferences of the real-footage sweep (mean 0.711, p95 0.749, max 0.794) |
| peak MPS driver allocation | 2.42 GB with two model instances loaded; Phase 2A measured 2.2 GB for one |
| determinism | bitwise-identical flow over three repeat calls, and at direct lag 3 |

**The promoted wrapper is bitwise identical to the Phase 2A one** — checked
directly (`np.array_equal` on the returned flow, max abs diff 0.0), so no
Phase 2A conclusion is invalidated by the move.

**Dependency handling.** `pyproject.toml` is untouched. `uw/metrics.py`
receives an already-constructed `OpticalFlowBackend` and never imports a
model, so importing the metric costs nothing. Temporal scoring runs from the
isolated Phase 2A interpreter (`experiments/week2a_flow/.venv-flow`), which
already carries numpy, opencv and torch; `python -m uw.cli` works there
unmodified. Asking for `--temporal` in the core venv fails with an
`ImportError` naming the interpreter to use. WAFT, FlowIt and VideoFlow-MOF
were **not** promoted and are not reachable from `uw/`.

**Known correspondence limitation, carried forward deliberately.** SEA-RAFT
invalidates smooth, low-texture, independently moving subjects as solid
blobs. `outputs/temporal_metric/gray_world/murky_eel/lag8_pair_652_660/valid_mask.png`
shows the entire eel body cut out. The animal a restoration is most likely to
damage is the part of the frame the metric does not measure. This is the
concrete reason coverage is a first-class part of every result.

### Convention re-verified after promotion

`scripts/searaft_check.py` rebuilds Phase 2A's known-motion test against the
promoted wrapper: five crops of one real 1080p frame, content moving
(+12, −5) px per frame at source scale, i.e. (+6.400, −2.667) px on the
960×540 metric grid.

| | @1 (direct) | @2 (direct) |
|---|---|---|
| measured mean flow | (+6.399, −2.664) | (+12.799, −5.332) |
| endpoint error | **0.0131 px** | **0.0137 px** |
| …if the channels were swapped | 12.82 px | 25.64 px |
| raw MC-Warp | 0.013306 | 0.011572 |
| …if the flow were negated | 0.104778 | 0.122711 |
| uncompensated | 0.094300 | 0.108645 |
| FB-valid coverage | 98.7 % | 97.5 % |

**A first draft of this test had the ground-truth sign backwards** (the crop
origin moves opposite to the content) and reported an EPE of 13.86 px. The
metric was right and the test was wrong: MC-Warp already read 0.0134 with the
model's flow against 0.1046 with it negated, a 7.8× separation that said the
direction was correct before the endpoint error was fixed. Recorded because
the counterfactual is what caught it.

---

## 2b. WAFT-a1 as an optional cross-check

Promoted alongside SEA-RAFT so a second opinion is one command away rather
than only reachable from the experiments tree. PLAN.md's rule: *"retained as a
periodic cross-check, not a default. Where the two disagree materially, treat
that clip's MC-Warp as low-confidence."*

WAFT-a1, princeton-vl/WAFT @ `b152ff1`, checkpoint `tar-c-t.pth`,
`config/a1/tar-c-t.json` **unmodified** — it is already `scale: 0`, so unlike
SEA-RAFT this backend needed no config change at all. ~1.7-3.0 s/inference
against SEA-RAFT's 0.71, same memory class; 3.48 GB peak MPS with both models
resident. Deterministic on repeat calls, and constructing it does not perturb
an already-constructed SEA-RAFT (verified bitwise).

**One thing Phase 2A could not have found**, because it ran one backend per
process: SEA-RAFT and WAFT both ship top-level `config/`, `model/` and
`utils/` packages. With SEA-RAFT's `core/` on `sys.path` first, WAFT's
`from utils.utils import Padder` resolves to SEA-RAFT's `core/utils/utils.py`
and raises `ImportError`. Both wrappers therefore import inside
`uw.flow.isolated_repo_imports`, which restores `sys.path` and evicts from
`sys.modules` exactly those modules loaded from the given checkout — and
nothing else, since evicting a torch submodule would make a later import build
duplicate classes and silently break `isinstance`.

### Comparison is only ever on the intersection of the two masks

`compare_backends_common_mask`, and `uw crosscheck` over it, is the promoted
form of Phase 2A's `scripts/common_mask_compare.py`. It takes only the
ORIGINAL sequence — this is a correspondence question and no corrected output
takes part. Four inferences per (anchor, lag), nothing retained beyond each
cell's scalars, a 0.5 % tie band, and a **tally of cells rather than an
aggregate score**.

`swimthrough`, 41-frame window at 181-221, anchors 16/18/20:

| lag | common | disputed | searaft cov | waft cov | searaft red | waft red | winner |
|---|---|---|---|---|---|---|---|
| @1 | 96.9 % | 0.3 % | 97.0 % | 97.0 % | **4.338** | 4.298 | searaft |
| @4 | 88.3 % | 0.4 % | 88.4 % | 88.6 % | **5.357** | 5.150 | searaft |
| @8 | 76.8 % | 0.7 % | 77.0 % | 77.4 % | **5.671** | 5.187 | searaft |

Phase 2A's headline cell was `swimthrough @8`, 5.615 vs 5.043 (11 %), measured
on a single anchor. Pooling three anchors gives 5.671 vs 5.187 (9.3 %) — the
same result at the same magnitude.

`murky_shark`, where Phase 2A recorded WAFT's only win:

| lag | common | searaft cov | waft cov | searaft red | waft red | winner |
|---|---|---|---|---|---|---|
| @1 | 93.4 % | 96.3 % | 96.1 % | 1.374 | 1.368 | **tie** |
| @4 | 90.8 % | 90.9 % | **97.8 %** | 2.331 | 2.340 | **tie** |
| @8 | 89.6 % | 89.7 % | **96.8 %** | 2.458 | 2.469 | **tie** |

This is the point of the whole apparatus in one table. WAFT measures **7 points
more of the frame** at @4 and @8 — a large advantage on its own mask — and on
the pixels both accept, the two are indistinguishable. Phase 2A §A6's
conclusion, that WAFT's advantage is about how much frame you get to measure
rather than how good the correspondence is, is now reproducible in one command.

Cross-backend flow disagreement is reported beside each verdict and grows with
lag: on `swimthrough`, median 0.145 / 0.427 / 0.971 px at @1/@4/@8 overall,
and 0.770 / 2.265 / 4.569 px inside the band where the two masks disagree.
Where the masks disagree, so does the flow, by 3-5x. **No threshold for
"materially" is hard-coded**: what counts as material depends on the clip's own
motion magnitude (Phase 2A: ~0.8 % of motion on `murky_eel`, ~22 % on
`murky_shark`), and a number tuned against the frozen clips is exactly what
PLAN.md forbids. The command prints the disagreement and the rule; the
judgement stays with the reader.

## 3. Raw MC-Warp

For a pair (t, t+k) with the **direct** flow t → t+k:

```
warped   = W(I_{t+k}, flow)                     # cv2.remap, bilinear
M        = FB-valid  &  warp-supported  &  finite
MC-Warp  = (1/|M|) * sum_{p in M} (1/3) * sum_c | warped(p)_c - I_t(p)_c |
```

* **Linear-light RGB throughout.** The sRGB view SEA-RAFT needs for its own
  input is built inside the backend, never written back into a `Frame`, and
  never reaches a residual. Pinned by a test: scaling both sequences by 0.4
  scales every photometric residual by exactly 0.4, which no gamma-domain or
  clipping metric could do.
* **L1**, not L2 / Charbonnier / SSIM / census / LPIPS. It stays in the units
  of the image, so the number reads as "mean linear-light difference per
  channel" and is directly comparable to Phase 2A's warp MAE; it is far less
  dominated by the handful of pixels (bubbles, marine snow, a thin rope, an
  occlusion edge) that Phase 2A showed dominate an underwater residual; and
  Charbonnier's only advantage over L1 — differentiability at zero — is
  irrelevant to a measurement.
* **Nothing is clipped.** gray-world produces linear values well above 1.0
  and the metric measures them as they are (tested).
* **Non-finite values are excluded explicitly**, never replaced: a NaN pixel
  is zeroed before resampling and its whole bilinear 2×2 support is marked
  unusable, so it can neither poison a neighbour nor be interpolated over.
* **Direction:** `warped` is "frame t+k as it would look if nothing had
  moved", compared against frame t on frame t's grid.
* **Empty mask returns `None`, not 0** — undefined is not the same as zero,
  and low coverage is not the same as either.

### Warping correctness

`cv2.remap` with absolute source-coordinate maps `map_x = x + u`,
`map_y = y + v` derived from the normative `(u, v)` convention, bilinear,
`BORDER_CONSTANT`. Tests assert, by intercepting the call, that the maps are
`float32`, C-contiguous, correctly shaped and equal to the absolute grid;
and that a sign flip, an x/y swap or a one-pixel offset each raise the
residual by 5–20× on real texture. `resize_flow` rescaling is re-checked.
Validity comes from explicit correspondence and support logic, never from a
warped pixel looking plausible.

---

## 4. Canonical illumination-aware MC-Warp

One bounded formulation, used as the regression metric:

```
                     fitted on ALIGNED ORIGINAL frames only
Y_t  ≈  gain * Y_W(t+k)  +  bias            (Y = linear relative luminance)
                     |
                     v  freeze
illum-aware MC-Warp  =  L1( C_t ,  gain * W(C_{t+k}) + bias )
```

**Model: one scalar gain and one scalar bias on linear luminance, applied
identically to R, G and B.** It is the lowest-capacity form that represents
the legitimate variation this footage actually contains — auto-exposure
steps, whole-scene ambient change — and, more importantly, the lowest-capacity
form that is *structurally incapable* of absorbing the failure the metric
exists to catch. A scalar applied to all channels cannot represent a red-only
change at all, so corrected-only chroma flicker survives it by construction
rather than by luck. Per-channel gains would have three times the freedom and
no such guarantee.

**Fit domain** (all predeclared from the 8-bit sRGB source encoding, none
tuned against the frozen clips): the validity mask, minus linear luminance
≥ 0.95 (sRGB code 250/255 — at or near clipping, no usable information) and
≤ 0.0025 (code 8/255 — one code is a ~12 % change), in **both** aligned
original frames. On the frozen clips this removes essentially nothing (the
fit domain is 100.0 % of valid on every clip), which is itself worth knowing:
underwater footage is neither clipped nor black.

**Identifiability guards**, also predeclared: at least 4096 fit pixels and a
MAD-based luminance spread of at least 0.005. Together these bound the gain's
own uncertainty, since σ_a ≈ σ_noise / (√N · spread) and one 8-bit code near
mid-grey is ~0.003 linear: N = 4096 with spread 0.005 gives σ_a ≈ 1 %, and a
real 960×540 frame does far better. A constant image cannot separate gain
from bias at all, and the model says so rather than inventing a number.

### Estimator: robust start → LTS concentration → fixed-scale Huber

Deterministic; no sampling, no RANSAC.

1. **Robust start** — `a = MAD(y)/MAD(x)`, `b = med(y) − a·med(x)`. Median and
   MAD each have 50 % breakdown in their own variable, so a contaminated
   minority cannot choose the starting point.
2. **LTS concentration steps** (FAST-LTS C-steps, keep 70 %, 8 steps). This is
   the stage that matters. A bubble, a lit particle or a specular glint is an
   outlier in *both* frames at once — a **high-leverage** outlier — and plain
   Huber IRLS does not resist those. Measured: on a synthetic 15 % leverage
   cluster, Huber-from-least-squares converged to a gain of **0.04** against a
   true 1.25. Trimming by residual rank fixes it, with a 30 % breakdown point.
3. **Fixed-scale Huber M-step** (k = 1.345, 10 iterations, scale taken once
   from the LTS fit and held). Re-estimating the scale each iteration runs
   away in exactly the case step 2 just solved — the cluster nudges the line,
   the residual MAD grows, the larger scale readmits the cluster. Measured:
   that loop carried an exact 1.2500 gain out to **1.1603** over ten
   iterations. Holding the scale (Yohai's MM construction) preserves the
   breakdown point through the efficiency step.

Measured robustness against a high-leverage cluster (true gain 1.25, bias 0.02):

| contamination | fitted gain | bias | status |
|---|---|---|---|
| 0 % | 1.2500 | +0.0200 | fitted |
| 5 % | 1.2500 | +0.0200 | fitted |
| 15 % | 1.2396 | +0.0225 | fitted |
| 40 % | — | — | **identity: gain-out-of-range**, canonical falls back to raw |

### Two guards, both measured only on the input

* **Gain sanity**: a fitted gain outside [0.25, 4.0] is not simple
  illumination variation; the transform is rejected.
* **Acceptance**: a transform fitted to explain the input's own post-warp
  residual is kept only if it does not make that residual more than 1 % worse.
  (The margin exists because the estimator minimises a weighted squared
  residual on the fit domain while the metric reports L1 over the whole valid
  mask; on footage with nothing to explain those objectives disagree at the
  0.1 % level.) A rejected transform falls back to identity, which makes the
  canonical metric *equal* the raw one — strictly more conservative — and
  says so in `status`.

Neither guard, and no part of the fit, ever touches the corrected sequence.

### Anti-gaming, verified three ways

1. **Structurally** — a scalar gain/bias is chroma-preserving; the
   difference between two channels scales by the gain and nothing else.
2. **Synthetically** — with a temporally stable input and a corrected output
   pumping its red channel, raw and illumination-aware MC-Warp agree to six
   decimals (0.034508 vs 0.034508) while the input's own raw MC-Warp is
   exactly 0.
3. **On real footage** — sweeping an injected red flicker from 0 % to 20 % on
   `lights` and `murky_shark`, the fitted gain does not move at all (1.0227
   and 0.9980 at every amplitude). The illumination-aware value rises
   *faster* than raw with the flicker (1.236× vs 1.179× at a = 0.20 on
   `lights`), i.e. the transform amplifies rather than hides it.

---

## 5. Normalisation, coverage and status

**Uncompensated residual@k** is the same L1 with no warping, on the same
mask, pair, lag and grid. **Motion-reduction ratio@k** = uncompensated / raw.
It is descriptive context — Phase 2A showed the absolute residual varies 8×
across clips and ~2 % across backends — and it replaces nothing.

**Valid coverage@k** is reported at every lag beside every value, and so is a
separate ΔE coverage. Status bands are predeclared and label a result, never
delete one:

* `low-coverage` below 50 % — the value describes less than half the frame.
* `illumination-confounded` when geometry *and* the fitted global model
  together explain less than 20 % of the input's frame-to-frame change
  (uncompensated / illumination-aware < 1.25).
* `illumination-identity:<reason>` when the transform declined or was
  rejected, with the reason preserved through aggregation.

A score is `None` only when the mask is empty. Low coverage and undefined are
kept distinct.

---

## 6. Alignment sensitivity — the companion is justified

`scripts/alignment_study.py` runs entirely without a model: take one real
frame per clip on the metric grid, translate it by a known sub-pixel amount,
warp it back with the *exactly correct* flow. Everything left is
interpolation and resampling.

Integer offsets (0, 0) and (1, 0) return **0.000000** on every clip — the
warp is exact when no resampling is required.

| clip | floor @(0.25, 0) | floor @(0.5, 0.5) | measured input MC-Warp@1 | floor as % of measured |
|---|---|---|---|---|
| swimthrough | 0.002844 | 0.006342 | 0.009318 | **68 %** |
| murky_eel | 0.010945 | 0.023194 | 0.020160 | **115 %** |
| murky_shark | 0.000543 | 0.001071 | 0.004094 | 26 % |
| lights | 0.002266 | 0.004436 | 0.041193 | 11 % |
| distance | 0.001622 | 0.003588 | 0.015250 | 24 % |

**This is the largest single component of MC-Warp on the textured clips**, and
it is not correspondence error — the SEA-RAFT check above measures 0.013 px
endpoint error on a sequence of identical content and still reports MC-Warp
0.0133, because the true motion at the metric grid is fractional and must be
resampled.

Where it lives, by Sobel-gradient band at (0.5, 0.5):

| clip | bottom 50 % | p50–90 | p90–99 | top 1 % | top1 / bottom50 |
|---|---|---|---|---|---|
| swimthrough | 0.00106 | 0.00833 | 0.02335 | 0.03781 | **35.7×** |
| lights | 0.00094 | 0.00540 | 0.01640 | 0.03325 | 35.5× |
| distance | 0.00072 | 0.00387 | 0.01547 | 0.02866 | 39.6× |
| murky_shark | 0.00065 | 0.00111 | 0.00269 | 0.00590 | 9.1× |
| murky_eel | 0.01477 | 0.02982 | 0.03830 | 0.04363 | **3.0×** |

The residual maps confirm it: `swimthrough` lights up on coral edges and on
the thin rope Phase 2A flagged, with open water at exactly zero;
`murky_eel` is dense broadband texture everywhere except the smooth eel body,
which is why its ratio is only 3× and its floor is the largest.

**Decision: one alignment-robust companion is added** — a single fixed 1.0 px
Gaussian low-pass on both images before the same L1, reported separately as
`alignment_robust_warp` and never replacing anything. It cuts the synthetic
sub-pixel floor 3.3–4.5×, and on real footage it separates the two things
cleanly:

| clip | input raw@1 | input AR@1 | AR as % of raw |
|---|---|---|---|
| murky_eel | 0.020160 | 0.008876 | **44 %** (resampling-dominated) |
| swimthrough | 0.009318 | 0.006431 | 69 % |
| distance | 0.015250 | 0.010902 | 71 % |
| murky_shark | 0.004094 | 0.003118 | 76 % |
| lights | 0.041193 | 0.040213 | **98 %** (illumination, not alignment) |

`sigma` is fixed globally and never tuned per clip. It is a companion because
a genuinely blurred output also scores better on it — see case G.

---

## 7. Temporal ΔE00

`temporal_delta_e` reuses the project's existing, validated path —
`linear_rgb_to_lab` then `ciede2000` — with no second ΔE implementation. It
uses the same flow, the same warp and the same validity mask as MC-Warp, so
the two describe the same pixels.

Near-black exclusion: pixels at or below linear luminance 0.0025 (code 8/255)
in either frame, where a single 8-bit code moves ΔE00 by several units. On
the frozen clips this removes **0.02–0.05 %, and only on `lights`** (the dark
region outside the beam); ΔE coverage equals valid coverage everywhere else.
Reported separately so the exclusion stays visible.

It is at least as sensitive to legitimate lighting change as MC-Warp is and
carries no illumination compensation, so input and corrected values are always
reported together. On `lights` the input's own temporal ΔE is 5.0 at @1 and
16.7 at @8 with no processing at all.

---

## 8. Synthetic validation

47 tests, ordinary venv, analytic flow backend (exact known correspondence,
so any residual is the metric's own behaviour). Measured values:

| case | result |
|---|---|
| **A** integer translation @1/@4/@8 | raw and illum-aware **0.000000** at all three lags; uncompensated 0.057/0.081/0.088; coverage 98.0/92.0/84.3 % |
| **B** fractional (0.5, 0.25) | raw **0.001334** vs 0.000000 for the integer control; small, non-zero, characterised in §6 |
| **C** global gain 1.10 | raw 0.041579 → illum-aware **0.000000**; fitted gain 0.9091 = 1/1.10 exactly |
| **D** gain 1.08 + bias 0.03 | raw 0.062065 → illum-aware **0.000000**; fitted (0.9259, −0.02333), both exact for the pair |
| **E** corrected-only red flicker | input raw exactly 0; corrected raw 0.034508, illum-aware **0.034508** (unchanged); temporal ΔE 8.860 vs 0.0000 on the input; fitted gain 1.0000, bias 0.00000 |
| **F** one-frame spike | per-pair raw {0: 0.0, 1: 0.0, **2: 0.100, 3: 0.100**, 4: 0.0}; per-pair ΔE {0, 0, **17.6, 17.6**, 0} |
| **G** blur | raw 0.001134 → **0.000413** (64 % lower). Blur wins on a photometric temporal score. Not superiority — spatial fidelity is a separate axis, and no function in the module ranks two results |
| **H** occlusion / disocclusion | band FB-inconsistent: coverage **75.0 %**, raw 0.000000 (the change inside the excluded band does not leak in). Same footage, band included: coverage 100 %, raw 0.100000 |
| **I** localised illumination | raw 0.030437 → illum-aware 0.029709; the global model explains **2.4 %**; status `illumination-confounded`. Separately: a local light in the input does not mask corrected-only flicker elsewhere |
| **J** coverage gaming | wide mask raw **0.281250** at 100 % coverage; masking the hard region raw **0.000000** at **43.8 %** coverage, status **`low-coverage`**. The score is preserved, not deleted, and nothing declares the masked run better |

Plus the invariants: correspondence is requested only from the original
sequence; the illumination fit is byte-identical across three wildly different
corrected sequences; lag 1/4/8 produce exactly the call sequence
`[(0,1),(1,0),(0,4),(4,0),(0,8),(8,0)]` with **no composition of shorter
hops**; each pair costs exactly two inferences even with the alignment-robust
companion on; the returned result contains no ndarray anywhere; and no field
in either result dataclass is named `overall`, `combined` or `score`.

### An aliasing property the real-data sweep exposed

A period-2 flicker is **invisible at every even lag**: frames t and t+8 sit on
the same phase and carry the identical gain. Measured synthetically: raw
0.046289 @1, **0.000000 @2 and @4**. This is a property of any lag-k
comparison, and it is the concrete reason to report three lags — but it also
means the @1/@4/@8 set is blind to a period-4 oscillation at two of its three
lags. Pinned by a test so it stays known rather than becoming folklore.

---

## 9. Real footage

Frame ranges, anchors and grid are **identical to the Phase 2A lag study** — a
41-frame window centred on the bakeoff excerpt, anchors at local 16/18/20,
960×540 (540×960 for the two portrait-decoding clips), linear-light
`INTER_AREA` downscale — so the two studies are directly comparable.

| clip | source | window | source size | flow inference | metric grid |
|---|---|---|---|---|---|
| swimthrough | `SWIMTHROUGH.MP4` | 181–221 | 1080×1920 | 544×960 | 540×960 |
| murky_eel | `MURKYEEL.MP4` | 636–676 | 1080×1920 | 544×960 | 540×960 |
| murky_shark | `MURKYSHARK.MP4` | 0–40 | 1920×1080 | 960×544 | 960×540 |
| lights | `LIGHTNIGHTDIVE.MP4` | 71–111 | 1920×1080 | 960×544 | 960×540 |
| distance | `DISTANCESHOT.MP4` | 246–286 | 1080×1920 | 544×960 | 540×960 |

### Reproduces Phase 2A

Motion-reduction ratio on the unprocessed input, against the Phase 2A lag
study's SEA-RAFT column:

| clip | @1 (2A / 2B) | @4 | @8 |
|---|---|---|---|
| swimthrough | 4.39 / **4.33** | 5.37 / **5.35** | 5.67 / **5.67** |
| murky_eel | 4.52 / **4.51** | 5.11 / **5.11** | 4.98 / **4.98** |
| murky_shark | 1.37 / **1.37** | 2.33 / **2.33** | 2.43 / **2.45** |
| lights | 1.14 / **1.12** | 1.07 / **1.07** | 1.02 / **1.02** |
| distance | 2.66 / **2.66** | 3.74 / **3.74** | 3.79 / **3.78** |

Mean coverage 97.0 / 90.8 / 83.3 % against Phase 2A's 97.0 / 90.8 / 83.4 %.
The remaining differences are the two deliberate ones: the mask now also
requires finite resampling support, and pairs are pooled by valid-pixel count
rather than averaged as per-pair means.

### Input baseline (`--method none`)

| clip | lag | raw | illum-aware | uncomp | reduction | AR | ΔE | coverage | gain | bias | explains | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| swimthrough | @1 | 0.009318 | 0.009330 | 0.040365 | 4.33× | 0.006431 | 2.554 | 97.0 % | 1.0013 | −0.00001 | −0.1 % | ok |
| | @4 | 0.012681 | 0.012711 | 0.067876 | 5.35× | 0.009468 | 3.191 | 88.4 % | 1.0064 | +0.00017 | −0.2 % | ok |
| | @8 | 0.014342 | 0.014263 | 0.081337 | 5.67× | 0.011926 | 3.571 | 77.0 % | 1.0270 | +0.00094 | 0.5 % | ok |
| murky_eel | @1 | 0.020160 | 0.020241 | 0.091021 | 4.51× | 0.008876 | 2.881 | 97.1 % | 1.0042 | −0.00225 | −0.4 % | illum identity (1/3 pairs) |
| | @4 | 0.025098 | 0.025070 | 0.128181 | 5.11× | 0.012730 | 3.665 | 89.0 % | 0.9965 | −0.00120 | 0.1 % | ok |
| | @8 | 0.029450 | 0.029255 | 0.146533 | 4.98× | 0.016840 | 4.215 | 78.4 % | 0.9874 | −0.00117 | 0.7 % | ok |
| murky_shark | @1 | 0.004094 | 0.004095 | 0.005601 | 1.37× | 0.003118 | 1.035 | 96.3 % | 0.9980 | +0.00038 | −0.0 % | ok |
| | @4 | 0.004839 | 0.004676 | 0.011277 | 2.33× | 0.003981 | 1.186 | 90.9 % | 1.0042 | +0.00099 | 3.4 % | ok |
| | @8 | 0.005395 | 0.005088 | 0.013217 | 2.45× | 0.004601 | 1.277 | 89.7 % | 1.0039 | +0.00151 | 5.7 % | ok |
| **lights** | @1 | 0.041193 | 0.041079 | 0.046265 | 1.12× | 0.040213 | 5.036 | 97.0 % | 1.0227 | +0.00462 | 0.3 % | **confounded** |
| | @4 | 0.093044 | 0.091372 | 0.099357 | 1.07× | 0.092511 | 12.060 | 95.1 % | 0.7356 | +0.03842 | 1.8 % | **confounded** |
| | @8 | 0.144203 | 0.126473 | 0.146653 | 1.02× | 0.143460 | 16.690 | 89.4 % | 0.3243 | +0.07299 | 12.3 % | **confounded** |
| distance | @1 | 0.015250 | 0.015069 | 0.040582 | 2.66× | 0.010902 | 2.387 | 97.8 % | 0.9905 | +0.00182 | 1.2 % | ok |
| | @4 | 0.020566 | 0.018919 | 0.076915 | 3.74× | 0.017176 | 3.105 | 90.6 % | 0.9801 | +0.00864 | 8.0 % | ok |
| | @8 | 0.028937 | 0.024904 | 0.109481 | 3.78× | 0.026041 | 4.068 | 82.2 % | 0.9661 | +0.01811 | 13.9 % | ok |

### Repeatability, and the metric's own error bar

`scripts/stability_check.py`. Two questions a regression metric has to answer,
and only the second had been asked before this was run.

**Repeat the identical evaluation: exact, on every clip and every lag.** The
snapshot of all six reported quantities compares equal, not approximately —
which follows from SEA-RAFT being bitwise deterministic here, but is worth
having measured rather than assumed.

**Measure the same window from three different anchor triples** — A = 16/18/20
(the reported one), B = 15/17/19, C = 17/19/21 — and the spread across them is
the metric's own sampling noise. It is what says how large a pipeline change
has to be before it means anything:

| clip | @1 raw | @4 raw | @8 raw | @1 reduction | @1 ΔE | worst coverage spread |
|---|---|---|---|---|---|---|
| swimthrough | 4.2 % | 6.3 % | 3.1 % | 6.5 % | 3.4 % | 2.2 % |
| murky_eel | **17.4 %** | 1.2 % | 1.8 % | 16.4 % | 20.4 % | 2.2 % |
| murky_shark | 1.4 % | 3.5 % | 2.2 % | 0.6 % | 0.9 % | 7.6 % |
| lights | **39.1 %** | 12.8 % | 2.7 % | 6.4 % | 11.9 % | 1.7 % |
| distance | 4.8 % | 6.1 % | 5.9 % | 9.6 % | 6.6 % | 1.2 % |

Two things follow.

* **The gray-world result survives comfortably on four clips.** A 2.05–2.73×
  change against a 1–6 % anchor spread is not ambiguous. `distance`'s 1.19–1.31×
  against 4.8–6.1 % is smaller but still an order of magnitude clear.
* **`lights` @1 has a 39 % anchor spread**, which is on its own enough to make
  that cell unusable — independently of the illumination confound, and pointing
  at the same cause (three anchors sample three different positions of a moving
  beam). The `illumination-confounded` label and the anchor spread agree.

The reduction ratio is often the steadier of the two — 6.4 % against raw's
39.1 % on `lights` @1, 0.1 % against 1.2 % on `murky_eel` @4 — but not always
(`distance` @1: 9.6 % against 4.8 %), so it earns its place beside the
absolute residual rather than instead of it.

Caveat on the number itself: three overlapping anchor triples inside one
41-frame window is a small, correlated sample. Read it as a floor on the
metric's variability, not an estimate of it.

### The metric moves when the pipeline changes

Raw MC-Warp, unprocessed input → gray-world output:

| clip | @1 | @4 | @8 | temporal ΔE @1 |
|---|---|---|---|---|
| murky_shark | 0.00409 → 0.01118 (**2.73×**) | 2.66× | 2.58× | 1.035 → 3.474 |
| murky_eel | 0.02016 → 0.05229 (**2.59×**) | 2.46× | 2.27× | 2.881 → 8.945 |
| swimthrough | 0.00932 → 0.02076 (**2.23×**) | 2.07× | 2.05× | 2.554 → 5.081 |
| distance | 0.01525 → 0.02005 (**1.31×**) | 1.22× | 1.19× | 2.387 → 3.584 |
| lights | 0.04119 → 0.04119 (**1.00×**) | 0.99× | 0.99× | 5.036 → 5.144 |

Gray-world roughly doubles-to-triples the motion-compensated residual on four
of five clips. That is the expected result and it is the point: a per-frame
global scaling with no temporal term is temporally unstable, and the metric
says so, at every lag, on every category.

The size of the effect tracks the size of the corrective gain rather than the
clip's difficulty. Measured over the same 41-frame windows, gray-world's
red-channel scale is **28.4× on `murky_eel`**, 17.1× on `murky_shark`, 15.8×
on `swimthrough`, 3.8× on `distance` and **0.91× on `lights`** — the last
because artificial white light needs almost no white balancing. A large gain
on a signal-starved red channel amplifies whatever instability that channel
has; a gain near 1 does not. (PLAN.md's "signal recoverability" axis; not this
phase's business, but it is what the temporal numbers are reacting to.)

### Qualitative observations from the residual maps

* **`murky_eel` @1 raw residual** is dense broadband texture over the whole
  frame — the sub-pixel resampling floor of dense rubble — with a bright
  outline along the eel's silhouette where the mask boundary leaks. The eel
  body itself is dark because it is excluded, not because it is stable.
* **`murky_eel` @8 validity mask** cuts the whole eel out as a solid blob,
  plus the expected disocclusion band on the leading edges.
* **`lights` @8 raw residual** is saturated across the entire beam-lit
  region at an 8× display gain — broad, smooth, and nothing like the
  edge-localised pattern of a misregistration.
* **`lights` illumination-correction magnitude** (what the fitted transform
  actually changed) is a monotone function of image brightness, brightest on
  the lit coral. It has no spatial structure because a global scalar has no
  spatial degrees of freedom. That picture is the limitation.

---

## 10. `lights` — the mandatory falsification (brief §20)

**Result: Case C. The bounded global model does not rescue the clip, and it is
labelled `illumination-confounded` at all three lags.**

The model explains **0.3 % / 1.8 % / 12.3 %** of the input's post-warp
residual at @1/@4/@8. Even at @8, where it strains hardest, combined
geometry + illumination explains only 1.16× of the frame-to-frame change,
below the predeclared 1.25× threshold. At @8 the fit reaches gain 0.3243 with
bias +0.073 and one of the three pairs is rejected outright as
`gain-out-of-range` — the model is being pushed far outside anything that
describes light, in exchange for 12 %.

**The one allowed alternative was not exercised, and the reason is in the
data, not in the budget.** The failure is not that gain/bias is the wrong
*photometric* representation; it is that the change is *spatially local*. A
camera-mounted beam relights part of the frame and leaves the rest alone.
Every bounded alternative on the shortlist — gradient-domain residual, census,
locally normalised correlation — is still a global, spatially-uniform recipe
applied to a spatially-varying phenomenon, and each would trade a real
sensitivity (gradient and census discard exactly the low-frequency intensity
information a restoration's most visible failure mode lives in) for a
confound they cannot remove either. §8 of the brief says the honest outcome
is to mark the clip confounded rather than escalate; the synthetic localised
illumination case (I) shows the same failure with the mechanism isolated,
which is the evidence that it is locality and not functional form.

**What `illumination-confounded` does and does not mean.** A first reading of
these numbers — "the metric is blind on `lights`, since gray-world's real
instability is invisible there" — did not survive being checked, and the check
is `scripts/lights_falsification.py`: inject a corrected-only red flicker of
known amplitude and sweep it, on `lights` and on the non-confounded
`murky_shark`.

| amplitude | `lights` raw | `lights` ΔE | `murky_shark` raw | `murky_shark` ΔE |
|---|---|---|---|---|
| 2 % | 0.994× | 1.015× | 1.000× | 1.001× |
| 5 % | 0.998× | 1.098× | 1.011× | 1.011× |
| 10 % | 1.031× | 1.346× | 1.046× | 1.046× |
| 20 % | **1.179×** | **2.031×** | 1.154× | 1.163× |

The *relative* sensitivity on `lights` is as good as on `murky_shark`, and
temporal ΔE is markedly better there — because artificial white light makes
the red channel bright, so a red perturbation is large in absolute terms. So
gray-world's null result on `lights` is not the metric failing to see; it is
gray-world's gains being ≈1 on that clip and genuinely doing very little.

The correct reading of the label is therefore narrower and worth stating
exactly: on a confounded clip the **absolute** residual is dominated by source
illumination, so it is not comparable to another clip's, the motion-reduction
ratio is uninformative (1.02–1.12×), and the illumination-aware value is not
meaningfully different from the raw one. Relative change under a fixed
pipeline comparison is still readable. Recorded as a correction because the
first version was asserted before it was measured — the same mistake, and the
same remedy, as Phase 2A's §A7.

---

## 11. `murky_shark` — near-static, low texture (brief §21)

Phase 2A's warning: all four backends reported 96–99 % FB-valid on this clip
while disagreeing with each other by ~22 % of the motion magnitude. **FB
consistency means the field is self-consistent, not that it is correct.**

The metric does not launder that into confidence:

* **@1 the reduction ratio is 1.37×** — motion compensation barely helps,
  because there is barely any motion (0.03 px/frame). The number itself
  announces that warping is not doing the work.
* **@4 and @8 it rises to 2.33× and 2.45×**, as the camera finally moves
  enough for correspondence to matter. The lags are not redundant here, and
  they run the *opposite* way from `lights`.
* **Coverage stays high and nearly flat** (96.3 / 90.9 / 89.7 %) — the least
  lag decay of any clip, because almost nothing leaves the frame.
* The **illumination model finds almost nothing** to explain (gain 0.998–1.004,
  3–6 % at @4/@8), which is the right answer on ambient-lit murk.

High coverage plus a low reduction ratio is exactly the signature that should
*not* be read as a confident result, and both numbers are always printed
together. The residual floor here is also the smallest in the set (0.0041),
so a pipeline change shows up clearly in relative terms — gray-world's 2.73×
at @1 is the **largest** relative jump of any clip, on the footage where
flicker is most visible to the eye. That is the reassuring half of Phase 2A's
open question 7.

No additional flow model was added to resolve the ambiguity, and none should
be: the ambiguity is about ground truth this test set does not have.

---

## 12. Known limitations

* **FB self-consistency is not correctness.** On low-texture water a smooth
  field is trivially self-consistent in both directions while still being
  wrong. High coverage on `murky_shark` means "nothing contradicted the flow".
* **The moving animal is the part not measured.** SEA-RAFT invalidates the
  eel body wholesale. Coverage reports how much, but not what.
* **Sub-pixel interpolation is the largest component of MC-Warp on textured
  clips** — 68 % of the measured value on `swimthrough` and more than 100 % of
  it on `murky_eel` at a half-pixel offset. The alignment-robust companion
  quantifies it; it does not remove it from the canonical number, by design.
* **Localised illumination defeats the canonical model** and is labelled, not
  fixed. `lights` is confounded at all three lags.
* **Camera exposure/WB behaviour** already in the source is only partly
  representable: a global exposure step is, a per-channel auto-WB step is not
  (deliberately — that freedom is what would let the model absorb chroma
  flicker).
* **Temporal aliasing**: MC-Warp@k cannot see an oscillation whose period
  divides k. The @1/@4/@8 set is blind to period-4 pumping at two of its
  three lags.
* **Blur lowers every photometric temporal score**, including the
  alignment-robust companion. Nothing here is a defence against a restoration
  that wins by softening; spatial fidelity is a separate axis and stays one.
* **Bubbles and particles** have no correct correspondence. SEA-RAFT tracks
  individual particles as fast-moving objects and then rejects them by its own
  FB mask; the bubble column on `distance` remains the largest structured
  residual, and only VideoFlow-MOF flagged it in Phase 2A — at 25× the cost
  and unusable at @4/@8.
* **Long-lag overlap.** At @8, coverage is 77–89 % and *which* four-fifths is
  measured depends on the backend's occlusion behaviour. Two configurations
  are comparable at @8 only if their coverage is too.
* **Illumination-fit breakdown is 30 %.** Past that the guards catch it and
  the canonical metric degrades to the raw one; between roughly 15 % and 30 %
  contamination the gain is biased by a few percent without being flagged.
* **Resolution.** Everything is measured at 960×540. Fine structure below
  that grid is not evaluated, and the sub-pixel floor would change at another
  resolution. Not a reason to revisit high-resolution flow yet — the
  interpolation floor is a property of resampling, not of the model.
* **Applying the frozen bias to a strongly-rescaled output.** If a pipeline
  multiplies the image substantially, the correct bias for the corrected
  sequence is its own gain times the fitted one, which cannot be known without
  looking at the corrected frames. The transform then under-removes the
  legitimate change. That error can only inflate the corrected residual, never
  flatter it, and `bias` is reported so a large one is visible.
* **Three anchors per clip per lag.** Enough to see a clip's behaviour, not a
  sampling of a whole clip. Nothing here tests drift over 30 seconds, which
  remains the Week 8 gate.

---

## 13. Repository changes

**Created — permanent:** `uw/searaft.py`, `uw/waft.py`,
`tests/test_temporal.py`, `tests/test_backends.py`.

**Deleted — exploratory:** `experiments/week2a_flow/backends/searaft_backend.py`
and `waft_backend.py` (promoted into `uw/`; two copies of a wrapper is two
copies that can drift), and `flowit_backend.py` (dropped on reproducibility in
Phase 2A §5, with §A8 removing the last reason to revisit).
`videoflow_backend.py` (MOF) stays: it is the only backend that flagged the
`distance` bubble column, which is a named future use. Every Phase 2A script
still runs and every Phase 2A number is still reproducible — `build_backend()`
now constructs the promoted classes, and the aggregation scripts already
skipped absent backends.

**Modified — permanent:** `uw/flow.py`, `uw/metrics.py` (the temporal section
and the cross-backend comparison; `delta_e`
and `ciede2000` untouched, `temporal_stability` kept and marked DEPRECATED so
pre-Phase-2B LOG entries stay reproducible), `uw/cli.py`, `uw/io.py`
(`start`/`count`).

**Created — exploratory:** `experiments/week2b_temporal/` (README, this
document, five scripts).

**Not modified:** `CLAUDE.md`, `pyproject.toml`,
`uw/types.py`, `uw/colorspace.py`, `uw/baselines.py`, and everything under
`experiments/week2a_flow/`. No footage was touched, staged or committed. No
`--no-temporal` flag was added, because no temporal correction stage exists.

**Generated diagnostics — `outputs/temporal_metric/` (gitignored):**

```
alignment/alignment_study.json          the sub-pixel floor, per clip and offset
alignment/<clip>_dx*_dy*.png            residual maps, shared scale per clip
searaft_check.json                      known-motion check of the promoted wrapper
lights_falsification.json               the injected-flicker sweep
stability_check.json                    repeatability and anchor-set spread
<method>/temporal_metrics.json          every number, per clip, lag and pair
<method>/<clip>/lag<k>_pair_<t>_<t1>/
    original_t.png  corrected_t.png  warped_corrected_t1.png
    residual_input_raw.png  residual_corrected_raw.png
    residual_input_illum_aware.png  residual_corrected_illum_aware.png
    residual_uncompensated.png  valid_mask.png
    illumination_correction_magnitude.png
```

---

## 14. Open questions for the next phase

1. **How much of the anchor spread is real clip variation?** Three
   overlapping triples inside one 41-frame window put it at 1–6 % on most
   cells and 17–39 % on two. Whether those two are the clip genuinely varying
   or the measurement being unstable is not separable from three samples, and
   it decides whether a `lights` @1 number is worth printing at all.
2. **Should the sub-pixel floor be subtracted or reported as a floor?** It is
   68–115 % of the measured value on textured clips and it is a property of
   the footage and the grid, not of the pipeline. Reporting a per-clip floor
   beside the score would make two clips' numbers comparable for the first
   time. Any subtraction is a metric redefinition and should not be done
   quietly.
3. **Is the eel-body exclusion acceptable?** The metric does not measure
   smooth moving subjects at all. If Week 6+ makes those a target, this
   becomes a real gap rather than a conservative choice.
4. **Do @4 and @8 earn their cost on a real regression?** They cost 2/3 of
   the runtime. On four of five clips gray-world's effect is largest at @1 and
   shrinks with lag; `murky_shark` is the case that argues for keeping them.
5. **30-second drift** — still untested, still the Week 8 gate, still the most
   informative experiment available (~23 min of SEA-RAFT per clip).
