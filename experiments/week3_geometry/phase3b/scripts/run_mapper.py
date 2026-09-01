"""Phase 3B — run a mapper (incremental or global) on an ALREADY PREPARED database.

EXPLORATORY. Main project venv (numpy only).

Phase 3A's `run_colmap.py` owns the whole pipeline: extract, match, map. 3B-2 and
3B-3 must NOT re-extract or re-match — the entire point is that the measurements
are the ones Phase 3A already made. So this driver starts at the mapper, on a
database produced by `prep_db.py`.

It writes a `run.json` in the SAME shape Phase 3A's driver writes, so
`sparse_metrics.py` and every downstream table read both without special cases.

Three things it does that matter:

* **It validates the camera model.** After mapping it asserts that the model name
  COLMAP wrote into `cameras.txt` is the one that was requested. A wrong model id
  in `prep_db.py` therefore cannot pass silently.
* **It pins the same reproducibility settings Phase 3A pinned** — seed 0
  everywhere, mapping on one thread, no GPU — because the claims here are
  differences between runs.
* **It records every sub-model's size.** A run that registers 48 images across
  four disjoint fragments has not reconstructed the clip, and only the sizes
  reveal that. Only the largest sub-model is evaluated.

Usage:
    .venv/bin/python -m experiments.week3_geometry.phase3b.scripts.run_mapper \
        --db  .../3b3_wreck_05_opencv.db \
        --images experiments/week3_geometry/outputs/frames/wreck_05 \
        --out .../colmap/M_opencv/wreck_05/run0 \
        --mapper incremental --config-label M_opencv --clip wreck_05
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

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week3_geometry.scripts.run_colmap import (  # noqa: E402
    binary_version,
    parse_cameras_txt,
    parse_images_txt,
    parse_points3d_txt,
)

COLMAP = "/opt/homebrew/bin/colmap"


def run(cmd: list[str], log) -> tuple[int, float, float]:
    before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    t0 = time.time()
    log.write("\n$ " + " ".join(cmd) + "\n")
    log.flush()
    proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
    wall = time.time() - t0
    after = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    div = 1e9 if platform.system() == "Darwin" else 1e6
    return proc.returncode, wall, max(after, before) / div


def _write(work: str, report: dict) -> None:
    with open(os.path.join(work, "run.json"), "w") as fh:
        json.dump(report, fh, indent=2)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, help="prepared database (a COPY)")
    ap.add_argument("--images", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mapper", choices=["incremental", "global"], default="incremental")
    ap.add_argument("--config-label", required=True)
    ap.add_argument("--clip", required=True)
    ap.add_argument("--hypothesis", default=None)
    ap.add_argument("--role", default="")
    ap.add_argument("--repeat", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--expect-camera-model", default=None,
                    help="assert cameras.txt reports this model name")
    ap.add_argument("--calibrate-view-graph", action="store_true",
                    help="run view_graph_calibrator on the database FIRST (a separate "
                         "intervention, reported separately from the mapper effect)")
    ap.add_argument("--fix-intrinsics", action="store_true",
                    help="incremental only: ba_refine_focal_length 0, "
                         "ba_refine_extra_params 0 (fixed-intrinsics diagnostic)")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    if not os.path.exists(args.db):
        raise SystemExit(f"no database at {args.db!r}")
    if not os.path.isdir(args.images):
        raise SystemExit(f"no images at {args.images!r}")
    n_images = len([f for f in os.listdir(args.images) if f.endswith(".png")])

    work = args.out
    if os.path.exists(work):
        if not args.overwrite:
            raise SystemExit(f"refusing to overwrite {work!r} (pass --overwrite)")
        shutil.rmtree(work)
    os.makedirs(work)
    sparse = os.path.join(work, "sparse")
    os.makedirs(sparse)

    report = {
        "config": args.config_label,
        "config_role": args.role,
        "hypothesis": args.hypothesis,
        "clip": args.clip,
        "repeat": args.repeat,
        "binary": COLMAP,
        "binary_version": binary_version(COLMAP),
        "seed": args.seed,
        "n_images_offered": n_images,
        "image_path": os.path.relpath(args.images, REPO_ROOT),
        "database_path": os.path.relpath(args.db, REPO_ROOT),
        "mapper_kind": args.mapper,
        "view_graph_calibrated": bool(args.calibrate_view_graph),
        "fixed_intrinsics": bool(args.fix_intrinsics),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "measurements_note": ("Features, descriptors, putative matches and two-view "
                              "geometries are Phase 3A's, byte-identical, carried in on a "
                              "COPY of the Phase 3A database. Nothing was re-extracted or "
                              "re-matched, so a difference against Phase 3A is a mapper / "
                              "camera-model difference and not a front-end difference."),
        "stages": {},
    }
    prep = os.path.splitext(args.db)[0] + ".prep.json"
    if os.path.exists(prep):
        report["database_prep"] = json.load(open(prep))

    logp = os.path.join(work, "stdout.log")
    with open(logp, "w") as log:
        if args.calibrate_view_graph:
            # ONE ordinary invocation. If it fails, that is recorded as a result
            # and the mapper still runs on the (unchanged) copy -- no debugging,
            # no fabricated focal priors, no parameter roulette.
            cmd = [COLMAP, "view_graph_calibrator",
                   "--default_random_seed", str(args.seed),
                   "--database_path", args.db]
            rc, wall, mem = run(cmd, log)
            report["stages"]["view_graph_calibrator"] = {
                "rc": rc, "seconds": round(wall, 1), "peak_rss_gb": round(mem, 2)}
            if rc != 0:
                report["view_graph_calibrator_failed"] = True
                report["view_graph_calibrator_note"] = (
                    "One ordinary invocation, non-zero exit. Recorded as an omission per "
                    "the Phase 3B strict fallback rule; the mapper proceeds on the copied "
                    "database and the calibration intervention is reported as NOT applied.")
                report["view_graph_calibrated"] = False

        if args.mapper == "incremental":
            cmd = [COLMAP, "mapper",
                   "--default_random_seed", str(args.seed),
                   "--Mapper.random_seed", str(args.seed),
                   "--database_path", args.db,
                   "--image_path", args.images,
                   "--output_path", sparse,
                   "--Mapper.multiple_models", "1",
                   "--Mapper.num_threads", "1"]
            if args.fix_intrinsics:
                cmd += ["--Mapper.ba_refine_focal_length", "0",
                        "--Mapper.ba_refine_extra_params", "0",
                        "--Mapper.ba_refine_principal_point", "0"]
        else:
            cmd = [COLMAP, "global_mapper",
                   "--default_random_seed", str(args.seed),
                   "--GlobalMapper.random_seed", str(args.seed),
                   "--database_path", args.db,
                   "--image_path", args.images,
                   "--output_path", sparse,
                   "--GlobalMapper.num_threads", "1",
                   "--GlobalMapper.gp_use_gpu", "0",
                   "--GlobalMapper.ba_ceres_use_gpu", "0"]
        report["mapper_command"] = cmd
        rc, wall, mem = run(cmd, log)
        report["stages"]["mapper"] = {"rc": rc, "seconds": round(wall, 1),
                                      "peak_rss_gb": round(mem, 2)}
        if rc != 0:
            report["failed_at"] = "mapper"
            _write(work, report)
            print(f"FAILED at mapper; see {logp}")
            return 1

        # global_mapper may write the model directly into output_path rather than
        # into numbered sub-directories, so handle both layouts.
        subdirs = sorted(d for d in os.listdir(sparse)
                         if os.path.isdir(os.path.join(sparse, d)))
        if not subdirs and os.path.exists(os.path.join(sparse, "cameras.bin")):
            models = [""]
        else:
            models = subdirs
        report["n_submodels"] = len(models)
        if not models:
            report["failed_at"] = "mapper_produced_no_model"
            _write(work, report)
            print(f"NO MODEL produced; see {logp}")
            return 1

        sizes = {}
        for m in models:
            probe = os.path.join(work, f"_probe_{m or 'root'}")
            os.makedirs(probe, exist_ok=True)
            rc_, _, _ = run([COLMAP, "model_converter",
                             "--input_path", os.path.join(sparse, m),
                             "--output_path", probe, "--output_type", "TXT"], log)
            sizes[m or "root"] = (len(parse_images_txt(os.path.join(probe, "images.txt")))
                                  if rc_ == 0 else -1)
            shutil.rmtree(probe, ignore_errors=True)
        best = max(models, key=lambda m: sizes[m or "root"])
        report["submodel_registered_images"] = sizes
        report["selected_submodel"] = best or "root"
        report["fragmentation_note"] = (
            "Only the largest sub-model is evaluated. `submodel_registered_images` lists "
            "them all: a run whose images are split across several fragments has NOT "
            "reconstructed the clip, however many images it registered in total.")

        txt = os.path.join(work, "sparse_txt")
        os.makedirs(txt, exist_ok=True)
        rc, wall, _ = run([COLMAP, "model_converter",
                           "--input_path", os.path.join(sparse, best),
                           "--output_path", txt, "--output_type", "TXT"], log)
        report["stages"]["model_converter"] = {"rc": rc, "seconds": round(wall, 1)}
        if rc != 0:
            report["failed_at"] = "model_converter"
            _write(work, report)
            return 1

    cams = parse_cameras_txt(os.path.join(txt, "cameras.txt"))
    imgs = parse_images_txt(os.path.join(txt, "images.txt"))
    pts = parse_points3d_txt(os.path.join(txt, "points3D.txt"))

    # Falsification control for the database rewrite: the model COLMAP actually
    # used must be the one that was asked for.
    got = next(iter(cams.values()), {}).get("model")
    report["camera_model_written_by_colmap"] = got
    if args.expect_camera_model and got != args.expect_camera_model:
        report["failed_at"] = "camera_model_mismatch"
        report["camera_model_mismatch"] = {
            "expected": args.expect_camera_model, "got": got,
            "note": ("The database rewrite did not produce the requested camera model. "
                     "Every arm depending on this database is void.")}
        _write(work, report)
        print(f"CAMERA MODEL MISMATCH: expected {args.expect_camera_model}, got {got}")
        return 1

    import numpy as np
    track_lens = [p["track_len"] for p in pts.values()]
    errs = [p["error"] for p in pts.values()]
    report["result"] = {
        "registered_images": len(imgs),
        "registered_fraction": round(len(imgs) / n_images, 4) if n_images else 0.0,
        "n_points3D": len(pts),
        "mean_track_length": float(np.mean(track_lens)) if track_lens else 0.0,
        "median_track_length": float(np.median(track_lens)) if track_lens else 0.0,
        "mean_observations_per_image": (float(np.mean([i["n_observations_2d"]
                                                       for i in imgs.values()]))
                                        if imgs else 0.0),
        "mean_reprojection_error_px": float(np.mean(errs)) if errs else float("nan"),
        "reprojection_error_note": ("DIAGNOSTIC ONLY. A more flexible camera model reaching "
                                    "a lower reprojection error has NOT been shown to "
                                    "produce better geometry. Never rank on this number."),
        "cameras": cams,
    }
    report["total_seconds"] = round(sum(s.get("seconds", 0)
                                        for s in report["stages"].values()), 1)
    report["peak_rss_gb"] = round(max(s.get("peak_rss_gb", 0)
                                      for s in report["stages"].values()), 2)
    _write(work, report)
    r = report["result"]
    cam = next(iter(cams.values()), {})
    print(f"{args.config_label}/{args.clip}/run{args.repeat} [{args.mapper}]: "
          f"registered {r['registered_images']}/{n_images} "
          f"({r['registered_fraction']:.0%}), {r['n_points3D']} points, "
          f"mean track {r['mean_track_length']:.2f}, "
          f"{cam.get('model')} f={cam.get('params', [float('nan')])[0]:.1f}, "
          f"{report['total_seconds']:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
