"""Week 4A — the per-model monocular prediction product on disk.

EXPLORATORY. Pure numpy, so it imports from every isolated model venv.

`experiments/week3_geometry/rangeio.py` stores exactly one thing: a canonical
`range_along_ray`. That was right for Week 3, where every entrant emitted a
central-camera range and the question was cross-family agreement. It is wrong
for Week 4A, whose whole point is that the seven entrants do NOT share a
representation: one emits disparity, one emits relative depth, four emit point
maps, and the alignment that is legal for one is illegal for another
(`MONO_DEPTH_FREEZE.md` §5 S0/S2).

So this writer keeps BOTH:

    the NATIVE output, unmodified, in the model's own units and semantics
    a CANONICAL range derived from it by an explicitly recorded rule

Reduction to "depth" never happens implicitly. `native_kind` says what the
native array is, and `range_rule` says, in words, how the canonical range was
obtained from it. A reader that wants the native quantity gets the native
quantity; a reader that wants range gets range and can see the rule.

Layout, per `CLAUDE.md` invariant 9 — one frame at a time to disk, nothing
accumulated in RAM, readers memory-map:

    <root>/<model>/<clip>/
        clip.json                 provenance, semantics, per-frame index
        f000008_range.npy         (H,W) float32   canonical range, NaN where invalid
        f000008_valid.npy         (H,W) bool
        f000008_native.npy        (H,W) or (H,W,3) float32   NATIVE output
        f000008_conf.npy          (H,W) float32   optional
        f000008_<aux>.npy         model-specific extras (e.g. FoundationGeo arms)

`NATIVE_KINDS` is closed on purpose. Adding a representation is a scientific
act — it changes which alignment family S2 is allowed to fit — so it has to be
a deliberate edit here rather than a free-form string a backend invents.
"""

from __future__ import annotations

import json
import os

import numpy as np

#: What the `_native.npy` array actually is. The alignment policy frozen in S2
#: keys off this, so it is deliberately a closed set.
NATIVE_KINDS = {
    # scalar, (H,W)
    "disparity_relative": "relative inverse depth; affine ambiguity lives HERE, not in depth",
    "depth_relative": "relative z-depth or range as the model defines it; see range_rule",
    "depth_along_ray_metric": "metric Euclidean camera-centre-to-point distance",
    # vector, (H,W,3)
    "pointmap_relative": "camera-frame point map, relative (up to its documented gauge)",
    "pointmap_metric": "camera-frame point map, metric-claimed",
    "pointmap": ("camera-frame point map whose SCALE CLAIM THE RELEASE DOES NOT STATE. "
                 "Distinct from both siblings on purpose: FREEZE 3.3 forbids inferring "
                 "Wat3R's native ambiguity from its released evaluation code's alignment, "
                 "so declaring it metric or relative here would be exactly the inheritance "
                 "the freeze rules out. It therefore carries the WIDEST legal family set "
                 "in S2 (none / scale / affine_depth) and the question is settled by "
                 "measurement, not by this label."),
}

#: How `_range.npy` relates to the native array. Recorded verbatim in clip.json.
RANGE_RULES = {
    "identity_depth_along_ray": "range = native, which is already ||pts3d_cam||",
    "norm_pointmap": "range = ||points|| over the last axis",
    "zdepth_to_range_with_K": "range = z_depth * ||K^-1 [u,v,1]||, using the model's own K",
    "invert_disparity": "range = 1/disparity AFTER an alignment fitted in disparity space",
    "unresolved": "no canonical range is defined for this product on its own",
}


