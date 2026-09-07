"""R2-3 SurGe S0 gate.  Official Python API (README lines 44-63), unchanged math.

Category B: device placement only (cpu, because NATTEN has no MPS backend and
the only CPU-capable official backend is `flex-fna`), and autocast dtype left
at the repo default float32 which torch disables on CPU with a warning.

`--gate-only` writes the record WITHOUT running inference. It exists because
inference on this machine does not fail -- it is killed, by the OS, with no
catchable exception, so the record could not otherwise be written at all. The
kill is a measurement and is carried in `runtime_gate.cpu_uncompiled_flex_measured`.
"""
import argparse, sys, json, gc
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import s0_common as C

import numpy as np, torch
from PIL import Image
sys.path.insert(0, str(C.ROUND2 / "vendor" / "surge" / "src"))
from surge import SurGe

DEV = "cpu"
LONG_SIDE = 1280


def load(p, long_side=LONG_SIDE):
    im = Image.open(p).convert("RGB")
    w0, h0 = im.size
    s = long_side / max(w0, h0)
    w, h = round(w0 * s), round(h0 * s)
    im = im.resize((w, h), Image.LANCZOS)
    a = np.asarray(im, dtype=np.float32) / 255.0
    return torch.from_numpy(a).permute(2, 0, 1)[None], (w0, h0), (w, h)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gate-only", action="store_true",
                    help="load the checkpoint and record the runtime gate, but do "
                         "not attempt inference (which the OS kills, uncatchably)")
    args = ap.parse_args()
    model = SurGe.from_pretrained("karimknaebel/surge-large").eval().to(DEV)
    nparam = sum(p.numel() for p in model.parameters())
    rec = {"model": "surge_large", "repo": "karimknaebel/surge-large",
           "impl_category": "B",
           "impl_category_notes": [
               "device placement: cpu (NATTEN exposes no MPS backend; "
               "natten.backends.choose_backend -> 'flex-fna' on cpu, "
               "NotImplementedError on mps)",
               "no model math, resolution, checkpoint or operator changes"],
           "license_code": "MIT (Microsoft), vendor/surge/LICENSE",
           "license_weights": "CC BY-NC 4.0 (per model card) -> research-only",
           "n_parameters": int(nparam),
           "n_neighborhood_attention_2d_blocks": 15,
           "runtime_gate": {
               "attention_operator": "natten 0.21.6 neighborhood_attention_generic "
                                     "(nad.py:359), kernel_size 9, 15 blocks over a "
                                     "4-level x2 upsampling pyramid whose base grid "
                                     "is set by num_tokens (max = 2802 -> 39x70, "
                                     "deepest level 624x1120)",
               "mps": "REFUSED by NATTEN. choose_backend raises NotImplementedError; "
                      "NATTEN_LOG_LEVEL=DEBUG gives verbatim: \"Can't run Flex "
                      "Attention; tensor is not on a CUDA, ROCm, or CPU device: mps\". "
                      "All CUTLASS/Hopper/Blackwell FNA backends are CUDA-only.",
               "cpu_compiled_flex": "REFUSED by NATTEN on two independent gates. "
                                    "(1) backends/configs/checks.py:695-699 -- "
                                    "\"Flex Attention (compiled) only supports CUDA "
                                    "devices with compute capability 70 or higher\" "
                                    "(utils/environment.py:61 gates on get_device_cc()). "
                                    "(2) checks.py:723-728 -- compiled flex accepts only "
                                    "FP16/BF16; FP32 is explicitly excluded. Enabling it "
                                    "would require overriding two library capability "
                                    "gates and/or dropping the model to half precision, "
                                    "and natten.allow_flex_compile() itself warns "
                                    "\"we cannot verify Flex's correctness in all "
                                    "scenarios ... your results may be affected "
                                    "significantly\". Not adopted: that is a "
                                    "numerically unverified attention-implementation "
                                    "change, which reference-implementation integrity "
                                    "forbids.",
               "cpu_uncompiled_flex": "the only NATTEN-sanctioned path on this machine; "
                                      "torch warns it 'will use an unfused implementation "
                                      "that materializes the full scores matrix'. "
                                      "In-model per-block cost at num_tokens=max: "
                                      "0.40-0.84 s at 39x70x1024, 6.0 s at 78x140x512, "
                                      "growing ~4x per pyramid level.",
               "conclusion": "see status/status_reason below",
           },
           "env": C.env_block(DEV, torch), "images": {}}

    # MEASURED, not estimated. `/usr/bin/time -l` on the full-resolution run of
    # the loop below, launched alone with nothing else competing for memory.
    rec["runtime_gate"]["cpu_uncompiled_flex_measured"] = {
        "command": ("/usr/bin/time -l round2/.venv-surge_large/bin/python -u "
                    "round2/scripts/s0_surge.py"),
        "input": "one 1280x720 frozen frame, the release default inference path "
                 "(model.infer(img) with no overrides)",
        "outcome": "KILLED by the OS before the first image completed",
        "wall_seconds": 931.53,
        "user_seconds": 361.77,
        "system_seconds": 805.29,
        "max_rss_bytes": 18477170688,
        "peak_memory_footprint_bytes": 148477076456,
        "page_reclaims": 211030822,
        "page_faults": 94722,
        "involuntary_context_switches": 12578078,
        "machine_ram_bytes": 24 * 1024 ** 3,
        "reading": ("system time exceeded user time 2.2x and the peak footprint reached "
                    "~138 GB on a 24 GB machine: the unfused flex path materialises the "
                    "full neighborhood-attention score matrix and the process spent most "
                    "of its life paging before jetsam killed it. Two earlier attempts "
                    "died the same way; the third was run alone to rule out contention."),
        "not_attempted_and_why": [
            "lowering the input long side below the frozen 1280 -- that is changing "
            "model input resolution merely to make memory fit, and §2 also forbids "
            "resampling the frozen footage",
            "natten.allow_flex_compile() + half precision -- a numerically unverified "
            "attention-implementation change, which the library itself warns about",
            "porting the CUDA FNA kernels to MPS, or substituting an unofficial "
            "implementation",
        ],
    }
    rec["status"] = "pending_cuda"
    rec["status_reason"] = (
        "SurGe's Neighborhood Attention has no backend that both runs on this machine "
        "and is numerically the released one. NATTEN refuses MPS outright and refuses "
        "compiled flex on two independent gates; the one sanctioned path, uncompiled "
        "CPU flex, was measured above to need ~138 GB of memory footprint and was "
        "killed by the OS at 931 s on a 24 GB machine.")
    rec["stopped_at"] = "S0 gate, first sanity inference -- no S1-S6 stage was entered"
    rec["environment_required"] = (
        "one CUDA GPU with compute capability >= 7.0, so NATTEN selects a fused FNA "
        "backend instead of materialising the score matrix")
    rec["to_resume"] = [
        "on a CUDA machine: pip install natten==0.21.6 built for that CUDA version",
        "round2/.venv-surge_large/bin/python round2/scripts/s0_surge.py   (S0 gate)",
        "then run_inference.py --model surge_large over the 288 frozen frames",
        "then the §18 thin-structure test at the wreck_07 crane lattice, which is "
        "where a LOCAL-SURFACE specialist is most likely to differ",
    ]
    rec["artifacts_needed"] = (
        "one native point map + depth + intrinsics per frame for the 288 frozen "
        "frames; plus the wreck_07 thin-structure subset")
    if args.gate_only:
        C.write("surge_large", rec)
        print("[s0-surge] gate-only: wrote pending_cuda record, no inference attempted")
        return

    for tag, path in C.SANITY:
        img, src_wh, run_wh = load(path)
        # Announce BEFORE the ~25-minute CPU inference, not only after it. Two
        # earlier runs of this script died silently with an empty log, and
        # without this line there was no way to tell "still on image 1" from
        # "never started".
        print(f"[s0-surge] START {tag} src={src_wh} run={run_wh}", flush=True)
        torch.manual_seed(0)
        with C.Timer() as t:
            out = model.infer(img.to(DEV))
        pts = out["points"][0].float().cpu().numpy()          # H,W,3
        dep = out["depth"][0].float().cpu().numpy()           # H,W
        K = out["intrinsics"][0].float().cpu().numpy()
        z = pts[..., 2]
        rng = np.linalg.norm(pts, axis=-1)
        fin = np.isfinite(dep) & np.isfinite(rng)
        rec["images"][tag] = {
            "path": str(path), "source_wh": src_wh, "run_wh": run_wh,
            "runtime_s": round(t.dt, 3), "rss_gb": round(C.rss_gb(), 3),
            "out_shape_points": list(pts.shape),
            "out_shape_depth": list(dep.shape),
            "intrinsics_normalized": K.tolist(),
            # decisive semantic test: which of z / ||p|| does `depth` equal?
            "max_abs_depth_minus_pointz": float(np.nanmax(np.abs(dep[fin] - z[fin]))),
            "max_abs_depth_minus_pointnorm": float(np.nanmax(np.abs(dep[fin] - rng[fin]))),
            "stats_depth": C.stats("depth", dep),
            "stats_range": C.stats("||points||", rng),
            "median_range_over_z": float(np.median(rng[fin] / np.maximum(z[fin], 1e-6))),
            "coverage_finite_frac": float(fin.mean()),
        }
        print(tag, rec["images"][tag]["runtime_s"], "s",
              "d-z", rec["images"][tag]["max_abs_depth_minus_pointz"],
              "d-|p|", rec["images"][tag]["max_abs_depth_minus_pointnorm"], flush=True)
        del out, pts, dep; gc.collect()

    C.write("surge_large", rec)


main()
