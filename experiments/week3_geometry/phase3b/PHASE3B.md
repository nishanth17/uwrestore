# Week 3 Phase 3B — frozen hypotheses and experimental plan

**Status of this file: the pre-registration.** It is written *before* any Phase 3B
run and records exactly six hypotheses, the experiment chosen for each, and — for
each — an explicit review of whether that experiment actually isolates its stated
variable. Results go in `FINDINGS.md`, never here.

Phase 3B is an **optional, bounded follow-up** to Phase 3A. It is not a blocker
for Week 4 and it is not another general geometry bakeoff. Its purpose is:

> take specific ambiguities and failure modes actually exposed by Phase 3A, run
> the minimum experiment that isolates each one, and determine whether anything
> materially changes the provisional geometry architecture.

The provisional Phase 3A architecture, unchanged until this phase's evidence says
otherwise:

```text
MapAnything           dense range supplier
COLMAP / SIFT         sparse geometry + structural cross-check
```

**The candidate/experiment landscape below is FROZEN. No seventh hypothesis may
be created.** Wat3R-Ren remains a serious locally runnable underwater challenger;
Phase 3A did not establish that it is objectively inferior, and nothing here
reopens that.

---

## 0. The six hypotheses

| id | name | Phase 3A trigger |
|---|---|---|
| **3B-1** | correspondence attribution | A→B changed feature *and* matcher together; +17–75 % track length, no registration gain |
| **3B-2** | incremental vs global SfM | the pose / global-consistency hypothesis was left open because GLUEMAP is CUDA-only |
| **3B-3** | camera-model / self-calibration sensitivity | classical focal estimates vary 1042–1552 px between clips; radius-dependent disagreement was read as possible refraction |
| **3B-4** | temporal-baseline / triangulation sensitivity | 48 redundant video frames register 48/48 without establishing that depth is well conditioned |
| **3B-5** | weak-parallax specialist (**conditional**) | `wreck_01` near-planar, `wreck_05` low-texture, both unstable |
| **3B-6** | dynamic / temporally-global learned geometry | MapAnything on `wreck_03`: 6.64× fitted per-frame scale wander, 129.8 % range-dependent residual swing |

Execution order — cheap and high-attribution first:

```text
3B-1  →  3B-2  →  3B-3  →  3B-4  →  [3B-5 trigger check]  →  3B-6A  →  3B-6B
```

---

## 1. Preflight facts established before any experiment

These were established during the Phase 3B preflight and are what several of the
plans below depend on. Evidence is persisted in
`outputs/preflight/` (`colmap_capabilities.json`, `footage_capture_metadata.json`,
`candidate_preflight.json`).

### 1.1 The installed COLMAP binary

`COLMAP 4.1.1 (Commit Unknown on Unknown without CUDA)`, Homebrew `colmap 4.1.1_3`.

* **`global_mapper` is present** — so 3B-2's global-SfM axis is testable locally.
* **`view_graph_calibrator` is present** — so the focal-prior intervention is
  available, and can be run as a *separate* arm rather than confounded into the
  mapper result.
* **`LoMa` is absent.** `libcolmap_feature.dylib` exposes exactly `SIFT`,
  `ALIKED_N16ROT`, `ALIKED_N32` and matchers `SIFT_BRUTEFORCE`,
  `SIFT_LIGHTGLUE`, `ALIKED_BRUTEFORCE`, `ALIKED_LIGHTGLUE`; no `LOMA*` symbol
  exists in the build.
* COLMAP's newest **release** is 4.1.1 (2026-07-17) — the version installed — and
  its only official prebuilt binaries are `colmap-x64-windows-{cuda,nocuda}.zip`.
  There is no official prebuilt macOS ARM binary at any version.

### 1.2 The footage — what the camera metadata actually says

Parsed from each source `.MP4`'s `moov/udta` GoPro settings block (`FIRM`,
`LENS`, `CASN`, plus the embedded GPMF `Global Settings` device). This had never
been read before; Phase 3A assumed nothing about capture mode either way.

