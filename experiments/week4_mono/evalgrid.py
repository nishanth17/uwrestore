"""Week 4A — the common evaluation grid, and how seven different grids reach it.

EXPLORATORY. Pure numpy. Imports `experiments/week3_geometry/geometry.py`, which
is also pure numpy and already unit-tested, rather than reimplementing
conventions the project has already fixed.

THE PROBLEM. The seven entrants do not agree on an output grid. On a 720x1280
source, `dav2_small`, `moge2_vitl`, `metricanything_pointmap` and
`foundationgeo_11` return the source resolution; `mapanything_n1` and `wat3r_n1`
return 294x518; `da3mono_large` returns 280x504. The Week-3 reference product
lives on 294x518. Comparing any two of those requires a correspondence, and
inventing one from resize arithmetic is precisely the silent convention error
this project keeps guarding against.

THE CONSTRUCTION.

    common evaluation grid, defined in SOURCE pixel coordinates
        |
        |  measured source -> model-grid affine map (from the S0 FOV audit,
        |  obtained by pushing markers through each model's OWN preprocessing)
        v
    each model's / the reference's native grid, sampled there

Everything is therefore expressed in the coordinates of the frozen extracted
frame, which is the one space all seven models and the reference genuinely
share. Nothing is resampled onto another model's grid, and no model is
privileged by having the comparison happen at its own resolution.

TWO DELIBERATE CONSERVATISMS, both inherited from Week 3.

* Sampling is bilinear but a sample is returned ONLY where all four neighbours
  are valid and finite. A sample whose 2x2 neighbourhood touches a hole comes
  back invalid rather than being filled from the valid side, because filling
  smears the far side of an occlusion boundary into the near side — and M-4
  measures boundary localisation.

* A source pixel that falls outside a model's grid is INVALID for that model,
  not extrapolated. That is how Wat3R's 44 % portrait FOV loss propagates into
  the evaluation honestly: those pixels simply have no Wat3R prediction.

The evaluation grid is the source downsampled by `EVAL_DOWNSAMPLE`. That is a
sampling density, not a resolution reduction of anyone's output: each grid point
samples every field at the same source location, at full sub-pixel precision.
"""

from __future__ import annotations

import json
import os

import numpy as np

from experiments.week3_geometry import geometry as g3
from experiments.week4_mono import common

#: Source-pixel stride between evaluation samples. 4 gives 320x180 = 57 600
#: samples per frame, which is ample for every metric here (M-5 samples pairs,
#: M-3 works on a lattice, M-1/M-2/M-6 are binned statistics) and keeps a
#: 288-frame, 7-model sweep tractable in memory and time.
EVAL_DOWNSAMPLE = 4


def eval_grid(source_hw: tuple[int, int], downsample: int = EVAL_DOWNSAMPLE):
    """(uv, eval_hw) — the source-pixel coordinates of every evaluation sample.

    Sample k of the downsampled grid sits at the CENTRE of the corresponding
    source block, i.e. `u = d*j + (d-1)/2`. That is `scale_intrinsics`' pixel
    convention run backwards, so an intrinsics matrix carried onto this grid by
    `K_source_to_eval` stays consistent with the samples.
    """
    h, w = source_hw
    d = int(downsample)
    eh, ew = h // d, w // d
    off = (d - 1) / 2.0
    us = d * np.arange(ew, dtype=np.float64) + off
    vs = d * np.arange(eh, dtype=np.float64) + off
    uu, vv = np.meshgrid(us, vs)
    uv = np.stack([uu.ravel(), vv.ravel()], axis=1)
    return uv, (eh, ew)


