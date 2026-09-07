# S2 — native ambiguity and the frozen alignment policy

**Stage:** S2. **All seven models continue.** The policy written here is FROZEN
for S3-S6 and lives in `S2_alignment_policy.json`.

What S2 freezes is a **policy, not a transform**. There is no alignment that is
legal for all seven entrants, and fitting one anyway is the standard way to make a
monocular comparison meaningless: Depth Anything V2's ambiguity lives in
*disparity*, and `a*d + b` in physical depth is not a stricter version of
`a*q + b` in disparity — it is a different group.

Measurement and decision were separated on purpose. `s2_ambiguity.py` measures and
decides nothing; `s2_freeze_policy.py` decides and records the evidence each
decision rests on, so a reader can check that the policy follows from the numbers.

## The frozen policy

| arm                     | native_kind            | E1 family        | convention | convention from | scope |
|-------------------------|------------------------|------------------|------------|-----------------|-------|
| mapanything_n1          | depth_along_ray_metric | scale            | range      | the             | clip  |
| dav2_small              | disparity_relative     | affine_disparity | range      | MEASURED        | clip  |
| moge2_vitl              | pointmap_metric        | scale            | range      | the             | clip  |
| metricanything_pointmap | pointmap_metric        | scale            | range      | the             | clip  |
| wat3r_n1                | pointmap               | scale            | range      | the             | clip  |
| da3mono_large           | depth_relative         | affine_depth     | range      | MEASURED        | clip  |
| foundationgeo_11        | pointmap_metric        | scale            | range      | the             | clip  |

FoundationGeo's three ablation arms (`fg_pre_ray`, `fg_post_ray`, and its primary
output as V4c's arm D) inherit this policy unchanged. They are the same
representation from the same checkpoint, and aligning an ablation arm differently
would confound the intervention with the alignment.

**Scope is clip-level for every arm.** Per-frame fitting exists here only as a
diagnostic. Week 3 established that renormalising each frame erases temporal scale
drift, and FREEZE C7 makes that drift a first-class failure mode rather than a
nuisance: a *constant* global scale bias is benign, because the physical
coefficients can be refit once as `beta' = beta/s`; *frame-varying* drift would
demand `beta'_t = beta/s_t`, i.e. water properties that change with the estimator.

## The two conventions S0 left open, settled by measurement

### `dav2_small`

- z-depth hypothesis: median abs-rel **0.1751**
- range hypothesis:   median abs-rel **0.1783**
- margin ratio: **1.018**, agreeing clips: **2/6**
- **verdict: `range`** — the two hypotheses are indistinguishable at the 3 % margin; defaulted to the project's canonical range, and the tie is recorded

### `da3mono_large`

- z-depth hypothesis: median abs-rel **0.1509**
- range hypothesis:   median abs-rel **0.1358**
- margin ratio: **1.111**, agreeing clips: **3/6**
- **verdict: `range`** — the range hypothesis leaves the smaller residual

Both hypotheses differ by this camera's secant factor, which spans about 1.00 at
the principal point to 1.35 at the corners — a large, purely radial signal. A
model whose field is genuinely z-depth should be visibly better explained by the
z-hypothesis; one whose shape error already exceeds a 35 % radial term will come
back INDISTINGUISHABLE, and that is itself a finding about the model rather than a
failure of the test.

## Does the additive term earn its place? (FREEZE C1)

- **`wat3r_n1`** — median relative gain from granting the shift over scale-only: **+0.111** (per clip: +0.144, +0.079, +0.305, -0.103, +0.074, +0.281)
- **`da3mono_large`** — median relative gain from granting the shift over scale-only: **+0.383** (per clip: +0.498, +0.075, +0.523, +0.268, +0.086, +0.556)

A gain near zero would license describing the checkpoint as behaving
**approximately scale-only on the tested domain** — a conclusion the freeze allows
only from data, never from architecture or from the presence of a
`least_squares_scale_scalar` utility in the release.

## Scale trajectories and clip-to-clip spread

| arm                     | clip-to-clip scale spread | median within-clip wander | worst wander | median log-std | median frame-to-frame log MAD |
|-------------------------|---------------------------|---------------------------|--------------|----------------|-------------------------------|
| mapanything_n1          | 1.200                     | 1.841                     | 5.591        | 0.1489         | 0.0499                        |
| dav2_small              | 4.594                     | 3.172                     | 17.367       | 0.2640         | 0.0745                        |
| moge2_vitl              | 1.559                     | 2.433                     | 7.186        | 0.2003         | 0.0703                        |
| metricanything_pointmap | 1.759                     | 2.279                     | 7.119        | 0.1937         | 0.0792                        |
| wat3r_n1                | 5.412                     | 2.297                     | 3.361        | 0.2580         | 0.0388                        |
| da3mono_large           | 3.259                     | 2.151                     | 4.405        | 0.2027         | 0.0488                        |
| foundationgeo_11        | 4.860                     | 1.949                     | 5.906        | 0.1505         | 0.0546                        |

`wander` is the ratio of the largest to the smallest per-frame scale within a clip.
A value of 1.0 would mean one clip-level scale describes every frame. Anything
materially above 1.0 is frame-varying scale drift, which under a shared clip-level
physical model is **not** a benign gauge — S5 is where that gets its full treatment,
but the quantity is measured here so the frozen policy carries it.

## Raw metric behaviour: RECORDED pre-C2, JUDGED post-C2

| arm                     | raw median abs-rel | E1-aligned median abs-rel | median coverage vs reference |
|-------------------------|--------------------|---------------------------|------------------------------|
| mapanything_n1          | 0.1158             | 0.1019                    | 0.759                        |
| dav2_small              | -                  | 0.1739                    | 0.764                        |
| moge2_vitl              | 0.6447             | 0.2189                    | 0.777                        |
| metricanything_pointmap | 0.6297             | 0.1943                    | 0.757                        |
| wat3r_n1                | 0.9354             | 0.2021                    | 0.755                        |
| da3mono_large           | -                  | 0.1331                    | 0.784                        |
| foundationgeo_11        | 0.5793             | 0.1869                    | 0.783                        |

The raw column is the model's own scale against the Week-3 reference's own scale,
with no alignment at all. Pre-C2 a disagreement there **cannot** be attributed:
there is no independent anchor to say whether the monocular scale is wrong or the
Week-3 scale is. It is recorded and left unjudged, per FREEZE §7. The relative-only
models have no raw column by construction.

## Cross-check: the reference is being read on the grid it was written on

This session's independent S0 FOV measurement of MapAnything's preprocessing and
Week 3's own `preprocess_maps.json` agree to about 1e-11 in scale and 1e-8 px in
offset. That matters because every number in S3-S6 is a comparison against the
persisted Week-3 product, sampled through that map. Two independent measurements of
the same preprocessing agreeing to floating-point precision is the evidence that the
comparison is well-posed.
