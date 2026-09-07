# Week 4A Round 2 — PART D: the evaluation grid-map defect

**Status: CORRECTNESS DEFECT FOUND AND REPAIRED. It invalidated part of the
Round-1 comparison and it changes a load-bearing Round-1 conclusion.**

Everything below is still PRE-C2. The Week-3 persisted range product remains a
PROVISIONAL MULTI-VIEW HYPOTHESIS, not ground truth. "Residual" here means
disagreement with that hypothesis. Nothing here declares a winner.

This defect was not in the Round-2 task list. It was found while wiring the
Round-2 backends into the Round-1 evaluation infrastructure, by checking that
the grid a Round-2 prediction would be sampled on is the grid it is stored on.
It is reported under §28(4) — a newly discovered correctness defect that
invalidates part of the comparison — and repaired rather than deferred, because
the repair is mechanical, the evidence that decides it was already persisted,
and the affected models include incumbent **I3 MoGe-2**.

---

## 1. The defect

`evalgrid.load_model_gridmap` returned the map from source pixels onto the grid
**the network consumes**, and every stage from S2 onward used it as the map onto
the grid **the persisted prediction lives on**. Those are the same grid for some
models and not for others.

The S0 FOV audit measures its map by probing `backend.preprocessed_image()` —
by construction the *input* tensor. But four of the seven Round-1 models
interpolate their outputs back up to the source `(H, W)` before returning, and
their own backends say so:

| evidence | text |
|---|---|
| `backends/dav2_small.py:117` | `"output_grid": "SOURCE resolution — the model interpolates back up"` |
| `backends/moge_family.py:244` | `"…and interpolates the outputs back to the SOURCE (H,W)"` |
| `backends/foundationgeo_11.py:305` | `"…then outputs interpolated back to [source]"` |

For those models the correct source→prediction map is the **identity**. The
audit map was applied instead, so every field was sampled at roughly
0.72–0.88× of the correct position — a systematic inward compression toward the
image origin, largest at the frame edges, which is exactly where the thin
structure and the depth boundaries live.

Measured directly from the persisted products:

| model | source | stored prediction | S0 audit grid | map used | map correct |
|---|---|---|---|---|---|
| `mapanything_n1` | 720×1280 | 294×518 | 294×518 | audit | audit ✓ |
| `wat3r_n1` | 720×1280 | 294×518 | 294×518 | audit | audit ✓ |
| `da3mono_large` | 720×1280 | 280×504 | 280×504 | audit | audit ✓ |
| `moge2_vitl` | 720×1280 | **720×1280** | 630×1120 | audit ✗ | **identity** |
| `dav2_small` | 720×1280 | **720×1280** | 518×924 | audit ✗ | **identity** |
| `foundationgeo_11` | 720×1280 | **720×1280** | 592×1056 | audit ✗ | **identity** |
| `metricanything_pointmap` | 720×1280 | **720×1280** | 630×1120 | audit ✗ | **identity** |

The reference side was **not** affected: Week 3 persisted its range product on
the MapAnything network grid (294×518), which is the grid
`load_reference_gridmap` returns, and the two match. The defect is confined to
the model side.

## 2. The repair

`evalgrid.model_output_grid(model, source_hw)` now decides which grid a model's
persisted prediction lives on **from evidence already in the S0 record** — the
probe's own `native_shape` — and not from a table, a backend docstring, or a
residual:

* probe output shape == audit `model_grid_hw` → the audit map;
* probe output shape == `source_hw` → the identity map;
* neither → `SystemExit`. It refuses to guess.

`load_model_gridmap` now takes an optional `pred_hw`. Callers that already have
the persisted product open (`s2_ambiguity`, `armio`) pass the stored
`native_shape`, and a mismatch against the resolved grid is fatal — that would
mean the file on disk was not produced by the preprocessing S0 measured, and no
map would be trustworthy.

This deliberately does **not** decide the question by residual. Round 1's DA3
mistake was settling a semantic question by which hypothesis fit better; the
grid a tensor is stored on is a fact about shapes, and it is read as one. The
residual comparison below is reported only as confirmation, after the fact.

**Confirmation** (log-space correlation against the provisional Week-3 range,
8 frames × 2 clips, no fitting — a scale- and shift-free agreement check):

| model | clip | audit map | identity map |
|---|---|---|---|
| `moge2_vitl` | `wreck_01` | +0.7595 | **+0.8523** |
| `foundationgeo_11` | `cenote_01` | +0.7485 | **+0.8519** |
| `foundationgeo_11` | `wreck_01` | +0.7236 | **+0.8699** |
| `metricanything_pointmap` | `wreck_01` | +0.8225 | **+0.8973** |
| `da3mono_large` | `wreck_01` | **+0.9279** | −0.4097 |
| `mapanything_n1` | `wreck_01` | **+0.9666** | −0.2573 |

