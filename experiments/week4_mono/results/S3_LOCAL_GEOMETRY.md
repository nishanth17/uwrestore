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
| dav2_small              | 0.1761      | 0.535       | 27.50             | 36.3           | 0.1022       | 0.1172          | 0.93            | 0.786    |
| moge2_vitl              | 0.2156      | 1.211       | 27.78             | 30.3           | 0.0355       | 0.0676          | 1.01            | 0.801    |
| metricanything_pointmap | 0.1819      | 0.975       | 27.50             | 30.0           | 0.0360       | 0.0665          | 0.94            | 0.782    |
| wat3r_n1                | 0.1840      | 1.223       | 15.62             | 19.9           | 0.0171       | 0.0057          | 0.93            | 0.776    |
| da3mono_large           | 0.1283      | 0.846       | 12.77             | 20.6           | 0.0285       | 0.0037          | 1.01            | 0.808    |
| foundationgeo_11        | 0.1712      | 0.845       | 32.71             | 38.5           | 0.0423       | 0.0862          | 0.79            | 0.806    |

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
| dav2_small              | 0.1761 | 0.0990 | 0.2540 | wreck_05 (0.2540) |
| moge2_vitl              | 0.2156 | 0.1342 | 0.3111 | wreck_01 (0.3111) |
| metricanything_pointmap | 0.1819 | 0.1273 | 0.3652 | wreck_01 (0.3652) |
| wat3r_n1                | 0.1840 | 0.1175 | 0.2550 | wreck_01 (0.2550) |
| da3mono_large           | 0.1283 | 0.0852 | 0.2159 | wreck_01 (0.2159) |
| foundationgeo_11        | 0.1712 | 0.1330 | 0.2358 | wreck_01 (0.2358) |

### M-2 slope b (1.0 ideal)

| arm                     | median | min   | max   | worst clip        |
|-------------------------|--------|-------|-------|-------------------|
| mapanything_n1          | 0.950  | 0.873 | 1.018 | cenote_01 (0.873) |
| dav2_small              | 0.535  | 0.101 | 0.817 | wreck_03 (0.101)  |
| moge2_vitl              | 1.211  | 0.556 | 2.242 | wreck_05 (2.242)  |
| metricanything_pointmap | 0.975  | 0.619 | 1.653 | wreck_05 (1.653)  |
| wat3r_n1                | 1.223  | 0.953 | 1.411 | wreck_01 (1.411)  |
| da3mono_large           | 0.846  | 0.592 | 1.148 | wreck_03 (0.592)  |
| foundationgeo_11        | 0.845  | 0.485 | 1.175 | wreck_03 (0.485)  |

### M-3 RelNormal deg (lower better)

| arm                     | median | min  | max   | worst clip             |
|-------------------------|--------|------|-------|------------------------|
| mapanything_n1          | 6.84   | 2.95 | 9.81  | cenote_01 (9.81)       |
| dav2_small              | 27.50  | 4.51 | 33.28 | wreck_05 (33.28)       |
| moge2_vitl              | 27.78  | 4.37 | 33.63 | swimthrough_02 (33.63) |
| metricanything_pointmap | 27.50  | 4.17 | 33.52 | swimthrough_02 (33.52) |
| wat3r_n1                | 15.62  | 2.64 | 17.98 | swimthrough_02 (17.98) |
| da3mono_large           | 12.77  | 3.44 | 15.74 | swimthrough_02 (15.74) |
| foundationgeo_11        | 32.71  | 7.22 | 36.30 | swimthrough_02 (36.30) |

### M-3 normal deg (lower better)

| arm                     | median | min  | max  | worst clip            |
|-------------------------|--------|------|------|-----------------------|
| mapanything_n1          | 7.9    | 6.4  | 13.6 | cenote_01 (13.6)      |
| dav2_small              | 36.3   | 20.7 | 47.8 | swimthrough_02 (47.8) |
| moge2_vitl              | 30.3   | 11.4 | 40.5 | swimthrough_02 (40.5) |
| metricanything_pointmap | 30.0   | 11.5 | 41.7 | swimthrough_02 (41.7) |
| wat3r_n1                | 19.9   | 10.4 | 25.5 | cenote_01 (25.5)      |
| da3mono_large           | 20.6   | 18.0 | 23.8 | wreck_05 (23.8)       |
| foundationgeo_11        | 38.5   | 12.8 | 47.2 | swimthrough_02 (47.2) |

### M-4 boundary (lower better)

