# WEEK 4A — POST-ROUND-2 FINAL REPORT

**EPISTEMIC STATUS: PRE-C2.** Everything below is measured against the Week-3
persisted multi-view range product, which is a **PROVISIONAL HYPOTHESIS, not
ground truth**. Every "error" in this document means *disagreement with that
hypothesis*. Agreement is consistency, not correctness — and where an arm and
the reference share an architecture, agreement is partly circular. Disagreement
cannot establish which side is wrong. Raw metric scale cannot be finally judged
here, and the absolute metre thresholds inherited from Week 3 remain provisional.

**No objective final Week-4 winner is declared.** §5 names a pre-C2 finalist set
and states, for each member, the exact C2 measurement that could remove it.

Scope: the six frozen clips — `wreck_07`, `wreck_05`, `cenote_01`,
`swimthrough_02`, `wreck_01`, `wreck_03` — 48 frames each, 1280-px long side,
**288 frames per arm**, the exact Round-1 frames, no resampling. Week-2 stress
footage is secondary and never enters the primary ranking.

---

## 1. Correctness repairs (§26.1)

Round 2 had two jobs. This one turned out to be the larger.

### Q1 — What changed after correcting DA3 from ray-range to native z-depth?

DA3 defines `P = t + D(u,v)·R·K^-1 p`. For `p = [u, v, 1]^T` the camera-frame
vector `K^-1 p` has z-component exactly 1, so `D` is **projective z-depth**, not
Euclidean ray range. That is a statement from the model's own definition, not a
residual test, and it settles a question Round 1 had recorded as "unresolved".
Round 1's residual test had in fact answered it **wrongly on three of six clips**
and returned INDISTINGUISHABLE on a fourth (`R2_PARTS_ABC_CORRECTNESS.md` §A,
"How badly the Round-1 residual test misled").

The repair chain is `ρ(x) = ‖K_eval^-1 p(x)‖`, `z_ref = r_ref / ρ`, fit
`z_ref = s·z_DA3 + t` at the frozen clip-level scope, then `r̂ = (s·z_DA3 + t)·ρ`.
The frozen provisional camera model was reused; no second `K` was invented.

What the fit itself shows (§A2): `s` varies **2.70 → 8.10** across clips (3.0×),
the shift `t` is **40–65 % of representative scene z** — it is doing real work,
not absorbing a small offset — and granting `t` reduces residual by 0.01–0.52
depending on clip. Per-frame `s_t` wander is 1.55–3.97, retained as a diagnostic
only; the primary fit stays clip-level.

Load-bearing metrics, OLD → CORRECTED:

| metric | OLD | CORRECTED | MapAnything (context) |
|---|---|---|---|
| M-1 abs-rel | 0.1283 | **0.1476** | 0.0853 |
| M-2 near/far `b` | 0.8464 | 0.8555 | 0.9503 |
| M-3 RelNormal ° | 12.77 | 13.35 | 6.84 |
| M-3 abs normal ° | 20.58 | **19.54** | 7.95 |
| M-4 boundary | 0.0285 | **0.0223** | 0.0028 |
| M-5 ordinal @0.25 | 0.0037 | 0.0062 | 0.0000 |
| M-6 outer/inner | 1.014 | **1.136** | 1.042 |
| S6 windowed radiance, median | 0.113 | **0.162** | 0.104 |

**The correction is a redistribution, not an improvement, and it must be reported
as one.** Mean agreement got worse (M-1 +15 %); boundaries and absolute surface
orientation got better; frame uniformity got worse, which withdraws Round 1's
M-6 claim outright. In S6 the same pattern is sharper: the median across clips
went **up** (0.113 → 0.162) while the worst clip nearly halved
(`wreck_05` 0.333 → 0.155) and `wreck_03` more than doubled (0.089 → 0.204).
"The repair helped DA3" is not what the data says.

**Two Round-1 verdicts are withdrawn on the strength of this repair.**

1. **"DA3 fills the open `wreck_07` crane lattice with a solid opaque surface" —
   RETRACTED.** §18 measures `fill = log(r_sea/r_open)` at +0.056 for corrected
   DA3, against +0.054 for the *reference itself* and +0.049 for MapAnything.
   The arms that actually fill are `moge2_vitl` (+0.291) and `wat3r_n1` (+0.239).
   Mandatory visual inspection closed it: in the S6 sheets the lattice is **black
   in all four range panels**, i.e. reference-invalid, outside common support, and
   excluded from every S6 number. Round 1 mistook the reference's own missing data
   for correctly-resolved open water. This retraction matters beyond DA3 — it is
   the sole reason MDA (R2-6) was authorised into Round 2.
2. **"DA3 is approaching UNSAFE for restoration" — WITHDRAWN.** Corrected DA3 is
   DEGRADED (7.2–22.2 % windowed radiance error, median 16.2 %), the same class as
   the other two S6 arms, not a worse one.

