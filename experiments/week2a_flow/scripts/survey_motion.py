"""Pick the bakeoff excerpts, reproducibly. EXPLORATORY.

Two jobs:
  1. Say which of the frozen test-set clips actually has the strongest
     camera motion, instead of guessing from the filenames.
  2. Choose one short excerpt per clip, by a rule written down here rather
     than by eye: the window whose mean inter-frame motion is highest, i.e.
     the most demanding stretch of that clip. Comparing backends on the easy
     seconds of a clip would tell us very little.

The motion measurement uses OpenCV Farneback at low resolution. That is
deliberately NOT one of the candidate backends — using a candidate to choose
the frames it is later judged on would bias the selection toward whichever
model likes that footage. Farneback is only accurate enough to rank
"how much is moving", which is all it is asked for.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import cv2
import numpy as np

_REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

SURVEY_LONG_SIDE = 480          # motion proxy only; not the eval resolution
STRIDE = 5                      # sample every 5th frame pair
WINDOW = 8                      # frames per excerpt (see run_bakeoff)


def survey_clip(path: str, max_frames: int | None = None) -> dict:
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise IOError(f"cannot open {path}")
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    prev, prev_idx = None, None
    samples = []
    idx = 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if idx % STRIDE == 0:
            ok, bgr = cap.retrieve()
            if not ok:
                break
            h, w = bgr.shape[:2]
            s = SURVEY_LONG_SIDE / max(h, w)
            small = cv2.cvtColor(
                cv2.resize(bgr, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA),
                cv2.COLOR_BGR2GRAY,
            )
            if prev is not None:
                f = cv2.calcOpticalFlowFarneback(
                    prev, small, None, 0.5, 3, 21, 3, 5, 1.2, 0
                )
                mag = np.sqrt(f[..., 0] ** 2 + f[..., 1] ** 2)
                # per-frame rate, in source pixels, undoing both the survey
                # downscale and the frame stride
                rate = float(np.median(mag)) / s / STRIDE
                samples.append({"frame": prev_idx, "median_motion_px_per_frame": rate})
            prev, prev_idx = small, idx
        idx += 1
        if max_frames and idx >= max_frames:
            break
    cap.release()
    rates = np.array([s["median_motion_px_per_frame"] for s in samples])
    frames = np.array([s["frame"] for s in samples])
    # smooth over ~1 s so a single blurred frame doesn't pick the window
    k = 6
    if len(rates) >= k:
        sm = np.convolve(rates, np.ones(k) / k, mode="valid")
        best = int(frames[int(np.argmax(sm))])
    else:
        best = int(frames[int(np.argmax(rates))]) if len(frames) else 0
    # keep the window (plus MOF's +/-2 context) inside the clip
    best = int(np.clip(best, 2, max(2, n - WINDOW - 3)))
    return {
        "path": os.path.relpath(path, _REPO),
        "frame_count": n,
        "samples": len(samples),
        "median_motion_px_per_frame": {
            "mean": float(rates.mean()) if len(rates) else None,
            "median": float(np.median(rates)) if len(rates) else None,
            "p90": float(np.percentile(rates, 90)) if len(rates) else None,
            "max": float(rates.max()) if len(rates) else None,
        },
        "selected_excerpt_start": best,
        "selection_rule": (
            f"argmax of a {k}-sample (~1 s) moving average of the Farneback "
            f"median motion, clamped so the {WINDOW}-frame excerpt and MOF's "
            f"+/-2 frame context fit inside the clip"
        ),
    }


CLIPS = {
    "swimthrough": "data/testset/swimthrough/SWIMTHROUGH.MP4",
    "murky_eel": "data/testset/murky/MURKYEEL.MP4",
    "murky_shark": "data/testset/murky/MURKYSHARK.MP4",
    "lights": "data/testset/lights/LIGHTNIGHTDIVE.MP4",
    "distance": "data/testset/distance/DISTANCESHOT.MP4",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="experiments/week2a_flow/excerpts.json")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    out_path = os.path.join(_REPO, args.out)
    if os.path.exists(out_path) and not args.overwrite:
        raise FileExistsError(f"{out_path!r} exists; pass --overwrite")

    result = {}
    for name, rel in CLIPS.items():
        print(f"surveying {name} ...", flush=True)
        result[name] = survey_clip(os.path.join(_REPO, rel))
        print(json.dumps(result[name], indent=2))

    ranked = sorted(result.items(),
                    key=lambda kv: kv[1]["median_motion_px_per_frame"]["mean"],
                    reverse=True)
    doc = {
        "_comment": (
            "Excerpt selection for the Week 2 Phase 1A optical-flow bakeoff. "
            "Motion measured with OpenCV Farneback at 480px long side — a "
            "proxy for choosing frames only, deliberately not one of the "
            "candidate backends."
        ),
        "strongest_camera_motion_clip": ranked[0][0],
        "motion_ranking": [k for k, _ in ranked],
        "clips": result,
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(doc, f, indent=2)
    print("\nranking (mean median motion px/frame, source pixels):")
    for k, v in ranked:
        print(f"  {k:14s} {v['median_motion_px_per_frame']['mean']:.3f}  "
              f"start={v['selected_excerpt_start']}")
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
