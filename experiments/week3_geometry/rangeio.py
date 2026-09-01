"""Week 3 Phase 3A — the common per-clip range product on disk.

EXPLORATORY. Not part of the `uw` package. Pure numpy, so the same writer is
importable from every isolated model venv without dragging anything else in.

The layout is `PLAN.md`'s "Common output representation", written the way
`CLAUDE.md` invariant 9 requires: per-frame `(H,W)` fields go to their own
memory-mappable `.npy` shard AS EACH FRAME IS PRODUCED, never accumulated into
one full-clip array, and readers take one frame at a time via `mmap_mode="r"`.
The small per-clip quantities live in a single JSON sidecar.

    <root>/<config>/<clip>/
        clip.json                    provenance, conventions, per-frame index
        f000008_range.npy            (H,W) float32  range_along_ray
        f000008_valid.npy            (H,W) bool
        f000008_conf.npy             (H,W) float32  (absent if the model emits none)

`water_path_length` is `PLAN.md`'s canonical field. Every central and learned
model in this bakeoff emits a central-camera quantity, so what is stored is
`range_along_ray` plus an explicit `path_source` label saying the water path is
being approximated by it. Nothing here ever writes an unlabelled "range".
"""

from __future__ import annotations

import json
import os

import numpy as np


class RangeWriter:
    """Streams one clip's per-frame range fields to disk, one frame at a time."""

    def __init__(self, root: str, config: str, clip: str, overwrite: bool = False):
        self.dir = os.path.join(root, config, clip)
        if os.path.exists(os.path.join(self.dir, "clip.json")) and not overwrite:
            raise SystemExit(f"refusing to overwrite {self.dir!r} (pass --overwrite)")
        os.makedirs(self.dir, exist_ok=True)
        self.config = config
        self.clip = clip
        self.frames: list[dict] = []

    def add_frame(self, frame_index: int, range_along_ray: np.ndarray,
                  valid: np.ndarray, K=None, T_wc=None,
                  conf=None, path_source: str = "",
                  extra: dict | None = None) -> None:
        """Write one frame's fields and record its metadata. Nothing is retained."""
        r = np.asarray(range_along_ray, dtype=np.float32)
        v = np.asarray(valid, dtype=bool)
        if r.shape != v.shape:
            raise ValueError(f"range {r.shape} and valid {v.shape} differ")
        # Non-finite or non-positive range is never stored as a number: it is
        # demoted into the mask and written as NaN, so no consumer can read a
        # zero and believe the camera is touching the scene.
        bad = ~np.isfinite(r) | (r <= 0)
        v = v & ~bad
        r = np.where(v, r, np.nan).astype(np.float32)

        stem = os.path.join(self.dir, f"f{frame_index:06d}")
        np.save(stem + "_range.npy", r)
        np.save(stem + "_valid.npy", v)
        rec = {
            "frame_index": int(frame_index),
            "shape_hw": [int(r.shape[0]), int(r.shape[1])],
            "K": None if K is None else np.asarray(K, dtype=np.float64).tolist(),
            "T_wc": None if T_wc is None else np.asarray(T_wc, dtype=np.float64).tolist(),
            "path_source": path_source,
            "valid_fraction": float(v.mean()),
            "range_median": float(np.nanmedian(r)) if v.any() else float("nan"),
            "range_p05": float(np.nanpercentile(r, 5)) if v.any() else float("nan"),
            "range_p95": float(np.nanpercentile(r, 95)) if v.any() else float("nan"),
        }
        if conf is not None:
            c = np.asarray(conf, dtype=np.float32)
            np.save(stem + "_conf.npy", c)
            rec["has_conf"] = True
            fin = np.isfinite(c)
            rec["conf_median"] = float(np.median(c[fin])) if fin.any() else float("nan")
        else:
            rec["has_conf"] = False
        if extra:
            rec.update(extra)
        self.frames.append(rec)

    def close(self, provenance: dict, conventions: dict,
              scale_convention: str = "scale-ambiguous") -> str:
        payload = {
            "_comment": ("Week 3 Phase 3A per-clip range product. `range_along_ray` "
                         "is the Euclidean camera-centre-to-scene-point distance, "
                         "NOT planar z-depth. `path_source` states whether the "
                         "canonical water path length is measured or approximated "
                         "by it."),
            "config": self.config,
            "clip": self.clip,
            "scale_convention": scale_convention,
            "conventions": conventions,
            "provenance": provenance,
            "n_frames": len(self.frames),
            "frames": self.frames,
        }
        path = os.path.join(self.dir, "clip.json")
        with open(path, "w") as fh:
            json.dump(payload, fh, indent=2)
        return path


class RangeReader:
    """Reads a clip product back one frame at a time (memory-mapped)."""

    def __init__(self, root: str, config: str, clip: str):
        self.dir = os.path.join(root, config, clip)
        with open(os.path.join(self.dir, "clip.json")) as fh:
            self.meta = json.load(fh)
        self.by_index = {f["frame_index"]: f for f in self.meta["frames"]}

    @property
    def frame_indices(self) -> list[int]:
        return [f["frame_index"] for f in self.meta["frames"]]

    def load(self, frame_index: int, want_conf: bool = False):
        """(range, valid[, conf]) for one frame. Memory-mapped; never a full stack."""
        stem = os.path.join(self.dir, f"f{frame_index:06d}")
        r = np.load(stem + "_range.npy", mmap_mode="r")
        v = np.load(stem + "_valid.npy", mmap_mode="r")
        if not want_conf:
            return r, v
        cp = stem + "_conf.npy"
        c = np.load(cp, mmap_mode="r") if os.path.exists(cp) else None
        return r, v, c
