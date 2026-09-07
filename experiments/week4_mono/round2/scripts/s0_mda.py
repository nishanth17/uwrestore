"""R2-6 MDA (mda_mog_sky_l2 / DA3_MOG_Sky_LogL2) S0 gate.

Official mono path: demo.py:304 treats a single image file as monocular
(one-view) inference, building views with prepare_views() and calling
DA3Wrapper.inference().  We call exactly those official helpers with a
one-element file list.

STRICT N=1 is verified empirically, not assumed:
  N1a  the batched tensor handed to the network has view dimension L == 1
  N1b  the same image run twice in a fresh call is bitwise identical
  N1c  running A alone vs. A inside a 2-view list CHANGES A's output, which
       proves cross-view coupling exists and therefore that L==1 is load-bearing
  N1d  A, then B, then A again -> A's two results identical (no cached state)
"""
import os, sys, gc, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import s0_common as C

MDA = C.ROUND2 / "vendor" / "MDA"
os.chdir(MDA)                      # model_choice resolves ckpt/config relatively
sys.path.insert(0, str(MDA))

import numpy as np, torch
import add_ckpt_path  # noqa: F401  side-effect: extends sys.path
from src.testing.utils.model_choice import choose_model
from src.testing.run_inference_video import prepare_views

DEV = torch.device(os.environ.get("MDA_DEVICE", "mps"))
SIZE = 512          # demo.py DemoConfig.size default (long edge)
MODEL_NAME = "mda_mog_sky_l2"


def to_np(x):
    return x.detach().float().cpu().numpy()


def run_one(model, loaded, paths):
    views = prepare_views([str(p) for p in paths], SIZE, loaded.patch_size, loaded.img_norm)
    with torch.no_grad():
        preds = model.inference(views, DEV, is_mog=True, use_sky_mask=True,
                                crop_center_112=False, cam_inp=False,
                                gt_cam_output=False, output_normalize=False)
    return preds


