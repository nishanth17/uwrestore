# Round-2 S0 acquisition brief (shared by all six challengers)

You are acquiring ONE monocular-geometry model for a frozen underwater-restoration
experiment. Your job is **acquisition + semantics + a runnable strict-N=1 inference
path**, not evaluation. Somebody else runs the 288-frame bakeoff.

Read this file once. Do NOT read the wider repository history, `LOG.md`,
`MONO_DEPTH_LANDSCAPE.md`, or the Round-1 result files — they are large and you do
not need them.

## Hardware and the one hard constraint

Apple M4, 10 cores, **24 GB unified memory, macOS. There is NO CUDA anywhere and no
cloud GPU is available.** Inference is MPS or CPU, **float32, autocast/fp16 OFF**
(half precision would put a stochastic floor under deltas the experiment must read).

If the official implementation genuinely cannot execute correctly without CUDA
(fused/compiled CUDA kernels with no correctness-equivalent CPU or MPS path):

    status = pending_cuda

and STOP that model. Record the exact checkpoint, the requirement, the command that
would run it, and where you stopped. **Do NOT port CUDA kernels, do NOT swap an
operator for an approximate one, do NOT substitute an unofficial reimplementation,
do NOT fabricate output.** A model that stops here is a legitimate, useful result.

Likewise, if you cannot establish correctness-equivalent execution for some other
reason: `status = pending_runtime`. Same rule.

## Reference-implementation integrity (record this explicitly)

Classify what you ran:

    A. exact official/reference implementation, unmodified
    B. mechanically adapted official implementation, model math UNCHANGED
       (device placement, dependency/version compatibility, file paths, tensor I/O)
    C. unofficial / reimplementation   <-- NOT acceptable for a primary result

