# Week 3 — multi-view geometry landscape: research note

**Date of pass: 2026-08-30.** One comprehensive pass, intended to freeze the
Week 3 experiment before implementation. `PLAN.md` carries the experimental
design and the decision rules; this file carries the evidence, the licences,
the integration facts, and the rejected alternatives.

Scope: what supplies **per-pixel range for range-dependent underwater
restoration**, not what wins a reconstruction leaderboard. Single-image depth
is Week 4 and is deliberately excluded here.

---

## 0. The three findings that actually shaped the design

### 0.1 Reprojection error is disqualified as the master metric — with underwater evidence

Refractive COLMAP (She, Seegräber, Nakath, Köser, IROS 2024, arXiv:2403.08640)
report, on their 5 740-image AUV seafloor dataset, that the **ordinary pinhole
treatment of underwater imagery achieved 0.277 px reprojection error while
producing "a severely distorted reconstruction" with a curved seafloor**;
refractive SfM reached 0.199 px *and* correct geometry. A bundle adjuster
minimising reprojection error will happily report a good number for a
systematically wrong world.

This is a stronger version of the Phase 2A lesson (leaderboard rank
anti-predicted usefulness) and it is why the Week 3 protocol scores
scale-aligned range residual and restoration sensitivity, not reprojection
error.

### 0.2 The same paper's *GoPro flat-port* experiment found refraction did not matter

Same paper, real tank experiment, **underwater GoPro with a calibrated flat
port**: model error was **2.061 mm for the pinhole treatment vs 2.103 mm for
refractive SfM** — the refractive model was very slightly *worse*. The authors
attribute the absent advantage to the small camera-to-interface distance
(< 2 mm) and the small scene.

That is our camera and roughly our working distance. The refraction advantage
in that paper is demonstrated at AUV-survey scale, not at diver-held
close-range scale. So the honest Week 3 prior is:

> Flat-port refraction is real, is non-central, and is range-coupled — and is
> also plausibly **below the restoration-relevance threshold for a GoPro at
> reef distances**. Week 3 must measure this rather than assume either way.

### 0.3 Global range scale is *exactly* absorbable by jointly fitted coefficients

For the standard image-formation model used from Week 5 onward,

```text
I_c = J_c · exp(−β_att,c · d) + B∞_c · (1 − exp(−β_bs,c · d))
```

the substitution `d → s·d`, `β_att → β_att/s`, `β_bs → β_bs/s` leaves `I_c`
unchanged. Global range scale is therefore **not identifiable at all** from a
single clip with free coefficients, and costs nothing when it is wrong.

It becomes identifiable, and starts to matter, only through external metric
evidence, and only where one of these holds:

- `β` must be physically meaningful (comparable to a water type),
- `β` is shared or transferred across clips,
- a light source with a distance-dependent falloff is introduced (Week 6B),
- range feeds anything with an absolute length scale.

Consequence for Week 3: **metric-scale claims by learned models are a
convenience, not a requirement**, and the gate weights *shape* error far above
*scale* error. This sharpens the prior already in `PLAN.md` rather than
contradicting it.

---

## 1. Underwater flat-port geometry — what is and is not a substitute

### 1.1 The physical fact

Behind a flat port, rays refract twice (water → port → air). The refracted
rays do **not** share a single centre of projection; they intersect a common
axis defined by the camera centre and the interface normal. The system is an
**axial / non-central** camera. Refractive COLMAP models exactly this, by
replacing each ray with a virtual pinhole camera placed where the refraction
axis meets the refracted ray, parameterised by interface normal `n_int`,
camera-to-interface distance `d_int`, interface thickness, and the refractive
index ratios.

Crucially, they state the pinhole approximation is **range-dependent**:
symmetric refraction through an orthogonal flat port partly absorbs into radial
distortion **for a specific working distance**, and fails across varied scene
scales. That gives Week 3 its sharpest diagnostic:

> Flat-port model error is a joint function of **image radius and range**.
> Pure lens distortion is a function of image radius alone.
> If the residual separates in radius only, the intrinsics have absorbed it.
> If it is radius × range coupled, the camera model is the bottleneck.

### 1.2 Generic "any camera model" methods are CENTRAL and are not substitutes

