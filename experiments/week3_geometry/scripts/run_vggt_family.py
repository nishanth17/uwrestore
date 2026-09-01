"""Stage 4 — configurations E0 (vanilla VGGT) and E (Wat3R), the underwater
domain-adaptation paired experiment.

EXPLORATORY. Runs in `experiments/week3_geometry/.venv-vggt`, NOT the main
project venv. ONE MODEL PER PROCESS: `--model` selects which, the repo for the
other one is never put on `sys.path`, and the process exit is the authoritative
MPS cleanup boundary.

WHY ONE SCRIPT FOR BOTH. `E0 -> E` is a single experimental axis: Wat3R is
VGGT re-trained with underwater domain adaptation, and its released repository
is a fork of VGGT's (its `load_and_preprocess_images` "crop" branch is
character-for-character VGGT's, and its outputs carry the same names and
shapes). If each model got its own script, any accidental difference in frame
order, preprocessing, pose handling, range conversion, validity policy or
output format would be indistinguishable from an adaptation effect. Everything
except the two lines that build the model is therefore literally shared code.

The one deliberate asymmetry: Wat3R's `load_and_preprocess_images` accepts an
extra "max" mode that VGGT's does not, and Wat3R's README uses it. This script
uses `mode="crop"` for BOTH, because that branch is identical in the two
repositories — matching the README would have silently given Wat3R different
pixels.

Usage:
    experiments/week3_geometry/.venv-vggt/bin/python \
        -m experiments.week3_geometry.scripts.run_vggt_family \
            --model vggt --clip wreck_07
"""

from __future__ import annotations

import argparse
import glob
import os
import platform
import re
import resource
import sys
import time

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import numpy as np
import torch

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week3_geometry.rangeio import RangeWriter  # noqa: E402

W3 = os.path.join(REPO_ROOT, "experiments", "week3_geometry")
VENDOR = os.path.join(W3, "vendor")

MODELS = {
    "vggt": {
        "config": "E0_vggt",
        "config_letter": "E0",
        "role": ("vanilla VGGT — the non-underwater-adapted paired CONTROL for Wat3R. "
                 "Not a general leaderboard entry; it exists to make E interpretable."),
        "repo_dir": os.path.join(VENDOR, "vggt"),
        "repo_url": "https://github.com/facebookresearch/vggt",
        "repo_commit": "a288dd0f14786c93483e45524328726ab7b1b4ce",
        "checkpoint": "facebook/VGGT-1B",
        "code_license": ("VGGT License v1 (2025-07-29): permits commercial use except "
                         "military applications."),
        "checkpoint_license": ("facebook/VGGT-1B is NON-COMMERCIAL. The commercial-use "
                               "checkpoint facebook/VGGT-1B-Commercial is gated behind an "
                               "application form and was not requested. VGGT is therefore "
                               "an experimental control only and must not be promoted into "
                               "a permanent project dependency on this checkpoint."),
    },
    "wat3r_ren": {
        "config": "E_wat3r_ren",
        "config_letter": "E",
        "role": ("Wat3R-Ren (Ren et al., ECCV 2026) — underwater-domain-adapted "
                 "feed-forward geometry. NAMED -Ren throughout because a second, "
                 "unrelated 2026 method is also called WAT3R (Xu et al.); see "
                 "configs/underwater_challengers.json."),
        "repo_dir": os.path.join(VENDOR, "Wat3R"),
        "repo_url": "https://github.com/LSXI7/Wat3R",
        "repo_commit": "93147df00e15605afa93f586923fec000b18cefc",
        "checkpoint": "lsxi77777/Wat3R",
        "code_license": "Apache-2.0",
        "checkpoint_license": "Apache-2.0 (released with the code and the Water3D dataset)",
    },
}


def frame_index_of(path: str) -> int:
    m = re.search(r"f(\d{6})\.png$", os.path.basename(path))
    if not m:
        raise ValueError(f"unexpected frame filename {path!r}")
    return int(m.group(1))


