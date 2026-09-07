"""R2-1 — MoGe-3 ViT-L, Step 0 (refinement disabled).

Runs in `experiments/week4_mono/round2/.venv-moge3`.

WHY IT IS TESTED (task §7). MoGe-3 is the successor of the Round-1 incumbent
MoGe-2 ViT-L, and its headline addition is a sparse 3D refiner (SSR) applied for
`refine_steps` iterations after the initial dense prediction. That makes it the
one challenger whose Step 0 -> Step 3 ablation is a SAME-CHECKPOINT question:
what does the refinement actually change, on this footage?

WHAT THIS BACKEND RUNS, AND WHAT IT DOES NOT. Step 0 only. The refiner's sparse
3D U-Net imports `flex_gemm`, a Triton/CUDA extension with no macOS
distribution at all (`triton` has no macOS wheel), so Step 3 is recorded as
`pending_cuda` and is NOT approximated here. Two properties make Step 0 a clean
measurement rather than a mutilated model:

  * the refiner is removed through the release's OWN documented configuration
    override, `from_pretrained(..., model_kwargs={"refiner": None})`
    (`v2.py:84-111` documents the mechanism; `v3.py:43,48` guard on it), not by
    editing model code;
  * `v3.py:168` shows the refiner is not entered at all when `refine_steps=0`,
    so Step 0 numbers here are the same numbers a CUDA machine would produce at
    `refine_steps=0` with the refiner present.

S0 audited every checkpoint key that went unloaded: all 86 are under
`refiner.`, and no non-refiner key is missing. `refine_steps > 0` raises
`ValueError: Refiner is not enabled but refine_steps > 0.` — loudly, rather
than silently degrading — which is why this arm cannot quietly become a Step-3
claim.

CATEGORY B, and the modification list is exactly two entries: an import-only
`flex_gemm` stub whose every symbol raises if constructed, and the documented
`model_kwargs` override. No operator, resolution, precision, checkpoint or
math change.
"""

from __future__ import annotations

import os

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import sys

import numpy as np

from experiments.week4_mono.round1.backends.base import (
    MonoBackend, norm_pointmap, pixel_K_from_normalized)
from experiments.week4_mono.round1.common import W4

ROUND2 = os.path.join(W4, "round2")
CODE = os.path.join(ROUND2, "vendor", "moge3")
SHIMS = os.path.join(ROUND2, "shims")

REPO = "Ruicheng/moge-3-vitl"
RESOLUTION_LEVEL = 9      # reference default
FORCE_PROJECTION = True   # reference default
REFINE_STEPS = 0          # Step 0; Step 3 is pending_cuda


