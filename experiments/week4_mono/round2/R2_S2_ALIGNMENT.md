# R2 — S2 AMBIGUITY AND ALIGNMENT (§16)

**EPISTEMIC STATUS: PRE-C2.** The reference is `D_mapanything`, a PROVISIONAL
MULTI-VIEW HYPOTHESIS. Every residual below is *disagreement with the current
Week-3 hypothesis*, never objective monocular error. Raw metric scale is
recorded, not judged.

Machine-readable policy: `R2_S2_alignment_policy.json` (incumbents, with the
`repairs` block) and `R2_S3_policy.json` (the merged 11-arm policy S3 consumed).
Raw fits: `outputs/r2_s2/r2_s2_raw.json`, `outputs/r2_s2/r2_s2_challengers.json`.

## 1. The policy did not move

One **policy**, not one transform. Round 1 froze it and Round 2 keeps it:

- The legal E1 family is a function of the **native representation**, never a
  universal `a·d + b`. Fitting one transform across representations is the
  standard way to make a monocular comparison meaningless.
- **Scope is clip-level for every arm.** Per-frame fits are DIAGNOSTICS ONLY.
  Rationale is FREEZE C7: `d'_t = s_t·d_t` is physically consistent under
  `β'_t = β/s_t`, so a *constant* clip-wide scale is a benign gauge (refit the
  water coefficients once), but *frame-varying* drift would demand water
  properties that change with the estimator. Renormalising per frame would
  erase exactly the failure mode S5 exists to measure.
- Raw output is preserved; the oracle scale is a diagnostic granting the one
  gauge a shared clip-level physical model can absorb, **not** a deployment
  entitlement.
- **No external helper model's scale enters any primary fit** (§10, §24). This
  is why `pxdepth` is evaluated on its native relative prediction and the
  MoGe-2-assisted metric path is a separate optional diagnostic.
- Nuisance parameters are reported, never hidden (FREEZE C9). A model that
  needs a large additive shift has told you something about itself.

| arm | native kind | E1 family | z-vs-range convention | source of the convention |
|---|---|---|---|---|
| `mapanything_n1` | `depth_along_ray_metric` | `scale` | range | verified semantics (S0) |
| `moge2_vitl` | `pointmap_metric` | `scale` | range | verified semantics (S0) |
| `metricanything_pointmap` | `pointmap_metric` | `scale` | range | verified semantics (S0) |
| `foundationgeo_11`, `fg_pre_ray`, `fg_post_ray` | `pointmap_metric` | `scale` | range | verified semantics (S0) |
| `wat3r_n1` | `pointmap` | `scale` | range | verified semantics (S0) |
| `moge3_vitl` | `pointmap_metric` | `scale` | range | **S0, source** |
| `da3mono_large` | `depth_relative` | `affine_depth` | **z_depth** | **SOURCE CODE (Part A repair)** |
| `dav2_small` | `disparity_relative` | `affine_disparity` | **z_depth** | **SOURCE CODE (Part B repair)** |
| `mda_mog_sky_l2` | `depth_relative` | `affine_depth` | **z_depth** | **S0, source** |
| `pxdepth` | `log1p_depth_affine_invariant` | `affine_log1p_depth` | **z_depth** | **SOURCE CODE** (residual disagreed) |

## 2. What moved: two conventions, decided by source and not by residual

Round 1 settled z-vs-range for two arms by comparing residuals under each
hypothesis. That was the wrong instrument, and §14 forbids repeating it.

**`da3mono_large` → `z_depth`.** Depth-Anything-3's own
`utils/geometry.py:271` builds `ray_directions = K⁻¹ · homogenize(coords)`
**without normalising** and returns `ray_directions · z`; `:359`
`pixel_space_to_camera_space` does `camera_space_points · depth`. `K⁻¹[u,v,1]ᵀ`
has third component 1, so the multiplying scalar is the camera-axis Z. The
parameter is literally named `z`. Round 1's residual test returned `range` at a
margin of only 1.138 — a 14 % preference over a hypothesis the source rules out.

