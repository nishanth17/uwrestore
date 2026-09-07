"""S1 — determinism, numerical noise floor, runtime and memory. ONE MODEL PER PROCESS.

EXPLORATORY. Runs inside the backend's own venv.

WHY THIS EXISTS (FREEZE §5 S1). Everything after this stage is a difference:
S3's model-vs-reference residual, S4's response to an appearance perturbation,
S5's frame-to-frame trajectory, S6's restoration delta. A difference is only
evidence if it is bigger than the noise the instrument makes on its own. So
before any of those are interpreted, each model is run repeatedly on IDENTICAL
input under IDENTICAL conditions, and the spread of its own output is measured.

    No downstream delta smaller than the floor measured here may be
    interpreted as scientific signal.

A non-deterministic candidate is NOT automatically eliminated — it just gets a
larger floor, and every later claim about it has to clear that floor.

Two kinds of repetition are measured, because they answer different questions:

    within-process   the same loaded model, called again
                     -> the floor for S4/S5, where one process sweeps many frames

    across-process   a fresh process, fresh weights load, fresh MPS context
                     -> the floor for comparing results persisted on different days

The freeze does NOT ask for the full 288-frame set here, and running it would
burn compute to answer a question a small representative subset answers just as
well. The subset is four frames spanning the frozen material's range of
difficulty and both orientations.

    experiments/week4_mono/.venv-mono/bin/python \\
        -m experiments.week4_mono.scripts.s1_determinism --model dav2_small --repeats 3
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import subprocess
import sys

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week4_mono import backends, common  # noqa: E402

#: Representative subset of the frozen material: the easy high-texture case, the
#: hard low-texture case, the widest near/far range, and the PORTRAIT clip.
#: Middle frame of each, so no clip is represented by its first frame alone.
S1_FRAMES = [("wreck_07", 0.5), ("wreck_05", 0.5), ("cenote_01", 0.5), ("wreck_01", 0.5)]


def s1_items() -> list[dict]:
    out = []
    for clip, frac in S1_FRAMES:
        idx = common.frame_indices(clip)
        fi = idx[int(frac * (len(idx) - 1))]
        out.append({"clip": clip, "frame": fi, "path": common.frame_path(clip, fi),
                    "role": common.CLIP_ROLE[clip]})
    return out


def field_of(out: dict) -> np.ndarray:
    """The array S1 compares: the canonical range where there is one, else native.

    Comparing the NATIVE field for models that have no range keeps the floor in
    the units the alignment policy will actually work in, rather than in a
    quantity the model never produced.
    """
    f = out.get("canonical_range")
    if f is None:
        f = out["native"]
    return np.asarray(f, dtype=np.float64)


def compare(a: np.ndarray, b: np.ndarray, valid: np.ndarray) -> dict:
    """Difference statistics between two runs, on their common valid support."""
    m = valid & np.isfinite(a) & np.isfinite(b)
    if a.ndim == 3:
        m = m & np.isfinite(a).all(axis=-1) & np.isfinite(b).all(axis=-1)
        d = np.linalg.norm(a - b, axis=-1)[m]
        ref = np.linalg.norm(a, axis=-1)[m]
    else:
        d = np.abs(a - b)[m]
        ref = np.abs(a)[m]
    if d.size == 0:
        return {"n": 0}
    with np.errstate(divide="ignore", invalid="ignore"):
        rel = d / np.where(ref > 0, ref, np.nan)
    rel = rel[np.isfinite(rel)]
    return {
        "n": int(d.size),
        "bitwise_identical": bool(np.array_equal(a[m], b[m])),
        "max_abs": float(d.max()),
        "median_abs": float(np.median(d)),
        "p99_abs": float(np.percentile(d, 99)),
        "max_rel": float(rel.max()) if rel.size else float("nan"),
        "median_rel": float(np.median(rel)) if rel.size else float("nan"),
        "p99_rel": float(np.percentile(rel, 99)) if rel.size else float("nan"),
    }


def run_repeats(model: str, device: str, items: list[dict], repeats: int) -> dict:
    """Within-process repetition: load once, infer each image `repeats` times."""
    common.seed_everything()
    be = backends.get(model)(device=device)
    be.load()
    per = {}
    runtimes = []
    for item in items:
        key = f"{item['clip']}/f{item['frame']:06d}"
        runs = []
        base_valid = None
        for r in range(repeats):
            common.seed_everything()          # reseeded every call, deliberately
            out = be.infer(item["path"])
            runtimes.append(out["extra"]["infer_seconds"])
            v = np.asarray(out["valid"])
            base_valid = v if base_valid is None else (base_valid & v)
            runs.append((field_of(out), v))
        rec = {"clip": item["clip"], "frame": item["frame"], "role": item["role"],
               "repeats": repeats,
               "valid_fraction_per_run": [float(v.mean()) for _, v in runs],
               "valid_mask_identical": bool(all(np.array_equal(runs[0][1], v)
                                                for _, v in runs[1:])),
               "pairs": []}
        for r in range(1, repeats):
            rec["pairs"].append({"vs_run0": r,
                                 **compare(runs[0][0], runs[r][0], base_valid)})
        rec["all_bitwise_identical"] = bool(all(p.get("bitwise_identical")
                                                for p in rec["pairs"])) if rec["pairs"] else None
        per[key] = rec
        del runs
        gc.collect()
    res = {
        "within_process": per,
        "runtime_seconds": {
            "n": len(runtimes),
            "median": float(np.median(runtimes)),
            "min": float(np.min(runtimes)),
            "max": float(np.max(runtimes)),
        },
        "load_seconds": round(be.load_seconds, 2),
        "peak_rss_gb": round(common.peak_rss_gb(), 2),
        "peak_mps_driver_gb": (round(common.mps_peak_gb(), 2) if device == "mps" else None),
    }
    del be
    gc.collect()
    return res


def dump_fields(model: str, device: str, items: list[dict], out_dir: str) -> str:
    """One inference per image, fields written to disk for an ACROSS-process compare."""
    common.seed_everything()
    be = backends.get(model)(device=device)
    be.load()
    os.makedirs(out_dir, exist_ok=True)
    for item in items:
        common.seed_everything()
        out = be.infer(item["path"])
        stem = os.path.join(out_dir, f"{item['clip']}_f{item['frame']:06d}")
        np.save(stem + "_field.npy", field_of(out).astype(np.float32))
        np.save(stem + "_valid.npy", np.asarray(out["valid"]))
    del be
    gc.collect()
    return out_dir


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, choices=backends.keys())
    ap.add_argument("--device", default="mps")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--out-dir", default=os.path.join(common.OUTPUTS, "s1"))
    ap.add_argument("--dump-fields", default=None,
                    help="internal: write one run's fields here and exit "
                         "(used to build the across-process comparison)")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    items = s1_items()

    if args.dump_fields:
        dump_fields(args.model, args.device, items, args.dump_fields)
        return 0

    out_path = os.path.join(args.out_dir, f"{args.model}.json")
    common.refuse_clobber(out_path, args.overwrite)

    report = {
        "model": args.model,
        "checkpoint": common.MODEL_CHECKPOINT[args.model],
        "device": args.device,
        "precision": "float32 (no autocast; MPS supports only bf16/fp16 autocast)",
        "seed": common.SEED,
        "env": common.env_report(),
        "subset": [{"clip": i["clip"], "frame": i["frame"], "role": i["role"]} for i in items],
        "subset_rationale": (
            "A representative subset, not the 288-frame benchmark. Determinism and runtime "
            "do not need the full set, and FREEZE S1 explicitly does not ask for it."),
        "compared_field": ("canonical_range where the model emits one, otherwise the NATIVE "
                           "field — so the floor is in the units the S2 alignment policy "
                           "will actually work in"),
    }
    report.update(run_repeats(args.model, args.device, items, args.repeats))

    # --- across-process: two fresh processes, compared on disk ------------
    tmp_root = os.path.join(args.out_dir, "_proc", args.model)
    procs = []
    for k in (0, 1):
        d = os.path.join(tmp_root, f"run{k}")
        cmd = [sys.executable, "-m", "experiments.week4_mono.scripts.s1_determinism",
               "--model", args.model, "--device", args.device, "--dump-fields", d]
        env = dict(os.environ)
        env["PYTHONPATH"] = REPO_ROOT
        r = subprocess.run(cmd, cwd=REPO_ROOT, env=env, capture_output=True, text=True)
        if r.returncode != 0:
            report["across_process"] = {"error": r.stderr[-2000:]}
            break
        procs.append(d)
    if len(procs) == 2:
        ap_rec = {}
        for item in items:
            key = f"{item['clip']}/f{item['frame']:06d}"
            stem = f"{item['clip']}_f{item['frame']:06d}"
            a = np.load(os.path.join(procs[0], stem + "_field.npy")).astype(np.float64)
            b = np.load(os.path.join(procs[1], stem + "_field.npy")).astype(np.float64)
            va = np.load(os.path.join(procs[0], stem + "_valid.npy"))
            vb = np.load(os.path.join(procs[1], stem + "_valid.npy"))
            ap_rec[key] = {"valid_mask_identical": bool(np.array_equal(va, vb)),
                           **compare(a, b, va & vb)}
        report["across_process"] = ap_rec

    # --- the noise floor, stated once -------------------------------------
    def worst(section):
        vals = []
        for rec in (section or {}).values():
            if isinstance(rec, dict) and "pairs" in rec:
                vals += [p.get("p99_rel", np.nan) for p in rec["pairs"]]
            elif isinstance(rec, dict) and "p99_rel" in rec:
                vals.append(rec["p99_rel"])
        vals = [v for v in vals if v is not None and np.isfinite(v)]
        return float(max(vals)) if vals else float("nan")

    wp = worst(report.get("within_process"))
    xp = worst(report.get("across_process") if isinstance(
        report.get("across_process"), dict) and "error" not in report["across_process"] else None)
    report["noise_floor"] = {
        "within_process_p99_rel": wp,
        "across_process_p99_rel": xp,
        "floor_p99_rel": float(np.nanmax([wp, xp])),
        "meaning": ("Worst 99th-percentile RELATIVE difference between repeated runs on "
                    "identical input. No downstream relative delta below this may be read "
                    "as signal for this model."),
    }
    all_bitwise = all(r.get("all_bitwise_identical") for r in report["within_process"].values())
    xproc = report.get("across_process")
    if isinstance(xproc, dict) and "error" not in xproc:
        all_bitwise = all_bitwise and all(r.get("bitwise_identical") for r in xproc.values())
    report["bitwise_reproducible"] = bool(all_bitwise)
    report["stochasticity_source"] = (
        "none observed — bitwise reproducible on this device and precision"
        if all_bitwise else
        "non-bitwise: MPS kernel scheduling / non-deterministic reduction order. No dropout "
        "or sampling is active (all models are in eval() under no_grad).")

    common.write_json(out_path, report, overwrite=True)
    print(f"[S1] {args.model}: bitwise={report['bitwise_reproducible']} "
          f"floor_p99_rel={report['noise_floor']['floor_p99_rel']:.3e} "
          f"runtime_median={report['runtime_seconds']['median']:.2f}s "
          f"rss={report['peak_rss_gb']}GB")
    for k, r in report["within_process"].items():
        wpair = max((p.get("p99_rel", 0) or 0) for p in r["pairs"]) if r["pairs"] else 0
        print(f"      {k:26s} within p99_rel={wpair:.3e} mask_identical={r['valid_mask_identical']}")
    if isinstance(xproc, dict) and "error" not in xproc:
        for k, r in xproc.items():
            print(f"      {k:26s} across p99_rel={r.get('p99_rel', float('nan')):.3e} "
                  f"bitwise={r.get('bitwise_identical')}")
    print(f"  -> {os.path.relpath(out_path, REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
