# R2 — S3 LOCAL GEOMETRY MINI-BAKEOFF (§17)

**EPISTEMIC STATUS: PRE-C2.** Reference is the Week-3 persisted range product, a
PROVISIONAL MULTI-VIEW HYPOTHESIS. "Error" here means *disagreement with that
hypothesis*, never objective monocular error. **No weighted master score**
(FREEZE 6): the six dimensions are reported separately and the §19 reduction is
argued on explicit multi-dimensional grounds.

Full frozen set: 6 clips × 48 frames = **288 frames per arm**, exactly the
Round-1 frames, no resampling. Alignment is the frozen S2 policy
(`R2_S3_policy.json`) — common policy, representation-specific transform,
clip-level scope.

Summary: `R2_S3_results.json`. Raw: `experiments/week4_mono/round1/outputs/s3/s3_raw.json`
(incumbents), `outputs/r2_s3/r2_s3_raw.json` (challengers) and
`outputs/r2_s3/r2_s3_convention_fix.json` (`da3mono_large`, `dav2_small`
recomputed under the §3/§4 convention repair — see §4).

## 1. Dimensions

| | meaning | direction |
|---|---|---|
| **M-1** | median `abs_rel` vs the provisional reference range | lower = closer |
| **M-2** | slope `b` of predicted vs reference log-range | 1.0 = no range compression/expansion |
| **M-3 rel** | relative surface-normal angle (structure, gauge-free) | lower = better |
| **M-3 abs** | absolute normal angle, and the fraction within 30° | lower / higher |
| **M-4** | symmetric boundary displacement, normalised | lower = sharper, better-placed edges |
| **M-5** | ordinal violation rate at 0.25 and 0.50 log margin | lower |
| **M-6** | outer-field / inner-field `abs_rel` ratio | 1.0 = uniform across the frame |
| **coverage** | fraction of reference-valid samples the arm predicts | higher |

## 2. Results — median over the six clips

| arm | role | M-1 | M-2 b | M-3 rel° | M-3 abs° | M-3 <30° | M-4 | M-5@.25 | M-5@.50 | M-6 | coverage |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `mapanything_n1` | incumbent I1 | **0.0853** | 0.950 | **6.84** | **7.95** | **0.95** | **0.0028** | 0.0000 | 0.0000 | 1.042 | 0.778 |
| `dav2_small` | Round-1 eliminated | 0.1094 | 0.994 | 12.65 | 18.64 | 0.76 | 0.0164 | 0.0052 | 0.0007 | **1.013** | 0.761 |
| `foundationgeo_11` | Round-1 | 0.1135 | 1.306 | 17.81 | 24.45 | 0.60 | 0.0219 | 0.0019 | 0.0001 | 1.176 | 0.806 |
| `fg_pre_ray` | mechanism arm | 0.1135 | 1.306 | 16.26 | 21.49 | 0.66 | 0.0209 | 0.0017 | 0.0001 | 1.037 | 0.806 |
| `fg_post_ray` | mechanism arm | 0.1135 | 1.306 | 16.26 | 21.49 | 0.66 | 0.0209 | 0.0017 | 0.0001 | 1.037 | 0.806 |
| `da3mono_large` | incumbent I2 (CORRECTED) | 0.1476 | 0.856 | 13.35 | 19.54 | 0.72 | 0.0223 | 0.0062 | 0.0003 | 1.136 | 0.808 |
| `metricanything_pointmap` | Round-1 | 0.1530 | 1.083 | 14.27 | 20.62 | 0.70 | 0.0249 | 0.0020 | 0.0003 | 1.080 | 0.763 |
| **`pxdepth`** | **R2-4 challenger** | 0.1589 | 0.746 | 15.42 | 20.36 | 0.72 | 0.0221 | 0.0035 | 0.0008 | 1.097 | 0.765 |
| **`moge3_vitl` (Step 0)** | **R2-1 challenger** | 0.1694 | 1.229 | 13.78 | 18.74 | 0.73 | 0.0143 | 0.0024 | 0.0001 | 0.985 | 0.755 |
| `wat3r_n1` | Round-1 | 0.1840 | 1.223 | 15.62 | 19.95 | 0.73 | 0.0171 | 0.0057 | 0.0004 | 0.932 | 0.776 |
| `moge2_vitl` | incumbent I3 | 0.1958 | 1.367 | 13.68 | 19.61 | 0.71 | 0.0320 | 0.0015 | 0.0004 | 1.072 | 0.801 |
| **`mda_mog_sky_l2`** | **R2-6 challenger** | 0.2088 | **0.473** | 17.21 | 33.34 | 0.43 | 0.0593 | 0.0394 | 0.0128 | 1.321 | 0.808 |