Checked against the actual formulations, not the marketing:

**GenSfM** — *Structure-from-Motion with a Non-Parametric Camera Model*, Wang,
Pan, Pollefeys, Larsson, CVPR 2025. §3, verbatim: *"We assume that the camera
is **radially symmetric** and that the principal point is known … the
intrinsics calibration of the camera can be modeled as a mapping between the
opening angle θ, i.e. angle to the principal axis, and the image radius r."*
One centre, one direction per radius. **Central.** Repo `Ivonne320/GenSfM`, a
COLMAP fork exposing an `IMPLICIT_DISTORTION` camera model; 75 stars, last push
2025-06-18; no SPDX licence detected.

**AnyMap** — Dal Cin, Dikov, Ju, Ghafoorian (Qualcomm XR Labs), CVPR 2025 pp.
16674–16684. §3.1, verbatim: *"The unprojection function π⁻¹ : Ω → S² maps x to
the directions s = (ψ,φ) of the incoming light ray on the unit sphere S²"*, and
`X_cam(x) = r·[sinψcosφ, sinψsinφ, cosψ]ᵀ`. Every ray originates at the camera
origin; only the direction is learned. **Central.** It also assumes constant
intrinsics and, when modelling radial distortion only, collapses to a 1-D map
ρ ↦ ψ.

Both can absorb the *directional* part of flat-port refraction. Neither can
represent the per-pixel **ray-origin shift along the axis**, which is precisely
what makes flat-port error range-dependent. **Neither is a substitute for
Refractive COLMAP.** They may still be useful as a probe of "how much of the
refraction can a flexible central model soak up", which is a different and
weaker claim.

One incidental but genuinely useful detail from AnyMap: it parameterises
geometry as a **range map along the ray**, not planar z-depth — closer to what
attenuation integrates over than planar z is.

**But it is still not quite the right canonical quantity here, precisely because
of §1.1.** Attenuation acts over the path through *water*; ray range from the
mathematical projection centre charges the air-and-glass segment to the water
budget, and — the real problem — it re-imposes a central camera on the one
configuration built to reject one. The Week 3 representation therefore makes
`water_path_length` canonical, keeps `range_along_ray` as the central-model
approximation every learned model natively emits, and records which is which in
`path_source`. Numerically the two agree here (millimetre housing offset against
metre-scale scenes); conceptually the distinction is what stops the refraction
experiment from being quietly undone by its own output format.

### 1.3 Refractive COLMAP is still the strongest open refractive SfM in 2026

No materially better open refractive SfM appeared in the search. What exists:

- **`the-sauer/colmap_underwater`** — the implementation of the IROS 2024
  paper (the authors' canonical host is a Kiel GitLab instance:
  `cau-git.rz.uni-kiel.de/inf-ag-koeser/colmap_underwater`). Flat **and** dome
  port; `enable_refraction` toggles in reconstruction, matching and BA;
  navigation-prior support. BSD (COLMAP's licence; GitHub reports
  `NOASSERTION`). README: *"Building COLMAP Underwater from source is exactly
  the same as building the original COLMAP since there is no extra
  dependency."*
- **Practical caveat that shapes the experiment:** its `CMakeLists.txt` says
  `COLMAP_VERSION "3.10-dev"`. Upstream COLMAP is at **4.1.1 (2026-07-17)**.
  The fork therefore has **no ALIKED/LightGlue, no global mapper, no random-seed
  reproducibility (added 3.13), no OpenImageIO**, and its database format is
  documented as incompatible with mainline COLMAP. 14 stars, last push
  2025-05-22.
  → The refraction axis must be run as `enable_refraction` **off vs on inside
  this one binary**. Comparing mainline 4.1 against the fork would confound the
  camera model with two years of unrelated COLMAP change.
- Side branches exist (`refractive_dense_variant1/2/3`,
  `refractive_dense_decenter_approximative_camera`,
  `refractive_dense_multiple_cameras`) — experimental refractive dense work,
  research shelf only. The paper itself does **not** extend MVS to refraction.
- The paper's own limitation: `d_int` is recoverable only up to scale without
  external scene scale, and their relative-pose step uses a 5-point solver on an
  approximated perspective camera ("BestApprox"), costing up to 2 % inlier
  ratio.

