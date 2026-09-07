# S3 — primary local-geometry bakeoff

**Stage:** S3, the primary pre-C2 field reduction.

Full frozen set: 6 clips x 48 frames = 288 frames per arm, against the Week-3 persisted range
product, under the frozen S2 alignment policy, with the six universal metrics.
Nothing else was added to the primary ranking.

**The reference is a provisional multi-view hypothesis, not ground truth.**
Everywhere below, "error" means disagreement with the current Week-3 hypothesis.
Week 3 measured its own reference's instability and it is large on exactly the
low-texture clips: whole-pipeline reruns moved `wreck_05` by 2.1-6.5 % median while
`wreck_07` moved 0.01 %. A few percent of monocular-vs-reference disagreement on
`wreck_05` or `wreck_01` says as much about the reference as about the model.

**There is no weighted master score.** Six dimensions, reported separately.

## Headline: the six dimensions, median across the six clips

| arm                     | M-1 abs-rel | M-2 slope b | M-3 RelNormal deg | M-3 normal deg | M-4 boundary | M-5 ordinal@25% | M-6 outer/inner | coverage |
|-------------------------|-------------|-------------|-------------------|----------------|--------------|-----------------|-----------------|----------|
| mapanything_n1          | 0.0853      | 0.950       | 6.84              | 7.9            | 0.0028       | 0.0000          | 1.04            | 0.778    |
| dav2_small              | 0.1092      | 0.908       | 12.72             | 20.8           | 0.0167       | 0.0057          | 0.94            | 0.761    |
| moge2_vitl              | 0.1958      | 1.367       | 13.68             | 19.6           | 0.0320       | 0.0015          | 1.07            | 0.801    |
| metricanything_pointmap | 0.1530      | 1.083       | 14.27             | 20.6           | 0.0249       | 0.0020          | 1.08            | 0.763    |
| wat3r_n1                | 0.1840      | 1.223       | 15.62             | 19.9           | 0.0171       | 0.0057          | 0.93            | 0.776    |
| da3mono_large           | 0.1283      | 0.846       | 12.77             | 20.6           | 0.0285       | 0.0037          | 1.01            | 0.808    |
| foundationgeo_11        | 0.1135      | 1.306       | 17.81             | 24.4           | 0.0219       | 0.0019          | 1.18            | 0.806    |

Direction of good: M-1 abs-rel lower better; M-2 slope b 1.0 ideal; M-3 RelNormal deg lower better; M-3 normal deg lower better; M-4 boundary lower better; M-5 ordinal@25% lower better; M-6 outer/inner 1.0 flat.

`coverage` is the fraction of evaluation samples where the arm AND the reference
both have valid support. It is a first-class result, not bookkeeping — an arm can
only be scored where it predicts something, and declining to predict is itself a
behaviour.

## Per-dimension detail, with the per-clip spread

FREEZE §6 forbids hiding a result that helps one category and hurts another, so
every dimension is given with its range across the six clips and its worst clip.

### M-1 abs-rel (lower better)

| arm                     | median | min    | max    | worst clip        |
|-------------------------|--------|--------|--------|-------------------|
| mapanything_n1          | 0.0853 | 0.0526 | 0.1689 | wreck_01 (0.1689) |
| dav2_small              | 0.1092 | 0.0965 | 0.2230 | wreck_01 (0.2230) |
| moge2_vitl              | 0.1958 | 0.0782 | 0.3166 | wreck_01 (0.3166) |
| metricanything_pointmap | 0.1530 | 0.0672 | 0.3635 | wreck_01 (0.3635) |
| wat3r_n1                | 0.1840 | 0.1175 | 0.2550 | wreck_01 (0.2550) |
| da3mono_large           | 0.1283 | 0.0852 | 0.2159 | wreck_01 (0.2159) |
| foundationgeo_11        | 0.1135 | 0.0985 | 0.2523 | wreck_01 (0.2523) |

