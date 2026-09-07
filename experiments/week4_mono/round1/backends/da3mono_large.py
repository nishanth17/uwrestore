"""Backend 6 — Depth Anything 3, monocular series (`DA3MONO-LARGE`).

Runs in `experiments/week4_mono/.venv-mono`.

ROLE (FREEZE §3.6): the modern DIRECT-DEPTH relative model. It earns its
mandatory slot because it predicts depth rather than inverse depth, which is
materially different for a range-driven physical model — not because it is
newer than DA V2.

AMBIGUITY (FREEZE §C1). The literature classification is affine-in-depth /
Class 3: DA3's teacher outputs scale-AND-shift-invariant DEPTH, and the
monocular student is trained from those targets. So the E1 family this backend
declares is `d' = s*d + t`. S2 additionally tests whether the simpler subgroup
`d' = s*d` is empirically indistinguishable on this domain; only measured
evidence may earn an "approximately scale-only" description, and nothing here
asserts one.

THE NAMING TRAP THE FREEZE CALLS OUT. DA3 and FoundationGeo both say "ray" and
mean structurally different things: DA3 pairs an UNNORMALISED ray with
Z-DEPTH, FoundationGeo pairs a UNIT ray with RANGE. Read side by side without
checking norms and you get it backwards.

WHAT S0 ACTUALLY MEASURED, WHICH IS NOT WHAT THE MAIN DA3 SERIES DOES. The
`da3mono-large` config is a DINOv2 ViT-L with a single DPT head of
`output_dim: 1`. There is no ray branch, no camera decoder and no confidence
head. Empirically the returned `Prediction` carries `depth` and `sky` and
NOTHING else — `intrinsics`, `extrinsics` and `conf` are all None.

That has a consequence the freeze's "no accidental use of z-depth where range
is required" rule forces into the open: **this backend cannot emit a canonical
range.** Range needs a camera, and this model does not have one. Inventing a
plausible focal to convert with would manufacture the exact radial error M-6
exists to detect. So `canonical_range` is None here, exactly as it is for
Depth Anything V2, and the range conversion is deferred to the frozen S2
policy, which supplies a camera as an explicit, recorded evaluation
convention rather than a silent backend assumption.

It also leaves the z-vs-range question about the native field genuinely open,
since the reference implementation's own `unproject_depth` (which treats depth
as z) is never reached for this checkpoint. S2 settles it by measurement:
this camera's secant factor spans about 1.0 to 1.35 across the frame, which is
far too large a signal to miss when the field is fitted against the reference
range and against the reference z-depth in turn.
"""

from __future__ import annotations

import os

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import numpy as np

from experiments.week4_mono.round1.backends.base import MonoBackend

CHECKPOINT = "depth-anything/DA3MONO-LARGE"

#: Reference-implementation defaults for `DepthAnything3.inference`, pinned so
#: they are recorded constants rather than per-stage choices.
PROCESS_RES = 504
PROCESS_RES_METHOD = "upper_bound_resize"


