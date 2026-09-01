#!/bin/bash
# 3B-2, 3B-3 and 3B-4 -- the three cheap classical experiments, in order.
#
# Sequential on purpose: runtime and peak memory are reported numbers, and
# running several COLMAP processes on ten cores would make them meaningless.
#
# Nothing here re-extracts frames or re-matches features. 3B-2 and 3B-3 start at
# the mapper on a COPY of the Phase 3A database; 3B-4 re-runs configuration A on
# symlinked subsets of the identical extracted PNGs. Phase 3A outputs are never
# mutated.
set -u
cd "$(dirname "$0")/../../../.." || exit 1
PY=.venv/bin/python
P3B=experiments/week3_geometry/phase3b
A_ROOT=experiments/week3_geometry/outputs/colmap/A
FRAMES=experiments/week3_geometry/outputs/frames
DB=$P3B/outputs/db
OUT=$P3B/outputs/colmap
METHODS=$P3B/configs/phase3b_methods.json

prep () {  # dst-name src-run [extra prep args...]
  $PY -m experiments.week3_geometry.phase3b.scripts.prep_db \
      --src-run "$2" --dst "$DB/$1.db" --overwrite "${@:3}" || echo "  -> prep failed"
}
map () {  # db-name images out-subpath label clip [extra run_mapper args...]
  echo "--- $4 / $5 $(date +%H:%M:%S)"
  $PY -m experiments.week3_geometry.phase3b.scripts.run_mapper \
      --db "$DB/$1.db" --images "$2" --out "$OUT/$3" \
      --config-label "$4" --clip "$5" --overwrite "${@:6}" || echo "  -> nonzero exit"
}

# =====================================================================
# 3B-2  incremental vs global SfM, on the SAME SIFT measurements
# =====================================================================
echo "===== 3B-2 global mapper $(date +%H:%M:%S) ====="
for clip in wreck_05 wreck_01 wreck_03 swimthrough_02; do
  prep "3b2_${clip}_plain"      "$A_ROOT/$clip/run0"
  prep "3b2_${clip}_cal"        "$A_ROOT/$clip/run0"
  map "3b2_${clip}_plain" "$FRAMES/$clip" "A_global/$clip/run0" A_global "$clip" \
      --mapper global --hypothesis 3B-2 \
      --role "global SfM on Phase 3A configuration A's own database"
  map "3b2_${clip}_cal" "$FRAMES/$clip" "A_global_cal/$clip/run0" A_global_cal "$clip" \
      --mapper global --calibrate-view-graph --hypothesis 3B-2 \
      --role "view_graph_calibrator then global SfM -- a SEPARATE intervention, so a focal change is not reported as a mapper effect"
done

# =====================================================================
# 3B-3  camera-model / self-calibration sensitivity
#       Same database, same mapper, same seed. Only the cameras row differs.
# =====================================================================
echo "===== 3B-3 camera models $(date +%H:%M:%S) ====="
for clip in wreck_07 wreck_05 swimthrough_02 wreck_01; do
  # M_simple_radial is the CONTROL: it must reproduce Phase 3A configuration A.
  # If it does not, every other arm on this database is void.
  for spec in "M_simple_radial:SIMPLE_RADIAL" "M_radial:RADIAL" \
              "M_opencv:OPENCV" "M_simple_radial_fisheye:SIMPLE_RADIAL_FISHEYE"; do
    label=${spec%%:*}; model=${spec#*:}
    prep "3b3_${clip}_${label}" "$A_ROOT/$clip/run0" --camera-model "$model"
    map "3b3_${clip}_${label}" "$FRAMES/$clip" "$label/$clip/run0" "$label" "$clip" \
        --mapper incremental --expect-camera-model "$model" --hypothesis 3B-3 \
        --role "central camera model $model on Phase 3A configuration A's own measurements"
  done
done

# Determinism check for the mapper-only path: with an identical database, one
# mapping thread and a fixed seed, a repeat should be identical. Cheap, and it
# tells 3B-2 and 3B-3 what their noise floor actually is.
echo "===== 3B-3 mapper-only repeat $(date +%H:%M:%S) ====="
map "3b3_wreck_05_M_simple_radial" "$FRAMES/wreck_05" "M_simple_radial/wreck_05/run1" \
    M_simple_radial wreck_05 --repeat 1 --mapper incremental \
    --expect-camera-model SIMPLE_RADIAL --hypothesis 3B-3 \
    --role "repeat of the control arm: mapper-only determinism floor"

# Optional fixed-intrinsics diagnostic. Justified ONLY because the capture
# metadata shows wreck_07/wreck_05/wreck_01 share body serial, lens serial,
# firmware, FOV setting, effective ZFOV, digital-zoom state and stabilisation
# mode. wreck_01 is the same optics rotated, so the focal transfers in pixels
# and only the principal point swaps. Diagnostic only -- it cannot establish
# that either focal is physically correct.
echo "===== 3B-3 fixed intrinsics $(date +%H:%M:%S) ====="
REF=$($PY - <<'EOF'
import json
r = json.load(open("experiments/week3_geometry/outputs/colmap/A/wreck_07/run0/run.json"))
cam = next(iter(r["result"]["cameras"].values()))
f, cx, cy, k = cam["params"]
print(f"{f},{cx},{cy},{k}")
EOF
)
F=$(echo "$REF" | cut -d, -f1); K=$(echo "$REF" | cut -d, -f4)
echo "  reference intrinsics from A/wreck_07: f=$F k=$K"
prep "3b3_wreck_05_fixed" "$A_ROOT/wreck_05/run0" \
     --camera-model SIMPLE_RADIAL --params "$F,640.0,360.0,$K" --mark-prior-focal
map "3b3_wreck_05_fixed" "$FRAMES/wreck_05" "M_fixed_from_wreck07/wreck_05/run0" \
    M_fixed_from_wreck07 wreck_05 --mapper incremental --fix-intrinsics \
    --expect-camera-model SIMPLE_RADIAL --hypothesis 3B-3 \
    --role "intrinsics FIXED to wreck_07's self-calibrated values -- diagnostic only"
prep "3b3_wreck_01_fixed" "$A_ROOT/wreck_01/run0" \
     --camera-model SIMPLE_RADIAL --params "$F,360.0,640.0,$K" --mark-prior-focal
map "3b3_wreck_01_fixed" "$FRAMES/wreck_01" "M_fixed_from_wreck07/wreck_01/run0" \
    M_fixed_from_wreck07 wreck_01 --mapper incremental --fix-intrinsics \
    --expect-camera-model SIMPLE_RADIAL --hypothesis 3B-3 \
    --role "intrinsics FIXED to wreck_07's values, principal point swapped for the rotated decode -- diagnostic only"

# =====================================================================
# 3B-4  temporal-baseline sensitivity: configuration A on nested schedules
# =====================================================================
echo "===== 3B-4 frame schedules $(date +%H:%M:%S) ====="
for clip in wreck_05 wreck_01 cenote_01; do
  for sched in S25 S13; do
    echo "--- A / ${clip}_${sched} $(date +%H:%M:%S)"
    $PY -m experiments.week3_geometry.scripts.run_colmap \
        --config A --clip "${clip}_${sched}" \
        --frames-root "$P3B/outputs/frames_schedules" \
        --methods "$METHODS" --out-root "$OUT" --repeat 0 --overwrite \
        || echo "  -> nonzero exit"
  done
done

echo "===== 3B-2/3/4 done $(date +%H:%M:%S) ====="
