# Week 2 Phase 1A — optical-flow backend bakeoff: findings

**Status: exploration complete, no selection made.** No backend has been
wired into `uw/metrics.py`, no project-wide default has been chosen, no
MC-Warp metric has been implemented, and no temporal correction exists. That
is Phase 1B, after review of what is written here.

---

## 1. What was built

| file | status | why |
|---|---|---|
| `uw/flow.py` | **permanent project code** | `FlowResult`, the `OpticalFlowBackend` interface, the normative coordinate convention, and the model-independent flow maths: `resize_flow` (rescales vectors with the grid), `warp_to_source`, `forward_backward_consistency`, `sample_flow`, `flow_magnitude`. numpy + opencv only. **Contains no backend and no default.** |
| `tests/test_flow.py` | permanent | 26 analytic tests of the conventions — channel order, direction, resize rescaling, warping, out-of-frame handling, the FB criterion either side of its threshold. Runs in the normal project venv. |
| `experiments/week2a_flow/**` | **exploratory, disposable** | four backend wrappers, isolated venvs, vendored repos, run scripts. Nothing under `uw/` imports any of it. |
| `outputs/flow_comparison/**` | local artifacts | gitignored; derived from local footage, so it stays local like the footage. |

`uw/metrics.py`, `uw/cli.py`, `uw/io.py`, `uw/types.py`, `uw/baselines.py`
and `uw/colorspace.py` are byte-identical to before this session.
`pyproject.toml` is untouched — the main project venv still has only numpy
and opencv.

### Coordinate convention (now normative, documented in `uw/flow.py`)

* flow is `(H, W, 2)` float32; `flow[y, x, 0] = u` is horizontal, positive
  toward increasing column (image right); `flow[y, x, 1] = v` is vertical,
  positive toward increasing row (image down). Channel order is `(u, v)`,
  i.e. `(x, y)` — **not** numpy's `(row, col)`.
* `estimate(frames, index_t, index_t1)` returns **source → target**
  displacement: a point at `(x, y)` in `frames[index_t]` is at
  `(x + u, y + v)` in `frames[index_t1]`.
* `index_t1 < index_t` is legal and is how backward flow is requested.
* Units are pixels **of the flow field's own grid**. Any resize must go
  through `resize_flow()`, which rescales `u` by the width ratio and `v` by
  the height ratio.

### Linear light is not violated

`Frame` stays linear-light everywhere. Each wrapper builds a **temporary**
sRGB-encoded uint8 view (`common.model_input_srgb_u8`) purely to feed the
pretrained network, because these models are trained on display-encoded
imagery and feeding them linear radiance is a silent domain shift that
crushes exactly the shadow detail a matcher relies on. That view is never
written back into a `Frame` and never used for measurement: **every
photometric residual in this report is computed on `frame.image`, i.e. in
linear light.**

The single downscale to the evaluation grid happens **in linear light**
(`cv2.INTER_AREA` on the linear array) *before* sRGB encoding, so the network
and the residual are looking at the same scene data, and the area-average is
done on the only values where averaging is physically meaningful.

---

## 2. Method

### Common evaluation resolution — 960×540

All three backends receive the identical 960×540 sRGB image (540×960 for the
two clips OpenCV decodes portrait), and every diagnostic is computed on that
grid. Nothing is upsampled back to 1920×1080: an upsampled 960×540 field
does not contain 1080p correspondence detail, and printing it at 1080p would
only imply that it does. Each backend's `inference_size` — the resolution
the network actually saw after its own internal padding — is recorded per
pair in `meta.json`.

### The common validity mask

Native confidence outputs are not comparable: SEA-RAFT emits a
mixture-of-Laplace log-b *uncertainty* (lower = better), FlowIt emits
separate *confidence* and *occlusion* heads from its optimal-transport
matching (higher = better), and VideoFlow-MOF emits **nothing**. They are
saved per pair for inspection but never compared to each other.

The cross-backend diagnostic is forward/backward consistency
(Sundaram–Brox–Keuper 2010), in `uw/flow.py`:

```
w  = flow_fwd(p)                    # source -> target
p' = p + w                          # its location in the target
w' = flow_bwd(p')                   # bilinear sample of the backward field
e  = ||w + w'||                     # round-trip error, in pixels
valid  <=>  e² ≤ 0.01·(||w||² + ||w'||²) + 0.5
```

* α = 0.01, β = 0.5 — the published constants, **identical for every
  backend**. Not re-tuned per model; the point is a shared yardstick, not a
  flattering one for each contender.
* **Boundary handling:** a pixel whose `p'` leaves the frame has no
  round-trip to check, so it is marked invalid and its error is left `NaN`
  rather than given a fabricated finite value. This makes the mask
  conservative at frame edges under strong camera motion — identically for
  all three.
* **Invalid regions:** non-finite flow in either direction invalidates the
  pixel. The backward field's finite mask is eroded by one pixel first, so a
  pixel is only trusted when the whole 2×2 bilinear support was finite.
* This costs **two inferences per evaluated pair**, deliberately. Both
  `FlowResult`s are held and reused for every metric and every image; nothing
  is recomputed per visualisation.

For VideoFlow-MOF the backward flow comes from an independent pass on the
reversed 5-frame window, **not** from MOFNet's own backward head. MOFNet does
emit both directions per pass — a real efficiency advantage, noted below —
but reusing it would make its FB numbers incomparable, since the two
directions would share a decoder state.

### Excerpt selection

Chosen by rule, not by eye (`scripts/survey_motion.py`, output committed as
`excerpts.json`): for each clip, the window whose ~1 s moving-average
inter-frame motion is highest, i.e. the most demanding stretch. Motion is
measured with **OpenCV Farneback**, deliberately not one of the candidates —
using a candidate to pick the frames it is later judged on would bias
selection toward whichever model likes that footage.

Twelve frames are decoded per clip and three pairs evaluated, positioned so
MOF's ±2-frame context always fits inside the excerpt without clamping:
pairs at local indices (4,5), (6,7), (8,9).

Measured camera motion across the frozen test set (median px/frame, source
resolution):

| clip | mean | median | p90 | max | excerpt frames |
|---|---|---|---|---|---|
| swimthrough | **10.51** | 9.79 | 17.27 | 25.81 | 195–206 |
| murky_eel | 10.09 | 10.27 | 14.58 | 21.90 | 650–661 |
| distance | 6.67 | 5.89 | 13.04 | 18.93 | 260–271 |
| lights | 3.70 | 3.33 | 6.29 | 9.53 | 85–96 |
| murky_shark | **0.03** | 0.01 | 0.08 | 0.15 | 2–13 |

**`swimthrough` is the strongest-camera-motion clip** — the prompt's fifth
category is the same clip as its first, so all five available clips were
evaluated rather than inventing a sixth. `murky_shark` turned out to be a
near-locked-off shot; it is kept as a useful control (does a backend
hallucinate motion when there is almost none?), not as a motion case.

