# S4 — appearance invariance

**Stage:** S4. Only S3 survivors run.

Same underlying image geometry, different appearance, measure the geometry
response. Every perturbation is a per-pixel intensity operation applied in LINEAR
light and re-encoded to 8-bit sRGB; nothing is warped, resampled or cropped, so the
scene geometry behind the image is identical by construction.

Frames: a CONTIGUOUS window of 16 frames from each clip's middle. S4 has
to be able to see frame-to-frame scale drift, and a strided sample would destroy
exactly that structure.

**Each perturbed field is compared against the SAME model's baseline field**, not
against the Week-3 reference. That isolates the response to appearance from the
model's standing disagreement with the reference, and means the answer does not
inherit the reference's own uncertainty.

## The frozen perturbations

| perturbation               | kind         | what it probes                                                                                                                                                                          |
|----------------------------|--------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| wb_warm                    | channel_gain | white balance pushed warm; a pure per-channel gain in linear light                                                                                                                      |
| wb_cool                    | channel_gain | white balance pushed cool, the opposite gain                                                                                                                                            |
| channel_neutralize         | gray_world   | channel neutralisation: each linear channel scaled to a common mean, i.e. the colour cast removed the way the project's gray-world baseline does                                        |
| attenuation_red            | channel_gain | stronger Beer-Lambert-like red loss, uniform over the frame so it changes appearance WITHOUT encoding depth                                                                             |
| contrast_low               | contrast     | contrast reduced about the frame's linear mean                                                                                                                                          |
| contrast_high              | contrast     | contrast increased about the frame's linear mean                                                                                                                                        |
| brightness_down            | gain         | exposure down; a pure scalar on linear radiance                                                                                                                                         |
| brightness_up              | gain         | exposure up                                                                                                                                                                             |
| veil_uniform               | veil         | uniform veiling light: x -> t*x + (1-t)*A. Haze-LIKE appearance with NO depth dependence, so the geometry cue is unchanged                                                              |
| hotspot                    | hotspot      | artificial dive light: a bright radial falloff added in linear light, the illumination structure a torch or video light produces                                                        |
| cue_conflict_inverted_veil | veil_depth   | CUE CONFLICT: veil strength runs OPPOSITE to the reference depth, so the image says 'far' where the geometry says 'near'. The reference builds the stimulus and never reaches the model |
| veil_depth_consistent      | veil_depth   | the CONTROL for the cue-conflict case: the same veil magnitude applied in the physically correct direction                                                                              |

The last two are a matched pair. `cue_conflict_inverted_veil` builds a veiling
light whose strength runs OPPOSITE to the reference depth, so the image says "far"
exactly where the geometry says "near"; `veil_depth_consistent` applies the same
veil magnitude in the physically correct direction. The reference is used to BUILD
THE STIMULUS and never reaches the model, which still sees one ordinary 8-bit image.

## The three-way decomposition

```text
CONSTANT GLOBAL SCALE BIAS      d' = s d, s fixed over the clip
    Potentially a BENIGN GAUGE: refit beta' = beta/s once. Week 3 verified that
    identity numerically to floating-point precision. Do NOT judge a model
    harshly for a fixed scale gauge.

FRAME-VARYING GLOBAL SCALE DRIFT   d'_t = s_t d_t
    A FAILURE under one shared clip-level physical model: absorbing it would
    demand beta'_t = beta/s_t, i.e. water properties that change with the estimator.

LOCAL RANGE DEFORMATION
    Spatially varying within the image. NOT absorbable by any global physical
    parameter transformation. The primary geometric failure.
```

### 1. Constant global scale bias — sigma (1.000 = no change)

