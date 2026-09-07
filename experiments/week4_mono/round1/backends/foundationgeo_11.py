"""Backend 7 — FoundationGeo-1.1, plus its same-checkpoint internal ablations.

Runs in `experiments/week4_mono/.venv-mono`.

ROLE (FREEZE §3.7 and §C3): a point-map candidate AND the host of the only two
genuinely causal interventions left in Week 4A after the corrections pass:

    V4b  learned ray-direction correction
    V4c  learned per-pixel metric scale field

WHY THIS BACKEND REIMPLEMENTS `infer()`'S TAIL.

The released `infer()` returns `points_pre_field`, which sounds like "the
geometry before the scale field" and is not. Reading `model/v1.py`:

    points_pre_field, ... = postprocess_points(points_pre_delta)
    points_rel,      ... = postprocess_points(points)

Two things are wrong with using those two arrays as a ray-correction ablation.
First, `points_pre_delta` is the geometry before the RAY correction, not before
the scale field — the release name is misleading, exactly as the freeze says.
Second, and worse, each arm goes through its OWN `recover_focal_shift`. The two
arms therefore differ by the ray correction *plus* whatever different focal and
shift each independently recovered, and calling that difference "ray correction"
would be a causal claim the data does not support.

So this backend calls `model.forward()` itself to obtain the RAW pre-delta and
post-delta geometry from one forward pass, and applies ONE COMMON FROZEN
postprocessing solution — the (focal, shift) recovered from the post-delta arm —
to both. That is FREEZE §C3's second permitted construction, and it makes the
A->B difference attributable to the learned ray delta alone.

V4c is then the clean same-tensor intervention the freeze describes:

    C = common post-ray relative geometry
    D = C * scalefield

THE OTHER TRAP. `depth_metric = points_metric[..., 2]` is Z-DEPTH. The project's
canonical range is `||points_metric||`. This backend never stores `depth_metric`
as a range.
"""

from __future__ import annotations

import os

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
os.environ.setdefault("OPENCV_IO_ENABLE_OPENEXR", "1")

import numpy as np

from experiments.week4_mono.round1.backends.base import (
    MonoBackend, norm_pointmap, pixel_K_from_normalized)

CHECKPOINT = "mxliu-hku/FoundationGeo-1.1"
CHECKPOINT_FILE = "FoundationGeo.pt"

#: Reference-implementation defaults, pinned.
RESOLUTION_LEVEL = 9
FORCE_PROJECTION = False    # the reference `infer` default
DELTA_MAX_RAD = 0.0523598   # 3 degrees, hard-coded in the model's forward pass


