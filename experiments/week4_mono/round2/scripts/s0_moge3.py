"""R2-1 MoGe-3 ViT-L S0 gate.

Step 0 = official `MoGeModel.from_pretrained(..., model_kwargs={"refiner": None})`
(an officially supported config override, v2.py:84-111) + `infer(refine_steps=0)`.
Step 3 is pending_cuda: the sparse refiner needs flex_gemm, which is Triton-powered,
and Triton publishes no macOS wheel.
"""
import sys, json, gc, warnings
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import s0_common as C

sys.path.insert(0, str(C.ROUND2 / "shims"))          # import-only flex_gemm stub
sys.path.insert(0, str(C.ROUND2 / "vendor" / "moge3"))

import numpy as np, torch
from PIL import Image
from moge.model.v3 import MoGeModel

DEV = "mps"
LONG_SIDE = 1280
REPO = "Ruicheng/moge-3-vitl"


def load(p, long_side=LONG_SIDE):
    im = Image.open(p).convert("RGB")
    w0, h0 = im.size
    s = long_side / max(w0, h0)
    w, h = round(w0 * s), round(h0 * s)
    im = im.resize((w, h), Image.LANCZOS)
    a = np.asarray(im, dtype=np.float32) / 255.0
    return torch.from_numpy(a).permute(2, 0, 1)[None], (w0, h0), (w, h)


def main():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = MoGeModel.from_pretrained(REPO, model_kwargs={"refiner": None})
    model = model.eval().to(DEV)

    # audit what the refiner-less instantiation actually dropped
    import glob
    ckpt_path = glob.glob(str(Path.home() / ".cache/huggingface/hub/models--Ruicheng--moge-3-vitl/snapshots/*/model.pt"))[0]
    sd = torch.load(ckpt_path, map_location="cpu", weights_only=True)["model"]
    have = set(model.state_dict().keys())
    ck = set(sd.keys())
    unloaded = sorted(ck - have)
    missing = sorted(have - ck)

    rec = {
        "model": "moge3_vitl", "repo": REPO, "impl_category": "B",
        "impl_category_notes": [
            "official from_pretrained model_kwargs override refiner=None "
            "(v2.py:84-111 documents model_kwargs as config override)",
            "import-only flex_gemm stub at round2/shims/ to satisfy the "
            "module-level import at v3.py:14 -> sparse_unet.py:14; every stub "
            "symbol raises on construction, so it cannot silently execute",
            "no changes to model math, resolution, checkpoint or operators",
        ],
        "step0_refiner_never_executes_evidence":
            "v3.py:121 raises if refine_steps>0 without a refiner; v3.py:168 "
            "`if refine_steps > 0:` guards the entire refinement loop, so at "
            "refine_steps=0 no refiner tensor is touched.",
        "step3_status": "pending_cuda",
        "step3_blocker": "moge/model/modules/sparse_unet.py:14 requires "
                         "flex_gemm.ops.NeighborCache; FlexGEMM is Triton-powered "
                         "(pyproject: triton>=3.2.0) and Triton has no macOS "
                         "distribution. No CUDA device on this machine.",
        "checkpoint_keys_total": len(ck),
        "checkpoint_keys_unloaded": len(unloaded),
        "checkpoint_keys_unloaded_all_refiner": all(k.startswith("refiner.") for k in unloaded),
        "checkpoint_keys_unloaded_sample": unloaded[:5],
        "model_keys_missing_from_checkpoint": missing,
        "n_parameters": int(sum(p.numel() for p in model.parameters())),
        "num_tokens_range": list(model.num_tokens_range),
        "env": C.env_block(DEV, torch), "images": {},
    }
    del sd; gc.collect()

    for tag, path in C.SANITY:
        img, src_wh, run_wh = load(path)
        torch.manual_seed(0)
        with C.Timer() as t:
            out = model.infer(img.to(DEV), resolution_level=9, refine_steps=0,
                              apply_mask=True, force_projection=True)
        pts = out["points"][0].float().cpu().numpy()
        dep = out["depth"][0].float().cpu().numpy()
        msk = out["mask"][0].cpu().numpy()
        K = out["intrinsics"][0].float().cpu().numpy()
        z = pts[..., 2]
        rng = np.linalg.norm(pts, axis=-1)
        fin = np.isfinite(dep) & np.isfinite(rng) & msk
        rec["images"][tag] = {
            "path": str(path), "source_wh": src_wh, "run_wh": run_wh,
            "runtime_s": round(t.dt, 3), "rss_gb": round(C.rss_gb(), 3),
            "out_shape_points": list(pts.shape), "out_shape_depth": list(dep.shape),
            "intrinsics_normalized": K.tolist(),
            "max_abs_depth_minus_pointz": float(np.max(np.abs(dep[fin] - z[fin]))),
            "max_abs_depth_minus_pointnorm": float(np.max(np.abs(dep[fin] - rng[fin]))),
            "stats_depth": C.stats("depth", np.where(fin, dep, np.nan)),
            "stats_range": C.stats("||points||", np.where(fin, rng, np.nan)),
            "median_range_over_z": float(np.median(rng[fin] / np.maximum(z[fin], 1e-6))),
            "mask_frac": float(msk.mean()),
            "coverage_finite_frac": float(fin.mean()),
        }
        print(tag, rec["images"][tag]["runtime_s"], "s",
              "cov", round(float(fin.mean()), 4),
              "med_depth", round(rec["images"][tag]["stats_depth"]["median"], 4), flush=True)
        del out, pts, dep; gc.collect()

    # refine_steps>0 must fail loudly, not silently degrade
    try:
        model.infer(load(C.SANITY[0][1])[0].to(DEV), refine_steps=3)
        rec["step3_guard_check"] = "UNEXPECTED: refine_steps=3 did not raise"
    except Exception as e:
        rec["step3_guard_check"] = f"{type(e).__name__}: {e}"

    C.write("moge3_vitl", rec)


main()
