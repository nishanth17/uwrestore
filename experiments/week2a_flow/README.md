# Week 2 Phase 1A — optical-flow backend bakeoff (exploratory)

> **Update (Phase 2B).** Two of the four wrappers this directory created were
> **promoted into the package** and their copies here deleted, so there is one
> definition of each rather than two that can drift:
>
> * `backends/searaft_backend.py` -> **`uw/searaft.py`** (canonical backend)
> * `backends/waft_backend.py` -> **`uw/waft.py`** (optional manual cross-check)
>
> `backends/flowit_backend.py` was **deleted outright**: FlowIt was dropped on
> reproducibility (§5) and the lag study removed the last reason to revisit
> that (§A8). Its vendored checkout and 345 MB checkpoint are still on disk and
> can be removed; the download commands below reinstate them if ever needed.
>
> `backends/videoflow_backend.py` (**MOF**) stays. It is the only backend that
> flagged the `distance` bubble column, which is a named future use, and it
> still runs in its own `.venv-videoflow`.
>
> **Every script here still works and every number below is still
> reproducible** — `build_backend()` now constructs the promoted classes, which
> are byte-identical in behaviour (verified: `np.array_equal` on the returned
> flow, max abs diff 0.0), and the aggregation scripts skip any backend whose
> output directory is absent. `common.model_input_srgb_u8` is now a re-export
> of `uw.flow.model_input_srgb_u8`.
>
> One thing changed that this session could not have known: SEA-RAFT and WAFT
> both ship top-level `config/`, `model/` and `utils/` packages, so importing
> both in one process made the second fail. Phase 1A never hit it because it
> ran one backend per process. The promoted wrappers import through
> `uw.flow.isolated_repo_imports`, which is what lets `uw crosscheck` hold both
> at once.

**This directory is not part of the `uwrestore` package.** It is scaffolding
for one comparison session: which optical-flow backend is trustworthy enough
on *our* footage to later underpin a temporal-stability metric. Nothing under
`uw/` imports anything from here, nothing here is installed, and none of it is
a project dependency. If a backend is chosen in Phase 1B, only that one
becomes a normal dependency — the rest of this tree can be deleted.

The one permanent artifact of this session is `uw/flow.py`: the abstraction,
the coordinate convention, and the model-independent flow maths (resize with
vector rescaling, warping, forward/backward consistency). It contains no
backend and no default. Tests for it live in `tests/test_flow.py` and run in
the normal project venv.

## Dependency exception

CLAUDE.md invariant 8 says lightweight dependencies by default. Evaluating
pretrained flow models needs PyTorch and research-repo code, so this phase is
a scoped exception. It is scoped in the strongest available sense: the heavy
stacks live in venvs *inside this directory*, `pyproject.toml` is untouched,
and the main project venv still has only numpy + opencv.

## Environments

Two isolated interpreters, because VideoFlow needs `timm==0.4.12` and the
others do not, and because SEA-RAFT, WAFT, FlowIt and VideoFlow each ship a
flat top-level `core/`/`model/`/`utils/` that would collide in one process.
Every backend therefore also runs in its own process.

| | `.venv-flow` | `.venv-videoflow` |
|---|---|---|
| Python | 3.13.5 | 3.13.5 |
| torch | 2.13.0 (MPS) | 2.13.0 (MPS) |
| extra | torchvision, huggingface-hub, gdown, einops, timm (current), opencv, scipy, matplotlib | yacs, loguru, einops, **timm==0.4.12**, imageio, opencv, scipy, matplotlib |
| backends | SEA-RAFT, WAFT (both now imported from `uw/`) | VideoFlow-MOF |

Hardware: Apple M4, 10 cores, 24 GB unified memory, macOS 26.6. No CUDA
anywhere; all inference on MPS.

Recreate with:

```bash
python3.13 -m venv experiments/week2a_flow/.venv-flow
experiments/week2a_flow/.venv-flow/bin/pip install torch torchvision numpy \
    opencv-python-headless huggingface-hub gdown einops timm scipy matplotlib imageio

python3.13 -m venv experiments/week2a_flow/.venv-videoflow
experiments/week2a_flow/.venv-videoflow/bin/pip install torch torchvision numpy \
    opencv-python-headless matplotlib scipy yacs loguru einops timm==0.4.12 imageio
```

## Vendored third-party code and checkpoints

`vendor/` and `checkpoints/` are gitignored — clone and download rather than
commit. **No vendored source file was edited.** Where a backend needed
different behaviour it was through a config value or at the call site in the
wrapper, and each wrapper's module docstring lists exactly what and why.