### M-2 slope b (1.0 ideal)

| arm                     | median | min   | max   | worst clip        |
|-------------------------|--------|-------|-------|-------------------|
| mapanything_n1          | 0.950  | 0.873 | 1.018 | cenote_01 (0.873) |
| dav2_small              | 0.908  | 0.510 | 1.120 | wreck_03 (0.510)  |
| moge2_vitl              | 1.367  | 0.918 | 2.116 | wreck_05 (2.116)  |
| metricanything_pointmap | 1.083  | 0.905 | 1.656 | wreck_05 (1.656)  |
| wat3r_n1                | 1.223  | 0.953 | 1.411 | wreck_01 (1.411)  |
| da3mono_large           | 0.846  | 0.592 | 1.148 | wreck_03 (0.592)  |
| foundationgeo_11        | 1.306  | 0.878 | 1.411 | cenote_01 (1.411) |

### M-3 RelNormal deg (lower better)

| arm                     | median | min  | max   | worst clip             |
|-------------------------|--------|------|-------|------------------------|
| mapanything_n1          | 6.84   | 2.95 | 9.81  | cenote_01 (9.81)       |
| dav2_small              | 12.72  | 4.09 | 17.78 | swimthrough_02 (17.78) |
| moge2_vitl              | 13.68  | 3.77 | 17.25 | swimthrough_02 (17.25) |
| metricanything_pointmap | 14.27  | 3.93 | 17.33 | swimthrough_02 (17.33) |
| wat3r_n1                | 15.62  | 2.64 | 17.98 | swimthrough_02 (17.98) |
| da3mono_large           | 12.77  | 3.44 | 15.74 | swimthrough_02 (15.74) |
| foundationgeo_11        | 17.81  | 6.67 | 19.62 | swimthrough_02 (19.62) |

### M-3 normal deg (lower better)

| arm                     | median | min  | max  | worst clip       |
|-------------------------|--------|------|------|------------------|
| mapanything_n1          | 7.9    | 6.4  | 13.6 | cenote_01 (13.6) |
| dav2_small              | 20.8   | 17.0 | 26.8 | cenote_01 (26.8) |
| moge2_vitl              | 19.6   | 9.3  | 30.5 | cenote_01 (30.5) |
| metricanything_pointmap | 20.6   | 10.0 | 29.5 | cenote_01 (29.5) |
| wat3r_n1                | 19.9   | 10.4 | 25.5 | cenote_01 (25.5) |
| da3mono_large           | 20.6   | 18.0 | 23.8 | wreck_05 (23.8)  |
| foundationgeo_11        | 24.4   | 13.6 | 29.4 | cenote_01 (29.4) |

### M-4 boundary (lower better)

| arm                     | median | min    | max    | worst clip         |
|-------------------------|--------|--------|--------|--------------------|
| mapanything_n1          | 0.0028 | 0.0000 | 0.0391 | cenote_01 (0.0391) |
| dav2_small              | 0.0167 | 0.0128 | 0.2038 | wreck_01 (0.2038)  |
| moge2_vitl              | 0.0320 | 0.0139 | 0.0622 | cenote_01 (0.0622) |
| metricanything_pointmap | 0.0249 | 0.0139 | 0.0480 | wreck_07 (0.0480)  |
| wat3r_n1                | 0.0171 | 0.0119 | 0.0269 | wreck_01 (0.0269)  |
| da3mono_large           | 0.0285 | 0.0118 | 0.0770 | cenote_01 (0.0770) |
| foundationgeo_11        | 0.0219 | 0.0115 | 0.0323 | wreck_01 (0.0323)  |

### M-5 ordinal@25% (lower better)

