"""Assemble per-clip, cross-backend comparison sheets. EXPLORATORY.

The qualitative read is a first-class deliverable of Phase 1A, and it is
much easier to see where two backends disagree when their outputs are on the
same page at the same scale than when they are in sibling directories.

One sheet per (clip, pair): a header strip with frame t, frame t+1 and the
uncompensated difference, then one row per backend with its flow, its warp
of t+1 into t, the warp residual, and the common FB validity mask.

Reads only what run_bakeoff already wrote; computes nothing.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import cv2
import numpy as np

_REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))

# FlowIt stays in this list although its wrapper was deleted in Phase 2B:
# these scripts read persisted metrics.json / .npy output and skip any
# backend whose directory is absent, so the historical Phase 2A tables
# still regenerate from what is on disk while a fresh run simply omits it.
BACKENDS = ["searaft", "waft", "flowit", "videoflow_mof"]
ROW_PANELS = [
    ("flow_forward.png", "flow t->t+1"),
    ("warped_t1_to_t.png", "t+1 warped to t"),
    ("residual_warped.png", "warp residual (linear)"),
    ("fb_valid_mask.png", "FB valid mask"),
]
HEADER_PANELS = [
    ("frame_t.png", "frame t"),
    ("frame_t1.png", "frame t+1"),
    ("residual_uncompensated.png", "uncompensated |t+1 - t|"),
    (None, ""),
]

TILE_W = 400
LABEL_H = 26
PAD = 6


def _tile(path, label, tile_w=TILE_W, tile_h=None):
    if path is None or not os.path.exists(path):
        img = np.full((tile_h or int(tile_w * 9 / 16), tile_w, 3), 32, np.uint8)
        label = label or "n/a"
    else:
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        h, w = img.shape[:2]
        img = cv2.resize(img, (tile_w, int(round(h * tile_w / w))),
                         interpolation=cv2.INTER_AREA)
    if tile_h is not None and img.shape[0] != tile_h:
        canvas = np.zeros((tile_h, tile_w, 3), np.uint8)
        canvas[:min(tile_h, img.shape[0])] = img[:min(tile_h, img.shape[0])]
        img = canvas
    strip = np.full((LABEL_H, img.shape[1], 3), 20, np.uint8)
    cv2.putText(strip, label, (6, LABEL_H - 8), cv2.FONT_HERSHEY_SIMPLEX,
                0.45, (235, 235, 235), 1, cv2.LINE_AA)
    return np.vstack([strip, img])


def _row(tiles):
    h = max(t.shape[0] for t in tiles)
    out = []
    for t in tiles:
        if t.shape[0] != h:
            pad = np.zeros((h - t.shape[0], t.shape[1], 3), np.uint8)
            t = np.vstack([t, pad])
        out.append(t)
        out.append(np.zeros((h, PAD, 3), np.uint8))
    return np.hstack(out[:-1])


def build(clip, pair_dirname, root, out_path, overwrite):
    rows = []
    ref = os.path.join(root, BACKENDS[0], clip, pair_dirname)
    probe = cv2.imread(os.path.join(ref, "frame_t.png"))
    tile_h = int(round(probe.shape[0] * TILE_W / probe.shape[1]))

    rows.append(_row([_tile(os.path.join(ref, p) if p else None, lbl, TILE_W, tile_h)
                      for p, lbl in HEADER_PANELS]))

    for be in BACKENDS:
        d = os.path.join(root, be, clip, pair_dirname)
        if not os.path.isdir(d):
            continue
        with open(os.path.join(d, "meta.json")) as f:
            meta = json.load(f)
        diag = meta["diagnostics"]
        rt = diag.get("runtime_s_forward")
        head = (f"{be}  |  {rt:.2f}s/inf  "
                f"FBvalid {diag['fb_valid_coverage_pct']:.1f}%  "
                f"warpMAE {diag['warp_residual_linear_over_fb_valid']['mae']:.4f}  "
                f"|flow|med {diag['flow_magnitude_px']['median']:.1f}px")
        tiles = [_tile(os.path.join(d, p), lbl, TILE_W, tile_h) for p, lbl in ROW_PANELS]
        row = _row(tiles)
        bar = np.full((28, row.shape[1], 3), 60, np.uint8)
        cv2.putText(bar, head, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.52,
                    (255, 255, 255), 1, cv2.LINE_AA)
        rows.append(np.vstack([bar, row]))

    sheet = np.vstack([np.vstack([r, np.zeros((PAD * 2, r.shape[1], 3), np.uint8)])
                       for r in rows])
    title = np.full((34, sheet.shape[1], 3), 15, np.uint8)
    cv2.putText(title, f"{clip}  {pair_dirname}   (960x540 evaluation grid)",
                (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    sheet = np.vstack([title, sheet])

    if os.path.exists(out_path) and not overwrite:
        raise FileExistsError(f"{out_path!r} exists; pass --overwrite")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    cv2.imwrite(out_path, sheet)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="outputs/flow_comparison")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    root = os.path.join(_REPO, args.root)
    out_root = os.path.join(root, "_contact_sheets")

    base = os.path.join(root, BACKENDS[0])
    for clip in sorted(os.listdir(base)):
        cdir = os.path.join(base, clip)
        if not os.path.isdir(cdir):
            continue
        for pd in sorted(os.listdir(cdir)):
            if not pd.startswith("pair_"):
                continue
            out = os.path.join(out_root, f"{clip}__{pd}.png")
            print(build(clip, pd, root, out, args.overwrite))


if __name__ == "__main__":
    main()
