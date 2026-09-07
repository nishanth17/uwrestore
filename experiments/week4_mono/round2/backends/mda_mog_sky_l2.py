"""R2-6 — MDA `mda_mog_sky_l2` (checkpoint DA3_MOG_Sky_LogL2).

Runs in `experiments/week4_mono/round2/.venv-mda_mog_sky_l2`.

WHY IT IS TESTED (task §12). Round 1 observed that DA3 Mono fills the open
crane lattice of `wreck_07` with a solid surface. MDA replaces DA3's single
depth regression with a MIXTURE head: several depth experts plus a mixing
weight, from which a per-pixel mode is recovered. That is a direct, mechanistic
candidate answer to the solid-fill failure, which is why this and not the VGGT
variant is the model under test.

WHAT THE MIXTURE ACTUALLY RETURNS, MEASURED FROM SOURCE. `find_gmm_mode_gpu_chunk`
(`mog_inference.py:196-256`) does NOT hard-select an expert. It builds a
CANDIDATE set — the N expert means followed by confidence-weighted pairwise
midpoints (`:109-138`) — scores every candidate by mixture NLL, keeps the best
per pixel (`_RunningBest`, :141-163) and then moves it with LBFGS. So the
returned index names which INITIALISATION won, and the returned depth is a
continuous optimum, not an expert's own prediction. S0 measured that 55-85 % of
pixels select a midpoint rather than an expert mean.

Everything the mixture exposes is persisted per frame — component depths,
component confidences, mixing log-weights, the winning candidate index and the
sky mask — so §12's questions (entropy, top-1 margin, component separation,
behaviour at the crane lattice) are answerable later WITHOUT re-inference.
Per §12 these quantities are NOT called calibrated confidence.

THE SKY MASK IS A FINDING, NOT A NUISANCE. `use_sky_mask=True` is the demo
default, and `da3_wrapper.py:275-296` pushes every pixel it calls sky to twice
the maximum valid depth. On the hazy `wreck_05` probe frame it claimed 26.7 %
of the image. Underwater footage contains no sky. The default is kept so the
model is measured as released, and the mask is persisted per frame so the
effect is attributable rather than silently mixed into the geometry.

CATEGORY B: device placement (`model_choice.py` hardcodes cuda-or-cpu) and a
working-directory change so the release's relative checkpoint paths resolve.
The official helpers `choose_model` / `prepare_views` / `DA3Wrapper.inference`
are called on a ONE-ELEMENT file list, which is exactly `demo.py:304`'s
monocular path. No model math, resolution, checkpoint or operator change.
"""

from __future__ import annotations

import os

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import sys

import numpy as np

from experiments.week4_mono.round1.backends.base import MonoBackend
from experiments.week4_mono.round1.common import W4

ROUND2 = os.path.join(W4, "round2")
MDA = os.path.join(ROUND2, "vendor", "MDA")

MODEL_NAME = "mda_mog_sky_l2"
SIZE = 512                # demo.py DemoConfig.size default (long edge)
USE_SKY_MASK = True       # demo default; kept so the model is measured as released


