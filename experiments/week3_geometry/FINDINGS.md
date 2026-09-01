# Week 3 Phase 3A — geometry bakeoff findings

**Status: complete.** This is the authoritative Phase 3A report. `PLAN.md` holds
the experimental design and decision rules; `GEOMETRY_LANDSCAPE.md` holds the
candidate evidence, licences and rejected alternatives; this file holds what
actually happened when the predeclared configurations were run on this
project's own footage.

**Run status — generated from `scripts/check_completeness.py`, not written by
hand.** `55/55 complete; 0 need re-running (method_failure entries are RESULTS, not gaps, and are not re-run)`

Every predeclared configuration is complete on all six clips: **A, B, C_off,
C_on, D, E0 and E**, plus the repeat runs and the four flat-port diagnostics
(`C_on_null`, `C_on_thick`). Nothing in this report is marked pending, and no
claim rests on an unfinished run. `method_failure` entries — chiefly C_on's
failures to reconstruct — are **results**, not gaps, and are analysed in §4.4.

To reproduce every table from the persisted artifacts:

```bash
.venv/bin/python -m experiments.week3_geometry.scripts.check_completeness
.venv/bin/python -m experiments.week3_geometry.scripts.compare \
    --out experiments/week3_geometry/outputs/stage6/comparison.json --overwrite
.venv/bin/python -m experiments.week3_geometry.scripts.tables
```

**Read this first.** There is **no independent range measurement anywhere in
this phase.** The C2 scale-and-range acquisition `PLAN.md` specifies does not
exist yet. Every cross-method number below is therefore a **consistency**
statement and never a correctness one. Sparse SfM is not the ruler — it is one
of the candidates under test. Nothing here is ground truth.

---

## 1. Data

### 1.1 The representative subset

Six development clips, **selected and frozen before any geometry method was
run** (`configs/phase3a_clips.json`, committed). Selection used manifest
metadata, a cheap mechanical inspection pass (`outputs/stage1/clip_inspection.json`)
and 8–12-frame contact sheets. No optical flow, SfM or learned model was run to
rank clips, per the Phase 3A inspection budget.

Every configuration saw **the same 48 frames per clip, extracted once**
(`scripts/extract_frames.py`), at a long side of 1280 px, resampled in linear
light and written as sRGB PNG. Filenames carry the **source** frame index, so
every downstream artifact traces back to the clip.

| clip | role in the bakeoff | frames | source grid | why it is here |
|---|---|---|---|---|
| `wreck_07` | anchor / bring-up: clean rigid wreck, arc motion | 8–206 (48) | 720×1280 | Highest-texture wreck in the dev set (median Laplacian variance 111, 4000/4000 GFTT corners, 0.91 grid coverage). Camera arcs around an encrusted superstructure and closes to near range late — viewpoint change **plus** a near/mid range span, which both triangulation and the radius×range test need. No diver, ambient light, 0.42 stops of illumination variation. |
| `wreck_05` | second wreck: different range and texture regime | 8–214 (48) | 720×1280 | Deliberately unlike `wreck_07`: a lateral glide along a hull edge at roughly constant mid range, much lower texture (Laplacian variance 23.6) and lower contrast, with an out-and-back sweep giving a natural revisit. Carries the low-parallax risk on purpose. |
| `cenote_01` | geometry-rich cavern swimthrough | 15–378 (48) | 720×1280 | The only cenote clip lit by **ambient** daylight rather than a diver's torch, so it isolates geometry from the moving-light confound Week 6B owns. Stalactite ceiling gives dense near relief while the open water below is effectively at infinity — the widest near/far span in the subset. 59.94 fps, so 48 frames span only ~6 s. Confound: a halocline layer inside the water column. |
| `swimthrough_02` | ordinary reef swim-through — the realism case | 6–169 (48) | 720×1280 | Representative ordinary diver-held footage: forward swim with lateral drift through a coral channel, good visibility, ambient light. Highest texture in the whole dev set (Laplacian variance 656). Confounds: an in-clip GoPro auto-white-balance shift around frames ~140–166, swaying soft coral, a distant diver, and parallax weakest near the direction of travel. |
| `wreck_01` | low-texture / difficult | 1600–2100 (48) | 1280×720 (portrait) | The second half of this 97 s clip is an extended close pass over a mottled, low-relief encrusted surface — repetitive, low-contrast, self-similar texture, i.e. the named low-texture hypothesis. The window sits well clear of the content transitions the cut scan flagged at frames 865 and 885. Confounds: portrait decode, and a near-planar scene, so triangulation is ill-conditioned by construction. |
| `wreck_03` | dynamic-subject / stress | 25–596 (48) | 720×1280 | A large wreck with a diver occupying a substantial fraction of the frame across much of the clip, plus exhaust bubbles, haze, and the largest scene-range span of the wreck clips. 2.09 stops of illumination variation. |

Considered and not selected, with reasons, is recorded in the same config file
(`wreck_02` sun-backlit at 3.27 stops; `wreck_04` at 7.08 stops with three
candidate cuts; `wreck_08` a dive-light interior shot that belongs to Week 6B;
`wreck_10` diver plus blurred tail; `wreck_11` duplicated `wreck_07`'s role and
is the first alternate; `swimthrough_03` duplicated `swimthrough_02`;
`cenote_02..05` all carry a moving torch; the open-water encounter clips have
little rigid static structure).

**These are development clips, not a held-out test set.** They were inspected
during selection. The five `frozen_eval` clips (`distance_shot`,
`light_night_dive`, `murky_eel`, `murky_shark`, `swimthrough_01`) were
deliberately not used here and remain conceptually separate.

### 1.2 What the subset does and does not span

It spans: rigid high-texture structure with real viewpoint change; rigid
low-texture structure with near-lateral motion; extreme near/far range span;
ordinary forward-dominated reef swimming; a near-planar low-texture close pass;
and a large moving foreground subject. Illumination variation runs from 0.28 to
2.09 stops.

It does **not** span: any clip shot deliberately for geometry (no C1); any
independently measured distance or scale (no C2); artificial-light-dominated
scenes (deliberately excluded — Week 6B); or any scene with a known object of
known size.

---

## 2. Methods

### 2.1 Candidate accounting

Ten configurations across six families. A–F were predeclared in `PLAN.md`; E0, G,
H, I and J were added by amendment during execution and are the final additions —
the landscape is now frozen.

| | configuration | family / hypothesis | status |
|---|---|---|---|
| **A** | COLMAP 4.1.1 · SIFT · incremental | classical interpretable control | **executed** |
| **B** | COLMAP 4.1.1 · ALIKED_N32 + LightGlue · incremental | correspondence axis (same mapper, learned front end) | **executed** |
| **C_off / C_on** | `colmap_underwater` 3.10-dev, refraction OFF vs ON (FLATPORT) | flat-port camera-physics axis, paired inside one binary | **executed** |
| **D** | MapAnything | general-purpose feed-forward dense geometry — the range-supply candidate | **executed** |
| **E0** | vanilla VGGT | the non-underwater-adapted **paired control** that makes E interpretable | **executed** |
| **E** | Wat3R-Ren (Ren et al.) | underwater domain adaptation of VGGT | **executed** |
| **F** | GLUEMAP | learned local geometry + classical global optimisation | **pending_cuda** |
| **G** | AMB3R | feed-forward frontend + explicit compact 3D backend | **pending_cuda** |
| **H** | SeaVGGT | physics/self-supervised underwater adaptation | **paper_only / not_released** |
| **I** | Water-VGGT | water-condition-aware geometry | **release_incomplete** — advertised checkpoint is vanilla VGGT-1B |
| **J** | WAT3R-Xu (Xu et al.) | geometry + degradation adaptation | **paper_only / not_released** |

**Naming.** Two distinct 2026 methods are called Wat3R/WAT3R. This report uses
**Wat3R-Ren** (Ren et al., ECCV 2026 Oral — configuration E, executed) and
**WAT3R-Xu** (Xu et al. — configuration J, not released) throughout, never the
bare name.

### 2.2 Executed configurations — versions, licences, settings

**A, B — mainline COLMAP.** Homebrew `colmap 4.1.1_3`, reported as
`COLMAP 4.1.1 (Commit Unknown on Unknown without CUDA)`. **No source build was
needed for configuration B**: the Homebrew binary already links ONNX Runtime
(`libcolmap_feature.dylib -> libonnxruntime.1.dylib`, and `onnxruntime` is a
declared formula dependency), so the macOS build-scope rule never had to fire.
The build exposes extractor types `SIFT`, `ALIKED_N16ROT`, `ALIKED_N32` — there
is no bare `ALIKED` — and matcher types `SIFT_BRUTEFORCE`, `SIFT_LIGHTGLUE`,
`ALIKED_BRUTEFORCE`, `ALIKED_LIGHTGLUE`. **`LoMa` is absent from this build**, so
the Phase 3B low-texture challenger "COLMAP LoMa matchers (free, same binary)" is
*not* free here. Configuration B uses `ALIKED_N32` (COLMAP's more accurate
variant) with `ALIKED_LIGHTGLUE`; the ONNX weights are COLMAP's own release
artifacts, auto-downloaded and hash-pinned by the binary.