**Pinax** (Łuczyński, Pfingsthorn, Birk, *Ocean Engineering* 2017; code
`tomluc/Pinax-camera-model`, mirror `fickrie67/…`) is the low-complexity
refractive control: a virtual-pinhole/axial hybrid that precomputes a
correction lookup table, accounts for the refractive index of water including
salinity, and — the reason it belongs here — **can be calibrated from in-air
calibration only**, no pool checkerboard required.

Refractive COLMAP criticises Pinax for *"requir[ing] a small camera-to-interface
distance in the order of millimeters, assum[ing] a fixed scene distance"* and
for not allowing refractive refinement inside BA. Note that the first of those
conditions is **satisfied**, not violated, by a GoPro: the lens cover sits
essentially on the lens. Pinax is therefore an unusually well-matched cheap
control for this project specifically, and it is filed as a conditional
challenger rather than dismissed.

Dome ports are out of scope: a pinhole at the centre of a spherical port sees
no refraction; our camera has a flat cover.

---

## 2. Classical and hybrid SfM — current state

**COLMAP 4.1.1 (2026-07-17)**, 4.1.0 (2026-06-26), **4.0.0 (2026-03-14)**,
3.13.0 (2025-11-07). Relevant facts:

- **4.0.0 integrated the GLOMAP global SfM pipeline into COLMAP** as a
  first-class alternative mapper (`global_mapper`, `automatic_reconstructor
  --mapper GLOBAL`). The standalone `colmap/glomap` repo was **archived
  2026-03-09**. There is no reason to install GLOMAP separately.
- **4.0.0 added ALIKED feature extraction and LightGlue matching via ONNX**
  (`-DONNX_ENABLED=ON`). Extractors: `SIFT`, `ALIKED` (`aliked-n16rot` faster
  and viewpoint-invariant, `aliked-n32` more accurate), and `LoMa` (DeDoDe-based,
  `LOMA_B`/`LOMA_B128`/`LOMA_R`/`LOMA_L`/`LOMA_G`). Matchers: `SIFT_BRUTEFORCE`,
  `SIFT_LIGHTGLUE`, `ALIKED_BRUTEFORCE`, `ALIKED_LIGHTGLUE`, LoMa variants.
  COLMAP's own guidance: LightGlue *"typically produces more matches and higher
  inlier ratios than brute-force matching, especially for challenging image
  pairs with large viewpoint or illumination changes."* Extractor and matcher
  families must not be mixed in one database.
- **3.13.0 added random-seed support for reproducible reconstruction.** This is
  what makes COLMAP admissible under the project's standing determinism
  requirement for measurement instruments.
- **Dense reconstruction is CUDA-only.** COLMAP FAQ, verbatim: *"If you do not
  have a CUDA-enabled GPU but some other GPU, you can use all COLMAP
  functionality **except the dense reconstruction part**."* Feature
  extraction/matching and mapping run on CPU.
- macOS/ARM64: an official Mac CI workflow exists and ONNX Runtime FetchContent
  gained ARM64 support; ONNX must still be explicitly enabled at build time.

**GLUEMAP** — *Global Structure-from-Motion Meets Feedforward Reconstruction*,
Pan, Schönberger, Pollefeys, **CVPR 2026**, arXiv:2605.26103, repo
`colmap/gluemap` (BSD-3, 343 stars, pushed 2026-06-22). Pipeline: SALAD
retrieval → optional Doppelgangers++ two-view disambiguation → feed-forward
star-graph local inference (`pi3` default, `pi3x`, `vggt`, `map_anything`) →
rotation/intrinsics/similarity averaging + global BA → SIFT track snapping with
augmented BA. Outputs a **COLMAP sparse reconstruction — poses and sparse
structure, no dense depth.** Has `is_sequential` / `sample_frequency` for
ordered video. Needs four checkpoints (Pi3, SALAD, VGGSfM tracker,
Doppelgangers++). INSTALL.md, verbatim: **"GLUEMAP requires CUDA at runtime —
the GPU PyTorch build is the only supported configuration."**