`mapanything_n1` leads every dimension. That is **not** a clean win: the
reference is a MapAnything-based multi-view product, so this row is partly
measuring self-agreement, and §18 shows the two share a specific failure
(thin structure) that this table cannot see. Recorded, judged post-C2.

### M-1 stratified two ways (§17 requires both)

Median over clips of the per-bin median `abs_rel`.

Provisional Week-3 **nominal metre** bins — the edges themselves are not
validated pre-C2:

| arm | 2–3 m | 3–5 m | 5–8 m | 8–12 m | 12+ m |
|---|---|---|---|---|---|
| `mapanything_n1` | 0.103 | 0.135 | 0.100 | 0.126 | 0.107 |
| `dav2_small` | 0.392 | 0.238 | 0.145 | 0.123 | 0.140 |
| `foundationgeo_11` | 0.154 | 0.188 | 0.240 | 0.134 | 0.168 |
| `fg_pre_ray` / `fg_post_ray` | 0.101 | 0.156 | 0.185 | 0.137 | 0.166 |
| `da3mono_large` | 0.482 | 0.554 | 0.235 | 0.125 | 0.139 |
| `metricanything_pointmap` | 0.173 | 0.202 | 0.166 | 0.215 | 0.345 |
| `pxdepth` | 0.601 | 0.437 | 0.199 | 0.234 | 0.178 |
| `moge3_vitl` | 0.111 | 0.190 | 0.177 | 0.226 | 0.208 |
| `wat3r_n1` | 0.458 | 0.314 | 0.186 | 0.183 | 0.200 |
| `moge2_vitl` | 0.174 | 0.191 | 0.162 | 0.224 | 0.322 |
| `mda_mog_sky_l2` | 0.610 | 0.434 | 0.385 | 0.256 | 0.220 |

**Scale-invariant** quantile bins (q0 nearest → q4 farthest, per clip):

| arm | q0 | q1 | q2 | q3 | q4 |
|---|---|---|---|---|---|
| `mapanything_n1` | 0.091 | 0.089 | 0.121 | 0.106 | 0.104 |
| `dav2_small` | 0.140 | 0.109 | 0.140 | 0.121 | 0.145 |
| `foundationgeo_11` | 0.136 | 0.111 | 0.127 | 0.103 | 0.241 |
| `fg_pre_ray` / `fg_post_ray` | 0.128 | 0.112 | 0.135 | 0.096 | 0.215 |
| `da3mono_large` | 0.257 | 0.118 | 0.100 | 0.166 | 0.138 |
| `metricanything_pointmap` | 0.127 | 0.143 | 0.174 | 0.140 | 0.573 |
| `pxdepth` | 0.256 | 0.109 | 0.123 | 0.158 | 0.275 |
| `moge3_vitl` | 0.178 | 0.151 | 0.138 | 0.167 | 0.357 |
| `wat3r_n1` | 0.176 | 0.185 | 0.157 | 0.199 | 0.229 |
| `moge2_vitl` | 0.135 | 0.188 | 0.173 | 0.202 | **1.196** |
| `mda_mog_sky_l2` | **0.400** | 0.174 | 0.125 | 0.125 | 0.313 |

The two stratifications disagree about *who* is worst and where, which is why
§17 demands both:

- **Near field.** `da3mono_large` (0.482 at 2–3 m, 0.554 at 3–5 m, q0 0.257), `wat3r_n1` (0.458),
  `pxdepth` (0.601, q0 0.256) and `mda_mog_sky_l2` (0.610, q0 0.400) are all much
  worse close in. For
  restoration this is the expensive end: attenuation and backscatter are most
  sensitive to near range.
- **Far field.** `moge2_vitl` q4 = **1.196** — the farthest fifth of every clip
  disagrees with the reference by more than a factor of two. This is the same
  far-field expansion §18 saw as `r_sea = 175 m`, arriving independently. It is
  substantially invisible in the nominal bins (0.322 at 12+ m) because those
  pool all far ranges together.
