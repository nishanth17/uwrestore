"""Backend 5 — Wat3R (Ren et al.), forced to N=1.

Runs in `experiments/week3_geometry/.venv-vggt`.

ROLE (FREEZE §3.3): the sole underwater-specialisation control. Does an
explicitly underwater-trained modern geometry model help on water regimes
outside its training distribution, or does specialisation increase fragility?

NAMED `wat3r_ren` in the Week-3 products because a second, unrelated 2026 method
is also called WAT3R (Xu et al.). The Week-4 key is `wat3r_n1`; the checkpoint
and repo are the same Ren et al. release Week 3 measured.

TWO THINGS THIS BACKEND DELIBERATELY DOES NOT DO.

1. It does not use `mode="max"`, even though Wat3R's README does. Week 3
   established that Wat3R's `load_and_preprocess_images` "crop" branch is
   character-for-character VGGT's; `mode` is a preprocessing choice, and
   changing it between the Week-3 product and this arm would confound the
   view-count question with a pixel-selection question. `mode="crop"` is kept.

2. It does not infer the model's native ambiguity from the released evaluation
   code's alignment (FREEZE §3.3). This backend records the raw output and its
   measured properties; S2 decides the alignment policy.

THE PORTRAIT TRAP. Week 3 measured this family losing 10 of 25 FOV markers on a
portrait 1280x720 source — the "crop" branch resizes the SHORT side to 518 and
centre-crops the long one. `wreck_01` is portrait, which is precisely why the
freeze keeps it in the primary set. The FOV loss is measured in S0, not assumed.
"""

from __future__ import annotations

import os

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import sys

import numpy as np

from experiments.week4_mono.backends.base import (
    MonoBackend, ray_range_from_zdepth, norm_pointmap)
from experiments.week4_mono.common import W3

CHECKPOINT = "lsxi77777/Wat3R"
VENDOR = os.path.join(W3, "vendor", "Wat3R")