**MP-SfM** — Pataki, Sarlin, Schönberger, Pollefeys, CVPR 2025,
arXiv:2504.20040, `cvg/mpsfm`, **Apache-2.0**, last push 2025-07-09. Injects
monocular depth and normal priors into classical SfM; targets low parallax, low
overlap, high symmetry; registers low-overlap images by absolute pose from
depth-lifted points. Conditional challenger for the weak-triangulation failure.

**Dense-SfM** — Lee & Yoo, CVPR 2025, arXiv:2501.14277. Dense matching plus a
Gaussian-Splatting-based track extension and a transformer/GP multi-view
kernelised refinement; targets **texture-poor** scenes (ETH3D, Texture-Poor
SfM). Conditional challenger for the low-texture failure. Note the released
repo reportedly omits the GS track-extension stage, which lowers its value as a
turnkey reproduction — verify before integrating.

---

## 3. Feed-forward geometry — the frontier, and the licence reality

| Method | Venue / date | Outputs | Scale | Code / ckpt licence | Hardware |
|---|---|---|---|---|---|
| **MapAnything** | 3DV 2026, arXiv:2509.13414, `facebookresearch/map-anything` | `pts3d`, `pts3d_cam`, `depth_z`, `depth_along_ray`, `ray_directions`, `camera_poses`/`cam_trans`/`cam_quats`, `conf`, `mask`, `non_ambiguous_mask`, `metric_scaling_factor` | metric when inputs give scale; `is_metric_scale` flags | **code Apache-2.0**; `facebook/map-anything` CC-BY-NC-4.0, **`facebook/map-anything-apache` Apache-2.0** | CUDA per README; memory scales with view count (up to 2000 views @140 GB in memory-efficient mode) |
| **VGGT-Ω** | **CVPR 2026 Oral**, arXiv:2605.15195, `facebookresearch/vggt-omega` | camera (quat, translation, FoV) + depth + confidence; point maps/tracks are training-time auxiliaries | metric (absolute translations and depths) | **FAIR Noncommercial Research License**; HF checkpoints **gated (approval required)** | CUDA; 1B-512 peak GPU mem 6.02 GB @1 frame, 13.37 GB @100, 43.15 GB @500 |
| **Pi3 / Pi3X** | **ICLR 2026**, arXiv:2507.13347, `yyfz/Pi3` | affine-invariant poses, scale-invariant local point maps, confidence; Pi3X adds conditional injection of pose/intrinsics/depth and **approximate** metric scale | scale-invariant (Pi3), approx metric (Pi3X) | **BSD-3-Clause** | CUDA |
| **Depth Anything 3** | **ICLR 2026**, arXiv:2511.10647, `bytedance-seed/depth-anything-3` | depth + ray map + camera extrinsics/intrinsics + confidence; any-view (1..N), `DA3-Streaming` for long video under 12 GB | relative; `DA3Metric-Large` metric | **code Apache-2.0**; Base/Small/Metric-Large Apache-2.0, Large/Giant CC-BY-NC-4.0 | CUDA (xformers) |
| **Wat3R** (Ren et al.) | **ECCV 2026 Oral**, arXiv:2607.08772, `LSXI7/Wat3R` | poses, per-view depth, world point maps, confidence | not claimed metric | **Apache-2.0**, checkpoint `lsxi77777/Wat3R` on HF, Water3D dataset released | CUDA checks + bf16/fp16 autocast |
| **WAT3R** (Xu et al.) | arXiv:2607.21023, 2026-07-23 | point maps, poses, depth, **plus restored clean images and global water parameters** | "metric scale via physics-guided supervision" | paper CC-BY-4.0; code/weights not confirmed released | — |
| CUT3R | CVPR 2025 Oral, arXiv:2501.12387 | online metric point maps, persistent state | metric | `NOASSERTION` | CUDA; repo last pushed 2025-08 |
| MASt3R-SfM / DUSt3R / MUSt3R | 2024–25 | matching-driven SfM, point maps | varies | **CC-BY-NC-SA-4.0**, checkpoint dataset terms are additionally restrictive (mapfree in particular) | CUDA |

### 3.1 VGGT-Ω carries a published contamination notice

The `facebookresearch/vggt-omega` README states (dated **2026-08-18**): *"We
recently became aware of an issue that may have caused benchmark contamination
in an ancestor checkpoint of the released 1B model"*, which may have inflated
the reported Tables 1–2. The model is said to still work for downstream use.

