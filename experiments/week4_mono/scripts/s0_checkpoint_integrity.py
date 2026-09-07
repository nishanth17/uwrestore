"""S0 integrity check — MetricAnything Student-PointMap vs stock MoGe-2 ViT-L.

EXPLORATORY. Runs in `experiments/week4_mono/.venv-moge`.

WHY THIS IS MANDATORY (FREEZE §C5). `metricanything_student_pointmap` is
documented as a MoGe-2 ViT-L fine-tune, and Week 4A treats that pair as
experimental variable V5. The whole comparison rests on the two checkpoints
sharing an architecture and a representation. This project has already been
bitten once by a checkpoint that was not what its release said it was — the
Week-3 Water-VGGT checkpoint-integrity finding — so the claim is checked at the
TENSOR level rather than taken from a model card.

The check is deliberately not "are they different". Of course they are; it is a
fine-tune. What it establishes is:

    same `model_config`?              -> same architecture, so V5 is controlled
    same parameter keys and shapes?   -> nothing was added, removed or resized
    HOW different is each tensor?     -> is this a fine-tune or a different model
    any tensor bitwise identical?     -> which parts were effectively frozen

An identical key set with a plausible fine-tune-sized perturbation supports the
documented lineage. A differing key set, a differing config, or a checkpoint
that is byte-identical to its base would each falsify a premise of V5, and the
freeze requires that to be recorded rather than discovered later as a confusing
S3 result.

    experiments/week4_mono/.venv-moge/bin/python \\
        -m experiments.week4_mono.scripts.s0_checkpoint_integrity
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week4_mono import common  # noqa: E402

BASE = ("Ruicheng/moge-2-vitl", "model.pt")
FINE = ("yjh001/metricanything_student_pointmap", "student_pointmap.pt")


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    import torch
    from huggingface_hub import hf_hub_download

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(common.OUTPUTS, "s0",
                                                  "checkpoint_integrity.json"))
    ap.add_argument("--top", type=int, default=15,
                    help="how many most-changed tensors to list")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    common.refuse_clobber(args.out, args.overwrite)

    paths = {}
    ckpts = {}
    for tag, (repo, fname) in (("base", BASE), ("fine", FINE)):
        p = hf_hub_download(repo_id=repo, filename=fname)
        paths[tag] = p
        ckpts[tag] = torch.load(p, map_location="cpu", weights_only=True)

    report = {
        "_comment": ("Tensor-level comparison of the MetricAnything Student-PointMap "
                     "checkpoint against stock MoGe-2 ViT-L. Mandated by "
                     "MONO_DEPTH_FREEZE.md C5 because Week 4A's V5 comparison assumes "
                     "the two share an architecture and a representation."),
        "base": {"repo": BASE[0], "file": BASE[1],
                 "bytes": os.path.getsize(paths["base"]), "sha256": sha256(paths["base"])},
        "fine": {"repo": FINE[0], "file": FINE[1],
                 "bytes": os.path.getsize(paths["fine"]), "sha256": sha256(paths["fine"])},
    }
    report["files_identical"] = report["base"]["sha256"] == report["fine"]["sha256"]

    cb, cf = ckpts["base"].get("model_config"), ckpts["fine"].get("model_config")
    report["model_config_base"] = cb
    report["model_config_fine"] = cf
    report["model_config_identical"] = (cb == cf)
    if cb != cf:
        keys = set(cb or {}) | set(cf or {})
        report["model_config_differences"] = {
            k: {"base": (cb or {}).get(k), "fine": (cf or {}).get(k)}
            for k in sorted(keys) if (cb or {}).get(k) != (cf or {}).get(k)}

    sb, sf = ckpts["base"]["model"], ckpts["fine"]["model"]
    kb, kf = set(sb), set(sf)
    report["n_params_base"] = len(kb)
    report["n_params_fine"] = len(kf)
    report["keys_only_in_base"] = sorted(kb - kf)
    report["keys_only_in_fine"] = sorted(kf - kb)
    report["key_sets_identical"] = (kb == kf)

    shared = sorted(kb & kf)
    shape_mismatch, rows = [], []
    n_identical = 0
    total_base_sq = 0.0
    total_diff_sq = 0.0
    for k in shared:
        a, b = sb[k], sf[k]
        if tuple(a.shape) != tuple(b.shape):
            shape_mismatch.append({"key": k, "base": list(a.shape), "fine": list(b.shape)})
            continue
        a = a.detach().float().numpy().ravel()
        b = b.detach().float().numpy().ravel()
        d = b - a
        same = bool(np.array_equal(a, b))
        n_identical += int(same)
        na = float(np.linalg.norm(a))
        nd = float(np.linalg.norm(d))
        total_base_sq += na * na
        total_diff_sq += nd * nd
        rows.append({
            "key": k, "numel": int(a.size), "bitwise_identical": same,
            "max_abs_diff": float(np.abs(d).max()) if d.size else 0.0,
            # Relative change in the L2 sense. A fine-tune moves most tensors a
            # few percent; a different model moves them of order 1.
            "rel_l2": float(nd / na) if na > 0 else float("nan"),
        })
    report["shape_mismatches"] = shape_mismatch
    report["n_tensors_compared"] = len(rows)
    report["n_tensors_bitwise_identical"] = n_identical
    report["fraction_bitwise_identical"] = (n_identical / len(rows)) if rows else float("nan")
    report["global_rel_l2"] = (float(np.sqrt(total_diff_sq / total_base_sq))
                               if total_base_sq > 0 else float("nan"))
    rows.sort(key=lambda r: (-(r["rel_l2"] if np.isfinite(r["rel_l2"]) else -1)))
    report["most_changed_tensors"] = rows[:args.top]
    report["least_changed_tensors"] = [r for r in rows[::-1]][:args.top]

    # Group by top-level module so "what was fine-tuned" is legible.
    groups: dict[str, list[float]] = {}
    for r in rows:
        g = r["key"].split(".")[0]
        if np.isfinite(r["rel_l2"]):
            groups.setdefault(g, []).append(r["rel_l2"])
    report["rel_l2_by_module"] = {
        g: {"n": len(v), "median": float(np.median(v)),
            "min": float(np.min(v)), "max": float(np.max(v))}
        for g, v in sorted(groups.items())}

    ok = (report["key_sets_identical"] and report["model_config_identical"]
          and not shape_mismatch and not report["files_identical"])
    report["verdict"] = "LINEAGE_CONSISTENT" if ok else "LINEAGE_QUESTIONED"
    report["verdict_meaning"] = (
        "LINEAGE_CONSISTENT: identical model_config, identical parameter key set, no shape "
        "mismatches, and the files are not the same file — everything V5 needs in order to "
        "be a controlled architecture/representation comparison. It does NOT establish "
        "which component of the fine-tuning treatment caused any downstream difference; "
        "FREEZE C5 keeps data, objectives, supervision and camera diversity confounded.")

    common.write_json(args.out, report, overwrite=True)
    print(f"[S0-integrity] verdict={report['verdict']}")
    print(f"  model_config identical : {report['model_config_identical']}")
    print(f"  key sets identical     : {report['key_sets_identical']} "
          f"({report['n_params_base']} vs {report['n_params_fine']})")
    print(f"  shape mismatches       : {len(shape_mismatch)}")
    print(f"  bitwise-identical      : {n_identical}/{len(rows)}")
    print(f"  global relative L2     : {report['global_rel_l2']:.4f}")
    for g, v in report["rel_l2_by_module"].items():
        print(f"    {g:22s} n={v['n']:4d} median_rel_l2={v['median']:.4f} "
              f"max={v['max']:.4f}")
    print(f"  -> {os.path.relpath(args.out, REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