| perturbation               | mapanything_n1 | metricanything_pointmap | wat3r_n1 | da3mono_large |
|----------------------------|----------------|-------------------------|----------|---------------|
| wb_warm                    | 1.0158         | 0.9730                  | 0.9925   | 0.9930        |
| wb_cool                    | 0.9773         | 1.0210                  | 1.0100   | 1.0101        |
| channel_neutralize         | 1.0817         | 0.8735                  | 1.0085   | 1.0088        |
| attenuation_red            | 0.9601         | 1.0486                  | 1.0012   | 0.9994        |
| contrast_low               | 0.9572         | 1.0403                  | 0.9978   | 1.0006        |
| contrast_high              | 0.8860         | 0.8931                  | 0.9884   | 0.9701        |
| brightness_down            | 0.9906         | 1.0128                  | 0.9995   | 0.9897        |
| brightness_up              | 1.0139         | 0.9897                  | 0.9994   | 1.0224        |
| veil_uniform               | 1.4156         | 1.2121                  | 1.0219   | 1.0941        |
| hotspot                    | 1.1611         | 0.9602                  | 0.9907   | 1.0608        |
| cue_conflict_inverted_veil | 1.0898         | 0.9830                  | 1.0233   | 1.1163        |
| veil_depth_consistent      | 1.2875         | 1.3172                  | 0.9474   | 1.0581        |

### 2. Frame-varying scale drift — wander ratio (1.000 = the bias is constant)

| perturbation               | mapanything_n1 | metricanything_pointmap | wat3r_n1 | da3mono_large |
|----------------------------|----------------|-------------------------|----------|---------------|
| wb_warm                    | 1.1119         | 1.0884                  | 1.0404   | 1.0148        |
| wb_cool                    | 1.0745         | 1.0756                  | 1.0365   | 1.0177        |
| channel_neutralize         | 1.6159         | 1.3116                  | 1.2183   | 1.0820        |
| attenuation_red            | 1.1108         | 1.1440                  | 1.0386   | 1.0217        |
| contrast_low               | 1.1534         | 1.1523                  | 1.0466   | 1.0385        |
| contrast_high              | 1.3513         | 1.2964                  | 1.1068   | 1.0938        |
| brightness_down            | 1.0617         | 1.0611                  | 1.0297   | 1.0185        |
| brightness_up              | 1.0884         | 1.0731                  | 1.0496   | 1.0248        |
| veil_uniform               | 1.3770         | 1.4037                  | 1.0730   | 1.1099        |
| hotspot                    | 1.2395         | 1.2684                  | 1.0783   | 1.0487        |
| cue_conflict_inverted_veil | 1.5141         | 1.8709                  | 1.1369   | 1.2951        |
| veil_depth_consistent      | 1.4684         | 1.4033                  | 1.1881   | 1.1000        |

Wander is max/min of the per-frame sigma within the window. This is the row that
matters more than row 1: a constant bias is a gauge, a wandering one is not.

### 3. Local range deformation — median |delta log range| after removing sigma_t

| perturbation               | mapanything_n1 | metricanything_pointmap | wat3r_n1 | da3mono_large |
|----------------------------|----------------|-------------------------|----------|---------------|
| wb_warm                    | 0.0079         | 0.0046                  | 0.0070   | 0.0074        |
| wb_cool                    | 0.0079         | 0.0041                  | 0.0065   | 0.0075        |
| channel_neutralize         | 0.0619         | 0.0283                  | 0.0401   | 0.0391        |
| attenuation_red            | 0.0124         | 0.0074                  | 0.0093   | 0.0096        |
| contrast_low               | 0.0155         | 0.0116                  | 0.0147   | 0.0212        |
| contrast_high              | 0.0367         | 0.0287                  | 0.0366   | 0.0422        |
| brightness_down            | 0.0048         | 0.0028                  | 0.0052   | 0.0049        |
| brightness_up              | 0.0081         | 0.0034                  | 0.0068   | 0.0050        |
| veil_uniform               | 0.0327         | 0.0759                  | 0.0552   | 0.1289        |
| hotspot                    | 0.0383         | 0.0259                  | 0.0570   | 0.0525        |
| cue_conflict_inverted_veil | 0.0578         | 0.1107                  | 0.1072   | 0.2487        |
| veil_depth_consistent      | 0.0245         | 0.0742                  | 0.0550   | 0.0567        |

