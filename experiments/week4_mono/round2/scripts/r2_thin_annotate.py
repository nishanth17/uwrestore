"""Round 2 §18 — the wreck_07 crane-lattice annotation.

TARGETED, NOT A NEW BENCHMARK. Six frames of ONE clip, one known failure
region. Nothing here is added to the primary S3 ranking.

WHY THIS IS ANNOTATED FROM THE IMAGE AND NOT FROM THE REFERENCE. The Week-3
range product is a PROVISIONAL MULTI-VIEW HYPOTHESIS, and multi-view
reconstruction is itself weak on thin structure -- using it to define where the
holes are would grade every model against the very failure under test. The
annotation therefore rests on one ordinal fact that is visible in the RGB frame
and needs no depth: the open water seen THROUGH a gap in the crane lattice is
much farther away than the encrusted member in front of it. That fact is
checkable by eye, and the visual check is mandatory (CLAUDE.md invariant 5).

THE RULE, stated so it is reproducible.

    water(x)     = blueness B/(R+G+B) high, local luminance texture low,
                   luminance not dark  -- open water column, near or far
    BACKGROUND   = the single largest connected water component (the open sea
                   to the right of the wreck)
    OPENING      = every other water component, i.e. water COMPLETELY
                   ENCLOSED by structure: a hole through the lattice
    MEMBER(c)    = the structure ring 3..9 px outside opening c -- the thin
                   member that stands in front of that hole
    LOCAL SEA    = BACKGROUND water within 60 px of a Tier-A opening: the open
                   water column immediately beside the lattice. Because a
                   Tier-A opening is photometrically identical to it, the two
                   are at comparable range, which makes LOCAL SEA a legitimate
                   FAR anchor -- established from veiling, not from any depth
                   estimate.

Openings are split into two tiers and only the first is PRIMARY.

    TIER A  the opening is photometrically INDISTINGUISHABLE from the open
            water column -- as blue and as bright as the sea beside the wreck.
            Underwater that is a statement about distance and nothing else:
            veiling is monotone in range, so a patch that has reached the water
            colour is far. Whatever the member in front of it is, it is nearer.
    TIER B  every other enclosed opening -- darker, less blue, i.e. some part
            of the wreck sits a short way behind the gap. The ordinal fact
            still holds but the margin is small, so these are recorded and
            reported SEPARATELY and never mixed into the primary number.

The tier split was made from the visual inspection, before any model was
scored, and for a stated reason about what the pixels contain -- not by
looking at which split produced a cleaner result.

Components are eroded by 2 px before measurement and the 0..3 px ring around
each is left unlabelled, so no sample sits on the mixed edge itself. A dark
hole into the wreck's interior is NOT water (low blueness, low luminance) and
so is never labelled an opening.

    experiments/week4_mono/.venv-eval/bin/python \\
        -m experiments.week4_mono.round2.scripts.r2_thin_annotate --overwrite
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import cv2
import numpy as np
from scipy import ndimage as ndi

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                         "..", "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week4_mono.round1 import common  # noqa: E402

CLIP = "wreck_07"

#: The six annotation frames, spread across the part of the clip where the
#: crane/davit lattice is silhouetted against open water. After ~f000160 the
#: camera has turned and the structure fills the frame, so there is no
#: background to see through it; those frames are not usable for this test and
#: are excluded for that reason, not because of how any model scored.
FRAMES = [25, 59, 92, 109, 126, 143]

#: Thresholds. Measured on f000109: open water patch (blueness 0.593, texture
#: 0.010, luminance 0.551); encrusted structure patch (0.358, 0.049, 0.318).
#: The gap between the two populations is wide, which is why a threshold works
#: here at all -- and why the overlay must still be inspected.
BLUENESS_MIN = 0.44
TEXTURE_MAX = 0.020
LUMA_MIN = 0.25
TEXTURE_WIN = 11

EROSION_PX = 2           # keep samples off the mixed edge
RING_INNER, RING_OUTER = 3, 9    # the member ring around an opening
MIN_OPENING_PX = 60      # below this an "opening" is compression speckle
MAX_OPENING_PX = 40000   # above this it is not a hole through a lattice
#: Tier A test, relative to THIS frame's own open-sea background so it does not
#: depend on exposure or grade: an opening counts as "sea-through" when its core
#: is no more than 0.05 less blue and at least 75 % as bright as the background
#: water column. Measured background on the six frames: blueness 0.587-0.592,
#: luminance 0.542-0.566; the darkest openings sit at 0.45/0.27.
TIER_A_BLUE_MARGIN = 0.05
TIER_A_LUM_FRAC = 0.75
#: How far from a Tier-A opening the local open-sea anchor may be drawn.
#: A disk-based "thin member" detector was tried first and abandoned after
#: visual inspection: on this footage it fired on marine snow and on the ridge
#: lines of the distant sand slope rather than on the crane arm, because the
#: sand slope is veiled to water colour and therefore joins the background
#: component. The near/far decomposition below needs no such detector.
LOCAL_SEA_RADIUS_PX = 60


def water_mask(bgr: np.ndarray) -> np.ndarray:
    """The open-water-column mask, from colour and texture alone."""
    im = bgr[:, :, ::-1].astype(np.float32) / 255.0
    blueness = im[..., 2] / (im.sum(2) + 1e-6)
    lum = im.mean(2)
    m = cv2.blur(lum, (TEXTURE_WIN, TEXTURE_WIN))
    texture = np.sqrt(np.maximum(cv2.blur(lum * lum, (TEXTURE_WIN,) * 2) - m * m, 0))
    w = (blueness > BLUENESS_MIN) & (texture < TEXTURE_MAX) & (lum > LUMA_MIN)
    # Morphology with a REPLICATED border: scipy pads with zeros, which erodes
    # the frame edge away and would hide the background component entirely.
    k = np.ones((5, 5), np.uint8)
    w = cv2.morphologyEx(w.astype(np.uint8), cv2.MORPH_OPEN, k,
                         borderType=cv2.BORDER_REPLICATE)
    w = cv2.morphologyEx(w, cv2.MORPH_CLOSE, k, borderType=cv2.BORDER_REPLICATE)
    return w.astype(bool)


def annotate(bgr: np.ndarray) -> dict:
    """Labels for one frame: background, openings (2 tiers), thin members."""
    water = water_mask(bgr)
    lab, n = ndi.label(water)
    if n == 0:
        z = np.zeros_like(water)
        return {"background": z, "openings": [], "structure": ~water,
                "water": water, "sea_local": z,
                "bg_blueness": None, "bg_luma": None}
    sizes = np.bincount(lab.ravel())
    sizes[0] = 0
    bg_id = int(np.argmax(sizes))
    background = lab == bg_id
    structure = ~water

    im = bgr[:, :, ::-1].astype(np.float32) / 255.0
    blueness = im[..., 2] / (im.sum(2) + 1e-6)
    luma = im.mean(2)
    bg_blue = float(np.median(blueness[background]))
    bg_luma = float(np.median(luma[background]))
    d_bg = ndi.distance_transform_edt(~background)

    er = np.ones((2 * EROSION_PX + 1,) * 2, np.uint8)
    openings = []
    for i in range(1, n + 1):
        if i == bg_id or not (MIN_OPENING_PX <= sizes[i] <= MAX_OPENING_PX):
            continue
        m = lab == i
        core = cv2.erode(m.astype(np.uint8), er,
                         borderType=cv2.BORDER_REPLICATE).astype(bool)
        if core.sum() < 20:
            continue
        d = ndi.distance_transform_edt(~m)
        ring = structure & (d >= RING_INNER) & (d <= RING_OUTER)
        if ring.sum() < 40:
            continue
        ob, ol = float(np.median(blueness[core])), float(np.median(luma[core]))
        tier = ("A" if (ob >= bg_blue - TIER_A_BLUE_MARGIN
                        and ol >= TIER_A_LUM_FRAC * bg_luma) else "B")
        openings.append({"id": int(i), "area": int(sizes[i]), "tier": tier,
                         "blueness": ob, "luma": ol,
                         "dist_to_sea_px": float(d_bg[m].min()),
                         "core": core, "ring": ring, "full": m})

    # LOCAL SEA: the open water column immediately beside the Tier-A holes.
    tier_a = [o for o in openings if o["tier"] == "A"]
    if tier_a:
        any_a = np.any(np.stack([o["full"] for o in tier_a]), axis=0)
        d_a = ndi.distance_transform_edt(~any_a)
        sea_local = background & (d_a <= LOCAL_SEA_RADIUS_PX)
    else:
        sea_local = np.zeros_like(background)

    return {"background": background, "structure": structure,
            "openings": openings, "water": water, "sea_local": sea_local,
            "bg_blueness": bg_blue, "bg_luma": bg_luma}


def overlay(bgr: np.ndarray, ann: dict) -> np.ndarray:
    """The picture a human has to look at before any of this counts."""
    vis = bgr.copy()
    bg = ann["background"]
    vis[bg] = (0.55 * vis[bg] + 0.45 * np.array([255, 0, 0])).astype(np.uint8)   # blue
    for o in ann["openings"]:
        c, r = o["core"], o["ring"]
        col = [0, 0, 255] if o["tier"] == "A" else [0, 255, 255]   # red / yellow
        vis[c] = (0.25 * vis[c] + 0.75 * np.array(col)).astype(np.uint8)
        vis[r] = (0.55 * vis[r] + 0.45 * np.array([0, 255, 0])).astype(np.uint8)  # green
    sl = ann["sea_local"]
    vis[sl] = (0.55 * vis[sl] + 0.45 * np.array([255, 0, 255])).astype(np.uint8)
    return vis


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "outputs", "thin"))
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    rec = {"clip": CLIP, "frames": FRAMES, "rule": {
        "blueness_min": BLUENESS_MIN, "texture_max": TEXTURE_MAX,
        "luma_min": LUMA_MIN, "texture_window": TEXTURE_WIN,
        "erosion_px": EROSION_PX, "ring_px": [RING_INNER, RING_OUTER],
        "opening_area_px": [MIN_OPENING_PX, MAX_OPENING_PX]}, "per_frame": {}}
    for fi in FRAMES:
        p = common.frame_path(CLIP, fi)
        bgr = cv2.imread(p)
        if bgr is None:
            raise SystemExit(f"missing frame {p}")
        ann = annotate(bgr)
        npz = os.path.join(args.out, f"labels_f{fi:06d}.npz")
        if os.path.exists(npz) and not args.overwrite:
            raise SystemExit(f"{npz} exists; pass --overwrite")
        np.savez_compressed(
            npz, background=ann["background"],
            core=np.stack([o["core"] for o in ann["openings"]]),
            ring=np.stack([o["ring"] for o in ann["openings"]]),
            area=np.array([o["area"] for o in ann["openings"]]),
            tier=np.array([o["tier"] for o in ann["openings"]]),
            sea_local=ann["sea_local"])
        cv2.imwrite(os.path.join(args.out, f"overlay_f{fi:06d}.png"),
                    overlay(bgr, ann))
        A = [o for o in ann["openings"] if o["tier"] == "A"]
        B = [o for o in ann["openings"] if o["tier"] == "B"]
        rec["per_frame"][f"f{fi:06d}"] = {
            "n_openings_tier_a": len(A), "n_openings_tier_b": len(B),
            "opening_core_px_tier_a": int(sum(o["core"].sum() for o in A)),
            "opening_core_px_tier_b": int(sum(o["core"].sum() for o in B)),
            "background_px": int(ann["background"].sum()),
            "local_sea_px": int(ann["sea_local"].sum()),
            "median_opening_area_px_tier_a": float(np.median(
                [o["area"] for o in A])) if A else None,
            "background_blueness": ann["bg_blueness"],
            "background_luma": ann["bg_luma"],
        }
        e = rec["per_frame"][f"f{fi:06d}"]
        print(f"[thin-annot] f{fi:06d} tierA={len(A)} ({e['opening_core_px_tier_a']}px) "
              f"tierB={len(B)} local_sea={e['local_sea_px']}px "
              f"bg={e['background_px']}px")
    with open(os.path.join(args.out, "annotation.json"), "w") as fh:
        json.dump(rec, fh, indent=1)
    print("->", os.path.join(args.out, "annotation.json"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
