# Week-4A monocular depth — DELTA REVIEW

**Superseded by MONO_DEPTH_FREEZE.md**

**Adversarial revision of `MONO_DEPTH_LANDSCAPE.md`. Compiled 2026-09-06.**
Assumes the first review as context; does not reproduce it.

> **Question answered:** after investigating the omissions, recent releases and
> contested claims below, what is the MINIMUM scientifically complete Week-4A
> pre-C2 bakeoff that maximises information about whether strict single-image
> depth is adequate for this underwater-restoration pipeline?

---

## THE ANSWER

**Three primary families + three cheap controls. Nine checkpoints, six wrappers.
Four of six run locally on the M4; one needs rented CUDA.**

```text
CONTROLS
C1  facebook/map-anything-apache      N=1     Apache/Apache   V1  view count
C2  Depth-Anything-V2-Large + -Small          Apache/(NC,Apache) V3 Class-4 +
                                                              the real N=1
                                                              underwater incumbent
C3  lsxi77777/Wat3R                   N=1     Apache/Apache   V7  underwater

PRIMARY FAMILIES  (both pairings isolate one variable each)
F1  Ruicheng/moge-2-vitl                      MIT/MIT      \  V5 camera-diverse
    yjh001/metricanything_student_pointmap    Apache/Apache /  metric pretraining
F2  depth-anything/DA3MONO-LARGE              Apache/Apache \  V3 Class-2 +
    depth-anything/DA3METRIC-LARGE            Apache/Apache /  V4a GLOBAL metric
F3  mxliu-hku/FoundationGeo-Base-1.1          MIT/MIT      \  V4b PIXEL-WISE
    mxliu-hku/FoundationGeo-1.1               MIT/MIT      /  scale field
```

**Plus one change that costs no model integration and may matter more than any
of them:** adopt **RelNormal** via `princeton-vl/EvalMDE` (BSD-3-Clause, no CUDA
dependencies) and SurGe's `MAE_normal`. The paper behind EvalMDE proves the exact
blindness that threatens this project's E1 protocol —
*"affine-aligned metrics are completely insensitive to geometric distortions from
affine transforms"* — which means the first review's planned E1 measurement could
not, on its own, have detected the failure mode it was designed to catch.

**Displaced from the first review's set:** UniDepth V2 (both its justifications
failed), the MoGe-1→MoGe-2 pairing (confounded; replaced by a fine-tune-of-the-same-
checkpoint pairing), Wat3R (primary → control), and the Depth Pro FOV trigger
(withdrawn — its evidence does not support it).


---

# 1. What the first review got wrong or missed

Seven items. Two are material corrections that change a recommendation; two are
omissions of real candidates; three are reasoning defects that happened to reach
the right conclusion by a weak route.

## 1.1 MATERIAL — the WideDepth trigger was overstated and must be withdrawn

The first review promoted Depth Pro to a conditional challenger on the strength of
"+9.0% AbsRel from 120°→195° vs Depth Anything V2's +166%", treating it as
evidence that a camera-*conditionable* model beats a camera-*general* one on
wide-FOV robustness.

Re-reading the primary source (arXiv **2605.24074**, ICRA 2026) [VERIFIED]:

- **The numbers are real.** Table III, caption: *"Percentage change in metrics for
  FOV 195 compared to FOV 120."* DA V2 **+166%**, Depth Pro **+9.0%** AbsRel.
  The UniK3D **+97%** figure I quoted is **NOT confirmed** — UniK3D-Large is in
  the table but I did not see its cell. `number_unverified`.
- **But three protocol facts void the inference:**
  1. *"All models received input data processed as described in Sec. III,
     including **equirectangular projection**, cropping of empty areas, and a
     90-degree counter-clockwise rotation."* Every model was fed **ERP imagery**,
     not native frames. That is a different experiment from this project's
     P0/P1/P2 question.
  2. **UniK3D ran in "camera-free mode without intrinsics"** — its
     camera-conditioning, the entire mechanism under test, was switched off. So
     the "any-camera loses to camera-conditionable" conclusion does not follow.
  3. **The FOV range is 120°→195°, entirely above this project's 105.383°.**
     The claim is an extrapolation *below* the measured range.
- The evaluated set is also narrower than implied: DA V2-Large, PatchFusion,
  ZoeDepth, Depth Pro, UniK3D-Large. **UniDepth, Metric3D and MoGe are not in it.**

**Correction:** the Depth Pro wide-FOV trigger is withdrawn. Depth Pro is
research-only and revocable anyway, so it could never ship. It survives only as an
optional diagnostic if the project's own radial-position error profile (LG-8) is
large.

## 1.2 MATERIAL — MetricAnything was missed, and it makes one of the proposed pairings obsolete

**MetricAnything** (arXiv **2601.22054**, **ECCV 2026**; Ma, Yang, Di, Zhang, Cui,
Li, Xie, Chen) was absent from the first review entirely. Verified now:

```text
yjh001/metricanything_student_pointmap   student_pointmap.pt   apache-2.0
yjh001/metricanything_student_depthmap   student_depthmap.pt   apache-2.0
created 2026-01-31 / 2026-02-05 · 0 downloads each
code  github.com/metric-anything/metric-anything
page  metric-anything.github.io/metric-anything-io
```

**The decisive fact, quoted verbatim from the model card** [VERIFIED]:

> "**MetricAnything Student PointMap** model is finetuned from **MoGe-2 ViT-l**."

Training scale: *"About 20M image-depth pairs spanning reconstructed, captured,
and rendered 3D data across **10000 camera models**"* [VERIFIED, abstract].

**Why this matters more than "another metric model".** It is a **fine-tune of the
exact MoGe-2 ViT-L checkpoint**. Architecture, representation, backbone size and
output semantics are therefore held constant by construction; the only變 variable is
the training data and objective. That makes

```text
MoGe-2 ViT-L  ->  MetricAnything Student-PointMap
```

a **strictly cleaner controlled experiment** than MoGe-1 → MoGe-2, which confounds
a different training run, a different dataset, *and* an added metric head. The
first review proposed the confounded pairing and did not know the clean one
existed.

**Licence chain is clean:** MoGe-2 is MIT, MetricAnything declares Apache-2.0.
MIT permits the relicensed derivative.

**Caveat, stated plainly:** **0 downloads on both checkpoints.** There is no
independent adoption whatsoever, and the first review's own Water-VGGT precedent —
an "underwater" checkpoint bitwise identical to `facebook/VGGT-1B` — is the reason
to verify the weights differ from stock MoGe-2 before trusting any result.

## 1.3 MATERIAL — SurGe was missed, and it names this project's exact problem

**SurGe** (arXiv **2605.31577**, Knaebel, Garcia, Schmidt, Fradlin, Nunes,
de Geus, Leibe — RWTH Aachen, the E2E-FT group). Abstract, verbatim:

> "Recent feedforward 3D reconstruction methods predict point maps and estimate
> global 3D geometry remarkably well. However, their predictions still exhibit
> **inaccurate local surface geometry, which is clearly visible qualitatively but
> only weakly reflected in common metrics**."

That is this project's primary axis, stated by someone else, independently.

Release status [VERIFIED]: repo `github.com/karimknaebel/surge` (66 stars, pushed
2026-08-22), weights `karimknaebel/surge-large` (152 downloads, created
2026-05-27, base model `facebook/dinov2-large`), HF Space demo, project page
`vision.rwth-aachen.de/surge`. Released 2026-06-01.

**Licences, quoted from the README** [VERIFIED]:
> "The **SurGe code** is released under the MIT license. The **SurGe weights** are
> released under **CC BY-NC 4.0**, due to the training datasets used."

(The repo's `LICENSE` file carries "MIT License / Copyright (c) **Microsoft
Corporation**" — the same template artifact seen in FoundationGeo, and for the
same reason: both borrow tooling from MoGe. GitHub reports NOASSERTION as a
result. The grant is unambiguous; the copyright line is wrong.)

**Deployment reality, and it is bad:** `pyproject.toml` requires
**`natten>=0.21.5`** (Neighborhood Attention). PyPI ships natten **0.21.7 as an
sdist only — no wheels at all** [VERIFIED], so it must compile from source; and
every SurGe README example is `.cuda()` / `torch.autocast("cuda")`, with no
MPS or CPU path. **SurGe is a rented-CUDA candidate, not a local one.** (A
third-party `mnmly/mlx-swift-SurGe` port exists, which is suggestive but is a
reimplementation, not the reference path.)

**Its metric contribution is separable from its model, and is adopted regardless
— see §8.**

## 1.4 The first review under-served the measurement problem it identified

It correctly argued that local geometry beats global scale, then proposed metrics
largely of its own invention. It missed that **the exact problem has been
formalised and the tooling released**:

- **arXiv 2510.19814** (Princeton VL) — *"all widely used metrics have very poor
  sensitivity to curvature perturbation"* and, more sharply,
  *"affine-aligned metrics are completely insensitive to geometric distortions
  from affine transforms."* Proposes **RelNormal**, a pairwise-relative
  surface-normal metric, and releases **`princeton-vl/EvalMDE`, BSD-3-Clause,
  with no CUDA-only dependencies** [VERIFIED] — i.e. runnable on the M4.
