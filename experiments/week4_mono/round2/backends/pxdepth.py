"""R2-4 — PXDepth, NATIVE path only.

Runs in `experiments/week4_mono/round2/.venv-pxdepth`.

WHY IT IS TESTED (task §10). PXDepth is the structure-preserving pixel-space
depth challenger: the claim under test is sharper, better-localised depth
boundaries, which is exactly what M-4 and the mandatory thin-structure test at
the `wreck_07` crane lattice measure.

THE ATTRIBUTION RULE THIS BACKEND EXISTS TO ENFORCE. The released repository
recovers metric scale by loading MoGe-2 and solving two affine parameters
against its prediction. Using a helper model's scale is NOT allowed for the
primary Round-2 geometry comparison. So this backend calls `forward()` --
documented in `PXDepth.py:188` as "Run the network without metric-scale
alignment" -- and NEVER `infer()`. `_reference_model` (the MoGe-2 handle) is
reachable only from `infer()`, so MoGe-2 is not merely unused, it is
unreachable on this code path; S0 confirmed `moge2_loaded == False` on every
probe image. Any MoGe-assisted metric reconstruction is a separate OPTIONAL
deployment-style diagnostic and may never replace this native result.

NATIVE REPRESENTATION AND ITS GAUGE. `forward()` returns
`depth_log1p_affine_invariant` and `mask`. The release's own recovery is
`depth = expm1(a * pred + b)` (`inference.py:174,189,195`), so the ambiguity is
affine IN LOG1P-DEPTH -- a group that is neither affine-in-depth nor
affine-in-disparity. That is why `log1p_depth_affine_invariant` was added to
`monoio.NATIVE_KINDS` and `affine_log1p_depth` to `alignment.FAMILIES`: the
frozen S2 POLICY is unchanged (clip scope, Huber IRLS, reference side converted
by the caller); only the SPACE is representation-specific.

The underlying physical quantity is projective z-depth, not ray range:
`scripts/infer.py:121` back-projects the recovered depth with
`utils3d.pt.depth_map_to_point_map(depth, intrinsics)`, which scales
unnormalised `K^-1` rays. The network emits NO intrinsics and NO point map, so
there is no model-native geometry independent of MoGe-2.

LICENCE: UNDECLARED. The repository ships no LICENSE file and the Hugging Face
model card is a 0-byte README. Recorded as undeclared and treated as
research-only. Not invented.

CATEGORY B, three entries. (1) Device placement: CPU. MPS raises
`Invalid buffer size: 23.26 GiB` in `Gated_Attention.py:97` because MPS SDPA
materialises the full score matrix for ~20-28k tokens and `precision.py` grants
autocast only on CUDA, so MPS is always fp32. Moving the process to CPU changes
no arithmetic. (2) The released `scripts/infer.py` is BROKEN as published --
line 74 does `from pxdepth.inference import parse_size, resize_image,
resize_map`, and no module `pxdepth.inference` exists, nor is any of those three
names defined anywhere in the repository -- so the preprocessing is
reimplemented to the repo's OWN documented policy (`infer.py:26-32`:
`--input-size 1022x770`, `--resize-by-area` default True, i.e. preserve the
source aspect at that pixel area), rounded to the patch size that
`PXDepth.py:210` requires. (3) `use_fp32=True`, the release's own fp32 switch.
No operator substitution, no interpolation-mode change, no resolution change to
make memory fit, no checkpoint substitution, no helper model.
"""

from __future__ import annotations

import os
import sys

import numpy as np

from experiments.week4_mono.round1.backends.base import MonoBackend
from experiments.week4_mono.round1.common import W4

ROUND2 = os.path.join(W4, "round2")
CODE = os.path.join(ROUND2, "vendor", "PXDepth")

#: `scripts/infer.py:26-32` — the released default input size, used by area.
INPUT_W, INPUT_H = 1022, 770
AREA = INPUT_W * INPUT_H
USE_FP32 = True


