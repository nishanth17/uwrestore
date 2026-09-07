# Week 4A Round 2 — Parts A, B, C: Round-1 correctness repairs

**Status: PRE-C2.** The reference `D_mapanything` is a provisional multi-view
hypothesis, not ground truth. Every "error" below is *disagreement with that
hypothesis*, and no objective winner is declared here.

Raw artifacts:
`outputs/r2_s2/r2_s2_raw.json`, `outputs/s3/s3_corrected_raw.json`,
`outputs/s4/s4_corrected_raw.json`, `outputs/s5/s5_corrected_raw.json`,
`outputs/s6/`, policy `R2_S2_alignment_policy.json`.
Round-1 files are untouched.

---

## The ray field (A1) — reused, not reinvented

No new camera was introduced. `rho(x) = || K_eval^-1 [u,v,1] ||` is computed by
`g3.ray_length_factor` on the **already frozen** provisional camera — the Week-3
reference `K` carried onto the shared evaluation grid by
`evalgrid.K_source_to_eval`, respecting the existing resize/crop/principal-point
mapping. Then `z_ref = r_ref / rho`.

Measured on the frozen set: `rho` median **1.045–1.127** per clip, max
**1.161–1.507**. So the correction is a 5–13 % effect typically and up to ~50 %
at the extreme corner of `cenote_01`.

This is a **provisional central-camera approximation**: no refraction, no port
model, and `K` is itself part of the Week-3 hypothesis. It cannot be validated
pre-C2.

---

## Part A — DA3 is z-depth, established from source, not from residual

`vendor/Depth-Anything-3/src/depth_anything_3/utils/geometry.py`:

- `:271 unproject(coordinates, z, intrinsics)` builds
  `ray_directions = K^-1 @ homogenize(coords)` and returns `ray_directions * z`.
  The rays are **not normalised**.
- `:359 pixel_space_to_camera_space` does the same: `(K^-1 [u,v,1]) * depth`.
- Contrast `:289 get_world_rays`, which *does* normalise
  (`directions / directions.norm(...)`). The library clearly distinguishes the
  two, and the depth path is the un-normalised one.

`K^-1 [u,v,1]` has third component exactly 1, so the scalar multiplying it **is
the camera-axis Z coordinate**. The parameter is even named `z`.

**`DA3MONO-LARGE`'s scalar is projective z-depth. The Round-1 statement that the
z-vs-range question was "unresolved" was wrong, and it was resolvable the whole
time by reading the code.**

### How badly the Round-1 residual test misled

Round 1 chose the convention by *fitting both and keeping the smaller residual*.
Under the now-established correct semantics, that test was not merely
underpowered — **it points the wrong way**:

| clip | Round-1 residual verdict | correct answer |
|---|---|---|
| wreck_07 | range | z_depth |
| wreck_05 | INDISTINGUISHABLE | z_depth |
| cenote_01 | z_depth | z_depth |
| swimthrough_02 | z_depth | z_depth |
| wreck_01 | range | z_depth |
| wreck_03 | range | z_depth |

It got 2 of 6 right, was undecidable on 1, and was confidently wrong on 3, with a
pooled margin of only 1.11. The reason is structural: DA3's own shape error is
much larger than the ~5–13 % median radial term, so the residual is dominated by
model error, and the affine fit absorbs part of the radial signature. **A
residual comparison cannot identify a representation convention when model error
exceeds the geometric difference between the hypotheses.** This is the concrete
justification for the protocol rule that semantic/source evidence wins.

### A2 — the corrected fit in native z-depth (clip-level, frozen scope)

`z_ref = s * z_DA3 + t`, Huber IRLS, `affine_depth`, clip scope.

| clip | s | t (m) | t / representative z | residual reduction from granting t |
|---|---|---|---|---|
| wreck_07 | 5.99 | 5.54 | 0.53 | 0.35 |
| wreck_05 | 6.73 | 10.36 | 0.62 | −0.03 |
| cenote_01 | 2.70 | 3.08 | 0.51 | 0.52 |
| swimthrough_02 | 8.10 | 4.44 | 0.40 | 0.27 |
| wreck_01 | 3.83 | 1.86 | 0.41 | 0.01 |
| wreck_03 | 5.50 | 10.14 | 0.65 | 0.42 |

Two things stand out, and neither is a small nuisance:

1. **`s` varies 2.70–8.10 across clips (3.0×).** DA3 mono carries no consistent
   scale. It is a relative model and must be treated as one.
