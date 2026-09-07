# S0 — semantics, preprocessing and runtime gate

**Stage:** S0 of the frozen Week-4A sequence in `MONO_DEPTH_FREEZE.md`. 
**Status:** all seven mandatory checkpoints PASS. No model exits at S0.

S0 is wrapper validation, not benchmarking. It ran the four-image sanity set the
freeze specifies — an ordinary project frame, a difficult project frame, a
portrait/orientation-sensitive project frame, and a vendored public reference
image — plus a 25-marker FOV audit at both source orientations. It did **not**
run the 288-frame benchmark, and it ranks nothing.

## 0. Frozen material

`verify_frozen_set --hash`: **ok=True**, 288/288 frames.

Every one of the six clips is present at 48 frames, every SHA-256 matches the
Week-3 `extraction_report.json`, and the persisted `D_mapanything` reference
product exists at 48 frames for each. The primary bakeoff therefore runs on
exactly the material Week 3 characterised; nothing was regenerated.

`wreck_01` is the one portrait clip (1280x720). That is not incidental — it is
the orientation case the freeze keeps in the primary set precisely because
Week-3 preprocessing lost field of view there.

## 1. Runtime and device matrix (measured on this host, not read from papers)

Apple M4, 24 GB unified memory, macOS 26.6.2. **No CUDA anywhere on this host.**
Times are one image on the ordinary-project frame; S1 measures runtime properly.

| model                   | status | load s | infer s | MPS | CPU   | strict N=1 |
|-------------------------|--------|--------|---------|-----|-------|------------|
| mapanything_n1          | PASS   | 15.5   | 1.33    | yes | yes   | True       |
| dav2_small              | PASS   | 0.9    | 0.28    | yes | FAILS | True       |
| moge2_vitl              | PASS   | 4.6    | 2.32    | yes | yes   | True       |
| metricanything_pointmap | PASS   | 4.9    | 2.13    | yes | yes   | True       |
| wat3r_n1                | PASS   | 9.0    | 1.37    | yes | yes   | True       |
| da3mono_large           | PASS   | 2.5    | 0.41    | yes | yes   | True       |
| foundationgeo_11        | PASS   | 4.9    | 1.71    | yes | yes   | True       |

Nothing in the mandatory set requires CUDA. The one CPU failure is a
reference-implementation quirk, not a capability limit: Depth Anything V2's
`image2tensor` picks its device from `torch.cuda.is_available()` /
`torch.backends.mps.is_available()` and ignores the device the model is on, so on
this host it always ships the tensor to MPS. Running DA V2 on CPU would need a
reference-implementation modification. It was not made, because MPS works and MPS
is what the bakeoff uses.

### Reference-implementation modifications actually required

- **da3mono_large** — two, both packaging-only and neither touching the model: (1) pyproject requires-python widened from '<=3.13' to '<3.14' so it installs on CPython 3.13.5; (2) the pycolmap-backed COLMAP EXPORT import in utils/export/__init__.py made optional, because importing pycolmap alongside torch aborts on macOS with a duplicate libomp. The export path is never used here. Patch: patches/da3_no_pycolmap_and_python313.patch

Recorded under `patches/`. Neither touches model weights, model structure or any
numerical path: one widens a `requires-python` bound, one makes an unused COLMAP
export import optional, and one moves an uninitialised-parameter allocation off a
hard-coded `cuda` that a CUDA-less host cannot satisfy — every one of those
parameters is then overwritten by a strict `load_state_dict`.

Two further deliberate non-modifications are worth stating, because each replaces a
patch that would have been easy and wrong:

- **MoGe family** — `moge` is put on `sys.path` explicitly rather than pip-installed.
  Both the MetricAnything release and upstream microsoft/MoGe ship a package literally
  named `moge`; an installed one would silently win, and V5 would quietly stop being a
  controlled architecture comparison. Both checkpoints load into the SAME class from
  the SAME source tree, and which tree is recorded in provenance.
- **FoundationGeo** — `infer()` is not called. It postprocesses its two ray-correction
  arms through independent `recover_focal_shift` solutions, so their difference is the
  ray correction PLUS whatever focal and shift each recovered separately. The backend
  calls `forward()` and applies one frozen solution to both arms instead, which is
  what FREEZE C3 requires for the difference to be attributable to the ray delta.

## 2. Native representation and what each model can honestly emit

| model                   | native_kind            | range_rule               | range? | K?  | conf? | native shape   |
|-------------------------|------------------------|--------------------------|--------|-----|-------|----------------|
| mapanything_n1          | depth_along_ray_metric | identity_depth_along_ray | yes    | yes | yes   | [294, 518]     |
| dav2_small              | disparity_relative     | unresolved               | NO     | no  | no    | [720, 1280]    |
| moge2_vitl              | pointmap_metric        | norm_pointmap            | yes    | yes | no    | [720, 1280, 3] |
| metricanything_pointmap | pointmap_metric        | norm_pointmap            | yes    | yes | no    | [720, 1280, 3] |
| wat3r_n1                | pointmap               | zdepth_to_range_with_K   | yes    | yes | yes   | [294, 518, 3]  |
| da3mono_large           | depth_relative         | unresolved               | NO     | no  | no    | [280, 504]     |
| foundationgeo_11        | pointmap_metric        | norm_pointmap            | yes    | yes | no    | [720, 1280, 3] |