def load_model(which: str, device: str):
    """Import ONLY the selected repo and build its model.

    Both repos ship a flat top-level package (`vggt`, `wat3r`) plus identically
    named submodules underneath. They do not currently collide, but importing
    only one keeps that true by construction rather than by luck.
    """
    spec = MODELS[which]
    sys.path.insert(0, spec["repo_dir"])
    if which == "vggt":
        from vggt.models.vggt import VGGT
        from vggt.utils.load_fn import load_and_preprocess_images
        from vggt.utils.pose_enc import pose_encoding_to_extri_intri
        model = VGGT.from_pretrained(spec["checkpoint"])
    else:
        from wat3r.models.wat3r import Wat3R
        from wat3r.utils.load_fn import load_and_preprocess_images
        from wat3r.utils.pose_enc import pose_encoding_to_extri_intri
        model = Wat3R.from_pretrained(spec["checkpoint"])
    return model.to(device).eval(), load_and_preprocess_images, pose_encoding_to_extri_intri


def zdepth_to_range(depth_z: np.ndarray, K: np.ndarray) -> np.ndarray:
    """(H,W) planar z-depth -> Euclidean ray range, using this frame's own K.

    Both models emit PLANAR z-depth ("depth", [S,H,W,1]) together with a
    pixel-space intrinsics matrix. Storing that as "range" would put a purely
    radial, tens-of-percent error into the very comparison Phase 3A uses to look
    for a radial refraction signature. The conversion is the tested one from
    experiments/week3_geometry/geometry.py, inlined here only because this venv
    deliberately does not import the main project package.
    """
    h, w = depth_z.shape
    u, v = np.meshgrid(np.arange(w, dtype=np.float64), np.arange(h, dtype=np.float64))
    uv1 = np.stack([u, v, np.ones_like(u)], axis=-1)
    dirs = uv1 @ np.linalg.inv(np.asarray(K, dtype=np.float64)).T
    factor = np.linalg.norm(dirs, axis=-1)
    out = depth_z.astype(np.float64) * factor
    return np.where(np.isfinite(depth_z) & (depth_z > 0), out, np.nan)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True,
                    choices=sorted(MODELS) + ["wat3r"],
                    help="'wat3r' is accepted as a deprecated alias for 'wat3r_ren'")
    ap.add_argument("--clip", required=True)
    ap.add_argument("--frames-root", default=os.path.join(W3, "outputs", "frames"))
    ap.add_argument("--out-root", default=os.path.join(W3, "outputs", "range"))
    ap.add_argument("--max-views", type=int, default=None,
                    help="bring-up/profiling only; the bakeoff uses every frame")
    ap.add_argument("--repeat", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    # `wat3r` is kept as an alias so an in-flight batch script that predates the
    # Wat3R-Ren / WAT3R-Xu naming split still resolves to the same model.
    if args.model == "wat3r":
        args.model = "wat3r_ren"
    spec = MODELS[args.model]
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    device = "mps" if torch.backends.mps.is_available() else "cpu"

    files = sorted(glob.glob(os.path.join(args.frames_root, args.clip, "f*.png")))
    if not files:
        raise SystemExit(f"no frames under {os.path.join(args.frames_root, args.clip)}")
    if args.max_views:
        idx = np.linspace(0, len(files) - 1, args.max_views).round().astype(int)
        files = [files[i] for i in sorted(set(idx))]

    t0 = time.time()
    model, load_images, pose_encoding_to_extri_intri = load_model(args.model, device)
    t_load = time.time() - t0

    t0 = time.time()
    images = load_images(files, mode="crop").to(device)   # (S,3,H,W)
    t_prep = time.time() - t0
    in_hw = [int(images.shape[-2]), int(images.shape[-1])]

    t0 = time.time()
    with torch.no_grad():
        # float32 throughout: MPS has no bf16 autocast path, and the project's
        # standing rule is that a measurement instrument must be reproducible
        # before it is fast.
        preds = model(images)
    t_infer = time.time() - t0
    peak_mps_gb = (torch.mps.driver_allocated_memory() / 1e9
                   if device == "mps" else float("nan"))

    extri, intri = pose_encoding_to_extri_intri(preds["pose_enc"], images.shape[-2:])
    extri = extri[0].detach().float().cpu().numpy()      # (S,3,4) world->camera
    intri = intri[0].detach().float().cpu().numpy()      # (S,3,3) pixel-space K
    depth = preds["depth"][0].detach().float().cpu().numpy()[..., 0]        # (S,H,W)
    dconf = preds["depth_conf"][0].detach().float().cpu().numpy()           # (S,H,W)
    wpts = preds["world_points"][0].detach().float().cpu().numpy()          # (S,H,W,3)

    config = spec["config"] if args.repeat == 0 else f"{spec['config']}_run{args.repeat}"
    w = RangeWriter(args.out_root, config, args.clip, overwrite=args.overwrite)
    conv_checks = []
    n = len(files)
    check_frames = sorted({n // 3, 2 * n // 3, n - 1}) if n >= 3 else [n - 1]
    for i, path in enumerate(files):
        K = intri[i]
        T_cw = np.eye(4)
        T_cw[:3, :4] = extri[i]                 # documented as OpenCV cam-FROM-world
        R = T_cw[:3, :3]
        T_wc = np.eye(4)
        T_wc[:3, :3] = R.T
        T_wc[:3, 3] = -R.T @ T_cw[:3, 3]

        rng = zdepth_to_range(depth[i], K)
        valid = np.isfinite(rng) & (rng > 0)

        # Convention check on frames spread across the clip, NEVER on the first
        # frames: VGGT-family models anchor the world frame to camera 0, so its
        # pose is the identity and inverting it changes nothing -- the
        # falsification control would silently be a no-op exactly where it is
        # most tempting to run it.
        if i in check_frames:
            # Convention check: unproject this frame's own z-depth with its own K
            # and pose and compare against the model's world_points. If these
            # agree, the pose convention read above is the right one; if the pose
            # were inverted they would disagree grossly.
            h, w_ = depth[i].shape
            uu, vv = np.meshgrid(np.arange(w_, dtype=np.float64),
                                 np.arange(h, dtype=np.float64))
            uv1 = np.stack([uu, vv, np.ones_like(uu)], axis=-1)
            cam = (uv1 @ np.linalg.inv(K.astype(np.float64)).T) * depth[i][..., None]
            world = cam @ T_wc[:3, :3].T + T_wc[:3, 3]
            # Falsification control: redo it with the pose deliberately inverted.
            # A convention check that only reports "the number is small" is not a
            # check -- it needs the wrong answer to be visibly worse.
            world_wrong = cam @ T_cw[:3, :3].T + T_cw[:3, 3]
            m = valid & np.isfinite(wpts[i]).all(axis=-1)
            if m.any():
                d = np.linalg.norm(world[m] - wpts[i][m], axis=-1)
                d_wrong = np.linalg.norm(world_wrong[m] - wpts[i][m], axis=-1)
                sc = float(np.median(np.linalg.norm(wpts[i][m] - T_wc[:3, 3], axis=-1)))
                conv_checks.append({
                    "frame": frame_index_of(path),
                    "median_abs_world_point_disagreement": float(np.median(d)),
                    "p95_abs_world_point_disagreement": float(np.percentile(d, 95)),
                    "median_scene_range_for_context": sc,
                    "relative_median_disagreement": float(np.median(d) / sc) if sc > 0 else float("nan"),
                    "relative_median_disagreement_with_pose_INVERTED": (
                        float(np.median(d_wrong) / sc) if sc > 0 else float("nan")),
                })

        w.add_frame(frame_index_of(path), rng, valid, K=K, T_wc=T_wc, conf=dconf[i],
                    path_source="ray_range_approx_water_path")

    rss_gb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9
    w.close(
        provenance={
            "method": "VGGT" if args.model == "vggt" else "Wat3R-Ren",
            "config_letter": spec["config_letter"],
            "role": spec["role"],
            "paired_axis": ("E0 -> E: vanilla VGGT vs the same architecture after "
                            "underwater domain adaptation. Read as ONE experiment."),
            "repo": spec["repo_url"],
            "repo_commit": spec["repo_commit"],
            "code_license": spec["code_license"],
            "checkpoint": spec["checkpoint"],
            "checkpoint_license": spec["checkpoint_license"],
            "torch": torch.__version__,
            "torch_pinned_upstream": ("VGGT pins torch==2.3.1 and Wat3R pins numpy==1.26.1; "
                                      "BOTH models here run on the same torch "
                                      f"{torch.__version__} so the pair stays controlled. "
                                      "Deviation from the upstream pin is recorded, not hidden."),
            "device": device,
            "dtype": "float32 (no autocast: MPS has no bf16 autocast path)",
            "seed": args.seed,
            "repeat": args.repeat,
            "platform": platform.platform(),
            "n_views": len(files),
            "input_frames": [os.path.relpath(f, REPO_ROOT) for f in files],
            "preprocessing": ("load_and_preprocess_images(mode='crop'), target_size=518. "
                              "The 'crop' branch is identical in both repositories, so both "
                              "models see the same pixels. Wat3R's README default mode='max' "
                              "was NOT used, because VGGT has no such mode and using it would "
                              "have given Wat3R different input."),
            "inference_resolution_hw": in_hw,
            "resolution_note": ("Dense geometry is produced on this grid, not at the "
                                "1280x720 extraction resolution. Portrait clips are "
                                "centre-cropped to 518x518 by the shared 'crop' branch, "
                                "which discards field of view identically for both models."),
            "seconds": {"model_load": round(t_load, 1), "preprocess": round(t_prep, 1),
                        "inference": round(t_infer, 1)},
            "peak_process_rss_gb": round(rss_gb, 2),
            "peak_mps_driver_gb": round(peak_mps_gb, 2),
        },
        conventions={
            "camera_frame": "OpenCV: +x right, +y down, +z forward",
            "native_pose": "pose_encoding_to_extri_intri -> extrinsics (S,3,4) = cam-FROM-world (T_cw)",
            "stored_pose": "T_wc = inverse of the native extrinsics; translation is the camera centre",
            "native_range_field": "predictions['depth'] (S,H,W,1) = PLANAR Z-DEPTH, not range",
            "stored_as": ("range_along_ray = z_depth * ||K^-1 [u,v,1]||, the tested central-camera "
                          "conversion. Storing the native field unconverted would have injected a "
                          "radial error of tens of percent at the frame edges."),
            "path_source": "ray_range_approx_water_path",
            "path_source_note": ("Central pinhole model; it cannot emit a water path length. "
                                 "Ray range stands in for it."),
            "confidence": ("predictions['depth_conf']; a learned score, NOT calibrated for "
                           "underwater input, and for VGGT specifically it is out of domain."),
            "mask": "no explicit mask is emitted; validity = finite and positive range only",
            "pose_convention_check": conv_checks,
            "pose_convention_check_note": ("Unprojects the model's own z-depth with its own K "
                                           "and the stored T_wc and compares against the model's "
                                           "world_points, then REPEATS IT with the pose inverted "
                                           "as a falsification control. The correct convention "
                                           "must be dramatically better than the inverted one. "
                                           "Note that the residual is NOT expected to be zero: "
                                           "VGGT-family models predict depth and world points "
                                           "with SEPARATE heads that are not constrained to agree, "
                                           "so a few percent is the models' own internal "
                                           "inconsistency, not a conversion error."),
        },
        scale_convention="scale-ambiguous (neither model's scale is independently verified here)",
    )
    cc = conv_checks[0]["relative_median_disagreement"] if conv_checks else float("nan")
    print(f"{spec['config']}/{args.clip}: {len(files)} views, inference {t_infer:.0f}s, "
          f"MPS peak {peak_mps_gb:.1f} GB, RSS {rss_gb:.1f} GB, grid {in_hw}, "
          f"pose-check rel disagreement {cc:.2e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