---

## 3. Integration record

### Successfully evaluated — all three primary candidates, plus WAFT

**Nothing was dropped and nothing was substituted.** SEA-RAFT, FlowIt and
VideoFlow-MOF all ran on their documented paths. DPFlow was deliberately not
integrated (see §9).

WAFT was added **after** the first three-way comparison, as a devil's-advocate
check rather than to make up a number. The provisional reading of the
three-way result was "SEA-RAFT, on efficiency and robustness" — and
SEA-RAFT's own README opens by pointing at WAFT as the same lab's "new
efficient state-of-the-art" method. That is a direct challenge to the one
axis the recommendation rested on, so it was worth testing rather than
citing.

| | SEA-RAFT | WAFT | FlowIt | VideoFlow-MOF |
|---|---|---|---|---|
| model | SEA-RAFT-M | WAFT-a1 (DepthAnythingV2 ViT-S trunk) | FlowIt-M | MOFNetStack, 5-frame |
| paper | arXiv:2405.14793 (ECCV 2024) | arXiv:2506.21526v2 (2025) | arXiv:2603.28759 (BMVC 2026) | arXiv:2303.08340 (ICCV 2023) |
| repo | princeton-vl/SEA-RAFT @ `9137517` | princeton-vl/WAFT @ `b152ff1` | sadrasafa/FlowIt @ `a6fa468` | XiaoyuShi97/VideoFlow @ `5148930` |
| checkpoint | `Tartan-C-T-TSKH-spring540x960-M` | `tar-c-t.pth` | `C-T-TSKH_Flowit-M.pth` | `MOF_sintel.pth` |
| source | HuggingFace (automatic) | Google Drive (`gdown`) | Google Drive (`gdown`) | Google Drive (`gdown`) |
| license | BSD-3-Clause | BSD-3-Clause | see repo LICENSE/NOTICE | Apache-2.0 |
| env | `.venv-flow` | `.venv-flow` | `.venv-flow` | **`.venv-videoflow`** (timm 0.4.12) |
| Python / torch | 3.13.5 / 2.13.0 | 3.13.5 / 2.13.0 | 3.13.5 / 2.13.0 | 3.13.5 / 2.13.0 |
| device | MPS (Apple M4, 24 GB) | MPS | MPS | MPS |
| network input | 960×540 → pad 960×544 (÷8) | 960×540 → pad 1008×560 (÷112) | 960×540 → pad 960×544 (÷32) | 960×540 → pad 960×544 (÷8) |
| pad mode | replicate | **zero** | replicate | replicate |
| input scale | `[0,255]`, model → `[-1,1]` | `[0,255]`, model → **ImageNet mean/std** | `[0,255]`, model → `[-1,1]` | `[0,255]`, model → `[-1,1]` |
| multi-frame | no | no | no | **yes, 5 frames** |
| native confidence | log-b uncertainty | log-b uncertainty (same head) | `conf` + `occ` | **none** |
| config changes | `scale` 0 (see below) | **none** | none | `mixed_precision=False` |

Checkpoints were matched on **training recipe, not leaderboard rank**: all
four are the general-purpose / zero-shot-generalisation checkpoints, not
KITTI- or Sintel-finetuned variants. Underwater footage is out of
distribution for all of them, so the cross-dataset checkpoint is the honest
one. WAFT's `tar-c-t.pth` is specifically the file its README recommends
"for downstream applications".

WAFT's preprocessing is the one real asymmetry in the table: it normalises
with ImageNet statistics rather than to `[-1, 1]`, because its frozen feature
trunk is a DepthAnythingV2 ViT-S, and it zero-pads to a multiple of 112 (the
DINOv2 patch size 14 × its 8× stride) where the others replicate-pad. Both
are that model's own documented behaviour, not a wrapper choice.

### Deviations from each documented inference path

No vendored source file was edited, for any backend. Everything below is a
config value or a call-site choice, documented in the relevant wrapper's
module docstring.

**SEA-RAFT — one config value.** `config/eval/spring-M.json` with `scale` set
to `0` instead of `-1`. Verified against the repo's training code rather than
assumed: in `core/datasets.py`, `scale` is the *augmentation zoom exponent*
and `image_size` is the crop actually fed to the network, so this checkpoint
(`image_size [540, 960]`, `scale -1`) was trained on 540×960 crops covering a
~1080×1920 field of view. `spring-M.json`'s eval `scale=-1` reproduces that
by halving a full 1920×1080 Spring frame. Our frames *are* already that 2×
downscale, so `scale=0` puts the network on the same content at the same
resolution; the only difference is that the downscale was done once, up
front, by `cv2.INTER_AREA` in linear light. Leaving `scale=-1` would have run
the network at 270×480 — half the trained scale and half the resolution the
others get. The repo's own `sintel-M`/`kitti-M` configs use `scale=0` for
exactly this reason.

**WAFT — none.** `config/a1/tar-c-t.json` is already `scale: 0`, and
`demo.py`/`evaluate.py` default `--scale 0.0`, so feeding the 960×540 grid
through the documented `InferenceWrapper.calc_flow()` needed no change at
all. Its trained crop is 432×960, so it sees 25% more height than it was
trained on — ordinary for flow evaluation (Sintel is 436 tall), and recorded
rather than corrected for.

**FlowIt — none.** `demo.py`'s documented path is `--resize 960 540`, which
is the common evaluation grid; the wrapper hands it a frame already at that
size and uses `MODEL_CONFIG` defaults verbatim.

**VideoFlow-MOF — three forced call-site adaptations.**
1. *Environment.* The README's `pytorch=1.6.0 + cudatoolkit=10.1` does not
   exist for Apple Silicon. Current torch on MPS instead; the pip
   dependencies are the documented ones (`yacs loguru einops timm==0.4.12
   imageio`) and installed clean on Python 3.13 first try. The one import
   risk in the repo — `twins_ft.py`'s `timm.models.fx_features`, absent from
   modern timm — is commented out upstream and never reached.
2. *Checkpoint loading.* `inference.py` wraps the net in
   `torch.nn.DataParallel` only to load a `module.`-prefixed state dict and
   then uses `.module` anyway. The wrapper strips the prefix and loads the
   bare module, and **fails loudly** on any missing or unexpected key rather
   than silently running a half-initialised model.
3. *`MOFNetStack.mixed_precision = False`.* The repo hardcodes
   `autocast = torch.cuda.amp.autocast`, which cannot enable half precision
   on a non-CUDA device — it would warn and silently disable itself. Setting
   the config knob to `False` makes the fp32 run explicit rather than
   accidental.

### The one-fix allowance

