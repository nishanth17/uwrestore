# R2-S1 — determinism, runtime and memory for the Round-2 challengers

**Stage:** S1 of the Round-2 mini-bakeoff (§15). **Everything here is PRE-C2.**

S1 asks one question and only one: run the model twice on byte-identical input
under identical conditions, and does it give back the same numbers? It is a
property of the instrument, not of the prediction. A bitwise-deterministic model
can be bitwise-deterministically wrong, and nothing in this file is evidence that
any arm's geometry is right. What S1 buys is the right to read a downstream
difference — an S2 residual, an S3 dimension, an S4 perturbation response, an S5
frame-to-frame step — as caused by the thing that was changed rather than by the
model rolling dice.

The protocol is the frozen Round-1 one, unchanged, so the Round-2 numbers sit in
the same units as `results/S1_DETERMINISM.md`: the same four frames, three
within-process repeats plus an independent fresh process, and the comparison made
on `canonical_range` where the model emits one and on the NATIVE field otherwise —
so the floor is expressed in the units the S2 alignment policy will actually work
in, not in a converted quantity that could hide or manufacture jitter.

The four frames are `wreck_07/f000105` (high texture, favourable geometry support),
`wreck_05/f000109` (low texture, weak support), `cenote_01/f000193` (widest near/far
span) and `wreck_01/f001845` (low-texture near-planar **portrait** — the orientation
trap). §15 does not ask for the 288-frame set here and it would not answer this
question any better.

## 1. Result

| arm | config | bitwise | p99 rel floor | median s | min–max s | load s | peak RSS GB | peak MPS GB |
|-----|--------|---------|---------------|----------|-----------|--------|-------------|-------------|
| `moge3_vitl` | Step 0 (`refine_steps = 0`) | **YES** | 0.0e+00 | 4.10 | 4.05–4.86 | 9.1 | 3.06 | 3.07 |
| `mda_mog_sky_l2` | official mono path, 512 long edge | **YES** | 0.0e+00 | 2.82 | 1.80–3.30 | 14.6 | 10.35 | 6.20 |
| `pxdepth` | official released ckpt, `use_fp32=True`, **CPU** | **YES** | 0.0e+00 | 16.45 | 15.40–17.09 | 3.9 | 5.69 | n/a |

All three runnable Round-2 challengers are **bitwise reproducible, within process
and across processes** — the two MPS arms in float32, `pxdepth` on CPU. Identical
valid masks, identical fields, byte for byte, on all four frames including the
portrait one. Measured noise floor exactly zero, matching all seven Round-1 arms.

Per frame, every arm, within-process and across-process: `p99_rel = 0.000e+00`,
`bitwise_identical = True`, `valid_mask_identical = True`. The compared sample
counts differ between the arms because they predict on different grids, and that
is worth recording rather than averaging away:

| arm | grid | n compared | coverage on the four frames |
|-----|------|-----------|------------------------------|
| `moge3_vitl` | source grid 1280×720 | 921 600 max | 0.913 / 0.767 / 1.000 / 1.000 |
| `mda_mog_sky_l2` | native patch-aligned 504×280 (long edge 512, patch 14) | 141 120 | 1.000 on all four |
| `pxdepth` | native network grid 1176×672 | 790 272 | 0.905 / 0.833 / 1.000 / 1.000 |

MoGe-3's mask is its own; it declines 8.7 % of `wreck_07` and 23.3 % of `wreck_05`,
and the mask is identical across repeats, so the declining is deterministic too.
MDA returns full coverage on its own smaller grid — its 1.0 is a statement about
its mask, not about its resolution, and §17 already records the resolution cost
separately.

For MDA the §12 mixture record — component depths, mixture probabilities, chosen
component, entropy, top-1-minus-top-2 margin — is reproduced bitwise along with the
depth. So the multi-hypothesis quantities are repeatable. Per §12 that is all this
says: they are **not** called calibrated confidence here, and §26 answers separately
(and negatively) whether they track actual disagreement.

## 2. What the zero floor licenses, and what it does not

**It licenses** reading any nonzero Round-2 downstream difference as attributable
to the thing that changed. There is no stochastic floor to subtract and no
`>= floor` filter is needed anywhere in R2-S2…S6. In particular the §18
thin-structure separations, which are small numbers on small regions, are not
run-to-run noise.

