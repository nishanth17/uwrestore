"""Stage 1 -> Stage 3/4 bridge: extract the one shared frame set every Phase 3A
configuration consumes.

EXPLORATORY. Not part of the `uw` package. Main project venv (numpy + opencv).

One extraction, one resolution, one set of source frame indices, reused by
configurations A-F. That is what makes the bakeoff a comparison rather than six
unrelated runs: no configuration gets to choose its own frames.

Resampling happens in LINEAR LIGHT (CLAUDE.md invariant 1): decode -> sRGB EOTF
-> INTER_AREA resize on radiance -> inverse EOTF -> 8-bit PNG. Area-averaging is
only physically meaningful on linear radiance. The files are written sRGB-encoded
because COLMAP and every third-party geometry model expect display-referred
images; no restoration measurement is made from them.

Filenames preserve the SOURCE frame index (`f001600.png`), never a renumbered
sequence, so every downstream artifact can be traced back to the clip.

Usage:
    .venv/bin/python -m experiments.week3_geometry.scripts.extract_frames \
        --spec experiments/week3_geometry/configs/phase3a_clips.json \
        --out-root experiments/week3_geometry/outputs/frames
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

import cv2
import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from uw.colorspace import linear_to_srgb, srgb_to_linear  # noqa: E402

MANIFEST = os.path.join(REPO_ROOT, "data", "testset", "manifest.json")


def frame_indices(start: int, end: int, n: int) -> list[int]:
    """n unique source frame indices evenly spanning [start, end] inclusive."""
    if n < 1:
        raise ValueError("n_frames must be >= 1")
    if end < start:
        raise ValueError(f"end {end} < start {start}")
    return sorted({int(round(v)) for v in np.linspace(start, end, n)})


def out_size(h: int, w: int, long_side: int) -> tuple[int, int]:
    """(out_h, out_w) with the long side set to `long_side`, orientation kept."""
    if w >= h:
        return int(round(long_side * h / w)), long_side
    return long_side, int(round(long_side * w / h))


def extract_clip(video_path: str, indices: list[int], long_side: int,
                 out_dir: str, overwrite: bool) -> dict:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"failed to open {video_path!r}")
    os.makedirs(out_dir, exist_ok=True)
    want = set(indices)
    written = []
    src_shape = None
    dst_shape = None
    try:
        i = 0
        while len(written) < len(indices):
            if not cap.grab():
                break
            if i in want:
                ok, bgr = cap.retrieve()
                if not ok:
                    break
                if src_shape is None:
                    src_shape = list(bgr.shape[:2])
                oh, ow = out_size(bgr.shape[0], bgr.shape[1], long_side)
                dst_shape = [oh, ow]
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
                linear = srgb_to_linear(rgb)
                small = cv2.resize(linear, (ow, oh), interpolation=cv2.INTER_AREA)
                enc = np.clip(linear_to_srgb(small) * 255.0 + 0.5, 0, 255).astype(np.uint8)
                path = os.path.join(out_dir, f"f{i:06d}.png")
                if os.path.exists(path) and not overwrite:
                    raise SystemExit(f"refusing to overwrite {path!r} (pass --overwrite)")
                cv2.imwrite(path, cv2.cvtColor(enc, cv2.COLOR_RGB2BGR))
                written.append(i)
            i += 1
    finally:
        cap.release()
    missing = sorted(want - set(written))
    if missing:
        raise IOError(f"{video_path!r}: could not decode frames {missing[:5]}"
                      f"{'...' if len(missing) > 5 else ''}")
    h = hashlib.sha256()
    for idx in written:
        with open(os.path.join(out_dir, f"f{idx:06d}.png"), "rb") as fh:
            h.update(fh.read())
    return {
        "n_written": len(written),
        "source_frame_indices": written,
        "source_decoded_shape_hw": src_shape,
        "extracted_shape_hw": dst_shape,
        "frame_set_sha256": h.hexdigest(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--clips", nargs="*", default=None, help="subset of spec clip ids")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    with open(args.spec) as fh:
        spec = json.load(fh)
    with open(MANIFEST) as fh:
        by_id = {c["id"]: c for c in json.load(fh)["clips"]}

    ex = spec["extraction"]
    report = {"spec": os.path.relpath(os.path.abspath(args.spec), REPO_ROOT),
              "extraction": ex, "clips": {}}
    for c in spec["clips"]:
        if args.clips and c["id"] not in args.clips:
            continue
        clip = by_id[c["id"]]
        idxs = frame_indices(c["start"], c["end"], ex["n_frames"])
        out_dir = os.path.join(args.out_root, c["id"])
        print(f"extracting {c['id']}: {len(idxs)} frames "
              f"[{idxs[0]}..{idxs[-1]}] -> {out_dir}", flush=True)
        info = extract_clip(os.path.join(REPO_ROOT, clip["local_path"]),
                            idxs, ex["long_side"], out_dir, args.overwrite)
        info["clip_local_path"] = clip["local_path"]
        info["start"] = c["start"]
        info["end"] = c["end"]
        report["clips"][c["id"]] = info
        print(f"  -> {info['extracted_shape_hw']} from {info['source_decoded_shape_hw']}"
              f"  sha256[:12]={info['frame_set_sha256'][:12]}")

    out_json = os.path.join(args.out_root, "extraction_report.json")
    if os.path.exists(out_json) and not args.overwrite:
        raise SystemExit(f"refusing to overwrite {out_json!r} (pass --overwrite)")
    with open(out_json, "w") as fh:
        json.dump(report, fh, indent=2)
    print(f"wrote {out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
