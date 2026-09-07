"""Do MDA's mixture quantities track its actual disagreement with the reference?

Task §12 persists component depths, mixing probabilities, chosen component,
entropy and the top-1/top-2 margin, and forbids calling them "calibrated
confidence". This script asks the weaker, answerable question instead: on the
288 frozen frames, do those quantities COVARY at all with the frame's measured
disagreement (S3 M-1 abs-rel) against the provisional Week-3 hypothesis?

Spearman rank correlation, so no linearity is assumed. A usable failure
indicator would show a consistently POSITIVE rho for entropy (more ambiguity ->
more disagreement) and a consistently NEGATIVE rho for the top-1/top-2 margin.

PRE-C2. The "error" here is disagreement with a provisional multi-view
hypothesis, never objective monocular error.

    experiments/week4_mono/.venv-eval/bin/python \\
        -m experiments.week4_mono.round2.scripts.r2_mda_ambiguity --overwrite
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

from experiments.week4_mono.round1 import common  # noqa: E402

ARM = "mda_mog_sky_l2"
QUANTITIES = {
    "entropy_median": "mixing-weight entropy (max = ln n_components)",
    "top1_prob_median": "largest mixing weight",
    "top1_minus_top2_median": "top-1 minus top-2 mixing weight",
    "chosen_candidate_midpoint_frac": "fraction of pixels whose winning candidate "
                                      "was a pairwise MIDPOINT, not an expert mean",
    "sky_mask_frac": "fraction of pixels the released sky mask pushed to 2x max depth",
}


def spearman(a, b) -> float:
    ra = np.argsort(np.argsort(np.asarray(a, dtype=float)))
    rb = np.argsort(np.argsort(np.asarray(b, dtype=float)))
    return float(np.corrcoef(ra, rb)[0, 1])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--s3", default=os.path.join(common.W4, "round2", "outputs",
                                                 "r2_s3", "r2_s3_raw.json"))
    ap.add_argument("--root", default=os.path.join(common.OUTPUTS, "predictions"))
    ap.add_argument("--out", default=os.path.join(common.W4, "round2", "outputs",
                                                  "r2_mda_ambiguity.json"))
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    with open(args.s3) as fh:
        clips = json.load(fh)["arms"][ARM]["clips"]

    per_clip, pool = {}, {"err": []}
    pool.update({q: [] for q in QUANTITIES})
    for clip, e in clips.items():
        if e.get("status") != "ok":
            continue
        pf = {int(f["frame"]): f for f in e["per_frame"] if f.get("status") == "ok"}
        with open(os.path.join(args.root, ARM, clip, "clip.json")) as fh:
            meta = {int(f["frame_index"]): f for f in json.load(fh)["frames"]}
        idx = sorted(set(pf) & set(meta))
        err = [pf[i]["m1_overall_abs_rel_median"] for i in idx]
        pool["err"] += err
        row = {"n_frames": len(idx)}
        for q in QUANTITIES:
            v = [meta[i][q] for i in idx]
            pool[q] += v
            row[q] = {"spearman_vs_m1": spearman(v, err),
                      "median": float(np.median(v)),
                      "min": float(np.min(v)), "max": float(np.max(v))}
        per_clip[clip] = row

    pooled = {q: {"spearman_vs_m1": spearman(pool[q], pool["err"]),
                  "median": float(np.median(pool[q])),
                  "min": float(np.min(pool[q])), "max": float(np.max(pool[q]))}
              for q in QUANTITIES}

    # The finding, stated as the sign test it is: an indicator that worked would
    # keep the SAME sign on every clip. Count how many clips agree with pooled.
    consistency = {}
    for q in QUANTITIES:
        signs = [np.sign(per_clip[c][q]["spearman_vs_m1"]) for c in per_clip]
        consistency[q] = {
            "pooled_sign": float(np.sign(pooled[q]["spearman_vs_m1"])),
            "n_clips_agreeing_with_pooled_sign":
                int(sum(1 for s in signs if s == np.sign(pooled[q]["spearman_vs_m1"]))),
            "n_clips": len(signs),
            "per_clip_spearman": {c: per_clip[c][q]["spearman_vs_m1"] for c in per_clip},
        }

    n_comp, ent_max = None, None
    for clip in clips:
        p = os.path.join(args.root, ARM, clip, "clip.json")
        if os.path.exists(p):
            with open(p) as fh:
                f0 = json.load(fh)["frames"][0]
            n_comp, ent_max = f0.get("n_mixture_components"), f0.get("entropy_max_possible")
            break

    payload = {
        "stage": "R2 — MDA mixture-ambiguity diagnostic",
        "arm": ARM,
        "n_frames": len(pool["err"]),
        "n_mixture_components": n_comp,
        "entropy_max_possible": ent_max,
        "quantities": QUANTITIES,
        "what_would_count": ("a usable failure indicator keeps ONE sign across clips: "
                             "entropy positively correlated with disagreement, margin "
                             "negatively correlated. A sign that flips clip to clip is "
                             "not an indicator, whatever its pooled value."),
        "reference_status": ("PROVISIONAL MULTI-VIEW HYPOTHESIS. The 'error' correlated "
                             "against is disagreement, not objective monocular error."),
        "not_calibrated_confidence": ("Task §12. Nothing here is called calibrated "
                                      "confidence, and this diagnostic does not test "
                                      "calibration; it tests covariation only."),
        "per_clip": per_clip,
        "pooled": pooled,
        "sign_consistency": consistency,
    }
    common.write_json(args.out, payload, overwrite=args.overwrite)
    print(f"[R2-MDA] n={payload['n_frames']} components={n_comp} "
          f"entropy_max={ent_max:.4f}")
    for q in QUANTITIES:
        c = consistency[q]
        print(f"  {q:34s} pooled_rho={pooled[q]['spearman_vs_m1']:+.3f} "
              f"same-sign clips {c['n_clips_agreeing_with_pooled_sign']}/{c['n_clips']} "
              f"median={pooled[q]['median']:.3f}")
    print(f"[R2-MDA] -> {os.path.relpath(args.out, REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
