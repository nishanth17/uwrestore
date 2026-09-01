#!/bin/bash
# Stage 4 driver — the learned arm over the whole Phase 3A subset.
#
# ONE MODEL PER PROCESS, strictly sequential: process exit is the authoritative
# MPS cleanup boundary (CLAUDE.md invariant 9 / the Phase 3A Apple Silicon rule),
# and two heavyweight models are never resident at once. Sequential also keeps
# the reported runtime and peak-memory numbers meaningful.
set -u
MA=experiments/week3_geometry/.venv-mapanything/bin/python
VG=experiments/week3_geometry/.venv-vggt/bin/python
CLIPS="wreck_07 wreck_05 cenote_01 swimthrough_02 wreck_01 wreck_03"

for clip in $CLIPS; do
  echo "=== D mapanything $clip $(date +%H:%M:%S) ==="
  $MA -m experiments.week3_geometry.scripts.run_mapanything --clip "$clip" --overwrite \
    || echo "  -> nonzero exit"
done
for model in vggt wat3r; do
  for clip in $CLIPS; do
    echo "=== $model $clip $(date +%H:%M:%S) ==="
    $VG -m experiments.week3_geometry.scripts.run_vggt_family --model "$model" \
        --clip "$clip" --overwrite || echo "  -> nonzero exit"
  done
done
# Repeat runs: determinism of a learned instrument is a standing project
# requirement (FlowIt was dropped in Phase 2A for failing exactly this).
for m in vggt wat3r; do
  echo "=== repeat $m wreck_07 $(date +%H:%M:%S) ==="
  $VG -m experiments.week3_geometry.scripts.run_vggt_family --model "$m" \
      --clip wreck_07 --repeat 1 --overwrite || echo "  -> nonzero exit"
done
echo "=== D repeat wreck_07 $(date +%H:%M:%S) ==="
$MA -m experiments.week3_geometry.scripts.run_mapanything --clip wreck_07 --repeat 1 --overwrite \
  || echo "  -> nonzero exit"
echo "=== learned batch done $(date +%H:%M:%S) ==="
