"""S4 step 1 — generate the frozen appearance perturbations as image files.

EXPLORATORY. Runs in `.venv-eval` (numpy + opencv + `uw.colorspace`).

FREEZE §5 S4 starts from the SAME frozen Week-3 frames and perturbs them
geometry-preservingly. It does NOT acquire or choose a new primary dataset, and
Atlantis++ is explicitly a secondary option only if its matched-geometry
structure can be verified — it is not used here.

WHY A SUBSET OF FRAMES. S4 needs a frame-to-frame trajectory (FREEZE C7's
distinction between a constant scale bias and frame-varying drift only exists
over consecutive frames), and it needs 12 perturbations per frame per surviving
model. Running the full 288-frame set 12 times over would cost hours of
inference to answer a question a contiguous window answers properly. So each
clip contributes a CONTIGUOUS window of `WINDOW` frames taken from its middle —
contiguous, because a stride would destroy the frame-to-frame structure the
stage exists to measure.

    6 clips x 16 consecutive frames x 12 perturbations = 1 152 images per model,
    plus the 96 unperturbed frames as the baseline arm.

Written to `outputs/perturbed/<clip>/<perturbation>/f%06d.png`, alongside a
manifest recording what each perturbation did to the appearance — so a geometry
response always has an appearance denominator.

    experiments/week4_mono/.venv-eval/bin/python \\
        -m experiments.week4_mono.scripts.s4_make_perturbations --overwrite
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week4_mono import common, evalgrid, perturb  # noqa: E402

#: Contiguous frames per clip. 16 gives 15 consecutive frame-to-frame steps,
#: which is enough to see a scale trajectory wander and cheap enough to run 12
#: perturbations over.
WINDOW = 16


def window_frames(clip: str, window: int = WINDOW) -> list[int]:
    idx = common.frame_indices(clip)
    start = max(0, (len(idx) - window) // 2)
    return idx[start:start + window]


def main() -> int:
    import cv2
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clips", nargs="*", default=None)
    ap.add_argument("--window", type=int, default=WINDOW)
    ap.add_argument("--out-root", default=os.path.join(common.OUTPUTS, "perturbed"))
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    clips = args.clips or common.CLIPS
    manifest = {
        "_comment": ("Frozen S4 appearance perturbations. Every one is a PER-PIXEL "
                     "intensity operation applied in LINEAR light (CLAUDE.md invariant 1) "
                     "and re-encoded to 8-bit sRGB. Nothing is warped, resampled or "
                     "cropped, so the underlying scene geometry is identical by "
                     "construction."),
        "window": args.window,
        "window_rationale": ("a CONTIGUOUS window from each clip's middle: S4 must be able "
                             "to see frame-to-frame scale drift, and a strided sample would "
                             "destroy exactly that structure"),
        "quantisation_note": ("perturbed frames are written as 8-bit PNGs before inference, "
                              "so every S4 response carries an 8-bit quantisation floor. "
                              "That cost buys each model its own real preprocessing path and "
                              "makes every perturbed input an inspectable artifact."),
        "perturbations": [{"name": n, "kind": k, "params": p, "probes": w}
                          for n, k, p, w in perturb.SPEC],
        "clips": {},
    }

    for clip in clips:
        frames = window_frames(clip, args.window)
        # The depth-structured veils need the reference range ON THE SOURCE GRID,
        # because they shape the stimulus pixel by pixel. It is read here, in the
        # image-generation step, and never goes near a model.
        ref = evalgrid.ReferenceClip(clip)
        rec = {"frames": frames, "n_frames": len(frames), "perturbations": {}}
        for name, kind, params, _ in perturb.SPEC:
            out_dir = os.path.join(args.out_root, clip, name)
            os.makedirs(out_dir, exist_ok=True)
            stats = []
            for fi in frames:
                dst = os.path.join(out_dir, f"f{fi:06d}.png")
                common.refuse_clobber(dst, args.overwrite)
                bgr = cv2.imread(common.frame_path(clip, fi))
                rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
                rr = None
                if kind == "veil_depth":
                    r_eval, ok = ref.load(fi)
                    # Upsample the evaluation-grid reference back to source size
                    # with nearest neighbour: it is shaping a smooth veil, not
                    # being measured, and nearest never invents a range value.
                    r_src = cv2.resize(np.where(ok, r_eval, np.nan).astype(np.float32),
                                       (rgb.shape[1], rgb.shape[0]),
                                       interpolation=cv2.INTER_NEAREST)
                    rr = r_src.astype(np.float64)
                out = perturb.apply_perturbation(rgb, kind, params, ref_range=rr)
                cv2.imwrite(dst, cv2.cvtColor(out, cv2.COLOR_RGB2BGR))
                stats.append(perturb.perturbation_summary(rgb, out))
            rec["perturbations"][name] = {
                "dir": os.path.relpath(out_dir, REPO_ROOT),
                "n_written": len(frames),
                "appearance_change": {
                    "linear_abs_diff_median":
                        float(np.median([s["linear_abs_diff_median"] for s in stats])),
                    "linear_abs_diff_p95":
                        float(np.median([s["linear_abs_diff_p95"] for s in stats])),
                    "clipped_high_fraction":
                        float(np.median([s["clipped_high_fraction"] for s in stats])),
                    "clipped_low_fraction":
                        float(np.median([s["clipped_low_fraction"] for s in stats])),
                },
            }
            ac = rec["perturbations"][name]["appearance_change"]
            print(f"[S4-gen] {clip:15s} {name:28s} n={len(frames)} "
                  f"dlin_med={ac['linear_abs_diff_median']:.4f} "
                  f"clip_hi={ac['clipped_high_fraction']:.4f}")
        manifest["clips"][clip] = rec

    common.write_json(os.path.join(args.out_root, "manifest.json"), manifest,
                      overwrite=True)
    total = sum(len(r["frames"]) * len(perturb.SPEC) for r in manifest["clips"].values())
    print(f"[S4-gen] {total} perturbed frames across {len(clips)} clips "
          f"x {len(perturb.SPEC)} perturbations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