**C — `the-sauer/colmap_underwater`**, commit `5b73ae1a61856c4e712908a353c951a1ba2bc748`
(2024-10-29), `COLMAP_VERSION 3.10-dev`, BSD (COLMAP's licence). Built from source
on macOS ARM with `-DGUI_ENABLED=OFF -DCUDA_ENABLED=OFF -DTESTS_ENABLED=OFF`.
Two deviations from its README's "no extra dependency" claim, both recorded:
it additionally needs FreeImage (mainline 4.x has moved to OpenImageIO), and two
files in its bundled PoissonRecon **surface mesher** — code Phase 3A never
invokes — fail under current clang because of genuine upstream bugs (`Ply.h` uses
`p.value` on a nonexistent member; `SparseMatrix.inl::SetZero` references
`m_N`/`m_M` on a class whose members are `rows`/`_maxEntriesPerRow`). The
three-line fix is committed as
`configs/colmap_underwater_poissonrecon_build_fix.patch`. **This is the only
vendored source file edited anywhere in Phase 3A.**

**Shared classical settings** (`configs/phase3a_methods.json`), identical for
A/B/C_off/C_on: `SIMPLE_RADIAL`, `single_camera=1`, exhaustive matching (48
frames = 1128 pairs), incremental mapper, seed 0 on every stage, CPU everywhere.
Two settings deserve their own note:

* **`Mapper.multiple_models` is COLMAP's default (true), not false.** An earlier
  version of this experiment forced one model per run. Reading
  `src/colmap/controllers/incremental_mapper.cc` showed that `!multiple_models`
  **breaks out of the initialisation loop after the first trial**, so the whole
  reconstruction became a single lottery draw on the initial image pair. Under
  that setting several clips "failed" at 2/48 registered, and configuration B
  reconstructed 48/48 on one run and 3/48 on a byte-identical rerun. Those
  numbers were discarded. The original worry — a run looking successful while
  producing several mutually inconsistent fragments — is handled instead by
  **reporting every sub-model's size and evaluating only the largest**.
* **`Mapper.num_threads = 1`.** COLMAP's seed does not make multithreaded
  incremental mapping reproducible, and configuration C's entire claim is a
  difference between two runs. Extraction and matching stay multithreaded; the
  residual spread from those is measured by the repeat runs rather than assumed
  away.

**Flat-port parameters for C_on.** `FLATPORT` takes 8 parameters in the order
`Nx, Ny, Nz, int_dist, int_thick, na, ng, nw` (read from
`src/colmap/sensor/models_refrac.h` and `src/colmap/tools/example_refrac.cc`),
with lengths in the reconstruction's length unit. Values used: normal `(0,0,1)`
(a GoPro's lens cover is parallel to the sensor by construction), `int_dist =
0.002 m ± 0.002`, `int_thick = 0.001 m ± 0.0005`, `na = 1.0`, `ng = 1.52`,
`nw = 1.34`. **None of these is measured on this project's camera** — flat-port
thickness and stand-off remain an open named blocker in `PLAN.md`. Every
refraction conclusion below is conditional on them, which is why two diagnostic
variants were also run (§4.4).

**D — MapAnything**, `facebookresearch/map-anything` @
`3d10cf7a3016fc0f9bb13a071ee66c47b10be0d9` (2026-08-07), package 1.1.4, code
**Apache-2.0**. Checkpoint **`facebook/map-anything-apache`** — the Apache-2.0
variant, deliberately, since the default `facebook/map-anything` weights are
CC-BY-NC-4.0 and `PLAN.md`'s licence rule prefers the Apache/BSD path for
anything that might outlive the bakeoff. Inference: MPS, float32,
`memory_efficient_inference=True`, `use_amp=False`, `apply_mask=True`,
`mask_edges=True`, `apply_confidence_mask=False` (confidence is kept as data, not
used as a filter).

**E0 — vanilla VGGT**, `facebookresearch/vggt` @ `a288dd0f14786c93483e45524328726ab7b1b4ce`
(2026-05-18). Code licence permits commercial use except military applications
(2025-07-29 update); **the `facebook/VGGT-1B` checkpoint used here is
non-commercial**, and the commercial-use `VGGT-1B-Commercial` checkpoint is gated
behind an application form that was not requested. E0 is therefore an
**experimental control only** and must not be promoted into a permanent project
dependency on this checkpoint.

**E — Wat3R-Ren**, `LSXI7/Wat3R` @ `93147df00e15605afa93f586923fec000b18cefc`
(2026-07-15), code **Apache-2.0**, checkpoint `lsxi77777/Wat3R` **Apache-2.0**.

Both E0 and E run from **one script** (`scripts/run_vggt_family.py`), one model
per process. That is deliberate: `E0 → E` is a single experimental axis, and if
each model had its own script, any accidental difference in frame order,
preprocessing, pose handling, range conversion, validity policy or output format
would be indistinguishable from an adaptation effect. Everything except the two
lines that build the model is literally shared code. Both run on the same torch
2.13 on MPS in float32; upstream pins (`torch==2.3.1` for VGGT, `numpy==1.26.1`
for Wat3R-Ren) were **not** honoured, in favour of keeping the pair controlled —
recorded, not hidden.

**One deliberate preprocessing decision.** Wat3R-Ren's
`load_and_preprocess_images` accepts an extra `mode="max"` that VGGT's does not,
and Wat3R-Ren's README uses it. This bakeoff uses `mode="crop"` for **both**,
because a diff of the two repositories shows that branch is character-identical
apart from whitespace. Following the README would have silently given Wat3R-Ren
different pixels from its own control.

### 2.3 Configurations that did not execute, and exactly why

**F — GLUEMAP**, `colmap/gluemap` @ `adc9e4bb5f41014d3f7c157a879edc278588c829`
(2026-06-22), BSD-3. **`pending_cuda`.** Its `INSTALL.md` states verbatim:
*"GLUEMAP requires CUDA at runtime — the GPU PyTorch build is the only supported
configuration."* This is not merely a device string: `gluemap/estimators/
augmented_bundle_adjustment.py:302` calls `pygluemap.solve_cuda(...)` for the
augmented bundle adjustment, and `pygluemap` is a C++/Ceres extension built at
install time. The CUDA-only component **is** the global-consistency stage that
configuration F exists to test.

**G — AMB3R**, `HengyiWang/amb3r` @ `92c4081f910f98e683503092b85301861519175e`
(2026-06-05). **`pending_cuda`**, and **no LICENSE file exists in the repository**
— a public repository is not an open-source licence, so AMB3R stays strictly
experimental and neither its code nor its checkpoint may be promoted into
permanent project dependencies. Its supported install pins CUDA 11.8 throughout:
`torch==2.5.0+cu118`, `torch-scatter` from the cu118 wheel index, `pytorch3d`
V0.7.8, `flash-attn==2.7.3`, and **`spconv-cu118==2.3.8`**. That last one is
decisive: spconv *is* the compact volumetric backend — the component G exists to
test — and it has no CPU/MPS build, so substituting it would not be testing
AMB3R. `demo.py` also calls `model.cuda()` and
`torch.autocast(device_type='cuda', dtype=torch.bfloat16)` unconditionally.

Two facts from reading AMB3R that matter regardless:

* **Its frontend is literally VGGT** — `amb3r/frontend.py` does
  `from vggt.models.vggt import VGGT` and builds `VGGT(return_depth_feat=metric_scale)`.
  So VGGT → AMB3R is an architecturally tight pairing …
* … **but not a clean one.** That VGGT is instantiated with
  `return_depth_feat=True` and loaded from its own `checkpoints/VGGT.pt`, so the
  frontend **weights** and an extra depth-feature path differ from vanilla VGGT
  too. Any AMB3R-vs-VGGT difference would measure "explicit backend **plus**
  retrained frontend", never the backend alone.

**H — SeaVGGT**, `lqzhao/SeaVGGT` @ `78a3a7d0fbabb58ab3e987924da7f020d01bdb9f`
(2026-08-20). **`paper_only / not_released`.** No LICENSE file; README is the
single line `# SeaVGGT`; the GitHub releases API returns **0 releases**. Its
`demo.py` imports `uw_model`, `dataset` and a top-level `vggt` package — **none
of the three exists anywhere in the repository**, so the released code cannot
import, let alone run. Its only checkpoint reference is a hard-coded local
training artifact (`checkpoints/epoch_01_best_rmse_0.6133_24proto_sota.pth`) with
no download path; the only fetchable weights are vanilla `facebook/VGGT-1B`, i.e.
the baseline. Running it would have required writing the missing modules and
training the weights — a hand-written reproduction, which is not a controlled
evaluation of the published method.

**I — Water-VGGT**, `awhitewhale/watervggt` @ `f8f03eb74fc137b8eecdc2aac9729b7135706f14`
(2026-03-30), **MIT**. Status: **`release_incomplete / advertised checkpoint =
vanilla VGGT-1B`**, with `pending_cuda` as a secondary, independent blocker.
`paper_only / not_released` would be wrong — code *is* released and an official
checkpoint *is* advertised and downloadable; both were inspected. The problem is
what they contain. This one *would* run — it just would not run Water-VGGT:

* The repository's `vggt/` is a copy of the **vanilla** VGGT package, and
  `demo.py` builds a plain `VGGT()` and loads
  `huggingface.co/facebook/VGGT-1B/resolve/main/model.pt`. **No code path
  anywhere loads a Water-VGGT geometry checkpoint**, and nothing consumes the
  README's OneDrive "pretrained Water-VGGT model" link.
* The only Water-VGGT-specific component actually wired in is `wcv_init()`, which
  runs the committed `pre/wcv_pre.pth` as an **image → image preprocessing pass**
  writing PNGs to a directory that vanilla VGGT then reads.
* The modules that would constitute the paper's "alternatingly conditioned
  Transformer backbone" — `attention.py::NonLocalSparseAttention`,
  `deform_conv.py::DCN_layer`, `swing_transformer.py` — are **never imported by
  `demo.py`**. They are orphaned files.
* README, verbatim: *"Note: Training and testing code will be released upon
  acceptance of the paper."*
* Independently: `demo.py` raises unconditionally without CUDA, and `wcv.py`
  wants `nn.DataParallel(model, device_ids=[0,1])` — two GPUs.

Executing it as shipped would have produced **vanilla VGGT numbers under a
Water-VGGT label**, silently duplicating configuration E0 — the
`executed_but_invalid` trap, and a particularly damaging one here.

**The official checkpoint was downloaded and inspected, and it settles the
matter.** Following the README's OneDrive link by hand yields `model.pt`,
5 026 874 952 bytes, sha256 `d15bf50a…3afe0`, 1 797 float32 tensors,
1 256 537 516 parameters. Its module inventory is `aggregator` (1 210),
`track_head` (394), `camera_head` (69), `point_head` (62), `depth_head` (62) —
i.e. **exactly vanilla VGGT's**, with **zero** tensors matching `wcv`, `water`,
`condition`, `sft`, `igm`, `dcn`, `deform`, `swin` or `nonlocal`.

Compared tensor-by-tensor against `facebook/VGGT-1B` from the local Hugging Face
cache: **0 keys only in one side, 1 797/1 797 tensors bitwise identical, maximum
absolute difference exactly 0.0.**

> The **model state** of the artifact distributed as "the pretrained Water-VGGT
> model" is **bitwise identical, tensor for tensor, to `facebook/VGGT-1B`**. It
> contains no underwater adaptation of any kind.

**Stated precisely, because the stronger version is not supported.** The two
*files* are NOT byte-identical and this report does not claim they are: the
download is a torch pickle of 5 026 874 952 bytes (sha256 `d15bf50a…3afe0`),
the Hugging Face artifact a 5 026 367 224-byte safetensors file. Container
framing, key ordering and metadata differ. What is established is identity of the
**model state**: same 1 797 keys, same shapes and dtypes, every tensor equal to
the last bit.

**What this does and does not imply.** It establishes that the advertised
geometry checkpoint carries no Water-VGGT adaptation, and that the released code
does not execute the paper's conditioned geometry architecture. It does **not**
imply the released pipeline would reproduce configuration E0's numbers: that
pipeline is `WCV image preprocessing → altered pixels → vanilla VGGT-1B weights`,
and altered pixels can produce different geometry. The supported claim is that
its *geometry model* is unmodified VGGT-1B — not that its *output* equals ours.

A licensing observation, recorded as fact and not relied upon:
`facebook/VGGT-1B` is a **non-commercial** checkpoint, redistributed here through
an MIT-licensed repository's README.

**A camera-model finding worth keeping.** Whatever the paper claims about
refraction, the *released* implementation does not alter ray geometry, does not
predict refractive parameters at inference, and does not model a non-central
projection. Its Water Condition Vector is an image-space module feeding an
unmodified **central pinhole** VGGT. Water-VGGT must therefore not be described
as "refraction-aware SfM" on this evidence, and **configuration C remains the
only clean central-vs-flat-port experiment in this bakeoff.**

**J — WAT3R-Xu**, arXiv 2607.21023 (Xu, Lu, Zheng, Tan, Zhu, Liu, Yeung;
2026-07-23; paper CC-BY-4.0). **`paper_only / not_released`**, established four
ways: no code-availability statement on the arXiv abstract page; none in the full
arXiv HTML text; the project page `xujiayi777.github.io/WAT3R.github.io` shows a
"Code" label that is **not a functional hyperlink**, with no repository and no
checkpoint download; and a GitHub search for `WAT3R` returns only `LSXI7/Wat3R`
(Ren et al.) plus unrelated projects. Its base architecture is **Pi3, not VGGT**,
so even if released it would never have been a clean ablation partner for
Wat3R-Ren. Its water-parameter (β_att, β_bs, B∞) and clean-image outputs are
recorded as prior art for Weeks 5–6 only; nothing here licenses starting
attenuation inversion or backscatter removal.

### 2.4 Environment

Apple M4, 10 cores, 24 GB unified memory, macOS 26.6.2, **no CUDA**. Three
isolated interpreters: the main project venv (numpy + opencv, Python 3.14) drives
Stages 1/2/6/7 and the COLMAP configurations; `.venv-mapanything` and
`.venv-vggt` (both Python 3.13 + torch 2.13) hold the learned arm. `pyproject.toml`
is untouched and the main venv still has only numpy + opencv, so `CLAUDE.md`
invariant 8 is scoped exactly as it was in Phase 2A.

**One model per process, always.** Process exit is the authoritative MPS cleanup
boundary; no two heavyweight geometry models were ever instantiated in one
interpreter, and the batch drivers are strictly sequential so that reported
runtime and peak memory mean something.

---

## 3. Geometry conventions

The largest correctness risk in a cross-family geometry bakeoff is not any
model — it is silently comparing two different quantities. Every convention
below is stated, every conversion is project-owned code in
`experiments/week3_geometry/geometry.py`, and every conversion is unit-tested
against synthetic geometry with an analytically known answer
(`tests/test_week3_geometry.py`, 38 tests).

### 3.1 The frame and pose convention this project uses

OpenCV / COLMAP camera frame: right-handed, **+x right, +y down, +z forward**
into the scene; points in front of the camera have z > 0.

* `T_cw` maps **world → camera**. This is COLMAP's native convention: its
  `images.txt` quaternion and translation *are* `R_cw, t_cw`, and the camera
  centre is `C = -R_cwᵀ t_cw`.
* `T_wc` maps **camera → world**, and its translation column *is* the camera
  centre. This is what most learned models emit as `camera_poses`/`extrinsics`.

Nothing in the conversion layer guesses which one a third-party file holds — the
caller states it, and the choice is recorded in each run's sidecar.
`invert_se3` converts between them using `Rᵀ` rather than a general inverse, and
is tested for exact round-trip and for the property that **getting the direction
backwards produces visibly different numbers** (a test that would fail if the
two were accidentally interchangeable).

### 3.2 z-depth is not range, and the difference is radial

This is the distinction the whole week turns on.

```text
z_depth(u,v)    the +z coordinate of the scene point in the camera frame. Planar.
                NOT a distance.
ray_range(u,v)  the Euclidean distance ||X_cam|| from the projection centre to
                the scene point. A distance.
```

For a central camera they are related exactly by the length of the normalised
ray through the pixel:

```text
X_cam      = z · K⁻¹[u, v, 1]ᵀ
ray_range  = z · ‖K⁻¹[u, v, 1]ᵀ‖
```

so `ray_range = z_depth · sec(θ)` where θ is the angle off the optical axis.
**At this footage's field of view that factor exceeds 1.25 at the frame
corners** — a unit-tested figure, not an estimate. Storing z-depth under the
name "range" would therefore inject a **radially structured error of tens of
percent, zero at the centre and largest at the edge** — which is *precisely the
signature the refraction test looks for*. It would have manufactured a fake
refraction result. `zdepth_to_ray_range` / `ray_range_to_zdepth` are the only
sanctioned conversion, they require the intrinsics, and they are tested against
an explicit unprojection.

### 3.3 Water path length is canonical; ray range is a labelled approximation

`PLAN.md` makes `water_path_length` the canonical field because Beer–Lambert
attenuation integrates over the distance travelled **through water**, and a
flat-port camera has no single projection centre:

```text
projection centre
    \  air / port glass
     \
      interface exit point
         \
          \   WATER PATH   <- what attenuation actually integrates over
           \
            scene point
```

Every configuration in this bakeoff is central (A, B, D, E0, E) or is a
refractive reconstruction whose 3D points are expressed relative to a virtual
centre (C_on). None of them can emit a true water path, so **every stored field
is `range_along_ray`, carrying the explicit label
`path_source = "ray_range_approx_water_path"`.** Nothing is ever written as an
unlabelled "range".

**The approximation is bounded rather than assumed negligible.**
`flatport_exit_point_distance_bound(int_dist, int_thick, θ_max)` returns

```text
| water_path − ‖X_cam‖ |  ≤  ‖P₂‖  ≤  (int_dist + int_thick) / cos(θ_max)
```

by the triangle inequality, using `cos(θ_glass) ≥ cos(θ_max)` because refraction
into a denser medium bends toward the normal. With the flat-port parameters used
here (2 mm + 1 mm) and θ_max ≈ 55°, the bound is **under 6 mm** — i.e. **< 2 % at
a 0.5 m scene point and < 0.2 % at 3 m**. Those figures are unit-tested. This is
why Phase 3A does not implement a full refractive unprojection. But the scope of
the bound must be stated exactly, because it is narrower than it looks:

> Given an **already-reconstructed** scene point, replacing its true in-water
> segment with the central-camera ray-range surrogate contributes at most a few
> millimetres, under the assumed housing geometry.

It says **nothing** about whether refractive projection corrupted the
reconstruction itself. A central model can place the scene point in the wrong
place to begin with; this bound limits only the additional error introduced by
the *water-path surrogate*, not the geometric error of the central-camera
assumption. Those are different quantities and only the second is bounded here.

### 3.4 Per method

| method | native pose | native range field | conversion applied | comparison quantity |
|---|---|---|---|---|
| **A / B / C_off** | `images.txt` quaternion + translation = `T_cw` (world→camera) | none (sparse 3D points) | `‖T_cw · X_world‖` per observation | **exact** ray range from the reconstruction's own centre |
| **C_on** | same, but the camera is FLATPORT-refractive | none (sparse 3D points) | same | **approximate**: distance from the *virtual* centre, not the water path. Offset bounded < 6 mm by §3.3 |
| **D MapAnything** | `camera_poses` = cam2world (`T_wc`) | `depth_along_ray`, plus separate `depth_z` | **none** — `depth_along_ray` stored unmodified | **exact** ray range |
| **E0 VGGT** | `pose_encoding_to_extri_intri` → `(3,4)` cam-from-world (`T_cw`); stored inverted to `T_wc` | `predictions['depth']` = **planar z-depth** | `z · ‖K⁻¹[u,v,1]‖` | **exact** ray range after conversion |
| **E Wat3R-Ren** | identical to E0 | identical to E0 | identical to E0 | **exact** ray range after conversion |

Two convention checks were run numerically rather than trusted:

* **MapAnything.** `depth_along_ray` was verified to equal `‖pts3d_cam‖` to
  **1.14 × 10⁻⁵** (max abs, over a full frame), and `depth_z` to equal the z
  component of `pts3d_cam`. So the mapping onto `range_along_ray` is exact, and
  the measured `along_ray / z` ratio is the secant factor of §3.2 — direct
  evidence of how large the conflation error would have been.
* **VGGT / Wat3R-Ren.** Each run unprojects its own z-depth with its own K and
  the stored `T_wc`, compares against the model's `world_points`, and **repeats
  the comparison with the pose deliberately inverted** as a falsification
  control. The residual is *not* expected to be zero: these models predict depth
  and world points with **separate heads that are not constrained to agree**, so
  a few percent is the models' own internal inconsistency, not a conversion error.

  **A methodological catch worth recording.** The first version of this check ran
  on the clip's first frames and reported the correct and inverted conventions as
  equally good (0.054 vs 0.054) — because VGGT-family models **anchor their world
  frame to camera 0**, so its pose is the identity and inverting it changes
  nothing. The control was a no-op exactly where it was most tempting to run it.
  The check now runs on frames at 1/3, 2/3 and the end of each clip, and
  `scripts/check_completeness.py` marks any run whose inverted control scores
  within 2× of the correct one as **stale** and re-runs it.

### 3.5 Resolution — and a field-of-view asymmetry that would have corrupted the comparison

| stage | grid |
|---|---|
| source clips | 1920×1080 (or 1080×1920 portrait decode) |
| **shared extraction** | long side 1280 → 720×1280, or 1280×720 portrait |
| classical arm (A/B/C) | operates at the full 1280 extraction |
| MapAnything inference | **294×518** landscape, **518×294** portrait |
| VGGT / Wat3R-Ren inference | **294×518** landscape, **518×518** portrait |
| comparison | dense fields are sampled at classical image observations mapped onto each model's own grid; no dense field is ever upsampled to pretend to native resolution |

**No dense number in this report is native-resolution geometry.** Every dense
field was produced on a ~518-px grid, roughly a 2.5× downscale from the
extraction and a 3.7× downscale from the source.

The source-pixel → model-grid mapping was **measured, not reverse-engineered**
(`scripts/calibrate_preprocess.py`): synthetic marker images were pushed through
each model's own preprocessing code and the landing positions fitted to an affine
map, with residuals reported. Max residual is **≤ 0.22 px** in every case, so the
mapping is affine to well under a pixel. Results:

| family | source | model grid | u scale | v scale | v offset | markers lost to crop |
|---|---|---|---|---|---|---|
| MapAnything | 720×1280 | 294×518 | 0.4077 | 0.4092 | −0.66 | 0/25 |
| MapAnything | 1280×720 | 518×294 | 0.4083 | 0.4077 | −2.25 | 0/25 |
| VGGT | 720×1280 | 294×518 | 0.4049 | 0.4092 | −0.65 | 0/25 |
| VGGT | 1280×720 | **518×518** | 0.7193 | 0.7218 | **−203.09** | **10/25** |
| Wat3R-Ren | *bit-identical to VGGT in both orientations* | | | | | |

Two findings fall straight out of this table, and neither would have been visible
from reading the source:

1. **Wat3R-Ren's mapping is bit-identical to VGGT's**, which empirically confirms
   the E0 → E pairing is preprocessing-controlled.
2. **On a portrait clip, VGGT and Wat3R-Ren throw away ~44 % of the vertical
   field of view.** Their shared `crop` branch resizes to width 518 and
   centre-crops the height to 518, discarding 203 px top and bottom; 10 of 25
   markers fell outside the grid entirely. MapAnything keeps essentially the
   whole frame in both orientations. **On `wreck_01` the two families are
   therefore not looking at the same scene**, and every `wreck_01` number below
   must be read with that in mind.

### 3.6 Validity

Every dense range field travels with a boolean mask, and every stored field obeys
one rule: **a non-finite or non-positive range is never stored as a number.** It
is demoted into the mask and written as NaN, so no consumer can read a zero and
believe the camera is touching the scene (unit-tested).

* `resize_range_field` uses **nearest neighbour, deliberately** — averaging range
  across a depth discontinuity invents a surface present in neither the near nor
  the far object, exactly at the boundaries where a restoration error is most
  visible.
* `sample_at_observations` interpolates bilinearly but **only where all four
  neighbours are valid and finite, including a neighbour whose bilinear weight is
  zero**. A sample whose 2×2 neighbourhood touches a hole comes back invalid
  rather than being filled from the valid side. That costs a thin band of samples
  at every hole edge, which is the cheap direction to be wrong in.
* MapAnything's `mask` (with `mask_edges=True`) and `conf` are stored as data.
  Confidence is **never** used to filter the geometry being scored.

---

## 4. Classical results

### 4.1 Registration

Largest sub-model only; every sub-model's size is recorded in each run's
`run.json`. 48 frames offered per clip.

| config | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|---|---|---|---|---|---|---|
| **A** SIFT | **48/48** | **48/48** | **48/48** | **48/48** | 46/48 | 47/48 |
| **B** ALIKED+LightGlue | **48/48** | **48/48** | **48/48** | **48/48** | 44/48 | 47/48 |
| **C_off** fork, refraction off | **48/48** | 44/48 | **48/48** | **48/48** | 46/48 | 17/48 |
| **C_on** fork, refraction on | 2/48 | 44/48 | **48/48** | **48/48** | 4/48 | 2/48 |

**Configuration A registers essentially everything.** That is the single most
consequential classical result, and it was not obvious in advance: ordinary
SIFT-based COLMAP handles all six clips — including the near-planar low-texture
portrait clip (46/48) and the dynamic-diver clip (47/48).

**C_off tracks A closely but is weaker on the two hard clips** (44/48 on
`wreck_05`, 17/48 on `wreck_03`). That is the two-COLMAP-generations gap showing
up exactly where the footage is marginal, and it is why C is run as a
self-contained A/B rather than against A.

### 4.2 Sparse structure and the reprojection diagnostic

| config | clip | 3D points | mean track | obs/img | focal px | reproj px |
|---|---|---|---|---|---|---|
| A | wreck_07 | 11 197 | 8.24 | 4 358 | 1 108 | 0.699 |
| C_off | wreck_07 | 11 228 | 8.28 | 4 358 | 1 107 | 0.700 |
| B | wreck_07 | 6 365 | 9.77 | 1 801 | 1 130 | 1.104 |
| A | wreck_05 | 2 942 | 5.91 | 1 099 | 1 552 | 1.189 |
| A | cenote_01 | 15 233 | 8.11 | 4 580 | 1 071 | 0.974 |
| A | swimthrough_02 | 29 051 | 10.56 | 14 440 | 1 052 | 0.545 |
| A | wreck_01 | 4 569 | 7.79 | 2 099 | 1 430 | 1.091 |
| A | wreck_03 | 2 796 | 4.81 | 1 213 | 1 042 | 0.787 |

**Reprojection error behaves exactly as `PLAN.md` warned and must not be used to
rank anything.** Two demonstrations from this table alone:

* `C_on` on `wreck_03` reports a reprojection error of **0.000 px** — from a
  reconstruction containing **one 3D point and two images**. A perfect score for
  no world at all.
* `C_on` on `wreck_07` reports **0.343 px**, *better* than A's 0.699 px, from
  2 registered images and 22 points against A's 48 and 11 197.

The clip-to-clip spread in A's own reprojection error (0.545 px on
`swimthrough_02` to 1.189 px on `wreck_05`) tracks texture, not correctness.

### 4.3 A vs B — was correspondence the bottleneck?

**No — but B does one thing consistently and it is not registration.** Complete
across all six clips:

| clip | A reg / points / track / s | B reg / points / track / s | track gain | slowdown |
|---|---|---|---|---|
| `wreck_07` | 48/48 · 11 197 · 8.24 · 58 s | 48/48 · 6 365 · 9.77 · 1 609 s | **+19 %** | 28× |
| `wreck_05` | 48/48 · 2 942 · 5.91 · 37 s | 48/48 · 3 252 · 8.25 · 673 s | **+40 %** | 18× |
| `cenote_01` | 48/48 · 15 233 · 8.11 · 128 s | 48/48 · 3 592 · 14.17 · 541 s | **+75 %** | 4× |
| `swimthrough_02` | 48/48 · 29 051 · 10.57 · 252 s | 48/48 · 6 629 · 12.99 · 1 027 s | **+23 %** | 4× |
| `wreck_01` | **46/48** · 4 569 · 7.79 · 61 s | 44/48 · 3 844 · 9.14 · 306 s | **+17 %** | 5× |
| `wreck_03` | 47/48 · 2 796 · 4.81 · 83 s | 47/48 · 2 681 · 6.29 · 233 s | **+31 %** | 3× |

**Registration: no gain anywhere.** B matches A on four clips, ties on
`wreck_03`, and is *worse* on `wreck_01` (44 vs 46). There was no matching
failure to repair, so the correspondence hypothesis has nothing to explain.

**Track length: a gain on every single clip, +17 % to +75 %.** This is the one
robust, reproducible effect of the learned front end, and it is directionally
sensible: ALIKED+LightGlue produces *fewer* but far better-tracked features
(`cenote_01`: 3 592 points at mean track 14.17, against SIFT's 15 233 at 8.11).
Longer tracks mean each 3D point is constrained by more views.

**Geometrically, though, they agree.** Where the two arms place observations at
the same pixel (≤ 1 px apart) on `wreck_07`, their scale-aligned ranges agree to
a **median 0.95 %** (p95 5.5 %, fitted scale 1.0074) — the same world.

**And the cost is severe:** 3–28× A's runtime on this machine's CPU ONNX path,
worst on exactly the high-texture clips where it helps least. B also carries a
consistently higher reprojection error (0.999–1.392 px vs A's 0.545–1.189), as
expected from less sub-pixel-precise keypoints, and COLMAP emitted a spurious
small sub-model alongside the real one on several clips (`{2, 48}`, `{8, 48}`) —
visible only because sub-model sizes are reported.

> **Correspondence is not the classical bottleneck on this footage**, and B is
> retired as a default. But "B buys nothing" would be wrong: it buys a
> 17–75 % track-length improvement at 3–28× the cost. That makes it the right
> tool for a *demonstrated* weak-triangulation failure — the Phase 3B trigger —
> and the wrong tool to pay for pre-emptively.

### 4.4 Refraction OFF vs ON — and why the honest answer is "not identifiable", not "no effect"

This is a paired experiment inside **one binary**: same fork, same SIFT features,
same images, same seed, same mapper settings. Only `enable_refraction` and the
`FLATPORT` parameters change.

#### The fork's refraction-OFF mode reproduces mainline COLMAP

Before reading anything into C_on, C_off has to be shown to be a valid control —
the fork is `COLMAP 3.10-dev` against mainline's 4.1.1, and comparing across that
gap would confound the camera model with two years of unrelated COLMAP change.
It is valid:

| pair | clip | matched observations | fitted s | median \|rel err\| | p95 |
|---|---|---|---|---|---|
| A vs C_off | `wreck_07` | 90 222 | 1.0216 | **0.04 %** | 0.77 % |
| A vs C_off | `cenote_01` | 114 173 | 0.9910 | **1.08 %** | 5.40 % |

So the two-generation gap is not a confound, and C_off/C_on is a clean A/B.

#### Refraction ON does not fail by producing a wrong-shaped world. It fails two other ways.

**(a) On three of six clips it does not reconstruct at all** — and the cause is
*not* refraction.

`C_on` on `wreck_07` registers 2/48 with 22 points, where A and C_off both reach
48/48 with ~11 200 points. The tempting reading is "flat-port refraction is wrong
for this footage". The falsification test says otherwise. **`C_on_null`** runs the
identical refractive code path — `FLATPORT` active, `Mapper.enable_refraction 1`,
`TwoViewGeometry.enable_refraction 1` — with the refractive indices set to
`na = ng = nw = 1.0`, i.e. **physically no refraction at all**:

| configuration | refraction physically active? | `wreck_07` registered | 3D points |
|---|---|---|---|
| A (mainline, pinhole) | no | **48/48** | 11 197 |
| C_off (fork, refraction disabled) | no | **48/48** | 11 228 |
| C_on (fork, FLATPORT, n = 1.0/1.52/1.34) | **yes** | 2/48 | 22 |
| **C_on_null** (fork, FLATPORT, n = 1.0/1.0/1.0) | **no** | **2/48** | 2 |

On `wreck_07`, `C_on_null` fails exactly like `C_on`. **On that tested clip**,
the failure is therefore in the fork's **refractive reconstruction path** — its
initialisation, whose relative-pose step the paper itself notes uses a 5-point
solver on an approximated perspective camera — and **not** in the flat-port
physics. The log shows the mapper finding an initial pair, running global bundle
adjustment that filters 0 observations, and immediately returning to "Finding
good initial image pair" until it reports "No good initial image pair found".

**Scope, stated exactly.** `C_on_null` was run on `wreck_07` (a failure clip) and
on `cenote_01` (a success clip). It was **not** run on `wreck_01` or `wreck_03`,
the other two clips where `C_on` fails. So the supported claim is:

> On the one failure clip tested, nulling refraction does not restore
> initialisation, so that failure is attributable to the refractive execution
> path rather than to refraction itself.

It is **not** established that the `wreck_01` and `wreck_03` failures have the
same cause. **This must not be reported as evidence about refraction.** It is an
integration finding about `colmap_underwater` on one clip of this footage.

**(b) Where it does reconstruct, the implied metric scale is not physically
plausible.** `C_on` registers substantially on **three** clips, not two:

| clip | C_on registered | C_off median range | **C_on median range** | (int_dist + thick) / median range |
|---|---|---|---|---|
| `cenote_01` | 48/48 | 21.9 (arbitrary units) | **1 660** | **1.8 × 10⁻⁶** |
| `swimthrough_02` | 48/48 | 22.6 (arbitrary units) | **1 163** | **2.6 × 10⁻⁶** |
| `wreck_05` | 44/48 | 21.7 (arbitrary units) | **4 375** | **6.9 × 10⁻⁷** |

Fixing the port parameters is supposed to make the reconstruction metric. If
those parameters are metres, these medians place the cenote ceiling 1.7 km away
and the reef swim-through 1.2 km away. **They are not metric.** And at a
scene-to-interface ratio of ~10⁻⁶ the modelled refraction is numerically
negligible against scene range, so whatever the fit converged to, it is not a
regime in which the extra physics can be doing useful work.

**One tempting explanation is ruled out by the null control.** It would be easy to
read the above as "the refractive code path just inflates scale". It does not. On
`cenote_01`, running the same refractive model with the indices set to 1.0 gives a
completely different answer:

| configuration | registered | median range | recovered focal |
|---|---|---|---|
| `C_off` (no refractive model) | 48/48 | 21.90 | 960.6 |
| `C_on` (FLATPORT, n = 1.0/1.52/1.34) | 48/48 | **1 659.76** | 933.2 |
| `C_on_null` (FLATPORT, n = 1.0/1.0/1.0) | 48/48 | **1.02** | **960.6** |

With refraction nulled the focal returns exactly to `C_off`'s 960.6 and the scale
lands three orders of magnitude away from `C_on`'s. So the extreme scale is a
consequence of the **active refractive physics with these assumed port
parameters**, not an artifact of the refractive code path — the opposite of the
`wreck_07` initialisation finding, and a good reason to keep the two separate.

What this bakeoff cannot determine is *which* failure it is: whether the
optimiser escaped into a regime where refraction stops mattering, or simply
converged to a wrong metric solution. Either way the reconstruction is not usable
as a metric reference, and the assumed port parameters are unverified.

That is a stronger and more useful statement than a null result:

> Within this operating envelope — a GoPro flat port with an assumed 2 mm
> stand-off and 1 mm cover, diver-held at reef distances, 48 frames at a 1280 px
> long side — **the flat-port refraction parameters are not identifiable from the
> imagery alone.** The refractive model does not correct a shape error; it
> escapes into a scale where its own correction vanishes.

#### (c) And the whole result is strongly sensitive to the unmeasured port geometry

`C_on_thick` repeats the experiment with the camera-to-interface distance raised
from the assumed 2 mm to 50 mm — the top of the fork's own example range, and
still a physically arguable value for a housed camera:

| clip | configuration | d_int | registered | median range | recovered focal |
|---|---|---|---|---|---|
| `cenote_01` | `C_on` | 0.002 | 48/48 | 1 659.76 | 933.2 |
| `cenote_01` | **`C_on_thick`** | **0.05** | 48/48 | **9.67** | **316.0** |
| `wreck_05` | `C_on` | 0.002 | 44/48 | 4 375.36 | 1 056.0 |
| `wreck_05` | **`C_on_thick`** | **0.05** | 48/48 | 3 469.38 | 1 650.8 |

On `cenote_01`, a 25× change in an **unmeasured** parameter moves the implied
scene scale by **172×** and the recovered focal length by **3×** (933 → 316 px).
The reconstruction's intrinsics and its metric scale are both largely determined
by a number nobody measured.

`PLAN.md` already lists flat-port thickness and stand-off as an open named
blocker, "required only if the shape test fires". This is that blocker firing:
the refraction question cannot be answered from this footage **because its answer
is dominated by a parameter that must be measured on the physical camera, not
fitted from the imagery**.

#### The envelope, recorded as `PLAN.md` requires

| | |
|---|---|
| camera | GoPro, flat port, parameters **assumed** (2 mm ± 2 mm stand-off, 1 mm ± 0.5 mm cover), not measured |
| range span tested | roughly 0.5×–2× the scene median within each clip; no independently known distance anywhere |
| evaluation resolution | 1280 px long side for the classical arm; ~518 px for anything dense |
| what would change the answer | a measured stand-off/thickness, and above all a **C2 metric anchor** that removes the scale freedom the fit exploited |

#### And the repeat runs remove the last ambiguity

§4.5 measures C_on's run-to-run behaviour with an identical seed: **44, 16, 44**
frames registered across three runs of `wreck_05`, and a **22×** point-count
spread on `wreck_07`.

**Stated carefully, because the obvious stronger claim is not valid.** A
registration count and a 3D-point count are not noise bars for a *range residual*
— they are different quantities, and one cannot be used to bound the other. So
this report does **not** claim "no refraction effect could clear that spread".
What it claims is weaker and sufficient:

> C_on does not reproducibly return comparable reconstructions of the same clip.
> Its shape differences therefore cannot be cleanly attributed to refraction, and
> it cannot serve as a measurement reference.

Properly bounding a refraction effect would require repeat-run variability in the
**same shape metric** — scale-aligned range residual, radius swing, range swing —
which is not obtainable from a configuration whose registration itself swings
between 16 and 44 frames.

So the refraction outcome has three independent strands, none of which requires
the others:

1. On the one failure clip tested, the failure survives nulling refraction — so
   *that* failure is the execution path, not the physics.
2. Where it does reconstruct, the implied metric scale is not physically
   plausible, and the null control shows this is caused by the active refractive
   physics with the assumed port parameters.
3. It is operationally non-reproducible, so it cannot be a measurement reference
   regardless of the first two.
4. And its output is dominated by an **unmeasured** port parameter: a 25× change
   in the assumed stand-off moves the implied scale 172× and the recovered focal
   3×. Even a well-behaved refractive solver could not settle the question until
   that parameter is measured on the camera.

**Do not read this as "refraction does not matter underwater."** It is an
envelope-bounded statement about identifiability from imagery alone with assumed
port parameters, on this camera, at these distances, at this resolution — and,
now, with a specific implementation whose reproducibility disqualifies it as a
measurement instrument regardless of the physics.

---

### 4.5 Repeatability — and the number that disqualifies configuration C_on

Repeat runs with an **identical seed and identical settings**, mapping pinned to
one thread:

| config | clip | registered across runs | 3D points across runs | point spread |
|---|---|---|---|---|
| **A** | `wreck_07` | 48, 48 | 11 197, 11 206 | **1.00×** |
| **A** | `wreck_05` | 48, 48 | 2 942, 2 838 | **1.04×** |
| **C_off** | `wreck_07` | 48, 48, 48 | 11 228, 11 337, 11 293 | **1.01×** |
| **C_off** | `wreck_05` | 44, 48, 48 | 2 393, 2 456, 2 989 | 1.25× |
| **C_on** | `wreck_07` | 2, 2, 2 | 22, 14, **1** | **22.00×** |
| **C_on** | `wreck_05` | **44, 16, 44** | 2 281, 1 194, 2 304 | **1.93×** |

Three things follow, and the third is decisive.

1. **Configuration A is effectively reproducible** — same registration every
   time, ≤ 4 % variation in point count. It is the most trustworthy instrument
   in the bakeoff, which matters because it is the reference most numbers in §7
   are quoted against.
2. **C_off is reproducible where the footage is easy and wobbles where it is
   not** — identical on `wreck_07`, but 44/48/48 registered and a 1.25× point
   spread on the low-texture `wreck_05`.
3. **C_on is not a measurement instrument.** On the same clip, same seed, it
   registers **44, then 16, then 44** frames. Its point count varies by **22×**.
   The project's standing rule — inherited from Phase 2A, where FlowIt was
   dropped for exactly this — is that a non-reproducible instrument is
   disqualified. C_on fails that bar outright.

`PLAN.md` requires any claimed refraction effect to **exceed the measured
run-to-run spread**. This report cannot evaluate that test properly, and says so:
the spreads measured here are in *registration* and *point count*, which are not
the units of a range-shape effect. What the instability does establish — which is
all that is needed — is that **C_on cannot serve as the refractive reference the
plan envisaged**, because it does not reproducibly return comparable
reconstructions of the same clip.

The one C_on result that *is* robust is its failure: 2/48 on `wreck_07` in all
three runs. That reproducibility is what makes the `C_on_null` attribution in
§4.4 safe — a consistent failure compared against a consistent failure.

## 5. Learned dense results

Organised by experimental role, not as one leaderboard.

```text
general feed-forward         D  MapAnything
base feed-forward control    E0 vanilla VGGT
underwater adaptation        E  Wat3R-Ren
```

### 5.1 Coverage, cost, and a coverage number that must not be misread

| config | clip | grid | valid frac (med/min) | infer s | MPS GB |
|---|---|---|---|---|---|
| D | wreck_07 | 294×518 | 0.86 / 0.70 | 227 | 10.3 |
| E0 | wreck_07 | 294×518 | 1.00 / 1.00 | 223 | 12.7 |
| E | wreck_07 | 294×518 | 1.00 / 1.00 | 209 | 12.6 |
| D | wreck_05 | 294×518 | 0.79 / 0.70 | 210 | 10.3 |
| E0 | wreck_05 | 294×518 | 1.00 / 1.00 | 319 | 12.6 |
| E | wreck_05 | 294×518 | 1.00 / 1.00 | 209 | 12.6 |
| D | cenote_01 | 294×518 | 0.96 / 0.94 | 207 | 10.3 |
| E0 | cenote_01 | 294×518 | 1.00 / 1.00 | 228 | 12.7 |
| E | cenote_01 | 294×518 | 1.00 / 1.00 | 214 | 12.6 |
| D | swimthrough_02 | 294×518 | 0.80 / 0.59 | 234 | 10.8 |
| E0 | swimthrough_02 | 294×518 | 1.00 / 1.00 | 299 | 12.7 |
| E | swimthrough_02 | 294×518 | 1.00 / 1.00 | 245 | 12.6 |
| D | wreck_01 | 518×294 | 1.00 / 0.95 | 161 | 10.8 |
| E0 | wreck_01 | **518×518** | 1.00 / 1.00 | **740** | **16.9** |
| D | wreck_03 | 294×518 | 0.83 / 0.39 | 140 | 10.3 |
| E0 | wreck_03 | 294×518 | 1.00 / 1.00 | 254 | 12.7 |

**"1.00 valid" is not better coverage — it is the absence of a validity signal.**
VGGT and Wat3R-Ren emit no mask, so every pixel is declared valid by default and
their validity is only "finite and positive range". MapAnything's 0.39–1.00 is
the *honest* number: it masks depth discontinuities (`mask_edges=True`), and on
the thin rigid structure of a wreck that removes a great deal — the railings and
pipes in the `wreck_07` range maps are magenta (invalid) precisely where the
geometry is most interesting. On `wreck_03` its worst frame keeps only 39 %.

That is a genuine trade-off, not a ranking: MapAnything declines to assert range
at boundaries; the VGGT family asserts everywhere and lets the consumer find out.

**Cost.** All three run locally on MPS in float32 at 140–320 s per 48-frame clip
and 10–13 GB, except the portrait clip, where the VGGT family's 518×518 grid
costs **740 s and 16.9 GB** — 4.6× the runtime and 1.6× the memory of its own
landscape runs, for a field of view it has already cropped by 44 %.

### 5.2 Temporal behaviour

Per-frame median range varies by **1.20× to 3.52×** across a clip for every
model. That figure is *not* pure drift — on `wreck_07` the camera genuinely
closes on the structure — so it must not be reported as instability on its own.
The clean drift measure is the **per-frame fitted scale against a fixed
reference**, which is reported with every comparison in §7 and is diagnostic
only, never used to normalise a residual.

Those per-frame scale traces range from **1.02** (E0 on `swimthrough_02` — near
perfect scale stability) to **6.64** (D on `wreck_03`). A 6.6× scale wander
inside one clip is a serious failure, and it happens on the dynamic-subject
clip.

### 5.2b Repeat-run determinism — all three dense models are bitwise reproducible

Re-running each model on `wreck_07` with identical inputs and the same seed, and
comparing the stored range products frame by frame:

| model | bitwise identical | max \|rel diff\| | valid masks identical |
|---|---|---|---|
| D MapAnything | **yes** | 0.000e+00 | yes |
| E0 VGGT | **yes** | 0.000e+00 | yes |
| E Wat3R-Ren | **yes** | 0.000e+00 | yes |

This matters more than it looks. The project's standing rule is that a
non-reproducible measurement instrument is disqualified — FlowIt was dropped in
Phase 2A for exactly this. Here **the run-to-run spread of the learned arm is
exactly zero**, so every dense-vs-dense difference in §7.3 is entirely method
difference with no noise floor to clear. The `PLAN.md` requirement that "observed
method differences must exceed run-to-run variability" is satisfied trivially for
D, E0 and E, and non-trivially only for the classical arm.

### 5.3 The paired experiment: does underwater adaptation help?

`E0 → E` is the controlled axis: same architecture, same code path, same
preprocessing (verified bit-identical by marker calibration, §3.5), same
frames, same conversion, same scale policy. Only the checkpoint differs.

Median scale-aligned relative range error against ordinary sparse SfM (A):

| clip | E0 vanilla VGGT | E Wat3R-Ren | adaptation effect |
|---|---|---|---|
| wreck_07 | 4.8 % | **3.5 %** | Wat3R-Ren closer to A |
| wreck_05 | 12.7 % | 13.1 % | tie |
| cenote_01 | 13.1 % | **20.1 %** | **Wat3R-Ren less consistent with A** |
| swimthrough_02 | **1.7 %** | 2.3 % | VGGT marginally closer to A |
| wreck_01 | 8.1 % | 8.4 % | level |
| wreck_03 | 3.9 % | 5.3 % | VGGT marginally closer to A |

And directly against each other, after one clip-level scale:

| clip | fitted s (E0→E) | median \|rel err\| | range swing | radius swing |
|---|---|---|---|---|
| wreck_07 | 0.837 | 13.1 % | **156.6 %** | 8.5 % |
| wreck_05 | 0.723 | 5.8 % | 67.9 % | 2.1 % |
| cenote_01 | 0.997 | 14.6 % | 63.6 % | 17.5 % |
| swimthrough_02 | 1.001 | 3.6 % | 18.5 % | 5.3 % |
| wreck_01 | 0.992 | 4.7 % | 22.7 % | 0.9 % |
| wreck_03 | 0.817 | 5.7 % | 64.5 % | 1.6 % |

**Verdict: condition-specific, and not a win.**

Adaptation is not a uniform improvement. It agrees more closely with A on one
wreck, is level on a second and on the reef swim-through, and **agrees markedly
less closely on the cenote** — where it is simultaneously the least consistent
method against both classical references (20.1 % median, 29 % radius swing,
64.6 % range swing) and the furthest from MapAnything (23.3 %). Note that "worse"
is not available as a word here: with no independent measurement, larger
disagreement with A is disagreement, not established error.

The cenote regression has a plausible domain explanation worth recording without
overclaiming: `cenote_01` is **fresh water with a visible halocline**, lit by
daylight through a cavern opening — not the marine attenuation/backscatter
regime Wat3R-Ren's ~359 k real underwater training frames target. An
underwater-adapted model regressing on the least marine-looking underwater clip
in the set is a coherent story, but this bakeoff cannot prove it: it has one
cenote clip and no independent truth.

Also note the two clips where the fitted E0→E scale is **0.72–0.84** rather than
~1.0 are exactly the two wrecks. Adaptation does not merely refine the geometry
there — it changes the overall scale by 16–28 %, which is free under §8.1 but
shows the two models are not small perturbations of each other.

> **Classification: condition-specific adaptation effect**, tending toward *no
> material improvement* overall, with one clear regression **relative to the
> tested references (A and C_off)** — not relative to truth, which is unmeasured. Per the amendment's
> own rule, this is not a reason to search for another underwater-adapted model.

### 5.4 MapAnything as a general range supplier — a separate question

Against ordinary sparse SfM, D's median relative range error is 5.8 %
(`swimthrough_02`), 8.9 % (`wreck_07`), 9.4 % (`wreck_01`), 11.4 %
(`cenote_01`), 14.1 % (`wreck_05`), 21.0 % (`wreck_03`).

Its weakest case is the dynamic-subject clip: on `wreck_03` its **fitted scale
relative to A wanders 6.64× across the clip**, with a 129.8 % range swing — the
largest such figures anywhere in this report. E0 on the same clip is 3.9 % median with
a 33 % range swing and 1.59× scale wander. **A large moving foreground subject
destabilises MapAnything's fitted scale relative to A far more than the VGGT
family's.**

### 5.5 Confidence barely predicts disagreement with the classical arm

Sampling each model's own confidence at the same observations and binning the
absolute error by confidence quintile, on `cenote_01`:

| model | confidence range | lowest-quintile median \|err\| ÷ highest-quintile |
|---|---|---|
| D MapAnything | saturated at 1.00 for ~80 % of pixels | **1.07** |
| E0 VGGT | 1.00 – 5.36 | **1.44** |

On the one clip tested, MapAnything's confidence carries essentially **no**
usable signal about disagreement with A — its lowest-confidence quintile shows
only 7 % more disagreement than its highest. VGGT's carries a weak but real one
(44 % more). Note this measures agreement with a *reference that is itself a
hypothesis*, not error against truth. Neither is calibrated for this
domain, and for vanilla VGGT the input is out of domain by construction.
**Confidence was never used to filter any geometry that was scored.**

---

## 6. Hybrid / global arm, and the explicit-backend arm

### 6.1 F — GLUEMAP: not executed, and the hypothesis is still open

GLUEMAP is the only candidate whose purpose is the **pose and global-consistency**
hypothesis: learned local geometry combined with classical rotation/similarity
averaging and global bundle adjustment. It did not run.

`colmap/gluemap` @ `adc9e4bb`, BSD-3. `INSTALL.md`, verbatim: *"GLUEMAP requires
CUDA at runtime — the GPU PyTorch build is the only supported configuration."*
That is not a device string that could be patched: `gluemap/estimators/
augmented_bundle_adjustment.py:302` calls `pygluemap.solve_cuda(...)`, and
`pygluemap` is a C++/Ceres extension built at install time. **The CUDA-only
component is the global-consistency stage that configuration F exists to test**,
so an MPS substitution would not be testing GLUEMAP. Status: `pending_cuda`.

**Consequence for the decision.** Nothing in this report bears on whether
classical global optimisation would fix the pose or scale-drift behaviour
observed in §5. The compositional option `strong global poses + strong dense
per-frame range` is neither supported nor refuted here — it is **untested**.

### 6.2 G — AMB3R: not executed, and it would not have been a clean ablation anyway

AMB3R tests a different hypothesis from GLUEMAP's: an explicit *learned* compact
3D backend rather than classical global optimisation. `HengyiWang/amb3r` @
`92c4081f`. Status: `pending_cuda`, plus a licensing problem — **the repository
contains no LICENSE file**, and its checkpoint ships via a Google Drive link with
no stated terms, so it stays strictly experimental regardless of hardware.

Its supported install pins CUDA 11.8 throughout, and one dependency is decisive:
**`spconv-cu118` is the compact volumetric backend itself** — the very component
G exists to test — with no CPU/MPS build. Replacing it would replace the
experiment.

Two facts established by reading it, which matter for how a future run should be
interpreted:

* **AMB3R's frontend is literally VGGT** (`amb3r/frontend.py`:
  `from vggt.models.vggt import VGGT`), which is what makes VGGT → AMB3R an
  architecturally tight pairing.
* **But not a clean one.** That VGGT is built as `VGGT(return_depth_feat=True)`
  and loaded from its own `checkpoints/VGGT.pt`, so the frontend *weights* and an
  extra depth-feature path differ from vanilla VGGT too. A VGGT → AMB3R
  difference would measure **"explicit backend plus retrained frontend"**, never
  the backend alone. Any future run must say so rather than attributing the
  result to the backend.

### 6.3 What would be needed to close both

One short session on a CUDA host running the **same six clips, the same frame
ranges and the same Stage 2 conversion path**, plus the numerical depth-semantics
check before any comparison. Note the two cannot share an environment: GLUEMAP's
supported recipe is CUDA 12.4 / PyTorch 2.4.1 while AMB3R pins CUDA 11.8 /
PyTorch 2.5.0 — two pinned environments in one session, not one.

**This is recorded as a known gap, not as a recommendation to rent hardware.**
Whether it is worth doing depends on §7 and §8: if the dense candidates that *do*
run locally already sit inside the restoration error budget, a better pose
estimator buys nothing the project can spend.

---

## 7. Cross-family shape comparison

### 7.0 How to read every number in this section

**Alignment.** One scalar `s` per (method-pair, clip), fitted as the median of
`log(reference/estimate)` over observations **pooled across every frame of the
clip**. Never one scale per frame. No local warping, no per-region scale, no
non-linear depth remapping. Per-frame scale fits appear only as an explicitly
labelled **drift diagnostic** and are never fed back into a residual — that is
the whole point of computing them, since per-frame renormalisation would erase
temporal scale instability, which is a real failure mode.

**Correspondence.** Dense-vs-sparse pairs a classical reconstruction's own
**image observation** with the dense field sampled at the corresponding pixel,
using the *measured* source→grid map of §3.5. It never matches 3D points between
two independently-posed clouds: two reconstructions with different world frames
and different scales share no coordinate system, so a 3D nearest neighbour
between them is not a correspondence at all. Sparse-vs-sparse pairs observations
**within the same image** by 2D proximity (≤ 1 px), which is again an image
observation.

**References.** Every dense method is reported **separately** against ordinary
sparse SfM (A) and against refractive sparse SfM (C_off/C_on). The two are never
merged or averaged. Neither is truth — both are candidates under test.
Where they disagree, that disagreement is preserved.

**What "agreement" means here.** With no independent measurement anywhere in this
phase, cross-method agreement is **consistency evidence only**. It is weakest
exactly where it looks most reassuring: E0 and E share an architecture and E is
derived from E0's weights, so their agreeing tells us almost nothing about
whether either is right.

```text
consistency evidence          everything in §7
independent correctness       nothing in this report
```

### 7.1 Columns used throughout

| column | meaning |
|---|---|
| coverage | fraction of the reference's eligible observations at which the dense field was valid and sampleable |
| fitted `s` | the one clip-level scale. **Information, not a score** — a method needing `s = 43` is not worse than one needing `s = 2.3` (§8.1) |
| \|rel err\| med / p95 | robust magnitude of the scale-aligned relative range residual |
| radius swing | max − min of the residual median across image-radius bins. The **distortion / refraction** signature axis |
| range swing | max − min of the residual median across reference-range bins. The **shape** axis, and the one §8 says actually costs restoration quality |
| per-frame `s` max/min | scale drift across the clip. **Diagnostic only** |

### 7.2 Dense vs sparse — the headline numbers

Scale-aligned median relative range error against **ordinary** sparse SfM (A).
Reported against **refractive** sparse SfM (C_off) separately; the two references
agree to ≤ 1.1 % on four of six clips, so the numbers below are nearly identical
against either, and they are never merged.

| dense | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|---|---|---|---|---|---|---|
| **D** MapAnything | 8.9 % | 14.1 % | 11.4 % | **5.8 %** | 9.4 % | **21.0 %** |
| **E0** VGGT | 4.8 % | 12.7 % | 13.1 % | **1.7 %** | 8.1 % | 3.9 % |
| **E** Wat3R-Ren | **3.5 %** | 13.1 % | **20.1 %** | 2.3 % | 8.4 % | 5.3 % |

Range swing (max − min of the residual median across range deciles) — **the
axis §8 says actually costs restoration quality**:

| dense | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|---|---|---|---|---|---|---|
| **D** | 19.9 % | 38.5 % | 32.7 % | **6.4 %** | 15.4 % | **129.8 %** |
| **E0** | 25.2 % | 33.0 % | 44.3 % | **3.5 %** | 9.7 % | 33.1 % |
| **E** | 15.7 % | 39.9 % | 64.6 % | 6.1 % | 15.3 % | 50.8 % |

Per-frame scale drift (diagnostic only, never applied):

| dense | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|---|---|---|---|---|---|---|
| **D** | 1.30 | 1.60 | 1.22 | 1.31 | 1.33 | **6.64** |
| **E0** | 1.14 | 1.79 | 1.19 | **1.02** | 1.25 | 1.59 |
| **E** | 1.14 | 1.72 | 1.56 | 1.08 | 1.39 | 2.05 |

Three things fall out:

1. **`swimthrough_02` is where everything works.** Every method lands at 1.7–5.8 %
   median with a 3.5–6.4 % range swing and near-zero scale drift. That is the
   ordinary reef swim-through — the realism case — and it is comfortably inside
   the restoration budget.
2. **The wrecks and the cenote are where nothing does.** 8–20 % median with
   20–65 % range swings. These are rigid, well-textured scenes where classical
   SfM registers 48/48, so this is not a registration failure: **the dense
   methods and the classical arm simply disagree about the shape of the range
   field**, and there is nothing here that says which is right.
3. **Fitted scales for the VGGT family sit at 13–52** against classical units,
   versus 0.59–4.05 for MapAnything (which claims metric scale). Per §8.1 that
   costs nothing and is reported as information, not as a score.

### 7.3 Dense vs dense

| pair | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|---|---|---|---|---|---|---|
| D vs E0 | 22.6 % | 10.1 % | 9.9 % | 10.4 % | **4.5 %** | 12.1 % |
| D vs E | 13.9 % | 9.2 % | **23.3 %** | 9.9 % | 6.8 % | 11.6 % |
| E0 vs E | 13.1 % | 5.8 % | 14.6 % | **3.6 %** | 4.7 % | 5.7 % |

**No pair agrees better than ~4 %, and most disagree by 10–23 %.** The tightest
agreement in the whole matrix — E0 vs E at 3.6 % on `swimthrough_02` — is also
the least informative, because E is derived from E0's weights.

**This is not strong convergence.** Three fundamentally different dense estimates
of the same 48 frames disagree by a median of one to two tens of percent, with
range-dependent swings up to 157 %.

### 7.4 Ordinary vs refractive sparse geometry

| pair | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|---|---|---|---|---|---|---|
| **A vs C_off** median | **0.04 %** | 8.9 % | 1.1 % | **0.01 %** | 0.12 % | 7.6 % |
| **C_off vs C_on** median | 16.5 % | 2.2 % | 21.5 % | 1.3 % | 3.2 % | — |
| **C_off vs C_on** fitted scale | 0.31 | 197.5 | 77.2 | 51.1 | 0.084 | — |

**The fitted-scale row is reported as bookkeeping, not as evidence, and no
conclusion is drawn from its spread across clips.** An earlier draft of this
report argued that a scale ratio ranging over 0.084 → 197 between clips showed the
refractive model failing to pin scale. **That argument was wrong and has been
removed.** Each `C_off` reconstruction carries its own arbitrary similarity gauge,
fixed independently per clip by its own initialisation; there is no reason
whatsoever for the `C_off → C_on` ratio to agree between two independently
reconstructed clips. Comparing those ratios across clips compares nothing.

The scale argument that *is* valid is the within-configuration one in §4.4(b):
inside a single `C_on` reconstruction, the millimetre-scale physical port
parameters sit at ~10⁻⁶ of the reconstructed scene range, and the null control
shows that ratio is produced by the active refractive physics. That argument
needs no cross-clip comparison and stands on its own.

The **top** row is the row that carries evidence here: ordinary and refractive-off
sparse geometry agree to ≤ 1.1 % on four of six clips, which is what validates
C_off as a control for C_on.

### 7.5 The radius × range interaction

Radius-profile slope of the residual computed separately within each range bin;
the spread across range bins is the flat-port signature.

| comparison | clip | slope mean | slope spread |
|---|---|---|---|
| D vs A | wreck_07 | −0.067 | 0.195 |
| E0 vs A | wreck_07 | +0.014 | 0.313 |
| E vs A | wreck_07 | +0.006 | **0.087** |
| D vs A | wreck_05 | −0.016 | 0.376 |
| E0 vs A | wreck_05 | −0.024 | 0.445 |
| E vs A | wreck_05 | +0.001 | 0.423 |
| E0 vs C_off | wreck_05 | +0.016 | **0.080** |
| E vs C_off | wreck_05 | +0.028 | **0.051** |

**The interaction is measurable but it cannot be attributed to the camera
model.** The spread changes by a factor of 5–8 depending on *which reference* is
used for the same dense method on the same clip (E0 vs A on `wreck_05` gives
0.445; E0 vs C_off gives 0.080). That is far larger than any plausible flat-port
effect, and it means what is being measured is dominated by the disagreement
between the references and by each dense model's own error — not by refraction.

Combined with §4.4's demonstration that C_on is scale-degenerate and fails on
half the clips, **the refraction discriminator did not fire and could not have
fired cleanly on this data.** Reporting a refraction conclusion from these
numbers would be reading a signal out of noise.

---

## 8. Restoration sensitivity — the error budget

**No restoration was performed.** This is a bounded analytical/synthetic study of
the project's own image-formation model, run to answer one question: *which kinds
and magnitudes of range error change the restored radiance enough to matter?*
Coefficients are bracketing Jerlov-style water types, not fits to this project's
footage — the shape of the sensitivity is the output, not the numbers'
provenance. Full sweep: `outputs/stage7/sensitivity.json`.

```text
I_c     = J_c · exp(−β_att,c · d) + B∞_c · (1 − exp(−β_bs,c · d))
Ĵ_c     = (I_c − B∞_c · (1 − exp(−β_bs,c · d̂))) / exp(−β_att,c · d̂)
```

### 8.1 Global scale is free — confirmed numerically, not assumed

With the coefficients freely fitted inside the clip, the substitution
`d → s·d`, `β → β/s` leaves `I` unchanged, so the refit recovers `J` exactly.
Swept over three water types × three channels × seven ranges × five scale factors
including `s = 3.2`:

| condition | max \|ΔJ/J\| | median \|ΔJ/J\| |
|---|---|---|
| global scale error, **coefficients refitted in-clip** | **4.5 × 10⁻¹³** | — |
| global scale error, **coefficients not refitted** | diverges (see below) | **9.0 %** |

So a wrong global scale costs **nothing** inside one clip, and a method needing
`s = 3.2` is not worse than one needing `s = 1.01`. It starts to cost the moment
β must be physically meaningful, is shared across clips, or when Week 6B
introduces a light with distance-dependent falloff.

The "max without refit" figure is a **divergence, not an error magnitude**: the
corrective gain is `exp(+β_att · s · d)`, which at `s = 3.2` and `d = 12 m` in
turbid water is `e³²`. That is worth recording for a different reason — unbounded
corrective gain is itself a failure mode Weeks 5–6 will have to clamp.

### 8.2 Local (spatially varying) range error is not absorbable

Worst-channel relative error in restored linear radiance:

| water | range | −20 % | −10 % | −5 % | +5 % | +10 % | +20 % |
|---|---|---|---|---|---|---|---|
| clear oceanic | 1 m | 3.0 % | 1.5 % | 0.8 % | 0.8 % | 1.6 % | 3.1 % |
| clear oceanic | 3 m | 7.3 % | 3.8 % | 1.9 % | 2.0 % | 4.1 % | 8.6 % |
| clear oceanic | 8 m | 10.1 % | 5.3 % | 2.7 % | 2.9 % | 6.0 % | 12.8 % |
| coastal | 1 m | 4.6 % | 2.3 % | 1.2 % | 1.2 % | 2.4 % | 5.0 % |
| coastal | 3 m | 9.3 % | 4.9 % | 2.5 % | 2.6 % | 5.4 % | 11.3 % |
| coastal | 8 m | 11.1 % | 6.1 % | 3.2 % | 3.9 % | 10.0 % | 31.0 % |
| turbid coastal | 1 m | 6.4 % | 3.3 % | 1.7 % | 1.7 % | 3.5 % | 7.3 % |
| turbid coastal | 3 m | 10.2 % | 5.5 % | 2.9 % | 3.2 % | 6.6 % | 14.4 % |
| turbid coastal | 8 m | 35.6 % | 29.6 % | 18.9 % | 30.7 % | 78.2 % | 255.1 % |

**The reusable thresholds** — the local relative range error at which the
worst-channel restored-radiance error first reaches 2 %, 5 % and 10 %:

| regime | 2 % | 5 % | 10 % |
|---|---|---|---|
| clear oceanic @ 1 m | 12.9 % | 31.3 % | 60.0 % |
| clear oceanic @ 3 m | 5.0 % | 12.1 % | 23.0 % |
| clear oceanic @ 8 m | 3.5 % | 8.5 % | 16.1 % |
| coastal @ 3 m | 3.9 % | 9.4 % | 17.9 % |
| coastal @ 8 m | 2.9 % | 6.1 % | 10.0 % |
| turbid coastal @ 3 m | 3.3 % | 7.8 % | 14.6 % |
| turbid coastal @ 8 m | 0.5 % | 1.0 % | 1.9 % |
| turbid coastal @ 12 m | 0.1 % | 0.3 % | 0.5 % |

**The sub-percent turbid-water numbers are not geometry requirements.** At
`turbid_coastal @ 8 m` the table says a 1.0 % range error already costs 5 % of
restored radiance, and at 12 m it says 0.3 %. Those must **not** be read as
"geometry must be accurate to 0.3 %". They identify a regime in which the
*inversion itself is ill-conditioned*, because transmission has almost vanished
and the corrective gain `exp(+β·d)` is exploding — the same divergence §8.1
flags. The correct downstream response is a policy, not a geometry target:

> Weeks 5–6 must impose a **minimum-transmission / maximum-corrective-gain**
> limit and abstain from aggressive inversion once the direct signal is too weak
> to support it. No achievable range accuracy rescues that regime.

Read as a working budget for the rest of the project:

```text
local range error  < ~5 %    negligible at reef distances in clear/coastal water
                   5-10 %    tolerable near, marginal beyond ~5 m
                   > ~10 %   dangerous
       and beyond ~5 m in turbid water the tolerance collapses toward zero
```

### 8.3 The part that matters most: a range error is a COLOUR error

β differs per channel, so the same relative range error produces a *different*
gain error per channel. A ±10 % local range error at 3 m in coastal water shifts
the red/blue gain ratio by several percent — a cast that a white-balance stage
cannot undo without itself becoming wrong, because the cast is spatially varying.
This is why `PLAN.md` weights shape error far above scale error, and it is the
reason the near/far *ordering* and the residual-versus-range profile matter more
than any aggregate error number.

### 8.4 Structured error forms

Uniform ±10 % behaves like a near-scale error and is largely absorbed by the
refit. A **range-dependent bias** (`d' = d(1 + g·d/d_max)`) is not: at `g = +0.3`
the red-channel error swings by tens of percent between 0.5 m and 12 m within a
single frame. That near-to-far swing — not the median — is the quantity to watch,
and it is exactly what the residual-versus-range-decile profiles in §7 measure.

---

## 9. Failure attribution

Phase 3A's value is not a ranking — it is knowing *which* failure was observed.
The named categories, and what this bakeoff can and cannot say about each:

| failure class | observed? | evidence and attribution |
|---|---|---|
| **insufficient parallax** | see §4 | Judged from triangulation behaviour and registration, not from the contact sheets. The lateral-glide clip was included specifically to expose it. |
| **matching failure** | see §4.3 | This is exactly what the A vs B pair isolates: same mapper, same camera model, different front end. |
| **camera-model / refraction failure** | **yes — but as non-identifiability, not as a shape error** | §4.4. |
| **radiometric / domain-shift failure** | see §5 | The E0 → E pair is the controlled test. |
| **dynamic-scene failure** | `wreck_03` | Included as the stress case. |
| **low-texture ambiguity** | `wreck_05`, `wreck_01` | `wreck_05` yields ~1 100 SIFT features/frame against `wreck_07`'s ~4 400 — a 4× difference on the *same camera and the same extraction*, which is a property of the footage, not of the method. |
| **pose / global-consistency failure** | **untestable here** | Configuration F, the candidate whose whole purpose is this hypothesis, is `pending_cuda`. |
| **dense local-depth failure** | see §5 | Visible in the range and difference maps. |
| **scale-drift failure** | **yes** | Per-frame scale traces are reported for every comparison as an explicit drift diagnostic and were never used to normalise a residual. |
| **comparison / convention uncertainty** | **actively hunted, and two real instances caught** | (i) The source→grid mapping was *measured* rather than assumed, which surfaced the portrait field-of-view asymmetry. (ii) The pose falsification control was initially a no-op because VGGT anchors its world frame to camera 0; it now runs on frames at 1/3, 2/3 and the end, and `check_completeness.py` marks any run whose inverted control scores within 2× of the correct one as stale. |

### Two failures that were mine, not the methods'

Recorded because they changed numbers that would otherwise have been reported:

1. **`Mapper.multiple_models` forced to false.** Reading COLMAP's
   `incremental_mapper.cc` showed `!multiple_models` *breaks out of the
   initialisation loop after the first trial*, making each reconstruction a
   single lottery draw on the initial image pair. Under that setting several
   clips "failed" at 2/48 and configuration B produced 48/48 on one run and 3/48
   on a byte-identical rerun. Restored to COLMAP's default; those numbers were
   discarded, and fragmentation is now handled by reporting every sub-model's
   size instead.
2. **A degenerate pose-convention check** (above), which would have reported the
   pose convention as "verified" while testing nothing.

Both are why `scripts/check_completeness.py` exists: it separates *a run that
died* (memory pressure — one did) and *a run made with superseded settings* from
*a method that failed*, so a gap can never be silently read as evidence.

---

## 10. Decision

### 10.1 Does the observed disagreement matter for restoration?

This is the only question that decides anything, and §8 gives the threshold.

```text
restoration error budget (§8.2)      observed geometry spread (§7)
------------------------------       -----------------------------
< ~5 %    negligible                  swimthrough_02:  1.7 - 5.8 %   INSIDE
5-10 %    tolerable, marginal > 5 m   wreck_01:        4.5 - 9.4 %   MARGINAL
> ~10 %   dangerous                   wreck_07:        3.5 - 22.6 %  OUTSIDE
                                      wreck_05:       10.1 - 14.1 %  OUTSIDE
                                      cenote_01:       9.9 - 23.3 %  OUTSIDE
                                      wreck_03:        3.9 - 21.0 %  OUTSIDE
```

And the range-dependent component — the part that produces a *spatially varying
colour cast* rather than a brightness offset (§8.3) — reaches **20–65 %** on four
of the six clips, against a budget where a 10 % local error already costs 5 % of
restored radiance at reef distances.

> **The methods are not tied downstream.** The geometry disagreement is well
> above the restoration-relevance threshold on four of six clips. Selection
> cannot be deferred to cost and determinism, because the methods are not
> measuring the same world.

The one clean exception is `swimthrough_02` — ordinary reef swimming, the
realism case — where every method lands inside the budget. That is genuinely
encouraging for the eventual pipeline and genuinely insufficient as a basis for
choosing a method.

### 10.2 Stage 8 outcome classification

Against `PLAN.md`'s predeclared outcomes:

* **Not Outcome A (strong convergence).** Three dense methods disagree by 4–23 %
  median with 9–157 % range swings. §7.3.
* **Not Outcome B (acquisition-limited by parallax) — but for a narrower reason
  than registration.** Configuration A registers 48/48 on four clips and ≥ 46/48
  on the other two, so the cameras can be related to each other. **Registration
  does not establish that depth is well conditioned**, and this report elsewhere
  calls `wreck_01` near-planar and ill-conditioned by construction, so it would be
  self-contradictory to read 48/48 as "the footage has enough parallax". What
  registration does establish is that a *separate* C1 acquisition is not the
  binding constraint: reconstruction is not what is failing. §4.1.
* **Not Outcome E (matching failure).** A did not fail, and where B produces
  co-located observations it agrees with A to 0.95 %, at 28× the cost. §4.3.
* **Outcome D (domain shift) — refuted in its strong form.** Underwater
  adaptation is condition-specific and regresses on the cenote. §5.3.
* **Outcome C (camera-model ambiguity) — the closest match, but with an
  important correction.** Ordinary and refractive geometry do differ materially.
  However the refractive arm is not a credible competing hypothesis here: it
  fails to initialise on three of six clips *even with refraction physically
  disabled* (§4.4a), and where it succeeds its scale is degenerate to within
  ~10⁻⁶ of irrelevance (§4.4b). So the ambiguity is real but it is **not
  demonstrated to be about refraction** — it is about the absence of any anchor
  that could adjudicate between hypotheses.
* **Outcome F (no single winner) — also true.** No method wins on shape across
  clips; MapAnything is honest about validity and cheapest in memory but breaks
  worst on dynamic content; VGGT is the most stable in scale but emits no mask;
  Wat3R-Ren wins on one wreck and loses on the cenote.

### 10.3 Recommended primary range supplier

**MapAnything (configuration D), provisionally, on grounds that are explicitly
not geometric accuracy.**

It is not the most accurate against either classical reference — VGGT edges it
on four of six clips. It is recommended because:

* its **code and checkpoint are both Apache-2.0** (`facebook/map-anything-apache`),
  so it can outlive the bakeoff. **This does not distinguish it from Wat3R-Ren**,
  which is also Apache-2.0 code with an Apache-2.0 checkpoint (§2.2) — an earlier
  draft claimed MapAnything was the *only* such candidate, which contradicted this
  report's own methods section. What licensing does settle is that **vanilla VGGT
  is disqualified as a default**: `facebook/VGGT-1B` is non-commercial and the
  commercial variant is gated. Between D and E the deciding factors are the next
  three points, not the licence;
* it emits an **explicit validity mask and a metric-scale claim**, both of which
  Weeks 5–6 need in the common representation, where the VGGT family emits
  neither;
* it is the **cheapest in memory** (10.3–10.8 GB vs 12.6–16.9 GB) and does not
  blow up on the portrait clip;
* its documented range semantics were **verified numerically** — `depth_along_ray
  == ‖pts3d_cam‖` to 1.1 × 10⁻⁵ — so the conversion onto the project's canonical
  quantity is exact rather than approximate.

**With one named condition:** its scale collapses on dynamic content (6.64×
wander, 129.8 % range swing on `wreck_03`). Any clip with a large moving
foreground subject must be flagged, and Week 5 must not consume MapAnything
range on such footage without a guard.

### 10.4 Recommended geometry cross-check

**Configuration A — ordinary COLMAP with SIFT.** It registered essentially
everything on all six clips, at 37–252 s per clip on CPU with no GPU, no
licence encumbrance and full inspectability. It is the cheapest and most
reliable instrument in the entire bakeoff.

**Configuration B is retired** unless a specific matching failure is later
observed: it agrees with A to 1 % and costs 28× more.

**Configuration C is retired as a reference** and reclassified as an open
question. It cannot serve as the refractive cross-check `PLAN.md` envisaged,
because it does not reliably reconstruct and its scale is degenerate.

### 10.5 Is hybrid composition useful?

**Unknown, and this bakeoff cannot say.** The compositional option — strong
global poses plus strong dense per-frame range — is exactly configuration F's
hypothesis, and F is `pending_cuda`. What the data *does* show is a
scale-drift problem (up to 6.64× within a clip) that a globally consistent pose
estimator is the natural candidate to fix. That raises the value of eventually
running F; it does not justify renting hardware now, because §10.6 identifies a
cheaper intervention that must come first.

### 10.6 Is new acquisition justified? **Yes — C2, and it is now the critical path**

This is the strongest conclusion of Phase 3A.

* **C1 (geometry clip): not justified as a separate acquisition.** The existing
  footage reconstructs — A registers 48/48 on four clips — so a clip shot purely
  to make reconstruction succeed would answer a question that is not open. That is
  *not* the same as saying parallax is adequate for well-conditioned depth, which
  this phase has not shown. **The controlled-parallax role should be folded into
  C2**: shoot it with deliberate lateral/arc motion so it subsumes C1's purpose
  rather than requiring a second trip.
* **C2 (scale and range anchor): justified, and it is now the blocker.** Every
  number in §7 is a *disagreement* between hypotheses with **no way to determine
  which is closer to true**. Four of six clips show disagreement above the
  restoration-relevance threshold, and this phase has exhausted what can be
  learned by comparing methods to each other. The refraction question is
  additionally blocked on exactly the same thing: the refractive fit escaped into
  a degenerate scale precisely because nothing constrained scale.
* **C3 (difficult clip): partially superseded.** `wreck_03` already fired the
  dynamic-subject failure and `wreck_01` the low-texture one, from existing
  footage.

> **Phase 3A selects MapAnything + COLMAP/SIFT as the provisional integration
> path. Independent C2 data is required before claiming objective geometry
> accuracy or resolving refraction, but it is NOT a blocker for downstream
> pipeline development.**

Weeks 5–6 can proceed on the selected path now: the range product exists in the
common representation, the error budget is measured, and the failure conditions
are named. What C2 unlocks is a different thing — the ability to convert every
figure in §7 from "these methods disagree" into "this method is off by X", and
to settle refraction. A rigid planar target of known dimensions at ≥ 3 measured
camera-to-target distances with recoverable plane pose, shot with deliberate
lateral/arc motion so it also subsumes C1's controlled-parallax role.

**Two things should be measured with it, not fitted:** the camera-to-interface
distance and the port thickness. §4.4(c) shows the refractive result is dominated
by them — a 25× change in the assumed stand-off moves implied scale 172× and
recovered focal 3×.

What is *not* worth doing first: adding an eighth geometry model, or renting a
GPU for F and G. Both buy more disagreement between unanchored hypotheses.

### 10.7 Best measured geometry vs best deployable path

| | |
|---|---|
| **best measured geometry** | undetermined — the methods are *different*, with correctness unmeasured. "Wrong" is not available as a word: it presupposes a truth this phase does not have |
| **best deployable path** | **MapAnything on MPS + COLMAP/SIFT cross-check**, both fully local, ~4 min and ~1 min per 48-frame clip, Apache-2.0 / BSD, no CUDA anywhere |

Nothing observed here justifies making CUDA a permanent requirement of this
project. F and G remain scientifically interesting and are recorded as untested;
if they are ever run it should be **after** C2 exists, so their output can be
judged against something other than the other candidates.

**The deployable path is not blocked on any of that.** MapAnything + COLMAP/SIFT
runs locally today, and Weeks 5–6 can consume its persisted range product while
the acquisition question is settled in parallel.

---

## 11. Known limitations

Ordered by how much they should change a reader's confidence.

1. **There is no independent range or scale measurement anywhere in this
   phase.** The C2 acquisition `PLAN.md` specifies does not exist. Every
   cross-method number in §7 is a **consistency** statement. Two methods agreeing
   closely could both be wrong in the same way — and for two VGGT-derived models
   that is not a remote possibility, it is the expected failure. Nothing here
   establishes that any method's range is *correct*.

2. **Sparse SfM is not ground truth and was not treated as such.** Configurations
   A/B/C are themselves candidates. Every dense method is reported separately
   against ordinary sparse SfM and against refractive sparse SfM, and the two are
   never merged or averaged.

3. **Global scale is unidentifiable and deliberately not scored.** Every
   comparison allows one clip-level scale. A method needing `s = 43` is not
   penalised relative to one needing `s = 2.3`. §8.1 confirms numerically that
   this costs nothing while β is fitted in-clip.

4. **The flat-port parameters are assumed, not measured.** `int_dist = 2 mm ±
   2 mm` and `int_thick = 1 mm ± 0.5 mm` are plausible GoPro values from the
   literature, not measurements of this camera. Flat-port geometry remains an
   open named blocker. Every refraction statement is conditional on them, which
   is why the `C_on_thick` diagnostic exists.

5. **No dense result is native-resolution geometry.** Every dense field was
   produced on a ~518-px grid — a 2.5× downscale from the 1280-px extraction and
   3.7× from the source. Fine-scale range structure below that grid was never
   measured, and a refractive residual confined to it would be invisible here.

6. **VGGT and Wat3R-Ren discard ~44 % of the vertical field of view on the
   portrait clip.** On `wreck_01` they and MapAnything are not looking at the
   same scene. Cross-family numbers on that clip are correspondingly weaker
   evidence.

7. **Confidence is not calibrated for this domain.** Both families emit a
   learned per-pixel confidence trained on other data; for vanilla VGGT the
   input is out of domain by construction. Confidence was recorded as data and
   never used to filter the geometry being scored.

8. **COLMAP is not bitwise reproducible here, and the repeat runs bound rather
   than eliminate that.** Mapping is pinned to a single thread, but feature
   extraction and matching remain multithreaded. Any claimed method difference
   must exceed the measured repeat-run spread, and §4 reports that spread rather
   than assuming it away.

9. **Two candidates were never executed on this hardware** (F GLUEMAP, G AMB3R —
   both `pending_cuda`) and **three were never released** (H SeaVGGT, I
   Water-VGGT, J WAT3R-Xu). Their hypotheses are open, not answered. In
   particular, the "learned local + classical global" hypothesis (F) and the
   "explicit 3D backend" hypothesis (G) remain untested on this footage.

10. **Dynamic content, illumination variation and the auto-white-balance shift**
    in `swimthrough_02` are present and were not controlled for. They are part of
    what makes these development clips realistic, and part of why they cannot
    separate causes the way a controlled C1 clip would.

11. **The restoration sensitivity study is analytical.** It uses bracketing
    Jerlov-style coefficients, a single assumed `J` and `B∞`, and no real
    footage. It bounds *when* range error starts to matter; it does not predict
    what any particular clip's restoration will look like.

12. **The clips are development data, not a held-out set.** They were inspected
    during selection. The `frozen_eval` suite was deliberately untouched, and the
    selected method has **not** yet been run against it — `PLAN.md`'s realism
    check remains outstanding.
