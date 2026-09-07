# S6 — restoration impact

**Stage:** S6. Only the S5 finalists run.

Each of the six frozen clips is restored twice — once driven by the Week-3
multi-view range, once by each finalist's monocular range — on identical frames at
SOURCE resolution.

## What the instrument is, and what it is not

**This is not the project's restoration.** Weeks 5-6 own backscatter removal and
attenuation inversion. S6 needs *some* stage that consumes range in order to answer
whether swapping the range field changes the restored image, so this implements the
project's standing image-formation model exactly as `PLAN.md` states it and as Week
3's stage-7 sensitivity study used it:

```text
I_c     = J_c * exp(-b_att_c * d) + Binf_c * (1 - exp(-b_bs_c * d))
J_hat_c = (I_c - Binf_c * (1 - exp(-b_bs_c * d_hat))) / exp(-b_att_c * d_hat)
```

**The coefficients are SHARED and FIXED across arms**, and the veiling light `Binf`
is estimated once per clip from the REFERENCE range. Between two arms the only
thing that changes is `d_hat`.

### Two admissibility corrections the first run made necessary

The instrument as first configured produced numbers that could not be read, and
the reason is worth stating because it is a property of this footage, not a coding
slip. Both corrections were applied identically to every arm.

**1. The veiling light has to be one the image can carry.** `Binf` was estimated as
the p90 of the far field under the reference range. On `wreck_07` and `wreck_03`
the water column is CLIPPED in the source — 10.7% and 14.4% of pixels at code 254+
— so that estimator returns `Binf_B = 1.0`, and `1.0 * (1 - exp(-0.22 * 7 m)) =
0.79` exceeds the observed blue at essentially every pixel that is not far away.
The inversion then subtracts more than the image contains. Measured: **99% of
pixels had at least one channel driven to zero**, restored medians were a pure red
`[0.75, 0, 0]`, and 50-84% of the common support was BIT-IDENTICAL between the two
arms. The resulting median delta E00 of 0.000 on four of six clips was two
saturations agreeing, not two range fields agreeing.

The model itself says what the bound is: `J >= 0` requires
`Binf_c <= min_p I_c(p) / (1 - exp(-b_bs_c d(p)))`, whose minimising pixels are the
darkest ones AT THEIR OWN RANGE — the dark-channel estimator, made exact by knowing
`d`. `Binf` is now the p90 far-field estimate capped by that bound (1st percentile,
not the hard minimum). Because the bound involves `b_bs` it is per water type;
within a water type all arms still share one `Binf`.

**2. The inversion gain has to be finite.** These clips carry reference ranges out
past 50 m, where `1/exp(-0.55 * d)` for red is 1e12. The 8-bit source's
quantisation step is ~3e-4 in linear light near the dark end, so past roughly 20x
the amplified step stops being negligible against restored medians of 0.2-0.5.
Transmission is therefore floored at `t_floor = 0.05`, per
channel: red stops responding beyond ~5.4 m in the coastal regime while green and
blue keep responding past 15 m, which is the physically honest statement about
which channel carries range information how far.

**3. Metrics are reported twice.** Once over the full common support, and once over
the RESPONSIVE WINDOW: pixels not floored in every channel and not pinned at either
end of the clamp in either arm. Outside that window two range fields produce the
same pixel however much they disagree. The window fraction is reported alongside,
because a number from a 10% window is a different claim from one from a 90% window.

That is what makes temporal scale drift bite here. A CONSTANT global scale error is
exactly absorbable by `b -> b/s` — Week 3 verified that identity to floating-point
precision — so a merely-biased model loses nothing. A model whose scale WANDERS
cannot be absorbed by any single `b`, and pays for it in colour.

Primary water type: `coastal` (b_att [0.55, 0.2, 0.19], b_bs [0.45, 0.22, 0.22], 1/m). These are the Jerlov-bracketing values Week 3 swept, NOT a fit to this
project's footage, which Week 6 owns.

Per-clip veiling light estimated from the reference, and what the uncorrected
far-field estimator would have used:

| clip           | Binf used (coastal)    | far-field p90 (inadmissible) |
|----------------|------------------------|------------------------------|
| wreck_07       | 0.0003, 0.0134, 0.0170 | 0.0056, 0.3916, 1.0000       |
| wreck_05       | 0.0000, 0.0232, 0.0432 | 0.0003, 0.1441, 0.7305       |
| cenote_01      | 0.0006, 0.0003, 0.0004 | 0.0052, 0.0212, 0.0482       |
| swimthrough_02 | 0.0271, 0.0236, 0.0091 | 0.1356, 0.5149, 0.4452       |
| wreck_01       | 0.0096, 0.0459, 0.0571 | 0.0252, 0.1070, 0.1529       |
| wreck_03       | 0.0000, 0.0219, 0.0191 | 0.0015, 0.6038, 1.0000       |

## Colour difference against the reference-driven restoration

CIEDE2000, computed after normalising BOTH restorations to the same median
exposure, so a pure brightness difference does not present as a colour difference.
The exposure ratio is reported separately.

### median delta E00 per frame

| arm            | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|----------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1 | 0.551    | 0.584    | 1.835     | 1.513          | 2.679    | 1.814    |
| da3mono_large  | 1.270    | 4.370    | 1.549     | 2.728          | 3.532    | 1.598    |

### p95 delta E00 within frame

| arm            | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|----------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1 | 5.070    | 4.565    | 7.839     | 7.528          | 7.520    | 4.688    |
| da3mono_large  | 10.536   | 13.319   | 5.130     | 10.910         | 10.024   | 8.355    |

### COLOUR PUMPING: frame-to-frame MAD of delta E00

| arm            | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|----------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1 | 0.274    | 0.529    | 0.620     | 0.614          | 1.093    | 0.688    |
| da3mono_large  | 0.238    | 0.457    | 0.116     | 0.321          | 0.345    | 0.462    |

### median |relative radiance error|

| arm            | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|----------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1 | 0.0002   | 0.0002   | 0.0836    | 0.0283         | 0.1256   | 0.0012   |
| da3mono_large  | 0.0007   | 0.0012   | 0.0645    | 0.0523         | 0.2238   | 0.0008   |

### RESPONSIVE WINDOW: median delta E00 per frame

| arm            | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|----------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1 | 2.129    | 2.558    | 1.833     | 2.718          | 2.700    | 2.928    |
| da3mono_large  | 3.181    | 7.780    | 1.589     | 3.486          | 3.534    | 4.278    |

### RESPONSIVE WINDOW: p95 delta E00 within frame

| arm            | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|----------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1 | 6.000    | 5.982    | 7.811     | 8.234          | 7.527    | 5.940    |
| da3mono_large  | 10.953   | 16.115   | 5.193     | 11.959         | 10.038   | 14.428   |

### RESPONSIVE WINDOW: colour pumping

| arm            | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|----------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1 | 0.583    | 1.721    | 0.621     | 1.091          | 1.105    | 0.721    |
| da3mono_large  | 0.194    | 0.503    | 0.114     | 0.415          | 0.334    | 1.130    |

### RESPONSIVE WINDOW: median |relative radiance error|

| arm            | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|----------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1 | 0.0389   | 0.1022   | 0.0834    | 0.1056         | 0.1256   | 0.1898   |
| da3mono_large  | 0.1339   | 0.3326   | 0.0642    | 0.0918         | 0.2240   | 0.0890   |

### responsive window as a fraction of common support

| arm            | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|----------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1 | 0.593    | 0.388    | 0.960     | 0.763          | 0.992    | 0.340    |
| da3mono_large  | 0.640    | 0.382    | 0.965     | 0.730          | 0.990    | 0.185    |

### exposure ratio vs reference

| arm            | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|----------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1 | 0.993    | 1.000    | 1.001     | 1.007          | 0.994    | 0.998    |
| da3mono_large  | 1.024    | 1.157    | 1.029     | 1.025          | 0.984    | 1.064    |

### fraction of restored pixels clamped high

| arm            | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|----------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1 | 0.1016   | 0.0410   | 0.0048    | 0.0252         | 0.0000   | 0.0363   |
| da3mono_large  | 0.1121   | 0.0945   | 0.0049    | 0.0606         | 0.0000   | 0.1180   |

### fraction with EVERY channel on the transmission floor

| arm            | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|----------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1 | 0.3887   | 0.5877   | 0.0000    | 0.1405         | 0.0000   | 0.4951   |
| da3mono_large  | 0.3467   | 0.6373   | 0.0000    | 0.1843         | 0.0000   | 0.7112   |