| arm                     | median | min    | max    | worst clip         |
|-------------------------|--------|--------|--------|--------------------|
| mapanything_n1          | 0.0000 | 0.0000 | 0.0083 | cenote_01 (0.0083) |
| dav2_small              | 0.0057 | 0.0003 | 0.1410 | cenote_01 (0.1410) |
| moge2_vitl              | 0.0015 | 0.0000 | 0.0675 | cenote_01 (0.0675) |
| metricanything_pointmap | 0.0020 | 0.0000 | 0.0591 | cenote_01 (0.0591) |
| wat3r_n1                | 0.0057 | 0.0000 | 0.0484 | cenote_01 (0.0484) |
| da3mono_large           | 0.0037 | 0.0000 | 0.0626 | cenote_01 (0.0626) |
| foundationgeo_11        | 0.0019 | 0.0000 | 0.0164 | cenote_01 (0.0164) |

### M-6 outer/inner (1.0 flat)

| arm                     | median | min  | max  | worst clip            |
|-------------------------|--------|------|------|-----------------------|
| mapanything_n1          | 1.04   | 0.78 | 1.20 | wreck_07 (0.78)       |
| dav2_small              | 0.94   | 0.65 | 1.28 | wreck_03 (0.65)       |
| moge2_vitl              | 1.07   | 0.97 | 2.03 | wreck_07 (2.03)       |
| metricanything_pointmap | 1.08   | 0.79 | 1.41 | wreck_07 (1.41)       |
| wat3r_n1                | 0.93   | 0.59 | 1.34 | cenote_01 (0.59)      |
| da3mono_large           | 1.01   | 0.68 | 1.52 | swimthrough_02 (1.52) |
| foundationgeo_11        | 1.18   | 0.62 | 1.47 | wreck_05 (1.47)       |

## By clip — M-1 abs-rel, the most legible single dimension

| arm                     | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|-------------------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1          | 0.0708   | 0.0526   | 0.0929    | 0.0777         | 0.1689   | 0.1306   |
| dav2_small              | 0.1054   | 0.1191   | 0.1130    | 0.0965         | 0.2230   | 0.1020   |
| moge2_vitl              | 0.1725   | 0.1538   | 0.2191    | 0.0782         | 0.3166   | 0.2197   |
| metricanything_pointmap | 0.1332   | 0.1152   | 0.2150    | 0.0672         | 0.3635   | 0.1728   |
| wat3r_n1                | 0.1745   | 0.2384   | 0.1300    | 0.1175         | 0.2550   | 0.1935   |
| da3mono_large           | 0.1546   | 0.2096   | 0.0852    | 0.1021         | 0.2159   | 0.0921   |
| foundationgeo_11        | 0.1046   | 0.1161   | 0.1772    | 0.0985         | 0.2523   | 0.1109   |

Clip roles: `wreck_07` high-texture arc / favourable geometry support; `wreck_05` lower-texture lateral glide / weak geometry support; `cenote_01` widest near/far range variation; `swimthrough_02` ordinary reef / representative normal case; `wreck_01` low-texture near-planar PORTRAIT orientation (FOV/orientation trap); `wreck_03` dynamic diver / moving-object and dynamic-scene failure.

### Coverage by clip

| arm                     | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|-------------------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1          | 0.797    | 0.723    | 0.930     | 0.732          | 0.991    | 0.760    |
| dav2_small              | 0.717    | 0.668    | 0.942     | 0.751          | 0.991    | 0.771    |
| moge2_vitl              | 0.810    | 0.706    | 0.942     | 0.752          | 0.991    | 0.791    |
| metricanything_pointmap | 0.753    | 0.686    | 0.942     | 0.752          | 0.991    | 0.773    |
| wat3r_n1                | 0.816    | 0.751    | 0.942     | 0.752          | 0.562    | 0.801    |
| da3mono_large           | 0.816    | 0.751    | 0.942     | 0.752          | 0.991    | 0.801    |
| foundationgeo_11        | 0.815    | 0.678    | 0.942     | 0.752          | 0.991    | 0.797    |

## M-1 range stratification, in both required forms

