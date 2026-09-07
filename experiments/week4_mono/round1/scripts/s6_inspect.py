"""S6 — the MANDATORY visual inspection renders.

EXPLORATORY. Runs in `.venv-eval`.

`CLAUDE.md` invariant 5 is not advisory: a metric improvement is not a
successful experiment until the output has been looked at for hallucinated
detail, broken scene identity and unnatural colour relationships. FREEZE §5 S6
names the specific things to look for:

    backscatter / particles turned into depth structure
    marine snow
    caustics
    animal boundaries
    artificial-light regions
    far-field range collapse
    colour pumping caused by temporal range drift
    thin structures

Two kinds of render, because they fail differently.

  SHEETS — one row per arm, over a few frames per clip: the source frame, the
  arm's range, its disagreement with the Week-3 reference, and the restoration
  it drives. This is where far-field collapse, a broken scene identity and a
  wrong overall colour show up.

  WORST-DISAGREEMENT CROPS — the tiles where the arm and the reference disagree
  most, magnified. This is where particulate-turned-into-geometry and invented
  thin structure show up, and it is chosen by the data rather than by whoever is
  looking, so it cannot be a flattering crop.

Range images use a shared per-clip colour scale taken from the REFERENCE, so two
arms rendered side by side are directly comparable and a model cannot look
better by being on its own scale.

    experiments/week4_mono/.venv-eval/bin/python \\
        -m experiments.week4_mono.round1.scripts.s6_inspect --arms moge2_vitl --overwrite
"""

from __future__ import annotations

import argparse
import gc
import os
import sys

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week4_mono.round1 import armio, common, evalgrid, policy  # noqa: E402
from experiments.week4_mono.round1.scripts.s6_restoration import (  # noqa: E402
    REFERENCE_ARM, reference_source_range, source_range)

TILE_W = 320


def colorize(field, valid, lo, hi):
    import cv2
    x = np.clip((np.asarray(field, dtype=np.float64) - lo) / max(hi - lo, 1e-9), 0, 1)
    img = cv2.applyColorMap((x * 255).astype(np.uint8), cv2.COLORMAP_TURBO)
    img[~np.asarray(valid, bool)] = (40, 40, 40)   # holes are grey, never a colour
    return img


#: A blue-white-red diverging LUT, built here rather than taken from OpenCV
#: because this build has no COOLWARM. Signed error needs a map whose midpoint
#: is visually neutral: on a sequential map like TURBO a zero would read as a
#: colour and "no disagreement" would look like a feature.
def _diverging_lut():
    import cv2
    t = np.linspace(-1.0, 1.0, 256)[:, None]
    neg = np.array([[0.90, 0.30, 0.20]])          # BGR: cool
    pos = np.array([[0.15, 0.20, 0.85]])          # BGR: warm
    white = np.ones((1, 3))
    w = np.abs(t)
    rgb = np.where(t < 0, white * (1 - w) + neg * w, white * (1 - w) + pos * w)
    return (np.clip(rgb, 0, 1) * 255).astype(np.uint8).reshape(256, 1, 3)


_DIVERGING = None


def signed_map(diff, valid, lim):
    import cv2
    global _DIVERGING
    if _DIVERGING is None:
        _DIVERGING = _diverging_lut()
    x = np.clip((np.asarray(diff, dtype=np.float64) + lim) / (2 * lim), 0, 1)
    img = cv2.applyColorMap((x * 255).astype(np.uint8), _DIVERGING)
    img[~np.asarray(valid, bool)] = (40, 40, 40)
    return img


def label(img, text):
    import cv2
    out = img.copy()
    cv2.rectangle(out, (0, 0), (out.shape[1], 22), (0, 0, 0), -1)
    cv2.putText(out, text, (5, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1,
                cv2.LINE_AA)
    return out


def fit_w(img, w=TILE_W):
    import cv2
    h = int(round(img.shape[0] * w / img.shape[1]))
    return cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)