| arm                     | median | min    | max    | worst clip         |
|-------------------------|--------|--------|--------|--------------------|
| mapanything_n1          | 0.0028 | 0.0000 | 0.0391 | cenote_01 (0.0391) |
| dav2_small              | 0.1022 | 0.0454 | 0.2749 | wreck_01 (0.2749)  |
| moge2_vitl              | 0.0355 | 0.0056 | 0.0724 | cenote_01 (0.0724) |
| metricanything_pointmap | 0.0360 | 0.0028 | 0.0891 | cenote_01 (0.0891) |
| wat3r_n1                | 0.0171 | 0.0119 | 0.0269 | wreck_01 (0.0269)  |
| da3mono_large           | 0.0285 | 0.0118 | 0.0770 | cenote_01 (0.0770) |
| foundationgeo_11        | 0.0423 | 0.0085 | 0.0624 | wreck_07 (0.0624)  |

### M-5 ordinal@25% (lower better)

| arm                     | median | min    | max    | worst clip         |
|-------------------------|--------|--------|--------|--------------------|
| mapanything_n1          | 0.0000 | 0.0000 | 0.0083 | cenote_01 (0.0083) |
| dav2_small              | 0.1172 | 0.0002 | 0.3223 | wreck_03 (0.3223)  |
| moge2_vitl              | 0.0676 | 0.0013 | 0.1687 | wreck_03 (0.1687)  |
| metricanything_pointmap | 0.0665 | 0.0000 | 0.1819 | wreck_03 (0.1819)  |
| wat3r_n1                | 0.0057 | 0.0000 | 0.0484 | cenote_01 (0.0484) |
| da3mono_large           | 0.0037 | 0.0000 | 0.0626 | cenote_01 (0.0626) |
| foundationgeo_11        | 0.0862 | 0.0000 | 0.2408 | wreck_03 (0.2408)  |

### M-6 outer/inner (1.0 flat)

| arm                     | median | min  | max  | worst clip            |
|-------------------------|--------|------|------|-----------------------|
| mapanything_n1          | 1.04   | 0.78 | 1.20 | wreck_07 (0.78)       |
| dav2_small              | 0.93   | 0.65 | 1.30 | wreck_03 (0.65)       |
| moge2_vitl              | 1.01   | 0.53 | 1.15 | swimthrough_02 (0.53) |
| metricanything_pointmap | 0.94   | 0.55 | 1.20 | swimthrough_02 (0.55) |
| wat3r_n1                | 0.93   | 0.59 | 1.34 | cenote_01 (0.59)      |
| da3mono_large           | 1.01   | 0.68 | 1.52 | swimthrough_02 (1.52) |
| foundationgeo_11        | 0.79   | 0.54 | 1.01 | swimthrough_02 (0.54) |

## By clip — M-1 abs-rel, the most legible single dimension

| arm                     | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|-------------------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1          | 0.0708   | 0.0526   | 0.0929    | 0.0777         | 0.1689   | 0.1306   |
| dav2_small              | 0.1880   | 0.2540   | 0.0990    | 0.1642         | 0.2260   | 0.1359   |
| moge2_vitl              | 0.1756   | 0.2285   | 0.2027    | 0.1342         | 0.3111   | 0.2720   |
| metricanything_pointmap | 0.1569   | 0.1569   | 0.2070    | 0.1273         | 0.3652   | 0.2351   |
| wat3r_n1                | 0.1745   | 0.2384   | 0.1300    | 0.1175         | 0.2550   | 0.1935   |
| da3mono_large           | 0.1546   | 0.2096   | 0.0852    | 0.1021         | 0.2159   | 0.0921   |
| foundationgeo_11        | 0.1330   | 0.2067   | 0.1763    | 0.1661         | 0.2358   | 0.1566   |

Clip roles: `wreck_07` high-texture arc / favourable geometry support; `wreck_05` lower-texture lateral glide / weak geometry support; `cenote_01` widest near/far range variation; `swimthrough_02` ordinary reef / representative normal case; `wreck_01` low-texture near-planar PORTRAIT orientation (FOV/orientation trap); `wreck_03` dynamic diver / moving-object and dynamic-scene failure.

### Coverage by clip

| arm                     | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|-------------------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1          | 0.797    | 0.723    | 0.930     | 0.732          | 0.991    | 0.760    |
| dav2_small              | 0.801    | 0.621    | 0.942     | 0.711          | 0.991    | 0.770    |
| moge2_vitl              | 0.816    | 0.695    | 0.942     | 0.752          | 0.991    | 0.786    |
| metricanything_pointmap | 0.781    | 0.664    | 0.942     | 0.744          | 0.991    | 0.784    |
| wat3r_n1                | 0.816    | 0.751    | 0.942     | 0.752          | 0.562    | 0.801    |
| da3mono_large           | 0.816    | 0.751    | 0.942     | 0.752          | 0.991    | 0.801    |
| foundationgeo_11        | 0.815    | 0.638    | 0.942     | 0.749          | 0.991    | 0.797    |

