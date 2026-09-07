"""Round 2 §18 — the TRIGGERED THIN-STRUCTURE TEST at the wreck_07 crane lattice.

MANDATORY in Round 2 because Round 1 found one arm inventing structure there:
`da3mono_large` filled the open lattice with a solid opaque surface on
`wreck_07` f000109, so water seen THROUGH the lattice was restored as though it
sat at the lattice's range (`results/S6_RESTORATION.md`). This is a small
targeted evaluation of that known region, NOT a new benchmark, and nothing it
produces enters the primary S3 ranking.

PRE-C2. The Week-3 range product is a provisional multi-view hypothesis and is
scored here as one arm among the others, never as the answer. What this test
does rest on is an ordinal fact taken from the RGB frames and confirmed by eye
(`r2_thin_annotate`): a Tier-A opening is photometrically identical to the open
water column beside the lattice, so it is FAR, and the member in front of it is
NEAR. Veiling is monotone in range; that is the whole of the assumption.

THE DECOMPOSITION. Three anchors per frame, all at full source resolution:

    r_sea    median range over LOCAL SEA -- open water within 60 px of the holes
    r_open   median range over one Tier-A opening core
    r_mem    median range over that opening's 3..9 px structure ring

and three logs, which separate the two failure modes the task names:

    fill    = log(r_sea / r_open)    hole pulled toward the near member
                                     -> 0 is correct; large is a FALSE SURFACE
    member  = log(r_sea / r_mem)     member placed nearer than the sea
                                     -> large is correct; ~0 is a MISSING MEMBER
    gap     = log(r_open / r_mem)    = member - fill; ordinal separation

`gap > 0` is ordinal correctness across the opening. `fill / member` is the
fraction of the way the hole has been dragged onto the member, which is what
"filled with a solid surface" means numerically. Reporting only `gap` would
confuse a model that erases the member with one that fills the hole: both
collapse `gap`, for opposite reasons.

EDGE DISPLACEMENT. `gap` is recomputed with the opening core eroded by 2, 5 and
8 px. A model whose depth edges sit where the image edges sit gains little from
eroding further in; one whose edges are displaced or smeared gains a lot.

RESOLUTION. Members here are 5-40 source pixels wide, so this stage evaluates
on the source grid itself (`downsample=1`, 1280x720 samples) rather than the
S3 stride of 4, which would sample straight past them. The ALIGNMENT is still
the frozen S2 clip-level fit, refitted exactly as S3 fits it (stride 4, all 48
frames, seed 0) and then APPLIED at full resolution -- the grid changes, the
gauge does not.

    experiments/week4_mono/.venv-eval/bin/python \\
        -m experiments.week4_mono.round2.scripts.r2_thin_structure --overwrite
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import cv2
import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                         "..", "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week4_mono.round1 import (armio, common, evalgrid,  # noqa: E402
                                    monoio, policy)
from experiments.week4_mono.round2.scripts import r2_thin_annotate as ANN  # noqa: E402
from experiments.week4_mono.round1.scripts import s2_ambiguity as S2  # noqa: E402

CLIP = ANN.CLIP
EROSIONS = (2, 5, 8)
SAMPLES_PER_FRAME = 4000          # identical to S3's pooling budget


def provisional_entry(model: str, root: str) -> dict | None:
    """A policy entry for an arm whose S2 measurement has not finished yet.

    Only the two things S2 does NOT decide are filled in: the transform family
    follows from the native representation (`PRIMARY_FAMILY`) and the z-vs-range
    convention from the model's own source code (`CONVENTION_FROM_SOURCE`).
    S2 measures the residual; it does not choose either of these. The entry is
    marked provisional and the marking is carried into the output, so a number
    produced under it can never be mistaken for one under the frozen policy.
    """
    kind = monoio.MonoReader(root, model, CLIP).native_kind
    fam = S2.PRIMARY_FAMILY.get(kind)
    conv = S2.CONVENTION_FROM_SOURCE.get(model)
    if fam is None or conv is None:
        return None
    return {"native_kind": kind, "family": fam, "convention": conv[0],
            "convention_source": "SOURCE CODE", "convention_evidence": conv[1],
            "scope": "clip", "provisional_pending_s2": True,
            "provisional_note": (
                "S2 has not finished for this model; family and convention come "
                "from the representation and the source code, which is where S2 "
                "would take them from in any case.")}


def clip_fit(arm_key: str, pol: policy.Policy, root: str):
    """The frozen S2 clip-level fit, obtained the way S3 obtains it."""
    a = armio.Arm(arm_key, CLIP, root)
    rng = np.random.default_rng(0)
    nat, refr, refz = [], [], []
    for fi in a.frames:
        fd = a.frame(fi)
        ok = fd["native_valid"] & fd["ref_valid"]
        idx = np.flatnonzero(ok.ravel())
        if idx.size == 0:
            continue
        take = idx if idx.size <= SAMPLES_PER_FRAME else rng.choice(
            idx, size=SAMPLES_PER_FRAME, replace=False)
        nat.append(fd["native"].ravel()[take])
        refr.append(fd["ref_range"].ravel()[take])
        refz.append(fd["ref_z"].ravel()[take])
        del fd
    if not nat:
        return None
    return pol.fit_clip(arm_key, np.concatenate(nat), np.concatenate(refr),
                        np.concatenate(refz))


def med(field, mask):
    v = field[mask]
    v = v[np.isfinite(v) & (v > 0)]
    return (float(np.median(v)), int(v.size)) if v.size >= 12 else (np.nan, int(v.size))


def score_frame(rng_field: np.ndarray, ann: dict) -> dict:
    """Per-opening fill/member/gap for one frame of one arm."""
    r_sea, n_sea = med(rng_field, ann["sea_local"])
    out = {"r_sea": r_sea, "n_sea_px": n_sea, "openings": []}
    if not np.isfinite(r_sea):
        return out
    er = {e: np.ones((2 * e + 1,) * 2, np.uint8) for e in EROSIONS}
    for o in ann["openings"]:
        r_mem, n_mem = med(rng_field, o["ring"])
        rec = {"tier": o["tier"], "area": o["area"], "r_mem": r_mem,
               "n_ring_px": n_mem, "by_erosion": {}}
        for e in EROSIONS:
            core = cv2.erode(o["full"].astype(np.uint8), er[e],
                             borderType=cv2.BORDER_REPLICATE).astype(bool)
            r_open, n_open = med(rng_field, core)
            if np.isfinite(r_open) and np.isfinite(r_mem):
                rec["by_erosion"][str(e)] = {
                    "r_open": r_open, "n_core_px": n_open,
                    "fill": float(np.log(r_sea / r_open)),
                    "member": float(np.log(r_sea / r_mem)),
                    "gap": float(np.log(r_open / r_mem)),
                }
        if rec["by_erosion"]:
            out["openings"].append(rec)
    return out


def summarise(frames: list[dict], tier: str, e: int = EROSIONS[0]) -> dict:
    """Pool one tier's openings across the annotation frames."""
    fill, mem, gap = [], [], []
    for f in frames:
        for o in f["openings"]:
            if o["tier"] != tier:
                continue
            d = o["by_erosion"].get(str(e))
            if d is None:
                continue
            fill.append(d["fill"]); mem.append(d["member"]); gap.append(d["gap"])
    if not gap:
        return {"n_openings": 0}
    fill, mem, gap = map(np.asarray, (fill, mem, gap))
    # "Filled" = the hole has been dragged more than half the way from the open
    # sea onto the member in front of it. Undefined when the model does not
    # separate the two at all, so those openings are counted, not divided.
    denom = mem
    frac = np.where(np.abs(denom) > 1e-3, fill / np.where(np.abs(denom) > 1e-3,
                                                          denom, 1.0), np.nan)
    return {
        "n_openings": int(gap.size),
        "median_gap": float(np.median(gap)),
        "median_fill": float(np.median(fill)),
        "median_member": float(np.median(mem)),
        "frac_gap_positive": float(np.mean(gap > 0)),
        "frac_gap_over_10pct": float(np.mean(gap > np.log(1.10))),
        "frac_gap_inverted_10pct": float(np.mean(gap < -np.log(1.10))),
        "median_fill_fraction": (float(np.nanmedian(frac))
                                 if np.isfinite(frac).any() else None),
        "frac_filled_over_half": (float(np.nanmean(frac > 0.5))
                                  if np.isfinite(frac).any() else None),
        "frac_member_erased": float(np.mean(mem < np.log(1.05))),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--arms", nargs="*")
    ap.add_argument("--policy", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "R2_S3_policy.json"))
    ap.add_argument("--root", default=os.path.join(common.OUTPUTS, "predictions"))
    ap.add_argument("--out", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "outputs", "thin", "r2_thin_raw.json"))
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    if os.path.exists(args.out) and not args.overwrite:
        raise SystemExit(f"{args.out} exists; pass --overwrite")

    pol = policy.Policy.load(args.policy)
    arms = list(args.arms or pol.entries)
    for arm in arms:
        if arm not in pol.entries:
            e = provisional_entry(armio.arm_model(arm), args.root)
            if e is None:
                raise SystemExit(f"{arm}: no frozen policy and no provisional "
                                 f"entry can be derived; S2 must run first")
            pol.entries[arm] = e
    arms = [a for a in arms if monoio.exists(args.root, armio.arm_model(a), CLIP)]

    # The annotation, recomputed deterministically from the same module that
    # wrote the inspected overlays.
    anns = {}
    for fi in ANN.FRAMES:
        bgr = cv2.imread(common.frame_path(CLIP, fi))
        anns[fi] = ANN.annotate(bgr)

    rec = {"_comment": __doc__.split("\n\n")[0], "stage": "R2-THIN",
           "clip": CLIP, "frames": ANN.FRAMES, "erosions": list(EROSIONS),
           "grid": "source resolution (downsample=1)",
           "policy": os.path.relpath(args.policy, REPO_ROOT), "arms": {}}

    # The provisional reference, scored as one arm among the rest.
    ref = evalgrid.ReferenceClip(CLIP, downsample=1)
    per = []
    for fi in ANN.FRAMES:
        r, ok = ref.load(fi)
        per.append(score_frame(np.where(ok, r, np.nan), anns[fi]))
    rec["arms"]["week3_reference"] = {
        "role": "the PROVISIONAL Week-3 multi-view hypothesis, scored like any "
                "other arm and authoritative over none of them",
        "alignment": {"family": "none", "note": "the reference defines the gauge"},
        "per_frame": per,
        "tier_a": summarise(per, "A"), "tier_b": summarise(per, "B"),
        "edge": {str(e): summarise(per, "A", e) for e in EROSIONS}}
    print(f"[thin] {'week3_reference':26s} "
          f"gap={rec['arms']['week3_reference']['tier_a']['median_gap']:.3f}")

    for arm in arms:
        if not monoio.exists(args.root, armio.arm_model(arm), CLIP):
            rec["arms"][arm] = {"status": "missing"}
            continue
        fit = clip_fit(arm, pol, args.root)
        if fit is None:
            rec["arms"][arm] = {"status": "no_overlapping_valid_samples"}
            continue
        a = armio.Arm(arm, CLIP, args.root, downsample=1)
        per = []
        for fi in ANN.FRAMES:
            fd = a.frame(fi)
            r = pol.to_range(arm, fd["native"], fit, fd["secant"])
            r = np.where(fd["native_valid"], r, np.nan)
            per.append(score_frame(r, anns[fi]))
            per[-1]["coverage_tier_a"] = float(np.mean(
                np.isfinite(r)[np.any(np.stack(
                    [o["core"] for o in anns[fi]["openings"]
                     if o["tier"] == "A"]), axis=0)]))
            del fd, r
        rec["arms"][arm] = {
            "role": armio.arm_role(arm), "policy": pol.entry(arm),
            "alignment": {"family": fit.family, "params": fit.params},
            "per_frame": per,
            "tier_a": summarise(per, "A"), "tier_b": summarise(per, "B"),
            "edge": {str(e): summarise(per, "A", e) for e in EROSIONS}}
        t = rec["arms"][arm]["tier_a"]
        print(f"[thin] {arm:26s} gap={t['median_gap']:+.3f} "
              f"fill={t['median_fill']:+.3f} member={t['median_member']:+.3f} "
              f"gap>0={t['frac_gap_positive']:.2f} "
              f"filled>half={t['frac_filled_over_half']:.2f}")
        del a

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(rec, fh, indent=1)
    print("->", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
