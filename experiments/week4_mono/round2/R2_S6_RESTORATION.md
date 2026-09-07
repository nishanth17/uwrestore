# S6 — restoration impact

**Stage:** S6. Three arms: the incumbent `mapanything_n1`, the Part-A-CORRECTED `da3mono_large`, and `dav2_small` (retained by §19 on S4, never run through S6 before).

Each of the 6 frozen clips is restored 4 times — once
driven by the Week-3 multi-view range, once by each arm's monocular range — on
identical frames at SOURCE resolution.

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
is estimated once per clip from the REFERENCE range. Between any two arms the only
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
| da3mono_large  | 1.743    | 3.310    | 1.515     | 2.732          | 3.191    | 2.367    |
| dav2_small     | 0.779    | 1.494    | 1.888     | 2.614          | 3.751    | 1.691    |

### p95 delta E00 within frame

| arm            | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|----------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1 | 5.070    | 4.565    | 7.839     | 7.528          | 7.520    | 4.688    |
| da3mono_large  | 10.772   | 12.381   | 4.798     | 11.481         | 8.410    | 8.276    |
| dav2_small     | 6.188    | 8.944    | 6.733     | 11.031         | 9.950    | 8.493    |

### COLOUR PUMPING: frame-to-frame MAD of delta E00

| arm            | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|----------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1 | 0.274    | 0.529    | 0.620     | 0.614          | 1.093    | 0.688    |
| da3mono_large  | 0.172    | 0.476    | 0.204     | 0.235          | 0.378    | 0.573    |
| dav2_small     | 0.285    | 0.380    | 0.215     | 0.312          | 0.527    | 0.629    |

### median |relative radiance error|

| arm            | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|----------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1 | 0.0002   | 0.0002   | 0.0836    | 0.0283         | 0.1256   | 0.0012   |
| da3mono_large  | 0.0008   | 0.0013   | 0.0713    | 0.0504         | 0.2224   | 0.0011   |
| dav2_small     | 0.0043   | 0.0014   | 0.0897    | 0.0334         | 0.1979   | 0.0010   |

### RESPONSIVE WINDOW: median delta E00 per frame

| arm            | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|----------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1 | 2.129    | 2.558    | 1.833     | 2.718          | 2.700    | 2.928    |
| da3mono_large  | 3.700    | 7.049    | 1.559     | 3.491          | 3.195    | 4.601    |
| dav2_small     | 1.596    | 4.787    | 1.936     | 3.136          | 3.733    | 5.068    |

### RESPONSIVE WINDOW: p95 delta E00 within frame

| arm            | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|----------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1 | 6.000    | 5.982    | 7.811     | 8.234          | 7.527    | 5.940    |
| da3mono_large  | 11.047   | 14.914   | 4.883     | 12.929         | 8.434    | 10.058   |
| dav2_small     | 7.387    | 10.061   | 6.725     | 12.630         | 9.870    | 11.147   |

### RESPONSIVE WINDOW: colour pumping

| arm            | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|----------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1 | 0.583    | 1.721    | 0.621     | 1.091          | 1.105    | 0.721    |
| da3mono_large  | 0.269    | 0.494    | 0.193     | 0.297          | 0.375    | 1.151    |
| dav2_small     | 0.382    | 0.903    | 0.174     | 0.452          | 0.532    | 1.207    |

### RESPONSIVE WINDOW: median |relative radiance error|

| arm            | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|----------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1 | 0.0389   | 0.1022   | 0.0834    | 0.1056         | 0.1256   | 0.1898   |
| da3mono_large  | 0.1678   | 0.1554   | 0.0715    | 0.0968         | 0.2223   | 0.2040   |
| dav2_small     | 0.0576   | 0.2125   | 0.0905    | 0.0791         | 0.1979   | 0.1779   |

### responsive window as a fraction of common support

| arm            | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|----------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1 | 0.593    | 0.388    | 0.960     | 0.763          | 0.992    | 0.340    |
| da3mono_large  | 0.634    | 0.383    | 0.965     | 0.734          | 0.990    | 0.173    |
| dav2_small     | 0.726    | 0.489    | 0.965     | 0.728          | 0.990    | 0.183    |

### exposure ratio vs reference

| arm            | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|----------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1 | 0.993    | 1.000    | 1.001     | 1.007          | 0.994    | 0.998    |
| da3mono_large  | 1.002    | 1.113    | 1.001     | 1.027          | 0.976    | 1.061    |
| dav2_small     | 0.999    | 0.976    | 0.992     | 1.047          | 0.931    | 1.061    |

