"""Command-line interface: `uw score <path>` and `uw correct <path> ...`."""

import argparse
import dataclasses
import json
import os
import sys

from uw.baselines import clahe, gray_world, white_patch
from uw.diagnostics import (
    aggregate_signal_diagnostics,
    correction_gain,
    out_of_range_fraction,
)
from uw.io import load, save
from uw.metrics import compare_backends_common_mask, delta_e, evaluate_temporal
from uw.types import Frame, TRANSFER_FUNCTIONS, FrameSequence

# Every IMPLEMENTED correction stage, in the order they'd run if all were
# requested. Adding an entry here is what "implemented" means for the
# ablation-flag rule below — no placeholder entries for stages that don't
# exist yet (CLAUDE.md invariant 4 / Phase 2C-2D brief §14).
STAGES = {
    "gray_world": gray_world,
    "white_patch": white_patch,
    "clahe": clahe,
}

# One ablation flag per implemented stage, and only per implemented stage:
# MC-Warp/temporal metrics are measurements, not stages, so they get none.
ABLATION_DEST = {
    "gray_world": "no_gray_world",
    "white_patch": "no_white_patch",
    "clahe": "no_clahe",
}

# Kept for `--method`, the backward-compatible single-stage alias (see
# _resolve_stage_list). "none" is not a stage — for `score` it scores the
# input against itself (how you check the metric reads zero when nothing
# changed); for `correct` it passes the frame through unchanged.
METHOD_CHOICES = tuple(sorted(STAGES)) + ("none",)

DEFAULT_LAGS = (1, 4, 8)
# Enough frames for three anchors at the default max lag without the anchors
# crowding each other. Bounded on purpose: a whole 1080p clip decoded eagerly
# into float32 is several GB, and a temporal metric only needs a window.
DEFAULT_TEMPORAL_FRAMES = 41

# SEA-RAFT-M is the canonical Phase 2B correspondence backend and the only
# one the temporal metric path needs. WAFT is available as a MANUAL
# cross-check — never a default, never run automatically, never averaged with
# SEA-RAFT, and never compared to it on differing pixels (`uw crosscheck`
# exists so that comparison is done on a common mask).
CANONICAL_FLOW_BACKEND = "searaft"
FLOW_BACKENDS = ("searaft", "waft")


def _resolve_stage_list(method, pipeline, default_method=None):
    """Turn --method / --pipeline into an ordered list of stage names.

    Exactly one of the two may be EXPLICITLY given (Phase 2C-2D brief §12:
    fail clearly rather than silently prefer one). Both argparse defaults
    are None on every subparser, specifically so this function — not
    argparse — is what decides "neither was explicitly passed": a caller's
    own historical default (`default_method`, e.g. "gray_world" for `score`)
    is applied only once we already know `method` is None because the user
    never touched --method, not because argparse pre-filled it, which would
    make it indistinguishable from an explicit `--method gray_world` and
    wrongly collide with an explicit `--pipeline`.
    """
    if method is not None and pipeline is not None:
        raise ValueError(
            "--method and --pipeline are mutually exclusive; pass only one "
            f"(got --method {method!r} and --pipeline {list(pipeline)!r})"
        )
    if pipeline is not None:
        pipeline = list(pipeline)
        unknown = [s for s in pipeline if s not in STAGES]
        if unknown:
            raise ValueError(
                f"unknown --pipeline stage(s) {unknown}; available: {sorted(STAGES)}"
            )
        return pipeline
    if method is None:
        method = default_method
    if method is None:
        raise ValueError("one of --method or --pipeline is required")
    if method == "none":
        return []
    if method not in STAGES:
        raise ValueError(f"unknown --method {method!r}; available: {METHOD_CHOICES}")
    return [method]


def _ablated_stages(args):
    """Which implemented stages the caller asked to skip via --no-<stage>."""
    return {name for name, dest in ABLATION_DEST.items() if getattr(args, dest, False)}


def _metadata_delta(previous: dict, current: dict) -> dict:
    """Metadata keys one stage added or changed.

    Comparison is defensive rather than a plain `!=`: a Frame's metadata is
    caller-controlled and may hold a numpy array (uw.metrics'
    `metric_resized_from`, for instance, or anything a future stage
    records), where `!=` returns an array and `bool()` of it raises. An
    ambiguous comparison is treated as "changed", which over-reports rather
    than silently dropping a stage's own diagnostic.
    """
    delta = {}
    for key, value in current.items():
        if key not in previous:
            delta[key] = value
            continue
        try:
            if bool(previous[key] != value):
                delta[key] = value
        except Exception:
            delta[key] = value
    return delta


