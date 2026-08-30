# Week 6B — spatially varying / artificial illumination: research note

**Date of pass: 2026-08-30.** `PLAN.md` carries the Week 6B experimental design
and decision rules. This file carries the evidence, formulations, licences,
identifiability findings and rejected alternatives.

Scope: the **restoration / physical model**. The Phase 2B temporal evaluator's
global luminance affine `Y_t ≈ gain·Y_warp(t+k) + bias` is a deliberately
low-capacity nuisance model fitted on aligned **original** frames and is
explicitly **out of scope**. Nothing here touches it.

---

## 0. The four findings that shaped the design

### 0.1 Artificial light attenuates over two water paths

From Relative Illumination Fields §3.3, verbatim: for a single point light at
the camera centre, `t_l = t_c`, so the attenuation over the whole light path
becomes

```text
exp(−σ_attn·t_l) · exp(−σ_attn·t_c) = exp(−2·σ_attn·t_c)
```

For any other light configuration the relation between `t_l` and `t_c` depends
on the light's pose relative to the camera and on the point position.

So the exact statement is: **a collocated camera/light doubles the direct-path
attenuation exponent; a real offset camera-mounted torch instead attenuates over
the sum of the light→surface and surface→camera water paths**, which varies
across the frame. Family B's transmission is therefore

```text
T_c(x) = exp( −β_c · [ d_light(x) + d_cam(x) ] )
```

which is computable only because Week 3 supplies the geometry.

This is the single most important physical fact for the roadmap: a
dive-light-lit clip fitted with the **single-path** model of Weeks 5–6 recovers
a `β` that is systematically wrong — exactly doubled in the collocated limit,
spatially varying otherwise. A predictable bias, not a mysterious failure, and
the reason Weeks 5 and 6 must declare their clip scope rather than silently
fitting on the `lights` clip.

### 0.2 Point-source inverse-square is a hypothesis to test, not a given

NeLiS (DarkGS, IROS 2024) replaces inverse-square with a **Lorentzian**
falloff, `Ψ_τ(x) = 1/(τ + ‖ω_x‖²)` with **τ learnable**, and reports that it fits
**the real light sources it tested** better at close range. A real luminaire is
an extended source, and at diver working distances we may be in its near field.

That is an empirical result for those camera-light systems, **not a law of dive
torches.** So the plan's instruction — *"do not assume the simple inverse-square
law alone is correct underwater"* — is right, and the correct response is an
experiment rather than a substitution: fit **both** `1/r²` and `1/(τ + r²)` on
our own underwater sweep and keep the simpler form unless held-out data supports
the extra parameter. If our torch is effectively far-field at 1–3 m, τ buys
nothing and disappears — which is itself a result worth having.

### 0.3 Both leading methods confirm that flexible capacity steals the illumination

RIF's own Discussion reports two identifiability failures, empirically:

- **Observable attenuation changes** — *"The changes in color caused by the
  medium attenuation can only be observed if the distance to the scene varies.
  If camera poses are at a constant distance the degree of attenuation is also
  constant and can not be distinguished from the object color."* Their Fig. 6
  shows exactly this failure on a constant-distance trajectory.
- **Observable light pattern** — NeRF's view-dependent colour term (SH-encoded
  ray direction, normally there to model specularity) **absorbs the illumination
  effect** when poses are limited. Their fix is to *disable* view dependency.
  They also disable the NeRF-W appearance embedding and camera pose
  optimisation, both of which *"interfere with our light representation."*

Song/She/Köser hit the same wall from the classical side: their correspondence
constraint has **four unknowns per correspondence pair**, so it cannot identify
the model alone; a unique solution needs *"at least four pairs of images
observ[ing] four different coloured objects at the same position in the local
camera coordinate system"*, which they call *"difficult to obtain in
practice."* They therefore fall back on known-colour, smoothness and pure-water
constraints.

Two independent research groups, two different formalisms, same conclusion:
**this problem is only weakly identifiable, and extra capacity makes it worse,
not better.** The bakeoff must therefore be judged on **held-out views**, and
capacity must be a last resort.

