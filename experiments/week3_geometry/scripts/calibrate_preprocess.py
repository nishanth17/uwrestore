"""Stage 2 support — measure, don't guess, how each dense model's preprocessing
maps SOURCE image coordinates onto its inference grid.

EXPLORATORY. Runs inside whichever model venv is being calibrated.

WHY THIS EXISTS. The dense-vs-sparse comparison samples a dense range field at
the image observation recorded by a classical reconstruction. That observation
lives on the 1280x720 (or 720x1280) extracted frame; the dense field lives on
the model's own grid. Both model families resize AND centre-crop to get there —
VGGT/Wat3R round the resized height to a multiple of 14 and centre-crop it to
518 when it overflows, MapAnything Lanczos-rescales to an aspect-ratio-mapped
resolution and then centre-crops. Reconstructing those rules from the source
would be exactly the kind of silent convention error that makes a cross-family
comparison meaningless.

So instead this measures the mapping using the models' OWN preprocessing
functions: push synthetic images carrying a bright marker at a known source
pixel through the real code path, find where the marker landed, and fit

    u_model = a * u_source + b
    v_model = c * v_source + d

A separate residual is reported; if the true mapping were not affine (it is:
isotropic-ish rescale plus an axis-aligned centred crop) the residual would
expose it rather than the fit hiding it.

Usage (one call per model venv):
    .venv-mapanything/bin/python -m experiments.week3_geometry.scripts.calibrate_preprocess \
        --family mapanything --out .../preprocess_maps.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile

import numpy as np
from PIL import Image

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

W3 = os.path.join(REPO_ROOT, "experiments", "week3_geometry")

# The two source geometries in the Phase 3A subset.
SOURCE_SIZES = [(720, 1280), (1280, 720)]
MARKER = 7          # odd, so the marker has an exact centre pixel
FRACTIONS = [0.12, 0.30, 0.5, 0.70, 0.88]


def marker_images(h: int, w: int, tmpdir: str) -> list[tuple[str, float, float]]:
    """One black image per marker position, marker centred on a known pixel."""
    out = []
    r = MARKER // 2
    for fy in FRACTIONS:
        for fx in FRACTIONS:
            u = int(round(fx * (w - 1)))
            v = int(round(fy * (h - 1)))
            u = min(max(u, r), w - 1 - r)
            v = min(max(v, r), h - 1 - r)
            img = np.zeros((h, w, 3), dtype=np.uint8)
            img[v - r:v + r + 1, u - r:u + r + 1] = 255
            p = os.path.join(tmpdir, f"m_{v:04d}_{u:04d}.png")
            Image.fromarray(img).save(p)
            out.append((p, float(u), float(v)))
    return out


def locate(arr: np.ndarray) -> tuple[float, float] | None:
    """Intensity-weighted centroid of the marker in a (H,W) response map."""
    a = arr.astype(np.float64)
    lo, hi = float(a.min()), float(a.max())
    if hi - lo < 1e-6:
        return None
    m = a >= (hi - 0.25 * (hi - lo))
    if m.sum() == 0:
        return None
    ys, xs = np.nonzero(m)
    wgt = a[ys, xs] - lo
    if wgt.sum() <= 0:
        return None
    return float((xs * wgt).sum() / wgt.sum()), float((ys * wgt).sum() / wgt.sum())


def fit_affine(src: np.ndarray, dst: np.ndarray) -> dict:
    """Independent per-axis linear fits with residuals."""
    out = {}
    for k, axis in enumerate(("u", "v")):
        A = np.stack([src[:, k], np.ones(len(src))], axis=1)
        coef, *_ = np.linalg.lstsq(A, dst[:, k], rcond=None)
        pred = A @ coef
        out[f"{axis}_scale"] = float(coef[0])
        out[f"{axis}_offset"] = float(coef[1])
        out[f"{axis}_max_abs_residual_px"] = float(np.abs(pred - dst[:, k]).max())
    return out


def run_family(family: str) -> dict:
    result = {}
    for (h, w) in SOURCE_SIZES:
        with tempfile.TemporaryDirectory() as td:
            items = marker_images(h, w, td)
            paths = [p for p, _, _ in items]
            if family == "mapanything":
                from mapanything.utils.image import load_images
                views = load_images(paths)
                grids = [np.asarray(v["img"])[0] for v in views]     # (3,H,W)
            elif family == "vggt":
                sys.path.insert(0, os.path.join(W3, "vendor", "vggt"))
                from vggt.utils.load_fn import load_and_preprocess_images
                t = load_and_preprocess_images(paths, mode="crop")
                grids = [t[i].numpy() for i in range(t.shape[0])]
            elif family == "wat3r_ren":
                sys.path.insert(0, os.path.join(W3, "vendor", "Wat3R"))
                from wat3r.utils.load_fn import load_and_preprocess_images
                t = load_and_preprocess_images(paths, mode="crop")
                grids = [t[i].numpy() for i in range(t.shape[0])]
            else:
                raise ValueError(family)

            src, dst = [], []
            missed = 0
            for g, (_, u, v) in zip(grids, items):
                resp = np.asarray(g).mean(axis=0)
                loc = locate(resp)
                if loc is None:
                    missed += 1
                    continue
                src.append([u, v])
                dst.append([loc[0], loc[1]])
            if not src:
                result[f"{h}x{w}"] = {"error": "no markers located"}
                continue
            gh, gw = np.asarray(grids[0]).shape[-2:]
            fit = fit_affine(np.asarray(src), np.asarray(dst))
            fit.update({
                "source_hw": [h, w],
                "model_grid_hw": [int(gh), int(gw)],
                "n_markers_used": len(src),
                "n_markers_lost_to_crop": missed,
                "note": ("Markers that fall outside the model grid after cropping are "
                         "reported as lost rather than silently dropped: they are direct "
                         "evidence of how much field of view the preprocessing discards."),
            })
            result[f"{h}x{w}"] = fit
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--family", required=True, choices=["mapanything", "vggt", "wat3r_ren"])
    ap.add_argument("--out", default=os.path.join(W3, "outputs", "preprocess_maps.json"))
    args = ap.parse_args()

    data = {}
    if os.path.exists(args.out):
        with open(args.out) as fh:
            data = json.load(fh)
    data.setdefault("_comment", (
        "Measured source-pixel -> model-grid affine maps for the Phase 3A dense "
        "models, obtained by pushing marker images through each model's OWN "
        "preprocessing code. Used by the dense-vs-sparse comparison to place a "
        "classical reconstruction's image observations onto the dense grid. "
        "Not derived from documentation or from reading the source."))
    data[args.family] = run_family(args.family)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(data, fh, indent=2)
    print(json.dumps({args.family: data[args.family]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