Only WAFT consumed it. `ViTWarpV8` constructs
`DepthAnythingFeature(..., pretrained=True)`, which reads a local
`depth-anything-ckpts/depth_anything_v2_vits.pth` at `__init__`. That file is
the README's documented prerequisite, so it was downloaded from HuggingFace
(`depth-anything/Depth-Anything-V2-Small`, 95 MB). It is functionally
redundant — the WAFT checkpoint already carries all 239 `da_feature.*`
tensors and `load_ckpt` overwrites them immediately — but supplying it is the
documented route, and the alternative (`pretrained=False`) would have meant
editing vendored source.

**xformers was not installed.** WAFT's README asks for it, but it is reached
only inside the vendored DepthAnythingV2 DINOv2 layers, behind a
`try/except ImportError` that falls back to plain PyTorch attention. It is an
optional accelerator with no CUDA-free build — precisely the "prefer the
official slower non-extension path" case in the brief. Its absence is a
runtime cost, not a correctness one, and it is part of why WAFT is slower
here than its paper's relative-speed claims suggest.

**No CUDA/C++ compilation, no dependency-downgrade chain, and no third-party
source edits were undertaken at any point.**

### A wrapper bug the synthetic check caught before any real run

VideoFlow's `InputPadder.pad()` takes a **single** tensor and returns a
tensor, and its `_pad` is 6 elements long so replicate padding works on the
5-D `(B, N, 3, H, W)` stack. SEA-RAFT's and FlowIt's `InputPadder` — same
class name, same docstring, all three copied from RAFT — is **variadic and
returns a list**. Indexing `[0]` into VideoFlow's return silently sliced off
the batch dimension, and MOFNet failed with `ValueError: not enough values to
unpack (expected 5, got 4)`. Caught by the known-motion test before any
real-footage run, which is exactly what that test is for.

### Cost of running FlowIt on this hardware

FlowIt builds a **global** cost volume at ¼ resolution: at 960×544 that is a
`(240·136)² ≈ 1.07 × 10⁹`-entry matrix, ~4.3 GB in fp32 before the Sinkhorn
temporaries. Peak MPS driver allocation was **22.8 GB**. On a 24 GB
unified-memory M4 the first pair ran in 32 s, then the allocator fragmented,
the machine went ~11 GB into swap and the second pair stalled indefinitely.
Adding `gc.collect()` + `torch.mps.empty_cache()` between pairs in the runner
(measurement hygiene only — it frees cached blocks and changes no result)
made the run complete. Worth knowing before Phase 1B considers FlowIt for
anything per-frame: its memory is quadratic in pixel count, so 1080p is not
"slower", it is out of reach on this machine. Model size does not help —
the cost volume depends on pixels, not parameters.

---

## 4. Synthetic known-motion check — all four pass

Run before any real-footage result was trusted
(`scripts/synthetic_check.py`; reports in
`outputs/flow_comparison/<backend>/synthetic_check.json`). Every case is a
**five-frame** constant-velocity sequence, not an isolated pair, so the
multi-frame backend is exercised through the same code path as the pairwise
ones; the evaluated pair is always (2, 3). The imagery is a real murky
underwater frame — particulate, low contrast — not a checkerboard that every
model solves trivially.

| case | what it would catch | SEA-RAFT | WAFT | FlowIt | MOF |
|---|---|---|---|---|---|
| **A** translation, GT (+12.0, −5.0) px, from five offset crops of one full-res frame (no resampling, no invented borders) | wrong magnitude; sign flip; x/y channel swap | (11.999, −5.002) EPE **0.011** | (11.982, −4.998) EPE **0.038** | (11.984, −4.963) EPE **0.042** | (12.000, −4.970) EPE **0.032** |
| … EPE if the channels were swapped | — | 24.04 | 24.03 | 24.00 | 24.02 |
| **B** same sequence, indices reversed | forward/backward confusion | (−11.991, +5.001) | (−11.998, +5.007) | (−11.995, +4.982) | (−12.009, +4.976) |
| **C** off-centre cumulative zoom, GT = (s−1)(p−c), max 34.6 px | spatial flip/transpose a constant field cannot reveal | EPE **0.032** | **0.047** | **0.059** | **0.038** |
| … EPE if GT flipped L-R / U-D | — | 23.40 / 11.39 | 23.40 / 11.39 | 23.37 / 11.39 | 23.40 / 11.40 |
| **D** `resize_flow` to ½ and 1.5× | vector magnitudes not rescaled with the grid | (6.000,−2.501) / (17.999,−7.503) | (5.991,−2.499) / (17.973,−7.497) | (5.992,−2.481) / (17.976,−7.444) | (6.000,−2.485) / (18.001,−7.455) |
| **D** analytic (model-free) constant field | same, with no model in the loop | exact | exact | exact | exact |
| **E** `warp_to_source` on **linear-light** data | warping direction; residual path | 3.8e−4 vs 7.9e−2 (**209×**) | 1.1e−3 (**71×**) | 1.3e−3 (**61×**) | 9.8e−4 (**81×**) |
| **F** NaN / Inf anywhere | non-finite output | 0 | 0 | 0 | 0 |

Expected values are in the table so a later reader can see what "pass" meant.
`|DX| ≠ |DY|` with opposite signs is deliberate: a channel swap or sign flip
cannot slip through, and the counterfactual EPEs (24 px swapped, 11–23 px
spatially flipped, against 0.01–0.06 px actual) show the test has the
discriminating power claimed for it.

**This validates the wrappers, not the models.** Passing says the coordinate
convention, direction, resize rescaling and warp are correct. It says nothing
about underwater performance.

---

## 5. Reproducibility — one backend is not deterministic

Not in the original plan; added because the two full runs of the bakeoff
disagreed on FlowIt's numbers. PLAN.md's operating loop requires ruling out
nondeterminism before treating a changed number as a regression, so this was
measured rather than assumed (`scripts/determinism_check.py`: three calls to
`estimate()` on the identical pair in the identical process).

| backend | run 0 | run 1 | run 2 | forward flow bitwise identical? |
|---|---|---|---|---|
| SEA-RAFT | 96.11 % | 96.11 % | 96.11 % | **yes** |
| WAFT | 99.27 % | 99.27 % | 99.27 % | **yes** |
| VideoFlow-MOF | 99.31 % | 99.31 % | 99.31 % | **yes** |
| **FlowIt** | 98.35 % | **91.81 %** | 98.35 % | **no** |

(FB-valid coverage, `MURKYSHARK` frames 6→7.)

FlowIt's forward flow differed by up to **0.858 px** (mean 0.149 px) between
two identical calls, flipping **6.5 % of the FB-validity mask**. It is
intermittent — run 2 reproduced run 0 exactly — and the backward flow was
identical in all three runs, so this looks like a sporadic numerical event
rather than a systematic one. On a clip whose median motion is 1.6 px, a mean
0.149 px perturbation is ~9 % of the motion, arriving from nothing but a
repeat call.

