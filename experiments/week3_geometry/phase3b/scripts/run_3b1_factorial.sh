#!/bin/bash
# 3B-1 -- the 2x2 correspondence factorial.
#
#            brute force        LightGlue
#   SIFT       F1 (=A, reused)    F2   <- run here
#   ALIKED     F3   <- run here   F4 (=B, reused)
#
# F1 and F4 are Phase 3A A/run0 and B/run0 and are NOT re-run. Only the two
# missing cells are executed, plus one bounded repeat of each on the primary
# clip (wreck_05) so the run-to-run spread of the NEW configurations is measured
# rather than assumed -- the claim under test is a difference in track length,
# and A's own repeat spread on that clip was 3.5% in point count.
#
# Sequential on purpose: runtime and peak memory are reported numbers.
set -u
cd "$(dirname "$0")/../../../.." || exit 1
PY=.venv/bin/python
METHODS=experiments/week3_geometry/phase3b/configs/phase3b_methods.json
OUT=experiments/week3_geometry/phase3b/outputs/colmap

run () {  # config clip repeat
  echo "=== $1 $2 run$3 $(date +%H:%M:%S) ==="
  $PY -m experiments.week3_geometry.scripts.run_colmap \
      --config "$1" --clip "$2" --repeat "$3" \
      --methods "$METHODS" --out-root "$OUT" --overwrite \
      || echo "  -> nonzero exit"
}

for clip in wreck_05 wreck_01; do
  for cfg in F2 F3; do run "$cfg" "$clip" 0; done
done
# bounded repeat, primary clip only
for cfg in F2 F3; do run "$cfg" wreck_05 1; done

echo "=== 3B-1 factorial done $(date +%H:%M:%S) ==="