| clip | camera | serial `CASN` | lens `LINF` | `OREN` | `DZOM` | `VFOV` | `ZFOV` | `EISE` | `EISA` | `PRJT` |
|---|---|---|---|---|---|---|---|---|---|---|
| `wreck_07` | HERO9 Black | C3441326805381 | LKO1053001400918 | U | N | W | 105.383° | Y | HS Boost | GPRO |
| `wreck_05` | HERO9 Black | C3441326805381 | LKO1053001400918 | U | N | W | 105.383° | Y | HS Boost | GPRO |
| `wreck_01` | HERO9 Black | C3441326805381 | LKO1053001400918 | **R** | N | W | 105.383° | Y | HS Boost | GPRO |
| `wreck_03` | HERO9 Black | C3441326805381 | LKO1053001400918 | U | N | W | 105.383° | Y | HS Boost | GPRO |
| `swimthrough_02` | HERO9 Black | C3441326805381 | LKO1053001400918 | U | N | W | 105.383° | Y | HS Boost | GPRO |
| `cenote_01` | HERO9 Black | C3441326805381 | LKO1053001400918 | U | **Y** | W | **123.473°** | Y | **HS High** | GPRO |

Firmware `HD9.01.01.60.00` on all six.

Four consequences, and they change what 3B-3 is allowed to do:

1. **All six clips are one physical camera and one physical lens.** Same body
   serial, same lens serial, same firmware.
2. **Five of the six share an identical capture mode** — Wide, digital zoom off,
   HyperSmooth Boost, effective diagonal FOV 105.383°. Only `cenote_01` differs
   (digital zoom on, HyperSmooth High, 123.473°). So a shared-intrinsics
   assumption is *evidence-supported* for the five, and explicitly not for
   `cenote_01`.
3. **`wreck_01`'s portrait decode is `OREN = R` — a rotation flag, not different
   optics.** Its `VFOV`/`ZFOV` are identical to the other wrecks. The
   field-of-view asymmetry Phase 3A §3.5 found on that clip is a property of the
   *VGGT family's square 518×518 centre crop*, not of the footage. **For the
   classical arm there is therefore no field-of-view confound on `wreck_01`**,
   which is the precondition the plan sets for including it in 3B-3.
4. **Electronic image stabilisation is ON in every clip** (`EISE = Y`,
   HyperSmooth Boost/High), and the output projection is `PRJT = GPRO` — GoPro's
   own non-rectilinear wide projection, *not* a linearised/dewarped image. Two
   things follow: a fisheye-family challenger has genuine metadata support (this
   is a 105–123° diagonal non-rectilinear projection), and EIS is a real,
   previously unrecorded confound for every Phase 3A geometry number.

### 1.3 External candidates