2. **`t` is 40–65 % of the representative scene z-depth.** The shift is not a
   small offset; it is comparable to half the scene. And the benefit of granting
   it is wildly clip-dependent (0.01 to 0.52), so the shift is absorbing
   something clip-specific rather than a fixed sensor property.

Per-frame diagnostic (`s_t`, `t_t`, never used for the primary fit): `s_t`
wander ratio **1.55–3.97**, `log_std` 0.11–0.31. The scale the model needs
changes by a factor of 1.5–4 *within a single clip*.

### A3 — OLD vs CORRECTED on every load-bearing metric

DA3 inference was **not** re-run; all numbers are recomputed from the persisted
native predictions.

**S3 (288 frames, 6 clips):**

| metric | OLD (range) | CORRECTED (z_depth) | change | mapanything_n1 |
|---|---|---|---|---|
| M-1 abs-rel | 0.1283 | **0.1476** | +15.0 % | 0.0853 |
| M-2 near/far b | 0.8464 | 0.8555 | +1.1 % | 0.9503 |
| M-3 RelNormal ° | 12.77 | 13.35 | +4.5 % | 6.84 |
| M-3 abs normal ° | 20.58 | **19.54** | −5.0 % | 7.95 |
| M-4 boundary | 0.0285 | **0.0223** | −21.8 % | 0.0028 |
| M-5 ordinal@25 % | 0.0037 | 0.0062 | +66.7 % (both ≈0) | 0.0000 |
| M-6 outer/inner | 1.014 | **1.136** | +12.1 % | 1.043 |
| coverage | 0.808 | 0.808 | — | 0.778 |

The correction is **not** uniformly favourable, which is what makes it credible:
boundary localisation improves 22 % and absolute normals improve 5 %, while
range agreement degrades 15 %.

**The M-6 result is the important one.** Round 1 reported DA3 M-6 ≈ 1.01, an
almost perfect radial-consistency number. That number was an artifact. Per clip:

| clip | M-6 OLD | M-6 CORRECTED |
|---|---|---|
| wreck_07 | 1.047 | 0.832 |
| wreck_05 | 0.980 | 1.224 |
| cenote_01 | 0.684 | 1.551 |
| swimthrough_02 | 1.521 | 1.574 |
| wreck_01 | 1.066 | 1.045 |
| wreck_03 | 0.705 | 1.047 |

Reading a z-depth as a range under-applies the radial term, and DA3's own radial
error partially cancelled the omission. Once the correct radial factor is
applied, the residual radial structure is exposed and spreads from 0.83 to 1.57.
**Round 1's "DA3 has excellent radial behaviour" conclusion was a compensating
pair of errors and is withdrawn.**

**S4 (appearance invariance):** every constant-global-scale and
frame-varying-drift number is **bit-identical** OLD vs CORRECTED
(delta = 0.0000), and native `local_range_deformation` is bit-identical too.
Only the physical-gauge variant moves (max |delta| 7.7e-03, e.g. cue-conflict
0.1128 → 0.1205). This is expected and not a defect: S4 compares the model
against *itself* under perturbation, and `rho(x)` is a fixed spatial gauge
common to both arms, so it cancels exactly. **The semantic correction changes no
S4 conclusion.** DA3's cue-conflict local deformation (0.249 native) remains the
largest of any perturbation.

**S5 (temporal):** the correction does **not** fix temporal scale drift. Scale
wander moves in both directions (−0.75 to +0.24) with no systematic improvement;
corrected DA3 still wanders **1.54–3.94** across clips. Under §21's reading, a
frame-varying `s_t` means `beta'_t = beta / s_t` — water properties that change
frame to frame — so this remains a physical-consistency failure, uncorrected.

*(Note: DA3's S5 `boundary_jitter` reads 0.00 px in both Round 1 and the
corrected run, while MapAnything reads 1.0–4.1 px. This is a pre-existing
measurement degeneracy for this arm, not an effect of the correction; flagged as
an open Round-1 issue rather than silently used.)*

**S6 (restoration impact, `coastal`, responsive window):** the correction does
not materially change restoration behaviour.

| metric | DA3 OLD | DA3 CORRECTED | mapanything_n1 |
|---|---|---|---|
| ΔE00 median | 2.163 | 2.550 | 1.664 |
| ΔE00 p95 | 10.280 | 9.591 | 6.295 |
| ΔE00 median (responsive window) | 3.510 | **3.596** | 2.629 |
| window fraction | 0.685 | 0.684 | 0.678 |
| radiance abs-rel | 0.0268 | 0.0258 | 0.0147 |

