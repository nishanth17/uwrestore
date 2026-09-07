# R2-S0 — native semantics, strict N=1, and runtime disposition

**Stage:** Round-2 S0 gate, six frozen challengers. **Pre-C2 throughout.** Nothing
here is a quality result; S0 decides only whether a model's representation is
understood well enough that it may be scored at all.

Machine-readable record: `R2_S0_results.json`. Per-model probe records:
`round2/s0_agent/<model>/s0_smoke.json` and `outputs/s0/<model>.json`.

## The gate

Task §14: *"No model enters S3 while its representation semantics remain
unresolved. Do NOT repeat the Round-1 DA3 mistake of deciding z-depth-vs-range
by residual. Semantic source/code evidence wins."*

Every semantic claim below is sourced to a line of the released implementation,
not to a residual and not to a paper's prose. Where the released code and the
residual test disagree, the code wins and the disagreement is recorded.

## Disposition

| # | model | status | why |
|---|---|---|---|
| R2-1 | `moge3_vitl` | **ready** (Step 0) | Step 3 refiner is `pending_cuda` |
| R2-2 | `hyden_mogev2_metric` | **pending_checkpoint** | gated repo, HTTP 401 |
| R2-3 | `surge_large` | **pending_cuda** | measured OOM-kill, see below |
| R2-4 | `pxdepth` | **ready** (CPU) | native relative prediction only |
| R2-5 | `pointdit_l512` | **pending_checkpoint** | DINOv3 encoder gated |
| R2-6 | `mda_mog_sky_l2` | **ready** | — |

Three of six challengers reached inference. The three that did not were stopped
by checkpoint access or by this machine's hardware, never by a judgement about
their quality, and each carries the exact command needed to resume.

## Native representation, settled from source

| model | native field | underlying scalar | legal gauge | range conversion |
|---|---|---|---|---|
| `moge3_vitl` | metric point map (H,W,3) | — | `scale` | `‖p‖` (`norm_pointmap`) |
| `pxdepth` | `depth_log1p_affine_invariant` | **projective z-depth** | `affine_log1p_depth` (2-DOF) | `expm1(a·d+b)` then `·ρ` |
| `mda_mog_sky_l2` | mixture-mode depth (H,W) | **projective z-depth** | `affine_depth` | `(s·z+t)·ρ` |

`ρ(x) = ‖K_eval⁻¹[u,v,1]‖`, the shared evaluation camera's secant factor.

**MoGe-3.** `depth` equals the point map's z channel exactly
(`max|depth − p_z| = 0.0`) and differs from `‖p‖` by up to 13.16 m, so the point
map — not the depth channel — is the geometry, and `‖p‖` is the range. Median
`‖p‖/z` on the frozen footage is 1.14–1.17.

**PXDepth.** `PXDepth.py:226` returns `{depth_log1p_affine_invariant, mask}`;
`model/inference.py:189` solves `(a,b)` and `:195` applies
`depth = expm1(scale·pred + shift)`. The gauge is affine in log1p-depth — a
**new family**, not one of the four frozen in Round 1 — and it is 2-DOF: scale
*and* shift are unknown, so there is no legal scale-only subgroup to compare
against. `scripts/infer.py:121` back-projects with
`utils3d.pt.depth_map_to_point_map(depth, intrinsics)`, which multiplies
**unnormalised** `K⁻¹` rays, so the underlying scalar is projective z-depth.

**MDA.** `utils/geometry.py:275` unprojects as `ray_directions · z` with
unnormalised rays (`:291`); the parameter is literally named `z`. Identical to
DA3, whose convention Round-2 Part A established from the same code.

> **This immediately caught a defect.** `s2_ambiguity` had no entry for MDA, so
> it fell through to the `else: conv = "range"` default. The residual test, run
> as a diagnostic, returned `range` on some clips and `INDISTINGUISHABLE` on
> others — exactly the failure that made Round 1 mislabel DA3. The source-code
> table `CONVENTION_FROM_SOURCE` now overrides it, the residual verdict is kept
> as recorded evidence in `residual_verdict_disagreed`, and MDA's S2 was
> re-measured in z-depth. The correction made MDA's score slightly *worse*
> (0.2195 → 0.2212 mean median-abs-rel), which is the point: the convention is
> decided by what the code does, not by which answer scores better.

## Strict N=1

`strict_n1_verified: true` for all three runnable challengers, enforced at two
levels: `backends/base.py::MonoBackend.infer` raises `TypeError` on any input
that is not a single path, and each backend asserts its own view dimension every
frame.

MDA's check is the strongest, because it is the one model whose architecture
could hide a second view:

| check | result |
|---|---|
| N1a view dimension `L` | `1` (asserted every frame, not once) |
| N1b repeat run bitwise identical | **yes**, max abs diff `0.0` |
| N1c A alone vs A inside a pair | max abs diff **12.887** |
| N1d A after B identical to A alone | **yes**, max abs diff `0.0` |