**Two models cannot emit a canonical range at all, and that is the correct answer,
not a gap.**

- `dav2_small` emits relative inverse depth. Its legal ambiguity is affine in
  DISPARITY (`q' = a q + b`). Inverting before that transform is fitted produces a
  number that looks like a range and is not one, so the backend writes none and S2
  does the inversion once, under the frozen policy.
- `da3mono_large` was expected to emit z-depth plus a camera. **It does not.** The
  `da3mono-large` config is a DINOv2 ViT-L with a single DPT head of `output_dim: 1`;
  the returned `Prediction` carries `depth` and `sky` and nothing else —
  `intrinsics`, `extrinsics` and `conf` are all `None`. Range needs a camera, so
  supplying one would have to be invented, and an invented focal manufactures
  exactly the radial error M-6 exists to detect. This also leaves the z-vs-range
  question about its native field genuinely open, because the reference
  implementation's own `unproject_depth` (which treats depth as z) is never reached
  for this checkpoint. S2 settles it by measurement: this camera's secant factor
  spans roughly 1.00-1.35 across the frame, far too large a signal to miss.

The z-vs-range conversions that WERE available are verified numerically per frame
rather than assumed:

| model                   | measured on the ordinary-project frame                                                                                 |
|-------------------------|------------------------------------------------------------------------------------------------------------------------|
| mapanything_n1          | max_abs_depth_z_minus_pts3d_cam_z=0; max_abs_range_minus_norm_pts3d_cam=1.14441e-05; median_ratio_range_over_z=1.11757 |
| moge2_vitl              | max_abs_depth_minus_points_z=0; median_ratio_range_over_z=1.19419                                                      |
| metricanything_pointmap | max_abs_depth_minus_points_z=0; median_ratio_range_over_z=1.11372                                                      |
| wat3r_n1                | max_abs_range_minus_norm_points=0                                                                                      |
| foundationgeo_11        | median_ratio_range_over_zdepth_metric=1.11683                                                                          |

`median_ratio_range_over_z` sits at 1.11-1.19 with a maximum of 1.35-1.59 at the
frame corners. That IS the size of the z-vs-range mistake on this wide-FOV camera:
treating z-depth as range would inject a 11-19 % median and up to 59 % corner error,
purely radial, straight into the diagnostic that decides whether a camera-model
challenger gets activated.

## 3. FOV audit — measured, at both orientations

25 markers per orientation, pushed through each model's OWN preprocessing (the
Week-3 method). Markers that fall outside the model grid after cropping are
reported, never silently dropped.

| model                   | orientation | model grid (H,W) | markers lost | area retained | affine residual |
|-------------------------|-------------|------------------|--------------|---------------|-----------------|
| mapanything_n1          | landscape   | [294, 518]       | 0/25         | 0.987         | resid<=0.22px   |
| mapanything_n1          | PORTRAIT    | [518, 294]       | 0/25         | 0.990         | resid<=0.20px   |
| dav2_small              | landscape   | [518, 924]       | 0/25         | 1.000         | resid<=0.24px   |
| dav2_small              | PORTRAIT    | [924, 518]       | 0/25         | 1.000         | resid<=0.24px   |
| moge2_vitl              | landscape   | [630, 1120]      | 0/25         | 0.999         | resid<=0.14px   |
| moge2_vitl              | PORTRAIT    | [1120, 630]      | 0/25         | 0.999         | resid<=0.14px   |
| metricanything_pointmap | landscape   | [630, 1120]      | 0/25         | 0.999         | resid<=0.14px   |
| metricanything_pointmap | PORTRAIT    | [1120, 630]      | 0/25         | 0.999         | resid<=0.14px   |
| wat3r_n1                | landscape   | [294, 518]       | 0/25         | 0.994         | resid<=0.22px   |
| wat3r_n1                | PORTRAIT    | [518, 518]       | 10/25        | 0.560         | resid<=0.14px   |
| da3mono_large           | landscape   | [280, 504]       | 0/25         | 0.997         | resid<=0.32px   |
| da3mono_large           | PORTRAIT    | [504, 280]       | 0/25         | 0.997         | resid<=0.32px   |
| foundationgeo_11        | landscape   | [592, 1056]      | 0/25         | 0.999         | resid<=0.29px   |
| foundationgeo_11        | PORTRAIT    | [1056, 592]      | 0/25         | 0.999         | resid<=0.29px   |

