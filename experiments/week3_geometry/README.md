# Week 3 Phase 3A — multi-view geometry bakeoff

**This directory is not part of the `uwrestore` package.** It is scaffolding for
one comparison session: which geometry approach can supply range whose *spatial
shape* is trustworthy enough for later backscatter removal and attenuation
inversion. Nothing under `uw/` imports anything here, none of it is installed,
and none of it is a project dependency. If a geometry path is selected it gets
promoted deliberately — the way `uw/flow.py` was in Phase 2B — not by accident.

The authoritative report is [`FINDINGS.md`](FINDINGS.md). The research note that
froze the candidate set is [`GEOMETRY_LANDSCAPE.md`](GEOMETRY_LANDSCAPE.md).

## Dependency exception

`CLAUDE.md` invariant 8 says lightweight dependencies by default. Evaluating
pretrained geometry models needs PyTorch and research-repo code, so this phase
is a scoped exception, scoped the same way Phase 2A was: the heavy stacks live
in venvs *inside this directory*, `pyproject.toml` is untouched, and the main
project venv still has only numpy + opencv. Everything that could become
permanent — the geometry conventions in `geometry.py`, the range product format
in `rangeio.py` — runs in the main venv and is tested in `tests/test_week3_geometry.py`.

## Environments

| | main `.venv` | `.venv-mapanything` | `.venv-vggt` |
|---|---|---|---|
| Python | 3.14 | 3.13 | 3.13 |
| holds | numpy, opencv | torch 2.13 (MPS), mapanything 1.1.4 | torch 2.13 (MPS) |
| runs | Stage 1, 2, 6, 7, diagnostics, COLMAP drivers | configuration D | configurations E0 and E |

```bash
python3.13 -m venv experiments/week3_geometry/.venv-mapanything
experiments/week3_geometry/.venv-mapanything/bin/pip install torch torchvision numpy
experiments/week3_geometry/.venv-mapanything/bin/pip install -e experiments/week3_geometry/vendor/map-anything

python3.13 -m venv experiments/week3_geometry/.venv-vggt
experiments/week3_geometry/.venv-vggt/bin/pip install torch torchvision numpy Pillow \
    huggingface_hub einops safetensors opencv-python-headless
```

Hardware: Apple M4, 10 cores, 24 GB unified memory, macOS 26.6.2. No CUDA.
All learned inference on MPS in float32 — MPS has no bf16 autocast path, and
the project's standing rule is that a measurement instrument must be
reproducible before it is fast. **One model per process**; process exit is the
authoritative MPS cleanup boundary.

## Vendored third-party code

`vendor/` and the venvs are gitignored — clone and download rather than commit.
Exact commits and licences are in `FINDINGS.md` §2.

```bash
cd experiments/week3_geometry/vendor
git clone --depth 1 https://github.com/the-sauer/colmap_underwater.git     # BSD (COLMAP)
git clone --depth 1 https://github.com/facebookresearch/map-anything.git   # Apache-2.0
git clone --depth 1 https://github.com/facebookresearch/vggt.git           # VGGT License v1
git clone --depth 1 https://github.com/LSXI7/Wat3R.git                     # Apache-2.0
git clone --depth 1 https://github.com/colmap/gluemap.git                  # BSD-3 (not runnable here)
git clone --depth 1 https://github.com/HengyiWang/amb3r.git                # NO LICENSE FILE (not runnable here)
```

Mainline COLMAP is the Homebrew build (`colmap 4.1.1_3`), which already has
ONNX Runtime linked, so configuration B needed no source build.

`colmap_underwater` **does** need a source build and it is the one place a
vendored file was edited. Two files in its bundled PoissonRecon mesher —
code Phase 3A never invokes — fail to compile under current clang because of
genuine upstream bugs (`p.value` on a member that does not exist; `m_N`/`m_M` on
a class whose members are `rows`/`_maxEntriesPerRow`). The three-line fix is
committed as `configs/colmap_underwater_poissonrecon_build_fix.patch`:

```bash
cd experiments/week3_geometry/vendor/colmap_underwater
git apply ../../configs/colmap_underwater_poissonrecon_build_fix.patch
cmake -S . -B build -GNinja -DCMAKE_BUILD_TYPE=Release \
      -DGUI_ENABLED=OFF -DCUDA_ENABLED=OFF -DTESTS_ENABLED=OFF
ninja -C build colmap_main          # -> build/src/colmap/exe/colmap, "COLMAP 3.10-dev"
```

## Layout

```
configs/phase3a_clips.json        the six selected clips + frame ranges. FIXED
                                  BEFORE any geometry method was run.
configs/phase3a_methods.json      A / B / C_off / C_on, and the flat-port params
configs/amb3r_provenance.json     configuration G, inspected but pending_cuda
geometry.py                       coordinate/pose/range conventions and the
                                  conversions, all unit-tested
rangeio.py                        the per-clip range product on disk
scripts/inspect_clips.py          Stage 1 mechanical inspection
scripts/contact_sheet.py          Stage 1 sparse visual triage
scripts/extract_frames.py         the ONE shared frame set every config consumes
scripts/calibrate_preprocess.py   MEASURES each model's source->grid mapping
scripts/run_colmap.py             configurations A, B, C_off, C_on
scripts/run_mapanything.py        configuration D
scripts/run_vggt_family.py        configurations E0 and E (one model per process)
scripts/run_classical_batch.sh    Stage 3 driver
scripts/run_learned_batch.sh      Stage 4 driver
scripts/compare.py                Stage 6 cross-family comparison
scripts/restoration_sensitivity.py Stage 7 error budget
scripts/visualize.py              range/confidence/difference/trajectory images
outputs/                          gitignored: frames, reconstructions, range
                                  products, diagnostics
```

## Reproducing

```bash
PY=.venv/bin/python
$PY -m experiments.week3_geometry.scripts.inspect_clips \
      --out experiments/week3_geometry/outputs/stage1/clip_inspection.json
$PY -m experiments.week3_geometry.scripts.extract_frames \
      --spec experiments/week3_geometry/configs/phase3a_clips.json \
      --out-root experiments/week3_geometry/outputs/frames

experiments/week3_geometry/.venv-mapanything/bin/python \
      -m experiments.week3_geometry.scripts.calibrate_preprocess --family mapanything
for f in vggt wat3r; do experiments/week3_geometry/.venv-vggt/bin/python \
      -m experiments.week3_geometry.scripts.calibrate_preprocess --family $f; done

bash experiments/week3_geometry/scripts/run_classical_batch.sh
bash experiments/week3_geometry/scripts/run_learned_batch.sh

$PY -m experiments.week3_geometry.scripts.compare \
      --out experiments/week3_geometry/outputs/stage6/comparison.json
$PY -m experiments.week3_geometry.scripts.restoration_sensitivity \
      --out experiments/week3_geometry/outputs/stage7/sensitivity.json
$PY -m experiments.week3_geometry.scripts.visualize
$PY -m pytest tests/test_week3_geometry.py
```

Every writer refuses to clobber an existing file unless `--overwrite` is passed
(`CLAUDE.md` invariant 7). `outputs/` is gitignored — the renders derive from
local dive footage and stay local, same rule as the footage.

## The one thing to know before reading any number

There is **no independent range measurement** anywhere in this phase. The C2
scale-and-range acquisition `PLAN.md` specifies does not exist yet. So every
cross-method figure here is a **consistency** statement, never a correctness
one, and nothing in this directory is ground truth — least of all sparse SfM,
which is itself one of the candidates under test.