- `metricanything_pointmap` (q4 0.573) and `moge3_vitl` (q4 0.357) show the
  same effect more weakly; `mapanything_n1` and `dav2_small` are flat across
  quantiles.

**Pre-C2 caveat, stated once and load-bearing:** far-field disagreement between
a monocular arm and a multi-view product is exactly where the multi-view product
is weakest (small parallax, few matches). Neither direction of this
disagreement can be attributed pre-C2.

## 3. The three Round-2 challengers with primary results

### R2-1 `Ruicheng/moge-3-vitl` — Step 0

Official ViT-L checkpoint (§7: ViT-G not run). Implementation **category B**:
the official `from_pretrained` path with `model_kwargs` overriding
`refiner=None` — which the released `v2.py:84-111` documents as a config
override — plus an import-only stub for `flex_gemm` whose every symbol raises on
construction, so it cannot silently execute. No change to model math,
resolution, checkpoint or operators. Device MPS, float32, 2.25–3.50 s/frame,
2.57 GB RSS.

Against its own incumbent `moge2_vitl` it is **better on M-1 (0.169 vs 0.196),
much better on M-4 boundaries (0.0143 vs 0.0320) and better on M-6 uniformity
(0.985 vs 1.072)**, with comparable normals and slightly lower coverage (0.755
vs 0.801). Its far-field q4 (0.357) is less extreme than MoGe-2's (1.196).
That is a real, multi-dimensional improvement over the incumbent it replaces.

Two things qualify it. Its M-2 slope is 1.229 — it still expands range relative
to the reference. And `wreck_01` is a genuine outlier (M-1 0.440 against 0.116
on `wreck_07`); the same clip drives its S2 residual of 0.5011 and its S5
result. S5 additionally finds it **temporally worse than MoGe-2**
(`f2f_log_mad` 0.0794 vs 0.0679). The trade-off is preserved, not resolved here.

**§7's Step 0 → Step 3 ablation is not answerable on this machine.** The S0 gate
established what `refine_steps` actually changes in the current code and
confirmed Step 0 never executes the refiner (checkpoint keys left unloaded are
all refiner keys). Step 3 requires the sparse-UNet / `flex_gemm` CUDA path:
`step3_status = pending_cuda`. Per the CUDA execution policy it is recorded, not
approximated, and no Step-3 arm exists in S3, §18 or S5.

### R2-4 PXDepth

Official released checkpoint, run at the repository's own documented
preprocessing policy. Implementation **category B**, and the adaptation is
larger than the other two, so it is enumerated: the released `scripts/infer.py`
is **broken as published** — line 74 imports three names from `pxdepth.inference`,
a module that does not exist anywhere in the repo — so the *entry script* was
reimplemented around the unmodified model. What it reimplements is the repo's
own documented policy (`--input-size 1022×770`, `--resize-by-area`, preserving
the source aspect), not a policy of ours. Model math, checkpoint, operators and
resolution are unchanged. Run on **CPU** (MPS not used for the full set),
22.25–23.68 s/frame, 6 847 s for 288 frames, peak RSS 5.68 GB — the slowest arm
in Round 2 by an order of magnitude.

**Licence: UNDECLARED.** The repository states no licence for code or weights.
Per §10 that is recorded as-is and the model is treated as **research-only**. No
licence is inferred.

**The MoGe-2 assist is excluded and was never run.** The released repo recovers
metric scale by loading MoGe-2; §10 forbids that in the primary Round-2 geometry
comparison, so the primary result here is the **native relative prediction**
only. No helper model's scale entered any number in this document.

**Native representation:** `log1p_depth_affine_invariant`, family
`affine_log1p_depth`, convention `z_depth` **from source code** — the released
`scripts/infer.py:121` back-projects with
`utils3d.pt.depth_map_to_point_map(depth, intrinsics)`, which multiplies
*unnormalised* `K^-1` rays by the scalar, so the field is log1p of projective
z-depth. The residual verdict disagreed (`INDISTINGUISHABLE` / `range`) and was
overruled: per §14, semantic source evidence wins over residual, which is the
exact mistake Round 1 made with DA3.

