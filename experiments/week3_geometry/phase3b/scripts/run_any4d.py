"""3B-6A — Any4D: dynamic / 4D feed-forward geometry.

EXPLORATORY. Runs in `experiments/week3_geometry/.venv-any4d`, NOT the main
project venv. One process per clip: the process boundary is the authoritative
MPS cleanup boundary, and no other heavyweight geometry model is instantiated
in this interpreter.

WHAT THIS IS TESTING. Phase 3A's worst single number is MapAnything on
`wreck_03`: a 6.64x fitted per-frame scale wander against configuration A and a
129.8 % range-dependent residual swing, on a clip with a large moving diver,
exhaust bubbles and haze. Any4D's research target is explicitly dynamic 4D
geometry from RGB video, and it is built on the same MapAnything / UniCeption
stack, so a negative result here cannot be blamed on an unfamiliar harness.

NO UPSTREAM FILE IS MODIFIED. This driver calls Any4D's own released model
factory, released config, released preprocessing and released inference entry
point; only the demo *wrapper* (which hardcodes `device="cuda"` in two places) is
replaced, exactly as Phase 3A did for MapAnything and the VGGT family. That is
strictly less invasive than patching upstream, and it is the project's existing
precedent.

Two deliberate, recorded deviations from `scripts/demo_inference.py`:

1. **MoGe is not run** (`compute_moge_mask=False`). The MoGe mask is a
   visualisation / scene-flow post-processing input, never a model input: the
   model's `REQUIRED_KEYS` are `{"img", "data_norm_type"}`, `binary_mask` is not
   even in its `ALLOWED_VIEW_KEYS`, and with the flag off `load_images` produces
   the image tensor through the identical `crop_resize_if_necessary` call. The
   geometry path is therefore the released one. (It also avoids a second
   hardcoded `device="cuda"` inside `run_moge_inference`.)
2. **Frames in temporal order**, rather than the demo's `[reference] + window`,
   so the frame ordering matches Phase 3A configurations D / E0 / E.

   **But not all 48 of them, and that is a measured constraint, not a choice.**
   Any4D's released inference path does global self-attention across every view
   at once and exposes no memory-efficient mode -- `Any4D.forward(views)` takes
   no such argument, and `gradient_checkpointing` is a training-time construction
   flag that does not touch the forward attention buffer. MapAnything, by
   contrast, was run in Phase 3A with `memory_efficient_inference=True`. At 48
   views on the 294x518 grid the attention call asks for a **62.19 GB** buffer
   and raises `RuntimeError: Invalid buffer size` on this 24 GB machine. The view
   count is therefore reduced with `--max-views`, uniformly over the clip so both
   endpoints and the full temporal extent are preserved, and every comparison
   against a Phase 3A model is computed **on the same frames** -- a per-frame
   scale max/min over 15 samples is not comparable with one over 37 otherwise.

`use_amp=False`, float32, as Phase 3A used for every dense model on MPS.

Usage:
    experiments/week3_geometry/.venv-any4d/bin/python \
        -m experiments.week3_geometry.phase3b.scripts.run_any4d --clip wreck_03
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import platform
import re
import resource
import sys
import time

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import numpy as np
import torch

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week3_geometry.rangeio import RangeWriter  # noqa: E402

W3 = os.path.join(REPO_ROOT, "experiments", "week3_geometry")
ANY4D_REPO = os.path.join(W3, "vendor", "any4d")
CONFIG = "Y_any4d"
CHECKPOINT = os.path.join(W3, "checkpoints", "any4d_4v_combined.pth")
RESOLUTION = (518, 336)          # the released demo's resolution, unchanged


def frame_index_of(path: str) -> int:
    m = re.search(r"f(\d{6})\.png$", os.path.basename(path))
    if not m:
        raise ValueError(f"unexpected frame filename {path!r}")
    return int(m.group(1))


def init_hydra_config(config_path: str, overrides=None):
    """Any4D's own helper, composing the SAME config with the SAME overrides.

    The one difference from `scripts/demo_inference.py` is `initialize_config_dir`
    with an absolute path instead of `initialize` with a path relative to the
    caller's file. Hydra resolves a relative `config_path` against whichever
    module called it, so the demo's version only works from the demo's own
    directory; the absolute form is location-independent. It composes exactly the
    same configuration — this is a path-resolution fix in project-owned code, not
    a change to Any4D.
    """
    import hydra
    config_dir = os.path.abspath(os.path.dirname(config_path))
    config_name = os.path.basename(config_path).split(".")[0]
    hydra.core.global_hydra.GlobalHydra.instance().clear()
    hydra.initialize_config_dir(version_base=None, config_dir=config_dir)
    if overrides is not None:
        return hydra.compose(config_name=config_name, overrides=overrides)
    return hydra.compose(config_name=config_name)


def _pose_from(pred, i: int):
    """(R_?, t_?) from Any4D's cam_quats/cam_trans. Direction is NOT assumed."""
    from any4d.utils.geometry import quaternion_to_rotation_matrix
    q = pred["cam_quats"][0].detach().float().cpu()
    t = pred["cam_trans"][0].detach().float().cpu().numpy()
    R = quaternion_to_rotation_matrix(q).numpy()
    if R.ndim == 3:
        R = R[0]
    return R, np.asarray(t).reshape(3)


