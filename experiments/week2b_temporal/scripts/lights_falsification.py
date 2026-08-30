"""How much corrected-only flicker can the metric still see on `lights`?

EXPLORATORY (Week 2 Phase 2B, brief section 20). The artificial-light clip is
the mandatory falsification target. `run_temporal_eval.py` already shows that
the bounded global gain/bias model explains almost none of its residual and
that the clip is labelled `illumination-confounded`. This script asks the
question that label is actually making a claim about:

    if a restoration DID pump colour on this clip, at what amplitude would
    the metric notice?

Method: take the real footage, synthesise a corrected sequence that is the
input with an alternating red-channel gain of (1 +/- a), and sweep a. The
input is untouched, so correspondence and the illumination fit are identical
across the whole sweep — which is also why the flow can be computed once and
reused (see CachedBackend; the cache is bounded to this one clip's pairs).

Run on `lights` and on `murky_shark` as a NOT-confounded control, so the
sensitivity numbers can be read against each other.

    experiments/week2a_flow/.venv-flow/bin/python \
        -m experiments.week2b_temporal.scripts.lights_falsification --overwrite
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

_REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "..", "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from uw.flow import OpticalFlowBackend  # noqa: E402
from uw.io import load  # noqa: E402
from uw.metrics import evaluate_temporal  # noqa: E402
from uw.searaft import SeaRaftBackend  # noqa: E402
from uw.types import Frame  # noqa: E402

WINDOW_FRAMES = 41
WINDOW_OFFSET = 14
ANCHORS = (16, 18, 20)
LAGS = (1, 8)
AMPLITUDES = (0.0, 0.02, 0.05, 0.10, 0.20)
CLIPS = ("lights", "murky_shark")


class CachedBackend(OpticalFlowBackend):
    """Memoises flow for one clip's (t, t1) pairs. Bounded and deliberate.

    Legitimate here and only here: every amplitude in the sweep shares the
    same ORIGINAL sequence, so the correspondence is provably identical and
    recomputing it would measure the same thing five times. The cache holds
    at most len(ANCHORS) * len(LAGS) * 2 fields for one clip and is dropped
    between clips — `evaluate_temporal` itself caches nothing.
    """

    def __init__(self, inner):
        self.inner = inner
        self.name = inner.name
        self._cache = {}
        self.inferences = 0

    def describe(self):
        return self.inner.describe()

    def clear(self):
        self._cache.clear()

    def estimate(self, frames, index_t, index_t1):
        key = (index_t, index_t1)
        if key not in self._cache:
            self._cache[key] = self.inner.estimate(frames, index_t, index_t1)
            self.inferences += 1
        return self._cache[key]


def red_flicker(frames, amplitude):
    """Corrected-only red pumping: the input is untouched, the output is not."""
    out = []
    for i, f in enumerate(frames):
        img = f.image.copy()
        img[..., 0] *= (1.0 + amplitude) if i % 2 else (1.0 - amplitude)
        out.append(Frame(image=img, metadata=dict(f.metadata)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="mps")
    ap.add_argument("--out", default="outputs/temporal_metric/lights_falsification.json")
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    with open(os.path.join(_REPO, "experiments/week2a_flow/excerpts.json")) as f:
        excerpts = json.load(f)["clips"]

    backend = CachedBackend(SeaRaftBackend(device=args.device))
    report = {
        "question": ("at what corrected-only red-flicker amplitude does the "
                     "metric notice, on a confounded clip vs a clean one?"),
        "backend": backend.describe(),
        "amplitudes": list(AMPLITUDES), "lags": list(LAGS),
        "anchors_local": list(ANCHORS), "clips": {},
    }

    for name in CLIPS:
        info = excerpts[name]
        start = max(0, min(int(info["selected_excerpt_start"]) - WINDOW_OFFSET,
                           int(info["frame_count"]) - WINDOW_FRAMES))
        frames = list(load(os.path.join(_REPO, info["path"]),
                           start=start, count=WINDOW_FRAMES))
        backend.clear()
        rows = []
        print(f"\n=== {name} frames {start}..{start + WINDOW_FRAMES - 1} ===")
        for amp in AMPLITUDES:
            result = evaluate_temporal(
                frames, red_flicker(frames, amp), backend,
                lags=LAGS, anchors=ANCHORS,
            )
            for lag in result.lags:
                rows.append({
                    "amplitude": amp, "lag": lag.lag,
                    "raw_warp": lag.raw_warp,
                    "illumination_aware_warp": lag.illumination_aware_warp,
                    "temporal_delta_e": lag.temporal_delta_e,
                    "input_raw_warp": lag.input_raw_warp,
                    "input_illumination_aware_warp": lag.input_illumination_aware_warp,
                    "input_temporal_delta_e": lag.input_temporal_delta_e,
                    "valid_fraction": lag.valid_fraction,
                    "illumination_gain": lag.illumination.gain,
                    "illumination_bias": lag.illumination.bias,
                    "illumination_confounded": lag.illumination_confounded,
                    "status": lag.status,
                })
        # Rises are measured against the amplitude-0 row of the same lag.
        base = {r["lag"]: r for r in rows if r["amplitude"] == 0.0}
        for r in rows:
            b = base[r["lag"]]
            r["raw_rise_vs_no_flicker"] = r["raw_warp"] / b["raw_warp"]
            r["illum_aware_rise_vs_no_flicker"] = (
                r["illumination_aware_warp"] / b["illumination_aware_warp"])
            r["delta_e_rise_vs_no_flicker"] = (
                r["temporal_delta_e"] / b["temporal_delta_e"])
            print(f"  a={r['amplitude']:.2f} @{r['lag']}: raw {r['raw_warp']:.6f} "
                  f"({r['raw_rise_vs_no_flicker']:.3f}x)  "
                  f"illum {r['illumination_aware_warp']:.6f} "
                  f"({r['illum_aware_rise_vs_no_flicker']:.3f}x)  "
                  f"dE {r['temporal_delta_e']:.3f} "
                  f"({r['delta_e_rise_vs_no_flicker']:.3f}x)  "
                  f"{'CONFOUNDED' if r['illumination_confounded'] else 'ok'}")
        report["clips"][name] = {
            "source": info["path"],
            "frame_range": [start, start + WINDOW_FRAMES - 1],
            "rows": rows,
        }
        print(f"  ({backend.inferences} inferences so far; cache holds "
              f"{len(backend._cache)} fields)")

    path = os.path.join(_REPO, args.out)
    if os.path.exists(path) and not args.overwrite:
        raise FileExistsError(f"{path!r} exists; pass --overwrite")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