### Q2 — Did DA3 remain a finalist?

**Yes — but not for the reason Round 1 kept it, and not on the numbers Round 1
kept it on.** It remains far behind `mapanything_n1` on every primary S3
dimension (M-1 0.148 vs 0.085, RelNormal 13.35° vs 6.84°, M-4 0.0223 vs 0.0028)
and it is the *worst* of the three S6 arms on the criterion metric. It is retained
because after the repair it is the **only arm that materially resolves the crane
lattice** (§18 `gap` +0.411, 4 % of members erased, against MapAnything's +0.006
and 46 %), because it is the **most appearance-stable arm on ordinary
perturbations** (S4 local Δlog 0.0128, best of five), and because it has the
**best local-surface temporal stability** in the field (S5 `local_dlog` 0.0119,
best of ten). Those are three axes on which no other retained arm is at least as
good. See §5.

### Q3 — Did corrected DA V2 remain eliminated?

**No.** This answer changed twice and both steps must be stated.

Part B did the bounded semantic repair the protocol asked for — fit the affine
ambiguity in **native disparity space**, `q_ref = 1/z_ref`, `q_ref = a·q_DAv2 + b`,
Huber IRLS, clip scope; the objective was *not* moved to log-depth or z-space,
which would have optimised away the far-range failure it exists to measure. The
predeclared range-balanced sensitivity refit moved `a` by **under 1 %** on every
clip, so the primary fit is driven by the model and not by how these clips sample
range. On those numbers Part B concluded "remains clearly eliminated" and stopped,
exactly as §4 instructs.

**Part D then invalidated the numbers Part B had stopped on.** The grid-map defect
was in *our* harness: source-grid arms were sampled 12–28 % off-position. DA v2 is
a source-grid arm. Corrected: M-1 0.1761 → **0.1094**, M-3 rel 27.50° → **12.65°**,
M-4 0.1022 → **0.0164**, M-5@0.25 0.1172 → **0.0052**. Ordinal violations fell
**95 %**, and the same repair moved `foundationgeo_11`, `moge2_vitl` and
`metricanything_pointmap` by 95–98 % on the same column. Sampling a smooth depth
field off-position manufactures ordinal violations, because the value fetched for
a far pixel is a nearer pixel's. **Those violations were an artefact of the
harness, not a property of any model** — and Round 1 read them as a property of
four models.

DA v2 then sat **second of twelve on M-1**, ahead of corrected DA3. §4's stop
condition ("if it remains clearly eliminated: STOP") was therefore **not met**, so
the elimination was withdrawn rather than restated, S4 was run on it (it had never
been measured there), it cleared, and it ran S6 for the first time. It is a
pre-C2 finalist. §5 states the narrow grounds.

The same standard was applied to DA3 in Q1 and to DA v2 here: **a Round-1 verdict
produced by our own broken harness is withdrawn, not defended.**

### Q4 — What did FoundationGeo's learned ray correction actually do?

**Nothing measurable.** Both arms were postprocessed under **one** frozen
`(focal, shift)` solution — the backend calls `forward()` rather than `infer()`
precisely so the two arms are not each given their own `recover_focal_shift`
solution, satisfying C1 by construction rather than by claim.

`fg_pre_ray` → `fg_post_ray`: point maps differ by mean relative **1.1e-03**; the
correction turns each ray by median **0.044°** (p99 0.21°, max 0.78°) against a 3°
cap; the induced change in range is median relative **2.3e-07**. After the Part D
grid repair the two arms are **identical to five decimals on all six S3
dimensions**, and §18 corroborates independently: the same `gap` to three decimals
on all six annotated lattice frames. The learned ray correction is mechanically
inert on this footage.

### Q5 — What did FoundationGeo's per-pixel scale field do?

**It buys nothing this evaluation can see and costs surface structure.** The field
is a near-uniform **0.840** multiplier (p01–p99 0.803–0.872) — effectively a global
scale, which S2 refits away anyway.

On the corrected grid, `fg_post_ray` → `foundationgeo_11`: M-1 0.11353 → 0.11351
(nothing), M-3 rel 16.27° → **17.81°** (+9.5 %), M-3 abs 21.49° → **24.45°**
(+13.7 %), M-6 1.037 → **1.176**, M-4 0.02088 → 0.02191 — the wrong way. One
earlier statement is withdrawn here too: the pre-Part-D table credited the scale
field with a "marginal boundary improvement"; that was the grid defect, and on the
corrected grid it degrades M-4 as well.

### Q6 (not asked, found while writing this report) — the late S3 convention defect

