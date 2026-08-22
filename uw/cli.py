"""Command-line interface: `uw score <path>` and `uw correct <path> ...`."""

import argparse
import json
import sys

from uw.baselines import gray_world
from uw.io import load, save
from uw.metrics import delta_e, temporal_stability
from uw.types import TRANSFER_FUNCTIONS

METHODS = {
    "gray_world": gray_world,
}


def _apply_method(frames, method_name):
    method = METHODS[method_name]
    return [method(frame) for frame in frames]


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


def cmd_score(args):
    frames = load(args.path, profile=args.profile)
    corrected = _apply_method(frames, "gray_world")
    stability = temporal_stability(corrected)
    print(f"frames: {len(corrected)}")
    print(f"temporal_stability (placeholder proxy): {stability}")

    if args.chart is None:
        print("ΔE: no chart reference data provided")
    else:
        chart_patches, is_placeholder = _load_chart_patches(args.chart)
        if is_placeholder:
            print(
                f"ΔE: no chart reference data provided "
                f"({args.chart} is still the schema placeholder)"
            )
        else:
            mean_delta_e = delta_e(corrected[0], chart_patches)
            print(f"ΔE (CIEDE2000, mean over patches): {mean_delta_e}")
    return 0


def cmd_correct(args):
    frames = load(args.path, profile=args.profile)
    if args.method not in METHODS:
        print(f"unknown method {args.method!r}; available: {sorted(METHODS)}", file=sys.stderr)
        return 1
    corrected = _apply_method(frames, args.method)
    from uw.types import FrameSequence

    save(FrameSequence(corrected), args.out, overwrite=args.overwrite)
    print(f"wrote {len(corrected)} frame(s) to {args.out}")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="uw")
    subparsers = parser.add_subparsers(dest="command", required=True)

    score_parser = subparsers.add_parser("score", help="Score a gray-world-corrected input")
    score_parser.add_argument("path")
    score_parser.add_argument(
        "--profile",
        choices=TRANSFER_FUNCTIONS,
        default="srgb",
        help="source transfer function (default: srgb)",
    )
    score_parser.add_argument(
        "--chart",
        default=None,
        help="path to a chart_refs.json with real (non-placeholder) patch data; "
        "if omitted, ΔE is not computed",
    )
    score_parser.set_defaults(func=cmd_score)

    correct_parser = subparsers.add_parser("correct", help="Apply a correction method and save")
    correct_parser.add_argument("path")
    correct_parser.add_argument("--method", choices=sorted(METHODS), required=True)
    correct_parser.add_argument("--out", required=True)
    correct_parser.add_argument(
        "--profile",
        choices=TRANSFER_FUNCTIONS,
        default="srgb",
        help="source transfer function (default: srgb)",
    )
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
