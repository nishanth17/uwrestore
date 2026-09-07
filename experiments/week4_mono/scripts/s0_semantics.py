"""S0 — semantics, preprocessing and runtime gate. ONE MODEL PER PROCESS.

EXPLORATORY. Runs inside the backend's own venv.

S0 is WRAPPER VALIDATION, not benchmarking. It deliberately does NOT run the
288-frame set: `MONO_DEPTH_FREEZE.md` and the task specification restrict it to
a four-image sanity set —

    one ordinary project underwater frame        (wreck_07, landscape)
    one difficult project underwater frame       (wreck_05, low texture)
    one portrait/orientation-sensitive frame     (wreck_01, PORTRAIT)
    one public/reference image                   (vendored, non-underwater)

What it establishes, per FREEZE §5 S0:

  * which devices actually work here — MPS / CPU / CUDA-required / needs
    reference-implementation modifications — from EXECUTION, never from a paper;
  * the strict N=1 invariant;
  * the exact native representation and its conversion to camera-centre range,
    including whether the model can honestly produce one at all;
  * valid-mask semantics;
  * preprocessing: resize, crop, letterbox, orientation, and the FOV AUDIT.

THE FOV AUDIT IS A MEASUREMENT. Week 3 found that preprocessing can silently
discard a third of the frame, and it found that by pushing marker images
through each model's OWN preprocessing and seeing where the markers landed —
not by reading resize code. That method is reused here through each backend's
`preprocessed_image()` probe, at BOTH source orientations, because `wreck_01`
is portrait and the VGGT-family crop is where Week 3's loss appeared.

A model that fails S0 gets ONE bounded repair attempt, and if that fails it is
recorded as failed and only that model is dropped. Semantics are never invented
to make a model pass.

    experiments/week4_mono/.venv-mono/bin/python \\
        -m experiments.week4_mono.scripts.s0_semantics --model dav2_small
"""

from __future__ import annotations

import argparse
import gc
import os
import sys
import traceback

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week4_mono import backends, common  # noqa: E402

#: Marker grid for the FOV audit, as fractions of (width-1, height-1). Same
#: construction as Week 3's `calibrate_preprocess.py` so the two are comparable.
MARKER_FRACTIONS = [0.12, 0.30, 0.50, 0.70, 0.88]
MARKER_SIDE = 7          # odd, so the marker has an exact centre pixel


# --------------------------------------------------------------------------
# FOV audit
# --------------------------------------------------------------------------


def _marker_images(h: int, w: int, tmpdir: str) -> list[tuple[str, float, float]]:
    """One black image per marker, marker centred on a known source pixel."""
    from PIL import Image
    out = []
    r = MARKER_SIDE // 2
    for fy in MARKER_FRACTIONS:
        for fx in MARKER_FRACTIONS:
            u = min(max(int(round(fx * (w - 1))), r), w - 1 - r)
            v = min(max(int(round(fy * (h - 1))), r), h - 1 - r)
            img = np.zeros((h, w, 3), dtype=np.uint8)
            img[v - r:v + r + 1, u - r:u + r + 1] = 255
            p = os.path.join(tmpdir, f"m_{v:04d}_{u:04d}.png")
            Image.fromarray(img).save(p)
            out.append((p, float(u), float(v)))
    return out


def _locate(grid: np.ndarray):
    """Intensity-weighted centroid of the marker on a preprocessed grid."""
    a = np.asarray(grid, dtype=np.float64)
    if a.ndim == 3:
        a = a.mean(axis=-1)
    lo, hi = float(a.min()), float(a.max())
    if hi - lo < 1e-6:
        return None
    m = a >= (hi - 0.25 * (hi - lo))
    if m.sum() == 0:
        return None
    ys, xs = np.nonzero(m)
    wgt = a[ys, xs] - lo
    if wgt.sum() <= 0:
        return None
    return float((xs * wgt).sum() / wgt.sum()), float((ys * wgt).sum() / wgt.sum())


def _fit_axis(src: np.ndarray, dst: np.ndarray) -> dict:
    out = {}
    for k, axis in enumerate(("u", "v")):
        A = np.stack([src[:, k], np.ones(len(src))], axis=1)
        coef, *_ = np.linalg.lstsq(A, dst[:, k], rcond=None)
        out[f"{axis}_scale"] = float(coef[0])
        out[f"{axis}_offset"] = float(coef[1])
        out[f"{axis}_max_abs_residual_px"] = float(np.abs(A @ coef - dst[:, k]).max())
    return out


