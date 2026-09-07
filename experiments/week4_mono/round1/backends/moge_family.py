"""Backends 3 and 4 — MoGe-2 ViT-L and MetricAnything Student-PointMap.

Runs in `experiments/week4_mono/.venv-moge`.

ONE MODULE FOR BOTH, ON PURPOSE. FREEZE §C5/§3.5 defines this pair as
experimental variable V5 — heterogeneous metric fine-tuning of a fixed
architecture:

    MoGe-2 ViT-L  ->  MetricAnything Student-PointMap

`metricanything_student_pointmap` is a MoGe-2 ViT-L fine-tune, and its release
ships its OWN vendored copy of the MoGe code. If each checkpoint ran through a
different code copy, any difference in preprocessing, FOV/shift recovery,
masking or output convention would be indistinguishable from a fine-tuning
effect — the same reasoning that made Week 3 run VGGT and Wat3R through one
script. So both checkpoints are loaded into the SAME class from the SAME source
tree, chosen explicitly by `--code-copy`, and which copy was used is recorded in
provenance.

Default `code_copy="metricanything"`: the MetricAnything release's vendored MoGe
snapshot. It is contemporaneous with both checkpoints (both are MoGe-**2**
checkpoints), whereas the upstream `microsoft/MoGe` tree has since moved to
MoGe-3 and changed the v2 forward path — it now forces the points and normal
heads' output projections to fp32. `code_copy="upstream"` runs the current
microsoft/MoGe tree instead, and S0 reports the difference between the two so
the choice is a measured one rather than a preference.

`moge` is imported by explicit `sys.path` insertion, not by installation. Both
copies are packages literally named `moge`, so an installed one would silently
win and the control would be lost without any error.
"""

from __future__ import annotations

import os

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
os.environ.setdefault("OPENCV_IO_ENABLE_OPENEXR", "1")

import sys

import numpy as np

from experiments.week4_mono.round1.backends.base import (
    MonoBackend, norm_pointmap, pixel_K_from_normalized)
from experiments.week4_mono.round1.common import W4_ROUND1

CODE_COPIES = {
    "metricanything": os.path.join(W4_ROUND1, "vendor", "metric-anything",
                                   "models", "student_pointmap"),
    "upstream": os.path.join(W4_ROUND1, "vendor", "moge"),
}

#: Reference-implementation defaults, pinned here so they are recorded constants
#: rather than per-call choices that could drift between stages.
RESOLUTION_LEVEL = 9      # the reference default
FORCE_PROJECTION = True   # the reference default: recompute points from (depth, K)

SPECS = {
    "moge2_vitl": {
        "checkpoint": "Ruicheng/moge-2-vitl",
        "checkpoint_file": "model.pt",
        "checkpoint_license": "MIT",
        "role": "strong monocular metric point-map baseline; V5 control arm",
        "repo": "https://github.com/microsoft/MoGe",
        "repo_commit": "74fbce054ebed49800de42d0ad0e83495065719a",
        "code_license": "MIT",
    },
    "metricanything_pointmap": {
        "checkpoint": "yjh001/metricanything_student_pointmap",
        "checkpoint_file": "student_pointmap.pt",
        "checkpoint_license": "Apache-2.0",
        "role": "V5 treatment arm: heterogeneous metric fine-tuning of MoGe-2 ViT-L",
        "repo": "https://github.com/metric-anything/metric-anything",
        "repo_commit": "616a5e6762f5fc40d1a4ef990fee04c800532f59",
        "code_license": "Apache-2.0",
    },
}


