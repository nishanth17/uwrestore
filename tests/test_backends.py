"""Tests for the promoted flow backends' plumbing — no torch required.

`uw/searaft.py` and `uw/waft.py` cannot be exercised end-to-end in the
ordinary venv: they need torch, which is deliberately not a project
dependency. What CAN and must be tested here is everything around the model —
that importing the modules costs nothing, that a missing checkout or
checkpoint fails with instructions rather than an AttributeError, that the
padding arithmetic matches each repo's own padder, and above all that the
import isolation works, since that is the mechanism letting two research
repositories with colliding top-level packages live in one process.

The models themselves are checked against known motion by
`experiments/week2b_temporal/scripts/searaft_check.py` and Phase 2A's
`synthetic_check.py`, which run in the isolated interpreter.
"""

import os
import sys
import textwrap

import numpy as np
import pytest

from uw import cli, searaft, waft
from uw.flow import OpticalFlowBackend, isolated_repo_imports, model_input_srgb_u8
from uw.types import Frame


def test_importing_the_backends_does_not_pull_in_torch():
    """The whole point of the lazy import: `uw.metrics` and `uw.cli` must stay
    usable in a numpy+opencv venv."""
    assert "torch" not in sys.modules
    assert issubclass(searaft.SeaRaftBackend, OpticalFlowBackend)
    assert issubclass(waft.WaftBackend, OpticalFlowBackend)
    assert searaft.SeaRaftBackend.name == "searaft"
    assert waft.WaftBackend.name == "waft"


def test_metrics_module_imports_no_backend():
    """`uw.metrics` receives a backend; it must never choose one."""
    import uw.metrics

    source = open(uw.metrics.__file__).read()
    assert "import torch" not in source
    assert "uw.searaft" not in source and "uw.waft" not in source


# ---------------------------------------------------------------------------
# Locating the checkouts and checkpoints
# ---------------------------------------------------------------------------


def test_missing_searaft_checkout_names_the_clone_command(monkeypatch, tmp_path):
    monkeypatch.setattr(searaft, "_SEARAFT_DIR_CANDIDATES", (str(tmp_path),))
    with pytest.raises(FileNotFoundError) as exc:
        searaft.searaft_dir()
    assert "git clone" in str(exc.value)
    assert "UW_SEARAFT_DIR" in str(exc.value)


def test_missing_waft_checkout_names_the_clone_and_its_prerequisite(monkeypatch, tmp_path):
    monkeypatch.setattr(waft, "_WAFT_DIR_CANDIDATES", (str(tmp_path),))
    with pytest.raises(FileNotFoundError) as exc:
        waft.waft_dir()
    message = str(exc.value)
    assert "git clone" in message
    assert "depth_anything_v2_vits.pth" in message      # the documented prerequisite
    assert "UW_WAFT_DIR" in message


def test_missing_waft_checkpoint_names_the_download(monkeypatch, tmp_path):
    monkeypatch.setattr(waft, "_WAFT_CKPT_CANDIDATES", (str(tmp_path / "nope.pth"),))
    with pytest.raises(FileNotFoundError) as exc:
        waft.waft_checkpoint()
    assert "gdown" in str(exc.value)
    assert "UW_WAFT_CHECKPOINT" in str(exc.value)


def test_checkout_resolution_prefers_the_environment_override(monkeypatch, tmp_path):
    (tmp_path / "core").mkdir()
    (tmp_path / "config").mkdir()
    monkeypatch.setenv("UW_SEARAFT_DIR", str(tmp_path))
    monkeypatch.setattr(searaft, "_SEARAFT_DIR_CANDIDATES",
                        (os.environ.get("UW_SEARAFT_DIR"), "/nonexistent"))
    assert searaft.searaft_dir() == os.path.abspath(str(tmp_path))


# ---------------------------------------------------------------------------
# Padding arithmetic — each repo's own padder, reproduced
# ---------------------------------------------------------------------------


def test_reported_inference_size_is_what_the_network_sees():
    """RAFT pads to a multiple of 8, WAFT's Padder to a multiple of 112.

    The reported `inference_size` is the padded size, not the tensor the
    wrapper handed over — a 540-row frame is inferred at 544 by SEA-RAFT and
    at 560 by WAFT, and a provenance record that said 540 would be wrong.
    """
    assert [searaft._pad_to_8(n) for n in (540, 960, 544, 1080)] == [544, 960, 544, 1080]
    assert [waft._pad_to_112(n) for n in (540, 960, 560, 1008)] == [560, 1008, 560, 1008]
    # both are idempotent on an already-aligned size
    for n in (8, 16, 960):
        assert searaft._pad_to_8(searaft._pad_to_8(n)) == searaft._pad_to_8(n)
    for n in (112, 560, 1008):
        assert waft._pad_to_112(waft._pad_to_112(n)) == waft._pad_to_112(n)


