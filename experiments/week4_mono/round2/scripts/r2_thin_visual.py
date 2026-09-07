"""Round 2 §18 — the MANDATORY visual inspection of the crane-lattice region.

CLAUDE.md invariant 5: a metric improvement is never an experiment result until
someone has looked at the picture. The numbers in `r2_thin_structure.py` say
which arms separate the lattice from the sea behind it; this says what that
looks like, which is the only way to tell "resolves the openings" from
"produces a noisy field that happens to differ across them".

Each arm is rendered on its OWN aligned range field, log-scaled between the 2nd
and 98th percentile OF THAT ARM inside the crop. That is deliberate: a shared
absolute colour scale would make every arm whose far field differs from the
reference's look uniformly wrong and hide the only thing this crop is about,
which is whether the OPENINGS are separated from the MEMBERS at all.

    experiments/week4_mono/.venv-eval/bin/python \\
        -m experiments.week4_mono.round2.scripts.r2_thin_visual --overwrite
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import cv2
import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                         "..", "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week4_mono.round1 import armio, common, evalgrid, monoio, policy  # noqa: E402
from experiments.week4_mono.round2.scripts import r2_thin_annotate as ANN  # noqa: E402
from experiments.week4_mono.round2.scripts import r2_thin_structure as TS  # noqa: E402

CLIP = ANN.CLIP
#: The crop, in source pixels: the crane/davit lattice silhouetted against open
#: water. Fixed for every frame and every arm so the panels are comparable.
CROP = (0, 540, 620, 1280)          # y0, y1, x0, x1
TILE_W = 330


def colourise(r: np.ndarray) -> np.ndarray:
    ok = np.isfinite(r) & (r > 0)
    out = np.zeros(r.shape + (3,), np.uint8)
    if not ok.any():
        return out
    lg = np.log(np.where(ok, r, 1.0))
    lo, hi = np.percentile(lg[ok], [2, 98])
    n = np.clip((lg - lo) / max(hi - lo, 1e-6), 0, 1)
    c = cv2.applyColorMap((255 * (1 - n)).astype(np.uint8), cv2.COLORMAP_TURBO)
    out[ok] = c[ok]
    return out


def label(img, text):
    cv2.rectangle(img, (0, 0), (img.shape[1], 16), (0, 0, 0), -1)
    cv2.putText(img, text, (3, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.36,
                (255, 255, 255), 1, cv2.LINE_AA)
    return img


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--frames", nargs="*", type=int, default=[59, 109])
    ap.add_argument("--arms", nargs="*")
    ap.add_argument("--policy", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "R2_S3_policy.json"))
    ap.add_argument("--root", default=os.path.join(common.OUTPUTS, "predictions"))
    ap.add_argument("--out", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "outputs", "thin"))
    ap.add_argument("--crop", nargs=4, type=int, default=list(CROP),
                    metavar=("Y0", "Y1", "X0", "X1"))
    ap.add_argument("--tile", type=int, default=TILE_W)
    ap.add_argument("--tag", default="ranges")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    pol = policy.Policy.load(args.policy)
    arms = list(args.arms or list(pol.entries) + ["pxdepth"])
    for arm in arms:
        if arm not in pol.entries:
            e = TS.provisional_entry(armio.arm_model(arm), args.root)
            if e is not None:
                pol.entries[arm] = e
    arms = [a for a in arms if a in pol.entries
            and monoio.exists(args.root, armio.arm_model(a), CLIP)
            and a not in ("fg_pre_ray", "fg_post_ray")]

    y0, y1, x0, x1 = args.crop
    tw = args.tile
    fits = {a: TS.clip_fit(a, pol, args.root) for a in arms}
    ref = evalgrid.ReferenceClip(CLIP, downsample=1)

    for fi in args.frames:
        rgb = cv2.imread(common.frame_path(CLIP, fi))[y0:y1, x0:x1]
        r, ok = ref.load(fi)
        panels = [label(cv2.resize(rgb, (tw, int(tw * (y1 - y0) / (x1 - x0)))),
                        f"RGB  {CLIP} f{fi:06d}"),
                  label(cv2.resize(colourise(np.where(ok, r, np.nan))[y0:y1, x0:x1],
                                   (tw, int(tw * (y1 - y0) / (x1 - x0)))),
                        "week3 reference (PROVISIONAL)")]
        for a in arms:
            arm = armio.Arm(a, CLIP, args.root, downsample=1)
            fd = arm.frame(fi)
            rr = pol.to_range(a, fd["native"], fits[a], fd["secant"])
            rr = np.where(fd["native_valid"], rr, np.nan)
            panels.append(label(cv2.resize(
                colourise(rr)[y0:y1, x0:x1],
                (tw, int(tw * (y1 - y0) / (x1 - x0)))), a))
            del arm, fd, rr
        cols = 4
        rows = [np.hstack(panels[i:i + cols] + [np.zeros_like(panels[0])] *
                          (cols - len(panels[i:i + cols])))
                for i in range(0, len(panels), cols)]
        sheet = np.vstack(rows)
        p = os.path.join(args.out, f"{args.tag}_f{fi:06d}.png")
        if os.path.exists(p) and not args.overwrite:
            raise SystemExit(f"{p} exists; pass --overwrite")
        cv2.imwrite(p, sheet)
        print("->", p, sheet.shape)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