class PXDepthNative(MonoBackend):

    key = "pxdepth"
    checkpoint = "yuanzhy29/PXDepth"
    native_kind = "log1p_depth_affine_invariant"
    # No honest range exists before S2 fixes (a, b): expm1 of an unfitted
    # log1p field is not a depth, and there are no intrinsics to turn a depth
    # into a range. Same discipline as the Round-1 DA V2 backend.
    range_rule = "unresolved"

    def __init__(self, device: str = "cpu", **kw):
        super().__init__(device, **kw)
        if device != "cpu":
            raise SystemExit(
                "PXDepth runs on CPU here: MPS raises 'Invalid buffer size: "
                "23.26 GiB' in Gated_Attention.py:97 (MPS SDPA materialises the "
                "full score matrix, and precision.py grants autocast only on "
                "CUDA). Lowering the resolution to fit is forbidden.")

    def _load(self) -> None:
        import glob
        from pathlib import Path
        import torch
        if CODE not in sys.path:
            sys.path.insert(0, CODE)
        from pxdepth import PXDepth
        self._torch = torch
        cands = sorted(Path.home().glob(
            ".cache/huggingface/hub/models--yuanzhy29--PXDepth/snapshots/*/model.pt"))
        if not cands:
            raise SystemExit("PXDepth checkpoint not found in the HF cache")
        self._ckpt_path = str(cands[0])
        model = PXDepth.from_pretrained(self._ckpt_path, strict=True)
        self.model = model.to(self.device).eval()
        self._patch = int(self.model.patch_size)
        self._n_param = int(sum(p.numel() for p in self.model.parameters()))

    def _run_size(self, w0: int, h0: int) -> tuple[int, int]:
        """The repo's documented area-preserving resize, snapped to the patch size."""
        ar = w0 / h0
        w = int(round((AREA * ar) ** 0.5 / self._patch)) * self._patch
        h = int(round((AREA / ar) ** 0.5 / self._patch)) * self._patch
        return w, h

    def _tensor(self, image_path: str):
        from PIL import Image
        torch = self._torch
        im = Image.open(image_path).convert("RGB")
        w0, h0 = im.size
        w, h = self._run_size(w0, h0)
        a = np.asarray(im.resize((w, h), Image.LANCZOS), dtype=np.float32) / 255.0
        t = torch.from_numpy(a).permute(2, 0, 1)[None]
        return t, (w0, h0), (w, h)

    def _infer(self, image_path: str) -> dict:
        torch = self._torch
        t, (w0, h0), (w, h) = self._tensor(image_path)
        with torch.no_grad():
            # forward(), never infer(): MoGe-2 is unreachable on this path.
            out = self.model.forward(t.to(self.device), use_fp32=USE_FP32)
        d = out["depth_log1p_affine_invariant"][0].float().cpu().numpy()
        m = out["mask"][0].float().cpu().numpy()

        valid = np.isfinite(d) & (m > 0.5)
        extra = {
            "source_hw": [int(h0), int(w0)],
            "output_hw": [int(d.shape[0]), int(d.shape[1])],
            "run_wh": [int(w), int(h)],
            "source_aspect": round(w0 / h0, 6),
            "run_aspect": round(w / h, 6),
            "input_area_px": AREA,
            "patch_size": self._patch,
            "use_fp32": USE_FP32,
            "mask_gt_0p5_frac": float((m > 0.5).mean()),
            "native_min": float(np.nanmin(d)),
            "native_max": float(np.nanmax(d)),
            "moge2_reachable_on_this_path": False,
            "moge2_loaded": any(k == "moge" or k.startswith("moge.")
                                for k in sys.modules),
        }
        return {"native": d.astype(np.float32), "valid": valid,
                "canonical_range": None, "K": None, "conf": m.astype(np.float32),
                "aux": {"mask_prob": m.astype(np.float32)}, "extra": extra}

    def preprocessed_image(self, image_path: str):
        t, _, _ = self._tensor(image_path)
        return t[0].numpy().transpose(1, 2, 0)

    def semantics(self) -> dict:
        return {
            "native_field": "depth_log1p_affine_invariant (H,W) float32",
            "native_meaning": ("log1p of depth, up to an affine transform IN THAT SPACE: "
                               "depth = expm1(a * native + b)"),
            "native_gauge_evidence": ("PXDepth.py:226 returns "
                                      "{'depth_log1p_affine_invariant','mask'}; "
                                      "inference.py:174 builds ref_log = log1p(ref_depth), "
                                      ":189 solves a*pred + b, :195 recovers "
                                      "depth = expm1(a*pred + b)"),
            "underlying_quantity": ("projective z-depth, NOT ray range — infer.py:121 "
                                    "back-projects with depth_map_to_point_map(depth, K), "
                                    "which scales unnormalised K^-1 rays"),
            "legal_alignment": "affine_log1p_depth (2-DOF, fitted in log1p-depth)",
            "illegal_alignment": ("a*d + b in depth or a*q + b in disparity — different "
                                  "transform groups, not stricter ones"),
            "range_conversion": ("NONE HERE. After S2 fixes (a,b): z = expm1(a*native+b), "
                                 "then r = z * ||K^-1 [u,v,1]|| with the FROZEN provisional "
                                 "camera, because the network emits no intrinsics."),
            "camera": "no intrinsics, no FOV, no point map emitted",
            "native_point_geometry_independent_of_moge2": False,
            "mask": "out['mask'] is a probability; validity is mask > 0.5",
            "confidence": "the mask probability is persisted; not interpreted as confidence",
            "claimed_scale": "relative only; the release's metric recovery uses MoGe-2",
            "moge2_role": ("solves only the two affine parameters inside infer(). Never "
                           "called here. A MoGe-assisted metric reconstruction may be "
                           "recorded separately as an OPTIONAL deployment diagnostic and "
                           "may never replace this native result."),
            "license": ("UNDECLARED — no LICENSE file in the repo, 0-byte HF model card. "
                        "Treated as research-only. Not invented."),
            "view_count": "strictly 1 — forward() takes a single (1,3,H,W) tensor",
        }

    def preprocessing(self) -> dict:
        return {
            "loader": "PIL -> RGB -> /255 -> (1,3,H,W) float32",
            "resize_rule": ("the repo's OWN documented policy, reimplemented because the "
                            "released CLI is broken: preserve the source aspect at "
                            f"{INPUT_W}x{INPUT_H} = {AREA} px, rounded to the patch size "
                            "required by PXDepth.py:210"),
            "resize_filter": "PIL LANCZOS",
            "input_area_px": AREA,
            "aspect_drift": ("1280x720 (1.7778) -> 1176x672 (1.7500), a 1.6 % drift that is "
                             "the minimum achievable under the patch-14 divisibility "
                             "constraint at this area. NOT a crop: the whole frame is kept."),
            "output_grid": ("the run grid, not the source grid — the release's own "
                            "`resize_map` helper is one of the three names its broken CLI "
                            "imports from a nonexistent module, so nothing is invented "
                            "here. The S0 FOV audit measures the source->grid map."),
            "fov_loss_expected": "none — full frame retained, slight anisotropic rescale",
            "use_fp32": USE_FP32,
        }

    def provenance(self) -> dict:
        import torch
        return {
            "method": "PXDepth (native, no metric alignment)",
            "role": "R2-4 challenger: structure-preserving pixel-space depth",
            "repo": "https://github.com/yuanzhy29/PXDepth",
            "code_copy_path": CODE,
            "checkpoint": "yuanzhy29/PXDepth model.pt",
            "checkpoint_path": getattr(self, "_ckpt_path", None),
            "checkpoint_load": "from_pretrained(..., strict=True)",
            "n_parameters": getattr(self, "_n_param", None),
            "code_license": "UNDECLARED (no LICENSE file)",
            "checkpoint_license": "UNDECLARED (0-byte model card)",
            "license_disposition": "research-only",
            "torch": torch.__version__,
            "device": self.device,
            "dtype": "float32",
            "impl_category": "B",
            "reference_impl_modifications": [
                "device placement: cpu (MPS OOMs at 23.26 GiB in Gated_Attention.py:97; "
                "precision.py grants autocast only on cuda). Arithmetic unchanged.",
                "preprocessing reimplemented to the repo's own documented policy because "
                "scripts/infer.py:74 imports three names from a nonexistent module "
                "`pxdepth.inference` and the released CLI therefore cannot run at all",
                "use_fp32=True — the release's own fp32 switch",
            ],
            "not_modified": ("forward() only, never infer(); no MoGe-2; no operator "
                             "substitution; no resolution change to fit memory; no "
                             "checkpoint substitution"),
        }


BACKEND = PXDepthNative