class GridMap:
    """A measured affine map from SOURCE pixels onto one model's output grid.

    `u_model = u_scale * u_source + u_offset`, and likewise for v. These
    coefficients are never derived from documentation: they come from the S0
    FOV audit, which pushed 25 marker images through the model's own
    preprocessing and fitted where the markers landed. The stored maximum
    residual says how well an affine describes the mapping; all seven came out
    sub-pixel.
    """

    def __init__(self, u_scale, u_offset, v_scale, v_offset, grid_hw,
                 source_hw, max_residual_px=float("nan"), origin=""):
        self.u_scale = float(u_scale)
        self.u_offset = float(u_offset)
        self.v_scale = float(v_scale)
        self.v_offset = float(v_offset)
        self.grid_hw = tuple(int(x) for x in grid_hw)
        self.source_hw = tuple(int(x) for x in source_hw)
        self.max_residual_px = float(max_residual_px)
        self.origin = origin

    @classmethod
    def identity(cls, source_hw, origin="identity"):
        return cls(1.0, 0.0, 1.0, 0.0, source_hw, source_hw, 0.0, origin)

    def apply(self, uv: np.ndarray) -> np.ndarray:
        uv = np.asarray(uv, dtype=np.float64)
        return np.stack([self.u_scale * uv[:, 0] + self.u_offset,
                         self.v_scale * uv[:, 1] + self.v_offset], axis=1)

    def to_dict(self) -> dict:
        return {"u_scale": self.u_scale, "u_offset": self.u_offset,
                "v_scale": self.v_scale, "v_offset": self.v_offset,
                "grid_hw": list(self.grid_hw), "source_hw": list(self.source_hw),
                "max_residual_px": self.max_residual_px, "origin": self.origin}

    def __repr__(self):
        return (f"GridMap(u={self.u_scale:.6f}x+{self.u_offset:.3f}, "
                f"v={self.v_scale:.6f}x+{self.v_offset:.3f}, grid={self.grid_hw}, "
                f"src={self.source_hw}, origin={self.origin!r})")


def _orientation_key(source_hw) -> str:
    return f"{int(source_hw[0])}x{int(source_hw[1])}"


def load_model_gridmap(model: str, source_hw, s0_dir: str | None = None) -> GridMap:
    """The measured source->grid map for one model at one source orientation."""
    s0_dir = s0_dir or os.path.join(common.OUTPUTS, "s0")
    with open(os.path.join(s0_dir, f"{model}.json")) as fh:
        rec = json.load(fh)
    fa = rec.get("fov_audit", {}).get(_orientation_key(source_hw))
    if not fa or not fa.get("measured"):
        raise SystemExit(f"no measured FOV audit for {model} at {_orientation_key(source_hw)}")
    return GridMap(fa["u_scale"], fa["u_offset"], fa["v_scale"], fa["v_offset"],
                   fa["model_grid_hw"], source_hw,
                   max(fa["u_max_abs_residual_px"], fa["v_max_abs_residual_px"]),
                   origin=f"S0 fov_audit/{model}")


def load_reference_gridmap(source_hw, week3_maps: str | None = None,
                           family: str = "mapanything") -> GridMap:
    """The source->grid map for the WEEK-3 reference product.

    Taken from Week 3's own `preprocess_maps.json` rather than re-measured,
    because that file is the authoritative record of how the persisted
    reference product was produced. `s2_ambiguity` cross-checks it against this
    session's independent S0 measurement of the same preprocessing code; the
    two agreeing is evidence the reference product is being read on the grid it
    was written on.
    """
    week3_maps = week3_maps or os.path.join(common.W3, "outputs", "preprocess_maps.json")
    with open(week3_maps) as fh:
        maps = json.load(fh)
    m = maps[family][_orientation_key(source_hw)]
    return GridMap(m["u_scale"], m["u_offset"], m["v_scale"], m["v_offset"],
                   m["model_grid_hw"], source_hw,
                   max(m["u_max_abs_residual_px"], m["v_max_abs_residual_px"]),
                   origin=f"week3 preprocess_maps/{family}")


def sample(field: np.ndarray, valid: np.ndarray, uv_source: np.ndarray,
           gmap: GridMap):
    """Sample one native-grid field at the evaluation grid's source coordinates.

    Returns (values, ok). `ok` is False outside the model's grid and anywhere
    the 2x2 neighbourhood is not fully valid.
    """
    uvm = gmap.apply(uv_source)
    return g3.sample_at_observations(np.asarray(field), np.asarray(valid), uvm)


def sample_vector(field: np.ndarray, valid: np.ndarray, uv_source: np.ndarray,
                  gmap: GridMap):
    """Same, for an (H,W,C) field. A sample is ok only if EVERY channel is ok."""
    field = np.asarray(field)
    outs, oks = [], None
    for c in range(field.shape[-1]):
        v, o = sample(field[..., c], valid, uv_source, gmap)
        outs.append(v)
        oks = o if oks is None else (oks & o)
    return np.stack(outs, axis=-1), oks


