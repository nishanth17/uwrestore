#!/usr/bin/env python3
"""Strict N=1 NATIVE PXDepth inference -- no helper model in the path.

PXDepth's network emits a single affine-invariant scalar field in log1p(depth)
space plus a finite-depth logit.  The repo's ``model.infer()`` /
``scripts/infer.py`` / ``app.py`` entry points additionally load MoGe-2 to fit
the (scale, shift) that turns that field into metric depth and to supply camera
intrinsics.  That is an EXTERNAL PRIOR, so this script deliberately bypasses it
and calls the model-native path only:

    resize_image(...)  ->  PXDepth.forward(...)  ->  resize_map(...)

which is exactly the body of the repo's own MoGe-free evaluation entry point
``pxdepth/inference/runner.py::predict_raw``.  ``moge`` is never imported; the
script asserts that at the end of the run.

Usage
-----
    round2/.venv-pxdepth/bin/python round2/s0_agent/pxdepth/infer_one.py \
        --image <path> --out <dir>

Outputs (in --out):
    depth_log1p_affine_invariant.npy  float32 [H,W]  NATIVE scalar, source res
    mask.npy                          bool    [H,W]  validity, source res
    mask_prob.npy                     float32 [H,W]  finite-depth prob, source res
    depth_log1p_native_res.npy        float32 [h,w]  NATIVE scalar, model res
    mask_prob_native_res.npy          float32 [h,w]  finite-depth prob, model res
    meta.json
"""

import argparse
import json
import os
import resource
import sys
import time
from pathlib import Path

import numpy as np
import torch

# --- repo on the path -------------------------------------------------------
REPO = Path(
    os.environ.get(
        "PXDEPTH_REPO",
        Path(__file__).resolve().parents[2] / "vendor" / "PXDepth",
    )
).resolve()
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

DEFAULT_CKPT = REPO / "checkpoints" / "pxdepth" / "model.pt"


# --- 1. model loading (kept separable for the production backend) -----------
def load_model(checkpoint, device="mps"):
    """Load the released PXDepth checkpoint in float32 on `device`."""
    from pxdepth.model import PXDepth

    t0 = time.perf_counter()
    model = PXDepth.from_pretrained(str(checkpoint), strict=True)
    model = model.float().to(device).eval()
    return model, time.perf_counter() - t0


# --- 2. the one forward pass ------------------------------------------------
@torch.inference_mode()
def forward_native(model, image_chw, input_size=(1022, 770), resize_by_area=True):
    """One image in, one NATIVE prediction out.

    Mirrors pxdepth/inference/runner.py::predict_raw exactly, but also returns
    the field at model resolution (predict_raw only returns it resized back to
    the source resolution).  No alignment, no intrinsics, no reference model.
    """
    from pxdepth.inference import resize_image, resize_map

    model_image, original_size = resize_image(
        image_chw, input_size, resize_by_area, model.patch_size
    )
    model_input = model_image.unsqueeze(0).to(device=model.device, dtype=torch.float32)

    t0 = time.perf_counter()
    out = model.forward(model_input, use_fp16=False, use_fp32=True)
    if model.device.type == "mps":
        torch.mps.synchronize()
    elapsed = time.perf_counter() - t0

    depth_native = out["depth_log1p_affine_invariant"][0]  # [h,w] model res
    prob_native = out["mask"][0]                           # [h,w] model res

    depth_src = resize_map(out["depth_log1p_affine_invariant"], original_size)[0]
    prob_src = resize_map(out["mask"], original_size)[0]
    mask_src = resize_map(out["mask"], original_size, is_mask=True)[0]

    return {
        "depth_log1p_affine_invariant": depth_src,
        "mask": mask_src,
        "mask_prob": prob_src,
        "depth_log1p_native_res": depth_native,
        "mask_prob_native_res": prob_native,
        "model_input_hw": tuple(model_input.shape[-2:]),
        "source_hw": tuple(original_size),
        "forward_s": elapsed,
    }