The split is exactly the one the shapes predict, and it is not marginal: for a
network-grid model the wrong map destroys the correlation outright.

## 3. What it changed — OLD vs CORRECTED

S2 primary-family median `abs_rel` against the provisional Week-3 range,
clip-level fit, frozen policy. **The three network-grid models are bitwise
unchanged**, which is itself the control: it shows the repair touched only what
it should have.

| model | OLD mean | CORRECTED mean | change |
|---|---|---|---|
| `mapanything_n1` | 0.1064 | 0.1064 | unchanged (control) |
| `wat3r_n1` | 0.1937 | 0.1937 | unchanged (control) |
| `da3mono_large` | 0.1466 | 0.1466 | unchanged (control) |
| `dav2_small` | 0.1763 | **0.1276** | **−27.6 %** |
| `foundationgeo_11` | 0.1932 | **0.1504** | **−22.2 %** |
| `metricanything_pointmap` | 0.2146 | **0.1886** | −12.1 % |
| `moge2_vitl` | 0.2247 | **0.2043** | −9.1 % |

Per clip, the effect is strongly clip-dependent rather than a uniform offset —
`swimthrough_02` and `wreck_05` improve by 30–50 % while `wreck_01` and
`cenote_01` barely move — which is what a *geometric* error looks like, not a
scale error. A scale error would have been absorbed by the clip-level fit.

Two conventions also flipped. `dav2_small` was read as `range` on `wreck_05`
and `swimthrough_02` under the wrong map and reads as `z_depth` under the right
one. That is a second reason not to settle representation semantics by
residual, and it is the same lesson Part A drew for DA3 — recorded here as
independent corroboration.

## 3b. What it changed in S3 — and it rewrites the Round-1 local-geometry story

Median over the six frozen clips, corrected S2 policy, same 288 frames, no
re-inference. The first three arms are the network-grid **controls** and are
bitwise identical; every changed number below belongs to a source-grid model.

> **Later correction, recorded here so this table is not misread as current.**
> The Part D recompute ran under the *Round-1* alignment policy, in which
> `da3mono_large` and `dav2_small` still carried `convention: "range"`. The §3/§4
> convention repair (z-depth, from source) was applied to those two arms
> afterwards and merged into `R2_S3_results.json`; see `R2_S3_LOCAL_GEOMETRY.md`
> §4. The Part D *deltas* below are unaffected — Part D is a sampling repair and
> the convention is held fixed across each arrow — but the right-hand values for
> those two arms are superseded: DA3 M-1 0.1283 → 0.1476, M-4 0.0285 → 0.0223;
> DA v2 M-1 0.1092 → 0.1094, M-4 0.0167 → 0.0164. The other five rows stand.

| arm | M-1 abs_rel | M-3 rel-normal (deg) | M-4 boundary | M-5 ord@0.25 | M-6 outer/inner |
|---|---|---|---|---|---|
| `mapanything_n1` | 0.0853 → 0.0853 | 6.84 → 6.84 | 0.0028 → 0.0028 | 0.0000 → 0.0000 | 1.043 → 1.043 |
| `da3mono_large` | 0.1283 → 0.1283 | 12.77 → 12.77 | 0.0285 → 0.0285 | 0.0037 → 0.0037 | 1.014 → 1.014 |
| `wat3r_n1` | 0.1840 → 0.1840 | 15.62 → 15.62 | 0.0171 → 0.0171 | 0.0057 → 0.0057 | 0.932 → 0.932 |
| `dav2_small` | 0.1761 → **0.1092** (−38 %) | 27.50 → **12.72** (−54 %) | 0.1022 → **0.0167** (−84 %) | 0.1172 → **0.0057** (−95 %) | 0.935 → 0.939 |
| `foundationgeo_11` | 0.1712 → **0.1135** (−34 %) | 32.71 → **17.81** (−46 %) | 0.0423 → **0.0219** (−48 %) | 0.0862 → **0.0019** (−98 %) | 0.794 → 1.176 |
| `moge2_vitl` | 0.2156 → **0.1958** (−9 %) | 27.78 → **13.68** (−51 %) | 0.0355 → 0.0320 (−10 %) | 0.0676 → **0.0015** (−98 %) | 1.008 → 1.072 |
| `metricanything_pointmap` | 0.1819 → **0.1530** (−16 %) | 27.50 → **14.27** (−48 %) | 0.0360 → 0.0249 (−31 %) | 0.0665 → **0.0020** (−97 %) | 0.938 → 1.080 |

The scale of the M-5 change is the tell. Ordinal violations at a 0.25 log
margin fell by **95–98 %** for every source-grid model. An ordinal violation is
a pair of points the model orders back-to-front by a wide margin; sampling a
smooth depth field 12–28 % off-position manufactures exactly that, because the
value fetched for a far pixel is the value of a nearer one. Those violations
were an artifact of the harness, not a property of any model.