**This corrects an earlier reading.** The first bakeoff showed FlowIt at
71.5 % FB-valid on `MURKYSHARK` 8→9, which looked like a clean "collapses on
textureless murk" story. The second run put that same pair at 99.3 % and
degraded two others instead. The real property is not *where* FlowIt fails
but that **it is not reproducible**, and the near-static murky clip — where
round-trip errors cluster near the β = 0.5 threshold — is where that
irreproducibility becomes visible. For a metric backend this is disqualifying
independently of accuracy: it makes "did the pipeline regress?" unanswerable.

Not investigated further (out of Phase 1A scope): whether the cause is MPS
reduction ordering, the Sinkhorn iterations in the optimal-transport
matching, or allocator state under memory pressure. Worth noting the run that
diverged is the one immediately after a large allocation.

---

## 6. Quantitative comparison

Full per-clip tables: `outputs/flow_comparison/comparison.md`; every number
per pair: `outputs/flow_comparison/<backend>/metrics.json`. Values are means
over the three pairs of each clip. **No weighted score is computed** — these
are different failure modes on five short excerpts, and summing them would
hide exactly the disagreements this phase exists to find. This is a probe,
not a leaderboard: 15 pairs from five clips cannot rank optical-flow methods.

### The headline: the warping residual does not separate the backends

| clip | warp MAE (linear) SEA-RAFT / WAFT / FlowIt / MOF | spread | uncompensated | reduction |
|---|---|---|---|---|
| swimthrough | 0.00894 / 0.00904 / 0.00899 / 0.00899 | 1.1 % | 0.0408 | 4.57 / 4.52 / 4.54 / 4.54× |
| murky_eel | 0.01963 / 0.02005 / 0.01969 / 0.01964 | 2.1 % | 0.0945 | 4.84 / 4.71 / 4.81 / 4.82× |
| murky_shark | 0.00385 / 0.00382 / 0.00392 / 0.00384 | 2.6 % | 0.0049 | 1.28 / 1.27 / 1.27 / 1.27× |
| lights | 0.03116 / 0.03100 / 0.03180 / 0.03127 | 2.5 % | 0.0370 | **1.19 / 1.19 / 1.19 / 1.19×** |
| distance | 0.01525 / 0.01616 / 0.01540 / 0.01488 | 8.0 % | 0.0396 | 2.60 / 2.46 / 2.58 / 2.65× |

Median flow magnitudes agree to within 0.2 px on every clip, so the four are
not disagreeing about bulk motion either. **Motion-compensated warping
residual measures the scene, not the model**: it varies 8× across clips
(0.0038 → 0.0312) and ~2 % across backends. As a Phase 1B regression signal
that is backwards — a temporal-stability number that moves more with which
clip you point it at than with what the pipeline did to the frames needs
per-clip normalisation (report the *reduction ratio*, not the absolute
residual) before it is useful.

### What does separate them

| | SEA-RAFT-M | WAFT-a1 | FlowIt-M | VideoFlow-MOF |
|---|---|---|---|---|
| s / inference (range over clips) | **0.73 – 0.80** | 2.03 – 2.98 | 37.9 – 52.2 | 15.8 – 21.3 |
| peak MPS driver allocation | **2.2 GB** | 2.4 GB | **22.8 GB** | 8.9 GB |
| peak process RSS | 1.38 GB | 1.51 GB | 1.84 GB | 1.56 GB |
| non-finite flow | 0.000 % | 0.000 % | 0.000 % | 0.000 % |
| deterministic | yes | yes | **no** | yes |
| FB valid coverage, worst clip | 96.5 % | **99.2 %** | 91.3 % | **99.2 %** |
| FB round-trip error, median px | 0.029 – 0.174 | 0.043 – 0.117 | 0.120 – 0.389 | 0.044 – 0.238 |
| FB round-trip error, **p95** px | 0.20 – 0.59 | **0.18 – 0.33** | 0.38 – 0.78 | 0.21 – 0.74 |
| \|flow\| max on 1–3 px-median clips | 22.5 – 23.0 px | 4.9 – 16.0 px | 5.0 – 15.0 px | 4.8 – 20.9 px |
| native confidence | log-b | log-b | conf + occ | **none** |

WAFT has the **tightest FB error tail of the four on every clip** and the
best worst-case coverage, in the same memory class as SEA-RAFT, for ~3× the
runtime. SEA-RAFT is the fastest by a wide margin and has the lowest FB
*median* on two clips, but the loosest tail. FlowIt is worst on nearly every
axis here and is the only non-deterministic one.

Runtime caveat, because the first row is easy to misread: MOF's
per-inference cost covers a 5-frame window from which it emits **three
forward and three backward flows**. With a stride-3 sliding window over a
real clip its amortised cost per bidirectional pair is ~4× SEA-RAFT's, not
~24×. This bakeoff deliberately did not amortise it, because taking the
backward flow from the same pass would make the two directions share decoder
state and quietly weaken the independence the FB check depends on. Both
numbers are true; which applies depends on how Phase 1B uses it.

Memory caveat: peak process RSS is misleadingly flat because MPS allocations
do not land in RSS. The driver-allocation row is the one that matters.

### Where the backends disagree with each other

Aggregate agreement is not evidence of agreement — four fields can share a
mean and differ everywhere. `scripts/disagreement.py` measures the endpoint
error *between* backends over pixels both call valid
(`outputs/flow_comparison/disagreement.json`, maps in `_disagreement/`).

| clip | median motion | median cross-backend EPE | as % of motion |
|---|---|---|---|
| murky_eel | 8.2 px | 0.05 – 0.08 px | ~0.8 % |
| swimthrough | 11.5 px | 0.11 – 0.19 px | ~1.4 % |
| distance | 8.2 px | 0.21 – 0.30 px | ~3 % |
| lights | 3.0 px | 0.12 – 0.17 px | ~5 % |
| **murky_shark** | **1.6 px** | **0.23 – 0.42 px** | **~22 %** |

**The backends agree least exactly where they are most self-consistent.** On
`murky_shark` all four report 96–99 % FB-valid while disagreeing with each
other by ~22 % of the motion magnitude. This is the sharpest result in the
session and it is a warning about the metric, not about any backend: FB
coverage measures self-consistency, and on near-textureless water a smooth
field is trivially self-consistent in both directions while still being
wrong. **WAFT's 99.4 % on that clip is therefore not, by itself, evidence
that WAFT is right there.**

Two further observations from the same data:
* WAFT and MOF agree most closely with each other on `murky_shark`
  (0.234 px, the lowest pair). The two highest-coverage models converging is
  weak evidence for correctness — two smooth fields agree for the same reason
  two correct ones do — though it is mildly interesting that a *pairwise*
  model and a *multi-frame* one converge on the clip where temporal context
  should matter most.