This is the number no argument can remove. `0.010` is about a 1 % local range
deformation; Week 3's restoration sensitivity budget is 31 % at 1 m, 12 % at 3 m and
8.5 % at 8 m, so these can be read against that budget under the current provisional
scale hypothesis — but not as an objective physical-metre acceptance test, which
waits for C2.

### 3b. Local range deformation — p95, the tail rather than the median

| perturbation               | mapanything_n1 | metricanything_pointmap | wat3r_n1 | da3mono_large |
|----------------------------|----------------|-------------------------|----------|---------------|
| wb_warm                    | 0.0288         | 0.0252                  | 0.0302   | 0.0289        |
| wb_cool                    | 0.0340         | 0.0280                  | 0.0278   | 0.0330        |
| channel_neutralize         | 0.2852         | 0.1413                  | 0.1429   | 0.1220        |
| attenuation_red            | 0.0514         | 0.0369                  | 0.0453   | 0.0412        |
| contrast_low               | 0.0888         | 0.0612                  | 0.0762   | 0.0682        |
| contrast_high              | 0.1673         | 0.1465                  | 0.2048   | 0.1755        |
| brightness_down            | 0.0255         | 0.0191                  | 0.0271   | 0.0321        |
| brightness_up              | 0.0411         | 0.0360                  | 0.0379   | 0.0461        |
| veil_uniform               | 0.2011         | 0.2440                  | 0.2163   | 0.3875        |
| hotspot                    | 0.1522         | 0.2112                  | 0.1816   | 0.1859        |
| cue_conflict_inverted_veil | 0.4063         | 0.3855                  | 0.4143   | 0.6661        |
| veil_depth_consistent      | 0.1222         | 0.2669                  | 0.2178   | 0.2743        |

### 3c. Local range deformation in PHYSICAL RANGE — the cross-model row

Rows 3 and 3b are in each model's OWN NATIVE quantity. That is the right object
for asking "did appearance move this model", but it is NOT comparable across
models. For a scale-family arm native is proportional to range, so a native log
ratio IS a range log ratio and this table repeats row 3 exactly. For an
AFFINE-family arm range is `s*d + t`, and the two differ by

```text
    L_phys  ~=  L_native * (1 - t/r)
```

`da3mono_large` is the only survivor with an affine family, and its fitted shift
is large (t = 1.78 to 11.56 m against median scene ranges of 6.4 to 22.5 m), so
reading its native numbers beside three scale-family arms overstates its response
by roughly a factor of two. The gauge here is fitted on the BASELINE arm alone and
then held fixed, so no oracle sees a perturbed field: this is a unit conversion,
not an alignment that could absorb the effect being measured.

| perturbation               | mapanything_n1 | metricanything_pointmap | wat3r_n1 | da3mono_large |
|----------------------------|----------------|-------------------------|----------|---------------|
| wb_warm                    | 0.0079         | 0.0046                  | 0.0070   | 0.0035        |
| wb_cool                    | 0.0079         | 0.0041                  | 0.0065   | 0.0035        |
| channel_neutralize         | 0.0619         | 0.0283                  | 0.0401   | 0.0171        |
| attenuation_red            | 0.0124         | 0.0074                  | 0.0093   | 0.0041        |
| contrast_low               | 0.0155         | 0.0116                  | 0.0147   | 0.0083        |
| contrast_high              | 0.0367         | 0.0287                  | 0.0366   | 0.0162        |
| brightness_down            | 0.0048         | 0.0028                  | 0.0052   | 0.0022        |
| brightness_up              | 0.0081         | 0.0034                  | 0.0068   | 0.0034        |
| veil_uniform               | 0.0327         | 0.0759                  | 0.0552   | 0.0598        |
| hotspot                    | 0.0383         | 0.0259                  | 0.0570   | 0.0218        |
| cue_conflict_inverted_veil | 0.0578         | 0.1107                  | 0.1072   | 0.1128        |
| veil_depth_consistent      | 0.0245         | 0.0742                  | 0.0550   | 0.0283        |