- **SurGe** provides a complementary *absolute* point-map normal metric and a
  point-gradient loss, both with exact equations (§8).

The first review cited 2510.19814 once, in passing, as "protocol guidance". It is
in fact the load-bearing citation for the whole Week-4A metric design.

## 1.5 UniDepth V2's "native radial range" advantage was overstated as unique

The first review justified P3 partly on UniDepth V2 natively emitting `radius`
(metric ray range) — "the only model that exposes both". That is wrong as a
*selection* argument: **MapAnything's `depth_along_ray` (the control, already
integrated and verified to 1.1e-5), MoGe's `||points||`, and FoundationGeo's
`d = ||p||₂` all give native range too.** Native range is a property of the
point-map family generally, not a UniDepth differentiator.

What remains genuinely distinctive to UniDepth V2 is **intrinsics conditioning
with an explicit `Fisheye624` camera class**, plus its underwater benchmark
result — which §3.1 now confirms is **E3-only evidence**.

## 1.6 The Cai & Metzler classification was right, by a weak argument

The first review established "raw E3, no alignment" by searching the text for
`median`, `affine`, `align`, `cap`, `crop`. **Absence of keywords is not evidence
of absence of a procedure**, particularly since the code was never released.
§3.1 replaces that with a sound argument (per-image median scaling cannot produce
AbsRel > 1; the paper reports 1.59 and 3.22). Conclusion unchanged, justification
repaired.

## 1.7 A logical gap: DA3's metric mechanism is analytically global

The first review treated DA3 Mono → DA3 Metric as a paired family testing "metric
conditioning", on equal footing with MoGe-1 → MoGe-2 and FoundationGeo I → II.
But DA3's documented conversion is

```text
metric_depth = focal * net_output / 300
```

which, for a fixed focal, is a **pure global multiplicative factor** — it
*cannot* introduce local deformation. FoundationGeo Stage-II's **pixel-wise scale
field** `P̃ = S ⊙ P̂` provably can. These two are therefore not interchangeable
tests of the same variable: they are the **control and the treatment** for the
question the brief raises in §13 — *is a spatially varying metric correction
harmless?* The first review missed that structure and would have spent slots
testing the same thing three times.


---

# 2. What new evidence materially changed the shortlist

## 2.1 Wat3R's single-view case is far weaker than the first review had it — and DAv2 is the real N=1 incumbent

The first review made Wat3R a **primary** family on the strength of its Table 4
single-view numbers. Those numbers are **confirmed exactly** — but four framing
facts, all newly verified from the paper and the released code, gut the argument.

**Table 4 is genuinely N=1.** [VERIFIED in prose *and* code] Section 4.5:
*"In this setting, **no complementary cues from other views are available**."*
And `evaluation/depth_eval_tools/get_models.py`:

```python
def get_depth_single(model, device, image_path):
    images = load_and_preprocess_images([image_path], mode='max', target_size=518)
    predictions = model(images, need_camera=False, need_point=False)
```

A one-element list. Good — the path is real. But:

**(a) DAv2, not DA3, is the strongest baseline — and it beats Wat3R on both
honest columns.** The first review quoted only the DA3 delta. The full row set:

| Method | FLSea VI | FLSea Stereo | **SQUID** | **Sea-thru** |
|---|---|---|---|---|
| WaterMono (grayed: trains on FLSea VI) | 0.074 | 0.206 | 0.261 | 0.145 |
| **DAv2** | 0.069 | 0.134 | **0.099** | **0.089** |
| MapAnything | 0.086 | 0.146 | 0.104 | 0.104 |
| π³ | 0.081 | 0.148 | 0.234 | 0.113 |
| DA3 | 0.090 | 0.154 | 0.151 | 0.111 |
| VGGT | 0.107 | 0.159 | 0.194 | 0.113 |
| **Wat3R** | **0.061** | **0.120** | 0.107 | 0.090 |

By the authors' own bolding, **DAv2 beats Wat3R on SQUID (0.099 vs 0.107) and
Sea-thru (0.089 vs 0.090)**.

**(b) FLSea-VI is in Wat3R's training data, and the paper does not say so.**
The unlabeled sources are described only as *"around 10,000 raw underwater videos
from public sources"*. But `training/config/wat3r_training.yaml` wires
`FLSEA_VI_DIR` into `RealVideoDataset` [VERIFIED]. Eval sequences *are* properly
held out at scene level (`self.select_scene(('red_sea/coral_table_loop',
'canyons/u_canyon'), opposite=True)`), so this is **not** train-on-test. But the
two FLSea columns are **in-distribution for Wat3R and zero-shot for every
baseline** — and they are exactly where Wat3R's margin lives. The authors gray out
WaterMono for training on FLSea VI while not disclosing their own use of it.

> **So the two genuinely zero-shot columns are SQUID and Sea-thru, and on those a
> plain terrestrial DAv2 wins.** That is close to a direct refutation of the
> "underwater adaptation matters more than architecture" hypothesis, published
> inside the underwater specialist's own paper.

**(c) Wat3R was not trained for N=1.** Verbatim: *"**Although our model is not
trained with single-image supervision**, it achieves the best performance across
four datasets. The cross-view supervision helps separate underwater degradation
from scene geometry. The learned geometric prior then transfers to single-view
input."*

**(d) Table 4 and Table 1 are not commensurable, and this is a trap.** The paper
never states Table 4's alignment; the released code resolves it as **per-image
least-squares scale+shift in depth space** (`--alignment` default `least_square`;
`disp=None` so the disparity branch never fires; `eval_single` called once per
image). Table 1 (multi-view) instead fits **one global scale+shift for the whole
10-view set**. Consequence:

```text
Wat3R Sea-thru:  0.167 MULTI-VIEW (Table 1)   vs   0.090 MONOCULAR (Table 4)
```

Monocular looks ~2x "better" than multi-view **on the same dataset** — an artifact
of per-image vs per-set alignment, not a capability. **Any conclusion of the form
"multi-view buys little" read off these two tables would be an error**, and the
Week-4A protocol must therefore impose one alignment rule on all entrants itself.

## 2.2 MapAnything's N=1 control is sound, and it is not a strawman

**The range identity holds algebraically at N=1, not approximately.** From
`facebook/map-anything-apache` `config.json`:
`"scene_rep_type": "raydirs+depth+pose"`,
`"ray_directions_normalize_to_unit_sphere": true`, `"depth_mode": "exp"`,
`"depth_vmin": 0`. And `mapanything/models/mapanything/model.py`:

```python
output_ray_directions, output_depth_along_ray = output_dense_rep.split([3, 1], dim=-1)
output_pts3d_cam = output_ray_directions * output_depth_along_ray
```

Unit-norm directions × positive depth ⇒ `‖pts3d_cam‖ ≡ depth_along_ray`
**by construction**. Week 3's measured `1.1e-5` was float error. Critically,
`grep` for `num_views == 1` / `single_view` over `model.py` **returns nothing**
and there are no view-count assertions — **N=1 runs the identical tensor code**,
so the identity and the wrapper both carry over unchanged. This is exactly what a
control needs.

**Its N=1 quality is real.** From Wat3R's independent Table 4: MapAnything
**FLSea VI 0.086, FLSea Stereo 0.146, SQUID 0.104, Sea-thru 0.104** — second-best
on SQUID and best δ₁ on Sea-thru among baselines, ahead of DA3 and VGGT.
(How Wat3R ran that baseline is not in their released code — `UNVERIFIED`.)

**One caveat that matters for E3.** MapAnything's own Table 4 disclaims N=1 twice
(*"has not been trained specifically for single-image inputs"*) and its N=1 metric
scale **collapses on ScanNet (rel 27.77, τ 2.9) while being fine on KITTI (9.69)**;
with median alignment ScanNet recovers to 4.95. **Shape is fine; the metric scale
is the fragile part** — precisely the pattern this project's error budget tolerates,
and a direct warning not to trust N=1 metric scale in a new domain.

## 2.3 MetricAnything replaces the confounded MoGe pairing

Because `metricanything_student_pointmap` is a **fine-tune of MoGe-2 ViT-L**
(§1.2), the pair `MoGe-2 → MetricAnything` holds architecture, representation and
backbone constant and varies only training data/objective (20M pairs, 10k camera
models). `MoGe-1 → MoGe-2` varies all three at once. **The clean pairing displaces
the confounded one.**

## 2.4 SurGe splits into an adopted metric and a deferred model

Its problem statement is this project's ("*inaccurate local surface geometry ...
only weakly reflected in common metrics*"), and its metric is exactly
implementable (§8). But **the weights are CC BY-NC 4.0** and the reference
implementation requires **`natten`, which PyPI ships as an sdist only — no wheels
at all** — with every README example on `.cuda()`. **The metric is adopted; the
model is deferred to a conditional.**

## 2.5 The measurement layer changed more than the model layer