def K_source_to_eval(K_grid: np.ndarray, gmap: GridMap,
                     downsample: int = EVAL_DOWNSAMPLE) -> np.ndarray:
    """Carry an intrinsics matrix from a model's own grid onto the evaluation grid.

    The composition is: eval index -> source pixel (`u = d*j + (d-1)/2`) ->
    model grid (`gmap`). So

        u_grid = (u_scale * d) * j + (u_scale * (d-1)/2 + u_offset)
               = A * j + B

    and an intrinsics expressed in grid pixels becomes, in evaluation-grid
    pixels, `fx' = fx / A`, `cx' = (cx - B) / A`.

    This is how M-3's normals and M-6's radius get ONE camera shared by every
    model, so that a difference between two models is a difference in geometry
    rather than a difference in whose focal was used to lift it.
    """
    d = float(downsample)
    K = np.asarray(K_grid, dtype=np.float64).copy()
    A_u = gmap.u_scale * d
    B_u = gmap.u_scale * (d - 1.0) / 2.0 + gmap.u_offset
    A_v = gmap.v_scale * d
    B_v = gmap.v_scale * (d - 1.0) / 2.0 + gmap.v_offset
    K[0, 0] /= A_u
    K[0, 1] /= A_u
    K[1, 1] /= A_v
    K[0, 2] = (K[0, 2] - B_u) / A_u
    K[1, 2] = (K[1, 2] - B_v) / A_v
    return K


def lift_to_xyz(range_field: np.ndarray, K_eval: np.ndarray, eval_hw) -> np.ndarray:
    """(H,W,3) camera-frame points from a RANGE field and the shared eval camera.

    Range, not z-depth: the point is `range * unit_ray`. Using z-depth here
    would silently reintroduce the secant error the whole pipeline is careful
    about, and M-3's normals would inherit it.
    """
    h, w = eval_hw
    dirs = g3.ray_directions_from_K(np.asarray(K_eval, dtype=np.float64), h, w,
                                    normalize=True)
    return dirs * np.asarray(range_field, dtype=np.float64).reshape(h, w, 1)


def radius_map(eval_hw) -> np.ndarray:
    """(H,W) normalised image radius from the principal point, for M-6."""
    h, w = eval_hw
    uu, vv = np.meshgrid(np.arange(w, dtype=np.float64), np.arange(h, dtype=np.float64))
    uv = np.stack([uu.ravel(), vv.ravel()], axis=1)
    return g3.image_radius(uv, (h, w)).reshape(h, w)


class ReferenceClip:
    """One clip of the Week-3 persisted range product, read on the evaluation grid.

    THE REFERENCE IS A PROVISIONAL MULTI-VIEW HYPOTHESIS, NOT GROUND TRUTH
    (`MONO_DEPTH_FREEZE.md` 7). Agreement with it means consistency with the
    current Week-3 hypothesis. This class exists to make that comparison
    well-posed, not to make it authoritative.
    """

    def __init__(self, clip: str, config: str | None = None,
                 downsample: int = EVAL_DOWNSAMPLE):
        from experiments.week3_geometry.rangeio import RangeReader
        self.clip = clip
        self.config = config or common.REFERENCE_CONFIG
        self.reader = RangeReader(common.W3_RANGE_ROOT, self.config, clip)
        self.source_hw = common.clip_source_hw(clip)
        self.downsample = downsample
        self.uv, self.eval_hw = eval_grid(self.source_hw, downsample)
        self.gmap = load_reference_gridmap(self.source_hw)
        self.radius = radius_map(self.eval_hw)

    @property
    def frame_indices(self):
        return self.reader.frame_indices

    def K_eval(self, frame_index: int) -> np.ndarray:
        K = self.reader.by_index[frame_index].get("K")
        if K is None:
            raise SystemExit(f"reference frame {frame_index} has no K")
        return K_source_to_eval(np.asarray(K, dtype=np.float64), self.gmap,
                                self.downsample)

    def load(self, frame_index: int, want_conf: bool = False):
        """(range, valid[, conf]) on the evaluation grid, shaped (H,W)."""
        got = self.reader.load(frame_index, want_conf=want_conf)
        r, v = got[0], got[1]
        vals, ok = sample(np.asarray(r), np.asarray(v), self.uv, self.gmap)
        h, w = self.eval_hw
        vals = np.where(ok, vals, np.nan).reshape(h, w)
        ok = ok.reshape(h, w)
        if not want_conf:
            return vals, ok
        c = got[2]
        if c is None:
            return vals, ok, None
        cv, cok = sample(np.asarray(c), np.asarray(v), self.uv, self.gmap)
        return vals, ok, np.where(cok, cv, np.nan).reshape(h, w)