N1c is the load-bearing one. A **non-zero** value proves cross-view attention is
real and active — which is precisely why feeding one image at a time is what
makes N=1 meaningful rather than nominal. N1d proves no state survives between
calls.

## Preprocessing, orientation, FOV retention

| model | source → network grid | landscape FOV kept | portrait FOV kept | map residual |
|---|---|---|---|---|
| `moge3_vitl` | 720×1280 → 630×1120 | 0.9993 | 0.9993 | 0.14 px |
| `pxdepth` | 720×1280 → 672×1176 | 0.9997 | 0.9997 | 0.30 px |
| `mda_mog_sky_l2` | 720×1280 → 280×504 | 0.9962 | 0.9962 | 0.35 px |

All three were probed in **both** orientations and handle portrait natively — no
silent crop (CLAUDE.md §7 / task §24). The residual column is the worst-case
disagreement between the measured affine source→grid map and the probe, i.e. the
map is exact to well under half a pixel.

**MoGe-3 returns its prediction on the SOURCE grid, not the network grid.** The
network consumes 630×1120 and interpolates its output back up to 720×1280, so
the map from source pixels to the *persisted prediction* is the **identity**,
not the audit map. This is the same trap that produced the Round-1 grid-map
defect (`R2_PART_D_GRIDMAP_DEFECT.md`); `evalgrid.model_output_grid` now settles
it from the probe's own output shape rather than from a hand-written table.

## Device, precision, runtime, memory

| model | device | precision | load | per image | peak RSS | CPU fallback |
|---|---|---|---|---|---|---|
| `moge3_vitl` | MPS | fp32 | — | 2.3–4.6 s | 2.57 GB | works, 22.5 s, 3.79 GB |
| `pxdepth` | **CPU only** | fp32 (`use_fp32=True`) | 3.9 s | 37–77 s | 5.14 GB | n/a |
| `mda_mog_sky_l2` | MPS | fp32 | — | 1.3–2.3 s | 10.54 GB | works, 75.3 s, 4.82 GB |

Autocast is off everywhere: MPS and CPU autocast support only bf16/fp16, so
`torch.autocast(..., dtype=float32)` silently disables itself. One model per
process, per CLAUDE.md invariant 9.

Full 288-frame runs: `moge3_vitl` 993 s (~3.5 s/frame), peak 3.04 GB;
`mda_mog_sky_l2` 603 s (~2 s/frame), peak 10.17 GB. Both 6/6 clips, 0 failures.

## Reference-implementation integrity

All three runnable challengers are **Category B** — mechanically adapted
official implementation, model math unchanged. The modifications, enumerated:

**`moge3_vitl`**
1. `from_pretrained(..., model_kwargs={"refiner": None})` — the release's *own*
   documented config override (`v2.py:84-111`).
2. An import-only `flex_gemm` stub, because `sparse_unet.py:14` imports it at
   module level. **Every stub symbol raises on construction**, so it cannot
   silently execute; it satisfies an import and nothing else.
3. Nothing else. Audited every run: 86 checkpoint keys go unloaded, **all 86
   prefixed `refiner.`**, and `model_keys_missing_from_checkpoint` is empty. A
   non-refiner key going unloaded would keep its random initialisation, so the
   backend refuses to run if that ever happens.

**`pxdepth`**
1. Device placement (CPU); `strict=True` checkpoint load.
2. The released `scripts/infer.py:74` imports `parse_size, resize_image,
   resize_map` from `pxdepth.inference` — **a module that does not exist in the
   repo, and none of those three names is defined anywhere in it**. The released
   entry point is broken as published. The preprocessing helper is reimplemented
   to the repo's own documented area/patch policy, and `forward()` is called
   directly, never `infer()`.
3. `infer()` is bypassed deliberately: it loads **MoGe-2** to solve `(a,b)`.
   §10 forbids that for the primary comparison. The backend records
   `moge2_reachable_on_this_path: False` and verifies live over `sys.modules`
   that MoGe-2 was never imported.

**`mda_mog_sky_l2`**
1. Device placement (`model_choice.py` hardcodes cuda-or-cpu).
2. A working-directory change so the release's relative checkpoint paths resolve.
3. Official `choose_model` / `prepare_views` / `DA3Wrapper.inference` on a
   one-element file list — exactly `demo.py:304`'s monocular path. Resolution
   (512 long edge), checkpoint and operators unchanged.

No operator substitutions, no interpolation-mode changes, no resolution changes
to fit memory, no attention-implementation changes, no unauthorised helper
models.

## Licence status

| model | code | weights | disposition |
|---|---|---|---|
| `moge3_vitl` | MIT | official ViT-L checkpoint | usable |
| `pxdepth` | **UNDECLARED** (no LICENSE file) | **UNDECLARED** (0-byte model card) | **research-only** |
| `mda_mog_sky_l2` | Apache-2.0 | official `DA3_MOG_Sky_LogL2.ckpt` | usable |
| `surge_large` | MIT (Microsoft) | CC BY-NC 4.0 | research-only |

Per §10, PXDepth's licence is recorded as undeclared and treated as
research-only. **No licence was invented for it.**

