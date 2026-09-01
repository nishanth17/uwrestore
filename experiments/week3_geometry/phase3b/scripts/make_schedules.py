"""3B-4 — build nested frame schedules over the ALREADY EXTRACTED Phase 3A frames.

EXPLORATORY. Main project venv (stdlib only).

The question is whether the classical reconstruction changes materially when 48
video observations are replaced by fewer views spanning the SAME temporal extent.
So nothing may be re-extracted: the schedules are symlinks to the identical PNG
files Phase 3A used, which makes the pixels provably the same and leaves the
frame subset as the only variable.

Schedules, over positions 0..47 in the extracted frame list:

    S48   all 48                                       (= Phase 3A A/run0, reused)
    S25   every 2nd, plus the last:  {0,2,...,46} u {47}
    S13   every 4th, plus the last:  {0,4,...,44} u {47}

    S13 subset-of S25 subset-of S48, and all three share BOTH endpoints.

They are named for their true sizes rather than "24" and "12" because exact
nesting and exact temporal extent were preferred over round numbers. Nesting is
what makes a shape comparison at *shared* observations possible at all; keeping
both endpoints is what makes "same temporal extent" literally true instead of
approximately true. Plain stride-2 and stride-4 would have ended at positions 46
and 44, shortening the span by 2 % and 6 %.

One thing this experiment cannot separate, and the report says so: the number of
matching pairs falls quadratically (1128 -> 300 -> 78), so a conditioning change
is a joint effect of sparser sampling and fewer constraints.

Usage:
    .venv/bin/python -m experiments.week3_geometry.phase3b.scripts.make_schedules \
        --clips wreck_05 wreck_01 cenote_01
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
W3 = os.path.join(REPO_ROOT, "experiments", "week3_geometry")
P3B = os.path.join(W3, "phase3b")
FRAMES = os.path.join(W3, "outputs", "frames")
OUT = os.path.join(P3B, "outputs", "frames_schedules")

SCHEDULES = {"S25": 2, "S13": 4}


def positions(n: int, stride: int) -> list[int]:
    """Nested, deterministic, endpoint-preserving positions."""
    pos = sorted(set(range(0, n, stride)) | {n - 1})
    return pos


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clips", nargs="+", required=True)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    record = {
        "_comment": ("3B-4 nested frame schedules. Symlinks to the Phase 3A extracted "
                     "frames -- identical pixels, no re-extraction, so the frame subset is "
                     "the only variable. S13 is a subset of S25 is a subset of S48, and all "
                     "three share both endpoints, so temporal extent is identical and a "
                     "shape comparison at shared observations is well defined."),
        "clips": {},
    }
    for clip in args.clips:
        src = os.path.join(FRAMES, clip)
        if not os.path.isdir(src):
            raise SystemExit(f"no extracted frames at {src!r}")
        files = sorted(f for f in os.listdir(src) if f.endswith(".png"))
        n = len(files)
        entry = {"n_source_frames": n, "schedules": {}}
        # S48 is not materialised: Phase 3A's A/<clip>/run0 already is it.
        entry["schedules"]["S48"] = {
            "n": n,
            "positions": "0..%d (all)" % (n - 1),
            "source_frame_indices": [int(f[1:7]) for f in files],
            "reused_run": f"outputs/colmap/A/{clip}/run0",
            "materialised": False,
        }
        for name, stride in SCHEDULES.items():
            pos = positions(n, stride)
            dst = os.path.join(OUT, f"{clip}_{name}")
            if os.path.exists(dst):
                if not args.overwrite:
                    raise SystemExit(f"refusing to overwrite {dst!r} (pass --overwrite)")
                shutil.rmtree(dst)
            os.makedirs(dst)
            chosen = [files[i] for i in pos]
            for f in chosen:
                os.symlink(os.path.join(src, f), os.path.join(dst, f))
            idxs = [int(f[1:7]) for f in chosen]
            entry["schedules"][name] = {
                "n": len(chosen),
                "stride": stride,
                "positions": pos,
                "source_frame_indices": idxs,
                "temporal_extent_source_frames": idxs[-1] - idxs[0],
                "n_exhaustive_pairs": len(chosen) * (len(chosen) - 1) // 2,
                "image_dir": os.path.relpath(dst, REPO_ROOT),
                "materialised": True,
            }
        # Nesting assertion -- if this ever fails the shape comparison is void.
        s48 = set(entry["schedules"]["S48"]["source_frame_indices"])
        s25 = set(entry["schedules"]["S25"]["source_frame_indices"])
        s13 = set(entry["schedules"]["S13"]["source_frame_indices"])
        assert s13 <= s25 <= s48, f"{clip}: schedules are not nested"
        ext = entry["schedules"]["S48"]["source_frame_indices"]
        assert (min(s13) == min(s25) == ext[0]) and (max(s13) == max(s25) == ext[-1]), \
            f"{clip}: schedules do not share endpoints"
        entry["nesting_verified"] = True
        record["clips"][clip] = entry
        print(f"{clip}: S48={n} S25={len(s25)} S13={len(s13)} "
              f"span={ext[-1] - ext[0]} frames (identical for all three)")

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "schedules.json"), "w") as fh:
        json.dump(record, fh, indent=2)
    print(f"wrote {os.path.relpath(os.path.join(OUT, 'schedules.json'), REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
