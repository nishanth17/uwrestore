#!/bin/bash
# Repeat runs for 3B-2, 3B-3 and 3B-4.
#
# Every Phase 3B claim is a difference between runs, and the project's standing
# rule (inherited from Phase 2A, where FlowIt was dropped for exactly this) is
# that a claimed effect must exceed the measured run-to-run spread. Phase 3A
# measured that spread only for configurations A, C_off and C_on. These four
# runs measure it for the new arms:
#
#   A_global / wreck_05  run1   the global mapper's own determinism
#   M_opencv / wreck_05  run1   the most flexible camera model, i.e. the arm
#                               most likely to wander between runs
#   A / wreck_05_S25     run1   a sparser schedule re-runs the WHOLE pipeline
#   A / wreck_05_S13     run1   (extraction + matching), so unlike the
#                               mapper-only arms it is not expected to be exact
set -u
cd "$(dirname "$0")/../../../.." || exit 1
PY=.venv/bin/python
P3B=experiments/week3_geometry/phase3b
OUT=$P3B/outputs/colmap
DB=$P3B/outputs/db
FRAMES=experiments/week3_geometry/outputs/frames
METHODS=$P3B/configs/phase3b_methods.json

echo "===== 3B extras: repeat runs $(date +%H:%M:%S) ====="

$PY -m experiments.week3_geometry.phase3b.scripts.run_mapper \
    --db "$DB/3b2_wreck_05_plain.db" --images "$FRAMES/wreck_05" \
    --out "$OUT/A_global/wreck_05/run1" --config-label A_global --clip wreck_05 \
    --repeat 1 --mapper global --hypothesis 3B-2 \
    --role "repeat: global mapper determinism floor" --overwrite || echo "  -> nonzero exit"

$PY -m experiments.week3_geometry.phase3b.scripts.run_mapper \
    --db "$DB/3b3_wreck_05_M_opencv.db" --images "$FRAMES/wreck_05" \
    --out "$OUT/M_opencv/wreck_05/run1" --config-label M_opencv --clip wreck_05 \
    --repeat 1 --mapper incremental --expect-camera-model OPENCV --hypothesis 3B-3 \
    --role "repeat: most flexible camera model, parameter stability" --overwrite \
    || echo "  -> nonzero exit"

for sched in S25 S13; do
  $PY -m experiments.week3_geometry.scripts.run_colmap \
      --config A --clip "wreck_05_${sched}" \
      --frames-root "$P3B/outputs/frames_schedules" \
      --methods "$METHODS" --out-root "$OUT" --repeat 1 --overwrite \
      || echo "  -> nonzero exit"
done

echo "===== 3B extras done $(date +%H:%M:%S) ====="