### fraction of restored pixels clamped high

| arm            | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|----------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1 | 0.1016   | 0.0410   | 0.0048    | 0.0252         | 0.0000   | 0.0363   |
| da3mono_large  | 0.1110   | 0.0945   | 0.0049    | 0.0574         | 0.0000   | 0.1191   |
| dav2_small     | 0.0689   | 0.0573   | 0.0048    | 0.0454         | 0.0000   | 0.0729   |

### fraction with EVERY channel on the transmission floor

| arm            | wreck_07 | wreck_05 | cenote_01 | swimthrough_02 | wreck_01 | wreck_03 |
|----------------|----------|----------|-----------|----------------|----------|----------|
| mapanything_n1 | 0.3887   | 0.5877   | 0.0000    | 0.1405         | 0.0000   | 0.4951   |
| da3mono_large  | 0.3323   | 0.6387   | 0.0000    | 0.1911         | 0.0000   | 0.7585   |
| dav2_small     | 0.2602   | 0.5112   | 0.0000    | 0.1863         | 0.0000   | 0.7464   |

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
| da3mono_large  | coastal        | 3.596            |
| da3mono_large  | clear_oceanic  | 2.570            |
| da3mono_large  | turbid_coastal | 3.686            |
| dav2_small     | coastal        | 3.434            |
| dav2_small     | clear_oceanic  | 2.059            |
| dav2_small     | turbid_coastal | 3.613            |

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
| da3mono_large   | wreck_07       | 0.01386    | 0.00895  | 0.01786 | 0.02488 | 3.646            | 2.816         | 0.743       |
| da3mono_large   | wreck_05       | 0.02263    | 0.01004  | 0.05235 | 0.06999 | 4.987            | 3.084         | 0.662       |
| da3mono_large   | cenote_01      | 0.00918    | 0.00843  | 0.01640 | 0.02426 | 2.929            | 2.506         | 0.949       |
| da3mono_large   | swimthrough_02 | 0.02897    | 0.01810  | 0.05067 | 0.06889 | 3.973            | 2.885         | 0.944       |
| da3mono_large   | wreck_01       | 0.00874    | 0.01002  | 0.00619 | 0.00697 | 4.718            | 2.134         | 0.454       |
| da3mono_large   | wreck_03       | 0.01859    | 0.00991  | 0.03106 | 0.06839 | 2.751            | 2.018         | 0.736       |
| dav2_small      | wreck_07       | 0.01955    | 0.00895  | 0.01964 | 0.02491 | 3.870            | 2.816         | 0.743       |
| dav2_small      | wreck_05       | 0.02331    | 0.01004  | 0.05552 | 0.08626 | 4.883            | 3.084         | 0.662       |
| dav2_small      | cenote_01      | 0.00942    | 0.00843  | 0.01678 | 0.02522 | 2.960            | 2.506         | 0.949       |
| dav2_small      | swimthrough_02 | 0.03915    | 0.01810  | 0.06906 | 0.08565 | 4.201            | 2.885         | 0.944       |
| dav2_small      | wreck_01       | 0.00755    | 0.01002  | 0.00503 | 0.00621 | 4.500            | 2.134         | 0.454       |
| dav2_small      | wreck_03       | 0.02942    | 0.00991  | 0.03860 | 0.07175 | 2.985            | 2.018         | 0.736       |

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

18 sheets and 216 crops under `outputs/s6/inspect/`.

Looked for specifically: backscatter or particles turned into depth structure; marine snow; caustics; animal boundaries; artificial-light regions; far-field range collapse; thin structures; colour pumping across frames.

### What the inspection actually showed

Written after viewing the Round-2 sheets and worst-disagreement crops listed in
`round2/outputs/s6/inspect/manifest.json` (CLAUDE.md invariant 5). Sheets viewed:
`wreck_07` f000109, `wreck_05` f000113, `cenote_01` f000200, `swimthrough_02`
f000089, `wreck_01` f001855, `wreck_03` f000317, plus the §18 artifact
`round2/outputs/thin/crane_f000109.png`. This is a THREE-arm run with the Part-A
convention repair applied to `da3mono_large`; the Round-1 notes for the two-arm
pre-repair run are not reused, and one Round-1 claim is retracted below.

