"""Inspect a third-party checkpoint without running it.

EXPLORATORY. Main project venv has no torch, so this runs in `.venv-vggt`.

Used for the Phase 3A release gate: a repository can advertise pretrained
weights while shipping no code path that can consume them. This reports what a
checkpoint actually CONTAINS — file identity, container structure, state-dict key
prefixes and tensor shapes — so the question "do the released weights correspond
to the claimed model?" is answered from the artifact rather than from the README.

Loads with `weights_only=True` so no pickled code from an untrusted checkpoint is
executed; falls back only if that fails, and says so loudly.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os

import torch


def sha256(path: str, limit_mb: int = 0) -> str:
    h = hashlib.sha256()
    n = 0
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
            n += len(chunk)
            if limit_mb and n > limit_mb * (1 << 20):
                break
    return h.hexdigest()


def describe(obj, depth=0, max_items=40):
    if isinstance(obj, dict):
        return {"type": "dict", "n_keys": len(obj), "keys": list(obj)[:max_items]}
    if isinstance(obj, (list, tuple)):
        return {"type": type(obj).__name__, "len": len(obj)}
    if torch.is_tensor(obj):
        return {"type": "tensor", "shape": list(obj.shape), "dtype": str(obj.dtype)}
    return {"type": type(obj).__name__, "repr": repr(obj)[:120]}


def prefix_histogram(sd, levels=(1, 2)):
    out = {}
    for lv in levels:
        c = collections.Counter(".".join(k.split(".")[:lv]) for k in sd)
        out[f"level_{lv}"] = c.most_common(40)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--path", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--expect-prefixes", nargs="*", default=[],
                    help="module names the claimed architecture should contain")
    args = ap.parse_args()

    st = os.stat(args.path)
    report = {
        "file": os.path.basename(args.path),
        "abspath": os.path.abspath(args.path),
        "size_bytes": st.st_size,
        "size_mb": round(st.st_size / 1e6, 2),
        "sha256": sha256(args.path),
    }

    safe = True
    try:
        obj = torch.load(args.path, map_location="cpu", weights_only=True)
    except Exception as e:
        safe = False
        report["weights_only_load_error"] = f"{type(e).__name__}: {e}"[:400]
        obj = torch.load(args.path, map_location="cpu", weights_only=False)
    report["loaded_with_weights_only"] = safe
    report["top_level"] = describe(obj)

    # Find the state dict, whatever the container calls it.
    sd, sd_key = None, None
    if isinstance(obj, dict):
        if all(torch.is_tensor(v) for v in obj.values()) and obj:
            sd, sd_key = obj, "<root is the state dict>"
        else:
            report["top_level_entries"] = {k: describe(v) for k, v in
                                           list(obj.items())[:40]}
            for k in ("state_dict", "model", "model_state_dict", "net",
                      "module", "weights"):
                if k in obj and isinstance(obj[k], dict):
                    sd, sd_key = obj[k], k
                    break
            if sd is None:
                for k, v in obj.items():
                    if isinstance(v, dict) and v and all(torch.is_tensor(x)
                                                         for x in v.values()):
                        sd, sd_key = v, k
                        break
    if sd is None:
        report["state_dict"] = "NOT FOUND — the container holds no tensor dict"
        print(json.dumps(report, indent=2))
        return 0

    report["state_dict_key"] = sd_key
    report["n_tensors"] = len(sd)
    report["n_parameters"] = int(sum(v.numel() for v in sd.values()
                                     if torch.is_tensor(v)))
    dts = collections.Counter(str(v.dtype) for v in sd.values() if torch.is_tensor(v))
    report["dtypes"] = dict(dts)
    report["prefix_histogram"] = prefix_histogram(sd)
    report["first_20_keys"] = list(sd)[:20]
    report["last_10_keys"] = list(sd)[-10:]
    if args.expect_prefixes:
        found = {}
        for p in args.expect_prefixes:
            hits = [k for k in sd if p.lower() in k.lower()]
            found[p] = {"n_keys": len(hits), "example": hits[:3]}
        report["expected_module_presence"] = found

    print(json.dumps(report, indent=2))
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w") as fh:
            json.dump(report, fh, indent=2)
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