Recorded because §28 stop-condition 4 requires it and because it changed a stated
finding. `R2_S3_results.json` labelled its DA3 row "(CORRECTED)" while printing
numbers byte-identical to the committed Round-1 file. Cause: the S3 summary sourced
its incumbent rows from `results/S3_results.json`, regenerated for Part D but under
the **Round-1** policy, where `da3mono_large` and `dav2_small` still carried
`convention: "range"`. Every stage reading `R2_S3_policy.json` — S2, S4, S5, §18,
S6 — had the repair; the S3 summary did not.

Confirmed three ways, repaired under the frozen policy, blast radius verified to be
**S3 only** by reading each downstream stage's persisted alignment parameters. Two
downstream statements changed: §19's incumbent bar (M-1 0.1283 → 0.1476; the
conclusion that no challenger clears both incumbents survives), and PXDepth's
"boundary placement better than corrected DA3 (0.0285)", which at the true 0.0223
is a **tie** and is now stated as one. Full record in `LOG.md` and
`R2_S3_LOCAL_GEOMETRY.md` §4.

---

## 2. Round-2 challengers (§26.2)

Six were authorised. **Three produced primary results; three were never
measured.** An arm that never ran has produced no evidence for or against itself
and is recorded as UNTESTED, never as eliminated.

### R2-1 — `Ruicheng/moge-3-vitl` (Step 0)

| | |
|---|---|
| **Why tested** | §7: newest MoGe generation, direct successor to incumbent I3 `moge2_vitl`; the SSR refinement ablation (Step 0 vs Step 3) was the specific mechanism question. |
| **Native representation** | Metric point map (H,W,3); range = `‖p‖`, gauge family `scale`. Median `‖p‖/z` 1.14–1.17, so range and z are genuinely different here. Category **B** (execution mechanics only). MIT code, official ViT-L checkpoint — ViT-G was **not** run. |
| **Runtime / device** | MPS fp32, **4.10 s/frame** median, peak RSS 3.06 GB (CPU fallback works at 22.5 s). |
| **Determinism** | **Bitwise reproducible**, p99 relative floor 0.0e+00, within- and across-process. |
| **S3 strengths** | Beats its own incumbent `moge2_vitl` on M-1 (0.1694 vs 0.1958), M-4 (**0.0143**, second-best of twelve), M-6 (0.985) and far-field q4 (0.357 vs 1.196). |
| **S3 weaknesses** | M-1 0.1694 is worse than **both** incumbents; M-2 `b` 1.229 is a real range expansion; coverage 0.755, lowest of the measured field. |
| **Thin structure (§18)** | Separates the lattice: `gap` **+0.542**, 9 % members erased, edge gain 1.32 — but `fill` **−0.101**, the only negative fill among the separating arms, i.e. it pushes open space *further* than the sea background. |
| **S4 / S5 / S6** | S4 and S6 not run (did not advance). S5 was run: **worst `local_dlog` of ten (0.0252)**, worst `f2f` of the non-MDA arms (0.0794), `nf_wander` 7.470. It does not inherit MoGe-2's temporal behaviour; it is worse than it. |
| **Verdict** | **NON-DOMINATED, does not advance.** Fails (A): worse than both incumbents on M-1. Fails (B): it separates the lattice but **not uniquely** — corrected DA3 already does, and better on `fill`. Fails (C): the robustness property it shows is negative. Novelty is not a criterion. |

### R2-2 — `facebook/hyden-mogev2-metric-point`

| | |
|---|---|
| **Why tested** | §8: high-resolution geometry challenger; official MetaDepth implementation, metric XYZ point map. |
| **Status** | **`pending_checkpoint`.** The gated HF repo returns **HTTP 401**. The official code checkout is present; only the weights are missing. Per the CUDA/authentication policy no credential provisioning was attempted, and per §24/§28 no unofficial checkpoint was substituted. |
| **Where execution stopped** | S0, before any inference. The bounded resolution ablation §8 requires (official/default vs highest practical config preserving the frozen aspect and FOV) was therefore never run. |
| **Licence** | FAIR Noncommercial Research License → research candidate regardless of outcome. |
| **Verdict** | **UNTESTED. Not eliminated.** |

### R2-3 — `karimknaebel/surge-large`

| | |
|---|---|
| **Why tested** | §9: the specialist local-surface challenger — local point-gradient/surface objectives plus Neighborhood Attention — and the intended falsification target for "does explicit local-surface training beat generic models on local surfaces?" |
| **Status** | **`pending_cuda`**, and this one is *measured*, not assumed. NATTEN 0.21.6's `neighborhood_attention_generic` exposes no MPS backend (`choose_backend` → `flex-fna`, `NotImplementedError` on MPS); the CPU path was run to termination and **OOM-killed at 931.53 s wall with a 148.5 GB peak footprint** on a 24 GB machine. |
| **Why not adapted** | Substituting a different attention implementation is numerically non-equivalent and is forbidden by the reference-implementation integrity rule. No CUDA kernel was ported to MPS. |
| **Licence** | MIT code, **CC BY-NC 4.0 weights** → research-only. |
| **Verdict** | **UNTESTED. Not eliminated.** |

