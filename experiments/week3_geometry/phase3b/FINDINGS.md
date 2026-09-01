# Week 3 Phase 3B — targeted geometry failure analysis

**Status: complete.** All quantitative result tables and quoted metrics are
generated from `outputs/analysis/analysis.json` via `scripts/tables_3b.py`; the
prose interpretation is written against those generated results. `PHASE3B.md`
holds the pre-registered hypotheses and the isolation review written before any
run.

---

## 0. What this phase is, and what it is not

Phase 3A selected a provisional architecture:

```text
MapAnything           dense range supplier
COLMAP / SIFT         sparse geometry + structural cross-check
```

Phase 3B is a bounded follow-up that takes six specific ambiguities Phase 3A
actually exposed, runs the minimum experiment that isolates each, and asks
whether anything materially changes that architecture. It is **not** a search for
a better general-purpose geometry model, not another literature review, and not a
re-run of the Phase 3A matrix.

**Read this first, exactly as in Phase 3A.** There is still **no independent
range measurement anywhere in Week 3.** The C2 scale-and-range acquisition
`PLAN.md` specifies does not exist. Every cross-arm number below is therefore a
**consistency** statement and never a correctness one. Sparse SfM is not the
ruler — it is one of the candidates under test.

---

## 1. Preflight — three things established before any experiment ran

### 1.1 The installed COLMAP exposes two of the three things Phase 3B needs

`COLMAP 4.1.1 (Commit Unknown on Unknown without CUDA)`, Homebrew `colmap 4.1.1_3`.
Verified by inspecting the binary, not by reading documentation
(`outputs/preflight/colmap_capabilities.json`).

| capability | present | consequence |
|---|---|---|
| `global_mapper` | **yes** | 3B-2's global-SfM axis is testable locally, on configuration A's own measurements. The pose/global-consistency hypothesis GLUEMAP could not answer here is at least partly reachable. |
| `view_graph_calibrator` | **yes** | the focal-prior intervention can be run as a *separate* arm, so a calibration effect cannot be reported as a mapper effect |
| `LoMa` | **no** | `libcolmap_feature.dylib` exposes exactly `SIFT`, `ALIKED_N16ROT`, `ALIKED_N32` and matchers `SIFT_BRUTEFORCE`, `SIFT_LIGHTGLUE`, `ALIKED_BRUTEFORCE`, `ALIKED_LIGHTGLUE`; no `LOMA*` symbol exists |

**On LoMa, and a correction the world forced during finalisation.** The Phase 3B
execution environment was Homebrew COLMAP **4.1.1_3**, which does not expose
LoMa. While this report was being written, upstream COLMAP **4.2.0** was released
(2026-09-01T05:44Z) and its notes add *"LoMa learned feature extraction and
matching through ONNX, including `LOMA_B` and `LOMA_B128` descriptors,
brute-force matching, and multiple dedicated matcher variants"*. Homebrew stable
remains 4.1.1_3 as of 2026-09-01. Changing the frozen COLMAP version mid-phase
would create a new environment, so **LoMa remains `not_practical` for Phase 3B as
executed** — the decision is unchanged, but the reason is now "the frozen
environment predates it", not "it is unreachable".

**One line of the original justification was simply wrong and is withdrawn.** The
preflight recorded that "there is no official prebuilt macOS ARM binary at any
version". That was false when written: Homebrew publishes `arm64_sonoma`,
`arm64_sequoia` and `arm64_tahoe` bottles for COLMAP — which is exactly how the
binary used throughout Weeks 3A and 3B was installed — and 4.2.0 additionally
ships an official `colmap-arm64-macos.zip` asset. Nothing downstream depended on
that sentence, but it should not have been written.

### 1.2 The footage's own camera metadata — read for the first time

Phase 3A assumed nothing about capture mode in either direction. Phase 3B read
it, because 3B-3 is forbidden from assuming that all GoPro footage shares one
calibration and forbidden from running a fisheye challenger merely because the
camera is a GoPro. Parsed from each source `.MP4`'s `moov/udta` GoPro block and
its embedded GPMF `Global Settings` device
(`outputs/preflight/footage_capture_metadata.json`).

| clip | camera | body serial | lens serial | `OREN` | `DZOM` | `VFOV` | `ZFOV` | `EISE` | `EISA` | `PRJT` |
|---|---|---|---|---|---|---|---|---|---|---|
| `wreck_07` | HERO9 Black | C3441326805381 | LKO1053001400918 | U | N | W | 105.383° | Y | HS Boost | GPRO |
| `wreck_05` | HERO9 Black | C3441326805381 | LKO1053001400918 | U | N | W | 105.383° | Y | HS Boost | GPRO |
| `wreck_01` | HERO9 Black | C3441326805381 | LKO1053001400918 | **R** | N | W | 105.383° | Y | HS Boost | GPRO |
| `wreck_03` | HERO9 Black | C3441326805381 | LKO1053001400918 | U | N | W | 105.383° | Y | HS Boost | GPRO |
| `swimthrough_02` | HERO9 Black | C3441326805381 | LKO1053001400918 | U | N | W | 105.383° | Y | HS Boost | GPRO |
| `cenote_01` | HERO9 Black | C3441326805381 | LKO1053001400918 | U | **Y** | W | **123.473°** | Y | **HS High** | GPRO |

Firmware `HD9.01.01.60.00` on all six. Four consequences, and they change what
the rest of the phase is allowed to claim.

**(a) All six clips are one physical camera and one physical lens.** Same body
serial, same lens serial, same firmware.

**(b) Five of the six share an identical capture mode.** Wide, digital zoom off,
HyperSmooth Boost, effective diagonal field of view 105.383°. Only `cenote_01`
differs — digital zoom on, HyperSmooth High, 123.473° — which is consistent with
its lower stabilisation crop. So a shared-intrinsics assumption is
**metadata-supported** for the five and explicitly not for `cenote_01`. This is
what licenses 3B-3's optional fixed-intrinsics diagnostic; without it the test
would have been manufacturing a cross-clip assumption from convenience.

**(c) `wreck_01`'s portrait decode is an orientation flag, not different optics.**
`OREN = R` with identical `VFOV` and `ZFOV`. The 44 % vertical field-of-view loss
Phase 3A §3.5 found on that clip is a property of the **VGGT family's square
518×518 centre crop** — a model preprocessing artefact — not of the footage. For
the classical arm there is therefore **no field-of-view confound on `wreck_01`**,
which is exactly the precondition `PHASE3B.md` set for including it in 3B-3.

**(d) Electronic image stabilisation is ON in every clip, and the lens
projection is identified but not reconstructed.** `EISE = Y` with HyperSmooth
Boost (or High), Wide FOV, and `PRJT = GPRO` — GoPro's own lens-projection
identifier. Two things follow, and both are narrower than they first look.

*On the projection:* the metadata identifies GoPro's GPRO lens projection, the
Wide FOV setting and a 105–123° diagonal field of view. That is enough to justify
**testing** a fisheye-family central model rather than assuming a radial one —
which is what 3B-3 does — but `PRJT = GPRO` **alone does not reconstruct the
output projection**. GoPro represents the detailed distortion separately (`POLY`,
`ZMPL` and related keys), which this preflight did not read, so nothing here
establishes that the delivered image is non-rectilinear or un-dewarped.

*On stabilisation:* **EIS is a previously unrecorded potential geometry
confound.** Its presence is established; its actual geometric impact is not.
HyperSmooth reprojects each frame toward a stabilised virtual camera, so the pose
SfM recovers is that virtual camera's, and whether one fixed intrinsic set
describes a clip depends on whether GoPro implements this as a rotation into a
*fixed* virtual camera or as something with a moving effective principal point.
Nothing in this phase can settle which, and no result below is attributed to it.

### 1.3 External candidates

Full provenance in `configs/candidate_preflight.json`.

| candidate | repository / commit | code licence | checkpoint licence | preflight verdict |
|---|---|---|---|---|
| LoMa | in COLMAP `main`, not in any release binary | — | — | `not_practical` (see §1.1) |
| MP-SfM | `cvg/mpsfm`, pushed 2025-07-09 | Apache-2.0 | — | pins `cupy-cuda12x` (CUDA-only) and `mmcv` (native) |
| Any4D | `Any-4D/Any4D` @ `aa9f1b0d` (2025-12-08) | Apache-2.0 | **not stated** | pure-PyTorch declared deps; `curope` CUDA kernel exists in its UniCeption fork but the model config selects `dinov2_large`, so it is never on the inference path — **passes the native-extension hard stop** |
| VGGT-SLAM 2.0 | `MIT-SPARK/VGGT-SLAM` @ `35327ac` (2026-06-29) | BSD-2-Clause | VGGT-1B: **non-commercial** | `gtsam-develop` has macOS wheels; SAM 3 / Perception Encoder are `--run_os`-only; assessed against the device budget at execution time |

Two licence facts that matter for the architecture bar before any number is
measured:

* **The Any4D checkpoint declares no licence at all.** The Hugging Face repo
  `airlabshare/any4d-checkpoint` has no licence field and no licence file. A
  public artifact with no stated terms is not an open-source licence — the same
  finding Phase 3A recorded for AMB3R — so Any4D stays strictly experimental
  regardless of how well it performs.
* **VGGT-SLAM loads `facebook/VGGT-1B`**, the non-commercial checkpoint Phase 3A
  already disqualified as a default. A good result there would be experimental
  evidence, not a deployable architecture.

---

## 2. Method and comparison invariants

Every Phase 3A invariant is inherited unchanged and is enforced in code
(`phase3b/scripts/sparse_metrics.py`, `phase3b/scripts/analyze.py`):

* **One global scale per method-pair per clip**, fitted over observations pooled
  across every frame. Per-frame fitted scales are computed and reported as a
  **drift diagnostic only** and are never fed back into a residual. No local
  scaling, no per-region normalisation, no nonlinear remapping, no local warp.
* **Correspondence by image observation.** Sparse-vs-sparse pairs observations
  within the same image by 2D proximity (≤ 1 px); dense-vs-sparse samples the
  dense field at the classical reconstruction's own observations through the
  *measured* source→grid affine map. A 3D nearest neighbour between two
  independently-posed clouds is never treated as a correspondence.
