# S5 — independent-frame temporal stability

**Stage:** S5. Runs on the SAME 288-frame products S3 scored; nothing was
re-inferred.

Every frame was inferred INDEPENDENTLY — one image in, one prediction out, no
neighbouring image, no temporal state, no Week-3 geometry input. The sequence is
used only AFTER inference, to ask what a strictly per-frame estimator does to a
moving scene.

**SEA-RAFT is used only for evaluation correspondence.** Comparing frame t and
frame t+1 at the same PIXEL measures scene motion, not estimator instability, so
flow maps pixels to the same scene point and the comparison happens there. The flow
never reaches a depth model. It is computed once per clip and shared by every arm,
so the temporal comparison cannot depend on which model is being scored.

### Correspondence quality

| clip           | pairs | median FB-consistent fraction | median flow (eval-grid px) |
|----------------|-------|-------------------------------|----------------------------|
| wreck_07       | 47    | 0.694                         | 4.78                       |
| wreck_05       | 47    | 0.418                         | 19.58                      |
| cenote_01      | 47    | 0.940                         | 4.62                       |
| swimthrough_02 | 47    | 0.932                         | 4.36                       |
| wreck_01       | 47    | 0.930                         | 7.10                       |
| wreck_03       | 47    | 0.467                         | 15.50                      |

Forward-backward consistency uses the published Sundaram/Brox/Keuper constants
(alpha 0.01, beta 0.5), not re-tuned — the same yardstick Week 2 applied to every
backend. Pixels that fail it are occlusions and independently moving objects, and
they are partitioned out rather than counted as geometric instability.

## The physical implication, stated before the numbers

```text
If   d'_t = s_t d_t
then absorbing it under ONE shared clip-level physical coefficient would require
     beta'_t = beta / s_t
i.e. water properties that change with the estimator.
```

So frame-varying scale drift is a physical-model inconsistency **even when every
individual frame looks geometrically fine after oracle alignment**. That is why S5
reports the trajectory rather than the average scale.

## Headline

| arm                     | median s | scale wander | frame-to-frame log MAD | near/far wander | local instability dlog | boundary jitter px | coverage |
|-------------------------|----------|--------------|------------------------|-----------------|------------------------|--------------------|----------|
| mapanything_n1          | 1.0295   | 1.842        | 0.0503                 | 2.89            | 0.0189                 | 1.00               | 0.778    |
| dav2_small              | 0.0190   | 3.547        | 0.0751                 | 1.38            | 0.0108                 | 0.50               | 0.784    |
| moge2_vitl              | 2.7493   | 2.429        | 0.0693                 | 3.79            | 0.0232                 | 0.00               | 0.801    |
| metricanything_pointmap | 2.6243   | 2.286        | 0.0773                 | 6.51            | 0.0197                 | 0.00               | 0.782    |
| wat3r_n1                | 16.5539  | 2.293        | 0.0391                 | 3.62            | 0.0217                 | 0.00               | 0.776    |
| da3mono_large           | 6.9355   | 2.036        | 0.0470                 | 2.17            | 0.0096                 | 0.00               | 0.808    |
| foundationgeo_11        | 2.1839   | 1.948        | 0.0543                 | 3.35            | 0.0230                 | 0.00               | 0.806    |

`scale wander` is max/min of the per-frame scale within a clip; 1.000 would mean one
clip-level scale describes every frame. `local instability` is |delta log range| at
CORRESPONDING SCENE POINTS after removing the pairwise global scalar — what is left
cannot be scene motion and cannot be a global gauge.

## Scale wander by clip

| arm                     | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|-------------------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1          | 1.544    | 1.521    | 5.607     | 1.631          | 2.477    | 2.052    |
| dav2_small              | 3.402    | 3.829    | 2.156     | 2.033          | 3.692    | 21.172   |
| moge2_vitl              | 1.686    | 1.467    | 3.172     | 1.305          | 7.161    | 4.860    |
| metricanything_pointmap | 1.887    | 1.537    | 2.686     | 1.294          | 7.112    | 4.933    |
| wat3r_n1                | 1.994    | 2.194    | 1.342     | 2.392          | 2.851    | 3.357    |
| da3mono_large           | 1.482    | 2.488    | 1.584     | 1.582          | 4.255    | 4.363    |
| foundationgeo_11        | 1.728    | 1.606    | 2.330     | 1.324          | 5.902    | 2.168    |

