"""Week 2 Phase 2C/2D — frozen-test-set baseline comparison.

Evaluates a bounded set of correction-stage configurations against the
frozen test set, reusing Phase 2B's EXACT excerpt geometry (same windows,
same anchors, same evaluation grid) so these numbers sit directly beside the
Phase 2B table in LOG.md rather than being a new, incomparable measurement.

Reuse (CLAUDE.md Phase 2C/2D "evaluation reuse across correction
configurations"): the original sequence is resized to the metric grid
EXACTLY ONCE per clip and that same list object is reused for every
configuration scored on that clip, wrapped in uw.flow.CachingFlowBackend.
`uw.metrics.evaluate_temporal`/`evaluate_temporal_pair` are untouched and
unaware this script exists — the reuse happens entirely on this side of the
OpticalFlowBackend interface. See _EVAL_ORIG_CACHE_NOTE below for the
equivalence check this script runs before trusting the cache.

Does NOT retune flow, illumination fitting, guards, or any Phase 2B
threshold. Does NOT add a new metric. This is the mechanical Phase 2C/2D
closer, not another empirical study (CLAUDE.md §25).

Run from the isolated flow interpreter (needs torch):
    experiments/week2a_flow/.venv-flow/bin/python \\
        experiments/week2c2d_baselines/scripts/run_baseline_eval.py \\
        [--json outputs/week2c2d_baselines/results.json] [--clip NAME]...
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from uw.cli import apply_pipeline  # noqa: E402
from uw.diagnostics import (  # noqa: E402
    aggregate_signal_diagnostics,
    correction_gain,
    out_of_range_fraction,
)
from uw.flow import CachingFlowBackend  # noqa: E402
from uw.io import load  # noqa: E402
from uw.metrics import (  # noqa: E402
    evaluate_temporal,
    metric_eval_size,
    prepare_temporal_pairs,
    resize_sequence_linear,
)
from uw.searaft import SeaRaftBackend  # noqa: E402

# Identical to Phase 2B's real-footage geometry (LOG.md, experiments/
# week2b_temporal/FINDINGS.md §9) — same clip, same start index, same
# 41-frame window, so a reader can set this session's numbers beside that
# table directly instead of re-deriving whether a difference is the
# baseline or the measurement.
CLIPS = {
    "swimthrough": ("data/testset/swimthrough/SWIMTHROUGH.MP4", 181, 41),
    "murky_eel": ("data/testset/murky/MURKYEEL.MP4", 636, 41),
    "murky_shark": ("data/testset/murky/MURKYSHARK.MP4", 0, 41),
    "lights": ("data/testset/lights/LIGHTNIGHTDIVE.MP4", 71, 41),
    "distance": ("data/testset/distance/DISTANCESHOT.MP4", 246, 41),
}

ANCHORS = (16, 18, 20)
LAGS = (1, 4, 8)
METRIC_LONG_SIDE = 960

# CLAUDE.md §24: "none / gray_world / white_patch / clahe / gray_world ->
# clahe / white_patch -> clahe". No default stack, no auto-combining
# gray_world with white_patch (they are competing global-WB assumptions).
CONFIGS = [
    ("none", []),
    ("gray_world", ["gray_world"]),
    ("white_patch", ["white_patch"]),
    ("clahe", ["clahe"]),
    ("gray_world_clahe", ["gray_world", "clahe"]),
    ("white_patch_clahe", ["white_patch", "clahe"]),
]


def _lag_summary(lag):
    d = dataclasses.asdict(lag)
    d.pop("pairs", None)  # per-pair arrays/records — not needed in the summary
    return d


def evaluate_clip(name: str, rel_path: str, start: int, count: int, alignment_robust: bool):
    path = REPO_ROOT / rel_path
    frames = list(load(str(path), profile="srgb", start=start, count=count))
    src_h, src_w = frames[0].image.shape[:2]
    eh, ew = metric_eval_size(src_h, src_w, METRIC_LONG_SIDE)

    # Resized ONCE. The SAME list object is passed to every evaluate_temporal
    # call below (eval_long_side=None => used as-is, no further resize) —
    # that identity is what makes CachingFlowBackend's estimate() a hit
    # after the first configuration.
    eval_orig = resize_sequence_linear(frames, eh, ew)
    backend = CachingFlowBackend(SeaRaftBackend(device="mps"))

    # Build the ORIGINAL-derived evaluation state once: flow, FB validity
    # mask, warped original and the accepted illumination transform for
    # every (anchor, lag). Every configuration below is then scored against
    # this identical frozen domain, so a difference between configurations
    # is a difference in the CORRECTION and cannot be a difference in the
    # evaluator. (Previously only the flow was reused and the mask/fit were
    # recomputed per configuration.)
    prepared_pairs = prepare_temporal_pairs(
        eval_orig, backend, lags=LAGS, anchors=ANCHORS)

    input_diag = aggregate_signal_diagnostics(frames)

    configs_out = {}
    for config_name, stages in CONFIGS:
        t0 = time.time()
        corrected = apply_pipeline(frames, stages)  # full source resolution
        eval_corr = resize_sequence_linear(corrected, eh, ew)

        gains = {}
        for stage in stages:
            vals = [g for g in (correction_gain(f.metadata, stage) for f in corrected)
                    if g is not None]
            gains[stage] = vals if vals else None  # None => no global gain (clahe)

        out_of_range = sum(out_of_range_fraction(f.image) for f in corrected) / len(corrected)

        temporal = evaluate_temporal(
            eval_orig, eval_corr, backend,
            lags=LAGS, anchors=ANCHORS, eval_long_side=None,
            alignment_robust=alignment_robust,
            prepared_pairs=prepared_pairs,
        )
        # eval_orig/eval_corr are already on the metric grid, so
        # source_size_hw as returned would read the METRIC grid, not the
        # true source resolution — correct it for the report only; nothing
        # about the computation changes.
        temporal = dataclasses.replace(temporal, source_size_hw=(int(src_h), int(src_w)))

        configs_out[config_name] = {
            "stages": stages,
            "gains": gains,
            "out_of_range_fraction": out_of_range,
            "cache": backend.describe(),
            "runtime_s": time.time() - t0,
            "temporal": {
                "backend": temporal.backend,
                "source_size_hw": temporal.source_size_hw,
                "flow_inference_size_hw": temporal.flow_inference_size_hw,
                "metric_size_hw": temporal.metric_size_hw,
                "anchors": temporal.anchors,
                "lags": [_lag_summary(lag) for lag in temporal.lags],
            },
        }

    return {
        "clip": name,
        "source_path": str(path),
        "frame_range": [start, start + count - 1],
        "source_size_hw": (int(src_h), int(src_w)),
        "input_signal_diagnostics": dataclasses.asdict(input_diag),
        "configs": configs_out,
        "flow_cache": backend.describe(),
    }


def _verify_reuse_is_lossless(clip_name, rel_path, start, count):
    """Sanity check, run once before trusting the cached run: scoring one
    configuration through the batch harness (pre-resized once, cache
    wrapper) must be numerically IDENTICAL to scoring it the ordinary way
    (evaluate_temporal resizing internally, no cache). If this ever fails,
    the reuse mechanism has silently changed what is being measured, which
    CLAUDE.md forbids."""
    path = REPO_ROOT / rel_path
    frames = list(load(str(path), profile="srgb", start=start, count=count))
    corrected = apply_pipeline(frames, ["gray_world"])

    ordinary_backend = SeaRaftBackend(device="mps")
    ordinary = evaluate_temporal(
        frames, corrected, ordinary_backend,
        lags=LAGS, anchors=ANCHORS, eval_long_side=METRIC_LONG_SIDE,
    )

    src_h, src_w = frames[0].image.shape[:2]
    eh, ew = metric_eval_size(src_h, src_w, METRIC_LONG_SIDE)
    eval_orig = resize_sequence_linear(frames, eh, ew)
    eval_corr = resize_sequence_linear(corrected, eh, ew)
    cached_backend = CachingFlowBackend(SeaRaftBackend(device="mps"))
    cached = evaluate_temporal(
        eval_orig, eval_corr, cached_backend,
        lags=LAGS, anchors=ANCHORS, eval_long_side=None,
    )

    for a, b in zip(ordinary.lags, cached.lags):
        assert a.raw_warp == b.raw_warp, (clip_name, a.lag, a.raw_warp, b.raw_warp)
        assert a.illumination_aware_warp == b.illumination_aware_warp
        assert a.valid_fraction == b.valid_fraction
        assert a.illumination.gain == b.illumination.gain
    print(f"[verify] {clip_name}: batch-harness reuse path is bit-identical to the "
          f"ordinary per-call path ({len(ordinary.lags)} lags checked)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clip", action="append", choices=sorted(CLIPS),
                         help="restrict to these clips (default: all)")
    parser.add_argument("--json", default=None)
    parser.add_argument("--alignment-robust", action="store_true", default=True)
    parser.add_argument("--overwrite", action="store_true",
                         help="allow replacing an existing --json artifact")
    parser.add_argument("--no-verify", action="store_true",
                         help="skip the reuse-equivalence check (it costs one extra "
                              "clip's worth of inference)")
    args = parser.parse_args()

    clip_names = args.clip or sorted(CLIPS)

    if not args.no_verify:
        first = clip_names[0]
        _verify_reuse_is_lossless(first, *CLIPS[first])

    all_results = {}
    for name in clip_names:
        rel_path, start, count = CLIPS[name]
        print(f"=== {name} ({rel_path}, frames {start}..{start + count - 1}) ===")
        t0 = time.time()
        result = evaluate_clip(name, rel_path, start, count, args.alignment_robust)
        print(f"    done in {time.time() - t0:.1f}s; "
              f"flow cache: {result['flow_cache']['cache_hits']} hits / "
              f"{result['flow_cache']['cache_misses']} misses")
        all_results[name] = result

    if args.json:
        out_path = REPO_ROOT / args.json
        # CLAUDE.md invariant 7 applies to "benchmark outputs, everything",
        # not just the corrected-media path: never silently overwrite a
        # generated artifact. Re-running the documented command would
        # otherwise destroy the previous run's reproducibility record.
        if out_path.exists() and not args.overwrite:
            raise SystemExit(
                f"refusing to overwrite {out_path} without --overwrite"
            )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(all_results, f, indent=2, default=str)
        print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