def apply_pipeline(frames, requested_stages, ablated_stages=()):
    """Run an ordered list of correction stages over a FrameSequence.

    Per-frame, per CLAUDE.md invariant 3 (explicit state only): each stage
    is `Frame -> Frame`, pure, and never mutates its input. Composition is
    the simplest thing that works —

        result = frame
        for stage in active_stages:
            result = stage(result)

    Different stages namespace their own metadata keys (`gray_world_*`,
    `white_patch_*`, `clahe_*`), so composing DIFFERENT stages never
    collides. But the same stage can legitimately appear twice in a
    pipeline, and then the second application's flat `<stage>_*` keys
    overwrite the first's — measured: `--pipeline white_patch white_patch`
    kept only the second gain (1.0x) and silently lost the first (2.43x).

    So, per the Phase 2C-2D brief's own prescription for colliding keys
    ("use a small explicit per-stage structure rather than inventing a
    general provenance framework"), `pipeline["stages"]` is an ORDERED list
    with one entry per executed stage, each holding exactly the metadata
    that stage added or changed plus its own post-stage out-of-range
    fraction. Nothing is lost to a repeated stage, and per-stage gains stay
    attributable to a specific position in the order rather than to a key
    name. The flat `<stage>_*` keys are still written (last-writer-wins) so
    existing readers keep working.

    NOTE: `"pipeline"` is a RESERVED metadata key — it is written
    unconditionally, so a pre-existing caller value under that name is
    replaced. Namespacing it against arbitrary caller keys would mean
    building the general provenance framework the brief explicitly rules
    out; reserving one documented name is the proportionate alternative.
    """
    ablated_stages = set(ablated_stages)
    unknown = ablated_stages - set(STAGES)
    if unknown:
        raise ValueError(f"unknown ablated stage(s) {sorted(unknown)}; available: {sorted(STAGES)}")
    active_stages = [s for s in requested_stages if s not in ablated_stages]

    results = []
    for frame in frames:
        result = frame
        stage_records = []
        for name in active_stages:
            previous_metadata = result.metadata
            result = STAGES[name](result)
            stage_records.append({
                "stage": name,
                "metadata": _metadata_delta(previous_metadata, result.metadata),
                "out_of_range_fraction": out_of_range_fraction(result.image),
            })
        meta = dict(result.metadata)
        meta["pipeline"] = {
            "requested": list(requested_stages),
            "executed": list(active_stages),
            "ablated": sorted(ablated_stages & set(requested_stages)),
            "stages": stage_records,
            "out_of_range_fraction": out_of_range_fraction(result.image),
        }
        results.append(Frame(image=result.image, metadata=meta))
    return results


def _load_chart_patches(chart_path):
    """Load chart_refs.json and report whether it's still the schema placeholder.

    The placeholder shipped in the repo (data/chart_refs.json) carries a
    "_schema" documentation key that a real, filled-in chart file would have
    no reason to keep. That key's presence is the signal, not any guess
    about specific patch values.
    """
    with open(chart_path) as f:
        data = json.load(f)
    is_placeholder = "_schema" in data
    return data, is_placeholder


# ---------------------------------------------------------------------------
# Temporal reporting
# ---------------------------------------------------------------------------


def _num(value, fmt="{:.6f}"):
    return "n/a" if value is None else fmt.format(value)


def _build_flow_backend(name, device):
    """Construct a flow backend, lazily, with a usable error if it can't be.

    Imported here and nowhere else in `uw/`: the wrappers are the only things
    in the project that need torch, and importing `uw.cli` or `uw.metrics`
    must not drag it in (CLAUDE.md invariant 8).
    """
    if name == "searaft":
        from uw.searaft import SeaRaftBackend

        return SeaRaftBackend(device=device)
    if name == "waft":
        from uw.waft import WaftBackend

        return WaftBackend(device=device)
    raise ValueError(f"unknown flow backend {name!r}; available: {FLOW_BACKENDS}")