## Local instability by clip (|delta log range| at corresponding scene points)

| arm                     | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|-------------------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1          | 0.0205   | 0.0174   | 0.0387    | 0.0157         | 0.0171   | 0.0228   |
| dav2_small              | 0.0187   | 0.0124   | 0.0109    | 0.0080         | 0.0074   | 0.0108   |
| moge2_vitl              | 0.0209   | 0.0256   | 0.0309    | 0.0165         | 0.0086   | 0.0366   |
| metricanything_pointmap | 0.0199   | 0.0198   | 0.0195    | 0.0144         | 0.0099   | 0.0328   |
| wat3r_n1                | 0.0249   | 0.0186   | 0.0277    | 0.0186         | 0.0116   | 0.0271   |
| da3mono_large           | 0.0093   | 0.0066   | 0.0085    | 0.0120         | 0.0099   | 0.0128   |
| foundationgeo_11        | 0.0219   | 0.0293   | 0.0241    | 0.0186         | 0.0095   | 0.0326   |

## The frozen epistemic partition

`wreck_03` carries a dynamic diver, and agreement with the Week-3 reference on a
moving object is **not** ground truth — a multi-view reference is least trustworthy
exactly where the scene moved. Week 3 also found MapAnything's dynamic failure on
`wreck_03` to be view-count-independent, so shortening the window is not a
workaround. Regions are therefore partitioned and reported separately, and
dynamic-region agreement is never used as a quality claim.

**static_anchored** — static, flow-consistent, reference has support

| arm                     | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|-------------------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1          | 0.0204   | 0.0173   | 0.0391    | 0.0154         | 0.0171   | 0.0228   |
| dav2_small              | 0.0181   | 0.0123   | 0.0109    | 0.0081         | 0.0073   | 0.0107   |
| moge2_vitl              | 0.0189   | 0.0242   | 0.0297    | 0.0150         | 0.0084   | 0.0324   |
| metricanything_pointmap | 0.0184   | 0.0188   | 0.0190    | 0.0134         | 0.0096   | 0.0292   |
| wat3r_n1                | 0.0239   | 0.0165   | 0.0274    | 0.0162         | 0.0116   | 0.0247   |
| da3mono_large           | 0.0081   | 0.0059   | 0.0082    | 0.0096         | 0.0098   | 0.0119   |
| foundationgeo_11        | 0.0215   | 0.0281   | 0.0236    | 0.0171         | 0.0094   | 0.0303   |

**static_reference_uncertain** — static, flow-consistent, reference support thin

| arm                     | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|-------------------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1          | 0.0232   | 0.0116   | 0.0374    | 0.0206         | -        | 0.0178   |
| dav2_small              | 0.0178   | 0.0098   | 0.0092    | 0.0100         | 0.0035   | 0.0074   |
| moge2_vitl              | 0.0326   | 0.0354   | 0.0301    | 0.0227         | 0.0072   | 0.0482   |
| metricanything_pointmap | 0.0289   | 0.0225   | 0.0240    | 0.0204         | 0.0078   | 0.0425   |
| wat3r_n1                | 0.0409   | 0.0371   | 0.0418    | 0.0312         | -        | 0.0429   |
| da3mono_large           | 0.0214   | 0.0183   | 0.0240    | 0.0201         | 0.0118   | 0.0210   |
| foundationgeo_11        | 0.0246   | 0.0320   | 0.0248    | 0.0223         | 0.0087   | 0.0360   |

**dynamic** — flow-inconsistent: occlusion or independent motion

| arm                     | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|-------------------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1          | 0.0131   | 0.0258   | 0.0137    | 0.0234         | 0.0180   | 0.0299   |
| dav2_small              | 0.0588   | 0.0122   | 0.0054    | 0.0067         | 0.0031   | 0.0158   |
| moge2_vitl              | 0.0534   | 0.0455   | 0.0193    | 0.0234         | 0.0091   | 0.0713   |
| metricanything_pointmap | 0.0435   | 0.0404   | 0.0151    | 0.0260         | 0.0110   | 0.0609   |
| wat3r_n1                | 0.0357   | 0.0329   | 0.0273    | 0.0286         | 0.0149   | 0.0540   |
| da3mono_large           | 0.0246   | 0.0193   | 0.0086    | 0.0305         | 0.0582   | 0.0336   |
| foundationgeo_11        | 0.0514   | 0.0458   | 0.0246    | 0.0216         | 0.0064   | 0.0490   |

