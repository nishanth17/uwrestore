"""Backend 2 — Depth Anything V2 Small.

Runs in `experiments/week4_mono/.venv-mono`.

ROLE (FREEZE §3.2): the cheap inverse-depth/disparity control, answering how
damaging affine disparity ambiguity is over this project's working range.

THE TRAP THIS BACKEND EXISTS TO AVOID. DA V2 emits relative INVERSE depth. Its
legal ambiguity is affine in DISPARITY:

    q' = a q + b

Fitting `a d + b` in physical depth instead is a different, illegal transform,
and it flatters the model in some scenes and destroys it in others. So this
backend stores the disparity UNMODIFIED as its native output and reports
`canonical_range = None`. There is no honest range for this model until S2's
alignment policy has fitted `(a, b)` in disparity space; the inversion happens
there, once, under the frozen policy — never here.

`native` is therefore the only product, and any consumer that asks this
backend for a range gets nothing rather than a plausible-looking wrong number.
"""

from __future__ import annotations

import os

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import sys

import numpy as np

from experiments.week4_mono.round1.backends.base import MonoBackend
from experiments.week4_mono.round1.common import W4_ROUND1

CHECKPOINT = "depth-anything/Depth-Anything-V2-Small"
VENDOR = os.path.join(W4_ROUND1, "vendor", "Depth-Anything-V2")

#: The `vits` row of the reference implementation's own `model_configs`.
VITS_CONFIG = {"encoder": "vits", "features": 64, "out_channels": [48, 96, 192, 384]}

#: The reference `run.py` default. Fixed here so it is a recorded constant
#: rather than a per-call choice that could drift between stages.
INPUT_SIZE = 518


class DepthAnythingV2Small(MonoBackend):
    key = "dav2_small"
    checkpoint = CHECKPOINT
    native_kind = "disparity_relative"
    range_rule = "unresolved"

    def _load(self) -> None:
        import torch
        from huggingface_hub import hf_hub_download
        if VENDOR not in sys.path:
            sys.path.insert(0, VENDOR)
        from depth_anything_v2.dpt import DepthAnythingV2
        self._torch = torch
        self._cv2 = __import__("cv2")
        ckpt = hf_hub_download(repo_id=CHECKPOINT, filename="depth_anything_v2_vits.pth")
        self._ckpt_path = ckpt
        model = DepthAnythingV2(**VITS_CONFIG)
        state = torch.load(ckpt, map_location="cpu")
        missing, unexpected = model.load_state_dict(state, strict=True), None
        self.model = model.to(self.device).eval()

    def _infer(self, image_path: str) -> dict:
        torch = self._torch
        bgr = self._cv2.imread(image_path)          # the reference path takes BGR
        if bgr is None:
            raise SystemExit(f"could not read {image_path!r}")
        with torch.no_grad():
            disparity = self.model.infer_image(bgr, input_size=INPUT_SIZE)
        disparity = np.asarray(disparity, dtype=np.float32)

        # DA V2 returns to the SOURCE resolution, so unlike every other entrant
        # this one needs no preprocessing map to reach the evaluation grid.
        valid = np.isfinite(disparity)
        # A non-positive disparity is not a far point, it is an unusable one:
        # inverting it later would produce a negative or infinite range.
        valid &= disparity > 0

        return {
            "native": disparity,
            "valid": valid,
            "canonical_range": None,
            "K": None,
            "conf": None,
            "aux": {},
            "extra": {
                "source_hw": [int(bgr.shape[0]), int(bgr.shape[1])],
                "output_hw": [int(disparity.shape[0]), int(disparity.shape[1])],
                "disparity_min": float(np.nanmin(disparity)),
                "disparity_max": float(np.nanmax(disparity)),
                "nonpositive_fraction": float((disparity <= 0).mean()),
            },
        }

    def preprocessed_image(self, image_path: str):
        bgr = self._cv2.imread(image_path)
        tensor, _ = self.model.image2tensor(bgr, INPUT_SIZE)
        return tensor[0].detach().cpu().numpy().transpose(1, 2, 0)

    def semantics(self) -> dict:
        return {
            "native_field": "relative inverse depth (disparity), (H,W) float32",
            "native_meaning": ("Larger is NEARER. Scale AND offset are free; the "
                               "documented ambiguity is affine in disparity."),
            "legal_alignment": "q' = a*q + b fitted in DISPARITY space, then inverted",
            "illegal_alignment": ("a*d + b fitted in physical depth. Doing that would be a "
                                  "different transform group, not a stricter one."),
            "range_conversion": ("NONE HERE. No canonical range is written, because there "
                                 "is no honest range before the S2 policy fixes (a,b)."),
            "camera": "no intrinsics, no FOV, no point map, no confidence",
            "output_grid": "SOURCE resolution — the model interpolates back up",
            "claimed_scale": "relative only; never metric",
        }

    def preprocessing(self) -> dict:
        return {
            "loader": "depth_anything_v2.dpt.DepthAnythingV2.image2tensor",
            "input_size": INPUT_SIZE,
            "resize_rule": ("Resize longest/both sides toward input_size with "
                            "ensure_multiple_of=14, keep_aspect_ratio=True, then "
                            "normalise. NO crop: the aspect ratio is preserved and the "
                            "output is interpolated back to the source (H,W)."),
            "fov_loss_expected": "none — full frame retained, verified in S0",
        }

    def provenance(self) -> dict:
        import torch
        return {
            "method": "Depth Anything V2 Small (ViT-S)",
            "role": "inverse-depth/disparity control",
            "repo": "https://github.com/DepthAnything/Depth-Anything-V2",
            "repo_commit": "a561b849ebae10a6f5ef49e26c83cbbcd36c71bf",
            "code_license": "Apache-2.0",
            "checkpoint": CHECKPOINT,
            "checkpoint_file": os.path.basename(getattr(self, "_ckpt_path", "")),
            "checkpoint_license": "Apache-2.0",
            "model_config": VITS_CONFIG,
            "torch": torch.__version__,
            "device": self.device,
            "dtype": "float32",
            "reference_impl_modifications": "none",
        }


BACKEND = DepthAnythingV2Small
