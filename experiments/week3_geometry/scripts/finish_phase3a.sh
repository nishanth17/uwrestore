#!/bin/bash
# Phase 3A tail: wait for the two predeclared batches, then close everything out.
#
# Order matters. Re-runs come BEFORE the diagnostics and the comparison, because
# a comparison built on a run that died mid-stage would silently mix "the method
# failed" with "the process was killed" -- the distinction check_completeness.py
# exists to preserve.
set -u
cd /Users/nishanthmohan/code/uwrestore
PY=.venv/bin/python
W3=experiments/week3_geometry

echo "=== waiting for the predeclared batches $(date +%H:%M:%S) ==="
while pgrep -qf "run_classical_batch.sh" || pgrep -qf "run_learned_batch.sh"; do sleep 120; done
echo "=== batches finished $(date +%H:%M:%S) ==="

echo "=== gap analysis ==="
$PY -m experiments.week3_geometry.scripts.check_completeness \
    --rerun-script $W3/outputs/rerun_gaps.sh || true
if [ -f $W3/outputs/rerun_gaps.sh ]; then
  echo "=== re-running gaps $(date +%H:%M:%S) ==="
  bash $W3/outputs/rerun_gaps.sh
fi

echo "=== refraction diagnostics $(date +%H:%M:%S) ==="
bash $W3/scripts/run_refraction_diagnostics.sh

echo "=== final completeness $(date +%H:%M:%S) ==="
$PY -m experiments.week3_geometry.scripts.check_completeness || true

echo "=== stage 6 comparison $(date +%H:%M:%S) ==="
$PY -m experiments.week3_geometry.scripts.compare \
    --out $W3/outputs/stage6/comparison.json --overwrite

echo "=== diagnostics images $(date +%H:%M:%S) ==="
$PY -m experiments.week3_geometry.scripts.visualize --overwrite || true

echo "=== PHASE 3A TAIL COMPLETE $(date +%H:%M:%S) ==="