p95, physical range:

| perturbation               | mapanything_n1 | metricanything_pointmap | wat3r_n1 | da3mono_large |
|----------------------------|----------------|-------------------------|----------|---------------|
| wb_warm                    | 0.0288         | 0.0252                  | 0.0302   | 0.0193        |
| wb_cool                    | 0.0340         | 0.0280                  | 0.0278   | 0.0231        |
| channel_neutralize         | 0.2852         | 0.1413                  | 0.1429   | 0.0905        |
| attenuation_red            | 0.0514         | 0.0369                  | 0.0453   | 0.0306        |
| contrast_low               | 0.0888         | 0.0612                  | 0.0762   | 0.0465        |
| contrast_high              | 0.1673         | 0.1465                  | 0.2048   | 0.1085        |
| brightness_down            | 0.0255         | 0.0191                  | 0.0271   | 0.0183        |
| brightness_up              | 0.0411         | 0.0360                  | 0.0379   | 0.0405        |
| veil_uniform               | 0.2011         | 0.2440                  | 0.2163   | 0.2353        |
| hotspot                    | 0.1522         | 0.2112                  | 0.1816   | 0.1010        |
| cue_conflict_inverted_veil | 0.4063         | 0.3855                  | 0.4143   | 0.3953        |
| veil_depth_consistent      | 0.1222         | 0.2669                  | 0.2178   | 0.1901        |

That the scale-family columns reproduce row 3 to four decimals is the check that
this conversion is implemented correctly.

### 4. Validity — does the perturbation make the model stop predicting?

| perturbation               | mapanything_n1 | metricanything_pointmap | wat3r_n1     | da3mono_large |
|----------------------------|----------------|-------------------------|--------------|---------------|
| wb_warm                    | 0.774->0.775   | 0.771->0.776            | 0.782->0.782 | 0.803->0.803  |
| wb_cool                    | 0.774->0.762   | 0.771->0.770            | 0.782->0.782 | 0.803->0.803  |
| channel_neutralize         | 0.774->0.785   | 0.771->0.781            | 0.782->0.782 | 0.803->0.803  |
| attenuation_red            | 0.774->0.765   | 0.771->0.771            | 0.782->0.782 | 0.803->0.803  |
| contrast_low               | 0.774->0.752   | 0.771->0.770            | 0.782->0.782 | 0.803->0.803  |
| contrast_high              | 0.774->0.756   | 0.771->0.766            | 0.782->0.782 | 0.803->0.803  |
| brightness_down            | 0.774->0.769   | 0.771->0.773            | 0.782->0.782 | 0.803->0.803  |
| brightness_up              | 0.774->0.771   | 0.771->0.778            | 0.782->0.782 | 0.803->0.803  |
| veil_uniform               | 0.774->0.777   | 0.771->0.770            | 0.782->0.782 | 0.803->0.803  |
| hotspot                    | 0.774->0.751   | 0.771->0.758            | 0.782->0.782 | 0.803->0.803  |
| cue_conflict_inverted_veil | 0.774->0.782   | 0.771->0.781            | 0.782->0.782 | 0.803->0.803  |
| veil_depth_consistent      | 0.774->0.758   | 0.771->0.776            | 0.782->0.782 | 0.803->0.803  |

### 5. Boundary jitter under perturbation (evaluation-grid pixels)

