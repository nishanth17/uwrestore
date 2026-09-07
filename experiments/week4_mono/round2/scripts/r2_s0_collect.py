"""Collect the per-model S0 smoke JSONs into R2_S0_results.json.

Also carries the two `pending_checkpoint` challengers, which have no smoke JSON
because their required official weights cannot be obtained without
authenticating to a gated service -- which the execution policy forbids.
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import s0_common as C

BLOCKED = {
    "hyden_mogev2_metric": {
        "model": "hyden_mogev2_metric", "challenger": "R2-2",
        "status": "pending_checkpoint",
        "repo": "facebook/hyden-mogev2-metric-point",
        "required_file": "hyden_mogev2_metric_point_vitl_fp32_f1066593896.pth",
        "repo_gated": "manual",
        "blocker": "GatedRepoError 401: 'Cannot access gated repo ... Access to "
                   "model facebook/hyden-mogev2-metric-point is restricted. You "
                   "must have access to it and be authenticated to access it.' "
                   "The repository requires a manually approved access request "
                   "plus an authenticated HF token; no token exists on this "
                   "machine and the execution policy forbids provisioning or "
                   "authenticating to a service.",
        "reference_implementation_present": "vendor/metadepth (official MetaDepth "
                                            "checkout, code only)",
        "environment_ready": True,
        "venv": "round2/.venv-hyden_mogev2_metric",
        "stopped_at": "S0 gate, checkpoint acquisition -- before any inference",
        "to_resume": [
            "obtain access to facebook/hyden-mogev2-metric-point and export HF_TOKEN",
            "hf download facebook/hyden-mogev2-metric-point "
            "hyden_mogev2_metric_point_vitl_fp32_f1066593896.pth",
            "run the s8 bounded resolution ablation (official/default config vs "
            "highest practical config preserving the frozen aspect and FOV) on a "
            "small representative subset BEFORE full S3, then freeze one config",
        ],
        "artifacts_needed": "one native metric XYZ point map per frame for the "
                            "288 frozen frames, plus the resolution-ablation subset",
    },
    "pointdit_l512": {
        "model": "pointdit_l512", "challenger": "R2-5",
        "status": "pending_checkpoint",
        "repo": "PointDiT-L 512 (local checkpoint present)",
        "local_checkpoint": "vendor/pointdit/pretrained/"
                            "pointditl-512-mixdata-nodinov3-240c1a4f.pth",
        "blocker": "The released PointDiT checkpoint is published WITHOUT the "
                   "DINOv3 image encoder -- the filename says so ('nodinov3') and "
                   "README:59-62 states 'The DINOv3 weights are gated and cannot "
                   "be redistributed, so they are not part of the released "
                   "checkpoints.' model.py:270 requires "
                   "feature_embedding_type='dinov3_vitb16' and :305-317 loads "
                   "pretrained/dinov3/dinov3_{vit_type}_pretrain_lvd1689m-{sha}.pth "
                   "from a third_party/dinov3 checkout. Fetching those weights "
                   "returns GatedRepoError 401 for "
                   "facebook/dinov3-vitb16-pretrain-lvd1689m (gated: manual).",
        "environment_ready": True,
        "venv": "round2/.venv-pointdit_l512",
        "stopped_at": "S0 gate, encoder-weight acquisition -- before any inference",
        "to_resume": [
            "obtain access to facebook/dinov3-vitb16-pretrain-lvd1689m and export HF_TOKEN",
            "clone third_party/dinov3 and place the weights in pretrained/dinov3/",
            "verify the single-step all-zero-initialisation path in the official "
            "code, run it as PRIMARY, then the bounded refinement ablation "
            "(one-step all-zero vs release-recommended multi-step) on a small subset",
        ],
        "artifacts_needed": "native point map per frame for the 288 frozen frames "
                            "at the single-step all-zero setting, plus the "
                            "refinement-ablation subset (M-3, M-4, thin structure, "
                            "runtime, determinism)",
        "note": "Not substituted with an unofficial reimplementation and not run "
                "with a different feature encoder; either would break "
                "reference-implementation integrity.",
    },
}

CHALLENGER = {"moge3_vitl": "R2-1", "surge_large": "R2-3",
              "pxdepth": "R2-4", "mda_mog_sky_l2": "R2-6"}


def main():
    out = {"stage": "R2-S0", "models": {}}
    for name, cid in CHALLENGER.items():
        p = C.ROUND2 / "s0_agent" / name / "s0_smoke.json"
        if p.exists():
            d = json.loads(p.read_text())
            d["challenger"] = cid
            d.setdefault("status", "ready")
            out["models"][name] = d
        else:
            out["models"][name] = {"model": name, "challenger": cid,
                                   "status": "MISSING smoke json"}
    out["models"].update(BLOCKED)
    dst = C.ROUND2 / "R2_S0_results.json"
    dst.write_text(json.dumps(out, indent=2, sort_keys=True, default=str))
    print("wrote", dst)
    for k, v in out["models"].items():
        print(f"  {v.get('challenger','?'):5s} {k:22s} {v.get('status')}")


main()
