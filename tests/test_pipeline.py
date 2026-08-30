"""Tests for uw/cli.py's Week 2 Phase 2C/2D pipeline composition and
ablation plumbing: --method/--pipeline resolution, ordered execution,
--no-<stage> ablations, backward compatibility, and CLI argument wiring.

Deliberately bounded per the brief: not a combinatorial CLI matrix, just the
specific behaviors §11-15/§22 ask for.
"""

import numpy as np
import pytest

from uw import cli
from uw.types import Frame


def _frame(h=6, w=6, value=0.3):
    return Frame(image=np.full((h, w, 3), value, dtype=np.float32), metadata={})


# ---------------------------------------------------------------------------
# _resolve_stage_list
# ---------------------------------------------------------------------------


def test_method_and_pipeline_together_is_rejected():
    with pytest.raises(ValueError, match="mutually exclusive"):
        cli._resolve_stage_list("gray_world", ["clahe"])


def test_method_none_resolves_to_empty_pipeline():
    assert cli._resolve_stage_list("none", None) == []


def test_method_gray_world_is_a_single_stage_pipeline_alias():
    assert cli._resolve_stage_list("gray_world", None) == \
        cli._resolve_stage_list(None, ["gray_world"])


def test_pipeline_preserves_requested_order():
    assert cli._resolve_stage_list(None, ["white_patch", "clahe"]) == \
        ["white_patch", "clahe"]
    assert cli._resolve_stage_list(None, ["clahe", "white_patch"]) == \
        ["clahe", "white_patch"]


def test_unknown_pipeline_stage_is_rejected():
    with pytest.raises(ValueError, match="unknown --pipeline stage"):
        cli._resolve_stage_list(None, ["not_a_real_stage"])


def test_unknown_method_is_rejected():
    with pytest.raises(ValueError, match="unknown --method"):
        cli._resolve_stage_list("not_a_real_stage", None)


def test_no_stages_and_no_default_pipeline_is_never_auto_stacked():
    """gray_world and white_patch must never be combined unless explicitly
    requested — no method/pipeline given resolves to a KeyError-free empty
    list only via 'none'; a bare, unresolved None/None is a caller error,
    not an implicit default chain."""
    assert cli._resolve_stage_list("gray_world", None) == ["gray_world"]
    assert cli._resolve_stage_list("white_patch", None) == ["white_patch"]
    # Never silently produces ["gray_world", "white_patch"] from either alone.


# ---------------------------------------------------------------------------
# apply_pipeline: ordering, chaining, ablation
# ---------------------------------------------------------------------------


def test_apply_pipeline_executes_in_order_and_chains_output(monkeypatch):
    calls = []

    def stage_a(frame):
        calls.append(("a", list(frame.metadata.get("chain", []))))
        meta = dict(frame.metadata)
        meta["chain"] = meta.get("chain", []) + ["a"]
        return Frame(image=frame.image + 1.0, metadata=meta)

    def stage_b(frame):
        calls.append(("b", list(frame.metadata.get("chain", []))))
        meta = dict(frame.metadata)
        meta["chain"] = meta.get("chain", []) + ["b"]
        return Frame(image=frame.image * 2.0, metadata=meta)

    monkeypatch.setitem(cli.STAGES, "gray_world", stage_a)
    monkeypatch.setitem(cli.STAGES, "white_patch", stage_b)

    frame = Frame(image=np.zeros((2, 2, 3), dtype=np.float32), metadata={})
    [result] = cli.apply_pipeline([frame], ["gray_world", "white_patch"])

    assert calls == [("a", []), ("b", ["a"])]
    assert result.metadata["chain"] == ["a", "b"]
    np.testing.assert_allclose(result.image, (0.0 + 1.0) * 2.0)
    assert result.metadata["pipeline"]["requested"] == ["gray_world", "white_patch"]
    assert result.metadata["pipeline"]["executed"] == ["gray_world", "white_patch"]
    assert result.metadata["pipeline"]["ablated"] == []


def test_pipeline_with_no_ablation_no_clahe():
    [result] = cli.apply_pipeline([_frame()], ["white_patch", "clahe"], ablated_stages={"clahe"})
    assert result.metadata["pipeline"]["executed"] == ["white_patch"]
    assert result.metadata["pipeline"]["ablated"] == ["clahe"]
    assert "white_patch_channel_gain" in result.metadata
    assert "clahe_out_of_range_fraction" not in result.metadata


