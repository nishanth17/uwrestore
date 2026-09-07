# Monocular depth for underwater restoration — landscape review

**Week 4A, pre-C2. Literature and release review only — no implementation.**
Compiled 2026-09-05. Coverage runs to approximately 2026-08-30.

**Superseded by MONO_DEPTH_FREEZE.md**

---

## THE ANSWER TO THE HEADLINE QUESTION

> *If I could integrate only the minimum scientifically complete set of monocular
> models before C2, which exact models/checkpoints should I run, and why?*

**Six families, nine checkpoints. Four run locally on the M4; only one needs a
rented GPU.**

```text
P0  facebook/map-anything-apache          1-view mode        Apache-2.0 / Apache-2.0
    THE CONTROL. Already integrated, already MPS-verified bitwise-reproducible,
    depth_along_ray == ||pts3d_cam|| already verified to 1.1e-5. Running the
    Week-3 model at N=1 isolates VIEW COUNT and nothing else - the only clean
    measurement of what dropping to monocular actually costs, which is the
    literal Week-4 question. Near-zero integration cost.

P1  Ruicheng/moge-2-vitl  +  Ruicheng/moge-vitl                  MIT / MIT
    Point-map geometry: range = ||P_cam|| exactly, with NO dependence on K -
    which matters because EIS makes this project's K provisional. Cleanest
    licence in the field. MoGe-1 vs MoGe-2 isolates metric conditioning within
    one architecture. Its failure modes are documented by three third parties.

P2  depth-anything/DA3MONO-LARGE  +  DA3METRIC-LARGE       Apache-2.0 / Apache-2.0
    The only relative foundation model whose ambiguity is SCALE-ONLY IN DEPTH -
    Class 2, the exactly-absorbable class Week 3 proved is free. Every other
    widely-used relative model is affine-in-disparity (Class 4). Its metric
    variant (metric = focal*net/300) degrades under focal error as a pure global
    scale - the benign failure. Requires rented CUDA: no MPS support exists.

P3  lpiccinelli/unidepth-v2-vitl14              CC BY-NC 4.0 / none declared
    THE FALSIFICATION TARGET. Won the only clean underwater monocular benchmark
    outright, and natively emits `radius` - metric ray range, this project's
    canonical quantity, measured rather than converted. Included specifically to
    test this review's own claim that its benchmark win is on an axis Week 3
    proved is free. Licence blocks deployment; research use only.

P4  lsxi77777/Wat3R                             Apache-2.0 / Apache-2.0
    The ONLY underwater specialist that clears the bar: verified weights, a
    fair-protocol single-view head-to-head against DA3/DAv2/VGGT/pi^3/
    MapAnything, Apache-2.0 throughout, and it runs on MPS. It is also a
    FRAGILITY PROBE: Week 3 already ran it (multi-view) and found it clearly
    worse on the cenote (20.1% vs 13.1%).

P5  depth-anything/Depth-Anything-V2-Small (+ -Large)   Apache-2.0 / Apache-2.0
    The reference floor. The only model with FIRST-PARTY Apple Silicon support,
    the substrate of every published underwater depth result, and the instrument
    for measuring how large the Class-4 penalty actually is. SPADE's globally
    aligned FLSea row - AbsRel 0.081 @<=10 m - is the number every other
    candidate must beat to justify its cost.
```

**Dropped from the supplied shortlist: WaterMono** — no licence on code or
weights, 9 stars / 0 forks / 4 open issues, disparity output, and its apparent win
over DA3 on FLSea is **in-domain** (it trains on FLSea); out-of-domain on Sea-thru
it **loses** (0.145 vs 0.111).

**Added that were not on the shortlist:** MapAnything 1-view (control), Wat3R
(the better underwater specialist), Depth Anything V2 (floor and Class-4
instrument).


---

# 1. Executive conclusions

**1. Ambiguity class beats benchmark rank, and it reorders the field.** Deriving
the invariance of the observation model (section 17.1) gives a strict ordering for
*this* application that no leaderboard shows:

```text
CLASS 1  raw metric                        no alignment needed
CLASS 2  scale-only in depth/range         EXACTLY absorbable (Week 3: 4.5e-13)
CLASS 3  affine (scale+shift) in depth     shift is NOT absorbable in the
                                           backscatter term; breaks d = 0
CLASS 4  affine in disparity/inverse depth  Mobius range deformation plus a
                                           FINITE DEPTH HORIZON - worst
```

The proof for Class 3 is short and decisive: with `d' = s*d + t`, matching
`B_inf(1 - exp(-beta_bs d))` for all `d` forces `k = exp(-beta'_bs t) = 1`, hence
`t = 0`. No refitting of `B_inf` or `beta_bs` absorbs an additive range shift.
Week 3's scale-invariance result **does not generalise to affine invariance**.

**2. Depth Anything 3 changed representation, and it matters more than its
accuracy.** DA3 predicts *depth* (as exponential depth), not disparity, and its
shipped aligner is `least_squares_scale_scalar` — **scale-only, no shift**. That
places it in Class 2 while the entire MiDaS/DA V2 lineage sits in Class 4. This is
the single most decision-relevant change in monocular depth since 2024 for a
physically-motivated pipeline.

**3. The one clean underwater benchmark scores the one axis this project does not
need.** Cai & Metzler (arXiv 2507.02148) is **raw metric with no alignment of any
kind** — verified by full-text search for `median`, `affine`, `align`, `cap`,
`crop`. UniDepth V2 wins it because it predicts scale from intrinsics. Week 3
proved global scale is absorbed exactly. **The benchmark's ranking is an E3
ranking and says almost nothing about shape.**

**4. Per-frame flicker is mostly ambiguity drift, not geometry error — the most
reassuring finding here.** DyFN (arXiv 2605.25308): one global scale+shift for a
whole sequence gives δ₁ **62.5**; per-frame alignment gives **99.8**. *"the primary
cause of temporal inconsistency is not geometric degradation but rather
frame-to-frame scale-shift variation."* Combined with (1), the fallback-video path
is much less risky than expected — **conditional on ambiguity class**. A Class-2
model that breathes in scale is nearly harmless; a Class-4 model that breathes in
its disparity offset is not.

**5. No released monocular model represents non-central (flat-port) imaging.**
Confirmed by two independent sweeps over nineteen-plus models. "Any camera" in
this literature means "any *central* projection". Combined with Phase 3B's finding
that projection *family* changed little while capacity changed much, and
WideDepth's measurement that a camera-**conditionable** pinhole model (Depth Pro,
+9.0% from 120°→195°) beat a camera-**general** one (UniK3D, +97%), the better
lever is **supplying a known FOV to a strong conventional model**, not buying an
any-camera architecture.

**6. Underwater specialisation is condition-specific — now observed three times
independently.** Week 3's Wat3R-Ren (worse on the cenote, 20.1% vs 13.1%); Cai &
Metzler's synthetic fine-tune (helps SQUID and Red Sea, flat-to-worse on
FLSea-Canyon); and the mechanism in section 20.4. **Working hypothesis for Week
4A: underwater-trained models are MORE water-type fragile, not less**, because
specialisation sharpens reliance on the appearance cue.

**7. Degradation as a false depth cue is real, physically grounded, and
unmeasured.** Longer range monotonically implies more attenuation and backscatter,
so appearance genuinely encodes distance — the underwater dehazing tradition
inverts exactly this. **No paper measures what happens to a modern model's
geometry under controlled, geometry-preserving underwater appearance
perturbation.** There is no underwater RoboDepth; the modern-model robustness
benchmark (PDE) has **no** haze/scattering perturbation, while the one that has
fog (RoboDepth) predates every modern model. **The two halves of the literature
never meet, and Week 4A's planned experiment is novel.** A circularity hazard
compounds it: estimating `d` from appearance and then using `d` to remove that
appearance is self-referential, and nobody has measured it.

**8. Licence and checkpoint verification were unexpectedly discriminating.**
DA V2 Giant **was never released**; DA V2 Large/Base are **CC BY-NC**; Depth Pro's
weights are **research-only, revocable, and bind fine-tunes** while its README
points at the wrong licence; Marigold's model licence is an **unfilled template**;
UniK3D and Dens3R are **CC BY-NC-SA (viral)**; and **Metric3D, UniDepth V2, UniK3D
and UniDAC all declare no checkpoint licence at all**. Week 3's Water-VGGT finding
— an "underwater" checkpoint **bitwise identical to `facebook/VGGT-1B`** —
justified this standard, and applying it removed more candidates than accuracy did.

**9. The generative family was substantially refuted from inside.** E2E-FT (WACV
2025 Oral) showed the multi-step advantage was largely a **scheduler bug** and that
fine-tuning Stable Diffusion directly matches Marigold, ~200× faster: *"casting
depth estimation as conditional image generation is not more effective than simple
end-to-end fine-tuning."* Pixel-Perfect Depth relocated the remaining sharpness
advantage to the **VAE**, not the sampler. And DepthMaster's diagnosis names the
specific underwater hazard: diffusion pretraining *"induce[s] the model to
prioritize texture details over structure"*, producing **"pseudo-textures"** —
which underwater would convert backscatter speckle and marine snow into geometry.
**No generative model earns a primary slot.**

**10. Metric scale is unsolved across the whole current generation, and it fails
in the far field.** MetricScenes (arXiv 2606.02379): *"MoGe-2, DepthAnything v3 and
Metric3D v2 exhibit scale-collapse behavior, consistently underestimating the size
of far-field structures"*; Arc de Triomphe, GT **44.8 m**, MoGe-2 **18.8 m**. Root
cause is training data *"hardware-constrained to homogenous vehicle-captured LiDAR
or short-range indoor scans."* FoundationGeo adds the mechanism: *"the network may
internalize a **biased implicit focal prior**, leading to systematic over- or
under-scaling on unseen optics."* **A GoPro is out-of-distribution on two counts —
short focal and the ~1.33× refractive flat-port shift — so expect raw metric output
to be unreliable and relative geometry to survive.** Those landmark measurements
are at hundreds of metres; the *direction* transfers to reef distances, the
*magnitude* does not, and testing that is a Week-4A job.

**11. There is no Depth Anything 4, no Depth Pro 2, no UniDepth V3, no Metric3D
v3.** The one arXiv paper titled "Depth Anything V4" is by unrelated authors and
was **withdrawn two days after posting, flagged "Major errors in research."**
Two shortlist entries, **CD-UDepth and UDepthDiff, turned out to be journal-only
and absent from arXiv**, with no code or weights. **"DepthDive" does not exist**
(arXiv full-text search: totalResults = 0).

**12. What Week 4A cannot do.** No underwater depth-GT dataset uses a flat-port
wide-FOV camera — every one uses a **dome port, chosen explicitly to eliminate
refraction**. The only verified GoPro underwater dataset (SubPipe) has **no dense
depth GT**. Public data can validate plumbing, relative shape and range-dependent
error growth. It cannot establish that any model works on this footage. That is
C2's job, and section 26 keeps it there.


---

# 2. Project-specific depth requirements

## 2.1 The quantity that is actually needed

The pipeline needs **`water_path_length`**: the distance light propagates through
water between the scene point and the sensor. For a central camera this is range
along the viewing ray. For the refractive path it is the distance from the
water-interface exit point to the scene point.

No monocular model in this review predicts `water_path_length`. Every candidate
predicts something that must be *transformed* into it, and the transformation is
exact for some models and approximate for others. Each candidate is therefore
tagged:

```text
measured               native output is range along the viewing ray
transformed_exactly    exact conversion exists (may be conditional on K)
approximated           conversion involves an assumption that is not exactly true
```

`z-depth`, `Euclidean camera-centre range`, `range along a viewing ray`,
`inverse depth`, `disparity`, `relative depth`, `3-D point map`, `ray direction`,
`ray origin` and `water_path_length` are kept distinct throughout this document.

## 2.2 What "good enough" means, quantitatively

Week 3 measured downstream restoration sensitivity directly, which replaces
benchmark rank as the acceptance criterion. Local relative range error at which
worst-channel restored-radiance error reaches 5%:

```text
clear oceanic     31%  @ 1 m      12%  @ 3 m     8.5% @ 8 m
coastal                           9.4% @ 3 m     6.1% @ 8 m
turbid                                           1.0% @ 8 m    0.3% @ 12 m
```

Three readings of this table matter for model selection.

1. **The budget is generous near, and brutal far and turbid.** A model that is
   excellent in the near field and biased at range fails exactly where the budget
   is tightest. Near/far systematic bias is therefore a first-class measurement,
   not a diagnostic afterthought.
2. **Because beta differs per channel, a local range error is a spatially varying
   COLOUR error**, not a brightness offset. This is why "the depth map looks
   plausible" is not an acceptance test, and why Invariant 5 applies with force.
3. **A single global multiplicative error costs nothing** (Week 3: absorbed to
   `4.5e-13`). So generic metric-depth leaderboard rank, which is dominated by
   global scale accuracy, is close to *irrelevant* to the primary criterion —
   while being highly relevant to the secondary criteria in 2.3.

## 2.3 When metric scale does matter

Raw metric performance is not the primary criterion but it is not optional
either. It becomes load-bearing when:

- physical coefficients are transferred or shared across clips;
- absolute water properties are interpreted physically;
- artificial-light modelling introduces distance-dependent falloff (week 6);
- camera-to-light geometry is used;
- cross-clip physical parameters are compared.

So metric capability is best treated as a **separable axis**: a model can be
selected for structure and separately assessed for whether its raw metric output
is usable. Section 17.2's E1/E2/E3 split exists precisely so this is not collapsed.

## 2.4 The error taxonomy that decides selection

Dangerous (ranked, roughly, by how badly they violate the budget in 2.2):

```text
nonlinear range compression/expansion       (Class-4 alignment produces this by construction)
near correct / far biased                   (hits the tightest part of the budget)
spatially varying multiplicative error      (becomes a spatially varying colour error)
local range deformation
incorrect foreground/background ordering
incorrect discontinuities and object-edge errors
temporal depth breathing                    (destabilises parameter estimation)
local failures hidden by good global scale
```

Harmless or nearly so:

```text
global multiplicative scale error           (exactly absorbed)
```

## 2.5 Hard operational constraints

From CLAUDE.md and the Week-3 record, these are constraints, not preferences:

- **Strict single-frame inference** for the fallback-video case: no neighbouring
  frames, no hidden temporal state, no multi-view path, no Week-3 pose or depth
  input, no cached cross-frame features.
- **Determinism.** Week 3 established that all three dense candidates are
  *bitwise* reproducible on MPS float32 with a fixed seed, and used that to argue
  every reported difference was method difference with no noise floor to clear.
  A monocular candidate that cannot meet this bar forfeits that argument and
  needs an explicitly measured noise floor before any of its deltas are readable.
- **Bounded memory / streaming** (Invariant 9): the model runs as a pass that
  persists outputs and exits.
- **Local execution preferred.** Apple M4, 24 GB unified memory, no CUDA. Week 3
  concluded "nothing observed justifies making CUDA a permanent project
  requirement". GPU rental remains available for a scientifically compelling
  model, so CUDA-only is a cost, not a disqualifier — but a CUDA-only *default*
  would break the local reproducibility loop the project runs on.
- **Licence.** Week 3 selected MapAnything partly because it was the only dense
  candidate with Apache-2.0 code *and* an Apache-2.0 checkpoint. The same
  standard should be applied here, and section 7 shows it is unexpectedly
  discriminating.


---

# 3. What Week 3 already established

Only the findings that constrain Week 4 are repeated here. Full record:
`LOG.md` (2026-08-31 entries) and `experiments/week3_geometry/FINDINGS.md`.

## 3.1 The provisional deployment path

```text
dense range     MapAnything          (Apache-2.0 code AND Apache-2.0 checkpoint)
cross-check     COLMAP / SIFT
```

MapAnything was chosen **on licence, validity signalling, memory cost and
verified output semantics — not on geometric accuracy**, where vanilla VGGT edges
it on four of six clips. Its `depth_along_ray == ||pts3d_cam||` was verified to
`1.1e-5`, so conversion to the project's canonical range quantity is exact.

**Named condition:** MapAnything's scale collapses on dynamic content — 6.6x
per-frame scale wander and a 130% range swing on the dynamic-diver clip, and this
failure is **view-count-independent** (16 views reproduces it), so shortening the
temporal window is not a workaround.

## 3.2 The scale-invariance result (the most reusable artifact)

With coefficients freely fitted in-clip, a global range scale error is absorbed
**exactly** (`max |dJ/J| = 4.5e-13` over a sweep to `s = 3.2`). Local error is
not; see the budget table in section 2.2. Section 17.1 extends this result and
shows that it does **not** generalise to an additive shift.

## 3.3 The epistemic situation: C2 has not been captured

Week 3's evidence is MapAnything, vanilla VGGT, Wat3R-Ren, COLMAP/SIFT and
classical perturbations. **None of these is independent ground truth.** Phase 3B
sharpened this considerably:

- Instability tracks **SIFT observation density** far more closely than the
  tested parallax proxies. Stable clips carry 4358-14440 observations/image;
  unstable ones 1099-2099.
- Consequently **a large part of Phase 3A's cross-family disagreement on the
  low-texture clips is the classical reference's own ill-conditioning**, not only
  the dense candidates. Two low-texture clips from the *same camera and capture
  mode* spread their recovered focal 1.113x and 1.294x across central camera
  models, against 1.026x and 1.056x for the high-observation clips.
- Whole-pipeline reruns are not exactly reproducible: 29 differing verified
  matches out of 65756 (0.04%) move `wreck_05`'s range field 3.3% median.

**Therefore, and this must survive into Week 4A:** cross-method agreement is
evidence of *consistency*, not automatically of *correctness*, and disagreement
with COLMAP on a low-observation clip is not evidence against the monocular model.

The `< ~2000 SIFT observations/image` figure is a **heuristic warning trigger
learned from this dataset, not a validity boundary**.

## 3.4 Findings that transfer directly to monocular candidate selection

**Underwater adaptation did not pay.** VGGT -> Wat3R-Ren was condition-specific
with no material win: better on one wreck (3.5% vs 4.8%), tied on a second and on
the reef swim-through, and **clearly worse on the cenote** (20.1% vs 13.1%, the
worst dense result anywhere). Per the standing rule this is not a reason to look
for another underwater-adapted model — but it *is* a calibrated prior for how
much to expect from underwater specialisation in Week 4.

**"Underwater-adapted" release claims need checkpoint-level verification.**
Week 3 inspected Water-VGGT and found its advertised pretrained model has a
**model state bitwise identical, tensor for tensor, to `facebook/VGGT-1B`**
(1797/1797 tensors, max abs difference 0.0, zero underwater-specific modules).
Its geometry model carries no underwater adaptation at all. This is the strongest
argument in the whole project record for the verification standard section 7
applies: *verify the checkpoint, not the paper*.

**Confidence is close to uncalibrated.** MapAnything's low-confidence pixels are
only **1.07x** worse than its high-confidence ones. A monocular model's confidence
map must clear a measured bar, not be trusted because it exists.

**Preprocessing silently destroys field of view.** The VGGT family discards ~44%
of the vertical FOV on portrait clips — measured, and shown in Phase 3B to be a
family preprocessing artefact rather than a footage property.

**Determinism is achievable and was achieved.** MapAnything, VGGT and Wat3R-Ren
are all bitwise reproducible across repeat runs on MPS float32 with a fixed seed.

**The camera is characterised.** GoPro HERO9 Black, Wide, ZFOV 105.383 deg,
**EIS on in every clip**, `PRJT = GPRO` — a documented, unresolved geometry
confound for every Week-3 number and for every Week-4 number.

## 3.5 What Week 3 says about adding more models

Phase 3A's closing judgement: adding another geometry model, or renting CUDA for
the unexecuted candidates, "buys more disagreement between unanchored hypotheses
and should wait". Week 4A is a different question — it is selecting a *fallback
capability* the project does not yet have at all, so a bounded bakeoff is
justified — but the same discipline applies to its size. That is the reasoning
behind the deliberately small primary set in section 22.


---

# 4. State of monocular depth through September 2026

## 4.1 The field in one paragraph

Monocular depth is no longer a benchmark race between architectures. Since
mid-2025 the frontier has been **what is predicted** (scalar depth vs point maps
vs ray fields), **in what representation the ambiguity lives** (disparity vs
depth vs point space), **which camera the model assumes**, and **where absolute
scale comes from**. Accuracy on NYU/KITTI has saturated to the point where
published deltas are frequently smaller than protocol differences. For this
project that is convenient: the axes the field now argues about — output
semantics, camera modelling, scale recovery — are precisely the axes that decide
whether a model is usable in a physical restoration pipeline, and they are
readable from papers and code rather than from leaderboards.

## 4.2 The six things that are true as of September 2026

**1. There is no Depth Anything 4.** The `DepthAnything` GitHub org holds three
repos; the HuggingFace org tops out at DA3. The one arXiv paper bearing the name
(**2608.18388**) is a 4D-Gaussian-splatting method by unrelated authors, and it
was **withdrawn two days after posting, flagged "Major errors in research."**
Similarly: **no Depth Pro 2, no UniDepth V3, no Metric3D v3** — all searched, all
absent. **Depth Anything 3 (ICLR 2026), UniDepth V2 (TPAMI), MoGe-3 (July 2026)
and the ECCV-2026 cohort are the current frontier.**

**2. The ambiguity moved from disparity space to depth space.** DA3's teacher
outputs scale-shift-invariant **depth** (predicted as *exponential* depth to
recover near-field sensitivity), explicitly contrasted against DA2's
scale-shift-invariant **disparity**. This is the most consequential single change
in the field for physically-motivated downstream use (section 17.1).

**3. Point maps won the representation argument for geometry.** MoGe-1/-2/-3,
FoundationGeo, PointDiT, MapAnything, VGGT, pi^3 and Dens3R all predict 3D points
or rays rather than a scalar. The practical payoff for this project is direct:
`range = ||P_cam||` needs no intrinsics.

**4. The generative detour has been substantially walked back by its own
community.** E2E-FT showed the multi-step advantage was largely a scheduler bug
and that fine-tuning Stable Diffusion directly matches Marigold's protocol;
Lotus, GenPercept, DepthMaster, Lotus-2, DVD and PointDiT have each moved toward
deterministic single-step or non-diffusion formulations. Pixel-Perfect Depth
relocated the remaining sharpness advantage to the **VAE**, not the sampler
(section 12).

**5. Metric scale is the field's acknowledged unsolved problem, and the failure
is in the far field.** *"Honey, I Shrunk the Arc de Triomphe!"* (Xiangli, Chen,
Tsang, Snavely, Cornell; arXiv **2606.02379**, 2026-06-01/26) [PAPER VERIFIED]
introduces **MetricScenes** and documents **scale collapse** — models
*"drastically underestimating the size of distant landmarks and expansive
landscapes."* Verbatim: *"MoGe-2, DepthAnything v3 and Metric3D v2 exhibit
scale-collapse behavior, consistently underestimating the size of far-field
structures"*; *"UniDepth v2 produces more realistic scales but still deviates"*;
*"DepthPro often fails to recover absolute scale, producing results that are
orders of magnitude smaller than reality."* Measured: Arc de Triomphe width, GT
**44.8 m**, MoGe-2 **18.8 m** (>2x small). Root cause: metric training data is
*"hardware-constrained to homogenous vehicle-captured LiDAR or short-range indoor
scans."*
> **Calibration for this project:** those measurements are at hundreds of metres,
> well outside this pipeline's 1-15 m working range, so the *magnitude* does not
> transfer. The **direction** does — systematic far-field underestimation is
> exactly the "near correct, far biased" failure that hits the tightest part of
> the section-2.2 budget. It is a named hypothesis to test, not an established
> result at reef distances. The DA3 attribution is additionally
> **qualitative only** — no DA3 far-field number appears in the paper's prose
> [`da3_scale_collapse_quantitative_status_unverified`].

**6. Camera generality became a research programme, and it is all central.**
UniK3D, Depth Any Camera, UniDAC (CVPR 2026), DA360, DA^2, PaGeR,
DepthMaster-2026, VGGT-360, RayTun3R. Every one models an arbitrary **central**
projection. **No released model represents non-central (refractive flat-port)
imaging** — confirmed by two independent sweeps over nineteen-plus models
(section 11.1).

## 4.3 What the field still does not do

Four gaps, all verified absent, all directly load-bearing here:

```text
no underwater RoboDepth            nobody sweeps turbidity/backscatter at FIXED
                                   geometry and reports a degradation curve for
                                   foundation models
no depth-before-vs-after-          despite haze being a deliberately exploited
   restoration measurement         underwater depth cue (Varghese, ICCV 2023)
no underwater temporal-stability   zero papers, for any depth model
   evaluation
no OOD-calibrated confidence       the best UQ synthesis (arXiv 2501.08188) is
                                   in-distribution only
```

And a fifth, structural: **the two halves of the robustness literature never
meet.** The **PDE** benchmark (arXiv **2507.00981**) evaluates exactly the right
nine models (MiDaS, DA, DA V2, ZoeDepth, UniDepthV2, Metric3D V2, Marigold,
DepthPro, MoGe) across 12 perturbations — but contains **no fog/haze/scattering
perturbation at all**. **RoboDepth** (NeurIPS 2023) *does* include fog but
evaluates only 2019-2023 architectures — **no MiDaS, no Depth Anything, no
Marigold, no DepthPro, no UniDepth, no Metric3D.** The modern models have never
been tested under participating media, and the participating-media benchmark has
never seen a modern model.

That gap is the space Week 4A occupies.


---

# 5. Major technical advances, 2023-2026

Each advance is graded on the only question that matters here:
**does it change this project's outcome, or is it a generic-benchmark
improvement?**