**It does not license** treating a small difference as important. The three floors
that sit above this one are unchanged from Round 1 and still bind: the 8-bit PNG
quantisation floor every S4 perturbation passes through; the Week-3 reference's own
uncertainty, which is large on exactly the low-texture clips (whole-pipeline reruns
moved `wreck_05` by 2.1–6.5 % median while `wreck_07` moved 0.01 %); and the Week-3
stage-7 restoration sensitivity budget (31 % at 1 m, 12 % at 3 m, 8.5 % at 8 m).
The reference floor is the binding one, and pre-C2 it is a *provisional* floor
around a *provisional* hypothesis.

## 3. Why it came out zero

Same reason as Round 1, verified per arm rather than assumed. Both models run under
`eval()` with no grad, no sampling, no dropout, no stochastic augmentation. Autocast
is off — MPS supports only bf16/fp16 autocast, so float32 is what actually executes.
Neither arm's official path introduces a stochastic element: MoGe-3 Step 0 is a
single deterministic forward with the refiner absent, and MDA's mixture head is an
argmax over deterministic component predictions, not a sample from them.

This is also the reason the one challenger where stochasticity was *expected* —
PointDiT, a generative point-map model whose primary configuration is single-step
all-zero initialisation — is the one that could not be tested. See §5.

## 4. Runtime and memory

Round-2 medians alongside the Round-1 field, all on the same machine (Apple M4,
10 cores, 24 GB unified, MPS float32, torch 2.14.0), one model per process:

| arm | median s/frame | peak RSS GB |
|-----|----------------|-------------|
| `dav2_small` | 0.19 | 0.77 |
| `da3mono_large` | 0.29 | 2.89 |
| `mapanything_n1` | 1.10 | 9.59 |
| `wat3r_n1` | 1.14 | 9.18 |
| `foundationgeo_11` | 1.45 | 2.71 |
| `moge2_vitl` | 2.09 | 2.80 |
| `metricanything_pointmap` | 2.12 | 2.80 |
| **`mda_mog_sky_l2`** | **2.82** | **10.35** |
| **`moge3_vitl` (Step 0)** | **4.10** | **3.06** |

Two things follow.

**MoGe-3 Step 0 is the slowest arm in the bakeoff — 2.0× MoGe-2 and 14× DA v2 — for
a model that is doing strictly less work than its own released configuration.**
Step 3 would add to this, not subtract from it. Whatever Step 0 → Step 3 turns out
to be worth on a CUDA machine, it is not free, and §7's instruction to preserve the
trade-off rather than pick a mode early is the right posture: the Step-0 runtime is
already the ceiling of this field.

**MDA has the largest memory footprint of any arm ever run here** — 10.35 GB peak
RSS, above both ViT-G-class multi-view architectures — while predicting on the
*smallest* grid (504×280, 6.5× fewer samples than the source grid). That is the
mixture head: four component depth fields plus probabilities carried through the
decoder. On a 24 GB machine it confirms the standing one-model-per-process rule
with no margin to spare.

The two Round-2 arms together cost 6.92 s/frame, so one 288-frame pass for both is
about 33 minutes of pure inference. S3 at full scale was affordable, which is why
§17 was run at full scale rather than subsampled.

The S1 medians supersede the S0 probe timings (MoGe-3 2.25–3.50 s, MDA 1.48–2.29 s):
S0 timed its own probe images, S1 times the frozen frames, and the frozen frames are
what every later stage runs on.

## 5. Arms that never reached S1

Recorded rather than omitted. None of these is a failure of the model; each is a
statement about this machine or this release, and each carries what would be needed
to resume.