**RETRACTED: "DA3 fills the thin crane lattice with a solid opaque surface."** The
Round-1 S6 report asserted that on `wreck_07` f000109 `da3mono_large` fills the
crane's lattice where the reference and `mapanything_n1` leave holes. Two
independent pieces of Round-2 evidence say that claim was wrong, and the second
explains how it was reached:

- §18, which exists precisely to adjudicate this, measures `fill = log(r_sea/r_open)`
  through the annotated openings at source resolution. Corrected `da3mono_large`
  scores **+0.056**, statistically indistinguishable from the reference's own
  **+0.054** and `mapanything_n1`'s **+0.049**. The arms that actually fill are
  `moge2_vitl` (+0.291) and `wat3r_n1` (+0.239) -- neither of which is in this run.
- On the sheet itself the lattice is BLACK in all four range panels, the reference's
  included. Those pixels carry no multi-view support; they are outside the common
  support and are excluded from every S6 number. The Round-1 reading mistook the
  reference's own missing data for correctly-resolved open water, and S6 -- which
  masks to the reference -- cannot see through-lattice behaviour at all. Only §18,
  which annotates the openings independently, can.

**No hallucinated texture, by construction -- but hallucinated GEOMETRY still arrives
as hallucinated colour.** The instrument is a per-pixel gain and offset; it cannot
invent detail, and scene identity survives intact in every restored frame of every
arm. What a range field can invent is structure, and the clip where that happens is
not `wreck_07`.

**`wreck_05` is a shared failure, not a DA3 failure.** The reference reads this
low-texture lateral pass as a nearly flat far field cut by one diagonal hull edge.
BOTH monocular arms replace it with a smooth corner-to-corner near-far ramp:
`da3mono_large`'s disagreement is strongly positive over the whole lower-right half
and its restoration turns visibly cyan against the reference's green-brown;
`dav2_small` does the same thing with the sign distributed differently (positive over
the upper half) and its restoration is cyan too. The metrics rank them in opposite
directions -- DA3 has the worse windowed delta E00 (7.05 vs 4.79), `dav2_small` the
worse windowed radiance error (0.2125 vs 0.1554) -- which is itself the finding: this
is one failure mode of monocular geometry on texture-poor lateral footage, expressed
by both arms, not a property of either model. `mapanything_n1` tracks the reference
here (windowed delta E00 2.56), and that agreement is partly circular.

**The dynamic subject is displaced by BOTH monocular arms, with the same sign.**
`wreck_03` f000317, the diver. `mapanything_n1` reproduces the silhouette and its
range, and its disagreement map is near-neutral across the body. `da3mono_large`
renders the diver as a solid strongly-positive region and restores it visibly warmer
and redder. **`dav2_small` does the same.** Round 1 recorded this as a DA3
scene-identity failure; with a second monocular arm in the run it reads instead as
strict-single-image geometry mishandling an independently moving subject, and
MapAnything's clean body is again partly circular evidence -- the reference was built
by MapAnything multi-view. This clip also has the least support of any (`window_fraction`
0.34 / 0.17 / 0.18) so its numbers rest on the smallest sample.

**The worst disagreements sit where the image carries no evidence.** All three arms'
worst crops on `cenote_01` land in the unlit cave void -- source tiles that are
essentially black -- and on the f000200 sheet all three reproduce the same
top-far/bottom-near banding while differing in broad low-frequency fields, not in
structure. No monocular model can do better there and the reference is not obviously
right either. What matters is that the guess is UNSTABLE: this is exactly the clip
where `mapanything_n1`'s motion-compensated warp error more than doubles against the
reference-driven arm (0.02330 vs 0.00983) and its temporal delta E00 goes from 2.82
to 6.75, while `da3mono_large` (0.00918) and `dav2_small` (0.00942) sit at or below
the reference.

**On the near-planar clip MapAnything's residual is a per-FRAME offset, and Round 1
called that benign too readily.** `wreck_01` f001855: `mapanything_n1`'s signed
disagreement is a near-uniform single-signed field over the entire portrait frame,
where DA3's and dav2's are near-white with a warm bloom along the bottom edge. The
S6 gauge is fit at CLIP level, so a spatially uniform residual on one frame is not
the benign constant of FREEZE C7 -- the constant part is already absorbed. What is
left is the frame-varying part, which `beta -> beta/s` cannot absorb, and it shows up
in this clip's windowed colour pumping: 1.11 for MapAnything against 0.38 for DA3 and
0.53 for dav2.