def _warn_non_canonical(name):
    """Say plainly that a non-canonical backend's numbers are not drop-in."""
    if name == CANONICAL_FLOW_BACKEND:
        return
    print()
    print(f"!! Non-canonical flow backend: {name}")
    print(f"   {CANONICAL_FLOW_BACKEND} is the canonical Phase 2B backend. These "
          f"numbers are a second")
    print("   opinion, not a substitute: two backends' residuals are computed "
          "over DIFFERENT")
    print("   valid pixels, so they are not comparable to a "
          f"{CANONICAL_FLOW_BACKEND} run value-for-value.")
    print("   To compare the two properly, on the intersection of their masks:")
    print("     uw crosscheck <path> [--start N --frames N]")


def _print_temporal(result, alignment_robust):
    print()
    print("Temporal consistency")
    print("--------------------")
    print(f"  backend:              {result.backend}")
    print(f"  source resolution:    {result.source_size_hw[0]}x{result.source_size_hw[1]}")
    inf = result.flow_inference_size_hw
    print(f"  flow inference:       "
          f"{f'{inf[0]}x{inf[1]}' if inf else 'n/a'}")
    print(f"  metric evaluation:    {result.metric_size_hw[0]}x{result.metric_size_hw[1]}")
    print(f"  anchors (window idx): {', '.join(str(a) for a in result.anchors)}")
    print(f"  correspondence from:  {result.correspondence_source}")
    print(f"  illumination fit from:{result.illumination_fit_source}")

    for lag in result.lags:
        print()
        print(f"@{lag.lag}")
        print(f"  Raw MC-Warp:                    {_num(lag.raw_warp)}")
        print(f"  Illum-aware MC-Warp:            {_num(lag.illumination_aware_warp)}")
        print(f"  Uncompensated residual:         {_num(lag.uncompensated)}")
        print(f"  Motion reduction:               {_num(lag.motion_reduction_ratio, '{:.2f}x')}")
        print(f"  Temporal ΔE00:                  {_num(lag.temporal_delta_e, '{:.3f}')}")
        if alignment_robust:
            print(f"  Alignment-robust MC-Warp:       {_num(lag.alignment_robust_warp)}")
        print(f"  Valid coverage:                 {lag.valid_fraction * 100:.1f}%")
        print(f"  ΔE coverage:                    {lag.delta_e_valid_fraction * 100:.1f}%")
        print(f"  Status:                         {lag.status}")

    print()
    print("Input baseline")
    print("--------------")
    print("  Same correspondence, same validity mask, same evaluation domain.")
    print("  Not a floor to subtract: the input residual already contains "
          "caustics, particles,")
    print("  moving animals, the camera's own exposure/WB behaviour, and "
          "correspondence error.")
    for lag in result.lags:
        print()
        print(f"@{lag.lag}")
        print(f"  Input raw MC-Warp:              {_num(lag.input_raw_warp)}")
        print(f"  Input illum-aware MC-Warp:      {_num(lag.input_illumination_aware_warp)}")
        print(f"  Input uncompensated residual:   {_num(lag.input_uncompensated)}")
        print(f"  Input motion reduction:         "
              f"{_num(lag.input_motion_reduction_ratio, '{:.2f}x')}")
        print(f"  Input temporal ΔE00:            {_num(lag.input_temporal_delta_e, '{:.3f}')}")
        if alignment_robust:
            print(f"  Input alignment-robust MC-Warp: {_num(lag.input_alignment_robust_warp)}")

    print()
    print("Illumination model")
    print("------------------")
    for lag in result.lags:
        fit = lag.illumination
        print(f"@{lag.lag}")
        print(f"  type:                           {fit.model}")
        print(f"  estimator:                      {fit.estimator}")
        print(f"  gain:                           {fit.gain:.4f}")
        print(f"  bias:                           {fit.bias:+.5f}")
        print(f"  fit domain:                     {fit.fit_pixels} px "
              f"({fit.fit_fraction * 100:.1f}% of valid)")
        print(f"  input residual explained:       "
              f"{_num(lag.illumination_explained_fraction, '{:.1%}')}")
        print(f"  illumination-confounded:        "
              f"{'yes' if lag.illumination_confounded else 'no'}")
        print(f"  fit status:                     {fit.status}")


def _fmt_gain_stat(values):
    return f"{min(values):.3f}-{max(values):.3f} (mean {sum(values) / len(values):.3f})"