# ---------------------------------------------------------------------------
# The shared model-input view
# ---------------------------------------------------------------------------


def test_model_input_view_is_srgb_uint8_and_leaves_the_frame_alone():
    image = np.array([[[0.0, 0.5, 1.0]]], dtype=np.float32)
    frame = Frame(image=image)
    view = model_input_srgb_u8(frame)
    assert view.dtype == np.uint8
    assert view.shape == (1, 1, 3)
    # linear 0.5 -> sRGB ~0.7354 -> 188; the encoding really is applied
    assert view[0, 0].tolist() == [0, 188, 255]
    assert np.array_equal(frame.image, image)          # not mutated
    assert frame.image.dtype == np.float32


def test_model_input_view_clips_out_of_range_linear_values():
    """gray-world output exceeds 1.0; a model input has to be a valid image
    even though the METRIC deliberately never clips."""
    frame = Frame(image=np.array([[[-0.4, 0.0, 7.0]]], dtype=np.float32))
    assert model_input_srgb_u8(frame)[0, 0].tolist() == [0, 0, 255]


# ---------------------------------------------------------------------------
# Import isolation — what lets SEA-RAFT and WAFT share a process
# ---------------------------------------------------------------------------


def _make_fake_repo(root, package, attribute):
    pkg = root / package
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "thing.py").write_text(f"VALUE = {attribute!r}\n")
    return str(root)


def test_isolated_imports_evict_only_modules_from_the_given_roots(tmp_path):
    """Two checkouts shipping the same top-level package name must not see
    each other's — the exact collision that broke WAFT when SEA-RAFT's
    `core/` was already on the path."""
    a = _make_fake_repo(tmp_path / "repo_a", "collide", "from-a")
    b = _make_fake_repo(tmp_path / "repo_b", "collide", "from-b")

    saved_path = list(sys.path)
    with isolated_repo_imports([a]):
        import collide.thing as first

        assert first.VALUE == "from-a"
        assert a in sys.path
    assert sys.path == saved_path                      # path restored
    assert "collide.thing" not in sys.modules          # and evicted
    assert "collide" not in sys.modules

    with isolated_repo_imports([b]):
        import collide.thing as second

        assert second.VALUE == "from-b"                # a clean second import
    assert "collide" not in sys.modules
    # the objects imported earlier keep working after eviction
    assert first.VALUE == "from-a"


def test_isolated_imports_leave_unrelated_modules_alone(tmp_path):
    """Evicting torch or its submodules would make a later import build
    duplicate classes and quietly break isinstance, so only modules loaded
    FROM the given roots may be removed."""
    root = _make_fake_repo(tmp_path / "repo", "solo", "x")
    sys.modules.pop("textwrap", None)
    with isolated_repo_imports([root]):
        import solo.thing  # noqa: F401
        import textwrap as freshly_imported  # noqa: F401

        import base64  # noqa: F401
    assert "solo.thing" not in sys.modules
    assert "base64" in sys.modules                     # unrelated: untouched
    assert "textwrap" in sys.modules


def test_isolated_imports_restore_state_even_when_the_body_raises(tmp_path):
    root = _make_fake_repo(tmp_path / "repo", "boom", "x")
    saved_path = list(sys.path)
    with pytest.raises(RuntimeError):
        with isolated_repo_imports([root]):
            import boom.thing  # noqa: F401

            raise RuntimeError("something went wrong mid-construction")
    assert sys.path == saved_path
    assert "boom.thing" not in sys.modules


# ---------------------------------------------------------------------------
# CLI wiring: WAFT is available, and is never the default
# ---------------------------------------------------------------------------


def test_searaft_is_the_canonical_backend_and_waft_is_not_a_default():
    assert cli.CANONICAL_FLOW_BACKEND == "searaft"
    assert set(cli.FLOW_BACKENDS) == {"searaft", "waft"}
    args = cli.build_parser().parse_args(["score", "clip.mp4"])
    assert args.flow_backend == "searaft"


def test_score_warns_when_a_non_canonical_backend_is_selected(capsys):
    cli._warn_non_canonical("searaft")
    assert capsys.readouterr().out == ""               # silent for the canonical one

    cli._warn_non_canonical("waft")
    out = capsys.readouterr().out
    assert "Non-canonical" in out
    assert "crosscheck" in out                         # points at the right tool
    assert "DIFFERENT" in out                          # says why, not just that


def test_crosscheck_defaults_to_the_two_backends_and_all_three_lags():
    args = cli.build_parser().parse_args(["crosscheck", "clip.mp4"])
    assert (args.a, args.b) == ("searaft", "waft")
    assert args.lags is None                           # i.e. DEFAULT_LAGS
    assert cli.DEFAULT_LAGS == (1, 4, 8)


def test_unknown_backend_is_rejected_with_the_available_names():
    with pytest.raises(ValueError, match="unknown flow backend"):
        cli._build_flow_backend("flowit", "cpu")