def fov_audit(be, source_hw: tuple[int, int], tmpdir: str) -> dict:
    """Measure the source-pixel -> model-grid map and how much frame is lost."""
    h, w = source_hw
    items = _marker_images(h, w, tmpdir)
    src, dst, lost = [], [], []
    grid_hw = None
    for path, u, v in items:
        grid = be.preprocessed_image(path)
        if grid is None:
            return {"measured": False,
                    "reason": "backend exposes no preprocessed_image() probe"}
        grid_hw = [int(grid.shape[0]), int(grid.shape[1])]
        loc = _locate(grid)
        if loc is None:
            # Markers that fall outside the grid after cropping are REPORTED,
            # never silently dropped: they are the direct evidence of how much
            # field of view the preprocessing discards.
            lost.append([u, v])
            continue
        src.append([u, v])
        dst.append(list(loc))

    res = {
        "measured": True,
        "source_hw": [h, w],
        "model_grid_hw": grid_hw,
        "n_markers_used": len(src),
        "n_markers_lost_to_crop": len(lost),
        "markers_lost_source_uv": lost,
    }
    if len(src) >= 3:
        res.update(_fit_axis(np.asarray(src), np.asarray(dst)))
        # Fraction of the SOURCE frame that survives onto the model grid,
        # computed from the fitted map and the grid bounds.
        us = res["u_scale"] * np.array([0.0, w - 1.0]) + res["u_offset"]
        vs = res["v_scale"] * np.array([0.0, h - 1.0]) + res["v_offset"]
        keep_u = (min(us[1], grid_hw[1] - 1.0) - max(us[0], 0.0)) / max(us[1] - us[0], 1e-9)
        keep_v = (min(vs[1], grid_hw[0] - 1.0) - max(vs[0], 0.0)) / max(vs[1] - vs[0], 1e-9)
        res["fov_retained_u"] = float(np.clip(keep_u, 0.0, 1.0))
        res["fov_retained_v"] = float(np.clip(keep_v, 0.0, 1.0))
        res["fov_retained_area"] = float(res["fov_retained_u"] * res["fov_retained_v"])
    else:
        res["fit"] = "insufficient surviving markers to fit"
    return res


# --------------------------------------------------------------------------
# per-image semantics probe
# --------------------------------------------------------------------------


def probe_image(be, item: dict) -> dict:
    """Run one sanity image and record what came back, without interpreting it."""
    out = be.infer(item["path"])
    native = np.asarray(out["native"])
    valid = np.asarray(out["valid"])
    rng = out.get("canonical_range")
    rec = {
        "key": item["key"],
        "why": item["why"],
        "clip": item["clip"],
        "frame": item["frame"],
        "path": os.path.relpath(item["path"], REPO_ROOT),
        "native_shape": [int(x) for x in native.shape],
        "native_dtype": str(native.dtype),
        "valid_shape": [int(x) for x in valid.shape],
        "valid_fraction": float(valid.mean()),
        "emits_range": rng is not None,
        "emits_K": out.get("K") is not None,
        "emits_conf": out.get("conf") is not None,
        "aux": sorted((out.get("aux") or {}).keys()),
        "extra": out.get("extra", {}),
    }
    if item["path"].endswith(".png") or item["path"].endswith(".jpg"):
        import cv2
        img = cv2.imread(item["path"])
        rec["source_hw"] = [int(img.shape[0]), int(img.shape[1])]
        rec["output_equals_source_grid"] = (rec["source_hw"] == list(valid.shape))
    v = valid & np.isfinite(native if native.ndim == 2 else native[..., 0])
    if rng is not None:
        r = np.asarray(rng)
        m = valid & np.isfinite(r)
        if m.any():
            rec["range_p05"] = float(np.percentile(r[m], 5))
            rec["range_median"] = float(np.median(r[m]))
            rec["range_p95"] = float(np.percentile(r[m], 95))
    nat = native[v] if native.ndim == 2 else native[v].reshape(-1, native.shape[-1])
    if nat.size:
        rec["native_p05"] = float(np.percentile(nat, 5))
        rec["native_median"] = float(np.median(nat))
        rec["native_p95"] = float(np.percentile(nat, 95))
    return rec