**M-1a — nominal reference bins.** The edges are Week-3 reference units /
provisional nominal metres, **not** independently validated physical metres. Pre-C2
nothing may claim the reference's nominal 8 m is objectively an 8 m water path.

| arm                     | 0-1 | 1-2 | 2-3   | 3-5   | 5-8   | 8-12  | 12+   |
|-------------------------|-----|-----|-------|-------|-------|-------|-------|
| mapanything_n1          | -   | -   | 0.103 | 0.135 | 0.100 | 0.126 | 0.107 |
| dav2_small              | -   | -   | 0.487 | 0.250 | 0.134 | 0.147 | 0.124 |
| moge2_vitl              | -   | -   | 0.174 | 0.191 | 0.162 | 0.224 | 0.322 |
| metricanything_pointmap | -   | -   | 0.173 | 0.202 | 0.166 | 0.215 | 0.345 |
| wat3r_n1                | -   | -   | 0.458 | 0.314 | 0.186 | 0.183 | 0.200 |
| da3mono_large           | -   | -   | 0.540 | 0.519 | 0.227 | 0.128 | 0.143 |
| foundationgeo_11        | -   | -   | 0.154 | 0.188 | 0.240 | 0.134 | 0.168 |

**M-1b — scale-invariant near/mid/far.** Bin edges are quantiles of each clip's
pooled reference range, so this survives an absolute scale that pre-C2 may be wrong.

| arm                     | q0-20 (near) | q20-40 | q40-60 | q60-80 | q80-100 (far) |
|-------------------------|--------------|--------|--------|--------|---------------|
| mapanything_n1          | 0.091        | 0.089  | 0.121  | 0.106  | 0.104         |
| dav2_small              | 0.139        | 0.110  | 0.128  | 0.114  | 0.127         |
| moge2_vitl              | 0.135        | 0.188  | 0.173  | 0.202  | 1.196         |
| metricanything_pointmap | 0.127        | 0.143  | 0.174  | 0.140  | 0.573         |
| wat3r_n1                | 0.176        | 0.185  | 0.157  | 0.199  | 0.229         |
| da3mono_large           | 0.235        | 0.121  | 0.097  | 0.138  | 0.129         |
| foundationgeo_11        | 0.136        | 0.111  | 0.127  | 0.103  | 0.241         |

## FoundationGeo internal ablations — the only causal interventions left

Both V4b arms come from ONE forward pass and share ONE frozen (focal, shift)
solution recovered from the post-delta arm. The released `infer()` postprocesses
its two arms through INDEPENDENT `recover_focal_shift` solutions, so its
difference would be the ray correction plus two different focals — which FREEZE
§C3 explicitly forbids calling a ray-correction ablation.

```text
V4b  fg_pre_ray  ->  fg_post_ray         the learned ray-direction correction
V4c  fg_post_ray ->  foundationgeo_11    the learned per-pixel scale field
```

| arm              | role                    | M-1 abs-rel | M-2 slope b | M-3 RelNormal deg | M-3 normal deg | M-4 boundary | M-5 ordinal@25% | M-6 outer/inner |
|------------------|-------------------------|-------------|-------------|-------------------|----------------|--------------|-----------------|-----------------|
| fg_pre_ray       | V4b arm A               | 0.1135      | 1.306       | 16.26             | 21.5           | 0.0209       | 0.0017          | 1.04            |
| fg_post_ray      | V4b arm B and V4c arm C | 0.1135      | 1.306       | 16.26             | 21.5           | 0.0209       | 0.0017          | 1.04            |
| foundationgeo_11 | V4c arm D               | 0.1135      | 1.306       | 17.81             | 24.4           | 0.0219       | 0.0019          | 1.18            |

**V4b learned ray correction: fg_pre_ray -> fg_post_ray**