def main():
    loaded = choose_model(MODEL_NAME)
    model = loaded.model.to(DEV).eval()
    rec = {
        "model": "mda_mog_sky_l2", "repo": "sy000/MDA",
        "checkpoint": loaded.checkpoint_path,
        "config": "src/depth_anything_3/configs/da3-giant-cam-mog-sky.yaml",
        "impl_category": "B",
        "impl_category_notes": [
            f"device placement {DEV} (model_choice.py hardcodes cuda-or-cpu)",
            "official helpers choose_model / prepare_views / DA3Wrapper.inference "
            "called with a one-element file list, exactly the demo.py:304 mono path",
            "no changes to model math, resolution (512 long edge = demo.py default), "
            "checkpoint or operators",
        ],
        "license_code": "Apache-2.0 (vendor/MDA/LICENSE)",
        "native_representation": "z-depth (projective), multi-hypothesis mixture",
        "native_representation_evidence":
            "utils/geometry.py:275 unproject(coordinates, z, intrinsics) returns "
            "ray_directions * z with UNNORMALISED K^-1 rays (:291); the parameter "
            "is named z. Identical to DA3, whose convention Round-2 Part A "
            "established from the same code.",
        "mixture_semantics":
            "model/mog_inference.py _prepare_inputs: preds['depth'] is a list of N "
            "component depth maps [B,L,H,W]; preds['depth_conf'] matching; "
            "preds['mog_weight'] is [B,L,H,W,N] LOG mixing weights. "
            "find_gmm_mode_gpu_chunk selects the mode -> preds['indices'], "
            "preds['depth_inference'].",
        "mixture_caveat":
            "These are mixture weights of a trained NLL objective. They are NOT "
            "called calibrated confidence pre-C2; they are exploratory "
            "failure-signalling evidence only.",
        "size_long_edge": SIZE, "patch_size": loaded.patch_size,
        "env": C.env_block(str(DEV), torch), "images": {}, "n1_checks": {},
    }

    ordinary = C.SANITY[0][1]
    difficult = C.SANITY[1][1]

    for tag, path in C.SANITY:
        with C.Timer() as t:
            out = run_one(model, loaded, [path])
        raw = out["raw_preds"]
        d_inf = to_np(out["depth"])                  # [B, L, H, W] chosen-mode depth
        img = out["views"]["img"]
        comps = [to_np(x) for x in raw["depth"]]     # N component depth maps
        logw = to_np(raw["mog_weight"])              # [B, L, H, W, N] log weights
        idx = to_np(raw["indices"]) if "indices" in raw else None
        sky = to_np(out["sky_mask"]) if out.get("sky_mask") is not None else None

        entry = {
            "path": str(path), "runtime_s": round(t.dt, 3),
            "rss_gb": round(C.rss_gb(), 3),
            "returned_keys": sorted(k for k in out),
            "raw_pred_keys": sorted(k for k in raw),
            "depth_shape": list(d_inf.shape),
            "view_tensor_shape": list(img.shape),
            "view_dim_L": int(img.shape[1]),
            "n_mixture_components": len(comps),
            "mog_weight_shape": list(logw.shape),
            "stats_depth_mode": C.stats("depth(mode)", d_inf),
            "component_medians": [round(float(np.median(c)), 4) for c in comps],
            "component_separation_median_maxminusmin": float(np.median(
                np.max(np.stack(comps, -1), -1) - np.min(np.stack(comps, -1), -1))),
        }
        w = np.exp(logw - logw.max(axis=-1, keepdims=True))
        w = w / w.sum(axis=-1, keepdims=True)
        ws = np.sort(w, axis=-1)
        ent = -(w * np.log(np.clip(w, 1e-12, None))).sum(-1)
        entry.update(
            top1_prob_median=float(np.median(ws[..., -1])),
            top1_minus_top2_median=float(np.median(ws[..., -1] - ws[..., -2])),
            entropy_median=float(np.median(ent)),
            entropy_max_possible=float(np.log(w.shape[-1])),
        )
        if idx is not None:
            # `indices` from find_gmm_mode_gpu_chunk indexes the CANDIDATE set,
            # not the expert set.  mog_inference.py:109-138 builds candidates as
            # the N expert means followed by the confidence-weighted pairwise
            # midpoints (capped just over 8), so for N experts there are
            # N + min(C(N,2), 9) candidates: with N=4 that is 4 means (bins 0-3)
            # then midpoints (0,1),(0,2),(0,3),(1,2),(1,3),(2,3) (bins 4-9).
            # _RunningBest (:141-163) then keeps the lowest-NLL candidate per
            # pixel, and LBFGS moves the returned DEPTH away from that
            # initialisation, so the index names which initialisation won -- it
            # is NOT a hard selection of one mixture component.
            n = len(comps)
            pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
            hist = np.bincount(idx.astype(np.int64).ravel(), minlength=n).tolist()
            entry["chosen_candidate_hist"] = hist
            entry["chosen_candidate_labels"] = (
                [f"mean[{i}]" for i in range(n)]
                + [f"mid[{i},{j}]" for i, j in pairs[: max(0, len(hist) - n)]]
            )
            tot = float(sum(hist)) or 1.0
            entry["chosen_candidate_midpoint_frac"] = float(sum(hist[n:])) / tot
            entry["chosen_candidate_note"] = (
                "index is into the candidate set (expert means then pairwise "
                "midpoints), not the mixture components; the reported depth is "
                "LBFGS-refined from the winning candidate."
            )
        if sky is not None:
            entry["sky_mask_frac"] = float(sky.mean())
            entry["sky_note"] = ("use_sky_mask=True is the demo.py default; sky "
                                 "pixels are pushed to 2x the max valid depth "
                                 "(da3_wrapper.py:275-296). Underwater there is "
                                 "no sky, so a non-trivial fraction here is "
                                 "itself a finding, not a nuisance.")
        rec["images"][tag] = entry
        print(tag, entry["runtime_s"], "s L=", entry["view_dim_L"],
              "N=", entry["n_mixture_components"],
              "top1", round(entry["top1_prob_median"], 4),
              "sky", round(entry.get("sky_mask_frac", float("nan")), 4), flush=True)
        del out, raw, comps, logw; gc.collect()

    # ---- strict N=1 checks -------------------------------------------------
    a1 = to_np(run_one(model, loaded, [ordinary])["depth"])
    a2 = to_np(run_one(model, loaded, [ordinary])["depth"])
    b1 = to_np(run_one(model, loaded, [difficult])["depth"])
    a3 = to_np(run_one(model, loaded, [ordinary])["depth"])
    pair = run_one(model, loaded, [ordinary, difficult])
    a_in_pair = to_np(pair["depth"])[:, 0]

    rec["n1_checks"] = {
        "N1a_view_dim_L": rec["images"]["ordinary"].get("view_dim_L"),
        "N1b_repeat_max_abs_diff": float(np.max(np.abs(a1 - a2))),
        "N1b_bitwise_identical": bool(np.array_equal(a1, a2)),
        "N1c_pair_shape": list(to_np(pair["depth"]).shape),
        "N1c_A_alone_vs_A_in_pair_max_abs_diff":
            float(np.max(np.abs(a1[:, 0] - a_in_pair))) if a_in_pair.shape == a1[:, 0].shape else None,
        "N1c_note": "a non-zero value proves cross-view attention is active, so "
                    "running one image at a time is what makes N=1 real",
        "N1d_A_after_B_identical_to_A": bool(np.array_equal(a1, a3)),
        "N1d_max_abs_diff": float(np.max(np.abs(a1 - a3))),
    }
    print("N1:", json.dumps(rec["n1_checks"], indent=1), flush=True)
    C.write("mda_mog_sky_l2", rec)


main()