### R2-4 — PXDepth (official released checkpoint)

| | |
|---|---|
| **Why tested** | §10: structure-preserving pixel-space depth — the direct test of whether pixel-space prediction fixes boundaries and thin structure. |
| **Native representation** | `depth_log1p_affine_invariant` — log1p of **projective z-depth**, gauge family `affine_log1p_depth` (2-DOF), `r̂ = expm1(a·d + b)·ρ`. The convention is from **source code** (`scripts/infer.py:121` back-projects with `utils3d.pt.depth_map_to_point_map`, multiplying *unnormalised* `K^-1` rays by the scalar). The residual verdict disagreed and **was overruled** — per §14, semantic source evidence wins, which is exactly the mistake Round 1 made with DA3. |
| **Attribution rule** | **The MoGe-2 assist was excluded and never run.** The released repo recovers metric scale by loading MoGe-2; §10 forbids that in the primary comparison. Every PXDepth number in Round 2 is the native relative prediction. The optional MoGe-assisted deployment diagnostic was not run either, so it is recorded as not-run rather than as a result. |
| **Runtime / device** | **CPU only** (fp32, `use_fp32=True`) — the only arm with no MPS path at all. 22.25–23.68 s/frame in S3, 16.45 s/frame on the S1 subset measured without competing load; peak RSS 5.69 GB. An order of magnitude slower than every other arm either way. |
| **Determinism** | **Bitwise reproducible**, p99 relative floor 0.0e+00, within- and across-process, identical valid masks on all four S1 frames. Run after its S3 inference released the CPU rather than concurrently, which would have corrupted both runtime measurements. |
| **Reference integrity** | Category **B**, and the repo is **broken as published**: `scripts/infer.py` imports three names from a non-existent `pxdepth.inference` module. The modifications are enumerated in S0 and are execution mechanics only; the model math is unchanged. |
| **S3 strengths** | Mid-pack M-1 0.1589; **M-4 0.0221**, better than `moge2_vitl` (0.0320) and level with corrected DA3 (0.0223); low ordinal violation; M-6 exactly 1.000 on five clips. |
| **S3 weaknesses** | M-2 `b` 0.746 is real range compression; quantile profile is U-shaped (q0 0.256, q1 0.109, q4 0.275) — best in the middle, worst at both ends. |
| **Thin structure** | `fill` +0.022, `gap` +0.240 — it does separate, modestly, and below corrected DA3. |
| **S5** | `local_dlog` 0.0151, second-best of ten, `nf_wander` 1.390, best of ten — **but the median is not a summary of the arm**: five clips are at or better than the field median and `cenote_01` is off the scale (`f2f` 1.9542, `wander` 65.9). |
| **Verdict** | **FAILURE**, on a reference-independent ground. On `cenote_01` the clip fit came out at `s = −0.2701` against +0.27…+1.93 elsewhere. Measured *before* any alignment — per-frame Spearman between the untouched native field and the reference, which no monotone gauge can move — that clip returns **−0.298 median with 79 % of frames negative** and a range spanning −0.871 to +0.811. The depth order inverts and the sign flips frame to frame. Whether `cenote_01`'s reference or PXDepth is at fault for their disagreement is open; **the frame-to-frame sign flip is PXDepth's either way**. |
| **Licence** | **UNDECLARED** — no LICENSE file, 0-byte model card. Recorded as undeclared; **no licence was invented**; treated as research-only. |

### R2-5 — PointDiT-L 512

| | |
|---|---|
| **Why tested** | §11: generative point-map inference; the specific questions were whether it improves local geometry and whether **single-step, all-zero initialisation** suffices. |
| **Status** | **`pending_checkpoint`.** The model's DINOv3 encoder dependency is gated. Per §11 the Huge variant was not substituted, and no unofficial checkpoint was used. |
| **Where execution stopped** | S0, before the single-step/all-zero path could be verified in official code — which §11 required *before* running it. |
| **Verdict** | **UNTESTED. Not eliminated.** |

### R2-6 — MDA `mda_mog_sky_l2`

