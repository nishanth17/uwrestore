# Week 4A — monocular depth bakeoff

**This directory is not part of the `uwrestore` package.** It is scaffolding for
one comparison: is strict monocular depth adequate for the underwater-restoration
fallback path? Nothing under `uw/` imports anything here, none of it is
installed, and none of it is a project dependency. If a monocular path is
selected it gets promoted deliberately — the way `uw/flow.py` was in Phase 2B —
not by accident.

The authoritative experimental specification is
[`MONO_DEPTH_FREEZE.md`](MONO_DEPTH_FREEZE.md). Where any other Week-4 document
conflicts with it, the freeze wins. The reports live in [`results/`](results/).

## The one thing to know before reading any number

The reference throughout is the **Week-3 persisted range product**
(`D_mapanything`), which is a **provisional multi-view hypothesis, not ground
truth**. There is still no independent range measurement anywhere in this
project — the C2 scale-and-range acquisition does not exist yet. So every
"error" here is *disagreement with the current Week-3 hypothesis*, and pre-C2 a
disagreement cannot say which side is wrong. There is no objective Week-4 winner
in these results, by construction.

Week 3 also measured its own reference's instability, and it is large on exactly
the low-texture clips: whole-pipeline reruns moved `wreck_05` by 2.1–6.5 %
median while `wreck_07` moved 0.01 %. That, not the models' numerical noise, is
the binding floor on this comparison.

## The frozen set

Six Week-3 development clips, the existing Week-3 extraction, unchanged:

| clip | role | orientation |
|---|---|---|
| `wreck_07` | high-texture arc; favourable geometry support | landscape |
| `wreck_05` | lower-texture lateral glide; weak geometry support | landscape |
| `cenote_01` | widest near/far range variation | landscape |
| `swimthrough_02` | ordinary reef / representative normal case | landscape |
| `wreck_01` | low-texture, near-planar; the FOV/orientation trap | **portrait** |
| `wreck_03` | dynamic diver; moving-object failure case | landscape |

48 frames each, 1280-pixel long side → **288 frames per model**. Verified
bit-for-bit against Week 3's `extraction_report.json` before anything ran
(`verify_frozen_set --hash`). Nothing was regenerated.

## Dependency exception

`CLAUDE.md` invariant 8 says lightweight dependencies by default. Evaluating
seven pretrained geometry models needs PyTorch and seven research repos, so this
phase is a scoped exception, scoped the same way Weeks 2A and 3 were: the heavy
stacks live in venvs *inside this directory*, `pyproject.toml` is untouched, and
the main project venv still has only numpy + opencv.

## Environments

One model per process. Process exit is the authoritative MPS cleanup boundary
(the Week-3 rule), and two entrants peak above 9 GB on a 24 GB machine.

| venv | Python | holds | runs |
|---|---|---|---|
| `.venv-mono` | 3.13 | torch 2.13, **numpy<2** | DA V2 Small, DA3 Mono, FoundationGeo |
| `.venv-moge` | 3.13 | torch 2.13, **numpy≥2**, utils3d @ 3fab839f | MoGe-2, MetricAnything |
| `.venv-eval` | 3.13 | torch 2.13, numpy≥2, EvalMDE, scipy | **all analysis** |
| `week3/.venv-mapanything` | 3.13 | mapanything 1.1.4 | MapAnything N=1 |
| `week3/.venv-vggt` | 3.13 | torch 2.13 | Wat3R N=1 |
| `week2a_flow/.venv-flow` | 3.13 | SEA-RAFT | S5 correspondence, S6 temporal |

The numpy split is not cosmetic: Depth Anything 3 pins `numpy<2` and MoGe pins
`numpy>=2`. `.venv-eval` is separate from every model venv on purpose — a change
to a model's stack must not be able to silently alter the measuring instrument.