**The portrait trap is real and it is Wat3R's alone.** On the 1280x720 portrait
source, `wat3r_n1` loses 10 of 25 markers and retains **56.0 %** of the frame area:
its `crop` branch resizes the short side to 518 and centre-crops the long side to
518, discarding the top and bottom of every portrait frame. This reproduces Week 3's
VGGT-family finding exactly. Every other entrant retains 98.7-100 % at both
orientations.

The consequence for `wreck_01` — the one portrait clip, and the low-texture
near-planar case — is that Wat3R is not seeing the same scene as the other six
models there. S3 must evaluate on the intersection of valid support, and Wat3R's
`wreck_01` column has to be read as a different, smaller field of view rather than
as a like-for-like result. The affine residuals are all sub-pixel, so the maps
themselves are trustworthy.

## 4. Strict single-image invariant

Every backend takes ONE image path. There is no batch, list or sequence argument to
get this wrong with. The two multi-view architectures assert it twice: MapAnything
checks both that `load_images` returned one view and that the model returned one
prediction; Wat3R asserts the preprocessed tensor has S=1. All seven verified.

## 5. Checkpoint integrity — MetricAnything vs stock MoGe-2

**Verdict: LINEAGE_CONSISTENT.**

- `model_config` identical: **True**
- parameter key sets identical: **True** (483 vs 483 tensors)
- shape mismatches: **0**
- bitwise-identical tensors: **3/483**
- global relative L2 change: **0.0096**

| module      | tensors | median rel L2 | max rel L2 |
|-------------|---------|---------------|------------|
| encoder     | 352     | 0.0002        | 0.1117     |
| mask_head   | 38      | 0.0194        | 0.0848     |
| neck        | 48      | 0.0326        | 0.1389     |
| points_head | 38      | 0.0269        | 0.1091     |
| scale_head  | 6       | 0.0436        | 0.1509     |

This is a decoder-heavy fine-tune and the numbers say so plainly: the DINOv2
encoder barely moves (median 0.02 % relative L2 over 352 tensors) while the neck,
points head, mask head and scale head move 1.9-4.4 %. The documented lineage
holds, which is what V5 needs — the architecture and representation really are
controlled. It does **not** identify which component of the fine-tuning treatment
causes any downstream difference; FREEZE C5 keeps data, objectives, supervision
and camera diversity confounded, and this measurement does not unconfound them.

The check was mandatory because of the Week-3 Water-VGGT checkpoint-integrity
finding, not because of download statistics.

## 6. Notable per-model observations

- **`dav2_small`** — 15.3 % of the ordinary-project frame comes back with disparity
  <= 0 (the head's floor). Those pixels are masked out rather than inverted; they are
  where the model has no usable far-field signal, and they will matter in M-1's far
  bins.
- **`moge2_vitl` vs `metricanything_pointmap`** — on the same frame the two infer
  materially different cameras: normalised fx 0.465 vs 0.611, i.e. MetricAnything
  recovers a substantially longer focal from the same pixels. Since both models'
  metric scale is coupled to the recovered focal, this is a concrete pre-S3 reason to
  expect their absolute scales to disagree, and it is what V9's known-FOV
  postprocessing ablation is for.
- **`foundationgeo_11`** — the two internal ablation arms come out of ONE forward
  pass and share ONE frozen (focal, shift) solution, per FREEZE C3. Two things are
  already visible on the sanity frame. The learned ray correction turns rays by a
  median of **0.044 deg** (p95 0.11 deg, max 0.78 deg) — an order of magnitude below
  its own 3 deg cap. And the `scalefield`, which the release describes as a per-pixel
  spatial field, has an interquartile spread of roughly 0.82-0.85 around a median of
  0.84: on this frame it is behaving almost like a global scalar. Both are
  observations on one frame and neither is a conclusion; S3 runs the ablation properly.
- **`mapanything_n1`** — `depth_along_ray == ||pts3d_cam||` re-verified at N=1 to
  7.6e-06, so the Week-3 range identity survives the view-count change. Its
  `metric_scaling_factor` is emitted per frame and is recorded, not applied.
- **`wat3r_n1`** — emits `world_points` and `world_points_conf` alongside the depth
  head. At N=1 the world frame is the single camera's frame, so those add nothing
  here; the camera-frame point map built from (z, K) is what is stored.

## 7. Gate outcome

**Survivors: 7/7 — all mandatory checkpoints continue to S1.**

No model failed semantics. Two models had a documented expectation corrected by
measurement rather than repaired (DA3 Mono emits no camera; DA V2 cannot be
inverted yet), which is the outcome the freeze asks for: record the semantics,
never invent them.

Carried into S2 as open questions S0 deliberately did not answer:

1. Is `da3mono_large`'s native field z-depth or range? (Measurable: fit it against
   the reference range and the reference z-depth in turn.)
2. What camera should lift `da3mono_large` and `dav2_small` into a range field, and
   is that a frozen evaluation convention rather than a model property?
3. Wat3R's native ambiguity, which the freeze forbids inferring from its released
   evaluation code's alignment.