### 0.4 There is a cheap, decisive calibration acquisition

Song §3.2.1: one observation of a known albedo constrains (α, β) only to a
**line** in the α–β plane; two observations with **widely disparate** known
colours give the intersection. Their stated ideal: *"an ideal diffuse object
that reflects all visible light wavelengths equally and a perfect black body …
the backscatter factor β … can be directly measured by filming the black body
in the medium at different distances. Once all β values are fixed, α values can
be computed directly … (α = (I−β)/I0, where I0 = 1)."*

The project already owns a colour chart. Filming it **at several ranges and
several positions in the frame** is therefore the cheapest high-value
acquisition in this phase, and it serves families A, B and D as well.

**Treat that algebra as the identifiability argument, not as the estimator.** A
real ColorChecker's darkest patch has `ρ ≠ 0`, so it *strongly constrains* the
additive term rather than measuring it; only the ideal black body measures it
directly. Song himself notes that measurement error turns each clean constraint
line into a finite interval, so the intersection is a region, not a point, and
the published method accordingly uses multiple constraint types, uncertainty
weighting, trilinear interpolation and smoothness inside an optimisation. Fit
jointly over the known calibrated reflectances of several patches; do not treat
the physical black patch as a perfect absorber and do not claim "no optimisation
required".

Song §3.2.4 adds a second cheap constraint: images of **pure water** bound the
backscatter, `β_N ≤ I_pw` for every slab along a ray, since β increases
monotonically along the ray. A diver produces this by pointing the camera into
open blue water for a few seconds.

---

## 1. Candidate family A — no explicit illumination model (control)

The existing Week 5/6 physics on ambient/diffuse footage. Not a paper; the
control that decides whether anything here is needed. Sea-thru
(Akkaynak & Treibitz, CVPR 2019) already carries a *spatially varying
illuminant* estimated from local space average colour, so the baseline is not
"global illumination" — it is "illuminant estimated from image statistics
without a light model."

---

## 2. Candidate family B — calibrated physical camera-light model

### NeLiS / DarkGS

Zhang, Huang, Zhi, Johnson-Roberson (CMU), **IROS 2024 Oral**,
arXiv:2403.10814.

- `tyz1030/neuralight` — **MIT**, 53 stars, last push 2024-05-20. The
  camera-light calibrator, standalone.
- `tyz1030/darkgs` — `NOASSERTION`, 118 stars, last push 2025-01-29. The 3DGS
  scene model built on it.

**Model.** Incident radiance from three learned components:

| Component | Form |
|---|---|
| Radiant intensity distribution | `Φ_θ(x) = MLP_θ(cos⁻¹(·))`, an MLP over the **angle between the light centreline and the ray** — *not* assumed Gaussian |
| Falloff | **Lorentzian** `Ψ_τ(x) = 1/(τ + ‖ω_x‖²)`, τ learnable |
| Ambient | learnable constant `A`, so calibration works in non-dark environments |

**Calibration.** White planar target with four AprilTags at the corners;
**~40 images per light source** from varied ranges and perspectives; camera and
light rigidly attached (their baseline ~32 cm); AprilTag PnP fixes the world
frame; the light pose `(R_lc, t_lc)` is optimised jointly. Fitting minimises
an L1 photometric loss over MLP weights, τ, A and the light pose, staged
(pose → RID → joint) through a human-in-the-loop GUI to avoid local minima.

**Stated limitations, all material here:** no medium scattering (clear air
only), no spectral modelling, Lambertian BRDF only, no shadows or specularity.

**Verdict.** This is the right *skeleton* for family B and the wrong *complete
model*. Family B must be NeLiS's geometry (RID + falloff, with `1/r²` and
`1/(τ+r²)` compared rather than one assumed, + ambient + rigid extrinsic)
**plus** two-path medium attenuation `exp(−β·(d_light + d_cam))`, Lambertian
`cos θ` shading from derived normals, **and an active-backscatter term.**