## Two findings that are not runtime notes

**MDA's sky mask fires underwater.** `use_sky_mask=True` is the released default;
`da3_wrapper.py:275-296` pushes every pixel it calls sky to **twice the maximum
valid depth**. Underwater frames contain no sky. Measured over the 288 frozen
frames the mask claims a median of 0.0–11.2 % per clip but reaches **32.1 % on
`wreck_05`** and **26.0 % on `wreck_07`**. The default is kept so the model is
measured as released, and the mask is persisted per frame so the effect stays
attributable rather than silently mixed into the geometry.

**MDA's mixture does not commit.** `find_gmm_mode_gpu_chunk` does not hard-select
an expert: it scores the 4 expert means *plus* confidence-weighted pairwise
midpoints (10 candidates total), keeps the lowest-NLL one and refines it with
LBFGS. **67–85 % of pixels select a midpoint rather than an expert mean**, so
the persisted `chosen_candidate_index` names a winning *initialisation*, not a
component. Per §12 none of these quantities is called calibrated confidence.

## `surge_large` — pending_cuda, measured not assumed

SurGe's Neighborhood Attention (NATTEN 0.21.6, kernel 9, 15 blocks over a
4-level pyramid) has **no backend that both runs here and is numerically the
released one**:

- **MPS: refused by NATTEN.** Verbatim: *"Can't run Flex Attention; tensor is
  not on a CUDA, ROCm, or CPU device: mps"*. All CUTLASS/Hopper/Blackwell FNA
  backends are CUDA-only.
- **CPU compiled flex: refused on two independent gates.** `checks.py:695-699`
  requires CUDA compute capability ≥ 7.0; `checks.py:723-728` excludes fp32.
  Forcing it would need `natten.allow_flex_compile()`, which itself warns *"we
  cannot verify Flex's correctness in all scenarios … your results may be
  affected significantly"* — a numerically unverified attention-implementation
  change, which reference-implementation integrity forbids.
- **CPU uncompiled flex: the only sanctioned path, and it does not fit.**
  Measured under `/usr/bin/time -l`, launched alone with nothing competing:

  | | |
  |---|---|
  | outcome | **killed by the OS before the first image finished** |
  | wall | 931.53 s (user 361.77 s, **sys 805.29 s**) |
  | max RSS | 18.48 GB |
  | peak memory footprint | **148.5 GB** |
  | page reclaims / faults | 211,030,822 / 94,722 |
  | involuntary context switches | 12,578,078 |
  | machine RAM | 24 GB |

  System time exceeding user time 2.2× and a ~138 GiB peak footprint on a 24 GB
  machine is the unfused flex path materialising the full neighborhood-attention
  score matrix: the process spent most of its life paging before jetsam killed
  it. Three attempts died the same way; the third was run alone specifically to
  rule out contention with other jobs.

**Not attempted, and why:** lowering the input long side below the frozen 1280
(that is changing model input resolution merely to make memory fit, and §2 also
forbids resampling the frozen footage); half precision plus
`allow_flex_compile()` (unverified numerics); porting the CUDA FNA kernels to
MPS or substituting an unofficial implementation (both forbidden outright).

**Stopped at:** the S0 gate, first sanity inference. No S1–S6 stage was entered.
**To resume:** one CUDA GPU with compute capability ≥ 7.0, then
`round2/scripts/s0_surge.py`, then the 288 frozen frames, then the §18
thin-structure test — where a *local-surface* specialist is most likely to
differ from everything else in the field.

## `hyden_mogev2_metric` and `pointdit_l512` — pending_checkpoint

Neither is blocked by hardware; both are blocked by weights that cannot be
obtained without authenticating to a gated service, which the execution policy
forbids.

**HyDen (R2-2).** `GatedRepoError 401`: *"Access to model
facebook/hyden-mogev2-metric-point is restricted. You must have access to it and
be authenticated to access it."* Manual approval plus an authenticated token; no
token exists on this machine. The official MetaDepth checkout and the venv are
in place — only
`hyden_mogev2_metric_point_vitl_fp32_f1066593896.pth` is missing.

**PointDiT-L 512 (R2-5).** The released checkpoint is published **without** its
image encoder — the filename says so (`nodinov3`) and `README:59-62` states *"The
DINOv3 weights are gated and cannot be redistributed, so they are not part of
the released checkpoints."* `model.py:270` requires
`feature_embedding_type='dinov3_vitb16'`; fetching those weights returns
`GatedRepoError 401` for `facebook/dinov3-vitb16-pretrain-lvd1689m`. Running it
with a *different* encoder, or with an unofficial reimplementation, would break
reference-implementation integrity, so neither was done.

Both records carry the exact resume commands and the artifacts each would need,
in `R2_S0_results.json`.

## Verdict

Three challengers pass the gate and enter S1/S2/S3: `moge3_vitl` (Step 0),
`mda_mog_sky_l2`, `pxdepth`. Three are deferred with recorded, reproducible
blockers. No model entered a scoring stage with unresolved representation
semantics, and no semantic question was settled by a residual.
