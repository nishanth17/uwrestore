"""Week 4A — an ARM: one scoreable geometry field, on the common evaluation grid.

EXPLORATORY. Pure numpy (torch only reaches this module through M-3).

Most entrants contribute exactly one arm: their primary prediction. FoundationGeo
contributes four, because FREEZE §C3/§5 requires its two internal ablations to be
scored the same way every other candidate is, not with a bespoke comparison:

    fg_pre_ray      raw geometry BEFORE the learned ray-direction delta
    fg_post_ray     raw geometry AFTER it            -> V4b is pre vs post
    fg_post_ray     common post-ray RELATIVE geometry (C)
    fg_metric       C * scalefield                   -> V4c is C vs D

Both arms of V4b come out of ONE forward pass and share ONE frozen (focal, shift)
solution, which is what makes their difference attributable to the ray delta
alone. Arms `fg_post_ray` and the C of V4c are the SAME field; it is listed twice
because it plays a role in both ablations, not because it is computed twice.

An arm knows how to hand back, for one frame, on the shared evaluation grid:

    the model's scalar in its NATIVE quantity  (what the alignment is fitted in)
    the reference range and the reference z-depth
    the secant factor, so a z-hypothesis can be converted to range
    validity, and the shared evaluation camera

Nothing here applies an alignment. That is `alignment.py`'s job, under the policy
S2 froze.
"""

from __future__ import annotations

import numpy as np

from experiments.week3_geometry.phase3a import geometry as g3
from experiments.week4_mono.round1 import common, evalgrid, monoio

#: arm key -> (model, aux array name or None, human role)
FG_ARMS = {
    "fg_pre_ray": ("foundationgeo_11", "points_pre_ray_common",
                   "V4b arm A: raw geometry BEFORE the learned ray-direction delta, "
                   "under the common frozen (focal, shift)"),
    "fg_post_ray": ("foundationgeo_11", "points_post_ray_common",
                    "V4b arm B and V4c arm C: raw geometry AFTER the ray delta, "
                    "same forward pass, same frozen (focal, shift)"),
}


def arm_keys(models: list[str]) -> list[str]:
    out = list(models)
    if "foundationgeo_11" in models:
        out += list(FG_ARMS)
    return out


def arm_model(arm: str) -> str:
    return FG_ARMS[arm][0] if arm in FG_ARMS else arm


def arm_role(arm: str) -> str:
    if arm in FG_ARMS:
        return FG_ARMS[arm][2]
    if arm == "foundationgeo_11":
        return "V4c arm D: post-ray relative geometry x scalefield — the model's primary output"
    return "primary prediction"


class Arm:
    """One arm of one clip, resampled onto the shared evaluation grid frame by frame."""

    def __init__(self, arm: str, clip: str, root: str,
                 downsample: int = evalgrid.EVAL_DOWNSAMPLE):
        # `downsample` exists ONLY for the Round-2 thin-structure test, which
        # has to look at members a few source pixels wide -- the default stride
        # of 4 would sample straight past them. Every primary stage leaves it
        # at `EVAL_DOWNSAMPLE`, so the frozen comparison grid is unchanged.
        self.arm = arm
        self.model = arm_model(arm)
        self.aux = FG_ARMS[arm][1] if arm in FG_ARMS else None
        self.clip = clip
        self.reader = monoio.MonoReader(root, self.model, clip)
        self.ref = evalgrid.ReferenceClip(clip, downsample=downsample)
        self.source_hw = common.clip_source_hw(clip)
        self.gmap = evalgrid.load_model_gridmap(
            self.model, self.source_hw,
            pred_hw=self.reader.meta["frames"][0]["native_shape"][:2])
        self.native_kind = self.reader.native_kind
        # An ablation arm is always a point map, whatever the primary output is.
        self.arm_kind = "pointmap_metric" if self.aux else self.native_kind
        self.eval_hw = self.ref.eval_hw
        self.radius = self.ref.radius

    @property
    def frames(self) -> list[int]:
        return [f for f in self.reader.frame_indices if f in self.ref.reader.by_index]

    def native_scalar(self, frame_index: int):
        """The model's own scalar, on its NATIVE grid, plus validity.

        For a point map that is `||p||` — the canonical range, never `p[..., 2]`,
        which is z-depth. For a scalar model it is the field itself, untouched.
        """
        v = np.asarray(self.reader.load_valid(frame_index))
        if self.aux:
            pts = self.reader.load_aux(frame_index, self.aux)
            if pts is None:
                raise SystemExit(f"{self.arm}: missing aux {self.aux!r} for frame {frame_index}")
            s = np.linalg.norm(np.asarray(pts, dtype=np.float64), axis=-1)
        else:
            nat = self.reader.load_native(frame_index)
            nat = np.asarray(nat, dtype=np.float64)
            s = np.linalg.norm(nat, axis=-1) if nat.ndim == 3 else nat
        return s, v

    def frame(self, frame_index: int) -> dict:
        """Everything one frame's metrics need, all on the evaluation grid."""
        r_ref, ok_ref = self.ref.load(frame_index)
        K_eval = self.ref.K_eval(frame_index)
        h, w = self.eval_hw
        sec = g3.ray_length_factor(K_eval, h, w)

        s_nat, v_pred = self.native_scalar(frame_index)
        vals, ok = evalgrid.sample(s_nat, v_pred, self.ref.uv, self.gmap)
        native = np.where(ok, vals, np.nan).reshape(h, w)
        ok = ok.reshape(h, w)

        return {
            "frame": int(frame_index),
            "native": native,
            "native_valid": ok,
            "ref_range": r_ref,
            "ref_valid": ok_ref,
            "ref_z": r_ref / sec,
            "secant": sec,
            "K_eval": K_eval,
            "eval_hw": (h, w),
            "radius": self.radius,
            # Coverage against the reference is a first-class result, not
            # bookkeeping: Wat3R's portrait FOV loss shows up here.
            "coverage": float((ok & ok_ref).mean()),
            "reference_coverage": float(ok_ref.mean()),
        }