**The active-backscatter term is not optional, and this was the one real hole in
the first design.** A dive light illuminates the water between camera and
object, not just the object — the torch cone is the dominant visual signature of
torch-lit footage. NeLiS explicitly has no medium at all, so taking it as-is
leaves family B unable to represent the cone. Both richer families *can*: family
C stores a spatially varying additive term per voxel, and family D decomposes
object and medium contributions with the illumination factor affecting both.

If B is allowed only a direct-signal model, C or D will beat it **because they
model an effect B was forbidden to represent**, and the experiment would return
"spatial flexibility was necessary" when the true answer was "you crippled the
control". A low-capacity ray-integrated form reusing B's own calibrated beam and
its own `β` is enough — no radiative transfer, no volume scattering function, no
new free field. The escalation then becomes *simple ray-integrated active
backscatter leaves structured light-cone residual → richer camera-relative
volumetric backscatter*, which is a fair comparison.

### Classical deep-sea light modelling

Supporting context: spotlights on underwater platforms have peak emission along
the central axis with drop-off at increasing angle, formalised as a **radiation
intensity distribution (RID)** curve, often approximated by a Gaussian; sources
are described by luminous flux, normalised spectrum, and a beam aperture
half-angle. The deep-sea robotic imaging simulator literature from the same
Kiel group builds on exactly this parameterisation. NeLiS's contribution is
replacing the assumed Gaussian RID with a learned one.

---

## 3. Candidate family C — low-capacity empirical camera-relative field

### Song, She, Köser 2024

*Advanced underwater image restoration in complex illumination conditions*,
**ISPRS Journal of Photogrammetry and Remote Sensing 209 (2024) 197–212**,
DOI 10.1016/j.isprsjprs.2024.02.004, arXiv:2309.02217. GEOMAR Kiel + CAU Kiel.
**Open access.** No public code found.

**Formulation.** Eq. 3: `I = α·I0 + β` with `α, β > 0`, where `I0` is object
albedo **after shading compensation**, α is a multiplicative direct-signal
factor and β an additive backscatter term. Restoration is Eq. 4:
`I0 = (I − β)/α`.

**Shading compensation is a prerequisite, not part of the model.** Verbatim:
*"Assuming that the object surface is Lambertian, shading compensation can be
performed by dividing the original pixel intensity by cos θ, where θ is the
angle between object surface normal and incoming light. We approximate the
light originates from the camera position, and the surface normal can be
calculated from the corresponding depth map."* So it needs **per-pixel normals
from range**, and it assumes a camera-centred light.

**Representation.** A **3D lookup table in the camera viewing frustum**: the
frustum is sliced into slabs, each slab a plane of voxels, each voxel storing
one α and one β **per colour channel**. Camera-relative and co-moving.
Justification: *"Giving the stable lighting and water conditions during a
single mission … the parameters in the lookup table are relatively fixed,
enabling rapid batch restoration of entire image sequences."*

**Estimation constraints:**

1. **Known colour** — two observations of widely disparate known albedos at the
   same voxel give a unique (α, β); black body + white diffuse is the ideal
   pair (§0.4 above).
2. **Correspondence** — the same point seen in two images lands in two voxels,
   giving `α₂·I₁ − α₂β₁ − α₁·I₂ + α₁β₂ = 0`. Underdetermined alone.
   Colour correspondences must come from **homogeneous superpixel regions**,
   not SIFT/SURF keypoints, which sit on edges where colour is unreliable.
3. **Smoothness** — 6-neighbour regularisation on α and β; weights stronger far
   from the lights, where illumination is smoother. Trilinear interpolation of
   parameters to each observation, needing ≥ 8 uniquely-solved points per group
   of 8 neighbouring voxels.
4. **Pure water** — `β_N ≤ I_pw` along each ray from images of open water.

Estimation is hierarchical, coarse-to-fine in LUT resolution.

**The identifiability caveat that matters most:** α and β *"represent the
combined effect of lighting and water at that particular 3D position."* They do
**not** separate medium from illumination. A fitted α cannot be read as
`exp(−β_att·d)` and β cannot be read as a Jerlov-comparable coefficient. Family
C is an appearance-correction field, and adopting it wholesale would destroy
the physically interpretable coefficients Week 6 exists to produce. The plan
therefore requires that if C wins, its parameters are persisted as an
**explicitly non-physical** appearance field alongside, not instead of, the
Week 5/6 physical state.

