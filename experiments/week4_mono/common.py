"""Week 4A monocular bakeoff — the frozen experiment definition and shared helpers.

EXPLORATORY. Not part of the `uw` package. Pure standard library + numpy, so the
same module imports cleanly from every isolated model venv without dragging a
model stack along with it.

The authoritative specification is `MONO_DEPTH_FREEZE.md`. Anything here that
looks like a scientific choice (which clips, which frames, which reference) is a
transcription of that document, not a decision made in code.
"""

from __future__ import annotations

import json
import os
import platform
import resource
import subprocess
import sys
import time

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
W3 = os.path.join(REPO_ROOT, "experiments", "week3_geometry")
W4 = os.path.join(REPO_ROOT, "experiments", "week4_mono")

FRAMES_ROOT = os.path.join(W3, "outputs", "frames")
W3_RANGE_ROOT = os.path.join(W3, "outputs", "range")

#: The Week-3 persisted range product Week 4A compares against. It is a
#: PROVISIONAL MULTI-VIEW HYPOTHESIS, never ground truth (FREEZE §7).
REFERENCE_CONFIG = "D_mapanything"

OUTPUTS = os.path.join(W4, "outputs")
RESULTS = os.path.join(W4, "results")

# --------------------------------------------------------------------------
# Frozen primary bakeoff set — FREEZE "FROZEN VIDEO / FRAME SET"
# --------------------------------------------------------------------------

#: The six Week-3 development clips, in the order the freeze lists them.
CLIPS = [
    "wreck_07",         # high-texture arc; favourable/high-support geometry
    "wreck_05",         # lower-texture lateral glide; weak feature support
    "cenote_01",        # widest near/far range variation
    "swimthrough_02",   # ordinary reef / representative normal case
    "wreck_01",         # low-texture, near-planar, PORTRAIT orientation
    "wreck_03",         # dynamic diver; moving-object failure case
]

CLIP_ROLE = {
    "wreck_07": "high-texture arc / favourable geometry support",
    "wreck_05": "lower-texture lateral glide / weak geometry support",
    "cenote_01": "widest near/far range variation",
    "swimthrough_02": "ordinary reef / representative normal case",
    "wreck_01": "low-texture near-planar PORTRAIT orientation (FOV/orientation trap)",
    "wreck_03": "dynamic diver / moving-object and dynamic-scene failure",
}

N_FRAMES_PER_CLIP = 48
EXTRACTION_LONG_SIDE = 1280

# --------------------------------------------------------------------------
# Frozen candidate set — FREEZE §3 and §9. Order is the INTEGRATION order
# from the task specification, which is not a ranking.
# --------------------------------------------------------------------------

MODELS = [
    "mapanything_n1",
    "dav2_small",
    "moge2_vitl",
    "metricanything_pointmap",
    "wat3r_n1",
    "da3mono_large",
    "foundationgeo_11",
]

MODEL_CHECKPOINT = {
    "mapanything_n1": "facebook/map-anything-apache",
    "dav2_small": "depth-anything/Depth-Anything-V2-Small",
    "moge2_vitl": "Ruicheng/moge-2-vitl",
    "metricanything_pointmap": "yjh001/metricanything_student_pointmap",
    "wat3r_n1": "lsxi77777/Wat3R",
    "da3mono_large": "depth-anything/DA3MONO-LARGE",
    "foundationgeo_11": "mxliu-hku/FoundationGeo-1.1",
}

#: Which venv each backend must run in. One model per process; process exit is
#: the authoritative MPS cleanup boundary (the Week-3 rule).
MODEL_VENV = {
    "mapanything_n1": os.path.join(W3, ".venv-mapanything"),
    "dav2_small": os.path.join(W4, ".venv-mono"),
    "moge2_vitl": os.path.join(W4, ".venv-moge"),
    "metricanything_pointmap": os.path.join(W4, ".venv-moge"),
    "wat3r_n1": os.path.join(W3, ".venv-vggt"),
    "da3mono_large": os.path.join(W4, ".venv-mono"),
    "foundationgeo_11": os.path.join(W4, ".venv-mono"),
}