* On the textured clips the ordering inverts: WAFT is the mild outlier in the
  tail (`searaft_vs_waft` p99 2.99 px on murky_eel, 3.41 px on distance,
  vs 0.85–1.95 px among the others), and its `|flow|` max on swimthrough is
  38.1 px against 17–26 px for the rest. WAFT is the consensus centre where
  texture is absent and the outlier where it is present.

---

## 7. Qualitative comparison — what the outputs actually show

Contact sheets in `outputs/flow_comparison/_contact_sheets/` put all four
backends' flow, warp, residual and validity mask for one pair on one page.
These observations come from looking at them.

### swim-through (`SWIMTHROUGH.MP4` 199–204, strongest camera motion)

**All four are visually indistinguishable here.** Same smooth global field,
same warp, same residual texture, same coverage (96.8–96.9 %), same warp MAE
to three decimals. Plenty of texture, coherent motion, nothing ambiguous — an
easy case that separates nothing.

Shared failure modes, present in all four:
* a bright **disocclusion band along the leading frame edges**, where content
  entered from outside the previous frame and cannot be warped. The FB mask
  correctly excludes it. At 12 px/frame it is a few percent of the frame; it
  will grow with faster motion, and a temporal metric must either exclude it
  or accept a motion-dependent bias.
* a thin rope/filament crossing the frame is a **bright curve in every
  residual** — no backend tracks sub-pixel-width structures precisely, and
  none flags them.
* elongated bright streaks from suspended particles.

**Direct answer to "does MOF's multi-frame context help the swim-through?":
no, not visibly and not measurably.** The case it should most favour is where
it adds least. Its temporal advantage showed up elsewhere.

### murky / particulate (`MURKYEEL.MP4` 654–659, `MURKYSHARK.MP4` 6–11)

**Moving animals separate plausibly from camera motion in all four.** The eel
is cut out of the background field with a crisp silhouette by every backend —
the most encouraging result of the session, since a temporal metric that
could not tell a swimming animal from a camera pan would be useless on dive
footage.

**But they disagree on what to do with it.** On the same pair:
* **SEA-RAFT** marks the whole eel *body* invalid — a large solid blob.
* **FlowIt** and **MOF** mark only a thin outline along its edge (MOF adds a
  small patch at the head).

The eel is a smooth, low-texture, elongated moving object — a textbook
aperture problem, where flow *along* the body is genuinely unrecoverable.
SEA-RAFT's conservatism is the safer behaviour for a metric; the others'
keeps more of the animal in the measured region. A Phase 1B design choice,
not a quality ranking.

**`MURKYSHARK` is where the backends diverge most** — near-static
(0.03 px/frame) over almost textureless murk, the hardest low-visibility case
in the set and the one that most resembles what a temporal metric will be
asked to judge.

* **WAFT and MOF are the most stable** (99.4 %, 99.2 %), with the smoothest
  fields.
* **SEA-RAFT sits at 96.5 %**, and its invalid pixels are *localised and
  interpretable* — the moving dark shape in the bottom-right, plus scattered
  single-pixel specks.
* **FlowIt is not reproducible here** (§5).

Those SEA-RAFT specks explain a number in the table: it reports flow maxima
of 22–26 px on clips whose median is 1–3 px, where the others cap at 5–17 px.
**They are individual suspended particles**, tracked as fast-moving objects
rather than smoothed into the background — and then rejected by its own FB
mask. The others suppress them at the flow stage instead. Both are
defensible; SEA-RAFT's is more transparent, because the particle motion is
visible and flagged rather than silently averaged away.

**Read all of the above against §6's disagreement result**: on this clip warp
residual is useless as a discriminator (all four within 2 %, and the
uncompensated residual is only 1.27× the warped one), FB coverage is 96–99 %
for everyone, *and the four fields differ from each other by ~22 % of the
motion*. This clip should be treated as a stability control, not an accuracy
test.

### artificial lights (`LIGHTNIGHTDIVE.MP4` 89–94)

**The most important finding of the session, and it is not about the
backends.** Warping reduces the residual 4.6–4.8× on `murky_eel` and
`swimthrough` but only **1.19×** here — identically for all four.

The residual image shows why: the dive light is **camera-mounted**. The lit
patch of sand travels *with* the camera, so a scene point's radiance changes
between frames. That is photometric, not geometric. Flow tracks the sand
texture correctly, the FB mask marks the hotspot **valid**, and the
illumination change lands whole in the residual — the bright blob around the
beam is nearly as strong after warping as before.

The consequence for Phase 1B: **a plain motion-compensated warping residual
would score artificial-light footage as temporally unstable no matter how
good the flow or the restoration is.** No choice of backend fixes this. It
needs an illumination-invariant photometric term, a per-frame gain/bias fit,
or an explicit exclusion — a metric-design decision, not a tuning knob.

Secondary observations:
* **Bright localised lights are not themselves a correspondence problem.** No
  backend produced spurious motion at the hotspot; the beam is attached to
  the camera, so it is stationary in image space and the flow there is smooth
  and plausible. The problem is entirely photometric.
* **The featureless lit sand plain is.** FlowIt shows a large invalid band
  across it (96.2 % vs 98.1–99.2 %), and all four show scattered invalid
  specks in the dark upper region where the only signal is particulate
  glinting in the beam.
* Particles lit by the beam are the brightest structured residual after the
  hotspot — marine snow near a light source is locally high-contrast, which
  makes it *more* attractive to a matcher, not less.

### distance (`DISTANCESHOT.MP4` 264–269)

The richest scene: a diver with a rising bubble column, a second diver in the
background, near-foreground coral, distant reef wall. **This is the clip that
most clearly distinguishes the four, and it is where WAFT's high coverage
turns out to have a cost.**

* **Parallax is resolved plausibly by all four.** Near-field coral and the
  diver's fins carry visibly different displacement from the distant wall,
  with sensible boundaries. Encouraging for Week 3/6, where depth-dependent
  correction needs exactly this.
* **Bubbles are the largest structured residual**, surviving as a bright
  vertical streak in every warped residual. Bubbles are non-rigid, appear and
  disappear, are semi-transparent and rise fast — there is no correct
  correspondence to find.
* **SEA-RAFT, FlowIt and MOF all render the bubble column as visibly distinct
  motion in the flow field. WAFT does not** — its field is a clean gradient
  through the plume, with no bubble structure at all.
* **Only MOF flags them.** Its FB mask has distinct invalid blobs over the
  column (96.7 % vs 97.8–98.0 %). The bubbles are inconsistent *over time*,
  which a 5-frame model can see and a frame-pair model structurally cannot.
  For a temporal metric, wanting bubbles excluded is a feature.