| Advance | What changed | Matters here? |
|---|---|---|
| **Large vision-foundation encoders** (DINOv2 -> DINOv3) | DINOv3 initialisation is now standard (DA3, FoundationGeo, UniDAC, PointDiT). UniDAC ablates DINOv3 > DINOv2, attributed to RoPE compatibility | **Indirectly.** Better features mean better OOD structure, which is what this project needs from a monocular model. But no encoder has seen water |
| **Relative-depth foundation models at scale** (DA V1/V2's 62M pseudo-labelled images) | Robust open-domain relative depth became commodity | **Yes** — this is why DA V2 is the substrate of every underwater result and a credible reference floor |
| **The disparity -> depth ambiguity shift** (DA3) | Affine invariance moved from `1/z` to `z`; DA3's shipped aligner is scale-only | **Yes — the single most decision-relevant advance in this review.** Class 4 -> Class 2 (section 17.1) |
| **Exponential-depth parameterisation** (DA3) | Recovers near-field sensitivity lost when leaving disparity | **Yes** — the near field is where the budget is loosest but the scene content densest |
| **Universal metric depth** (ZoeDepth -> Metric3D -> UniDepth -> UniDepth V2) | Zero-shot metric via canonical-camera or camera-conditioning | **Partly.** Wins the only underwater benchmark, but that benchmark scores E3, and Week 3 proved E3 is nearly free (section 14.1) |
| **Camera-conditioned models** (Metric3D CSTM, UniDepth camera module, DA3 `focal/300`, MoGe `--fov_x`, Depth Pro `f_px`) | Intrinsics as a first-class optional input | **Yes** — this is the P1 convention (section 16.4) and, per WideDepth, a better FOV lever than camera-general architecture |
| **Point maps instead of scalar depth** (MoGe, DUSt3R lineage, FoundationGeo) | Geometry in camera coordinates, no intrinsics needed to get range | **Yes** — removes the `K`-dependence of the z-depth -> range conversion (section 17.4) |
| **Explicit range + unit-ray decomposition** (FoundationGeo) | `d = \|\|p\|\|_2`, `r = p/\|\|p\|\|_2` | **Yes** — the project's canonical quantity, natively |
| **Joint ray/intrinsics/depth prediction** (DA3's ray map + RQ decomposition) | Camera recovered post-hoc from the geometry | **Marginal.** Useful sanity check against measured GoPro intrinsics; not a deliverable |
| **Any-camera modelling** (UniK3D, DAC, UniDAC, PaGeR cubemaps) | Fisheye/ERP/spherical handled natively | **Conditionally.** All central; WideDepth suggests camera-*conditionable* beat camera-*general* on FOV robustness (section 11.6) |
| **Discriminative vs generative** | The generative advantage was substantially refuted from inside the family (E2E-FT, Lotus, GenPercept, DepthMaster, PointDiT) | **Yes, negatively** — it removes a whole family from the primary set (section 12) |
| **Synthetic-scale training + dense synthetic GT** | Dense synthetic labels taught thin structure that sparse LiDAR could not | **Yes** — this, not diffusion, is the real source of boundary sharpness; and it is the recipe underwater adaptation copies |
| **Pseudo-labelling and distillation** | DA V1/V2's data engine; MetaDepth-CPU; DepthART; ZipDepth | **Cautionary.** Underwater, it produced pseudo-GT datasets (USOD10K, BlueDepth) that are routinely mistaken for ground truth (section 14.3) |
| **Uncertainty prediction** (UniDepth V2, DA3 `conf`, GNLL fine-tuning) | Confidence heads became standard | **Not yet.** No OOD calibration evidence exists for any of them (section 18) |
| **Multi-task geometric representations** (depth + normals + masks + intrinsics) | MoGe-2/-3, Metric3D v2, FoundationGeo, OptiGeo, PaGeR all emit normals | **Yes, latently** — week 6's illumination modelling wants normals, and getting them free from the range pass is a real saving |
| **Adapter / LoRA tuning** | Endoscopy, weather, underwater stereo all converged on PEFT rather than full fine-tuning | **Yes, as Week 4.5** (section 21) |
| **Inference-time refinement / TTA** | The leading depth "TTA" is sparse-point *rescaling* (arXiv 2412.14103, IROS 2025) | **Yes, negatively** — it fixes global scale, which Week 3 proved is free (section 21.2) |
| **Temporal/video depth** (DepthCrafter, VDA, RollingDepth, StableDPT, DyFN) | Per-frame flicker measured, and its **cause localised to per-frame scale-shift re-estimation, not geometry** (DyFN) | **Yes — the most reassuring finding in this review** (section 19.1) |
| **Efficiency** (ZipDepth ECCV 2026, DepthART ACM MM 2026, MetaDepth-CPU 2.8 MB at 15-30 FPS on phone CPUs) | Foundation depth became deployable on mobile | **Latently.** Relevant if per-frame cost ever binds; MetaDepth-CPU is **relative depth only** and **not released** |

## 5.1 The advances that do NOT matter here, and why

Recorded so they are not revisited:

- **Language-conditioned metric scale** — TR2M (arXiv **2506.13387**, CVPR 2026),
  *Language as Prior, Vision as Calibration* (arXiv **2601.01457**), VGLD (arXiv
  **2505.02704**). Recover scale from text descriptions of the scene. There is no
  text channel here, and the mechanism has no underwater grounding.
- **Depth from defocus** — *Zero-Shot Depth from Defocus* (arXiv **2603.26658**,
  ECCV 2026), *Repurposing Marigold ... via Defocus Blur Cues* (arXiv
  **2505.17358**). Both need aperture control or dual-aperture capture. A GoPro
  has a fixed aperture and a near-hyperfocal lens.
- **Depth completion / sparse-prompted depth** — PromptDA (CVPR 2025, `assert
  prompt_depth is not None`), Prior Depth Anything, MTD, Any-to-Full, OASIS-DC.
  All consume sparse depth at inference. Their headline gains (e.g. DA V2 on
  DIODE 0.260 -> 0.093 AbsRel) **must never be read as zero-shot monocular
  numbers.** They become relevant only if the project decides to feed Week-3
  sparse points into the monocular pass — which is section 23's scale trigger,
  not Week 4A.
- **Radar/thermal/event fusion** — no such sensor exists in this pipeline.
- **Multi-layer / transparency ambiguity** — *One Scene, Two Depths* (ECCV 2026),
  MD-3k, Laplacian Visual Prompting. A different meaning of "ambiguity"
  (section 20.3); relevant at most to the glass port and the water surface.


---

# 6. Candidate-family taxonomy

Grouped by the **scientific hypothesis** each family tests, not by architecture.
This is the grouping that determines redundancy, and therefore the size of the
primary set.

```text
H1  "Universal metric depth generalises underwater"
    UniDepth V2, Metric3D v2, DA3 Metric, Depth Pro, ZoeDepth, UniDAC
    Discriminator: raw metric error (E3) AND far-field bias, on underwater data

H2  "Explicit point-map geometry preserves shape better, and gives range natively"
    MoGe-1/-2/-3, FoundationGeo, OptiGeo, PointDiT, (MapAnything/VGGT/pi^3 as
    multi-view relatives already characterised in Week 3)
    Discriminator: oracle-aligned local shape error (E1) + range-conversion
    exactness

H3  "A large relative-depth foundation model sets the structural ceiling"
    DA V2, DA3 Mono, MiDaS
    Discriminator: E1 after alignment in the model's OWN native representation

H4  "Underwater adaptation matters more than architecture"
    Wat3R, WaterMono, UDepth, CD-UDepth, UMono, Tree-Mamba, UW-Adapter,
    Cai & Metzler's synthetic fine-tune
    Discriminator: does the specialist beat a zero-shot foundation model on
    OUT-OF-DOMAIN water, under a common alignment?

H5  "Camera-general modelling matters for a wide-FOV GoPro"
    UniK3D, UniDAC, Depth Any Camera, PaGeR, DepthMaster-2026, DA360, RayTun3R
    Discriminator: error as a function of radial image position / FOV, and the
    P0 vs P1 vs P2 preprocessing comparison

H6  "Generative priors materially improve thin / detail geometry"
    Marigold, Lotus, Lotus-2, DepthFM, GenPercept, PointDiT, Pixel-Perfect Depth
    Discriminator: boundary metrics on thin structures, at equal determinism cost

H7  "Inference-time adaptation removes water-domain shift without breaking
     frame independence"
    depth-rescaling (2412.14103), ReDepth Anything, online self-supervised
    Discriminator: does it help under PHOTOMETRIC shift (not just scale), while
    staying deterministic and single-image?
```

## 6.1 Redundancy analysis — which of these collapse

**H6 collapses into H2/H3.** The family's own literature relocated its advantage
to dense synthetic supervision and pixel-space decoding, both of which
discriminative models now have (section 12.2-12.3). Testing H6 with a diffusion
model would cost determinism (Invariant 3) and 40 GB of VRAM to answer a question
its own community has largely answered. **No primary slot.**

**H7 collapses into a nuisance parameter.** The leading depth-TTA method recovers
*global metric scale* — which Week 3 proved is absorbed exactly. It answers a
question this project does not have (section 21.2). **No primary slot.**

**H5 is not yet triggered.** Phase 3B found that among central camera models,
well-conditioned clips were stable to <= 1.5% across four projection families, and
the difference was **capacity, not projection family**. WideDepth independently
suggests a camera-*conditionable* pinhole model beat a camera-*general* one on FOV
robustness by ~10x. The better lever is supplying a known FOV to a strong
conventional model. **Conditional challenger, not primary** (section 11.6).

**H1 and H3 must be tested together, not separately.** The most efficient
instrument is a **paired checkpoint from one architecture** — DA3 Mono vs DA3
Metric, or FoundationGeo Stage-I vs Stage-II — which isolates the
relative-vs-metric variable with the backbone, training data and preprocessing
all held constant. Testing H1 with UniDepth and H3 with DA V2 confounds the
variable with everything else about the two models.

**H2 and H4 survive as independent primary hypotheses**, and H4 has an unusual
advantage here: the project already holds independent evidence about its leading
candidate (section 13.2).

## 6.2 The axes that actually separate candidates

Ranked by how much they move the decision:

```text
1. AMBIGUITY CLASS + native representation     (s.17.1) - dominates everything
2. RANGE SEMANTICS: measured / exact / approx  (s.2.1, s.17.4)
3. Verified checkpoint + licence on BOTH       (s.7) - unexpectedly discriminating
4. Runs on Apple M4 / MPS, deterministically   (s.2.5) - gates the daily loop
5. Underwater evidence under a FAIR protocol   (s.14)
6. Near/far systematic bias                    (s.4.2 item 5)
7. Confidence, only if measurably separating   (s.18)
8. Generic benchmark rank                      - near-irrelevant, listed last
```

Note that axes 1-4 are readable from papers, code and model cards **before any
inference is run**. That is what makes a bounded Week-4A bakeoff possible: the
literature can eliminate most of the field on semantics and availability, leaving
measurement to decide only between genuinely distinct hypotheses.


---

# 7. Comprehensive candidate / release table

Verification tags: **P**=paper, **C**=code repo loads, **K**=checkpoint verified
present, **L**=licence read from a primary source. `?` = unverified/absent.
Ambiguity class per section 17.1. "Range" = how `water_path_length` is obtained.

## 7.1 Primary-tier and near-tier candidates

| Model / checkpoint | Venue & ID | P C K L | Code lic | Ckpt lic | Native output | Class | Range | MPS? |
|---|---|---|---|---|---|---|---|---|
| **MoGe-2** `Ruicheng/moge-2-vitl` (326M) | arXiv 2507.02546 | ✔✔✔✔ | MIT | **MIT** | metric point map + z-depth + mask + intrinsics (+normals variant) | **1** | `\|\|P_cam\|\|` **exact, no K** | likely (untested) |
| **MoGe-1** `Ruicheng/moge-vitl` (314M) | arXiv 2410.19115, CVPR'25 Oral | ✔✔✔✔ | MIT | **MIT** | affine-invariant point map + FOV | **3** (train: scale + z-shift; output claimed shift-resolved — **verify**) | `\|\|P_cam\|\|` | likely |
| **MoGe-3** `Ruicheng/moge-3-vitl` (370M) / `-vitg` (1.25B) | arXiv 2607.17967 | ✔✔✔✔ | MIT | **MIT** | metric point map + normals | **1** | exact | **NO** (FlexGEMM/Triton) |
| **DA3MONO-LARGE** (0.35B) | arXiv 2511.10647, **ICLR 2026** | ✔✔✔✔ | Apache-2.0 | **Apache-2.0** | **z-depth** (exponential-depth param) + `depth_conf` + ray | **2** (shipped aligner is scale-only; teacher described as scale+shift — **verify**) | `D * \|\|K⁻¹p\|\|` **exact given K** | **NO** (xformers, cuda hardcoded, PR abandoned) |
| **DA3METRIC-LARGE** (0.35B) | same | ✔✔✔✔ | Apache-2.0 | **Apache-2.0** | metric z-depth, `= focal * net_out / 300` | **1** | exact given K | **NO** |
| **UniDepth V2 ViT-L** `lpiccinelli/unidepth-v2-vitl14` | arXiv 2502.20110, **TPAMI** | ✔✔✔✗ | **CC BY-NC 4.0** | **none declared** | pseudo-spherical: **`radius` (metric ray range)** + `depth` (z) + points + intrinsics + uncertainty | **1** | **measured natively** | Linux+CUDA 11.8 documented |
| **Wat3R** `lsxi77777/Wat3R` (4.76 GB) | arXiv 2607.08772, **ECCV 2026 Oral** | ✔✔✔✔ | Apache-2.0 | **Apache-2.0** | point maps + depth + conf + extrinsics/intrinsics | **3** (LSQ scale **and** shift) | `\|\|P_cam\|\|` | **YES** — VGGT family, Week 3 ran it bitwise-reproducibly on MPS fp32 |
| **DA V2 Small** (24.8M) | arXiv 2406.09414, **NeurIPS 2024** | ✔✔✔✔ | Apache-2.0 | **Apache-2.0** | affine-invariant **inverse depth** | **4** | via fitted disparity affine | **YES — first-party** |
| **DA V2 Large** (335M) | same | ✔✔✔✔ | Apache-2.0 | **CC BY-NC 4.0** | same | **4** | same | **YES** |

## 7.2 Challenger tier

| Model | Venue & ID | P C K L | Code lic | Ckpt lic | Output / Class | Note |
|---|---|---|---|---|---|---|
| **FoundationGeo** `mxliu-hku/FoundationGeo-1.1` (314M) + `-Base-1.1` (313M) | arXiv 2607.11588, **ECCV 2026** | ✔✔✔✔ | MIT | **MIT** | **native Euclidean range + unit ray**; Stage-I affine (3), Stage-II metric (1) | Best native semantics found; ⚠️ LICENSE copyright line says "Microsoft Corporation" (template artifact); GitHub API reports NOASSERTION |
| **OptiGeo** `mxliu-hku/OptiGeo` (**30M**) | arXiv 2608.29881 (2026-08-30) | ✔✔✔✔ | MIT | **MIT** | metric depth + point map + mask + **estimated FOV** | Targets transparent/reflective/specular; smallest credible local option |
| **UniDAC** `girish1511/UniDAC` (1.42 GB) | arXiv 2603.27105, **CVPR 2026** pp.26953-26963 | ✔✔✔✗ | **MIT** | **none declared** | metric, **internally Euclidean** (`# convert depth from zbuffer to euclid`) | ⚠️ **Requires GT camera parameters**; trained 100% on perspective; loses to UniDepth on plain perspective |
| **Depth Pro** `apple/DepthPro` | arXiv 2410.02073, **ICLR 2025** | ✔✔✔✔ | Apple sample-code | **`apple-amlr` research-only, revocable, binds fine-tunes** | metric z-depth; accepts `f_px` | **Most FOV-robust measured** (+9.0% vs DA V2 +166%, 120→195°); worst underwater raw metric (SQUID 3.2185); ⚠️ pass `torch.tensor(f_px)`, not a float |
| **UniK3D** `lpiccinelli/unik3d-vitl` | arXiv 2503.16591, CVPR 2025 (repo-asserted) | ✔✔✔✗ | **CC BY-NC-SA** (viral) | **none declared** | spherical-harmonic ray field, metric | +97% AbsRel 120→195° — "any-camera" ≠ FOV-robust |
| **RayTun3R** | arXiv 2607.02711 | ✔✗✗✗ | ? | ? | adapter (**10,752 params**) for fisheye 110-200° on DUSt3R/MASt3R/VGGT/π³/**DA3** | Needs a short temporal segment to fit — but it is a **per-camera**, not per-frame, fit; could be frozen offline |
| **PointDiT** `haofeixu/pointdit` | arXiv 2607.02515, **ICML 2026** | ✔✔✔✔ | Apache-2.0 | Apache-2.0 | affine-invariant point map, z from z-component | **3** | ⚠️ requires **gated DINOv3** weights at inference |
| **Lotus-2** `jingheya/Lotus-2` | arXiv 2512.01030 (no venue) | ✔✔✔✔ | Apache-2.0 | apache-2.0 (⚠️ FLUX.1-dev non-commercial inheritance unstated) | affine-invariant **disparity** | **4** | Deterministic by design; ⚠️ **requires ≥40 GB VRAM** |
| **Metric3D v2** | arXiv 2404.15506, TPAMI 2024 | ✔✔✔✗ | BSD-2 | **never stated** | metric z-depth + normals | **1** | ⚠️ **intrinsics REQUIRED** (fallback = 9-value focal sweep); ViT-L untested underwater |
| **DepthMaster (2026)** `VCLab-PolyU/DepthMaster` | arXiv **2606.12368** | ✔✔✔✔ | MIT | ? | metric metres + points + intrinsics + mask | ⚠️ **name collides** with arXiv 2501.02576 — cite by ID |
| **PaGeR** `prs-eth/PaGeR` (1.41B) | arXiv 2605.26368 | ✔✔✔✔ | Apache-2.0 | **CC BY-NC 4.0** | scale-inv depth + metric depth + normals + sky mask | 🟢 Licensing done right: two separate files, HF agrees |

## 7.3 Underwater tier

| Model | Venue & ID | P C K L | Code lic | Ckpt lic | Verdict |
|---|---|---|---|---|---|
| **Wat3R** | arXiv 2607.08772, ECCV 2026 Oral | ✔✔✔✔ | Apache-2.0 | Apache-2.0 | **The only one clearing the bar.** See 7.1 |
| **WaterMono** | arXiv 2406.13344, IEEE TIM 2025 | ✔✔~✗ | **none** | **none** | Disparity (Class 4); FLSea win is **in-domain**; loses out-of-domain on Sea-thru (0.145 vs DA3 0.111); 9★/0 forks/4 open issues |
| **UDepth** | arXiv 2209.12358, ICRA 2023 | ✔✔✔✗ | **none — all rights reserved** | **none** | Worst in Wat3R's table (0.212); USOD10K pseudo-label supervision |
| **CD-UDepth** | **Information Fusion** 118:102961, DOI 10.1016/j.inffus.2025.102961 | ✔✔~✗ | **none** | **none** | **Not on arXiv.** UDepth backbone; no foundation-model comparison; repo 1★ |
| **UMono** | arXiv 2407.17838, IEEE JOE 2026 | ✔✗✗✗ | — | — | No code, no weights |
| **UDepthDiff** | **IEEE Access** 14:26953-26964, DOI 10.1109/access.2026.3651731 | ✔✗✗✗ | — | — | **Not on arXiv.** APC megajournal; no code, no weights |
| **UW-Depth / TRUDepth** | arXiv 2310.16750, ICRA 2024 | ✔✔✔✔ | **MIT** | MIT (repo) | **Requires sparse depth priors at inference** — not monocular |
| **SPADE** | arXiv 2510.25463, **IEEE JOE 2026** | ✔✔✗✔ | **MIT** | **"coming soon" — NOT RELEASED** | Requires sparse priors; its **DA V2+GA baseline row** is its value here |
| **Tree-Mamba** | arXiv 2507.07687 (no venue) | ✔✗✗✗ | **none** | — | Repo is **0 KB, 1 commit, README only**, predating its own arXiv posting |
| **UW-Adapter** | **IEEE TMM** 27:4808-4818 | ✔✗✗✗ | — | — | Conceptually ideal (frozen backbone + transmission/high-freq adapters); **completely unobtainable** |
| **Atlantis** | arXiv 2312.12471, **CVPR 2024 Highlight** | ✔✔n/a✔ | **MIT** | n/a | **Data-generation pipeline, not a depth model.** README redirects to MiDaS |

## 7.4 Licence findings that would surprise a casual reader

```text
DA V2 Large / Base            CC BY-NC 4.0   (only Small is Apache-2.0)
DA V2 Giant                   NEVER RELEASED (3 independent negatives)
DA3-LARGE-1.1                 CONFLICT: HF card apache-2.0 vs README CC BY-NC 4.0
DA V2 metric fine-tunes       tagged apache-2.0 despite a CC-BY-NC base
Depth Pro weights             apple-amlr, research-only, REVOCABLE, binds fine-tunes
                              - and the repo README points at the wrong licence
UniDepth V2 / UniK3D ckpts    NO licence declared on HuggingFace
Metric3D / UniDAC ckpts       NO licence declared
UniK3D + Dens3R code          CC BY-NC-SA - non-commercial AND VIRAL
Marigold LICENSE-MODEL.txt    an UNFILLED TEMPLATE - Attachment A "Use
                              Restrictions" contains literal "[insert use
                              restrictions]"
DepthCrafter                  hard non-commercial, code AND weights
UDepth / WaterMono / CD-UDepth / StereoAdapter   NO licence file at all
MoGe-1/-2/-3, FoundationGeo, OptiGeo             MIT on code AND every checkpoint
Wat3R                         Apache-2.0 on code AND checkpoint AND dataset
```

**Four of the most capable camera-general/metric options — Metric3D, UniDepth V2,
UniK3D, UniDAC — all have `checkpoint_license_unverified`.** That is a systemic
finding, not four coincidences, and it is exactly the standard Week 3 applied when
it chose MapAnything.


---

# 8. Relative / foundation depth

## 8.1 The lineage split that matters more than any benchmark

The single most consequential finding in this family is that **the affine
ambiguity moved representation between Depth Anything V2 and Depth Anything 3**,
and the DA3 paper states the contrast explicitly.

| Model | Native prediction | Ambiguity lives in | Class (s.17.1) |
|---|---|---|---|
| MiDaS v3.1 / DA V1 / DA V2 | **inverse depth (disparity)** | **disparity space** | **4 (worst)** |
| **DA3-Mono** | **depth**, predicted as **exponential depth** | **depth space** | **2-3** |

DA1 defines the inherited loss verbatim: *"the depth value is first transformed
into the disparity space by `d = 1/t` and then normalized to 0~1 on each depth
map"*, with `d_hat = (d - t(d))/s(d)`, `t(d) = median(d)`,
`s(d) = (1/HW) SUM |d_i - t(d)|`. DA V2 confirms inheritance: *"our models
produce affine-invariant inverse depth"* and *"a scale- and shift-invariant loss
L_ssi and a gradient matching loss L_gm ... these two objective functions are not
new, as they are proposed by MiDaS."*

DA3 states the break:

> "Unlike DA2, which predicts scale-shift-invariant disparity, our teacher outputs
> scale-shift-invariant depth. Depth is preferable for downstream tasks... To
> address depth's reduced sensitivity for near-camera regions comparing to
> disparity, we predict **exponential depth** instead of linear depth."

**And DA3's own shipped alignment utility is scale-only.** `least_squares_scale_scalar`
in `src/depth_anything_3/utils/alignment.py`, documented as *"Compute least
squares scale factor s such that a ~= s * b"* — **no shift term, in depth space.**
Its training target is also normalised by a single scale (*"all ground-truth
signals are normalized by a common scale factor ... the mean l2 norm of the valid
reprojected point maps"*).

**This puts DA3-Mono in Class 2 — the exactly-absorbable class — while the entire
MiDaS/DA V2 lineage sits in Class 4.** For this project that is a larger
difference than any AbsRel delta in any table.

**One unresolved tension to settle empirically, not from documents:** the *teacher*
is described as scale-**shift**-invariant in depth (Class 3) while the shipped
alignment code and the training normalisation are scale-only (Class 2). Week 4A
should fit scale-only and scale+shift against reference range and test whether the
fitted shift is significantly non-zero. **This is a measurement, not a literature
fact**, and it decides whether DA3-Mono is Class 2 or Class 3.

## 8.2 Depth Anything V2

```text
paper       Yang, Kang, Huang, Zhao, Xu, Feng, Zhao. arXiv 2406.09414
            v1 2024-06-13 / v2 2024-10-20. Comments: "Accepted by NeurIPS 2024"
repo        github.com/DepthAnything/Depth-Anything-V2   [CODE VERIFIED]
code lic    Apache-2.0
```

| Variant | Params | HF repo | Checkpoint licence |
|---|---|---|---|
| Small | 24.8M | `depth-anything/Depth-Anything-V2-Small` | **apache-2.0** |
| Base | 97.5M | `depth-anything/Depth-Anything-V2-Base` | **cc-by-nc-4.0** |
| Large | 335.3M | `depth-anything/Depth-Anything-V2-Large` | **cc-by-nc-4.0** |
| Giant | 1.3B | — | **NEVER RELEASED** |

**Giant is paper-only, 2+ years on** — three independent negatives: README says
"Coming soon"; absent from a complete 48-model enumeration of the HF org; the API
returns HTTP 401. Do not plan around it.

- **Output:** affine-invariant inverse depth. Code-verified: `forward` ends
  `depth = F.relu(depth); return depth.squeeze(1)` — one non-negative,
  unnormalised channel. **Class 4.**
- **Camera:** pinhole implicit. No intrinsics in or out, no FOV head, no rays.
  **Nothing in the model is aware of lens geometry.**
- **Confidence:** **none**, verified by absence in code.
- **Training:** 595K synthetic labelled (BlendedMVS 115K, Hypersim 60K, IRS 103K,
  TartanAir 306K, VKITTI2 20K) + 62M pseudo-labelled real. **No underwater or
  scattering data.**
- **Compute:** default input 518. **MPS officially supported, first-party** —
  the README's own device line selects `cuda` -> `mps` -> `cpu`. **This is the
  only model in the entire review with first-party Apple Silicon support.**
- ⚠️ **Licence inconsistency:** the metric fine-tunes
  `Depth-Anything-V2-Metric-Hypersim-Large` and `-Metric-VKITTI-Large` carry
  **apache-2.0** tags despite deriving from the CC-BY-NC Large checkpoint.

**Why it still matters despite Class 4.** It is the substrate of the entire
underwater literature — SPADE, OceanLens, Atlantis's pseudo-labelling, TIDE's
depth annotations, and Cai & Metzler's fine-tune all build on DA V2. And SPADE's
globally-aligned FLSea row (section 21.2) is the best affine-aligned underwater
number available for *any* model. It is the reference floor, and it is nearly free
to run locally.

## 8.3 Depth Anything 3 — monocular path

```text
paper       arXiv 2511.10647, v1 2025-11-13. ByteDance Seed.
venue       ICLR 2026 - VERIFIED at iclr.cc/virtual/2026/poster/10006531
            (listed Poster, with an associated Oral Session 2E; the project page
            markets "Oral". OpenReview forum yirunib8l8, bot-blocked, UNVERIFIED)
repo        github.com/ByteDance-Seed/Depth-Anything-3, code Apache-2.0
```

- **Monocular is first-class:** `DA3MONO-LARGE` is a dedicated, separately
  downloadable, **Apache-2.0**, 0.35B single-image checkpoint (98K downloads).
  README: *"A dedicated model for high-quality relative monocular depth
  estimation. Unlike disparity-based models (e.g., Depth Anything 2), it directly
  predicts depth, resulting in superior geometric accuracy."* Architecturally,
  cross-view attention degenerates to identity at N=1.
- **Output is z-depth — settled by two independent routes.** (i) The paper's ray
  is `r = (t, d)` with `d = R K^-1 p` and *"We do not normalize d, so its
  magnitude preserves the projection scale"*, and `P = t + D(u,v) * d`; since
  `K^-1 p` has camera-frame z-component exactly 1, `D` is z-depth. (ii) The
  shipped code: `unproject(coordinates, z, intrinsics)` — *"Unproject 2D camera
  coordinates with the given Z values"* — `return ray_directions * z[..., None]`,
  with no normalisation anywhere. **Note ByteDance's own marketing blog describes
  depth as "the distance from a pixel to the camera", which contradicts their
  paper's math. Trust the equations and the code.**
- **Central, not non-central.** The representation is a per-pixel 6-vector with an
  origin, so it is *structurally* capable of non-central imaging, but `t` is the
  view's single camera centre. See section 16.2.
- **Camera:** intrinsics neither required nor input; recovered post-hoc by RQ
  decomposition of the homography implied by the ray map.
- **Confidence:** `depth_conf`, `ray_conf`, activation `expp1 = exp(x)+1`
  (>= 1, unbounded); a **Laplace NLL precision weight, not a probability**;
  **no calibration evidence**. See section 18.2.
- **Monocular results** (paper Table 4, delta_1, KITTI/NYU/SINTEL/ETH3D/DIODE):
  DA2 94.6/97.9/**77.2**/86.5/95.2 vs DA3 95.3/**97.4**/**75.5**/98.6/95.4.
  **DA3 is *worse* than DA2 on NYU and SINTEL**; its large win is ETH3D. The
  "outperforms DA2" claim is an average-rank result, not a sweep.
- ⚠️ **No MPS support.** `cli.py` declares `device: str = typer.Option("cuda")`;
  there is **no `mps` handling anywhere in the codebase**; `api.py` calls
  `torch.cuda.is_bf16_supported()` unconditionally; `xformers` is a hard
  dependency; repo issue #123 for Apple Silicon was **closed/abandoned Dec 2025**.
  **DA3 will not run as shipped on this project's machine.**
- ⚠️ **Data-safety, Invariant 7:** the DA3 CLI exposes
  `auto_cleanup: bool = typer.Option(False, help="Automatically clean export
  directory if it exists (no prompt)")`. **Never wire this to True.**
- ⚠️ **Unresolved discrepancies:** `DA3-LARGE-1.1` licence (HF card says
  apache-2.0 in both front-matter and body; GitHub README table says CC BY-NC
  4.0); parameter counts differ paper vs README (Small 0.03B vs 0.08B); author
  list differs arXiv v1 (8) vs ICLR page (12); abstract claims 44.3%/25.1% vs the
  HTML body's 35.7%/23.6%.
- **DA3 is not a temporal answer.** The paper contains **zero occurrences of
  "temporal", "flicker" or "TAE"**. `da3 video` samples frames at 1 FPS into a
  **multi-view** reconstruction path — it is not per-frame video depth.

## 8.4 Also reviewed in this family

- **MiDaS v3.1** (arXiv **2307.14460**) — **a technical report, no venue.** Code
  MIT; **no weights licence stated anywhere in the repo.** Conceptual ancestor;
  superseded on every axis. StableDPT's measurements show DA V2 is already far
  more temporally stable than MiDaS-v2.1 per-frame.
- **DepthMaster (2026)** — arXiv **2606.12368**, *"Unified Monocular Depth
  Estimation for Perspective and Panoramic Images"*, Wang et al., PolyU. **Note
  the name collision** with arXiv **2501.02576** (*"Taming Diffusion Models for
  Monocular Depth Estimation"*, IEEE TCSVT 2026) — different authors, different
  method. **Cite by arXiv ID, never by name.** The 2026 one is **metric**, MIT
  code, checkpoint `VCLab-PolyU/DepthMaster` released; cubemap decomposition for
  panoramas (see section 11).
- **Focusable Monocular Depth Estimation** (arXiv **2605.11756**) — **no venue**,
  and **not a new model**: a prompt-conditioning wrapper injecting SAM 3 features
  into the Depth Anything family. Indoor/tabletop/embodied benchmarks only. **No
  code, dataset, or checkpoint release statement exists.**
- **DA360** (arXiv **2512.22819**, Insta360) — mechanism worth knowing: it learns
  *"a shift parameter from the ViT backbone, transforming the model's scale- and
  shift-invariant output into a **scale-invariant** estimate"*. That is a learned
  Class-3 -> Class-2 upgrade, exactly the transition section 17.1 values.
- **"Depth Anything 4" does not exist.** The `DepthAnything` GitHub org contains
  three repos; the HF org tops out at DA3. The one arXiv paper bearing the name
  (**2608.18388**, Fan et al., **none of whom are Depth Anything authors**) is a
  4D-Gaussian-splatting method that was **withdrawn 2026-08-20, two days after
  posting, flagged "Major errors in research."** Do not cite it.


---

# 9. Metric depth

## 9.1 Framing: metric capability is a separable axis, not a rank

Week 3 proved a global multiplicative range error is absorbed exactly. So metric
accuracy is **not** the primary criterion (section 2.2) — but it *is* load-bearing
for cross-clip coefficient transfer, absolute water-property interpretation,
artificial-light falloff (week 6) and camera-to-light geometry (section 2.3).
Section 17.2's E3 exists to score it without letting it dominate E1.

A prediction that should be held in mind throughout this section, from
FoundationGeo's own ablation (section 10.3): **metric scale degrades sharply on
focal lengths outside the training distribution**, and this project's camera is
out-of-distribution on two independent axes (very short focal + ~1.33x refractive
flat-port shift). Expect raw metric output from *every* model here to be
unreliable on GoPro footage; expect relative geometry to survive.

## 9.2 UniDepth V2 — the underwater metric champion, with a licence problem

```text
paper    "UniDepthV2: Universal Monocular Metric Depth Estimation Made Simpler"
         Piccinelli et al. arXiv 2502.20110 (v2 2025-02-27).
         Venue: TPAMI, DOI 10.1109/TPAMI.2025.3628473
predecessor  UniDepth, CVPR 2024, arXiv 2403.18913
repo     github.com/lpiccinelli-eth/UniDepth
ckpts    lpiccinelli/unidepth-v2-vits14 / -vitb14 / -vitl14
```

- **Output semantics — the best fit to this project's canonical quantity.** It
  uses a **pseudo-spherical output representation** that disentangles camera from
  depth, and **natively distinguishes `radius` (metric ray range) from `depth`
  (its z-component)**. It is, on the evidence gathered, the only model that
  exposes both explicitly. `radius` is `measured` in section 2.1's taxonomy.
- **Camera:** a **self-promptable camera module** predicting a dense camera
  representation that conditions the depth features. Known intrinsics can be
  supplied at inference — a documented, supported API accepting a 3x3 tensor
  **or a camera class object including `Fisheye624`** (`camera.py`). That is a
  genuine, first-class camera-conditioning path.
- **Confidence:** V2 adds an uncertainty output (V1 has none), alongside an
  edge-guided loss for sharper depth boundaries. **No calibration evidence found**
  (section 18).
- **Underwater evidence:** the **best zero-shot result in the only clean
  underwater metric benchmark** — FLSea-Canyon AbsRel 0.1156 / delta_1 0.9109;
  Red Sea 0.0932 / 0.9439; SQUID 0.3222 / 0.5201 (section 14.1). But see 14.1 for
  why that benchmark rewards exactly the axis this project doesn't need.
- ⚠️ **Licence: code is CC BY-NC 4.0; the checkpoints carry NO licence field at
  all on HuggingFace** [VERIFIED — `lpiccinelli/unidepth-v2-vitl14` returns no
  licence tag]. `checkpoint_license_unverified`. Against a project that selected
  MapAnything partly for Apache-2.0 on both, this is a real deployment blocker.
- ⚠️ **Requirements state Linux and CUDA 11.8+.** No MPS or CPU path documented.

## 9.3 Depth Pro — the most FOV-robust released model, and research-only

```text
paper    Bochkovskii et al. (Apple). arXiv 2410.02073. ICLR 2025 (comments field)
repo     github.com/apple/ml-depth-pro ; HF apple/DepthPro, apple/DepthPro-hf
```

- **Accepts a known focal length**, and the docstring is explicit: *"if the focal
  length is given, the estimated value is ignored and the provided focal length is
  use to generate the metric depth values."* Mechanism is the canonical-camera
  trick — predict canonical inverse depth, rescale by `f_px / W`.
- ⚠️ **Implementation gotcha, verified by execution:** `f_px = f_px.squeeze()`
  runs unconditionally, so passing a plain Python `float` — which the type hint
  invites — raises `AttributeError`. Pass `torch.tensor(f_px)`.
- **FOV robustness — the standout result, and the reason it is not dismissed.**
  **WideDepth** (arXiv **2605.24074**, **ICRA 2026**) [PAPER VERIFIED] — a
  millimetre-accurate fisheye benchmark, 101 scenes, 5K high-resolution stereo
  pairs with LiDAR-derived GT, paired pinhole and fisheye across varying FOV —
  measured degradation from **120 deg to 195 deg**:

  ```text
  Depth Pro           +9.0 %  AbsRel
  UniK3D              +97 %   AbsRel
  Depth Anything V2   +166 %  AbsRel
  ```

  [These per-model figures come from the paper body via an agent's extraction and
  were **not** confirmed on the abstract page — **re-verify against the PDF before
  making them load-bearing.** The paper's identity, venue and benchmark design
  are verified.] If they hold, they are the most directly relevant quantitative
  evidence in this review for a 105-deg camera, and they invert the intuition that
  an "any-camera" model is automatically the FOV-robust choice.
- ⚠️ **Licence — the README misstates it.** The README points at Apple's
  permissive 47-line sample-code licence, but the 88-line `LICENSE` shipped beside
  `depth_pro.pt` on HF is the **Apple Machine Learning Research Model License**:
  *"exclusively for Research Purposes... non-commercial scientific research and
  academic development"*, explicitly excluding commercial products, **binding
  fine-tunes to the same terms**, and **revocable**. HF tags it `apple-amlr`.
  Research use is fine; shipping is not.
- **Underwater:** poor in the one benchmark — SQUID AbsRel **3.2185**, the worst
  number in the table (section 14.1). Note this is a *raw metric* score, so it is
  primarily a scale failure; its *shape* is untested underwater.

## 9.4 Metric3D / Metric3D v2

```text
Metric3D    arXiv 2307.10984, ICCV 2023
Metric3D v2 arXiv 2404.15506, TPAMI 2024
```

- **Intrinsics are REQUIRED**, not optional; the documented fallback is a
  **9-value focal sweep**. For an EIS-warped GoPro with an unmeasured effective
  focal, that is a direct dependency on the project's weakest known parameter.
- Canonical camera space (CSTM) transform; predicts depth + surface normals.
- ⚠️ **Code BSD-2; checkpoint licence never stated.** The
  `onnx-community/metric3d-vit-large` `cc0-1.0` tag is a **third-party
  re-upload's assertion, not the authors'** — do not rely on it.
- **Underwater:** the ViT-S variant scored AbsRel 1.5331 / 0.8130 / 1.3059 in
  section 14.1; the ViT-L variant was **excluded from that benchmark for hardware
  reasons**, so the strongest Metric3D configuration is **untested underwater**.
- **There is no Metric3D v3** — ten arXiv queries plus the official repo, whose
  News ends at *"[2024/8] Metric3Dv2 is accepted by TPAMI!"*.

## 9.5 DA3 Metric

`DA3METRIC-LARGE`, 0.35B, **Apache-2.0 checkpoint** — see section 8.3 for the
family. Its metric mechanism is stated exactly:

```text
metric_depth = focal * net_output / 300.
```

(canonical focal normalisation, `f_c / f`; code-confirmed in `apply_metric_scaling`
as `depth * focal_length / 300.0`).

**This is the most transparent metric mechanism of any candidate**, and it has a
specific, favourable consequence for this project: **absolute scale is directly
proportional to the focal length supplied.** An error in the assumed focal is
therefore a **pure global multiplicative range error** — Class 2, absorbed exactly
per Week 3. So DA3 Metric's metric claim degrades *gracefully* under exactly the
uncertainty this project has (EIS, unmeasured effective focal), rather than
deforming shape. That is a better failure mode than most of this section.

## 9.6 ZoeDepth

arXiv **2302.12288**. ⚠️ **No peer-reviewed venue** — no comments field, no
journal-ref, never revised, and the repo's own BibTeX is `@misc`. It is widely
miscited as a conference paper. **Intrinsics are ignored entirely.** Licence is
the cleanest here (**MIT code and MIT weights**), but it is the **worst performer
underwater by a wide margin** (AbsRel 1.5907 / 1.3335 / 1.3214). Historical
interest only.

## 9.7 The 2026 negative results

Searched and not found: **no Depth Pro 2, no UniDepth V3, no Metric3D v3**
(arXiv queries returned zero). The metric family's 2026 movement is in
**camera-general** modelling (section 11) and in **scale-recovery mechanisms**
(TR2M arXiv 2506.13387 CVPR 2026 and *Language as Prior, Vision as Calibration*
arXiv 2601.01457 both recover metric scale from language descriptions;
*Zero-Shot Depth from Defocus* arXiv 2603.26658 ECCV 2026 uses defocus) — none of
which applies to a fixed-aperture, text-free underwater pipeline.


---

# 10. Explicit 3-D / point-map approaches

## 10.1 Why this family is structurally advantaged here

A model that predicts a **point map in camera coordinates** gives the project's
canonical quantity directly:

```text
range(u,v) = || P_cam(u,v) ||
```

with **no intrinsics required and no approximation** — the `transformed_exactly
(conditional on K)` caveat of section 17.4 disappears. Week 3 already validated
this route once: MapAnything's `depth_along_ray == ||pts3d_cam||` to `1.1e-5`.
That is a real advantage for a wide-FOV camera whose `K` is itself provisional
under EIS.

## 10.2 MoGe family

```text
MoGe    arXiv 2410.19115, CVPR 2025 Oral
MoGe-2  arXiv 2507.02546  "Accurate Monocular Geometry with Metric Scale and Sharp Details"
MoGe-3  arXiv 2607.17967  "Fine-Detail Monocular Geometry Estimation with
                           Self-Guided Sparse Volumetric Refinement" (2026-07)
repo    github.com/microsoft/MoGe
```

| Version | HF checkpoint | Metric | Normals | Params |
|---|---|---|---|---|
| MoGe-1 | `Ruicheng/moge-vitl` | - | - | 314M |
| MoGe-2 | `Ruicheng/moge-2-vitl` | yes | - | 326M |
| MoGe-2 | `Ruicheng/moge-2-vitl-normal` | yes | yes | 331M |
| MoGe-2 | `Ruicheng/moge-2-vitb-normal` | yes | yes | 104M |
| MoGe-2 | `Ruicheng/moge-2-vits-normal` | yes | yes | 35M |
| MoGe-3 | `Ruicheng/moge-3-vitl` | yes | yes | 370M |
| MoGe-3 | `Ruicheng/moge-3-vitg` | yes | yes | 1.25B |

**Licence: MIT for code and MIT on every checkpoint** [VERIFIED via HF API on all
seven]. This is the cleanest licensing position of any model in this review.

- **Outputs:** `points` (metric point map, OpenCV camera coords, x right / y down
  / z forward), `depth` (**z-depth**, the z-component), `intrinsics`
  (normalised), `mask` (binary validity), optional `normal`.
- **MoGe-1's ambiguity, stated precisely:** *"P is agnostic to the global scale
  `s` and offset `t`"*, `P ~= sP + t`, simplified under the assumption of a
  centred principal point and square pixels to **a scale and a Z-axis shift
  `t_z`** (`t_x = t_y = 0`). That is **Class 3** — the additive-shift class that
  section 17.1 shows is *not* absorbable in the backscatter term. Evaluation uses
  their ROE solver: `argmin_{s,t} SUM (1/z_i) || s p_hat_i + t - p_i ||_1`.
- **MoGe-2/-3 resolve the shift** by predicting metric scale, moving them to
  **Class 1**. This within-family pairing (MoGe-1 relative vs MoGe-2 metric) is
  itself a clean isolation of the metric variable.
- **Camera:** accepts an optional **`--fov_x`** (horizontal FOV in degrees);
  otherwise estimates it. This is a documented, supported monocular API — a real
  advantage for a camera whose FOV is measured (105.383 deg) but whose effective
  focal is disturbed by EIS.
- **Compute:** 60 ms/image (A100 or RTX 3090, FP16, ViT-L). `resolution_level`
  0-9 adjusts inference detail without changing output dimensions.
- ⚠️ **macOS:** the repo states *"macOS is not supported: MoGe-3 depends on
  FlexGEMM, which builds on Triton, and Triton publishes no macOS wheels."* The
  statement is scoped to MoGe-3's dependency; whether MoGe-1/-2 (plain PyTorch)
  still run on MPS is **not stated and must be tested**, not assumed either way.
  This is a Week-4A plumbing check, and it materially affects which MoGe version
  is deployable locally.
- **`moge infer_panorama`** splits a panorama into perspective views and
  recombines the point maps (README marks it *"an experimental extension"*) — a
  shipped instance of the tile-and-fuse pattern discussed in section 11.

**A dissenting mechanistic critique worth carrying forward.** DAGE (CVPR 2026)
rejected MoGe's objective: *"MoGe applies a multi-scale affine-invariant pointmap
loss by subsampling local regions... While this improves single-image sharpness,
we found that **per-region independent alignments introduce patch-wise degrees of
freedom that break cross-view consistency, leading to seams and drift**."* And
DyFN's temporal ablation (section 19.1) used **MoGe** as its representative model
— i.e. the 62.5 -> 99.8 scale-shift-drift finding is a MoGe measurement. Both
suggest **MoGe should not be selected on single-image sharpness alone**, and that
its per-frame stability is a specific thing to measure.

## 10.3 FoundationGeo — the best native semantics found

```text
paper    "FoundationGeo: Learning Spatial Pixel-Wise Fields for Monocular Metric
         Geometry". Liu, Lyu, Ren, Dai, Wu, Zhang, Zhang, Lin, Shi, Qi (HKU +
         Voyager Research, Didi). arXiv 2607.11588, v1 2026-07-13.
         Comments: "Accepted to ECCV 2026"  [PAPER VERIFIED]
repo     github.com/mx-liu6/FoundationGeo   code MIT
ckpts    mxliu-hku/FoundationGeo, -1.1        (Stage-II, metric, 314M)
         mxliu-hku/FoundationGeo-Base, -1.1   (Stage-I, affine-invariant, 313M)
         all four VERIFIED license: mit, ungated. The -1.1 variants are preferred.
```

**It is the only model reviewed that natively decomposes into Euclidean range and
a unit ray**, verbatim:

> "Let `p_hat_i in R^3` be the predicted affine-invariant point at pixel `i`. We
> decompose it into a **range term and a unit ray direction**, with
> `d_hat_i = ||p_hat_i||_2` and `r_hat_i = p_hat_i / ||p_hat_i||_2`."

`d_hat_i` **is** Euclidean camera-centre range — an l2 norm. That makes it
`measured` rather than `transformed_exactly` in section 2.1's taxonomy, and it is
exactly the pair a Beer-Lambert attenuation model wants.

> ⚠️ **DA3 and FoundationGeo both use the word "ray" for structurally different
> objects.** DA3: unnormalised ray + z-depth. FoundationGeo: unit ray + range.
> Read side by side without checking the norms and you will get this backwards.

Pipeline: Stage-I predicts an affine-invariant point map + validity mask;
Stage-II applies a **ray-direction correction field** and a **pixel-wise scale
field** `S in R^{HxW}`, `P_tilde = S (*) P_hat`. So the relative->metric bridge is
two named, inspectable fields — and Stage-I ships separately, giving another clean
relative-vs-metric pairing within one architecture. No confidence output; no FOV
output (it *consumes* intrinsics, with an `--oracle` flag for GT).

**Its OOD-focal finding is the most directly predictive result in this review:**

> "monocular metric prediction is fundamentally coupled with focal length. When
> training covers only a limited set of camera models, the network may internalize
> a **biased implicit focal prior**, leading to systematic over- or under-scaling
> on unseen optics."

> "Datasets whose focal lengths closely align with our training distribution
> (NYUv2, KITTI, iBims-1) show strong accuracy with minimal scale drift, whereas
> **camera-mismatched benchmarks (DDAD, ETH3D, HAMMER, DIODE) ... exhibit degraded
> performance.** These results confirm that the remaining performance gap
> primarily stems from **out-of-distribution focal lengths**, where the model's
> implicit scale prior becomes unreliable."

**The GoPro is out-of-distribution on two counts at once** — a very short focal
length, *and* the ~1.33x refractive focal shift from the flat port. The
prediction that follows is concrete and testable: **expect every metric monocular
model to have unreliable *absolute* scale on this footage, while relative geometry
survives.** Which, per Week 3, is the benign failure. This raises confidence in
treating the metric scalar as a nuisance parameter rather than a measurement.

Training: 19 datasets, **10.2M frames**, DINOv3-initialised ViT-L. **No underwater
data.** No fisheye/distortion handling. No temporal evaluation. VRAM/runtime not
stated. ⚠️ Its `LICENSE` reads *"MIT License / Copyright (c) Microsoft
Corporation"* — byte-identical to MoGe's template despite HKU authorship; the MIT
grant is unambiguous but GitHub's API reports `NOASSERTION` as a result.

**OptiGeo** (arXiv **2608.29881**, 2026-08-30, same group; repo
`github.com/mx-liu6/OptiGeo`, checkpoint `mxliu-hku/OptiGeo`, **30M params, MIT
code and MIT checkpoint**) targets **transparent/reflective/specular** scenes and
outputs metric depth + metric point map + validity mask + **estimated FOV**. Its
thesis — **sensor-induced supervision bias**, models inheriting depth-sensor
failure patterns from biased real supervision — is the nearest published framing
to the underwater problem, and at 30M params it is the most plausible candidate
for cheap local inference. arXiv only, no venue.

## 10.4 PointDiT

arXiv **2607.02515**, **ICML 2026** (Google / ETH / Tübingen / Microsoft / TUM),
repo `github.com/google-research/pointdit`, code and checkpoints **Apache-2.0**.
States the semantics outright: *"Our model predicts **affine-invariant point
maps**, from which affine-invariant depth maps are obtained by **extracting the
z-component of each point**"*, normalised by centroid and a scalar scale ⇒
*"recovered up to an unknown scale and shift"* (**Class 3**). Trained **100% on
synthetic data**. Note *"On Rel^p, MoGe remains slightly ahead (4.21 vs 4.40)"*.

⚠️ **The blocker is in every checkpoint filename (`...-nodinov3-...`):** *"The
**DINOv3 weights are gated and cannot be redistributed**, so they are not part of
the released checkpoints... They are needed for **evaluation and the demo as well
as for training**."* Apache-2.0 on paper, gated Meta weights in practice.

## 10.5 Genuinely monocular vs degenerate-multiview

| Model | Venue | Single-image status |
|---|---|---|
| MoGe / -2 / -3 | CVPR'25 / 2025 / 2026 | **Genuinely monocular** — the only mode |
| **FoundationGeo** | **ECCV 2026** | **Genuinely monocular** |
| **PointDiT** | **ICML 2026** | **Genuinely monocular** |
| DA3 (`DA3MONO-LARGE`) | ICLR 2026 | **Genuinely monocular** — dedicated checkpoint |
| Dens3R | ICLR 2026 (repo-claimed) | DUSt3R/MASt3R pair heritage |
| MapAnything | 3DV 2026 | Monocular is an explicitly listed supported task |
| pi^3 / VGGT | ICLR'26 / CVPR'25 | Works, **explicitly never trained for it** (VGGT: *"surprisingly good ... although it was never trained for this task"*) |
| DAGE | CVPR 2026 | **Multi-view by construction** — degenerates at N=1 |
| DUSt3R / MASt3R | CVPR'24 / ECCV'24 | Duplicating the image is **not** a monocular path |

**Dens3R** (arXiv **2507.16290**, Alibaba, 398 stars) is explicitly excluded on
licence: *"licensed under the Creative Commons Attribution-NonCommercial-**ShareAlike**
4.0 license."* **ShareAlike is viral** — the sharpest restriction found anywhere
in this review.


---

# 11. Any-camera models

## 11.1 The two questions the brief asked, answered

**Q1 — As of September 2026, does any released monocular depth model represent
non-central (refractive / flat-port) imaging?**

> **No.** Two independent verification sweeps covering nineteen-plus models —
> including UniK3D, UniDepth V2, UniDAC, Depth Any Camera, DA3, MoGe, Depth Pro,
> Metric3D, ZeroDepth, DMD, Pow3R, Pi3X, PaGeR, DepthMaster-2026 — found that
> **every one assumes a central camera**, with the principal point at the image
> centre. UniK3D and UniDepth V2 generalise the **ray field**; both still
> back-project from a single optical centre. Targeted searches for
> "non-central camera monocular depth", "refractive camera model deep depth",
> "axial camera model neural network" and related terms returned no released model.

This confirms section 16.2's framing: **"any camera" in this literature means
"any *central* projection"** — pinhole, Brown-Conrady, Kannala-Brandt fisheye,
EUCM/UCM, equirectangular. A per-pixel ray *direction* field from one shared
origin is not a flat-port model.

**Q2 — What is the measured cost of feeding wide-FOV imagery to a pinhole-trained
model, and is a standard mitigation documented with numbers?**

The cost is now measured, by **WideDepth** (arXiv **2605.24074**, **ICRA 2026**) —
degradation from 120 deg to 195 deg FOV: **Depth Pro +9.0%**, **UniK3D +97%**,
**Depth Anything V2 +166%** AbsRel [per-model figures extracted from the paper
body by an agent; **re-verify against the PDF before relying on them**]. If they
hold, the ordering is counter-intuitive and important: **a camera-*conditionable*
pinhole model given the right focal beat a camera-*general* model.**

Two mitigations are documented, both by construction rather than by ablation
numbers:

- **Cubemap / tile-and-fuse.** PaGeR (arXiv **2605.26368**, ETH `prs-eth`)
  does *not* process equirectangular panoramas directly; it reformats into a
  **six-face cubemap** via gnomonic projection because *"equirectangular
  projection introduces serious geometric distortions... an extremely uneven
  sampling of the ray space... one cannot easily employ transfer learning from
  models trained with perspective images."* DepthMaster-2026 (arXiv
  **2606.12368**) uses the same six-face decomposition. **MoGe ships a working
  instance** — `moge infer_panorama` splits into perspective views and recombines
  the point maps (README: *"an experimental extension"*).
- **ERP conversion** — Depth Any Camera's approach, inherited by UniDAC.

**No paper measures the P0/P1/P2 tradeoff (section 16.4) on flat-port underwater
wide-FOV footage.** That remains a Week-4A measurement.

## 11.2 UniDAC — verified real, and the strongest camera-general candidate

```text
paper   "UniDAC: Universal Metric Depth Estimation for Any Camera"
        Girish Chandar Ganesan, Yuliang Guo, Liu Ren, Xiaoming Liu
        arXiv 2603.27105, v1 2026-03-28, v2 2026-04-08.
        arXiv cs.CV only - NO peer-reviewed venue as of 2026-09-05
predecessor  Depth Any Camera (DAC), arXiv 2501.02464 - same group
```

The user's shortlist entry is **real** [PAPER VERIFIED]. Method: decouples the
problem into **relative depth prediction + spatially varying scale estimation**,
with a **Depth-Guided Scale Estimation module** upsampling the scale map using
relative depth as guidance. Handles *"diverse camera types, such as fisheye and
360 deg cameras"* via **ERP** with a latitude-aware RoPE-phi positional embedding.

- **Output:** metric. Convention: its own demo source contains
  `# convert depth from zbuffer to euclid`, consistent with DAC's stated
  *"Euclidean Distance from the camera center"* — so **internally Euclidean
  range**, which is the project's canonical quantity. [Code comment evidence; the
  paper does not state it.]
- **Central only.** ERP and a latitude-weighted positional encoding model an
  arbitrary *central* projection. No per-pixel ray origins.
- ⚠️ **Licence: MIT code; checkpoint carries no HuggingFace licence metadata**
  → `checkpoint_license_unverified`. Same status as Metric3D, UniDepth V2 and
  UniK3D — **the four most capable camera-general options all have unverifiable
  checkpoint licences.**
- No code link appears in the abstract; release status was not independently
  confirmed on a repo page. `code_status_unverified` pending a direct check.

## 11.3 UniK3D

arXiv **2503.16591**, **CVPR 2025** (repo-asserted). Spherical-harmonic ray field
with an angular loss, explicitly targeting wide-FOV and non-pinhole cameras —
architecturally the most optics-aware of the UniDepth lineage.

- ⚠️ **Licence: code CC BY-NC-**SA** — non-commercial *and viral*. Checkpoint
  `lpiccinelli/unik3d-vitl` carries **no declared licence** [VERIFIED].
- ⚠️ **WideDepth measured it at +97% AbsRel from 120->195 deg**, nearly ten times
  Depth Pro's degradation. If that number survives verification, **UniK3D's
  "any-camera" branding does not translate into FOV robustness**, which is a
  strong reason not to promote it on architecture alone.
- **Still central** — a generalised ray field from one optical centre.

## 11.4 RayTun3R — the interesting 2026 entry

```text
paper  "RayTun3R: Online Camera Adaptation in 3D Foundation Models"
       Daniil Sinitsyn, Nikita Araslanov, Daniel Cremers (TUM)
       arXiv 2607.02711, 2026-07-02. No venue.
```

Adapts pretrained 3D foundation models — it names **DUSt3R, MASt3R, VGGT, pi^3
and Depth Anything 3** — to fisheye geometries at **110-200 deg**, targeting the
pinhole bias directly. The adapter touches *"only lightweight components tied to
token position and camera geometry"*: **10,752 trainable parameters**, geometric
losses, **no runtime overhead once adapted**.

**Why it matters here despite requiring a temporal segment.** It learns from
*"a short temporal segment"* and then *"transfers effectively to the remaining
frames of the sequence."* That reads as a violation of frame independence — but
it is a **per-camera** fit, not a per-frame one. For a fixed GoPro in a fixed
housing, the adaptation could be performed **once, offline, and frozen**, after
which inference is strictly single-frame and deterministic. That makes it
compatible with the project's constraints in a way genuine TTA is not, and it
composes with DA3, which is already a candidate. Release status and determinism
are **not stated** on the abstract page.

## 11.5 Also in this family

- **Depth Any Camera (DAC)**, arXiv **2501.02464** — UniDAC's predecessor; ERP
  conversion so a perspective-trained model generalises to fisheye/360.
- **DepthMaster (2026)**, arXiv **2606.12368**, PolyU — unified perspective +
  panoramic, **metric metres**, MIT code, checkpoint `VCLab-PolyU/DepthMaster`
  released. Cubemap decomposition + correspondence-consistency loss. No backbone
  or parameter count in the README; no MPS/CPU mention.
- **PaGeR**, arXiv **2605.26368**, ETH — scale-invariant depth, metric depth,
  normals and sky masks in one pass; **no point maps**. 🟢 **Licensing done right,
  and the model others should copy:** *"Source code: Apache License 2.0 ·
  Pretrained PaGeR model weights: CC BY-NC 4.0 (LICENSE-MODEL)"* — two separate
  files, HF card agrees, no conflict. Weights are non-commercial. Measured
  1,414,126,099 params (1.41B).
- **DA360** (arXiv **2512.22819**), **DA^2 "Depth Anything in Any Direction"**
  (arXiv **2509.26618**, Tencent Hunyuan), **VGGT-360** (arXiv **2603.18943**),
  **Sphere-Depth benchmark** (arXiv **2604.23432**), **"From Perspective to
  Fisheye Depth Estimation and Open-Vocabulary Segmentation"** (arXiv
  **2608.27860**) — panoramic/fisheye work, all central.