`princeton-vl/EvalMDE` (**BSD-3-Clause, no CUDA dependencies**) implements
**RelNormal**, and its paper proves the specific blindness that threatens this
project's E1 protocol: *"affine-aligned metrics are completely insensitive to
geometric distortions from affine transforms."* This is the single highest
information-per-unit-work change available, and it costs no model integration at
all.


---

# 3. Re-audit of two protocol claims from the first review

## 3.1 Cai & Metzler (arXiv 2507.02148) — conclusion survives, justification did not

**What the first review claimed.** That the table is "unequivocally raw E3, no
alignment", established by searching the full text for `median`, `affine`,
`align`, `cap`, `crop` and finding nothing.

**Why that justification was inadequate.** Absence of keywords is not evidence of
absence of a procedure, especially when **the code was never released** (verified:
all 27 public repos of the first author enumerated, nothing underwater). A paper
can median-align without using the word "median".

**What the paper actually says — the complete set of relevant statements**
[VERIFIED, arXiv HTML v2]:

> "All predictions are rescaled to match the dataset-specific depth units."
> — Section 3.5 (Evaluation Datasets)

> "Metrics are computed only on valid (non-zero) ground-truth pixels and follow
> the dataset-specific evaluation protocols."
> — Section 4.2 (Metrics)

Metric definitions given:
`AbsRel = (1/|T|) Σ_{i∈T} |d_i − d̂_i| / d_i`;
`δ₁ = %{ max(d_i/d̂_i, d̂_i/d_i) < 1.25 }`.

**No mechanism for the rescaling is described anywhere.** The phrase "follow the
dataset-specific evaluation protocols" is an unaudited deferral. So the paper is
**underspecified**, and the first review's confidence was unearned.

**The finding is nonetheless recoverable, from internal evidence rather than
keywords.** The reported scores include:

```text
ZoeDepth       AbsRel 1.5907 / 1.3335 / 1.3214
Metric3D V2-S  AbsRel 1.5331 / 0.8130 / 1.3059
Depth Pro      AbsRel 0.9858 / 0.3888 / 3.2185
```

**Per-image median scaling forces the median prediction/GT ratio to 1, which
bounds AbsRel far below 1 for any functioning model. AbsRel of 1.59 and 3.22 is
therefore near-proof that no per-image alignment of any kind was applied.**
That is a much stronger argument than the keyword search, and it is the one to
cite.

**Corrected classification.**

```text
E3 (raw metric)  - high confidence, from the AbsRel>1 argument
NOT E1           - certain; no per-image alignment can be present
"rescaled to ... depth units"  ambiguous between a pure UNIT conversion
                 (m vs mm) and a DATASET-GLOBAL constant. Both are E3-class;
                 neither is per-image. The distinction does not change the
                 classification, and cannot be resolved without the code.
```

**A second, unchanged finding worth re-stating:** the paper describes **no
conversion between z-depth and Euclidean range** anywhere [VERIFIED — searched].
SQUID's GT is Euclidean range; most benchmarked models emit z-depth. That
systematic mismatch remains unaddressed and inflates SQUID error for every
z-depth model, worst at wide field angles.

**Net effect on the shortlist: none.** UniDepth V2's win remains E3 evidence and
not E1 evidence. But the reasoning is now defensible.

## 3.2 WideDepth (arXiv 2605.24074, ICRA 2026) — MATERIAL CORRECTION

This one **does** change a recommendation.

**What the first review claimed:** that WideDepth measured Depth Pro as "by far
the most FOV-robust model" (+9.0% AbsRel from 120°→195°) against DA V2 (+166%)
and UniK3D (+97%), and used this to justify a conditional trigger promoting Depth
Pro on wide-FOV grounds.

**What the paper actually contains** [VERIFIED, arXiv HTML v1]:

- **The evaluated set is narrower than implied:** *Depth Anything V2-Large,
  PatchFusion, ZoeDepth, Depth Pro, UniK3D-Large.* **UniDepth, Metric3D and MoGe
  are NOT evaluated.** The first review's framing suggested a broad comparison.
- **Table III caption, verbatim:** *"Percentage change in metrics for FOV 195
  compared to FOV 120. Green indicates improved results with a wider angle, while
  red - decline in performance at a wider angle."* Values are **relative
  percentage change, not absolute error**.
- **CONFIRMED:** Depth Anything V2 **+166%** AbsRel; Depth Pro **+9.0%** AbsRel.
- **NOT CONFIRMED:** the UniK3D **+97%** figure. UniK3D-Large is in the table, but
  I did not see its AbsRel cell in the fetched content. Treat as
  `number_unverified`.

**Three caveats the first review missed, and together they gut the trigger:**

1. **The inputs are equirectangular projections, not native frames.** Verbatim:
   *"All models received input data processed as described in Sec. III, including
   **equirectangular projection**, cropping of empty areas, and a 90-degree
   counter-clockwise rotation."* Every model was fed ERP imagery. Feeding ERP to a
   perspective-trained network is itself a large domain shift. This is a
   *different* experiment from the project's P0/P1/P2 question (native GoPro frame
   vs supplied-K vs undistorted-and-cropped).
2. **UniK3D was deliberately handicapped.** It *"operated in camera-free mode
   without intrinsics"* — its camera-conditioning, the entire mechanism that makes
   it an any-camera model, was switched off. So "the any-camera model degraded
   more than Depth Pro" is **not a fair test of any-camera modelling**, and the
   first review's inference — that camera-*conditionable* beats camera-*general* —
   does not follow from this table.
3. **The FOV range is 120°→195°, entirely above this project's 105.383°.** The
   result is an extrapolation *below* the measured range, in a regime where all
   these models are far closer to their training distribution. Whether Depth Pro's
   advantage exists at 105° is simply not measured.

Whether the other models received focal length or calibration **is not stated**
in the fetched text — a further gap.

**Corrected status.** WideDepth is a real, useful benchmark (101 scenes, 5K
stereo pairs, LiDAR-derived millimetre GT, paired pinhole/fisheye) and its
headline Depth Pro / DA V2 contrast is confirmed. But it **cannot carry a
conditional trigger at 105° FOV**, and it does **not** establish that
camera-conditioning beats camera-general modelling.

**Action:** downgrade the Depth Pro FOV trigger from "activate on wide-FOV
degradation" to "consult only if the project's own measured radial-position error
(M-R below) is large **and** a research-only licence is acceptable for a
diagnostic". Depth Pro remains research-only and revocable, so it could never
ship regardless.


---

# 4. Frontier omission sweep (through 2026-09-05)

## 4.1 The September 2026 survey as a coverage cross-check

*"Monocular Depth Estimation from a Single Image: Progress and Opportunities"*,
arXiv **2609.01172**, accepted to **Computational Visual Media Journal**, posted
**2026-09-01** [PAPER VERIFIED].

The models it names as current state of the art, by category:

```text
relative/affine   Depth Anything V3 (DAv3), VGGT
metric            FoundationGeo, Metric3D V2, DepthPro, UniDepthV2, ZeroDepth
point-map         MoGe-2
generative        Diffusion-E2E, GenPercept, GeoWizard
video             DepthCrafter, ChronoDepth, Depth Any Video, Video Depth
                  Anything, FlashDepth, DyFN
panoramic/any-cam UniK3D, Depth Any Camera, PanDA, Depth Any Panoramas, DA2
```

**Two useful negative results.**

1. **The survey names nothing this review has not already considered.** Every
   model it lists is either already in the candidate set, already in the
   conditional list, or already rejected with a reason. The only names not
   previously catalogued — **ZeroDepth**, **PanDA**, **Depth Any Panoramas**,
   **FlashDepth** — are respectively a 2023 metric model superseded by
   UniDepth/Metric3D, and three panoramic/video models outside the single-image
   perspective scope.
2. **The survey's own coverage is narrower than this review's.** It does not
   mention **MoGe-3, MetricAnything, SurGe, UniDAC, MapAnything, π³, or Lotus-2**.
   So it cannot be used to argue an omission, only to confirm one is unlikely in
   the mainstream.

It also states, in Section 4.1, that OOD conditions *"such as underwater
environments, adverse weather"* are a challenge — but provides **no dedicated
methods or results** for them, and **does not discuss metric limitations or
surface-geometry evaluation** at all, reporting only AbsRel and δ₁ under a uniform
*"affine-invariant alignment procedure"*. That is itself a data point: the
mainstream survey literature has not caught up with either of this project's two
central concerns.

## 4.2 Independent arXiv sweep, 2026-06 → 2026-09-05

Queried across point-map/normal, metric/camera, and monocular-geometry axes.
Ranked by whether they test one of the eight mechanisms named in the brief.

**Nothing found displaces a candidate or names a new hypothesis.** The most
relevant items, and why each stops short:

| Work | ID | Mechanism | Why it does not enter |
|---|---|---|---|
| **Toward A Better Understanding of Monocular Depth Evaluation** | 2510.19814 v3 | **(1) local surface geometry** | **Not a model — a METRIC contribution, and it is adopted.** See §8 |
| SCOPE: Scale-Consistent One-Pass Estimation of 3D Geometry | 2606.21300 | scale consistency | SIGGRAPH 2026; scale consistency across a *scene/sequence*, not single-image local shape |
| DrivingDepth: Sparse-Prompted Pixel-wise Scale Correction | 2606.31488 | pixel-wise scale | **Consumes sparse depth prompts.** Useful only as corroboration that pixel-wise scale correction is an active idea — see the FoundationGeo Stage-II concern |
| DAPM: UAV Monocular Depth from Any Height, Pitch, Roll and FOV | 2607.21438 | (3) explicit FOV conditioning | UAV/aerial domain; conditioning on flight geometry, not a general camera model |
| Breaking the Horizontal Prior (roll-robust monocular depth) | 2608.00678 | orientation bias | Relevant to the portrait clip, but a training-side fix with no released general model that displaces anything |
| From Perspective to Fisheye Depth Estimation | 2608.27860 | (3) wide-FOV | Fisheye + open-vocab segmentation; no evidence it beats supplying a known FOV |
| OmniDS: Omnidirectional Depth from Fisheye | 2607.03038 | (3) wide-FOV | Omnidirectional/dual-fisheye rig, not a single wide-FOV frame |
| GIFT: Geometry-Invariant Fine-Tuning for Non-Lambertian | 2608.02068 | (8) hard surfaces | Non-Lambertian/specular; a fine-tuning recipe, not a released general model |
| Fin3R: Fine-tuning Feed-forward 3D Reconstruction via Monocular Distillation | 2511.22429 | (6) adaptation | NeurIPS 2025; adaptation *recipe*, belongs to the Week-4.5 conditional, not a bakeoff slot |
| X-Lens: Real-Time Metric Depth with Heterogeneous Cameras | 2607.12993 | (2)(3) | Multi-camera rig |
| DepthART / ZipDepth | 2607.17099 / 2607.08771 | efficiency | Smaller models, same hypotheses |

**Mechanisms from the brief with NO new qualifying entry found:**
(5) reliable uncertainty under domain shift — still nothing;
(6) underwater foundation-model adaptation with released modern checkpoints —
still only Wat3R;
(7) deterministic single-image inference-time refinement — still only
ReDepth Anything (arXiv 2512.17908, CVPR 2026 Findings), which mutates weights
per sample and so forfeits determinism-by-construction.

**Conclusion:** the candidate landscape is stable. The delta to the first review
comes from the four models it *missed or misjudged* (MetricAnything, SurGe,
MoGe-3 status, FoundationGeo Stage-II), not from anything released since.


---

# 5. FoundationGeo Stage-II: the mechanism, settled from source

The brief asked whether Stage-II improves E3 metric accuracy by introducing
spatial deformation that hurts E1 local geometry. The published ablation could not
be verified (the audit agent was killed by a session rate limit). **But the
mechanism itself is settled from the released source**, and that is what decides
whether F3 keeps its slot.

From `foundationgeo/model/v1.py` [CODE VERIFIED, fetched from
`raw.githubusercontent.com/mx-liu6/FoundationGeo/main/`]:

**1. The scale field is a genuine per-pixel channel of the same DPT-style head:**
```python
dim_out=[3, 1, 1, 2],   # pointmap, mask, scalefield, delta
```
One channel for `scalefield`, two for the ray `delta`.

**2. It is predicted in log space, bilinearly upsampled, and applied
element-wise:**
```python
logS = F.interpolate(logS, (original_height, original_width), mode='bilinear', ...)
scalefield = torch.exp(logS.permute(0, 2, 3, 1).contiguous())
...
points_metric = points_rel * scalefield
```
**No smoothness prior, TV regulariser or low-rank parameterisation appears in the
inference path.** `gaussian_blur_2d` is imported at module level, but alongside
mask utilities (`dilate_with_mask`); it is not visibly applied to `logS`
[NOT VERIFIED either way — I did not trace every call site].

**3. The ray-direction correction IS explicitly bounded:**
```python
r_prime = apply_delta_to_ray(r, delta1, delta2, delta_max_rad=0.0523598)  # 3 deg
```
`0.0523598 rad = 3.0°` hard cap. That is a real constraint — the correction cannot
arbitrarily re-invent the camera model. But 3° of ray deviation at the edge of a
~105° field is not negligible for range-dependent physics.

## 5.1 What this settles, and what it does not

```text
SETTLED   S is a genuinely SPATIALLY VARYING multiplicative field, free at the
          head's output resolution and bilinearly interpolated to full size.
          It is NOT a global factor in disguise, and it is NOT low-rank.
          => F3's variable (V4b) is real. The contingency in section 7 is
             RESOLVED IN FAVOUR OF KEEPING F3.

SETTLED   The ray correction is capped at 3 degrees.

NOT SETTLED  Whether Stage-II's spatial freedom actually HURTS E1 on this
          footage. No Stage-I-vs-Stage-II ablation on a shape/scale-invariant
          metric was verified. This is precisely why it must be MEASURED
          (matrix stage S3, ablation A2) rather than assumed either way.
```

**The experiment this licenses.** Because DA3's metric conversion is provably a
*global* factor (`metric = focal · net / 300`) and FoundationGeo's is provably a
*per-pixel field*, running both and scoring **E1** gives a direct read on the
brief's section-8 question: *is a spatially varying metric correction harmless?*
Neither model alone answers it; the contrast does.


---

# 6. Redundancy matrix

## 6.1 The scientific variables, and which comparison identifies each

Rather than 45 pairwise cells of mostly "essentially model quality", the useful
structure is: **what variables exist, and what is the cheapest comparison that
identifies each?**

```text
V1  VIEW COUNT           N>1 -> N=1, architecture/ckpt/wrapper held fixed
V2  REPRESENTATION       point map  vs  scalar depth  vs  disparity
V3  AMBIGUITY CLASS      scale-only-depth / affine-depth / affine-disparity
V4  METRIC MECHANISM     none / global canonical factor / pixel-wise scale field
V5  CAMERA-DIVERSE TRAINING   does 10k-camera metric pretraining help an OOD camera
V6  LOCAL-SURFACE OBJECTIVE   does training for surface geometry fix surface geometry
V7  UNDERWATER ADAPTATION     does water-specific training beat architecture
V8  FINE-DETAIL REFINEMENT    does explicit 3D refinement improve local geometry
V9  INTRINSICS CONDITIONING   does supplying known K/FOV help at 105 deg
```

| Variable | Identified by | Cost | Verdict |
|---|---|---|---|
| **V1** | **MapAnything N>1 (Week 3, done) → MapAnything N=1** | ~zero: same ckpt, same wrapper, no view-count special-casing in `model.py` | **Unique. Nothing else identifies it.** This is the literal Week-4 question and PLAN.md's gate |
| **V2** | MoGe-2 (point map) vs DA3 Mono (scalar depth) vs DA V2 (disparity) | already in set | Identified across the primary families; no dedicated slot needed |
| **V3** | **DA V2** vs everything else | ~zero: 24.8M params, first-party MPS | **Unique.** The only Class-4 instrument, and — newly — the actual N=1 underwater incumbent |
| **V4a** *global* factor | DA3 Mono → DA3 Metric (`metric = focal·net/300`, provably global) | +1 ckpt, same wrapper | **Control arm** for V4 |
| **V4b** *pixel-wise* field | **FoundationGeo Base-1.1 → FoundationGeo-1.1** (`P̃ = S ⊙ P̂`) | +1 family | **Treatment arm** for V4. The dangerous mechanism |
| **V5** | **MoGe-2 ViT-L → MetricAnything Student-PointMap** (a *fine-tune of that exact checkpoint*) | +1 ckpt, same wrapper | **Unique and clean.** Displaces MoGe-1→MoGe-2 |
| **V6** | SurGe vs any point-map model | +1 family, **rented CUDA + NC weights** | **Deferred** — the *metric* is imported instead (§8) |
| **V7** | **Wat3R N=1** vs DA V2 / DA3 | low: VGGT family, MPS-proven in Week 3, Apache-2.0 | Retained as a **control**, not a primary — see 7.2 |
| **V8** | MoGe-2 → MoGe-3 ViT-L | +1 family, CUDA-only (pending) | **Conditional** |
| **V9** | MoGe-2 with/without `--fov_x`; DA3 Metric with measured vs predicted focal | ~zero: same model, one flag | **Free.** An ablation, not a model slot |

## 6.2 The redundant clusters, named

**Cluster A — "metric models", the biggest redundancy risk.**
`{UniDepth V2, DA3 Metric, MoGe-2, MetricAnything, FoundationGeo-1.1}` all emit
metric output. Run for E3 alone they are **mutually redundant: the identifiable
variable is model quality.** They stop being redundant only when they span the
*mechanism* axis V4. **Two arms suffice**: one provably-global (DA3 Metric) and
one pixel-wise (FoundationGeo-1.1). MetricAnything earns its place on V5, not on
being metric. **UniDepth V2 is left with no unique variable** — see 7.3.

**Cluster B — MoGe generations.** `MoGe-2 vs MoGe-3` identifies V8 only. If V8 is
not the deciding axis, they are redundant. **MoGe-3 → conditional.**
`MoGe-1 vs MoGe-2` is strictly dominated by `MoGe-2 vs MetricAnything`. **Dropped.**