class MoGeFamily(MonoBackend):
    """MoGe-2-architecture point-map models. `key` selects the checkpoint."""

    native_kind = "pointmap_metric"
    range_rule = "norm_pointmap"

    def __init__(self, device: str = "mps", key: str = "moge2_vitl",
                 code_copy: str = "metricanything", fov_x: float | None = None, **kw):
        super().__init__(device, **kw)
        if key not in SPECS:
            raise ValueError(f"unknown MoGe-family key {key!r}")
        if code_copy not in CODE_COPIES:
            raise ValueError(f"unknown code copy {code_copy!r}")
        self.key = key
        self.spec = SPECS[key]
        self.checkpoint = self.spec["checkpoint"]
        self.code_copy = code_copy
        #: V9 known-FOV POSTPROCESSING ablation (FREEZE §2 V9). Supplying this
        #: does NOT condition the network; it replaces the focal/shift recovery
        #: step's inferred FOV with a supplied one. Default None = model-inferred.
        self.fov_x = fov_x

    def _load(self) -> None:
        import torch
        from huggingface_hub import hf_hub_download
        root = CODE_COPIES[self.code_copy]
        if root not in sys.path:
            sys.path.insert(0, root)
        import moge  # noqa: F401  (resolved by the path insertion above)
        from moge.model.v2 import MoGeModel
        self._torch = torch
        self._moge_file = moge.__file__
        if not self._moge_file.startswith(root):
            raise SystemExit(f"wrong moge copy resolved: {self._moge_file} (wanted {root})")

        ckpt_path = hf_hub_download(repo_id=self.spec["checkpoint"],
                                    filename=self.spec["checkpoint_file"])
        self._ckpt_path = ckpt_path
        checkpoint = torch.load(ckpt_path, map_location="cpu", weights_only=True)
        self._model_config = dict(checkpoint["model_config"])
        model = MoGeModel(**checkpoint["model_config"])
        res = model.load_state_dict(checkpoint["model"], strict=False)
        # Both copies call load_state_dict(strict=False). That is fine for an
        # optional head and catastrophic for a mismatched architecture, since a
        # missing key keeps its RANDOM initialisation and looks like a bad
        # prediction rather than a loading failure. So it is recorded, and S0
        # treats a non-empty list as a semantics failure for this arm.
        self._missing_keys = list(getattr(res, "missing_keys", []) or [])
        self._unexpected_keys = list(getattr(res, "unexpected_keys", []) or [])
        self.model = model.to(self.device).eval()

    def _infer(self, image_path: str) -> dict:
        import cv2
        torch = self._torch
        bgr = cv2.imread(image_path)
        if bgr is None:
            raise SystemExit(f"could not read {image_path!r}")
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        tensor = torch.tensor(rgb / 255.0, dtype=torch.float32,
                              device=self.device).permute(2, 0, 1)
        with torch.no_grad():
            # use_fp16 defaults to TRUE in the reference implementation. It is
            # forced off: the project's standing rule since Week 3 is that a
            # measurement instrument must be reproducible before it is fast, and
            # half precision would put a stochastic floor under every S1/S4/S5
            # delta this bakeoff is trying to read.
            out = self.model.infer(tensor, fov_x=self.fov_x, use_fp16=False,
                                   resolution_level=RESOLUTION_LEVEL,
                                   force_projection=FORCE_PROJECTION,
                                   apply_mask=True)

        points = out["points"].float().cpu().numpy()          # (H,W,3)
        depth = out["depth"].float().cpu().numpy()            # (H,W) z-depth
        mask = np.asarray(out["mask"].cpu().numpy(), bool)
        K_norm = out["intrinsics"].float().cpu().numpy()      # normalised intrinsics

        h, w = mask.shape
        K = pixel_K_from_normalized(K_norm, h, w)

        rng = norm_pointmap(points)
        valid = mask & np.isfinite(points).all(axis=-1) & np.isfinite(rng) & (rng > 0)

        extra = {
            "output_hw": [int(h), int(w)],
            "fov_x_supplied": self.fov_x,
            "intrinsics_normalised": K_norm.tolist(),
            "use_fp16": False,
            "resolution_level": RESOLUTION_LEVEL,
            "force_projection": FORCE_PROJECTION,
        }
        # The z-vs-range distinction, measured rather than assumed: if these were
        # ever confused the error would be radial and would land in M-6.
        m = valid & np.isfinite(depth)
        if m.any():
            extra["max_abs_depth_minus_points_z"] = float(
                np.abs(depth[m] - points[..., 2][m]).max())
            ratio = rng[m] / np.where(depth[m] > 0, depth[m], np.nan)
            ratio = ratio[np.isfinite(ratio)]
            if ratio.size:
                extra["median_ratio_range_over_z"] = float(np.median(ratio))
                extra["max_ratio_range_over_z"] = float(ratio.max())
        if "normal" in out:
            extra["emits_normal"] = True
        if "mask_metric" in out:
            extra["emits_mask_metric"] = True

        # `points` IS `native`; only the z field is additional information.
        aux = {"depth_z": depth.astype(np.float32)}
        return {
            "native": points.astype(np.float32),
            "valid": valid,
            "canonical_range": rng,
            "K": K,
            "conf": None,
            "aux": aux,
            "extra": extra,
        }

    def preprocessed_image(self, image_path: str):
        """Reproduce MoGe's internal resize exactly, using the model's own numbers.

        MoGe does not expose the resized tensor, so this repeats the two lines
        `MoGeModel.infer` uses: a token-budget-derived resolution and one
        bilinear/antialiased resize. Nothing is cropped, which is the property
        the FOV audit is checking.
        """
        import cv2
        import torch
        import torch.nn.functional as F
        bgr = cv2.imread(image_path)
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        t = torch.tensor(rgb / 255.0, dtype=torch.float32).permute(2, 0, 1)[None]
        h, w = t.shape[-2:]
        min_tokens, max_tokens = self.model.num_tokens_range
        num_tokens = int(min_tokens + (RESOLUTION_LEVEL / 9) * (max_tokens - min_tokens))
        aspect_ratio = w / h
        base = (num_tokens * 14 ** 2 / aspect_ratio) ** 0.5
        rh, rw = int(base), int(base * aspect_ratio)
        out = F.interpolate(t, (rh, rw), mode="bilinear", align_corners=False, antialias=True)
        return out[0].numpy().transpose(1, 2, 0)

    def semantics(self) -> dict:
        return {
            "native_field": "points (H,W,3) camera-frame point map",
            "native_meaning": "metric-claimed 3D point per pixel in the camera frame",
            "canonical_range": "||points|| — NOT points[..., 2], which is z-depth",
            "z_field": "out['depth'] is planar z-depth; verified equal to points[...,2]",
            "camera_frame": "OpenCV: +x right, +y down, +z forward",
            "mask": "out['mask'], the model's own validity",
            "confidence": "none emitted",
            "intrinsics": ("out['intrinsics'] is NORMALISED (0..1); scaled to pixels by "
                           "the output (H,W) here"),
            "claimed_scale": "metric; PROVISIONAL pre-C2 on this camera",
            "fov_postprocessing": ("fov_x=None means the model's own focal/shift recovery. "
                                   "Supplying fov_x replaces that recovery's focal — it is "
                                   "POSTPROCESSING/CALIBRATION, the network is NOT "
                                   "conditioned on it (V9)."),
            "view_count": "strictly 1 by construction — infer() takes a single (3,H,W) tensor",
        }

    def preprocessing(self) -> dict:
        return {
            "loader": "cv2.imread -> RGB -> /255 -> (3,H,W) float32; MoGe resizes internally",
            "resize_rule": ("MoGeModel.infer resizes to a token-budget-derived resolution "
                            "and interpolates the outputs back to the SOURCE (H,W)."),
            "resolution_level": RESOLUTION_LEVEL,
            "force_projection": FORCE_PROJECTION,
            "force_projection_note": ("the reference default. With it on, `points` is "
                                      "recomputed from (depth, K), so the point map is "
                                      "projection-consistent by construction."),
            "use_fp16": "False (reference default is True; overridden for reproducibility)",
            "fov_loss_expected": "none — aspect ratio preserved, no crop; verified in S0",
            "code_copy": self.code_copy,
            "code_copy_path": CODE_COPIES[self.code_copy],
        }

    def provenance(self) -> dict:
        import torch
        p = {
            "method": f"MoGe-2 architecture ({self.key})",
            "role": self.spec["role"],
            "repo": self.spec["repo"],
            "repo_commit": self.spec["repo_commit"],
            "code_license": self.spec["code_license"],
            "code_copy": self.code_copy,
            "code_copy_path": CODE_COPIES[self.code_copy],
            "code_copy_resolved_module": getattr(self, "_moge_file", None),
            "checkpoint": self.spec["checkpoint"],
            "checkpoint_file": self.spec["checkpoint_file"],
            "checkpoint_license": self.spec["checkpoint_license"],
            "model_config": getattr(self, "_model_config", None),
            "load_state_dict_missing_keys": getattr(self, "_missing_keys", None),
            "load_state_dict_unexpected_keys": getattr(self, "_unexpected_keys", None),
            "torch": torch.__version__,
            "device": self.device,
            "dtype": "float32",
            "fov_x_supplied": self.fov_x,
            "reference_impl_modifications": (
                "none to the model code. `moge` is put on sys.path explicitly instead of "
                "pip-installed so that the code copy is chosen rather than inherited."),
        }
        return p


class MoGe2ViTL(MoGeFamily):
    def __init__(self, device: str = "mps", **kw):
        kw.setdefault("key", "moge2_vitl")
        super().__init__(device, **kw)


class MetricAnythingPointMap(MoGeFamily):
    def __init__(self, device: str = "mps", **kw):
        kw.setdefault("key", "metricanything_pointmap")
        super().__init__(device, **kw)


BACKENDS = {"moge2_vitl": MoGe2ViTL,
            "metricanything_pointmap": MetricAnythingPointMap}