| | |
|---|---|
| **Why tested** | §12, for exactly one reason: Round 1 observed that "DA3 fills the open `wreck_07` crane lattice with a solid surface", and MDA's mixture-of-experts depth was the authorised candidate fix. |
| **Native representation** | Mixture-mode depth (H,W), **projective z-depth** (`utils/geometry.py:275`), family `affine_depth`. Official `DA3_MOG_Sky_LogL2.ckpt`, Apache-2.0, Category **B**. **A semantic defect was caught here:** the arm's missing `s2_ambiguity` entry fell through to a default `conv = "range"`; it was overridden by `CONVENTION_FROM_SOURCE`, and the correction made MDA slightly **worse** (0.2195 → 0.2212) — recorded because a correction that helps the corrector is the one to distrust. |
| **Strict N=1** | Verified independently, not assumed: view dimension `L == 1` asserted **every frame**; A-alone vs A-inside-a-pair max abs diff **12.887** (so the pair path is genuinely different and was not used); A-after-B identical to A-alone (0.0), i.e. no cached multi-view state. |
| **Runtime / device** | MPS fp32, **2.82 s/frame**, peak RSS 10.35 GB / 6.20 GB MPS. |
| **Determinism** | **Bitwise reproducible**, p99 relative floor 0.0e+00, including the mixture outputs. |
| **S3 strengths** | `local_dlog` 0.0174 (3rd of ten) — genuinely smooth local surfaces. |
| **S3 weaknesses** | **M-2 `b` = 0.473**: it compresses range by roughly a factor of two against the reference. A slope is not a gauge — no clip-level scale and no member of its legal `affine_depth` family can remove it. Every other arm sits in 0.75–1.37. Also worst M-1 (0.2088), worst M-3 abs (33.34°), worst M-4 (0.0593), worst M-5 (0.0394). Its sky mask fires **underwater** (32.1 % of `wreck_05`). |
| **Thin structure** | Best `fill` of any arm (**−0.004**, no false surface) — but achieved by not committing: it erases **29 %** of members and is the **only arm that inverts openings** (4 % of Tier-A openings scored nearer than their own member). |
| **S5** | **Disqualifying.** `f2f_log_mad` **0.1743**, worst on all six clips and 2.2× the next worst; `wander_ratio` **11.06**. Under FREEZE C7 a clip-constant scale offset is absorbable by `β' = β/s`; a scale moving ~19 % between adjacent frames would require the water's attenuation to change every 1/30 s in step with the estimator. |
| **Verdict** | **FAILURE**, on three independent grounds, plus a fourth that is really the decisive one: **its reason for inclusion dissolved.** Corrected DA3 resolves the lattice (`gap` +0.411, 4 % erased) and does so **better than MDA** (+0.226, 29 % erased). The failure MDA was brought in to fix was ours, it is fixed, and MDA does not fix it better. |

### 2.1 Reference-implementation integrity

All three measured challengers reached S1 and are **bitwise reproducible** with a
p99 relative noise floor of exactly `0.0e+00`, so no downstream difference in this
report is at risk of being instrument noise. All three are **Category B** — official implementation,
mechanically adapted, model math unchanged — with modifications enumerated in
`R2_S0_SEMANTICS_RUNTIME.md` and limited to device placement, dependency
compatibility, file paths and tensor I/O. No operator was replaced with an
approximation, no interpolation mode changed, no input resolution changed to fit
memory, no checkpoint substituted, no refinement stage removed, no attention
implementation swapped, and no unauthorised helper model used. Where
correctness-equivalent execution could not be established the arm is
`pending_cuda` or `pending_checkpoint`, not approximated. FOV retention across
the source→network grid mapping is 0.9962–0.9997 with map residual ≤ 0.35 px.

---

## 3. Mechanism questions (§26.3)

**MoGe-3 — did SSR Step 0 → Step 3 actually improve underwater geometry?**
**Unanswerable on this machine, and recorded as such.** The Step 3 refiner
requires `flex_gemm.ops.NeighborCache`; FlexGEMM is Triton-powered and Triton has
no macOS distribution → `pending_cuda`. §7's ablation was designed as a
same-checkpoint comparison and cannot be simulated by anything else. What *is*
measured is Step 0, and it is a genuine multi-dimensional improvement over its own
incumbent MoGe-2 on M-1/M-4/M-6/far-field while being **temporally worse than
MoGe-2** (S5 `local_dlog` 0.0252 vs 0.0245, `f2f` 0.0794 vs 0.0679). That is a
trade-off to preserve, not a preference to select.

**HyDen — did its high-resolution dual path matter at this project's
resolution?** **Not measured** — `pending_checkpoint` (HTTP 401). The §8
resolution ablation never ran. No inference from silence.

**SurGe — did explicit local-surface training beat generic models on local
surfaces?** **Not measured** — `pending_cuda`, with the blocker quantified
(148.5 GB peak on a 24 GB machine). This is the one question Round 2 most wanted
answered and did not answer: SurGe was the designed falsification target for the
local-surface hypothesis, and the hypothesis therefore stands untested. It is
recorded as an explicit C2/Round-2B item, **not** as a licence to search for
substitutes (§24).