**Cluster C — DA V2 Small vs Large.** Identifies capacity only. **But** Wat3R's
Table 4 benchmarks "DAv2" without a stated variant, so **Large is needed for
comparability with the published number and Small for deployability**. Both are
cheap; run both, and the pair also answers the brief's explicit "does capacity
change the conclusion" question at near-zero cost.

**Cluster D — underwater specialists.** `{Wat3R, WaterMono, UDepth, CD-UDepth,
UMono}` all test V7. Wat3R strictly dominates on licence, release and evidence.
**One arm only.**

## 6.3 The displacement: UniDepth V2 loses its slot

The first review's two justifications both fail on re-audit:

1. *"Only model with native radial range."* **False as a differentiator.**
   MapAnything (`depth_along_ray`, and it is the control), MoGe/MetricAnything
   (`‖points‖`), and FoundationGeo (`d = ‖p‖₂`) all supply native range. Native
   range is a property of the point-map family.
2. *"Won the underwater benchmark."* **E3-only evidence** (§3.1), on the axis
   Week 3 proved is exactly absorbable. And the re-audit found **no published
   aligned-shape underwater evaluation of UniDepth V2 at all.**

Against that: code **CC BY-NC 4.0**, checkpoint declaring **no licence**, and
Linux+CUDA 11.8 documented. Its one surviving distinctive feature is **intrinsics
conditioning with an explicit `Fisheye624` class** — which is variable V9, and V9
is obtainable for free from MoGe's `--fov_x` and DA3 Metric's focal term.

> **UniDepth V2 is displaced to a conditional challenger.** Trigger: E3 is
> promoted to a primary criterion (cross-clip coefficient sharing, week-6
> artificial-light geometry), **or** the V9 ablation shows intrinsics conditioning
> materially helps and a first-class camera class is wanted.

## 6.4 What each retained entry uniquely buys

```text
MapAnything N=1        V1 - the only measurement of the cost of losing multi-view.
                       Zero marginal integration. PLAN.md's Week-4 gate needs it.
DA V2 Small + Large    V3 - the only Class-4 instrument; AND the incumbent that
                       currently beats the underwater specialist on both zero-shot
                       columns; AND the only first-party-MPS model.
MoGe-2 -> MetricAnything   V5 - clean camera-diverse-metric-training contrast on
                       an identical architecture (fine-tune of that checkpoint).
                       Also supplies the point-map arm of V2.
DA3 Mono (+ Metric)    V2/V3 - the direct-depth relative arm, and the only
                       Class-2 candidate; Metric is the GLOBAL arm of V4.
FoundationGeo Base->1.1    V4b - the pixel-wise-scale-field arm. Tests the
                       specific mechanism the brief flags as dangerous.
Wat3R N=1              V7 - the only underwater arm. Expected to lose; see 8.
```


---

# 7. The final pre-C2 Week-4A execution set

**Three primary families + three cheap controls. Nine checkpoints, six wrappers.**
Four of six run locally on the M4; one needs rented CUDA.

## Controls (cheap, high information, run first)

### C1 — MapAnything at N=1 · `facebook/map-anything-apache` · Apache-2.0 / Apache-2.0
**Variable: V1, view count.** The only measurement of what losing multi-view
costs, and PLAN.md's Week-4 gate requires exactly this comparison.
Marginal cost ~zero: same checkpoint and wrapper as Week 3.
`‖pts3d_cam‖ ≡ depth_along_ray` holds **algebraically** (unit-norm ray directions
× `exp` depth), and `model.py` contains **no view-count special-casing**, so the
N=1 path is the identical tensor code. Runs on MPS, bitwise reproducible.
**Not a strawman:** third-party N=1 underwater (Wat3R Table 4) gives it
SQUID 0.104 / Sea-thru 0.104 — ahead of DA3 and VGGT.

### C2 — Depth Anything V2 · `...-V2-Large` (CC BY-NC) **and** `...-V2-Small` (Apache-2.0)
**Variables: V3 (Class-4 instrument) + the true N=1 underwater incumbent + capacity.**
The first review had this as a floor. It is not a floor — **by Wat3R's own
Table 4 bolding, DAv2 is the best single-image model on both genuinely zero-shot
underwater columns** (SQUID 0.099, Sea-thru Rel 0.089), beating Wat3R, DA3,
MapAnything, π³ and VGGT. Large is needed for comparability with that published
row; Small is the deployable, first-party-MPS variant. Running both answers the
brief's capacity question for near-zero cost.

### C3 — Wat3R at N=1 · `lsxi77777/Wat3R` · Apache-2.0 / Apache-2.0
**Variable: V7, underwater adaptation.** Demoted from primary to control, because
the published evidence now points against the hypothesis it tests (§2.1). Cheap:
VGGT family, MPS-proven bitwise-reproducible in Week 3, permissive licence.
**Expected to lose**, and that is a legitimate, informative outcome.

## Primary families

### F1 — MoGe-2 ViT-L → MetricAnything Student-PointMap *(paired)*
```text
Ruicheng/moge-2-vitl                      MIT / MIT
yjh001/metricanything_student_pointmap    Apache-2.0 / Apache-2.0
```
**Variable: V5, camera-diverse metric pretraining, architecture held constant.**
The model card states it plainly: *"finetuned from MoGe-2 ViT-l"*. Same
architecture, same representation, same backbone — only training data and
objective differ (20M pairs, 10,000 camera models, Sparse Metric Prompt, whose
stated purpose is to *"decouple spatial reasoning from sensor and camera biases"*
— i.e. exactly the OOD-camera question a GoPro poses). Repo is Apache-2.0 with
350 stars / 25 forks. Supplies the point-map arm of V2 and native range via
`‖points‖` with no K dependence.
**This pairing displaces MoGe-1 → MoGe-2**, which confounds architecture, data and
metric head simultaneously.

### F2 — DA3 Mono → DA3 Metric *(paired)*
```text
depth-anything/DA3MONO-LARGE      Apache-2.0 / Apache-2.0
depth-anything/DA3METRIC-LARGE    Apache-2.0 / Apache-2.0
```
**Variables: V3 (the only Class-2 candidate) + V4a (the *global* metric arm).**
The only widely-used relative foundation model predicting **depth** rather than
disparity. Its metric conversion `metric = focal · net / 300` is **provably a
global multiplicative factor**, which makes it the **control arm** against F3's
pixel-wise field.
**Cost and risk, stated:** requires rented CUDA (no MPS path exists), and by
Wat3R's Table 4 **DA3 is beaten by DA V2 on both zero-shot underwater columns**
(SQUID 0.151 vs 0.099; Sea-thru 0.111 vs 0.089). This is the entry most likely to
be cut after S2/S3 — which is itself worth knowing early.

### F3 — FoundationGeo Base-1.1 → FoundationGeo-1.1 *(paired)*
```text
mxliu-hku/FoundationGeo-Base-1.1   MIT / MIT   (Stage-I, affine point map)
mxliu-hku/FoundationGeo-1.1        MIT / MIT   (Stage-II, metric)
```
**Variable: V4b, the pixel-wise scale field.** Stage-II applies
`P̃ = S ⊙ P̂` with a per-pixel `S` plus a ray-direction correction. **A global
multiplicative range error is exactly absorbable; a spatially varying one is
not** — so this pairing tests the specific mechanism the brief flags as dangerous,
scored on **E1, not E3**. It also natively decomposes into Euclidean range and a
unit ray (`d = ‖p‖₂`, `r = p/‖p‖₂`).
> **Contingency RESOLVED — F3 stays.** Source inspection (§5) confirms
> `scalefield` is a genuine per-pixel channel: `dim_out=[3,1,1,2] # pointmap,
> mask, scalefield, delta`, computed as `exp(logS)`, bilinearly upsampled, and
> applied as `points_metric = points_rel * scalefield`, with **no smoothness
> prior in the inference path**. It is not a global factor in disguise, so V4b is
> a real variable. The ray correction is separately hard-capped at **3°**.

## 7.1 Displaced, with what replaced it

| Displaced | By | Reason |
|---|---|---|
| **UniDepth V2 ViT-L** (was primary) | nothing — slot returned | Both justifications failed on re-audit (§6.3): native range is not unique to it, and **no aligned-shape underwater evidence for it exists anywhere** (verified across 21 underwater papers + 590 citing papers; exactly one underwater paper cites it, and that one is raw-metric). Code CC BY-NC; checkpoint declares **no licence** |
| **MoGe-1 → MoGe-2** pairing | **MoGe-2 → MetricAnything** | Strictly cleaner: a fine-tune of the exact checkpoint vs a different training run |
| **Wat3R** (was primary) | demoted to control | Its N=1 lead is confined to FLSea, which is **in its own undisclosed training pool**; on the zero-shot columns DAv2 wins |
| **Depth Pro** conditional trigger | withdrawn | WideDepth's protocol does not support it (§1.1) |
| **SurGe** (as a model) | its **metric**, imported | CC BY-NC weights + `natten` sdist-only + CUDA-only examples. The metric is the valuable part and it is free |