## 11.6 What this family should and should not buy in Week 4A

Section 16.3 argued from the project's own Phase-3B evidence that among *central*
camera models, well-conditioned clips are stable to <= 1.5% across four projection
families, and that an equal-capacity fisheye changed the weak clip by 0.8% — i.e.
**capacity, not projection family**, drove the differences. Combined with
WideDepth's finding that a camera-*conditionable* pinhole model (Depth Pro) beat a
camera-*general* one (UniK3D) by ~10x on FOV robustness, the conclusion is:

> **"Any-camera" architecture does not earn a primary Week-4A slot.** Supplying a
> known FOV/focal to a strong conventional model (MoGe's `--fov_x`, Depth Pro's
> `f_px`, UniDepth V2's camera object, DA3 Metric's focal term) is the
> better-evidenced lever, and it is exactly the P1 convention in section 16.4.

This family becomes a **conditional challenger** with an explicit trigger
(section 23), and the trigger is a *measured* FOV/distortion failure, not the
prior expectation of one.


---

# 12. Generative / diffusion approaches

## 12.1 Verdict first

**No generative model earns a primary Week-4A slot, and the reason is not
prejudice against the family — it is that the family's own literature has largely
retracted the claim that motivated including it.**

The hypothesis this family was supposed to test was "generative priors materially
improve thin/detail geometry". That hypothesis is now better tested by
*non-generative* means, for three documented reasons developed below.

## 12.2 The advantage was substantially refuted from inside the family

**E2E-FT — "Fine-Tuning Image-Conditional Diffusion Models is Easier than You
Think"** (Garcia, Knaebel, Schmidt, de Geus, Hermans, Leibe; arXiv **2409.11355**,
**WACV 2025 Oral**; repo `VisualComputingInstitute/diffusion-e2e-ft`)
[PAPER VERIFIED, CODE VERIFIED, CHECKPOINT VERIFIED].

Two results matter:

1. **The multi-step advantage was partly a scheduler bug.** Marigold's DDIM used
   *leading* timestep spacing, excluding the final timestep, so — quoting the
   paper — *"the model receives a timestep encoding that indicates an almost
   perfect depth map whereas the actual input is pure noise."* With *trailing*
   spacing, single-step inference recovers essentially all the quality:
   AbsRel on NYUv2 **5.5** (Marigold, 50 steps x 10 ensemble) vs **5.7**
   (Marigold + DDIM fix, 1 step) vs **5.2** (Marigold + E2E-FT, 1 step), at
   roughly **200x** less compute. After the fix, multi-step is *worse* than
   single-step.
2. **The ablation that removes the formulation entirely.** End-to-end fine-tuning
   *Stable Diffusion itself*, with none of the Marigold diffusion-training
   protocol, reaches **5.4**. The paper's conclusion, verbatim:
   *"casting depth estimation as conditional image generation is not more
   effective than simple end-to-end fine-tuning."*

What transfers is the **pretrained representation**, not the generative process.
Independent agreement from within the family: GenPercept (ICLR 2025, arXiv
**2403.06090**) — *"the stochastic nature of diffusion models has a slightly
negative impact on deterministic visual perception tasks"*; Lotus (ICLR 2025,
arXiv **2409.18124**) whose entire contribution is removing the diffusion process
to avoid *"harmful variance"*.

**PointDiT** (Google/ETH/Tübingen; arXiv **2607.02515**, **ICML 2026**)
[PAPER VERIFIED] is the endpoint of that argument: a pixel-space Diffusion
Transformer on a plain ViT over frozen DINOv3 features, **trained from scratch
with no pretrained latent diffusion model at all**, which still beats latent
diffusion methods. By 2026 the "generative image prior" is no longer the
load-bearing component.

## 12.3 The sharpness advantage is real but misattributed

**Pixel-Perfect Depth** (arXiv **2510.07316**, **NeurIPS 2025**)
[PAPER VERIFIED] relocates the cause: latent-space diffusion depth
*"inevitably introduces flying pixels at edges and details"* because of the
**SD VAE**, and *"increasing the latent dimension in VAEs fails to eliminate
flying pixels."* Working in pixel space removes the artefact. So boundary quality
is a **representation** question (pixel vs latent), not a **sampler** question.

A second confounder must be stated: diffusion depth models train on **dense
synthetic GT** (Hypersim, Virtual KITTI); the discriminative models they were
compared against historically trained on **sparse LiDAR**, which cannot teach
thin structure at all. A large part of "generative sharpness" is a training-data
property. MoGe-2/-3 and DA3, trained on dense supervision, now compete on
boundary metrics directly.

## 12.4 The mechanism that makes this family actively dangerous underwater

**DepthMaster** (arXiv **2501.02576**) [PAPER VERIFIED] diagnoses diffusion depth
pretraining as follows: *"the reconstruction task used to pre-train the denoising
network induces the model to prioritize texture details over structure, leading
to unrealistic textures in depth predictions"*, producing **"pseudo-textures"** —
depth structure invented from colour detail. Their fix, injecting external
semantic features, **improved edge F1 from 0.306 to 0.337**, i.e. suppressing the
generative texture bias made boundaries *better*.

This is the single most project-relevant finding in the family. Underwater frames
are saturated with high-frequency *appearance* that has no geometric counterpart:
backscatter speckle, suspended particulate, caustics, marine snow. A model that
converts high-frequency appearance into high-frequency geometry will convert
marine snow into structure. That is Invariant 5's failure mode arriving years
before the week-10 learned residual, and it is exactly the class of error that
metrics will not catch and visual inspection will.

Corroborating: **DVD** (arXiv **2603.12250**, 2026) states plainly that
*"generative models suffer from stochastic geometric hallucinations and scale
drift"*; **Iris** (arXiv **2603.16340**, **CVPR 2026**) notes diffusion depth
methods *"struggle with synthetic-to-real domain transfer"* — and every model here
is trained on synthetic in-air data.

## 12.5 Determinism: a hard constraint this family mostly fails, with exceptions

Week 3 established bitwise reproducibility for all three dense candidates on MPS
float32 and used that to argue every reported difference was method difference
with no noise floor to clear. That argument is worth preserving.

Marigold's own official documentation states the problem in plain language:
*"Due to Marigold's generative nature, each prediction is unique and defined by
the random noise sampled for the latent initialization. This becomes an obvious
drawback compared to traditional end-to-end dense regression networks."*
Measured cross-seed pixel-wise std: **0.033 (NYUv2), 0.025 (KITTI)** over 10 runs
(paper Table S2). A fixed `torch.Generator` seed pins the output, but the repo
notes `--batch_size 1` "helps to increase reproducibility" and that full
determinism additionally needs PyTorch deterministic mode with results still
varying across hardware. **A seed alone is not a byte-identical regression test.**

Determinism ranking (best first):

```text
E2E-FT             no latent seed at all - "noise should always be zeros,
                   ensemble size and inference steps should always be 1"
Lotus-2            both stages explicitly noise-free by design
Lotus -d variants  discriminative/regression reformulation
GenPercept, DepthMaster, DVD   one-step deterministic
DepthFM            flow matching from image start; determinism UNVERIFIED
Marigold, GeoWizard            seeded stochastic, with caveats above
DepthCrafter, ChronoDepth, RollingDepth   no determinism statement published
```

## 12.6 Lotus-2, specifically — the shortlist challenger, and why it loses