def main() -> int:
    import cv2
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arms", nargs="*", required=True)
    ap.add_argument("--clips", nargs="*", default=None)
    ap.add_argument("--frames-per-clip", type=int, default=3)
    ap.add_argument("--root", default=os.path.join(common.OUTPUTS, "predictions"))
    ap.add_argument("--restored-root", default=os.path.join(common.OUTPUTS, "s6", "restored"))
    ap.add_argument("--policy", default=os.path.join(common.RESULTS,
                                                     "S2_alignment_policy.json"))
    ap.add_argument("--out-root", default=os.path.join(common.OUTPUTS, "s6", "inspect"))
    ap.add_argument("--n-crops", type=int, default=4)
    ap.add_argument("--crop", type=int, default=128)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    pol = policy.Policy.load(args.policy)
    clips = args.clips or common.CLIPS
    os.makedirs(args.out_root, exist_ok=True)
    manifest = {"clips": {}, "what_to_look_for": [
        "backscatter or particles turned into depth structure",
        "marine snow", "caustics", "animal boundaries",
        "artificial-light regions", "far-field range collapse",
        "thin structures", "colour pumping across frames"]}

    for clip in clips:
        source_hw = common.clip_source_hw(clip)
        frames_all = common.frame_indices(clip)
        pick = [frames_all[int(round(f * (len(frames_all) - 1)))]
                for f in np.linspace(0.15, 0.85, args.frames_per_clip)]

        # One colour scale per clip, from the REFERENCE, so arms are comparable.
        d0, ok0 = reference_source_range(clip, pick[0], source_hw)
        lo, hi = np.percentile(d0[ok0], [2, 98])
        del d0, ok0

        arms_open = {k: armio.Arm(k, clip, args.root) for k in args.arms}
        fits = {}
        for k, a in arms_open.items():
            rngen = np.random.default_rng(0)
            n_, r_, z_ = [], [], []
            for fi in a.frames:
                fd = a.frame(fi)
                ok = fd["native_valid"] & fd["ref_valid"]
                idx = np.flatnonzero(ok.ravel())
                if idx.size:
                    take = idx if idx.size <= 4000 else rngen.choice(idx, 4000, replace=False)
                    n_.append(fd["native"].ravel()[take])
                    r_.append(fd["ref_range"].ravel()[take])
                    z_.append(fd["ref_z"].ravel()[take])
                del fd
            fits[k] = pol.fit_clip(k, np.concatenate(n_), np.concatenate(r_),
                                   np.concatenate(z_))
            del n_, r_, z_

        crec = {"frames": pick, "range_scale": [float(lo), float(hi)], "sheets": [],
                "crops": []}
        for fi in pick:
            src = cv2.imread(common.frame_path(clip, fi))
            d_ref, ok_ref = reference_source_range(clip, fi, source_hw)
            rows = [np.hstack([
                fit_w(label(src, f"{clip} f{fi:06d} source")),
                fit_w(label(colorize(d_ref, ok_ref, lo, hi), "Week-3 reference range")),
                fit_w(label(np.full_like(src, 40), "")),
                fit_w(label(_restored(args.restored_root, clip, REFERENCE_ARM, fi, src),
                            "restored / reference range")),
            ])]
            for k in args.arms:
                d, okd = source_range(arms_open[k], fi, pol, fits[k], source_hw)
                both = okd & ok_ref
                with np.errstate(invalid="ignore", divide="ignore"):
                    rel = np.where(both, (d - d_ref) / np.where(d_ref > 0, d_ref, np.nan), np.nan)
                rows.append(np.hstack([
                    fit_w(label(src, f"{k}")),
                    fit_w(label(colorize(d, okd, lo, hi), f"{k} range (shared scale)")),
                    fit_w(label(signed_map(np.nan_to_num(rel), both, 0.5),
                                "rel. disagreement +/-50%")),
                    fit_w(label(_restored(args.restored_root, clip, k, fi, src),
                                f"restored / {k} range")),
                ]))
                # worst-disagreement crops, chosen by the data
                crec["crops"] += _crops(args, clip, k, fi, src, d, d_ref, both, lo, hi)
                del d, okd, both, rel
            sheet = np.vstack(rows)
            dst = os.path.join(args.out_root, f"{clip}_f{fi:06d}_sheet.png")
            common.refuse_clobber(dst, True)
            cv2.imwrite(dst, sheet)
            crec["sheets"].append(os.path.relpath(dst, REPO_ROOT))
            print(f"[S6-inspect] {os.path.relpath(dst, REPO_ROOT)}")
            del src, d_ref, ok_ref, rows, sheet
            gc.collect()
        manifest["clips"][clip] = crec
        del arms_open
        gc.collect()

    common.write_json(os.path.join(args.out_root, "manifest.json"), manifest,
                      overwrite=True)
    return 0


def _restored(root, clip, arm, fi, fallback):
    import cv2
    p = os.path.join(root, clip, arm, f"f{fi:06d}.png")
    img = cv2.imread(p) if os.path.exists(p) else None
    return img if img is not None else np.full_like(fallback, 40)


def _crops(args, clip, arm, fi, src, d, d_ref, both, lo, hi):
    """Magnify the tiles where this arm and the reference disagree MOST.

    Chosen by the data, not by whoever is looking, so it cannot be a flattering
    crop. This is where particulate turned into geometry and invented thin
    structure become visible.
    """
    import cv2
    c = args.crop
    h, w = d.shape
    with np.errstate(invalid="ignore", divide="ignore"):
        rel = np.abs(np.where(both, (d - d_ref) / np.where(d_ref > 0, d_ref, np.nan), np.nan))
    ny, nx = h // c, w // c
    if ny < 1 or nx < 1:
        return []
    tiles = rel[:ny * c, :nx * c].reshape(ny, c, nx, c)
    score = np.nanmedian(tiles, axis=(1, 3))
    score = np.nan_to_num(score, nan=-1.0)
    order = np.dstack(np.unravel_index(np.argsort(-score, axis=None), score.shape))[0]
    out = []
    for (iy, ix) in order[:args.n_crops]:
        y0, x0 = int(iy) * c, int(ix) * c
        panel = np.hstack([
            fit_w(label(src[y0:y0 + c, x0:x0 + c], f"src {iy},{ix}"), 220),
            fit_w(label(colorize(d_ref[y0:y0 + c, x0:x0 + c],
                                 both[y0:y0 + c, x0:x0 + c], lo, hi), "reference"), 220),
            fit_w(label(colorize(d[y0:y0 + c, x0:x0 + c],
                                 both[y0:y0 + c, x0:x0 + c], lo, hi),
                        f"{arm} ({score[iy, ix]:.2f})"), 220),
        ])
        dst = os.path.join(args.out_root,
                           f"{clip}_f{fi:06d}_{arm}_crop{int(iy)}_{int(ix)}.png")
        cv2.imwrite(dst, panel)
        out.append({"path": os.path.relpath(dst, REPO_ROOT), "arm": arm,
                    "frame": int(fi), "tile": [int(iy), int(ix)],
                    "median_abs_rel_disagreement": float(score[iy, ix])})
    return out


if __name__ == "__main__":
    raise SystemExit(main())
