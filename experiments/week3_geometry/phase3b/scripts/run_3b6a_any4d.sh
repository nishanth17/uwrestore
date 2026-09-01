#!/bin/bash
# 3B-6A -- Any4D on the clip that produced Phase 3A's worst number.
#
# wreck_03 is the trigger: MapAnything showed a 6.64x fitted per-frame scale
# wander against configuration A and a 129.8% range-dependent residual swing
# there. swimthrough_02 is the easy control -- the clip where every Phase 3A
# method landed inside the restoration budget -- so a failure on wreck_03 can be
# read as a dynamic-content failure rather than as "this model does not work".
#
# One model per process, sequential: the process boundary is the authoritative
# MPS cleanup boundary and the reported runtime and peak memory have to mean
# something.
set -u
cd "$(dirname "$0")/../../../.." || exit 1
W3=experiments/week3_geometry
PY=$W3/.venv-any4d/bin/python
CKPT=$W3/checkpoints/any4d_4v_combined.pth

echo "===== 3B-6A Any4D $(date +%H:%M:%S) ====="
if [ ! -f "$CKPT" ]; then echo "no checkpoint at $CKPT"; exit 1; fi

# Checkpoint identity, recorded before anything consumes it (Phase 3A's
# Water-VGGT episode is why this is not optional).
mkdir -p "$W3/phase3b/outputs/preflight"
$PY - <<'PYEOF'
import hashlib, json, os
p = "experiments/week3_geometry/checkpoints/any4d_4v_combined.pth"
h = hashlib.sha256()
with open(p, "rb") as fh:
    for chunk in iter(lambda: fh.read(1 << 22), b""):
        h.update(chunk)
rec = {"path": p, "bytes": os.path.getsize(p), "sha256": h.hexdigest(),
       "source": "https://huggingface.co/airlabshare/any4d-checkpoint/resolve/main/any4d_4v_combined.pth",
       "license": "NOT STATED -- the Hugging Face repo declares no licence field and no licence file"}
out = "experiments/week3_geometry/phase3b/outputs/preflight/any4d_checkpoint.json"
json.dump(rec, open(out, "w"), indent=2)
open(os.path.splitext(p)[0] + ".sha256", "w").write(rec["sha256"] + "  " + os.path.basename(p) + "\n")
print("checkpoint", rec["bytes"], "bytes, sha256", rec["sha256"])
PYEOF

for clip in wreck_03 swimthrough_02; do
  echo "--- Any4D / $clip $(date +%H:%M:%S)"
  $PY -m experiments.week3_geometry.phase3b.scripts.run_any4d \
      --clip "$clip" --checkpoint "$CKPT" --overwrite || echo "  -> nonzero exit"
done
echo "===== 3B-6A done $(date +%H:%M:%S) ====="