## 7.2 Why this is non-redundant

Every entry owns at least one variable no other entry identifies:

```text
C1  V1  view count            unique by construction
C2  V3  Class-4 + incumbent   the only disparity-native entry; the model to beat
C3  V7  underwater            the only underwater arm
F1  V5  camera-diverse metric the only architecture-controlled metric pairing
F2  V4a global metric factor  the only Class-2 candidate; the global control arm
F3  V4b pixel-wise scale      the only spatially-varying metric mechanism
```

Free ablations riding on the above, costing no extra wrapper: **V9** (MoGe-2
`--fov_x` on/off; DA3 Metric measured-vs-predicted focal) and **capacity**
(DA V2 Small vs Large).


---

# 8. Expanded local-geometry measurements

## 8.1 Why the conventional metrics are not merely insufficient — they are blind in the exact way that matters

**"Toward A Better Understanding of Monocular Depth Evaluation"**, arXiv
**2510.19814** (v1 2025-10-22, v3 2025-11-17), Princeton VL [PAPER VERIFIED].
This paper is the strongest evidence in either review that AbsRel/δ₁ cannot
support Week-4A's primary criterion. Two findings, quoted:

> "all widely used metrics have very poor sensitivity to curvature perturbation
> (e.g., making a smooth surface bumpy)"

> "affine-aligned metrics are completely insensitive to geometric distortions
> from affine transforms"

The second is the sharper one for this project. **The E1 protocol — fit the
model's legal ambiguity, then score — is by construction blind to the very
deformation the ambiguity spans.** That is correct and intended. But it means
E1-under-AbsRel cannot distinguish "correct shape" from "shape distorted along
the ambiguity direction, then fitted away". The remedy is not to abandon the
alignment; it is to add a metric that is *invariant to the alignment group but
sensitive to curvature*.

They evaluate ten methods — DepthAnything, DA V2, GeoWizard, Marigold, MiDaS,
DepthPro, Metric3D V2, **MoGe-2**, **UniDepthV2**, ZoeDepth — across 9 benchmarks.

**Their metric, RelNormal, is exactly that construction:**

```text
RelNormal = (1/pi) * (1/|C|) * SUM_{(p,q) in C} | angle(n_hat_p, n_hat_q) - angle(n_p, n_q) |
```

where `n_p`, `n_q` are surface normals of *patches* in the GT depth and
`n_hat_p`, `n_hat_q` the corresponding predicted normals, and `C` is a set of
patch **pairs**. Because it compares *relative* angles between pairs of patches,
it is invariant to a global rotation of the normal field and to the global
alignment, while remaining sensitive to local curvature error. Composited with
existing metrics (their SAWA-H) it reaches **0.97 cosine similarity with human
judgement, against 0.88 without RelNormal**.

**Code is released and it is usable here:** `github.com/princeton-vl/EvalMDE`,
**BSD-3-Clause**, 17 stars, created 2025-10-17, last pushed 2025-11-17
[CODE + LICENSE VERIFIED via GitHub API]. Dependencies are `numpy`,
`opencv-python`, `open3d`, `pyrender`, `imageio`, `timm`, `evo`, `plyfile` —
**no CUDA-only libraries**, so it runs on Apple Silicon [VERIFIED from `setup.py`].
`open3d`/`pyrender` on arm64 are the only install risk and are not blockers.

> **Recommendation: adopt RelNormal via EvalMDE regardless of which models are
> run.** It is the single cheapest, highest-leverage change to Week 4A, it is
> licensed permissively, and it directly measures the failure mode the section-2.2
> error budget punishes.

## 8.2 The measurement set