Combined with the FAIR Noncommercial licence and gated checkpoints, this makes
VGGT-Ω a poor **primary** integration for a project whose operating rule is
"do not integrate on leaderboard position". It stays available as a
harness-swappable backbone, which costs nothing.

### 3.2 The harness question (research Q10) has a clean answer

`facebookresearch/map-anything` ships `mapanything/models/external/` containing
wrappers for **DA3, DUSt3R, MASt3R, MUSt3R, Pi3, MoGe, AnyCalib** (and, per the
model docs, VGGT and VGGT-Omega), whose stated purpose is *"external model code
that we use to train and benchmark external models fairly"*, all emitting the
MapAnything field convention above. Some wrappers (VGGT-Omega, MUSt3R) load
checkpoints through Hydra configs and need their optional deps installed.

So: **use MapAnything's external-model interface as the wrapper for the learned
half of the bakeoff, and adopt its field names as our own output convention.**
That removes the need to write per-model wrappers and removes the need to
invent a schema. It is an evaluation convenience, not a permanent project API.

### 3.3 Underwater domain adaptation is a real, separate family (new since the original plan)

Two independent July 2026 papers, confusingly both called Wat3R:

- **Wat3R**, Ren, Jiang, Song, Xu, Lin, Liang, Bai (HUST), ECCV 2026 Oral,
  arXiv:2607.08772. VGGT adapted by **cross-domain semi-supervised mean-teacher
  training**: labelled synthetic underwater renderings of terrestrial RGB-D
  data, plus **~359 k unlabelled real underwater frames** filtered from ~10 000
  videos, with a cross-view consistency loss. Reported +12.1 % multi-view depth
  over VGGT on **Sea-thru**, +13.1 % on FLSea Stereo, 43 % relative-error
  reduction in monocular depth on FLSea VI. Beaten baselines include Fast3R,
  MapAnything, Pi3, DA3, VGGT, WaterSplatting, COLMAP variants, UDepth,
  UW-Depth, WaterMono. **Apache-2.0, code + checkpoint + Water3D dataset
  released.**
- **WAT3R**, Xu, Lu, Zheng, Tan, Zhu, Liu, Yeung (HKUST/CUHK/PKU),
  arXiv:2607.21023. Pi3 backbone + a neural degradation-adaptation module +
  a water-parameter head; DPT head replaces pixel-shuffle upsampling to kill
  grid artifacts. −15 % Abs Rel vs Pi3 on FLSea-Canyons (0.0693 vs 0.0819; DA3
  0.0929), +21.2 % RPE-rot vs Pi3. Code release not confirmed.

**Both address the radiometric domain shift only.** Neither models refraction;
both assume a pinhole camera with depth-dependent radiometric degradation. That
is the clean statement for the plan: underwater feed-forward adaptation and
refractive SfM fix *different* problems and are complementary, not competing.

The second paper's water-parameter head is an interesting overlap with Weeks
5–6 and is explicitly **not** adopted — Week 3 buys range, not a restoration
model.

---

## 4. Video specialists

**MegaSaM** — Li et al., arXiv:2412.04463, `mega-sam/mega-sam`, **Apache-2.0**,
1355 stars, last push 2026-01-05. Differentiable BA layer plus an
uncertainty-aware global BA; designed for casual dynamic video with little
parallax, unknown FoV, moving objects; outputs camera parameters and dense
video depth. Genuinely the right tool for the named failure.

Cost is the problem. README pins **Python 3.10, CUDA 11.8, PyTorch 2.0.1**, and
installs **xformers from a prebuilt `linux-64 … cu11.8 pyt2.0.1` archive**.
That is a Linux+CUDA-only, frozen, two-generation-old stack. It is a conditional
challenger with a real integration bill, and the plan says so.

**Streaming VGGT family** — StreamVGGT (ICLR 2026, `wzzheng/StreamVGGT`, 960
stars, last push 2025-10-27), plus 2026 follow-ups addressing its unbounded
KV-cache growth (XStreamVGGT, FrameVGGT, IncVGGT, LongStream). Relevant only if
long-sequence drift becomes a demonstrated failure; our clips are 10–25 s.