* **Trajectory comparison uses exactly one similarity** (rotation, translation,
  scale) over the camera centres of shared frames, with the residual normalised
  by the trajectory's own extent, because the gauge is arbitrary.
* **`range_along_ray` everywhere**, with `path_source =
  "ray_range_approx_water_path"`. z-depth, ray range and water path length are
  never conflated.
* **Reprojection error is diagnostic.** A more flexible camera model reaching a
  lower reprojection error has not been shown to produce better geometry.
* **Nothing is ground truth.** Agreement between two arms is consistency.

### 2.1 New quantities, and why each is unit-tested

Phase 3B computes four things Phase 3A did not, and a silent error in any of them
would be indistinguishable from a real effect. All are tested against synthetic
geometry with an analytically known answer, each with a falsification element
(`tests/test_week3_phase3b.py`, 12 tests):

| quantity | definition | why it exists |
|---|---|---|
| triangulation angle | the **largest** angle subtended at a 3D point by any two observing camera centres | registration says the cameras can be related; this says whether depth is observable. Forty cameras in nearly the same place are one observation, however long the track |
| baseline / depth | max pairwise baseline over the track's median range | the same conditioning fact in a linear unit |
| track temporal span | max − min **source** frame index over the track | a track seen in twenty consecutive frames of a 60 fps clip is not the evidence a track spanning the whole sweep is |
| trajectory residual | Umeyama similarity over shared camera centres, normalised by extent | 3B-2 asks whether the poses move; two gauges cannot be compared without it |

### 2.2 How the classical arms were kept honest

* **3B-1** generates its configurations *from* Phase 3A's `shared` settings block
  rather than retyping it, and records the source file's sha256, so drift is
  impossible.
* **3B-2 and 3B-3** never re-extract or re-match. They start at the mapper on a
  **copy** of Phase 3A configuration A's own database, so keypoints, descriptors,
  putative matches and two-view geometries are byte-identical across arms. The
  Phase 3A database is opened read-only and never written.
* **3B-3's camera-model rewrite is validated, not trusted.** Every arm asserts
  that the model name COLMAP wrote into `cameras.txt` equals the one requested,
  and a `SIMPLE_RADIAL` control arm runs through the identical rewrite path and
  must reproduce Phase 3A configuration A. If it does not, every other 3B-3 arm
  is void.
* **All arms start from the same camera initialisation.** COLMAP's own
  convention, read out of the source database: `f₀ = 1.2·max(w,h) = 1536`,
  principal point at the image centre, distortion zero, focal repeated for
  two-focal models. No arm gets a different starting guess, so a difference
  between arms is the camera model and not the initialisation.
* **`Mapper.ba_refine_principal_point` stays at COLMAP's default (off)** in every
  3B-3 arm, so the principal point is a fixed quantity in all of them and the
  only varying parameters are focal and distortion. That is deliberate: enabling
  it would have added a second variable.
* **3B-4 re-uses the identical extracted PNGs** through symlinks; the frame
  subset is the only thing that changes.

---

## 3. 3B-1 — correspondence attribution

**Phase 3A trigger.** Configuration B (ALIKED_N32 + ALIKED LightGlue) did not
improve registration over configuration A (SIFT + SIFT brute force), but raised
mean track length on every clip by **+17 % to +75 %**, usually with fewer points
and always at substantially higher cost. A→B changes the **feature
representation** and the **matcher** simultaneously, so Phase 3A could not
attribute that gain.

**Hypothesis.** The track-length gain is attributable to one identifiable
component; and longer tracks do not by themselves change the recovered scene
shape.

**Experiment.** A 2×2 factorial inside one binary, with the same 48 extracted
PNGs, `SIMPLE_RADIAL`, `single_camera=1`, exhaustive matching, seed 0, mapper
pinned to one thread and CPU everywhere. F1 (= Phase 3A A) and F4 (= Phase 3A B)
are reused, not re-run; F2 and F3 fill the missing cells. The configurations are
generated *from* Phase 3A's `shared` block (sha256 recorded), so drift is
impossible.

|  | brute-force matcher | LightGlue matcher |
|---|---|---|
| **SIFT features** | **F1** = Phase 3A **A** | **F2** |
| **ALIKED_N32 features** | **F3** | **F4** = Phase 3A **B** |

### 3.1 The attribution: it is the matcher, not the features

Mean track length, and what happens to registration, on the two clips:

| axis | held fixed | `wreck_05` track | `wreck_01` track | registration |
|---|---|---|---|---|
| brute force → LightGlue | SIFT | 5.91 → **8.96** (+51.5 %) | 7.79 → **11.01** (+41.3 %) | 48/48 → 48/48; 46/48 → **47/48** |
| brute force → LightGlue | ALIKED | 6.60 → 8.25 (+25.0 %) | 8.79 → 9.14 (+4.0 %) | **32/48 → 48/48**; **26/48 → 44/48** |
| SIFT → ALIKED | brute force | 5.91 → 6.60 (+11.7 %) | 7.79 → 8.79 (+12.8 %) | **48/48 → 32/48**; **46/48 → 26/48** |
| SIFT → ALIKED | LightGlue | 8.96 → **8.25 (−7.9 %)** | 11.01 → **9.14 (−16.9 %)** | 48/48 → 48/48; 47/48 → 44/48 |

> **Most of Phase 3A's track-length gain is attributable to replacing brute-force
> matching with the descriptor-specific LightGlue matcher, not to switching SIFT
> features for ALIKED.** With the matcher held at LightGlue, swapping SIFT for
> ALIKED *shortens* tracks on both clips; with the matcher held at brute force,
> ALIKED collapses registration to 32/48 and 26/48. The single worst configuration
> tested is ALIKED + brute force — a combination Phase 3A never ran, and the one
> that shows its ALIKED result depended on LightGlue.

Stated precisely, because the row and column effects are not symmetric: **ALIKED
does not explain the Phase 3A track-length gain and degrades registration in the
tested pairings.** It is not inert — under brute force it *raises* mean track
length by 11.7 % and 12.8 % — but it does so while losing 16 and 20 registered
frames, and under LightGlue it is strictly behind SIFT on both axes.

Triangulation conditioning moves on the same axis. On `wreck_05`, median
triangulation angle 5.37° → **7.03°** and baseline/depth 0.140 → 0.180 across
F1→F2, while tracks spanning ≥ 25 % of the clip go 33.3 % → **62.8 %**. Across
F1→F3 (the feature axis) the angle *falls* to 4.87° and the fraction of points
below 2° more than doubles, to 10.5 %.

Cost is also the matcher, not the features: F3 (ALIKED + brute force) runs in
**33 s** against configuration A's 37 s, while F2 costs 357 s and F4 673 s on
`wreck_05`, and 1 302 s / 306 s on `wreck_01`. SIFT + LightGlue is the most
expensive cell precisely because SIFT emits ~2 000 keypoints per image against
ALIKED's ~900.

### 3.2 Do longer tracks change the recovered shape? On this clip, yes — and that is not good news

Scale-aligned range residual at co-visible image observations, `wreck_05`, one
global scale per pair:

| pair | matched obs | fitted s | median | p95 | range swing | trajectory RMSE / extent |
|---|---|---|---|---|---|---|
| F1 → F2 (matcher axis) | 13 293 | 1.276 | **10.8 %** | 43.4 % | **46.3 %** | 19.1 % |
| F3 → F4 (matcher axis) | 5 468 | 0.738 | 29.3 % | 63.6 % | 104.1 % | 21.6 % |
| F1 → F4 (= Phase 3A A vs B) | 83 | 1.242 | 12.9 % | 56.8 % | — | 14.8 % |

**The cross-feature comparisons are not usable and are reported as such.** SIFT
and ALIKED detect at different pixels, so the ≤ 1 px within-image observation
match finds only 36–150 correspondences on `wreck_05`, against 5 468–13 293 for
the within-feature pairs. The matcher axis — the one this hypothesis is about —
is exactly the well-populated one; the feature axis is not, and no shape
conclusion is drawn from it.

### 3.3 The noise floor, measured for the first time

Phase 3A bounded configuration A's run-to-run spread in *registration* and
*point count* and said explicitly that the shape spread was not obtainable that
way. It is obtainable, and it is large where it matters. Identical settings,
identical seed, whole pipeline re-run:

| clip / arm | median | p95 | range swing | registration | points |
|---|---|---|---|---|---|
| `wreck_07` A run0 vs run1 | **0.01 %** | 0.32 % | 0.03 % | 48, 48 | 11 197, 11 206 |
| `wreck_05` F1 run0 vs run1 | **3.34 %** | 12.90 % | **6.70 %** | 48, 48 | 2 942, 2 838 |
| `wreck_05` F2 run0 vs run1 | 2.09 % | 8.91 % | 7.91 % | 48, 48 | 3 218, 3 287 |
| `wreck_05` F3 run0 vs run1 | 6.52 % | 13.02 % | 19.12 % | **32, 38** | 1 029, 1 247 |

The mechanism is identifiable. Both `wreck_05` runs extracted the **identical
52 745 keypoints**; they differ by **29 verified matches out of 65 756** (0.04 %),
which is the multithreaded geometric-verification stage Phase 3A deliberately
left unpinned. On `wreck_07` the same pipeline differs by 4 verified matches out
of 352 999 and the resulting geometry differs by 0.01 %.

> A 0.04 % perturbation of the correspondences moves `wreck_05`'s recovered range
> field by 3.3 % median and 6.7 % range swing — into the restoration-relevant
> band — while `wreck_07` absorbs a perturbation of the same kind entirely. This
> completes limitation #8 of the Phase 3A report in the units that actually
> decide something, and it reframes every `wreck_05` number in Phase 3A §7.2:
> those dense-vs-A residuals are measured against a reference whose own repeat
> noise on that clip is 3.3 % median and 6.7 % range swing.

Against that floor, the F1→F2 shape change (10.8 % median, 46.3 % range swing) is
**~3× the noise in median and ~6× in range swing** — a real effect.

### 3.4 Classification

**`interesting_but_not_material`.**

The attribution is clean and it is worth keeping: the correspondence gain Phase
3A observed is mostly LightGlue's; ALIKED does not explain it and degrades
registration in the tested pairings, with ALIKED + brute force the worst arm run. LightGlue also measurably improves triangulation
conditioning and track continuity on the weak clip, and on `wreck_01` it is the
only configuration that registers 47/48.