**`dav2_small` → `z_depth`.** DA v2 emits relative disparity, i.e. inverse depth
in the monocular-depth dataset sense, and KITTI/NYU/Hypersim targets are all
projective z. The affine ambiguity is therefore legal in `1/z`, so the reference
enters as `q_ref = 1/z_ref`, not `1/r_ref`. Round 1's residual test returned
INDISTINGUISHABLE (margin 1.019) — **which is itself the finding**: this model's
shape error exceeds this camera's ~35 % radial secant term, so the residual test
had no power here even in principle.

Part D found the same lesson independently: under the *wrong* grid map,
`dav2_small` read as `range` on `wreck_05` and `swimthrough_02` and as `z_depth`
under the right one. A verdict that flips when an unrelated harness bug is fixed
was never evidence about the model.

**Conversion.** `ρ(x) = ‖K⁻¹p(x)‖` from the frozen provisional camera model — no
new K was invented, and resize/crop/orientation/principal-point handling is the
frozen mapping. `z_ref = r_ref/ρ`; fit in the model's native space; then
`r̂ = ẑ·ρ`. Frozen-set `ρ`: median 1.045–1.127, max 1.161–1.507. Central-camera
approximation, provisional pre-C2.

## 3. E1 residual after the frozen clip-level fit (`log_residual_mad`)

Lower = closer agreement with the provisional hypothesis. **Not a score.**

| arm | family | wreck_07 | wreck_05 | cenote_01 | swimthr_02 | wreck_01 | wreck_03 | median |
|---|---|---|---|---|---|---|---|---|
| `mapanything_n1` | scale | 0.0740 | 0.0618 | 0.1172 | 0.0870 | 0.1617 | 0.1304 | **0.1021** |
| `dav2_small` | affine_disparity | 0.1080 | 0.1071 | 0.1147 | 0.1061 | 0.2025 | 0.1246 | 0.1114 |
| `foundationgeo_11` | scale | 0.1262 | 0.1243 | 0.1917 | 0.0976 | 0.2563 | 0.1184 | 0.1252 |
| `da3mono_large` | affine_depth | 0.1719 | 0.2213 | 0.0864 | 0.1104 | 0.2336 | 0.1232 | 0.1475 |
| `pxdepth` | affine_log1p_depth† | 0.1529 | 0.1693 | 0.1568 | 0.1500 | 0.2655 | 0.1667 | 0.1618 |
| `moge3_vitl` (Step 0) | scale | 0.1224 | 0.1501 | 0.2668 | 0.1377 | 0.5011 | 0.2065 | 0.1783 |
| `metricanything_pointmap` | scale | 0.1702 | 0.1163 | 0.2071 | 0.0681 | 0.4206 | 0.2225 | 0.1887 |
| `wat3r_n1` | scale | 0.1878 | 0.2264 | 0.1305 | 0.1447 | 0.2606 | 0.2226 | 0.2052 |
| `mda_mog_sky_l2` | affine_depth | 0.1782 | 0.3369 | 0.1509 | 0.2285 | 0.2777 | 0.1852 | 0.2068 |
| `moge2_vitl` | scale | 0.2005 | 0.1553 | 0.2293 | 0.0811 | 0.3577 | 0.2833 | 0.2149 |

† **`pxdepth`'s row is recomputed, and this is a comparability defect worth
recording.** `Alignment.log_residual_mad` is measured in each family's own
fitting space. For every other family that space is depth-like or
disparity-like, so the stored number *is* the robust spread of the log range
ratio and the column is comparable. `affine_log1p_depth` fits against
`log1p(z_ref)`, so its stored residual is the spread of `log(log1p(z)/fitted)` —
the log **of** a log1p — which is systematically smaller and is a different
quantity. The stored values (0.0587 / 0.0574 / 0.0697 / 0.0573 / 0.1247 /
0.0558, median 0.0581) would have put `pxdepth` at the top of this table by a
wide margin, which would have been a units error rather than a result. The row
above is instead the MAD of `log(r_ref) − log(r̂)` after the frozen clip fit and
the `r̂ = ẑ·ρ` conversion, pooled over each clip exactly as the other rows are
(`outputs/r2_s2/r2_pxdepth_comparable_e1.json`). No primary metric was affected —
M-1…M-6 are all computed on converted ranges — only this diagnostic column.