**`pointdit_l512` — `pending_checkpoint`, and this is the one that matters for S1.**
§15 requires the single-step all-zero-initialisation path to be tested *directly*
for determinism, because a diffusion-family model is the one challenger where
stochastic initialisation is the expected failure mode and where a nonzero floor
would have been a genuine finding rather than a formality. That test is **blocked,
not passed and not skipped.** The released checkpoint ships without the DINOv3 image
encoder (`README:59-62`: "The DINOv3 weights are gated and cannot be redistributed,
so they are not part of the released checkpoints"), while `model.py:270` requires
`feature_embedding_type='dinov3_vitb16'`. Obtaining the encoder requires
authenticating to a gated repository, which the execution policy forbids.

**`hyden_mogev2_metric` — `pending_checkpoint`.** `facebook/hyden-mogev2-metric-point`
is a gated repository returning `GatedRepoError 401`; access needs a manually
approved request plus an authenticated token. Stopped at the S0 gate.

**`surge_large` — `pending_cuda`.** Not a checkpoint problem: SurGe's Neighborhood
Attention has no backend that both runs on this machine and is numerically the
released one. NATTEN 0.21.6 refuses MPS outright, and refuses compiled flex on two
independent gates (CUDA compute capability ≥ 7.0, and FP16/BF16 only). The one
NATTEN-sanctioned path here, uncompiled CPU flex, was measured at a ~138 GB memory
footprint and killed by the OS at 931 s on a 24 GB machine. Three shortcuts were
available and all three were declined as reference-implementation violations:
lowering the input below the frozen 1280 long side, enabling unverified compiled
flex at half precision, and porting the CUDA FNA kernels. Resuming needs one CUDA
GPU with compute capability ≥ 7.0.

**`moge3_vitl` Step 3 — `pending_cuda`.** `moge/model/modules/sparse_unet.py:14`
requires `flex_gemm.ops.NeighborCache`; FlexGEMM is Triton-powered and Triton has no
macOS distribution. Step 0 is measured above; the Step 0 → Step 3 comparison §7 asks
for cannot be completed on this machine.

**`pxdepth` — run, and it is in the table above.** It was queued behind its own
288-frame S3 inference rather than run concurrently, which would have corrupted both
runtime measurements; it has since been measured on the same four-frame subset and
is **bitwise reproducible on CPU**, floor `0.0e+00`, within and across processes,
with identical valid masks. Its median here is **16.45 s/frame** against the
22.25–23.68 s/frame recorded in S3 — the S3 figure is the honest one for that stage
because it was measured under that stage's own load, and the gap is machine
contention, not a model difference. Either way it is the slowest arm in the study by
an order of magnitude, and it is the only arm with **no MPS path at all**.

## 6. Pre-C2 reading

Three of six Round-2 challengers reached S1, and all three are perfectly
deterministic. That is a clean instrument but a thin field, and the thinness is not a
property of the models: two are gated checkpoints and two are CUDA-only operators
(counting MoGe-3's Step 3 refiner, which is the fourth blocked item). §19's
reduction and §26's per-challenger accounting must report those as *untested*, never
as eliminated — an arm that never ran has produced no evidence for or against
itself, and the pre-C2 conclusion Round 1 reached is unchanged by silence.

## Artifacts

- `outputs/r2_s1/moge3_vitl.json`, `outputs/r2_s1/mda_mog_sky_l2.json`,
  `outputs/r2_s1/pxdepth.json` — raw records.
- `R2_S1_results.json` — this stage's persisted summary, including the pending arms
  and the Round-1 incumbent runtime/memory table reproduced for comparison
  (§13 forbids rerunning the incumbents; determinism is a property of model and
  device, and the Part A/B/D corrections touched only post-inference semantics and
  grid mapping, so the Round-1 floors stand unchanged).

## Reproduce

```
experiments/week4_mono/round2/.venv-moge3/bin/python -u \
  -m experiments.week4_mono.round1.scripts.s1_determinism \
  --model moge3_vitl --device mps --repeats 3 --overwrite \
  --out-dir experiments/week4_mono/round2/outputs/r2_s1

experiments/week4_mono/round2/.venv-mda_mog_sky_l2/bin/python -u \
  -m experiments.week4_mono.round1.scripts.s1_determinism \
  --model mda_mog_sky_l2 --device mps --repeats 3 --overwrite \
  --out-dir experiments/week4_mono/round2/outputs/r2_s1

PYTHONPATH=$PWD experiments/week4_mono/round2/.venv-pxdepth/bin/python -u \
  -m experiments.week4_mono.round1.scripts.s1_determinism \
  --model pxdepth --device cpu --repeats 3 --overwrite \
  --out-dir experiments/week4_mono/round2/outputs/r2_s1
```

Note: the MDA venv's entry point runs with its working directory inside
`round2/vendor/MDA`, so a relative `--out-dir` resolves against that directory. The
run above wrote there and the file was moved to `outputs/r2_s1/`; pass an absolute
`--out-dir` to avoid it.