But it does not clear the architecture bar, on three grounds. It **repairs no
named Phase 3A failure** — registration was never the problem, and Phase 3A's own
rule already says longer tracks alone do not count. It **costs 10–21×**
configuration A's runtime. And most importantly, the shape it produces is
*different*, not *better*: with no independent measurement, a 10.8 % median
change on a clip whose instrument noise is already 3.3 % tells us the front end
partly determines the answer on that footage — which is an argument for caution
about the reference, not for adopting a more expensive front end.

**Configuration A remains the cross-check**, and F2 is demoted from what an
earlier draft called it. It is **not** a demonstrated registration-failure
fallback: the 32/48 → 48/48 and 26/48 → 44/48 rescues are *ALIKED + LightGlue
versus ALIKED + brute force* — a different factorial cell — while SIFT + LightGlue
itself gives 48/48 → 48/48 and 46/48 → 47/48, one frame, with unmeasured noise.
3B-2's global mapper reaches 48/48 on that clip in seconds (§4.1).

> **SIFT + LightGlue is a conditional correspondence-strengthening option, for use
> when ordinary SIFT matching is specifically diagnosed as weak.** This phase
> demonstrates materially longer and better-conditioned SIFT tracks — +41–52 %
> mean length, median triangulation angle 5.37° → 7.03°, tracks spanning ≥ 25 % of
> the clip 33.3 % → 62.8 % — and does **not** demonstrate a large SIFT
> registration rescue.

**LoMa sub-experiment: `not_practical`**, closed at preflight (§1.1), no
troubleshooting spent.

## 4. 3B-2 — incremental vs global SfM

**Phase 3A trigger.** The pose / global-consistency hypothesis was left open
because GLUEMAP is CUDA-only, and Phase 3A's §10.5 explicitly recorded the
compositional option "strong global poses + strong dense per-frame range" as
neither supported nor refuted. The installed COLMAP exposes `global_mapper`, so
the classical half of that question is answerable here.

**Experiment.** Three arms on the **same SIFT measurements** — configuration A's
own database, copied, never mutated. `A_incremental` is Phase 3A's A/run0,
reused. `A_global` runs `global_mapper` on a copy; `A_global_cal` runs
`view_graph_calibrator` first, on a *separate* copy, so a calibration effect
cannot be reported as a mapper effect.

**Noise floor: exactly zero.** `A_global` run0 vs run1 on `wreck_05`: identical
registration, identical point count (2 264, 2 264), **0.00 % median, 0.00 % range
swing**. With the front end not re-run and mapping pinned to one thread, the
mapper-only path is deterministic, so every number below is 100 % method
difference with no noise to clear.

### 4.1 The global mapper is invariant on the strongest clip and materially different on the three difficult ones

| clip | obs/img | A_incr → A_global median | range swing | trajectory RMSE | focal: incr → global |
|---|---|---|---|---|---|
| `swimthrough_02` | 14 440 | **0.0 %** | **0.0 %** | **0.03 %** | 1 052.4 → 1 055.7 |
| `wreck_01` | 2 099 | 9.2 % | 21.8 % | 11.2 % | 1 429.6 → **1 192.8** |
| `wreck_05` | 1 099 | 14.1 % | 52.2 % | 15.7 % | 1 552.0 → **1 283.1** |
| `wreck_03` | 1 213 | 11.5 % (p95 **367 %**) | 366 % | 38.8 % | 1 041.7 → 1 258.9 |

On the high-texture clip the mapper choice is **irrelevant** — 304 859 matched
observations agreeing to under 0.05 %, and camera trajectories agreeing to 0.03 %
of their own extent. On the other three it changes the reconstruction by 9–14 %
median, with range swings far outside the restoration budget. Those three are not
one category: `wreck_01` is the near-planar low-texture clip, `wreck_05` the
low-texture lateral glide, and `wreck_03` the dynamic-subject stress case with the
second-lowest observation density. What they share is few observations per image,
not a common failure mode.

Registration coverage improves where it was short: `wreck_01` 46/48 → **48/48**,
`wreck_03` 47/48 → **48/48**, and no clip fragments (every arm returns a single
sub-model). That is a real operational gain, at 4–52 s against the incremental
mapper's 37–252 s.

### 4.2 The calibrator did something, but not what its name suggests

`view_graph_calibrator` exited 0 on all four clips. Its own log is the important
part: on `wreck_05` it **"Upgraded 0 / 391 pairs to calibrated through
cross-validation"** — unsurprising, since these databases carry
`prior_focal_length = 0` and there are no focal priors to cross-validate. What it
actually did was flag **65 / 391** two-view geometries invalid and **re-estimate
326 relative poses**.

> So the `A_global_cal` arm is a **view-graph pruning and relative-pose
> re-estimation** effect, not a focal-prior calibration. Reporting it as
> "calibration" would have been a false attribution, which is exactly why the
> plan required it to be a separate arm.

Its effect is wildly clip-dependent: **nothing** on `wreck_01` and
`swimthrough_02` (0.0 % median against `A_global`, focal 1 192.8 → 1 195.6), but
**30.6 % median with a 146.6 % range swing** on `wreck_05`, where it also moves
the focal 1 283.1 → **1 766.9**. Removing 17 % of the view graph moves that
clip's recovered focal by 38 %.

### 4.3 A degenerate reconstruction, caught by the degeneracy screen

`A_global_cal` on `wreck_03` registers 48/48 and reports a *better* reprojection
error than the incremental arm (0.659 px vs 0.787 px) — and **15 of its 48 frames
have a median observation range below 10⁻³ of the clip median**, the smallest at
≈ 3 × 10⁻⁶: cameras placed coincident with the structure. **12.2 % of all its
observations** are degenerate that way. Its median residual against A looks
healthy at 0.9 %; its p95 is 8 × 10⁸ %.

That is why a degeneracy screen (fraction of observations below 10⁻³ of the clip
median, and the per-frame median-range ratio) is reported for every arm rather
than left to be noticed. Run across **every arm in 3B-1 through 3B-4 it fires on
exactly this one**, so it is not a screen that flags everything: the next-largest
per-frame range ratio anywhere is 4.08 against this arm's 6.8 × 10⁶. **No shape
statistic from that arm is used**, and the episode is a second, independent
demonstration of Phase 3A's rule that reprojection error cannot rank anything.

### 4.4 Restoration relevance, and the honest limit

The 9–14 % medians and 21–366 % range swings on the low-texture clips are far
above the ~5 % local-range-error threshold at which Phase 3A §8.2's budget says restoration
quality starts to cost (Phase 3A §8.2's restoration-sensitivity budget). But
**this does not mean the global mapper is worse, or
better** — there is no truth here. What it establishes is narrower and more
useful:

> On this footage the *classical reference itself* is mapper-dependent at a
> restoration-relevant magnitude on all three difficult clips, and
> mapper-independent to 0.05 % on the high-texture one.

Read against Phase 3A §7.2, that is a caution about the reference used to
quote every dense-vs-sparse number on `wreck_01`, `wreck_03` and `wreck_05` —
not a new candidate.

### 4.5 Classification

**`failure_not_repaired`**, with a recorded operational benefit.

The global mapper does not repair a named Phase 3A failure. It does not stabilise
the dense arm's scale drift (§8), it does not resolve the shape disagreement — it
*adds* a second, equally unanchored hypothesis on exactly the clips where the
disagreement was already largest — and on `wreck_03` the calibrated variant
produces a degenerate reconstruction. GLUEMAP's hypothesis (learned local
geometry + classical global optimisation) is **not** answered by this: what was
tested is classical-global vs classical-incremental on identical SIFT
measurements, which is a strictly weaker question.

What it does buy is cheap: full registration on the two clips where incremental
fell short, no fragmentation, and 4–52 s per clip. It is recorded as a **useful
diagnostic second opinion** — running both mappers and comparing is now the
cheapest available detector of an ill-conditioned clip — and not as a
replacement.

## 5. 3B-3 — camera-model / self-calibration sensitivity

**Phase 3A trigger.** Configuration A's self-calibrated focal lengths vary from
1 042 to 1 552 px between clips at the same 1 280 px extraction, and radius-
dependent dense-vs-sparse disagreement was a candidate refraction signature. The
metadata of §1.2 sharpens this into something Phase 3A could not say: **five of
the six clips are the same camera, the same lens, the same firmware and the same
capture mode**. That does not licence "at most one of those focal numbers can be
right" — §1.2(d)'s EIS caveat means identical capture settings need not imply
identical *effective virtual-camera* intrinsics after stabilisation. What it does
licence is weaker and sufficient: **a 1 042–1 552 px spread across clips from one
physical camera cannot all be stable estimates of one physical calibration.**

**This is not a refraction experiment.** It tests *central* camera-model
complexity and self-calibration, not flat-port non-central refraction.

**Experiment.** Copy A's database, rewrite **only** the `cameras` row, run the
same incremental mapper with the same seed. All arms start from COLMAP's own
initialisation — `f₀ = 1 536`, principal point at centre, distortion zero — read
out of the source database, so no arm gets a different starting guess.
`ba_refine_principal_point` stays at COLMAP's default (off) throughout, so focal
and distortion are the only free intrinsics in every arm.

**The control arm validates the method.** `A_phase3a` vs `M_simple_radial`, on
all four clips: fitted scale **1.0000**, median **0.0 %**, range swing **0.0 %**,
identical point counts and identical focals. The database-rewrite path is
provably inert, so every other arm is valid. And the mapper-only repeats
(`M_simple_radial`, `M_opencv` on `wreck_05`) are **bitwise identical run to
run** — 0.00 % median, identical point counts — so the noise floor here is also
exactly zero.

### 5.1 Well-conditioned clips are stable; weak clips are not

Scale-aligned median residual against `SIMPLE_RADIAL` (range swing in brackets):