`mapanything_n1` leading is expected and **not** evidence of superiority: the
reference is a MapAnything-based multi-view product, so this row partly measures
self-agreement. §18 makes that concrete — the reference and `mapanything_n1`
share the thin-structure failure exactly.

`wreck_01` is the hardest clip for every arm and by a wide margin for
`moge3_vitl` (0.5011) and `metricanything_pointmap` (0.4206).

## 4. OLD vs CORRECTED

Two independent repairs land in S2:

**Part A/B (convention).** Affects only `da3mono_large` and `dav2_small`; per
clip, primary-family `log_residual_mad`:

| arm | wreck_07 | wreck_05 | cenote_01 | swimthr_02 | wreck_01 | wreck_03 |
|---|---|---|---|---|---|---|
| `da3mono_large` OLD | 0.1569 | 0.2147 | 0.0912 | 0.1157 | 0.2151 | 0.1051 |
| `da3mono_large` CORRECTED | 0.1719 | 0.2213 | 0.0864 | 0.1104 | 0.2336 | 0.1232 |
| `dav2_small` OLD | 0.1167 | 0.1195 | 0.1106 | 0.1145 | 0.2075 | 0.1074 |
| `dav2_small` CORRECTED | 0.1080 | 0.1071 | 0.1147 | 0.1061 | 0.2025 | 0.1246 |

Note the direction: **correcting DA3's semantics made its E1 residual slightly
worse on four of six clips.** That is the point of §14 — the correct convention
is the one the source declares, not the one that minimises disagreement with a
provisional reference. The corrected DA3 is also the arm that turns out to
resolve the crane lattice (§18), which the old, better-scoring convention did
not.

**Part D (grid map).** Affects the four source-grid arms; the three
network-grid arms are bitwise unchanged controls. Mean primary-family
`abs_rel`: `dav2_small` 0.1763 → 0.1276 (−27.6 %), `foundationgeo_11` 0.1932 →
0.1504 (−22.2 %), `metricanything_pointmap` 0.2146 → 0.1886 (−12.1 %),
`moge2_vitl` 0.2247 → 0.2043 (−9.1 %). Full accounting in
`R2_PART_D_GRIDMAP_DEFECT.md`.

## 5. Nuisance parameters, reported not hidden (FREEZE C9)

### `da3mono_large`, native z, `z_ref = s·z_DA3 + t`

| clip | s | t (m) | t / representative scene z | residual reduction from granting t | s_t median | s_t log-std | s_t wander | s_t f2f MAD | t_t IQR (m) |
|---|---|---|---|---|---|---|---|---|---|
| wreck_07 | 5.987 | 5.54 | 0.53 | +0.351 | 6.057 | 0.110 | 1.69 | 0.034 | 2.56 |
| wreck_05 | 6.734 | 10.36 | 0.62 | **−0.033** | 6.959 | 0.270 | 2.35 | 0.049 | 9.43 |
| cenote_01 | 2.696 | 3.08 | 0.51 | +0.523 | 2.760 | 0.138 | 1.84 | 0.055 | 1.14 |
| swimthrough_02 | 8.101 | 4.44 | 0.40 | +0.268 | 8.994 | 0.118 | 1.55 | 0.031 | 1.62 |
| wreck_01 | 3.834 | 1.86 | 0.41 | +0.013 | 2.887 | 0.313 | 3.97 | 0.064 | 1.20 |
| wreck_03 | 5.495 | 10.14 | 0.65 | +0.416 | 6.141 | 0.280 | 3.61 | 0.092 | 2.31 |

Three things this table says and the headline residual does not:

1. **The additive term is large.** `t` is 40–65 % of the representative scene
   z-depth on every clip. DA3's relative depth is not "approximately
   scale-only" here, and per FREEZE C1 only measured evidence may earn that
   description — this measurement denies it.
2. **Granting `t` does not always help.** Reduction is +0.52 on `cenote_01` but
   **−0.03 on `wreck_05`** and +0.01 on `wreck_01` (the fit optimises a Huber
   log residual; `median_abs_rel` is a different statistic and can move against
   it). The affine family is retained anyway because it is the *legal* family
   for this representation, not because it wins.
