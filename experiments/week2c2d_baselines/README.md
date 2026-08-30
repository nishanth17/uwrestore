# Week 2 Phase 2C/2D — baseline comparison (exploratory scaffolding)

The baselines, diagnostics, pipeline plumbing, and flow-reuse mechanism are
all **permanent project code** and live in `uw/`:

| file | what |
|---|---|
| `uw/baselines.py` | `gray_world` (Week 1) + `white_patch`, `clahe` (this phase) |
| `uw/colorspace.py` | gained `y_to_lstar` / `lstar_to_y`, CLAHE's perceptual-lightness pathway |
| `uw/diagnostics.py` | signal-recoverability diagnostics: near-floor/saturation fractions, gain lookup, out-of-range fraction — NOT SNR/noise |
| `uw/flow.py` | gained `CachingFlowBackend`, the reuse mechanism for scoring several correction configurations without repeating flow inference |
| `uw/cli.py` | `--pipeline`, `--no-<stage>` ablations, `--method` backward compat, the pipeline/diagnostics/gains report |
| `tests/test_baselines.py`, `tests/test_diagnostics.py`, `tests/test_pipeline.py` | 60 new tests, ordinary venv, no torch |
| `tests/test_flow.py` | +7 tests for `CachingFlowBackend` |

**This directory is the disposable part**: the script that runs a bounded
set of correction configurations against the frozen footage and writes
diagnostics. Nothing under `uw/` imports anything from here.

## Running it

Needs the isolated flow interpreter (torch), same as Phase 2A/2B:

```bash
FV=experiments/week2a_flow/.venv-flow/bin/python

$FV experiments/week2c2d_baselines/scripts/run_baseline_eval.py \
    --json outputs/week2c2d_baselines/results.json
```

`--clip NAME` (repeatable) restricts to specific clips; `--no-verify` skips
the one-time equivalence check against the non-cached evaluation path
(costs one extra clip's worth of inference, on by default).

Six configurations are evaluated per clip: `none`, `gray_world`,
`white_patch`, `clahe`, `gray_world→clahe`, `white_patch→clahe` — see
CLAUDE.md's Phase 2C/2D brief §24 for why this set and not a sweep.

Uses **Phase 2B's exact excerpt geometry** (same clip, same start index,
same 41-frame window, same anchors 16/18/20, same 960-long-side grid) so
these numbers sit directly beside the Phase 2B table in `LOG.md`.

## Full write-up

`LOG.md`'s 2026-08-29 Phase 2C/2D entry has the full results, including two
real bugs found by actually running this script rather than by reasoning
about the code: an argparse default that made a bare `--pipeline` look
like an ambiguous `--method`+`--pipeline`, and a cache-key strategy that
missed on every call because `uw.metrics.evaluate_temporal` rewraps its
`original` argument in a new list on every call. `outputs/week2c2d_baselines/
results.json` (gitignored) has every number.