Per clip (window ΔE00): wreck_05 improves 7.78 → 7.05 but stays by far the worst;
wreck_07 degrades 3.18 → 3.70. Corrected DA3 remains **DEGRADED** relative to the
provisional reference, at ~1.37× MapAnything's window ΔE00.

### Re-decision on DA3 finalist status

Corrected DA3 remains **far behind MapAnything N=1 on every primary dimension**
(M-1 0.148 vs 0.085; RelNormal 13.35° vs 6.84°; M-4 0.0223 vs 0.0028). The
correction changes the *interpretation* substantially — it withdraws the M-6
claim and improves the boundary claim — but it does **not** change DA3's rank or
its standing relative to the incumbent. DA3 Mono is carried into Round 2 as the
corrected incumbent I2, not promoted.

---

## Part B — DA V2 semantic repair, and the stop

Depth Anything V2 emits relative **disparity**, i.e. inverse depth in the
monocular-depth dataset sense, where "depth" is the projective z coordinate
(KITTI/NYU/Hypersim targets are all z). The legal affine ambiguity therefore
lives in `1/z`, so the reference enters as `q_ref = 1 / z_ref`, not `1 / r_ref`.

Primary fit unchanged in form and objective: `q_ref = a * q_DAv2 + b`, Huber
IRLS, native disparity space, clip scope, frozen valid-mask support, guards
before inversion. **The objective was not moved to log-depth or z-space** — that
would have optimised away the far-range failure this is meant to measure.

| metric | OLD | CORRECTED | change |
|---|---|---|---|
| M-1 abs-rel | 0.1761 | 0.1798 | +2.1 % |
| M-2 near/far b | 0.535 | 0.581 | +8.8 % |
| M-3 RelNormal ° | 27.50 | 28.19 | +2.5 % |
| M-3 abs normal ° | 36.25 | 39.30 | +8.4 % |
| M-4 boundary | 0.1022 | 0.1001 | −2.1 % |
| M-5 ordinal@25 % | 0.1172 | 0.1197 | +2.1 % |
| M-6 outer/inner | 0.935 | 0.926 | −0.9 % |

**Predeclared sensitivity check** (range-balanced weighting, *same* disparity
objective, equal weight to near/mid/far bands — SENSITIVITY ONLY, never
substituted for the primary fit): the refitted `a` differs from the primary by
**under 1 %** on every clip (e.g. wreck_07 0.02939 → 0.02917). The primary S2 fit
is therefore driven by the model, not by how these clips happen to sample range.

**Gate decision: DA V2 remains clearly eliminated, and Part B stops here.**
The correction moved nothing materially (M-1 +2.1 %), and DA V2 is still
catastrophic on the dimensions that matter for restoration: abs normal 39.3°
(vs 7.9°), boundary 0.100 (vs 0.0028 — a factor of 36), ordinal violations 0.120
(vs 0.000). Its per-frame scale wander on `wreck_03` is **118.6**. Per the
protocol, S4–S6 were **not** re-run for DA V2; correcting the semantics did not
come close to reversing the original elimination.

---

## Part C — FoundationGeo mechanism check: already present, now surfaced