Hardware: Apple M4, 10 cores, 24 GB unified memory, macOS 26.6.2. **No CUDA.**
All inference on MPS in float32, autocast off everywhere — MoGe's and
FoundationGeo's `use_fp16=True` defaults are explicitly overridden, because half
precision would put a stochastic floor under every delta S3–S6 tries to read.

## Vendored third-party code

`vendor/` and the venvs are gitignored — clone and download rather than commit.

```bash
cd experiments/week4_mono/vendor
git clone --depth 1 https://github.com/microsoft/MoGe.git moge                        # MIT
git clone --depth 1 https://github.com/metric-anything/metric-anything.git            # Apache-2.0
git clone --depth 1 https://github.com/DepthAnything/Depth-Anything-V2.git            # Apache-2.0
git clone --depth 1 https://github.com/ByteDance-Seed/Depth-Anything-3.git            # Apache-2.0
git clone --depth 1 https://github.com/mx-liu6/FoundationGeo.git                      # MIT
git clone --depth 1 https://github.com/princeton-vl/EvalMDE.git                       # metric only
```

MapAnything and Wat3R reuse the Week-3 clones unchanged.

### The two patches, and why they are the only ones

`patches/` holds the complete set. Neither touches weights, model structure or
any numerical path.

- **Depth Anything 3** — `requires-python` widened from `<=3.13` to `<3.14` so it
  installs on CPython 3.13.5; and the pycolmap-backed COLMAP **export** import
  made optional, because importing pycolmap alongside torch aborts on macOS with
  a duplicate libomp. The export path is never used here.
- **FoundationGeo** — a hard-coded `device='cuda'` moved to `'cpu'`. With
  `pretrained=False` it only chooses where *uninitialised* parameters are
  allocated; `from_pretrained` then overwrites every one of them through a strict
  `load_state_dict`, and the caller moves the model to its real device after.

Two deliberate NON-modifications are worth as much as the patches:

- **`moge` is put on `sys.path` explicitly, not pip-installed.** Both the
  MetricAnything release and upstream microsoft/MoGe ship a package literally
  named `moge`. An installed one would silently win, and V5 — the controlled
  MoGe-2 → MetricAnything comparison — would stop being controlled with no error
  anywhere. Both checkpoints load into the *same* class from the *same* tree.
- **FoundationGeo's `infer()` is not called.** It postprocesses its two
  ray-correction arms through *independent* `recover_focal_shift` solutions, so
  their difference is the ray correction *plus* two different focals. The
  backend calls `forward()` and applies one frozen solution to both arms, which
  is what FREEZE §C3 requires for the difference to be attributable to the ray
  delta.

## Layout

```
common.py         the frozen experiment definition: clips, models, venvs, paths
monoio.py         the per-model product on disk — NATIVE output plus a derived
                  canonical range, never a silent reduction to "depth"
evalgrid.py       the common evaluation grid, and how seven different output
                  grids reach it through MEASURED preprocessing maps
alignment.py      the E1 families, one per native representation
policy.py         the frozen S2 policy, made executable
armio.py          an "arm": one scoreable geometry field (FoundationGeo has four)
metrics_geom.py   M-1 .. M-6
perturb.py        the frozen S4 appearance perturbations, applied in linear light
restoration.py    the S6 range-driven restoration INSTRUMENT (not the project's)
backends/         one module per model; infer() takes ONE image path
scripts/          one per stage, plus the report generators
outputs/          gitignored: predictions, flow, perturbed frames, renders
results/          the stage deliverables (committed)
```

## Reproducing

