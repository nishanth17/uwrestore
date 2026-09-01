#!/bin/bash
# Refraction failure attribution (Stage 3 follow-up).
#
# Run ONLY after C_on has been observed to fail. These are diagnostics, not
# bakeoff candidates: they exist to decide whether a C_on failure is caused by
# refraction, by the unmeasured flat-port parameters, or by the refractive
# implementation not initialising on this footage at all.
set -u
PY=.venv/bin/python
# cenote_01 and wreck_05 are the two clips where C_on actually reconstructs,
# so they are where the scale question can be asked; wreck_07 is where C_on
# fails, so it is where the "is it refraction or the pipeline?" question can.
for clip in cenote_01 wreck_05; do
  for cfg in C_on_null C_on_thick; do
    echo "=== $cfg $clip $(date +%H:%M:%S) ==="
    $PY -m experiments.week3_geometry.scripts.run_colmap --config "$cfg" --clip "$clip" \
        --overwrite || echo "  -> nonzero exit"
  done
done
echo "=== refraction diagnostics done $(date +%H:%M:%S) ==="
