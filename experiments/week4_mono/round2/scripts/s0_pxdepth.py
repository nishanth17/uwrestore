"""R2-4 PXDepth S0 gate — NATIVE path only.

Per protocol s10 the released repo's MoGe-2-assisted metric recovery is NOT
allowed for the primary Round-2 geometry comparison.  We therefore call
`PXDepth.forward()`, documented as "Run the network without metric-scale
alignment", which returns the native `depth_log1p_affine_invariant` + `mask`
and provably never touches MoGe-2 (`_reference_model` is only reached from
`infer()`).
"""
import sys, gc, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import s0_common as C

sys.path.insert(0, str(C.ROUND2 / "vendor" / "PXDepth"))
import numpy as np, torch
from PIL import Image
from pxdepth import PXDepth

DEV = "cpu"
# Released default policy, scripts/infer.py:26-32: --input-size 1022x770 with
# --resize-by-area default True => preserve source aspect ratio at that area.
AREA = 1022 * 770
CKPT = sorted(Path.home().glob(
    ".cache/huggingface/hub/models--yuanzhy29--PXDepth/snapshots/*/model.pt"))[0]


def area_resize(p, patch):
    im = Image.open(p).convert("RGB")
    w0, h0 = im.size
    ar = w0 / h0
    w = int(round((AREA * ar) ** 0.5 / patch)) * patch
    h = int(round((AREA / ar) ** 0.5 / patch)) * patch
    im2 = im.resize((w, h), Image.LANCZOS)
    a = np.asarray(im2, dtype=np.float32) / 255.0
    return torch.from_numpy(a).permute(2, 0, 1)[None], (w0, h0), (w, h)


def main():
    model = PXDepth.from_pretrained(str(CKPT), strict=True).to(DEV).eval()
    patch = int(model.patch_size)
    rec = {
        "model": "pxdepth", "repo": "yuanzhy29/PXDepth", "impl_category": "B",
        "impl_category_notes": [
            "device placement mps; model math, checkpoint (strict=True) and "
            "operators unchanged",
            "the released scripts/infer.py is BROKEN as published: line 74 does "
            "`from pxdepth.inference import parse_size, resize_image, resize_map` "
            "but no module `pxdepth.inference` exists and none of those three "
            "names is defined anywhere in the repo.  The preprocessing helper is "
            "therefore reimplemented here to the repo's OWN documented policy "
            "(scripts/infer.py:26-32: --input-size 1022x770, --resize-by-area "
            "default True => preserve source aspect ratio at that pixel area), "
            "rounded to the encoder patch size required by PXDepth.py:210.",
            "NATIVE path only: forward(), never infer(); MoGe-2 is never loaded",
        ],
        "native_representation": "depth_log1p_affine_invariant",
        "native_gauge": "affine in log1p-depth: depth = expm1(a*d_native + b); "
                        "2-DOF, scale AND shift unknown",
        "native_gauge_evidence":
            "PXDepth.py:226 returns {'depth_log1p_affine_invariant', 'mask'}; "
            "model/inference.py:189 solves (a,b) via solve_depth_affine and :195 "
            "`depth = torch.expm1(scale*pred + shift)`.",
        "native_underlying_quantity": "z-depth (projective), not ray range",
        "native_underlying_quantity_evidence":
            "scripts/infer.py:121 back-projects the recovered depth with "
            "utils3d.pt.depth_map_to_point_map(depth, intrinsics), which "
            "multiplies unnormalised K^-1 rays by the scalar.",
        "native_intrinsics_or_fov": None,
        "native_point_geometry_independent_of_moge2": False,
        "native_point_geometry_note":
            "no point map is produced by the network; scripts/infer.py obtains "
            "intrinsics either from --fov-x or from the MoGe-2 reference.",
        "moge2_role": "solves only the two affine parameters (a,b) in infer(); "
                      "forward() is unaffected. Recorded as an OPTIONAL "
                      "deployment-style diagnostic, never a primary result.",
        "license_code": "UNDECLARED - no LICENSE file in the released repo",
        "license_weights": "UNDECLARED - the HF model card README.md is 0 bytes",
        "license_disposition": "research-only (undeclared; not invented)",
        "alignment_family_required": "affine_log1p_depth (NEW - not one of the "
                                     "four frozen Round-1 families)",
        "patch_size": patch,
        "input_area_policy": {"area_px": AREA, "aspect": "source-preserving",
                              "rounded_to": patch},
        "n_parameters": int(sum(p.numel() for p in model.parameters())),
        "env": C.env_block(DEV, torch), "images": {},
    }

    for tag, path in C.SANITY:
        img, src_wh, run_wh = area_resize(path, patch)
        torch.manual_seed(0)
        with torch.no_grad(), C.Timer() as t:
            out = model.forward(img.to(DEV), use_fp32=True)
        d = out["depth_log1p_affine_invariant"][0].float().cpu().numpy()
        m = out["mask"][0].float().cpu().numpy()
        fin = np.isfinite(d)
        rec["images"][tag] = {
            "path": str(path), "source_wh": src_wh, "run_wh": run_wh,
            "source_aspect": round(src_wh[0] / src_wh[1], 6),
            "run_aspect": round(run_wh[0] / run_wh[1], 6),
            "runtime_s": round(t.dt, 3), "rss_gb": round(C.rss_gb(), 3),
            "out_shape": list(d.shape),
            "stats_native": C.stats("depth_log1p_affine_invariant", d),
            "stats_mask_prob": C.stats("mask", m),
            "mask_gt_0p5_frac": float((m > 0.5).mean()),
            "coverage_finite_frac": float(fin.mean()),
            "moge2_loaded": "MoGeModel" in sys.modules or any(
                "moge" in k for k in sys.modules),
        }
        print(tag, rec["images"][tag]["runtime_s"], "s", run_wh,
              "native[min,max]", round(rec["images"][tag]["stats_native"]["min"], 4),
              round(rec["images"][tag]["stats_native"]["max"], 4),
              "moge2_loaded", rec["images"][tag]["moge2_loaded"], flush=True)
        del out, d, m; gc.collect()

    C.write("pxdepth", rec)


main()