**Far-field over-gain is visible, not merely numerical -- in both monocular arms.**
`swimthrough_02` f000089: DA3 and dav2 both put the central swim-through channel much
deeper than the reference and both blow it out to bright cyan, while the reference and
MapAnything keep it continuous with the surrounding water; `dav2_small` additionally
shows a solid black over-subtraction lobe at top centre. On the same frame the
reference range is riddled with holes tracing the fine coral branches while all three
monocular fields are dense there -- so on reef footage a large part of what this
comparison CANNOT see is the reference's own missing data, excluded from common
support rather than counted against anyone. That exclusion is systematic and it runs
in the monocular arms' favour on exactly the thin structure they are worst at.

**Colour relationships are unnatural in EVERY arm, the reference included.** All
coastal restorations sit orange-brown against a green-blue source (red over-corrected
at around 7 m), and `wreck_01`'s far corner blooms red in all four rows. That is the
fixed Jerlov-bracketing coefficients, not any range field -- Week 6 owns the
coefficients. Recorded so the S6 tables are not misread as a claim that this
restoration looks right. It is a differencing instrument, not a deliverable.

**Black regions in the restored panels are reference-invalid pixels and depth-edge
over-subtraction, not model output.** They are excluded from every number above.

## Provisional classification

```text
ADEQUATE / DEGRADED / UNSAFE
relative to the CURRENT WEEK-3 HYPOTHESIS
```

Judged against the Week-3 error budget (LOG.md): the local relative range error at
which the worst channel's restored radiance error reaches 5% is 9.4% at 3 m and 6.1%
at 8 m in the coastal regime, 12% and 8.5% clear oceanic. The directly comparable
measurement is the responsive-window median |relative radiance error|. Three arms run
here: the incumbent `mapanything_n1`, the Part-A-CORRECTED `da3mono_large`, and
`dav2_small`, which §19 retained on S4 and which had never had S6 run at all.

**Control.** `mapanything_n1`'s Round-2 numbers are bit-identical to Round 1 on every
clip and every water type -- verified by direct comparison of the two raw files, 0
differing scalars. The recompute changed nothing it should not have; every DA3
movement below is the convention repair and nothing else.

- `mapanything_n1`: **DEGRADED.** 3.9-19.0% radiance error in the responsive window
  (median **10.4%**), roughly twice the criterion. It is the best of the three on the
  criterion metric -- and on `wreck_07` at 3.9% it is the ONLY arm/clip combination in
  this round that meets the 5% budget at all. Its static colour difference is also the
  most bounded and the most uniform across clips (windowed median delta E00 1.83-2.93). Its hazard is temporal,
  not static: the highest windowed colour pumping of the three on five of six clips
  (median 0.906 against 0.336 and 0.492), and on `cenote_01` it more than doubles the
  motion-compensated warp error against the reference-driven arm (0.02330 vs 0.00983)
  and lifts temporal delta E00 from 2.82 to 6.75 while both other arms sit at or below
  the reference. The `wreck_01` sheet shows the mechanism: a spatially uniform
  single-signed residual AFTER a clip-level gauge fit is the frame-varying part of the
  scale, which `beta -> beta/s` cannot absorb. Pre-C2 its lead on the static metric is
  also the arm's weakest evidence, because the reference was built from MapAnything
  multi-view and agreement is partly circular.

