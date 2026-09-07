"""S4 step 2 — run one surviving model over the baseline window and every perturbation.

EXPLORATORY. ONE MODEL PER PROCESS, inside that model's own venv.

Each frame is still inferred INDEPENDENTLY — one image path per call, no
neighbour, no state. The perturbation changes what the image looks like, never
how many images the model sees.

Products land under `outputs/s4_predictions/<perturbation>/<model>/<clip>/`,
with `baseline` as the unperturbed arm, so `s4_analysis.py` can compare a
perturbed field against the baseline field frame by frame using the same
`MonoReader` every other stage uses.

    experiments/week4_mono/.venv-moge/bin/python \\
        -m experiments.week4_mono.scripts.s4_run --model moge2_vitl
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import time

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week4_mono import backends, common, monoio  # noqa: E402


def run(be, model: str, clip: str, frames: list[int], paths: list[str],
        root: str, tag: str, overwrite: bool) -> dict:
    w = monoio.MonoWriter(root, model, clip, overwrite=overwrite)
    t0 = time.perf_counter()
    for fi, p in zip(frames, paths):
        out = be.infer(p)
        w.add_frame(fi, native=out["native"], valid=out["valid"],
                    canonical_range=out.get("canonical_range"), K=out.get("K"),
                    conf=out.get("conf"), aux=out.get("aux"), extra=out.get("extra"))
        del out
        gc.collect()
    wall = time.perf_counter() - t0
    prov = be.provenance()
    prov.update({
        "s4_arm": tag,
        "n_frames": len(frames),
        "frames": frames,
        "input_paths": [os.path.relpath(p, REPO_ROOT) for p in paths],
        "seconds": {"inference_total": round(wall, 1)},
        "peak_process_rss_gb": round(common.peak_rss_gb(), 2),
        "single_image_invariant": (
            "one image path per call; the perturbation changes what the image looks "
            "like, never how many images the model sees"),
    })
    w.close(native_kind=be.native_kind, range_rule=be.range_rule,
            semantics=be.semantics(), provenance=prov,
            preprocessing=be.preprocessing())
    return {"clip": clip, "arm": tag, "n_frames": len(frames), "seconds": round(wall, 1)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, choices=backends.keys())
    ap.add_argument("--device", default="mps")
    ap.add_argument("--clips", nargs="*", default=None)
    ap.add_argument("--perturbed-root", default=os.path.join(common.OUTPUTS, "perturbed"))
    ap.add_argument("--out-root", default=os.path.join(common.OUTPUTS, "s4_predictions"))
    ap.add_argument("--arms", nargs="*", default=None,
                    help="perturbation names; default: baseline + every frozen one")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--skip-existing", action="store_true")
    args = ap.parse_args()

    with open(os.path.join(args.perturbed_root, "manifest.json")) as fh:
        man = json.load(fh)
    clips = args.clips or [c for c in common.CLIPS if c in man["clips"]]
    arms = args.arms or (["baseline"] + [p["name"] for p in man["perturbations"]])

    common.seed_everything()
    be = backends.get(args.model)(device=args.device)
    be.load()
    print(f"[S4] {args.model} loaded in {be.load_seconds:.1f}s")

    done = []
    for tag in arms:
        root = os.path.join(args.out_root, tag)
        for clip in clips:
            if args.skip_existing and monoio.exists(root, args.model, clip):
                continue
            frames = man["clips"][clip]["frames"]
            if tag == "baseline":
                paths = [common.frame_path(clip, fi) for fi in frames]
            else:
                d = os.path.join(args.perturbed_root, clip, tag)
                paths = [os.path.join(d, f"f{fi:06d}.png") for fi in frames]
            missing = [p for p in paths if not os.path.exists(p)]
            if missing:
                print(f"[S4] {tag}/{clip}: MISSING {len(missing)} inputs, skipping")
                continue
            common.seed_everything()
            rec = run(be, args.model, clip, frames, paths, root, tag, args.overwrite)
            done.append(rec)
        print(f"[S4] {args.model} {tag}: {sum(1 for d in done if d['arm'] == tag)} clips, "
              f"{sum(d['seconds'] for d in done if d['arm'] == tag):.0f}s")

    common.write_json(os.path.join(args.out_root, f"_run_{args.model}.json"),
                      {"model": args.model, "arms": arms, "clips": clips, "done": done,
                       "peak_process_rss_gb": round(common.peak_rss_gb(), 2)},
                      overwrite=True)
    print(f"[S4] {args.model}: {len(done)} (arm,clip) products, "
          f"{sum(d['seconds'] for d in done):.0f}s total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