| perturbation               | mapanything_n1 | metricanything_pointmap | wat3r_n1 | da3mono_large |
|----------------------------|----------------|-------------------------|----------|---------------|
| wb_warm                    | 0.00           | 0.00                    | 0.00     | 0.00          |
| wb_cool                    | 0.00           | 0.00                    | 0.00     | 0.00          |
| channel_neutralize         | 0.75           | 0.00                    | 0.00     | 0.00          |
| attenuation_red            | 0.00           | 0.00                    | 0.00     | 0.00          |
| contrast_low               | 0.38           | 0.00                    | 0.00     | 0.00          |
| contrast_high              | 2.28           | 0.00                    | 0.00     | 0.00          |
| brightness_down            | 0.00           | 0.00                    | 0.00     | 0.00          |
| brightness_up              | 0.00           | 0.00                    | 0.00     | 0.00          |
| veil_uniform               | 1.21           | 0.00                    | 0.00     | 0.00          |
| hotspot                    | 1.52           | 0.00                    | 0.00     | 0.00          |
| cue_conflict_inverted_veil | 3.05           | 0.00                    | 0.00     | 0.00          |
| veil_depth_consistent      | 1.00           | 0.00                    | 0.00     | 0.00          |

## Worst clip per model, on the dimension that matters most

| model                   | perturbation               | worst clip | local deformation |
|-------------------------|----------------------------|------------|-------------------|
| da3mono_large           | cue_conflict_inverted_veil | wreck_07   | 0.3567            |
| wat3r_n1                | cue_conflict_inverted_veil | wreck_07   | 0.2738            |
| da3mono_large           | veil_uniform               | wreck_07   | 0.2636            |
| metricanything_pointmap | cue_conflict_inverted_veil | cenote_01  | 0.2365            |
| wat3r_n1                | veil_uniform               | wreck_07   | 0.2291            |
| mapanything_n1          | cue_conflict_inverted_veil | cenote_01  | 0.1890            |
| da3mono_large           | veil_depth_consistent      | wreck_03   | 0.1508            |
| metricanything_pointmap | veil_uniform               | cenote_01  | 0.1500            |
| wat3r_n1                | veil_depth_consistent      | wreck_07   | 0.1428            |
| da3mono_large           | contrast_high              | wreck_03   | 0.1239            |
| mapanything_n1          | channel_neutralize         | wreck_05   | 0.1161            |
| wat3r_n1                | contrast_high              | wreck_07   | 0.1094            |
| metricanything_pointmap | veil_depth_consistent      | cenote_01  | 0.1026            |
| mapanything_n1          | veil_uniform               | wreck_07   | 0.0993            |
| metricanything_pointmap | contrast_high              | wreck_03   | 0.0976            |

## Findings

### 0. Two defects in this stage, found and fixed before the conclusions were drawn

**(a) The cue conflict was measuring its own control.** The first S4 pass produced
`cue_conflict_inverted_veil` and `veil_depth_consistent` as bit-identical stimuli.
Each arm expressed its direction TWICE — swapped `t_near`/`t_far` AND an `invert`
flag — so the double negation cancelled. Caught because the two arms agreed to four
decimals on every model and every clip, which is not something two different stimuli
do. `invert` is now removed from `perturb.py` so direction is stated once, by the
endpoints; the arm was regenerated (96 frames changed, the other 11 arms
byte-identical by hash) and re-inferred on the four survivors. Two tests added:
pairwise, no two arms may be the same stimulus; and on the stimulus itself, the
control must veil the FAR field and the conflict the NEAR.

Had it survived, every model would have scored identically on the conflict and its
control and the flattering conclusion would have been "nothing is fooled by
depth-inconsistent haze."

**(b) The cross-model table was comparing different units.** Rows 3/3b are in each
model's own native quantity. Three survivors are scale-family, where native is
proportional to range, so their native and physical numbers are identical. But
`da3mono_large` is `affine_depth`, where range is `s*d + t`, and its fitted shift is
large — `t` = 1.78 to 11.56 m against median scene ranges of 6.4 to 22.5 m. Its
native log-ratios are therefore inflated by about `1/(1 - t/r)` ~ 2x relative to the
same response measured in range.

