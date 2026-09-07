"""Produce one model's monocular prediction product over the frozen clips.

EXPLORATORY. ONE MODEL PER PROCESS, runs inside that model's own venv.

This is the shared inference pass behind S2, S3 and S5: they all need the same
thing — every frozen frame, inferred INDEPENDENTLY, persisted with its native
representation intact — and running it once is the difference between a
tractable bakeoff and three full sweeps.

    6 clips x 48 frames = 288 frames per model.

THE INVARIANT THIS SCRIPT EXISTS TO PROTECT. Frames are iterated in order and
handed to the model ONE AT A TIME. The model is never given a neighbour, a
window, a previous prediction or any Week-3 geometry. Sequence structure is used
only AFTER inference, by the evaluation stages. That the frames come from a clip
is, from the model's point of view, not knowable.

Memory (CLAUDE.md invariant 9): nothing accumulates. Each frame's fields go
straight to their own `.npy` shard via `MonoWriter` and are dropped; only the
small per-frame metadata record is retained, and the peak RSS is recorded so the
claim is checked rather than asserted.

    experiments/week4_mono/.venv-mono/bin/python \\
        -m experiments.week4_mono.scripts.run_inference --model dav2_small
"""

from __future__ import annotations

import argparse
import gc
import os
import sys
import time
import traceback

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week4_mono import backends, common  # noqa: E402
from experiments.week4_mono.monoio import MonoWriter  # noqa: E402


def run_clip(be, model: str, clip: str, root: str, overwrite: bool,
             limit: int | None = None) -> dict:
    frames = common.frame_indices(clip)
    if limit:
        frames = frames[:limit]
    w = MonoWriter(root, model, clip, overwrite=overwrite)
    t0 = time.perf_counter()
    infer_seconds = []
    for fi in frames:
        # ONE frame in, ONE prediction out. No neighbour is in scope here.
        out = be.infer(common.frame_path(clip, fi))
        infer_seconds.append(out["extra"].get("infer_seconds", float("nan")))
        w.add_frame(fi,
                    native=out["native"],
                    valid=out["valid"],
                    canonical_range=out.get("canonical_range"),
                    K=out.get("K"),
                    conf=out.get("conf"),
                    aux=out.get("aux"),
                    extra=out.get("extra"))
        del out
        gc.collect()
    wall = time.perf_counter() - t0

    prov = be.provenance()
    prov.update({
        "n_frames": len(frames),
        "frames": frames,
        "source_hw": list(common.clip_source_hw(clip)),
        "clip_role": common.CLIP_ROLE[clip],
        "seed": common.SEED,
        "env": common.env_report(),
        "seconds": {
            "model_load": round(be.load_seconds, 2),
            "inference_total": round(wall, 1),
            "inference_median_per_frame": round(float(np.median(infer_seconds)), 3),
        },
        "peak_process_rss_gb": round(common.peak_rss_gb(), 2),
        "peak_mps_driver_gb": round(common.mps_peak_gb(), 2),
        "single_image_invariant": (
            "Every frame was inferred independently: one image path per call, no "
            "neighbouring image, no temporal state, no Week-3 geometry input. The "
            "clip ordering is used only by the evaluation stages, after inference."),
    })
    path = w.close(native_kind=be.native_kind, range_rule=be.range_rule,
                   semantics=be.semantics(), provenance=prov,
                   preprocessing=be.preprocessing())
    return {"clip": clip, "n_frames": len(frames), "seconds": round(wall, 1),
            "median_per_frame": round(float(np.median(infer_seconds)), 3),
            "clip_json": os.path.relpath(path, REPO_ROOT)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, choices=backends.keys())
    ap.add_argument("--device", default="mps")
    ap.add_argument("--clips", nargs="*", default=None,
                    help="default: all six frozen clips, in the frozen order")
    ap.add_argument("--limit", type=int, default=None,
                    help="bring-up only; the bakeoff uses every frame")
    ap.add_argument("--root", default=os.path.join(common.OUTPUTS, "predictions"))
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--skip-existing", action="store_true")
    args = ap.parse_args()

    clips = args.clips or common.CLIPS
    for c in clips:
        if c not in common.CLIPS:
            raise SystemExit(f"{c!r} is not one of the six frozen clips: {common.CLIPS}")

    common.seed_everything()
    be = backends.get(args.model)(device=args.device)
    be.load()
    print(f"[infer] {args.model} loaded in {be.load_seconds:.1f}s on {args.device}")

    done, failed = [], []
    for clip in clips:
        from experiments.week4_mono import monoio
        if args.skip_existing and monoio.exists(args.root, args.model, clip):
            print(f"[infer] {args.model}/{clip}: exists, skipping")
            continue
        try:
            rec = run_clip(be, args.model, clip, args.root, args.overwrite, args.limit)
            done.append(rec)
            print(f"[infer] {args.model}/{clip}: {rec['n_frames']} frames in "
                  f"{rec['seconds']}s ({rec['median_per_frame']}s/frame)")
        except SystemExit as exc:
            failed.append({"clip": clip, "error": str(exc)})
            print(f"[infer] {args.model}/{clip}: REFUSED — {exc}")
        except Exception as exc:
            failed.append({"clip": clip, "error": f"{type(exc).__name__}: {exc}",
                           "traceback": traceback.format_exc()})
            print(f"[infer] {args.model}/{clip}: FAILED — {exc}")

    summary = {"model": args.model, "device": args.device, "clips_done": done,
               "clips_failed": failed,
               "peak_process_rss_gb": round(common.peak_rss_gb(), 2),
               "peak_mps_driver_gb": round(common.mps_peak_gb(), 2)}
    sp = os.path.join(args.root, f"_run_{args.model}.json")
    common.write_json(sp, summary, overwrite=True)
    total = sum(d["seconds"] for d in done)
    print(f"[infer] {args.model}: {len(done)} clips ok, {len(failed)} failed, "
          f"{total:.0f}s total, peak RSS {summary['peak_process_rss_gb']} GB")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