```bash
cd experiments/week2a_flow/vendor
git clone --depth 1 https://github.com/princeton-vl/SEA-RAFT.git   # BSD-3-Clause
git clone --depth 1 https://github.com/princeton-vl/WAFT.git       # BSD-3-Clause
git clone --depth 1 https://github.com/sadrasafa/FlowIt.git        # see its LICENSE/NOTICE.md
git clone --depth 1 https://github.com/XiaoyuShi97/VideoFlow.git   # Apache-2.0
```

WAFT additionally needs its documented DepthAnythingV2 prerequisite, which
its model constructor reads from a repo-relative path:

```bash
# -> vendor/WAFT/depth-anything-ckpts/depth_anything_v2_vits.pth  (95 MB)
huggingface-cli download depth-anything/Depth-Anything-V2-Small depth_anything_v2_vits.pth
```

`xformers`, which WAFT's README also asks for, is **not** installed and is
not needed: it is reached only inside the vendored DepthAnythingV2 DINOv2
layers, behind a `try/except ImportError` with a pure-PyTorch fallback.

Checkpoints:

* SEA-RAFT — pulled automatically from HuggingFace
  (`MemorySlices/Tartan-C-T-TSKH-spring540x960-M`) by the wrapper.
* WAFT — `gdown 1CxzBQx0iSg6AyIgt6MF0ROlF_cAeZLPC` into
  `checkpoints/waft/` (`tar-c-t.pth`, 245 MB), the file the README
  recommends "for downstream applications".
* FlowIt — `gdown --folder <authors' Drive folder>` into
  `checkpoints/flowit/C-T-TSKH/`. The folder contains S/M/L/XL; **only
  `C-T-TSKH_Flowit-M.pth` (345 MB) is kept.** XL is 1.8 GB and does not fit
  this machine's working set, and the larger variants would not help anyway —
  FlowIt's memory is dominated by its global cost volume (quadratic in pixel
  count), not by model size. The wrapper raises a clear `FileNotFoundError`
  naming the re-download path if another size is requested.
* VideoFlow — `gdown --folder <authors' Drive folder>` into
  `checkpoints/videoflow/`. The folder contains BOF and MOF checkpoints for
  things/sintel/kitti; **only `MOF_sintel.pth` (52 MB) is kept** — it is what
  `configs/multiframes_sintel_submission.py` points at, and BOF is the
  3-frame variant this bakeoff is not testing.

Total kept: **405 MB**, down from 6.7 GB as downloaded.

## Layout

```
common.py                 excerpt loading, linear->sRGB model-input view,
                          visualisation, quantitative diagnostics
backends/                 videoflow only — searaft and waft were promoted to
                          uw/ and flowit deleted (see the note at the top)
scripts/survey_motion.py  picks the excerpts (Farneback proxy, not a candidate)
scripts/synthetic_check.py known-motion wrapper-correctness test
scripts/determinism_check.py repeat-call reproducibility check
scripts/run_bakeoff.py    one backend over all excerpts -> outputs/
scripts/contact_sheets.py cross-backend comparison sheets
excerpts.json             the selected clips/frames (committed: it is the
                          experiment definition, not footage)
FINDINGS.md               the Phase 1A writeup
```

## Reproducing

```bash
FV=experiments/week2a_flow/.venv-flow/bin/python
VV=experiments/week2a_flow/.venv-videoflow/bin/python

$FV -m experiments.week2a_flow.scripts.survey_motion            # writes excerpts.json
for b in searaft waft; do   # both now come from uw/, not from backends/
  $FV -m experiments.week2a_flow.scripts.synthetic_check --backend $b \
      --report outputs/flow_comparison/$b/synthetic_check.json
  $FV -m experiments.week2a_flow.scripts.run_bakeoff --backend $b
done
$VV -m experiments.week2a_flow.scripts.synthetic_check --backend videoflow_mof \
    --report outputs/flow_comparison/videoflow_mof/synthetic_check.json
$VV -m experiments.week2a_flow.scripts.run_bakeoff --backend videoflow_mof

$FV -m experiments.week2a_flow.scripts.contact_sheets
$FV -m experiments.week2a_flow.scripts.aggregate --out outputs/flow_comparison/comparison.md
$FV -m experiments.week2a_flow.scripts.disagreement
for b in searaft waft; do
  $FV -m experiments.week2a_flow.scripts.determinism_check --backend $b --repeats 3
done
$VV -m experiments.week2a_flow.scripts.determinism_check --backend videoflow_mof --repeats 3
```

Every writer refuses to clobber an existing file unless `--overwrite` is
passed (CLAUDE.md invariant 7). Diagnostics land in
`outputs/flow_comparison/`, which is gitignored — the renders are derived
from local dive footage and stay local, same rule as the footage.
