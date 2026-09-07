"""S6 — the frozen Week-2 temporal evaluation, run on the restored sequences.

EXPLORATORY. Runs in `experiments/week2a_flow/.venv-flow`.

FREEZE §5 S6 requires the project's own frozen temporal metrics, not a new one
invented for this stage. So this calls `uw.metrics.evaluate_temporal` unchanged:
motion-compensated warp error in linear light with SEA-RAFT correspondence, at
lags 1/4/8, plus temporal delta E00, on the Phase-2B evaluation grid.

`original` is always the UNPROCESSED frozen frame sequence — it is the only
thing that drives correspondence and the illumination fit, exactly as Phase 2B
specified. `corrected` is the restored sequence driven by one range field. So
the question this asks is the project's standing one: does this pipeline
configuration make the output less temporally stable than its input, and by how
much, with scene motion compensated away.

The restored frames were written as `J/J_CLAMP` in sRGB, which is a single
global scalar away from the restored radiance. `evaluate_temporal`'s
illumination fit absorbs a global gain by construction, so the scalar does not
enter the result — and every arm carries the SAME scalar anyway.

    experiments/week2a_flow/.venv-flow/bin/python \\
        -m experiments.week4_mono.scripts.s6_temporal --arms moge2_vitl
"""

from __future__ import annotations

import argparse
import gc
import os
import sys
import traceback

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week4_mono import common  # noqa: E402
from experiments.week4_mono.scripts.s6_restoration import REFERENCE_ARM  # noqa: E402


def load_seq(paths):
    from uw.io import load
    from uw.types import FrameSequence
    return FrameSequence([load(p)[0] for p in paths])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arms", nargs="*", required=True)
    ap.add_argument("--clips", nargs="*", default=None)
    ap.add_argument("--restored-root", default=os.path.join(common.OUTPUTS, "s6", "restored"))
    ap.add_argument("--device", default="mps")
    ap.add_argument("--lags", nargs="*", type=int, default=[1, 4, 8])
    ap.add_argument("--n-anchors", type=int, default=3)
    ap.add_argument("--out", default=os.path.join(common.OUTPUTS, "s6", "s6_temporal.json"))
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    from uw.metrics import evaluate_temporal
    from uw.searaft import SeaRaftBackend

    backend = SeaRaftBackend(device=args.device)
    clips = args.clips or common.CLIPS
    arms = [REFERENCE_ARM] + [a for a in args.arms if a != REFERENCE_ARM]

    out = {
        "_comment": ("Frozen Week-2 (Phase 2B) temporal evaluation, unchanged, applied to "
                     "the S6 restored sequences. `original` is always the unprocessed "
                     "frozen frames: it drives correspondence and the illumination fit and "
                     "is never itself measured."),
        "stage": "S6-temporal",
        "backend": backend.describe(),
        "lags": args.lags, "n_anchors": args.n_anchors,
        "arms": {},
    }
    for arm in arms:
        rec = {"clips": {}}
        for clip in clips:
            d = os.path.join(args.restored_root, clip, arm)
            frames = common.frame_indices(clip)
            paths = [os.path.join(d, f"f{fi:06d}.png") for fi in frames]
            if not all(os.path.exists(p) for p in paths):
                rec["clips"][clip] = {"status": "missing_restored_frames"}
                continue
            try:
                original = load_seq([common.frame_path(clip, fi) for fi in frames])
                corrected = load_seq(paths)
                res = evaluate_temporal(original, corrected, backend,
                                        lags=tuple(args.lags), n_anchors=args.n_anchors)
                m = {"status": "ok", "metric_size_hw": list(res.metric_size_hw),
                     "anchors": list(res.anchors)}
                for lag in res.lags:
                    k = lag.lag
                    # `raw_warp` is the Phase-2B primary: motion-compensated L1
                    # in linear light. Everything is recorded for BOTH the
                    # restored sequence and its unprocessed input, on the same
                    # correspondence and the same mask, because a temporal number
                    # without its input is not interpretable.
                    m[f"status_lag{k}"] = lag.status
                    m[f"n_pairs_lag{k}"] = lag.n_pairs
                    m[f"coverage_lag{k}"] = float(lag.valid_fraction)
                    for name, val in (("mcwarp", lag.raw_warp),
                                      ("mcwarp_illum_aware", lag.illumination_aware_warp),
                                      ("motion_reduction_ratio", lag.motion_reduction_ratio),
                                      ("temporal_delta_e", lag.temporal_delta_e),
                                      ("mcwarp_input", lag.input_raw_warp),
                                      ("temporal_delta_e_input", lag.input_temporal_delta_e)):
                        if val is not None:
                            m[f"{name}_lag{k}"] = float(val)
                    m[f"illumination_confounded_lag{k}"] = bool(lag.illumination_confounded)
                rec["clips"][clip] = m
                print(f"[S6-temporal] {arm:22s} {clip:15s} "
                      + " ".join(f"@{l}={m.get(f'mcwarp_lag{l}', float('nan')):.5f}"
                                 for l in args.lags))
                del original, corrected, res
                gc.collect()
            except Exception as exc:
                rec["clips"][clip] = {"status": "error",
                                      "error": f"{type(exc).__name__}: {exc}",
                                      "traceback": traceback.format_exc()}
                print(f"[S6-temporal] {arm}/{clip}: FAILED {exc}")
        out["arms"][arm] = rec
        common.write_json(args.out, out, overwrite=True)
    common.write_json(args.out, out, overwrite=True)
    print(f"[S6-temporal] -> {os.path.relpath(args.out, REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
