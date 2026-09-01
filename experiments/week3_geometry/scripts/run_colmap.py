"""Stage 3 — run one classical-arm configuration (A, B, C_off, C_on) on one clip.

EXPLORATORY. Not part of the `uw` package. Main project venv (numpy only).

One process per (configuration, clip, repeat). Everything is driven from
`configs/phase3a_methods.json` so A/B differ only in the feature front end and
C_off/C_on differ only in refraction — inside one binary, per `PLAN.md`.

Outputs, under `--out-root/<config>/<clip>/run<k>/`:
    database.db, sparse/            COLMAP's own artifacts
    sparse_txt/                     the model converted to TXT for parsing
    run.json                        provenance + the diagnostics this phase uses
    stdout.log                      full COLMAP output, kept for failure attribution

Refuses to write into an existing run directory unless `--overwrite` is passed
(CLAUDE.md invariant 7).
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import shutil
import subprocess
import sys
import time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

W3 = os.path.join(REPO_ROOT, "experiments", "week3_geometry")
SYSTEM_COLMAP = "/opt/homebrew/bin/colmap"
FORK_COLMAP = os.path.join(W3, "vendor", "colmap_underwater", "build",
                           "src", "colmap", "exe", "colmap")

BINARIES = {"system_colmap": SYSTEM_COLMAP, "fork_colmap": FORK_COLMAP}


def binary_version(path: str) -> str:
    out = subprocess.run([path, "-h"], capture_output=True, text=True)
    for line in (out.stdout + out.stderr).splitlines():
        if "COLMAP" in line and ("Commit" in line or line.strip().startswith("COLMAP")):
            return line.strip()
    return "unknown"


def _opt_names(is_fork: bool) -> dict:
    """The two binaries name the same options differently.

    COLMAP 4.x renamed the extraction/matching option groups when it gained
    non-SIFT front ends; the 3.10-dev fork predates that.
    """
    if is_fork:
        return {"seed": "--random_seed",
                "extract_gpu": "--SiftExtraction.use_gpu",
                "match_gpu": "--SiftMatching.use_gpu",
                "extract_type": None, "match_type": None,
                "mapper_seed": None}
    # COLMAP 4.x renamed the global seed to --default_random_seed and added a
    # separate --Mapper.random_seed (default -1 = seed from the clock), so the
    # mapper needs BOTH set for a reproducible reconstruction.
    return {"seed": "--default_random_seed",
            "extract_gpu": "--FeatureExtraction.use_gpu",
            "match_gpu": "--FeatureMatching.use_gpu",
            "extract_type": "--FeatureExtraction.type",
            "match_type": "--FeatureMatching.type",
            "mapper_seed": "--Mapper.random_seed"}


def run(cmd: list[str], log) -> tuple[int, float, float]:
    """Run a subprocess, tee its output, return (rc, wall_seconds, peak_rss_gb)."""
    before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    t0 = time.time()
    log.write("\n$ " + " ".join(cmd) + "\n")
    log.flush()
    proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
    wall = time.time() - t0
    after = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    # macOS reports ru_maxrss in bytes; Linux in kilobytes.
    div = 1e9 if platform.system() == "Darwin" else 1e6
    return proc.returncode, wall, max(after, before) / div


def parse_cameras_txt(path: str) -> dict:
    """Parse cameras.txt, including the fork's refractive extension.

    colmap_underwater appends `REFRAC_MODEL REFRAC_PARAMS[]` after the ordinary
    intrinsics on the same line (its own header documents this as
    `OPTIONAL[REFRAC_MODEL REFRAC_PARAMS[]]`). Mainline COLMAP writes no such
    suffix. Splitting on the first non-numeric token handles both without
    guessing how many intrinsics the camera model has.
    """
    cams = {}
    with open(path) as fh:
        for line in fh:
            if line.startswith("#") or not line.strip():
                continue
            p = line.split()
            tail = p[4:]
            numeric = []
            refrac_model = None
            refrac_params = []
            for tok in tail:
                if refrac_model is None:
                    try:
                        numeric.append(float(tok))
                        continue
                    except ValueError:
                        refrac_model = tok
                        continue
                refrac_params.append(float(tok))
            cams[int(p[0])] = {"model": p[1], "width": int(p[2]), "height": int(p[3]),
                               "params": numeric,
                               "refrac_model": refrac_model,
                               "refrac_params": refrac_params}
    return cams


def parse_images_txt(path: str) -> dict:
    """COLMAP images.txt -> {image_id: {...}}.

    COLMAP's quaternion/translation are WORLD-TO-CAMERA (R_cw, t_cw); the
    camera centre is -R_cw^T t_cw. That convention is asserted here once and
    relied on everywhere downstream.
    """
    images = {}
    with open(path) as fh:
        lines = [ln for ln in fh if not ln.startswith("#")]
    i = 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        p = lines[i].split()
        img_id = int(p[0])
        qw, qx, qy, qz = (float(x) for x in p[1:5])
        tx, ty, tz = (float(x) for x in p[5:8])
        cam_id = int(p[8])
        name = p[9]
        obs = lines[i + 1].split() if i + 1 < len(lines) else []
        pts = []
        for j in range(0, len(obs), 3):
            pid = int(obs[j + 2])
            if pid != -1:
                pts.append((float(obs[j]), float(obs[j + 1]), pid))
        images[img_id] = {"name": name, "camera_id": cam_id,
                          "qvec_wxyz_cw": [qw, qx, qy, qz],
                          "tvec_cw": [tx, ty, tz],
                          "n_observations_2d": len(obs) // 3,
                          "observations": pts}
        i += 2
    return images


def parse_points3d_txt(path: str) -> dict:
    pts = {}
    with open(path) as fh:
        for line in fh:
            if line.startswith("#") or not line.strip():
                continue
            p = line.split()
            pid = int(p[0])
            track = [int(p[k]) for k in range(8, len(p), 2)]
            pts[pid] = {"xyz": [float(p[1]), float(p[2]), float(p[3])],
                        "error": float(p[7]), "track_len": len(track)}
    return pts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--clip", required=True)
    ap.add_argument("--frames-root",
                    default=os.path.join(W3, "outputs", "frames"))
    ap.add_argument("--out-root", default=os.path.join(W3, "outputs", "colmap"))
    ap.add_argument("--methods",
                    default=os.path.join(W3, "configs", "phase3a_methods.json"))
    ap.add_argument("--repeat", type=int, default=0,
                    help="repeat index; separate directory, same settings")
    ap.add_argument("--seed", type=int, default=None,
                    help="override the shared random seed (repeat-run study)")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    with open(args.methods) as fh:
        meth = json.load(fh)
    if args.config not in meth["configs"]:
        raise SystemExit(f"unknown config {args.config!r}; "
                         f"have {sorted(meth['configs'])}")
    cfg = meth["configs"][args.config]
    shared = meth["shared"]
    # A diagnostic configuration may override the flat-port parameters; the
    # override is recorded in the run report so no run is ambiguous about which
    # port geometry produced it.
    fp = dict(meth["flatport_params"])
    fp.update(cfg.get("flatport_params_override", {}))

    binary = BINARIES[cfg["binary"]]
    if not os.path.exists(binary):
        raise SystemExit(f"binary not found: {binary}")
    is_fork = cfg["binary"] == "fork_colmap"
    names = _opt_names(is_fork)

    image_path = os.path.join(args.frames_root, args.clip)
    if not os.path.isdir(image_path):
        raise SystemExit(f"no extracted frames at {image_path}")
    n_images = len([f for f in os.listdir(image_path) if f.endswith(".png")])

    work = os.path.join(args.out_root, args.config, args.clip, f"run{args.repeat}")
    if os.path.exists(work):
        if not args.overwrite:
            raise SystemExit(f"refusing to overwrite {work!r} (pass --overwrite)")
        shutil.rmtree(work)
    os.makedirs(work)

    db = os.path.join(work, "database.db")
    sparse = os.path.join(work, "sparse")
    os.makedirs(sparse)
    seed = args.seed if args.seed is not None else shared["random_seed"]
    gpu = "1" if shared["use_gpu"] else "0"

    report = {
        "config": args.config,
        "config_role": cfg["role"],
        "clip": args.clip,
        "repeat": args.repeat,
        "binary": binary,
        "binary_version": binary_version(binary),
        "seed": seed,
        "n_images_offered": n_images,
        "image_path": os.path.relpath(image_path, REPO_ROOT),
        "shared_settings": shared,
        "extractor": cfg["extractor"],
        "matcher_type": cfg["matcher_type"],
        "refraction": cfg["refraction"],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "stages": {},
    }

    logp = os.path.join(work, "stdout.log")
    with open(logp, "w") as log:
        # ---- feature extraction -------------------------------------------
        cmd = [binary, "feature_extractor",
               names["seed"], str(seed),
               "--database_path", db,
               "--image_path", image_path,
               "--ImageReader.camera_model", shared["camera_model"],
               "--ImageReader.single_camera", "1" if shared["single_camera"] else "0",
               names["extract_gpu"], gpu]
        if names["extract_type"]:
            cmd += [names["extract_type"], cfg["extractor"]]
        if cfg["refraction"]:
            refrac = ",".join(str(x) for x in (
                list(fp["int_normal"]) + [fp["int_dist_m"], fp["int_thick_m"],
                                          fp["n_air"], fp["n_glass"], fp["n_water"]]))
            cmd += ["--ImageReader.camera_refrac_model", "FLATPORT",
                    "--ImageReader.camera_refrac_params", refrac]
            report["flatport_params_used"] = refrac
        rc, wall, mem = run(cmd, log)
        report["stages"]["feature_extractor"] = {"rc": rc, "seconds": round(wall, 1),
                                                 "peak_rss_gb": round(mem, 2)}
        if rc != 0:
            report["failed_at"] = "feature_extractor"
            _write(work, report)
            print(f"FAILED at feature_extractor; see {logp}")
            return 1

        # ---- matching ------------------------------------------------------
        cmd = [binary, "exhaustive_matcher",
               names["seed"], str(seed),
               "--database_path", db,
               names["match_gpu"], gpu]
        if names["match_type"]:
            cmd += [names["match_type"], cfg["matcher_type"]]
        if cfg["refraction"]:
            cmd += ["--TwoViewGeometry.enable_refraction", "1"]
        rc, wall, mem = run(cmd, log)
        report["stages"]["exhaustive_matcher"] = {"rc": rc, "seconds": round(wall, 1),
                                                  "peak_rss_gb": round(mem, 2)}
        if rc != 0:
            report["failed_at"] = "exhaustive_matcher"
            _write(work, report)
            print(f"FAILED at exhaustive_matcher; see {logp}")
            return 1

        # ---- mapping -------------------------------------------------------
        cmd = [binary, "mapper",
               names["seed"], str(seed),
               "--database_path", db,
               "--image_path", image_path,
               "--output_path", sparse,
               "--Mapper.multiple_models",
               "1" if shared["multiple_models"] else "0",
               "--Mapper.num_threads", str(shared.get("mapper_num_threads", -1))]
        if names["mapper_seed"]:
            cmd += [names["mapper_seed"], str(seed)]
        if cfg["refraction"]:
            cmd += ["--Mapper.enable_refraction", "1"]
        elif is_fork:
            cmd += ["--Mapper.enable_refraction", "0"]
        rc, wall, mem = run(cmd, log)
        report["stages"]["mapper"] = {"rc": rc, "seconds": round(wall, 1),
                                      "peak_rss_gb": round(mem, 2)}
        if rc != 0:
            report["failed_at"] = "mapper"
            _write(work, report)
            print(f"FAILED at mapper; see {logp}")
            return 1

        # ---- convert to TXT for parsing -----------------------------------
        models = sorted(d for d in os.listdir(sparse)
                        if os.path.isdir(os.path.join(sparse, d)))
        report["n_submodels"] = len(models)
        if not models:
            report["failed_at"] = "mapper_produced_no_model"
            _write(work, report)
            print(f"NO MODEL produced; see {logp}")
            return 1
        # Evaluate the LARGEST sub-model, and record every sub-model's size.
        # Fragmentation is a real failure mode and must stay visible: a run that
        # registers 48 images across four disjoint fragments has not
        # reconstructed the clip, and only the sizes reveal that.
        sizes = {}
        for m in models:
            probe = os.path.join(work, f"_probe_{m}")
            os.makedirs(probe, exist_ok=True)
            rc_, _, _ = run([binary, "model_converter",
                             "--input_path", os.path.join(sparse, m),
                             "--output_path", probe, "--output_type", "TXT"], log)
            sizes[m] = len(parse_images_txt(os.path.join(probe, "images.txt"))) if rc_ == 0 else -1
            shutil.rmtree(probe, ignore_errors=True)
        best = max(models, key=lambda m: sizes[m])
        report["submodel_registered_images"] = sizes
        report["selected_submodel"] = best
        report["fragmentation_note"] = (
            "Only the largest sub-model is evaluated. `submodel_registered_images` lists "
            "them all: a run whose images are split across several fragments has NOT "
            "reconstructed the clip, however many images it registered in total.")
        txt = os.path.join(work, "sparse_txt")
        os.makedirs(txt, exist_ok=True)
        rc, wall, _ = run([binary, "model_converter",
                           "--input_path", os.path.join(sparse, best),
                           "--output_path", txt,
                           "--output_type", "TXT"], log)
        report["stages"]["model_converter"] = {"rc": rc, "seconds": round(wall, 1)}
        if rc != 0:
            report["failed_at"] = "model_converter"
            _write(work, report)
            return 1

    # ---- diagnostics -------------------------------------------------------
    cams = parse_cameras_txt(os.path.join(txt, "cameras.txt"))
    imgs = parse_images_txt(os.path.join(txt, "images.txt"))
    pts = parse_points3d_txt(os.path.join(txt, "points3D.txt"))
    track_lens = [p["track_len"] for p in pts.values()]
    errs = [p["error"] for p in pts.values()]
    import numpy as np
    report["result"] = {
        "registered_images": len(imgs),
        "registered_fraction": round(len(imgs) / n_images, 4),
        "n_points3D": len(pts),
        "mean_track_length": float(np.mean(track_lens)) if track_lens else 0.0,
        "median_track_length": float(np.median(track_lens)) if track_lens else 0.0,
        "mean_observations_per_image": (float(np.mean([i["n_observations_2d"]
                                                       for i in imgs.values()]))
                                        if imgs else 0.0),
        "mean_reprojection_error_px": float(np.mean(errs)) if errs else float("nan"),
        "reprojection_error_note": ("DIAGNOSTIC ONLY. Refractive COLMAP's own AUV "
                                    "result shows a pinhole model reaching a LOWER "
                                    "reprojection error than the refractive model "
                                    "while producing a visibly distorted world. "
                                    "Never rank configurations on this number."),
        "cameras": cams,
    }
    report["total_seconds"] = round(sum(s.get("seconds", 0)
                                        for s in report["stages"].values()), 1)
    report["peak_rss_gb"] = round(max(s.get("peak_rss_gb", 0)
                                      for s in report["stages"].values()), 2)
    _write(work, report)
    r = report["result"]
    print(f"{args.config}/{args.clip}/run{args.repeat}: "
          f"registered {r['registered_images']}/{n_images} "
          f"({r['registered_fraction']:.0%}), {r['n_points3D']} points, "
          f"mean track {r['mean_track_length']:.2f}, "
          f"reproj {r['mean_reprojection_error_px']:.3f}px [diagnostic], "
          f"{report['total_seconds']:.0f}s")
    return 0


def _write(work: str, report: dict) -> None:
    with open(os.path.join(work, "run.json"), "w") as fh:
        json.dump(report, fh, indent=2)


if __name__ == "__main__":
    raise SystemExit(main())