**Lotus-2: Advancing Geometric Dense Prediction with Powerful Image Generative
Model.** He, Li, Sheng, Chen (HKUST(GZ)/HKUST/UCSD). arXiv **2512.01030**
(v1 2025-11-30, v3 2026-05-18). Project page `lotus-2.github.io`, repo
`EnVision-Research/Lotus-2`, checkpoint `jingheya/Lotus-2`.
[PAPER VERIFIED, CODE VERIFIED, CHECKPOINT VERIFIED]
**No peer-reviewed venue as of 2026-09-05 — arXiv preprint only.**

It is genuinely the best-designed generative candidate: explicitly noise-free in
both stages, and its critique of ensembling is sharp — averaging *"introduces
prediction bias"* by *"blending both correct and incorrect structural
hypotheses."* Accuracy is strong (AbsRel NYUv2/KITTI **4.1 / 6.7** on 59K training
samples vs DA V2 4.5 / 7.4 on 62.6M).

It nonetheless fails three project gates:

1. **Ambiguity class 4.** It trains and predicts **in disparity space**
   (`d = 1/d'`) and evaluates with least-squares affine alignment in that space.
   Per section 17.1 this is the *worst* ambiguity class for this application:
   Mobius range deformation plus a finite depth horizon, concentrated at long
   range where the restoration budget is tightest.
2. **Hardware.** The repo requires a GPU with **at least 40 GB** of memory. That
   is not rentable-and-forget; it is a permanent CUDA dependency for a fallback
   path, against a project that concluded "nothing observed justifies making CUDA
   a permanent project requirement."
3. **Licence risk.** Code is Apache-2.0 and the HF card declares apache-2.0, but
   the README requires gated access to `black-forest-labs/FLUX.1-dev`, governed by
   the **FLUX.1 [dev] Non-Commercial License Agreement** [VERIFIED on the official
   BFL card]. Neither the Lotus-2 repo nor its card mentions this inheritance.
   Outputs are likely fine; the weights are encumbered.

No runtime or inference-VRAM measurement is published in either the paper or the
repo [VERIFIED ABSENT].

## 12.7 What this family should contribute to Week 4A instead

Not a model slot — three transferable results:

- **The determinism bar.** E2E-FT's "noise is literally zeros" is the standard
  every candidate should be held to, and it is achievable.
- **The pseudo-texture hazard**, which becomes a named, testable failure mode in
  the section-20 appearance-invariance work: *does the candidate convert
  backscatter speckle into geometry?*
- **A per-frame flicker baseline number.** RollingDepth's OPW table gives
  per-frame Marigold at **0.48e-3** on ScanNet against RollingDepth's 0.20e-3
  (2.4x less smooth), while per-frame Marigold remains *accuracy*-competitive
  (PointOdyssey AbsRel 14.9 vs DA V2 14.4). **The deficit is specifically
  temporal, not accuracy** — which is the exact distinction section 19 needs.

## 12.8 Licence findings worth recording

The family has a systematic licence-hygiene problem that the project's Week-3
standard would flag:

- **Marigold's `LICENSE-MODEL.txt` is an unfilled template** — its Attachment A
  "Use Restrictions" contains the literal placeholder `[insert use restrictions]`,
  so Section 5 binds a licensee to restrictions that are never enumerated
  [VERIFIED by direct fetch of the raw file]. The HF cards also disagree with the
  repo: `marigold-depth-v1-1` declares CreativeML Open RAIL++-M while
  `marigold-depth-v1-0` declares apache-2.0. Same family, same SD2 ancestry.
- **DepthCrafter is hard non-commercial** for code *and* weights: *"You agree to
  use the DepthCrafter only for academic, research and education purposes, and
  refrain from using it for any commercial or production purposes under any
  circumstances"*, with "Software" explicitly including the model weights.
- **Several SD/SVD/FLUX-derived checkpoints declare `apache-2.0` or `mit` on HF
  while their upstream weights are RAIL++-M / SVD-non-commercial /
  FLUX-non-commercial.** Lotus and ChronoDepth are both in this category.

None of these is disqualifying on its own for research use; all of them are
reasons this family is a poor fit for a pipeline that has been selecting on
clean Apache/MIT provenance since Week 3.


---

# 13. Underwater-specific models

## 13.1 The state of the subfield, stated bluntly

The underwater monocular-depth literature is numerically large and evidentially
thin. The dominant pattern, verified case by case: **weak venues, unreleased or
unlicensed code, supervision from pseudo-labels, and comparison only against
pre-foundation-model baselines.** Two structural facts govern how much of it can
be used:

1. **Most underwater "depth ground truth" is not measured** (section 15.2).
   USOD10K's depth maps are **DPT pseudo-labels**; BlueDepth's are an **ensemble
   of six monocular models**; TIDE's are generated. UDepth and Tree-Mamba are both
   supervised by such labels. Tree-Mamba's own paper states the problem outright:
   *"existing UMDE datasets usually contain unreliable depth labels."*
2. **Most underwater specialists never compare against a modern foundation
   model.** UDepth, UMono, CD-UDepth, Tree-Mamba, UDepthDiff and even SPADE
   (published in IEEE JOE in **2026**) benchmark against UW-GAN, UDepth, UW-Depth
   and 2019-2024 completion methods — **not** against UniDepth, Metric3D, Depth
   Pro or DA3. That is significant negative evidence about the subfield's
   evaluation hygiene, and it means most "SOTA underwater" claims are
   intra-underwater-literature claims.

**HuggingFace confirms the vacuum.** Searching `underwater` across the model hub
surfaces essentially no serious underwater depth model — the only relevant hits
are `lsxi77777/Wat3R` and a hobbyist
`hdnndh/NEMO-Underwater_Finetuned_DepthAnythingV2` with 4 downloads and no paper.

**And Week 3 supplies the sharpest cautionary precedent in the whole project
record:** the advertised "pretrained Water-VGGT model" has a **model state bitwise
identical, tensor for tensor, to `facebook/VGGT-1B`** (1797/1797 tensors, max abs
difference 0.0, zero underwater-specific modules). An underwater release claim is
not evidence of underwater adaptation. **Verify the checkpoint, not the paper.**

## 13.2 Wat3R — the one that clears the bar

```text
paper   "Wat3R: Underwater 3D Geometry Learning without Annotations"
        Jiangwei Ren, Xingyu Jiang, Zijie Song, Wei Xu, Hongkai Lin,
        Dingkang Liang, Xiang Bai (HUST). arXiv 2607.08772, 2026-07-09.
        Comments field: "Accepted to ECCV 2026"; repo says ECCV 2026 Oral.
repo    github.com/LSXI7/Wat3R  - 73 stars, pushed 2026-07-15   [CODE VERIFIED]
ckpt    HF lsxi77777/Wat3R - model.safetensors, 4,762,545,592 bytes confirmed
        by HTTP content-length; base model tag facebook/VGGT-1B  [CKPT VERIFIED]
licence CODE Apache-2.0 (GitHub API spdx_id + LICENSE file)
        CHECKPOINT apache-2.0 (HF cardData)          [BOTH LICENSE VERIFIED]
```

**Method:** teacher/student cross-domain semi-supervised adaptation of **VGGT** to
water. Labelled side = synthetic UIFM degradation applied to VGGT's own on-land
training data; unlabelled side = **~359k frames from 5,504 manually filtered real
underwater clips** (from ~10,000 raw), ratio 1:3, with a cross-view consistency
loss. Trained 19,200 steps on **4x RTX 4090**.

**Output:** pixel-aligned point maps + per-pixel depth + confidence + camera
extrinsics/intrinsics. **Affine (scale-and-shift) ambiguous, not metric** — the
evaluation protocol is explicit least-squares scale **and** shift. Real point
geometry, not a transmission proxy.

**It is the only underwater model with a fair-protocol head-to-head.** Its Table 4
uses a **single-view (monocular) protocol** with a **stated common alignment**
(least-squares scale and shift) applied to all methods, against **DAv2, DA3, VGGT,
pi^3, MapAnything, Fast3R, UDepth, UW-Depth and WaterMono** (Rel down / delta_1 up):

| Method | FLSea VI | SQUID | Sea-thru |
|---|---|---|---|
| UDepth | 0.212 / 0.683 | 0.312 / 0.547 | — |
| WaterMono | 0.074 / 0.949 | — | 0.145 / 0.829 |
| DA3 (zero-shot) | 0.090 / 0.936 | — | 0.111 / 0.950 |
| **Wat3R** | **0.061 / 0.971** | **0.107 / 0.893** | **0.090 / 0.976** |

[Numbers extracted from the paper HTML by an agent — **verify against the PDF
before quoting.**]

> ⚠️ **These numbers are NOT comparable with section 14.1's table.** Wat3R aligns
> with explicit least-squares **scale and shift**; Cai & Metzler use **raw metric,
> no alignment at all**. The FLSea subsets also differ (Wat3R: FLSea VI;
> Cai & Metzler: FLSea-Canyon and FLSea-Red Sea). **DA3's 0.090 here is not
> "better than" UniDepth V2's 0.1156 there.** They score different things.

### The decisive caveat: this project already has independent evidence

**Week 3 tested this exact model** (as `Wat3R-Ren`, configuration E) and found the
underwater adaptation **condition-specific with no material win**: better on one
wreck (3.5% vs 4.8%), tied on a second and on the reef swim-through, and
**clearly worse on the cenote (20.1% vs 13.1%, the worst dense result anywhere)**.

The agent sweep concluded *"no independent reproduction found"* for any underwater
depth model. **That is no longer true — this project is the independent
reproduction**, in multi-view. The comparison is not like-for-like (Week 3 ran the
multi-view path; the table above is single-view), but it is a real, measured
warning that Wat3R's advantage does not transfer to unfamiliar water and lighting.
That should temper the table above considerably, and it is exactly the kind of
evidence section 3.4 said to carry forward.

**Other honest limitations:** not metric; heavy (VGGT-1B, 4.76 GB, 518 px);
multi-view-native, so single-frame quality and stability need measuring; its
training video is forward-looking robot-survey footage, so the project's
`lights/` and `swimthrough/` categories are off-distribution; and its labelled
side is **synthetic UIFM degradation of in-air data — the same image formation
model this pipeline implements**, so depth from it is *not* independent evidence
that the physical model is right (a circularity worth recording).

## 13.3 The rest, graded

**Tier B — code verified, weights link live but not exercised:**

- **WaterMono** — arXiv **2406.13344**; **IEEE TIM 2025**. Repo
  `OUCVisionGroup/WaterMono`: **9 stars, 0 forks, 4 open issues**, 12 commits.
  **No LICENSE file at all.** Monodepth2/Lite-Mono lineage; teacher-guided anomaly
  mask for dynamic marine life; UIFM-based enhancement fed back into depth;
  rotation-robustness distillation. Output **disparity, scale-ambiguous**,
  448x288. Requires CUDA 11.7 / Ubuntu 18.04.
  **The protocol asymmetry that decides it:** WaterMono beats DA3 on FLSea VI
  (0.074 vs 0.090) — **but it trains on FLSea**, so that is an in-domain number.
  **Out-of-domain on Sea-thru it collapses to 0.145 against DA3's 0.111.**
  Combined with no licence and near-zero adoption, **WaterMono should be dropped
  from the shortlist.**
- **CD-UDepth** — Guo et al., **Information Fusion vol. 118, art. 102961, June
  2025**, DOI 10.1016/j.inffus.2025.102961 [PAPER VERIFIED] — a genuinely
  high-impact journal, unusual here. Repo `cainsmile/CD-UDepth`: **1 star, no
  licence.** **Built on UDepth as backbone**, inheriting its scale ambiguity and
  USOD10K pseudo-label supervision. **No comparison against any foundation model
  found.** Note: **it does not appear on arXiv** — journal-only.

**Tier A but disqualified on other grounds:**

- **UDepth** — arXiv **2209.12358**, ICRA 2023. Repo `uf-robopi/UDepth`, weights
  committed in-repo (62.7 MB). **⚠️ NO LICENSE — all rights reserved for code and
  weights.** Its RMI input space (R, Max(G,B), I) exploiting red-channel
  attenuation is conceptually interesting for this project's linear-light
  reasoning, but it is the **worst performer** in Wat3R's table (0.212 vs DA3's
  0.090) and is supervised by USOD10K pseudo-labels.
- **UW-Depth / TRUDepth** — arXiv **2310.16750**, ICRA 2024. Repo
  `ebnerluca/uw_depth`, **MIT** — the only cleanly-licensed metric option. **But
  it requires sparse triangulated depth priors at inference**; its metric claim
  comes from those priors, not the model. Disqualified as a monocular candidate
  (an untested `nullpriors` checkpoint exists).
- **SPADE** — arXiv **2510.25463**, **IEEE JOE 2026**. Repo
  `Jayzhang2333/Sparsity-Adaptive-Depth-Estimator`, **MIT**, but **weights say
  "coming soon" — NOT RELEASED**. DAv2-Small backbone + sparse priors. Its most
  valuable contribution to this review is not the model but its **"DA V2 + global
  alignment" baseline row** (section 21.2) and its observation that **caustics
  reduce relative-depth consistency** (section 19.5).

**Tier C — credible paper, no usable artifact:**
**UMono** (arXiv 2407.17838; **IEEE J. Oceanic Engineering** 2026) — no code.
**PUDE / Physics-Informed Knowledge Transfer** (**ECCV 2024**, DOI
10.1007/978-3-031-73209-6_26) — transfers an in-air model to water using physics
bound losses, **no GT depth needed**; strong venue, code not located.
**UW-Adapter** (**IEEE TMM** 27:4808-4818, 2025) — freezes a terrestrial
foundation model and trains only a *transmission adapter* and a *high-frequency
adapter*; **conceptually the closest thing to what this project would want, and
completely unobtainable** (no code, no weights, foundation model unnamed).
**Tree-Mamba** (arXiv 2507.07687) — repo is **0 KB, 1 commit, README only**,
untouched since a date that *predates its own arXiv posting*.
**Dense Geometry Supervision** (arXiv 2504.18233), **A Practical Approach to
Underwater Depth and Surface Normals** (arXiv 2410.02072 — note it **distils its
own teachers' output**, which CLAUDE.md's rule against imitating pipeline output
should flag).

**Tier D — treat as unsubstantiated:** **UDepthDiff** — Zhu & Xing, **IEEE Access
14:26953-26964, 2026**, DOI 10.1109/access.2026.3651731 [PAPER VERIFIED]. IEEE
Access is an APC-funded megajournal with light review; **no code, no weights, no
repo.** Like CD-UDepth, **it is not on arXiv.** Also in this tier: AquaDepth
(SSRN preprints only), LPTMono, MAU-Depth, Lpg-Lap Unet, and several
Ocean-Engineering/Applied-Soft-Computing entries — none with locatable code.

## 13.4 Underwater single-image geometry that is not called "monocular depth"

- **Osmosis** (arXiv **2403.14837**, **ECCV 2024**; Bar Nathan, Levy, Treibitz,
  Rosenbaum) — an **unconditional RGBD diffusion prior trained on in-air outdoor
  scenes**, applied to underwater restoration with guidance from the underwater
  image formation physics, **never having seen underwater imagery in training**.
  Conceptually the most interesting alternative in this review: it treats depth
  and colour as a *joint* prior rather than estimating depth then inverting.
  Not a monocular depth predictor, and it inherits every determinism concern in
  section 12.5 — but it is the closest published relative of this project's
  architecture and worth reading.
- **Atlantis** (arXiv **2312.12471**, **CVPR 2024 Highlight**) — repo
  `zkawfanx/Atlantis`, **MIT**. **What is released is the data-generation
  pipeline, not a depth model**; the README correctly redirects to MiDaS weights
  for depth. Journal extension **Atlantis++**, **IJCV** 134(6) art. 260, DOI
  10.1007/s11263-026-02823-1 (2026-05-07), claims a benchmark with *"controlled
  turbidity levels and colour casts"* — **exactly the controlled stress the field
  otherwise lacks. Springer-paywalled; contents UNVERIFIED. This is the single
  highest-value follow-up read in this whole review.**
- **Underwater 3DGS/NeRF** — SeaSplat (ICRA 2025), WaterSplatting (3DV 2025),
  UW-GS (WACV 2025), Gaussian Splashing (Sci. Reports 2026), ReefMapGS (arXiv
  2604.11992), Swimm3R (arXiv 2608.00950), NemoSplat (arXiv 2608.22888). All are
  **per-scene optimisation**, not single-image predictors. One is directly useful:
  **"Gaussian Splatting Underwater: A Controlled Cross-Regime Study"** (arXiv
  **2608.25483**, repo `olayasturias/uw3dgs`) — an *independent* controlled
  comparison of five public underwater-3DGS systems under shared poses, init,
  budget and evaluator. Two findings transfer directly: **SfM frame registration
  collapses from 99.5% success in clear water to 0.0% at 12 NTU**, and **moving
  artificial lights can make medium-aware systems *underperform* medium-blind
  ones.** The latter is a direct warning for the project's `lights/` category and
  for Wat3R specifically.
- **Sea-thru** (CVPR 2019) and **Haze-Lines / SQUID** (TPAMI 2020) — both
  **consume** or *estimate a transmission map*, not a geometric depth map.
  Sea-thru requires an input range map; it is a consumer of depth, not a source.

## 13.5 The verified negative results

Searched and confirmed absent — these matter as much as the positives:

1. **No published zero-shot underwater evaluation of DA3 (monocular), Marigold,
   MoGe, or MiDaS** other than inside Wat3R's own table.
2. **No underwater RoboDepth.** Nobody sweeps turbidity / backscatter strength /
   attenuation coefficient at **fixed geometry** and reports a degradation curve
   for foundation models. This is the gap section 20 identifies.
3. **No causal isolation of backscatter** as the corrupting factor — every paper
   bundles "attenuation, scattering, turbidity" as one domain shift.