class MDAMoGSkyL2(MonoBackend):

    key = "mda_mog_sky_l2"
    checkpoint = "sy000/MDA :: DA3_MOG_Sky_LogL2.ckpt"
    native_kind = "depth_relative"
    # Same discipline as the Round-1 DA3 backend: the scalar is projective
    # z-depth whose gauge S2 has not fitted yet, so no canonical range is
    # written here. S2 resolves (s, t) and only then is r = (s*z + t) * rho.
    range_rule = "unresolved"

    def _load(self) -> None:
        import torch
        self._cwd0 = os.getcwd()
        os.chdir(MDA)                       # model_choice resolves ckpt paths relatively
        if MDA not in sys.path:
            sys.path.insert(0, MDA)
        import add_ckpt_path  # noqa: F401   side-effect: extends sys.path
        from src.testing.utils.model_choice import choose_model
        from src.testing.run_inference_video import prepare_views
        self._torch = torch
        self._prepare_views = prepare_views

        loaded = choose_model(MODEL_NAME)
        self._loaded = loaded
        self._patch = int(loaded.patch_size)
        self._img_norm = loaded.img_norm
        self._ckpt_path = str(getattr(loaded, "checkpoint_path", ""))
        self.model = loaded.model.to(self.device).eval()
        # `is_mog` is derived by the wrapper from the presence of head_mog; it
        # is asserted rather than assumed, because a False here would silently
        # turn the mixture challenger into a plain DA3 rerun.
        if not hasattr(self.model.net, "head_mog"):
            raise SystemExit("this checkpoint has no head_mog: it is not the mixture model")

    def _infer(self, image_path: str) -> dict:
        torch = self._torch
        # ONE path in a one-element list -- the official monocular path. The
        # view dimension L is asserted below, so N=1 is checked every frame
        # rather than trusted.
        views = self._prepare_views([str(image_path)], SIZE, self._patch, self._img_norm)
        if len(views) != 1:
            raise SystemExit(f"prepare_views returned {len(views)} views for one image")
        with torch.no_grad():
            out = self.model.inference(views, self.device, is_mog=True,
                                       use_sky_mask=USE_SKY_MASK,
                                       crop_center_112=False, cam_inp=False,
                                       gt_cam_output=False, output_normalize=False)

        depth = out["depth"]
        if depth.shape[1] != 1:
            raise SystemExit(f"view dimension is {depth.shape[1]}, not 1 -- N=1 violated")
        z = depth[0, 0].float().cpu().numpy()                    # (H,W) z-depth
        h, w = z.shape

        raw = out.get("raw_preds") or {}
        comps = raw.get("depth") or []
        comp_d = np.stack([c[0, 0].float().cpu().numpy() for c in comps], 0) \
            if comps else None
        confs = raw.get("depth_conf") or []
        comp_c = np.stack([c[0, 0].float().cpu().numpy() for c in confs], 0) \
            if confs else None
        logw = raw.get("mog_weight")
        logw = logw[0, 0].float().cpu().numpy() if logw is not None else None
        idx = raw.get("indices")
        idx = idx[0, 0].cpu().numpy().astype(np.int16) if idx is not None else None
        sky = out.get("sky_mask")
        sky = np.asarray(sky[0, 0].float().cpu().numpy() > 0.5) if sky is not None else None
        conf = out.get("depth_conf")
        conf = conf[0, 0].float().cpu().numpy() if conf is not None else None

        # The model's own camera, from its 9-vector pose encoding
        # (transform.py:42-66: T(3), quat(4), fov_h, fov_w).
        K = None
        pose_enc = out.get("pose_enc")
        pe = None
        if pose_enc is not None and pose_enc.shape[-1] == 9:
            pe = pose_enc[0, 0].float().cpu().numpy()
            fov_h, fov_w = float(pe[7]), float(pe[8])
            fy = (h / 2.0) / max(np.tan(fov_h / 2.0), 1e-6)
            fx = (w / 2.0) / max(np.tan(fov_w / 2.0), 1e-6)
            K = np.array([[fx, 0.0, w / 2.0], [0.0, fy, h / 2.0], [0.0, 0.0, 1.0]])

        valid = np.isfinite(z) & (z > 0)

        extra = {
            "output_hw": [int(h), int(w)],
            "size_long_edge": SIZE,
            "patch_size": self._patch,
            "use_sky_mask": USE_SKY_MASK,
            "n_mixture_components": 0 if comp_d is None else int(comp_d.shape[0]),
            "view_dim_L": int(depth.shape[1]),
            "pose_enc": None if pe is None else [float(x) for x in pe],
            "fov_h_rad": None if pe is None else float(pe[7]),
            "fov_w_rad": None if pe is None else float(pe[8]),
        }
        if sky is not None:
            extra["sky_mask_frac"] = float(sky.mean())
        if logw is not None:
            wgt = np.exp(logw - logw.max(axis=-1, keepdims=True))
            wgt /= np.clip(wgt.sum(axis=-1, keepdims=True), 1e-12, None)
            ws = np.sort(wgt, axis=-1)
            extra["top1_prob_median"] = float(np.median(ws[..., -1]))
            extra["top1_minus_top2_median"] = float(np.median(ws[..., -1] - ws[..., -2]))
            ent = -(wgt * np.log(np.clip(wgt, 1e-12, None))).sum(-1)
            extra["entropy_median"] = float(np.median(ent))
            extra["entropy_max_possible"] = float(np.log(wgt.shape[-1]))
        if idx is not None and comp_d is not None:
            n = int(comp_d.shape[0])
            hist = np.bincount(idx.astype(np.int64).ravel(), minlength=n)
            extra["chosen_candidate_hist"] = hist.tolist()
            extra["chosen_candidate_midpoint_frac"] = float(hist[n:].sum()) / float(hist.sum())

        aux = {}
        if comp_d is not None:
            aux["component_depth"] = comp_d.astype(np.float32)
        if comp_c is not None:
            aux["component_conf"] = comp_c.astype(np.float32)
        if logw is not None:
            aux["mog_log_weight"] = logw.astype(np.float32)
        if idx is not None:
            aux["chosen_candidate_index"] = idx
        if sky is not None:
            aux["sky_mask"] = sky

        return {"native": z.astype(np.float32), "valid": valid,
                "canonical_range": None, "K": K, "conf": conf,
                "aux": aux, "extra": extra}

    def preprocessed_image(self, image_path: str):
        """The image on the model's own grid, via the release's own prepare_views."""
        views = self._prepare_views([str(image_path)], SIZE, self._patch, self._img_norm)
        return views[0]["img"][0].detach().cpu().numpy().transpose(1, 2, 0)

    def semantics(self) -> dict:
        return {
            "native_field": "depth (H,W) — the per-pixel mixture MODE",
            "native_meaning": ("projective z-depth, NOT ray range: "
                               "utils/geometry.py:275,291 unprojects as "
                               "ray_directions * z with UNNORMALISED rays, "
                               "identical to DA3"),
            "mixture": ("mog_inference.py:196-256 scores a candidate set (expert means "
                        "+ confidence-weighted pairwise midpoints, :109-138), keeps the "
                        "lowest-NLL candidate per pixel (:141-163) and refines it with "
                        "LBFGS. The persisted `chosen_candidate_index` names the winning "
                        "INITIALISATION, not a hard component selection."),
            "mixture_quantities": ("component_depth, component_conf, mog_log_weight, "
                                   "chosen_candidate_index persisted per frame. These are "
                                   "NOT called calibrated confidence (task §12)."),
            "sky_mask": ("da3_wrapper.py:275-296 sets sky pixels to 2x the maximum valid "
                         "depth. Underwater frames contain no sky; the released default "
                         "is kept and the mask persisted so its effect is attributable."),
            "legal_alignment": ("affine in z-depth (s*z + t), with the scale-only fit kept "
                                "as a diagnostic. The release does not declare a metric "
                                "scale for this checkpoint, so none is assumed."),
            "range_conversion": ("NONE HERE. r = (s*z + t) * ||K^-1 [u,v,1]|| once S2 has "
                                "fixed (s,t); K is the model's own, recovered from pose_enc."),
            "camera": ("pose_enc is a 9-vector (T, quat, fov_h, fov_w), transform.py:42-66. "
                       "Measured on wreck_07: fov_h 0.5894 rad, fov_w 0.9916 rad."),
            "confidence": "depth_conf emitted; persisted, not interpreted",
            "claimed_scale": "not declared by the release for this checkpoint",
            "view_count": ("strictly 1 — one image path per call, prepare_views returns one "
                           "view, and the view dimension L is asserted == 1 every frame. "
                           "S0 measured that A-alone differs from A-in-a-pair by 12.887, so "
                           "cross-view coupling is real and L==1 is load-bearing."),
        }

    def preprocessing(self) -> dict:
        return {
            "loader": ("official prepare_views (run_inference_video.py:151-225) on a "
                       "one-element list: load_images_for_eval_safe(size=512, crop=False, "
                       "square_ok=True), patch-size snap, centre crop to the snapped "
                       "aspect, bilinear+antialias resize"),
            "size_long_edge": SIZE,
            "normalisation": "IMAGENET_NORM (model_choice.py)",
            "output_grid": ("the model grid, e.g. 1280x720 -> 504x280. Aspect 1.800 vs "
                            "source 1.778; the S0 FOV audit measures the exact "
                            "source->grid map, including the anisotropy."),
            "fov_loss_expected": "small; measured by the S0 FOV audit, not assumed",
            "camera_pose_input": ("identity, and ray_map is all-NaN — the release's own "
                                  "no-camera-prior path (cam_inp=False)"),
        }

    def provenance(self) -> dict:
        import torch
        return {
            "method": "MDA mixture-of-depth (mda_mog_sky_l2)",
            "role": ("R2-6 challenger: multi-hypothesis depth, tested against Round-1's "
                     "observed solid-fill of the wreck_07 crane lattice"),
            "repo": "https://github.com/sy000/MDA",
            "code_copy_path": MDA,
            "checkpoint": "DA3_MOG_Sky_LogL2.ckpt (official)",
            "checkpoint_path": getattr(self, "_ckpt_path", None),
            "config": "src/depth_anything_3/configs/da3-giant-cam-mog-sky.yaml",
            "license": "Apache-2.0",
            "variant_note": "the VGGT variant is NOT added (task §12)",
            "torch": torch.__version__,
            "device": str(self.device),
            "dtype": "float32",
            "impl_category": "B",
            "reference_impl_modifications": [
                "device placement (model_choice.py hardcodes cuda-or-cpu)",
                "chdir to the release root so its relative checkpoint/config paths resolve",
                "lightning-bolts and setuptools<81 installed to unpickle the Lightning "
                "checkpoint; neither touches model math",
            ],
            "not_modified": ("no operator substitution, no resolution change, no precision "
                             "change, no checkpoint substitution, no helper model, "
                             "sky mask left at the released default"),
        }


BACKEND = MDAMoGSkyL2
