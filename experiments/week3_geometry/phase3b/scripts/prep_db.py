"""Phase 3B — copy a Phase 3A COLMAP database and, optionally, rewrite ONE row.

EXPLORATORY. Main project venv (stdlib only).

3B-2 and 3B-3 both need to change exactly one thing about an existing
reconstruction and nothing else. Re-running `feature_extractor` with a different
`--ImageReader.camera_model` would also re-run multithreaded matching, and Phase
3A had to *measure* that stage's nondeterminism rather than assume it away. So
instead: copy the Phase 3A database, and for 3B-3 rewrite the single `cameras`
row that names the camera model.

That keeps the extracted frames, the SIFT keypoints, the descriptors, the
putative matches and the two-view geometries **byte-identical** across arms.

Two safety rules, both enforced here:

* The Phase 3A database is opened READ-ONLY and is never written to. Everything
  happens on the copy (CLAUDE.md invariant 7).
* The rewrite uses COLMAP's own initialisation convention, read out of the source
  row: the focal it already holds, the principal point it already holds, extra
  parameters zero, focal repeated when the model has two. No arm gets a different
  starting point from any other, so a difference between arms is the camera
  model and not a different initial guess.

The rewrite is validated downstream, not trusted: `run_mapper.py` asserts that the
model name COLMAP writes into `cameras.txt` is the one that was requested, and
3B-3 runs a `SIMPLE_RADIAL` control arm through this same path that must reproduce
Phase 3A's configuration A.

Usage:
    .venv/bin/python -m experiments.week3_geometry.phase3b.scripts.prep_db \
        --src-run experiments/week3_geometry/outputs/colmap/A/wreck_05/run0 \
        --dst    experiments/week3_geometry/phase3b/outputs/db/3b3_wreck_05_opencv.db \
        --camera-model OPENCV
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import struct
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

# (model_id, n_focal, n_principal_point, n_extra) read from the INSTALLED
# COLMAP 4.1.1 headers at /opt/homebrew/include/colmap/sensor/models.h, not from
# memory or documentation. Only the models Phase 3B declares are listed.
CAMERA_MODELS = {
    "SIMPLE_PINHOLE":        (0, 1, 2, 0),
    "PINHOLE":               (1, 2, 2, 0),
    "SIMPLE_RADIAL":         (2, 1, 2, 1),
    "RADIAL":                (3, 1, 2, 2),
    "OPENCV":                (4, 2, 2, 4),
    "SIMPLE_RADIAL_FISHEYE": (8, 1, 2, 1),
}


def initial_params(model: str, f0: float, cx: float, cy: float) -> list[float]:
    """COLMAP's own initialisation: focal (repeated if two), centre, zeros."""
    _mid, nf, npp, nex = CAMERA_MODELS[model]
    assert npp == 2
    return [f0] * nf + [cx, cy] + [0.0] * nex


def read_camera(db_path: str) -> dict:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = con.execute("SELECT camera_id, model, width, height, params, "
                           "prior_focal_length FROM cameras").fetchall()
    finally:
        con.close()
    if len(rows) != 1:
        raise SystemExit(f"expected exactly one camera in {db_path!r}, found {len(rows)}. "
                         "Phase 3A used single_camera=1; a multi-camera database is not "
                         "something this script should silently guess about.")
    cid, model, w, h, blob, prior = rows[0]
    params = list(struct.unpack("<%dd" % (len(blob) // 8), blob))
    return {"camera_id": cid, "model_id": model, "width": w, "height": h,
            "params": params, "prior_focal_length": bool(prior)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src-run", required=True,
                    help="Phase 3A run directory containing database.db")
    ap.add_argument("--dst", required=True, help="destination database path (a COPY)")
    ap.add_argument("--camera-model", default=None,
                    help=f"rewrite the camera model; one of {sorted(CAMERA_MODELS)}")
    ap.add_argument("--params", default=None,
                    help="explicit comma-separated params (fixed-intrinsics diagnostic); "
                         "must match the model's parameter count")
    ap.add_argument("--mark-prior-focal", action="store_true",
                    help="set prior_focal_length=1 (only meaningful with --params)")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    src_db = os.path.join(args.src_run, "database.db")
    if not os.path.exists(src_db):
        raise SystemExit(f"no database at {src_db!r}")
    if os.path.exists(args.dst) and not args.overwrite:
        raise SystemExit(f"refusing to overwrite {args.dst!r} (pass --overwrite)")
    os.makedirs(os.path.dirname(os.path.abspath(args.dst)), exist_ok=True)

    before = read_camera(src_db)
    shutil.copy2(src_db, args.dst)

    record = {
        "source_run": os.path.relpath(args.src_run, REPO_ROOT),
        "source_database": os.path.relpath(src_db, REPO_ROOT),
        "destination": os.path.relpath(args.dst, REPO_ROOT),
        "source_camera": before,
        "rewrote_camera": False,
        "note": ("The Phase 3A database was opened read-only and copied. Keypoints, "
                 "descriptors, putative matches and two-view geometries are byte-identical "
                 "to Phase 3A's; only the cameras row may differ."),
    }

    if args.camera_model:
        model = args.camera_model.upper()
        if model not in CAMERA_MODELS:
            raise SystemExit(f"unknown camera model {model!r}; have {sorted(CAMERA_MODELS)}")
        mid, nf, npp, nex = CAMERA_MODELS[model]
        n_expected = nf + npp + nex
        if args.params:
            params = [float(x) for x in args.params.split(",")]
            if len(params) != n_expected:
                raise SystemExit(f"{model} takes {n_expected} params, got {len(params)}")
            source_of_params = "explicit --params (fixed-intrinsics diagnostic)"
        else:
            # The source row's own focal and principal point, so no arm gets a
            # different starting guess from any other.
            f0 = before["params"][0]
            _mid_s, nf_s, _npp_s, _nex_s = next(
                (v for v in CAMERA_MODELS.values() if v[0] == before["model_id"]),
                (before["model_id"], 1, 2, 1))
            cx, cy = before["params"][nf_s], before["params"][nf_s + 1]
            params = initial_params(model, f0, cx, cy)
            source_of_params = ("COLMAP's initialisation convention, using the focal and "
                                "principal point already in the source database")
        prior = 1 if args.mark_prior_focal else (1 if before["prior_focal_length"] else 0)
        blob = struct.pack("<%dd" % len(params), *params)
        con = sqlite3.connect(args.dst)
        try:
            con.execute("UPDATE cameras SET model = ?, params = ?, prior_focal_length = ? "
                        "WHERE camera_id = ?",
                        (mid, blob, prior, before["camera_id"]))
            con.commit()
        finally:
            con.close()
        after = read_camera(args.dst)
        record.update({
            "rewrote_camera": True,
            "requested_model": model,
            "requested_model_id": mid,
            "params_source": source_of_params,
            "destination_camera": after,
            "validation_note": ("The model id written here is validated downstream: "
                                "run_mapper.py asserts that the model NAME COLMAP writes "
                                "into cameras.txt equals the requested one, so a wrong id "
                                "cannot pass silently."),
        })

    with open(os.path.splitext(args.dst)[0] + ".prep.json", "w") as fh:
        json.dump(record, fh, indent=2)
    print(f"prepared {os.path.relpath(args.dst, REPO_ROOT)}"
          + (f" [camera -> {args.camera_model.upper()} "
             f"{[round(p, 4) for p in record['destination_camera']['params']]}]"
             if record["rewrote_camera"] else " [camera unchanged]"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
