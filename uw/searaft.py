"""SEA-RAFT-M optical-flow backend — the canonical Phase 2B correspondence model.

Selected in Week 2 Phase 2A on measured, project-specific evidence (see
`experiments/week2a_flow/FINDINGS.md` §6, §7 and the @1/@4/@8 lag addendum):
deterministic on this MPS environment, ~0.75 s/inference, ~2.2 GB peak MPS
allocation, usable at direct @4 and @8, and equal-or-better than WAFT in
14/15 clip-lag cells when both were scored on the *intersection* of their
validity masks (largest real gap: swimthrough @8, 5.615x vs 5.043x).

Known limitation, carried forward deliberately: SEA-RAFT conservatively
invalidates large regions of smooth, low-texture, independently moving
subjects (the eel body is marked invalid as a solid blob). That is the safer
behaviour for a metric — it measures less rather than measuring wrongly —
but it is *why* valid coverage is a first-class part of every temporal
result rather than auxiliary metadata.

-------------------------------------------------------------------------
Dependency and environment handling (CLAUDE.md invariant 8)
-------------------------------------------------------------------------
This module is the ONLY place in `uw/` that imports torch, and it imports it
lazily inside `SeaRaftBackend.__init__`, not at module scope. Importing
`uw.searaft` therefore costs nothing; nothing else under `uw/` imports it,
and `uw/metrics.py` never does — it receives an already-constructed
`OpticalFlowBackend` (see `uw.metrics.evaluate_temporal`).

`pyproject.toml` is unchanged: the core project venv still has only numpy +
opencv, and temporal scoring is run from the isolated interpreter created in
Phase 2A:

    experiments/week2a_flow/.venv-flow/bin/python -m uw.cli score \
        data/testset/swimthrough/SWIMTHROUGH.MP4 --temporal

That venv already carries numpy, opencv and torch, and `python -m` puts the
repo root on `sys.path`, so the normal CLI runs there unmodified. Everything
except the temporal report runs in the ordinary `.venv`.

-------------------------------------------------------------------------
Provenance
-------------------------------------------------------------------------
Model:      SEA-RAFT (Wang, Lipson & Deng, ECCV 2024), "M" size
Repository: https://github.com/princeton-vl/SEA-RAFT  (BSD-3-Clause)
Commit:     9137517ba24e628442aec097d3afe71d03503b75 (as vendored)
Checkpoint: HuggingFace MemorySlices/Tartan-C-T-TSKH-spring540x960-M
            (TartanAir -> Chairs -> Things -> Sintel/KITTI/HD1K -> Spring)
Config:     config/eval/spring-M.json with `scale` set to 0.

`scale = 0` is the one config deviation, unchanged from Phase 2A and
verified against the repo's own training code rather than assumed. At eval,
calc_flow() resamples the input by 2**scale. This checkpoint was trained
with image_size [540, 960] and scale -1, i.e. on 540x960 crops covering a
~1080x1920 field of view; spring-M.json's eval scale=-1 reproduces that by
halving a full 1920x1080 Spring frame. Our frames are ALREADY that 2x
downscale, so scale=0 puts the network on the same content at the same
resolution. Leaving scale=-1 would run it at 270x480 — half the trained
scale. The repo's own sintel-M / kitti-M configs use scale=0 for exactly
this reason. No vendored source file is modified.

Preprocessing (a temporary, model-only view; the project stays linear-light):
  1. linear-light Frame -> sRGB encoding (uw.colorspace.linear_to_srgb)
  2. uint8 RGB, then a float32 tensor still in [0, 255] — SEA-RAFT's own
     forward() does 2*(x/255)-1 internally, so the documented input scale is
     0..255, NOT 0..1. Feeding [0,1] hands the network a near-black image.
  3. no resize here: the caller supplies frames already on the metric's
     evaluation grid.
  4. RAFT's InputPadder (the model's own code) replicate-pads H,W up to a
     multiple of 8 and unpads the output.
This view is never written back into a Frame and is never used for any
photometric measurement — every residual in `uw.metrics` is computed on
`frame.image`, i.e. in linear light.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

import numpy as np

from uw.flow import (
    FlowResult, OpticalFlowBackend, isolated_repo_imports, model_input_srgb_u8,
)

CHECKPOINT = "MemorySlices/Tartan-C-T-TSKH-spring540x960-M"
CONFIG_REL = "config/eval/spring-M.json"
REPO_COMMIT_EXPECTED = "9137517ba24e628442aec097d3afe71d03503b75"

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# Where the (unedited) SEA-RAFT clone lives. Phase 2A put it under
# experiments/, and re-cloning 400 MB elsewhere buys nothing, so that stays
# the default. Overridable so the checkout can move without a code change.
_SEARAFT_DIR_CANDIDATES = (
    os.environ.get("UW_SEARAFT_DIR"),
    os.path.join(_REPO_ROOT, "vendor", "SEA-RAFT"),
    os.path.join(_REPO_ROOT, "experiments", "week2a_flow", "vendor", "SEA-RAFT"),
)


def searaft_dir() -> str:
    """Locate the vendored SEA-RAFT checkout, or fail with instructions."""
    for candidate in _SEARAFT_DIR_CANDIDATES:
        if candidate and os.path.isdir(os.path.join(candidate, "core")):
            return os.path.abspath(candidate)
    raise FileNotFoundError(
        "SEA-RAFT checkout not found. Looked at: "
        + ", ".join(repr(c) for c in _SEARAFT_DIR_CANDIDATES if c)
        + ". Clone it with:\n"
        "  git clone --depth 1 https://github.com/princeton-vl/SEA-RAFT.git \\\n"
        "      experiments/week2a_flow/vendor/SEA-RAFT\n"
        "or point UW_SEARAFT_DIR at an existing checkout."
    )


def _pad_to_8(n: int) -> int:
    """RAFT's InputPadder rounds each dimension up to a multiple of 8."""
    return int(n) + (((int(n) // 8) + 1) * 8 - int(n)) % 8


def _git_head(path: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", path, "rev-parse", "HEAD"], text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


class SeaRaftBackend(OpticalFlowBackend):
    """SEA-RAFT-M behind uw.flow.OpticalFlowBackend.

    Honours the project's normative coordinate convention: `estimate(frames,
    t, t1)` returns source -> target (u, v) displacement on the grid of the
    frames it was given. `t1 < t` is legal and is how backward flow is
    requested; `|t1 - t| > 1` is legal and is how a lag-k *direct*
    correspondence is requested — no adjacent-flow chaining anywhere.
    """

    name = "searaft"

    def __init__(self, device: str = "mps", iters: int | None = None):
        try:
            import torch
        except ImportError as exc:  # pragma: no cover - environment-dependent
            raise ImportError(
                "SEA-RAFT needs PyTorch, which is deliberately NOT a core "
                "project dependency (CLAUDE.md invariant 8). Run temporal "
                "scoring from the isolated Phase 2A interpreter:\n"
                "  experiments/week2a_flow/.venv-flow/bin/python -m uw.cli "
                "score <path> --temporal"
            ) from exc

        repo = searaft_dir()
        # SEA-RAFT's modules import each other flat (`from raft import RAFT`),
        # so its core/ has to be on sys.path — and its top-level config/ and
        # utils/ collide with WAFT's, so the imports are contained and evicted
        # afterwards (see uw.flow.isolated_repo_imports). Without that, a
        # process that constructs both backends breaks whichever comes second.
        with isolated_repo_imports([repo, os.path.join(repo, "core")]):
            from config.parser import json_to_args  # type: ignore
            from raft import RAFT  # type: ignore

            args = json_to_args(os.path.join(repo, CONFIG_REL))
            args.scale = 0  # see module docstring
            if iters is not None:
                args.iters = iters
            model = RAFT.from_pretrained(CHECKPOINT, args=args)

        self._torch = torch
        self.repo = repo
        self.args = args
        self.device = torch.device(device)
        self.model = model.to(self.device).eval()

    # -- provenance ---------------------------------------------------------

    def describe(self) -> dict:
        head = _git_head(self.repo)
        return {
            "backend": self.name,
            "model": "SEA-RAFT-M",
            "paper": "arXiv:2405.14793 (ECCV 2024)",
            "repository": "https://github.com/princeton-vl/SEA-RAFT",
            "repo_path": self.repo,
            "repo_commit": head,
            "repo_commit_expected": REPO_COMMIT_EXPECTED,
            "repo_commit_matches_expected": (head == REPO_COMMIT_EXPECTED)
            if head else None,
            "checkpoint": CHECKPOINT,
            "checkpoint_source": "huggingface_hub",
            "license": "BSD-3-Clause",
            "config": CONFIG_REL + " with scale=0 (see module docstring)",
            "iters": int(self.args.iters),
            "python": sys.version.split()[0],
            "torch": self._torch.__version__,
            "device": str(self.device),
            "modifications_to_third_party_code": "none",
            "preprocessing": (
                "linear Frame -> linear_to_srgb -> uint8 RGB -> float32 tensor "
                "in [0,255]; model normalises to [-1,1] internally; RAFT "
                "InputPadder replicate-pads H,W to a multiple of 8 and unpads. "
                "No resize in the wrapper."
            ),
            "native_confidence": (
                "mixture-of-Laplace log-b uncertainty (SEA-RAFT custom.py "
                "get_heatmap); LOWER = more confident. Inspection only — not "
                "used by any metric."
            ),
            "known_limitation": (
                "conservatively invalidates smooth low-texture independently "
                "moving subjects (whole eel body); mean FB-valid coverage in "
                "the Phase 2A lag study fell ~97% @1 / ~91% @4 / ~83% @8"
            ),
        }

    # -- inference ----------------------------------------------------------

    def _tensor(self, frame):
        arr = model_input_srgb_u8(frame)                    # H,W,3 uint8 RGB
        t = self._torch.from_numpy(arr.astype(np.float32))  # 0..255
        return t.permute(2, 0, 1)[None].to(self.device)

    def estimate(self, frames, index_t: int, index_t1: int) -> FlowResult:
        torch = self._torch
        import torch.nn.functional as F  # noqa: N812

        with torch.no_grad():
            img1 = self._tensor(frames[index_t])
            img2 = self._tensor(frames[index_t1])
            h, w = img1.shape[-2:]

            t0 = time.perf_counter()
            scale = self.args.scale
            a = F.interpolate(img1, scale_factor=2 ** scale, mode="bilinear",
                              align_corners=False)
            b = F.interpolate(img2, scale_factor=2 ** scale, mode="bilinear",
                              align_corners=False)
            net_h, net_w = a.shape[-2:]
            out = self.model(a, b, iters=self.args.iters, test_mode=True)
            flow = out["flow"][-1]
            info = out["info"][-1]
            flow = F.interpolate(flow, scale_factor=0.5 ** scale, mode="bilinear",
                                 align_corners=False) * (0.5 ** scale)
            info = F.interpolate(info, scale_factor=0.5 ** scale, mode="area")
            if self.device.type == "mps":
                torch.mps.synchronize()
            runtime = time.perf_counter() - t0

            flow_np = flow[0].permute(1, 2, 0).float().cpu().numpy().astype(np.float32)

            # SEA-RAFT's own uncertainty read-out (custom.py::get_heatmap).
            raw_b = info[:, 2:]
            log_b = torch.zeros_like(raw_b)
            weight = info[:, :2].softmax(dim=1)
            log_b[:, 0] = torch.clamp(raw_b[:, 0], min=0, max=self.args.var_max)
            log_b[:, 1] = torch.clamp(raw_b[:, 1], min=self.args.var_min, max=0)
            heatmap = (log_b * weight).sum(dim=1)[0].float().cpu().numpy().astype(np.float32)

        return FlowResult(
            flow=flow_np,
            valid_mask=np.isfinite(flow_np).all(axis=2),
            confidence=heatmap,
            metadata={
                "backend": self.name,
                "checkpoint": CHECKPOINT,
                "device": str(self.device),
                # What the NETWORK saw, not what the wrapper handed it: RAFT's
                # own InputPadder replicate-pads both dimensions up to a
                # multiple of 8 inside forward() and unpads the output, so a
                # 540-row frame is inferred at 544. Same arithmetic as
                # core/utils/utils.py::InputPadder.
                "inference_size": (_pad_to_8(net_h), _pad_to_8(net_w)),
                "model_input_size": (int(net_h), int(net_w)),
                "output_size": (int(h), int(w)),
                "source_size": tuple(int(x) for x in frames[index_t].image.shape[:2]),
                "index_t": int(index_t),
                "index_t1": int(index_t1),
                "lag": int(index_t1 - index_t),
                "context_indices": [int(index_t), int(index_t1)],
                "runtime_s": float(runtime),
                "confidence_semantics": "log-b uncertainty; lower = more confident",
            },
        )
