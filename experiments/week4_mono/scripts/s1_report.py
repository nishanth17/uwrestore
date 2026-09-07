"""Aggregate the per-model S1 runs into the frozen S1 deliverables.

EXPLORATORY. Reads JSON only; imports no model stack.

    experiments/week4_mono/.venv-eval/bin/python \\
        -m experiments.week4_mono.scripts.s1_report --overwrite
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week4_mono import common  # noqa: E402
from experiments.week4_mono.scripts.s0_report import md_table  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--s1-dir", default=os.path.join(common.OUTPUTS, "s1"))
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    recs = {}
    for p in sorted(glob.glob(os.path.join(args.s1_dir, "*.json"))):
        with open(p) as fh:
            d = json.load(fh)
        recs[d["model"]] = d
    order = [m for m in common.MODELS if m in recs]

    payload = {
        "_comment": ("S1 — determinism, numerical noise floor, runtime and memory. The "
                     "floor recorded here bounds what any later stage is allowed to call "
                     "signal."),
        "stage": "S1",
        "models": recs,
        "noise_floors": {m: recs[m]["noise_floor"] for m in order},
        "bitwise_reproducible": {m: recs[m]["bitwise_reproducible"] for m in order},
    }
    out_json = os.path.join(common.RESULTS, "S1_results.json")
    common.write_json(out_json, payload, overwrite=args.overwrite)

    rows = []
    for m in order:
        r = recs[m]
        rows.append([
            m,
            "YES" if r["bitwise_reproducible"] else "no",
            f"{r['noise_floor']['floor_p99_rel']:.1e}",
            f"{r['runtime_seconds']['median']:.2f}",
            f"{r['runtime_seconds']['min']:.2f}-{r['runtime_seconds']['max']:.2f}",
            f"{r['load_seconds']:.1f}",
            f"{r['peak_rss_gb']:.1f}",
            ("-" if r.get("peak_mps_driver_gb") is None else f"{r['peak_mps_driver_gb']:.1f}"),
        ])

    total_median = sum(recs[m]["runtime_seconds"]["median"] for m in order)

    L = []
    A = L.append
    A("# S1 — determinism and numerical noise floor")
    A("")
    A("**Stage:** S1 of the frozen Week-4A sequence. **All seven models continue.**")
    A("")
    A("Everything after this stage is a difference — S3's residual against the Week-3")
    A("reference, S4's response to an appearance perturbation, S5's frame-to-frame")
    A("trajectory, S6's restoration delta. A difference is only evidence if it exceeds")
    A("the noise the instrument makes on its own, so each model was run repeatedly on")
    A("identical input under identical conditions and the spread of its own output")
    A("measured.")
    A("")
    A("Two repetitions, because they answer different questions: **within-process** (same")
    A("loaded model, called again) is the floor for S4/S5, where one process sweeps many")
    A("frames; **across-process** (fresh process, fresh weight load, fresh MPS context) is")
    A("the floor for comparing products persisted on different days.")
    A("")
    A("Subset: the middle frame of `wreck_07` (easy, high texture), `wreck_05` (hard, low")
    A("texture), `cenote_01` (widest near/far span) and `wreck_01` (PORTRAIT). Three")
    A("within-process repeats plus two independent processes each. FREEZE S1 explicitly")
    A("does not ask for the 288-frame set here, and it would not answer this question")
    A("any better.")
    A("")
    A("## Result")
    A("")
    A(md_table(rows, ["model", "bitwise", "p99 rel floor", "median s", "min-max s",
                      "load s", "peak RSS GB", "peak MPS GB"]))
    A("")
    A("**Every model is bitwise reproducible, within process and across processes, on MPS")
    A("in float32. The measured noise floor is exactly zero for all seven** — identical")
    A("valid masks, identical fields, byte for byte, on all four frames.")
    A("")
    A("That is a stronger result than the freeze required, and it is worth being precise")
    A("about what it does and does not license.")
    A("")
    A("**It does license:** reading any nonzero downstream difference as attributable to")
    A("the thing that was changed — a view count, an appearance perturbation, a different")
    A("frame, an ablated field — rather than to run-to-run variation. There is no")
    A("stochastic floor to subtract, and no `>= floor` filter is needed anywhere in")
    A("S3-S6.")
    A("")
    A("**It does not license** treating an arbitrarily small difference as *important*.")
    A("Zero run-to-run noise is a statement about the estimator's determinism, not about")
    A("its sensitivity, and three further floors sit above it and are measured where they")
    A("arise, not here:")
    A("")
    A("- the **8-bit PNG quantisation floor**, which every S4 perturbation passes through,")
    A("  because perturbed inputs are written to disk before inference;")
    A("- the **reference's own uncertainty**, which Week 3 measured and which is large on")
    A("  exactly the low-texture clips — whole-pipeline reruns moved `wreck_05` by 2.1-6.5 %")
    A("  median while `wreck_07` moved 0.01 %;")
    A("- the **restoration sensitivity budget** from Week 3 stage 7 (31 % at 1 m, 12 % at")
    A("  3 m, 8.5 % at 8 m), which is what makes a range error consequential rather than")
    A("  merely nonzero.")
    A("")
    A("The reference floor is the binding one. A monocular-vs-Week-3 disagreement of a few")
    A("percent on `wreck_05` says as much about the reference as about the model, and S3")
    A("reports it that way.")
    A("")
    A("## Why it came out zero")
    A("")
    A("No sampling, no dropout, no stochastic augmentation: every model runs `eval()` under")
    A("`no_grad`/`inference_mode`. Autocast is off everywhere — MPS supports only bf16 and")
    A("fp16 autocast, so the fp32 autocast blocks inside MoGe and FoundationGeo are no-ops")
    A("and warn as much, and both MoGe's `use_fp16=True` and FoundationGeo's fp16 default")
    A("were explicitly overridden to False. That override is the reason this table is full")
    A("of zeros; half precision would have put a stochastic floor under every later delta.")
    A("It costs runtime, and the project's standing rule since Week 3 is that a measurement")
    A("instrument must be reproducible before it is fast.")
    A("")
    A("## Runtime and memory budget for the stages that follow")
    A("")
    A(f"Median per-frame inference across all seven models totals **{total_median:.1f} s**, so one")
    A(f"full 288-frame pass costs roughly **{total_median * 288 / 60:.0f} minutes** of pure inference for the")
    A("whole field — S3 is affordable at full scale, which is what the freeze requires of it.")
    A("")
    A("Peak RSS splits the field in two: the two ViT-G-class multi-view architectures")
    A("(`mapanything_n1` 9.6 GB, `wat3r_n1` 9.2 GB) cost about three times the five")
    A("monocular models (0.8-2.9 GB). On a 24 GB machine that rules out co-resident")
    A("models and confirms the Week-3 rule this bakeoff already follows: one model per")
    A("process, with process exit as the authoritative MPS cleanup boundary.")
    A("")
    A("`dav2_small` is the cheapest entrant by a wide margin — 0.19 s and 0.8 GB, roughly")
    A("11x faster and 12x smaller than MapAnything. If it survives S3 on geometry, that")
    A("ratio becomes a real deployment argument rather than a footnote.")

    out_md = os.path.join(common.RESULTS, "S1_DETERMINISM.md")
    common.refuse_clobber(out_md, args.overwrite)
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    with open(out_md, "w") as fh:
        fh.write("\n".join(L) + "\n")
    print(f"[S1-report] {len(order)} models -> {os.path.relpath(out_md, REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