## M-1 range stratification, in both required forms

**M-1a — nominal reference bins.** The edges are Week-3 reference units /
provisional nominal metres, **not** independently validated physical metres. Pre-C2
nothing may claim the reference's nominal 8 m is objectively an 8 m water path.

| arm                     | 0-1 | 1-2 | 2-3   | 3-5   | 5-8   | 8-12  | 12+   |
|-------------------------|-----|-----|-------|-------|-------|-------|-------|
| mapanything_n1          | -   | -   | 0.103 | 0.135 | 0.100 | 0.126 | 0.107 |
| dav2_small              | -   | -   | 0.468 | 0.298 | 0.209 | 0.178 | 0.291 |
| moge2_vitl              | -   | -   | 0.250 | 0.260 | 0.187 | 0.206 | 0.318 |
| metricanything_pointmap | -   | -   | 0.210 | 0.314 | 0.188 | 0.199 | 0.341 |
| wat3r_n1                | -   | -   | 0.458 | 0.314 | 0.186 | 0.183 | 0.200 |
| da3mono_large           | -   | -   | 0.540 | 0.519 | 0.227 | 0.128 | 0.143 |
| foundationgeo_11        | -   | -   | 0.121 | 0.203 | 0.166 | 0.146 | 0.271 |

**M-1b — scale-invariant near/mid/far.** Bin edges are quantiles of each clip's
pooled reference range, so this survives an absolute scale that pre-C2 may be wrong.

| arm                     | q0-20 (near) | q20-40 | q40-60 | q60-80 | q80-100 (far) |
|-------------------------|--------------|--------|--------|--------|---------------|
| mapanything_n1          | 0.091        | 0.089  | 0.121  | 0.106  | 0.104         |
| dav2_small              | 0.212        | 0.113  | 0.135  | 0.171  | 0.333         |
| moge2_vitl              | 0.157        | 0.197  | 0.226  | 0.255  | 1.098         |
| metricanything_pointmap | 0.143        | 0.146  | 0.172  | 0.211  | 0.682         |
| wat3r_n1                | 0.176        | 0.185  | 0.157  | 0.199  | 0.229         |
| da3mono_large           | 0.235        | 0.121  | 0.097  | 0.138  | 0.129         |
| foundationgeo_11        | 0.136        | 0.138  | 0.181  | 0.234  | 0.336         |

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
| fg_pre_ray       | V4b arm A               | 0.1596      | 0.834       | 32.15             | 36.3           | 0.0433       | 0.0863          | 0.81            |
| fg_post_ray      | V4b arm B and V4c arm C | 0.1596      | 0.834       | 32.15             | 36.3           | 0.0433       | 0.0863          | 0.81            |
| foundationgeo_11 | V4c arm D               | 0.1712      | 0.845       | 32.71             | 38.5           | 0.0423       | 0.0862          | 0.79            |

**V4b learned ray correction: fg_pre_ray -> fg_post_ray**

| dimension         | before | after  | delta   | relative |
|-------------------|--------|--------|---------|----------|
| M-1 abs-rel       | 0.1596 | 0.1596 | +0.0000 | +0.000   |
| M-2 slope b       | 0.834  | 0.834  | -0.0000 | -0.000   |
| M-3 RelNormal deg | 32.15  | 32.15  | -0.0000 | -0.000   |
| M-3 normal deg    | 36.3   | 36.3   | -0.0004 | -0.000   |
| M-4 boundary      | 0.0433 | 0.0433 | +0.0000 | +0.000   |
| M-5 ordinal@25%   | 0.0863 | 0.0863 | +0.0000 | +0.000   |
| M-6 outer/inner   | 0.81   | 0.81   | +0.0000 | +0.000   |

**V4c learned scale field: fg_post_ray -> foundationgeo_11**

| dimension         | before | after  | delta   | relative |
|-------------------|--------|--------|---------|----------|
| M-1 abs-rel       | 0.1596 | 0.1712 | +0.0116 | +0.073   |
| M-2 slope b       | 0.834  | 0.845  | +0.0108 | +0.013   |
| M-3 RelNormal deg | 32.15  | 32.71  | +0.5672 | +0.018   |
| M-3 normal deg    | 36.3   | 38.5   | +2.2078 | +0.061   |
| M-4 boundary      | 0.0433 | 0.0423 | -0.0011 | -0.024   |
| M-5 ordinal@25%   | 0.0863 | 0.0862 | -0.0001 | -0.002   |
| M-6 outer/inner   | 0.81   | 0.79   | -0.0123 | -0.015   |