| clip | obs/img | RADIAL | OPENCV | SIMPLE_RADIAL_FISHEYE | focal spread across models |
|---|---|---|---|---|---|
| `wreck_07` | 4 358 | 1.5 % (5.1 %) | 1.2 % (5.1 %) | 0.4 % (1.3 %) | 1 049–1 108 → **1.06×** |
| `swimthrough_02` | 14 440 | 0.4 % (0.5 %) | 0.5 % (0.6 %) | 0.4 % (1.0 %) | 1 026–1 052 → **1.03×** |
| `wreck_05` | 1 099 | 8.0 % (31.8 %) | **23.9 % (77.3 %)** | 0.8 % (1.3 %) | 1 403–1 561 → **1.11×** |
| `wreck_01` | 2 099 | 9.7 % (22.7 %) | 8.1 % (16.0 %) | 9.3 % (21.0 %) | 1 104–1 430 → **1.29×** |

Registration collapses for specific models on the weak clips only: `RADIAL`
44/48 on `wreck_05`, `OPENCV` **26/48** on `wreck_01`. On the two well-conditioned
clips every model registers 48/48 with point counts within 3 %.

**The fisheye result is the informative one.** `SIMPLE_RADIAL_FISHEYE` has
*exactly the same parameter count* as `SIMPLE_RADIAL`, and on `wreck_07` and
`wreck_05` it changes the geometry by 0.4 % and 0.8 % — nothing. `RADIAL` (one
extra parameter) and `OPENCV` (four extra, plus a second focal) destabilise
`wreck_05` by 8 % and 24 %.

> On `wreck_05` the destabilising variable is **capacity, not projection family**.
> Changing what the projection *is*, at fixed capacity, does essentially nothing;
> adding degrees of freedom to an under-constrained problem does a great deal.
> `wreck_01` — the near-planar clip — is the exception that is worse: it moves
> ~9 % under *every* model change including the equal-capacity one.

This also answers the question the fisheye arm was run for. The footage is a
105.4° diagonal `PRJT = GPRO` projection, which genuinely justified testing a
fisheye family; the test says the central-radial model is not the limitation.

### 5.2 The fixed-intrinsics diagnostic, and where the weak clips' focals really sit

