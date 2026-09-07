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