Conventional AbsRel/δ₁ are **retained** (for continuity with the literature and
with the first review's tables) but **demoted to secondary**. The following are
primary. All are computed *after* fitting the model's legal ambiguity in its
native representation, and all are reported **stratified**, never as a single
scalar.

```text
LG-1  PER-RANGE-BIN RELATIVE RANGE ERROR
      median |r_hat - r| / r within bins, e.g. [0-1, 1-2, 2-3, 3-5, 5-8, 8-12, 12+] m
      Read directly against the Week-3 budget: 31%@1m, 12%@3m, 8.5%@8m clear;
      9.4%@3m, 6.1%@8m coastal; 1.0%@8m, 0.3%@12m turbid.
      This is THE acceptance test. A single AbsRel cannot express it.

LG-2  NEAR/FAR SYSTEMATIC BIAS
      fit log(r_hat) = a + b*log(r) over valid pixels; report b.
      b == 1 means no range-dependent distortion; b < 1 is far-field compression
      (the "scale collapse" direction reported for MoGe-2/DA3/Metric3D v2).
      Report b with a confidence interval, per clip and pooled.
      Rationale: a pure global scale moves `a` only and is FREE; `b != 1` is a
      nonlinear range deformation and is NOT absorbable.

LG-3  RANGE-GRADIENT ERROR
      relative error of the spatial gradient of range, |grad r_hat - grad r| / |grad r|,
      on valid, non-boundary pixels. Directly penalises the "smooth surface made
      bumpy" failure that 2510.19814 shows AbsRel misses.

LG-4  POINT-MAP NORMAL ANGULAR ERROR  (two variants, both reported)
      (a) ABSOLUTE: median angular error between predicted and GT normals induced
          from the point map.
      (b) RELATIVE: RelNormal, per 2510.19814 above - invariant to the alignment
          group, sensitive to curvature. PRIMARY of the two.
      SurGe (arXiv 2605.31577) proposes a closely related point-map normal metric;
      where its formulation differs, report both and say which is which.

LG-5  BOUNDARY LOCALISATION ERROR
      Chamfer distance between Canny edges of predicted and GT range maps
      (the C_PDBE construction from DAGE, CVPR 2026). Also usable frame-to-frame
      with no GT at all, which is why it doubles as the temporal edge-jitter
      measure.

LG-6  FOREGROUND/BACKGROUND ORDERING VIOLATIONS
      over sampled pixel pairs (p,q) with |r_p - r_q| above a margin, the fraction
      whose predicted order is inverted. Ordinal, so it is invariant to ANY
      monotonic range transform - which makes it the one metric immune to every
      ambiguity class in section 17. Report at several margins.

LG-7  LOCAL PLANARITY / CURVATURE ERROR
      on reference-supported planar patches, RMS residual to a fitted plane, and
      the curvature error where support permits. Underwater the natural supports
      are sand flats, wreck plating and the chart board.

LG-8  RADIAL-IMAGE-POSITION ERROR PROFILE
      LG-1 recomputed as a function of normalised radius from the principal point.
      This is the specific diagnostic for wide-FOV / flat-port / z-depth-vs-range
      confusion: all three predict error growing toward the frame edge, and this
      is the measurement that would trigger the camera-model challengers.

LG-9  THIN-STRUCTURE RETENTION
      on hand-labelled thin supports (coral branches, rope, fins), the fraction
      recovered as distinct from background at a range margin, plus false-positive
      structure introduced where GT is smooth - the latter catches the
      "pseudo-texture" hazard of converting backscatter speckle into geometry.
```

## 8.3 The decomposition that must accompany every one of them

Per the first review's section 17.2 and 20.5(3), and reinforced by DyFN: every
measurement above is reported **twice** — once with the fitted ambiguity
parameters exposed, once on the residual after fitting.

```text
part A   the fitted ambiguity itself (scale; and shift where legal)
         -> a pure global-scale response is BENIGN (Week 3: absorbed to 4.5e-13)
part B   the residual after the legal fit, per range bin
         -> this is the real damage, read against the section-2.2 budget
```

Reporting only part B would discard the distinction the whole project rests on;
reporting only the raw change would condemn models for a free scale wobble.

## 8.4 The explicit downstream justification

A small global scale error is absorbed exactly by refitting `beta` and `B_inf`.
A **spatially varying** local range error is not, and because `beta` differs per
channel, it becomes a **spatially varying colour/radiance error** after physical
restoration. LG-1 through LG-9 exist to measure that specific quantity; AbsRel
exists to be comparable with the literature. **They are not interchangeable, and
2510.19814 is the citation that establishes it.**


---

# 9. The minimum experiment matrix to reduce to 2–3 finalists

Seven stages. Stages 0–2 are gates: a candidate failing them produces numbers that
cannot be interpreted, so no accuracy stage runs until they pass.

```text
S0  SEMANTICS + WRAPPER GATE                                    all entrants
    - verify the range conversion NUMERICALLY per model, the way Week 3 verified
      MapAnything (which now turns out to hold ALGEBRAICALLY, not just to 1.1e-5)
    - audit preprocessing for crop/letterbox/resize FOV loss (Week 3 measured the
      VGGT family silently discarding ~44% of vertical FOV on portrait)
    - confirm on VAROS (dense, hole-free) + Sea-thru (linear PNG, metres, 0=NaN)
    - MetricAnything ONLY: confirm the weights actually differ from stock MoGe-2
      (tensor-diff, per the Water-VGGT precedent). 0 downloads = no external check
    FAIL => candidate is out. This stage is cheap and eliminates fastest.

S1  DETERMINISM + NOISE FLOOR                                   all entrants
    - bitwise repeat-run reproducibility, MPS fp32 fixed seed where local;
      rented-CUDA entrants measured the same way on that machine
    - any entrant that cannot meet it needs a measured noise floor before its
      deltas are readable at all

S2  AMBIGUITY CLASS, MEASURED                                   all entrants
    - fit scale-only vs scale+shift IN THE NATIVE REPRESENTATION; test whether the
      shift is significantly non-zero, and whether it DRIFTS frame-to-frame
    - settles DA3 Mono's Class-2-vs-3 status and MoGe-1's shift-resolution
    - ONE alignment rule is then frozen for all subsequent stages. This is
      mandatory: Wat3R's own Table 1 vs Table 4 discrepancy (0.167 vs 0.090 on the
      same dataset) is caused by exactly this and would otherwise be inherited.

S3  LOCAL GEOMETRY (E1) - THE PRIMARY AXIS                      all entrants
    - LG-1..LG-9 from section 8, reported per range bin against the Week-3 budget
    - RelNormal (EvalMDE, BSD-3) and SurGe's MAE_normal are the discriminators
      that AbsRel provably cannot supply
    - reference: Week 3's persisted range product, with section-3.3 epistemics -
      agreement is consistency, not correctness

S4  APPEARANCE INVARIANCE (M6)                                  all entrants
    - physically-generated, geometry-preserving perturbations + a CUE-CONFLICT
      condition; response decomposed into ambiguity drift vs post-fit residual
    - if Atlantis++ Bench turns out to render matched geometry under controlled
      turbidity/colour (unverified - see 8), it supplies a second, independent
      instance of this test at no acquisition cost

S5  INDEPENDENT-FRAME STABILITY                                 all entrants
    - DyFN's cheap diagnostic FIRST: one global alignment vs per-frame alignment;
      the gap IS the affine-drift component
    - then OPW (flow-based, no GT poses needed) and edge-jitter Chamfer

S6  RESTORATION IMPACT (PLAN.md's actual gate)                  survivors only
    - run the range-dependent restoration with multi-view range vs each monocular
      range; ask PLAN.md's question: "Does the monocular depth error materially
      change restoration?"
    - MANDATORY visual inspection per Invariant 5, specifically for backscatter
      speckle / marine snow / caustics converted into geometry
    - produce the adequate / degraded / unsafe classification PLAN.md requires
```

## 9.1 What reduces the field, and when

```text
after S0-S1   expect to lose any entrant with a broken wrapper or non-determinism
after S2      expect to lose Class-4 entrants for DEPLOYMENT (they remain as
              instruments); DA V2's fate is decided here
after S3      the primary cut. 6 entrants -> 3-4
after S4-S5   3-4 -> 2-3 frozen finalists
S6            does not cut; it produces the error budget PLAN.md's gate requires
```

## 9.2 The three ablations that are free and must not be skipped

```text
A1  V9 intrinsics conditioning   MoGe-2 with and without --fov_x;
                                 DA3 Metric with measured vs predicted focal.
                                 Same model, one flag. Answers the P0/P1 question
                                 without buying an any-camera model.
A2  V4 metric mechanism          DA3 Mono vs DA3 Metric (global factor) contrasted
                                 with FoundationGeo Base vs -1.1 (pixel-wise field),
                                 scored on E1 not E3. This is the brief's section-8
                                 question, answered directly.
A3  capacity                     DA V2 Small vs Large. Also required for
                                 comparability with Wat3R's published DAv2 row.
```


---

# 10. Conditional challengers, with measured triggers

```text
────────────────────────────────────────────────────────────────────────────
TRIGGER  RelNormal / MAE_normal show LARGE local-surface error across ALL six
         entrants (i.e. the whole field is bad at the primary axis, not just
         some of it)
ACTIVATE SurGe  (karimknaebel/surge-large)
WHY      It is the only model that TRAINS for this quantity - a point-gradient
         matching loss on depth-normalised 3D finite differences. If everyone
         fails the metric, the question becomes "is this trainable?", and SurGe
         is the only released answer.
COST     rented CUDA + a `natten` source build (sdist-only, no wheels) + CC BY-NC
         weights. Measure first; this is why the metric is imported and the model
         is not.
────────────────────────────────────────────────────────────────────────────
TRIGGER  Thin-structure retention (LG-9) is the deciding axis AND a CUDA machine
         is already rented for F2
ACTIVATE MoGe-3 ViT-L  (Ruicheng/moge-3-vitl, MIT/MIT)
WHY      Direct successor to F1's baseline, same output semantics, same licence,
         explicitly built for fine-grained point-map geometry (V8).
CAVEAT   Its FlexGEMM/Triton scope is UNRESOLVED (§13 item 27) - determine in S0
         whether a no-refinement path exists before budgeting for it.
         ViT-G gets no slot: it tests model scaling, not a new variable.
────────────────────────────────────────────────────────────────────────────
TRIGGER  E3 is promoted to a primary criterion - i.e. week-6 artificial-light
         geometry or cross-clip coefficient sharing actually lands
ACTIVATE UniDepth V2 ViT-L  (lpiccinelli/unidepth-v2-vitl14)
WHY      It remains the best-measured metric model underwater (E3), it natively
         emits `radius` (verified in source), and it accepts a first-class
         `Fisheye624` camera object. Its displacement is conditional on E3
         staying secondary, not on the model being weak.
CAVEAT   Code CC BY-NC 4.0, checkpoint declares NO licence. Research-only.
────────────────────────────────────────────────────────────────────────────
TRIGGER  LG-8 (radial-image-position error profile) shows error growing sharply
         toward the frame edge, AND the A1 intrinsics ablation does not fix it
ACTIVATE UniDAC (girish1511/UniDAC, CVPR 2026, MIT code) - and only then
WHY      Camera-general modelling becomes worth buying only once a camera-model
         error is MEASURED. UniDAC requires GT intrinsics, so this trigger is
         genuinely gated on C2.
NOT      Depth Pro - its WideDepth justification was withdrawn (§1.1), and its
         weights are research-only and revocable.
────────────────────────────────────────────────────────────────────────────
TRIGGER  Zero-shot structure is good but the M6 appearance battery moves geometry
         beyond the section-2.2 budget
ACTIVATE Week-4.5 LoRA/adapter adaptation of DA V2 Small (Apache-2.0) or Wat3R
WHY      The only failure mode adaptation is evidenced to fix. Precedent is
         consistently PEFT-shaped (DARES, EndoDAC, Surgical-DINO, ER-LoRA,
         StereoAdapter's +5.12% on SQUID).
HARD PRECONDITION  Do NOT train against Week-3 MapAnything/COLMAP output before
         C2 - CLAUDE.md forbids imitating the pipeline's own output, and the
         student would inherit MapAnything's 6.6x dynamic scale wander as a target.
────────────────────────────────────────────────────────────────────────────
TRIGGER  Absolute scale is genuinely needed
ACTIVATE Sparse-point rescaling (arXiv 2412.14103, IROS 2025, CC-BY-4.0), feeding
         Week-3 COLMAP/MapAnything sparse points into the monocular prediction
WHY      Deterministic, no GT, published, licensed, and demonstrated underwater
         by SPADE (DA V2 + global alignment: AbsRel 0.081 @<=10 m on FLSea).
         The right answer to "we need scale" is NOT switching to a metric model.
────────────────────────────────────────────────────────────────────────────
```

# 11. Rejected, and why they add no information

| Rejected | Reason |
|---|---|
| **MoGe-1 → MoGe-2 pairing** | Strictly dominated by MoGe-2 → MetricAnything, which is a fine-tune of the exact checkpoint and therefore controls architecture |
| **UniDepth V2** (primary slot) | Both justifications failed: native range is shared with three other entrants; the only underwater evidence is E3-only, and **no aligned-shape underwater evaluation of it exists**. Licence blocks deployment |
| **Depth Pro** | WideDepth trigger withdrawn (ERP inputs, UniK3D handicapped, FOV range above 105°). Research-only, revocable weights |
| **UniK3D** | CC BY-NC-SA (viral) code, undeclared checkpoint licence, and its WideDepth degradation figure is unverified |
| **SurGe** (as a model, now) | Metric imported instead; weights CC BY-NC, `natten` sdist-only, CUDA-only examples |
| **MoGe-3 ViT-G** | Tests model scaling, not a distinct variable |
| **Lotus-2, Marigold, PointDiT, Pixel-Perfect Depth** | The generative hypothesis was answered by its own literature (E2E-FT); determinism cost is real; Lotus-2 is Class-4 and needs ≥40 GB |
| **WaterMono, UDepth, CD-UDepth, UDepthDiff, UMono, Tree-Mamba** | One underwater arm suffices, and Wat3R dominates all of them on licence, release and evidence. CD-UDepth and UDepthDiff are journal-only with no code |
| **Metric3D v2, ZoeDepth** | Intrinsics required / ignored respectively; undeclared checkpoint licence; worst underwater performers |
| **DUSt3R, MASt3R, VGGT, π³, DAGE, Dens3R** | Multi-view by construction or degenerate at N=1; several are CC BY-NC-SA (viral) |
| **Video depth models** (VDA, DepthCrafter, StableDPT, ICDepth …) | Week 4 tests the single-image fallback path by definition |
| **ZeroDepth, PanDA, Depth Any Panoramas, FlashDepth** | Surfaced by the 2026-09 survey; superseded, or panoramic/video, i.e. outside single-image perspective scope |


---

# 12. What still cannot be decided before C2

Unchanged from the first review in substance, sharpened in two places.

```text
CANNOT BE ESTABLISHED PRE-C2
  definitive objective accuracy on this camera
  final absolute range error, and final metric-scale accuracy on this footage
  whether MapAnything or any Week-3 hypothesis is objectively correct
  definitive confidence calibration
  the final adequate / degraded / unsafe envelope
  the final Week-4 winner
```

Two sharpenings from this delta pass:

**(a) The reference-quality ceiling is now quantified by someone else.** Wat3R's
Table 4 vs Table 1 discrepancy (Sea-thru 0.090 "monocular" vs 0.167 "multi-view",
same dataset, same model) shows that **alignment convention alone can move an
underwater depth number by ~2x**. Pre-C2, this project's reference is Week-3
multi-view range under its own conventions. So any pre-C2 monocular-vs-multi-view
gap is a statement about *this project's alignment and reference*, not about
objective accuracy. S2's frozen alignment rule bounds the damage; it does not
remove it.

**(b) Metric scale is now expected to fail, for a named reason.** MapAnything's
own N=1 metric collapses on ScanNet (rel 27.77) while being fine on KITTI, and the
authors attribute it to benchmark quality; FoundationGeo attributes OOD metric
failure to a *"biased implicit focal prior"*; MetricScenes documents far-field
scale collapse across MoGe-2 / DA3 / Metric3D v2. **Pre-C2 there is no way to
distinguish "this model's metric scale is wrong on my camera" from "my reference's
scale is wrong", because both are unanchored.** E3 must therefore be *recorded*
pre-C2 and *judged* post-C2.

## 12.1 What C2 must capture, updated by this pass

Carrying forward the first review's four items (chart at several known distances;
explicitly recorded z-depth-vs-range convention; two water/visibility conditions
with and without dive lights; a matched EIS-off take), this pass adds one:

```text
NEW  Capture at least one scene at a range spanning the FAR end of the working
     envelope (>= 10-15 m where visibility permits), with chart support.
     Rationale: every documented metric failure in this review is a FAR-FIELD
     failure (MetricScenes' scale collapse; the section-2.2 budget tightening to
     1.0% @8m turbid). A C2 that only samples 1-5 m cannot test the failure mode
     the literature predicts.
```


---

# 13. Confidence levels for every load-bearing claim

| # | Claim | Confidence | Primary source |
|---|---|---|---|
| 1 | `metricanything_student_pointmap` is a **fine-tune of MoGe-2 ViT-L** | **Certain** | Model card verbatim: *"finetuned from MoGe-2 ViT-l"* — `huggingface.co/yjh001/metricanything_student_pointmap` + `models/student_pointmap/README.md` |
| 2 | MetricAnything ckpts are Apache-2.0; repo Apache-2.0, 350★/25 forks | **Certain** | HF API licence tag; GitHub API |
| 3 | MetricAnything: ~20M pairs, **10,000 camera models**, ECCV 2026 | **High** | arXiv 2601.22054 abstract |
| 4 | Wat3R Table 4 numbers (Wat3R 0.061 / DA3 0.090 FLSea-VI; 0.090 / 0.111 Sea-thru) | **Certain** | arXiv 2607.08772v1 HTML — **independently confirmed by two separate audits** |
| 5 | **DAv2 beats Wat3R on SQUID (0.099 vs 0.107) and Sea-thru Rel (0.089 vs 0.090)**, by the authors' own bolding | **Certain** | Same table, both audits |
| 6 | Wat3R Table 4 is **genuinely N=1** | **Certain** | Paper: *"no complementary cues from other views are available"*; code `get_depth_single` passes `[image_path]` |
| 7 | Wat3R was **not trained for N=1** (samples 2–12 images) | **Certain** | Paper verbatim: *"our model is not trained with single-image supervision"* |
| 8 | **FLSea-VI is in Wat3R's training pool, undisclosed in the paper**; eval scenes held out at scene level | **High** | `training/config/wat3r_training.yaml` (`FLSEA_VI_DIR`); `real_video_data.py` `select_scene(..., opposite=True)` |
| 9 | Wat3R Table 4 uses **per-image LSQ scale+shift in depth**; Table 1 uses per-set — **the two are not commensurable** | **High** | Resolved from code (`--alignment least_square` default; `disp=None`); paper does not state it for Table 4 |
| 10 | MapAnything `‖pts3d_cam‖ ≡ depth_along_ray` **algebraically**, and N=1 uses the identical code path | **Certain** | `config.json` (`ray_directions_normalize_to_unit_sphere: true`, `depth_mode: exp`) + `model.py`; no view-count special-casing found |
| 11 | MapAnything disclaims N=1 training; its N=1 **metric scale** collapses on ScanNet (rel 27.77) but recovers under alignment (4.95) | **High** | arXiv 2509.13414v3 Tables 3/4 + captions |
| 12 | **No aligned-shape underwater evaluation of UniDepth V2 exists** | **High** (strong negative, not exhaustive) | Full-text grep of 21 underwater papers + Semantic Scholar citation sweep (590 citing papers → exactly one underwater, and it is raw-metric) |
| 13 | UniDepth `radius` = Euclidean camera-centre distance; `depth` = its z-component | **Certain** | `unidepthv2.py` L334-337: `out["radius"] = points.norm(dim=1, keepdim=True)`; `out["depth"] = points[:, -1:]` |
| 14 | UniDepth V2 checkpoint declares **no licence**; repo is CC BY-NC 4.0 | **Certain** | HF API `license: None`; repo LICENSE |
| 15 | Cai & Metzler is **raw metric, no per-image alignment (E3)** | **High** | Two independent greps (`median`/`affine`/`scale and shift` = 0 hits) **plus** the decisive internal argument: reported AbsRel of 1.59 and 3.22 is incompatible with per-image median scaling |
| 16 | WideDepth: DA V2 **+166%**, Depth Pro **+9.0%** AbsRel, 120°→195° | **High** | arXiv 2605.24074 Table III |
| 17 | WideDepth fed **ERP-projected** inputs and ran **UniK3D camera-free without intrinsics**; FOV range is entirely **above** 105° | **High** | Same paper, Sec. III / protocol text |
| 18 | The WideDepth **UniK3D +97%** figure | **UNVERIFIED** | Reported by an agent; I did not see the cell |
| 19 | FoundationGeo's `scalefield` is a **genuinely per-pixel** multiplicative field (1-ch head output, `exp(logS)`, bilinear upsample, element-wise multiply), with **no visible smoothness prior** | **High** | `foundationgeo/model/v1.py` lines 207, 348-359, 496 |
| 20 | FoundationGeo's ray correction is **hard-capped at 3°** | **Certain** | `v1.py`: `delta_max_rad=0.0523598  # 3 deg` |
| 21 | Whether Stage-II's spatial freedom **hurts E1** | **UNKNOWN — must be measured** | Ablation not verified (agent killed by rate limit) |
| 22 | SurGe weights are **CC BY-NC 4.0**, code MIT; `natten` is a hard dep shipped **sdist-only** | **Certain** | README licence section verbatim; `pyproject.toml`; PyPI JSON for natten 0.21.7 |
| 23 | SurGe metric: 4 local normals from cross products of adjacent point-map differences, averaged; `MAE_normal = (1/\|V_N\|) Σ ∠(N̂,N)` | **High** | arXiv 2605.31577 HTML |
| 24 | EvalMDE is **BSD-3-Clause with no CUDA-only deps**; RelNormal formula as given | **Certain** | GitHub API + `setup.py`; arXiv 2510.19814v3 |
| 25 | *"affine-aligned metrics are completely insensitive to geometric distortions from affine transforms"* | **Certain** | arXiv 2510.19814v3, verbatim |
| 26 | No new model family released through 2026-09-05 displaces the set | **Moderate** | arXiv API sweeps + the 2026-09-01 survey (2609.01172) as cross-check; **web search was unavailable all session** (budget exhausted), so indexing gaps are possible |
| 27 | **MoGe-3's FlexGEMM/Triton scope** (whole model vs refinement only) and whether MoGe-1/-2 run on MPS | **UNRESOLVED** | Both audit agents killed before finishing; this gates only a *conditional* challenger and P1's local feasibility, which S0 will settle empirically |
| 28 | Atlantis++ Bench structure (matched geometry under controlled turbidity) | **UNVERIFIED** | Springer-paywalled; **not on arXiv** (verified). An agent fragment mentioned test sets named `Clean_Blue / Turbid_Blue / Clean_Green / Turbid_Green` but died before substantiating it — **treat as a lead, not a finding** |