3. **`s` varies 3.0× across clips** (2.70 → 8.10). The clip-level gauge is doing
   real work; a single global constant would not survive.

### `dav2_small`, native disparity, `q_ref = a·q_DAv2 + b`

`a` ranges 0.0100 → 0.0367 across clips (3.7×) and `b` 0.0166 → 0.1196 (7.2×).
The per-frame `a_t` wander ratio reaches 3.66 (`wreck_03`) and 3.22
(`cenote_01`). Per §4 the recompute stopped at S2 + S3; the elimination decision
is carried to §19, with one flag: after the Part D repair DA v2's S3 M-1 is
0.1094, i.e. **better than corrected DA3's 0.1476**, so "clearly eliminated" can
no longer be asserted on the Round-1 grounds and must be re-argued.

### Challengers

`moge3_vitl` — `scale` only (metric point map). Clip fits `s` = 2.027, 2.727,
1.220, 2.349, 3.285, 2.317 (a 2.7× spread; the per-frame trajectory medians give
the same picture, `clip_to_clip_scale_spread` 2.89). `wreck_01` shows a per-frame
`wander_ratio` of 8.21 with `f2f_log_mad` 0.255 — that single clip drives both
its worst E1 (0.5011) and its S5 result.

`mda_mog_sky_l2` — `affine_depth`, convention `z_depth` from source. Recorded in
its raw block: **the residual test disagrees with the source on five of six
clips** — it returns `range` on `wreck_07`, `wreck_01`, `wreck_03` and
INDISTINGUISHABLE on `wreck_05`, `swimthrough_02`, agreeing only on `cenote_01`.
Source wins, per §14, and a residual test that lands on three different answers
across six clips of the same camera is a good illustration of why. Clip fits
range from `s` 1.62, `t` 4.38 (`cenote_01`) to `s` 15.62, `t` 2.19
(`wreck_07`) — a 9.6× spread in `s`, the largest of any arm. On `wreck_07` the
scale-only family actually fits *better* (0.1620 vs 0.1782), the same
non-monotonicity DA3 shows on `wreck_05`.

`pxdepth` — `affine_log1p_depth`, convention `z_depth` **from source code**;
the residual test again disagreed, returning a pooled `range` at a margin ratio
of 1.0031 (i.e. the two hypotheses differ by 0.3 %, well inside the 3 % tie
band) and landing on three different answers across the six clips — `z_depth`
on `wreck_07` and `cenote_01`, INDISTINGUISHABLE on `wreck_05` and
`swimthrough_02`, `range` on `wreck_01` and `wreck_03`. Source wins, per §14.
Clip fits: `s` = +1.727, +1.925, **−0.270**, +1.718, +0.274, +0.564, with `t` =
1.88, 2.40, 2.06, 2.06, 1.61, 2.65. **The negative `s` on `cenote_01` is not a
fitting artefact**: measured without any alignment at all, the raw native field
is rank-*inverted* against the reference on that clip (median Spearman −0.298,
sign flipping frame to frame), while the other five sit at +0.94…+0.996 through
the identical code path. The evidence is in S3 §3 R2-4 and
`outputs/r2_s3/r2_pxdepth_rank_diagnostic.json`. The small `s` on `wreck_01`
(+0.274) is by contrast a *correct* fit — that clip's reference log1p spread is
only 0.35 against PXDepth's 0.87, and its rank agreement is the highest of the
six.

The MoGe-2-assisted metric path is **not** admissible for the primary comparison
(§10) and **was never run**: no helper model's scale enters any S2 number.

## 6. Not yet fitted

| arm | status |
|---|---|
| `surge_large` | `pending_cuda` |
| `hyden`, `pointdit_l_512` | `pending_checkpoint` |
| MoGe-3 Step 3 | `pending_cuda` (`refine_steps > 0` unsupported on this backend) |

## 7. Sensitivity fits declared but NOT substituted

The predeclared range-balanced / robust variant is **sensitivity only**. It does
not replace the frozen primary fit and is not selected on the basis of which
produces the better model score. Likewise the primary DA v2 objective stays in
native inverse-z; it was **not** moved to log-depth or z-space to improve
far-range restoration error.