Row 3c is the fix: the same residual in physical range, under a gauge fitted on the
BASELINE arm alone and then frozen, so no oracle sees a perturbed field. The
scale-family columns reproduce row 3 to four decimals, which is the check that the
conversion is right.

**This reversed the stage's conclusion.** Read natively, `da3mono_large` looked like
the worst model here by a wide margin and the obvious elimination. Read in range, it
is the most appearance-invariant of the four overall. Every claim below is made on
row 3c.

### 1. Colour and exposure do not move geometry

`wb_warm`, `wb_cool`, `brightness_down`, `brightness_up`: 0.0022–0.0081 for all four
models, at the 8-bit round-trip floor these stimuli pass through. `attenuation_red`
0.0041–0.0124. Per-channel gain and exposure in linear light are geometrically inert
for every survivor — the colour cast this project exists to correct is not what
perturbs their geometry.

### 2. The response is essentially all veil, and it splits the field in two

Mean physical local deformation, veil family (`veil_uniform`, `cue_conflict`,
`veil_depth_consistent`) against the other nine arms:

| model | non-veil mean (9 arms) | veil mean (3 arms) | all 12 |
|---|---|---|---|
| mapanything_n1 | 0.0215 | **0.0383** | 0.0257 |
| metricanything_pointmap | 0.0130 | 0.0869 | 0.0315 |
| wat3r_n1 | 0.0204 | 0.0725 | 0.0334 |
| da3mono_large | **0.0089** | 0.0670 | **0.0234** |

Two different models win the two halves, and the split is the finding:

- `da3mono_large` is the steadiest model under everything that is not a veil —
  0.0089 mean, 1.5x better than the next — and the best single arm on 9 of 12.
- `mapanything_n1` is the steadiest under veils, 0.0383 mean, **1.75x better than the
  next model**, and best on all three veil arms individually.

For underwater footage the veil column is the one that matters. Haze is not an
occasional perturbation here; it is the permanent condition of the medium, and it
covaries with the exact quantity being estimated.

### 3. The cue conflict: how much of each model's geometry is carried by haze

`cue_conflict_inverted_veil` and `veil_depth_consistent` apply the SAME veil
magnitude (transmission spanning 0.45–0.95) and differ only in whether it agrees with
the reference depth. Their ratio isolates veil-leaning, and — because both terms
carry the same unit factor — it is the one statistic the units defect never touched:

| model | conflict | control | ratio |
|---|---|---|---|
| mapanything_n1 | 0.0578 | 0.0245 | 2.36x |
| metricanything_pointmap | 0.1107 | 0.0742 | 1.49x |
| wat3r_n1 | 0.1072 | 0.0550 | 1.95x |
| da3mono_large | 0.1128 | 0.0283 | **3.99x** |

Every model reads haze as depth to some degree. `da3mono_large` leans hardest: it is
the calmest model in the field until the veil disagrees with the geometry, at which
point it moves four times as much as under the identical veil applied correctly. Its
low baseline response and its high ratio are the same fact — a model relying on the
veil cue is stable exactly as long as the cue is honest.

`metricanything_pointmap`'s low ratio is NOT robustness. Its control response
(0.0742) is the worst of the four: it is already deformed under a physically correct
veil, so the conflict adds proportionally less. Low ratio, high floor.

**The ecological caveat, so this is not overread.** Real footage has veil running WITH
depth — the control column, 0.0245–0.0742, inside Week 3's 12 %-at-3 m budget. The
inverted arm is physically impossible and probes mechanism, not deployment. It is not
evidence that any of these models fails on real footage.

**But the mechanism is a specific risk for THIS pipeline.** If a model draws geometry
from veil, and the restoration stage exists to remove veil, then range-before- and
range-after-restoration are different fields and the pipeline is self-referential:
depth feeds restoration, restoration changes the image, the changed image would yield
different depth. The ratio above measures how tight that loop is, and it is tightest
for the model that otherwise looks steadiest. Named question for S6.

### 4. Global scale bias is largely a gauge; local deformation is not (FREEZE C7)