* **WAFT is simultaneously the smoothest, the highest-coverage, and the worst
  on warp residual here** (0.01616 vs MOF's 0.01488 — an 8 % gap, the largest
  backend spread anywhere in the study). Those three facts are the same fact:
  it neither tracks the independently-moving structures nor flags them, so
  they land in the residual unwarned.
* **SEA-RAFT's uncertainty head is genuinely informative**: it lights up on
  the bubble column, the near-foreground coral edge (large-parallax
  disocclusion) and the frame borders, and stays dark over the diver's body.
  Not comparable to other backends' native maps, but as a standalone signal
  it agrees with where the geometry is actually hard.
* **Distant low-detail water is not a failure region for anyone.** The far
  reef wall — low contrast, low detail — produced smooth, plausible, fully
  valid flow in all four. Failures cluster at occlusion boundaries, non-rigid
  objects and *textureless* regions, not at *distant* ones. **Distance is not
  the risk factor; absence of texture is.**

### What WAFT's coverage advantage actually is

Putting §6 and the `distance` sheet together: WAFT's best-in-class FB
coverage and tightest error tail come substantially from producing a
**smoother, more strongly regularised field** — one that does not attempt the
correspondences that are genuinely ambiguous. It is the consensus centre
where texture is absent and the outlier where texture is present; it is the
only backend that does not represent the bubble plume; and it has the worst
warp residual on the clip with the most independent motion.

That is not a criticism — for a temporal-stability metric, a stable
camera-motion field with ambiguity handled by explicit exclusion may be
exactly what is wanted. But it means **WAFT's 99.4 % on textureless murk
should not be read as "more accurate there"**, and the depth-foundation-trunk
hypothesis that motivated testing it is not confirmed by this evidence.
Separating "smoother" from "righter" needs ground truth this test set does
not have.

### GoPro / fisheye frame edges

No systematic edge-specific breakdown was observed in any backend. What is
present at the edges is ordinary and shared: the disocclusion band on the
leading edges under camera motion, and the FB mask's deliberate rejection of
pixels whose round-trip leaves the frame. Every flow field stays smooth into
the corners; none showed the radial artefacts a wide fisheye can provoke. The
excerpts here are 3–12 px/frame, and this should not be extrapolated to a
violent surge sequence, which the test set does not currently contain.

---

## 8. Repository changes

### Created — permanent
* `uw/flow.py` — the abstraction, the coordinate convention, the
  model-independent flow maths. No backend, no default, no torch.
* `tests/test_flow.py` — 26 analytic tests of the conventions.

### Created — exploratory, disposable
* `experiments/week2a_flow/README.md` — environments, provenance, reproduction.
* `experiments/week2a_flow/FINDINGS.md` — this document.
* `experiments/week2a_flow/common.py` — excerpt loading, the temporary
  linear→sRGB model-input view, visualisation, quantitative diagnostics.
* `experiments/week2a_flow/backends/{searaft,waft,flowit,videoflow}_backend.py`
  — one wrapper each, every one documenting its own checkpoint,
  preprocessing and deviations in its module docstring.
* `experiments/week2a_flow/scripts/` — `survey_motion.py` (excerpt
  selection), `synthetic_check.py` (known-motion correctness),
  `determinism_check.py` (reproducibility), `run_bakeoff.py`,
  `contact_sheets.py`, `aggregate.py`, `disagreement.py`.
* `experiments/week2a_flow/excerpts.json` — the experiment definition
  (clips + frame ranges + how they were chosen). Committed deliberately: it
  is metadata, not footage.

### Modified
* `.gitignore` — added `outputs/`, `experiments/week2a_flow/.venv-*/`,
  `vendor/`, `checkpoints/`.
* `LOG.md` — this session's entry.

### Not modified
`CLAUDE.md`, `PLAN.md`, `pyproject.toml`, and every Week 1 module
(`uw/metrics.py`, `uw/cli.py`, `uw/io.py`, `uw/types.py`, `uw/baselines.py`,
`uw/colorspace.py`) are byte-identical to before this session. No footage was
touched, staged or committed. No depth/restoration/temporal scaffolding was
added, no model registry, no plugin system.

### Isolated environments (gitignored, recreatable — see README)
* `.venv-flow` — Python 3.13.5, torch 2.13.0 (MPS); SEA-RAFT, WAFT, FlowIt.
* `.venv-videoflow` — Python 3.13.5, torch 2.13.0, **timm 0.4.12**; MOF only.
* `vendor/` — four cloned repos, unedited.
* `checkpoints/` — **405 MB kept** (FlowIt-M 345 MB, `MOF_sintel.pth` 52 MB,
  WAFT `tar-c-t.pth` 245 MB, plus DAv2-Small 95 MB inside `vendor/WAFT/`),
  trimmed from ~6.9 GB as downloaded. FlowIt S/L/XL and VideoFlow's seven
  unused BOF/things/kitti checkpoints were deleted; the FlowIt wrapper raises
  a `FileNotFoundError` naming the re-download path if another size is asked
  for. FlowIt XL (1.8 GB) does not fit this machine's working set, and larger
  FlowIt variants would not have helped anyway — its memory is set by the
  global cost volume, which scales with pixel count, not parameters.

### Generated diagnostics — `outputs/flow_comparison/` (gitignored)
```
<backend>/environment.json          full provenance for that backend
<backend>/synthetic_check.json      known-motion test report
<backend>/determinism_check.json    3-repeat reproducibility report
<backend>/metrics.json              every number, per clip and pair
<backend>/<clip>/pair_<t>_<t1>/
    frame_t.png  frame_t1.png
    flow_forward.png  flow_backward.png     (shared magnitude scale)
    flow_forward.npy  flow_backward.npy     (raw float32, (u,v), eval grid)
    warped_t1_to_t.png
    residual_warped.png  residual_uncompensated.png
    fb_valid_mask.png  fb_error.png
    native_confidence_forward.png           (SEA-RAFT, WAFT, FlowIt)
    native_occlusion_forward.png            (FlowIt)
    meta.json                               per-pair metadata + diagnostics
_contact_sheets/<clip>__pair_<t>_<t1>.png   all four backends, one page
_disagreement/<clip>__pair_<t>_<t1>.png     max pairwise disagreement map
comparison.md   disagreement.json
```
120 raw `.npy` flow fields are on disk, so Phase 1B can prototype metric
variants without paying for inference again. Every writer refuses to clobber
an existing file without `--overwrite`.

---

## 9. Open questions for Phase 1B

1. **Does the temporal metric need an illumination-invariant photometric
   term?** The `lights` result says a plain MC-Warp residual measures
   camera-mounted-light illumination change more than temporal instability.
   Candidates: a per-frame gain/bias fit before differencing, a gradient- or
   census-domain residual, or normalised cross-correlation over local
   windows. **Highest-value open question, and independent of which backend
   wins.**