## Worst clip per arm

| arm                     | worst scale wander | worst local instability | worst coverage   |
|-------------------------|--------------------|-------------------------|------------------|
| mapanything_n1          | cenote_01 (5.607)  | cenote_01 (0.0387)      | wreck_03 (0.320) |
| dav2_small              | wreck_03 (21.172)  | wreck_07 (0.0187)       | wreck_03 (0.308) |
| moge2_vitl              | wreck_01 (7.161)   | wreck_03 (0.0366)       | wreck_03 (0.354) |
| metricanything_pointmap | wreck_01 (7.112)   | wreck_03 (0.0328)       | wreck_03 (0.348) |
| wat3r_n1                | wreck_03 (3.357)   | cenote_01 (0.0277)      | wreck_03 (0.354) |
| da3mono_large           | wreck_03 (4.363)   | wreck_03 (0.0128)       | wreck_03 (0.354) |
| foundationgeo_11        | wreck_01 (5.902)   | wreck_03 (0.0326)       | wreck_03 (0.352) |

## Findings

A note on units first, because it decided the S4 reading. Everything in S5 is in
PHYSICAL RANGE — `s5_temporal` applies the frozen S2 policy before measuring, so the
affine-family arm and the scale-family arms are already on one scale here and no
correction of the kind S4 needed applies. The four survivors are directly comparable
below.

### 1. Depth Anything 3 Mono is the most temporally stable model in the field

| model | local instability | near/far wander | frame-to-frame MAD | scale wander | coverage |
|---|---|---|---|---|---|
| da3mono_large | **0.0096** | **2.17** | 0.0470 | 2.036 | **0.808** |
| mapanything_n1 | 0.0189 | 2.89 | 0.0503 | **1.842** | 0.778 |
| metricanything_pointmap | 0.0197 | 6.51 | 0.0773 | 2.286 | 0.782 |
| wat3r_n1 | 0.0217 | 3.62 | **0.0391** | 2.293 | 0.776 |

Local instability is the dimension that cannot be explained away: it is
|delta log range| at CORRESPONDING SCENE POINTS after removing the pairwise global
scalar, so it is neither scene motion nor a global gauge. `da3mono_large` is 2.0x
better than the next model, and it is better on EVERY ONE of the six clips
(0.0066–0.0128 against 0.0157–0.0387 for mapanything). In the `static_anchored`
partition — static, flow-consistent, reference-supported, the only region where the
reference is entitled to arbitrate — it wins all six again, 0.0059–0.0119.

This is the same model that S4 (read in physical range) found steadiest under every
non-veil perturbation. The two stages agree, and they agree for a coherent reason: a
single-image relative-depth model with a strong learned layout prior returns the same
layout for similar-looking frames. Its stability is prior-driven.

The corollary is the S4 cue-conflict result, which is the price of the same
mechanism: that prior is keyed on appearance including haze, so the model is steady
exactly as long as the haze cue stays honest (3.99x ratio, the highest in the field).
S5 and S4 are measuring one property from two sides.

### 2. MetricAnything is the weakest survivor, and near/far wander is why

`near/far wander` — the drift of the aligned field's OWN near/far ratio across a clip
— is 6.51 for `metricanything_pointmap` against 2.17–3.62 for the others. The shape
of its depth range, not just its scale, changes by a factor of six within a single
clip. It also has the worst frame-to-frame MAD (0.0773) and a 7.112 scale wander on
`wreck_01`.

That compounds its S3 record (M-1b far quintile 0.682, the worst of all seven
candidates by 2.9x over the next) and its S4 record (worst response to a physically
CORRECT veil, worst veil mean, worst cue-conflict wander at 1.8709). It is last or
near-last in every stage it has entered.

The S0 lineage finding explains rather than excuses this: MetricAnything is MoGe-2
with retrained heads (483 identical tensor keys, encoder rel-L2 0.0002 vs heads
0.019–0.044). Its V5 heterogeneous metric fine-tuning bought a better median scale
than MoGe-2 but did not buy far-field or temporal behaviour.

### 3. MapAnything's failure is concentrated on one clip, and it is the diagnostic one

`cenote_01` is `mapanything_n1`'s worst clip on both scale wander (5.607, against
1.521–2.477 elsewhere) and local instability (0.0387, against 0.0157–0.0228). It is
the clip with the widest near/far range in the frozen set.