`mapanything_n1` has the LARGEST global scale response to `veil_uniform` (sigma
1.4156, a 42 % shift) and the SMALLEST local deformation (0.0327). `da3mono_large` is
milder globally (1.0941) and larger locally (0.0598).

Under FREEZE C7 these are not comparable failures. A constant global scale bias is a
benign gauge, absorbed by `beta' = beta/s` in the attenuation coefficient at no cost
to the restoration. Local deformation varies spatially and no global physical
parameter transformation can absorb it. So MapAnything responds to haze by rescaling
the scene (recoverable) rather than bending it (not). Ranking these two on sigma would
invert the ranking that matters.

Together with defect (b), this stage produced two separate ways in which a naive
robustness number would have ranked the field backwards.

### 5. Frame-varying drift, where the gauge argument stops

Wander (max/min of per-frame sigma) says whether that benign bias at least holds
still. For the two point-map models it does not:

- `cue_conflict_inverted_veil`: metricanything 1.8709, mapanything 1.5141,
  da3mono 1.2951, wat3r 1.1369.
- `channel_neutralize`: mapanything 1.6159 — its worst wander, on an arm whose median
  deformation is only 0.0619.

`wat3r_n1` (1.03–1.22 across all twelve) and `da3mono_large` (1.01–1.30) hold scale
far more steadily than `mapanything_n1` (1.06–1.62) or `metricanything_pointmap`
(1.06–1.87).

The `channel_neutralize` result carries a direct pipeline consequence: gray-world
neutralisation — what this project's own baseline does — is MapAnything's worst
wander arm. Applying it before monocular inference is not a neutral preprocessing
choice.

### 6. Two models cannot signal their own failure

Coverage is exactly unchanged for `wat3r_n1` (0.782) and `da3mono_large` (0.808) on
all twelve arms, by construction: neither emits a confidence channel (S0 recorded
`conf: None` for `da3mono_large`), so validity is appearance-independent.
`mapanything_n1` and `metricanything_pointmap` do move (mapanything 0.774 -> 0.751
under `hotspot`, -> 0.785 under `channel_neutralize`).

Constant coverage is not stability, it is silence. When these two are wrong under a
perturbation nothing downstream is told. For a pipeline whose temporal stage must
know which pixels to trust, a model that abstains is worth more than one that is
quietly confident — and this is the mark against `da3mono_large` that the metric rows
do not carry.

### 7. Boundary jitter discriminates only MapAnything, and is floor-saturated

Row 5 is 0.00 for three models on all twelve arms. That is a real measurement, not a
missing one: it is a MEDIAN nearest-neighbour distance, so 0.00 means over half the
perturbed edge pixels land exactly on a baseline edge pixel. Being floored it cannot
rank those three against each other. Only `mapanything_n1` registers (3.05 px under
the cue conflict, 2.28 px under `contrast_high`), consistent with its edge set being
the most responsive — which its low local deformation does not contradict, since
boundaries can move while the field between them stays undeformed. Reported for
completeness, not used for ranking.

## Gate decision — all four advance to S5

No elimination at S4. The frozen sequence reduces to 2–3 finalists AFTER S5, and after
the unit correction this stage does not contain a disqualifying result.

| model | S4 standing (physical range) |
|---|---|
| mapanything_n1 | best under veils by 1.75x, the family that matters underwater; its large veil response is gauge not geometry; weakness is scale wander, worst under gray-world |
| da3mono_large | most appearance-invariant overall and by far the best on non-veil arms; but the highest veil-leaning ratio (3.99x) and cannot abstain |
| wat3r_n1 | steadiest scale; mid on everything else; cannot abstain |
| metricanything_pointmap | worst response to a PHYSICALLY CORRECT veil (0.0742), worst veil mean, wanders most under cue conflict (1.8709) — the weakest of the four here |

Carried into S6 as a named question: does a finalist's range field change when
restoration removes the veil it partly derived that range from?