```bash
REPO=$PWD
MONO=experiments/week4_mono/.venv-mono/bin/python
MOGE=experiments/week4_mono/.venv-moge/bin/python
EVAL=experiments/week4_mono/.venv-eval/bin/python
MAPA=experiments/week3_geometry/.venv-mapanything/bin/python
VGGT=experiments/week3_geometry/.venv-vggt/bin/python
FLOW=experiments/week2a_flow/.venv-flow/bin/python
export PYTHONPATH=$REPO

# 0. baseline safety and the frozen material
.venv/bin/python -m uw.cli score data/testset/murky/MURKYSHARK.MP4
.venv/bin/python -m pytest tests/
.venv/bin/python -m experiments.week4_mono.scripts.verify_frozen_set --hash

# S0 — one model per process, in its own venv
$MAPA -m experiments.week4_mono.scripts.s0_semantics --model mapanything_n1 --skip-cpu
$MONO -m experiments.week4_mono.scripts.s0_semantics --model dav2_small
$MOGE -m experiments.week4_mono.scripts.s0_semantics --model moge2_vitl
$MOGE -m experiments.week4_mono.scripts.s0_semantics --model metricanything_pointmap
$VGGT -m experiments.week4_mono.scripts.s0_semantics --model wat3r_n1 --skip-cpu
$MONO -m experiments.week4_mono.scripts.s0_semantics --model da3mono_large
$MONO -m experiments.week4_mono.scripts.s0_semantics --model foundationgeo_11
$MOGE -m experiments.week4_mono.scripts.s0_checkpoint_integrity
$EVAL -m experiments.week4_mono.scripts.s0_report --overwrite

# S1 — determinism and noise floor (same per-venv pattern)
$MONO -m experiments.week4_mono.scripts.s1_determinism --model dav2_small
...
$EVAL -m experiments.week4_mono.scripts.s1_report --overwrite

# the shared 288-frame inference pass
bash experiments/week4_mono/scripts/run_all_inference.sh --skip-existing

# S2 -> the frozen policy
$EVAL -m experiments.week4_mono.scripts.s2_ambiguity --overwrite
$EVAL -m experiments.week4_mono.scripts.s2_freeze_policy --overwrite

# S3 — the primary bakeoff
$EVAL -m experiments.week4_mono.scripts.s3_local_geometry --overwrite
$EVAL -m experiments.week4_mono.scripts.s3_report --overwrite

# S4 — survivors only
$EVAL -m experiments.week4_mono.scripts.s4_make_perturbations --overwrite
$MOGE -m experiments.week4_mono.scripts.s4_run --model moge2_vitl
$EVAL -m experiments.week4_mono.scripts.s4_analysis --overwrite
$EVAL -m experiments.week4_mono.scripts.s4_report --overwrite

# S5 — correspondence once per clip, then every arm
$FLOW -m experiments.week4_mono.scripts.s5_flow --skip-existing
$EVAL -m experiments.week4_mono.scripts.s5_temporal --overwrite
$EVAL -m experiments.week4_mono.scripts.s5_report --overwrite

# S6 — finalists only
$EVAL -m experiments.week4_mono.scripts.s6_restoration --arms <finalists> --sweep-water --overwrite
$FLOW -m experiments.week4_mono.scripts.s6_temporal --arms <finalists>
$EVAL -m experiments.week4_mono.scripts.s6_inspect --arms <finalists> --overwrite
$EVAL -m experiments.week4_mono.scripts.s6_report --overwrite
$EVAL -m experiments.week4_mono.scripts.finalists_report --overwrite
```

Every writer refuses to clobber an existing file unless `--overwrite` is passed
(`CLAUDE.md` invariant 7). `outputs/` is gitignored — the renders derive from
local dive footage and stay local, same rule as the footage.

## The invariant this whole directory is built around

**One frame in, one prediction out.** `MonoBackend.infer()` takes a single image
path; there is no batch, list or sequence argument to get it wrong with. The two
multi-view architectures assert it twice — MapAnything checks both that
`load_images` returned one view and that the model returned one prediction;
Wat3R asserts the preprocessed tensor has `S=1`. Sequence structure is used only
*after* inference, by the evaluation stages, and SEA-RAFT flow supplies
correspondence for evaluation only and never reaches a depth model.