2. **Should the reported quantity be the reduction ratio rather than the
   absolute residual?** Warp residual varies 8× across clips and ~2 % across
   backends. A score that moves more with which clip you point it at than
   with what the pipeline did is not yet a regression signal. PLAN.md now
   specifies `MC-Warp@1/4/8`; the normalisation question applies to all three
   lags.
3. **How should validity be decided?** SEA-RAFT excludes whole moving
   animals; the others keep their interiors. Excluding more is safer and
   measures less. PLAN.md's rule — never let a method score well by masking
   difficult regions, and always report coverage with the score — makes this
   a first-class decision rather than an implementation detail.
4. **Can "smoother" be separated from "righter" without ground truth?** §6
   and §7 show the backends disagreeing by ~22 % of the motion on the murky
   clip while all reporting 96–99 % validity, and WAFT achieving the highest
   coverage partly by not representing difficult motion at all. Chart or
   controlled footage with known motion, or a synthetic degradation of a
   clean clip, may be the only way to settle it.
5. **Should bubbles and particulate be excluded explicitly?** MOF flags the
   bubble column; the pairwise models do not, and WAFT does not even
   represent it. If bubbles need excluding, is MOF's implicit flagging worth
   its runtime, or is an explicit detector (high-frequency, high-magnitude,
   low-FB-consistency) cheaper and more controllable?
6. **Is 960×540 the right operating resolution for the metric?** Chosen here
   so four backends could be compared fairly on this hardware. Whether a
   temporal metric on 4K footage should run at 960×540 or higher is untested
   — and FlowIt cannot answer it at all on a 24 GB machine. **DPFlow was
   deliberately not integrated in Phase 1A**: it is built for adaptive/
   high-resolution generalisation, which answers this question, and this
   question is not yet live. It also lives inside the `ptlflow` model-zoo
   framework, a heavier integration than the repo link suggests. Revisit only
   if Phase 1B decides the metric must run above 960×540.
7. **Does the near-static murky case need a different check entirely?** On
   `MURKYSHARK` neither the residual nor the FB mask discriminates, yet it is
   exactly the footage where restoration flicker is most visible. A metric
   validated only on textured, moving clips may be blind on the clips that
   matter most.
8. **How stable is any of this over 30 seconds rather than 3 frames?** The
   Week 8 gate is "no visible pumping on a 30-second swim-through". Nothing
   here tested drift, accumulation or long-range consistency. At measured
   rates a 30 s clip (~900 bidirectional pairs) costs ~23 min for SEA-RAFT,
   ~65 min for WAFT, ~95 min for MOF amortised, ~21 h for FlowIt. **This is
   probably the single most informative next experiment.**
9. **Does the FB threshold need revisiting for underwater footage?**
   α = 0.01, β = 0.5 are Sintel-era constants, held fixed here so the
   comparison stayed fair. Whether β = 0.5 px is the right floor for
   1–3 px/frame murky footage is untested, and it is the knob that most
   changes what "valid" means — FlowIt's irreproducibility became visible
   precisely because that clip's round-trip errors cluster near it.
10. **Is FlowIt's nondeterminism reproducible on other hardware?** Observed
    only on MPS, in one wrapper, on one clip family. If it is an MPS artefact
    rather than an algorithmic one, the conclusion changes.

---

## 10. What was deliberately NOT done

Per the Phase 1A brief:
* **No backend selected.** The evidence is here; the choice is not made.
* Nothing wired into `uw/metrics.py`; `temporal_stability` is untouched and
  still the Week 1 placeholder.
* MC-Warp not implemented as a metric.
* No project-wide default flow backend.
* No temporal correction or smoothing.
* No Week 3 work, no depth/restoration scaffolding, no model registry, no
  plugin system.
* DPFlow not integrated (see open question 6).

The author's own reading, recorded as opinion rather than as a decision, is
in `LOG.md`'s "next hypothesis" for this session.

---

# ADDENDUM — MC-Warp lag study (@1 / @4 / @8)

Added after the main bakeoff, because §1–10 measured only lag 1 while
PLAN.md specifies `MC-Warp@1/4/8`. A ranking built on one third of the metric
has no automatic authority over the other two thirds — at 3–12 px/frame,
lag 8 means 25–100 px displacements, a materially different regime.

Script: `scripts/run_lag_study.py`; tables:
`scripts/aggregate_lags.py`; results under `outputs/flow_lag_study/`.

## A1. Method

Deliberately parallel to the main bakeoff so the numbers are comparable: same
clips, same 960×540 grid, same linear-light downscale, same temporary sRGB
model-input view, same FB thresholds, residuals again on linear light. 41
frames decoded per clip; three anchors at local indices 16/18/20 so that even
at lag 8 a multi-frame backend's `[t−2k, t−k, t, t+k, t+2k]` window fits
without clamping. Anchors are identical across lags and backends — only the
lag varies. Every value is two real inferences.

The comparable quantity across lags is **not** the absolute residual (which
grows with lag for trivial reasons) but the **reduction ratio** against the
uncompensated residual at the same lag: how much of the frame-to-frame change
the flow actually explains. Coverage is reported beside every value, per
PLAN.md.

## A2. Coverage decays sharply with lag — and that is a metric-design problem

| backend | cov @1 | cov @4 | cov @8 | @1→@8 loss |
|---|---|---|---|---|
| WAFT | 97.6 % | 92.9 % | **86.3 %** | **11.3 pts** |
| FlowIt | 96.9 % | 91.6 % | 83.8 % | 13.1 pts |
| SEA-RAFT | 97.0 % | 90.8 % | 83.4 % | 13.7 pts |
| VideoFlow-MOF | 96.9 % | 85.6 % | 79.6 % | 17.3 pts |

At @8 the metric measures roughly four-fifths of the frame, and *which*
four-fifths depends on the backend's occlusion handling. Two consequences
for Phase 1B:

* **MC-Warp@8 is unreadable without its coverage number.** Comparing two
  pipeline versions at @8 is only valid if their coverage is comparable too.
* **Backends' @4/@8 values are not measured on the same pixels**, so their
  MC-Warp numbers are not directly comparable to each other at all — see A5.

## A3. The lags are not redundant — different clips need different ones

Residual reduction ratio, SEA-RAFT:

| clip | @1 | @4 | @8 |
|---|---|---|---|
| swimthrough | 4.39× | 5.37× | 5.67× |
| murky_eel | 4.52× | 5.11× | 4.98× |
| **murky_shark** | **1.37×** | 2.33× | **2.43×** |
| **lights** | **1.14×** | 1.07× | **1.02×** |
| distance | 2.66× | 3.74× | 3.79× |

`murky_shark` is near-static, so at @1 there is too little motion for warping
to help at all (1.37×); by @8 the camera has moved enough for flow to earn
its keep (2.43×). The reverse holds on `lights` — see A4. A single-lag metric
would be blind on one or the other.