On the table it lands mid-pack: M-1 0.1589 (between `metricanything_pointmap`
and `moge3_vitl`), with **boundary placement (M-4 0.0221) better than MoGe-2
(0.0320) and level with corrected DA3 (0.0223)** — which is *part* of what a
structure-preserving pixel-space method is supposed to buy, but only part: after
the §3/§4 convention repair reached this stage (§4 below) DA3's M-4 improved from
0.0285 to 0.0223, so the DA3 comparison is a tie, not a win. Against MoGe-2 the
margin stands. Ordinal violation is low. Its M-2 slope
of 0.746 is a real range compression, and its quantile profile is U-shaped
(q0 0.256, q1 0.109, q4 0.275): best in the middle, worst at both ends.

#### The `cenote_01` failure, and what it is not

Five of the six clips behave; `cenote_01` does not, and it is not a small
outlier — it is a **sign inversion**. The frozen clip fit came out at
**s = −0.2701** (`log1p(z_ref) ≈ s·native + t`) against +1.72, +1.93, +1.72,
+0.27, +0.56 on the others. A negative slope means the fit believes the model's
field runs backwards.

Because a negative slope is exactly the kind of number that must be attributed
before it is reported, the raw pre-alignment order agreement was measured
directly — per-frame Spearman rank correlation between the untouched native
field and the reference, no fit, no gauge, no conversion. Rank correlation is
invariant to *any* monotone gauge, so nothing the alignment does can move it
(`outputs/r2_s3/r2_pxdepth_rank_diagnostic.json`):

| clip | Spearman median | range over frames | frames < 0 | fitted `s` |
|---|---|---|---|---|
| `wreck_07` | +0.974 | +0.940 … +0.994 | 0.00 | +1.727 |
| `wreck_05` | +0.989 | +0.944 … +0.996 | 0.00 | +1.925 |
| **`cenote_01`** | **−0.298** | **−0.871 … +0.811** | **0.79** | **−0.270** |
| `swimthrough_02` | +0.973 | +0.939 … +0.987 | 0.00 | +1.718 |
| `wreck_01` | +0.996 | +0.691 … +0.999 | 0.00 | +0.274 |
| `wreck_03` | +0.938 | −0.154 … +0.988 | 0.02 | +0.564 |

The five control clips sit at 0.94–0.996 through the *same* arm, the same code
path and the same Part-D grid map, so this is **not a harness defect** — a
mis-sampling would not spare five clips and invert the sixth.

Pre-C2 it must still be stated as *disagreement*: the reference is a provisional
hypothesis, and a cave interior with large low-texture volumes is exactly where a
multi-view product is weakest. But one part of it the reference cannot explain:
within `cenote_01` the correlation's **sign flips frame to frame** (−0.871 to
+0.811 across 48 frames of a continuous shot). A multi-view product over a
continuous clip does not reverse its own depth order between adjacent frames.
Whatever share of the disagreement belongs to the reference, the *instability*
is PXDepth's, and it is the same clip and the same mechanism that produces its
S5 collapse (`wander` 65.9, `f2f_log_mad` 1.954, i.e. ×7 between adjacent
frames).

This one clip carries most of PXDepth's bad medians. Excluding it:

| | all six clips | five clips, `cenote_01` removed |
|---|---|---|
| M-1 | 0.1589 | 0.1599 |
| M-2 `b` | 0.746 | 0.781 |
| M-3 rel° | 15.42 | 13.88 |
| M-3 abs° | 20.36 | 19.46 |
| M-5@0.25 | 0.0035 | 0.0031 |
| M-6 | 1.097 | **1.000** |
| coverage | 0.765 | 0.752 |

M-1 barely moves — a near-degenerate fit can still land close in `abs_rel` when
the reference's own depth spread is narrow — but M-6 goes to 1.000, i.e. on the
five working clips PXDepth is *uniform across the frame*, and the whole
non-uniformity was that one clip. **Both rows are reported; neither replaces the
other.** The six-clip row is the frozen result and the one §19 must use; the
five-clip row is what says the failure is localised rather than diffuse.

One further reading, so `wreck_01` is not mistaken for a second failure: its
fitted `s` is small (+0.274) while its rank agreement is the *highest* of all six
(+0.996). The reference's own log1p spread on that clip is only 0.35 against
PXDepth's 0.87, so a small slope is the correct fit, not a degraded one. Its
elevated M-1 (0.248) and M-4 (0.194) come from `abs_rel` and boundary
normalisation being hypersensitive when the reference field is nearly flat — a
property of the clip, shared with other arms, not of PXDepth.