4. **No measurement of depth quality before vs after restoration** — despite haze
   being a *deliberately exploited* underwater depth cue (Varghese et al., ICCV
   2023: *"UW depth estimation has been attempted before by utilizing either the
   haze information present or the geometry cue"*). The circularity in section
   20.2 is unmeasured by anyone.
5. **No temporal-stability evaluation of any depth foundation model underwater.
   Zero papers.**
6. **"DepthDive"** — surfaced in a search snippet as a LoRA underwater adaptation
   of Depth Anything. arXiv full-text search for `all:"DepthDive"` returned
   **totalResults=0**. No DOI, no repo. **Do not cite it.**

And one near-miss worth naming so it is not mistaken for coverage:
**DepthAnything-AC**'s fog is **not physical** — verbatim, *"Fog - Using the
**Diamond-Square algorithm** to generate a 2D self-similar noise field, where a
severity parameter controls fog density and texture."* That is a range-independent
texture overlay. It does not model the range-dependent veiling term
`B_inf (1 - exp(-beta_bs z))` that actually correlates with depth, which is the
entire mechanism of concern in section 20.


---

# 14. Underwater benchmark evidence

## 14.1 The one internally-consistent benchmark, and why its ranking is the wrong ranking for this project

**Cai & Metzler, "Underwater Monocular Metric Depth Estimation: Real-World
Benchmarks and Synthetic Fine-Tuning with Vision Foundation Models",
arXiv 2507.02148** (v1 2025-07-02, v2 2025-07-10; no venue stated).
[PAPER VERIFIED, full text checked]

This is the most relevant published evaluation in existence for Week 4A, and it
must be read carefully rather than cited for its winner.

**Setup.** 11,288 FLSea images (Canyon: `u_canyon` + `flatiron` = 5,369, 4-7 m;
Red Sea: `big_dice_loop` + `cross_pyramid_loop` + `coral_table_loop` + `sub_pier`
= 6,919, 3-8 m) plus all 57 SQUID pairs. Metrics: **AbsRel and delta_1 only**.
No enhancement or colour restoration applied to inputs. UW-Depth was correctly
**excluded from FLSea for training-data leakage**.

**Zero-shot results (AbsRel down / delta_1 up):**

| Model | FLSea-Canyon | FLSea-Red Sea | SQUID |
|---|---|---|---|
| ZoeDepth | 1.5907 / 0.2345 | 1.3335 / 0.2109 | 1.3214 / 0.0968 |
| Metric3D V2 (ViT-S) | 1.5331 / 0.0967 | 0.8130 / 0.2136 | 1.3059 / 0.1680 |
| Depth Pro | 0.9858 / 0.1557 | 0.3888 / 0.3772 | 3.2185 / 0.1678 |
| DA V2 (ViT-S) | 0.3576 / 0.4463 | 0.2569 / 0.4722 | 0.5242 / 0.2054 |
| DA V2 (ViT-B) | 0.2447 / 0.5696 | 0.2471 / 0.4301 | 0.4495 / 0.2649 |
| DA V2 (ViT-L) | 0.2269 / 0.6363 | 0.2307 / 0.4812 | 0.3390 / 0.2896 |
| UniDepth V2 (ViT-S) | 0.2233 / 0.6763 | 0.1524 / 0.8122 | 0.4012 / 0.4789 |
| UniDepth V2 (ViT-B) | 0.1276 / 0.8844 | 0.1045 / 0.9167 | 0.3638 / 0.4725 |
| **UniDepth V2 (ViT-L)** | **0.1156 / 0.9109** | **0.0932 / 0.9439** | **0.3222 / 0.5201** |
| UW-Depth | *omitted (leakage)* | *omitted (leakage)* | 0.4948 / 0.3446 |

> ⚠️ **These numbers are NOT comparable with Wat3R's table in section 13.2.**
> That table aligns with least-squares **scale and shift** on FLSea VI; this one is
> **raw metric with no alignment** on FLSea-Canyon / Red Sea. Never cross-read them.

### The decisive protocol finding

**This is a RAW METRIC benchmark with no alignment of any kind.** The paper's only
statement is *"All predictions are rescaled to match the dataset-specific depth
units."* The full v2 text was searched for `median`, `affine`, `align`, `scale`,
`cap`, `crop`: **there is no median scaling, no least-squares affine fit in any
representation, no depth cap at evaluation, and no Eigen/Garg crop.** The 20 m
"max depth" appears only in the *fine-tuning* configuration.

Four consequences, and they matter more than the table:

1. **AbsRel > 1.0 is a scale failure, not a shape failure.** ZoeDepth,
   Metric3D-S and Depth Pro are being scored on absolute units. A model with
   perfect relative shape and a 2x scale error scores *worse here* than a model
   with mediocre shape and lucky scale.
2. **The paper reports no affine- or median-aligned companion table**, so it
   **cannot separate scale error from shape error**. That is its single biggest
   gap, and it is exactly the separation section 17.2 requires (E1 vs E3).
3. **UniDepth V2 wins because it predicts scale from intrinsics** — it is
   optimised for precisely the axis this protocol rewards.
4. **Week 3 proved that axis is nearly free for this project.** A global
   multiplicative range error is absorbed exactly (`4.5e-13`). So *the ranking of
   the only good underwater monocular benchmark is, for the primary Week 5-6
   criterion, close to irrelevant.* It answers E3, not E1.

This does **not** make UniDepth V2 a weak candidate — it makes the *evidence* for
it weak in the dimension that matters. Week 4A must re-run this comparison with
aligned protocols before treating any of it as a shape ranking.

### A second protocol defect this project must not inherit

**SQUID's ground truth is Euclidean range**, stated consistently in the SQUID
paper as *"the true distance from the camera"*. Most of the benchmarked models
emit **z-depth**. The benchmark applies no conversion. That is an unexamined
systematic mismatch which inflates SQUID error for every z-depth model, **worst at
wide field angles** — i.e. the error grows exactly where a wide-FOV project cares
most. Part of the uniform SQUID difficulty (best delta_1 0.52 vs 0.94 on FLSea)
is likely this convention error rather than scene difficulty. Section 17.4's
conversion is mandatory; this paper is the cautionary example of skipping it.

### The fine-tuning result, reported honestly by its authors

DA V2 ViT-S fine-tuned on Hypersim RGB-D re-rendered through
`I_c = J_c*exp(-beta_c*z) + B_c_inf*(1-exp(-beta_c*z))` across Jerlov types
I, II, III and coastal 1C-9C (AdamW, lr 5e-6, 20 epochs, SiLogLoss, 518x518,
**first half of the ViT encoder frozen**, augmentation = random illumination +
grayscale):

| | FLSea-Canyon | FLSea-Red Sea | SQUID |
|---|---|---|---|
| Baseline (clean Hypersim) | 0.3576 / 0.4463 | 0.2569 / 0.4722 | 0.5242 / 0.2054 |
| Fine-tuned (synthetic UW) | 0.3620 / 0.4683 | 0.2266 / 0.6170 | 0.4465 / 0.3204 |

**Helps SQUID substantially and Red Sea clearly; flat-to-slightly-worse on
FLSea-Canyon** (0.3576 -> 0.3620 AbsRel). A genuine, honestly reported tradeoff —
and one that echoes Week 3's Wat3R-Ren result almost exactly: underwater
adaptation is *condition-specific*, not uniformly better. Two independent
observations of the same pattern is worth more than either alone.

Note also: the fine-tuned model is DA V2 **ViT-S**, and it does not overtake
zero-shot **UniDepth V2 ViT-L** on any column. Domain adaptation of a small model
did not beat architecture + scale + intrinsics-conditioning.

## 14.2 Everything else, and why the numbers do not stack

**Do not build a combined leaderboard.** These papers differ on zero-shot vs
retrained, metric set, alignment (raw metric / unstated / none), GT provenance
(SfM / stereo / pseudo-label), and test splits.

| Work | Setup | Comparable to 2507.02148? |
|---|---|---|
| **Atlantis** (arXiv 2312.12471, CVPR 2024 Highlight) | Trains iDisc and NeWCRFs on Atlantis; evaluates on Sea-thru D3/D5, SQUID. **Alignment protocol not stated.** | **No** — retrained not zero-shot, different splits, larger metric set, unstated alignment |
| **UW-Depth** (arXiv 2310.16750, ICRA 2024) | Supervised on FLSea; **fuses sparse triangulated-feature depth priors at inference** to resolve scale. Repo `ebnerluca/uw_depth` [VERIFIED] | **No** — it is not monocular-only; it consumes sparse depth priors |
| **Tree-Mamba / BlueDepth** (arXiv 2507.07687) | 13 methods **retrained** on BlueDepth. GT is a **6-model monocular pseudo-label ensemble** (AdaBins, DPT, Marigold, DA V1, DA V2, Lotus) over recycled Sea-thru/NYU-U/SQUID/FLSea/Atlantis/SUIM-SDA/USOD10K images | **No** — measures agreement-with-ensemble, not metric accuracy |
| **Dense Geometry Supervision** (arXiv 2504.18233) | Multi-view depth as supervision + enhanced images, evaluated on FLSea. Baselines/metrics/alignment **UNVERIFIED** | Unknown — insufficiently specified |
| **Atlantis++** (IJCV, DOI 10.1007/s11263-026-02823-1, 2026) | Exists; framed around *"the absence of high-quality benchmarks"*. **Paywalled, contents UNVERIFIED** | **Highest-value follow-up read** |

**A methodological paper worth reading before writing the 4A protocol:**
"Toward A Better Understanding of Monocular Depth Evaluation", arXiv **2510.19814**
(v1 2025-10-22, v3 2025-11-17) [PAPER VERIFIED] finds existing metrics
*"severely under-sensitive to curvature perturbation such as making smooth
surfaces bumpy"* and proposes a relative-surface-normal metric. Given that this
project cares about *local shape* far more than global scale, under-sensitivity of
AbsRel/delta_1 to exactly that is a direct warning.

## 14.3 The pseudo-label contamination problem

Three widely cited "underwater depth datasets" do not contain measured depth:

- **USOD10K** — depth maps are **DPT monocular pseudo-labels** (stated in the
  official repo acknowledgements) [VERIFIED].
- **BlueDepth** (Tree-Mamba) — labels are an **ensemble of six monocular models**
  [VERIFIED from the paper].
- **TIDE** (arXiv 2503.21771) — image *and* dense annotation are jointly
  generated [VERIFIED].

A model scoring well on any of these has matched a monocular predictor ensemble,
not reality. BlueDepth in particular is the item most likely to be mistaken for a
"2025 underwater depth benchmark". **None of these may be used as ground truth in
Week 4A**, and any paper whose headline result rests on them should be discounted
accordingly.


---

# 15. Public datasets relevant to Week 4A

## 15.1 The three real datasets with usable depth/range GT

### FLSea
```text
paper           arXiv 2302.12772 (2023-02-24) [PAPER VERIFIED]
                journal: J. Field Robotics, DOI 10.1002/rob.70291, 2026-07-08
                (Randall, Lifschitz, Treibitz) [PARTIALLY VERIFIED - Wiley 403]
real/synthetic  real
camera (stereo) 2x Nikon D810, 35 mm, opening angle 54.3 deg, 1280x720 @10 Hz,
                Hugyfot HFN-D810 housings, DOME PORT, rigid fixed baseline
camera (VI)     BlueROV2, iDS UI-3260CP, 4 mm, opening angle 80 deg, 968x608,
                VectorNav VN-100 IMU @100 Hz, BlueRobotics 4" tube, DOME PORT
environment     Mediterranean (Nachsholim canyons, 4-7 m) and Red Sea (Eilat,
                3-8 m). Natural light; caustics; some fixed-exposure clipping
GT source       SfM photogrammetry, Agisoft Metashape. Authors state explicitly
                they had no access to LiDAR
GT density      semi-dense - "white areas are where depth was not resolved"
metric?         YES - scale from measuring tape and known-size targets at 1 m
                spacing; validated against known measurements
range/z-depth?  NOT STATED. Called "depth maps" throughout; never disambiguated
counts          VI: 12 sets, 22,451 images. Stereo: 5 sets, 19,596 L/R pairs
                (note: v1 abstract says "5 stereo and 8 VI" but Table 3 lists 12
                VI, and Kaggle lists 12 VI + 4 stereo - three inconsistent counts)
licence         CC BY-NC-SA 4.0 [LICENSE VERIFIED]
download        Kaggle viseaonlab/flsea-vi (92.35 GB), flsea-stereo (90.65 GB)
                [DOWNLOAD VERIFIED]
```

### SQUID
```text
paper           arXiv 1811.01343; IEEE TPAMI 2020 (Berman et al.) [PAPER VERIFIED]
camera          2x Nikon D810 + AF-S NIKKOR 35 mm f/1.8G ED, Hugyfot DOME PORT.
                Authors state: "The pin-hole model holds since we use a dome port
                and a wide-angle lens, such that the lens entrance pupil is at the
                center of the dome, and there is no refraction at the interface
                between the water and the housing."
environment     4 Israeli sites: Katzaa (Red Sea reef, 10-15 m), Satil (Red Sea
                wreck, 20-30 m), Nachsholim (Med. rocky reef, 3-6 m), Mikhmoret
                (Med. rocky reef, 10-12 m). NATURAL LIGHT ONLY
GT source       stereo triangulation; MATLAB calibration, EpicFlow bi-directional
                dense matching, validity gate = end-point error <= 5 px
GT density      semi-dense; explicitly missing in low-texture and veiling-light
                regions ("impossible to triangulate")
metric?         YES - validated against colour charts of known size (12.5x18 cm)
range/z-depth?  EUCLIDEAN RANGE - "the true distance from the camera"
colour charts   YES, waterproof DGK charts at MULTIPLE known distances per scene
count/res       57 stereo pairs, 1827x2737. RAW + TIF + calibration + distance maps
licence         CC BY-NC-SA 4.0 [LICENSE VERIFIED]
download        Zenodo DOI 10.5281/zenodo.5744037, 45.8 GB [DOWNLOAD VERIFIED]
```

### Sea-thru
```text
paper           Akkaynak & Treibitz, CVPR 2019 [PARTIALLY VERIFIED - the CVF HTML
                returns 403 and the PDF text is stored as vector outlines and is
                not extractable, so paper-body claims could not be verified]
camera          NOT VERIFIED - do not assume
GT source       SfM, Agisoft Metashape Pro
GT density      semi-dense - "zero values in depth maps should be interpreted as
                NaNs ... Zero is not a valid depth value"
metric?         YES - "The depth maps are scaled (in meters)"
range/z-depth?  NOT STATED
count/format    ~1,100 images, 5 scenes (D1-D5). LINEAR PNG, no colour correction,
                0.3x original size. Original RAW on request
licence         CC BY-NC-SA 4.0 [LICENSE VERIFIED]
download        Kaggle colorlabeilat/seathru-dataset, 38.44 GB [DOWNLOAD VERIFIED]
```

### VAROS (synthetic, and the best plumbing check)
```text
paper           ICCVW 2021 (Zwilgmeyer et al., NTNU)
GT              rendered: dense hole-free metric depth, SURFACE NORMALS, GT poses,
                IMU @200 Hz, depth gauge. Blender ray-traced, simulated AUV
                dynamics, moving illumination
licence         CC BY 4.0 [LICENSE VERIFIED] - the only permissive licence here
download        Zenodo 10.5281/zenodo.5567209, SEQ1 18.0 GB [DOWNLOAD VERIFIED]
```

## 15.2 Datasets whose "depth" is NOT measured ground truth

| Dataset | What its depth actually is |
|---|---|
| **USOD10K** | **DPT monocular pseudo-labels** (official repo acknowledgement) [VERIFIED] |
| **Atlantis** (arXiv 2312.12471) | **Real terrestrial LiDAR** (DIODE-outdoor, FARO Focus, +-1 mm, MIT) + **generated** underwater images via a Depth2Underwater ControlNet. 3,200 pairs from 400 DIODE images. Real depth, fake water, **terrestrial scene geometry**. Kaggle, CC BY-NC-SA 4.0, code MIT [VERIFIED] |
| **BlueDepth** (Tree-Mamba) | **Ensemble of six monocular models** (AdaBins, DPT, Marigold, DA V1, DA V2, Lotus) over 38,162 recycled images [VERIFIED] |
| **TIDE** (arXiv 2503.21771) | Image and dense annotation **jointly generated** [VERIFIED] |

**UIEB, EUVP, LSUI, SUIM** contain **no depth GT at all** [all VERIFIED]. UIEB's
"reference" images are *selected*, not measured.

## 15.3 The finding that governs how these datasets may be used

**Essentially no underwater depth-GT dataset uses a flat-port wide-FOV camera.**

| Dataset | Port | FOV | Depth GT |
|---|---|---|---|
| FLSea stereo | **Dome** | **54.3 deg** | Yes |
| FLSea VI | **Dome** | **80 deg** | Yes |
| SQUID | **Dome** | ~54 deg | Yes |
| Sea-thru | not stated | not stated | Yes |
| **SubPipe** | **GoPro Hero 10 (flat port)** | wide | **No dense depth GT** |

SQUID's authors chose a dome **specifically so that refraction is eliminated and
a pinhole model holds**. A GoPro flat port is the opposite case by construction.
The only verified GoPro underwater dataset, **SubPipe** (arXiv 2401.17907, Zenodo
10.5281/zenodo.10053564), has **no dense depth ground truth** — only vehicle
pressure-depth, altitude, segmentation masks and sonar. It does publish full
intrinsics (1520x2704, fx 1612.36, fy 1622.56, cx 1365.43, cy 741.27, distortion
[-0.247, 0.0869, -0.006, 0.001]) [VERIFIED via official repo README], which makes
it usable for **optics-realism stress** but not for scoring depth.

## 15.4 Which dataset answers which Week-4A question

```text
wrapper / plumbing correctness   VAROS first (dense, hole-free, normals, poses -
                                 a loader or unit bug shows immediately), then
                                 Sea-thru (explicit: linear PNG, metres, 0 = NaN).
                                 Do NOT use FLSea/SQUID - their GT holes will be
                                 misread as loader bugs.
raw metric accuracy (E3)         FLSea (only real metric set with volume), SQUID
                                 as the harder secondary check.
relative shape (E1)              SQUID - independent stereo triangulation at
                                 1827x2737 with an explicit <=5 px validity gate,
                                 plus charts of known size. Sea-thru second.
                                 MUST add an alignment step; 2507.02148 does not.
near/far systematic bias         SQUID, uniquely - charts at MULTIPLE known
                                 distances per scene, and sites spanning 3-6 m to
                                 20-30 m (a 10x span). FLSea tops out ~12 m.
underwater domain-shift stress   Stratify WITHIN the real sets: SQUID Satil
                                 (20-30 m blue) and Michmoret/Nachsholim
                                 (temperate, murkier) vs Katzaa (tropical);
                                 FLSea Canyons vs Red Sea.
severe colour cast               SQUID - natural light only, RAW/linear TIF,
                                 charts at multiple distances, Jerlov-diverse.
moving subjects                  NONE. See 15.5.
low texture                      Synthetic only (VAROS, UWStereo). See 15.5.
```

## 15.5 Two holes that Week 4A must not paper over

**Moving subjects: no public underwater depth GT exists.** Every real GT source
here — FLSea (Metashape SfM), SQUID (stereo + EpicFlow), Sea-thru (Metashape SfM)
— assumes a **static scene**. FLSea advertises "dynamic underwater environments",
but that refers to *camera* motion. Moving fish are exactly where photogrammetric
GT fails and gets masked out. Since Week 3 found MapAnything's worst failure is
precisely on the dynamic-diver clip, this is a hole the project feels directly.

**Low texture: evaluating on valid pixels only is optimistically biased exactly
where this project fails.** SQUID and FLSea both **delete their GT in low-texture
regions** — SQUID says so outright. Week 3 found low SIFT-observation clips are
where classical geometry stops being identified. So the public datasets mask out
the failure mode the project most needs measured. Real-data low-texture scores
must be reported as **unmeasured**, not as passes.

A third, quieter hole: **there is no published underwater depth benchmark with
temporal-stability metrics at all.** For a video-first pipeline that is a
first-order concern, and it means section 19's evidence must come from
terrestrial video-depth papers plus this project's own measurements.

## 15.6 Honest limits on generalising to GoPro reef footage

1. **Optics mismatch is fundamental, not cosmetic.** Every depth-GT dataset uses
   a dome port chosen to *eliminate* refraction. A flat port multiplies effective
   focal length by ~1.33, compresses FOV, and adds wavelength-dependent radial
   distortion growing toward frame edges.
2. **FOV mismatch of roughly 2x** — 54-80 deg vs the project's measured
   105.383 deg ZFOV. Metric models infer scale partly from FOV priors; this is
   *why* UniDepth V2 wins in 14.1, and it is exactly the prior most disturbed.
3. **Range mismatch.** FLSea ~0-12 m; SQUID reaches 30 m but with 57 pairs.
4. **Geography.** Everything real is Israeli — Mediterranean and Gulf of Aqaba.
   No Indo-Pacific or Caribbean reef; different Jerlov type, particulate load and
   reef morphology.
5. **GT is not independent of the images.** FLSea and Sea-thru GT is SfM from the
   same frames; SQUID is optical-flow stereo. All inherit photometric-consistency
   assumptions that scattering violates. This is the same epistemic caution
   Week 3 applied to its own COLMAP reference (section 3.3).
6. **Encoding mismatch.** Sea-thru ships linear PNG at 0.3x; SQUID ships RAW/TIF;
   GoPro delivers compressed 8-bit Protune. **None of these datasets exercises the
   project's GoPro transfer-function ingest path** (Invariant 1), so a depth stage
   validated on them entered linear light by a completely different route.

**Bottom line.** These datasets can establish that the plumbing is correct
(VAROS/Sea-thru), that relative shape is sane underwater (SQUID, with alignment),
and roughly how error grows with range (SQUID stratified). They **cannot**
establish that any model works on flat-port wide-FOV GoPro reef video. That gap
is C2's job, and section 26 keeps it there.


---

# 16. Camera-model implications for GoPro / flat-port footage

## 16.1 What the footage actually is (measured in Week 3, not assumed)

All six Week-3 development clips are one **GoPro HERO9 Black**, one lens serial,
one firmware. Five share an identical capture mode: **Wide, digital zoom off,
HyperSmooth Boost, ZFOV 105.383 deg**. Only `cenote_01` differs. Critically:

- **EIS is on in every clip** (`EISE = Y`), output projection `PRJT = GPRO`.
- `wreck_01`'s portrait decode is `OREN = R`, a rotation flag with identical FOV.

Three things follow that bear directly on monocular model selection.

**(a) The effective intrinsics are time-varying.** HyperSmooth is an
electronic stabiliser: it crops and warps per frame. The per-frame effective
focal length and principal point are therefore not constant, and `PRJT = GPRO` is
a proprietary output projection, not a documented pinhole or Kannala-Brandt
model. Any candidate whose metric scale is a documented function of supplied
focal length inherits this uncertainty directly.

**(b) FOV-destroying preprocessing is a measured, not hypothetical, risk.**
Week 3 measured that the VGGT family **discards ~44% of the vertical field of
view on portrait clips**, and Phase 3B established this was a *preprocessing
artefact of that family*, not a footage property — the classical arm had no FOV
confound on the same clip. Every monocular candidate must therefore have its
preprocessing audited for crop/letterbox/resize behaviour before any accuracy
number is believed. This is a wrapper-correctness check, and it belongs in
Week 4A's earliest measurement category.

**(c) Wide FOV makes the z-depth/range distinction large**, per section 17.4.

## 16.2 Central vs non-central: the distinction that must not be blurred

A flat port in water is a **non-central** imaging system. Refraction at the
air-glass-water interfaces means the back-projected rays do not intersect in a
single point; they are tangent to a caustic, and the system is at best *axial*
(rays intersect the optical axis, but at different points). The correct forward
model has a **per-pixel ray origin**, not merely a per-pixel ray direction.

This is the discrimination the brief demands, and it is worth stating sharply:

> A network that predicts a different ray **direction** per pixel, all emanating
> from one common origin, is modelling an arbitrary **central** camera. It is not
> modelling a refractive flat port, no matter how general its camera
> parameterisation is.

Depth Anything 3 is a clean illustration. Its representation is genuinely a
per-pixel 6-vector `r = (t, d)` with an origin `t` and a direction `d`
(`d = R K^-1 p`, deliberately unnormalised so that `P = t + D*d` recovers points).
The *format* admits per-pixel origins. But `t` is the camera centre of the view,
shared by every pixel of that view. So DA3 is central. The same reading must be
applied to every "any-camera" claim in section 11: the question is not whether
the model has a ray field, it is whether the origins differ per pixel and whether
anything in training ever supervised that.

## 16.3 Why this is nonetheless *not* a reason to chase a refractive model in Week 4

Three project facts, all established rather than assumed:

1. **Refraction is currently not identified.** Week 3 retired the refractive
   cross-check because `colmap_underwater` with refraction on is **not a
   reproducible instrument** (44, 16, 44 registered frames across three identical
   runs of one clip; a 22x point-count spread on another). PLAN.md requires an
   effect to exceed run-to-run spread; nothing came close.
2. **The refraction answer is dominated by an unmeasured parameter.** A 25x
   change in assumed camera-to-port stand-off moved the implied scale 172x and
   the recovered focal 3x. C2 must *measure* stand-off and port thickness.
3. **Where reconstruction did run with fixed port parameters, bundle adjustment
   drove the scene to ~10^6 times the stand-off**, where modelled refraction is
   numerically negligible.

Meanwhile Phase 3B found that among *central* camera models, well-conditioned
clips are stable to <= 1.5% across four different projection families, and an
equal-capacity fisheye changed `wreck_05` by 0.8% — i.e. **capacity, not
projection family**, drove the differences. That is direct evidence that on this
footage, at this stage, the central-camera approximation is not the binding
constraint.

**Therefore:** non-central modelling is correctly classified as a *Week 4B / post-C2
question*, and "any-camera" capability should be treated in Week 4A as a
**conditional challenger trigger** (wide-FOV/distortion error dominates), not as a
primary selection criterion. Buying an any-camera model now would buy more
disagreement between unanchored hypotheses — the same argument Week 3 used to
decline adding more geometry models.

## 16.4 The practical preprocessing decision Week 4A must make explicit

Three admissible input conventions, which must be fixed and recorded, because
they are not interchangeable and they silently change every number:

```text
P0  native GoPro frame, model's own preprocessing, model-predicted intrinsics
P1  native frame, known/estimated K supplied where the model's documented
    monocular API accepts it
P2  undistorted-to-pinhole (and necessarily cropped) frame
```

P2 discards field of view and therefore discards scene content the restoration
needs; P0 feeds a wide, EIS-warped, GPRO-projected frame to models overwhelmingly
trained on narrower pinhole-ish imagery; P1 is only available where the model's
monocular path genuinely supports it (per section 7, several do not, and supplying
intrinsics to a model that merely *predicts* them is not the same thing).

This is a measurement category for Week 4A, not a decision to make from the
literature. No paper found in this review measures the P0/P1/P2 tradeoff on
flat-port underwater wide-FOV footage.


---

# 17. Output semantics and permitted alignment

This section is the analytical core of the review. It is written before the
candidate tables because it changes which candidates are admissible.

## 17.1 The physical argument, done properly

The observation model is

```text
I_c(x) = J_c(x) * exp(-beta_att_c * d(x))
       + B_inf_c * (1 - exp(-beta_bs_c * d(x)))
```

### Pure multiplicative scale: exactly absorbable

Substitute `d -> s*d`, `beta_att -> beta_att/s`, `beta_bs -> beta_bs/s`.
Both exponents `beta*d` are invariant, so **both** the direct-transmission term
and the backscatter term are invariant, exactly and for every pixel. Week 3
confirmed this numerically (`max |dJ/J| = 4.5e-13` over a sweep to `s = 3.2`).

### Additive range offset: NOT absorbable, and the failure is in the backscatter term

Substitute `d' = s*d + t` and allow the coefficients to be refitted freely.

*Direct term.* Requiring `exp(-beta'_att * d') = exp(-beta_att * d)` for all `d`
forces `beta'_att = beta_att/s` from the `d`-linear part, leaving a residual
**constant** factor `exp(-beta'_att * t)`. This is degenerate with a per-channel
radiometric gain on `J`. So the shift is absorbable here only by aliasing into a
per-channel gain — i.e. it converts a range error into a **global colour cast**.
Because `beta_att` differs per channel, the aliased gain differs per channel.
It is absorbable arithmetic, but it is not free: it corrupts exactly the quantity
the project scores (chart deltaE).

*Backscatter term.* Requiring
`B'_inf * (1 - exp(-beta_bs*d - beta'_bs*t)) = B_inf * (1 - exp(-beta_bs*d))`
for all `d`, write `e = exp(-beta_bs*d)` and `k = exp(-beta'_bs*t)`:

```text
B'_inf * (1 - k*e) = B_inf * (1 - e)   for all e in (0, 1]
constant part:  B'_inf = B_inf
linear in e:    B'_inf * k = B_inf   =>  k = 1  =>  t = 0
```

So **no choice of refitted `B_inf` and `beta_bs` absorbs an additive range shift
in the backscatter term.** The residual is spatially varying (it is a function of
`d(x)`), so it cannot be removed by any global correction downstream.

*Boundary condition.* `d = 0` is physically meaningful: zero water path must
produce zero water-column attenuation and zero backscatter. Any `t != 0` predicts
`B_inf * (1 - exp(-beta_bs * t))` of backscatter at zero water path. The model is
not merely mis-parameterised, it is outside its own physical family.

**Conclusion.** Week 3's scale-invariance result must not be casually generalised
to affine invariance. Scale is free. Shift is not.

### Affine ambiguity in *disparity* is a different and worse animal

Many relative-depth models (the MiDaS / Depth Anything V1-V2 lineage) are
scale-and-shift invariant in **disparity / inverse depth**, not in depth. If

```text
disp_pred = a * (1/d_true) + b
```

then recovering depth gives

```text
d_pred = 1 / (a/d_true + b)  =>  d_true = a / (1/d_pred - b)   (equivalently)
```

which is a **Mobius transform of range**, not an affine one. Three consequences,
all of which are on Week 3's list of dangerous errors:

1. **Nonlinear range compression/expansion.** Near and far range are deformed by
   different local gains. This is precisely the "spatially varying multiplicative
   error" category, arriving as a systematic function of depth.
2. **A finite depth horizon.** As `disp_pred -> b`, `d -> infinity`. A small error
   in the fitted `b` creates a hyperbolic blow-up at long range. Long range is
   exactly where `beta*d` is largest and where the restoration is most sensitive.
3. **The error is invisible to the usual metric.** Standard evaluation of these
   models fits `a, b` in disparity and reports AbsRel in depth on a capped range.
   That protocol hides the far-field blow-up that this project cares about.

### The resulting ordering of ambiguity classes, best to worst, for THIS application

```text
CLASS 1  RAW METRIC                       no alignment needed
CLASS 2  SCALE-ONLY IN DEPTH/RANGE        exactly absorbable (Week 3 proven)
CLASS 3  AFFINE (SCALE + SHIFT) IN DEPTH  shift unabsorbable in backscatter;
                                          breaks the d = 0 boundary condition
CLASS 4  AFFINE IN DISPARITY/INVERSE      Mobius range deformation + finite
                                          depth horizon; worst for restoration
```

This ordering is a *project-specific* ranking. It does not track generic
benchmark quality at all, and it is the single most important reordering this
review applies to the supplied shortlist.

## 17.2 The three evaluations, kept separate

Per the brief, three questions must never be collapsed:

**(E1) Oracle structural evaluation.** Grant the model exactly the ambiguity it
legitimately claims, fitted per image against reference range, and ask whether
the remaining spatial geometry is right. This is the ceiling. It answers "is the
shape correct", not "is it deployable".

**(E2) Deployable frozen calibration.** Fit one calibration on allowed
calibration evidence, freeze it, reuse it unchanged on held-out clips. This is
what actually ships. The gap between E1 and E2 is the cost of not having per-image
ground truth.

**(E3) Raw metric prediction.** No alignment at all. Only meaningful for Class 1
models. This is what matters for cross-clip coefficient transfer, artificial-light
falloff modelling, and camera-to-light geometry.

A model can win E1 and lose E2 badly — that is the *expected* failure for a
Class 3 or Class 4 model whose ambiguity parameters drift per image. Reporting
only E1 would hide it. Reporting only E3 would wrongly eliminate a structurally
excellent relative model.

## 17.3 Alignment must be fitted in the model's native representation

The rule this project should adopt:

> Fit the ambiguity in the representation the model's own training loss
> normalised, then transform to range. Never fit `d_gt = a*d_pred + b` by default.

Concretely: for a Class 4 model, fit `(a, b)` in disparity and then invert;
do not fit an affine map in depth, because that is not the model's invariance and
it will flatter or punish the model arbitrarily. For a Class 2 model, fit one
scalar; granting it a shift it never claimed is a gift that inflates E1 and
guarantees the E1->E2 gap is misread.

## 17.4 z-depth is not range, and the conversion is exact only with intrinsics

The project's canonical quantity is `water_path_length`. For a central camera
this is range along the viewing ray. Several leading models natively emit
**z-depth** (distance along the optical axis), not range. The conversion

```text
range(u,v) = D_z(u,v) * || K^-1 [u, v, 1]^T ||
```

is **exact**, but only given `K`. Two project-specific consequences:

- On a ~105 deg horizontal FOV GoPro frame the ratio `|| K^-1 p ||` reaches
  roughly `1 / cos(theta)` at the field edge, so z-depth and range differ by tens
  of percent in the corners. Treating z-depth as range is therefore not a small
  approximation here; it is a large, *spatially structured* error concentrated at
  the frame edge — the exact shape of error Week 3 identified as dangerous.
- The conversion inherits the uncertainty in `K`. With EIS active and an
  unmeasured effective focal length, `K` is itself provisional. The
  z-depth -> range conversion should therefore be recorded per candidate as
  `transformed_exactly (conditional on K)` rather than `measured`.

Models that natively emit a point map or a radial/ray distance (MoGe family,
UniDepth's pseudo-spherical output, MapAnything's `depth_along_ray`) avoid this
step entirely. Week 3 already verified MapAnything's
`depth_along_ray == ||pts3d_cam||` to 1.1e-5, and the same verification must be
run for every monocular candidate rather than assumed from documentation.


---

# 18. Confidence / uncertainty evidence

## 18.1 The project's calibrated prior

Week 3 measured MapAnything's confidence and found its **low-confidence pixels
are only 1.07x worse than its high-confidence ones**. That is close to
uninformative. Nothing in the monocular literature reviewed here justifies
raising expectations, and several findings justify lowering them.

## 18.2 What the released models actually emit

| Model | Emits | What it actually is | Calibration evidence |
|---|---|---|---|
| **DA3** | `depth_conf`, `ray_conf` | Activation `expp1` = `exp(x) + 1`, so **confidence >= 1, unbounded above**. The loss is `L_D = (1/Z) SUM m_p (D_c,p * |D_hat - D| - lambda_c log D_c,p)` — a **Laplace negative-log-likelihood precision weight, not a probability** | **None in paper or repo** |
| **UniDepth V2** | uncertainty output | Added in V2 alongside the edge-guided loss; *"an additional uncertainty-level output which enables downstream tasks requiring confidence"* | **None found** |
| **MoGe / MoGe-2 / MoGe-3** | `mask` | A **validity/infinity mask**, not a confidence — it marks where geometry is defined (e.g. sky), not how much to trust it | N/A |
| **MapAnything** | mask + confidence | (Week 3, measured) | **1.07x separation — measured, and near-useless** |
| **Depth Anything V2** | **nothing** | Code-verified by absence: `forward` returns a single tensor; `infer_image` returns `depth.cpu().numpy()` | N/A |
| **Marigold / DepthFM** | ensemble disagreement | Genuine **epistemic** signal from seed variance — but only available by paying for an ensemble, and it forfeits determinism | Qualitative |
| **DAGE** | deliberately none | *"we do not attenuate errors with confidences, as we found this can suppress hard structures and reduce sharpness"* | N/A |

The DA3 detail deserves emphasis because it is the most likely to be misused:
**`expp1` output is a precision term in a Laplace likelihood.** It is a *relative
reliability ordering* learned jointly with the depth loss. It is not a
probability, not a variance in metres, and has no documented mapping to error
magnitude. Any Week-4A use must treat it as an ordinal, and must **measure the
error separation directly** — Week 3's 1.07x number is the template.

## 18.3 The best available synthesis, and its limit

**Landgraf, Qin & Ulrich, "A Critical Synthesis of Uncertainty Quantification and
Foundation Models in Monocular Depth Estimation"**, arXiv **2501.08188**
(2025-01-14) [PAPER VERIFIED]. It fuses **five UQ methods with Depth Anything V2**
across **four datasets** for metric depth, and concludes that **fine-tuning with
the Gaussian Negative Log-Likelihood loss (GNLL)** is the most promising —
reliable uncertainty at preserved accuracy and efficiency.

**The limit, and it is the whole story for this project:** the abstract makes no
claim about distribution shift or out-of-distribution evaluation, and none was
found in the accessible material [OOD calibration UNVERIFIED / apparently absent].
So the field's best synthesis on depth UQ is **in-distribution evidence**.

## 18.4 The honest state of the art

> As of September 2026, **no released monocular depth model emits a confidence map
> with published evidence that it stays calibrated under domain shift**, and none
> has been calibrated on underwater imagery at all.

Consequences for Week 4A:

1. **Confidence is a candidate feature to be measured, never a feature to be
   trusted.** The acceptance test is an error-separation ratio measured on this
   project's own footage, reported alongside Week 3's 1.07x baseline so the two
   are comparable.
2. **Confidence jitter is itself a listed concern** (section 11 of the brief).
   A confidence map that is uninformative *and* unstable is worse than none,
   because it invites masking decisions that vary frame to frame.
3. **The GNLL result is a Week-4.5 lead, not a Week-4A one.** It requires
   fine-tuning, which section 21 keeps out of the primary bakeoff.
4. **An underwater-specific hazard:** a confidence head trained on in-air data has
   never seen backscatter. The most likely failure is that it reports *high*
   confidence in the low-contrast far field — where the geometry is worst and the
   restoration budget is tightest (section 2.2). That specific inversion should be
   tested explicitly rather than assumed.


---

# 19. Independent-frame temporal consistency evidence

## 19.1 The mechanism is known, and it is the best news in this review

**DyFN — "Stabilizing Streaming Video Geometry via Dynamic Feature
Normalization"**, Lyu, Liu et al. (HKU / USTC / Voyager), arXiv **2605.25308**
(2026-05-25) [PAPER VERIFIED] runs the one ablation that separates the two
competing explanations for per-frame flicker. Verbatim:

> "**We find that the model's underlying geometric understanding is already
> robust.** ... when fusing the predicted point clouds using a **single
> sequential alignment (one scale/shift for the entire sequence)**, the
> reconstruction suffers from severe non-rigid warping and geometric drift,
> achieving an accuracy (delta < 1.25) of **only 62.5**. In stark contrast, when
> we align **each frame individually (per-frame scale and shift)**, the accuracy
> dramatically increases to **99.8**. **This reveals that the primary cause of
> temporal inconsistency is not geometric degradation but rather frame-to-frame
> scale-shift variation.**"

They trace it one level further:

> "**the mean and variance of latent features are strongly coupled with the
> prediction's scale and shift, but are largely decoupled from its relative
> geometric accuracy.** ... uncontrolled fluctuations in these feature statistics
> across a video stream are the direct cause of the observed scale-shift drift."

**Caveat, and it matters:** the representative model in that study is **MoGe**,
not Depth Anything V2. The 62.5 / 99.8 figures are MoGe-specific; DyFN's DA V2
tables are rendered as figures and could not be extracted
[DA V2-specific numbers UNVERIFIED].

Independent corroboration from **oVDA** (arXiv **2510.09182**, Heidelberg):
*"applying such a non-metric, i.e. scale- and shift-invariant, single-image
method to each frame of a video sequence, naturally produces temporally
flickering depth maps"* — and its only quantitative temporal figure is a **scale-
drift curve**. Video Depth Anything attributes flicker instead to training data
(*"trained exclusively on static images"*), which is a *cause of*, not an
alternative to, the affine account. **No paper found claims the opposite.**

### Why this reframes the whole risk

The project's fallback-video use case runs the model independently per frame and
was expected to suffer. The literature says the damage is concentrated in the
**ambiguity parameters**, not in the geometry — and section 17.1 established that

```text
a pure global scale wobble is absorbed EXACTLY (Week 3: 4.5e-13)
a shift wobble is NOT
```

So per-frame instability is **conditionally survivable**, and the condition is
precisely the model's ambiguity class. A Class-2 (scale-only in depth) model that
breathes in scale is nearly harmless. A Class-3 or Class-4 model that breathes in
its shift or disparity offset is not. This turns section 17's taxonomy from a
static property into the dominant predictor of temporal behaviour, and it means
the right Week-4A measurement is **not** "how much does the depth map change"
but "**how much of the change lives in the legal ambiguity, and how much
survives fitting it**" — the same decomposition section 20.5(3) demands.

## 19.2 The cheapest possible diagnostic, requiring no flow and no poses

Directly implied by DyFN, and it fits this project's constraints exactly:

> Run the clip twice — once aligned with **a single global scale (+shift)** for
> the whole clip, once with **per-frame** alignment. The gap between the two
> curves *is* the affine-drift component. Whatever remains is genuine prediction
> noise.

No optical flow, no ground-truth poses, no extra model. It should be the first
temporal measurement Week 4A runs.

## 19.3 Published per-frame flicker numbers

**Temporal Alignment Error (TAE)**, ScanNet 170-frame sequences, from Video Depth
Anything (arXiv **2501.12375**, CVPR 2025) [PAPER VERIFIED]. VDA states its
baseline protocol verbatim: *"For Depth-Anything-V2, we obtain the video depth
results by inferring each frame individually with a minimum dimension of 518."*

| Method | ScanNet-170 TAE (lower better) |
|---|---|
| **DA V2-L (per-frame)** | **1.140** |
| NVDS | 2.176 |
| NVDS + DA V2-L | 2.536 |
| ChronoDepth | 1.022 |
| DepthCrafter | 0.639 |
| VDA-S | 0.703 |
| **VDA-L** | **0.570** |

Two readings. First, a dedicated video model halves per-frame DA V2-L's error —
real, but a factor of two, not an order of magnitude. Second, and more useful:
**NVDS variants are *worse* than the naive per-frame baseline.** A temporal module
does not automatically help. That is a direct warning against reaching for video
depth as a reflex.

**OPW (optical-flow-based warping error)** from NVDS+ (arXiv **2307.08695**,
ICCV 2023 + TPAMI 2024):

| Method | VDW | Sintel | NYUDv2 | KITTI |
|---|---|---|---|---|
| MiDaS-v2.1-Large (per-frame) | 0.676 | 0.843 | 0.862 | 0.602 |
| DPT-Large (per-frame) | 0.470 | 0.612 | 0.811 | 0.585 |
| NVDS+-Large | **0.129** | **0.403** | **0.339** | **0.233** |

**StableDPT** (arXiv **2601.02793**, 2026-01-06) opens: *"Applying single image
Monocular Depth Estimation (MDE) models to video sequences introduces significant
temporal instability and flickering artifacts."* On Infinigen, per-frame DA V2 ->
VDA is a **~33% OPW** and **~29% TGM** reduction — a **much smaller gap than
MiDaS's**, i.e. **DA V2 is already substantially more stable per-frame than the
MiDaS generation.** Modern foundation models have improved on this axis.

**Which metric this project can actually use.** **TAE requires ground-truth
camera poses** (its transform comes from dataset intrinsics and extrinsics) —
unavailable on GoPro footage. **OPW needs only optical flow**, which Week 2A
already built a backend bakeoff for:

```text
OPW = 1/(N-1) SUM_n (1/M) SUM_j  O_(n=>n-1)^(j) * | D_n^(j) - D_hat_(n-1)^(j) |
```

where `D_hat_(n-1)` is `D_(n-1)` warped into frame `n` by flow. **OPW is the
right choice**, and it composes with the Week-2B temporal-stability machinery.

**A comparability warning:** TAE is **not comparable across papers.** Its
originator, Depth Any Video (arXiv **2410.10815**), normalises by `1/(2(T-2))`
summing `k = 0..T-1`; VDA restates it as `1/(2(N-1))` summing `k = 1..N-1`.
Different constants. StableDPT separately warns that **TGM structurally favours
models trained with the TGM loss**. Do not cross-cite these numbers.

## 19.4 The boundary-jitter metric nobody else reports

**DAGE** (arXiv **2603.03744**, **CVPR 2026**) is the only work found that
measures depth-**edge** temporal stability rather than depth-value stability:

> "Because F1 does not reflect temporal stability, we also measure the pseudo
> depth boundary error (C_PDBE), defined as the Chamfer distance between
> prediction and ground-truth at canny-detected edges. ... While DepthPro attains
> a higher F1 on some datasets, DAGE yields lower C_PDBE — indicating more
> temporally consistent boundaries in the video setting."

It also diagnoses the exact failure this project would hit: *"single-view geometry
estimators ... produce sharp, detail-rich depth/pointmaps from single images, yet
they **lack temporal and multi-view consistency by design**"* and *"these methods
typically exhibit **temporal jitter and inconsistent scale** when applied to
videos."*

DAGE itself is **not a candidate** — it is multi-view by construction (a
sequence-level global-attention stream that degenerates at N=1), its code carries
**CC BY-NC 4.0** (in a file named `license.md`), and its checkpoint `TuanNgo/DAGE`
declares **no licence at all** on HuggingFace. Its value here is the **metric**:
a Chamfer distance at Canny edges between consecutive frames is a cheap,
pose-free, GT-free jitter measure this project can adopt directly, and depth-edge
position jitter is explicitly on the project's list of concerns.

One design note from DAGE worth recording, because it cuts against MoGe:

> "MoGe applies a multi-scale affine-invariant pointmap loss by subsampling local
> regions ... While this improves single-image sharpness, we found that
> **per-region independent alignments introduce patch-wise degrees of freedom
> that break cross-view consistency, leading to seams and drift**."

That is a specific, mechanistically-argued prediction that **MoGe may be less
temporally stable than its single-image sharpness suggests**. It should be tested
in Week 4A rather than assumed either way — and it is a reason not to select
MoGe-2 on single-image sharpness alone.

## 19.5 The underwater gap

**No temporal-stability evaluation of any depth foundation model underwater
exists. Zero papers** [searched and confirmed absent]. There is also no underwater
depth benchmark with temporal metrics at all (section 15.5). Everything in 19.3
is terrestrial, indoor, or automotive.

Two project-specific aggravators the terrestrial numbers do not capture:

- **EIS is on in every clip** (`EISE = Y`, HyperSmooth Boost). The stabiliser
  crops and warps per frame, so the effective intrinsics vary frame to frame.
  A model whose scale prior is coupled to focal length (section 11/16) will
  therefore breathe *even on a static scene* — a mechanism absent from every
  published measurement.
- **Caustics.** SPADE (arXiv **2510.25463**) notes verbatim that *"unique
  underwater lighting effects, such as **caustics**, can reduce relative depth
  prediction consistency in regions with rapidly changing illumination"* — moving
  illumination patterns that are pure appearance and pure temporal noise.

So Week 4A must measure per-frame stability on this project's own footage; the
literature supplies the metric (OPW), the decomposition (DyFN), and a rough
expectation, but no transferable number.


---

# 20. Underwater appearance / domain-shift analysis

## 20.1 The cue is real, and that is exactly the problem

Underwater image formation makes appearance a **monotone function of range**:

```text
greater range -> greater wavelength-dependent attenuation
             -> more backscatter / veiling light
             -> lower contrast
             -> stronger, range-dependent colour shift
```

So a monocular network that reads contrast and colour as distance is not making a
mistake in the usual sense. It is exploiting a **genuine physical regularity**.
The literature confirms the regularity is strong enough to invert: the entire
single-image dehazing tradition estimates a transmission map `t = exp(-beta*d)`
and treats it as depth, and the underwater variants (UDCP, Berman's
non-local/haze-lines) do the same in water. Recent work continues to couple them
explicitly — e.g. "Depth-Centric Dehazing and Depth-Estimation from Real-World
Hazy Driving Video" (arXiv **2412.11395**, AAAI 2025) and "UDPNet: Unleashing
Depth-based Priors for Robust Image Dehazing" (arXiv **2601.06909**).

The hazard is therefore not that the cue is spurious. It is that the cue is
**conditionally valid** — valid at fixed `beta`, `B_inf`, exposure and white
balance, and invalid the moment any of those change. Which they do, constantly,
across:

```text
water type / turbidity        beta and B_inf both change
artificial dive lights        adds a distance-dependent illumination term the
                              ambient model does not contain
camera exposure / auto-WB     GoPro adjusts both continuously, within a clip
colour correction             the project's own pipeline removes the cue
visibility changes            backscatter varies independently of geometry
```

## 20.2 The circularity hazard, stated plainly

This project uses estimated range `d` to **invert** the very image formation that
generates the appearance cue. If the range estimator is itself reading that
appearance, then

```text
d_hat = f(appearance)
appearance = g(d_true, beta, B_inf, illumination)
```

and the restoration solves `g^-1` using `d_hat`. Errors in the assumed water
parameters propagate into `d_hat` and then back into the inversion **in a
correlated way**. The result can look self-consistent — the residual is small,
the image looks corrected — while `d_hat` and the fitted coefficients are both
wrong along a compensating direction. That is precisely the failure Invariant 5
warns about, and no aggregate metric will catch it.

This concern is not addressed anywhere in the literature reviewed. It is
specific to pipelines that both *estimate* and *remove* the medium, and it is a
strong argument for preferring a range estimator whose evidence is **geometric**
(multi-view parallax, or a monocular model demonstrated to be appearance-invariant)
over one whose evidence is **radiometric**.

## 20.3 What the literature actually establishes, and where it stops

**Established: monocular depth networks lean on non-geometric cues.**
van Dijk & de Croon, *"How do neural networks see depth in single images?"*
(arXiv **1905.07005**, ICCV 2019) [PAPER VERIFIED] is the canonical probe. Its
findings on MonoDepth: the network relies on **vertical position in the image**
in preference to apparent size; it only **partially corrects for camera pitch and
roll**, so those perturbations shift estimated obstacle distance; and it
**requires a strong edge at the ground contact point**. That is a clear
demonstration that the cue structure is contextual and breakable — but it is a
2019 automotive model and the cues probed are geometric-contextual, **not
photometric**.

**Established: photometric corruption degrades depth, measured at scale.**
**RoboDepth** (arXiv **2310.15171**, **NeurIPS 2023**) [PAPER VERIFIED] benchmarks
**42 depth models** under **18 corruptions** spanning weather/lighting (brightness,
contrast, fog among them), sensor failure and motion, and data-processing
anomalies, and finds leading models broadly susceptible. Repo
`github.com/ldkong1205/RoboDepth`. This is the closest methodological precedent
for the planned Week-4A experiment — but its corruptions are atmospheric and
automotive, applied to KITTI/NYU, and it measures *degradation against GT*, not
*geometry change under appearance-only intervention*.

**Established: adverse-condition robustness is an active, adaptation-shaped
research area.** md4all/Robust-Depth-style work, "Always Clear Depth" (arXiv
**2505.12199**), "Depth Anything at Any Condition" (arXiv **2507.01634**, repo
`HVision-NKU/DepthAnythingAC`) [VERIFIED] which fine-tunes with *unsupervised
consistency regularization on a small amount of unlabeled data* plus a Spatial
Distance Constraint on patch-level relative relationships, and LoRA variants
(**2412.20162**, **2509.00665** ER-LoRA). The consistency-regularization framing in
2507.01634 is notable: it is essentially the invariance objective this section
argues for, used as a *training* signal.

**Not established — the gap this project must fill itself.** No paper found in
this review measures **the change in predicted geometry of a modern monocular
foundation model under controlled, physically-generated, appearance-only
underwater perturbation with geometry held exactly fixed.** Two near misses worth
naming so they are not rediscovered:

- *"One Scene, Two Depths: Probing Geometric Ambiguity in Monocular Foundation
  Models"* (arXiv **2606.29600**, **ECCV 2026**) and its predecessor arXiv
  **2503.06014** [both PAPER VERIFIED] sound directly on point but are **not**.
  Their "geometric ambiguity" is **multi-layer depth through transparent
  surfaces** — one ray hitting glass then background — benchmarked with
  MD-3k and probed with Laplacian Visual Prompting. Relevant to a glass port or
  the water surface; irrelevant to the appearance-shortcut question.
- RoboDepth measures accuracy loss, not geometry displacement under intervention.

**So the planned Week-4A appearance-invariance experiment is not redundant with
the literature. It is, as far as this review can determine, novel for underwater
foundation-model depth.** That raises its value and also its burden of care.

## 20.4 Does underwater specialisation make this better or worse?

The intuitive assumption is that an underwater-trained model is more robust
underwater. The available evidence points the other way, and there are now **three
independent observations** of the same pattern:

1. **Week 3, this project.** VGGT -> Wat3R-Ren underwater adaptation was
   condition-specific with no material win — better on one wreck, tied on two,
   and **clearly worse on the cenote** (20.1% vs 13.1%, the worst dense result
   anywhere). The cenote is the clip with the most distinct water and lighting.
2. **Cai & Metzler (arXiv 2507.02148).** Synthetic-underwater fine-tuning of
   DA V2 ViT-S **helps SQUID (0.5242 -> 0.4465 AbsRel) and FLSea-Red Sea, but is
   flat-to-slightly-worse on FLSea-Canyon** (0.3576 -> 0.3620).
3. **The mechanism is predictable.** A model trained on one water type learns the
   `beta`, `B_inf` statistics of that water type as part of its appearance-to-depth
   mapping. Specialisation *sharpens* the appearance cue rather than removing
   reliance on it. Self-supervised underwater models (the WaterMono / Monodepth2
   lineage) are the most exposed, because their photometric reconstruction loss is
   *itself* computed on water-degraded pixels — brightness constancy fails
   underwater, so the training signal is partly a water-appearance signal.

**Working hypothesis for Week 4A, to be tested rather than assumed:**
*underwater-specialised models will show larger geometry displacement under
water-type perturbation than general foundation models, not smaller.* If true,
that inverts the usual reason for including an underwater control — it becomes a
**fragility probe** rather than a robustness baseline.

## 20.5 The experiment: the design is sound, with four refinements

The proposed design — hold geometry fixed, vary WB / channel attenuation /
contrast / haze-backscatter / brightness / artificial-light hotspot, then measure
geometry change after removing **only** the ambiguity that model legitimately
claims — is the right shape and should proceed. Four refinements, each of which
measures something the naive version misses:

**(1) Perturb on the physical manifold, not arbitrarily.** Rather than applying
generic photometric edits, re-render using the project's own forward model with
the provisional reference range field held fixed, sweeping `beta_c` and `B_inf_c`
across Jerlov water types. Two gains: the perturbations are ones the model will
actually meet, and the intervention is *guaranteed* geometry-preserving by
construction rather than by assumption. This also reuses machinery Weeks 5-6 need
anyway. (Cai & Metzler used exactly this rendering approach to *train*; here it is
used to *probe*.)

**(2) Add a cue-conflict condition — this is the decisive one.** Consistent
perturbations cannot distinguish "the model uses the appearance cue" from "the
model ignores appearance". Render a haze/attenuation gradient that is
**inconsistent with the true geometry** — reversed, or aligned with an orthogonal
axis. If predicted geometry follows the fake gradient, the shortcut is confirmed
*and quantified* in range units. If it does not, appearance-invariance is
positively demonstrated rather than merely not refuted.

**(3) Decompose the response into ambiguity drift vs shape change.** This is the
measurement that connects directly to Week 3. After perturbation, fit the model's
legal ambiguity (section 17.1) and report **both** parts separately:

```text
part A   the fitted ambiguity parameters themselves (scale, and shift where legal)
         -> a pure global-scale response is BENIGN: Week 3 proved it is absorbed
            exactly, so a model whose entire appearance sensitivity lands here is
            acceptable
part B   the residual after the legal fit, per range bin
         -> this is the real damage, and it must be read against the section-2.2
            budget (31%/12%/8.5% clear; 9.4%/6.1% coastal; 1.0%/0.3% turbid)
```

Reporting only the post-alignment residual would discard part A and lose the
distinction that the whole project rests on. Reporting only the raw change would
condemn models for a scale wobble that costs nothing.

**(4) Test invariance and responsiveness together.** Invariance alone is
satisfiable by a model that is insensitive to everything. Pair each
appearance-only perturbation with a geometry-only control (same water, changed
scene depth) and confirm the model responds correctly there. A model that is flat
under both is not robust, it is inert.

**One caveat to record before running it.** An appearance perturbation applied to
an *already-degraded* real frame composes two attenuations, and for strong
perturbations the result leaves the physically reachable set (negative implied
radiance, clipped channels). Perturbation magnitudes should be bounded to the
physically realisable region and the clipping fraction reported, or the
experiment will measure out-of-gamut behaviour rather than water-type sensitivity.


---

# 21. Fine-tuning / adaptation / TTA options

## 21.1 Verdict

**Adaptation and TTA stay out of the primary Week-4A bakeoff.** They are a
Week-4.5 experiment with an explicit trigger (section 23). Three independent
lines of evidence support this, and one of them dissolves the TTA question
entirely.

## 21.2 The TTA question, answered precisely

The brief asked what the actual adaptation signal is for continuous depth
regression, and warned against importing classification-style entropy-minimisation
arguments. That warning is correct: **entropy minimisation (TENT) has no
well-posed analogue for a continuous dense regression output**, and no depth
method found relies on it.

**What the leading "depth TTA" paper actually does is not weight adaptation at
all.** Marsal, Chapoutot, Xu & Filliat, *"A Simple yet Effective Test-Time
Adaptation for Zero-Shot Monocular Metric Depth Estimation"*, arXiv **2412.14103**
(2024-12-18), **published at IROS 2025**, repo
`github.com/ENSTA-U2IS-AI/depth-rescaling`, **CC-BY-4.0** [PAPER VERIFIED, CODE
VERIFIED]. The method **rescales Depth Anything predictions using sparse 3D
points** from *"sensors or techniques such as low-resolution LiDAR or
structure-from-motion with poses given by an IMU"*, explicitly avoiding
fine-tuning to preserve generalisation. It is deterministic, needs no GT, and is
robust to sparse-depth noise and calibration error.

Read against section 17.1, this is decisive:

> **The leading depth-TTA method solves a problem this project does not have.**
> It recovers *global metric scale* from sparse points — and Week 3 proved global
> scale is absorbed exactly (`4.5e-13`), costing nothing.

It is nonetheless *useful* here, just not as TTA: it is a published, licensed
precedent for exactly the anchoring step the project would use if it ever needs
absolute scale — feeding Week-3 COLMAP/MapAnything sparse points into a monocular
prediction. Note SPADE (arXiv **2510.25463**, IEEE JOE 2026) does the same thing
underwater and reports the cleanest affine-aligned underwater number in existence:
**DA V2 + global scale-and-shift alignment to ~400 sparse points/frame on FLSea =
AbsRel 0.081 @ <=10 m, 0.068 @ <=5 m, 0.065 @ <=2 m** (MAE 0.277 / 0.170 /
0.099 m). That single row is the strongest evidence in this review that a
terrestrial foundation model's *shape* is not catastrophically broken underwater.

**Answering the brief's test directly** — is there a TTA/TTT method for depth that
is (a) single-image, (b) deterministic, (c) bounded runtime, (d) needs no GT, and
(e) has published evidence it helps under *photometric/domain* shift?

> **No method found satisfies all five.** 2412.14103 satisfies (a)-(d) but its
> demonstrated benefit is *metric scale*, not photometric robustness. Online
> self-supervised adaptation (CoMoDA-style, photometric-loss-driven) fails (a)
> outright — it needs neighbouring frames, violating the frame-independence
> constraint — and additionally fails underwater because **brightness constancy
> does not hold** through an attenuating, backscattering medium, so its loss is
> partly a water-appearance signal. `ReDepth Anything` (arXiv **2512.17908**,
> CVPR 2026 Findings) does per-image test-time refinement via self-supervised
> re-lighting on DA-V2/DA3, updating intermediate embeddings and decoder weights
> — genuinely single-image, but it mutates weights per sample, which forfeits
> determinism-by-construction and regression-testability unless proven otherwise
> [not evaluated underwater].

## 21.3 Supervised adaptation: what actually works, with numbers

**Precedent is strong in analogous domains.** Endoscopy is the best-developed
case and it is consistently **LoRA/adapter-shaped, not full fine-tuning**:
`DARES` — *Depth Anything in Robotic Endoscopic Surgery with Self-supervised
Vector-LoRA* (arXiv **2408.17433**), `EndoDAC` (arXiv **2405.08672**, MICCAI 2024),
`Surgical-DINO` (arXiv **2401.06013**, IPCAI 2024), `EndoUFM` (arXiv
**2508.17916**). Weather/adverse conditions likewise: `ER-LoRA` (arXiv
**2509.00665**), *Multi-Modality Driven LoRA for Adverse Condition Depth
Estimation* (arXiv **2412.20162**).

**The underwater precedents, in order of usefulness:**

1. **Wat3R** (arXiv **2607.08772**, **ECCV 2026 Oral**) — teacher/student
   cross-domain semi-supervised adaptation of **VGGT** to water: synthetic UIFM
   degradation of VGGT's own on-land training data as the labelled side, plus
   **~359k frames from 5,504 manually filtered real underwater clips** (from
   ~10,000 raw) unlabelled, ratio 1:3, with a cross-view consistency loss.
   Trained 19,200 steps on **4x RTX 4090** — i.e. genuinely reproducible scale.
2. **StereoAdapter** (arXiv **2509.16415**) / **StereoAdapter-2** (arXiv
   **2602.16915**) — LoRA-adapted monocular foundation encoder with dynamic rank
   selection, pretrained on synthetic `UW-StereoDepth-40K`. **+5.12% on SQUID.**
3. **Cai & Metzler** (arXiv **2507.02148**) — the recipe in full: DA V2 ViT-S,
   Hypersim RGB-D re-rendered through the underwater image formation model across
   Jerlov I/II/III and coastal 1C-9C, AdamW lr 5e-6, wd 1e-2, cosine annealing,
   4-epoch warmup, 20 epochs, batch 4, **SiLogLoss**, 518x518, **first half of the
   ViT encoder frozen**. Results in section 14.1.
4. **UW-Adapter** (IEEE TMM 27:4808-4818, 2025, DOI 10.1109/tmm.2025.3543089)
   [PAPER VERIFIED] — conceptually the closest to what this project would want:
   **freeze a terrestrial depth foundation model, train only lightweight
   adapters** (a *transmission adapter* and a *high-frequency adapter*),
   self-supervised. **No code, no weights, foundation model unnamed in the
   abstract, full text paywalled.** Unusable, but worth citing as prior art.

## 21.4 The two findings that argue for restraint

**(a) Underwater adaptation is condition-specific, observed three times
independently.** Week 3's Wat3R-Ren result (worse on the cenote, 20.1% vs 13.1%);
Cai & Metzler's fine-tune (helps SQUID and Red Sea, flat-to-worse on
FLSea-Canyon); and the mechanism in section 20.4. Adaptation reliably buys
in-domain gains and does not reliably generalise across water types.