EVAL_VENV = os.path.join(W4, ".venv-eval")

#: Native representation declared by each model's own documentation. S0 VERIFIES
#: these empirically; nothing downstream may assume one that S0 did not confirm.
DECLARED_NATIVE = {
    "mapanything_n1": "depth_along_ray_metric",
    "dav2_small": "disparity_relative",
    "moge2_vitl": "pointmap_metric",
    "metricanything_pointmap": "pointmap_metric",
    "wat3r_n1": "pointmap",
    "da3mono_large": "depth_relative",
    "foundationgeo_11": "pointmap_metric",
}

# --------------------------------------------------------------------------
# Frame set access
# --------------------------------------------------------------------------


def frame_indices(clip: str) -> list[int]:
    """The 48 frozen Week-3 source frame indices for one clip, in order."""
    d = os.path.join(FRAMES_ROOT, clip)
    out = sorted(int(f[1:7]) for f in os.listdir(d) if f.endswith(".png"))
    return out


def frame_path(clip: str, index: int) -> str:
    return os.path.join(FRAMES_ROOT, clip, f"f{index:06d}.png")


def clip_source_hw(clip: str) -> tuple[int, int]:
    """(H, W) of the frozen extracted frames. `wreck_01` is portrait."""
    report = os.path.join(FRAMES_ROOT, "extraction_report.json")
    with open(report) as fh:
        h, w = json.load(fh)["clips"][clip]["extracted_shape_hw"]
    return int(h), int(w)


def verify_frozen_frames() -> dict:
    """Confirm the persisted Week-3 material is present and matches its report.

    A missing or altered frame set is a frozen-baseline change, which is a STOP
    condition, so this reports rather than repairs.
    """
    report_path = os.path.join(FRAMES_ROOT, "extraction_report.json")
    with open(report_path) as fh:
        report = json.load(fh)
    out = {"extraction": report["extraction"], "clips": {}, "ok": True}
    for clip in CLIPS:
        rec = report["clips"][clip]
        idx = frame_indices(clip)
        present = [i for i in idx if os.path.exists(frame_path(clip, i))]
        ref_dir = os.path.join(W3_RANGE_ROOT, REFERENCE_CONFIG, clip)
        ref_ok = os.path.exists(os.path.join(ref_dir, "clip.json"))
        n_ref = 0
        if ref_ok:
            with open(os.path.join(ref_dir, "clip.json")) as fh:
                n_ref = json.load(fh)["n_frames"]
        entry = {
            "n_frames_expected": N_FRAMES_PER_CLIP,
            "n_frames_present": len(present),
            "source_frame_indices_match": idx == rec["source_frame_indices"],
            "extracted_shape_hw": rec["extracted_shape_hw"],
            "orientation": "portrait" if rec["extracted_shape_hw"][0] > rec["extracted_shape_hw"][1] else "landscape",
            "reference_product_present": ref_ok,
            "reference_n_frames": n_ref,
        }
        entry["ok"] = (entry["n_frames_present"] == N_FRAMES_PER_CLIP
                       and entry["source_frame_indices_match"]
                       and ref_ok and n_ref == N_FRAMES_PER_CLIP)
        out["ok"] = out["ok"] and entry["ok"]
        out["clips"][clip] = entry
    return out


# --------------------------------------------------------------------------
# S0 sanity set — FREEZE / task "S0 semantics/runtime": four images only.
# --------------------------------------------------------------------------

S0_SANITY = [
    {"key": "ordinary_project", "clip": "wreck_07", "frame": None,
     "why": "ordinary project underwater frame, high texture, landscape"},
    {"key": "difficult_project", "clip": "wreck_05", "frame": None,
     "why": "difficult project underwater frame, low texture / hazy, landscape"},
    {"key": "portrait_project", "clip": "wreck_01", "frame": None,
     "why": "PORTRAIT/orientation-sensitive frame; Week 3 lost 10/25 FOV markers "
            "here in the VGGT family, so this is the preprocessing trap case"},
    {"key": "public_reference", "clip": None, "frame": None,
     "why": "public/reference image with independently documented semantics"},
]