### R2-6 MDA `mda_mog_sky_l2`

Official DA3_MOG_Sky_LogL2 checkpoint (§12: the VGGT variant was **not** added).
Implementation **category B**: device placement only — `model_choice.py`
hardcodes cuda-or-cpu; the official `choose_model` / `prepare_views` /
`DA3Wrapper.inference` are called with a one-element file list, which is exactly
the `demo.py:304` mono path, at the demo default 512 long edge. Apache-2.0.
1.48–2.29 s/frame, 10.54 GB RSS — by far the heaviest arm here.

**Strict N=1 verified independently** (§12): one image enters, the view
dimension L = 1, repeat inference is bitwise identical, and running image A
alone versus A inside a pair changes the output by up to 12.89 — a non-zero
difference that *proves* the pair path is genuinely multi-view and that the N=1
path is not silently receiving neighbours.

It is last or near-last on every dimension: M-1 0.209, M-4 0.0593 (2× the next
worst), M-5@0.25 0.0394 (an order of magnitude above everything else), M-6 1.321
(strongly non-uniform across the frame), M-3 within-30° only 0.43. **M-2 b =
0.473** is the structural finding: it compresses the range field by roughly a
factor of two against the reference, which no clip-level scale can fix because a
slope is not a gauge. Its near field is its worst region (2–3 m: 0.610).

Against that, §18 found it *does* separate the crane lattice (gap +0.226 with
`fill` −0.004, i.e. no false surface) and S5 found its local surface stability
third-best of nine — its instability is almost entirely in the frame-varying
global scale (`f2f_log_mad` 0.174 vs 0.079 next-worst). So the failure is
specific and describable: **MDA's shape is locally reasonable and its global
range mapping is wrong and drifting.**

The mixture quantities (component depths, probabilities, chosen component,
entropy, top-1/top-2 margin, component separation) are persisted in
`outputs/r2_mda_ambiguity.json`. Per §12 they are **not** called calibrated
confidence; whether they correlate with actual failure is a §26 question
answered separately.

## 4. OLD vs CORRECTED

**Three** repairs land here, not two, and they have to be kept apart because two
of them touch different arms. Full per-arm accounting for the grid repair is in
`R2_PART_D_GRIDMAP_DEFECT.md` §3b; for the convention repair, `R2_PARTS_ABC_CORRECTNESS.md`
§A3 and §B.

- **D — grid repair.** Sampling defect in *our* harness. Affected the four
  source-grid arms (`dav2_small`, `foundationgeo_11`, `moge2_vitl`,
  `metricanything_pointmap`). `mapanything_n1`, `da3mono_large` and `wat3r_n1`
  are controls.
- **A/B — convention repair.** DA3's scalar is projective **z-depth**, not
  Euclidean range (§3, from `P = t + D·R·K^-1 p`); DA v2's disparity inverts to
  z-depth the same way (§4). Affects exactly `da3mono_large` and `dav2_small`.
- **A/B late-arriving defect.** The convention repair reached S2, S4, S5, §18 and
  S6 — every stage that reads `R2_S3_policy.json` — but the S3 summary
  originally sourced its two incumbent rows from `results/S3_results.json`, which
  had been regenerated for the grid repair under the **Round-1** policy
  (`convention: "range", convention_source: "MEASURED in S2"`). So this table
  printed "(CORRECTED)" over uncorrected numbers. Found while assembling the
  final report, recomputed under the frozen `R2_S3_policy.json`, and merged here
  (`outputs/r2_s3/r2_s3_convention_fix.json`). Blast radius verified to be **S3
  only**: §18, S4, S5 and S6 all store the corrected alignment (`s = 5.9868,
  t = 5.5356` for DA3), and the recompute reproduces `R2_PARTS_ABC_CORRECTNESS.md`
  §A3 to four decimals. The ten other rows are byte-identical before and after.