| candidate | repository | licence | preflight verdict |
|---|---|---|---|
| LoMa | `davnords/LoMa`, integrated in COLMAP `main` | — | absent from every official release binary; source build of an alternate COLMAP tree is outside the integration budget |
| MP-SfM | `cvg/mpsfm`, Apache-2.0, last push 2025-07-09 | Apache-2.0 | `requirements.txt` pins **`cupy-cuda12x`** plus `mmcv` — CUDA-only and native |
| Any4D | `Any-4D/Any4D`, Apache-2.0 | Apache-2.0 | pure-PyTorch declared deps, `torch~=2.6.0`, encoder `dinov2_large` (so UniCeption's `curope` CUDA kernel is never on the path), device selector is one `cuda if available else cpu` line |
| VGGT-SLAM 2.0 | `MIT-SPARK/VGGT-SLAM` @ `35327ac` | see FINDINGS | `gtsam-develop` has macOS universal2 wheels; SAM 3 / Perception Encoder are `--run_os`-only. Multiple hardcoded CUDA sites; assessed at execution time against the one-adaptation budget |

---

## 2. 3B-1 — correspondence attribution

### Hypothesis

Phase 3A's A→B comparison changed **two** things at once — feature
representation (SIFT → ALIKED_N32) and matcher (brute force → LightGlue) — so the
+17–75 % mean-track-length gain cannot be attributed to either. The hypothesis is
that the track-length gain is attributable to one identifiable component, **and**
that longer tracks do not by themselves change the recovered scene shape.

### Experiment — clean 2×2 factorial, one binary, everything else fixed

|  | brute-force matcher | LightGlue matcher |
|---|---|---|
| **SIFT features** | **F1** `SIFT` + `SIFT_BRUTEFORCE` ( = Phase 3A **A**) | **F2** `SIFT` + `SIFT_LIGHTGLUE` |
| **ALIKED_N32 features** | **F3** `ALIKED_N32` + `ALIKED_BRUTEFORCE` | **F4** `ALIKED_N32` + `ALIKED_LIGHTGLUE` ( = Phase 3A **B**) |

F1→F2 is the matcher effect with features fixed; F3→F4 the same with ALIKED
fixed; F1→F3 and F2→F4 are the feature effect with the matcher family fixed.

Clips: **`wreck_05`** primary, **`wreck_01`** secondary, `wreck_07` control only
if a result is genuinely unexplained. F1 and F4 are **reused** from Phase 3A
`outputs/colmap/A|B/<clip>/run0` — not re-run. One bounded repeat of F2 and F3 on
`wreck_05` bounds the new configurations' run-to-run spread, because the claim
being tested is a *difference in track length* and A's own repeat spread on that
clip was 3.5 % in point count.

### Does this isolate the variable? — review

**Mostly, with one honest limitation that must be stated in the report.**

* Everything except the extractor/matcher type is literally identical: the same
  48 extracted PNGs, `SIMPLE_RADIAL`, `single_camera=1`, exhaustive matching,
  `multiple_models` at COLMAP's default, seed 0 on every stage, mapper pinned to
  one thread, CPU everywhere. The configurations are generated *from* the Phase
  3A `shared` block rather than retyped, so drift is impossible.
* **The limitation:** `SIFT_LIGHTGLUE` and `ALIKED_LIGHTGLUE` are different
  LightGlue ONNX weights, and `SIFT_BRUTEFORCE` and `ALIKED_BRUTEFORCE` compare
  different descriptors. The "matcher axis" is therefore *"nearest-neighbour
  matching vs the learned LightGlue matcher trained for that descriptor"*, not a
  single matcher applied to two descriptors. That is the strongest factorial the
  installed binary permits and the claim will be scoped to it.
* Reprojection error is recorded but **cannot rank anything** (Phase 3A §4.2).
* Longer tracks are not the endpoint. The decisive measurement is triangulation
  conditioning (per-point maximum triangulation angle, the baseline/depth proxy)
  and whether the **scale-aligned sparse shape** at co-visible image observations
  actually moves. If shape agrees after one clip-level scale, the track gain is
  classified *useful-but-not-architecture-changing*.

### LoMa sub-experiment — closed at preflight

**`not_practical`.** LoMa is absent from the installed COLMAP 4.1.1 build
(verified by symbol inspection), 4.1.1 is COLMAP's newest release, and its only
official prebuilt binaries are Windows x64. Reaching LoMa needs a source build of
an alternate COLMAP tree, which the Phase 3B integration budget forbids
explicitly. Branch terminated; no further troubleshooting. The 2×2 factorial is
and remains the primary 3B-1 experiment.

---

## 3. 3B-2 — incremental vs global SfM

### Hypothesis

Some Phase 3A pose/shape instability is a consequence of **incremental** SfM
rather than of the measurements themselves. GLUEMAP could not test this
(`pending_cuda`); the installed `global_mapper` can test the classical half of it
locally.

### Experiment

Three arms on the **same SIFT measurements**:

```text
A_incremental    Phase 3A A/run0                              (reused, not re-run)
A_global         global_mapper on a COPY of A's database
A_global_cal     view_graph_calibrator, then global_mapper, on a SEPARATE copy
```

The Phase 3A database is **never mutated**; each arm works on its own copy, and
the calibrator arm is separate precisely so a focal-length change cannot be
reported as a mapper effect.

Clips: `wreck_05`, `wreck_01`, `wreck_03`; `swimthrough_02` as an easy control.

**Calibrator fallback, strict.** If `view_graph_calibrator` fails on one ordinary
invocation — including because the databases carry `prior_focal_length = 0`, i.e.
no priors at all — record the omission and go straight to `global_mapper` on the
unmodified copy. No debugging, no fabricated focal priors, no second COLMAP
build, no parameter roulette.

### Does this isolate the variable? — review

**It isolates the *pipeline*, not a single algorithmic axis, and the report must
say so.** `mapper` and `global_mapper` differ in more than incremental-vs-global
registration: different triangulation thresholds, a different bundle-adjustment
schedule, rotation averaging plus global positioning instead of sequential
resection. What is genuinely held fixed is the **measurement set** — identical
features, identical matches, identical two-view geometries, identical images.
That is the meaningful control here, and it is exactly what GLUEMAP would also
have varied.

Reproducibility settings are pinned to match the Phase 3A instrument:
`--GlobalMapper.random_seed 0`, `--GlobalMapper.num_threads 1`,
`gp_use_gpu 0`, `ba_ceres_use_gpu 0`.

### Success condition

A global reconstruction matters **only** if it materially improves a named Phase
3A failure signature: weak triangulation, severe shape disagreement, temporal
scale instability, or fragmentation. A prettier trajectory is not a result.

---

## 4. 3B-3 — camera-model / self-calibration sensitivity

### Hypothesis

Before any radius-dependent dense-vs-sparse disagreement is attributed to learned
depth error or to refraction, determine whether ordinary COLMAP geometry is
itself sensitive to its central camera model and to self-calibration. This is
**not** a refraction experiment: it tests *central* camera-model complexity, not
flat-port non-central refraction.

Preflight §1.2 sharpens this into a much stronger statement than Phase 3A could
make. Five clips are **metadata-identical in optics and capture mode**, yet
Phase 3A's self-calibrated focal lengths on those five span **1042 → 1552 px**
(1.49×) at the same 1280 px extraction. Under the metadata, at most one of those
numbers can be right.

### Experiment

Copy A's database per clip, rewrite **only** the `cameras` row to the challenger
model — keeping COLMAP's own initialisation convention, `f₀ = 1.2 · max(w, h) =
1536`, `cx = w/2`, `cy = h/2`, distortion 0, exactly the values already in the
database — then run the **same** incremental mapper with the **same** settings and
seed.

| arm | model | parameters | role |
|---|---|---|---|
| `M_simple_radial` | `SIMPLE_RADIAL` | f, cx, cy, k | **control** — must reproduce Phase 3A A; validates the database-rewrite path |
| `M_radial` | `RADIAL` | f, cx, cy, k1, k2 | one more radial term |
| `M_opencv` | `OPENCV` | fx, fy, cx, cy, k1, k2, p1, p2 | separate focals + tangential |
| `M_simple_radial_fisheye` | `SIMPLE_RADIAL_FISHEYE` | f, cx, cy, k | **projection family**, at identical parameter count to the control |

`FULL_OPENCV` is deliberately not run. Exactly **one** fisheye model is run, and
it is the one whose parameter count matches the control, so the comparison is
projection-family rather than parameter-count. Its justification is metadata, not
"it's a GoPro": `PRJT = GPRO` at a 105.4° diagonal field of view is a
non-rectilinear wide projection, not an already-dewarped image.

Clips: `wreck_07` (well-conditioned control), `wreck_05` (weak/anomalous),
`swimthrough_02` (realism), and **`wreck_01` — now included**, because preflight
§1.2(3) establishes its portrait decode is a rotation flag with an identical
field of view, so the confound the plan guarded against does not exist for the
classical arm.

### Optional fixed-intrinsics test — now evidence-supported

Because five clips are metadata-identical, take the intrinsics self-calibrated on
the **strongest** clip (`wreck_07`: 48/48 registered, 11 197 points, highest
texture) and re-run the two weak clips with those intrinsics **fixed**
(`ba_refine_focal_length 0`, `ba_refine_extra_params 0`). For `wreck_01` the same
physical focal transfers directly in pixels and only the principal point swaps,
because the rotation is a decode flag. **Diagnostic only** — it tests whether the
weak clips' focals are a self-calibration artefact, and it cannot establish that
either value is physically correct.

### Does this isolate the variable? — review

**Yes, more tightly than re-extraction would.** Rewriting one row of a copied
database holds the extracted frames, the SIFT keypoints, the descriptors, the
matches and the two-view geometries **literally byte-identical**; re-running
`feature_extractor` with a different `--ImageReader.camera_model` would have
re-run multithreaded matching and reintroduced exactly the nondeterminism Phase
3A had to measure. The `M_simple_radial` control arm exists to prove the rewrite
path is inert: it must reproduce Phase 3A's A within A's own measured repeat
spread, and if it does not, every other arm in 3B-3 is void.

Reprojection error may be inspected and cannot select a winner — a more flexible
camera model reaching lower reprojection error establishes nothing. No central
model will be called physically correct: there is no independent calibration.

---

## 5. 3B-4 — temporal-baseline / triangulation sensitivity

### Hypothesis

Successful registration does not establish well-conditioned triangulation. Video
contains many near-duplicate frames with tiny baselines. If the classical
reconstruction is materially unchanged when 48 observations are replaced by
roughly half and roughly a quarter of them **spanning the same temporal extent**,
then weak temporal baseline is unlikely to explain Phase 3A's large shape
disagreement.

### Experiment

Nested deterministic schedules over the existing 48 extracted frames — no
re-extraction, identical pixels, images provided by symlink:

```text
S48   all 48                                      indices 0..47
S25   every 2nd, plus the last                    {0,2,4,...,46} ∪ {47}
S13   every 4th, plus the last                    {0,4,8,...,44} ∪ {47}
S13 ⊂ S25 ⊂ S48,  and all three share both endpoints
```

They are named for their true sizes (25 and 13, not 24 and 12) because exact
nesting and exact temporal extent were preferred over round numbers: nesting is
what makes the shape comparison possible at *shared* observations, and preserving
both endpoints is what keeps temporal extent identical.

Method: ordinary configuration **A** — SIFT, brute force, incremental — with no
other parameter changed. Clips: `wreck_05`, `wreck_01`, plus `cenote_01` (59.94
fps, so its 48 frames span only ~6 s, the most redundant sampling in the set).

### Does this isolate the variable? — review

**Yes.** The only variable is which subset of already-extracted frames the
pipeline sees. Frame count and temporal spacing move together by construction —
that is intrinsic to the question, not a confound, because the question is
whether *fewer, wider-spaced* views over the same span reconstruct differently.
One thing must not be over-read: the number of matching pairs falls
quadratically (1128 → 300 → 78), so any conditioning change is a joint effect of
sparser sampling and fewer constraints, and the report will say so.

Three outcomes are all informative: stable across schedules (weak baseline does
not explain the Phase 3A disagreement); better with fewer wider-spaced frames
(the video sampling contributes conditioning error); worse (dense temporal
overlap is helping despite small neighbouring baselines).

---

## 6. 3B-5 — weak-parallax / near-planar specialist (CONDITIONAL)

**Not run by default.** The trigger is read only *after* 3B-2, 3B-3 and 3B-4 have
reported: 3B-5 runs only if those leave a concrete residual hypothesis that weak
triangulation or planar structure is materially affecting `wreck_01` or
`wreck_05`. If the cheaper experiments already explain the instability, the
classification is `not_triggered` and no further method is run.

Challenger, if triggered: the predeclared **MP-SfM** (`cvg/mpsfm`, Apache-2.0),
official implementation only. No hand reimplementation, no adjacent substitute,
no new weak-parallax survey. Clips `wreck_01` and `wreck_05` only.

Preflight already records that its `requirements.txt` pins `cupy-cuda12x` and
`mmcv`. That is recorded now so the trigger check is honest about what would
follow, and it does not pre-empt the trigger check itself.

### The trigger rule, pre-registered before 3B-2/3/4 report

Written now, while the outcome is unknown, so the decision cannot be
reverse-engineered from whichever answer is convenient.

**3B-5 is TRIGGERED if all three hold**, on `wreck_01` or `wreck_05`:

1. **3B-4 shows real conditioning sensitivity.** The scale-aligned shape between
   frame schedules disagrees by more than the restoration-relevance threshold
   (> ~5 % median, or a range swing above ~10 %), *and* that disagreement tracks
   the triangulation-angle distribution rather than merely the point count.
2. **3B-3 does not explain it.** The camera-model arms and the fixed-intrinsics
   diagnostic leave the clip's instability substantially in place — i.e. the
   anomaly is not simply a focal/distortion self-calibration degeneracy.
3. **3B-2 does not repair it.** The global mapper leaves the same instability,
   so it is not an artefact of incremental registration order.

**3B-5 is `not_triggered` if any one of those fails** — most obviously if 3B-3's
fixed-intrinsics arm collapses the anomaly, which would make the story
"self-calibration degeneracy", not "weak parallax".

**The trigger decision and the practicality verdict are separate results and are
reported separately.** If the trigger fires, the classification is whatever the
practicality assessment then yields (on current preflight evidence,
`not_practical_local`); if it does not fire, the classification is
`not_triggered` and practicality is moot. Neither is allowed to stand in for the
other.

---

## 7. 3B-6 — dynamic and temporally-global learned geometry

The Phase 3A trigger is **`wreck_03`**, where MapAnything shows ≈ **6.64×** fitted
per-frame scale wander against A and a **129.8 %** range-dependent residual swing
— the worst figures anywhere in Phase 3A — on a clip with a large moving diver,
exhaust bubbles and haze.

Two subquestions, strict execution order, and **not** a model leaderboard.

### Mandatory native-extension hard stop (applies to both)

If evaluating a candidate requires compiling a candidate-specific C++/CUDA
extension, custom PyTorch operator, correlation volume, `lietorch`, spatial
hashing, or any native extension driven by `setup.py`/CMake on this Mac:
**abort immediately**, classify `not_practical_local`, stop that candidate. No
waiting on clang, no patching native source, no CUDA→Metal porting, no rewriting
a native operator in Python, no substituting a different implementation of a core
algorithmic component. Ordinary prebuilt wheels and pure-Python dependencies are
fine. The purpose is to evaluate released methods, not to perform a macOS port.

### 3B-6A — Any4D

`Any-4D/Any4D`, Apache-2.0. Relevant because its research target is explicitly
dynamic/4D geometry from RGB video, and because it is built on the MapAnything /
UniCeption stack that already runs on MPS in this project — so a *negative*
result cannot be blamed on an unfamiliar harness.

Primary clip `wreck_03`; `swimthrough_02` as an easy control if it runs.

Budget: at most **one trivial device-selection change** (`cuda|cpu` →
`cuda|mps|cpu`, including the same script's hardcoded `device="cuda"` strings,
and float32 instead of AMP as Phase 3A did for every dense model). No kernel
porting, no component replacement, no attention or scene-flow surgery. If a
required core operation is unsupported on MPS: `not_practical_local`, stop. A
tiny CPU smoke test to establish semantics is permitted; a prohibitively long CPU
evaluation to "claim the model ran" is not.

Before any score: native depth/range definition, metric-scale semantics, camera
pose semantics, dynamic-point/scene-flow semantics, reference-frame semantics,
mask semantics, whether geometry is per-time or static-world, crop/resize
mapping, invalid values, confidence.

**Success bar.** The MapAnything failure is enormous. A few-percent numerical
difference is not a result. Any4D matters only if it *materially repairs the
dynamic failure signature*.

### 3B-6B — VGGT-SLAM 2.0

`MIT-SPARK/VGGT-SLAM` @ `35327ac`. Relevant because it targets sequence-level
geometric consistency and drift rather than independent feed-forward per-frame
geometry — which maps onto both the learned scale instability and the
near-planar weak-geometry concern, and gives a local test of a global-consistency
hypothesis GLUEMAP could not answer here.

Clips `wreck_01` (planar/weak) and `wreck_03` (dynamic/unstable);
`swimthrough_02` optional control.

**Licensing is recorded separately for code and checkpoint.** The ordinary
VGGT-1B experimental checkpoint remains non-commercial, so even a successful
result may be *experimental evidence* rather than *deployable architecture*.

**Attribution rule.** VGGT-SLAM is **not** automatically a clean
"VGGT → global optimiser" ablation. Its VGGT implementation is a fork
(`MIT-SPARK/VGGT_SPARK`), and its preprocessing, frame sampling, heads and camera
handling must be compared against E0 before any output difference is attributed
to global alignment. Every difference gets recorded.

The same hard stop and the same one-adaptation budget apply.

---

## 8. CUDA-reference systems — recorded, not ported

**MegaSaM**, **WildPose**, **MonST3R** are scientifically relevant and are **not**
local execution targets. They are candidate accounting only, and they do **not**
count as additional Phase 3B experiments. No MPS ports, no xformers surgery, no
CUDA kernel compilation, no forcing a ~23 GB VRAM workload through unified
memory, and no cloud GPU rental in this phase.

---

## 9. Comparison invariants inherited from Phase 3A — not renegotiable

* **Scale.** Exactly **one global scale per method-pair per clip**, fitted over
  observations pooled across every frame. Per-frame fitted scales are *diagnostics
  only* and are never fed back into a residual. No local scaling, no per-region
  normalisation, no nonlinear remapping, no local warp.
* **Correspondence.** Dense-vs-sparse samples the dense field **at the actual
  image observations belonging to the sparse geometry**. Sparse-vs-sparse matches
  observations **within the same image** by 2D proximity. A 3D nearest neighbour
  between two independently-posed clouds is never a correspondence.
* **Geometry semantics.** `z_depth`, `ray_range` and water path length are never
  conflated. Every stored field is `range_along_ray` with
  `path_source = "ray_range_approx_water_path"`. **Any new conversion requires a
  synthetic unit test.**
* **Validity.** Masks, NaNs, non-positive ranges, crops, FOV, resolution and
  confidence stay explicit. Invalid geometry is never silently filled.
* **Epistemology.** None of SIFT COLMAP, global COLMAP, MapAnything, VGGT,
  Wat3R-Ren, Any4D, VGGT-SLAM or an MP-SfM challenger is ground truth. Agreement
  is **consistency**. Reprojection error is diagnostic. A method moving closer to
  COLMAP has not been shown to be more correct. Objective-accuracy claims remain
  impossible without independent truth (C2).

## 10. Phase 3A facts that are not reopened

Wat3R-Ren remains a legitimate candidate with a condition-dependent adaptation
effect. Refractive COLMAP `C_on` stays retired as a measurement reference and
**no second refractive solver is added**. Water-VGGT's distributed geometry
checkpoint is bitwise vanilla VGGT-1B and is not revisited; its released pipeline
still preprocesses images before vanilla VGGT, so it is not claimed to equal E0
numerically. SeaVGGT and WAT3R-Xu have no runnable release and are not revisited.
GLUEMAP and AMB3R remain `pending_cuda`.

---

## 11. Classifications and the architecture-change bar

Every hypothesis finishes in exactly one of:

| classification | meaning |
|---|---|
| `failure_repaired` | large, repeatable, attributable, restoration-relevant repair of the named failure |
| `interesting_but_not_material` | a real effect, but too small / costly / fragile / licence-constrained / narrow |
| `failure_not_repaired` | ran faithfully, did not improve the targeted failure |
| `not_practical` | faithful evaluation impossible inside the integration/dependency budget |
| `not_practical_local` | viable elsewhere; faithful local execution would need unsupported hardware, native compilation or substantial porting |
| `not_triggered` | a conditional experiment rendered unnecessary by earlier Phase 3B evidence |
| `not_identifiable` | without independent truth the hypothesis cannot be adjudicated |

`not_identifiable` is **never** translated into "run another model".

A 3B result may change the architecture only with evidence that is
simultaneously **large, repeatable, specifically attributable,
restoration-relevant and practically deployable**. Things that do not clear the
bar: longer tracks alone; more points alone; lower reprojection error; smoother
visualisation; agreement with another uncalibrated method; a tiny residual
reduction; a CUDA-only method being slightly better; a non-commercial checkpoint
being slightly better; a method needing a large new permanent stack for one edge
case. A specialist that fixes only one recognised failure regime may be adopted
as a **conditional fallback**, not as the default.

## 12. Restoration relevance — the standing budget

Reused from Phase 3A §8, not re-derived. Global scale is largely absorbable while
water coefficients are fitted within a clip; the dangerous component is
**spatially / range-dependent shape error**:

```text
local range error  < ~5 %    usually small at ordinary clear/coastal reef ranges
                   5-10 %    increasingly relevant
                   > ~10 %   potentially restoration-significant
```

The sub-percent tolerances found at extreme distance in turbid water do **not**
imply geometry must be sub-percent accurate — they identify an ill-conditioned
inversion regime whose correct answer is a minimum-transmission /
maximum-corrective-gain limit and abstention, not an impossible geometry target.

For every Phase 3B effect the closing question is: **is this improvement large
enough to change downstream physical restoration?** If not, it may be
scientifically interesting and operationally irrelevant.

---

## 13. Scope freeze

Six hypotheses. Named clips only. No full six-clip sweep except where existing
Phase 3A outputs are simply reused. One bounded repeat where reproducibility
genuinely matters. No new candidate search, no new acquisition, no CUDA rental,
no restoration, no Week 4 work, no substantial upstream porting, no generic
geometry framework. A blocked method is classified, documented, and left.

**No seventh hypothesis may be created.**

---

## 14. Erratum (added 2026-09-01, after execution)

This file is the **pre-registration** and its body is deliberately left as
written, so the record of what was believed before running stays intact. One
statement in it is wrong and one has been overtaken; both are corrected in
`FINDINGS.md` §1.1 and recorded here.

1. **Wrong when written.** §1.1 and §1.3 state that "there is no official
   prebuilt macOS ARM binary at any version" of COLMAP. That is false: Homebrew
   publishes `arm64_sonoma` / `arm64_sequoia` / `arm64_tahoe` bottles for COLMAP,
   which is exactly how the binary used throughout Weeks 3A and 3B was installed.
2. **Overtaken during finalisation.** §1.1 states that COLMAP's newest release is
   4.1.1. Upstream **4.2.0** was released 2026-09-01T05:44Z, adding LoMa
   (`LOMA_B`, `LOMA_B128`, brute-force and dedicated matcher variants) and the
   first official `colmap-arm64-macos.zip`. Homebrew stable remains 4.1.1_3.

**The LoMa decision is unchanged, but its scope is now stated correctly.** The
Phase 3B execution environment was frozen on Homebrew COLMAP 4.1.1_3, which does
not expose LoMa; changing the COLMAP version mid-phase would have created a new
environment and broken comparability with the Phase 3A runs that used the same
binary. So LoMa is `not_practical` **for Phase 3B as executed** — an
environment-scoped decision, not a claim that LoMa is unreachable. A future phase
can test it by adopting 4.2.0 as its frozen environment.