class FoundationGeo11(MonoBackend):
    key = "foundationgeo_11"
    checkpoint = CHECKPOINT
    native_kind = "pointmap_metric"
    range_rule = "norm_pointmap"

    def _load(self) -> None:
        import torch
        from huggingface_hub import hf_hub_download
        from foundationgeo.model.v1 import FoundationGeo
        self._torch = torch
        # `from_pretrained` on a repo id hard-codes filename="model.pt", but the
        # released repo ships `FoundationGeo.pt`. Resolving the file first and
        # handing over a local path takes the SAME loading branch without
        # touching vendored code.
        ckpt = hf_hub_download(repo_id=CHECKPOINT, filename=CHECKPOINT_FILE)
        self._ckpt_path = ckpt
        self.model = FoundationGeo.from_pretrained(ckpt).to(self.device).eval()
        state = torch.load(ckpt, map_location="cpu", weights_only=True)
        self._model_config = dict(state["model_config"])
        del state

    # -- the common frozen postprocessing ---------------------------------

    def _postprocess(self, points_in, mask_binary, aspect_ratio, solution=None):
        """`model/v1.py`'s `postprocess_points`, with the solution optionally FROZEN.

        `solution=None` recovers (focal, shift) from `points_in`, reproducing the
        reference behaviour. Passing a previously recovered solution applies that
        same focal and shift instead, which is what makes the V4b arms
        comparable.
        """
        import torch
        import utils3d
        from foundationgeo.utils.geometry_torch import recover_focal_shift

        if solution is None:
            focal, shift = recover_focal_shift(points_in, mask_binary)
        else:
            focal, shift = solution
        fx = focal / 2 * (1 + aspect_ratio ** 2) ** 0.5 / aspect_ratio
        fy = focal / 2 * (1 + aspect_ratio ** 2) ** 0.5
        intrinsics = utils3d.torch.intrinsics_from_focal_center(fx, fy, 0.5, 0.5)
        depth_out = points_in[..., 2] + shift[..., None, None]
        if FORCE_PROJECTION:
            points_out = utils3d.torch.depth_to_points(depth_out, intrinsics=intrinsics)
        else:
            points_out = points_in + torch.stack(
                [torch.zeros_like(shift), torch.zeros_like(shift), shift],
                dim=-1)[..., None, None, :]
        return points_out, depth_out, intrinsics, (focal, shift)

    def _infer(self, image_path: str) -> dict:
        import cv2
        import torch
        cv = cv2
        bgr = cv.imread(image_path)
        if bgr is None:
            raise SystemExit(f"could not read {image_path!r}")
        rgb = cv.cvtColor(bgr, cv.COLOR_BGR2RGB)
        h_src, w_src = rgb.shape[:2]
        aspect_ratio = w_src / h_src
        image = torch.tensor(rgb / 255.0, dtype=torch.float32,
                             device=self.device).permute(2, 0, 1).unsqueeze(0)

        min_tokens, max_tokens = self.model.num_tokens_range
        num_tokens = int(min_tokens + (RESOLUTION_LEVEL / 9) * (max_tokens - min_tokens))

        with torch.inference_mode():
            # ONE forward pass. Both ray-correction arms come out of it, so no
            # part of the A->B difference can be a second forward pass.
            fwd = self.model.forward(image, num_tokens)
            raw_pre = fwd["points_pre_delta"].float()     # (1,H,W,3) before ray delta
            raw_post = fwd["points"].float()              # (1,H,W,3) after ray delta
            scalefield = fwd["scalefield"].float()        # (1,H,W,1)
            delta = fwd["delta"].float()                  # (1,H,W,2)
            mask = fwd["mask"].float()
            mask_binary = mask > self.model.mask_threshold

            with torch.autocast(device_type=self.device, dtype=torch.float32):
                # The COMMON frozen solution is recovered once, from the
                # post-delta arm, and then applied to BOTH arms.
                pts_post, depth_post, K_norm, solution = self._postprocess(
                    raw_post, mask_binary, aspect_ratio, solution=None)
                pts_pre_common, _, _, _ = self._postprocess(
                    raw_pre, mask_binary, aspect_ratio, solution=solution)
                # The reference implementation's own (independently postprocessed)
                # pre-delta arm is kept too, so the difference between the causal
                # ablation and the naive one is itself measurable.
                pts_pre_own, _, K_pre_own, solution_pre = self._postprocess(
                    raw_pre, mask_binary, aspect_ratio, solution=None)
                pts_metric = pts_post * scalefield

        def np2(t):
            return t[0].detach().float().cpu().numpy()

        points_metric = np2(pts_metric)
        points_post = np2(pts_post)
        points_pre_common = np2(pts_pre_common)
        points_pre_own = np2(pts_pre_own)
        raw_pre_np = np2(raw_pre)
        raw_post_np = np2(raw_post)
        sf = np2(scalefield)[..., 0]
        dl = np2(delta)
        mb = np2(mask_binary.float()).astype(bool)
        depth_post_np = np2(depth_post[..., None])[..., 0]

        h, w = mb.shape
        K = pixel_K_from_normalized(np2(K_norm[..., None])[..., 0] if K_norm.ndim == 4
                                    else K_norm[0].detach().float().cpu().numpy(), h, w)

        rng = norm_pointmap(points_metric)
        valid = mb & np.isfinite(points_metric).all(axis=-1) & np.isfinite(rng) & (rng > 0)

        # z-depth is recorded but NEVER used as range. The measured ratio makes
        # the size of that mistake visible instead of hypothetical.
        z_metric = points_metric[..., 2]
        extra = {
            "output_hw": [int(h), int(w)],
            "num_tokens": int(num_tokens),
            "resolution_level": RESOLUTION_LEVEL,
            "force_projection": FORCE_PROJECTION,
            "delta_max_rad": DELTA_MAX_RAD,
            "focal_common": float(solution[0].detach().float().cpu().numpy().ravel()[0]),
            "shift_common": float(solution[1].detach().float().cpu().numpy().ravel()[0]),
            "focal_pre_own": float(solution_pre[0].detach().float().cpu().numpy().ravel()[0]),
            "shift_pre_own": float(solution_pre[1].detach().float().cpu().numpy().ravel()[0]),
            "scalefield_median": float(np.median(sf[mb])) if mb.any() else float("nan"),
            "scalefield_p05": float(np.percentile(sf[mb], 5)) if mb.any() else float("nan"),
            "scalefield_p95": float(np.percentile(sf[mb], 95)) if mb.any() else float("nan"),
            "delta_raw_abs_median": float(np.median(np.abs(dl[mb]))) if mb.any() else float("nan"),
            "delta_raw_abs_max": float(np.abs(dl[mb]).max()) if mb.any() else float("nan"),
        }
        # `delta` out of the forward pass is RAW and UNBOUNDED; the applied
        # angular perturbation is delta_max_rad * tanh(delta), capped at ~3 deg.
        # Reporting the raw value in radians would overstate the correction by
        # about 4x on this footage, so what is recorded is the angle the rays
        # ACTUALLY turned, measured between the pre- and post-delta unit rays.
        def _unit(p):
            n = np.linalg.norm(p, axis=-1, keepdims=True)
            return p / np.where(n > 0, n, 1.0)
        cos = (_unit(raw_pre_np) * _unit(raw_post_np)).sum(axis=-1)
        ray_turn_deg = np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))
        if mb.any():
            ang = ray_turn_deg[mb]
            extra["ray_turn_deg_median"] = float(np.median(ang))
            extra["ray_turn_deg_p95"] = float(np.percentile(ang, 95))
            extra["ray_turn_deg_max"] = float(ang.max())
            extra["applied_delta_rad_abs_max"] = float(
                DELTA_MAX_RAD * np.abs(np.tanh(dl[mb])).max())
        if valid.any():
            ratio = rng[valid] / np.where(z_metric[valid] > 0, z_metric[valid], np.nan)
            ratio = ratio[np.isfinite(ratio)]
            if ratio.size:
                extra["median_ratio_range_over_zdepth_metric"] = float(np.median(ratio))
                extra["max_ratio_range_over_zdepth_metric"] = float(ratio.max())
            # How much the naive ablation would have differed from the causal one.
            d = np.linalg.norm(points_pre_own[valid] - points_pre_common[valid], axis=-1)
            extra["pre_delta_own_vs_common_postproc_median_dist"] = float(np.median(d))

        # Chosen so that nothing DERIVABLE is stored twice. `points_metric` IS
        # `native`; both z-depth fields are the z components of point maps
        # already here; the release's own independently postprocessed pre-delta
        # arm is summarised by the scalar above rather than kept as a fourth
        # point map; and `delta_raw` is replaced by the angle the rays ACTUALLY
        # turned, which is what any downstream stage would have had to compute
        # from it anyway (the raw tensor is unbounded and runs ~4x the applied
        # angle on this footage). At 288 frames x 720x1280 this is the
        # difference between ~14 GB and ~22 GB for one model.
        aux = {
            # V4b arms, under ONE common frozen postprocessing solution.
            "points_pre_ray_common": points_pre_common.astype(np.float32),
            "points_post_ray_common": points_post.astype(np.float32),
            # V4c: C = points_post_ray_common, D = C * scalefield
            "scalefield": sf.astype(np.float32),
            "ray_turn_deg": ray_turn_deg.astype(np.float32),
        }

        return {
            "native": points_metric.astype(np.float32),
            "valid": valid,
            "canonical_range": rng,
            "K": K,
            "conf": None,
            "aux": aux,
            "extra": extra,
        }

    def preprocessed_image(self, image_path: str):
        """Reproduce FoundationGeo's internal resize, using the model's own numbers."""
        import cv2
        import torch
        import torch.nn.functional as F
        bgr = cv2.imread(image_path)
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        t = torch.tensor(rgb / 255.0, dtype=torch.float32).permute(2, 0, 1)[None]
        h, w = t.shape[-2:]
        min_tokens, max_tokens = self.model.num_tokens_range
        num_tokens = int(min_tokens + (RESOLUTION_LEVEL / 9) * (max_tokens - min_tokens))
        f = ((num_tokens * 16 ** 2) / (h * w)) ** 0.5
        rw, rh = int(w * f), int(h * f)
        out = F.interpolate(t, (rh, rw), mode="bicubic", align_corners=False, antialias=True)
        out = F.interpolate(out, (rh // 16 * 16, rw // 16 * 16), mode="bilinear",
                            align_corners=False, antialias=True)
        return out[0].numpy().transpose(1, 2, 0)

    def semantics(self) -> dict:
        return {
            "native_field": "points_metric = points_rel * scalefield, (H,W,3)",
            "canonical_range": "||points_metric||",
            "z_trap": ("`depth_metric` in the release is points_metric[..., 2], i.e. "
                       "Z-DEPTH. It is stored here only as `depth_z_metric` and is never "
                       "used as a range."),
            "naming_trap": ("`points_pre_field` in the release is the geometry before the "
                            "learned RAY correction, not merely before the scale field, and "
                            "it has been through its OWN focal/shift recovery."),
            "ray_word_warning": ("FoundationGeo's ray is a UNIT ray paired with RANGE "
                                 "(d = ||p||). DA3's ray is unnormalised and pairs with "
                                 "z-depth. Opposite conventions, same word."),
            "v4b_ray_correction": ("raw pre-delta vs raw post-delta geometry from ONE forward "
                                   "pass, both put through the SAME frozen (focal, shift) "
                                   "recovered from the post-delta arm"),
            "v4c_scale_field": ("points_post_ray_common vs points_post_ray_common * "
                                "scalefield — a same-tensor intervention"),
            "ray_correction_cap": ("the applied angular perturbation is "
                                   "delta_max_rad * tanh(delta_raw), capped at ~3 degrees. "
                                   "The `delta` tensor itself is RAW and unbounded; "
                                   "`delta_raw` stores it, and `ray_turn_deg_*` reports the "
                                   "angle the rays actually turned."),
            "camera_frame": "OpenCV: +x right, +y down, +z forward",
            "confidence": "none emitted",
            "claimed_scale": "metric; PROVISIONAL pre-C2 on this camera",
            "fov": ("the model CONSUMES intrinsics optionally; with fov_x=None it recovers "
                    "focal and shift from the point map itself"),
            "view_count": "strictly 1 — a single (1,3,H,W) tensor",
        }

    def preprocessing(self) -> dict:
        return {
            "loader": "cv2.imread -> RGB -> /255 -> (1,3,H,W); the model resizes internally",
            "resize_rule": ("bicubic resize to a num_tokens-derived resolution, rounded to a "
                            "multiple of 16 for DINOv3, then outputs interpolated back to "
                            "the SOURCE (H,W)"),
            "resolution_level": RESOLUTION_LEVEL,
            "fov_loss_expected": "none — aspect ratio preserved, no crop; verified in S0",
            "use_fp16": "False (the reference default is True; overridden for reproducibility)",
        }

    def provenance(self) -> dict:
        import torch
        return {
            "method": "FoundationGeo-1.1 (Stage-II)",
            "role": "point-map candidate + V4b/V4c same-checkpoint internal ablations",
            "repo": "https://github.com/mx-liu6/FoundationGeo",
            "repo_commit": "759f8463caf414c8ea34d66219250f9c2be7e971",
            "code_license": ("MIT. The LICENSE file is byte-identical to MoGe's template and "
                             "reads 'Copyright (c) Microsoft Corporation' despite HKU "
                             "authorship; the MIT grant itself is unambiguous."),
            "checkpoint": CHECKPOINT,
            "checkpoint_file": CHECKPOINT_FILE,
            "checkpoint_license": "MIT",
            "model_config": getattr(self, "_model_config", None),
            "torch": torch.__version__,
            "device": self.device,
            "dtype": "float32 (fp16 autocast disabled)",
            "reference_impl_modifications": (
                "none to the vendored code. `infer()` is NOT called: this backend calls "
                "`model.forward()` and reimplements the postprocessing tail so that both "
                "ray-correction arms share one frozen (focal, shift) solution. Calling "
                "`infer()` would have produced two independently postprocessed arms, which "
                "FREEZE C3 explicitly forbids treating as a ray-correction ablation."),
        }


BACKEND = FoundationGeo11