So MapAnything — the strongest model in S3 by a wide margin and the most veil-robust
in S4 — destabilises specifically where the scene is deep. That is a targeted
weakness rather than a general one, and it is the condition Week 3's far-field
sensitivity budget (8.5 % at 8 m) is tightest under.

### 4. Wat3R degrades where the reference thins out

Across the epistemic partition, `wat3r_n1` goes from 0.0116–0.0274 in
`static_anchored` to 0.0312–0.0429 in `static_reference_uncertain` — the largest
anchored-to-uncertain degradation of the four, and the only one where the uncertain
region is consistently worse than every other model's. `da3mono_large` moves
0.0059–0.0119 -> 0.0118–0.0240 over the same partition.

Read carefully, this is a statement about correlated failure, not about truth: the
regions where the multi-view reference has thin support are also the regions where a
feed-forward point-map model has little to work with. It is a reason to distrust
Wat3R where it is least checkable, which is the worst place to have to trust it.

### 5. The epistemic partition did its job on wreck_03

Dynamic-region numbers are reported and NOT used as a quality claim, per the freeze:
agreement with a multi-view reference on a moving diver is not ground truth. Recorded
for completeness: on `wreck_03`'s dynamic region, mapanything 0.0299, da3mono 0.0336,
wat3r 0.0540, metricanything 0.0609.

Worth noting that `da3mono_large`'s single worst dynamic-region number in the whole
table is `wreck_01` at 0.0582 — the low-texture near-planar PORTRAIT clip, where
"dynamic" means occlusion rather than independent motion. No claim is made on it.

### 6. Nobody is temporally stable in absolute terms

Scale wander is 1.84–2.29 for all four: the single scalar relating a model's output
to the reference changes by a factor of two or more within a 48-frame clip for every
survivor. Under one shared clip-level physical coefficient that requires
`beta'_t = beta / s_t` — water properties that change with the estimator.

No monocular candidate in this field can supply a temporally coherent scale on its
own. That is not a tiebreaker between them, it is a constraint on the architecture
downstream: Week 5-6's temporal stage must own scale continuity, and no choice made
here removes that requirement.

## Reduction to finalists — 4 -> 2

**Eliminated: `metricanything_pointmap`.** Last or near-last in every stage: S3 far
quintile 0.682 (worst of all seven candidates, 2.9x the next), S4 worst veil mean and
worst response to a physically correct veil, S5 worst near/far wander (6.51) and
worst frame-to-frame MAD. Nothing it does is best-in-field, and its V5 lineage
advantage over MoGe-2 does not extend to the axes that matter here.

**Eliminated: `wat3r_n1`.** Dominated by `da3mono_large` on the S3 geometry
dimensions (M-1 0.184 vs 0.128, M-1b far 0.229 vs 0.129, normal error 15.62° vs
12.77°) and by both finalists in `static_reference_uncertain`. Independently, S0
recorded that it loses 10 of 25 FOV markers and 44 % of frame area on the portrait
clip — a hard structural failure for a video pipeline that cannot be traded against a
metric. Its one distinction, the steadiest scale in the field, is not enough against
that.

**Finalists for S6:**

| finalist | why it advances | what S6 must test |
|---|---|---|
| `mapanything_n1` | best S3 geometry by a wide margin (M-1 0.085, normal 6.84°, both ~1.5–1.9x the next); most veil-robust in S4 (1.75x); veil response is benign gauge not deformation | whether its `cenote_01` deep-scene instability degrades restoration where the far-field budget is tightest |
| `da3mono_large` | most temporally stable by 2.0x and best in `static_anchored` on all six clips; most appearance-invariant on non-veil arms | whether its 3.99x veil-leaning closes the self-reference loop once restoration removes the veil; and whether an affine gauge with a large oracle shift is usable without an oracle |

Two finalists rather than three: the pair spans the design space (multi-view-trained
metric point map vs single-image affine-ambiguous relative depth), and the two
eliminated arms are each dominated rather than merely behind.

**The unresolved question both finalists share.** `da3mono_large` needs a fitted
affine `(s, t)` with t = 1.78-11.56 m, and `mapanything_n1` needs a scale. Neither is
available at inference time without an oracle. S6 measures restoration impact under
the frozen oracle alignment; it does NOT establish that either finalist can be
deployed without one. That is a C2 question and it is not answered here.
