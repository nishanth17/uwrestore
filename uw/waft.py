"""WAFT-a1 optical-flow backend — the optional manual cross-check.

**Not the canonical backend and not a default anywhere.** Phase 2A selected
SEA-RAFT-M (`uw/searaft.py`) as the canonical Phase 2B correspondence model
and that selection is closed. WAFT is promoted here for one purpose: when a
specific SEA-RAFT result looks suspicious, a second opinion should be one
import away rather than only reachable from the experiments tree.

The rules that came with it, from Phase 2A, hold:

* it is never run automatically during normal scoring — `uw score --temporal`
  uses SEA-RAFT unless you say otherwise, and says so loudly if you do;
* the two backends are never averaged, and there is no combined-backend
  metric anywhere;
* **cross-backend residuals are only meaningful on the INTERSECTION of the
  two validity masks.** WAFT masks less than SEA-RAFT nearly everywhere
  (15/15 clip-lag cells tie-or-better on coverage in the Phase 2A lag study),
  so comparing each on its own mask measures masking policy, not
  correspondence quality. Use `uw.metrics.compare_backends_common_mask`
  (or `uw crosscheck`), which is the promoted form of Phase 2A's
  `scripts/common_mask_compare.py`.

What Phase 2A actually measured, for context on when a second opinion is
worth the runtime. Scored on the common mask, SEA-RAFT was equal-or-better in
**14 of 15** clip-lag cells, so WAFT's headline advantages — best FB coverage,
tightest round-trip error tail, best coverage retention with lag — are about
how much frame you get to measure rather than how good the correspondence is.
Its known weakness is **low-contrast** independent motion: it smooths straight
through the dark shark on `murky_shark @8` and reports 96.8 % valid where
SEA-RAFT cuts out the bottom third. Its known strength is the converse:
where SEA-RAFT conservatively invalidates a whole smooth moving subject (the
eel body), WAFT keeps more of it in the measured region. Those are the two
situations where asking it is informative.

-------------------------------------------------------------------------
Dependency and environment handling (CLAUDE.md invariant 8)
-------------------------------------------------------------------------
Same contract as `uw/searaft.py`: torch is imported lazily inside
`__init__`, nothing else under `uw/` imports this module, and
`pyproject.toml` is unchanged. Run it from the isolated Phase 2A
interpreter:

    experiments/week2a_flow/.venv-flow/bin/python -m uw.cli crosscheck \
        data/testset/murky/MURKYSHARK.MP4 --start 0 --frames 41

WAFT is ~3x SEA-RAFT's runtime here (2.0-3.0 s vs 0.75 s per inference) in
the same memory class (2.4 vs 2.2 GB peak MPS), which is the other reason it
is a spot-check rather than a default.

-------------------------------------------------------------------------
Provenance
-------------------------------------------------------------------------
Model:      WAFT-a1 (Wang & Deng, 2025), "Warping-Alone Field Transforms" —
            RAFT's cost volume replaced by high-resolution warping.
Repository: https://github.com/princeton-vl/WAFT @ b152ff1  (BSD-3-Clause)
Checkpoint: tar-c-t.pth (245 MB), the file the README explicitly recommends
            "for downstream applications" — TartanAir -> Chairs -> Things,
            the zero-shot generalisation model. Same selection principle as
            SEA-RAFT's: a general-purpose checkpoint, not a Sintel- or
            KITTI-finetuned one.
Config:     config/a1/tar-c-t.json, **unmodified**. It is already `scale: 0`,
            and demo.py / evaluate.py default `--scale 0.0`, so unlike
            SEA-RAFT this backend needed no config change at all. Its trained
            crop is 432x960, so on the 960x540 metric grid it sees 25 % more
            height than it was trained on — ordinary for flow evaluation
            (Sintel is 436 tall), and recorded rather than corrected for.

Preprocessing, which differs from SEA-RAFT's in two documented ways:
  1. linear-light Frame -> sRGB uint8 (uw.flow.model_input_srgb_u8), then a
     float32 tensor in [0, 255] — same as SEA-RAFT so far;
  2. the model's own normalize_image() applies **ImageNet mean/std** to
     x/255, NOT the [-1, 1] rescale SEA-RAFT uses, because WAFT-a1's frozen
     feature trunk is a DepthAnythingV2 ViT-S which expects those statistics;
  3. `Padder(factor=112)` **zero**-pads H,W to a multiple of 112 (the DINOv2
     patch size 14 times the 8x stride) — 540x960 -> 560x1008 — where RAFT
     replicate-pads to a multiple of 8. Both are the models' own code.
  4. no resize in the wrapper: frames arrive on the metric's grid.
This view exists only for correspondence estimation; every photometric
residual in `uw.metrics` is computed on `frame.image`, in linear light.

Two environment notes, unchanged from Phase 2A:
  * `ViTWarpV8` constructs `DepthAnythingFeature(..., pretrained=True)`,
    which reads a repo-relative `depth-anything-ckpts/depth_anything_v2_vits.pth`
    at __init__. That file is the README's documented prerequisite (95 MB,
    HuggingFace `depth-anything/Depth-Anything-V2-Small`). It is functionally
    redundant — the WAFT checkpoint carries all 239 `da_feature.*` tensors and
    `load_ckpt` overwrites them immediately — but supplying it is the
    documented route, and `pretrained=False` would have meant editing
    vendored source. Because the path is repo-relative, construction chdirs
    into the checkout and restores the working directory afterwards.
  * `xformers` is NOT installed. It is reached only inside the vendored
    DepthAnythingV2 DINOv2 layers, behind a `try/except ImportError` with a
    pure-PyTorch fallback, and has no CUDA-free build. Its absence is a
    runtime cost, not a correctness one, and is part of why WAFT is slower
    here than its paper's relative-speed claims suggest.

No vendored source file is modified.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

import numpy as np

from uw.flow import FlowResult, OpticalFlowBackend, isolated_repo_imports, model_input_srgb_u8

CHECKPOINT_NAME = "tar-c-t.pth"
CONFIG_REL = "config/a1/tar-c-t.json"
REPO_COMMIT_EXPECTED = "b152ff1"

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# Where the (unedited) WAFT clone and its checkpoint live. Phase 2A put both
# under experiments/, and re-downloading 340 MB elsewhere buys nothing, so
# that stays the default. Overridable so the checkout can move.
_WAFT_DIR_CANDIDATES = (
    os.environ.get("UW_WAFT_DIR"),
    os.path.join(_REPO_ROOT, "vendor", "WAFT"),
    os.path.join(_REPO_ROOT, "experiments", "week2a_flow", "vendor", "WAFT"),
)
_WAFT_CKPT_CANDIDATES = (
    os.environ.get("UW_WAFT_CHECKPOINT"),
    os.path.join(_REPO_ROOT, "checkpoints", "waft", CHECKPOINT_NAME),
    os.path.join(_REPO_ROOT, "experiments", "week2a_flow", "checkpoints", "waft",
                 CHECKPOINT_NAME),
)


def waft_dir() -> str:
    """Locate the vendored WAFT checkout, or fail with instructions."""
    for candidate in _WAFT_DIR_CANDIDATES:
        if candidate and os.path.isdir(os.path.join(candidate, "config")):
            return os.path.abspath(candidate)
    raise FileNotFoundError(
        "WAFT checkout not found. Looked at: "
        + ", ".join(repr(c) for c in _WAFT_DIR_CANDIDATES if c)
        + ". Clone it with:\n"
        "  git clone --depth 1 https://github.com/princeton-vl/WAFT.git \\\n"
        "      experiments/week2a_flow/vendor/WAFT\n"
        "and fetch its documented DepthAnythingV2 prerequisite into\n"
        "  <checkout>/depth-anything-ckpts/depth_anything_v2_vits.pth\n"
        "  (huggingface-cli download depth-anything/Depth-Anything-V2-Small "
        "depth_anything_v2_vits.pth)\n"
        "or point UW_WAFT_DIR at an existing checkout."
    )


def waft_checkpoint() -> str:
    """Locate tar-c-t.pth, or fail with the download instruction."""
    for candidate in _WAFT_CKPT_CANDIDATES:
        if candidate and os.path.isfile(candidate):
            return os.path.abspath(candidate)
    raise FileNotFoundError(
        f"WAFT checkpoint {CHECKPOINT_NAME!r} not found. Looked at: "
        + ", ".join(repr(c) for c in _WAFT_CKPT_CANDIDATES if c)
        + ".\nFetch the README's recommended downstream checkpoint with:\n"
        "  gdown 1CxzBQx0iSg6AyIgt6MF0ROlF_cAeZLPC -O "
        "experiments/week2a_flow/checkpoints/waft/tar-c-t.pth\n"
        "or point UW_WAFT_CHECKPOINT at an existing copy."
    )


def _git_head(path: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", path, "rev-parse", "HEAD"], text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def _module_version(name: str) -> str | None:
    try:
        import importlib

        return importlib.import_module(name).__version__
    except Exception:
        return None


class WaftBackend(OpticalFlowBackend):
    """WAFT-a1 behind uw.flow.OpticalFlowBackend. A cross-check, not a default.

    Honours the project's normative coordinate convention identically to
    SEA-RAFT: `estimate(frames, t, t1)` returns source -> target (u, v) on the
    grid of the frames it was given, `t1 < t` requests backward flow, and
    `|t1 - t| > 1` requests a direct lag-k correspondence.
    """

    name = "waft"

    def __init__(self, device: str = "mps"):
        try:
            import torch
        except ImportError as exc:  # pragma: no cover - environment-dependent
            raise ImportError(
                "WAFT needs PyTorch, which is deliberately NOT a core project "
                "dependency (CLAUDE.md invariant 8). Run it from the isolated "
                "Phase 2A interpreter:\n"
                "  experiments/week2a_flow/.venv-flow/bin/python -m uw.cli "
                "crosscheck <path>"
            ) from exc

        repo = waft_dir()
        ckpt = waft_checkpoint()

        # Two things have to be contained here. (1) WAFT's top-level config/,
        # model/ and utils/ collide with SEA-RAFT's — `from utils.utils import
        # Padder` resolves to SEA-RAFT's core/utils/utils.py and raises — so
        # the imports happen inside isolated_repo_imports and are evicted
        # afterwards. (2) DepthAnythingFeature reads a repo-relative
        # checkpoint path at construction, so build from inside the checkout
        # and restore the working directory whatever happens.
        cwd = os.getcwd()
        with isolated_repo_imports([repo]):
            os.chdir(repo)
            try:
                from config.parser import json_to_args  # type: ignore
                from inference_tools import InferenceWrapper  # type: ignore
                from model import fetch_model  # type: ignore
                from utils.utils import load_ckpt  # type: ignore

                args = json_to_args(os.path.join(repo, CONFIG_REL))
                # demo.py / evaluate.py default --scale to 0.0 and parse_args
                # puts the CLI value last, so 0 is the documented inference
                # default and this is not a config change.
                args.scale = 0
                model = fetch_model(args)
                load_ckpt(model, ckpt)
                wrapped = InferenceWrapper(
                    model, scale=args.scale, train_size=args.image_size,
                    pad_to_train_size=False, tiling=False,
                )
            finally:
                os.chdir(cwd)

        self._torch = torch
        self.repo = repo
        self.checkpoint = ckpt
        self.args = args
        self.device = torch.device(device)
        self.model = model.to(self.device).eval()
        self.wrapped = wrapped
        self._xformers = _module_version("xformers")

    # -- provenance ---------------------------------------------------------

    def describe(self) -> dict:
        head = _git_head(self.repo)
        return {
            "backend": self.name,
            "role": "optional manual cross-check; NOT the canonical backend",
            "model": "WAFT-a1 (DepthAnythingV2 ViT-S trunk, vits refine net)",
            "paper": "arXiv:2506.21526v2 (2025)",
            "repository": "https://github.com/princeton-vl/WAFT",
            "repo_path": self.repo,
            "repo_commit": head,
            "repo_commit_expected_prefix": REPO_COMMIT_EXPECTED,
            "repo_commit_matches_expected": (
                head.startswith(REPO_COMMIT_EXPECTED) if head else None
            ),
            "checkpoint": self.checkpoint,
            "checkpoint_source": "authors' Google Drive (gdown)",
            "license": "BSD-3-Clause",
            "config": CONFIG_REL + " (unmodified; scale=0 is the demo/evaluate default)",
            "iters": int(self.args.iters),
            "python": sys.version.split()[0],
            "torch": self._torch.__version__,
            "xformers": self._xformers
            or "not installed (optional; pure-PyTorch attention fallback)",
            "device": str(self.device),
            "modifications_to_third_party_code": (
                "none. One documented prerequisite supplied: "
                "depth-anything-ckpts/depth_anything_v2_vits.pth from "
                "HuggingFace depth-anything/Depth-Anything-V2-Small."
            ),
            "preprocessing": (
                "linear Frame -> linear_to_srgb -> uint8 RGB -> float32 tensor "
                "in [0,255]; the model normalises with IMAGENET mean/std on "
                "x/255 (not [-1,1] like SEA-RAFT) because its frozen trunk is "
                "DepthAnythingV2 ViT-S; Padder(factor=112) ZERO-pads H,W to a "
                "multiple of 112 (540x960 -> 560x1008) and unpads the output. "
                "No resize in the wrapper."
            ),
            "native_confidence": (
                "mixture-of-Laplace log-b uncertainty, same head and read-out "
                "as SEA-RAFT; LOWER = more confident. Inspection only — not "
                "used by any metric, and not compared across backends."
            ),
            "known_limitation": (
                "smooths through LOW-CONTRAST independent motion and reports it "
                "valid (the dark shark on murky_shark @8: 96.8% valid where "
                "SEA-RAFT excludes the bottom third). Higher coverage than "
                "SEA-RAFT nearly everywhere, which is why its residuals are "
                "only comparable on a common mask."
            ),
        }

    # -- inference ----------------------------------------------------------

    def _tensor(self, frame):
        arr = model_input_srgb_u8(frame)                    # H,W,3 uint8 RGB
        t = self._torch.from_numpy(arr.astype(np.float32))  # 0..255
        return t.permute(2, 0, 1)[None].to(self.device)

    def estimate(self, frames, index_t: int, index_t1: int) -> FlowResult:
        torch = self._torch
        with torch.no_grad():
            img1 = self._tensor(frames[index_t])
            img2 = self._tensor(frames[index_t1])
            h, w = img1.shape[-2:]

            t0 = time.perf_counter()
            out = self.wrapped.calc_flow(img1, img2)
            flow = out["flow"][-1]
            info = out["info"][-1]
            if self.device.type == "mps":
                torch.mps.synchronize()
            runtime = time.perf_counter() - t0

            flow_np = flow[0].permute(1, 2, 0).float().cpu().numpy().astype(np.float32)

            # Same mixture-of-Laplace read-out as SEA-RAFT's get_heatmap.
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
                "checkpoint": CHECKPOINT_NAME,
                "device": str(self.device),
                # What the NETWORK saw: WAFT's Padder rounds each dimension up
                # to a multiple of 112 (DINOv2 patch 14 x stride 8), zero-padded.
                "inference_size": (_pad_to_112(h), _pad_to_112(w)),
                "model_input_size": (int(h), int(w)),
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


def _pad_to_112(n: int) -> int:
    """WAFT's Padder rounds each dimension up to a multiple of 112."""
    n = int(n)
    return n + (-n) % 112