**(b) The circularity and shortcut-entrenchment risk is real and unmeasured.**
Every underwater adaptation recipe above trains on either (i) synthetic renders of
the *same* image-formation model the pipeline implements, or (ii) real underwater
video whose photometric statistics *are* the appearance cue. Both push the model
toward reading water rather than geometry. Section 20.4's working hypothesis —
that specialisation *increases* water-type fragility — applies directly to any
adaptation this project performs on its own footage.

**A specific hazard for this project's pseudo-label plan.** Adapting against
Week-3 MapAnything/COLMAP range would violate the standing rule in CLAUDE.md
against training a model to imitate the pipeline's own output: the student
inherits MapAnything's **6.6x scale wander on dynamic content** and COLMAP's
ill-conditioning on low-observation clips (section 3.3) as *targets*. Since C2 is
not captured, there is no independent anchor to catch that. **Adaptation against
Week-3 products should wait for C2**, which is an argument from the project's own
epistemics, not from the literature.

## 21.5 If adaptation does proceed: the best target

Ranked on architecture, licence permitting derivative works, released **training**
code (not just inference), and community fine-tuning precedent:

```text
1. Depth Anything V2 (Small, Apache-2.0)   the field's default adaptation target;
   every underwater adaptation above builds on it or its lineage; first-party MPS
   support; the largest body of LoRA/adapter precedent. Note Base/Large are
   CC-BY-NC-4.0 - only Small is cleanly licensed for derivative work.
2. Wat3R (Apache-2.0 code AND checkpoint)  training code released, underwater
   already, and the project has it integrated from Week 3.
3. DA3MONO-LARGE (Apache-2.0)              best ambiguity semantics (Class 2), but
   no MPS and no released training recipe for the mono head specifically.
```

**Not MoGe** despite its MIT licence — no adaptation precedent was found, and
DAGE's critique of its multi-scale local loss (section 19.4) suggests the
training objective is not straightforwardly transferable.

## 21.6 Honest verdict

Adaptation is a **Week-4.5 conditional experiment**, triggered only by the
specific finding described in section 23: zero-shot structure excellent,
underwater radiometry producing systematic failure. TTA is **not** a primary
strategy; the one credible depth-TTA method addresses a nuisance parameter this
project has already proven is free.


---

# 22. Primary Week-4A candidate set

> **This is the INITIAL recommendation.** Section 27 attacks it and changes it;
> section 28 is the final set. The three are kept separate deliberately.

**Five families, seven checkpoints.** Two families are deliberately *paired* to
isolate one variable each at near-zero marginal cost.

---

## P1 — MoGe-2 ViT-L (+ MoGe-1 as the paired relative control)

```text
checkpoints  Ruicheng/moge-2-vitl        (326M, metric)      MIT / MIT
             Ruicheng/moge-vitl          (314M, affine)      MIT / MIT
paper        arXiv 2507.02546 / arXiv 2410.19115 (CVPR 2025 Oral)
role         Point-map / native-range baseline, and the metric-vs-relative
             variable isolated within one architecture
hypothesis   H2: explicit point-map geometry preserves local shape better, and
             yields water_path_length exactly without depending on K
```

**Why this exact model.** MIT on code *and* every checkpoint — the cleanest
licence position in the review, and the standard Week 3 set. `range = ||P_cam||`
is exact and needs **no intrinsics**, which matters because EIS makes this
project's `K` provisional. It accepts a documented optional `--fov_x`, so the
P0/P1 comparison (section 16.4) is available without hacking. It emits a validity
mask. MoGe-1 vs MoGe-2 isolates *metric conditioning* with backbone, data and
preprocessing held constant.

**Challenges:** DA3 (on whether point maps beat a scalar-depth model),
and UniDepth V2 (on whether a metric model needs intrinsics conditioning).