Every one of these deltas clears the S1 noise floor trivially: that floor is
exactly zero for this model, bitwise, so no part of an ablation difference is
run-to-run variation.

## The nuisance parameters the alignment consumed

FREEZE §C9: the transform that bought the E1 ceiling is reported, never hidden.

| arm                     | family           | median s | s across clips   | median t | median log-residual MAD |
|-------------------------|------------------|----------|------------------|----------|-------------------------|
| mapanything_n1          | scale            | 1.026    | 0.9355-1.117     | -        | 0.1021                  |
| dav2_small              | affine_disparity | 0.01911  | 0.006448-0.03878 | 0.04867  | 0.1741                  |
| moge2_vitl              | scale            | 2.768    | 1.891-3.048      | -        | 0.2309                  |
| metricanything_pointmap | scale            | 2.686    | 1.696-2.996      | -        | 0.1982                  |
| wat3r_n1                | scale            | 16.16    | 5.136-25.18      | -        | 0.2052                  |
| da3mono_large           | affine_depth     | 6.546    | 2.843-7.952      | 5.51     | 0.1363                  |
| foundationgeo_11        | scale            | 2.211    | 0.5534-2.509     | -        | 0.1889                  |

`s` across clips is the clip-to-clip scale spread. A model whose `s` is stable
across six different scenes is carrying a real, if unverified, notion of scale; one
whose `s` swings has an oracle-only scale. Neither can be judged as CORRECT pre-C2
— there is no independent anchor — but the spread itself is measured and recorded.

## Secondary literature-continuity metrics (never decisive)

| arm                     | AbsRel | delta<1.25 | RMSE log |
|-------------------------|--------|------------|----------|
| mapanything_n1          | 0.1319 | 0.8140     | 0.1635   |
| dav2_small              | 0.2567 | 0.6033     | 0.3337   |
| moge2_vitl              | 0.7085 | 0.4879     | 0.6102   |
| metricanything_pointmap | 0.4730 | 0.5562     | 0.5103   |
| wat3r_n1                | 0.2343 | 0.5450     | 0.2859   |
| da3mono_large           | 0.1749 | 0.7584     | 0.2226   |
| foundationgeo_11        | 0.2779 | 0.5678     | 0.4097   |

Reported for continuity with the outside world. They are never used in a ranking
argument on their own (FREEZE §6).

## Field reduction

**7 -> 4.** No weighted master score is used, and none is possible: the six
dimensions disagree about the ordering, which is the reason FREEZE §6 forbids
collapsing them. Each exit below names the dimension and the number that decided
it, and each is checked against the full spread of the frozen set rather than a
favourable clip.

### The confound that has to be stated before any ranking is read

`mapanything_n1` leads every one of the six dimensions, several by a factor of
two or more (M-3 RelNormal 6.84 deg against 12.77 deg for the next arm; M-5
ordinal violations 0.0000 against 0.0037; M-4 boundary 0.0028 against 0.0171).
**The reference is MapAnything run multi-view.** Agreement between a model and
its own architecture's multi-view solution is weaker evidence than the same
agreement from an independent architecture, because the two share inductive
biases and therefore share systematic errors — and a shared systematic error is
invisible to a disagreement metric. Pre-C2 there is no independent anchor that
can separate "this arm has better geometry" from "this arm has the same errors
as the reference". It advances as a finalist because the whole point of the
Week-4 fallback question is whether the SAME architecture retains usable geometry
at N=1; it does not advance as the objective best, and S6 must not read it that
way.

### Eliminated at S3

**`dav2_small` — structure, on M-4 and M-2.** Boundary localisation 0.1022 is
roughly 3x the next-worst arm (0.0360) and 36x the leader, worst on the portrait
clip at 0.2749. Its M-2 slope of 0.535 (falling to 0.101 on `wreck_03`) is severe
near/far compression: the relationship between predicted and reference range is
not close to proportional anywhere in the set. Structural failure at boundaries
is exactly what a backscatter/attenuation stage propagates into visible haloes,
so this is not a dimension the project can trade away. It also carries the widest
within-clip scale wander measured in S2 (17.4). Its cheapness is real — 0.2 s per
frame against 1.8-2.5 s for the point-map models — but not at this cost.