| arm | M-1 | M-3 rel° | M-4 | M-5@0.25 | M-6 |
|---|---|---|---|---|---|
| `mapanything_n1` (control) | 0.0853 → 0.0853 | 6.84 → 6.84 | 0.0028 → 0.0028 | 0.0000 → 0.0000 | 1.043 → 1.043 |
| `wat3r_n1` (control) | 0.1840 → 0.1840 | 15.62 → 15.62 | 0.0171 → 0.0171 | 0.0057 → 0.0057 | 0.932 → 0.932 |
| `da3mono_large` (A only) | 0.1283 → **0.1476** | 12.77 → 13.35 | 0.0285 → **0.0223** | 0.0037 → 0.0062 | 1.014 → 1.136 |
| `dav2_small` (D, then B) | 0.1761 → 0.1092 → **0.1094** | 27.50 → 12.72 → **12.65** | 0.1022 → 0.0167 → **0.0164** | 0.1172 → 0.0057 → **0.0052** | 0.935 → 0.939 → 1.013 |
| `foundationgeo_11` | 0.1712 → **0.1135** | 32.71 → **17.81** | 0.0423 → **0.0219** | 0.0862 → **0.0019** | 0.794 → 1.176 |
| `moge2_vitl` | 0.2156 → **0.1958** | 27.78 → **13.68** | 0.0355 → 0.0320 | 0.0676 → **0.0015** | 1.008 → 1.072 |
| `metricanything_pointmap` | 0.1819 → **0.1530** | 27.50 → **14.27** | 0.0360 → 0.0249 | 0.0665 → **0.0020** | 0.938 → 1.080 |

Ordinal violations at a 0.25 log margin fell **95–98 %** for every source-grid
model. Sampling a smooth depth field 12–28 % off-position manufactures exactly
that kind of violation, because the value fetched for a far pixel is the value of
a nearer one. **Those violations were an artifact of the harness, not a property
of any model** — and Round 1 read them as a property of the models.

Two consequences that must be carried into §19:

1. **`dav2_small` can no longer be called "clearly eliminated" on Round-1
   grounds.** At M-1 0.1094 it is now second only to `mapanything_n1`, ahead of
   corrected DA3 (0.1476) and every point-map arm. Per §4 the DA v2 recompute
   stops here; the elimination has to be re-argued on the dimensions that
   actually still separate it — coverage 0.761, and §18's Tier-A coverage of
   only 0.464 with an edge-gain of 2.51, i.e. it does not place edges.
2. **The Round-1 "source-grid models are a distinct worse tier" conclusion was
   the defect, not the models.**

## 5. Not in this table

| arm | status | why |
|---|---|---|
| `surge_large` (R2-3) | `pending_cuda` | NATTEN 0.21.6 `neighborhood_attention_generic` exposes no MPS backend (`choose_backend` → `flex-fna` on CPU, `NotImplementedError` on MPS). Substituting a different attention implementation is forbidden (numerically non-equivalent), so it is recorded, not approximated. MIT code, **CC BY-NC 4.0 weights → research-only**. |
| `hyden` (R2-2) | `pending_checkpoint` | Official MetaDepth checkout present, code only. FAIR Noncommercial Research License → research candidate. |
| `pointdit_l_512` (R2-5) | `pending_checkpoint` | — |
| MoGe-3 Step 3 | `pending_cuda` | see §3 above |

No fabricated results, no unofficial substitutes, no ported CUDA kernels.

## 6. Pre-C2 reading

- Three of the six authorised challengers produced primary results. None
  displaces `mapanything_n1` on this table.
- `moge3_vitl` Step 0 is a **genuine multi-dimensional improvement over its own
  incumbent `moge2_vitl`** (M-1, M-4, M-6, far-field q4) while being temporally
  worse (S5). That is a trade-off to carry into §19, not a promotion.
- `mda_mog_sky_l2` **fails** the primary local-geometry comparison — M-2 b =
  0.473 is a range-compression the alignment cannot absorb — while showing a
  specialist property at the lattice and good local surface stability. §19 will
  have to decide between FAILURE and SPECIALIST on stated grounds.
- `pxdepth` is the most *bimodal* arm in the stage: on five clips it is a
  competent structure-preserving predictor with boundary placement better than
  `moge2_vitl` and level with corrected `da3mono_large` (M-4 0.0221 vs 0.0320 and
  0.0223) and M-6 exactly 1.000, and on `cenote_01` its depth
  order inverts and its sign flips frame to frame. §19 must classify a model
  that is neither dominated nor safe.
- The largest single change in this stage is **not** attributable to any
  challenger: it is the Part D grid repair, which removed a harness artifact
  that Round 1 had read as a property of four models.
