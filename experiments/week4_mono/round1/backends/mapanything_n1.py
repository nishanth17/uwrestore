"""Backend 1 — MapAnything, forced to N=1.

Runs in `experiments/week3_geometry/.venv-mapanything`.

ROLE (FREEZE §3.1): the control. This is the Week-3 incumbent with its
multi-view information removed, so V1 (view count) is the one variable that
changes between the Week-3 reference product and this arm. Every other thing —
checkpoint, preprocessing, representation, wrapper conventions, device, dtype —
is deliberately held at the Week-3 settings, and the range conversion is the
identity that Week 3 already verified numerically.

The single-view invariant is enforced twice: `load_images` is handed a
one-element list, and the returned view count is asserted before inference.
"""

from __future__ import annotations

import os

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import numpy as np

from experiments.week4_mono.round1.backends.base import MonoBackend

CHECKPOINT = "facebook/map-anything-apache"


class MapAnythingN1(MonoBackend):
    key = "mapanything_n1"
    checkpoint = CHECKPOINT
    native_kind = "depth_along_ray_metric"
    range_rule = "identity_depth_along_ray"

    def _load(self) -> None:
        import torch
        from mapanything.models import MapAnything
        from mapanything.utils.image import load_images
        self._torch = torch
        self._load_images = load_images
        self.model = MapAnything.from_pretrained(CHECKPOINT).to(self.device).eval()

    def _infer(self, image_path: str) -> dict:
        torch = self._torch
        views = self._load_images([image_path])
        if len(views) != 1:
            raise RuntimeError(f"strict N=1 violated: load_images returned {len(views)} views")
        with torch.no_grad():
            preds = self.model.infer(
                views,
                memory_efficient_inference=True,
                use_amp=False,              # MPS has no bf16 autocast path
                apply_mask=True,
                mask_edges=True,
                apply_confidence_mask=False,  # confidence stays DATA, never a filter
            )
        if len(preds) != 1:
            raise RuntimeError(f"strict N=1 violated: model returned {len(preds)} predictions")
        pred = preds[0]

        dar = pred["depth_along_ray"][0].detach().float().cpu().numpy()[..., 0]
        p3c = pred["pts3d_cam"][0].detach().float().cpu().numpy()
        dz = pred["depth_z"][0].detach().float().cpu().numpy()[..., 0]
        mask = pred["mask"][0].detach().cpu().numpy()
        mask = mask[..., 0] if mask.ndim == 3 else mask
        conf = pred["conf"][0].detach().float().cpu().numpy()
        K = pred["intrinsics"][0].detach().float().cpu().numpy()

        valid = np.asarray(mask, bool) & np.isfinite(dar) & (dar > 0)

        # Week 3 verified `depth_along_ray == ||pts3d_cam||` to 1.9e-06. Re-check
        # it per frame at N=1: this arm is the one place a view-count change
        # could plausibly alter what the field means, and an unchecked identity
        # is exactly the silent convention error the project keeps guarding
        # against.
        m = valid & np.isfinite(p3c).all(axis=-1)
        conv = {}
        if m.any():
            norm = np.linalg.norm(p3c, axis=-1)
            conv["max_abs_range_minus_norm_pts3d_cam"] = float(np.abs(norm[m] - dar[m]).max())
            conv["max_abs_depth_z_minus_pts3d_cam_z"] = float(np.abs(p3c[..., 2][m] - dz[m]).max())
            with np.errstate(invalid="ignore", divide="ignore"):
                ratio = dar[m] / np.where(dz[m] > 0, dz[m], np.nan)
            ratio = ratio[np.isfinite(ratio)]
            if ratio.size:
                conv["median_ratio_range_over_z"] = float(np.median(ratio))
                conv["max_ratio_range_over_z"] = float(ratio.max())

        extra = dict(conv)
        if "non_ambiguous_mask" in pred:
            nam = pred["non_ambiguous_mask"][0].detach().cpu().numpy()
            extra["non_ambiguous_fraction"] = float(np.asarray(nam, bool).mean())
        if "metric_scaling_factor" in pred:
            extra["metric_scaling_factor"] = float(
                pred["metric_scaling_factor"].detach().float().cpu().numpy().ravel()[0])
        extra["n_views_seen_by_model"] = 1

        return {
            "native": dar.astype(np.float32),
            "valid": valid,
            "canonical_range": dar.astype(np.float32),
            "K": K,
            "conf": conf,
            "aux": {"pts3d_cam": p3c.astype(np.float32),
                    "depth_z": dz.astype(np.float32)},
            "extra": extra,
        }

    def preprocessed_image(self, image_path: str):
        views = self._load_images([image_path])
        return np.asarray(views[0]["img"])[0].transpose(1, 2, 0)

    def semantics(self) -> dict:
        return {
            "native_field": "depth_along_ray (B,H,W,1)",
            "native_meaning": ("Euclidean camera-centre-to-point distance. Verified per "
                               "frame against ||pts3d_cam||; see "
                               "max_abs_range_minus_norm_pts3d_cam."),
            "z_field": "depth_z (B,H,W,1) is the PLANAR z component, not range",
            "camera_frame": "OpenCV: +x right, +y down, +z forward",
            "range_conversion": "identity — the native field already IS the range",
            "mask": "pred['mask'] with apply_mask=True, mask_edges=True",
            "confidence": "pred['conf'], learned per-pixel, NOT calibrated underwater",
            "claimed_scale": "metric; at N=1 the absolute scale is PROVISIONAL pre-C2",
            "view_count": "strictly 1 — asserted on both the loader and the model output",
        }

    def preprocessing(self) -> dict:
        return {
            "loader": "mapanything.utils.image.load_images (default fixed_mapping mode)",
            "resolution_set": 518,
            "note": ("Lanczos rescale to an aspect-ratio-mapped resolution, then centre "
                     "crop. Every dense number is produced on that grid, NOT at the "
                     "1280-long-side extraction resolution."),
        }

    def provenance(self) -> dict:
        import torch
        return {
            "method": "MapAnything (N=1)",
            "role": "V1 view-count control against the Week-3 N=48 reference product",
            "repo": "https://github.com/facebookresearch/map-anything",
            "repo_commit": "3d10cf7a3016fc0f9bb13a071ee66c47b10be0d9",
            "package_version": "1.1.4",
            "code_license": "Apache-2.0",
            "checkpoint": CHECKPOINT,
            "checkpoint_license": "Apache-2.0 (default facebook/map-anything is CC-BY-NC-4.0)",
            "torch": torch.__version__,
            "device": self.device,
            "dtype": "float32 (use_amp=False; MPS has no bf16 autocast path)",
            "reference_impl_modifications": "none",
        }


BACKEND = MapAnythingN1