class MonoWriter:
    """Streams one model's predictions for one clip to disk, one frame at a time."""

    def __init__(self, root: str, model: str, clip: str, overwrite: bool = False):
        self.dir = os.path.join(root, model, clip)
        if os.path.exists(os.path.join(self.dir, "clip.json")) and not overwrite:
            raise SystemExit(f"refusing to overwrite {self.dir!r} (pass --overwrite)")
        os.makedirs(self.dir, exist_ok=True)
        self.model = model
        self.clip = clip
        self.frames: list[dict] = []

    def add_frame(self, frame_index: int, native: np.ndarray, valid: np.ndarray,
                  canonical_range: np.ndarray | None = None,
                  K: np.ndarray | None = None, conf: np.ndarray | None = None,
                  aux: dict[str, np.ndarray] | None = None,
                  extra: dict | None = None) -> None:
        """Write one frame. Nothing is retained beyond a small metadata record."""
        nat = np.asarray(native, dtype=np.float32)
        v = np.asarray(valid, dtype=bool)
        if nat.shape[:2] != v.shape:
            raise ValueError(f"native {nat.shape} and valid {v.shape} disagree on (H,W)")

        stem = os.path.join(self.dir, f"f{frame_index:06d}")
        np.save(stem + "_native.npy", nat)

        rec = {
            "frame_index": int(frame_index),
            "shape_hw": [int(v.shape[0]), int(v.shape[1])],
            "native_shape": list(int(x) for x in nat.shape),
            "K": None if K is None else np.asarray(K, dtype=np.float64).tolist(),
        }

        if canonical_range is not None:
            r = np.asarray(canonical_range, dtype=np.float32)
            if r.shape != v.shape:
                raise ValueError(f"range {r.shape} and valid {v.shape} differ")
            # Same discipline as Week 3: a non-finite or non-positive range is
            # never stored as a number. It is demoted into the mask and written
            # as NaN, so no consumer can read a zero and believe the camera is
            # touching the scene.
            bad = ~np.isfinite(r) | (r <= 0)
            v = v & ~bad
            r = np.where(v, r, np.nan).astype(np.float32)
            np.save(stem + "_range.npy", r)
            rec["has_range"] = True
            if v.any():
                rec["range_median"] = float(np.nanmedian(r))
                rec["range_p05"] = float(np.nanpercentile(r, 5))
                rec["range_p95"] = float(np.nanpercentile(r, 95))
            else:
                rec["range_median"] = rec["range_p05"] = rec["range_p95"] = float("nan")
        else:
            rec["has_range"] = False

        np.save(stem + "_valid.npy", v)
        rec["valid_fraction"] = float(v.mean())

        # Native summary statistics are taken over the valid set only, and are
        # the cheap trace S1/S2/S5 read instead of reloading whole fields.
        nv = nat[v] if nat.ndim == 2 else nat[v].reshape(-1, nat.shape[-1])
        nv = nv[np.isfinite(nv).all(axis=-1)] if nv.ndim == 2 else nv[np.isfinite(nv)]
        if nv.size:
            rec["native_median"] = float(np.median(nv))
            rec["native_p05"] = float(np.percentile(nv, 5))
            rec["native_p95"] = float(np.percentile(nv, 95))
        else:
            rec["native_median"] = rec["native_p05"] = rec["native_p95"] = float("nan")

        if conf is not None:
            c = np.asarray(conf, dtype=np.float32)
            np.save(stem + "_conf.npy", c)
            rec["has_conf"] = True
            fin = np.isfinite(c)
            rec["conf_median"] = float(np.median(c[fin])) if fin.any() else float("nan")
        else:
            rec["has_conf"] = False

        if aux:
            rec["aux"] = sorted(aux)
            for name, arr in aux.items():
                np.save(f"{stem}_{name}.npy", np.asarray(arr, dtype=np.float32))
        if extra:
            rec.update(extra)
        self.frames.append(rec)

    def close(self, *, native_kind: str, range_rule: str, semantics: dict,
              provenance: dict, preprocessing: dict) -> str:
        if native_kind not in NATIVE_KINDS:
            raise ValueError(f"unknown native_kind {native_kind!r}; add it to NATIVE_KINDS "
                             f"deliberately, it changes what alignment is legal")
        if range_rule not in RANGE_RULES:
            raise ValueError(f"unknown range_rule {range_rule!r}")
        payload = {
            "_comment": ("Week 4A monocular prediction product. `native` is the model's "
                         "OWN output, unmodified. `range` is a derived canonical "
                         "Euclidean camera-centre-to-point distance obtained by "
                         "`range_rule`; it is NOT planar z-depth. Nothing here has "
                         "been aligned to any reference."),
            "model": self.model,
            "clip": self.clip,
            "native_kind": native_kind,
            "native_kind_meaning": NATIVE_KINDS[native_kind],
            "range_rule": range_rule,
            "range_rule_meaning": RANGE_RULES[range_rule],
            "semantics": semantics,
            "preprocessing": preprocessing,
            "provenance": provenance,
            "n_frames": len(self.frames),
            "frames": self.frames,
        }
        path = os.path.join(self.dir, "clip.json")
        tmp = path + ".tmp"
        with open(tmp, "w") as fh:
            json.dump(payload, fh, indent=2)
        os.replace(tmp, path)
        return path


class MonoReader:
    """Reads one model/clip product back one frame at a time (memory-mapped)."""

    def __init__(self, root: str, model: str, clip: str):
        self.dir = os.path.join(root, model, clip)
        with open(os.path.join(self.dir, "clip.json")) as fh:
            self.meta = json.load(fh)
        self.by_index = {f["frame_index"]: f for f in self.meta["frames"]}

    @property
    def frame_indices(self) -> list[int]:
        return [f["frame_index"] for f in self.meta["frames"]]

    @property
    def native_kind(self) -> str:
        return self.meta["native_kind"]

    def _stem(self, frame_index: int) -> str:
        return os.path.join(self.dir, f"f{frame_index:06d}")

    def load_native(self, frame_index: int):
        return np.load(self._stem(frame_index) + "_native.npy", mmap_mode="r")

    def load_valid(self, frame_index: int):
        return np.load(self._stem(frame_index) + "_valid.npy", mmap_mode="r")

    def load_range(self, frame_index: int):
        p = self._stem(frame_index) + "_range.npy"
        return np.load(p, mmap_mode="r") if os.path.exists(p) else None

    def load_conf(self, frame_index: int):
        p = self._stem(frame_index) + "_conf.npy"
        return np.load(p, mmap_mode="r") if os.path.exists(p) else None

    def load_aux(self, frame_index: int, name: str):
        p = f"{self._stem(frame_index)}_{name}.npy"
        return np.load(p, mmap_mode="r") if os.path.exists(p) else None

    def K(self, frame_index: int):
        k = self.by_index[frame_index].get("K")
        return None if k is None else np.asarray(k, dtype=np.float64)


def exists(root: str, model: str, clip: str) -> bool:
    return os.path.exists(os.path.join(root, model, clip, "clip.json"))