Both required ablations were computed in Round 1 under **one** frozen
`(focal, shift)` solution applied to both arms — the backend deliberately calls
`forward()` rather than `infer()` precisely so that the two ray-correction arms
are *not* postprocessed through independent `recover_focal_shift` solutions.
So the C1 requirement ("do not independently recover focal/shift for each arm
and call the difference causal") was already satisfied by construction.

**C1 — learned ray correction (`fg_pre_ray` → `fg_post_ray`):** all six
dimensions move by less than printing precision. The point maps differ by mean
relative **1.1e-03** in the 3-vector; the correction turns each ray by median
**0.044°** (p99 0.21°, max 0.78°) against a 3° cap; the induced change in range
is median relative **2.3e-07** (p99 3.8e-06). **The learned ray correction is
mechanically inert on this footage.**

**C2 — per-pixel scale field (`fg_post_ray` → `foundationgeo_11`):**

| metric | pre-scalefield | post-scalefield | change |
|---|---|---|---|
| M-1 | 0.1596 | 0.1712 | +7.3 % |
| M-2 | 0.834 | 0.845 | +1.3 % |
| M-3 RelNormal | 32.15 | 32.71 | +1.8 % |
| M-3 abs normal ° | 36.3 | 38.5 | +6.1 % |
| M-4 | 0.0433 | 0.0423 | −2.4 % |
| M-5 | 0.0863 | 0.0862 | −0.1 % |
| M-6 | 0.81 | 0.79 | −1.5 % |

Scale field median **0.840**, p01–p99 span 0.803–0.872 — a nearly uniform ~0.84
multiplier. It behaves almost like a global scale, and since S2 refits scale
anyway, it mostly **degrades** agreement (M-1 +7.3 %, normals +6.1 %) while
buying a marginal boundary improvement.

**Neither FoundationGeo mechanism earns its complexity on this footage.** No
re-inference was required.

### Part C, recomputed after the Part D grid repair

The C1 and C2 tables above were computed before Part D fixed the grid map, and
FoundationGeo is a **source-grid** model, so both are affected. Recomputed on the
corrected grid (median over the six clips, `R2_S3_results.json`):

| metric | `fg_pre_ray` | `fg_post_ray` | `foundationgeo_11` (post-scalefield) |
|---|---|---|---|
| M-1 | 0.11353 | 0.11353 | 0.11351 |
| M-2 b | 1.3058 | 1.3058 | 1.3059 |
| M-3 rel ° | 16.265 | 16.265 | **17.810** |
| M-3 abs ° | 21.495 | 21.494 | **24.448** |
| M-4 | 0.02088 | 0.02088 | 0.02191 |
| M-5 @0.25 | 0.00167 | 0.00167 | 0.00185 |
| M-6 | 1.0371 | 1.0371 | **1.1763** |
| coverage | 0.80592 | 0.80592 | 0.80592 |

**C1 is unchanged and if anything stronger:** `fg_pre_ray` and `fg_post_ray` are
now identical to five decimals on every dimension. §18 corroborates this
independently on the crane lattice, where the two arms produce the same gap to
three decimals on all six annotated frames.

**C2 changes in detail but not in verdict, and one earlier statement must be
withdrawn.** On the corrected grid the scale field no longer degrades M-1
(0.11353 → 0.11351, i.e. nothing) — the +7.3 % degradation reported above was
partly the grid defect. But it also no longer buys the "marginal boundary
improvement" that table credited it with: M-4 now moves the wrong way
(0.02088 → 0.02191). What it does is degrade the *structural* dimensions —
relative normals +9.5 %, absolute normals +13.7 %, and frame uniformity M-6 from
1.037 to 1.176. **The conclusion stands and is now cleaner: the per-pixel scale
field buys nothing this evaluation can see and costs surface structure.**

---

## Part E — a load-bearing Round-1 *statement* that was wrong, independent of any code

Parts A–D repaired computations. This one repaired a sentence, and it is recorded
here because §26 asks for it explicitly and because the sentence is still sitting in
a persisted Round-1 deliverable.

`results/FINALISTS_PRE_C2.md:279` reads:

> **2. Nobody can supply scale at inference.** MapAnything needs a clip-level scale;
> da3mono needs a clip-level (s, t) …

**The first clause is false for MapAnything and must not be repeated.** MapAnything
**produces raw metric-scale output**. What actually happened in S2 is that the
evaluation *fitted* a clip-level scale to it — a scale-family gauge, `s` only, no
shift — and it did so for every arm including the metric ones, because the Week-3
reference is itself a provisional product whose own gauge is unvalidated. Fitting a
gauge to remove the *reference's* ambiguity is an evaluation decision. Reading it
back as a statement that the *model* cannot supply scale inverts the direction of the
inference.

The correct statement, and the one used everywhere in Round 2:

> **MapAnything produces raw metric-scale output, but its absolute scale is not
> independently validated pre-C2.**

Two Round-2 measurements sharpen it rather than soften it.

- The fitted scale is close to unity — `mapanything_n1` clip fit `s` = 1.0476 in
  §18's frozen gauge — so its raw metric output and the provisional reference agree
  on scale to within a few percent. That is *consistency*, not validation: the
  reference was built from the same architecture, so the agreement is exactly what
  the §26 reference-architecture confound predicts either way.
- R2-S4 F2 measures what the raw scale actually responds to: a uniform veil carrying
  **no depth information** multiplies MapAnything's clip range by 1.416 median and
  2.465 on the worst clip, and the constant scale swings by ±40 % across the twelve
  perturbations, against ±5 % for `wat3r_n1` on identical stimuli.

So the honest pre-C2 position is neither "it needs a scale" nor "its scale is
correct". It is: **the scale exists, it is emitted natively, it agrees with a
reference that cannot independently confirm it, and it is a function of how the
water looked.** Which is precisely why §27's C2 requirement has to include a scale
measurement taken under *varying* water appearance rather than on one clean clip.

The Round-1 file is left unmodified — it is the persisted record of what Round 1
concluded, and rewriting it would erase the correction. This section is the
correction.