def test_ablate_gray_world_from_a_requested_pipeline():
    [result] = cli.apply_pipeline(
        [_frame()], ["gray_world", "clahe"], ablated_stages={"gray_world"}
    )
    assert result.metadata["pipeline"]["executed"] == ["clahe"]
    assert "gray_world_channel_scale" not in result.metadata
    assert "clahe_out_of_range_fraction" in result.metadata


def test_ablate_white_patch_from_a_requested_pipeline():
    [result] = cli.apply_pipeline(
        [_frame()], ["white_patch", "clahe"], ablated_stages={"white_patch"}
    )
    assert result.metadata["pipeline"]["executed"] == ["clahe"]
    assert "white_patch_channel_gain" not in result.metadata


def test_ablating_an_unrequested_stage_is_a_no_op_but_recorded_only_if_requested():
    [result] = cli.apply_pipeline([_frame()], ["clahe"], ablated_stages={"gray_world"})
    assert result.metadata["pipeline"]["executed"] == ["clahe"]
    # gray_world was never requested, so it does not appear in "ablated"
    # (that field means "requested AND skipped", not "flag was passed").
    assert result.metadata["pipeline"]["ablated"] == []


def test_apply_pipeline_rejects_unknown_ablated_stage():
    with pytest.raises(ValueError, match="unknown ablated stage"):
        cli.apply_pipeline([_frame()], ["clahe"], ablated_stages={"not_a_stage"})


def test_metadata_from_each_stage_is_attributable_after_real_composition():
    """Uses the REAL stages (not stubs): each stage's own namespaced
    metadata keys must all survive composition without collision."""
    [result] = cli.apply_pipeline([_frame(value=0.3)], ["white_patch", "clahe"])
    assert "white_patch_channel_gain" in result.metadata
    assert "white_patch_out_of_range_fraction" in result.metadata
    assert "clahe_out_of_range_fraction" in result.metadata
    assert "clahe_clip_limit" in result.metadata


def test_repeated_stage_keeps_both_applications_attributable():
    """REGRESSION. Different stages namespace their own keys, but the SAME
    stage twice used to overwrite its own flat `<stage>_*` keys, silently
    losing the first application's gain (measured: first 2.43x, second 1.0x,
    only the second recoverable). `pipeline["stages"]` is the small explicit
    per-stage structure the brief prescribes for exactly this case."""
    rng = np.random.default_rng(0)
    image = np.clip(
        np.full((32, 32, 3), 0.3, np.float32)
        + rng.normal(0, 0.02, (32, 32, 3)).astype(np.float32),
        0, None,
    )
    image[:4, :4] = [0.35, 0.85, 0.85]
    [result] = cli.apply_pipeline(
        [Frame(image=image, metadata={})], ["white_patch", "white_patch"]
    )

    stages = result.metadata["pipeline"]["stages"]
    assert [s["stage"] for s in stages] == ["white_patch", "white_patch"]

    first_gain = stages[0]["metadata"]["white_patch_channel_gain"]
    second_gain = stages[1]["metadata"]["white_patch_channel_gain"]
    # The first application's real correction survives...
    assert first_gain[0] > 1.5
    # ...and is distinct from the second's near-identity re-application.
    assert second_gain[0] == pytest.approx(1.0, abs=0.05)
    # The flat key still exists for existing readers, holding the last write.
    assert result.metadata["white_patch_channel_gain"] == second_gain


def test_per_stage_records_are_ordered_and_carry_their_own_range_behavior():
    [result] = cli.apply_pipeline([_frame(value=0.3)], ["white_patch", "clahe"])
    stages = result.metadata["pipeline"]["stages"]
    assert [s["stage"] for s in stages] == ["white_patch", "clahe"]
    assert "white_patch_channel_gain" in stages[0]["metadata"]
    assert "clahe_clip_limit" in stages[1]["metadata"]
    # Each stage records the range behavior AS OF that stage, not just the end.
    for record in stages:
        assert "out_of_range_fraction" in record


def test_ablated_stage_produces_no_per_stage_record():
    [result] = cli.apply_pipeline(
        [_frame()], ["white_patch", "clahe"], ablated_stages={"clahe"}
    )
    stages = result.metadata["pipeline"]["stages"]
    assert [s["stage"] for s in stages] == ["white_patch"]