The pumping row is the one that connects S5 to a visible artifact: a steady colour
offset is a bias a downstream stage could in principle absorb, whereas a colour
difference that MOVES frame to frame is the artifact the project's temporal
invariant exists to prevent.

For scale, the reference-driven restoration's own behaviour:

| clip           | clamped high | driven negative | fully floored | responsive | p99 gain the inversion ASKED for |
|----------------|--------------|-----------------|---------------|------------|----------------------------------|
| wreck_07       | 0.1009       | 0.0075          | 0.3350        | 0.6505     | 1e+08                            |
| wreck_05       | 0.0447       | 0.0044          | 0.5708        | 0.4109     | 1e+08                            |
| cenote_01      | 0.0045       | 0.0070          | 0.0000        | 0.9674     | 314                              |
| swimthrough_02 | 0.0284       | 0.0148          | 0.1465        | 0.7733     | 1.03e+05                         |
| wreck_01       | 0.0000       | 0.0021          | 0.0000        | 0.9920     | 68.7                             |
| wreck_03       | 0.0501       | 0.0000          | 0.5817        | 0.4119     | 1e+08                            |

## Robustness across water regimes

The same comparison under all three Jerlov-bracketing coefficient sets. A
conclusion that only holds for one regime is a conclusion about the coefficients.

| arm            | water type     | median delta E00 |
|----------------|----------------|------------------|
| mapanything_n1 | coastal        | 2.629            |
| mapanything_n1 | clear_oceanic  | 1.642            |
| mapanything_n1 | turbid_coastal | 2.940            |
| da3mono_large  | coastal        | 3.510            |
| da3mono_large  | clear_oceanic  | 2.816            |
| da3mono_large  | turbid_coastal | 5.671            |

## Frozen Week-2 temporal metrics on the restored sequences

The Phase-2B machinery, unchanged: motion-compensated warp error in linear light
with SEA-RAFT correspondence, at lags 1/4/8, plus temporal delta E00.

| arm             | clip           | MC-warp @1 | input @1 | @4      | @8      | temporal dE00 @1 | input dE00 @1 | coverage @1 |
|-----------------|----------------|------------|----------|---------|---------|------------------|---------------|-------------|
| week3_reference | wreck_07       | 0.02016    | 0.00895  | 0.02140 | 0.02617 | 3.561            | 2.816         | 0.743       |
| week3_reference | wreck_05       | 0.02808    | 0.01004  | 0.05955 | 0.07682 | 5.260            | 3.084         | 0.662       |
| week3_reference | cenote_01      | 0.00983    | 0.00843  | 0.01602 | 0.02173 | 2.819            | 2.506         | 0.949       |
| week3_reference | swimthrough_02 | 0.04379    | 0.01810  | 0.05829 | 0.06959 | 4.666            | 2.885         | 0.944       |
| week3_reference | wreck_01       | 0.00733    | 0.01002  | 0.00717 | 0.00848 | 4.423            | 2.134         | 0.454       |
| week3_reference | wreck_03       | 0.03699    | 0.00991  | 0.03949 | 0.06588 | 3.793            | 2.018         | 0.736       |
| mapanything_n1  | wreck_07       | 0.01997    | 0.00895  | 0.02165 | 0.02774 | 3.460            | 2.816         | 0.743       |
| mapanything_n1  | wreck_05       | 0.02882    | 0.01004  | 0.05988 | 0.07788 | 5.179            | 3.084         | 0.662       |
| mapanything_n1  | cenote_01      | 0.02330    | 0.00843  | 0.01745 | 0.05495 | 6.748            | 2.506         | 0.949       |
| mapanything_n1  | swimthrough_02 | 0.04916    | 0.01810  | 0.06622 | 0.07993 | 5.263            | 2.885         | 0.944       |
| mapanything_n1  | wreck_01       | 0.00762    | 0.01002  | 0.02423 | 0.01788 | 4.228            | 2.134         | 0.454       |
| mapanything_n1  | wreck_03       | 0.03035    | 0.00991  | 0.03638 | 0.06682 | 3.355            | 2.018         | 0.736       |
| da3mono_large   | wreck_07       | 0.01386    | 0.00895  | 0.01795 | 0.02607 | 3.595            | 2.816         | 0.743       |
| da3mono_large   | wreck_05       | 0.02357    | 0.01004  | 0.05180 | 0.06993 | 5.043            | 3.084         | 0.662       |
| da3mono_large   | cenote_01      | 0.00851    | 0.00843  | 0.01608 | 0.02375 | 2.806            | 2.506         | 0.949       |
| da3mono_large   | swimthrough_02 | 0.02890    | 0.01810  | 0.05031 | 0.06889 | 3.950            | 2.885         | 0.944       |
| da3mono_large   | wreck_01       | 0.00869    | 0.01002  | 0.00672 | 0.00710 | 4.789            | 2.134         | 0.454       |
| da3mono_large   | wreck_03       | 0.01862    | 0.00991  | 0.03127 | 0.07001 | 2.769            | 2.018         | 0.736       |

