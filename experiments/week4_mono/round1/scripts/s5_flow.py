"""S5 step 1 — consecutive-frame correspondence, computed ONCE per clip.

EXPLORATORY. Runs in `experiments/week2a_flow/.venv-flow`.

FREEZE §5 S5: "Use SEA-RAFT only for evaluation correspondence." That is exactly
what this is. The flow never reaches a depth model, never conditions an
inference and never enters a prediction; it exists so that S5 can ask "did the
geometry at THIS SCENE POINT change between frames?" instead of "did the numbers
at this PIXEL change?", which scene motion alone would answer yes to.

Computed once per clip and persisted, because every arm needs the same
correspondence and recomputing it per arm would make the temporal comparison
depend on which model was being scored.

SEA-RAFT-M is the project's canonical Phase-2B correspondence backend
(`uw.cli.CANONICAL_FLOW_BACKEND`), used here unchanged, with the same
forward-backward consistency mask (Sundaram/Brox/Keuper, alpha 0.01, beta 0.5)
that Week 2 applied identically to every backend. The mask is what makes an
occlusion or a fast-moving diver drop out rather than register as geometric
instability.

Flow is estimated on the frozen source frames and resampled onto the Week-4
evaluation grid with `uw.flow.resize_flow`, which rescales the displacement
magnitudes as well as the array — a flow vector is measured in pixels of its own
grid, so changing the grid must change the numbers.

    experiments/week2a_flow/.venv-flow/bin/python \\
        -m experiments.week4_mono.round1.scripts.s5_flow --clip wreck_07
"""

from __future__ import annotations

import argparse
import gc
import os
import sys
import time

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week4_mono.round1 import common, evalgrid  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clips", nargs="*", default=None)
    ap.add_argument("--device", default="mps")
    ap.add_argument("--out-root", default=os.path.join(common.OUTPUTS, "flow"))
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--skip-existing", action="store_true")
    args = ap.parse_args()

    from uw.flow import forward_backward_consistency, resize_flow
    from uw.io import load
    from uw.searaft import SeaRaftBackend
    from uw.types import Frame, FrameSequence

    backend = SeaRaftBackend(device=args.device)
    clips = args.clips or common.CLIPS
    summary = {"backend": backend.describe(), "clips": {}}

    for clip in clips:
        out_dir = os.path.join(args.out_root, clip)
        meta_path = os.path.join(out_dir, "flow.json")
        if args.skip_existing and os.path.exists(meta_path):
            print(f"[S5-flow] {clip}: exists, skipping")
            continue
        common.refuse_clobber(meta_path, args.overwrite)
        os.makedirs(out_dir, exist_ok=True)

        frames_idx = common.frame_indices(clip)
        # The frozen frames are individual PNGs, so they are loaded one at a
        # time and assembled into a FrameSequence — `uw.io.load` maps sRGB into
        # linear light, which is the representation every backend expects.
        seq = FrameSequence([load(common.frame_path(clip, i))[0] for i in frames_idx])
        source_hw = common.clip_source_hw(clip)
        uv, eval_hw = evalgrid.eval_grid(source_hw)

        t0 = time.perf_counter()
        recs = []
        for k in range(len(frames_idx) - 1):
            fwd = backend.estimate(seq, k, k + 1).flow
            bwd = backend.estimate(seq, k + 1, k).flow
            valid, fb_err = forward_backward_consistency(fwd, bwd)
            f_eval = resize_flow(fwd, eval_hw[0], eval_hw[1])
            # Nearest-neighbour on the mask: a validity flag must never be
            # interpolated into a fractional confidence.
            import cv2
            v_eval = cv2.resize(valid.astype(np.uint8), (eval_hw[1], eval_hw[0]),
                                interpolation=cv2.INTER_NEAREST).astype(bool)
            stem = os.path.join(out_dir, f"p{frames_idx[k]:06d}_{frames_idx[k+1]:06d}")
            np.save(stem + "_flow.npy", f_eval.astype(np.float32))
            np.save(stem + "_valid.npy", v_eval)
            mag = np.linalg.norm(f_eval, axis=-1)
            recs.append({
                "t": int(frames_idx[k]), "t1": int(frames_idx[k + 1]),
                "valid_fraction": float(v_eval.mean()),
                "flow_median_px_eval_grid": float(np.median(mag[v_eval]))
                                            if v_eval.any() else float("nan"),
                "flow_p95_px_eval_grid": float(np.percentile(mag[v_eval], 95))
                                         if v_eval.any() else float("nan"),
                "fb_error_median_px_source": float(np.nanmedian(fb_err)),
            })
            del fwd, bwd, valid, fb_err, f_eval, v_eval
            gc.collect()

        meta = {
            "_comment": ("Consecutive-frame SEA-RAFT correspondence for S5. Used ONLY to "
                         "evaluate; it never reaches a depth model and never conditions an "
                         "inference. Flow is stored on the Week-4 EVALUATION grid, with "
                         "magnitudes rescaled to that grid."),
            "clip": clip,
            "source_hw": list(source_hw),
            "eval_hw": list(eval_hw),
            "eval_downsample": evalgrid.EVAL_DOWNSAMPLE,
            "n_pairs": len(recs),
            "seconds": round(time.perf_counter() - t0, 1),
            "fb_consistency": ("Sundaram/Brox/Keuper eq.6 with the published alpha=0.01, "
                               "beta=0.5, not re-tuned — the same yardstick Week 2 applied "
                               "to every backend"),
            "backend": backend.describe(),
            "pairs": recs,
        }
        common.write_json(meta_path, meta, overwrite=True)
        summary["clips"][clip] = {
            "n_pairs": len(recs), "seconds": meta["seconds"],
            "median_valid_fraction": float(np.median([r["valid_fraction"] for r in recs])),
            "median_flow_px": float(np.median([r["flow_median_px_eval_grid"] for r in recs])),
        }
        s = summary["clips"][clip]
        print(f"[S5-flow] {clip:15s} {len(recs)} pairs in {meta['seconds']}s "
              f"valid={s['median_valid_fraction']:.3f} "
              f"flow={s['median_flow_px']:.2f}px(eval grid)")
        del seq
        gc.collect()

    common.write_json(os.path.join(args.out_root, "_summary.json"), summary,
                      overwrite=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