class Wat3RN1(MonoBackend):
    key = "wat3r_n1"
    checkpoint = CHECKPOINT
    native_kind = "pointmap"
    range_rule = "zdepth_to_range_with_K"

    def _load(self) -> None:
        import torch
        if VENDOR not in sys.path:
            sys.path.insert(0, VENDOR)
        from wat3r.models.wat3r import Wat3R
        from wat3r.utils.load_fn import load_and_preprocess_images
        from wat3r.utils.pose_enc import pose_encoding_to_extri_intri
        self._torch = torch
        self._load_images = load_and_preprocess_images
        self._pose_dec = pose_encoding_to_extri_intri
        self.model = Wat3R.from_pretrained(CHECKPOINT).to(self.device).eval()

    def _infer(self, image_path: str) -> dict:
        torch = self._torch
        images = self._load_images([image_path], mode="crop").to(self.device)  # (S,3,H,W)
        if images.shape[0] != 1:
            raise RuntimeError(f"strict N=1 violated: loader produced {images.shape[0]} views")
        with torch.no_grad():
            preds = self.model(images)

        # (B,S,H,W,*) with B=1, S=1 throughout.
        depth_z = preds["depth"][0].float().cpu().numpy()
        depth_z = depth_z[0, ..., 0] if depth_z.ndim == 4 else depth_z[0]
        conf = None
        if "depth_conf" in preds:
            c = preds["depth_conf"][0].float().cpu().numpy()
            conf = c[0] if c.ndim >= 3 else c

        hw = (images.shape[-2], images.shape[-1])
        extri, intri = self._pose_dec(preds["pose_enc"], hw)
        K = intri[0, 0].float().cpu().numpy()
        T_cw = extri[0, 0].float().cpu().numpy()

        rng = ray_range_from_zdepth(depth_z, K)
        valid = np.isfinite(rng) & (rng > 0)

        # The native product is the camera-frame point map implied by (z, K).
        # Storing z-depth as "the point map" would be the same z-vs-range
        # confusion the freeze warns about for FoundationGeo, so the point map
        # is constructed explicitly and the z field is kept beside it.
        h, w = depth_z.shape
        u, v = np.meshgrid(np.arange(w, dtype=np.float64), np.arange(h, dtype=np.float64))
        uv1 = np.stack([u, v, np.ones_like(u)], axis=-1)
        dirs = uv1 @ np.linalg.inv(np.asarray(K, dtype=np.float64)).T   # z == 1
        points = dirs * depth_z.astype(np.float64)[..., None]

        extra = {
            "output_hw": [int(h), int(w)],
            "n_views_seen_by_model": int(images.shape[0]),
            "pred_keys": sorted(preds.keys()),
            "max_abs_range_minus_norm_points": float(
                np.abs(norm_pointmap(points)[valid] - rng[valid]).max()) if valid.any() else float("nan"),
        }
        if "world_points" in preds:
            extra["emits_world_points"] = True
        if "world_points_conf" in preds:
            extra["emits_world_points_conf"] = True

        return {
            "native": points.astype(np.float32),
            "valid": valid,
            "canonical_range": rng,
            "K": K,
            "conf": conf,
            "aux": {"depth_z": depth_z.astype(np.float32),
                    "T_cw": np.asarray(T_cw, dtype=np.float32)},
            "extra": extra,
        }

    def preprocessed_image(self, image_path: str):
        t = self._load_images([image_path], mode="crop")
        return t[0].detach().cpu().numpy().transpose(1, 2, 0)

    def semantics(self) -> dict:
        return {
            "native_field": ("point map built as K^-1[u,v,1] * depth, from the model's own "
                             "PLANAR z-depth head and its decoded pixel intrinsics"),
            "native_meaning": "camera-frame 3D point per pixel",
            "z_field": "preds['depth'] is PLANAR z-depth, not range",
            "canonical_range": "z * ||K^-1 [u,v,1]|| — the secant conversion",
            "camera_frame": "OpenCV: +x right, +y down, +z forward",
            "pose": "pose_encoding_to_extri_intri returns world2cam extrinsics",
            "confidence": "preds['depth_conf'], learned; NOT calibrated for this domain",
            "claimed_scale": ("NOT established here. The model was trained multi-view and "
                              "the released evaluation aligns before scoring; native "
                              "ambiguity is an S2 measurement, not an inheritance."),
            "training_caveat": ("not trained with single-image supervision; FLSea is in its "
                                "training pool though its evaluation scenes are held out"),
            "view_count": "strictly 1 — asserted on the preprocessed tensor",
        }

    def preprocessing(self) -> dict:
        return {
            "loader": "wat3r.utils.load_fn.load_and_preprocess_images",
            "mode": "crop",
            "mode_rationale": ("Wat3R's README uses mode='max'; Week 3 uses 'crop' because "
                               "that branch is identical to VGGT's, which keeps the "
                               "family comparison on identical pixels. Kept for Week 4 so "
                               "this arm differs from the Week-3 product ONLY in view count."),
            "resize_rule": ("resize so the SHORT side reaches 518 rounded to a multiple of "
                            "14, then centre-crop the long side to 518"),
            "fov_loss_expected": ("substantial on PORTRAIT sources — Week 3 lost 10/25 FOV "
                                  "markers at 1280x720. Measured in S0, not assumed."),
        }

    def provenance(self) -> dict:
        import torch
        return {
            "method": "Wat3R-Ren (N=1)",
            "role": "sole underwater-specialisation control",
            "repo": "https://github.com/LSXI7/Wat3R",
            "repo_commit": "93147df00e15605afa93f586923fec000b18cefc",
            "code_license": "Apache-2.0",
            "checkpoint": CHECKPOINT,
            "checkpoint_license": "Apache-2.0",
            "torch": torch.__version__,
            "device": self.device,
            "dtype": "float32 (no autocast)",
            "reference_impl_modifications": "none",
            "naming_note": ("Ren et al. ECCV 2026. A second unrelated 2026 method is also "
                            "called WAT3R (Xu et al.); Week 3 records this one as wat3r_ren."),
        }


BACKEND = Wat3RN1