`input` columns are the UNPROCESSED sequence measured on the same
correspondence and the same mask. A restoration that is less stable than its
own input has made the footage worse in the project's own frozen terms, and
the comparison that matters is each arm against the reference-driven row on
the same clip.

## Mandatory visual inspection

`CLAUDE.md` invariant 5: a metric improvement is not a successful experiment
until the output has been looked at for hallucinated detail, broken scene
identity and unnatural colour relationships. Two kinds of render:

- **sheets** — one row per arm over three frames per clip: source, the arm's
  range on a colour scale SHARED with the reference, its signed disagreement, and
  the restoration it drives;
- **worst-disagreement crops** — the tiles where the arm and the reference
  disagree most, magnified. Chosen by the data, so it cannot be a flattering crop.

18 sheets and 144 crops under `outputs/s6/inspect/`.

Looked for specifically: backscatter or particles turned into depth structure; marine snow; caustics; animal boundaries; artificial-light regions; far-field range collapse; thin structures; colour pumping across frames.

### What the inspection actually showed

**No hallucinated texture, by construction -- but hallucinated GEOMETRY arrives as
hallucinated colour.** The instrument is a per-pixel gain and offset; it cannot
invent detail, and scene identity survives intact in every restored frame. What a
range field CAN invent is structure, and one arm does. On `wreck_07` f000109
`da3mono_large` fills the thin lattice of the crane and rigging with a solid opaque
surface exactly where both the reference and `mapanything_n1` leave holes -- so
water seen THROUGH the lattice is restored as though it sat at the lattice's range.
That is the thin-structure failure mode expressed photometrically rather than as
texture, and it is the one finding here that touches scene identity.

**The worst disagreements sit where the image carries no evidence.** Both arms'
worst-disagreement crops on `cenote_01` land in the unlit cave void -- source tiles
that are essentially black. The reference places the void far; MapAnything and DA3
both pull it much nearer (crops 4,6 and 0,9). No monocular model can do better
there, and the reference is not obviously right either. What matters is that the
guess is UNSTABLE, and this is precisely the clip where MapAnything's temporal
delta E00 blows up (6.748 against an unprocessed-input control of 2.506) while
DA3's does not (2.806). A wandering guess in a black void still costs colour,
because the void's gain is where the inversion is most sensitive.

**On the near-planar clip the two error SHAPES are categorically different.**
`wreck_01` f001855: MapAnything's signed disagreement is a near-uniform field over
the entire frame -- a global offset, the benign gauge of FREEZE C7, absorbable by
`b -> b/s`. DA3's is a large smooth blob, neutral along the top edge and strongly
positive through the lower centre -- a genuine low-frequency deformation of the same
scene. The two restorations look nearly identical to the eye (both dark teal, both
with a red bloom in the far bottom-left corner), which is why the delta E00
separation on this clip is modest; the shapes say the errors are not the same kind
of thing.

**The dynamic subject.** `wreck_03` f000317, the diver. MapAnything reproduces the
silhouette and its range; its disagreement map is near-neutral across the whole
body. DA3 renders the diver as a solid strongly-positive region -- it places the
moving subject substantially farther than the reference -- and its restoration
shows the diver visibly warmer and redder than both the reference and MapAnything.
The one object a viewer actually looks at is the object DA3 displaces.

**Far-field over-gain is visible, not merely numerical.** `swimthrough_02` f000089:
DA3 puts the central swim-through channel much deeper than the reference, and the
restoration blows that channel out to a bright cyan while the reference and
MapAnything keep it continuous with the surrounding water. On the same frame the
reference range is riddled with holes tracing the fine coral branches while both
monocular arms are dense there -- so on reef footage a large part of what the
comparison CANNOT see is the reference's own missing data, excluded from the common
support rather than counted against anyone.