class MoGe3ViTL(MonoBackend):

    key = "moge3_vitl"
    native_kind = "pointmap_metric"
    range_rule = "norm_pointmap"
    checkpoint = REPO

    def __init__(self, device: str = "mps", **kw):
        super().__init__(device, **kw)
        self.refine_steps = int(kw.get("refine_steps", REFINE_STEPS))
        if self.refine_steps != 0:
            raise SystemExit(
                "MoGe-3 Step 3 is pending_cuda on this machine: the refiner's "
                "sparse 3D U-Net requires flex_gemm/Triton, which has no macOS "
                "build. Refusing to fake it.")

    def _load(self) -> None:
        import torch
        for p in (SHIMS, CODE):
            if p not in sys.path:
                sys.path.insert(0, p)
        import moge  # noqa: F401
        from moge.model.v3 import MoGeModel
        self._torch = torch
        self._moge_file = moge.__file__
        if not self._moge_file.startswith(CODE):
            raise SystemExit(f"wrong moge copy resolved: {self._moge_file}")

        # The refiner is disabled through the release's own from_pretrained
        # config override, and the load report is kept so the audit is a record
        # rather than a claim.
        model = MoGeModel.from_pretrained(REPO, model_kwargs={"refiner": None})

        # Audit what the refiner-less instantiation actually dropped, every run:
        # a missing NON-refiner key would keep its random initialisation and
        # look like a bad prediction rather than a loading failure.
        import glob
        from pathlib import Path as _P
        cands = glob.glob(str(_P.home() / ".cache/huggingface/hub"
                              "/models--Ruicheng--moge-3-vitl/snapshots/*/model.pt"))
        ck = set(self._torch.load(cands[0], map_location="cpu",
                                  weights_only=True)["model"].keys()) if cands else set()
        have = set(model.state_dict().keys())
        self._unloaded = sorted(ck - have)
        self._missing = sorted(have - ck)
        if self._missing:
            raise SystemExit(f"model keys absent from the checkpoint: {self._missing[:5]}")
        if self._unloaded and not all(k.startswith("refiner.") for k in self._unloaded):
            raise SystemExit("a NON-refiner checkpoint key went unloaded; refusing to run")
        self.model = model.to(self.device).eval()
        self._n_param = int(sum(p.numel() for p in self.model.parameters()))
        self._num_tokens_range = list(getattr(self.model, "num_tokens_range", []))

    def _infer(self, image_path: str) -> dict:
        import cv2
        torch = self._torch
        bgr = cv2.imread(image_path)
        if bgr is None:
            raise SystemExit(f"could not read {image_path!r}")
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        t = torch.tensor(rgb / 255.0, dtype=torch.float32,
                         device=self.device).permute(2, 0, 1)
        with torch.no_grad():
            out = self.model.infer(t, resolution_level=RESOLUTION_LEVEL,
                                   force_projection=FORCE_PROJECTION,
                                   apply_mask=True, refine_steps=self.refine_steps,
                                   use_fp16=False)

        points = out["points"].float().cpu().numpy()            # (H,W,3) metric
        depth = out["depth"].float().cpu().numpy()              # (H,W) z-depth
        mask = np.asarray(out["mask"].cpu().numpy(), bool)
        K_norm = out["intrinsics"].float().cpu().numpy()
        h, w = mask.shape
        K = pixel_K_from_normalized(K_norm, h, w)

        rng = norm_pointmap(points)
        valid = mask & np.isfinite(points).all(axis=-1) & np.isfinite(rng) & (rng > 0)

        extra = {
            "output_hw": [int(h), int(w)],
            "refine_steps": self.refine_steps,
            "resolution_level": RESOLUTION_LEVEL,
            "force_projection": FORCE_PROJECTION,
            "use_fp16": False,
            "intrinsics_normalised": K_norm.tolist(),
        }
        m = valid & np.isfinite(depth)
        if m.any():
            # measured, not assumed: `depth` is z, `range` is ||p||
            extra["max_abs_depth_minus_points_z"] = float(
                np.abs(depth[m] - points[..., 2][m]).max())
            ratio = rng[m] / np.where(depth[m] > 0, depth[m], np.nan)
            ratio = ratio[np.isfinite(ratio)]
            if ratio.size:
                extra["median_ratio_range_over_z"] = float(np.median(ratio))
                extra["max_ratio_range_over_z"] = float(ratio.max())

        aux = {"depth_z": depth.astype(np.float32)}
        if "normal" in out:
            aux["normal"] = out["normal"].float().cpu().numpy().astype(np.float32)
        return {"native": points.astype(np.float32), "valid": valid,
                "canonical_range": rng, "K": K, "conf": None,
                "aux": aux, "extra": extra}

    def preprocessed_image(self, image_path: str):
        """Reproduce the tensor the ViT actually consumes, using the model's own numbers.

        MoGe-3 does not expose it, so this repeats the three lines that produce
        it: the token budget (`v3.py:271-273`), the base token grid
        (`v3.py:128-132`), and the encoder's one resize
        (`dinov2_encoder.py:59`). Nothing is cropped, which is the property the
        FOV audit is checking.

        NOTE FOR THE GRID MAP. This is the NETWORK INPUT grid. MoGe-3 resizes
        its outputs back up to the source (H,W) before returning, so the map
        from source pixels to the PERSISTED prediction is the identity, not the
        map measured here. `evalgrid.model_output_grid` settles that from the
        S0 probe's own output shape rather than from this method.
        """
        import cv2
        import torch
        import torch.nn.functional as F
        bgr = cv2.imread(image_path)
        if bgr is None:
            raise SystemExit(f"could not read {image_path!r}")
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        t = torch.tensor(rgb / 255.0, dtype=torch.float32).permute(2, 0, 1)[None]
        h, w = t.shape[-2:]
        min_tokens, max_tokens = self.model.num_tokens_range
        num_tokens = int(min_tokens + (RESOLUTION_LEVEL / 9) * (max_tokens - min_tokens))
        ar = w / h
        base_h, base_w = round((num_tokens / ar) ** 0.5), round((num_tokens * ar) ** 0.5)
        out = F.interpolate(t, (base_h * 14, base_w * 14), mode="bilinear",
                            align_corners=False, antialias=True)
        return out[0].numpy().transpose(1, 2, 0)

    def semantics(self) -> dict:
        return {
            "native_field": "points (H,W,3) camera-frame point map",
            "native_meaning": ("metric-claimed 3D point per pixel; v3.py multiplies the "
                               "affine point map by the predicted `metric_scale` before "
                               "returning it"),
            "canonical_range": "||points|| — NOT points[...,2]",
            "z_field": ("out['depth'] is planar z-depth; v3.py sets depth = points[...,2]. "
                        "S0 measured max|depth - points_z| = 0.0 on all four probe images."),
            "camera_frame": "OpenCV: +x right, +y down, +z forward",
            "mask": "out['mask'], the model's own validity",
            "confidence": "none emitted",
            "intrinsics": "out['intrinsics'] is NORMALISED (0..1); scaled to pixels here",
            "claimed_scale": ("metric; PROVISIONAL pre-C2 — raw metric scale cannot be "
                              "finally judged before C2"),
            "refinement": ("Step 0 only. The SSR refiner is disabled via the release's own "
                           "model_kwargs override; v3.py:168 shows it is not entered at "
                           "refine_steps=0. Step 3 is pending_cuda (flex_gemm/Triton)."),
            "view_count": "strictly 1 — infer() takes a single (3,H,W) tensor",
        }

    def preprocessing(self) -> dict:
        return {
            "loader": "cv2.imread -> RGB -> /255 -> (3,H,W) float32; MoGe-3 resizes internally",
            "resize_rule": ("MoGeModel.infer resizes to a token-budget resolution set by "
                            "resolution_level and interpolates outputs back to the SOURCE "
                            "(H,W); aspect preserved, no crop"),
            "resolution_level": RESOLUTION_LEVEL,
            "num_tokens_range": getattr(self, "_num_tokens_range", None),
            "force_projection": FORCE_PROJECTION,
            "use_fp16": "False (reference default is already False for v3.infer)",
            "fov_loss_expected": "none — aspect ratio preserved, no crop",
            "portrait": "1280x720 and 720x1280 both handled natively (S0)",
        }

    def provenance(self) -> dict:
        import torch
        return {
            "method": "MoGe-3 ViT-L (Step 0, refinement disabled)",
            "role": "R2-1 challenger: successor of the Round-1 incumbent MoGe-2 ViT-L",
            "repo": "https://github.com/microsoft/MoGe",
            "code_copy_path": CODE,
            "code_copy_resolved_module": getattr(self, "_moge_file", None),
            "checkpoint": REPO,
            "checkpoint_note": ("official checkpoint is ViT-L; ViT-G is NOT run — task §7 "
                                "forbids running a larger variant without a measured "
                                "capacity question"),
            "n_parameters": getattr(self, "_n_param", None),
            "unloaded_checkpoint_keys_n": len(getattr(self, "_unloaded", []) or []),
            "unloaded_checkpoint_keys_all_refiner": bool(
                getattr(self, "_unloaded", None) is not None
                and all(k.startswith("refiner.") for k in self._unloaded)),
            "model_keys_missing_from_checkpoint": getattr(self, "_missing", None),
            "torch": torch.__version__,
            "device": self.device,
            "dtype": "float32",
            "impl_category": "B",
            "reference_impl_modifications": [
                "import-only `flex_gemm` stub (round2/shims/flex_gemm) so the module "
                "graph resolves without Triton/CUDA; every symbol raises RuntimeError "
                "if constructed, so it cannot silently participate in a forward pass",
                "model_kwargs={'refiner': None} — the release's own documented "
                "from_pretrained config override (v2.py:84-111)",
            ],
            "not_modified": ("no operator substitution, no interpolation-mode change, no "
                             "resolution change, no precision change, no checkpoint "
                             "substitution, no helper model"),
        }


BACKEND = MoGe3ViTL