| dimension         | before | after  | delta   | relative |
|-------------------|--------|--------|---------|----------|
| M-1 abs-rel       | 0.1135 | 0.1135 | +0.0000 | +0.000   |
| M-2 slope b       | 1.306  | 1.306  | -0.0000 | -0.000   |
| M-3 RelNormal deg | 16.26  | 16.26  | +0.0000 | +0.000   |
| M-3 normal deg    | 21.5   | 21.5   | -0.0005 | -0.000   |
| M-4 boundary      | 0.0209 | 0.0209 | +0.0000 | +0.000   |
| M-5 ordinal@25%   | 0.0017 | 0.0017 | +0.0000 | +0.000   |
| M-6 outer/inner   | 1.04   | 1.04   | -0.0000 | -0.000   |

**V4c learned scale field: fg_post_ray -> foundationgeo_11**

| dimension         | before | after  | delta   | relative |
|-------------------|--------|--------|---------|----------|
| M-1 abs-rel       | 0.1135 | 0.1135 | -0.0000 | -0.000   |
| M-2 slope b       | 1.306  | 1.306  | +0.0001 | +0.000   |
| M-3 RelNormal deg | 16.26  | 17.81  | +1.5457 | +0.095   |
| M-3 normal deg    | 21.5   | 24.4   | +2.9535 | +0.137   |
| M-4 boundary      | 0.0209 | 0.0219 | +0.0010 | +0.049   |
| M-5 ordinal@25%   | 0.0017 | 0.0019 | +0.0002 | +0.112   |
| M-6 outer/inner   | 1.04   | 1.18   | +0.1392 | +0.134   |

Every one of these deltas clears the S1 noise floor trivially: that floor is
exactly zero for this model, bitwise, so no part of an ablation difference is
run-to-run variation.

## The nuisance parameters the alignment consumed

FREEZE §C9: the transform that bought the E1 ceiling is reported, never hidden.

| arm                     | family           | median s | s across clips   | median t | median log-residual MAD |
|-------------------------|------------------|----------|------------------|----------|-------------------------|
| mapanything_n1          | scale            | 1.026    | 0.9355-1.117     | -        | 0.1021                  |
| dav2_small              | affine_disparity | 0.02032  | 0.009059-0.03041 | 0.03224  | 0.1156                  |
| moge2_vitl              | scale            | 2.615    | 1.798-3.346      | -        | 0.2149                  |
| metricanything_pointmap | scale            | 2.545    | 1.629-3.191      | -        | 0.1887                  |
| wat3r_n1                | scale            | 16.16    | 5.136-25.18      | -        | 0.2052                  |
| da3mono_large           | affine_depth     | 6.546    | 2.843-7.952      | 5.51     | 0.1363                  |
| foundationgeo_11        | scale            | 2.106    | 0.5069-2.794     | -        | 0.1252                  |

`s` across clips is the clip-to-clip scale spread. A model whose `s` is stable
across six different scenes is carrying a real, if unverified, notion of scale; one
whose `s` swings has an oracle-only scale. Neither can be judged as CORRECT pre-C2
— there is no independent anchor — but the spread itself is measured and recorded.

## Secondary literature-continuity metrics (never decisive)

| arm                     | AbsRel | delta<1.25 | RMSE log |
|-------------------------|--------|------------|----------|
| mapanything_n1          | 0.1319 | 0.8140     | 0.1635   |
| dav2_small              | 0.1370 | 0.7948     | 0.1864   |
| moge2_vitl              | 0.5630 | 0.5144     | 0.5534   |
| metricanything_pointmap | 0.3709 | 0.5630     | 0.4200   |
| wat3r_n1                | 0.2343 | 0.5450     | 0.2859   |
| da3mono_large           | 0.1749 | 0.7584     | 0.2226   |
| foundationgeo_11        | 0.2058 | 0.7285     | 0.2611   |

Reported for continuity with the outside world. They are never used in a ranking
argument on their own (FREEZE §6).

## Field reduction

_(written against the numbers above; see `FINALISTS_PRE_C2.md` for the full chain)_
