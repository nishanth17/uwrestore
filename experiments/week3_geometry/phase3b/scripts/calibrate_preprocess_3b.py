"""Phase 3B — measure the source-pixel -> model-grid map for a Phase 3B dense model.

EXPLORATORY. Runs inside the model's own venv.

Same method and the same marker code as Phase 3A's `calibrate_preprocess.py`:
push synthetic marker images through the model's OWN preprocessing and fit

    u_model = a * u_source + b
    v_model = c * v_source + d

with the per-axis residual reported, so a non-affine mapping would show up
instead of being hidden by the fit. Phase 3A caught a 44 % vertical field-of-view
loss on the portrait clip this way; it is not a step to skip.

Written to a **Phase 3B-owned file**, `phase3b/outputs/preprocess_maps_3b.json`.
Phase 3A's `outputs/preprocess_maps.json` is never modified — the analysis merges
the two at read time, Phase 3A's entries winning any name collision.

Usage:
    experiments/week3_geometry/.venv-any4d/bin/python \
        -m experiments.week3_geometry.phase3b.scripts.calibrate_preprocess_3b --family any4d
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week3_geometry.scripts.calibrate_preprocess import (  # noqa: E402
    SOURCE_SIZES,
    fit_affine,
    locate,
    marker_images,
)

W3 = os.path.join(REPO_ROOT, "experiments", "week3_geometry")
OUT = os.path.join(W3, "phase3b", "outputs", "preprocess_maps_3b.json")


def grids_for(family: str, paths: list[str]) -> list[np.ndarray]:
    if family == "any4d":
        from any4d.utils.image import load_images
        # compute_moge_mask=False: the MoGe mask is a visualisation / scene-flow
        # post-processing input, never a model input (the model's REQUIRED_KEYS
        # are {"img", "data_norm_type"}), and with it off the image tensor is
        # produced by exactly the same crop_resize_if_necessary call. So the
        # geometry path being calibrated here is the released one.
        views = load_images(paths, size=(518, 336), norm_type="dinov2",
                            patch_size=14, compute_moge_mask=False)
        return [np.asarray(v["img"])[0] for v in views]
    raise ValueError(family)


def run_family(family: str) -> dict:
    result = {}
    for (h, w) in SOURCE_SIZES:
        with tempfile.TemporaryDirectory() as td:
            items = marker_images(h, w, td)
            grids = grids_for(family, [p for p, _, _ in items])
            src, dst, missed = [], [], 0
            for g, (_, u, v) in zip(grids, items):
                loc = locate(np.asarray(g).mean(axis=0))
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
                "note": ("Markers falling outside the grid after cropping are reported as "
                         "lost, not silently dropped: they measure how much field of view "
                         "the preprocessing discards."),
            })
            result[f"{h}x{w}"] = fit
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--family", required=True, choices=["any4d"])
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    data = {}
    if os.path.exists(args.out):
        with open(args.out) as fh:
            data = json.load(fh)
    data.setdefault("_comment", (
        "Phase 3B measured source-pixel -> model-grid affine maps, obtained by pushing "
        "marker images through each model's OWN preprocessing. Separate file from Phase "
        "3A's outputs/preprocess_maps.json, which is never modified; the analysis merges "
        "them at read time with Phase 3A's entries winning any collision."))
    data[args.family] = run_family(args.family)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(data, fh, indent=2)
    print(json.dumps({args.family: data[args.family]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