def _print_pipeline_report(requested_stages, ablated_stages, original_frames, corrected_frames):
    """Pipeline / signal-diagnostics / gains / range report — Phase 2C-2D §17.

    Deliberately three separate labeled sections rather than one score:
    what ran, what the ORIGINAL input signal looked like before any of it
    ran, what gain each global stage applied, and what the correction did
    to the output range. Reading "original near-floor fraction" beside "gain
    applied" beside "output out-of-range fraction" is the point — CLAUDE.md
    Phase 2C-2D §3: a large gain on a signal-starved channel must stay
    visible even when the corrected image looks attractive.
    """
    executed = [s for s in requested_stages if s not in ablated_stages]
    really_ablated = sorted(set(ablated_stages) & set(requested_stages))

    print()
    print("Pipeline")
    print("--------")
    print(f"  requested: {', '.join(requested_stages) if requested_stages else 'none'}")
    print(f"  executed:  {', '.join(executed) if executed else 'none'}")
    print(f"  ablated:   {', '.join(really_ablated) if really_ablated else 'none'}")

    diag = aggregate_signal_diagnostics(original_frames)
    print()
    print(f"Signal diagnostics (ORIGINAL input, {len(original_frames)} frame(s), "
          f"{diag.pixel_count} px total, profile={diag.transfer_function})")
    print(f"  near-floor fraction (<= {diag.near_floor_threshold}):   "
          f"R={diag.near_floor_fraction['r']:.4f}  "
          f"G={diag.near_floor_fraction['g']:.4f}  "
          f"B={diag.near_floor_fraction['b']:.4f}")
    print(f"  representation-ceiling fraction (>= {diag.saturation_threshold}):   "
          f"R={diag.saturation_fraction['r']:.4f}  "
          f"G={diag.saturation_fraction['g']:.4f}  "
          f"B={diag.saturation_fraction['b']:.4f}")
    print("  This is the fraction sitting AT the decoded representation's upper bound.")
    print("  It does NOT establish sensor/source clipping: codec range conversion,")
    print("  grading and quantisation can all put a value at the ceiling without the")
    print(f"  sensor having clipped. Profile here is {diag.transfer_function!r}; for an")
    print("  8-bit-quantised profile the ceiling is exactly reachable, which is a")
    print("  necessary but not sufficient condition for reading it as clipping.")
    print("  A corrected-frame near-floor fraction lower than the original's does "
          "NOT mean")
    print("  information was recovered — a global multiply cannot recreate signal "
          "that was")
    print("  clipped, quantized away, or buried below the floor at capture time.")

    print()
    print("Correction gains")
    if not executed:
        print("  (no correction stage ran)")
    for name in executed:
        gains = [g for g in (correction_gain(f.metadata, name) for f in corrected_frames)
                 if g is not None]
        if not gains:
            print(f"  {name}: no single global per-channel gain "
                  f"(local/perceptual-lightness stage, not a global multiply)")
            continue
        r = [g[0] for g in gains]
        g_ = [g[1] for g in gains]
        b = [g[2] for g in gains]
        print(f"  {name}: R {_fmt_gain_stat(r)}  G {_fmt_gain_stat(g_)}  "
              f"B {_fmt_gain_stat(b)}")

    avg_out_of_range = (
        sum(out_of_range_fraction(f.image) for f in corrected_frames) / len(corrected_frames)
    )
    print()
    print("Post-correction range")
    print(f"  out-of-range fraction (mean over {len(corrected_frames)} frame(s)): "
          f"{avg_out_of_range:.4f}")