## A4. The `lights` failure gets monotonically worse with lag — for every backend

| lag | reduction on `lights` (SEA-RAFT / WAFT / MOF) |
|---|---|
| @1 | 1.14× / 1.14× / 1.14× |
| @4 | 1.07× / 1.06× / 1.06× |
| @8 | **1.02× / 1.02× / 1.02×** |

**At @8, flow explains ~2 % of the frame-to-frame change on the
artificial-light clip.** The further the camera travels, the more completely
the camera-mounted light's illumination change dominates the geometric
change. This is the §7 finding, now quantified across lag and shown to be
backend-independent to three significant figures. **MC-Warp@8 on `lights`
would measure the dive light, not the pipeline.** No backend choice affects
this; an illumination-invariant photometric term is required.

## A5. VideoFlow-MOF cannot serve a multi-lag metric

MOFNet emits flow only between *consecutive* frames of its window, so a
lag-k pair must be served by a stride-k subsampled window — off the
adjacent-frame distribution its checkpoint was trained on. The cost is
specific and severe:

| `murky_shark` | @1 | @4 | @8 |
|---|---|---|---|
| SEA-RAFT | 96.3 % | 90.9 % | 89.7 % |
| WAFT | 96.1 % | 97.8 % | 96.8 % |
| FlowIt | 98.2 % | 91.9 % | 87.7 % |
| **MOF** | **95.1 %** | **63.1 %** | **63.0 %** |

A ~36-point collapse, from joint-best at @1 to worst-by-27-points at @4. On
textured clips (`swimthrough`, `murky_eel`) MOF tracks SEA-RAFT closely at
all three lags, and on `lights` it holds 93–97 %, so the failure is
**off-distribution stride × low texture**, not long lag alone. Visual
confirmation: at `murky_shark` @8 MOF's warped frame is visibly *skewed*,
with a slanted black edge — its flow carries a large spurious global
component.

Note the trap this sets. MOF has the **highest** reduction ratio on
`murky_shark` @8 (2.88× vs SEA-RAFT's 2.43×) — achieved by discarding 37 % of
the frame and explaining the easy remainder well. Read without its coverage,
that number would rank MOF best on the clip where it is worst. It is the
cleanest live example of why PLAN.md forbids scoring well by masking.

## A6. SEA-RAFT vs WAFT, judged on identical pixels

Every per-backend number in this study is computed on that backend's *own*
validity mask, which makes cross-backend residuals incomparable whenever the
masks differ. WAFT masks less than SEA-RAFT everywhere (15/15 clip-lag cells
tie-or-better on coverage), so its lower reduction ratio might have been an
artefact of *including* harder pixels — or SEA-RAFT's higher one an artefact
of *excluding* them. The scepticism applied to MOF in A5 has to apply here
too, including to the preferred backend.

`scripts/common_mask_compare.py` intersects the two masks and scores both on
the common set. Anything that survives is a correspondence-quality
difference; anything that vanishes was masking policy.

**Result: SEA-RAFT 7 cells, WAFT 1, 7 ties (<0.5 %).** SEA-RAFT is
equal-or-better in 14 of 15. Most margins are under 3 % — practical ties —
with one real gap:

| cell | SEA-RAFT | WAFT | gap |
|---|---|---|---|
| swimthrough @8 (~100 px displacement) | **5.615×** | 5.043× | **11 %** |
| murky_shark @8 (WAFT's only win) | 2.930× | 2.955× | <1 % |

So SEA-RAFT's advantage is real and survives the fair test, and it is
largest in the large-displacement regime. WAFT's advantage — best coverage,
tightest FB error tail, best coverage retention — is about **how much frame
you get to measure**, not how good the correspondence is.

## A7. Two readings corrected during this addendum

Recorded because both were stated before being checked, and the checks
changed them:

1. **"WAFT doesn't detect independent motion."** Overstated. At
   `murky_shark` @8 WAFT smooths straight through the dark shark and reports
   96.8 % valid where SEA-RAFT cuts out the bottom third — but at
   `distance` @8 WAFT detects and flags the moving diver exactly like the
   others. The failure is specific to **low-contrast** independent motion,
   which matters here only because dark animals in murky water are a core
   test-set category, not because it is a general property.
2. **"WAFT silently includes regions where its own flow failed."** Not
   supported. In the disputed 7.16 % band, WAFT's own warp residual is
   *lower* than SEA-RAFT's (0.00794 vs 0.00866). The region is simply harder
   for everyone (1.4–1.6× each backend's own baseline) and the two make
   different decisions about counting it. What is solid: they disagree by
   2.71 px there against 0.85 px frame-wide, so at least one is substantially
   wrong and this test set cannot say which.

Both errors were the same mistake — inferring a mechanism from a
visualisation before quantifying it. The A6 common-mask test was written in
response, and is the check that should gate any future backend comparison.

## A8. FlowIt across lag — no large-displacement advantage

FlowIt was carried into the lag study for one reason: its **global**
optimal-transport matching might plausibly beat local cost-volume methods at
@8's 70–100 px displacements. That was the last live argument for a backend
already disqualified on reproducibility (§5).

It does not hold. Reduction ratio at @8:

| clip | SEA-RAFT | FlowIt | MOF | WAFT |
|---|---|---|---|---|
| swimthrough (~100 px) | **5.67×** | 5.56× | 5.65× | 5.19× |
| murky_eel (~75 px) | 4.98× | 4.98× | **5.05×** | 4.92× |
| distance (~70 px) | 3.79× | 3.86× | **4.03×** | 3.83× |

FlowIt lands mid-pack at every lag on every clip, never leading, at
**39.7 s/inference** (≈50× SEA-RAFT) and 22.8 GB peak MPS allocation. Its
coverage decay (13.1 pts @1→@8) is likewise unremarkable.

So the architectural property that might have justified its cost does not
materialise on this footage. FlowIt is dropped on reproducibility, and the
lag study removes the one remaining reason to revisit that decision.

Its `murky_shark` @1 coverage in this run (98.2 / 96.9 / 99.5 % across the
three anchors) is also a third independent sighting of the pair-level
irreproducibility from §5 — the first bakeoff run put one of those pairs at
71.5 %.

## A9. Revised standing after the lag study

```text
canonical        SEA-RAFT-M
optional check   WAFT-a1
research shelf   VideoFlow-MOF   (@1 only)
dropped          FlowIt-M        (not reproducible; no large-motion win)
```

Recorded in PLAN.md under *Phase 2A — result*. Still a recommendation, not a
selection: the choice is the reader's.

The lag study did not change the backend ranking. It changed the
**metric** requirements — illumination invariance (A4), coverage gating
(A2), per-lag normalisation (A3) — which is consistent with the central
finding that the backend was never the constraint.
