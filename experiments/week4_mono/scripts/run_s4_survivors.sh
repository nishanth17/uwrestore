#!/bin/bash
# Week 4A — S4 appearance inference, S3 survivors only, one model per process.
#
# EXPLORATORY. Same rule as the main sweep: process exit is the authoritative
# MPS cleanup boundary, and these run strictly in series in each model's own venv.
set -u
cd "$(dirname "$0")/../../.."
REPO=$PWD
export PYTHONPATH=$REPO
MOGE=$REPO/experiments/week4_mono/.venv-moge/bin/python
MONO=$REPO/experiments/week4_mono/.venv-mono/bin/python
MAPA=$REPO/experiments/week3_geometry/.venv-mapanything/bin/python
VGGT=$REPO/experiments/week3_geometry/.venv-vggt/bin/python
ARGS="${*:-}"

run () {
  echo "=================== S4 $2  $(date +%H:%M:%S)"
  "$1" -u -m experiments.week4_mono.scripts.s4_run --model "$2" $ARGS
  echo "=================== S4 $2 exit=$? $(date +%H:%M:%S)"
}

run "$MAPA" mapanything_n1
run "$MONO" da3mono_large
run "$VGGT" wat3r_n1
run "$MOGE" metricanything_pointmap
echo "S4 ALL DONE $(date +%H:%M:%S)"