def load_image(path):
    """Read an image as a float32 CHW RGB tensor in [0,1] (as scripts/infer.py)."""
    import cv2

    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise SystemExit(f"unreadable image: {path}")
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return torch.from_numpy(rgb.astype(np.float32) / 255.0).permute(2, 0, 1), rgb


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--image", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--checkpoint", default=str(DEFAULT_CKPT))
    ap.add_argument("--device", default="mps", choices=["mps", "cpu"])
    ap.add_argument("--input-size", default="1022x770", help="WIDTHxHEIGHT reference")
    ap.add_argument("--fixed-size", action="store_true",
                    help="Force exact --input-size instead of the default equal-area policy.")
    ap.add_argument("--png", default=None, help="Optional path for a colourised preview.")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    from pxdepth.inference import parse_size

    out = Path(args.out)
    if out.exists() and any(out.iterdir()) and not args.overwrite:
        raise SystemExit(f"refusing to overwrite non-empty {out} (use --overwrite)")
    out.mkdir(parents=True, exist_ok=True)

    torch.manual_seed(0)
    image_chw, _rgb = load_image(args.image)
    model, load_s = load_model(args.checkpoint, args.device)

    res = forward_native(
        model,
        image_chw,
        input_size=parse_size(args.input_size),
        resize_by_area=not args.fixed_size,
    )

    def save(name, tensor, dtype):
        arr = tensor.detach().cpu().numpy().astype(dtype)
        np.save(out / f"{name}.npy", arr)
        return arr

    depth = save("depth_log1p_affine_invariant", res["depth_log1p_affine_invariant"], np.float32)
    mask = save("mask", res["mask"], np.bool_)
    save("mask_prob", res["mask_prob"], np.float32)
    save("depth_log1p_native_res", res["depth_log1p_native_res"], np.float32)
    save("mask_prob_native_res", res["mask_prob_native_res"], np.float32)

    peak_rss_gb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9
    peak_mps_gb = (
        torch.mps.driver_allocated_memory() / 1e9 if args.device == "mps" else 0.0
    )

    meta = {
        "model": "PXDepth",
        "checkpoint": str(args.checkpoint),
        "image": str(args.image),
        "native_kind": "depth_relative",
        "native_field": "depth_log1p_affine_invariant",
        "native_semantics": (
            "affine-invariant scalar in log1p(z-depth) space; metric depth = "
            "expm1(scale * pred + shift) with (scale, shift) UNKNOWN to the model"
        ),
        "scalar_convention": "z_depth",
        "legal_ambiguity": "scale+shift in log1p(depth) space",
        "predicts_camera": False,
        "camera": None,
        "source_hw": list(res["source_hw"]),
        "model_input_hw": list(res["model_input_hw"]),
        "output_hw_native": list(res["depth_log1p_native_res"].shape),
        "output_hw_saved": list(depth.shape),
        "restore_interpolation": "nearest (pxdepth/inference/resize.py:156)",
        "mask_semantics": "finite-depth probability > 0.5 (model.mask_threshold)",
        "mask_valid_fraction": float(mask.mean()),
        "device": args.device,
        "dtype": "float32",
        "autocast": "disabled (use_fp32=True; reduced_precision() is a no-op off CUDA)",
        "torch": torch.__version__,
        "load_s": round(load_s, 3),
        "forward_s": round(res["forward_s"], 3),
        "peak_rss_gb": round(peak_rss_gb, 3),
        "peak_mps_driver_gb": round(peak_mps_gb, 3),
        "helper_model_used": False,
        "moge_imported": "moge" in sys.modules,
        "depth_log1p_min": float(np.nanmin(depth)),
        "depth_log1p_max": float(np.nanmax(depth)),
    }
    assert not meta["moge_imported"], "MoGe was imported -- native attribution broken"
    (out / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")

    if args.png:
        from pxdepth.utils.vis import colorize_depth_affine
        import cv2

        vis = colorize_depth_affine(depth, mask=mask)
        Path(args.png).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(args.png), cv2.cvtColor(vis, cv2.COLOR_RGB2BGR))

    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