def device_probe(model_key: str, device: str, image: str) -> dict:
    """Does this device work AT ALL for this model? Load + one inference."""
    rec = {"device": device}
    try:
        common.seed_everything()
        cls = backends.get(model_key)
        be = cls(device=device)
        be.load()
        rec["load_seconds"] = round(be.load_seconds, 2)
        out = be.infer(image)
        rec["infer_seconds"] = round(out["extra"]["infer_seconds"], 3)
        rec["works"] = True
        rec["peak_rss_gb"] = round(common.peak_rss_gb(), 2)
        if device == "mps":
            rec["peak_mps_driver_gb"] = round(common.mps_peak_gb(), 2)
        del be, out
        gc.collect()
    except Exception as exc:
        rec["works"] = False
        rec["error"] = f"{type(exc).__name__}: {exc}"
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, choices=backends.keys())
    ap.add_argument("--device", default="mps")
    ap.add_argument("--skip-cpu", action="store_true",
                    help="skip the CPU device probe (it is slow for large models)")
    ap.add_argument("--skip-fov", action="store_true")
    ap.add_argument("--out-dir", default=os.path.join(common.OUTPUTS, "s0"))
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    out_path = os.path.join(args.out_dir, f"{args.model}.json")
    common.refuse_clobber(out_path, args.overwrite)

    common.seed_everything()
    items = common.s0_sanity_items()
    report = {
        "model": args.model,
        "checkpoint": common.MODEL_CHECKPOINT[args.model],
        "declared_native_representation": common.DECLARED_NATIVE[args.model],
        "env": common.env_report(),
        "seed": common.SEED,
        "sanity_set": [{"key": i["key"], "clip": i["clip"], "frame": i["frame"],
                        "why": i["why"],
                        "path": os.path.relpath(i["path"], REPO_ROOT)} for i in items],
    }

    # --- 1. the model itself, on the requested device --------------------
    try:
        cls = backends.get(args.model)
        be = cls(device=args.device)
        be.load()
    except Exception:
        report["status"] = "FAIL_LOAD"
        report["traceback"] = traceback.format_exc()
        common.write_json(out_path, report, overwrite=True)
        print(f"[S0] {args.model}: FAIL_LOAD -> {out_path}")
        return 2

    report["load_seconds"] = round(be.load_seconds, 2)
    report["native_kind"] = be.native_kind
    report["range_rule"] = be.range_rule
    report["semantics"] = be.semantics()
    report["preprocessing_declared"] = be.preprocessing()
    report["provenance"] = be.provenance()

    # --- 2. the four sanity images ---------------------------------------
    probes, failures = [], []
    for item in items:
        try:
            probes.append(probe_image(be, item))
        except Exception as exc:
            failures.append({"key": item["key"], "error": f"{type(exc).__name__}: {exc}",
                             "traceback": traceback.format_exc()})
    report["image_probes"] = probes
    report["image_failures"] = failures

    # --- 3. FOV audit at BOTH source orientations ------------------------
    if not args.skip_fov:
        import tempfile
        fov = {}
        for hw in [(720, 1280), (1280, 720)]:
            with tempfile.TemporaryDirectory() as td:
                try:
                    fov[f"{hw[0]}x{hw[1]}"] = fov_audit(be, hw, td)
                except Exception as exc:
                    fov[f"{hw[0]}x{hw[1]}"] = {"measured": False,
                                               "error": f"{type(exc).__name__}: {exc}"}
        report["fov_audit"] = fov

    del be
    gc.collect()

    # --- 4. device matrix -------------------------------------------------
    # One image only. This answers "does it run here", not "how fast is it" —
    # S1 measures runtime properly.
    dev_img = items[0]["path"]
    devices = [{"device": args.device, "works": True,
                "note": "the run above"}]
    if not args.skip_cpu:
        devices.append(device_probe(args.model, "cpu", dev_img))
    report["device_matrix"] = devices
    report["cuda_available_here"] = report["env"].get("cuda_available", False)

    # --- 5. gate ----------------------------------------------------------
    n_ok = len(probes)
    single_view_ok = all(
        p["extra"].get("n_views_seen_by_model", 1) == 1 for p in probes)
    report["strict_n1_verified"] = bool(single_view_ok)
    report["status"] = "PASS" if (n_ok == len(items) and single_view_ok) else "PARTIAL"
    if n_ok == 0:
        report["status"] = "FAIL_INFER"

    common.write_json(out_path, report, overwrite=True)
    print(f"[S0] {args.model}: {report['status']} "
          f"({n_ok}/{len(items)} images) -> {os.path.relpath(out_path, REPO_ROOT)}")
    for p in probes:
        print(f"      {p['key']:20s} native={p['native_shape']} "
              f"valid={p['valid_fraction']:.4f} range={p.get('range_median', float('nan')):.4g}")
    if not args.skip_fov:
        for k, v in report["fov_audit"].items():
            if v.get("measured"):
                print(f"      FOV {k}: grid={v['model_grid_hw']} "
                      f"lost={v['n_markers_lost_to_crop']}/25 "
                      f"area_retained={v.get('fov_retained_area', float('nan')):.3f}")
            else:
                print(f"      FOV {k}: NOT MEASURED ({v.get('reason') or v.get('error')})")
    for f in failures:
        print(f"      FAILED {f['key']}: {f['error']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
