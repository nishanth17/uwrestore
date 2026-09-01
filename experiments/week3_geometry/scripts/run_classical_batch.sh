#!/bin/bash
# Stage 3 driver — every classical-arm configuration over the whole Phase 3A
# subset, in a fixed order, one process per (config, clip, repeat).
#
# Deliberately NOT parallel across configurations: runtime and peak memory are
# reported numbers, and running four COLMAP processes on ten cores would make
# them meaningless.
set -u
PY=.venv/bin/python
CLIPS="wreck_07 wreck_05 cenote_01 swimthrough_02 wreck_01 wreck_03"
run () {  # config clip repeat [extra...]
  echo "=== $1 $2 run$3 $(date +%H:%M:%S) ==="
  $PY -m experiments.week3_geometry.scripts.run_colmap \
      --config "$1" --clip "$2" --repeat "$3" "${@:4}" || echo "  -> nonzero exit"
}
for clip in $CLIPS; do
  for cfg in A C_off C_on; do run "$cfg" "$clip" 0 --overwrite; done
done
for clip in $CLIPS; do run B "$clip" 0 --overwrite; done
# Repeat-run spread. C_on/C_off carry the whole refraction claim, so they get
# the most repeats; A is the control for "is COLMAP itself reproducible here".
for clip in wreck_07 wreck_05; do
  for r in 1 2; do
    for cfg in C_off C_on; do run "$cfg" "$clip" "$r" --overwrite; done
  done
  run A "$clip" 1 --overwrite
done
echo "=== classical batch done $(date +%H:%M:%S) ==="