---

## 4. Candidate family D — learned illumination field

### Relative Illumination Fields

She, Seegräber, Nakath, Schöntag, Köser (Kiel University + GEOMAR),
**ICCV 2025**, arXiv:2504.10024. Code: `MDSKiel/relative-illumination`,
**Apache-2.0**, last push 2026-03-09 (3 stars). Data:
`opendata.uni-kiel.de/receive/fdr_mods_00000261` (Tank, Abu Dhabi, Color
Checker).

**Formulation.** A local illumination field attached to the camera:

```text
α = F^l_Θ( φ_Hash(x^c), φ_SH(n^c) )        Eq. 6
ĉ'_i = α_i(x^c, n^c) · c_i                 Eq. 5
x^c = cT_w · x^w        n^c = cR_w · n^w   Eq. 7
```

α is a **per-colour-channel** light-intensity factor over **camera-frame
position and camera-frame surface normal**. Normals come from the gradient of
the predicted density field — i.e. from the NeRF itself, no external geometry.

The full physical form (Eq. 4) is
`c'_i = α_i(x^c, n^c, d_l)·f_r·λ_vis·c_i`; they **drop** the BRDF `f_r`
(*"most non-artificial materials can be reasonably assumed to behave Lambertian
underwater"*) and **drop** the visibility term `λ_vis` (*"lights are commonly
close to the camera and shadows are cast behind objects, outside of view"*),
acknowledging shadows as a limitation.

**Key assumption:** *"the cumulative illumination a surface point receives
within the camera's viewing frustum is more critical than knowing all the
characteristics of each individual light source … the three dimensional
illumination pattern remains constant in relation to the camera."* Rigid
camera-light rig; **number, position and profile of the lights need not be
known**; multiple lights supported.

**Medium** is modelled separately and jointly estimated: attenuation
coefficient `σ_attn`, medium colour `c_med`, backscatter `σ_bs`, integrated
into an underwater volume-rendering formulation. So unlike family C, **D does
attempt medium/illumination separation** — which is exactly why its
identifiability discussion (§0.3) is so informative.

**Why α must be per-channel:** in air one scalar α suffices if all lights share
a colour; in a medium the light is already attenuated on its way to the object,
wavelength-dependently, so α is estimated per channel. Their ablation shows the
single-channel version develops a blue-green hue in medium — *and* that on
their real dataset *"the metric does not show an improvement … the rather small
effect is drowned in the noise of the real dataset due to imperfect calibration
and poses."* Honest, and a warning about how small these effects can be
relative to geometry error.

**Implementation.** Nerfstudio / Nerfacto extension; RawNeRF-style HDR handling
with loss on Bayer-masked RAW; exponential activation on scene colour, sigmoid
on the illumination field; a dataset-dependent scaling factor on α that the
authors say *"requires further investigation."* NeRF-W appearance embeddings and
pose optimisation disabled.

**Their evaluation protocol, worth copying.** Colour-checker patches averaged
over **five held-out test views**; reference for real data captured in air with
the *same camera and light*, in a lawnmower pattern at constant distance and
angle, taking the highest intensity of each patch mean; object colour recovered
only **up to scale**, so all colours are aligned by one least-squares scalar
over the 24 patches before computing the mean L2 norm.

**The transferability limitation.** RIF is a per-scene NeRF. It restores by
**re-rendering the reconstructed field**, not by processing arbitrary video
frames. It cannot be dropped into a `FrameSequence -> FrameSequence` stage. Its
role in this project is as a **capacity ceiling and identifiability oracle** on
one controlled scene, not as a candidate pipeline stage.

The authors also note: *"Since we are tackling a largely unsolved problem,
there are virtually no competitor methods to compare against."* This subfield is
young. Do not expect a mature best answer to exist.

---

## 5. Searched for a 2026 successor — none found for this problem

Extensive search through 2026 surfaced no method that supersedes RIF for
**co-moving artificial light + scattering medium**. What exists is a large and
growing underwater 3DGS literature that decouples **medium** from appearance
under *ambient* illumination — SeaSplat (ICRA 2025), WaterSplatting, UW-3DGS
(AAAI 2026), 3D-UIR, WaterClear-GS, Underwater360, R-Splatting, DualPhys-GS,
Spatiotemporal Degradation-Aware 3DGS. These model attenuation and backscatter,
not a co-moving light cone, and all are per-scene novel-view-synthesis
optimisers.

Adjacent 2026 work noted but not adopted: SpotlessGS (relightable 3DGS under
dynamic illumination for robotic perception, arXiv:2608.14713) — in-air,
relighting-focused; and the halo-separation underwater restoration line
(arXiv:2605.10374), which targets the artificial-light halo as an image-space
artefact rather than a physical illumination model.

**Conclusion for research question 3: no materially stronger 2026 successor to
RIF has appeared.** The 2024 ISPRS LUT and the 2025 ICCV field remain the two
poles, and NeLiS remains the best calibrated-physical reference.

---

## 6. Answers to the required research questions

1. **Song/She/Köser 2024 formulation, code?** `I = α·I0 + β` on
   shading-compensated intensity, with (α, β) per RGB channel stored in a
   camera-frustum voxel LUT; four constraint types; hierarchical estimation.
   **No public code found.** Reimplementation is required, and is tractable —
   the LUT plus a linear-in-(α,β) least-squares system with smoothness is not
   a large piece of work. The known-colour path alone (black + white chart at
   several ranges) is implementable in a day.
2. **What RIF models and requires:** camera-frame MLP over (position, normal) →
   per-channel α, times NeRF albedo, with a separately estimated volumetric
   medium; requires multi-view images, a rigid camera-light rig, **varying
   camera-to-scene distance**, and a full per-scene NeRF fit. Apache-2.0 code
   and public data.
3. **Stronger 2026 successor?** No. See §5.
4. **Physical models to test before neural fields?** Yes — NeLiS-style
   RID + Lorentzian falloff + ambient + rigid extrinsic, extended with two-path
   attenuation and normal-dependent shading. Both leading papers assume
   Lambertian surfaces anyway, so the physical model gives up little.
5. **Best representation of a dive light:** a **calibrated angular beam (RID)
   with a learnable near-field falloff**, not an ideal point source and not a
   pure inverse-square law. Escalate to a camera-relative field only on
   demonstrated residual structure.
6. **Combining ambient + artificial:** NeLiS's learnable constant ambient `A` is
   the minimal correct form; the physical model then has an ambient path
   (single attenuation, camera-to-point) plus an artificial path (two
   attenuations, light-to-point and point-to-camera). Do not merge them into
   one exponent.
7. **Which separate illumination from medium?** RIF explicitly does (separate
   `σ_attn`, `c_med`, `σ_bs` alongside the illumination MLP). Song's LUT
   explicitly does **not** — α and β are the *combined* effect. Family B
   separates them by construction.
8. **Which work on ordinary video restoration?** Families A, B and C produce a
   per-frame correction usable in a `FrameSequence -> FrameSequence` stage.
   **Family D does not** — it restores by re-rendering a fitted scene.
9. **Necessary calibration/acquisition:** rigid camera-light offset (measured);
   chart with black and white patches at ≥ 3 ranges and ≥ 3 frame positions;
   a white/grey planar target sweep for RID fitting; a few seconds of open
   water for the pure-water bound; and the *same* scene shot from enough poses
   that scene points are seen under different beam incidence. Everything else
   is optional.
10. **Parameters to persist:** see `PLAN.md` Week 6B.
11. **Escalation evidence:** see the trigger table in `PLAN.md` Week 6B.
12. **Placement:** Week 6B is correct — see §7.

---

## 7. Why Week 6B, and the one sequencing correction

**After Weeks 3–6, because every candidate depends on their outputs:**

- Song requires per-pixel **surface normals from a depth map**; family B
  requires `d_cam`, `d_light` and normals; RIF requires enough distance
  variation for the medium to be identifiable at all (§0.3).
- **Normals are a Week 6B preparation step, not a retroactive Week 3
  deliverable.** Week 3 was frozen around *range*. Normals are derived, and
  derived worse: `d(x,y) → ∇d → n(x,y)` amplifies high-frequency range noise, so
  a range field good enough for attenuation can still give normals too noisy for
  a `cos θ` term. Derive them before Week 6B, propagate the Week 3 range error
  budget through the gradient, quantify the normal uncertainty, and compare
  local-gradient normals against reconstructed-surface normals where available.
  This does not reopen Week 3.
- Families B and C are corrections *relative to* a baseline medium estimate.
  Without Week 5's backscatter and Week 6's attenuation there is no null
  hypothesis to beat.

**Before Week 7, because** Week 7 stress-tests a selected pipeline. Stressing an
unselected illumination model tests nothing. Week 7 keeps the broader taxonomy
(moving beams, multiple lights, shadows, mixed lighting, thermocline,
extrapolation beyond the calibrated beam); Week 6B answers only the
architectural question.

**The one correction to make now.** Weeks 5 and 6 will otherwise fit on the
frozen test set including `lights/LIGHTNIGHTDIVE.MP4`, and §0.1 predicts a
systematically wrong `β` there — roughly doubled for a camera-mounted light.
Weeks 5 and 6 must therefore **declare their clip scope as ambient/diffuse** and
record the artificial-light clip's failure as *expected input to Week 6B*, not
as a Week 5/6 regression. That is a two-line change, made in `PLAN.md`.

---

## 8. Rejected, with reasons

- **Replacing or extending the Phase 2B temporal evaluator.** Out of scope by
  instruction and by design: the evaluator must stay conservative, global and
  independent, or corrected outputs end up fitting their own judge.
- **Underwater NeRF/3DGS medium-decoupling methods** (SeaSplat, WaterSplatting,
  UW-3DGS, 3D-UIR, WaterClear-GS, Underwater360, R-Splatting, DualPhys-GS) —
  they decouple medium from appearance under *ambient* light, not a co-moving
  light cone, and all are per-scene novel-view-synthesis optimisers. Wrong
  problem and wrong output shape.
- **DarkGS itself** (as opposed to NeLiS) — 3DGS scene model, in-air, no
  medium, `NOASSERTION` licence. Take NeLiS (MIT); leave DarkGS.
- **SpotlessGS** and in-air relightable-3DGS generally — no medium.
- **Halo-separation image-space methods** — treat the artificial-light halo as
  a 2D artefact to suppress; no physical state, nothing for Weeks 5–6 to
  consume.
- **Full ray-traced light modelling with a Volume Scattering Function** — RIF
  rejects it for the right reason: it needs known light count, models and
  poses, joint estimation is *"challenging"*, and volumetric ray-tracing needs
  an accurate VSF. Far beyond what this project can calibrate.
- **BRDF estimation / non-Lambertian surface response** — both leading papers
  drop it deliberately. Revisit only if specular residual is demonstrated.
- **Shadow / visibility modelling** — a named gap in *both* RIF and NeLiS.
  Conditional challenger only, on demonstrated shadow residual.
- **Per-LED / multi-light individual calibration** — Song's opening argument is
  that it is *"time-consuming, error-prone and tedious"* and that only the
  integrated illumination in the viewing volume matters. A diver has one torch;
  this is moot.

---

## 9. Open items

1. Measured camera-to-light rigid offset for the actual dive-light mount. Family
   B's whole geometry depends on it.
2. Whether the dive light's beam is stable enough across battery state and
   across dives for one calibration to transfer. Cheap to test: repeat the
   white-target sweep at the start and end of a dive.
3. Whether the existing `lights/LIGHTNIGHTDIVE.MP4` clip has enough
   camera-to-scene distance variation for the medium to be identifiable at all
   (§0.3). If not, it is a stress clip only and cannot fit anything.
4. Whether RIF's Nerfstudio stack runs at all without CUDA. Assume not; it is
   the same rented-GPU line item as Week 3's learned arm.