---

## 5. Underwater reconstruction benchmarks — useful context, not candidates

- **BALTIC** (Grimaldi, Nakath, Pizarro, Scharff Willners, Carlucho, Petillot,
  arXiv:2604.19133, 2026-04) — 13 controlled datasets, **two media (air/water)
  × three lighting conditions (ambient / artificial / mixed)**, water tank,
  ground-truth poses from an HTC Vive tracker. Evaluates COLMAP, NeRF and 3DGS.
  Finding: 3DGS with basic white-balance preprocessing matches specialised
  underwater methods **under controlled texture-consistent conditions**, and
  robustness falls off in complex real environments. Cross-domain trick:
  augment underwater sequences with a few in-air views under similar lighting.
  Takeaway adopted: **lighting regime is a first-class acquisition axis**, which
  is why the controlled clip specifies diffuse ambient and the artificial-light
  case is quarantined into the difficult clip (and into Week 6B).
- **FLSea** (Randall & Treibitz) — 22 451 frames, RGB + metric GT depth from
  photogrammetry, 12 sites, 5 stereo + 8 visual-inertial sets, 3–8 m depth,
  natural reef and man-made structure. **Sea-thru** — 1 100 underwater images
  with range maps. Both public. Used in Week 3 only as a **wrapper-validation
  set**, the geometry analogue of the Phase 2A synthetic known-motion check: if
  a wrapper cannot reproduce published numbers on FLSea, its numbers on our
  footage mean nothing.
- ISPRS Archives XLVIII-2/W10-2025 pp. 199 (Muhammad, Mugiaraya, Alodia,
  Sternberg, 2025-07-07) compares refraction-aware SfM (UW-Colmap), HLOC, and
  Gaussian Splatting on a dual air/underwater dataset; concludes RSfM + GS is
  the most reliable pipeline and that *"deep learning methods are best applied
  at the feature level, followed by structured SfM for accurate geometry."*
  That is an independent third-party vote for our A/B feature axis and for
  keeping classical geometry in the loop.
- Underwater NeRF/3DGS (SeaSplat ICRA 2025, UW-3DGS AAAI 2026, WaterSplatting,
  DualPhys-GS, RUSplatting, Gaussian Splashing, refraction-aware GS for shallow
  bathymetry) — per-scene optimisation for novel-view synthesis. Different
  objective, no per-frame range estimator for arbitrary new video. **Rejected
  for Week 3.** Some are relevant later as illumination/medium references.

---

## 6. Hardware reality on this machine

Target machine: **MacBook Air M4, 10 cores, 24 GB unified memory, macOS 26.6.2.
No CUDA, no NVIDIA GPU.** Precedent from Phase 2A: PyTorch on MPS, 2.2–22.8 GB
peak, one model per process, isolated venvs per repo.