- `da3mono_large` (corrected): **DEGRADED.** 7.2-22.2% radiance error (median
  **16.2%**), the worst of the three on the criterion metric. **Round 1's "approaching
  UNSAFE on low-texture lateral footage" verdict is WITHDRAWN.** It rested entirely on
  `wreck_05`, and the convention repair moves that clip from 33.3% radiance error /
  windowed delta E00 7.78 / p95 16.1 to **15.5% / 7.05 / 14.9**. Nothing in the
  corrected run is six times the criterion; the worst clip is now `wreck_01` at 22.2%.

  Reported straight, because it cuts the other way too: the repair did not simply
  improve DA3. It redistributed. OLD -> CORRECTED windowed radiance error per clip:
  `wreck_07` 0.134 -> 0.168, `wreck_05` **0.333 -> 0.155**, `cenote_01` 0.064 -> 0.072,
  `swimthrough_02` 0.092 -> 0.097, `wreck_01` 0.224 -> 0.222, `wreck_03` 0.089 ->
  **0.204**. Median 0.113 -> 0.162. The correction removed one catastrophic clip and
  raised the ordinary ones, so DA3's corrected MEDIAN is worse than its uncorrected
  median while its worst case is far better. The corrected numbers are the valid ones
  -- the old fit was absorbing a z-vs-range convention error into `s` and `t` -- but
  "the repair helped DA3" is not what the data says.

  Two Round-1 scene-identity charges against DA3 do not survive Round 2. The crane
  lattice fill is **retracted** on §18 evidence (DA3 `fill` +0.056 vs reference +0.054;
  the fillers are `moge2_vitl` and `wat3r_n1`, absent from this run). The `wreck_03`
  diver displacement is **confirmed but not unique** -- `dav2_small` displaces the
  diver the same way with the same sign. Counter-evidence, stated rather than buried:
  DA3 is the most temporally stable arm here, with the lowest windowed colour pumping
  on four of six clips (`dav2_small` takes `cenote_01`, `mapanything_n1` takes
  `wreck_03`) and lag-1 warp error at or below the reference-driven arm on five.

- `dav2_small`: **DEGRADED.** 5.8-21.3% radiance error (median **13.4%**), between the
  other two. No Round-1 S6 exists for it, so there is no OLD column: this arm was
  eliminated in Round 1 before S6 and only re-entered via the §4 semantic repair. Its
  profile is genuinely different from DA3's despite both being monocular relative-depth
  arms: it has the lowest windowed delta E00 of the three on `wreck_07` (1.60 against
  2.13 and 3.70, though MapAnything's radiance error there is the lower: 3.9% vs 5.8%)
  and the lowest radiance error of the three on `swimthrough_02` (7.9% against 9.7% and
  10.6%), while being the worst of the three on `wreck_05` (21.3%). Its §18 separation (`gap` +0.165) is real but far short of corrected DA3's
  +0.411, and it erases 21% of the annotated members against DA3's 4%. It is
  temporally the middle arm. Nothing here promotes it over either incumbent; it is
  retained as a survivor, not as a leader.

**No arm is ADEQUATE against the Week-3 budget on this footage.** The criterion metric
orders them `mapanything_n1` 10.4% < `dav2_small` 13.4% < `da3mono_large` 16.2%, all
at least twice the 5% budget, and the temporal metric orders them in the opposite
direction. Pre-C2 that split is not resolvable: there is no independent anchor that
says whether static agreement with a MapAnything-derived reference or temporal
steadiness is the better evidence of correct geometry.

Four limits on how far that verdict travels:

1. **Pre-C2 the reference is a hypothesis, not ground truth.** The reference's own
   restoration health is worst on exactly the clips where disagreement is worst --
   median responsive fraction 0.38-0.49 on `wreck_05` and 0.17-0.34 on `wreck_03`,
   with the inversion asking for p99 gains of 1e8.
   DEGRADED is a statement about the magnitude of disagreement relative to the budget,
   not a proof that the monocular side is the side that is wrong.

2. **The common-support mask is the reference's, and it hides the monocular arms'
   worst structural failure.** Wherever the multi-view reference has no support -- the
   `wreck_07` crane lattice, the `swimthrough_02` coral branches -- those pixels are
   excluded from every S6 number while the monocular fields are dense there. S6
   therefore cannot see thin-structure behaviour at all. §18 is the only measurement in
   this round that can, and it must not be substituted for by an S6 reading.

3. **Every arm, reference included, makes the footage temporally worse than its own
   unprocessed input** at lag 1 on five of six clips (reference/input warp ratios
   1.17-3.73; `wreck_01` is the one exception, at 0.73). A range-driven inversion with fixed coefficients amplifies
   per-frame range noise into colour. That is a property of the instrument: the
   temporal rows are arm-vs-reference comparisons, never arm-vs-nothing.

4. **`turbid_coastal` is not measurable on this footage and its row above should not be
   used.** The transmission floor swallows the frame: every channel is floored on 100%
   of pixels for four of six clips under `da3mono_large`, three under `dav2_small` and
   two under `mapanything_n1`, and the median responsive window is 0.000 or near it on
   two to four clips per arm. The measurable regimes here are `coastal` and `clear_oceanic`;
   both rank the arms the same way.

S6 does not produce the final objective Week-4 winner. Pre-C2 there is no
independent anchor, so a monocular-vs-reference disagreement cannot say which side
is wrong.