**Colour relationships are unnatural in EVERY arm, the reference included.** All
coastal restorations sit orange-brown against a green-blue source (red
over-corrected at around 7 m), and `wreck_01`'s far corner blooms red. That is the
fixed Jerlov-bracketing coefficients, not any range field -- Week 6 owns the
coefficients. It is recorded here so the S6 tables are not misread as a claim that
this restoration looks right. It is a differencing instrument, not a deliverable.

**Black regions in the restored panels are reference-invalid pixels and depth-edge
over-subtraction, not model output.** They are excluded from every number above.

## Provisional classification

```text
ADEQUATE / DEGRADED / UNSAFE
relative to the CURRENT WEEK-3 HYPOTHESIS
```

Judged against the Week-3 error budget (LOG.md): the local relative range error at
which the worst channel's restored radiance error reaches 5% is 9.4% at 3 m and
6.1% at 8 m in the coastal regime, 12% and 8.5% clear oceanic. The directly
comparable measurement is the responsive-window median |relative radiance error|.

- `mapanything_n1`: **DEGRADED.** 3.9-19.0% radiance error in the responsive window
  across the six clips (median about 10%), roughly twice the 5% criterion. Colour
  difference is bounded and similar on every clip -- windowed median delta E00
  1.83-2.93, under the threshold at which most observers see a difference at all --
  and on the near-planar clip its disagreement is close to a pure global gauge,
  which is benign. Its one real hazard is temporal, not static: its responsive-window
  colour pumping is the higher of the two arms on five of six clips (1.72 on
  `wreck_05`, 1.11 and 1.09 on `wreck_01` and `swimthrough_02`), and on `cenote_01`
  it more than doubles the motion-compensated warp error against the reference-driven
  arm (0.02330 vs 0.00983) and lifts temporal delta E00 from 2.82 to 6.75. That is
  frame-varying scale drift, which no single fixed `b` can absorb.

- `da3mono_large`: **DEGRADED, and approaching UNSAFE on low-texture lateral
  footage.** 6.4-33.3% radiance error, up to six times the criterion. `wreck_05` is
  the failure: windowed median delta E00 7.78 with a p95 of 16.1 and 33% radiance
  error, which the sheet shows as a large smoothly-growing disagreement over the
  whole lower-right and a markedly bluer restoration. Two of its failures are
  scene-identity failures rather than photometric ones -- the thin lattice filled
  solid on `wreck_07`, the dynamic diver displaced on `wreck_03`. Counter-evidence,
  stated rather than buried: DA3 is the MORE temporally stable arm. Lower colour
  pumping on five of six clips, the only arm that does not degrade `cenote_01`
  relative to the reference, and on `wreck_01` its warp error at lag 8 (0.00710)
  beats the reference-driven arm's (0.00848).

Neither finalist is ADEQUATE against the Week-3 budget on this footage.

Three limits on how far that verdict travels:

1. **Pre-C2 the reference is a hypothesis, not ground truth.** The reference's own
   restoration health is worst on exactly the clips where disagreement is worst --
   responsive fraction 0.41 on `wreck_05` and `wreck_03`, with the inversion asking
   for p99 gains of 1e8. DEGRADED is a statement about the magnitude of
   disagreement relative to the budget, not a proof that the monocular side is the
   side that is wrong.

2. **Every arm, reference included, makes the footage temporally worse than its own
   unprocessed input** at lag 1 on five of six clips (reference ratios 1.17-3.73).
   A range-driven inversion with fixed coefficients amplifies per-frame range noise
   into colour. That is a property of the instrument, and it means the temporal
   rows should be read as arm-vs-reference, never as arm-vs-nothing.

3. **`turbid_coastal` is not measurable on this footage and its row above should not
   be used.** The transmission floor swallows the frame: every channel is floored on
   100% of pixels for four of six clips under `da3mono_large` and two under
   `mapanything_n1`, and the surviving windowed medians rest on a handful of frames
   with slivers of window (`wreck_03`/MapAnything reports 2.94 from a median window
   fraction of 0.000). The measurable regimes here are `coastal` and
   `clear_oceanic`; both rank the arms the same way.

S6 does not produce the final objective Week-4 winner. Pre-C2 there is no
independent anchor, so a monocular-vs-reference disagreement cannot say which side
is wrong.