class DA3MonoLarge(MonoBackend):
    key = "da3mono_large"
    checkpoint = CHECKPOINT
    native_kind = "depth_relative"
    range_rule = "unresolved"

    def _load(self) -> None:
        import torch
        from depth_anything_3.api import DepthAnything3
        self._torch = torch
        model = DepthAnything3.from_pretrained(CHECKPOINT)
        self.model = model.to(device=torch.device(self.device)).eval()
        self._model_name = getattr(model, "model_name", None)

    def _infer(self, image_path: str) -> dict:
        torch = self._torch
        with torch.no_grad():
            pred = self.model.inference(
                [image_path],                      # exactly one view
                process_res=PROCESS_RES,
                process_res_method=PROCESS_RES_METHOD,
                export_dir=None,
            )
        depth = np.asarray(pred.depth)             # (N,H,W)
        if depth.shape[0] != 1:
            raise RuntimeError(f"strict N=1 violated: got {depth.shape[0]} predictions")
        d = depth[0].astype(np.float32)
        valid = np.isfinite(d) & (d > 0)

        conf = None
        if pred.conf is not None:
            conf = np.asarray(pred.conf)[0].astype(np.float32)

        h, w = d.shape
        extra = {
            "output_hw": [int(h), int(w)],
            # `is_metric` comes back as an empty addict Dict for this checkpoint,
            # i.e. falsy, so it is recorded as a bool rather than coerced to int.
            "is_metric": bool(getattr(pred, "is_metric", None)),
            "scale_factor": (None if pred.scale_factor is None else float(pred.scale_factor)),
            "aux_keys": sorted(pred.aux.keys()) if getattr(pred, "aux", None) else [],
            "emits_intrinsics": pred.intrinsics is not None,
            "emits_extrinsics": pred.extrinsics is not None,
            "emits_conf": conf is not None,
            "emits_sky": pred.sky is not None,
            "process_res": PROCESS_RES,
            "process_res_method": PROCESS_RES_METHOD,
        }
        if valid.any():
            extra["depth_min"] = float(d[valid].min())
            extra["depth_max"] = float(d[valid].max())
        aux = {}
        if pred.sky is not None:
            sky = np.asarray(pred.sky)[0]
            aux["sky"] = np.asarray(sky, dtype=np.float32)
            extra["sky_fraction_gt_half"] = float((np.asarray(sky) > 0.5).mean())
        if pred.processed_images is not None:
            extra["processed_image_hw"] = [int(pred.processed_images.shape[1]),
                                           int(pred.processed_images.shape[2])]

        return {
            "native": d,
            "valid": valid,
            "canonical_range": None,
            "K": None,
            "conf": conf,
            "aux": aux,
            "extra": extra,
        }

    def preprocessed_image(self, image_path: str):
        # DA3 hands back the processed image it actually consumed, so the probe
        # needs no reimplementation of its input pipeline.
        torch = self._torch
        with torch.no_grad():
            pred = self.model.inference([image_path], process_res=PROCESS_RES,
                                        process_res_method=PROCESS_RES_METHOD,
                                        export_dir=None)
        return np.asarray(pred.processed_images)[0].astype(np.float32)

    def semantics(self) -> dict:
        return {
            "native_field": "prediction.depth (N,H,W), N=1",
            "native_meaning": ("relative depth, larger is farther. The MAIN DA3 series "
                               "pairs this field with predicted rays and its own "
                               "`unproject_depth` treats it as PLANAR z-depth. This "
                               "monocular checkpoint emits no rays and no camera, so that "
                               "code path is never reached and the convention is NOT "
                               "established by the wrapper. S2 settles it by measurement."),
            "canonical_range": ("NONE HERE. The head is output_dim=1 with no camera branch, "
                                "so there is no intrinsics to convert with. Supplying an "
                                "invented focal would manufacture a radial error."),
            "emits": "depth and sky only; intrinsics, extrinsics and conf are all None",
            "ray_word_warning": ("DA3's 'ray' is UNNORMALISED and pairs with z-depth. "
                                 "FoundationGeo's 'ray' is UNIT and pairs with range. The "
                                 "two are not interchangeable."),
            "documented_ambiguity": ("affine in depth / Class 3: the DA3 teacher outputs "
                                     "scale-shift-invariant DEPTH and the mono student is "
                                     "trained from those targets"),
            "e1_family": "d' = s*d + t (S2 also tests the s-only subgroup empirically)",
            "camera_frame": "OpenCV: +x right, +y down, +z forward",
            "confidence": "prediction.conf where the checkpoint emits one",
            "claimed_scale": "relative; is_metric is recorded per frame",
            "view_count": "strictly 1 — a one-element image list, count asserted",
        }

    def preprocessing(self) -> dict:
        return {
            "loader": "depth_anything_3.utils.io.input_processor.InputProcessor",
            "process_res": PROCESS_RES,
            "process_res_method": PROCESS_RES_METHOD,
            "resize_rule": ("upper_bound_resize toward process_res with patch-size "
                            "rounding; outputs stay on the PROCESSED grid, not the source "
                            "grid, so a source->grid map is required to evaluate"),
            "fov_loss_expected": "measured in S0, not assumed",
        }

    def provenance(self) -> dict:
        import torch
        return {
            "method": "Depth Anything 3 — monocular series, Large",
            "role": "modern direct-depth relative model",
            "repo": "https://github.com/ByteDance-Seed/Depth-Anything-3",
            "repo_commit": "3d835ec1a5802d64a8b8b15f817a1ab54809bfe4",
            "code_license": "Apache-2.0",
            "checkpoint": CHECKPOINT,
            "checkpoint_license": "Apache-2.0",
            "model_name": getattr(self, "_model_name", None),
            "torch": torch.__version__,
            "device": self.device,
            "dtype": "float32",
            "reference_impl_modifications": (
                "two, both packaging-only and neither touching the model: (1) "
                "pyproject requires-python widened from '<=3.13' to '<3.14' so it "
                "installs on CPython 3.13.5; (2) the pycolmap-backed COLMAP EXPORT "
                "import in utils/export/__init__.py made optional, because importing "
                "pycolmap alongside torch aborts on macOS with a duplicate libomp. "
                "The export path is never used here. Patch: "
                "patches/da3_no_pycolmap_and_python313.patch"),
        }


BACKEND = DA3MonoLarge