def s0_sanity_items() -> list[dict]:
    """Resolve the sanity set to concrete image paths (middle frame of each clip)."""
    items = []
    for spec in S0_SANITY:
        item = dict(spec)
        if spec["clip"] is not None:
            idx = frame_indices(spec["clip"])
            fi = idx[len(idx) // 2]
            item["frame"] = fi
            item["path"] = frame_path(spec["clip"], fi)
        else:
            item["path"] = public_reference_image()
        items.append(item)
    return items


def public_reference_image() -> str:
    """A non-underwater image whose scene semantics are unambiguous by inspection.

    Vendored with the model repositories, so it needs no download and its
    provenance is recorded in the repo it came from.
    """
    for cand in [
        os.path.join(W4, "vendor", "FoundationGeo", "demo", "indoor.jpg"),
        os.path.join(W4, "vendor", "moge", "example_images"),
    ]:
        if os.path.isfile(cand):
            return cand
    raise FileNotFoundError("no vendored public reference image found")


# --------------------------------------------------------------------------
# Determinism / environment
# --------------------------------------------------------------------------

SEED = 0


def seed_everything(seed: int = SEED) -> None:
    import random
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch
        torch.manual_seed(seed)
        torch.use_deterministic_algorithms(False)  # MPS has no deterministic mode
    except Exception:
        pass


def env_report() -> dict:
    """Everything needed to tell an environment change from a code change."""
    rep = {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
    }
    try:
        import torch
        rep["torch"] = torch.__version__
        rep["mps_available"] = bool(torch.backends.mps.is_available())
        rep["mps_built"] = bool(torch.backends.mps.is_built())
        rep["cuda_available"] = bool(torch.cuda.is_available())
    except Exception as exc:
        rep["torch"] = f"unavailable: {exc}"
    try:
        rep["numpy"] = np.__version__
    except Exception:
        pass
    return rep


def peak_rss_gb() -> float:
    """Peak resident set size of this process, in GB (macOS reports bytes)."""
    ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return float(ru) / (1024 ** 3)


def mps_peak_gb() -> float:
    try:
        import torch
        return float(torch.mps.driver_allocated_memory()) / (1024 ** 3)
    except Exception:
        return float("nan")


class Timer:
    """Wall-clock accumulator with a dict view, so runtime lands in provenance."""

    def __init__(self):
        self.spans: dict[str, float] = {}
        self._t0 = None
        self._key = None

    def __call__(self, key: str):
        self._key = key
        return self

    def __enter__(self):
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        dt = time.perf_counter() - self._t0
        self.spans[self._key] = self.spans.get(self._key, 0.0) + dt
        return False


# --------------------------------------------------------------------------
# Output-file safety — CLAUDE.md invariant 7
# --------------------------------------------------------------------------


def refuse_clobber(path: str, overwrite: bool) -> None:
    if os.path.exists(path) and not overwrite:
        raise SystemExit(f"refusing to overwrite {path!r} (pass --overwrite)")


def write_json(path: str, payload, overwrite: bool = False) -> str:
    refuse_clobber(path, overwrite)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(payload, fh, indent=2, sort_keys=False, default=_json_default)
    os.replace(tmp, path)
    return path


def _json_default(o):
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.bool_,)):
        return bool(o)
    raise TypeError(f"not JSON serialisable: {type(o)}")


def run_in_venv(venv: str, module: str, args: list[str], env_extra: dict | None = None,
                capture: bool = False) -> subprocess.CompletedProcess:
    """Run `python -m <module> <args>` in an isolated venv, from the repo root."""
    env = dict(os.environ)
    env["PYTHONPATH"] = REPO_ROOT
    env.setdefault("TOKENIZERS_PARALLELISM", "false")
    if env_extra:
        env.update(env_extra)
    cmd = [os.path.join(venv, "bin", "python"), "-m", module, *args]
    return subprocess.run(cmd, cwd=REPO_ROOT, env=env,
                          capture_output=capture, text=True)
