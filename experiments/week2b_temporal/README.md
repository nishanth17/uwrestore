# Week 2 Phase 2B — motion-aware temporal metric (exploratory scaffolding)

The metric itself is **permanent project code** and lives in `uw/`:

| file | what |
|---|---|
| `uw/metrics.py` | the temporal metrics: `temporal_warp_error`, `fit_illumination`, `temporal_delta_e`, `evaluate_temporal_pair`, `evaluate_temporal`, and the `TemporalLagMetrics` / `TemporalMetrics` / `IlluminationFit` results. numpy + opencv only; **no flow model is imported here** |
| `uw/searaft.py` | the canonical SEA-RAFT-M backend behind `uw.flow.OpticalFlowBackend`; imports torch lazily |
| `uw/waft.py` | WAFT-a1, the optional **manual cross-check**. Never a default, never run automatically, never averaged with SEA-RAFT; imports torch lazily |
| `uw/flow.py` | gained the shared `model_input_srgb_u8` view and `isolated_repo_imports`, which is what lets two research repos with colliding top-level packages share a process |
| `uw/cli.py` | `uw score --temporal`, and `uw crosscheck` (two backends on a common mask) |
| `tests/test_temporal.py` | 52 synthetic validation tests, run in the ordinary venv against an analytic flow backend |
| `tests/test_backends.py` | 16 tests of the wrappers' plumbing — lazy torch, missing-checkout errors, padding arithmetic, import isolation, CLI defaults |

**This directory is the disposable part**: run scripts that point the metric
at the frozen footage and write diagnostics. Nothing under `uw/` imports
anything from here.

## Environment

The metric needs only numpy + opencv, so `uw score` without `--temporal`,
and the whole test suite, run in the ordinary `.venv`. SEA-RAFT needs torch,
which is deliberately **not** a project dependency — `pyproject.toml` is
unchanged. Temporal scoring runs from the isolated Phase 2A interpreter,
which already has numpy, opencv and torch:

```bash
FV=experiments/week2a_flow/.venv-flow/bin/python

$FV -m uw.cli score data/testset/swimthrough/SWIMTHROUGH.MP4 \
    --temporal --start 181 --frames 41 --anchors 16,18,20 --alignment-robust
```

## Using WAFT as a second opinion

`uw/waft.py` exists for the case PLAN.md names: *"where the two disagree
materially, treat that clip's MC-Warp as low-confidence."* It is never a
default and never runs during normal scoring.

The **only** sanctioned way to compare the two is on the intersection of their
validity masks. Scoring each on its own mask measures masking policy, not
correspondence quality — WAFT masks less than SEA-RAFT nearly everywhere, so
it would flatter whichever one excludes more of the hard region:

```bash
$FV -m uw.cli crosscheck data/testset/murky/MURKYSHARK.MP4 \
    --start 0 --frames 41 --anchors 16,18,20
```

`uw score --temporal --flow-backend waft` also works, and prints a warning
saying its numbers are not comparable value-for-value to a SEA-RAFT run.
Because SEA-RAFT and WAFT ship colliding top-level `config/`, `model/` and
`utils/` packages, both wrappers import through `uw.flow.isolated_repo_imports`
— without it, whichever is constructed second fails with
`cannot import name 'Padder' from 'utils.utils'`.

`python -m` puts the repo root on `sys.path`, so the normal CLI runs there
unmodified. The SEA-RAFT checkout is found at
`experiments/week2a_flow/vendor/SEA-RAFT` (see Phase 2A's README for how to
clone it) or wherever `UW_SEARAFT_DIR` points; the checkpoint is pulled from
HuggingFace by the wrapper.

## Reproducing this phase

```bash
PV=.venv/bin/python                              # ordinary project venv
FV=experiments/week2a_flow/.venv-flow/bin/python # torch

$PV -m pytest tests/ -q                                     # 176 tests
$PV -m experiments.week2b_temporal.scripts.alignment_study   # no torch needed
$FV -m experiments.week2b_temporal.scripts.searaft_check
$FV -m experiments.week2b_temporal.scripts.run_temporal_eval --method none
$FV -m experiments.week2b_temporal.scripts.run_temporal_eval --method gray_world
$FV -m experiments.week2b_temporal.scripts.lights_falsification
$FV -m experiments.week2b_temporal.scripts.stability_check
```

Every writer refuses to clobber an existing file without `--overwrite`
(CLAUDE.md invariant 7). Diagnostics land in `outputs/temporal_metric/`,
which is gitignored — the renders derive from local dive footage and stay
local, same rule as the footage.

## Layout

```
scripts/alignment_study.py       sub-pixel resampling floor of MC-Warp (no model)
scripts/searaft_check.py         known-motion check of the PROMOTED wrapper
scripts/run_temporal_eval.py     the frozen test set, at Phase 2A's frame ranges
scripts/lights_falsification.py  how much corrected-only flicker survives the
                                 illumination confound on `lights`
scripts/stability_check.py       does the metric stay put? repeatability and
                                 anchor-set spread (the metric's error bar)
FINDINGS.md                      the Phase 2B writeup
```