**Wins if:** oracle-aligned local shape error (E1) is best or tied-best, its range
conversion verifies exactly (as MapAnything's did to 1.1e-5), and the metric head
does not show far-field bias at reef distances.
**Loses if:** DAGE's critique bites — per-region alignment artefacts show up as
seams, or per-frame stability is materially worse than a scalar-depth model — or
if the *"Honey, I Shrunk the Arc de Triomphe"* far-field scale collapse (Arc width
44.8 m predicted as **18.8 m**) reproduces inside 15 m.
**Must be checked first:** whether MoGe-1/-2 actually run on MPS. The repo's
"macOS is not supported" note is scoped to MoGe-3's Triton dependency, but it is
**not stated** that the earlier versions work. If they do not, P1's local-loop
advantage evaporates and it must be re-costed against P2.

---

## P2 — DA3MONO-LARGE + DA3METRIC-LARGE (paired)

```text
checkpoints  depth-anything/DA3MONO-LARGE    (0.35B)   Apache-2.0 / Apache-2.0
             depth-anything/DA3METRIC-LARGE  (0.35B)   Apache-2.0 / Apache-2.0
paper        arXiv 2511.10647, ICLR 2026
role         The field reference, and the best-documented ambiguity semantics
hypothesis   H1 + H3 together: does metric conditioning add anything over a pure
             relative model of identical architecture, on underwater footage?
```

**Why this exact model.** Three reasons no other candidate combines:

1. **The best ambiguity class available in a relative model.** DA3 predicts
   *depth*, not disparity, and its shipped aligner (`least_squares_scale_scalar`)
   is **scale-only in depth space** — Class 2, the exactly-absorbable class
   (section 17.1). Every other relative foundation model in wide use is Class 4.
2. **The metric variant degrades gracefully.** `metric = focal * net_out / 300`
   means focal error is a **pure global multiplicative** range error — free, per
   Week 3. That is a better failure mode under this project's specific `K`
   uncertainty than a model whose scale error deforms shape.
3. **Comparability.** DA3 is the model Wat3R benchmarks against, so results here
   can be read against published underwater numbers.

**Challenges:** MoGe-2 (scalar depth + K vs point map) and Wat3R (does underwater
adaptation beat the model it was adapted from?).

**Wins if:** DA3 Mono's E1 is at or near the top *and* the fitted shift is
statistically indistinguishable from zero (confirming Class 2), making it the
only candidate that is both structurally excellent and deployably aligned.
**Loses if:** the shift is significantly non-zero (demoting it to Class 3), or
DA3 Metric adds nothing over DA3 Mono once a scale is fitted — in which case the
metric half is dropped and the family costs one slot instead of two.

⚠️ **Known cost, accepted deliberately: DA3 does not run on this machine.**
`xformers` is a hard dependency, `device` defaults to `"cuda"` with no `mps`
handling anywhere in the codebase, `torch.cuda.is_bf16_supported()` is called
unconditionally, and the Apple-Silicon issue (#123) was abandoned in Dec 2025.
**This candidate requires rented CUDA.** It is included anyway because it is the
only way to test the Class-2 hypothesis on the field's reference model, and
because Week 3 explicitly left GPU rental available for a scientifically
compelling case. ⚠️ Also: never set the CLI's `auto_cleanup=True` (Invariant 7).

---

## P3 — UniDepth V2 ViT-L

```text
checkpoint   lpiccinelli/unidepth-v2-vitl14      code CC BY-NC 4.0
                                                 checkpoint: NO LICENCE DECLARED
paper        arXiv 2502.20110, TPAMI (DOI 10.1109/TPAMI.2025.3628473)
role         The incumbent underwater metric champion, and the only model whose
             native output IS the project's canonical quantity
hypothesis   H1: universal metric depth generalises underwater
```

**Why this exact model.** It **won the only clean underwater monocular metric
benchmark** by a wide margin (FLSea-Canyon 0.1156/0.9109; Red Sea 0.0932/0.9439;
SQUID 0.3222/0.5201). It **natively distinguishes `radius` — metric ray range —
from `depth`**, so `water_path_length` is `measured`, not transformed. It accepts
known intrinsics including a `Fisheye624` camera object, giving a first-class P1
path. And the Arc-de-Triomphe study rates it the least-bad on far-field scale
(*"more realistic scales but still deviates"*, vs outright collapse for MoGe-2 /
DA3 / Metric3D v2 and *"orders of magnitude"* failure for Depth Pro).

**Its role is adversarial:** it is the model the project's own reasoning predicts
should *not* matter much, because it wins on the E3 axis Week 3 proved is free.
Including it tests that reasoning rather than assuming it.

**Challenges:** every other primary candidate, on whether the benchmark ranking
survives a *shape*-based (E1) protocol.

**Wins if:** it leads on E1 as well as E3 — which would mean the underwater
benchmark ranking was measuring something real after all, and would be a genuine
surprise worth acting on.
**Loses if:** its E1 advantage vanishes under oracle alignment while others catch
up — confirming section 14.1's reading that the benchmark scores scale, not shape.

⚠️ **Licence is a deployment blocker, not a research one.** Code is CC BY-NC 4.0
and the checkpoint declares **no licence at all**. It may inform the Week-4A
decision; it cannot ship without a licence clarification from the authors. This
must be recorded in LOG.md at selection time, not discovered later.

---

## P4 — Wat3R

```text
checkpoint   lsxi77777/Wat3R   (4.76 GB)    Apache-2.0 / Apache-2.0
paper        arXiv 2607.08772, ECCV 2026 Oral
role         The underwater specialist control - and the fragility probe
hypothesis   H4: underwater adaptation matters more than architecture
```

**Why this exact model, and not WaterMono.** It is the **only** underwater model
where all four hold: verifiably downloadable weights, a head-to-head against
DAv2/DA3/VGGT/π³/MapAnything/Fast3R, a **stated common alignment** applied to all
methods, and a genuine **single-view** protocol. Apache-2.0 on code, checkpoint
*and* dataset. WaterMono fails on licence (none), adoption (9★/0 forks), and
protocol — its FLSea win is in-domain, and out-of-domain on Sea-thru it loses to
DA3 (0.145 vs 0.111).

**Two decisive practical advantages nobody else has here.** (a) It is a **VGGT
derivative, and Week 3 already ran the VGGT family on MPS float32 with bitwise
reproducibility** — so it runs locally, deterministically, today. (b) **The
project already has it integrated** as `Wat3R-Ren`, with its own independent
measurement.

**And that measurement is why it is framed as a fragility probe.** Week 3 found
it condition-specific with no material win — better on one wreck, tied on two,
**clearly worse on the cenote (20.1% vs 13.1%, the worst dense result anywhere)**.
The agent sweep concluded no independent reproduction of any underwater depth
model exists; **this project is that reproduction.** Section 20.4's hypothesis
predicts the specialist will be *more* water-type fragile, not less.

**Wins if:** it beats DA3 Mono and MoGe-2 on E1 across *all* five test-set
categories including `lights/` and the cenote-like conditions.
**Loses if:** its advantage is confined to the conditions resembling its
forward-looking robot-survey training video — which would confirm the pattern now
observed three independent times (Week 3, Cai & Metzler, section 20.4).

⚠️ Not metric (LSQ scale **and** shift — Class 3). ⚠️ Its labelled training side
is synthetic UIFM degradation of in-air data using **the same image-formation
model this pipeline implements**, so its depth is *not* independent evidence that
the physical model is correct.

---

## P5 — Depth Anything V2 (Small; Large where licence permits)

```text
checkpoints  depth-anything/Depth-Anything-V2-Small  (24.8M)  Apache-2.0 / Apache-2.0
             depth-anything/Depth-Anything-V2-Large  (335M)   Apache-2.0 / CC BY-NC 4.0
paper        arXiv 2406.09414, NeurIPS 2024
role         The reference floor, the Class-4 comparison point, and the link to
             every published underwater number
hypothesis   H3, and a control on the whole exercise
```

**Why include a model this review has argued against on semantics.** Four
reasons, and together they are strong:

1. **It is the only model with first-party Apple Silicon support** — the README's
   own device line selects `cuda -> mps -> cpu`. It will run in the daily loop
   when nothing else will, which makes it the natural regression anchor.
2. **It is the substrate of the entire underwater literature** — SPADE, OceanLens,
   Atlantis's pseudo-labelling, TIDE's depth annotations, Cai & Metzler's
   fine-tune, and every underwater benchmark row. Results here are directly
   comparable to published work in a way nothing else is.
3. **The best affine-aligned underwater number in existence is its own.**
   SPADE's "DA V2 + global scale-and-shift" row on FLSea: **AbsRel 0.081 @ <=10 m,
   0.068 @ <=5 m, 0.065 @ <=2 m.** That is direct evidence a terrestrial model's
   *shape* is not catastrophically broken underwater — and it is the number every
   other candidate must beat to justify its cost.
4. **It makes the Class-4 penalty measurable rather than theoretical.** Section
   17.1 predicts a Möbius range deformation with a finite depth horizon. DA V2 is
   the instrument for testing whether that prediction is real at reef distances,
   and by how much. If the penalty is small, a large part of this review's
   reasoning needs revising — which is exactly why it must be measured.

**Wins if:** the Class-4 penalty proves small in the 1-15 m band, which would
reopen the whole MiDaS lineage and simplify deployment enormously.
**Loses if:** far-field deformation is large — the predicted outcome — in which
case it remains a floor and a regression anchor, not a deployment candidate.

---

## 22.1 What this set deliberately does not include

- **No generative/diffusion model** — section 12; the hypothesis was answered by
  the family's own literature, and the determinism cost is real.
- **No any-camera model** — section 11.6; conditional, not primary.
- **No adaptation or TTA** — section 21; Week 4.5.
- **No video-depth model** — the brief scopes Week 4 to the single-image fallback
  path, and section 19 shows a video model is not automatically better (NVDS
  variants score *worse* than per-frame DA V2-L on TAE).
- **No second underwater specialist** — H4 is a single hypothesis and Wat3R is its
  strongest instance; adding WaterMono or UDepth would add unlicensed code and
  pseudo-label-supervised weights for no new hypothesis.


---

# 23. Conditional challengers with explicit triggers

Each entry names an **observed failure**, the model to activate, and **why that
model specifically addresses it**. No model appears here merely so that a
reviewed paper has a role.

```text
────────────────────────────────────────────────────────────────────────────
TRIGGER  z-depth -> range conversion error, or K uncertainty, dominates the
         error budget (e.g. error grows systematically with radial image
         position, or changes materially when K is perturbed within its
         plausible EIS range)
ACTIVATE FoundationGeo-1.1  (mxliu-hku/FoundationGeo-1.1, MIT/MIT, ECCV 2026)
WHY      It is the ONLY model that natively decomposes into Euclidean range and
         a UNIT ray: d = ||p||_2, r = p/||p||_2. That removes the conversion and
         its K-dependence entirely. It also ships a separate Stage-I
         affine-invariant checkpoint, so it can replace P2 as the paired
         relative-vs-metric family if DA3's CUDA requirement becomes intolerable.
         Its own OOD-focal ablation is the best published predictor of how a
         GoPro will break.
────────────────────────────────────────────────────────────────────────────
TRIGGER  Wide-FOV degradation dominates - error concentrated in the outer field,
         or P2 (undistort+crop) materially outperforms P0 (native frame)
ACTIVATE Depth Pro (apple/DepthPro) with the measured focal supplied
WHY      WideDepth (ICRA 2026) measured it as by far the most FOV-robust model:
         +9.0% AbsRel from 120->195 deg, against DA V2's +166% and UniK3D's +97%.
         And its focal input is documented to OVERRIDE the estimate entirely.
         ⚠️ Research-only, revocable licence that also binds fine-tunes - it can
         inform a decision but can never ship. ⚠️ Pass torch.tensor(f_px).
────────────────────────────────────────────────────────────────────────────
TRIGGER  Camera-model error specifically (not just FOV) dominates AND reliable
         intrinsics are available from C2
ACTIVATE UniDAC (girish1511/UniDAC, CVPR 2026, MIT code) - NOT UniK3D
WHY      UniDAC is the current best cross-camera model and decouples relative
         depth from a spatially varying scale field, which is the right shape for
         a distortion-driven error. UniK3D is deprioritised on two counts: its
         code is CC BY-NC-SA (viral), and WideDepth measured it at +97% - i.e.
         "any-camera" branding did not deliver FOV robustness.
         ⚠️ UniDAC REQUIRES ground-truth camera parameters, so this trigger is
         genuinely gated on C2, and its checkpoint declares no licence.
────────────────────────────────────────────────────────────────────────────
TRIGGER  A pinhole/fisheye mismatch is diagnosed AND the preferred model is one
         RayTun3R already supports (DA3, VGGT, pi^3, DUSt3R, MASt3R)
ACTIVATE RayTun3R (arXiv 2607.02711)
WHY      10,752 trainable parameters, no runtime overhead once adapted, and -
         crucially - it is a PER-CAMERA fit, not a per-frame one. For a fixed
         GoPro in a fixed housing it can be fitted ONCE offline and frozen,
         preserving strict frame-independent, deterministic inference. It is the
         only camera-adaptation method found that is compatible with the
         project's constraints. ⚠️ Release status unverified.
────────────────────────────────────────────────────────────────────────────
TRIGGER  ALL discriminative candidates lose thin structure - coral branches,
         ropes, fish fins systematically absent or merged into background, and
         this is confirmed visually per Invariant 5
ACTIVATE Pixel-Perfect Depth (NeurIPS 2025) or PointDiT (ICML 2026, Apache-2.0)
         - NOT Lotus-2, and NOT Marigold
WHY      Pixel-Perfect Depth localised the sharpness deficit to the SD VAE
         ("flying pixels at edges"; "increasing the latent dimension in VAEs
         fails to eliminate" them) and fixes it in pixel space. PointDiT drops
         the pretrained latent diffusion model entirely and still beats latent
         diffusion. Both deliver the thin-structure hypothesis WITHOUT the
         stochastic sampler. Lotus-2 is excluded: Class-4 disparity ambiguity,
         >=40 GB VRAM, and undisclosed FLUX.1-dev non-commercial inheritance.
         ⚠️ PointDiT needs gated DINOv3 weights at inference.
────────────────────────────────────────────────────────────────────────────
TRIGGER  Zero-shot STRUCTURE is excellent but underwater RADIOMETRY produces
         systematic, reproducible failure - i.e. the section-25 appearance
         perturbations move geometry beyond the section-2.2 budget, while
         oracle-aligned shape on clean-water frames is good
ACTIVATE Week 4.5 adaptation experiment: LoRA / adapter tuning of
         Depth Anything V2 Small (Apache-2.0) or Wat3R (Apache-2.0)
WHY      This is the one failure mode adaptation is actually evidenced to fix.
         The precedent is strong and consistently PEFT-shaped: DARES, EndoDAC,
         Surgical-DINO, EndoUFM (endoscopy); ER-LoRA and 2412.20162 (weather);
         StereoAdapter's +5.12% on SQUID (underwater); Cai & Metzler's full
         recipe. ⚠️ Two hard preconditions: (1) it must NOT be trained against
         Week-3 MapAnything/COLMAP output before C2 - that violates CLAUDE.md's
         rule against imitating the pipeline's own output and would inherit
         MapAnything's 6.6x dynamic scale wander as a target; (2) section 20.4's
         hypothesis says adaptation may INCREASE water-type fragility, so the
         appearance-invariance battery must be re-run on the adapted model.
────────────────────────────────────────────────────────────────────────────
TRIGGER  Absolute metric range is genuinely required - cross-clip coefficient
         transfer, artificial-light falloff (week 6), or camera-to-light geometry
ACTIVATE Sparse-point rescaling: depth-rescaling (arXiv 2412.14103, IROS 2025,
         CC-BY-4.0) or SPADE's global-alignment approach
WHY      Feed Week-3 COLMAP/MapAnything sparse points into the monocular
         prediction. Deterministic, needs no GT, published, licensed, and
         demonstrated underwater by SPADE (DA V2 + global alignment: AbsRel 0.081
         @<=10 m on FLSea). This is the correct answer to "we need scale" - NOT
         switching to a metric model, since Week 3 proved global scale is free
         and section 4.2 shows every metric model has far-field scale problems.
────────────────────────────────────────────────────────────────────────────
TRIGGER  Public underwater accuracy is acceptable but independent-frame
         predictions BREATHE beyond what the physical parameter estimator can
         absorb
ACTIVATE Before switching models: run DyFN's diagnostic (section 19.2) - one
         global alignment vs per-frame alignment, and read the gap.
         Only if the residual survives that decomposition, investigate a
         stability-specific challenger.
WHY      DyFN showed the instability lives in the per-frame scale-shift
         re-estimation, not the geometry (delta_1 62.5 -> 99.8). If the breathing
         is pure scale, Week 3 proved it is FREE and no model change is warranted
         - only a smoothed scale estimate. Changing models before running this
         decomposition would be solving the wrong problem.
────────────────────────────────────────────────────────────────────────────
TRIGGER  Per-frame runtime or memory binds on a full clip, or a small local model
         is needed for the daily loop
ACTIVATE OptiGeo (mxliu-hku/OptiGeo, 30M params, MIT/MIT) or
         MoGe-2 ViT-S (Ruicheng/moge-2-vits-normal, 35M, MIT/MIT)
WHY      Both are two orders of magnitude smaller than the primary candidates
         with clean licences. OptiGeo additionally targets optically challenging
         (transparent/reflective) scenes and its "sensor-induced supervision
         bias" thesis is the nearest published framing to the underwater problem.
────────────────────────────────────────────────────────────────────────────
TRIGGER  Fine detail is the deciding axis AND a CUDA machine is already rented
ACTIVATE MoGe-3 (Ruicheng/moge-3-vitl 370M or -vitg 1.25B, MIT/MIT)
WHY      Direct successor to a primary candidate, same output semantics, same
         licence, explicitly built for fine-grained point-map geometry.
         ⚠️ macOS is NOT supported (FlexGEMM -> Triton, no macOS wheels), so it
         can never be the local default.
────────────────────────────────────────────────────────────────────────────
```

## 23.1 Triggers deliberately NOT created

- **"A newer model appeared."** Novelty is not a trigger. Section 24 lists what
  was reviewed and rejected so it is not re-litigated.
- **"An underwater specialist exists that we haven't tried."** Week 3's standing
  rule after Wat3R-Ren: a condition-specific result with no material win is *not*
  a reason to look for another underwater-adapted model. Section 13.1's survey
  found nothing that changes this.
- **"UniDepth V2 lost."** Its licence already blocks deployment; losing on E1
  would simply confirm section 14.1's reading, requiring no follow-up.


---

# 24. Reviewed and NOT selected

Recorded so these are not rediscovered and re-argued. Grouped by reason.

## 24.1 Rejected from the supplied shortlist

| Candidate | Verdict | Reason |
|---|---|---|
| **WaterMono** | **Removed from core** | **Not the best underwater control.** No LICENCE file on code or weights; 9★/0 forks/4 open issues; output is disparity (Class 4); and its apparent win over DA3 on FLSea (0.074 vs 0.090) is **in-domain — it trains on FLSea**. Out-of-domain on Sea-thru it **loses** (0.145 vs DA3's 0.111). Replaced by Wat3R, which is Apache-2.0 on code, checkpoint and dataset, has a fair-protocol single-view head-to-head, and is already integrated here |
| **UniDepth V2-L** | **Retained, but reframed** | Kept as P3, but **not** because it leads a benchmark. The benchmark it leads is **raw metric with no alignment** (section 14.1) and scores the one axis Week 3 proved is free. Its real justifications are native `radius` output and adversarial value. Licence blocks deployment |
| **DA3 Mono + DA3 Metric** | **Retained as ONE paired family** | Confirmed as the right pairing — it isolates metric conditioning with everything else held constant. Counted as one slot, not two |
| **MoGe-2-L** | **Retained, with a caveat the shortlist lacked** | Kept as P1, but the shortlist did not know that MoGe is the model in which DyFN measured scale-shift drift, that DAGE argues its multi-scale local loss *"break[s] cross-view consistency, leading to seams and drift"*, or that it is named in the far-field scale-collapse finding (Arc de Triomphe 44.8 m → **18.8 m**) |

## 24.2 Superseded or redundant

- **MiDaS v3.1** (arXiv 2307.14460) — a **technical report, no venue**; no weights
  licence stated anywhere; superseded by DA V2 on every axis, and StableDPT shows
  DA V2 is far more per-frame-stable than the MiDaS generation. Conceptual
  ancestor only.
- **Depth Anything V1** — strictly superseded by V2, same disparity-space
  ambiguity.
- **MoGe-3** — same family, same licence, better detail, but **macOS unsupported**
  (FlexGEMM → Triton). Conditional challenger, not primary.
- **UniDepth V1** — superseded by V2, which adds the uncertainty head and the
  edge-guided loss.
- **Metric3D (v1)** — superseded by v2.
- **Marigold, GeoWizard, DepthFM, GenPercept, BetterDepth** — superseded within
  their own family by E2E-FT's result and by deterministic successors
  (section 12.2).
- **DUSt3R / MASt3R** — duplicating an image is **not** a monocular path; also
  CC BY-NC-SA (viral).

## 24.3 Rejected on output semantics

- **Depth Anything V2 as a *deployment* candidate** — affine-invariant in
  **disparity** (Class 4): Möbius range deformation plus a finite depth horizon at
  long range, exactly where the budget is tightest. **Retained as P5 only** as a
  floor, regression anchor and the instrument for measuring how big the Class-4
  penalty actually is.
- **Lotus / Lotus-2** — Lotus-2 is the best-designed generative candidate
  (explicitly noise-free both stages) but trains and predicts **in disparity
  space** (Class 4), requires **≥40 GB VRAM**, and its Apache-2.0 declaration does
  not mention its **FLUX.1-dev non-commercial** inheritance.
- **ZoeDepth** — **no peer-reviewed venue** (no comments, no journal-ref, repo
  BibTeX is `@misc`), **intrinsics ignored entirely**, and the **worst underwater
  performer by a wide margin** (AbsRel 1.5907 / 1.3335 / 1.3214). Clean MIT/MIT
  licensing does not rescue it.

## 24.4 Rejected on availability or licence

- **Depth Anything V2 Giant** — **never released.** Three independent negatives:
  README "Coming soon"; absent from a complete 48-model HF org enumeration; API
  returns HTTP 401. Two-plus years after publication.
- **Depth Pro** as a deployment candidate — weights are **`apple-amlr`,
  research-only, revocable, and bind fine-tunes to the same terms**, and the repo
  README points at the wrong (permissive) licence. Retained as a *conditional*
  FOV-robustness probe only.
- **UniK3D** — code **CC BY-NC-SA** (non-commercial *and viral*), checkpoint
  licence undeclared, and WideDepth measured **+97%** FOV degradation.
- **Dens3R** (arXiv 2507.16290, Alibaba) — **CC BY-NC-SA**: ShareAlike is viral
  and could bind derivative work. Disqualifying regardless of quality.
- **Metric3D v2** — checkpoint licence **never stated**; the `cc0-1.0` tag on
  `onnx-community/metric3d-vit-large` is a **third-party re-upload's assertion**.
  **Intrinsics are required**, with a 9-value focal sweep as fallback — a direct
  dependency on this project's weakest parameter. Its ViT-L was **excluded from
  the underwater benchmark for hardware reasons**, so its best configuration is
  untested underwater.
- **UDepth** — **no licence at all** (all rights reserved, code and weights);
  USOD10K pseudo-label supervision; worst entry in Wat3R's table.
- **CD-UDepth** — good journal (*Information Fusion*), but **no arXiv record**,
  repo at 1★ with **no licence**, built on UDepth's backbone and pseudo-labels, and
  **no comparison against any foundation model**.
- **UDepthDiff** — **IEEE Access** (APC megajournal, light review), **not on
  arXiv**, no code, no weights, no repo.
- **UMono, Tree-Mamba, UW-Adapter, PUDE, Dense Geometry Supervision** — no usable
  artifact. Tree-Mamba's repo is **0 KB, 1 commit, README only**, untouched since
  a date that **predates its own arXiv posting**.
- **SPADE** — code MIT, but **weights "coming soon" — not released**, and it
  requires sparse priors at inference. Its **DA V2 + global-alignment baseline
  row** is nonetheless one of the most useful numbers in this review.
- **MetaDepth-CPU** — genuinely impressive (2.8 MB, 15-30 FPS on phone CPUs) but
  **relative depth only**, and **not released**.
- **DAGE** — code licence is CC BY-NC 4.0 shipped in a file named `license.md`;
  checkpoint declares **no licence**. Also multi-view by construction.
- **DepthCrafter** — hard non-commercial for **code and weights**: *"refrain from
  using it for any commercial or production purposes under any circumstances."*
- **PaGeR** — weights CC BY-NC 4.0 (though its licensing hygiene is the best in
  the review — two separate files, HF card agrees).

## 24.5 Rejected as not monocular / not single-image

- **MapAnything, VGGT, π³** — already characterised in Week 3 as multi-view; VGGT
  is explicit that single-view works *"although it was never trained for this
  task"*. Week 3 also measured the VGGT family discarding **~44% of vertical FOV
  on portrait clips**.
- **UW-Depth / TRUDepth, PromptDA, Prior Depth Anything, MTD, Any-to-Full,
  OASIS-DC** — all **consume sparse depth at inference**. Their headline gains
  (e.g. DA V2 on DIODE 0.260 → 0.093 AbsRel) **must never be read as zero-shot
  monocular numbers**.
- **Video Depth Anything, DepthCrafter, RollingDepth, ChronoDepth, NVDS,
  StableDPT, ICDepth, GemDepth, DVD, VeloDepth** — video-only. Week 4 explicitly
  tests the single-image fallback path, and section 19 shows a temporal module is
  not automatically better (NVDS scores **worse** than per-frame DA V2-L on TAE).
- **Underwater 3DGS/NeRF** (SeaSplat, WaterSplatting, UW-GS, ReefMapGS, Swimm3R,
  NemoSplat, Gaussian Splashing) — per-scene optimisation, not predictors.
- **Sea-thru** — **consumes** a range map; a consumer of depth, not a source.
- **Haze-Lines / Berman** — produces a **transmission map, not geometric depth**.

## 24.6 Rejected as irrelevant mechanisms

- **Language-conditioned scale** — TR2M (CVPR 2026), *Language as Prior*, VGLD.
  No text channel exists here.
- **Depth from defocus** — *Zero-Shot Depth from Defocus* (ECCV 2026), Marigold
  defocus repurposing. Requires aperture control; a GoPro has none.
- **Radar / thermal / event / dual-pixel fusion** — no such sensor.
- **Multi-layer transparency ambiguity** — *One Scene, Two Depths* (ECCV 2026),
  MD-3k, LVP. A different meaning of "ambiguity" (section 20.3).
- **DepthAnything-AC** — its fog is a **Diamond-Square noise texture overlay**,
  **range-independent**. It does not model `B_inf(1 - exp(-beta_bs z))`, so it
  does not address the mechanism of concern.

## 24.7 Do not cite

- **"Depth Anything V4"** (arXiv **2608.18388**) — **withdrawn 2026-08-20**, two
  days after posting, flagged **"Major errors in research"**; a 4D-Gaussian-
  splatting method by authors unaffiliated with the Depth Anything team.
- **"DepthDive"** — arXiv full-text search returns **totalResults = 0**. No DOI,
  no repo. It does not exist.
- **USOD10K / BlueDepth / TIDE depth annotations as ground truth** — all are
  monocular pseudo-labels (section 14.3).
- **The `onnx-community/metric3d-vit-large` cc0-1.0 tag** — a third-party
  re-upload's assertion, not the authors'.
- **MD2E's project page BibTeX** — it serves the citation for an entirely
  different paper.
- **"DepthMaster" by name** — two unrelated papers (arXiv 2606.12368 and arXiv
  2501.02576). **Cite by arXiv ID.**


---

# 25. Proposed acquisition-independent Week-4A measurement categories

**High level only.** This is a list of *what must be measured*, not the protocol.
The protocol is written separately, after this review is accepted.

```text
M0  WRAPPER AND SEMANTICS CORRECTNESS                        (must pass first)
    - verify the range conversion numerically for each candidate, the way Week 3
      verified MapAnything's depth_along_ray == ||pts3d_cam|| to 1.1e-5
    - audit preprocessing for crop / letterbox / resize: Week 3 measured the VGGT
      family silently discarding ~44% of vertical FOV on portrait clips
    - confirm on VAROS (dense, hole-free, metric, CC BY 4.0) and Sea-thru
      (linear PNG, metres, 0 = NaN) before touching project footage
    - record which of P0 / P1 / P2 (s.16.4) each candidate is being run under

M1  DETERMINISM AND NOISE FLOOR
    - repeat-run bitwise reproducibility on MPS fp32, fixed seed, matching the
      standard the Week-3 dense arm met
    - any candidate that cannot meet it needs a MEASURED noise floor before any
      of its deltas are readable

M2  AMBIGUITY CLASS, MEASURED NOT ASSUMED                    (decides s.17)
    - fit scale-only vs scale+shift in the model's NATIVE representation and test
      whether the shift is significantly non-zero
    - settles the two open questions in this review: is DA3 Mono Class 2 or 3,
      and is MoGe-1's released output shift-resolved or not

M3  ORACLE STRUCTURAL ACCURACY (E1)
    - per-image legal-ambiguity fit, then local shape error
    - reported PER RANGE BIN against the s.2.2 budget, not as a single AbsRel
    - includes an explicit near-vs-far bias readout (the s.4.2 scale-collapse
      hypothesis, tested at reef distances rather than assumed from landmarks)

M4  DEPLOYABLE FROZEN CALIBRATION (E2)
    - one calibration fitted on allowed evidence, frozen, reused on held-out
      clips. The E1 -> E2 gap is the cost of not having per-image GT

M5  RAW METRIC (E3)
    - no alignment. Only meaningful for Class-1 candidates
    - expected to be poor for every model per s.4.2 and FoundationGeo's OOD-focal
      result; the question is whether it is poor in a benign (global) way

M6  APPEARANCE INVARIANCE                                    (the novel one)
    - physically-generated, geometry-preserving perturbations (s.20.5)
    - cue-conflict condition included
    - response DECOMPOSED into ambiguity drift vs post-fit residual (s.20.5(3))
    - paired geometry-only controls so invariance is distinguished from inertness

M7  INDEPENDENT-FRAME TEMPORAL STABILITY
    - DyFN's cheap diagnostic FIRST (s.19.2): one global alignment vs per-frame
      alignment; the gap is the affine-drift component
    - OPW (flow-based, no poses needed) rather than TAE (needs GT poses)
    - depth-edge jitter via a Chamfer distance at Canny edges (DAGE's C_PDBE idea)
    - confidence jitter where a confidence map exists

M8  CONFIDENCE, IF ANY
    - error-separation ratio between high- and low-confidence pixels, reported
      alongside Week 3's MapAnything baseline of 1.07x so the two are comparable
    - specifically test whether confidence is HIGH in the low-contrast far field

M9  CROSS-METHOD CONSISTENCY ON PROJECT FOOTAGE
    - against MapAnything and COLMAP/SIFT, with the s.3.3 epistemics enforced:
      agreement is evidence of consistency, NOT correctness; and disagreement on
      a low-observation clip is NOT evidence against the monocular model

M10 PUBLIC-DATASET SANITY
    - SQUID for relative shape and near/far bias (charts at multiple known
      distances; and CONVERT z-depth to range first - the published benchmark
      did not, which inflates every z-depth model's SQUID error)
    - FLSea for volume
    - report low-texture results as UNMEASURED, since both datasets delete GT
      exactly there (s.15.5)

M11 COST
    - runtime, peak memory, and whether it runs locally on MPS at all
    - recorded per candidate, since it decides the daily loop, not the science

M12 PROVISIONAL RESTORATION IMPACT
    - feed each candidate's range into the existing pipeline and measure the
      downstream quantity that actually matters, per the s.2.2 budget
    - visual inspection for hallucinated structure is MANDATORY here
      (Invariant 5), with particular attention to whether backscatter speckle,
      marine snow or caustics have been converted into geometry (s.12.4)
```

**Ordering matters.** M0-M2 gate everything: a candidate that fails semantics
verification produces numbers that cannot be interpreted, and M2 determines which
alignment M3-M5 are even allowed to use. Running M3 before M2 is the single most
likely way to produce a confidently wrong ranking.


---

# 26. What must wait for C2 / Week 4B

## 26.1 Establishable in Week 4A, before C2

```text
the candidate landscape and its release/licence status      (this document)
output semantics and legal alignment per candidate          M0, M2
determinism and noise floor                                 M1
runtime, memory, and local feasibility                      M11
relative shape behaviour under oracle alignment             M3
near/far deformation against PROVISIONAL references         M3, M9
edge behaviour                                              M3, M7
underwater-domain stress on public data                     M10
appearance invariance                                       M6
independent-frame temporal stability                        M7
cross-method consistency on project footage                 M9
provisional restoration impact                              M12
=> 2-3 frozen finalists
```

## 26.2 NOT honestly establishable before C2

```text
definitive objective accuracy on this camera
final absolute range error
final metric-scale accuracy on this footage
whether MapAnything or any other Week-3 hypothesis is objectively correct
definitive confidence calibration
the final adequate / degraded / unsafe operating envelope
the final Week-4 winner
```

The reason is unchanged from Week 3 and was *strengthened* by Phase 3B: **the
reference itself is unidentified on exactly the clips where cross-family
disagreement was largest.** A monocular candidate that disagrees with COLMAP on a
1,099-observation clip has not been shown to be wrong. Week 4A must carry that
distinction into every table it produces, or it will manufacture a false ranking
from an unanchored reference.

## 26.3 Week 4B, after C2 — and its scope limit

Only the **frozen finalists** are evaluated against:

```text
independent C2 anchors
the final Week-3 selected + runner-up products
fixed calibration transfer                                  (E2, properly closed)
raw metric output                                           (E3, properly closed)
definitive confidence calibration
the definitive restoration-sensitivity envelope
```

**Week 4B is not another discovery pass.** If a new model appears between now and
then, it enters through a section-23 trigger or not at all.

## 26.4 What C2 must capture, from this review's perspective

Week 3 already specified deliberate lateral/arc motion, and **measured**
camera-to-interface stand-off and port thickness (a 25x change in assumed
stand-off moved implied scale 172x and recovered focal 3x). This review adds four
requirements that are cheap at capture time and impossible to reconstruct later:

1. **A colour/scale chart at several known distances in one frame**, following
   SQUID's design. It is the only construction that measures **near/far bias**
   directly, and near/far bias is the failure mode the section-2.2 budget punishes
   hardest. SQUID's charts are 12.5 x 18 cm and doubled as its metric validation.
2. **Record whether the GT quantity is z-depth or Euclidean range, explicitly.**
   FLSea and Sea-thru both leave this **unstated**, and the published underwater
   benchmark compared z-depth predictions against SQUID's Euclidean range with no
   conversion — an error that grows toward the frame edge and would be invisible
   in a summary metric.
3. **Capture the same scene under at least two water/visibility conditions, and
   with and without dive lights.** Without this, M6's appearance-invariance work
   rests entirely on synthetic perturbation, and section 20.4's fragility
   hypothesis cannot be tested on real water.
4. **Capture with EIS off if the camera permits it, alongside the EIS-on take.**
   EIS is a documented, unresolved confound for every Week-3 number and is a
   specific mechanism for per-frame scale breathing (section 19.5). One matched
   pair would separate stabiliser-induced instability from model instability, for
   the cost of one extra take.


---

# 27. Adversarial self-review

Second pass, written to **disprove** section 22. Three findings changed the
recommendation; the rest are recorded as accepted risks.

---

## 27.1 The initial recommendation

```text
P1  MoGe-2-L  (+ MoGe-1 paired)
P2  DA3MONO-LARGE + DA3METRIC-LARGE  (paired)
P3  UniDepth V2 ViT-L
P4  Wat3R
P5  Depth Anything V2 (Small / Large)
```

---

## 27.2 CHANGE 1 — a missing control that answers the actual Week-4 question

**Q19: is there a family that could dominate this shortlist that I failed to
investigate?** Yes, and it was hiding in the project's own repository.

The Week-4 question is: *can a strictly single-image estimator substitute for
multi-view range when video geometry is unavailable?* Every candidate in section
22 answers "which monocular model is best". **None of them measures the thing the
question actually asks — the size of the monocular-vs-multi-view gap** — because
each differs from MapAnything in architecture, training data, preprocessing and
output semantics simultaneously.

**MapAnything's own single-view path is the exact control**, and it costs almost
nothing:

```text
already integrated                Week 3 built and ran the wrapper
already MPS-verified              bitwise reproducible on MPS fp32, fixed seed
already licence-cleared           facebook/map-anything-apache, Apache-2.0
already semantics-verified        depth_along_ray == ||pts3d_cam|| to 1.1e-5
                                  - range is MEASURED, not converted
emits an explicit validity mask
monocular is a documented supported task   (arXiv 2509.13414, 3DV 2026)
```

Running it at N=1 isolates **view count and nothing else**. That is the only clean
measurement of what dropping to monocular costs, and it directly calibrates
whether *any* monocular candidate is good enough — the actual gate.

The counter-argument is that VGGT-family single-view quality is weak ("*surprisingly
good ... although it was never trained for this task*"). That is exactly why it is
a **control and a floor**, not a candidate: its value is in isolating the variable,
and it is independent of whether it wins.

**Added as P0.** This takes the set to six families — justified under the brief's
"six if genuinely necessary", because P0 is not a sixth hypothesis but the control
for the whole exercise, at near-zero marginal cost.

## 27.3 CHANGE 2 — two benchmark tables I was at risk of cross-reading

**Q7: did I compare incompatible benchmark numbers?** Nearly.

This document contains two underwater tables that **must never be read against
each other**:

```text
Wat3R Table 4        alignment: explicit least-squares SCALE AND SHIFT
                     subsets:   FLSea VI, SQUID, Sea-thru
                     e.g. DA3 = 0.090 Rel on FLSea VI

Cai & Metzler        alignment: RAW METRIC, none (verified by full-text search
                                for median/affine/align/cap/crop)
                     subsets:   FLSea-Canyon, FLSea-Red Sea, SQUID
                     e.g. UniDepth V2-L = 0.1156 AbsRel on FLSea-Canyon
```

Different alignment, different subsets, different definition of the score.
**DA3's 0.090 is not "better than" UniDepth V2's 0.1156.** An explicit warning is
now carried in sections 13.2 and 14.1. This is the single easiest way for a later
reader to draw a wrong conclusion from this document.

**A reconciliation this exposed, which strengthens the framework.** Depth Pro
appears in three sources with apparently contradictory verdicts:

```text
WideDepth (ICRA 2026)      MOST FOV-robust:  +9.0% (vs DA V2 +166%)
Cai & Metzler              WORST underwater: SQUID AbsRel 3.2185
Honey I Shrunk... (2026)   "orders of magnitude smaller than reality"
```

These are **not** contradictory once E1 and E3 are separated: Depth Pro's *shape
and FOV behaviour* are excellent while its *absolute scale* is catastrophic. Two
of the three sources score E3; one scores shape robustness. **That is independent
validation of section 17.2's insistence on keeping the three evaluations
separate** — a single "which model is best underwater" number would have been
actively misleading here.

## 27.4 CHANGE 3 — I under-weighted the closest competitor for the wrong reason

**Q9: did I exclude a candidate mainly because it is inconvenient to run?**
Not quite — but I excluded **FoundationGeo** partly for *immaturity*, which is a
weaker reason than I initially treated it as.

Head to head against P1:

```text
                        FoundationGeo-1.1        MoGe-2-L
native range            YES (d = ||p||_2)        via ||P_cam||  (equivalent)
unit ray direction      YES, native              derived
relative/metric pairing Stage-I / Stage-II,      MoGe-1 / MoGe-2,
                        SAME training run        DIFFERENT training runs
licence                 MIT / MIT                MIT / MIT
venue                   ECCV 2026                CVPR 2025 Oral
OOD-focal analysis      YES, explicit            no
validity mask           yes                      yes
third-party evaluation  NONE                     DyFN, DAGE, MetricScenes
runtime published       no                       60 ms (A100, fp16, ViT-L)
```

FoundationGeo's pairing is **cleaner** than MoGe's (two stages of one training run
vs two separate models), and its native semantics are marginally better. The
honest tiebreaker is **not** maturity for its own sake: it is that **MoGe-2's
failure modes are documented by three independent third parties** — DyFN measured
scale-shift drift on it, DAGE argued its multi-scale local loss breaks
consistency, and MetricScenes measured its far-field scale collapse. For a bakeoff
whose purpose is *elimination*, a candidate whose failure modes are already
characterised yields more information per run than one with no external evaluation
at all.

**Recorded as the closest call in this review.** FoundationGeo keeps the
strongest conditional trigger (section 23, first entry), and if MoGe-1/-2 turn out
not to run on MPS, **FoundationGeo should be reconsidered for P1 immediately**
rather than defaulting to a CUDA rental.

---

## 27.5 Accepted risks — challenges considered that did NOT change the set

**Q2 / Q8: three metric models is arguably over-weighting a free axis.**
MoGe-2, DA3 Metric and UniDepth V2 all carry metric heads, in a review that argues
metric scale is nearly free. This is the weakest part of the set. It is retained
because the three use **genuinely different scale-recovery mechanisms** (point-map
metric head; canonical-focal `focal*net/300`; dense predicted camera) and section
4.2 shows they **fail differently** in the far field. **Named collapse condition:**
if M5 shows all three failing in a *benign global* way, drop to one metric model
for Week 4B and reallocate the slot.

**Q1: did I overweight benchmark SOTA?** UniDepth V2 is in the set *because* it
won a benchmark — but its role is explicitly adversarial (falsify the claim that
its benchmark win is irrelevant), and its cost is capped: standard battery only,
one resolution, no extra ablations. If it also loses E1, it is dropped from 4B.

**Q5: did I confuse multi-view capability with monocular performance?** Partly, on
**Wat3R** — and this needs stating plainly. Week 3 ran its **multi-view** path;
the single-view numbers in its Table 4 are its authors' own. So "already
integrated" is **half true**: the environment, licence and MPS feasibility carry
over; the single-view wrapper does not, and must be built and verified under M0
like any other. The claim in section 13.2 that this project holds the only
independent evidence about Wat3R remains true, but that evidence is about a
different inference mode.

**Q3: did I miss a newer 2026 model?** Coverage runs to roughly **2026-08-30**;
the last week of arXiv is under-indexed, and the session's web-search budget was
exhausted mid-review (arXiv/GitHub/HuggingFace APIs carried the remainder). A very
recent release could have been missed. Section 23's triggers are the intended
remedy — novelty alone is not one.

**Q4: did I miss an underwater specialist?** The sweep was thorough and produced
two informative surprises: **CD-UDepth and UDepthDiff are journal-only, absent
from arXiv**, which is why they were hard to verify and why their claims are
unsupported by code. **The one real gap is Atlantis++** (IJCV 2026, DOI
10.1007/s11263-026-02823-1), paywalled, which claims a benchmark with *"controlled
turbidity levels and colour casts"* — precisely the controlled stress this review
found missing. It is the highest-value follow-up read.

**Q6: central vs non-central.** Confirmed by two independent sweeps over
nineteen-plus models. Section 16.3 additionally argues from the project's *own*
Phase-3B data that the central approximation is not currently the binding
constraint.

**Q10: confidence.** No model's confidence is trusted anywhere in this document;
section 18 requires a measured separation ratio against Week 3's 1.07x.

**Q11 / Q12: checkpoint and licence verification.** Done systematically, and it
found more than expected: DA V2 Giant never released; DA3-LARGE-1.1's licence
conflicting between two official sources; Depth Pro's README pointing at the wrong
licence; Marigold's model licence being an **unfilled template**; and four of the
most capable metric/camera-general checkpoints (Metric3D, UniDepth V2, UniK3D,
UniDAC) declaring **no licence at all**. The Water-VGGT precedent from Week 3 —
an "underwater" checkpoint bitwise identical to `facebook/VGGT-1B` — justified
this standard, and it paid.

**Q13 / Q14: representation errors.** DA3's z-depth settled by two independent
routes (paper equations and shipped `unproject(coordinates, z, intrinsics)`).
**Two open items are flagged as measurements rather than resolved on paper:**
DA3 Mono's Class 2-vs-3 status, and whether MoGe-1's released output is
shift-resolved. Both are M2.

**Q16: secondary sources.** Three load-bearing numbers came from agent extraction
of paper *bodies* rather than my own verification: **WideDepth's per-model FOV
degradation**, **Wat3R's Table 4**, and **the Arc de Triomphe figures**. All three
are flagged inline. None of them alone changes the primary set, but WideDepth's
ordering underpins a conditional trigger and should be confirmed against the PDF
before it is acted on.

**Q17: TTA priming.** The prompt raised TTA; the review concluded the leading
method solves a problem this project does not have. That is the opposite of
priming.

**Q18: shortlist preservation.** Of five supplied core candidates, one was removed
(WaterMono), one was reframed (UniDepth V2), one was confirmed as a paired family
(DA3), one was retained with new caveats (MoGe-2), and two models were added that
were not on the list (Wat3R, DA V2) — plus P0 from the adversarial pass.

**Q15: paper variant vs released.** DA V2 Giant, Metric3D v2 ViT-L (excluded from
the underwater benchmark for hardware reasons, so its best configuration is
untested underwater), SPADE's unreleased weights, and MetaDepth-CPU all caught.

**Q20: unreconciled contradictions.** Reconciled: Depth Pro (27.3). Recorded as
open: DA3-LARGE-1.1's licence (two official sources disagree); DA3's parameter
counts and author list (paper vs README vs ICLR page); DA3's abstract claiming
44.3%/25.1% against its own HTML body's 35.7%/23.6%; and MoGe-1's ambiguity class.
None blocks the recommendation; all are logged.

## 27.6 One structural doubt worth stating

This review has repeatedly used Week 3's scale-invariance result to discount
metric accuracy. That result is solid — but it holds **with coefficients freely
fitted *in-clip***. Section 2.3 lists five situations where coefficients are
*shared or transferred*, and week 6's artificial-light modelling is one of them
and is not far away. **If the pipeline moves to cross-clip coefficient sharing,
the discount on metric accuracy weakens considerably**, and P3's role changes from
adversarial to central. That is not a reason to change Week 4A, but it is a reason
to record the metric numbers carefully now rather than discarding them as
uninteresting.


---

# 28. Final recommendation

## 28.1 The set, after adversarial review

**Six families, nine checkpoints.** One is a control, two are internally paired.

| # | Family | Checkpoint(s) | Licence (code / ckpt) | Role | Local? |
|---|---|---|---|---|---|
| **P0** | **MapAnything, 1-view** | `facebook/map-anything-apache` | Apache-2.0 / **Apache-2.0** | **Control**: isolates view count and nothing else; measures the monocular-vs-multi-view gap directly | **yes, verified** |
| **P1** | **MoGe-2** (+ MoGe-1) | `Ruicheng/moge-2-vitl`, `Ruicheng/moge-vitl` | MIT / **MIT** | Point-map / native-range baseline; metric-vs-relative isolated | likely — **M0 must confirm** |
| **P2** | **DA3 Mono + Metric** | `depth-anything/DA3MONO-LARGE`, `DA3METRIC-LARGE` | Apache-2.0 / **Apache-2.0** | Field reference; best-documented ambiguity semantics (Class 2) | **no — rented CUDA** |
| **P3** | **UniDepth V2 ViT-L** | `lpiccinelli/unidepth-v2-vitl14` | CC BY-NC 4.0 / **none declared** | Falsification target: the underwater benchmark champion | CUDA documented |
| **P4** | **Wat3R** | `lsxi77777/Wat3R` | Apache-2.0 / **Apache-2.0** | Underwater specialist control **and** fragility probe | **yes** (VGGT family, MPS-proven in Week 3) |
| **P5** | **Depth Anything V2** | `...-V2-Small` (+`-Large`) | Apache-2.0 / Apache-2.0 (Large: CC BY-NC) | Reference floor; Class-4 measurement instrument; regression anchor | **yes — first-party MPS** |

Four of six run locally. Only P2 requires a rental, and it is the only way to test
the Class-2 hypothesis on the field's reference model.

## 28.2 What each family would have to do to win or lose

```text
P0  wins    if the multi-view/monocular gap is small - which would mean any
            decent monocular model suffices and the bakeoff can be cheap
    loses   if the gap is large - which sets the bar every other candidate must
            clear, and is itself the most valuable single number in Week 4A

P1  wins    best/tied E1, exact range conversion, no far-field bias inside 15 m
    loses   DAGE's seam/drift critique bites, or MetricScenes' scale collapse
            reproduces at reef distances, or it will not run on MPS

P2  wins    top-tier E1 AND the fitted shift is indistinguishable from zero
            (confirming Class 2) - the only candidate that could be both
            structurally excellent and deployably aligned
    loses   shift is significantly non-zero (demoting it to Class 3), or the
            metric half adds nothing once a scale is fitted

P3  wins    it leads E1 as well as E3 - a genuine surprise, and evidence the
            underwater benchmark was measuring something real
    loses   its lead evaporates under oracle alignment - confirming s.14.1

P4  wins    beats P1/P2 on E1 across ALL five test-set categories, including
            lights/ and cenote-like conditions
    loses   its advantage is confined to conditions resembling its training
            video - the pattern now seen three times independently

P5  wins    the Class-4 penalty proves small inside 1-15 m, which would reopen
            the whole MiDaS lineage and simplify deployment enormously
    loses   far-field Mobius deformation is large - the predicted outcome
```

## 28.3 The three findings a later reader should not lose

1. **Ambiguity class dominates benchmark rank.** Scale-only-in-depth is
   exactly absorbable; affine-in-depth breaks the backscatter term and the `d=0`
   boundary condition; affine-in-disparity is a Möbius range deformation with a
   finite depth horizon. This reorders the field in a way no leaderboard shows,
   and it is derived (section 17.1), not asserted.
2. **Per-frame flicker is mostly ambiguity drift, not geometry error.** DyFN:
   δ₁ **62.5** under one global alignment vs **99.8** per-frame. Combined with
   Week 3's scale invariance, the fallback-video path is far less risky than it
   looked — *conditional on the candidate's ambiguity class*.
3. **The one clean underwater benchmark scores the one axis this project doesn't
   need.** Cai & Metzler is raw-metric with no alignment. Its ranking is an E3
   ranking. Week 4A must re-run it with aligned protocols before treating any of
   it as evidence about shape.

## 28.4 What to do first

```text
1. M0 on P0 and P5 - both already run locally. Establishes the harness, the
   range-conversion verification, and the preprocessing audit, on the two
   cheapest candidates.
2. M0 + M2 on P1. If MoGe will not run on MPS, escalate FoundationGeo-1.1 to P1
   NOW rather than defaulting to a CUDA rental (section 27.4).
3. M2 on P2 (rented). The DA3 Class-2-vs-3 question is the highest-information
   single measurement in Week 4A: it decides whether the field's reference
   relative model is deployable here at all.
4. Everything else in the M3-M12 order of section 25.
```

## 28.5 Honest limits of this document

- It is a **literature and release** review. It selects candidates; it does not
  establish that any of them works on this footage.
- **No underwater depth-GT dataset uses a flat-port wide-FOV camera.** Nothing
  here can be extrapolated to GoPro reef video without C2.
- **Three load-bearing numbers were extracted from paper bodies by delegated
  agents rather than verified by me**: WideDepth's per-model FOV degradation,
  Wat3R's Table 4, and the MetricScenes/Arc-de-Triomphe figures. Flagged inline;
  confirm against PDFs before acting on them.
- Coverage runs to roughly **2026-08-30**; the session's web-search budget was
  exhausted mid-review and the remainder was carried by the arXiv, GitHub and
  HuggingFace APIs.
- **Atlantis++ (IJCV 2026) is paywalled and unread**, and it claims exactly the
  controlled-turbidity benchmark this review found missing. It is the one known
  gap that could change section 25's design.


---

# 29. Source inventory

Verification tags: **P**=paper identity verified at a primary registry;
**C**=code repo fetched and contains real source; **K**=checkpoint verified
present (model card and/or byte size); **L**=licence read from a primary file or
model-card field. `—` = not applicable. `?` = attempted and unverified.

## 29.1 Primary candidates

| Work | Identifier | Venue / date | P C K L | Code lic | Ckpt lic |
|---|---|---|---|---|---|
| MapAnything | arXiv 2509.13414 | 3DV 2026 | ✔✔✔✔ | Apache-2.0 | `facebook/map-anything-apache` **apache-2.0**; `facebook/map-anything` cc-by-nc-4.0 |
| MoGe | arXiv 2410.19115 | CVPR 2025 Oral | ✔✔✔✔ | MIT | MIT |
| MoGe-2 | arXiv 2507.02546 | 2025-07-03 | ✔✔✔✔ | MIT | MIT |
| MoGe-3 | arXiv 2607.17967 | 2026-07-20 | ✔✔✔✔ | MIT | MIT |
| Depth Anything 3 | arXiv 2511.10647 | **ICLR 2026** (`iclr.cc/virtual/2026/poster/10006531`; OpenReview `yirunib8l8`, bot-blocked) | ✔✔✔✔ | Apache-2.0 | MONO/METRIC/BASE/SMALL **apache-2.0**; GIANT/NESTED cc-by-nc-4.0; **LARGE-1.1 CONFLICT** |
| UniDepthV2 | arXiv 2502.20110 | TPAMI, DOI 10.1109/TPAMI.2025.3628473 | ✔✔✔✗ | **CC BY-NC 4.0** | **none declared** |
| UniDepth (v1) | arXiv 2403.18913 | CVPR 2024 | ✔✔✔✗ | CC BY-NC 4.0 | none declared |
| Wat3R | arXiv 2607.08772 | **ECCV 2026** (Oral per repo) | ✔✔✔✔ | Apache-2.0 | **apache-2.0**; `model.safetensors` 4,762,545,592 B |
| Depth Anything V2 | arXiv 2406.09414 | **NeurIPS 2024** | ✔✔✔✔ | Apache-2.0 | Small **apache-2.0**; Base/Large **cc-by-nc-4.0**; **Giant NEVER RELEASED** (HTTP 401; absent from a complete 48-model org enumeration) |
| Depth Anything V1 | arXiv 2401.10891 | CVPR 2024 | ✔✔✔✔ | Apache-2.0 | — |

## 29.2 Challengers

| Work | Identifier | Venue / date | P C K L | Code lic | Ckpt lic |
|---|---|---|---|---|---|
| FoundationGeo | arXiv 2607.11588 | **ECCV 2026** | ✔✔✔✔ | MIT (⚠️ copyright line says "Microsoft Corporation"; GitHub API reports NOASSERTION) | **MIT** ×4 |
| OptiGeo | arXiv 2608.29881 | 2026-08-30 | ✔✔✔✔ | MIT | MIT |
| UniDAC | arXiv 2603.27105 | **CVPR 2026**, pp. 26953-26963 | ✔✔✔✗ | **MIT** | **none declared**; `unidac.pt` 1.42 GB |
| Depth Any Camera | arXiv 2501.02464 | 2025-01-05 | ✔?✗✗ | — | — |
| UniK3D | arXiv 2503.16591 | CVPR 2025 (repo-asserted) | ✔✔✔✗ | **CC BY-NC-SA** (viral) | **none declared** |
| Depth Pro | arXiv 2410.02073 | **ICLR 2025** | ✔✔✔✔ | Apple sample-code | **`apple-amlr`** research-only, revocable, binds fine-tunes ⚠️ README misstates |
| RayTun3R | arXiv 2607.02711 | 2026-07-02 | ✔✗✗✗ | ? | ? |
| PointDiT | arXiv 2607.02515 | **ICML 2026** | ✔✔✔✔ | Apache-2.0 | Apache-2.0 (⚠️ needs **gated DINOv3**) |
| PaGeR | arXiv 2605.26368 | preprint | ✔✔✔✔ | Apache-2.0 | **CC BY-NC 4.0** (separate LICENSE-MODEL; 1.41B params) |
| DepthMaster (panoramic) | arXiv **2606.12368** | 2026-06-10, no venue | ✔✔✔✔ | MIT | ? |
| DepthMaster (diffusion) | arXiv **2501.02576** | IEEE TCSVT 2026 | ✔✔✗✗ | ? | ? |
| Metric3D v2 | arXiv 2404.15506 | TPAMI 2024 | ✔✔✔✗ | BSD-2 | **never stated** |
| Metric3D | arXiv 2307.10984 | ICCV 2023 | ✔✔✔✗ | BSD-2 | never stated |
| ZoeDepth | arXiv 2302.12288 | **NO VENUE** (repo BibTeX `@misc`) | ✔✔✔✔ | MIT | MIT |
| Dens3R | arXiv 2507.16290 | ICLR 2026 (repo-claimed) | ✔✔✔✔ | **CC BY-NC-SA** | same |
| DAGE | arXiv 2603.03744 | **CVPR 2026** (comments) | ✔✔✔~ | **CC BY-NC 4.0** (in `license.md`) | **none declared** |
| WideDepth | arXiv 2605.24074 | **ICRA 2026** | ✔?✗✗ | ? | ? |
| MetricScenes / "Honey, I Shrunk the Arc de Triomphe!" | arXiv 2606.02379 | 2026-06-01 / -26 | ✔?✗✗ | ? | ? |

## 29.3 Generative family

| Work | Identifier | Venue | Code lic | Ckpt lic |
|---|---|---|---|---|
| Marigold | arXiv 2312.02145 | CVPR 2024 Oral | Apache-2.0 | ⚠️ `LICENSE-MODEL.txt` is an **unfilled template** (`[insert use restrictions]`); HF: v1-0 apache-2.0, v1-1 **openrail++** |
| Marigold (journal ext.) | arXiv 2505.09358 | IEEE (unverified) | — | — |
| Marigold-DC | arXiv 2412.13389 | **ICCV 2025** | Apache-2.0 | not restated |
| Lotus | arXiv 2409.18124 | **ICLR 2025** | Apache-2.0 | apache-2.0 (⚠️ SD-derived) |
| **Lotus-2** | arXiv 2512.01030 | **no venue** | Apache-2.0 | apache-2.0 ⚠️ **FLUX.1-dev non-commercial inheritance unstated**; **≥40 GB VRAM** |
| E2E-FT | arXiv 2409.11355 | **WACV 2025 Oral** | ⚠️ LICENSE 404 | apache-2.0 |
| GenPercept | arXiv 2403.06090 | ICLR 2025 | BSD-2 + non-commercial README clause | not stated |
| DepthFM | arXiv 2403.13788 | AAAI 2025 | MIT | **undisclosed** (SD2.1-derived) |
| GeoWizard | arXiv 2403.12013 | ECCV 2024 (repo) | ? | ? |
| BetterDepth | arXiv 2407.17952 | venue unverified | **no repo found** | — |
| Pixel-Perfect Depth | arXiv 2510.07316 | **NeurIPS 2025** | ? | ? |
| Iris | arXiv 2603.16340 | **CVPR 2026** | ? | ? |
| DVD | arXiv 2603.12250 | 2026-03-12 | Apache-2.0 | **CC BY-NC 4.0** |
| DepthCrafter | arXiv 2409.02095 | venue unverified | **hard non-commercial, code AND weights** | same |
| RollingDepth | arXiv 2411.19189 | **CVPR 2025** | Apache-2.0 | RAIL++-M |
| ChronoDepth | arXiv 2406.01493 | CVPR 2025 | ? | MIT (⚠️ SVD-derived) |

## 29.4 Underwater

| Work | Identifier | Venue | P C K L | Notes |
|---|---|---|---|---|
| Wat3R | arXiv 2607.08772 | ECCV 2026 | ✔✔✔✔ | See 29.1 |
| WAT3R (**different paper**) | arXiv 2607.21023 | no venue | ✔✗✗✗ | Project page advertises code; **no repo URL anywhere** |
| Cai & Metzler | arXiv 2507.02148 | **no venue, preprint** | ✔✗✗✗ | Code and fine-tuned weights **never released** (27 repos of first author enumerated) |
| WaterMono | arXiv 2406.13344 | IEEE TIM 2025 | ✔✔~✗ | **No LICENSE file**; 9★/0 forks/4 issues |
| UDepth | arXiv 2209.12358 | ICRA 2023 | ✔✔✔✗ | **No LICENSE — all rights reserved** |
| UW-Depth / TRUDepth | arXiv 2310.16750 | ICRA 2024 | ✔✔✔✔ | **MIT**; requires sparse priors |
| SPADE | arXiv 2510.25463 | **IEEE JOE 2026**, DOI 10.1109/joe.2026.3707696 | ✔✔✗✔ | MIT code; **weights "coming soon"** |
| CD-UDepth | **DOI 10.1016/j.inffus.2025.102961**, Information Fusion 118:102961 | 2025-06 | ✔✔~✗ | **NOT on arXiv**; repo 1★, no licence |
| UDepthDiff | **DOI 10.1109/access.2026.3651731**, IEEE Access 14:26953-26964 | 2026 | ✔✗✗✗ | **NOT on arXiv**; APC megajournal; no code |
| UMono | arXiv 2407.17838 | IEEE JOE 2026 | ✔✗✗✗ | No code |
| Tree-Mamba / BlueDepth | arXiv 2507.07687 | no venue | ✔✗✗✗ | Repo **0 KB, 1 commit**, predates its own posting |
| UW-Adapter | **DOI 10.1109/tmm.2025.3543089**, IEEE TMM 27:4808-4818 | 2025 | ✔✗✗✗ | Conceptually ideal, unobtainable |
| PUDE | **DOI 10.1007/978-3-031-73209-6_26** | **ECCV 2024** | ✔✗✗✗ | Code not located |
| Atlantis | arXiv 2312.12471 | **CVPR 2024 Highlight** | ✔✔—✔ | **MIT**; data pipeline, **no depth checkpoint** |
| Atlantis++ | **DOI 10.1007/s11263-026-02823-1**, IJCV 134(6):260 | 2026-05-07 | ✔✗✗✗ | **PAYWALLED — contents unverified. Highest-value follow-up** |
| Osmosis | arXiv 2403.14837 | **ECCV 2024** | ✔?✗✗ | RGBD diffusion prior, never trained underwater |
| StereoAdapter | arXiv 2509.16415 | 2025-09 | ✔✔?✗ | No licence file |
| StereoAdapter-2 | arXiv 2602.16915 | 2026-02 | ✔?✗✗ | README claims CC BY-NC-SA, no file |
| TIDE | arXiv 2503.21771 | **CVPR 2025** | ✔✔✔✔ | **Apache-2.0**; ⚠️ depth annotations are **DA V2 output** |
| uw3dgs cross-regime study | arXiv 2608.25483 | 2026-08-26 | ✔✔——✗ | Independent controlled comparison |
| "DepthDive" | — | — | **DOES NOT EXIST** | arXiv full-text `all:"DepthDive"` → totalResults=0 |

## 29.5 Datasets

| Dataset | Identifier | GT source | Metric? | Quantity | Licence | Download |
|---|---|---|---|---|---|---|
| FLSea | arXiv 2302.12772; JFR DOI 10.1002/rob.70291 | Agisoft Metashape SfM | yes (1 m targets) | **not stated** | CC BY-NC-SA 4.0 ✔ | Kaggle `viseaonlab/flsea-vi` 92.35 GB, `-stereo` 90.65 GB ✔ |
| SQUID | arXiv 1811.01343; **IEEE TPAMI 2020** | stereo + EpicFlow, ≤5 px EPE gate | yes (12.5×18 cm charts) | **Euclidean RANGE** | CC BY-NC-SA 4.0 ✔ | Zenodo 10.5281/zenodo.5744037, 45.8 GB ✔ |
| Sea-thru | **CVPR 2019** (PDF text is vector outlines, unextractable) | Metashape SfM | yes (metres) | **not stated** | CC BY-NC-SA 4.0 ✔ | Kaggle `colorlabeilat/seathru-dataset` 38.44 GB ✔ |
| VAROS | ICCVW 2021 | rendered | yes | rendered | **CC BY 4.0** ✔ | Zenodo 10.5281/zenodo.5567209 ✔ |
| SubPipe | arXiv 2401.17907; Zenodo 10.5281/zenodo.10053564 | — | — | **no dense depth GT** | ✔ | ✔ (**GoPro Hero 10**, full intrinsics published) |
| Atlantis | arXiv 2312.12471 | **real terrestrial LiDAR (DIODE)** + generated water | yes | — | CC BY-NC-SA 4.0 ✔ | Kaggle ✔ |
| USOD10K | IEEE TIP 2023 | **DPT pseudo-labels** | no | — | academic-only | — |
| BlueDepth | arXiv 2507.07687 | **6-model monocular ensemble** | no | — | — | Google Drive, unverified |
| UIEB / EUVP / LSUI / SUIM | 1901.05495 / 1903.09766 / 2111.11843 / 2004.01241 | — | — | **no depth GT** | — | — |

## 29.6 Robustness, temporal, uncertainty, adaptation

| Work | Identifier | Venue | Used for |
|---|---|---|---|
| van Dijk & de Croon | arXiv 1905.07005 | ICCV 2019 | Canonical cue-probing; vertical-position dominance |
| RoboDepth | arXiv 2310.15171 | **NeurIPS 2023** | 18 corruptions, 42 models — but only 2019-2023 architectures |
| PDE | arXiv 2507.00981 | — | 9 modern models, 12 perturbations — but **no haze/scattering** |
| DepthAnything-AC | arXiv 2507.01634 | — | ⚠️ fog is a **Diamond-Square noise overlay**, range-independent |
| DyFN | arXiv 2605.25308 | 2026-05-25 | **δ₁ 62.5 vs 99.8 — flicker is scale-shift drift** (on MoGe) |
| Video Depth Anything | arXiv 2501.12375 | **CVPR 2025** | TAE table; DA V2-L per-frame = 1.140 |
| NVDS+ | arXiv 2307.08695 | ICCV 2023 + TPAMI 2024 | OPW definition and per-frame MiDaS/DPT numbers |
| StableDPT | arXiv 2601.02793 | 2026-01-06 | DA V2 far more stable per-frame than MiDaS |
| oVDA | arXiv 2510.09182 | — | Independent scale-drift corroboration |
| Depth Any Video | arXiv 2410.10815 | — | Original TAE definition (⚠️ different constant from VDA's) |
| Landgraf, Qin, Ulrich | arXiv 2501.08188 | 2025-01-14 | Best UQ synthesis; **in-distribution only** |
| Marsal et al. (depth-rescaling) | arXiv 2412.14103 | **IROS 2025** | The leading "depth TTA" is sparse-point rescaling; CC-BY-4.0 |
| ReDepth Anything | arXiv 2512.17908 | **CVPR 2026 Findings** | Single-image test-time refinement; mutates weights per sample |
| DARES | arXiv 2408.17433 | — | LoRA-on-DA precedent (endoscopy) |
| EndoDAC | arXiv 2405.08672 | MICCAI 2024 | PEFT precedent |
| Surgical-DINO | arXiv 2401.06013 | IPCAI 2024 | Adapter precedent |
| EndoUFM | arXiv 2508.17916 | — | Foundation-model domain adaptation |
| ER-LoRA | arXiv 2509.00665 | — | Weather-generalised depth via LoRA |
| Multi-Modality LoRA | arXiv 2412.20162 | — | Adverse-condition depth |
| Toward a Better Understanding of Monocular Depth Evaluation | arXiv 2510.19814 | — | Metrics *"severely under-sensitive to curvature perturbation"* |
| Monocular Depth Estimation from a Single Image: Progress and Opportunities | arXiv 2609.01172 | CVMJ | 2026-09-01 survey; coverage cross-check |
| One Scene, Two Depths | arXiv 2606.29600 | **ECCV 2026** | ⚠️ *multi-layer/transparency* ambiguity, **not** appearance shortcuts |

## 29.7 Verification method and its limits

Verification used arXiv abstract and HTML pages, the **arXiv API**, CVF and
`iclr.cc` virtual pages, **OpenAlex** and **Crossref** for DOIs and journal
identity, the **GitHub REST API** and `raw.githubusercontent.com` for licences and
source, and the **HuggingFace API** for checkpoint existence, licence fields and
byte sizes. Where a repo shipped both a `LICENSE` and a model licence, both were
read.

**Known limits.**
- The session's **WebSearch budget (200) was exhausted mid-review**; the remainder
  ran on the arXiv/GitHub/HuggingFace APIs, which index differently. Coverage runs
  to roughly **2026-08-30**.
- **Blocked hosts:** OpenReview (bot challenge), Springer/Wiley/Elsevier
  (paywall or 403), CVF (blocks fetch; reachable by `curl` with a browser UA).
  The Sea-thru CVPR PDF's text is stored as **vector outlines and is not
  extractable**.
- **Three load-bearing numbers came from delegated agents' extraction of paper
  bodies, not from my own verification**: WideDepth's per-model FOV degradation,
  Wat3R's Table 4, and the MetricScenes figures. All flagged inline.
- Unresolved contradictions, all logged in-place: DA3-LARGE-1.1's licence (HF card
  vs GitHub README); DA3's parameter counts and author list; DA3's abstract
  (44.3%/25.1%) vs its own HTML body (35.7%/23.6%); MoGe-1's ambiguity class
  (paper says scale + z-shift, one source reports the released output is
  shift-resolved); VGGT's CVPR 2025 Best Paper award (repo-asserted, not confirmed
  on CVF).
