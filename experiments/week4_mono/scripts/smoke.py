"""Bring-up smoke test: load one backend, run it on one image, print what came back.

EXPLORATORY. Runs inside the backend's own venv. This is integration bring-up,
NOT S0 — it produces no persisted result and decides nothing. S0 is
`s0_semantics.py`.

    experiments/week4_mono/.venv-mono/bin/python \
        -m experiments.week4_mono.scripts.smoke --model dav2_small
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week4_mono import backends, common  # noqa: E402


def describe(name, a):
    a = np.asarray(a)
    fin = np.isfinite(a)
    lo = float(a[fin].min()) if fin.any() else float("nan")
    hi = float(a[fin].max()) if fin.any() else float("nan")
    print(f"    {name:28s} shape={str(a.shape):20s} dtype={a.dtype} "
          f"finite={fin.mean():.4f} range=[{lo:.4g}, {hi:.4g}]")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True, choices=backends.keys())
    ap.add_argument("--image", default=None)
    ap.add_argument("--device", default="mps")
    args = ap.parse_args()

    img = args.image or common.frame_path("wreck_07", common.frame_indices("wreck_07")[0])
    print(f"[smoke] model={args.model} image={os.path.relpath(img, REPO_ROOT)}")
    print(f"[smoke] env={common.env_report()}")

    common.seed_everything()
    cls = backends.get(args.model)
    be = cls(device=args.device)
    try:
        be.load()
    except Exception:
        traceback.print_exc()
        print("[smoke] LOAD FAILED")
        return 2
    print(f"[smoke] loaded in {be.load_seconds:.1f}s")

    try:
        out = be.infer(img)
    except Exception:
        traceback.print_exc()
        print("[smoke] INFER FAILED")
        return 3

    print(f"[smoke] native_kind={be.native_kind} range_rule={be.range_rule}")
    describe("native", out["native"])
    describe("valid", out["valid"])
    if out.get("canonical_range") is not None:
        describe("canonical_range", out["canonical_range"])
    else:
        print("    canonical_range              None (by design for this representation)")
    if out.get("conf") is not None:
        describe("conf", out["conf"])
    if out.get("K") is not None:
        print(f"    K=\n{np.asarray(out['K'])}")
    for k, v in (out.get("aux") or {}).items():
        describe(f"aux/{k}", v)
    print(f"[smoke] extra={out.get('extra')}")
    print(f"[smoke] peak_rss_gb={common.peak_rss_gb():.2f} mps_gb={common.mps_peak_gb():.2f}")
    print("[smoke] OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