def test_metadata_delta_tolerates_unhashable_and_array_metadata():
    """A Frame's metadata is caller-controlled; a numpy array in it must not
    make the per-stage delta raise on an ambiguous `!=` truth value."""
    frame = Frame(
        image=np.full((6, 6, 3), 0.3, dtype=np.float32),
        metadata={"metric_resized_from": np.array([1080, 1920])},
    )
    [result] = cli.apply_pipeline([frame], ["white_patch"])
    assert result.metadata["pipeline"]["stages"][0]["stage"] == "white_patch"


def test_pipeline_order_matters():
    frame = Frame(
        image=(0.3 + 0.02 * np.random.default_rng(0).standard_normal((16, 16, 3))
               ).astype(np.float32),
        metadata={},
    )
    [a] = cli.apply_pipeline([frame], ["white_patch", "clahe"])
    [b] = cli.apply_pipeline([frame], ["clahe", "white_patch"])
    assert not np.allclose(a.image, b.image)


def test_gray_world_and_white_patch_are_not_auto_stacked():
    """Requesting one baseline alone must never pull the other in."""
    [result] = cli.apply_pipeline([_frame()], ["gray_world"])
    assert "white_patch_channel_gain" not in result.metadata
    [result2] = cli.apply_pipeline([_frame()], ["white_patch"])
    assert "gray_world_channel_scale" not in result2.metadata


# ---------------------------------------------------------------------------
# CLI argument wiring
# ---------------------------------------------------------------------------


def test_score_method_defaults_to_gray_world_backward_compatibly():
    # argparse itself leaves --method as None when the flag is omitted —
    # see _add_pipeline_args's docstring for why. The "gray_world" default
    # is applied by _resolve_stage_list, which cmd_score calls with
    # default_method="gray_world".
    args = cli.build_parser().parse_args(["score", "in.mp4"])
    assert args.method is None
    assert args.pipeline is None
    assert cli._resolve_stage_list(args.method, args.pipeline, default_method="gray_world") \
        == ["gray_world"]


def test_score_pipeline_only_is_not_treated_as_ambiguous():
    """The bug this guards against: argparse pre-filling --method with a
    default used to make a bare --pipeline collide with it."""
    args = cli.build_parser().parse_args(["score", "in.mp4", "--pipeline", "clahe"])
    assert args.method is None
    assert cli._resolve_stage_list(args.method, args.pipeline, default_method="gray_world") \
        == ["clahe"]


def test_correct_requires_method_or_pipeline():
    args = cli.build_parser().parse_args(["correct", "in.png", "--out", "out.png"])
    assert args.method is None
    assert args.pipeline is None
    result = cli.cmd_correct(args)
    assert result == 1  # fails cleanly, not a KeyError/crash


def test_pipeline_flag_accepts_an_ordered_stage_list():
    args = cli.build_parser().parse_args(
        ["correct", "in.png", "--out", "out.png", "--pipeline", "white_patch", "clahe"]
    )
    assert args.pipeline == ["white_patch", "clahe"]


def test_ablation_flags_parse_to_the_expected_dests():
    args = cli.build_parser().parse_args(
        ["correct", "in.png", "--out", "out.png",
         "--pipeline", "white_patch", "clahe", "--no-clahe"]
    )
    assert args.no_clahe is True
    assert args.no_gray_world is False
    assert args.no_white_patch is False


def test_score_rejects_ambiguous_method_and_pipeline_before_touching_the_file():
    """--method and --pipeline together must fail cleanly — and BEFORE any
    attempt to decode `path`, which does not even exist here."""
    args = cli.build_parser().parse_args(
        ["score", "/does/not/exist.mp4", "--method", "gray_world",
         "--pipeline", "clahe"]
    )
    result = cli.cmd_score(args)
    assert result == 1


def test_no_placeholder_ablation_flags_exist():
    """Only implemented stages get an ablation switch — no --no-depth,
    --no-backscatter, --no-attenuation, --no-temporal."""
    parser = cli.build_parser()
    score_actions = {a.dest for a in parser._subparsers._group_actions[0].choices["score"]._actions}
    for placeholder in ("no_depth", "no_backscatter", "no_attenuation", "no_temporal"):
        assert placeholder not in score_actions
    assert set(cli.ABLATION_DEST.values()) <= score_actions
