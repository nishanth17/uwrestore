"""Week 4A — the FROZEN S2 alignment policy, and how S3-S6 consume it.

EXPLORATORY. Pure numpy.

`MONO_DEPTH_FREEZE.md` §5 S2: "After S2 the alignment POLICY, transform family
per representation, and fitting scope are frozen for S3-S6." This module is that
freeze made executable, so that no later stage can quietly fit something else.

A policy entry says, per arm:

    family        which E1 transform is legal for this representation
    convention    whether the arm's native scalar is z-depth or range
    scope         clip-level (primary) — per-frame fits are diagnostics only

and S3-S6 call `align_frame` rather than choosing anything themselves.

WHAT THE POLICY DOES NOT DO. It does not decide that the aligned number is
deployable. E1 answers "if the model's documented legal ambiguity were known,
how good is the remaining shape?" (FREEZE C9). The nuisance parameters it
consumed are reported alongside, because a model that needs a large shift, or a
scale that wanders frame to frame, has told you something the residual does not.
"""

from __future__ import annotations

import json
import os

import numpy as np

from experiments.week4_mono.round1 import alignment


class Policy:
    """The frozen per-arm alignment policy."""

    def __init__(self, entries: dict, meta: dict | None = None):
        self.entries = entries
        self.meta = meta or {}

    @classmethod
    def load(cls, path: str) -> "Policy":
        with open(path) as fh:
            d = json.load(fh)
        return cls(d["arms"], {k: v for k, v in d.items() if k != "arms"})

    def save(self, path: str) -> str:
        payload = dict(self.meta)
        payload["arms"] = self.entries
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(payload, fh, indent=2)
        os.replace(tmp, path)
        return path

    def entry(self, arm: str) -> dict:
        if arm not in self.entries:
            raise KeyError(f"no frozen policy for arm {arm!r}; S2 must freeze one "
                           f"before S3 may score it")
        return self.entries[arm]

    # -- fitting ----------------------------------------------------------

    def fit_clip(self, arm: str, native: np.ndarray, ref_range: np.ndarray,
                 ref_z: np.ndarray) -> alignment.Alignment:
        """The ONE clip-level fit S3-S6 are allowed to use for this arm."""
        e = self.entry(arm)
        ref_side = ref_z if e["convention"] == "z_depth" else ref_range
        fam = e["family"]
        if fam == "none":
            return alignment.Alignment("none", {}, int(np.isfinite(native).sum()),
                                       int(native.size), "clip")
        if fam == "scale":
            return alignment.fit_scale(native, ref_side, scope="clip")
        if fam == "affine_depth":
            return alignment.fit_affine(native, ref_side, "affine_depth", scope="clip")
        if fam == "affine_disparity":
            return alignment.fit_affine(native, alignment.to_disparity(ref_side),
                                        "affine_disparity", scope="clip")
        if fam == "affine_log1p_depth":
            # ROUND 2 / PXDepth. Its documented gauge is affine in log1p(depth),
            # so the REFERENCE is carried into that space and the fit happens
            # there -- the same rule as disparity, applied to a different space.
            # Fitting a*d+b in physical depth would be a different group, not a
            # stricter one.
            return alignment.fit_affine(native, alignment.to_log1p(ref_side),
                                        "affine_log1p_depth", scope="clip")
        raise ValueError(f"unknown family {fam!r}")

    def to_range(self, arm: str, native: np.ndarray, fit: alignment.Alignment,
                 secant: np.ndarray) -> np.ndarray:
        """Apply a fitted transform and return a RANGE field on the evaluation grid.

        The z-hypothesis conversion happens HERE and only here: an arm whose
        convention is `z_depth` is aligned in z-depth and multiplied by the
        shared camera's secant factor afterwards. Doing it in the other order
        would mix a per-pixel radial factor into a global fit.
        """
        e = self.entry(arm)
        aligned = alignment.apply(fit, native)
        rng = alignment.to_range(aligned, fit.family)
        if e["convention"] == "z_depth":
            rng = rng * np.asarray(secant, dtype=np.float64)
        return rng