**The Round-1 local-geometry conclusion does not survive this intact.** Under
the old numbers the four source-grid models looked like a distinct, badly worse
tier on M-3, M-4 and M-5 — relative normals at 27–33° against MapAnything's 7°,
ordinal violations at 7–12 % against 0 % — and MapAnything N=1 looked like it
was in a different league on local structure. Corrected, the field is bunched:

| arm | M-1 | M-3 (deg) | M-5 ord@0.25 |
|---|---|---|---|
| `mapanything_n1` | **0.0853** | **6.84** | **0.0000** |
| `dav2_small` | 0.1092 | 12.72 | 0.0057 |
| `foundationgeo_11` | 0.1135 | 17.81 | 0.0019 |
| `da3mono_large` | 0.1283 | 12.77 | 0.0037 |
| `metricanything_pointmap` | 0.1530 | 14.27 | 0.0020 |
| `wat3r_n1` | 0.1840 | 15.62 | 0.0057 |
| `moge2_vitl` | 0.1958 | 13.68 | 0.0015 |

MapAnything N=1 still leads every dimension, so the *ordering at the top* is
unchanged and the pre-C2 finding that a strict single-image model has not
matched it stands. What does not stand is the *margin*: relative normals go
from a 4–5× gap to under 3×, and the ordinal-consistency gap essentially
closes. Any Round-1 sentence resting on the size of that gap has to be reread.

Two individual readings also invert. **MoGe-2, incumbent I3, is now the worst
arm in the field on M-1** (0.196) while being the second best on M-5 (0.0015) —
a split that the old numbers hid. And **FoundationGeo's M-6 outer/inner ratio
crosses 1.0**, from 0.794 (under-estimating range at the periphery) to 1.176
(over-estimating it) — the sign of its radial bias flips, because a radial
statistic is precisely what a radial sampling error corrupts. No Round-1
statement about FoundationGeo's peripheral behaviour is usable.

## 4. The conclusion this overturns

**Depth Anything V2 Small is no longer clearly eliminated, so §4's "if it
remains clearly eliminated: STOP" does not fire and DA V2 continues into S3.**

Combining both repairs — Part B's affine fit in native disparity space and Part
D's grid map — DA V2's median `abs_rel` per clip is now:

| clip | `dav2_small` (Parts B+D) | `da3mono_large` (Part A) |
|---|---|---|
| `wreck_07` | 0.1106 | 0.1716 |
| `wreck_05` | 0.1124 | 0.2154 |
| `cenote_01` | 0.1143 | 0.0859 |
| `swimthrough_02` | 0.1119 | 0.1155 |
| `wreck_01` | 0.2199 | 0.2301 |
| `wreck_03` | 0.1264 | 0.1302 |
| **mean** | **0.1326** | **0.1581** |

Round 1 eliminated DA V2 as the weakest arm in the field. After repair it is the
most *uniform* arm in the field — five of six clips within 0.11–0.13, with the
portrait clip `wreck_01` the sole outlier — and on this pre-C2 consistency
measure it is ahead of the corrected DA3. That is a genuine reversal of a
Round-1 conclusion, and it is stated here as such.

It does **not** make DA V2 a winner. It is one metric, pre-C2, against a
provisional hypothesis, and a relative-disparity model that needs two fitted
parameters per clip is not thereby shown to be usable as a fallback geometry
source. S3, the thin-structure test, and S4–S6 decide what it is actually good
at.

## 5. Scope of the invalidation

Recomputed from the persisted predictions, with **no re-inference**:

* **S2** — recomputed, policy re-frozen. Round-2 Parts A and B recomputed on top.
* **S3** — recomputed in full (§3b below). The `mapanything_n1`, `wat3r_n1` and
  `da3mono_large` results are bitwise unchanged.
* **S4, S5, S6** — the Round-1 results for `moge2_vitl`, `dav2_small`,
  `foundationgeo_11` and `metricanything_pointmap` were computed through the
  wrong map and are being recomputed.
* The pre-repair result files are preserved under
  `experiments/week4_mono/round1/archive/pre_gridfix_2026-09-07/` (JSON and Markdown
  only, gitignored) so every OLD value in this report is checkable.

## 6. Consequence for Round 2

Every Round-2 challenger is covered by the repaired path automatically, because
`model_output_grid` decides from that model's own S0 probe. Two of the four
runnable Round-2 challengers return on the source grid (MoGe-3 interpolates its
outputs back up) and two on the network grid (MDA at 504×280, PXDepth at its run
grid), so this defect would have hit the Round-2 comparison too, asymmetrically,
had it not been found first.
