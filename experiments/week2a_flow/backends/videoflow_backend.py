"""VideoFlow-MOF wrapper implementing uw.flow.OpticalFlowBackend. EXPLORATORY.

Model:      VideoFlow MOFNetStack (Shi et al., ICCV 2023) — the multi-frame
            ("MOF", 5-frame) variant, the reason this candidate is here.
Source:     https://github.com/XiaoyuShi97/VideoFlow  (Apache-2.0)
Checkpoint: MOF_sintel.pth from the authors' Google Drive — the checkpoint
            configs/multiframes_sintel_submission.py points at, i.e. the
            repo's own default inference path.
Config:     configs/multiframes_sintel_submission.py, unmodified except
            `MOFNetStack.mixed_precision = False` (see below).

Environment: runs in its own interpreter, experiments/week2a_flow/.venv-videoflow,
because it needs timm==0.4.12 (for `timm.models.layers` and
`timm.create_model('twins_svt_large')`) which is incompatible with a modern
timm. It is never imported into the same process as the other backends —
SEA-RAFT, FlowIt and VideoFlow all ship a flat top-level `core.utils`.

Preprocessing:
  1. linear-light Frame -> sRGB encoding (uw.colorspace.linear_to_srgb)
  2. uint8 RGB -> float32 tensor (1, N, 3, H, W) in [0, 255]; MOFNet.forward
     applies `2*(x/255)-1` internally, so 0..255 is the documented scale.
  3. no resize in the wrapper: frames arrive on the common 960x540 grid.
  4. RAFT-style InputPadder pads H,W to a multiple of 8 (540 -> 544,
     replicate) and unpads the output — the repo's own inference.py does
     exactly this.

Temporal context: MOFNet takes N=5 frames and emits N-2 forward flows
(w1->w2, w2->w3, w3->w4) plus N-2 backward flows. This wrapper builds the
window in the direction of travel,

    W = [t-2d, t-d, t, t+d, t+2d]      d = index_t1 - index_t

and reads forward-flow index 1, i.e. W2 -> W3 = index_t -> index_t1. Note d
is the full signed stride, not its sign: MOFNet only ever emits flow between
CONSECUTIVE frames of its window, so serving a lag-k pair means giving it a
window sampled at stride k. For k > 1 that is off this checkpoint's training
distribution (adjacent video frames) — a structural constraint of the
architecture that a lag study has to account for, and one the pairwise
backends do not share. The
window is symmetric about the evaluated pair, and the same rule produces the
backward flow from an independent forward pass on the reversed window rather
than from the model's own backward head — so the forward/backward
consistency check costs this backend two real inferences, exactly as it does
for the pairwise backends. (MOFNet does emit both directions per pass; that
is a genuine efficiency advantage of the architecture, but reusing it here
would make its FB numbers incomparable, since the two directions would share
a decoder state.) Windows are clamped at sequence ends; the actual frames
used are always reported in metadata["context_indices"].

Deviations from the documented path, all forced and all recorded:
  * The README's environment (pytorch 1.6 + cudatoolkit 10.1) does not exist
    for Apple Silicon. Ran on current torch with MPS/CPU instead; the pip
    deps are the documented ones (yacs loguru einops timm==0.4.12 imageio).
  * inference.py wraps the net in torch.nn.DataParallel purely to load a
    `module.`-prefixed checkpoint and then uses `.module` anyway. This
    wrapper strips the prefix and loads the bare module — same weights, no
    DataParallel on a single non-CUDA device.
  * `mixed_precision` set to False. The repo hardcodes
    `autocast = torch.cuda.amp.autocast`, which cannot enable half precision
    on a non-CUDA device; running fp32 is the honest, non-degraded reading
    of that config knob rather than relying on a silently-disabled autocast.
  * The optional `alt_cuda_corr` extension is NOT built (the README calls it
    optional and inference-only); `corr_fn` stays at the default all-pairs
    implementation, as shipped.
No source file of the vendored repo was edited.
"""

from __future__ import annotations

import os
import sys
import time

