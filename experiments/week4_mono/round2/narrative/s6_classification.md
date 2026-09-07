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
