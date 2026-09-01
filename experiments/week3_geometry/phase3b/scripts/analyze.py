"""Phase 3B — collect every executed arm into one analysis artifact.

EXPLORATORY. Main project venv (numpy only).

One pass over whatever has actually been run. For each hypothesis it emits:

* a summary row per arm (registration, sub-model sizes, structure, triangulation
  conditioning, track temporal span, front-end yield, intrinsics, cost);
* the scale-aligned sparse-vs-sparse SHAPE comparison for the pairs that
  hypothesis is about, with the residual profiled against range and against
  image radius;
* where a repeat exists, the same comparison between run0 and run1 — the noise
  floor any claimed effect has to clear.

For 3B-2 it additionally re-measures the Phase 3A dense products (D, E0, E)
against the GLOBAL reconstruction, because "does the dense model's per-frame
scale drift change when the reference poses change?" is a different question
from "how much does it drift against the incremental reference?", and only the
pair of numbers separates a property of the dense model from an artefact of
incremental pose estimation.

Missing arms are skipped and recorded as missing. Nothing here re-runs anything.

Usage:
    .venv/bin/python -m experiments.week3_geometry.phase3b.scripts.analyze --overwrite
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week3_geometry.scripts import compare as cmp  # noqa: E402
from experiments.week3_geometry.phase3b.scripts.sparse_metrics import (  # noqa: E402
    compare_sparse,
    compare_trajectories,
    load_run,
    summarise_run,
)

W3 = os.path.join(REPO_ROOT, "experiments", "week3_geometry")
P3B = os.path.join(W3, "phase3b")
A3 = os.path.join(W3, "outputs", "colmap")          # Phase 3A runs (read only)
B3 = os.path.join(P3B, "outputs", "colmap")         # Phase 3B runs
OUT = os.path.join(P3B, "outputs", "analysis")

DENSE = {"D_mapanything": "mapanything", "E0_vggt": "vggt", "E_wat3r_ren": "wat3r_ren"}

#: Phase 3B dense products live under phase3b/outputs/range; Phase 3A's under
#: outputs/range. Nothing in the Phase 3A tree is written to.
P3B_RANGE = os.path.join(P3B, "outputs", "range")
#: A VIEW-COUNT-CONTROLLED re-run of the Phase 3A dense arm. Any4D's released
#: inference path cannot process 48 views on this machine (§8), so comparing it
#: against a 48-view MapAnything would confound "explicit dynamic modelling"
#: with "three times as many views". These products are the same models on the
#: same frames Any4D actually saw. Phase 3A's own outputs are untouched.
P3B_RANGE_16V = os.path.join(P3B, "outputs", "range_16v")
P3A_RANGE = os.path.join(W3, "outputs", "range")
P3B_DENSE = {"Y_any4d": "any4d"}
STAGE6 = os.path.join(W3, "outputs", "stage6", "comparison.json")


def merged_preprocess_maps() -> dict:
    """Phase 3A's measured maps, plus Phase 3B's, Phase 3A winning collisions.

    Phase 3A's outputs/preprocess_maps.json is read-only here; Phase 3B's
    additions live in its own file and are merged at read time.
    """
    maps = dict(cmp.load_preprocess_maps())
    p = os.path.join(P3B, "outputs", "preprocess_maps_3b.json")
    if os.path.exists(p):
        with open(p) as fh:
            extra = json.load(fh)
        for fam, val in extra.items():
            if fam.startswith("_") or fam in maps:
                continue
            maps[fam] = val
    return maps


def analyze_3b6(maps: dict) -> dict:
    """3B-6: the Phase 3B dense products, measured the same way Phase 3A measured
    D / E0 / E, and set beside Phase 3A's own numbers on the same clips.

    The comparison that matters is against configuration A on `wreck_03`, where
    MapAnything showed a 6.64x fitted per-frame scale wander and a 129.8 %
    range-dependent residual swing. A challenger matters only if it materially
    repairs that signature -- a few percent is not a result.
    """
    block = {
        "question": ("Does explicit dynamic modelling (Any4D) or sequence-level global "
                     "consistency (VGGT-SLAM) materially repair MapAnything's dynamic "
                     "failure on wreck_03?"),
        "dense_summary": [], "dense_vs_sparse": [], "dense_vs_dense": [],
        "phase3a_reference_rows": [], "missing": [],
    }
    if not os.path.isdir(P3B_RANGE):
        block["missing"].append({"note": "no Phase 3B dense product on disk"})
        return block

    for cfg, fam in P3B_DENSE.items():
        root = os.path.join(P3B_RANGE, cfg)
        if not os.path.isdir(root):
            block["missing"].append({"config": cfg, "note": "not run"})
            continue
        for clip in sorted(os.listdir(root)):
            cj = os.path.join(root, clip, "clip.json")
            if not os.path.exists(cj):
                continue
            meta = json.load(open(cj))
            vf = np.array([f["valid_fraction"] for f in meta["frames"]])
            med = np.array([f["range_median"] for f in meta["frames"]], dtype=float)
            prov = meta["provenance"]
            block["dense_summary"].append({
                "config": cfg, "clip": clip,
                "n_frames": meta["n_frames"],
                "inference_grid_hw": prov.get("inference_resolution_hw"),
                "valid_fraction": {"median": float(np.median(vf)), "min": float(vf.min())},
                "per_frame_median_range_max_over_min": (
                    float(np.nanmax(med) / np.nanmin(med)) if np.nanmin(med) > 0 else float("nan")),
                "seconds": prov.get("seconds"),
                "peak_mps_driver_gb": prov.get("peak_mps_driver_gb"),
                "device": prov.get("device"),
                "checkpoint_license": prov.get("checkpoint_license"),
                "pose_convention_verified": (meta.get("conventions", {})
                                             .get("convention_check", {})
                                             .get("consistent_convention")),
                "validity_policy": meta.get("conventions", {}).get("validity_policy"),
            })
            # Against the classical arms, exactly as Phase 3A measured D/E0/E.
            for ccfg in ("A", "C_off"):
                r = cmp.dense_vs_sparse(cfg, fam, ccfg, clip, maps, range_root=P3B_RANGE)
                if r:
                    block["dense_vs_sparse"].append(r)
            # And against the Phase 3A dense products on the same grid.
            for other, ofam in DENSE.items():
                r = cmp.dense_vs_dense(cfg, fam, other, ofam, clip, maps,
                                       root_a=P3B_RANGE, root_b=P3A_RANGE)
                if r:
                    block["dense_vs_dense"].append(r)

    # THE FAIR COMPARISON. A Phase 3B challenger that could only be run on a
    # subset of views must not be set beside a Phase 3A model measured on all 48:
    # a per-frame scale max/min over 15 samples is smaller than one over 37 by
    # construction, and a range swing pooled over fewer frames spans less of the
    # clip. So every Phase 3A dense product is re-measured against the same
    # classical reference RESTRICTED TO THE CHALLENGER'S OWN FRAMES.
    block["phase3a_on_matched_frames"] = []
    for row in block["dense_summary"]:
        clip = row["clip"]
        cj = os.path.join(P3B_RANGE, row["config"], clip, "clip.json")
        frames = {f["frame_index"] for f in json.load(open(cj))["frames"]}
        for other, ofam in DENSE.items():
            r = cmp.dense_vs_sparse(other, ofam, "A", clip, maps, frames=frames)
            if r:
                r["restricted_to_frames_of"] = row["config"]
                r["n_frames_restricted_to"] = len(frames)
                r["views_seen_by_model"] = 48
                block["phase3a_on_matched_frames"].append(r)
            # The fully controlled arm: the same model re-run seeing only the
            # frames the challenger saw.
            r16 = cmp.dense_vs_sparse(other, ofam, "A", clip, maps,
                                      range_root=P3B_RANGE_16V)
            if r16:
                r16["restricted_to_frames_of"] = row["config"]
                r16["views_seen_by_model"] = 16
                r16["dense"] = other + "_16v"
                block["phase3a_on_matched_frames"].append(r16)

    # Phase 3A's own rows for the same clips, quoted for side-by-side reading.
    clips = sorted({d["clip"] for d in block["dense_summary"]})
    if clips and os.path.exists(STAGE6):
        s6 = json.load(open(STAGE6))
        for row in s6.get("dense_vs_sparse", []):
            if row.get("clip") in clips and row.get("reference") == "A":
                block["phase3a_reference_rows"].append({
                    "dense": row["dense"], "clip": row["clip"], "reference": "A",
                    "coverage_fraction": row.get("coverage_fraction"),
                    "global_scale": row.get("global_scale"),
                    "abs_relative_error": row.get("abs_relative_error"),
                    "residual_vs_reference_range": row.get("residual_vs_reference_range"),
                    "per_frame_scale_diagnostic": {
                        k: v for k, v in (row.get("per_frame_scale_diagnostic") or {}).items()
                        if k != "trace"},
                })
    return block


def rd(root: str, config: str, clip: str, repeat: int = 0) -> str:
    return os.path.join(root, config, clip, f"run{repeat}")


# --------------------------------------------------------------------------
# Hypothesis definitions. `arm -> (root, config, clip_suffix)`.
# --------------------------------------------------------------------------

HYP: dict[str, dict] = {
    "3B-1": {
        "question": ("Which component of A->B produces the longer tracks -- the ALIKED "
                     "features, the LightGlue matcher, or their interaction -- and does "
                     "any of it change the recovered scene shape?"),
        "clips": ["wreck_05", "wreck_01"],
        "arms": {
            "F1_sift_bruteforce":    (A3, "A", ""),
            "F2_sift_lightglue":     (B3, "F2", ""),
            "F3_aliked_bruteforce":  (B3, "F3", ""),
            "F4_aliked_lightglue":   (A3, "B", ""),
        },
        "pairs": [("F1_sift_bruteforce", "F2_sift_lightglue"),
                  ("F3_aliked_bruteforce", "F4_aliked_lightglue"),
                  ("F1_sift_bruteforce", "F3_aliked_bruteforce"),
                  ("F2_sift_lightglue", "F4_aliked_lightglue"),
                  ("F1_sift_bruteforce", "F4_aliked_lightglue")],
        # F1's repeat is Phase 3A's own A/<clip>/run1 -- reused, not re-run. It is
        # the noise floor the F1->F2 shape difference has to clear, and Phase 3A
        # measured its spread only in registration and point count, never in the
        # shape metric that actually decides anything here.
        "repeats": {"F1_sift_bruteforce": ["wreck_05"],
                    "F2_sift_lightglue": ["wreck_05"],
                    "F3_aliked_bruteforce": ["wreck_05"]},
    },
    "3B-2": {
        "question": ("Are Phase 3A's pose/shape instabilities consequences of INCREMENTAL "
                     "SfM rather than of the measurements themselves?"),
        "clips": ["wreck_05", "wreck_01", "wreck_03", "swimthrough_02"],
        "arms": {
            "A_incremental": (A3, "A", ""),
            "A_global":      (B3, "A_global", ""),
            "A_global_cal":  (B3, "A_global_cal", ""),
        },
        "pairs": [("A_incremental", "A_global"),
                  ("A_incremental", "A_global_cal"),
                  ("A_global", "A_global_cal")],
        "repeats": {"A_global": ["wreck_05"]},
        "dense_against": ["A_global"],
    },
    "3B-3": {
        "question": ("Is ordinary COLMAP geometry stable to reasonable CENTRAL "
                     "camera-model choices, or is self-calibration a major source of the "
                     "Phase 3A cross-family disagreement?"),
        "clips": ["wreck_07", "wreck_05", "swimthrough_02", "wreck_01"],
        "arms": {
            "A_phase3a":               (A3, "A", ""),
            "M_simple_radial":         (B3, "M_simple_radial", ""),
            "M_radial":                (B3, "M_radial", ""),
            "M_opencv":                (B3, "M_opencv", ""),
            "M_simple_radial_fisheye": (B3, "M_simple_radial_fisheye", ""),
            "M_fixed_from_wreck07":    (B3, "M_fixed_from_wreck07", ""),
        },
        "pairs": [("A_phase3a", "M_simple_radial"),
                  ("M_simple_radial", "M_radial"),
                  ("M_simple_radial", "M_opencv"),
                  ("M_simple_radial", "M_simple_radial_fisheye"),
                  ("M_simple_radial", "M_fixed_from_wreck07"),
                  ("A_phase3a", "M_fixed_from_wreck07")],
        "repeats": {"M_simple_radial": ["wreck_05"], "M_opencv": ["wreck_05"]},
        # The dense products are re-measured against each camera-model arm as
        # CONSISTENCY evidence only: a camera model that moves COLMAP closer to
        # the dense estimates has not been shown to be more correct, and §14's
        # bar explicitly excludes "agreement with another uncalibrated method".
        "dense_against": ["M_simple_radial", "M_opencv",
                          "M_simple_radial_fisheye", "M_fixed_from_wreck07"],
    },
    "3B-4": {
        "question": ("Does the classical reconstruction change materially when 48 "
                     "observations are replaced by fewer views spanning the SAME temporal "
                     "extent?"),
        "clips": ["wreck_05", "wreck_01", "cenote_01"],
        "arms": {
            "S48": (A3, "A", ""),
            "S25": (B3, "A", "_S25"),
            "S13": (B3, "A", "_S13"),
        },
        "pairs": [("S48", "S25"), ("S25", "S13"), ("S48", "S13")],
        "repeats": {"S25": ["wreck_05", "wreck_01", "cenote_01"],
                    "S13": ["wreck_05", "wreck_01", "cenote_01"]},
    },
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(OUT, "analysis.json"))
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--only", nargs="*", default=None, help="restrict to these hypotheses")
    args = ap.parse_args()
    if os.path.exists(args.out) and not args.overwrite:
        raise SystemExit(f"refusing to overwrite {args.out!r} (pass --overwrite)")

    out = {
        "_comment": ("Phase 3B analysis. Every residual uses exactly ONE global scale per "
                     "method-pair per clip, fitted over observations pooled across the whole "
                     "clip; per-frame scale fits appear only as drift diagnostics and are "
                     "never fed back. Sparse-vs-sparse correspondence is by 2D proximity "
                     "WITHIN the same image. No arm is treated as ground truth -- there is "
                     "no independent range measurement anywhere in Week 3, so every "
                     "cross-arm number is a CONSISTENCY statement, never a correctness one."),
        "hypotheses": {},
    }

    maps = None
    if not args.only or "3B-6" in args.only:
        maps = merged_preprocess_maps()
    for hid, spec in HYP.items():
        if args.only and hid not in args.only:
            continue
        block: dict = {"question": spec["question"], "runs": [], "missing": [],
                       "shape_comparisons": [], "trajectory_comparisons": [],
                       "repeat_spread": []}
        models: dict[tuple[str, str], dict] = {}

        for clip in spec["clips"]:
            for arm, (root, cfg, suffix) in spec["arms"].items():
                d = rd(root, cfg, clip + suffix)
                run = load_run(d)
                if run is None:
                    block["missing"].append({"arm": arm, "clip": clip,
                                             "expected": os.path.relpath(d, REPO_ROOT)})
                    continue
                row = summarise_run(run)
                row["arm"] = arm
                row["clip"] = clip
                block["runs"].append(row)
                if run["model"] is not None:
                    models[(arm, clip)] = run["model"]

        for clip in spec["clips"]:
            for a, b in spec["pairs"]:
                ma, mb = models.get((a, clip)), models.get((b, clip))
                if ma is None or mb is None:
                    continue
                r = compare_sparse(ma, mb, a, b)
                r["clip"] = clip
                block["shape_comparisons"].append(r)
                tr = compare_trajectories(ma, mb, a, b)
                tr["clip"] = clip
                block["trajectory_comparisons"].append(tr)

        for arm, clips in spec.get("repeats", {}).items():
            root, cfg, suffix = spec["arms"][arm]
            for clip in clips:
                r0 = load_run(rd(root, cfg, clip + suffix, 0))
                r1 = load_run(rd(root, cfg, clip + suffix, 1))
                if r0 is None or r1 is None or r0["model"] is None or r1["model"] is None:
                    continue
                r = compare_sparse(r0["model"], r1["model"], f"{arm}/run0", f"{arm}/run1")
                r["clip"] = clip
                r["kind"] = "repeat_run_spread"
                res0 = r0["report"].get("result") or {}
                res1 = r1["report"].get("result") or {}
                r["registered"] = [res0.get("registered_images"),
                                   res1.get("registered_images")]
                r["n_points3D"] = [res0.get("n_points3D"), res1.get("n_points3D")]
                block["repeat_spread"].append(r)

        # 3B-2 only: the dense products re-measured against the global poses.
        if spec.get("dense_against"):
            if maps is None:
                maps = merged_preprocess_maps()
            block["dense_vs_reference"] = []
            for ref_arm in spec["dense_against"]:
                for clip in spec["clips"]:
                    m = models.get((ref_arm, clip))
                    if m is None:
                        continue
                    for dcfg, fam in DENSE.items():
                        try:
                            r = cmp.dense_vs_sparse(dcfg, fam, ref_arm, clip, maps, model=m)
                        except Exception as exc:            # noqa: BLE001
                            r = {"dense": dcfg, "reference": ref_arm, "clip": clip,
                                 "error": f"{type(exc).__name__}: {exc}"}
                        if r:
                            r["reference_arm"] = ref_arm
                            block["dense_vs_reference"].append(r)

        out["hypotheses"][hid] = block
        print(f"{hid}: {len(block['runs'])} runs, {len(block['shape_comparisons'])} shape "
              f"comparisons, {len(block['repeat_spread'])} repeats, "
              f"{len(block['missing'])} missing")

    if not args.only or "3B-6" in args.only:
        if maps is None:
            maps = merged_preprocess_maps()
        b6 = analyze_3b6(maps)
        out["hypotheses"]["3B-6"] = b6
        print(f"3B-6: {len(b6['dense_summary'])} dense products, "
              f"{len(b6['dense_vs_sparse'])} dense-vs-sparse, "
              f"{len(b6['dense_vs_dense'])} dense-vs-dense")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=2, default=_jsonable)
    print(f"wrote {os.path.relpath(args.out, REPO_ROOT)}")
    return 0


def _jsonable(o):
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


if __name__ == "__main__":
    sys.exit(main())