Metadata licenses this: `wreck_07`, `wreck_05` and `wreck_01` share body serial,
lens serial, firmware, FOV setting and stabilisation mode, so a shared-intrinsics
assumption is evidence-supported. Taking `wreck_07`'s self-calibrated
`f = 1 108.2, k = −0.0102` and **fixing** them (principal point swapped for
`wreck_01`'s rotated decode):

| clip | self-calibrated | with `wreck_07`'s intrinsics fixed | shape change |
|---|---|---|---|
| `wreck_05` | 48/48, 2 942 pts, track 5.91, f = 1 552.0 | **48/48**, 2 361 pts, track **6.52** | 6.1 % median, 57.8 % range swing |
| `wreck_01` | 46/48, 4 569 pts, track 7.79, f = 1 429.6 | **46/48**, 4 751 pts, track **7.99** | 9.7 % median, 23.2 % range swing |

Neither weak clip is broken by a focal 23–29 % below its own self-calibrated
value; both keep their registration and both get *longer* tracks. The
self-calibrated focals are therefore **not required by the imagery** — they are
what an under-constrained fit happened to land on.

### 5.3 Every independent perturbation moves the weak clips the same way

Collecting the focal estimates for `wreck_05` and `wreck_01` across experiments
that share nothing but the footage:

| perturbation | `wreck_05` focal | `wreck_01` focal |
|---|---|---|
| Phase 3A A (incremental, SIFT, 48 frames) | **1 552.0** | **1 429.6** |
| 3B-1 F2 (SIFT + LightGlue) | 1 779.7 | — |
| 3B-1 F4 (ALIKED + LightGlue) | 1 241.0 | 1 111.0 |
| 3B-2 `A_global` | 1 283.1 | 1 192.8 |
| 3B-3 `RADIAL` | 1 522.1 | 1 104.3 |
| 3B-3 `OPENCV` | 1 402.9 | 1 392.7 |
| 3B-4 S25 (25 frames) | 1 236.4 | 1 178.4 |
| 3B-4 S13 (13 frames) | 1 487.6 | 1 216.9 |
| high-observation clips in the same metadata group | `wreck_07` 1 108.2 · `swimthrough_02` 1 052.4 · `wreck_03` 1 041.7 | |

Collecting **every** focal estimate produced anywhere in Phase 3B — excluding
`M_fixed_from_wreck07`, whose focal is imposed rather than estimated:

| clip | obs/img | arms | focal range | spread |
|---|---|---|---|---|
| `swimthrough_02` | 14 440 | 8 | 1 025.9 – 1 056.2 | **1.030×** |
| `wreck_07` | 4 358 | 5 | 1 049.3 – 1 108.2 | **1.056×** |
| `cenote_01` | 4 580 | 3 | 962.9 – 1 070.5 | 1.112× |
| `wreck_03` | 1 213 | 3 | 1 041.7 – 1 258.9 | 1.209× |
| `wreck_01` | 2 099 | 15 | 1 104.3 – 1 429.6 | 1.295× |
| `wreck_05` | 1 099 | 15 | 1 236.4 – 1 779.7 | **1.439×** |

**Two caveats before that table is read as a law.** The number of arms differs
per clip (3 to 15) and a max−min statistic grows with sample count, so the rows
are not directly comparable. And `wreck_03` is *not* in the converged group
despite its incremental focal of 1 041.7 landing in the well-conditioned band —
the global mapper moves it to 1 258.9, i.e. 21 %.

The comparison that **is** apples-to-apples is the four camera-model arms of
§5.1, the one perturbation family applied identically to four clips:
`swimthrough_02` **1.026×** and `wreck_07` **1.056×** against `wreck_05`
**1.113×** and `wreck_01` **1.294×**. That is a clean split by observation
density, not a monotone law: the two clips carrying ≥ 4 358 observations per image
hold their focal to within 6 % under every perturbation applied to them, and the
low-observation clips do not.

**One anomaly is recorded rather than smoothed over:** `cenote_01` self-calibrates
to 1 070.5, inside that band, even though its metadata says its field of view is
*wider* (123.473° vs 105.383°), which should give a smaller focal. This phase
cannot explain that, and it is a reason to treat the "converged" band as
consistency rather than as a calibration.

### 5.4 Classification

**`failure_not_repaired` — but it substantially reattributes a Phase 3A finding.**

Nothing here repairs a failure; no camera model is better, and with no
independent calibration none can be called physically correct. What the
experiment establishes is a cause:

> Ordinary COLMAP geometry is **stable** to reasonable central camera-model
> choices where the footage constrains it (≤ 1.5 % median, ≤ 5.1 % range swing on
> `wreck_07` and `swimthrough_02`) and **fragile** where it does not (8–24 %
> median, 16–77 % range swings, with registration collapsing for specific models
> on the weak clips only). Camera-model and self-calibration fragility is
> therefore a **restoration-relevant confound in the Phase 3A cross-family
> disagreement on the low-texture clips** — a property of the classical
> reference, not of the dense candidates it was used to judge. How much of that
> disagreement it accounts for is not measured here and would need C2 to settle.

Phase 3A §7.5 already concluded that the radius × range interaction "cannot be
attributed to the camera model" because it moved by 5–8× depending on which
reference was used. This says the same thing from the other side and explains
why: on those clips the reference's own intrinsics are not identified.

**Consequence for the architecture: it strengthens configuration A as the
cross-check, with a stated condition.** A is stable, deterministic and cheap
where the footage supports it; on a low-texture clip its intrinsics — and hence
its range field — are not identified, and Weeks 5–6 must not treat it as a
structural check there without a guard. The cheapest available detector is now
known: disagreement between the incremental and global mappers (§4.1), which
costs seconds and is exactly zero on well-conditioned footage.

## 6. 3B-4 — temporal-baseline / triangulation sensitivity

**Phase 3A trigger.** Configuration A registered 48/48 on four clips and ≥ 46/48
on the other two, and Phase 3A was explicit that **registration does not
establish that depth is well conditioned**. Video contains many near-duplicate
frames with tiny baselines. If the reconstruction is unchanged when 48
observations are replaced by roughly half and roughly a quarter of them
**spanning the same temporal extent**, weak temporal baseline is unlikely to
explain the Phase 3A shape disagreement.

**Experiment.** Nested, deterministic, endpoint-preserving schedules over the
*identical* extracted PNGs (symlinks, no re-extraction): S48 (all 48, = Phase 3A
A/run0, reused), S25 (every 2nd plus the last), S13 (every 4th plus the last).
S13 ⊂ S25 ⊂ S48, all three share both endpoints, so temporal extent is identical.
Configuration A throughout, nothing else varied.

### 6.1 Sparser sampling improves conditioning everywhere — and changes the answer only where the clip is weak

| clip | schedule | reg | points | median tri angle | focal | S48 → this schedule: median (range swing) |
|---|---|---|---|---|---|---|
| `cenote_01` | S48 | 48/48 | 15 233 | 7.38° | 1 070.5 | — |
| | S25 | 25/25 | 7 635 | 8.33° | 985.6 | **1.0 % (3.4 %)** |
| | S13 | 13/13 | 3 550 | **10.41°** | 962.9 | **1.1 % (3.9 %)** |
| `wreck_01` | S48 | 46/48 | 4 569 | 5.59° | **1 429.6** | — |
| | S25 | 23/25 | 2 716 | 6.52° | 1 178.4 | 9.2 % (20.1 %) |
| | S13 | 11/13 | 1 355 | 6.40° | 1 216.9 | 9.2 % (20.5 %) |
| `wreck_05` | S48 | 48/48 | 2 942 | 5.37° | **1 552.0** | — |
| | S25 | 25/25 | 1 137 | 6.16° | 1 236.4 | 10.8 % (49.8 %) |
| | S13 | **9/13** | 338 | 6.01° | 1 487.6 | 7.5 % (18.1 %) |

Median triangulation angle rises on every clip as the schedule thins — exactly
as it should, since neighbouring frames are being removed. On `cenote_01`, the
59.94 fps clip whose 48 frames span only ~6 s and therefore carries the most
redundant sampling in the set, **13 frames reconstruct the same world as 48 to
1.1 %**, with a 3.9 % range swing and a 4.25 % trajectory residual. Dense temporal
overlap buys that clip nothing.

On the two weak clips the geometry moves by ~9–11 % median. Note what `wreck_01`
does: **S25 and S13 agree with each other to 0.5 %** while both differ from S48 by
9.2 %, and their focals (1 178, 1 217) sit with the global mapper's (1 193) and
far from S48's 1 430.

### 6.2 The repeat runs decide which of those numbers may be quoted

Unlike 3B-2 and 3B-3, a schedule run re-executes the **whole** pipeline, so its
noise floor is not zero — and it turns out to differ by three orders of magnitude
between clips. Every schedule was run twice with identical settings and seed:

| clip | S25 run0 vs run1 | S13 run0 vs run1 | registration across repeats |
|---|---|---|---|
| `wreck_01` | **0.03 %** (0.05 % swing) | **0.01 %** (0.01 % swing) | 23, 23 · 11, 11 |
| `cenote_01` | 0.88 % (3.43 % swing) | 0.55 % (2.44 % swing) | 25, 25 · 13, 13 |
| `wreck_05` | **32.89 %** (141.36 % swing) | **10.18 %** (37.72 % swing) | **25, 24 · 9, 12** |

Reading §6.1 against that floor:

* **`wreck_01`: the effect is real and large.** Its schedule runs are essentially
  deterministic (0.01–0.03 %), so the 9.2 % S48→S25 difference is roughly **300×
  its own noise**. And the direction is informative: S25 and S13 agree with each
  other to 0.5 %, and their focals (1 178, 1 217) sit with the global mapper's
  (1 193) while S48's 1 430 is the outlier.
* **`cenote_01`: stable, and now provably so.** Its observed S48→S25 difference
  (1.0 % median, 3.4 % swing) is **at its own repeat noise** (0.88 %, 3.43 %).
  Dropping 73 % of the frames changes that clip's geometry no more than re-running
  the same schedule does.
* **`wreck_05`: `not_identifiable`.** The S48→S25 difference (10.8 %, 49.8 %) is
  well *below* S25's own run-to-run spread (32.9 %, 141.4 %). Quoting it as a
  schedule effect would have been reading a signal out of noise.

That last row is a finding in its own right, and not the one the hypothesis went
looking for: **below ~25 frames `wreck_05` stops being reconstructible
repeatably at all** — registration swings between 9 and 12 of 13 across
byte-identical invocations. Once again it is the low-observation clip
(1 000–1 100 keypoints per image) that fails, while `wreck_01` at ~2 000 and
`cenote_01` at ~4 500 are reproducible at the same frame counts.

### 6.3 Classification

**`failure_not_repaired`, and partly `not_identifiable`.**

* **Weak temporal baseline does not explain the Phase 3A shape disagreement.** On
  the well-conditioned, most-redundantly-sampled clip, removing 73 % of the frames
  changes the recovered geometry by 1.1 % — while triangulation angles improve.
  If redundant small-baseline frames were the problem, `cenote_01` is where it
  should have shown, and it does not.
* **On `wreck_05` the question is `not_identifiable`** at these frame counts: the
  effect is far below the instrument's own spread.
* **On `wreck_01` the effect is real** — 9.2 %, above the restoration threshold and
  ~300× its measured noise floor — **and it is more consistent with
  self-calibration / mapping instability than with a simple
  redundant-small-baseline explanation**: the two sparser schedules agree with each
  other to 0.5 % and with the global mapper, and disagree with the 48-frame
  incremental fit whose focal is the outlier. It is not a clean parallax test
  either way, because frame count and frame spacing changed together (§10.7).

Nothing here changes the architecture. What it adds operationally is a caution:
a 48-frame window is not automatically better than a 25-frame one, and on
low-texture footage reducing the frame count *below* ~25 destroys
reproducibility, which Weeks 5–6 should not discover by accident.

## 7. 3B-5 — weak-parallax / near-planar specialist

**Conditional experiment. The trigger rule was pre-registered in `PHASE3B.md`
§6 before 3B-2, 3B-3 and 3B-4 reported**, so the decision cannot be
reverse-engineered from whichever answer turned out convenient. It required all
three of:

1. 3B-4 shows conditioning sensitivity above the restoration threshold **and that
   sensitivity tracks the triangulation-angle distribution rather than merely the
   point count**;
2. 3B-3 does not explain the instability as a self-calibration degeneracy;
3. 3B-2's global mapper does not repair it.

### 7.1 Condition (1) fails, and the reason is the most useful single table in this phase

Configuration A on all six clips, ordered by observation density:

| clip | points | obs/img | **median triangulation angle** | baseline/depth | focal | stable under 3B-2/3B-3/3B-4? |
|---|---|---|---|---|---|---|
| `swimthrough_02` | 29 051 | 14 440 | **5.23°** | 0.149 | 1 052.4 | **yes** — 0.0 % mapper, 0.4–0.5 % camera model |
| `cenote_01` | 15 233 | 4 580 | 7.38° | 0.145 | 1 070.5 | **yes** — 1.0–1.1 % across all frame schedules |
| `wreck_07` | 11 197 | 4 358 | 7.18° | 0.128 | 1 108.2 | **yes** — 0.4–1.5 % camera model |
| `wreck_01` | 4 569 | 2 099 | 5.59° | 0.276 | **1 429.6** | no — 8–10 % everywhere |
| `wreck_03` | 2 796 | 1 213 | 6.62° | 0.134 | 1 041.7 | no — 11.5 % mapper |
| `wreck_05` | 2 942 | 1 099 | 5.37° | 0.140 | **1 552.0** | no — 8–24 % camera model, 14 % mapper |

**`swimthrough_02` has the lowest median triangulation angle in the entire set
(5.23°) and is the most stable clip under every perturbation applied in this
phase.** `wreck_01` and `wreck_05` have comparable or *higher* triangulation
angles — and `wreck_01` has by far the largest baseline/depth ratio, 0.276
against `wreck_07`'s 0.128 — and are the least stable.

> The tested triangulation-conditioning proxies do **not** predict which clips are
> unstable. Observation density tracks it much more closely: every stable clip
> carries 4 358–14 440 observations per image, every unstable one 1 099–2 099. That
> is **consistent with a shortage of constraints relative to the free parameters**
> rather than a shortage of parallax — but it is a pattern across six clips, not a
> demonstrated causal law, and a *global* median angle cannot exclude a local
> parallax-topology failure within a clip.

That is the pre-registered clause firing exactly as intended: the sensitivity is
real, but it tracks the constraint count, not the triangulation-angle
distribution.

### 7.2 Condition (2) also fails

3B-3 supplies a positive, mechanistic explanation: on precisely the low-observation
clips, adding camera-model degrees of freedom moves the geometry by 8–24 % and
collapses registration for particular models, while an equal-capacity change of
projection family does essentially nothing; and fixing intrinsics to a
well-conditioned clip's values reconstructs both weak clips at full registration
with *longer* tracks. Every independent perturbation in this phase — a different
matcher, a different mapper, a different camera model, a sparser frame schedule —
moves their focal over a 1 104–1 780 range while the high-observation clips of
the same physical camera sit inside 1 042–1 108. That is a self-calibration
degeneracy, which is condition (2)'s disqualifier.

### 7.3 Classification: `not_triggered`

The cheaper experiments explain the instability, so per the pre-registered rule
no further method is run. MP-SfM injects **monocular depth and normal priors to
repair low parallax and low overlap** — a hypothesis this evidence does not
support, since the clip with the weakest parallax proxy is the stable one.

**The counter-argument is recorded rather than hidden.** Priors of that kind
would also add constraints to an under-constrained problem, so MP-SfM might well
help these clips for a reason other than its stated one. That is speculation, it
is not what the trigger was written to test, and acting on it would be adding a
seventh hypothesis. It is left as a note for whoever revisits this after C2.

For completeness, and reported separately from the trigger decision as the plan
requires: had it triggered, MP-SfM would have been **`not_practical_local`** —
its `requirements.txt` pins `cupy-cuda12x` (CUDA-only, no macOS ARM wheel) plus
`mmcv`. The trigger decision does not rest on that, and the practicality verdict
does not stand in for it.

## 8. 3B-6 — dynamic and temporally-global learned geometry

**Phase 3A trigger.** MapAnything on `wreck_03`: a **6.64×** fitted per-frame
scale wander against configuration A and a **129.8 %** range-dependent residual
swing — the worst figures anywhere in Phase 3A — on a clip with a large moving
diver, exhaust bubbles and haze. Two mechanisms were tested, in a strict order,
against a deliberately high bar: the failure is enormous, so a few-percent
numerical difference is not a result.

### 8.1 3B-6A — Any4D: a real, controlled reduction that still does not clear the bar

`Any-4D/Any4D` @ `aa9f1b0d`, Apache-2.0 code, checkpoint
`any4d_4v_combined.pth` (7 727 258 559 bytes, sha256
`e78d2ef2…d4d06ed85`), **no licence stated**. Installed into a dedicated venv
(Python 3.13.5, torch 2.6.0, MPS) with **zero native compilation** — `uniception`
and `utils3d` both built as pure `py3-none-any` wheels, and the model config
selects the `dinov2_large` encoder so the fork's `curope` CUDA kernel never
enters the path. **No Any4D file was modified**: a project-owned driver calls the
released model factory, released Hydra config, released preprocessing and
released inference entry point, exactly as Phase 3A did for MapAnything.

#### Conventions, verified rather than assumed

* `depth_along_ray` equals `‖pts3d_cam‖` to **1.4 × 10⁻⁶** (max abs, full frame),
  so the mapping onto the project's `range_along_ray` is exact.
* The pose convention is **cam2world (`T_wc`)**, established numerically by
  composing `(cam_quats, cam_trans)` both ways against the model's own `pts3d`
  and checking that the wrong direction scores materially worse — run at frames
  1/3, 2/3 and the end, never at frame 0, because this model family anchors its
  world frame to camera 0 and the control would be a no-op there (Phase 3A's
  §3.4 lesson).
* The checkpoint loads with **0 missing and 0 unexpected keys**, so this is not a
  repeat of the Water-VGGT situation.
* The measured source→grid map is **294×518 / 518×294 with 0 of 25 markers lost
  to crop** in both orientations — essentially MapAnything's grid, and unlike the
  VGGT family it discards no field of view on a portrait clip.
* **Validity: the model asserts everything.** `non_ambiguous_mask` is present and
  *was* applied (shape 294×518, verified per frame) — and its true-fraction is
  exactly **1.0000 on every frame of both clips**. So Any4D's "valid 1.00" is the
  absence of a validity signal, the same situation Phase 3A §5.1 flagged for the
  VGGT family, not perfect coverage. That is now established rather than assumed.
* **Reproducibility: bitwise.** Re-running `wreck_03` gives max |rel diff|
  **0.000 × 10⁰** with identical masks, so the noise floor is exactly zero and
  every difference below is method difference.

#### One thing had to be measured before anything could be compared

Any4D's released inference path does **global self-attention across every view at
once and exposes no memory-efficient mode** — `Any4D.forward(views)` takes no such
argument, and `gradient_checkpointing` is a training-time construction flag that
does not touch the forward attention buffer. MapAnything, by contrast, was run in
Phase 3A with `memory_efficient_inference=True`. At 48 views on the 294×518 grid
the attention call requests a **62.19 GB** buffer and raises
`RuntimeError: Invalid buffer size` on this 24 GB machine.

So Any4D was run on **16 views**, sampled uniformly with both endpoints kept so
the temporal extent is identical. That is a handicap for exactly the property
under test, which is why **MapAnything was re-run on the same 16 frames** rather
than compared across view counts. The control removes the confound outright:

| | 48 views | 16 views |
|---|---|---|
| D vs A on `wreck_03`, median | 25.2 % | 25.0 % |
| range swing | 127.5 % | 129.5 % |
| per-frame scale max/min | 6.30× | **7.05×** |

MapAnything's dynamic failure is **not** a function of view count.

#### The result, all arms scored against configuration A on the same 15–16 frames

| clip | model | views | coverage | median | range swing | per-frame scale |
|---|---|---|---|---|---|---|
| **`wreck_03`** | D MapAnything | 16 | 0.769 | 25.0 % | 129.5 % | **7.05×** |
| (the trigger) | **Y Any4D** | 16 | 1.000 | 21.7 % | **72.8 %** | **2.57×** |
| | E0 VGGT | 48 | 1.000 | **4.0 %** | 33.4 % | 1.59× |
| | E Wat3R-Ren | 48 | 1.000 | 5.8 % | 50.8 % | 2.04× |
| `swimthrough_02` | D MapAnything | 16 | 0.852 | 5.9 % | 6.1 % | 1.31× |
| (easy control) | **Y Any4D** | 16 | 1.000 | **7.0 %** | **8.8 %** | 1.30× |
| | E0 VGGT | 48 | 1.000 | **1.7 %** | 3.5 % | 1.02× |
| | E Wat3R-Ren | 48 | 1.000 | 2.3 % | 6.1 % | 1.07× |

**At equal view count, Any4D — which includes explicit dynamic modelling —
reduces MapAnything's observed dynamic-clip instability.** Per-frame fitted-scale
wander falls **7.05× → 2.57×** and the range-dependent residual swing
**129.5 % → 72.8 %**, with a bitwise-zero noise floor and no view-count confound.
That is a real, repeatable effect on precisely the signature the hypothesis names.

**The mechanism is not isolated, and the wording above is deliberate.** This
compares *Any4D against MapAnything*, not *MapAnything with and without a dynamic
head*. The two models differ in training data, weights and architecture as well as
in dynamic modelling, so nothing here attributes the improvement to the dynamic
head specifically. A clean attribution would need an ablation neither model
exposes.

**What can be said about the head is that it is strongly active.** Any4D's
scene-flow output has a median per-pixel magnitude of **1.80** on `wreck_03`
against a median scene range of 5.9–21.6, and **0.0027** on the rigid
`swimthrough_02` control — a ratio of about 670×. That establishes the head
responds to the dynamic clip; it does **not** establish that it caused the
improvement, nor that it separated foreground motion correctly. If anything the
opposite: a *median* flow of 1.80 implies asserted motion across most of the
frame rather than a localised diver, which is hard to reconcile with a clean
rigid/dynamic separation. (Recorded as data only, never used to filter or correct
the range field.)

#### Why it still does not clear the architecture bar

Four reasons, none of which is about the size of the effect:

1. **It does not bring the failure inside the budget.** 2.57× scale wander and a
   72.8 % range-dependent swing remain far outside the ~5–10 % band of Phase 3A
   §8.2's restoration-sensitivity study. The clip is still unusable for
   range-dependent restoration.
2. **Contextual, not decisive: an existing 48-view result is substantially closer
   to A on this clip.** Phase 3A's E0 (vanilla VGGT) reaches 4.0 % median, 33.4 %
   swing and 1.59× wander on `wreck_03`. **This comparison is not view-count
   controlled** — E0 saw 48 views to Any4D's 16 — so it is recorded as context and
   is *not* used to reject Any4D. Points 1, 3 and 4 do that on their own.
3. **It regresses on the easy case.** On `swimthrough_02` Any4D is the worst of
   the four arms — 7.0 % median against E0's 1.7 % — so this is not a specialist
   that is strong everywhere and merely weakest on dynamics.
4. **It is not practically deployable here.** 226 s and **26.5 GB** of MPS
   allocation for 16 views, against MapAnything's **21 s and 7.7 GB** for the
   same 16 frames — 10.8× the runtime and 3.4× the memory, on a 24 GB machine it
   is already over-committing. It cannot process the project's standard 48-frame
   window at all. It emits no usable validity signal. And its checkpoint carries
   **no stated licence**, so it could not become a project dependency whatever
   the numbers said.

#### Classification: `interesting_but_not_material`

Not `failure_not_repaired` — the improvement on the named signature is real,
repeatable and view-count-controlled, and it should be recorded as such: **Any4D
reduces MapAnything's dynamic scale instability by roughly 2.7× at matched view
count**, though which of its differences produces that is not isolated. Not
`failure_repaired` — it leaves the residual far outside the restoration budget,
regresses on the control clip, costs an order of magnitude more, cannot run the
standard 48-frame window, emits no usable validity signal, and its checkpoint
states no licence. Those five are sufficient on their own; the E0 comparison is
not needed and is not relied on.

**A note for the dense-supplier decision that is more useful than Any4D itself.**
The controlled 16-view re-run shows MapAnything's `wreck_03` failure is
**view-count-independent**, so shortening the window is not a workaround. That
sharpens Phase 3A §10.3's named condition rather than changing it: the
dynamic-content guard on MapAnything is needed, it is not a sampling artefact,
and it is not something a dynamic-specialist model fixes cheaply here.

### 8.2 3B-6B — VGGT-SLAM 2.0: `not_practical_local`

**Decided at the pre-installation inspection point the plan specifies**, not
after a night of patching. `MIT-SPARK/VGGT-SLAM` @ `35327ac` (2026-06-29),
BSD-2-Clause, backbone fork `MIT-SPARK/VGGT_SPARK` (GitHub recognises no licence
file), checkpoint `facebook/VGGT-1B` (non-commercial).

Four independent blockers, each verified rather than assumed:

1. **An unconditional CUDA call on the default path.**
   `vggt_slam/solver.py:309` reads
   `dtype = torch.bfloat16 if torch.cuda.get_device_capability()[0] >= 8 else torch.float16`.
   Executed on this machine it raises `AssertionError: Torch not compiled with
   CUDA enabled`. That is a crash, not a slow fallback. Together with the two
   `cuda if available else cpu` selectors (`main.py:44`, `solver.py:301`) and the
   hardcoded `model.to(torch.bfloat16)` (`main.py:79`), the default path needs
   **at least four** CUDA-specific changes — more than the one trivial
   device-selection adaptation the Phase 3B budget allows.
2. **Neither currently available project interpreter satisfies the pinned torch
   version.** `requirements.txt` pins `torch==2.3.1`, whose macOS arm64 wheels
   cover cp38–cp312; this machine has Python 3.13 and 3.14. Python 3.11 could of
   course be installed — the point is not that it is impossible, but that standing
   up a new interpreter and environment for an optional test is outside the budget
   once blocker 1 already applies.
3. **The official install path declares mutually incompatible requirements and
   pulls a dependency with no macOS ARM wheel.** `setup.sh` installs both
   `facebookresearch/perception_models` (pins `numpy==2.1.2`) and
   `facebookresearch/sam3` (pins `numpy>=1.26,<2`). It also pulls
   `decord==0.6.0`, which publishes no macOS ARM wheel at any Python version, so
   pip would attempt a CMake/C++ source build — the mandatory hard stop.
   *In fairness this one is avoidable*: both packages are imported only inside
   `if args.run_os:` (open-set semantic search), which the SLAM path does not
   need. It is recorded because it is what the official install does, not as the
   decisive blocker.
4. **Licensing.** `perception_models` is under the FAIR Noncommercial Research
   License, the backbone fork carries no recognised licence, and the checkpoint
   is the non-commercial `facebook/VGGT-1B` Phase 3A already disqualified as a
   default.

**And it would not have been the clean ablation it looks like.** VGGT-SLAM is
*not* a `VGGT → global optimiser` A/B against configuration E0: its backbone is a
fork rather than upstream VGGT, and it runs the model in **bfloat16** where E0
ran float32 on MPS. Any difference would have measured "global alignment **plus**
a different frontend build **plus** a different numeric precision". So even a
successful run would not have isolated the variable this hypothesis names.

**Classification: `not_practical_local`.** The method may well be viable on a
CUDA host with Python 3.11; faithful local execution here would be a macOS port,
which is explicitly out of scope. The sequence-level global-consistency
hypothesis therefore remains **open**, exactly as GLUEMAP's did in Phase 3A —
recorded as a known gap, not as a recommendation to rent hardware.

## 9. Summary and decision

### 9.1 What every experiment cost, and what its noise floor was

Every quantitative conclusion whose interpretation depends on repeatability is
compared against a measured **same-metric** noise floor where practical; the cases
without one are marked below and are not used for strong claims. The floors that
were measured differ by five orders of magnitude:

| experiment | what re-runs | measured run-to-run spread |
|---|---|---|
| 3B-2, 3B-3 | mapper only, on a fixed database | **exactly zero** — identical registration, identical point counts, 0.00 % median |
| 3B-6A | Any4D on MPS | **exactly zero** — bitwise identical, max &#124;rel diff&#124; 0.000 × 10⁰ |
| 3B-1 | whole pipeline | `wreck_07` 0.01 % · `wreck_05` 2.1–6.5 % median, 6.7–19.1 % range swing |
| 3B-4 | whole pipeline | `wreck_01` 0.01–0.03 % · `cenote_01` 0.55–0.88 % · **`wreck_05` 10.2–32.9 %** |

**Where there is no floor, it is said so.** 3B-5 and 3B-6B were never executed,
so they have none and carry no quantitative claim. F2's single-frame registration
gain over configuration A on `wreck_01` (46/48 → 47/48) has an unmeasured floor —
Phase 3A repeated A only on `wreck_05` and `wreck_07` — and is explicitly not
relied on (§3.4). `wreck_07`, `wreck_03` and `swimthrough_02` have no
frame-schedule floor because 3B-4 did not run on them.

The mechanism behind the 3B-1 floor is identified: `wreck_05`'s two runs
extracted the **identical 52 745 keypoints** and differed by **29 verified matches
out of 65 756** (0.04 %), which moved the recovered range field by 3.3 % median
and 6.7 % range swing. `wreck_07` absorbed a perturbation of the same kind
entirely (4 differing matches out of 352 999 → 0.01 %).

### 9.2 The finding that connects all four classical experiments

Four perturbations that share nothing but the footage — a different matcher, a
different mapper, a different central camera model, a sparser frame schedule —
were applied independently. They agree with each other about which clips are
stable, and it is not the axis anyone expected:

| clip | obs/img | mapper (3B-2) | camera model (3B-3) | schedule (3B-4) | median tri angle |
|---|---|---|---|---|---|
| `swimthrough_02` | 14 440 | **0.0 %** | 0.4–0.5 % | — | **5.23°** (lowest) |
| `cenote_01` | 4 580 | — | — | **1.0–1.1 %** (at its own noise) | 7.38° |
| `wreck_07` | 4 358 | — | 0.4–1.5 % | — | 7.18° |
| `wreck_01` | 2 099 | 9.2 % | 8.1–9.7 % | 9.2 % | 5.59° |
| `wreck_03` | 1 213 | 11.5 % | — | — | 6.62° |
| `wreck_05` | 1 099 | 14.1 % | 0.8–23.9 % | not identifiable | 5.37° |

> **Within these six clips, instability tracks SIFT observation density much more
> closely than it tracks the tested global triangulation-angle and baseline/depth
> proxies.** The clip with the *lowest* median triangulation angle in the set is
> the most stable one under every perturbation, and the clip with the *largest*
> baseline/depth ratio (`wreck_01`, 0.276 against `wreck_07`'s 0.128) is among the
> least. Every stable clip carries 4 358–14 440 observations per image; every
> unstable one 1 099–2 099.
>
> **This is consistent with an under-constrained / self-calibration regime. It
> does not establish observation density as the causal variable**, and six clips
> cannot. Median triangulation angle and median baseline/depth are *global*
> summaries: they cannot rule out a local parallax-topology failure — degenerate
> subsets, a dominant plane, or motion nearly along the optical axis over part of
> a clip — that a per-point median would hide.

And they agree about the consequence. Under the one perturbation family applied
identically to four clips — the four central camera models of §5.1 — the two
high-observation clips hold their focal to **1.026×** and **1.056×**, while the
two low-texture clips *from the same physical camera, same lens, same firmware
and same capture mode* spread **1.113×** and **1.294×**, with registration
collapsing for particular models. Across *all* Phase 3B arms `wreck_05`'s focal
estimates span **1 236–1 780** and `wreck_01`'s **1 104–1 430**. Imposing the
well-conditioned clip's intrinsics on either costs no registration and
*lengthens* its tracks.

> **Classical-reference ill-conditioning is a restoration-relevant confound in the
> Phase 3A disagreement on the weak clips.** That does not make the dense methods
> right — there is still no truth anywhere in Week 3 — and it is deliberately not
> stated as a decomposition: nothing here splits a dense-vs-A residual into
> "X % reference, Y % dense". What it does establish is that a **substantial
> portion of the interpretation of Phase 3A §7.2 is now confounded by the fact
> that, on those clips, the reference itself is not identified.**

### 9.3 Results table

| hypothesis | result | classification | architecture impact |
|------------|--------|----------------|---------------------|
| **3B-1** correspondence attribution | The track-length gain is **the matcher, not the features**: +51.5 %/+41.3 % from LightGlue at fixed features, −7.9 %/−16.9 % from ALIKED at fixed matcher, and ALIKED + brute force collapses registration to 32/48 and 26/48. Triangulation conditioning improves on the same axis (5.37° → 7.03°). Shape moves 10.8 % median / 46.3 % range swing, ~3–6× the noise floor. Cost 10–21×. | `interesting_but_not_material` | **None.** Configuration A remains the cross-check. SIFT + LightGlue recorded as a *conditional fallback* for a demonstrated registration failure. LoMa: `not_practical`. |
| **3B-2** incremental vs global SfM | Zero noise floor. Identical on the high-texture clip (**0.0 % median, 0.03 % trajectory RMSE**), 9–14 % median and 22–366 % range swings on the three difficult clips (near-planar, low-texture and dynamic). Registration completed 46→48 and 47→48; no fragmentation; 4–52 s. `view_graph_calibrator` upgraded **0/391** pairs and instead pruned 65 two-view geometries; on `wreck_03` its output has **15 degenerate frames** while reporting the *best* reprojection error of the three arms. | `failure_not_repaired` | **None.** Adopted as a cheap *diagnostic second opinion* — the cheapest available ill-conditioning detector. The calibrator is **not** adopted. GLUEMAP's hypothesis stays open. |
| **3B-3** camera model / self-calibration | Control arm reproduces Phase 3A A to **0.0 %**, validating the method; noise floor zero. Well-conditioned clips are stable to every central model (≤ 1.5 % median, focal spread 1.03–1.06×); weak clips move 8–24 % with registration collapsing for specific models. Equal-capacity fisheye changes `wreck_05` by **0.8 %** — it is capacity, not projection family. Fixed intrinsics from `wreck_07` keep full registration on both weak clips and lengthen tracks. | `failure_not_repaired` (reattributes a Phase 3A finding) | **None**, but it **strengthens configuration A with a stated condition**: trustworthy where observation density is high, intrinsics not identified where it is low. |
| **3B-4** temporal baseline | `cenote_01` — the most redundantly sampled clip — reconstructs the same world from 13 frames as from 48, to **1.0–1.1 %**, at its own repeat noise, while triangulation angles *improve* (7.38° → 10.41°). `wreck_01` moves 9.2 %, ~300× its noise floor, with the sparse schedules agreeing with the global mapper and against the 48-frame focal. `wreck_05` is **not identifiable** — the effect is below its own 32.9 % spread, and below ~25 frames it stops being reconstructible repeatably at all. | `failure_not_repaired`, partly `not_identifiable` | **None.** Weak temporal baseline does **not** explain the Phase 3A disagreement. |
| **3B-5** weak-parallax specialist | Trigger rule pre-registered before 3B-2/3/4 reported. Condition (1) fails — the sensitivity tracks observation density, not the triangulation-angle distribution. Condition (2) fails — 3B-3 supplies a self-calibration-degeneracy explanation. | `not_triggered` | **None.** No further method run. (Had it triggered: MP-SfM is `not_practical_local` — pins `cupy-cuda12x` and `mmcv`.) |
| **3B-6A** Any4D (dynamic) | Runs locally, no native compilation, bitwise reproducible, conventions verified (`depth_along_ray` = ‖pts3d_cam‖ to 1.4 × 10⁻⁶, cam2world, 0 missing keys). Its released path cannot do 48 views (62.19 GB attention buffer), so MapAnything was **re-run at 16 views** to remove the confound — showing D's failure is view-count-independent. At matched views Any4D cuts scale wander **7.05× → 2.57×** and range swing **129.5 % → 72.8 %**; its scene-flow head is 670× more active on the dynamic clip than on the control, which shows the head responds but does not isolate it as the cause. | `interesting_but_not_material` | **None.** Still far outside the restoration budget; *worse* than every arm on the easy control; 10.8× the runtime and 3.4× the memory of MapAnything at equal views; cannot run the 48-frame window; no usable validity signal; no stated checkpoint licence. |
| **3B-6B** VGGT-SLAM 2.0 (global) | Decided at the prescribed pre-installation inspection. Four independent blockers, verified: an unconditional `torch.cuda.get_device_capability()` on the default path (raises here) plus three more CUDA sites; `torch==2.3.1` has no wheel for either interpreter present; neither available project interpreter satisfies the pinned `torch==2.3.1`; the official install path declares mutually incompatible NumPy requirements (2.1.2 vs < 2) and pulls `decord`, which has no macOS ARM wheel; and a noncommercial dependency licence. | `not_practical_local` | **None.** The sequence-level global-consistency hypothesis stays **open**, as GLUEMAP's did. |

---

# Did Phase 3B change the Phase 3A architecture?

## NO

The provisional integration path is **frozen**:

```text
MapAnything           dense range supplier
COLMAP / SIFT         sparse geometry + structural cross-check
```

No result was simultaneously large, repeatable, specifically attributable,
restoration-relevant **and** practically deployable. Two came close and are
recorded honestly: 3B-1's matcher attribution is clean and real but repairs no
named failure and costs 10–21×; Any4D produces a genuine, view-count-controlled
2.7× reduction in the exact failure it targets and still leaves it far outside
the restoration budget, while regressing on the easy clip, costing an order of
magnitude more, being unable to run the standard 48-frame window, and carrying no
stated checkpoint licence.

### Narrowly justified conditional fallbacks

Neither replaces the default; both are recorded with their trigger.

1. **SIFT + LightGlue (`--FeatureMatching.type SIFT_LIGHTGLUE`)** — a
   *correspondence-strengthening* option for a clip where ordinary SIFT matching
   is specifically diagnosed as weak, and only after the cheaper option in (2).
   It raises mean track length 41–52 %, median triangulation angle 5.37° → 7.03°,
   and tracks spanning ≥ 25 % of the clip 33.3 % → 62.8 %. **It is not a
   registration-failure fallback** — its own registration gain over A is one frame
   with unmeasured noise; the large rescues in this phase belong to a different
   factorial cell (ALIKED + LightGlue over ALIKED + brute force). It costs 10–21×
   configuration A and *changes the recovered shape by ~11 % median on a weak
   clip*, so it must not be on by default.
2. **`global_mapper` as a second opinion, never as a replacement** — 4–52 s per
   clip on configuration A's existing database. Its disagreement with the
   incremental mapper is **0.0 %** on well-conditioned footage and 9–14 % on
   ill-conditioned footage, which makes it the cheapest ill-conditioning detector
   available, and it completes registration where incremental falls short.
   **`view_graph_calibrator` is explicitly not adopted**: it performs no focal
   calibration without priors, and on `wreck_03` it produced a reconstruction with
   15 degenerate frames and the best reprojection error of the three arms.

### The acquisition position is unchanged

> **C2 is required for definitive objective geometry validation and for resolving
> refraction, but C2 is NOT a blocker to downstream pipeline development.**

Phase 3B strengthens the case for C2 rather than altering it. It has now shown
that on low-texture clips the classical reference's own intrinsics are not
identified — the same clips where Phase 3A's cross-family disagreement was
largest — so an independent metric anchor would resolve *both* sides of that
disagreement at once. Weeks 5–6 can proceed on the frozen path now.

### One new operational guard for Weeks 5–6

Phase 3A §10.3 already required flagging clips with a large moving foreground
subject before consuming MapAnything range. Phase 3B adds a second, cheap and
measurable guard, and sharpens the first:

* **Observation density is a heuristic warning trigger learned from this dataset,
  not a validity boundary.** On these six clips, below roughly 2 000 SIFT
  observations per image the classical geometry stopped being identified: focal
  estimates moved 10–29 % under ordinary perturbations, and at reduced frame counts
  one clip became non-reproducible outright. Treat `< ~2 000 obs/image` as a
  **flag to check**, not a threshold with any calibrated meaning — six clips cannot
  establish one — and do not use configuration A as a structural cross-check on a
  flagged clip without the check in the next bullet.
* **The detector is one extra mapper run.** `global_mapper` on the same database
  costs seconds and disagrees by 0.0 % exactly when the clip is well conditioned.
* **MapAnything's dynamic failure is not a view-count artefact.** Re-running it at
  16 views reproduces the failure exactly (25.0 % vs 25.2 % median, 7.05× vs 6.30×
  scale wander), so shortening the window is not a workaround.

---

## 10. Limitations of Phase 3B itself

Ordered by how much they should change a reader's confidence.

1. **There is still no independent range or scale measurement.** Every number
   here is consistency. "The reference is not identified on low-texture clips" is
   an identifiability statement, not a claim that any particular reconstruction is
   wrong.
2. **Electronic image stabilisation is on in every clip and was never modelled**
   — by Phase 3A or here. `EISE = Y` with HyperSmooth Boost/High means each frame
   is reprojected into a stabilised virtual camera. The single-camera assumption
   used throughout depends on GoPro implementing that as a rotation into a *fixed*
   virtual camera rather than a translating sensor crop. Nothing in this phase can
   settle which, and it is a live candidate explanation for part of the
   self-calibration behaviour reported in §5.
3. **`cenote_01` self-calibrates into the same focal band as the 105.383° clips
   despite metadata saying its field of view is wider (123.473°).** This is
   unexplained and is a reason to read §5.3's "converged band" as consistency
   rather than as a calibration.
4. **Any4D was evaluated at 16 views, not 48**, because its released inference
   path cannot do more here. MapAnything was re-run at 16 views to control the
   comparison against it, but E0 and E were not, so the statement "E0 is 5× better
   on `wreck_03`" is not view-count-controlled.
5. **3B-1's factorial is not a single-matcher-two-descriptors design.**
   `SIFT_LIGHTGLUE` and `ALIKED_LIGHTGLUE` are different LightGlue weights, and
   the two brute-force matchers compare different descriptors. The matcher axis is
   "nearest-neighbour vs the learned matcher trained for that descriptor". The
   cross-*feature* cells are additionally near-useless: SIFT and ALIKED detect at
   different pixels, so within-image observation matching found only 36–150
   correspondences against 5 468–13 293 for the within-feature pairs.
6. **3B-2 compares pipelines, not one algorithmic axis.** `mapper` and
   `global_mapper` differ in triangulation thresholds, bundle-adjustment schedule
   and registration strategy. What is held fixed is the measurement set.
7. **3B-4's frame count and frame spacing move together** by construction, and
   the number of exhaustive matching pairs falls quadratically (1 128 → 300 → 78),
   so a conditioning change there is a joint effect.
8. **Only two clips carry the 3B-6 evidence**, and only one of them is the
   dynamic trigger. `wreck_03` is a single clip with a single dynamic subject.
9. **Two hypotheses were closed without execution** (3B-5 `not_triggered`, 3B-6B
   `not_practical_local`) and one sub-experiment at preflight (LoMa
   `not_practical`). Their hypotheses are open, not answered — in particular the
   sequence-level global-consistency question, which both GLUEMAP and VGGT-SLAM
   would have addressed and neither could be run here.
10. **`ba_refine_principal_point` was left at COLMAP's default (off)** in every
    3B-3 arm, deliberately, so the principal point is fixed in all of them. A
    camera model's ability to move the principal point was therefore never tested.


---

## 11. Adversarial self-review

Run against every hypothesis before any was declared closed. What it checked,
what it found, and what it changed.

### 11.1 The checklist

| risk | how it was checked | outcome |
|---|---|---|
| geometry-convention mistakes | every new quantity unit-tested against synthetic geometry with an analytic answer, each with a falsification element (`tests/test_week3_phase3b.py`, 12 tests; 323 in the suite pass) | triangulation angle verified to use the **widest** camera pair, not an adjacent or averaged one — the property that makes it meaningful for video; Umeyama trajectory alignment verified to absorb a pure similarity exactly and to expose a bent trajectory |
| depth/range semantics | Any4D's `depth_along_ray` compared numerically against `‖pts3d_cam‖` | equal to **1.4 × 10⁻⁶**; stored unmodified as `range_along_ray` with `path_source = "ray_range_approx_water_path"` |
| pose convention | composed both directions against the model's own `pts3d`, at frames 1/3, 2/3 and the end — never frame 0, where this family's world frame is the identity | cam2world residual **9.5 × 10⁻⁷** vs world2cam **1.2 × 10¹**, a ratio of 1.3 × 10⁷. The control is emphatically not a no-op |
| preprocessing / FOV confounds | source→grid map **measured** with markers through Any4D's own preprocessing; footage capture metadata parsed | Any4D 294×518 / 518×294, **0 of 25 markers lost** in both orientations; `wreck_01`'s portrait FOV confound *disproved* for the classical arm from metadata |
| scale / gauge | one global scale per method-pair per clip everywhere; per-frame fits diagnostic only; trajectories aligned with exactly one similarity, residual normalised by extent | no per-frame normalisation anywhere; no local scaling, no nonlinear remapping |
| run-to-run instability | every hypothesis given a measured noise floor in the **shape** metric | see §9.1. It changed a conclusion — see 11.2 |
| degenerate reconstructions | screen on every arm: observations below 10⁻³ of the clip median, and the per-frame median-range ratio | fired on **exactly one** arm of the ~50 run (`A_global_cal`/`wreck_03`), which had the *best* reprojection error of its three |
| view-count confounds | the challenger could only run 16 views, so the incumbent was **re-run at 16 views** | MapAnything's failure is view-count-independent, removing the confound outright |
| unsupported correctness claims | full-text sweep for correctness language | every occurrence is an explicit denial or a measured-instability statement; no arm is called more correct than another anywhere |
| Phase 3A comparison rules | correspondence by image observation only; every dense method reported separately against A and C_off; neither merged nor treated as truth | obeyed; `Y_any4d vs C_off` on `wreck_03` matched only 6 frames (C_off registered 17/48 there) and is therefore **not quoted** |

### 11.2 What the review actually caught

Four things, recorded because each changed something that had already been
written down.

1. **A conclusion that was noise.** The `wreck_05` frame-schedule effect (10.8 %
   median, 49.8 % range swing) had been written up as a real result. Its repeat
   run then measured S25's own spread at **32.9 % median / 141.4 % range swing** —
   three times larger. The claim was withdrawn and reclassified
   `not_identifiable`. Without the repeat it would have been reported as a
   finding.
2. **A factual error in my own summary.** The draft called SIFT + LightGlue "the
   one configuration that improved registration anywhere in this phase". The
   global mapper reached **48/48** on `wreck_01` and `wreck_03` — better than F2's
   47/48 — and does it in seconds. Corrected in §3.4 and in the fallback list,
   and F2's registration credential narrowed to the ALIKED rescue, whose
   magnitude (32/48 → 48/48) is unambiguous, rather than a single frame whose
   noise is unmeasured.
3. **An over-general grouping.** The draft claimed "the three high-observation
   clips self-calibrate to 1 042–1 108 px". `wreck_03` is not one of them: its
   incremental focal lands in that band but the global mapper moves it to 1 258.9
   (+21 %). The claim was replaced with the full per-clip table, an explicit
   warning that arm counts differ from 3 to 15 so max−min is not comparable
   across rows, and the apples-to-apples four-camera-model comparison as the
   statement that actually carries weight.
4. **A silently unapplied mask, nearly.** Any4D's first run reported "valid 1.00",
   which could equally have meant a perfect mask or a mask whose shape check
   failed and was skipped. The driver was instrumented to record the mask's raw
   shape, whether it was applied and its true-fraction, and both clips re-run: it
   **is** applied, at 294×518, with a true-fraction of exactly **1.0000 on every
   frame**. So the coverage number means "the model asserts everything", which is
   Phase 3A §5.1's warning, not perfect coverage — now established instead of
   assumed.

### 11.3 One methodological point worth carrying forward

Three of the four catches above came from the same discipline: **measuring the
instrument's own spread in the units the conclusion is stated in.** Phase 3A
measured configuration A's repeat spread in registration and point count and said
explicitly that this did not bound a range-shape effect. Phase 3B measured it in
range-shape, and that single change turned one reported effect into noise
(`wreck_05` schedules), promoted another to ~300× its floor (`wreck_01`
schedules), and showed a third clip's apparent stability was genuinely at its own
noise (`cenote_01`). Any future phase should budget for the repeat runs before
the headline runs, not after.