| Component | On the M4 | Note |
|---|---|---|
| COLMAP 4.1 sparse (SIFT / ALIKED+LightGlue / incremental / global mapper) | **yes** | CPU; ONNX Runtime ARM64 for the learned front-ends; `-DONNX_ENABLED=ON` needed |
| COLMAP dense (PatchMatch stereo) | **no** | CUDA-only, per COLMAP FAQ. The classical arm is sparse-only locally |
| `colmap_underwater` refractive SfM | **probably** | "no extra dependency" over COLMAP; 3.10-dev era, so verify the build |
| Pinax LUT pre-correction | **yes** | CPU image warp |
| Feed-forward torch models (MapAnything, Pi3X, DA3, Wat3R, VGGT-Ω) | **partly** | float32 on MPS, bounded frame counts; every repo assumes CUDA (bf16 autocast, xformers, flash-attn). Expect per-model patching. A community `vggt-mps` port exists (float32 only, no fp16 autocast on MPS) |
| **GLUEMAP** | **no** | INSTALL.md: "requires CUDA at runtime — the GPU PyTorch build is the only supported configuration" |
| **MegaSaM** | **no** | CUDA 11.8 + prebuilt linux-64 xformers + DROID-style CUDA ops |
| **Depth Anything 3** | **no** (as shipped) | xformers |
| **MapAnything** | **yes, try locally first** | **MPS inference support added 2026-03-23 (`facebookresearch/map-anything` #131).** The README quickstart still shows the older `cuda if available else cpu` line, which is what made the first pass call it CUDA-only. Profile it at 40–80 views on 24 GB before renting anything |

**Conclusion:** the bakeoff splits rather than being wholly blocked.

- **Local:** COLMAP 4.x sparse (A, B), `colmap_underwater` (C), Pinax, and
  **MapAnything (D) on MPS** — attempt before renting, and fall back on measured
  cost, not assumption.
- **Rented GPU:** GLUEMAP (explicit "requires CUDA at runtime"), Wat3R, MegaSaM
  if triggered, COLMAP dense if ever justified.

Do **not** assume one session or one environment covers the GPU set: MegaSaM
pins CUDA 11.8 / PyTorch 2.0.1 with a prebuilt `linux-64` xformers, while
GLUEMAP's supported recipe is CUDA 12.4 / PyTorch 2.4.1 from conda-forge. Those
are mutually incompatible. Batch GPU-only candidates into as few short
reproducible sessions as practical, each in its own pinned environment or
container, and profile before sizing the card. Every artifact is persisted in
the common representation so the rest of the project stays laptop-local.

This is a real, named and now correctly-scoped blocker, and it is in `PLAN.md`.

**Correction, first pass → second pass.** The first pass listed MapAnything as
categorically CUDA-only on the strength of its README device line. That was
wrong: MPS inference support was merged 2026-03-23. Recorded here because the
project's rule is to say what changed rather than quietly restate.

---

## 7. Rejected, with reasons

- **GenSfM** — central + radially symmetric by explicit assumption (§3). Cannot
  represent flat-port ray-origin shift. Not a refraction substitute. Old COLMAP
  fork, no clear licence.
- **AnyMap** — central by explicit formulation (π⁻¹ : Ω → S², rays from the
  origin). Same verdict. Its range-along-ray parameterisation was borrowed; the
  method was not.
- **VGGT-Ω as a primary** — FAIR Noncommercial licence, gated checkpoints, and a
  self-reported benchmark-contamination notice on the released 1B checkpoint.
  Retained as a zero-cost harness backbone.
- **MASt3R-SfM / DUSt3R / MUSt3R / CUT3R** — superseded for this purpose and
  CC-BY-NC-SA with additional restrictive checkpoint dataset terms; CUT3R's repo
  is a year stale. Reachable through the harness if the learned candidates
  disagree.
- **Standalone GLOMAP** — archived 2026-03-09; its functionality is COLMAP's
  `global_mapper`. Use that.
- **Depth Anything 3 as a Week 3 primary** — it is the natural **Week 4**
  monocular baseline, and its multi-view mode is reachable through the harness.
  Integrating it twice would blur the Week 3 / Week 4 boundary the plan
  deliberately maintains.
- **Underwater NeRF / 3DGS** — wrong objective (novel-view synthesis), per-scene
  optimisation, no range estimator for new video.
- **WAT3R (Xu et al.)** — no confirmed code/weights release. Watchlist.
- **PMVS2 / COLMAP-CL / OpenMVS as a CPU dense-MVS substitute** — considered for
  laptop-local dense range from classical poses; rejected as unnecessary
  scaffolding once the rented-GPU session is accepted, and because the feed-forward
  arm already supplies dense range. Revisit only if the rented session is refused.
- **Custom neural refractive SfM** — only after Refractive COLMAP is
  demonstrated inadequate, per the project's earn-your-complexity rule.
- **Dome-port modelling** — not our camera.

---

## 8. Open items deliberately left open

1. Whether `colmap_underwater` 3.10-dev builds cleanly on macOS ARM. Cheap to
   settle; do it first, before any acquisition.
2. Whether ONNX/ALIKED is enabled in the available COLMAP build, or whether a
   source build with `-DONNX_ENABLED=ON` is needed.
3. Measured GoPro flat-port thickness and camera-to-interface distance. Needed
   only if the shape test fires; record with an explicit uncertainty either way.
4. Determinism of each learned candidate under repeated inference on identical
   input. The project already treats non-reproducibility as disqualifying for a
   measurement instrument (FlowIt was dropped for exactly this). Verify before
   trusting any number.
