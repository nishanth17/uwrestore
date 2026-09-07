"""Shared S0 harness for Round-2 challengers.

Every challenger runs the SAME four fixed sanity images (BRIEF.md), records
runtime / memory / device, and dumps a per-model JSON under
round2/s0_agent/<model>/s0_smoke.json.  Nothing here touches Round-1 products.
"""
from __future__ import annotations

import json
import os
import platform
import resource
import time
from pathlib import Path

W4 = Path(__file__).resolve().parents[2]          # experiments/week4_mono
ROUND2 = W4 / "round2"
FRAMES = W4.parent / "week3_geometry" / "phase3a" / "outputs" / "frames"

SANITY = [
    ("ordinary",  FRAMES / "wreck_07" / "f000109.png"),
    ("difficult", FRAMES / "wreck_05" / "f000113.png"),
    ("portrait",  FRAMES / "wreck_01" / "f001855.png"),
    ("public",    W4 / "round1" / "vendor" / "FoundationGeo" / "demo" / "indoor.jpg"),
]


def rss_gb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 ** 3)


class Timer:
    def __enter__(self):
        self.t = time.perf_counter()
        return self

    def __exit__(self, *a):
        self.dt = time.perf_counter() - self.t


def env_block(device: str, torch_mod) -> dict:
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "torch": torch_mod.__version__,
        "device": device,
        "cuda_available": bool(torch_mod.cuda.is_available()),
        "mps_available": bool(getattr(torch_mod.backends, "mps", None)
                              and torch_mod.backends.mps.is_available()),
    }


def write(model: str, payload: dict) -> Path:
    out = ROUND2 / "s0_agent" / model
    out.mkdir(parents=True, exist_ok=True)
    p = out / "s0_smoke.json"
    p.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str))
    print(f"[S0] wrote {p}")
    return p


def stats(name, arr):
    import numpy as np
    a = np.asarray(arr, dtype="float64")
    fin = np.isfinite(a)
    d = {"name": name, "shape": list(a.shape), "dtype": str(np.asarray(arr).dtype),
         "finite_frac": float(fin.mean())}
    if fin.any():
        v = a[fin]
        d.update(min=float(v.min()), max=float(v.max()),
                 median=float(np.median(v)), mean=float(v.mean()))
    return d