import numpy as np
import torch

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from experiments.week2a_flow.common import model_input_srgb_u8  # noqa: E402
from uw.flow import FlowResult, OpticalFlowBackend  # noqa: E402

VF_DIR = os.path.abspath(os.path.join(_HERE, "..", "vendor", "VideoFlow"))
CKPT = os.path.abspath(os.path.join(_HERE, "..", "checkpoints", "videoflow", "MOF_sintel.pth"))

INPUT_FRAMES = 5
FORWARD_INDEX = 1  # W2 -> W3 within the 5-frame window


class VideoFlowMOFBackend(OpticalFlowBackend):
    name = "videoflow_mof"

    def __init__(self, device: str = "mps"):
        for p in (VF_DIR, os.path.join(VF_DIR, "core")):
            if p not in sys.path:
                sys.path.insert(0, p)
        # The repo's config module resolves a repo-relative default
        # checkpoint path at import time, so import from inside VF_DIR.
        _cwd = os.getcwd()
        os.chdir(VF_DIR)
        from configs.multiframes_sintel_submission import get_cfg  # type: ignore
        from core.Networks import build_network  # type: ignore
        from core.utils.utils import InputPadder  # type: ignore

        cfg = get_cfg()
        cfg.MOFNetStack.mixed_precision = False  # see module docstring
        cfg.model = CKPT
        self.cfg = cfg
        self._InputPadder = InputPadder

        model = build_network(cfg)
        state = torch.load(CKPT, map_location="cpu", weights_only=True)
        state = {k[len("module."):] if k.startswith("module.") else k: v
                 for k, v in state.items()}
        missing, unexpected = model.load_state_dict(state, strict=False)
        if missing or unexpected:
            raise RuntimeError(
                f"checkpoint/state_dict mismatch: {len(missing)} missing, "
                f"{len(unexpected)} unexpected keys — refusing to run a "
                f"partially-loaded model. missing[:5]={list(missing)[:5]} "
                f"unexpected[:5]={list(unexpected)[:5]}"
            )
        self.device = torch.device(device)
        self.model = model.to(self.device).eval()
        self._torch_version = torch.__version__
        os.chdir(_cwd)  # never leave the process's cwd moved

    def describe(self) -> dict:
        return {
            "backend": self.name,
            "model": "VideoFlow MOFNetStack (5-frame multi-frame)",
            "paper": "arXiv:2303.08340 (ICCV 2023)",
            "repository": "https://github.com/XiaoyuShi97/VideoFlow",
            "repo_commit": _git_head(VF_DIR),
            "checkpoint": "MOF_sintel.pth",
            "checkpoint_source": "authors' Google Drive (gdown)",
            "license": "Apache-2.0",
            "config": ("configs/multiframes_sintel_submission.py, "
                       "MOFNetStack.mixed_precision=False, corr_fn=default "
                       "(all-pairs; alt_cuda_corr extension NOT built)"),
            "input_frames": INPUT_FRAMES,
            "decoder_depth": int(self.cfg.MOFNetStack.decoder_depth),
            "python": sys.version.split()[0],
            "torch": self._torch_version,
            "timm": _timm_version(),
            "device_requested": str(self.device),
            "hardware": "Apple M4 (24 GB unified memory), macOS; no CUDA",
            "isolated_env": "experiments/week2a_flow/.venv-videoflow (timm==0.4.12)",
            "multi_frame": True,
            "preprocessing": (
                "linear Frame -> linear_to_srgb -> uint8 RGB -> float32 tensor "
                "(1,5,3,H,W) in [0,255]; model normalises to [-1,1] internally; "
                "InputPadder pads H,W to a multiple of 8 (replicate) and unpads "
                "the output. No resize in the wrapper."
            ),
            "native_confidence": "none — MOFNet exposes no confidence/uncertainty head",
            "modifications_to_third_party_code": (
                "none to vendored source files; call-site only — see wrapper docstring"
            ),
        }

    def _window(self, n_frames: int, index_t: int, index_t1: int):
        """5-frame window at the same stride as the requested pair.

        MOFNet emits flow between CONSECUTIVE frames of its window, so a
        lag-k pair can only be served by handing it a window sampled at
        stride k: [t-2k, t-k, t, t+k, t+2k]. That is a real architectural
        limitation, not a wrapper convenience — the checkpoint was trained on
        adjacent video frames, so for |k| > 1 the model runs off its training
        distribution (its "temporal context" is now k frames apart). The
        alternative, chaining k adjacent-frame flows, accumulates error and
        is not obviously better. Both facts are recorded in the metadata so a
        lag study can weigh MOF's numbers accordingly.
        """
        d = index_t1 - index_t
        if d == 0:
            raise ValueError("index_t and index_t1 must differ")
        win = [index_t - 2 * d, index_t - d, index_t, index_t1, index_t1 + d]
        # Clamp into range, keeping the evaluated pair at positions 2 and 3.
        # A clamp duplicates an end frame, which is what the repo's own
        # sequence handling does at clip boundaries; it is recorded.
        lo, hi = 0, n_frames - 1
        return [min(max(i, lo), hi) for i in win]

    @torch.no_grad()
    def estimate(self, frames, index_t: int, index_t1: int) -> FlowResult:
        win = self._window(len(frames), index_t, index_t1)
        arrs = [model_input_srgb_u8(frames[i]).astype(np.float32) for i in win]
        stack = np.stack(arrs, axis=0)                       # N,H,W,3
        t = torch.from_numpy(stack).permute(0, 3, 1, 2)[None]  # 1,N,3,H,W
        t = t.to(self.device)
        h, w = t.shape[-2:]

        t0 = time.perf_counter()
        padder = self._InputPadder(t.shape)
        # NB: VideoFlow's InputPadder.pad() takes ONE tensor and returns a
        # tensor, unlike the SEA-RAFT/FlowIt version of the same class,
        # which is variadic and returns a list. Its _pad is 6-long so
        # replicate padding works on the 5D (B,N,3,H,W) stack.
        padded = padder.pad(t)
        net_h, net_w = padded.shape[-2:]
        out, _ = self.model(padded, {})
        out = padder.unpad(out[0])                            # 2*(N-2), 2, H, W
        if self.device.type == "mps":
            torch.mps.synchronize()
        runtime = time.perf_counter() - t0

        flow = out[FORWARD_INDEX]
        flow_np = flow.permute(1, 2, 0).float().cpu().numpy().astype(np.float32)
        valid = np.isfinite(flow_np).all(axis=2)

        return FlowResult(
            flow=flow_np,
            valid_mask=valid,
            confidence=None,
            metadata={
                "backend": self.name,
                "checkpoint": "MOF_sintel.pth",
                "device": str(self.device),
                "inference_size": (int(net_h), int(net_w)),
                "output_size": (int(h), int(w)),
                "source_size": tuple(int(x) for x in frames[index_t].image.shape[:2]),
                "index_t": int(index_t),
                "index_t1": int(index_t1),
                "context_indices": [int(i) for i in win],
                "frame_stride": int(index_t1 - index_t),
                "off_distribution": bool(abs(index_t1 - index_t) != 1),
                "context_note": (
                    "5-frame window at the SAME STRIDE as the evaluated pair, "
                    "ordered in the direction of travel; the pair sits at "
                    "window positions 2 and 3, so the model sees 2 steps "
                    "before and 1 after it. Duplicated indices mean a "
                    "clip-boundary clamp. For |stride| > 1 the window is "
                    "frame-subsampled, which is OFF this checkpoint's training "
                    "distribution (it was trained on adjacent video frames)."
                ),
                "runtime_s": float(runtime),
                "runtime_note": (
                    "one MOFNet pass also produces the other 2 forward and all "
                    "3 backward flows of this window; only the pair's flow is "
                    "used here, so this is the cost of an isolated pair, not "
                    "the amortised per-pair cost on a long clip."
                ),
            },
        )


def _timm_version():
    try:
        import timm
        return timm.__version__
    except Exception:
        return None


def _git_head(path: str) -> str | None:
    import subprocess
    try:
        return subprocess.check_output(["git", "-C", path, "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return None