**PXDepth — did pixel-space prediction actually fix boundaries / thin
structures?** **Partly, and not enough to matter.** Boundaries: M-4 0.0221 beats
MoGe-2 (0.0320) and ties corrected DA3 (0.0223) — a real but modest effect, and
after the §3/§4 convention repair the DA3 margin it was originally credited with
disappeared. Thin structure: `gap` +0.240 against corrected DA3's +0.411 — it
separates less than a corrected scalar-depth model from 2024. So the mechanism
does something in the direction claimed, and is beaten in that direction by the
incumbent it was brought in to challenge. The `cenote_01` rank inversion then
removes it regardless.

**PointDiT — did generative point-map inference improve local geometry, and was
one-step deterministic inference sufficient?** **Not measured** —
`pending_checkpoint` (gated DINOv3 encoder). §11 required verifying the
single-step all-zero path in official code *before* running it; execution stopped
before that verification.

**MDA — did multi-hypothesis depth fix DA3-family flying-point / solid-fill
failures, and did its mixture probabilities correlate with actual failure?**
**No to both, and the first question turned out to be built on a false premise.**

*Solid fill:* the DA3 solid-fill observation that authorised MDA was an artefact
of our own convention and fitting family (Q1). Corrected DA3 does not fill, and
resolves the lattice better than MDA does. MDA's own `fill` of −0.004 is the best
in the field, but it is bought by non-commitment: 29 % of members erased and the
only inverted openings measured.

*Mixture probabilities:* **the mixture does not commit.** Median entropy
1.21–1.25 against a maximum of `ln 4 = 1.386`, and **67–85 % of pixels select a
pairwise midpoint rather than an expert**. Against per-frame M-1 the
confidence-like quantities point the **wrong way**: pooled Spearman **−0.222** for
entropy and **+0.116** for the top-1/top-2 margin, with the sign flipping clip to
clip — failing the criterion predeclared in `outputs/r2_mda_ambiguity.json`. Per
§12 these are **ambiguity quantities, not calibrated confidence**, and that is now
a measured statement rather than a caution.

---

## 4. The honest headline

§6 set Round 2's goal as determining "whether newer/specialized monocular geometry
methods materially change the pre-C2 conclusion reached by Round 1."

**On the evidence obtained: they do not. No Round-2 challenger advances.** Zero of
the three that produced primary results clear criterion (A), (B) or (C); three of
six were never measured. A Round-2 conclusion drawn from three of six is a
conclusion about three of six, and it is stated that narrowly.

**The materially changed conclusions in Week 4A came from repairing our own work:**

1. Part A's DA3 z-depth repair reversed an elimination-grade Round-1 finding —
   corrected DA3 resolves the crane lattice it was recorded as filling.
2. Part D's grid-map repair removed a harness artefact Round 1 had read as a
   property of four models, and withdrew `dav2_small`'s elimination.
3. §18 established that the provisional reference is itself **blind to thin
   structure** (41 % of members erased, `gap` +0.000) and that the S3 leader
   inherits that blindness exactly — so no reference-based metric can reward an
   arm for resolving the lattice, and will actively penalise one that does.
4. The late S3 convention defect (Q6) changed a stated PXDepth finding.

**The largest source of error found in Week 4A was Week 4A.**

---

## 5. FINAL PRE-C2 FINALISTS

```text
FINAL PRE-C2 FINALISTS: 3

  1. mapanything_n1            (incumbent I1, N=1)
  2. da3mono_large             (incumbent I2, CORRECTED to z-depth)
  3. dav2_small                (Round-1 elimination WITHDRAWN)
```

Not preserved: `moge2_vitl` (incumbent I3 — dominated; §18 `gap` confounded with
far-field expansion, S6 never earned), `metricanything_pointmap`, `wat3r_n1`,
`foundationgeo_11` and its two mechanism arms, `moge3_vitl`, `mda_mog_sky_l2`,
`pxdepth`. **No incumbent is preserved because it won Round 1, and no challenger
is preserved because it is SOTA.**

Each finalist is non-dominated, and each is retained on an axis where **neither
other finalist is at least as good**:

| finalist | retained for | what would remove it at C2 |
|---|---|---|
| `mapanything_n1` | Native metric output, and by far the best agreement with the provisional reference (M-1 0.0853, RelNormal 6.84°, M-4 0.0028) plus the best S6 criterion (median 10.4 %, and the **only** arm/clip in the whole study meeting the Week-3 budget — `wreck_07` at 3.9 %). | A C2 scale measurement under **varying water appearance**. S4 F2 measures a uniform veil carrying *no* range information multiplying its clip range by **1.416 median, 2.465 worst**, with its constant scale swinging **±40 %** across the twelve perturbations against ±5 % for `wat3r_n1`. If C2 shows the metric scale is appearance-set rather than geometry-set, its native-metric advantage — the whole reason a fallback would use it — is gone. This is the retention most likely to be overturned. |
| `da3mono_large` (corrected) | The only arm that materially resolves thin structure (§18 `gap` **+0.411**, 4 % members erased, vs MapAnything's +0.006 / 46 % and the reference's +0.000 / 41 %); best local-surface temporal stability of ten (`local_dlog` **0.0119**); most appearance-stable on ordinary perturbations (S4 **0.0128**). | An independent range measurement at the lattice showing its separation is far-field expansion rather than acuity — the §18 F5 confound that already disqualifies `moge2_vitl`'s larger gap. Its `r_sea` (~31–34 m) is in the plausible band where `moge2`'s 175 m is not, but that is an argument, not a measurement. Also: its S6 median (16.2 %) is the worst of the three, so if C2 shows its lattice advantage is illusory there is nothing left. |
| `dav2_small` | Second-best M-1 of twelve (0.1094) at **0.19 s/frame and 0.77 GB** — an order of magnitude cheaper than either incumbent; the steadiest delivered gauge under appearance change (`max \|log σ\|` **0.073** vs MapAnything's 0.348, lowest S4 p95 in the field at 0.0597); and better than corrected DA3 on the S6 criterion (13.4 % vs 16.2 %). | Its non-domination is thinnest and is qualified by S4 F7: **an arm that asserts no metric scale cannot have one disturbed**, so its gauge steadiness is not evidence that its geometry is right. Where it must do work it is weakest — §18 Tier-A coverage **0.464** (it declines to predict on more than half the annotated lattice), edge gain 2.51, 21 % of members erased, and the lowest S3 coverage of the three (0.761). A C2 test on the lattice at full coverage, or any use case requiring range without a surface to fit against, removes it. |

**All three are DEGRADED, none is ADEQUATE, and the set is not a ranking.** It is
three different failure profiles: MapAnything is accurate and blind, DA3 sees
structure and drifts in the mean, DA v2 is cheap and stable and declines to
commit.

---

## 6. §27 — THE FINAL SCIENTIFIC QUESTION

> After correcting Round-1 semantics and challenging the incumbents with current
> 2026 SOTA/fine-geometry models, is STRICT SINGLE-IMAGE DEPTH demonstrated
> ADEQUATE, DEGRADED, or UNSAFE as the fallback geometry source for this
> underwater-restoration pipeline relative to the provisional Week-3 hypothesis?

### **DEGRADED.**

Under the S6 instrument — physical coefficients **shared and fixed** across arms,
`B∞` taken from the reference range, only `d̂` changing, so the only thing being
measured is range error — every arm is DEGRADED and none is ADEQUATE or UNSAFE.

**Why not ADEQUATE.** The Week-3 error budget is 9.4 % at 3 m / 6.1 % at 8 m
coastal. Responsive-window median relative radiance error is 10.4 % for
`mapanything_n1`, 13.4 % for `dav2_small`, 16.2 % for corrected `da3mono_large`.
**Exactly one arm/clip pair in the entire study meets the budget** —
`mapanything_n1` on `wreck_07` at 3.9 %. Windowed ΔE00 medians run 1.6–7.1 with
p95 medians 6.8–10.6. Visual inspection (mandatory, and decisive here) shows a
shared failure on `wreck_05` where both monocular arms impose a smooth ramp the
scene does not have, and the `wreck_03` diver displaced by both arms **with the
same sign** — the errors are not independent, so they will not average out.

**Why not UNSAFE — with two named exceptions inside the class.** Every retained
arm's degradation is bounded (3.9–22.2 %), attributable, and stable in sign, and
the instrument is verified: re-running S6 under the Round-2 policy reproduces
Round 1's `mapanything_n1` numbers with **0 differing scalars**, while
`da3mono_large` differs on 266 — exactly the arm the convention repair touched,
and only that arm. But UNSAFE behaviour **does** exist
in the strict-single-image class as measured this round, and the finalist set is
what excludes it: PXDepth's reference-independent **rank inversion with a
frame-to-frame sign flip** on `cenote_01`, and MDA's **~19 %-per-frame scale
drift**, which under FREEZE C7 would demand the water's attenuation change every
1/30 s. Either, deployed, would be UNSAFE rather than DEGRADED.

**Three qualifications this verdict cannot survive without.**

1. **The criterion is measured against a hypothesis, not truth.** The reference is
   a provisional multi-view product built from MapAnything, so `mapanything_n1`'s
   lead is partly self-agreement.
2. **The S6 common-support mask is the reference's, and it hides exactly the
   failure §18 exists to find.** The crane lattice is black in all four range
   panels and is excluded from every S6 number. S6 measures where the reference
   can see; §18 measures where it cannot; they disagree about DA3 for that reason.
3. **The temporal rows are arm-vs-reference, never arm-vs-nothing.** Every arm
   *including the reference* makes the footage temporally worse than its own
   unprocessed input at lag 1 on five of six clips (ratios 1.17–3.73; `wreck_01`
   is the exception at 0.73). And `turbid_coastal` is unmeasurable on this footage
   — all channels floored on four of six clips under DA3, three under DA v2, two
   under MapAnything — so its rows must not be used.

### What exact C2 measurements are required

Ordered by what they unblock. Each converts a *named* pre-C2 hypothesis into an
objective conclusion; none is a request for more models.

1. **Absolute range at known distance, on the same scene, under ≥3 distinct
   visibility conditions.** This is the single most important measurement and it
   is required by S4 F2, not merely desirable: a veil carrying no range
   information moves MapAnything's clip scale by up to **2.465×**. Measuring scale
   on one clean clip would validate a scale that appearance happened to set.
   Unblocks: whether any arm's metric claim survives; whether `mapanything_n1`
   stays a finalist at all.
2. **Independent geometry at the `wreck_07` crane lattice** — direct measurement
   of the actual member/opening geometry (physical measurement, or a
   higher-baseline photogrammetric reconstruction that is *not* the Week-3
   product). §18 F1 established the reference erases 41 % of members, so **no
   existing metric in this study can adjudicate thin structure**. Unblocks: F5's
   open question — whether `moge2_vitl`'s `gap` +1.619 and
   `metricanything_pointmap`'s +1.333 are lattice acuity or far-field expansion
   (their `r_sea` of **175 m** and **85 m** against a plausible ~31–34 m), and
   whether corrected DA3's +0.411 is real acuity. Also decides whether DA3 keeps
   its finalist slot.
3. **Near-field absolute range, 2–5 m.** This is where restoration is most
   sensitive (attenuation and backscatter both) and where every scalar arm is
   worst: corrected DA3 0.482 at 2–3 m and 0.554 at 3–5 m, `pxdepth` 0.601, MDA
   0.610, against MapAnything's 0.103. Unblocks: whether the near-field gap is the
   models' or the reference's.
4. **Far-field absolute range on at least one clip with true far structure.**
   Settles the M-2 slope question directly: is MDA's `b` = 0.473 a real
   two-fold compression, or is the reference expanded? Same for `moge2_vitl`'s
   q4 = 1.196 and `moge3_vitl`'s `b` = 1.229.
5. **The water's own coefficients, per clip** — chart or known-reflectance targets
   at known ranges, giving measured attenuation and veiling-light parameters. S6
   holds `β_att`, `β_bs` and `B∞` **fixed and shared** by design, so its numbers
   are range error *under an assumed water model*. Without this, the responsive-
   window radiance error cannot be attributed between range error and coefficient
   error, and the unnatural colour seen in **every** arm's restoration —
   reference included — cannot be assigned.
6. **A rigid, static scene with known camera motion.** The reference itself makes
   footage temporally worse than its input at lag 1 on five of six clips. Until
   that is explained, S5 and S6's temporal columns cannot separate "the arm is
   unstable" from "the warp metric or the reference is". Unblocks: whether
   `mapanything_n1`'s per-frame residual drift on `wreck_01` and its doubled
   `cenote_01` warp error (0.0233 vs the reference's 0.0098) are the model's.
7. **`cenote_01`'s reference validity.** The one clip where PXDepth's raw order
   inverts, where MapAnything's warp error doubles while both scalar arms' do not,
   and where DA v2's frozen gauge wanders 2.73. The frame-to-frame sign flip is
   PXDepth's regardless — but whether the clip's reference is sound is not
   established and three separate findings depend on it.

**No further model search is recommended.** §23's optional Round-2B set
(InfiniDepth, UniDAC, GeoNeXt, OptiGeo) remains **not run**, and no trigger for it
has fired: Round 2's measured failures are attributable to specific mechanisms in
specific models, not to a missing capability class. The three unmeasured
challengers — HyDen, SurGe, PointDiT — are the correct place to spend the next
model-side effort, and each needs exactly one thing: a checkpoint, a CUDA host, a
checkpoint. Nothing about them was decided here.

---

## Artifacts

`R2_S0_SEMANTICS_RUNTIME.md` · `R2_S1_DETERMINISM.md` · `R2_S2_ALIGNMENT.md` ·
`R2_S3_LOCAL_GEOMETRY.md` · `R2_THIN_STRUCTURE.md` · `R2_S4_APPEARANCE.md` ·
`R2_S5_TEMPORAL.md` · `R2_S6_RESTORATION.md` · `R2_S19_REDUCTION.md` ·
`R2_PARTS_ABC_CORRECTNESS.md` · `R2_PART_D_GRIDMAP_DEFECT.md`, each with its
machine-readable `*_results.json`, plus `outputs/` (native predictions persisted
so a further semantic correction needs no re-inference) and the stage summaries in
`LOG.md`.
