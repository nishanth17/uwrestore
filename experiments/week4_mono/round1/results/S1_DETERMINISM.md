# S1 — determinism and numerical noise floor

**Stage:** S1 of the frozen Week-4A sequence. **All seven models continue.**

Everything after this stage is a difference — S3's residual against the Week-3
reference, S4's response to an appearance perturbation, S5's frame-to-frame
trajectory, S6's restoration delta. A difference is only evidence if it exceeds
the noise the instrument makes on its own, so each model was run repeatedly on
identical input under identical conditions and the spread of its own output
measured.

Two repetitions, because they answer different questions: **within-process** (same
loaded model, called again) is the floor for S4/S5, where one process sweeps many
frames; **across-process** (fresh process, fresh weight load, fresh MPS context) is
the floor for comparing products persisted on different days.

Subset: the middle frame of `wreck_07` (easy, high texture), `wreck_05` (hard, low
texture), `cenote_01` (widest near/far span) and `wreck_01` (PORTRAIT). Three
within-process repeats plus two independent processes each. FREEZE S1 explicitly
does not ask for the 288-frame set here, and it would not answer this question
any better.

## Result

| model                   | bitwise | p99 rel floor | median s | min-max s | load s | peak RSS GB | peak MPS GB |
|-------------------------|---------|---------------|----------|-----------|--------|-------------|-------------|
| mapanything_n1          | YES     | 0.0e+00       | 1.10     | 1.07-1.34 | 18.3   | 9.6         | 5.1         |
| dav2_small              | YES     | 0.0e+00       | 0.19     | 0.19-0.46 | 0.8    | 0.8         | 1.2         |
| moge2_vitl              | YES     | 0.0e+00       | 2.09     | 2.05-2.30 | 4.5    | 2.8         | 3.1         |
| metricanything_pointmap | YES     | 0.0e+00       | 2.12     | 2.09-2.16 | 4.4    | 2.8         | 3.1         |
| wat3r_n1                | YES     | 0.0e+00       | 1.14     | 1.12-2.04 | 8.0    | 9.2         | 6.1         |
| da3mono_large           | YES     | 0.0e+00       | 0.29     | 0.29-0.41 | 2.7    | 2.9         | 2.1         |
| foundationgeo_11        | YES     | 0.0e+00       | 1.45     | 1.43-1.56 | 4.5    | 2.7         | 3.1         |

**Every model is bitwise reproducible, within process and across processes, on MPS
in float32. The measured noise floor is exactly zero for all seven** — identical
valid masks, identical fields, byte for byte, on all four frames.

That is a stronger result than the freeze required, and it is worth being precise
about what it does and does not license.

**It does license:** reading any nonzero downstream difference as attributable to
the thing that was changed — a view count, an appearance perturbation, a different
frame, an ablated field — rather than to run-to-run variation. There is no
stochastic floor to subtract, and no `>= floor` filter is needed anywhere in
S3-S6.

**It does not license** treating an arbitrarily small difference as *important*.
Zero run-to-run noise is a statement about the estimator's determinism, not about
its sensitivity, and three further floors sit above it and are measured where they
arise, not here:

- the **8-bit PNG quantisation floor**, which every S4 perturbation passes through,
  because perturbed inputs are written to disk before inference;
- the **reference's own uncertainty**, which Week 3 measured and which is large on
  exactly the low-texture clips — whole-pipeline reruns moved `wreck_05` by 2.1-6.5 %
  median while `wreck_07` moved 0.01 %;
- the **restoration sensitivity budget** from Week 3 stage 7 (31 % at 1 m, 12 % at
  3 m, 8.5 % at 8 m), which is what makes a range error consequential rather than
  merely nonzero.

The reference floor is the binding one. A monocular-vs-Week-3 disagreement of a few
percent on `wreck_05` says as much about the reference as about the model, and S3
reports it that way.

## Why it came out zero

No sampling, no dropout, no stochastic augmentation: every model runs `eval()` under
`no_grad`/`inference_mode`. Autocast is off everywhere — MPS supports only bf16 and
fp16 autocast, so the fp32 autocast blocks inside MoGe and FoundationGeo are no-ops
and warn as much, and both MoGe's `use_fp16=True` and FoundationGeo's fp16 default
were explicitly overridden to False. That override is the reason this table is full
of zeros; half precision would have put a stochastic floor under every later delta.
It costs runtime, and the project's standing rule since Week 3 is that a measurement
instrument must be reproducible before it is fast.

## Runtime and memory budget for the stages that follow

Median per-frame inference across all seven models totals **8.4 s**, so one
full 288-frame pass costs roughly **40 minutes** of pure inference for the
whole field — S3 is affordable at full scale, which is what the freeze requires of it.

Peak RSS splits the field in two: the two ViT-G-class multi-view architectures
(`mapanything_n1` 9.6 GB, `wat3r_n1` 9.2 GB) cost about three times the five
monocular models (0.8-2.9 GB). On a 24 GB machine that rules out co-resident
models and confirms the Week-3 rule this bakeoff already follows: one model per
process, with process exit as the authoritative MPS cleanup boundary.

`dav2_small` is the cheapest entrant by a wide margin — 0.19 s and 0.8 GB, roughly
11x faster and 12x smaller than MapAnything. If it survives S3 on geometry, that
ratio becomes a real deployment argument rather than a footnote.
