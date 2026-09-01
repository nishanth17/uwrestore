"""Stage 1 — sparse contact sheets for visual clip triage (Week 3 Phase 3A).

EXPLORATORY. Not part of the `uw` package. Main project venv (numpy + opencv).

Writes one sheet per clip: `--frames` frames sampled on the same deterministic
grid as `inspect_clips.py` (5%..95% of the clip, evenly spaced), laid out in a
grid and annotated with the source frame index.

The Phase 3A inspection budget allows 6-12 frames per candidate, sampled
across duration rather than searched for favourable content — so the sampling
grid is fixed and shared with the statistics script, and there is no
"pick the best frame" path anywhere in this file.

Frames are shown as decoded (sRGB-encoded), NOT linear light: these sheets are
for a human to judge scene content, motion character and visibility, and the
sRGB view is the one a human reads correctly. No restoration measurement is
made from them.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import cv2
import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week3_geometry.scripts.inspect_clips import sample_indices  # noqa: E402

MANIFEST = os.path.join(REPO_ROOT, "data", "testset", "manifest.json")


def sheet(path: str, n_frames: int, frames: int, cell_w: int, cols: int) -> np.ndarray:
    idxs = sample_indices(n_frames, frames)
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise IOError(f"failed to open {path!r}")
    tiles = []
    try:
        want = set(idxs)
        i = 0
        while len(tiles) < len(idxs):
            if not cap.grab():
                break
            if i in want:
                ok, bgr = cap.retrieve()
                if not ok:
                    break
                h, w = bgr.shape[:2]
                cell_h = int(round(cell_w * h / w))
                t = cv2.resize(bgr, (cell_w, cell_h), interpolation=cv2.INTER_AREA)
                cv2.putText(t, str(i), (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                            (0, 0, 0), 3, cv2.LINE_AA)
                cv2.putText(t, str(i), (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                            (255, 255, 255), 1, cv2.LINE_AA)
                tiles.append(t)
            i += 1
    finally:
        cap.release()
    if not tiles:
        raise IOError(f"{path!r}: decoded no frames")
    ch, cw = tiles[0].shape[:2]
    rows = int(np.ceil(len(tiles) / cols))
    canvas = np.zeros((rows * ch, cols * cw, 3), dtype=np.uint8)
    for j, t in enumerate(tiles):
        r, c = divmod(j, cols)
        canvas[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw] = t
    return canvas


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--clips", nargs="+", required=True, help="manifest clip ids")
    ap.add_argument("--frames", type=int, default=8)
    ap.add_argument("--cell-width", type=int, default=320)
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    with open(MANIFEST) as fh:
        by_id = {c["id"]: c for c in json.load(fh)["clips"]}
    os.makedirs(args.out_dir, exist_ok=True)
    for cid in args.clips:
        clip = by_id[cid]
        out = os.path.join(args.out_dir, f"{cid}.jpg")
        if os.path.exists(out) and not args.overwrite:
            raise SystemExit(f"refusing to overwrite {out!r} (pass --overwrite)")
        img = sheet(os.path.join(REPO_ROOT, clip["local_path"]),
                    int(clip["frame_count"]), args.frames, args.cell_width, args.cols)
        cv2.imwrite(out, img, [cv2.IMWRITE_JPEG_QUALITY, 88])
        print(f"wrote {out}  {img.shape[1]}x{img.shape[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