Enumerate every category-B change, one line each. The following are **forbidden**
and turn a result into C: replacing unsupported operators with approximations,
changing interpolation modes, changing model input resolution to make memory fit,
substituting checkpoints, removing refinement stages, changing attention
implementations that are not numerically equivalent, or pulling in a helper model
(e.g. using MoGe to supply another model's scale).

`torch.nn.functional.scaled_dot_product_attention` backend selection is fine.
`xformers`/`flash-attn` unavailable on Mac: use the stock PyTorch attention path the
repo itself falls back to, and say so.

## Strict N=1 — the invariant the whole phase is built on

**One image in, one prediction out.** You must verify from the SOURCE CODE, not the
README, that a single-image call:

  * feeds exactly one view to the network,
  * does not silently duplicate/pair the frame into a 2-view batch,
  * carries no cached state between calls,
  * uses no sequence/temporal/multi-view aggregation.

If the model's single-image path internally builds a multi-view structure, document
exactly what happens — do not paper over it. Strict N=1 is mandatory; a violation is
a STOP for that model.

## Semantics — read the code, never the paper's abstract

The single most expensive error available here is guessing what the model's output
number means. Round 1 got this wrong for one model by deciding z-depth-vs-range from
a residual instead of from the code, and it cost a whole re-analysis. **Source
evidence wins.** Cite file:line for every claim below.

Resolve, from the released code:

    native_kind          which of: disparity_relative | depth_relative |
                         depth_along_ray_metric | pointmap_relative |
                         pointmap_metric | pointmap  (unstated scale claim)
    scalar convention    if it emits a scalar: projective/camera-axis Z-DEPTH, or
                         Euclidean ray RANGE ||P||?  Show the unprojection code.
                         (Idiom: `P = D * K^-1 [u,v,1]` with an UNNORMALISED ray has
                         z-component 1, so D is Z-DEPTH. `P = D * unit_ray` is RANGE.)
    legal ambiguity      metric / scale-only / scale+shift, and IN WHICH SPACE the
                         shift is legal (depth? disparity? the point map's z?)
    point-map gauge      for point-map models: the documented normalisation
    camera                does it predict intrinsics/FOV? in what parameterisation?
    mask/validity        what the mask means; sky handling
    output resolution    and how it relates to the input
    preprocessing        resize/crop/pad/normalise; ASPECT RATIO and FOV handling;
                         orientation (this set contains a PORTRAIT clip, 1280x720)
    confidence           present or absent; what it is

## The four fixed sanity images

```
ordinary  /Users/nishanthmohan/code/uwrestore/experiments/week3_geometry/phase3a/outputs/frames/wreck_07/f000109.png   720x1280 landscape underwater
difficult /Users/nishanthmohan/code/uwrestore/experiments/week3_geometry/phase3a/outputs/frames/wreck_05/f000113.png   720x1280 landscape, low texture/hazy
portrait  /Users/nishanthmohan/code/uwrestore/experiments/week3_geometry/phase3a/outputs/frames/wreck_01/f001855.png   1280x720 PORTRAIT — the orientation trap
public    /Users/nishanthmohan/code/uwrestore/experiments/week4_mono/round1/vendor/FoundationGeo/demo/indoor.jpg      non-underwater control with obvious scene semantics
```

Run all four. The portrait one matters: one Round-1 entrant lost 44 % of the frame
to a square-crop preprocessing path and that was only caught because this image was
in the set. Report, for the portrait frame, whether the model's preprocessing
preserves the full field of view or crops it, and by how much.

## Where things go — and what you must NOT touch

```
experiments/week4_mono/round2/vendor/<repo>/       your git clone (gitignored)
experiments/week4_mono/round2/.venv-<key>/         your venv (gitignored)
experiments/week4_mono/round2/s0_agent/<key>/      YOUR DELIVERABLES
experiments/week4_mono/round2/outputs/s0/<key>/    smoke .npy/.png dumps
```

**Do not modify ANY file outside those four paths.** In particular do not touch
`experiments/week4_mono/*.py`, `scripts/`, `results/`, `common.py`, the existing
venvs, `uw/`, `LOG.md`, or anything under `data/`. Do not `git add`, `git commit`,
or `git checkout`. Do not delete anything you did not create.

Clone with `git clone --depth 1` and **record the resolved commit SHA**.
Build the venv with the SAME python as the others: `/opt/homebrew/bin/python3.13`
if present, else the interpreter that `experiments/week4_mono/.venv-eval/bin/python
-V` reports. Install torch as a normal pip wheel (MPS is built in on macOS arm64).

## Serialise every inference

Downloads and pip runs go in parallel; **network forward passes must not.** Wrap any
command that runs a model:

```
python3 experiments/week4_mono/round2/gpu_lock.py -- <your command>
```

Keep peak memory under ~9 GB. If you OOM, report it as a measurement, do not shrink
the input resolution to get around it.

## Deliverables — exactly these three files

### 1. `round2/s0_agent/<key>/semantics.json`

```json
{
  "key": "<key>", "checkpoint": "<exact hub id or URL>",
  "repo": {"url": "...", "commit": "...", "license": "...", "license_source": "file:line or URL"},
  "checkpoint_license": "...", "checkpoint_license_source": "...",
  "status": "ready | pending_cuda | pending_runtime | failed",
  "integrity_category": "A | B | C",
  "category_b_changes": ["..."],
  "strict_n1": {"verified": true, "how": "file:line evidence", "notes": "..."},
  "native_kind": "...", "native_kind_evidence": "file:line",
  "scalar_convention": "z_depth | range | n/a", "scalar_convention_evidence": "file:line",
  "legal_ambiguity": "...", "ambiguity_space": "...", "ambiguity_evidence": "file:line",
  "predicts_camera": true, "camera_parameterisation": "...",
  "mask_semantics": "...", "confidence": "...",
  "preprocessing": {"resize": "...", "crop": "...", "aspect_preserved": true,
                    "fov_retained_portrait": 0.0, "orientation_handling": "...",
                    "output_hw_for": {"720x1280": [0,0], "1280x720": [0,0]}},
  "runtime": {"device": "mps|cpu", "dtype": "float32", "load_s": 0.0,
              "per_frame_s": 0.0, "peak_rss_gb": 0.0, "peak_mps_gb": 0.0},
  "determinism_quick": {"same_process_bitwise": true, "cross_process_bitwise": true},
  "smoke": {"ordinary": "...", "difficult": "...", "portrait": "...", "public": "..."},
  "open_questions": ["..."]
}
```

Every field you could not establish gets `null` plus a line in `open_questions`.
**Never guess a value.** A null with a reason is worth more than a plausible number.

### 2. `round2/s0_agent/<key>/REPORT.md`

Under 120 lines. Cover: what the model is and why it is being tested (given in your
task), how you acquired it, the semantics with file:line citations, the strict-N=1
evidence, integrity category and every B change, the smoke results including the
portrait FOV finding, runtime/memory, determinism, and anything that surprised you.
Include the exact commands to reproduce.

### 3. `round2/s0_agent/<key>/infer_one.py`

A standalone script, runnable as

```
round2/.venv-<key>/bin/python round2/s0_agent/<key>/infer_one.py --image <path> --out <dir>
```

that loads the checkpoint, runs ONE image, and saves the NATIVE output plus a
validity mask as `.npy`, with a small `meta.json` recording native_kind, shapes,
device, dtype, timing, and the model's camera if it predicts one. Keep it plain and
dependency-light; it becomes the basis for the production backend, so make the
model-loading and the one forward pass obvious and separable.

Also save a quick visual (`.png`, e.g. a normalised depth/z colourmap) per sanity
image under `round2/outputs/s0/<key>/` — a human will look at these.

## Reporting back

Your final message is a COMPACT summary: status, integrity category, native_kind +
convention with its evidence, strict-N=1 verdict, portrait FOV retention, per-frame
runtime and peak memory, determinism, and the two or three things that would change
how the model is scored. Do not paste code, logs, or JSON dumps into it — those live
in the files. Under 40 lines.

If the model stops (`pending_cuda` / `pending_runtime` / `failed`), say so in the
first line and make sure `semantics.json` records everything needed to resume it
elsewhere.
