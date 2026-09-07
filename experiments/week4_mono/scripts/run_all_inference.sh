#!/bin/bash
# Week 4A — the shared 288-frame inference pass, one model per process.
#
# EXPLORATORY. ONE MODEL PER PROCESS is not a convenience here: process exit is
# the authoritative MPS cleanup boundary (the Week-3 rule), and two of these
# models peak above 9 GB on a 24 GB machine. They therefore run strictly in
# series, in the freeze's integration order, each in its own venv.
set -u
cd "$(dirname "$0")/../../.."
REPO=$PWD
export PYTHONPATH=$REPO
MONO=$REPO/experiments/week4_mono/.venv-mono/bin/python
MOGE=$REPO/experiments/week4_mono/.venv-moge/bin/python
MAPA=$REPO/experiments/week3_geometry/.venv-mapanything/bin/python
VGGT=$REPO/experiments/week3_geometry/.venv-vggt/bin/python
ARGS="${*:-}"

run () {  # run <python> <model>
  echo "=================== $2  $(date +%H:%M:%S)"
  "$1" -m experiments.week4_mono.scripts.run_inference --model "$2" $ARGS
  echo "=================== $2 exit=$? $(date +%H:%M:%S)"
}

run "$MAPA" mapanything_n1
run "$MONO" dav2_small
run "$MOGE" moge2_vitl
run "$MOGE" metricanything_pointmap
run "$VGGT" wat3r_n1
run "$MONO" da3mono_large
run "$MONO" foundationgeo_11
echo "ALL DONE $(date +%H:%M:%S)"