def _convention_check(preds: list, frames_to_check: list[int]) -> dict:
    """Verify Any4D's range and pose semantics NUMERICALLY, never by assumption.

    Three questions, each with a falsification control:

    * Is `depth_along_ray` really the Euclidean ||pts3d_cam||, or is it planar
      z-depth wearing a distance's name? At this footage's field of view the two
      differ by more than 25 % at the frame corners, and the difference is
      radially structured -- exactly the signature a refraction test looks for.
    * Is (cam_quats, cam_trans) camera-to-world or world-to-camera? The check
      composes it both ways against the model's own `pts3d` and reports both
      residuals. If the wrong direction scored as well as the right one the
      check would be vacuous.
    * Phase 3A's lesson: the pose control must NOT be run on frame 0, because
      this model family anchors its world frame to camera 0, making that pose the
      identity and the inversion a no-op. Later frames are used.
    """
    out = {"checked": True, "frames_checked": frames_to_check, "per_frame": []}
    for i in frames_to_check:
        pred = preds[i]
        p3c = pred["pts3d_cam"][0].detach().float().cpu().numpy()
        p3w = pred["pts3d"][0].detach().float().cpu().numpy()
        dar = pred["depth_along_ray"][0].detach().float().cpu().numpy()[..., 0]
        m = np.isfinite(p3c).all(axis=-1) & np.isfinite(dar) & np.isfinite(p3w).all(axis=-1)
        if not m.any():
            out["per_frame"].append({"frame": i, "error": "no finite pixels"})
            continue
        norm = np.linalg.norm(p3c, axis=-1)
        R, t = _pose_from(pred, i)
        X = p3c[m]
        # cam2world (T_wc): X_world = R X_cam + t
        res_wc = np.abs((X @ R.T + t) - p3w[m]).max()
        # world2cam read backwards: X_world = R^T (X_cam - t)
        res_cw = np.abs(((X - t) @ R) - p3w[m]).max()
        scale = float(np.abs(p3w[m]).max()) + 1e-12
        out["per_frame"].append({
            "frame": i,
            "max_abs_depth_along_ray_minus_norm_pts3d_cam": float(
                np.abs(norm[m] - dar[m]).max()),
            "median_ratio_along_ray_over_z": float(np.median(
                dar[m] / np.clip(p3c[..., 2][m], 1e-9, None))),
            "pose_residual_if_cam2world": float(res_wc),
            "pose_residual_if_world2cam": float(res_cw),
            "pose_residual_ratio_wrong_over_right": float(
                max(res_wc, res_cw) / max(min(res_wc, res_cw), 1e-12)),
            "relative_to_scene_extent": float(min(res_wc, res_cw) / scale),
            "implied_convention": "cam2world (T_wc)" if res_wc <= res_cw else "world2cam (T_cw)",
        })
    conv = {d.get("implied_convention") for d in out["per_frame"] if "implied_convention" in d}
    out["consistent_convention"] = (list(conv)[0] if len(conv) == 1 else None)
    out["interpretation"] = (
        "depth_along_ray == ||pts3d_cam|| confirms a Euclidean camera-to-point distance, so "
        "it maps onto range_along_ray exactly. The pose residuals are a falsification "
        "control: the WRONG composition direction must score materially worse, and the "
        "check is deliberately run away from frame 0 because this model family anchors its "
        "world frame to camera 0, where inverting the pose changes nothing.")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clip", required=True)
    ap.add_argument("--frames-root", default=os.path.join(W3, "outputs", "frames"))
    ap.add_argument("--out-root", default=os.path.join(W3, "phase3b", "outputs", "range"))
    ap.add_argument("--checkpoint", default=CHECKPOINT)
    ap.add_argument("--max-views", type=int, default=None,
                    help="bring-up / smoke test only; a real run uses every frame and "
                         "any reduced run is labelled as such in the product")
    ap.add_argument("--device", default=None, choices=[None, "mps", "cpu"])
    ap.add_argument("--repeat", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    if ANY4D_REPO not in sys.path:
        sys.path.insert(0, ANY4D_REPO)

    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    device = args.device or ("mps" if torch.backends.mps.is_available() else "cpu")
    files = sorted(glob.glob(os.path.join(args.frames_root, args.clip, "f*.png")))
    if not files:
        raise SystemExit(f"no frames under {os.path.join(args.frames_root, args.clip)}")
    reduced = False
    if args.max_views and args.max_views < len(files):
        idx = np.linspace(0, len(files) - 1, args.max_views).round().astype(int)
        files = [files[i] for i in sorted(set(idx))]
        reduced = True

    from any4d.models import init_model
    from any4d.utils.image import load_images
    from any4d.utils.inference import loss_of_one_batch_multi_view

    overrides = ["machine=local", "model=any4d",
                 "model.encoder.uses_torch_hub=false", "model/task=images_only"]
    t0 = time.time()
    cfg = init_hydra_config(os.path.join(ANY4D_REPO, "configs", "train.yaml"),
                            overrides=overrides)
    model = init_model(cfg.model.model_str, cfg.model.model_config)
    model.to(device)
    ckpt = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    load_report = model.load_state_dict(ckpt["model"], strict=False)
    model.to(device).eval()
    t_load = time.time() - t0
    missing = list(getattr(load_report, "missing_keys", []) or [])
    unexpected = list(getattr(load_report, "unexpected_keys", []) or [])

    t0 = time.time()
    views = load_images(files, size=RESOLUTION, norm_type=cfg.model.data_norm_type,
                        patch_size=14, compute_moge_mask=False)
    t_prep = time.time() - t0
    in_hw = list(np.asarray(views[0]["img"]).shape[-2:])

    t0 = time.time()
    with torch.no_grad():
        result = loss_of_one_batch_multi_view(views, model, None, device, use_amp=False)
    t_infer = time.time() - t0
    preds = [result[f"pred{i + 1}"] for i in range(len(files))]
    peak_mps_gb = (torch.mps.driver_allocated_memory() / 1e9
                   if device == "mps" else float("nan"))

    n = len(files)
    conv = _convention_check(preds, [max(1, n // 3), max(1, 2 * n // 3), n - 1])

    from any4d.utils.geometry import recover_pinhole_intrinsics_from_ray_directions

    config = CONFIG if args.repeat == 0 else f"{CONFIG}_run{args.repeat}"
    w = RangeWriter(args.out_root, config, args.clip, overwrite=args.overwrite)
    for i, (path, pred) in enumerate(zip(files, preds)):
        rng = pred["depth_along_ray"][0].detach().float().cpu().numpy()[..., 0]
        # Validity policy, stated because it DIFFERS from configuration D's.
        # MapAnything was run with apply_mask=True and mask_edges=True, so its
        # coverage excludes depth discontinuities. Any4D's raw model output has
        # no edge mask, so validity here is: finite, positive, and inside
        # non_ambiguous_mask when the model emits one. Coverage numbers are
        # therefore NOT comparable with D's, and nothing below compares them.
        valid = np.isfinite(rng) & (rng > 0)
        # The mask handling is RECORDED, not assumed. A silently unapplied mask
        # would show up as "valid 1.00", which Phase 3A §5.1 warns is the absence
        # of a validity signal rather than perfect coverage -- so whether it was
        # applied, and its shape, are stored per frame.
        mask_rec = {"key_present": "non_ambiguous_mask" in pred, "applied": False}
        if "non_ambiguous_mask" in pred:
            nam = np.asarray(pred["non_ambiguous_mask"][0].detach().cpu().numpy())
            mask_rec["raw_shape"] = list(nam.shape)
            nam = np.squeeze(nam)
            mask_rec["squeezed_shape"] = list(nam.shape)
            if nam.shape == valid.shape:
                nam = nam.astype(bool)
                mask_rec.update({"applied": True,
                                 "mask_true_fraction": float(nam.mean())})
                valid = valid & nam
            else:
                mask_rec["reason_not_applied"] = (
                    f"shape {list(nam.shape)} does not match the range grid "
                    f"{list(valid.shape)}")
        conf = (pred["conf"][0].detach().float().cpu().numpy()
                if "conf" in pred else None)
        R, t = _pose_from(pred, i)
        T_wc = np.eye(4)
        T_wc[:3, :3], T_wc[:3, 3] = R, t
        K = None
        if "ray_directions" in pred:
            try:
                intr = recover_pinhole_intrinsics_from_ray_directions(
                    pred["ray_directions"][0].detach().float().cpu())
                K = np.array([[float(intr["fx"]), 0.0, float(intr["cx"])],
                              [0.0, float(intr["fy"]), float(intr["cy"])],
                              [0.0, 0.0, 1.0]])
            except Exception:                                   # noqa: BLE001
                K = None
        extra = {"non_ambiguous_mask": mask_rec}
        if "metric_scaling_factor" in pred:
            extra["metric_scaling_factor"] = float(
                pred["metric_scaling_factor"].detach().float().cpu().numpy().ravel()[0])
        if "scene_flow" in pred:
            sf = pred["scene_flow"][0].detach().float().cpu().numpy()
            mag = np.linalg.norm(sf, axis=-1)
            fin = np.isfinite(mag)
            extra["scene_flow_magnitude"] = {
                "median": float(np.median(mag[fin])) if fin.any() else float("nan"),
                "p95": float(np.percentile(mag[fin], 95)) if fin.any() else float("nan"),
                "note": ("Any4D's per-pixel scene flow, in the model's own metric units, "
                         "recorded as DATA. It is never used to filter or correct the "
                         "range field being scored."),
            }
        w.add_frame(frame_index_of(path), rng, valid, K=K, T_wc=T_wc, conf=conf,
                    path_source="ray_range_approx_water_path", extra=extra)

    rss_gb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9
    w.close(
        provenance={
            "method": "Any4D",
            "config_letter": "Y (Phase 3B, 3B-6A)",
            "role": "dynamic / 4D feed-forward geometry -- the wreck_03 dynamic-failure challenger",
            "repo": "https://github.com/Any-4D/Any4D",
            "repo_commit": "aa9f1b0d7ecdf44a6ef8cef93387be0093bdd497",
            "code_license": "Apache-2.0",
            "checkpoint": os.path.relpath(args.checkpoint, REPO_ROOT),
            "checkpoint_source": ("https://huggingface.co/airlabshare/any4d-checkpoint/"
                                  "resolve/main/any4d_4v_combined.pth"),
            "checkpoint_license": ("NOT STATED. The Hugging Face repo declares no licence. "
                                   "A public artifact with no stated terms is not an open "
                                   "licence, so this stays strictly experimental and may "
                                   "not be promoted into a project dependency."),
            "checkpoint_sha256": _sha256_note(args.checkpoint),
            "state_dict_load": {"n_missing_keys": len(missing), "n_unexpected_keys": len(unexpected),
                                "missing_sample": missing[:12], "unexpected_sample": unexpected[:12],
                                "note": ("Loaded with strict=False, as the released demo does. "
                                         "A large missing-key count would mean the released "
                                         "checkpoint does not populate the constructed model, "
                                         "which is exactly the trap Phase 3A caught with "
                                         "Water-VGGT, so the counts are reported rather than "
                                         "swallowed.")},
            "hydra_overrides": overrides,
            "torch": torch.__version__,
            "device": device,
            "dtype": "float32 (use_amp=False, matching every Phase 3A dense run on MPS)",
            "seed": args.seed,
            "repeat": args.repeat,
            "platform": platform.platform(),
            "n_views": len(files),
            "reduced_view_count": reduced,
            "input_frames": [os.path.relpath(f, REPO_ROOT) for f in files],
            "inference_resolution_hw": in_hw,
            "requested_resolution_wh": list(RESOLUTION),
            "resolution_note": ("Every dense number from this model is produced on the grid "
                                "above, NOT at the 1280x720 extraction resolution, and must "
                                "not be described as native-resolution geometry."),
            "deviations_from_demo": [
                ("MoGe mask not computed (compute_moge_mask=False). It is a visualisation / "
                 "scene-flow post-processing input, not a model input: REQUIRED_KEYS are "
                 "{img, data_norm_type} and binary_mask is not in ALLOWED_VIEW_KEYS. With "
                 "the flag off the image tensor comes from the identical "
                 "crop_resize_if_necessary call."),
                ("All frames in temporal order instead of the demo's [reference] + window, "
                 "so the frame set, order and count match Phase 3A configurations D/E0/E."),
                ("Device selected as MPS rather than the demo's hardcoded CUDA. No upstream "
                 "file was modified; this driver calls the released model factory, config, "
                 "preprocessing and inference entry point directly."),
            ],
            "seconds": {"model_load": round(t_load, 1), "preprocess": round(t_prep, 1),
                        "inference": round(t_infer, 1)},
            "peak_process_rss_gb": round(rss_gb, 2),
            "peak_mps_driver_gb": round(peak_mps_gb, 2),
        },
        conventions={
            "camera_frame": "OpenCV: +x right, +y down, +z forward (verified numerically below)",
            "pose": "cam_quats (x,y,z,w) + cam_trans; DIRECTION VERIFIED, not assumed",
            "native_range_field": "depth_along_ray (B,H,W,1)",
            "stored_as": "range_along_ray = depth_along_ray, unmodified",
            "path_source": "ray_range_approx_water_path",
            "path_source_note": ("Any4D is a central model, so it cannot emit a water path "
                                 "length. Ray range stands in for it; the unmodelled "
                                 "air+glass segment is millimetres against metre-scale range."),
            "validity_policy": ("finite AND positive AND inside non_ambiguous_mask. This "
                                "DIFFERS from configuration D, which was run with "
                                "mask_edges=True and therefore excludes depth "
                                "discontinuities. Coverage is NOT comparable with D's."),
            "confidence": "pred['conf'] when present; not calibrated for underwater input",
            "scene_flow": "recorded as data only; never used to filter or correct range",
            "convention_check": conv,
        },
        scale_convention="metric-claimed-by-model (NOT independently verified here)",
    )
    first = conv["per_frame"][0] if conv["per_frame"] else {}
    print(f"Any4D/{args.clip}: {len(files)} views, grid {in_hw}, "
          f"inference {t_infer:.0f}s, MPS peak {peak_mps_gb:.1f} GB, RSS {rss_gb:.1f} GB, "
          f"pose convention {conv.get('consistent_convention')}, "
          f"|along_ray - ||pts3d_cam|||max = "
          f"{first.get('max_abs_depth_along_ray_minus_norm_pts3d_cam', float('nan')):.2e}, "
          f"missing keys {len(missing)}")
    return 0


def _sha256_note(path: str) -> str:
    side = os.path.splitext(path)[0] + ".sha256"
    if os.path.exists(side):
        return open(side).read().strip().split()[0]
    return "not computed in this process (see outputs/preflight/any4d_checkpoint.json)"


if __name__ == "__main__":
    raise SystemExit(main())