**`foundationgeo_11` — shape, on M-3 and M-6.** The worst surface orientation in
the field on both forms (RelNormal 32.71 deg, absolute normal 38.5 deg, worst
clip 47.2 deg), and the worst radial signature (M-6 0.79, i.e. error at the frame
edge systematically **lower** than at the centre by 21 %, reaching 0.54 on
`swimthrough_02`). A systematic radial term on a wide-FOV underwater camera is
the specific failure M-6 exists to catch. Its S2 scale is also the least
consistent of any metric claimant (0.55-2.51 across six scenes): a scene-dependent
scale is worse for this project than a uniformly wrong one, because only a
constant is absorbable by `b -> b/s`.

**`moge2_vitl` — far field, on M-1b, and it loses its own V5 comparison.** The
scale-invariant far quintile is **1.098** — a median relative range error above
100 % in exactly the band where the water path is longest and where attenuation
inversion is most sensitive. `metricanything_pointmap`, the same architecture
with heterogeneous metric fine-tuning, reaches 0.682 in that band with better M-1
(0.182 vs 0.216) and a far better M-2 (0.975 vs 1.211). V5's question is answered
here and the answer is that the fine-tune helps; carrying both forward would be
carrying the control past the point where it controls anything.

### The two FoundationGeo interventions, measured causally

**V4b (learned ray correction) is null on this footage.** Every one of the six
dimensions moves by less than the printing precision. That is not a measurement
artefact and it is not the arms being the same data — the two point maps differ,
with a mean relative difference of 1.1e-03 in the 3-vector. The mechanism is
visible in the raw fields: the correction turns each ray by a median of **0.044
deg** (p99 0.21 deg, max 0.78 deg) against its own 3 deg cap, and rotating a ray
changes its direction while leaving its length almost untouched — the induced
change in **range** is a median relative **2.3e-07** (p99 3.8e-06). Since this
project consumes range, not bearing, V4b is irrelevant to it by construction. The
0.044 deg figure is itself the finding: the learned delta is barely using the
capacity it was given.

**V4c (learned per-pixel scale field) makes agreement worse, not better.**
Applying it costs +7.3 % on M-1 (0.1596 -> 0.1712), +6.1 % on absolute normal
error and +1.8 % on RelNormal, buying back only -2.4 % on M-4 and -1.5 % on M-6.
The field is also barely per-pixel: median 0.840 with a p01-p99 span of
0.803-0.872, i.e. a global 0.84 scalar carrying a +-4 % spatial ripple. Because
the E1 policy already grants a clip-level scale, that global part is absorbed by
the alignment and what remains to be scored is the ripple — and the ripple is a
net loss on the dimensions that matter most here. Both ablation deltas clear the
S1 noise floor trivially, that floor being exactly zero, bitwise.

### Advancing to S4

| arm | why it advances | what it must survive |
|---|---|---|
| `mapanything_n1` | leads all six dimensions; the N=1 form of the Week-3 pipeline, which is the fallback question itself | the family-affinity confound above; it must show appearance and temporal robustness that does not simply mirror the reference's |
| `da3mono_large` | strongest arm independent of the reference architecture: 2nd on M-1 (0.128), 2nd on M-3 RelNormal (12.77 deg), M-5 0.0037, M-6 1.01 (flattest radial signature in the field), best coverage (0.808), and the flattest far-field profile on M-1b | relative-only, so it brings no scale at all; its near quintile (0.235) is its own worst band, and near-field error drives the backscatter term |
| `wat3r_n1` | the underwater-specialisation control, and it earns its place on structure: M-4 0.0171 and M-5 0.0057, both 2nd best, with the 2nd flattest far field (0.229) | it loses **44 % of the portrait frame** (coverage 0.562 on `wreck_01` against 0.99 for everyone else), and S2 measured its scale at 5.2-28.2x across six scenes — an oracle-only scale, not a metric one |
| `metricanything_pointmap` | best of the metric-claimed point-map models on M-1, M-2 and far field; keeps a metric claim in the field that is not the reference's own architecture | far quintile 0.682 is still a large error in the band that matters most for attenuation inversion, and M-1 0.365 on the portrait clip is the worst single value in the surviving set |

The field deliberately keeps four different *kinds* of arm — the reference's own
architecture at N=1, an independent relative-depth model, an underwater-specialised
point-map model, and a metric-claimed point-map model — rather than the four best
numbers. A reduction that kept only the top four M-1 values would have discarded
every architecture that could disagree with the reference for an interesting reason.

See `FINALISTS_PRE_C2.md` for the full chain.