def cmd_score(args):
    # Validate the pipeline request BEFORE decoding anything: an ambiguous
    # or unknown --method/--pipeline should fail immediately, not after
    # paying for a full video decode.
    try:
        requested_stages = _resolve_stage_list(
            args.method, args.pipeline, default_method="gray_world"
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    ablated = _ablated_stages(args)

    lags = tuple(int(k) for k in args.lags.split(",")) if args.lags else DEFAULT_LAGS
    anchors = tuple(int(a) for a in args.anchors.split(",")) if args.anchors else None

    count = args.frames
    if count is None and args.temporal:
        count = DEFAULT_TEMPORAL_FRAMES
    frames = list(load(args.path, profile=args.profile, start=args.start, count=count))
    corrected = apply_pipeline(frames, requested_stages, ablated)

    print(f"frames: {len(corrected)} (source index {args.start}"
          f"..{args.start + len(corrected) - 1})")
    _print_pipeline_report(requested_stages, ablated, frames, corrected)

    print()
    print("Color")
    print("-----")
    if args.chart is None:
        print("  ΔE: no chart reference data provided")
    else:
        chart_patches, is_placeholder = _load_chart_patches(args.chart)
        if is_placeholder:
            print(
                f"  ΔE: no chart reference data provided "
                f"({args.chart} is still the schema placeholder)"
            )
        else:
            print(f"  ΔE (CIEDE2000, mean over patches): {delta_e(corrected[0], chart_patches)}")

    if not args.temporal:
        print()
        print("Temporal consistency: not computed (pass --temporal).")
        print("  It needs an optical-flow backend, which is deliberately not a")
        print("  core dependency. Run it from the isolated interpreter:")
        print("    experiments/week2a_flow/.venv-flow/bin/python -m uw.cli score "
              f"{args.path} --temporal")
        return 0

    _warn_non_canonical(args.flow_backend)
    backend = _build_flow_backend(args.flow_backend, args.device)
    result = evaluate_temporal(
        frames, corrected, backend,
        lags=lags, anchors=anchors, n_anchors=args.n_anchors,
        eval_long_side=args.metric_long_side,
        alignment_robust=args.alignment_robust,
    )
    _print_temporal(result, args.alignment_robust)

    if args.json:
        if os.path.exists(args.json) and not args.overwrite:
            print(f"\nrefusing to overwrite {args.json!r} without --overwrite",
                  file=sys.stderr)
            return 1
        payload = dataclasses.asdict(result)
        payload["source_path"] = os.path.abspath(args.path)
        payload["frame_range"] = [args.start, args.start + len(corrected) - 1]
        payload["method"] = args.method
        payload["pipeline"] = {
            "requested": requested_stages,
            "executed": [s for s in requested_stages if s not in ablated],
            "ablated": sorted(ablated & set(requested_stages)),
        }
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w") as f:
            json.dump(payload, f, indent=2, default=str)
        print(f"\nwrote {args.json}")
    return 0


def cmd_crosscheck(args):
    """Score two flow backends on the pixels they BOTH call valid.

    The only sanctioned way to compare backends. Scoring each on its own
    validity mask measures masking policy, not correspondence quality: the
    backend that excludes more of the difficult region wins on what is left.
    """
    lags = tuple(int(k) for k in args.lags.split(",")) if args.lags else DEFAULT_LAGS
    anchors = tuple(int(a) for a in args.anchors.split(",")) if args.anchors else None
    count = args.frames if args.frames is not None else DEFAULT_TEMPORAL_FRAMES
    frames = load(args.path, profile=args.profile, start=args.start, count=count)

    a = _build_flow_backend(args.a, args.device)
    b = _build_flow_backend(args.b, args.device)
    result = compare_backends_common_mask(
        list(frames), a, b, lags=lags, anchors=anchors, n_anchors=args.n_anchors,
        eval_long_side=args.metric_long_side,
    )

    na, nb = result.backend_a, result.backend_b
    print(f"frames: {len(frames)} (source index {args.start}"
          f"..{args.start + len(frames) - 1})")
    print(f"metric evaluation: {result.metric_size_hw[0]}x{result.metric_size_hw[1]}"
          f"   anchors: {', '.join(str(x) for x in result.anchors)}")
    print()
    print(f"Backend cross-check — {na} vs {nb}")
    print("-" * 60)
    print(f"  scored on {result.scored_on}")
    print("  correspondence only: no corrected output takes part")
    print()
    header = (f"{'lag':>4} | {'common':>7} {'disputed':>8} | "
              f"{na[:10] + ' cov':>14} {nb[:10] + ' cov':>14} | "
              f"{na[:10] + ' red':>14} {nb[:10] + ' red':>14} | winner")
    print(header)
    print("-" * len(header))
    for cell in result.cells:
        red = cell.motion_reduction_ratio
        print(f"{cell.lag:>4} | {cell.common_fraction:6.1%} {cell.disputed_fraction:7.1%} | "
              f"{cell.own_fraction[na]:13.1%} {cell.own_fraction[nb]:13.1%} | "
              f"{_num(red[na], '{:.3f}'):>14} {_num(red[nb], '{:.3f}'):>14} | "
              f"{cell.verdict}")
    print("-" * len(header))
    print(f"cells won on the common mask: {result.tally}")
    print()
    print("  A difference here is a correspondence-quality difference. A difference")
    print("  in the two backends' own per-backend numbers that vanishes here was a")
    print("  masking-policy difference. The tally counts cells; it is not a score,")
    print("  and the cells are not summed.")
    print()
    print("  Cross-backend flow disagreement, on the same pixels:")
    for cell in result.cells:
        epe = cell.flow_epe_px
        print(f"  @{cell.lag}  median {_num(epe['median_overall'], '{:.3f}')} px"
              f"   in the band where the two masks disagree "
              f"{_num(epe['median_in_disputed_band'], '{:.3f}')} px")
    print()
    print("  PLAN.md's rule: where the two backends disagree MATERIALLY, treat that")
    print("  clip's MC-Warp as low-confidence. No threshold is hard-coded here — what")
    print("  counts as material depends on the clip's own motion magnitude, and a")
    print("  number tuned against the frozen clips would be exactly the kind of")
    print("  threshold PLAN.md forbids. Read the disagreement against the median")
    print("  flow magnitude for that clip (Phase 2A: ~0.8 % of motion on murky_eel,")
    print("  ~22 % on murky_shark, where all backends still reported 96-99 % valid).")

    if args.json:
        if os.path.exists(args.json) and not args.overwrite:
            print(f"\nrefusing to overwrite {args.json!r} without --overwrite",
                  file=sys.stderr)
            return 1
        payload = dataclasses.asdict(result)
        payload["source_path"] = os.path.abspath(args.path)
        payload["frame_range"] = [args.start, args.start + len(frames) - 1]
        os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
        with open(args.json, "w") as f:
            json.dump(payload, f, indent=2, default=str)
        print(f"\nwrote {args.json}")
    return 0


def cmd_correct(args):
    try:
        requested_stages = _resolve_stage_list(args.method, args.pipeline)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    ablated = _ablated_stages(args)

    frames = load(args.path, profile=args.profile, start=args.start, count=args.frames)
    corrected = apply_pipeline(frames, requested_stages, ablated)

    executed = [s for s in requested_stages if s not in ablated]
    really_ablated = sorted(set(ablated) & set(requested_stages))
    print(f"pipeline: {', '.join(requested_stages) if requested_stages else 'none'}"
          f"  executed: {', '.join(executed) if executed else 'none'}"
          f"  ablated: {', '.join(really_ablated) if really_ablated else 'none'}")

    save(FrameSequence(corrected), args.out, overwrite=args.overwrite)
    print(f"wrote {len(corrected)} frame(s) to {args.out}")
    return 0


def _add_pipeline_args(parser, method_default):
    """--method / --pipeline / --no-<stage> — shared by `score` and `correct`.

    argparse's own default for --method is ALWAYS None here, regardless of
    `method_default` — that default is applied later, inside
    _resolve_stage_list, which is what actually needs to distinguish "the
    user explicitly passed --method" from "neither flag was given, apply
    the command's historical default". If argparse pre-filled --method with
    "gray_world", `uw score in.mp4 --pipeline clahe` would look identical to
    an explicit `--method gray_world --pipeline clahe` and wrongly trip the
    mutual-exclusivity check below.
    """
    parser.add_argument(
        "--method",
        choices=METHOD_CHOICES,
        default=None,
        help="single correction stage under test — backward-compatible alias "
             "for --pipeline <stage>; 'none' means no correction. Mutually "
             "exclusive with --pipeline."
             + (f" (default: {method_default})" if method_default else " (required "
                "if --pipeline is not given)"),
    )
    parser.add_argument(
        "--pipeline",
        nargs="+",
        choices=sorted(STAGES),
        default=None,
        metavar="STAGE",
        help="ordered correction stages to compose, e.g. "
             "--pipeline white_patch clahe. Mutually exclusive with --method. "
             "Stages are never auto-stacked — gray_world and white_patch are "
             "competing global-WB baselines, not a default chain.",
    )
    for stage, dest in ABLATION_DEST.items():
        parser.add_argument(
            f"--no-{stage.replace('_', '-')}", dest=dest, action="store_true",
            help=f"skip {stage} if it was requested via --method/--pipeline",
        )


def build_parser():
    parser = argparse.ArgumentParser(prog="uw")
    subparsers = parser.add_subparsers(dest="command", required=True)

    score_parser = subparsers.add_parser("score", help="Score a corrected input")
    score_parser.add_argument("path")
    score_parser.add_argument(
        "--profile",
        choices=TRANSFER_FUNCTIONS,
        default="srgb",
        help="source transfer function (default: srgb)",
    )
    _add_pipeline_args(score_parser, method_default="gray_world")
    score_parser.add_argument(
        "--chart",
        default=None,
        help="path to a chart_refs.json with real (non-placeholder) patch data; "
        "if omitted, ΔE is not computed",
    )
    score_parser.add_argument("--start", type=int, default=0,
                              help="first source frame to decode (default: 0)")
    score_parser.add_argument("--frames", type=int, default=None,
                              help=f"how many frames to decode (default: all, or "
                                   f"{DEFAULT_TEMPORAL_FRAMES} with --temporal)")
    score_parser.add_argument(
        "--temporal", action="store_true",
        help="compute the motion-aware temporal metrics (needs a flow backend)",
    )
    score_parser.add_argument(
        "--flow-backend", choices=FLOW_BACKENDS, default=CANONICAL_FLOW_BACKEND,
        help=f"correspondence backend (default: {CANONICAL_FLOW_BACKEND}, the "
             f"canonical one). Anything else is a manual second opinion whose "
             f"values are not comparable value-for-value — see `uw crosscheck`.",
    )
    score_parser.add_argument("--device", default="mps")
    score_parser.add_argument("--lags", default=None,
                              help="comma-separated lags (default: 1,4,8)")
    score_parser.add_argument("--anchors", default=None,
                              help="comma-separated anchor indices WITHIN the decoded "
                                   "window; default is evenly spread")
    score_parser.add_argument("--n-anchors", type=int, default=3,
                              help="how many evenly-spread anchors (default: 3)")
    score_parser.add_argument("--metric-long-side", type=int, default=960,
                              help="metric evaluation grid long side (default: 960, "
                                   "the Phase 2A grid)")
    score_parser.add_argument("--alignment-robust", action="store_true",
                              help="also report the separately-named "
                                   "alignment-robust companion diagnostic")
    score_parser.add_argument("--json", default=None,
                              help="write the full temporal result to this path")
    score_parser.add_argument("--overwrite", action="store_true",
                              help="allow overwriting an existing --json output")
    score_parser.set_defaults(func=cmd_score)

    cross_parser = subparsers.add_parser(
        "crosscheck",
        help="Compare two flow backends on the intersection of their validity masks",
    )
    cross_parser.add_argument("path")
    cross_parser.add_argument(
        "--profile", choices=TRANSFER_FUNCTIONS, default="srgb",
        help="source transfer function (default: srgb)",
    )
    cross_parser.add_argument("--a", choices=FLOW_BACKENDS, default="searaft")
    cross_parser.add_argument("--b", choices=FLOW_BACKENDS, default="waft")
    cross_parser.add_argument("--device", default="mps")
    cross_parser.add_argument("--start", type=int, default=0)
    cross_parser.add_argument("--frames", type=int, default=None)
    cross_parser.add_argument("--lags", default=None,
                              help="comma-separated lags (default: 1,4,8)")
    cross_parser.add_argument("--anchors", default=None)
    cross_parser.add_argument("--n-anchors", type=int, default=3)
    cross_parser.add_argument("--metric-long-side", type=int, default=960)
    cross_parser.add_argument("--json", default=None)
    cross_parser.add_argument("--overwrite", action="store_true")
    cross_parser.set_defaults(func=cmd_crosscheck)

    correct_parser = subparsers.add_parser("correct", help="Apply a correction pipeline and save")
    correct_parser.add_argument("path")
    correct_parser.add_argument("--out", required=True)
    correct_parser.add_argument(
        "--profile",
        choices=TRANSFER_FUNCTIONS,
        default="srgb",
        help="source transfer function (default: srgb)",
    )
    _add_pipeline_args(correct_parser, method_default=None)
    correct_parser.add_argument("--start", type=int, default=0)
    correct_parser.add_argument("--frames", type=int, default=None)
    correct_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="allow overwriting an existing output file",
    )
    correct_parser.set_defaults(func=cmd_correct)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
