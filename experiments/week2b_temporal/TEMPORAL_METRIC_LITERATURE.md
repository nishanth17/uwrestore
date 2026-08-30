# Long-duration temporal-stability diagnostics — comprehensive adversarial literature review

**Advisory research only.** No implementation code was changed, no metric was
implemented, no model or dependency was installed, no bakeoff was run, and
Phase 2B was not reopened. `FINDINGS.md`, `PLAN.md`, `LOG.md` and everything
under `uw/` are untouched.

Question:

> Does the project have a meaningful temporal-evaluation blind spot that
> justifies investigating one additional long-duration diagnostic in Week 8?

**Revision history.** Pass 1 was bounded and concluded "add nothing". Pass 2
covered the video-generation/SR metric literature and time-series statistics
and moved to "carry one candidate". Pass 3 was a broad sweep — at the time
intended as exhaustive, a claim since withdrawn (§13.4): fourteen literatures,
forty-plus searches, formulations extracted directly from source PDFs where
fetchers failed. **The conclusion of pass 2
survives pass 3 unchanged in substance and is much better specified.** Two
things did change: a serious new candidate family surfaced that both earlier
passes missed (§6 C6, the CIE temporal-light-artefact visibility measure), and
the field-level negative result hardened from "I did not find one" to a
documented, multiply-confirmed absence (§5).

**Pass 4** was a dedicated retrieval-and-re-test pass: every source the earlier
passes could not open was attacked again through alternate routes — local PDF
decoding (Flate **and** LZW, the latter added for pre-2000 scanned-era files),
ar5iv mirrors, institutional repositories, standards-sample servers and vendor
documentation — and every rejection was re-tested against the recovered
formulation. **Six of eight blocked sources were recovered; no rejection
changed; the recommendation is unchanged** (§11). Two FR/RR video-quality
models no earlier pass had examined were also tested and rejected. One
genuinely new and project-relevant fact surfaced — *motion silencing*, the
measured perceptual suppression of local flicker by large coherent motion
(§11.7) — which does not alter the recommendation but does change how Week 8
must read its results, and is written into §9 as an interpretation rule.

**Pass 5** was prompted by a correct challenge: a field that obsesses over
flicker cannot plausibly have no flicker metrics. It doesn't. This pass
recovered **Lai et al.'s original `E_warp`** (§12.1) and found **seven
no-reference video flicker metrics**, two of which (CTI, FDI) no earlier pass
had reached, and one of which (Guthier et al.) operates on exactly the 1-D
brightness trajectory recommended here — plus a genuinely novel
compression-based family (OMIQ). **§5's claim that the instrument "does not
exist as a video metric" is withdrawn and corrected.** Every recovered metric
was then re-tested and still rejected, on specific grounds recorded in §12.
Pass 5 also ran an adversarial review of every option including the
recommendation itself (§13), which survives but now carries **three mandatory
adoption conditions**, and demotes the perceptual runner-up. §13.4 gives a
four-axis completeness argument showing which cell of the design space is
empty and why.

**Pass 7** was the final editorial and statistical cleanup: §1 rewritten to
match the decision tree rather than naming a "primary" test, stale pre-pass-6
cells purged from §2/§6/§8/§11.9/§13.3, §9 marked historical, and three
substantive statistical safeguards added — wavelet multiplicity over the
time–frequency plane, multiplicity above the individual trace, and the
selection-bias hazard in "exclude peaks then refit". An instrument inventory was
added as §16.1. **No new literature result overturned §16.** This document is
now considered freezeable; the remaining uncertainty is empirical, not
bibliographic.

**Pass 6** applied an independent review that checked this document's claims
against primary sources and searched beyond its candidate set. It confirmed the
architectural conclusion and found **six factual errors** (corrected in place,
each marked *Correction (pass 6)*), **three statistical overclaims**, and **one
genuinely missed family — time-localised wavelet significance** (Torrence &
Compo), together with cross-wavelet coherence for attribution and two Bayesian /
GP escalation paths. §13.4's "completeness proof" is **withdrawn**. Week 8 is
now specified as a **decision tree** rather than a precommitment to one
statistical test (§15.6), with four consolidated adoption conditions (§15.7).
The title changed from "exhaustive" to "comprehensive adversarial". Final
position: §16.

---

## 1. Executive conclusion

### B. One candidate family worth carrying into Week 8 — as a decision tree.

```text
Family:  periodicity / whiteness / trend analysis of physical-parameter
         trajectories, in parameter space.
Test:    NOT chosen in advance. Characterise the noise first, then branch:
             stationary, phase-coherent pumping
                 -> validated continuum + multitaper / periodogram significance
             transient, bursty, frequency-wandering pumping
                 -> time-localised wavelet power with a validated background
             ambiguous attribution
                 -> cross-wavelet coherence against covariates
Companions: whiteness (Ljung-Box), drift (Sen slope + autocorrelation-aware
         significance), spikes (robust z on max |delta p|).
Domain:  parameter space. NOT an addition to the frozen image metrics.
```

The full design is §15.6; the adoption conditions are §15.7. **Do not read this
section as a precommitment to one statistical test.** An earlier version named
Vaughan or Thomson as "the primary", and pass 6 withdrew that for a good reason:
the estimator whose noise those tests assume does not exist yet.

One family. The frozen Phase 2B evaluator — raw and illumination-aware
MC-Warp@1/@4/@8, alignment-robust companion, temporal ΔE00, coverage/status,
input baselines — is unchanged. Nothing is added to it, nothing retuned, no lag
added, no weighted score invented.

Why this family and not one of the forty-odd alternatives in §7 and §12:

1. **The question is a hypothesis test, and no video metric reviewed performs
   one.** "Is there periodic pumping in this trajectory, or is it noise?" needs a
   null distribution. Every image-space candidate found returns a bare scalar.
   Phase 2B already learned what that costs: the `lights` @1 cell has a 39 %
   anchor spread and is unusable *as a number*, with no principled way to say how
   large a change must be to mean something.
2. **No fixed lag, so no aliasing blind spot** of the kind `{1, 4, 8}`
   demonstrably has.
3. **Four of the five confounds that make the image-space question hard do not
   arise** — blur gaming, the subpixel resampling floor, correspondence masking,
   coverage decay — because nothing is warped, masked, or resampled (§8).
4. **A strong methodological precedent.** Functional MRI quality assurance has
   decomposed long-run imaging-system instability into separate trace-level
   diagnostics since 2006 (§6 C5).
5. **Cost is effectively zero**: numpy only, and the traces are a byproduct of a
   run that has to happen anyway.

**Free instruments available immediately, before any estimator exists** (§17):
the per-frame log-average brightness trace on input and corrected, and an x–t
spatio-temporal slice. Neither is an addition to the frozen metrics.

**Conditional instruments valid on `murky_shark` only** (§17): long-range anchor
warp error and Eulerian Video Magnification both fail elsewhere *because of
camera motion*, and that clip barely moves.

**This is carried to be tested, not adopted.** There is still no demonstrated
long-duration failure (§4). §9 gives the minimum experiment and the criterion
that kills the candidate.

**The one strong runner-up, and why it is second not first.** CIE TN 006's
visibility measure combined with the elaTCSF sensitivity function (§6 C6) is a
free, standardised, no-reference, frequency-domain instrument that answers
*"would a human see this?"* with an absolute threshold at 1.0 — which is
exactly the "how big is too big" question Phase 2B correctly refused to
hard-code. It is second because its sensitivity curve is calibrated for
full-field light modulation on a display, and transferring it to "the estimated
attenuation coefficient oscillates 3 %" assumes a mapping from parameter
oscillation to perceived luminance modulation that nobody has validated. This
project has already faced that exact choice once and got it right: Week 1
refused to ship an unvalidated Protune curve rather than fabricate one
(`LOG.md`, 2026-08-22). The same standard applies here. Detection first, with
no perceptual assumptions; visibility second, if and when detection fires.

---

## 2. What this review covered, and how

Fourteen literatures were searched. For each candidate that receives analysis
below, the actual mathematical formulation was read — from HTML where
available, and otherwise by extracting text from the source PDF locally when
the fetcher returned only binary. Candidates whose formulation could not be
obtained are listed as discarded-for-unverifiability in §7 and are **not**
analysed, per the verification rule.

| literature | representative works reached | yield |
|---|---|---|
| blind video temporal consistency | Lai ECCV'18, Lei NeurIPS'20 / DVP | pairwise warp; formulations recovered in passes 5–6 (§11.1, §12.1) |
| video super-resolution | TecoGAN (tOF, tLP) | pairwise; usable without GT via the input-as-reference variant (§12) |
| video generation benchmarks | VBench, StreamingT2V (MAWE), spatiotemporal-consistency survey 2025 | pairwise; the survey did not identify a long-window, calibrated trajectory metric |
| **video deflickering** | Lei CVPR'23 (All-In-One-Deflicker) | **a deflickering paper with no flicker metric** |
| old film restoration | Wan CVPR'22; van Roosmalen; Pitié & Kokaram | E_warp; α(t),β(t) correction models |
| video demoiréing / colorization / low-light | RWE, CDC, MABD | pairwise, mostly full-reference |
| underwater video enhancement | Du arXiv'24, WaterWave'25 | MABD/CDC or aesthetic NR scores |
| video depth, long sequences | Video Depth Anything CVPR'25 (TAE), OPW | consecutive-frame and GT-referenced; consistency *is* evaluated quantitatively, but no transferable NR long-trajectory drift test |
| video stabilization | Liu SIGGRAPH'13 stability score; ATE/RPE from SLAM | trajectory-spectral, but sign-inverted for us |
| video coding flicker | H.264/HEVC I-frame flicker metrics | full-reference, static-region, GOP-period |
| perceptual video metrics | ColorVideoVDP TOG'24, FovVideoVDP TOG'21 | full-reference; real temporal channels |
| **display / lighting flicker metrology** | **CIE TN 006:2016**, IEC 61000-4-15, JEITA/VESA, **elaTCSF SIGGRAPH Asia'24** | **a genuine no-reference 1-D visibility measure** |
| tone mapping temporal artifacts | Boitard et al.; Eilertsen CGF'13; Guthier SPIE'11 | recovered in passes 5–6: taxonomy plus a per-frame brightness trace read qualitatively; Guthier adds a JND detector (§12.2) |
| **time-series statistics & estimator diagnostics** | Welch, Thomson, Fisher, **Vaughan'05**, Lomb–Scargle, **RobustPeriod SIGMOD'21**, specparam, Ljung–Box, Allan/Hadamard, Mann–Kendall/Sen, PELT, CUSUM/EWMA, RQA, DFA, spectral kurtosis, Kalman NIS/whiteness | **the instruments that actually fit** |
| **imaging-system stability QA** | **fMRI QA: Friedman & Glover JMRI'06**, Weisskoff RDC, TIM JMRI'24; remote-sensing radiometric drift | **an established protocol of exactly this shape** |

---

## 3. What the current evaluator already covers

| failure mode | covered by | evidence |
|---|---|---|
| frame-to-frame chroma flicker from correction | raw + illumination-aware MC-Warp@1, temporal ΔE00 | injected-flicker sweep; gray-world 2.05–2.73× on four clips |
| instability at 4- and 8-frame separation | MC-Warp@4/@8 | `murky_shark` reduction ratio 1.37 → 2.45 with lag |
| legitimate global exposure / ambient change | bounded gain/bias fit on aligned originals, frozen before scoring | synthetic C/D reach exactly 0.000000; case E unchanged at 0.034508 |
| legitimate *local* illumination | not corrected — labelled `illumination-confounded` | `lights` at all three lags; synthetic case I |
| how much of the frame was measured | valid coverage@k, ΔE coverage, `low-coverage` | case J: raw → 0 at 43.8 % coverage, and says so |
| resampling vs instability | alignment-robust companion + per-clip synthetic floor | 11 %–115 % of measured MC-Warp@1 |
| is the number real or sampling noise | three-anchor-triple spread | 1–6 % most cells, 17 % / 39 % on two |
| single-frame spike | per-pair values retained, not only pooled | case F: {0, 0, 0.100, 0.100, 0} |

**The exhaustive pass established something worth recording: on the pairwise
axis the frozen stack is at or ahead of the published state of the art.**

* **MAWE** (StreamingT2V 2024) is `W(V)/(c·OFS(V))` — warp error divided by mean
  optical-flow *magnitude*. **Correction (pass 6): this is not the project's
  motion-reduction ratio**, and an earlier version wrongly said it was. Ours is
  `uncompensated residual / motion-compensated raw MC-Warp`. MAWE normalises by
  how much the scene moved; ours reports how much of the unaligned frame
  difference geometric compensation removed. Different normalisers, different
  questions. MAWE is still rejected — another pairwise flow/photometric
  statistic — but not for being a duplicate.
* **tOF / tLP** (TecoGAN, ACM TOG 2020). **Correction (pass 6): these do not
  inherently require ground truth.** For supervised super-resolution they use a
  reference, but TecoGAN explicitly adapts them to *unpaired* video translation
  by taking the motion/perceptual-change trajectory of the **input** as the
  reference — which is available to us. They are still rejected, on the correct
  grounds: both are short-range consecutive-frame statistics that do not address
  long-duration periodicity or drift; tOF asks whether output *motion* differs
  from input motion (a geometry/task-preservation question, not a stability
  question); and tLP introduces LPIPS, a learned perceptual representation.
  **tLP is worth retaining as a candidate Week 9 task-preservation
  diagnostic**, not as Week 8's missing instrument.
* **RWE** (video demoiréing, 2022) requires ground truth.
* **MABD** requires ground truth and uses no flow; **CDC** is a
  consecutive-frame colour-histogram divergence with no flow. Both are
  motion-confounded — on a swim-through they measure the swim.
* **VBench temporal flickering** is evaluated on **deliberately static
  scenes** — it does not mask motion, it selects videos that have none (§11.2),
  so it is undefined for our footage.
* **TAE** (Video Depth Anything, CVPR 2025) needs GT depth and camera poses.
* No work in any of these lines reports coverage, an illumination confound, a
  resampling floor, or a metric error bar. Phase 2B reports all four.

---

## 4. The actual remaining blind spot

### Known mathematical limitation — proved, synthetic

MC-Warp@k compares frames `t` and `t+k`; an oscillation whose period divides
`k` sits on the same phase in both. Measured: raw 0.046289 @1, **exactly
0.000000 at @2 and @4**. The `{1,4,8}` set is blind to period-2 at two of three
lags and to period-4 at two of three lags.

* **Slow pumping and drift are unrepresented at any lag.** The largest
  separation the evaluator forms is 8 frames — 0.27 s at 30 fps. A 0.2 Hz
  oscillation or a 30 s drift shows only as a slightly elevated @8 value, with
  no signature distinguishing it from a noisier clip.
* **Aggregation destroys the trajectory.** Three anchor triples per clip per lag
  are pooled to one scalar. The evaluator emits points; the question is a curve.
* **No quantity in the stack has a null distribution.** Phase 2B measured its
  own sampling spread empirically and correctly refused to hard-code a
  threshold. The consequence is that the project cannot currently say *"this
  oscillation is not noise, p < 0.01"* about anything.

### Demonstrated real pipeline failure

**None**, and this survives the exhaustive pass. No temporal correction stage
exists, no physical parameter estimator exists (Weeks 5–6), every temporal
number so far comes from 41-frame windows, and the only pipeline ever measured
fails so loudly at @1 that no long-duration instrument was needed.

---

## 5. Field-level finding: NR flicker metrics exist, but not of the needed shape

> **Correction (pass 5).** An earlier version of this section claimed "the
> instrument does not exist as a video metric". That was too strong and is
> withdrawn. **No-reference video flicker metrics exist in quantity** — §12
> catalogues seven of them, including two (CTI, FDI) that earlier passes missed
> entirely, and one (Guthier et al.) that operates on exactly the 1-D brightness
> trajectory this report recommends. The accurate claim is narrower and is what
> the rest of this section supports: **no published metric is simultaneously
> no-reference, robust to large camera motion, and trajectory-based over a long
> window with a calibrated null.** Every existing flicker metric fails at least
> one of those three.

This is the most reusable result of the review, and it is now supported by five
independent confirmations rather than by absence of evidence.

1. **A 2025 survey of spatiotemporal consistency in video generation**
   (<https://arxiv.org/html/2502.17863v1>) names **no** temporal metric using
   frequency analysis, autocorrelation, periodicity detection, drift statistics,
   or multi-frame trajectory analysis. Every temporal metric it cites is a
   pairwise consecutive-frame comparison. Its own §7: current metrics "are
   mostly borrowed from the image field. They overlook the temporal information
   in videos and are unable to evaluate dynamic content."
2. **The state of the art in blind video *deflickering* has no flicker metric.**
   Lei et al., CVPR 2023 — a paper whose entire subject is removing flicker —
   evaluates with `E_warp^t = E_pair(O_t, O_{t−1}) + E_pair(O_t, O_1)`, i.e.
   warping error to the previous frame plus to the first frame, and resolves
   the rest with human A/B preference. If a dedicated flicker metric existed,
   that paper would use it.
3. **Long-video depth consistency is evaluated quantitatively, but not with a
   transferable drift statistic.** *(Correction (pass 6): an earlier version said
   the field had "no drift metric" and documented drift "only qualitatively" —
   that overstated it. Video Depth Anything (CVPR 2025) explicitly targets
   arbitrarily long videos and does evaluate temporal consistency
   quantitatively.)* The accurate statement: its temporal evaluation revolves
   around local/adjacent-frame depth consistency using ground-truth depth and
   camera poses (TAE), so **among the methods reviewed I found no directly
   transferable no-reference long-trajectory drift/periodicity test** of the kind
   needed here.
4. **"Frequency-domain temporal consistency" in video means something else.**
   FreMOTR (ACM MM 2022) sounds like the missing instrument; on reading, its
   Fourier transform is the **2-D spatial DFT of each frame**, and its Temporal
   Amplitude/Phase Change terms are **adjacent-frame differences of those
   spatial spectra** — a full-reference training loss, not a temporal-trajectory
   analysis.
5. **Underwater and old-film restoration inherit the same pairwise toolkit** —
   MABD/CDC and E_warp respectively.

The one genuine exception found in vision is the video-stabilization "stability
score", which *is* a trajectory-spectral measure — and is sign-inverted for our
purpose (§6 C7).

**Conclusion: the instrument this project needs is not a video metric. It exists
as ordinary time-series statistics, and as a QA protocol in imaging fields that
have had to certify long-run temporal stability for decades.**

---

## 6. Candidate comparison — finalists (pre-pass-6; read with §15)

> **Read with §15.** This section and its summary table were written before the
> pass-6 corrections. It does not include time-localised wavelet significance,
> which is now a first-class branch (§15.1), and a few table cells retain
> pre-pass-6 shorthand that the prose elsewhere has since corrected. Where they
> disagree, §15 governs.

Only candidates that plausibly add information beyond
`MC-Warp@1/@4/@8 · illumination-aware MC-Warp · temporal ΔE00 ·
alignment-robust warp · coverage/status · parameter-trace inspection`.
Everything else is catalogued in §7.

---

### C1 — Trials-corrected periodicity test against a fitted noise continuum ← **carried**

Two interchangeable primary instruments; pick one at implementation time.

#### C1a — Vaughan (2005) red-noise periodogram test

**Identity.** S. Vaughan, "A simple test for periodic signals in red noise",
*Astronomy & Astrophysics* 431:391–403, 2005; arXiv:astro-ph/0412697.

**Exact measurement.** The periodogram

```text
I(f_j) = (2 dT / (<x>^2 N)) |X_j|^2
```

is distributed about the true spectrum as `I(f_j) = P(f_j) · chi^2_2 / 2`.
Because the scatter is multiplicative, a power-law continuum `P(f) = N f^-alpha`
is fitted by **least squares on the log-periodogram**, where the scatter becomes
additive and identical at every frequency. The test statistic for a candidate
peak is the ratio

```text
gamma_j = 2 I_j / P_hat_j
```

whose distribution folds in the log-normal uncertainty of the fitted continuum,
and the threshold is corrected for the number of independent frequencies
examined:

```text
integral from gamma_eps to infinity of p(z) dz  =  1 - (1 - eps)^(1/n')  ~  eps / n'
```

**Why this matters for us specifically.** A physical-parameter estimator's noise
is **likely** to be red rather than white — successive frames share scene
content, and estimator error is correlated. Every naive periodicity test
(Fisher's g, Lomb–Scargle false-alarm probability) assumes a **white** null and
silently produces spurious significance under red noise; VanderPlas (2018) says
so explicitly of Lomb–Scargle FAP. Vaughan's test is built precisely to avoid
that failure, and it handles the multiple-comparison problem that arises from
scanning hundreds of frequencies.

#### C1b — Thomson multitaper harmonic F-test

**Identity.** D. J. Thomson, "Spectrum estimation and harmonic analysis",
*Proc. IEEE* 70(9):1055–1096, 1982; formulation verified in Patil et al.,
<https://arxiv.org/html/2405.18509>.

**Exact measurement.** With DPSS (Slepian) tapers `v_{k,n}`, eigencoefficients
`y_k(f) = sum_n v*_{k,n} x_n exp(-i 2 pi f t_n)`, least-squares line amplitude
`mu_hat(f) = [sum_k U_k(N,W;0) y_k(f)] / [sum_k U_k(N,W;0)^2]`, and

```text
F(f) = (K-1) |mu_hat(f)|^2 sum_k |U_k(N,W;0)|^2
       / sum_k | y_k(f) - mu_hat(f) U_k(N,W;0) |^2
```

distributed as **F(2, 2K−2)** under "no strictly periodic component at `f`".
It is an analysis of variance: variance explained by a phase-coherent sinusoid
against residual variance. The verified source states it is "extremely sensitive
to (and preferentially picks) strictly periodic signals", performs well on
**short** records (variance falling as 1/T³), resolves below the Rayleigh limit,
and its F-value "does not depend — to first order — on the magnitude of the
noise".

**Known weakness, stated up front.** It tests for *strictly periodic,
phase-coherent* components. Quasi-periodic pumping whose frequency wanders —
the plausible real case if an estimator is driven by swell or fin cadence — is
what a phase-coherent test under-detects. Keep the plain Welch PSD alongside
it: a broad hump is visible there and invisible to the F-test.

#### Shared assessment

**Reference class.** No-reference / blind. Only the 1-D trace, evenly sampled.
No clean target, no flow, no segmentation, no pretrained network, no labels.

**Periodic-flicker sensitivity.** Period-2 (Nyquist), 3, 4, 5 and arbitrary
non-aligned periods are all just frequencies. There is no lag to alias against.
Resolution for 900 samples at 30 fps:

```text
period 2  -> 15.0 Hz = exactly the Nyquist bin
period 3  -> 10.0 Hz     period 4 -> 7.5 Hz     period 5 -> 6.0 Hz
nperseg 256, 50% overlap -> 6 averages, df = 0.117 Hz -> slowest period ~8.5 s
nperseg 512, 50% overlap -> 2-3 averages, df = 0.059 Hz -> slowest period ~17 s
```

Two consequences to write into Week 8's report *before* collecting data.
Period-2 lands exactly on the Nyquist bin — present, but the bin most exposed to
windowing and leakage and carrying no phase — so pair it with the exact
period-2 detector, `mean((-1)^t · p_detrended(t))`, equivalently lag-1
autocorrelation → −1. And **a 30 s clip cannot separate a ~30 s-period
oscillation from drift**; anything slower than about a third of the record must
be reported "unresolved", never as one or the other.

**Slow drift.** Not this instrument's job. Fit and report drift separately —
which is also NIST SP 1065's advice for stability analysis: "It is usually best
to use a stability plot only to show the noise, and analyzing and removing the
drift separately." Use **Sen's slope** as the robust effect-size estimator (the
median of all pairwise slopes) together with an **autocorrelation-aware trend
test**.

**Correction (pass 6):** an earlier version proposed plain Mann–Kendall and
called Sen's slope "strictly better than OLS". Both are wrong. Standard
Mann–Kendall assumes serial independence, and positive autocorrelation inflates
its Type-I error — which matters here precisely because these traces come from
consecutive video frames and this report's own premise is that they are serially
dependent. Use a prewhitened or variance-corrected Mann–Kendall variant, or a
GLS/state-space trend test, and validate the choice synthetically. And Sen's
slope is more *robust* than OLS, not strictly better: OLS is more efficient when
its assumptions hold.

**One-frame spike.** Missed by both, and by the PSD, and by ADEV (NIST §11.6:
the ADEV of a record with a large spike has a τ^−1/2 characteristic — a spike
*disguises itself as white noise*). A separate robust z on `max |Δp|` is
mandatory, not optional.

**Blur gaming: immune, structurally.** Parameters are estimated from the input,
so blurring the output changes no parameter trace at all. This is the sharpest
advantage over every image-space candidate. Phase 2B case G measured blur
cutting a photometric temporal score by 64 %, and TecoGAN's authors
independently state that pixel-wise temporal metrics are "easily deceived by
very blurry results".

**Legitimate illumination: not immune, and the underwater case is nameable.**
Caustics under swell oscillate near 0.15–0.5 Hz; fin cadence sits near
0.5–1 Hz; a hand-held or camera-mounted light sweeps at whatever rate the diver
moves. All are real radiance changes a correct estimator *should* track. A
significant peak is therefore not evidence of instability on its own: the same
test must be run on an input-derived covariate (frame-mean linear luminance of
the ORIGINAL footage, camera-motion magnitude, range) and the peak attributed.
This mirrors the frozen evaluator's existing discipline of always reporting the
`--method none` input baseline beside the corrected number.

**Motion, correspondence failure, subpixel resampling: do not arise.** No flow,
no mask, no warp, no resampling.

**Moving objects: neither measured nor excluded.** A global parameter trace says
nothing about instability confined to the eel body. This is the candidate's real
limitation and the §9 rejection trigger.

**Cost.** The whole 30 s trace (~900 samples); no image data. CPU, milliseconds.
DPSS tapers come from the tridiagonal eigenvector formulation
(`scipy.signal.windows.dpss` documents exactly this, citing Percival & Walden
1993 and Slepian 1978); for N ≈ 900 a dense `numpy.linalg.eigh` is adequate, so
**no new dependency is forced** — `pyproject.toml` stays numpy + opencv.

**Public implementation: available.** `tapify` (F-test),
`scipy.signal.windows.dpss` (tapers), `scipy.signal.welch` (PSD), `allantools`
(LGPL, ADEV), `statsmodels` (Ljung–Box), `ruptures` (BSD, change points).
None is required; each is short from the equations above.

**Incremental information.** *"There is a periodic component at 3.2 Hz in the
backscatter coefficient, significant at p < 0.001 after correcting for 450
frequencies scanned, carrying 22 % of the detrended variance, with no
corresponding component in the input's own luminance trace."* No quantity in
the frozen stack, and no published video temporal metric found, produces a
statement of that form.

---

### C2 — Ljung–Box portmanteau whiteness test (companion)

**Identity.** G. M. Ljung, G. E. P. Box, *Biometrika* 65:297–303, 1978.

```text
Q* = T (T+2) * sum_{k=1..h} r_k^2 / (T - k)      ~  chi^2(h - K)
```

`T` = length, `r_k` = lag-`k` autocorrelation of the detrended series, `h` =
lags tested jointly. Large `Q*` rejects "this series is white noise".

**Role.** The pre-test. It aggregates evidence across lags `1…h` simultaneously
— so like C1 it has no aliasing blind spot — but names no frequency. If it does
not reject, that is **not** grounds to disbelieve a spectral peak.
**Correction (pass 6): an earlier version made Ljung–Box an authorisation gate
for C1, and that rule is withdrawn.** The two tests have different alternatives
and different power — a narrow, weak spectral line can be significant under a
line test while a portmanteau statistic pooled over lags 1..h stays quiet.
Report them side by side (Ljung–Box for broad serial structure, the line test
for concentrated oscillatory structure) and let neither authorise the other. Two stages of one instrument, in the same way
Phase 2B's illumination fit has an acceptance guard.

It also catches what C1 misses by design: **an over-damped stabiliser that lags
a real transition** leaves correlated but non-periodic residuals, which
Ljung–Box rejects and a harmonic test does not see. That is `PLAN.md` Week 8
§2's requirement — *suppress jitter, follow a true step* — made testable.

**Blur, motion, correspondence, subpixel: as C1.** Drift must be removed first
or the test says only "not white". A single spike is diluted across `h` lags.
Cost: three lines of numpy given the ACF.

---

### C3 — RobustPeriod (the industrial-grade variant of C1)

**Identity.** Q. Wen, K. He, L. Sun et al., "RobustPeriod: Robust Time-Frequency
Mining for Multiple Periodicity Detection", **SIGMOD 2021**,
DOI [10.1145/3448016.3452779](https://doi.org/10.1145/3448016.3452779);
arXiv:2002.09535.

**Exact measurement**, as read from the paper: Hodrick–Prescott trend filtering
to remove trend and mitigate spikes and dips → **MODWT** (maximal overlap
discrete wavelet transform) to decouple the series into scales so different
periodic components are isolated → robust unbiased **wavelet variance** at each
level to rank which scales plausibly carry periodicity → a **Huber-periodogram**
(the periodogram reformulated as an M-estimator, with proven theoretical
properties) with **Fisher's test** applied to it to select candidate period
lengths → **Huber-ACF**, computed from the Huber-periodogram via the
Wiener–Khinchin theorem, to validate the candidates.

**Why it is here.** It is the same instrument as C1, hardened for exactly the
conditions a real parameter trace will have: a trend, outliers, spikes and dips,
and possibly more than one periodicity at once. Its use of Fisher's test on a
*robust* periodogram is the answer to Fisher's classical weakness (a white-noise
null, easily broken by a single outlier).

**Assessment.** No-reference; 1-D trace only. Detects multiple simultaneous
periodicities, which neither C1a nor C1b does naturally. Blur/motion/
correspondence/subpixel do not arise. Cost is still trivial for 900 samples, but
it is materially more machinery than C1 (HP filter + MODWT + robust variance +
M-estimator periodogram). **Recommendation: start with C1; escalate to C3 only
if the real traces prove too contaminated for C1 to be trusted.**

---

### C4 — Overlapping Allan deviation, ADEV(τ) (supporting plot)

**Identity.** D. W. Allan, *Proc. IEEE* 54(2):221–230, 1966,
DOI [10.1109/PROC.1966.4634](https://doi.org/10.1109/PROC.1966.4634). Working
reference read directly: W. J. Riley, *Handbook of Frequency Stability
Analysis*, NIST Special Publication 1065, 2008,
<https://tf.nist.gov/general/pdf/2220.pdf>. Spectral cross-check: V. Ossenkopf,
*A&A* 479:915, 2008,
DOI [10.1051/0004-6361:20079188](https://doi.org/10.1051/0004-6361:20079188).

**Exact measurement.** SP1065 Eq. (6):
`sigma_y^2(tau) = 1/(2(M-1)) * sum_i [y_{i+1} - y_i]^2`, the variance of the
first difference of the τ-averaged series, plotted against τ; the overlapping
form (Eq. 10) reuses every sample at each averaging factor. Ossenkopf's
equivalent view: the variance of the signal convolved with a Haar wavelet of
width L, so an `f^-alpha` spectrum appears as `L^(alpha-1)`. Transfer function
(Eq. 64, Table 15):

```text
|H_A(f)|^2 = 2 sin^4(pi tau f) / (pi tau f)^2
```

**Why it is a supporting plot and not the candidate.** SP1065 §5.27, verbatim:
"These responses have their peaks where the frequency is one-half the sampling
rate, and nulls where it is a multiple of the sampling rate (i.e., at f = n/τ,
where n is an integer)." ADEV at a single τ is a two-sample difference at lag τ
— **the same family as MC-Warp@k, with the same null at τ = n·T**. It escapes
the blind spot only by sweeping τ, which turns the null into a signature
(§11.5: "Nulls in the Allan deviation occur at averaging times equal to the
multiples of the … sinusoidal modulation period … Peaks … at the modulation
half cycles"). NIST's own worked example (§11.4, a 500 s sinusoid in white
noise) settles the comparison: "quite visible in an all tau stability plot as a
null", but "clearly visible in the power spectral density", "less visible in an
autocorrelation plot" — closing with the policy "It is a good analysis policy to
examine the power spectral density when periodic fluctuations are visible on a
stability plot and periodic interference is suspected."

**Where it is uniquely strong.** It shows **timescale-dependent stability** —
how the variability of the trace behaves as you average over longer windows.
That answers a question no spectral test answers well: *does the estimator's
noise average away with longer integration, or does it accumulate?* — precisely
Week 8's "accumulation of small estimation errors". Worth one plot per trace.

**Correction (pass 6): do not import the metrology noise labels literally.** The
canonical slope-to-noise-type mapping (−1/2 white, 0 flicker, +1/2 random walk,
+1 linear drift) is defined for *specific data types and noise processes in
frequency and phase metrology*. An Allan-style variance curve for an attenuation
coefficient is perfectly computable, but "slope ≈ +1, therefore this estimator
has linear frequency drift" is a category transfer that has not been justified
for our quantities. Read the curve as an averaging-behaviour plot first; attach
classical noise-process names only if the mapping is shown to apply.

**Public implementation: available** — `allantools`
(<https://github.com/aewallin/allantools>, LGPL-3.0, PyPI, conda-forge).
Not needed; Eq. (10) is ~10 lines of numpy, and taking an LGPL dependency for
ten lines would violate invariant 8.

---

### C5 — The fMRI quality-assurance protocol (methodological precedent)

**Identity.** L. Friedman, G. H. Glover, "Report on a multicenter fMRI quality
assurance protocol", *J. Magn. Reson. Imaging* 23(6):827–839, 2006,
DOI [10.1002/jmri.20583](https://doi.org/10.1002/jmri.20583); the radius-of-
decorrelation plot is R. M. Weisskoff, *Magn. Reson. Med.* 36:643–645, 1996;
a recent addition is A. Schmidt et al., "A Temporal Instability Measure for fMRI
Quality Assurance", *JMRI*, 2024,
DOI [10.1002/jmri.28748](https://doi.org/10.1002/jmri.28748).

**What it is.** Not a metric — a **protocol**, and the closest existing analogue
to what Week 8 needs. A long phantom acquisition is reduced to a per-volume
signal trace, and the trace is characterised by: temporal SNR (temporal mean
divided by temporal standard deviation in a fixed ROI); signal-to-fluctuation-
noise ratio (mean signal over the standard deviation of the total noise);
percent signal fluctuation (SD/mean, as a percentage); **percent signal drift**
(the low-frequency component, attributed to gradient heating); the **Fourier
spectrum of the residual trace** to expose periodic artifacts; and the Weisskoff
**radius-of-decorrelation** plot, which tracks how the standard deviation of the
ROI mean falls as the ROI grows — a variance-versus-averaging-scale curve of
exactly the same shape as an ADEV plot.

**Why it matters here.** An entire imaging community, facing precisely our
problem — *"is my instrument temporally stable over a long run, and if not is it
drift, a periodicity, or a spike?"* — converged on: reduce to a 1-D trace,
detrend, report drift as its own number, spectrum for periodicity, separate
spike detection, and a variance-versus-scale plot. That is the §8 battery,
independently arrived at and in routine use since 2006. It is the strongest
available evidence that the recommended route is standard practice rather than
improvisation.

**Also worth noting: TIM (2024)** is the eigenratio of the correlation matrix
between all pairs of time points — a genuinely multi-frame statistic with no
fixed lag. It is a *sensitivity* measure for detecting that instability exists,
not for characterising its frequency, and it needs a fixed-ROI phantom-like
setting. Not carried, but it is the only new shape of statistic the whole sweep
turned up that was not already covered by the spectral/ACF family.

---

### C6 — CIE TN 006 visibility measure + elaTCSF (the runner-up)

**Identity.** CIE, *Visual Aspects of Time-Modulated Lighting Systems —
Definitions and Measurement Models*, **CIE TN 006:2016**, freely available at
<https://files.cie.co.at/883_CIE_TN_006-2016.pdf> (read directly). Sensitivity
function: Y. Cai, A. Bozorgian, M. Ashraf, R. Wanat, R. K. Mantiuk, "elaTCSF: A
Temporal Contrast Sensitivity Function for Flicker Detection and Modeling
Variable Refresh Rate Flicker", **SIGGRAPH Asia 2024**,
DOI [10.1145/3680528.3687586](https://doi.org/10.1145/3680528.3687586),
arXiv:2503.16759, code at
<https://www.cl.cam.ac.uk/research/rainbow/projects/elaTCSF/>.

**Exact measurement — frequency-domain framework (TN 006 §4.3).** Normalise the
temporal signal by its mean so amplitudes are level-independent; apply a Hann
window; take the DFT; peak-find and keep peaks at least 1 Hz apart, giving
amplitudes `C_m` at frequencies `f_m`; divide each by the visibility threshold
for a sinusoid at that frequency, `T_m = T_v(f_m)`; combine by Minkowski
summation — TN 006 Eq. (4):

```text
M_v1  =  ( sum_m ( C_m / T_m )^n )^(1/n)
```

Amplitudes outside the range where `T_v(f)` is defined are set to zero. The
interpretation is absolute and is the point of the whole construction:
`M_v1 = 1` means the modulation is **just visible** — 50 % detection by an
average observer; above 1, more likely detected; below 1, less. `n` is the
Minkowski exponent: 2 (Euclidean) as used by Perz et al. and Bodington et al.
for flicker, `n → ∞` (Chebyshev) as used by de Lange (1958), and 3.7 in the
Stroboscopic Effect Visibility Measure of Perz et al. (2014).

**Exact measurement — time-domain framework (TN 006 §4.4),** for modulation that
is *not* periodic, where the frequency method does not apply: filter the
normalised input with a filter whose amplitude response matches the sensitivity
curve; subtract a low-pass version so the short-term mean is zero; square, to
obtain the short-term variance (equivalent to Minkowski `n = 2`); then apply
**order statistics** — for example the 90th percentile, so "the effect will be
visible if there is a probability larger than 10 % of the modulation being more
visible than a periodic waveform at visibility threshold". TN 006 names the
**IEC flickermeter as the example embodiment** of this generic framework, which
means the architecture of the paywalled IEC standard is documented here in a
free source even though its filter coefficients are not.

**The sensitivity curve is now available.** elaTCSF predicts sensitivity as a
function of temporal frequency, luminance, eccentricity and stimulus area:
a luminance term `S_L(L) = k1 (1 + k2/L)^(-k3)`, a frequency–luminance
interaction, an eccentricity decay, and spatial probability summation over area
`E = c^beta * integral of S^beta dA` with fitted `E_thr = 6.53`, `beta = 3.80`;
visibility is the condition sensitivity = 1 at threshold contrast. It is
explicitly built for **low-contrast** flicker rather than the full-on/off
critical-flicker-frequency regime, and the paper criticises the IDMS TCSF for
overlooking luminance, eccentricity and area, and the IEC lighting standards for
resting on contrast sensitivity measured for incandescent lighting. Code is
public.

**Assessment.**

*Reference class:* no-reference. Only a 1-D modulation signal, plus a viewing
context (luminance, area, eccentricity) to select the threshold curve.

*Periodic sensitivity:* direct and frequency-resolved, with an absolute
threshold. *Slow pumping:* covered down to whatever the record resolves; the
flicker sensitivity curve peaks near 8–10 Hz and falls off below ~1 Hz, so very
slow pumping is correctly reported as barely visible — which is a *feature* if
the question is "does it matter" and a *bug* if the question is "is the
estimator misbehaving". *One-frame spike:* the time-domain variant's order
statistics handle it far better than any spectral method. *Monotonic drift:*
essentially invisible, by design.

*Blur gaming:* immune in parameter space, as C1. *Motion, correspondence,
subpixel:* do not arise.

*Cost:* trivial — DFT plus a threshold curve; elaTCSF evaluation is a closed
form. No GPU.

*Public implementation:* **available** (elaTCSF code released; TN 006 free).

**Why it is not carried.** One unvalidated transfer. `T_v(f)` is calibrated for
full-field luminance modulation of a light source or display at a stated
luminance, area and eccentricity. Our signal is "the estimated attenuation
coefficient oscillates 3 %", whose mapping to perceived full-field luminance
modulation is spatially varying, channel-dependent, and unmeasured. Adopting the
curve anyway would import a fabricated calibration into a project that has
already refused exactly that once, deliberately, and recorded why (`LOG.md`
2026-08-22: `protune_flat_to_linear` raises `NotImplementedError` rather than
ship an unvalidated curve). Also, `M_v1` is a point estimate with no null
distribution, so it cannot distinguish a real 0.9 from a noise-driven 0.9.

**When it becomes the right call.** The moment C1 says "there is a periodic
component at 3.2 Hz, p < 0.001" and the next question is "does anyone see it?"
At that point the transfer can be *validated* rather than assumed — render the
corrected sequence with and without the oscillation, measure the actual
full-field luminance modulation it produces, and only then apply the curve. That
is a Week 8+ experiment, not a Week 8 instrument.

---

### C7 — Video-stabilization "stability score"

**Identity.** S. Liu, L. Yuan, P. Tan, J. Sun, "Bundled camera paths for video
stabilization", *ACM TOG* (SIGGRAPH) 2013,
DOI [10.1145/2461912.2461995](https://doi.org/10.1145/2461912.2461995);
formulation verified as restated in Choi & Kweon,
<https://ar5iv.labs.arxiv.org/html/1909.02641>.

**Exact measurement.** "Two 1D profile signals can be made from extracting the
translation and rotation components" of the camera path; then "the ratio of the
sum of lowest (2nd to 6th) frequency energies and the total energy is computed,
and the final stability score is obtained by taking the minimum" — i.e. per axis
`S_i = sum_{n=2..6} |F_i(n)|^2 / sum_{n=2..N} |F_i(n)|^2`, DC excluded, and
`S = min_i S_i`.

**This is the only published trajectory-spectral stability metric in vision, and
it is sign-inverted for us.** All the energy of a monotonic or very slow
trajectory sits in the lowest bins, driving `S → 1`: **slow drift scores as
excellent stability**. For camera paths that is correct — slow motion is the
intended motion. For a restoration parameter, slow pumping and drift *are* the
failure. Its bands are also indices rather than frequencies, so the score
depends silently on clip length, and it carries no null distribution.
**Rejected**, and recorded so the "stabilization already solved this" idea is
not re-explored.

---

### C8 — ColorVideoVDP / FovVideoVDP

**Identity.** R. K. Mantiuk et al., "ColorVideoVDP: a visual difference
predictor for image, video and display distortions", *ACM TOG* 43(4), 2024,
DOI [10.1145/3658144](https://doi.org/10.1145/3658144), arXiv:2401.11485,
project page <https://www.cl.cam.ac.uk/research/rainbow/projects/colorvideovdp/>;
predecessor FovVideoVDP, *ACM TOG* 40(4), 2021.

**Exact measurement.** A psychophysical visual difference predictor between a
**test and a reference** video, given a display specification (peak luminance,
black level, gamut, resolution, viewing distance, ambient reflectivity) and a
colour encoding. Temporal vision is modelled by castleCSF with **two temporal
achromatic channels — sustained (low-pass) and transient (band-pass) — plus one
temporal channel for each of the red-green and violet-yellow cardinal
directions**, with a filter support of 250 ms. Output: a single quality value in
JOD units, a per-pixel distortion map, and a **distogram** showing distortions
over time per channel and spatial frequency band. The paper explicitly notes an
artifact showing "as low-frequency flicker in the achromatic transient channel".

**Assessment.** The most principled temporal-vision model in the entire sweep,
and the transient achromatic channel is genuinely a flicker detector. But it is
**full-reference**, and this project has no clean reference video — the
corrected output is *supposed* to differ from the input, so feeding the pair to
a difference predictor measures the restoration, not its stability. It also
requires torch and a display model.

**Not carried.** There is one legitimate future use worth recording: run the
pipeline twice over the same clip, once with per-frame parameter estimation and
once with parameters frozen at the clip median, and use the distogram to ask
whether the *difference between those two outputs* is visible and whether it
lives in the transient channel. That is a well-posed A/B with a real reference,
and it is a Week 8+ experiment rather than a metric.

---

### C9 — Long-range / anchor warping error

**Identity.** The long-term variant of warping error: Lai et al., ECCV 2018
(<http://vllab.ucmerced.edu/wlai24/video_consistency/>); Lei et al., NeurIPS
2020 (<https://arxiv.org/abs/2010.11838>); and, in the form actually read this
session, Lei et al. CVPR 2023:

```text
E_pair(O_t, O_s) = || M_{t,s} .* (O_t - warp(O_s)) ||_1
E_warp^t         = E_pair(O_t, O_{t-1}) + E_pair(O_t, O_1)
```

**Rejected.** It is another flow-warp photometric error at another fixed lag,
explicitly excluded by the brief and by `PLAN.md`. Structurally: Phase 2B
already measures coverage falling to 77–89 % at @8 on a 41-frame window; warping
to an anchor tens of seconds away on a swim-through leaves essentially nothing
valid, and §12's rule — two configurations are comparable at @8 only if their
coverage is too — makes the result uninterpretable before it makes it wrong.

---

### Summary table

| | **C1 periodicity test** | C2 Ljung–Box | C3 RobustPeriod | C4 ADEV(τ) | C6 CIE M_v1 + elaTCSF | C7 stability score | C8 ColorVideoVDP | C9 long-range warp |
|---|---|---|---|---|---|---|---|---|
| what it measures | significance of a spectral line vs fitted continuum | joint autocorrelation over lags 1..h | multiple periodicities, robustly | variance of τ-averaged first differences, swept | perceptual visibility of a 1-D modulation | energy fraction in FFT bins 2–6 | perceptual difference test vs reference | warped L1 to a distant anchor |
| reference class | **no-reference** | no-reference | no-reference | no-reference | no-reference | no-ref (camera path) | **full-reference** | no-ref (needs flow) |
| **null distribution** | **yes, trials-corrected** | **yes (χ²)** | yes (Fisher) | no | no | no | no | no |
| period-2 | **yes** (Nyquist bin + sign statistic) | yes (r₁→−1) | yes | null at τ=2,4,… | yes | conflated | yes | inherits aliasing |
| period-4 / arbitrary | **yes, no lag to alias** | yes | **yes, multiple at once** | null at τ=nT | yes | conflated | yes | blind at aligned lags |
| slow sinusoidal pumping | **yes if period ≲ record/3** | yes | yes | bump/null at long τ | yes but down-weighted | **scored "stable"** | yes | no |
| quasi-periodic | Vaughan yes / Thomson weak | yes | yes | broad | yes | conflated | yes | no |
| monotonic drift | via Sen slope + **autocorrelation-aware** significance | after detrend | HP-filtered out | rising at long τ (do not import metrology noise labels) | ~invisible by design | **scored "stable"** | partly | conflated with coverage loss |
| one-frame spike | no (needs robust z) | weak | partly | no (τ^−1/2) | **yes, order statistics** | no | yes | yes |
| blur gaming | **immune** | immune | immune | immune | **immune** | immune | **vulnerable** | **yes, −64 %** |
| legitimate illumination | needs covariates | needs covariates | needs covariates | needs covariates | needs covariates | n/a | partly | partly; `lights` confounded |
| motion / correspondence | **n/a** | n/a | n/a | n/a | n/a | n/a | n/a | full flow + mask |
| subpixel floor | **none** | none | none | none | none | none | none | **recreates it** |
| moving animals | not measured | not measured | not measured | not measured | not measured | n/a | measured | excluded (eel) |
| cost | numpy, ms | numpy, µs | numpy, ms | numpy, ms | numpy, ms | trivial | torch + display model | ~21 min SEA-RAFT / clip |
| implementation | `tapify`, scipy | statsmodels | authors' | `allantools` | elaTCSF released | none standard | released | available |
| verdict | **CARRIED** | **companion** | escalation path | supporting plot | **runner-up** | rejected | not carried | rejected |

---

## 7. Full catalogue of what was examined

Everything reached in the sweep, with its verdict. Entries marked
**unverifiable** were not analysed, per the verification rule.

### Pairwise photometric temporal metrics (all excluded by the brief)

| metric | source | why rejected |
|---|---|---|
| warping error / E_warp | Lai ECCV'18; Lei NeurIPS'20; Lei CVPR'23 | this *is* MC-Warp; long-range variant is C9 |
| tOF, tLP | TecoGAN, ACM TOG 2020, arXiv:1811.09393 | `tOF=‖OF(b_{t−1},b_t)−OF(g_{t−1},g_t)‖₁`, `tLP` likewise in LPIPS space. **Not GT-only** — TecoGAN adapts both to unpaired translation using the *input* as reference. Rejected as consecutive-frame; tOF measures motion preservation, tLP needs LPIPS. tLP = possible Week 9 diagnostic |
| MAWE | StreamingT2V, arXiv:2403.14773 | `W(V)/(c·OFS(V))`, c=9.5 — warp error normalised by scene-motion magnitude. **Not** the motion-reduction ratio (different normaliser); rejected as another pairwise flow/photometric statistic |
| RWE / relation loss | Dai CVPR'22, arXiv:2204.02957 | `‖(O^{t+1}−O^t)−(G^{t+1}−G^t)‖₁` — **full-reference** |
| VBench temporal flickering | Huang CVPR'24, arXiv:2311.17982 | mean absolute difference across consecutive frames on **deliberately static scenes** — motion excluded by construction, not masked (recovered via ar5iv, §11.2). Undefined on all five frozen clips |
| MABD | Du arXiv:2403.11506, after Jiang & Zheng ICCV'19 | per-pixel temporal brightness derivative, no flow, MSE against GT MABD — full-reference, motion-confounded |
| CDC | Liu, *Comp. Vis. Media*, via Du arXiv:2403.11506 | JS divergence of colour distributions between consecutive frames, no flow |
| TAE | Video Depth Anything, CVPR'25 | consecutive-frame reprojection error, needs GT depth + poses |
| OPW | video-depth literature | MC-Warp applied to depth; same family (useful in Weeks 3–4, not here) |
| TAC / TPC (FreMOTR) | ACM MM'22, DOI 10.1145/3503161.3547781 | "Fourier space" is the **2-D spatial** DFT; TAC/TPC are adjacent-frame differences of amplitude/phase spectra — full-reference training loss |
| SSIM / LPIPS / CLIP-Temp / FloLPIPS / TCC / TMC | various | excluded by the brief |

### Trajectory-based but wrongly shaped

| method | source | why rejected |
|---|---|---|
| stability score | Liu SIGGRAPH'13 | C7 — rewards low-frequency-dominated trajectories; scores drift as stable |
| trajectory curvature / perceptual straightening | Hénaff, Goris & Simoncelli, *Nat. Neurosci.* 22:984–991, 2019, DOI 10.1038/s41593-019-0377-4; restated arXiv:2507.00583 | `theta_i = arccos(<dz_i,dz_{i+1}>/(‖dz_i‖‖dz_{i+1}‖))` — motion-dominated in image space (needs DINOv2, 75,648-dim/frame); blind to drift by design; on a parameter trace it reduces to a normalised second difference, subsumed by §8 |
| TRAJAN, motion histograms | Allen et al., arXiv:2505.00209 | learned trajectory autoencoder over BootsTAPIR point tracks; assesses **motion plausibility**, which restoration does not alter |
| recurrence quantification analysis | Marwan et al., *Physics Reports* 438:237–329, 2007, DOI 10.1016/j.physrep.2006.11.001 | diagonal-line measures do detect periodicity, but require an embedding dimension and a recurrence threshold — two parameters that would have to be tuned against the frozen clips, which `PLAN.md` forbids; answers no more than the ACF/periodogram pair |
| detrended fluctuation analysis / Hurst | Peng et al.; critiques in *Sci. Rep.* 2:315 | answers a long-range-correlation question we do not have; documented finite-size artifacts under nonlinear trends; ADEV's slope is more interpretable |
| Hadamard variance | NIST SP 1065 | insensitive to linear drift **by construction** — discards the signal, not a nuisance |
| spectral kurtosis / kurtogram | Antoni, *MSSP* | designed to locate impulsive transients in a frequency band; for a single spike in a 900-sample trace a robust z on `max|Δp|` is simpler and sufficient |
| EMD / Hilbert–Huang | — | adaptive but with known mode-mixing; no null distribution; not needed once the continuum is modelled explicitly |

### Not measuring what we mean by stability

| method | why rejected |
|---|---|
| learned NR-VQA (TLVQM, VIDEVAL, RAPIQUE, FAST-VQA, DOVER, StableVQA) | trained on human MOS; score attractiveness or shakiness; need a pretrained scorer; blur-sensitive in the wrong direction — against invariant 5, whose point is that a metric can improve while the image becomes less true |
| "drift score" / VDE families in video generation | standard deviation of a learned quality score along the clip; same objection |
| VBench subject / background consistency | DINO/CLIP feature similarity across frames and to the first frame — a learned long-range drift curve that would drift on a swim-through by design |
| WaterWave (arXiv:2512.05492) | evaluates with CLIP-A / NIMA aesthetic scores plus a qualitative temporal profile |
| NIQE / BRISQUE, as used for real old-film data (Wan CVPR'22) | single-frame naturalness; no temporal content |
| Eulerian Video Magnification | Wu et al., ACM TOG 2012, DOI 10.1145/2185520.2185561 — a *visualisation*, not a metric, and it assumes a near-static camera; on a swim-through it amplifies parallax, and motion-compensating it first reintroduces every flow confound the parameter route avoids |
| motion-compensated temporal filtering | a filtering technique for denoising/coding, not a diagnostic |
| ATE / RPE (Sturm et al., IROS 2012) | trajectory-error metrics for SLAM; not applicable to appearance — **but see §9, their all-Δ evaluation convention is the transferable idea** |
| online photometric calibration (Bergmann, Wang & Cremers, RA-L 2017; code at <https://github.com/tum-vision/online_photometric_calibration>) | recovers per-frame exposure, response and vignetting from auto-exposure video via gain-robust KLT tracks and nonlinear optimisation. Not a stability metric — but it is the right citation if the §9 contingency (a per-frame appearance gain/bias trajectory) is ever built |
| CUSUM / EWMA / Page-Hinkley control charts | online change-alarm methods with an average-run-length design; the offline question here is better served by PELT-style segmentation |
| PELT / `ruptures` (Truong, Oudre & Vayatis, arXiv:1801.00826) | retained as the tool for case I only, not as a stability metric |
| remote-sensing radiometric drift monitoring | methodologically just covariate-corrected trend fitting; confirms the recipe, adds no instrument |

### Previously unverifiable — now retrieved (see §11 for the retrieval log)

A dedicated retrieval pass recovered most of what the earlier passes could not
read, by decoding the source PDFs locally (adding LZW support for
pre-2000 scanned-era files) and by routing around blocked hosts. **Every
recovered formulation was re-tested against the project's requirements and
every rejection held.** Details in §11; summary here:

* **IEC 61000-4-15 flickermeter** — **recovered**. Rejected on two measured
  grounds: a 10-minute observation window against our 30 s, and a calibration
  tied to a 60 W/230 V/50 Hz incandescent filament lamp.
* **JEITA and VESA display flicker metrics** — **recovered** at vendor-
  documentation level. `JEITA = 10·log10(Px/P0)` dB after a perceptual filter;
  `VESA FMA = (Vmax−Vmin)/[(Vmax+Vmin)/2]`. Both subsumed by C6 or degenerate.
* **van Roosmalen et al., intensity flicker** — **recovered** (IEEE TCSVT
  9(7):1013–1027, 1999). A *correction* method whose spatially smooth α, β
  field has far more freedom than Phase 2B's deliberately minimal global
  scalar; adopting it would reopen the anti-gaming guarantee. Door closed.
* **Boitard et al., video tone mapping** — **recovered**. Confirms the field
  uses a per-frame global brightness trace read *qualitatively*; no objective
  metric exists there to borrow.
* **Lai ECCV'18 / Lei NeurIPS'20 E_warp** — **recovered** via Lei et al.'s
  own equations (6)–(7). Rejection stands and is now quantitative.
* **Video-coding flicker metrics** — still behind IEEE paywalls, and the two
  open-access mirrors refuse connections. Rejected on properties stated in
  accessible sources: **full-reference**, and the named psychovisual instance
  is **TSSIM**, an SSIM variant — both explicitly excluded by the brief.

### Statistical instruments examined and retained or noted

| instrument | source | role |
|---|---|---|
| Vaughan red-noise test | *A&A* 431:391, 2005, arXiv:astro-ph/0412697 | **C1a — carried** |
| Thomson harmonic F-test | *Proc. IEEE* 70:1055, 1982 | **C1b — carried alternative** |
| RobustPeriod | SIGMOD 2021, DOI 10.1145/3448016.3452779 | **C3 — escalation path** |
| Ljung–Box | *Biometrika* 65:297, 1978 | **C2 — companion** |
| Mann–Kendall + Sen's slope | non-parametric monotonic trend + median pairwise slope | **drift statistic** |
| Welch PSD | *IEEE TAE* 15:70, 1967; `scipy.signal.welch` | supporting view — catches quasi-periodic humps |
| Allan / overlapping ADEV | NIST SP 1065 | **C4 — timescale-dependent stability** (not metrology noise typing) |
| Fisher's exact g-test | Fisher 1929; statistic and exact p-value verified via MathWorks, citing Percival & Walden 1993 and Wichert et al., *Bioinformatics* 20:5, 2004 | **superseded** — assumes a **white** null; kept only inside RobustPeriod, on a robust periodogram |
| Lomb–Scargle FAP | VanderPlas 2018 | **rejected** — FAP is valid only for white noise and degrades under correlated noise; our data is evenly sampled so LS offers nothing over the FFT anyway |
| specparam / FOOOF | Donoghue et al., *Nat. Neurosci.* 2020, DOI 10.1038/s41593-020-00744-x; <https://github.com/fooof-tools/fooof> | **noted** — models a PSD as a 1/f-like aperiodic component plus Gaussian peaks, the same decomposition Vaughan performs, but returns parameter estimates rather than a significance test. Useful as a visualisation; not a decision rule |
| Kalman consistency: innovation whiteness, NIS vs χ² | standard estimator practice | **framing for §8** |
| fMRI QA protocol | Friedman & Glover, *JMRI* 2006; Weisskoff RDC 1996; TIM 2024 | **C5 — methodological precedent** |

---

## 8. Parameter-trace alternative — recommendation

**Yes, unambiguously.** Direct trajectory analysis of the estimated physical
parameters is both simpler and more informative than any image-space video
metric found. The carried candidate belongs in parameter space.

| Phase 2B confound | image-space diagnostic | parameter-trace diagnostic |
|---|---|---|
| subpixel resampling floor (11–115 % of MC-Warp@1) | recreated in full | **does not arise — no warp, no resampling** |
| correspondence masking / coverage gaming | must be guarded and reported | **does not arise — no mask exists** |
| the eel body SEA-RAFT deletes | unmeasured region stays unmeasured | **does not arise** (but see the gap below) |
| blur lowers every photometric score (case G) | must be paired with spatial inspection | **does not arise — a blurred output has the same parameter trace** |
| localised illumination (`lights`) | confounded, labelled, unfixable | still needs covariates, but the covariate is directly available |
| cost | ~0.71 s × 2 × 900 ≈ 21 min of SEA-RAFT per clip per lag | **free — the traces are a byproduct of the run** |
| causality | infers instability from its downstream shadow | **names the unstable variable directly** |

Four of seven rows collapse to "does not arise".

**The gap, stated honestly: spatial localisation.** A global parameter trace says
nothing about instability confined to one object — the very eel body the flow
mask already deletes. That is the §9 rejection trigger.

**The framing that makes it rigorous.** Weeks 5–6 plan a temporal stabiliser for
estimated parameters, with a synthetic-transition framework requiring it to
*suppress jitter but follow a true step*. That is the setting of
**filter-consistency testing**: for a correctly specified filter the innovation
sequence must be zero-mean white noise, checked by a whiteness test and by the
Normalized Innovation Squared statistic against its χ² reference. The carried
candidate is therefore not an exotic import — it is the textbook diagnostic for
the estimator Week 5 is already committed to building:

```text
periodic pumping          -> autocorrelated innovations -> Ljung-Box rejects, C1 names the frequency
over-damped, lags a step  -> autocorrelated innovations -> Ljung-Box rejects, C1 silent
correctly tuned           -> white innovations          -> neither rejects
```

**The battery** (all numpy; descriptive statistics plus tests, not an addition to
the frozen evaluator):

```text
level / spread    mean and MAD after removing a fitted trend
drift             Sen's slope in the parameter's own units per 30 s, with an
                  AUTOCORRELATION-AWARE significance test (prewhitened or
                  variance-corrected Mann-Kendall, or GLS/state-space).
                  Plain Mann-Kendall is invalid on serially dependent traces.
step energy       mean and max |p(t) - p(t-1)|, plus a robust z of the max
                  -- the spike detector that C1, C2, C4 and the PSD all miss
whiteness         Ljung-Box Q* on the detrended trace, h ~ 20-40, with p-value
periodicity       C1: periodogram, fitted noise continuum, peak significance with a
                  trials correction over the frequencies scanned; report frequency,
                  p-value and the fraction of detrended variance carried
spectrum          Welch PSD, plotted -- catches quasi-periodic humps a line test misses
period-2          mean((-1)^t * p_detrended(t)), reported ALONGSIDE lag-1 ACF.
                  Complementary, not equivalent -- they coincide only for an
                  ideal noiseless alternating sequence.
averaging         overlapping ADEV vs tau -- timescale-dependent stability.
                  Do NOT import the metrology noise-type labels.
covariates        every statistic above, recomputed on input-derived signals -- the
                  ORIGINAL footage's frame-mean linear luminance, camera-motion
                  magnitude, range. A matching peak is EVIDENCE OF POSSIBLE
                  COUPLING, not an attribution -- for that, cross-wavelet
                  coherence with phase statistics (S15.2).
```

**Prerequisite, cheap now and expensive later:** none of this exists unless
Weeks 5–6 **persist per-frame parameter estimates, indexed by frame, for the
whole run** — not summarised. `PLAN.md` Week 5 already lists "parameter
innovation magnitude" as a diagnostic, so the intent is there; what matters is
that the raw trace survives to Week 8.

---

## 9. Week 8 recommendation

> **HISTORICAL — superseded by §15.6 and §15.7.** The falsification cases A–I
> below remain valid as a synthetic validation suite and should still be run.
> Everything else here is pre-pass-6 and must not be used as an implementation
> guide: it precommits to a single periodicity test, specifies plain
> Mann–Kendall, imports metrology noise labels for ADEV, and makes the 30-lag
> MC-Warp sweep (step 5) a required measurement rather than the contingency it
> now is. **Implement from §15.6, not from here.**

### Minimum experiment

1. **Run the frozen evaluator, unchanged, over one continuous ~30 s clip** — raw
   and illumination-aware MC-Warp@1/@4/@8, alignment-robust companion, temporal
   ΔE00, coverage, status, and the `--method none` input baseline. Retune
   nothing. **Report MC-Warp@1 as a per-frame series, not only pooled** — the
   per-pair values already exist, so this costs nothing and turns the existing
   metric into a trajectory without redefining it.
2. **Persist every physical-parameter trace** over the same interval, with the
   covariates in §8.
3. **Compute the §8 battery** on each parameter trace, on each covariate, and on
   the MC-Warp@1 series from step 1.
4. **Validate the instrument on synthetic traces before believing it on real
   ones** — the A–I cases below, exactly as Phase 2B validated the warp metric
   against an analytic flow backend before trusting it on footage.
5. **Sweep the lag once, as a characterisation, and plot the curve.** Two
   unrelated mature fields independently converged on the same answer to "which
   interval?": NIST's all-τ ADEV plot, where a periodicity shows as a null at
   τ = the period (SP1065 §11.4–11.5); and the TUM RGB-D benchmark's relative
   pose error, which "by default computes the error between all pairs of
   timestamps" and is the standard drift measure in visual odometry. The image-
   space analogue is MC-Warp@k plotted against k, and it is affordable as a
   one-off: 12 anchors × 30 lags × 2 inferences × 0.71 s ≈ **8.5 minutes**.
   A period-P oscillation produces nulls at k = nP — the signature that
   `{1, 4, 8}` cannot show. **This adds no metric**: it is the frozen MC-Warp,
   swept and plotted rather than pooled. Recorded explicitly because `PLAN.md`
   Week 8 §5 says "Do not add a dense bank of MC-Warp lags" — that instruction
   is about the *reported metric set*, and this is a one-off characterisation
   that answers the very question that section asks. If that reading is not
   accepted, the sweep should be dropped and the parameter traces relied on
   instead.

### Falsification — what would prove the candidate is not useful to us

| case | required behaviour | rejected if |
|---|---|---|
| **A. stable sequence** | Ljung–Box does not reject; no peak survives multiplicity correction; ADEV falls with τ as simple averaging would predict | either test fires on a trace with nothing injected — a diagnostic that invents structure is worse than none |
| **B. period-2 pumping** | significant at the Nyquist bin; lag-1 ACF → −1; alternating-sign statistic ≈ amplitude | any fails to move at an amplitude visible in the output |
| **C. period-4 pumping** | significant at f_s/4 | no significant peak at the known frequency |
| **D. slow sinusoidal pumping** | significant at the injected frequency for periods ≲ 10 s; explicitly "unresolved" when slower than record/3 | a slower-than-resolvable oscillation is reported as confident drift |
| **E. monotonic drift** | an autocorrelation-aware trend test rejects, Sen's slope quantifies, ADEV rises at long τ — and it is **not** automatically called pathological; a real descent or change of water body legitimately drifts | drift is called instability without checking the covariates |
| **F. one-frame spike** | caught by the robust z on `max|Δp|` — **not** by C1, C2, the PSD or ADEV, all of which hide it (SP1065 §11.6) | the step-energy statistic is dropped and a spike is averaged away invisibly |
| **G. spatial blur only** | **no change in any parameter statistic** | any parameter statistic moves under output-only blur — that would mean the trace is not what we think it is |
| **H. legitimate moving dive light / caustics / fin cadence** | the peak appears in the input-derived covariate too, and is attributed | a swell-driven caustic oscillation is reported as restoration instability |
| **I. real scene transition** | a step matched by a step in the covariates, reported as a followed transition; if segmentation is needed, penalised change-point detection (`ruptures`, arXiv:1801.00826, `min_t V(t,y) + pen(t)`, BSD) | a genuine step is classified as pumping, or a stabiliser that lags a transition scores well |

Case G and four rows of §8 are answered **by construction** rather than by a
guard. That asymmetry is the substantive reason to prefer this over any
image-space alternative.

### The criterion that kills the candidate

**Drop it — do not elaborate it — if Week 8 shows output flicker visible or
measurable in MC-Warp@1 while every parameter trace is white and quiet.** That
would mean the instability does not live in the parameters: it is spatially
localised, or in a stage with no exposed scalar state, and a parameter-space
instrument is measuring the wrong variable. Only then does the follow-on apply:
a **flow-aligned appearance trajectory** — reuse the frozen machinery to emit a
per-frame 1-D signal (the per-frame pooled aligned residual, or a per-frame
global gain/bias fitted between consecutive *corrected* frames, the `α(t), β(t)`
form of the archive-film flicker literature and of online photometric
calibration) and apply the same §8 battery to it. That is a new *use* of
existing code producing a trajectory, not a new metric definition, and it must
still be paired with spatial-fidelity inspection because any photometric
trajectory can be flattened by blur.

### If detection fires and the question becomes "does it matter"

Then, and only then, reach for C6 — CIE TN 006's visibility measure with an
elaTCSF sensitivity curve — and **validate the transfer first**: render the
corrected sequence with and without the detected oscillation, measure the actual
full-field luminance modulation it produces, and apply the curve to that
measured modulation rather than to the raw parameter amplitude.

### An interpretation rule Week 8 must adopt (costs nothing)

**Motion silencing.** Local flicker visibility is measurably suppressed by
large coherent motion — the finding that FS-MOVIE exists to model (§11.7).
All else equal, the same local flicker **may** therefore be more visible in
low-motion content (`murky_shark`) than in high-motion content (`swimthrough`),
so the physical ordering of clips by measured instability need not be their
perceptual ordering by objectionability. Week 8 must not rank clips by measured
residual and treat that as a ranking of severity, and must not dismiss a smaller
measured instability on a static clip as less important than a larger one on a
moving clip.

**This is a tendency, not a correction factor.** Actual visibility also depends
on eccentricity, texture, flicker frequency, luminance, spatial extent and
display. Do not convert motion silencing into a deterministic ranking or a
numerical adjustment between clips; use it only to stop *assuming* that a larger
measured residual is a worse perceptual outcome. It is a rule for reading
results, not a metric, and requires no code.

### Zero-cost inspection worth doing regardless

A spatio-temporal slice — one scanline stacked over 900 frames into an x–t
image. Periodic pumping appears as horizontal banding, drift as a gradient. One
numpy slice, no inference, and it satisfies invariant 5's requirement to look at
the image before believing a number.

---

## 10. Sources

Read in their actual formulation unless listed in §7 as unverifiable.

**Carried and companion instruments**

* S. Vaughan, "A simple test for periodic signals in red noise", *A&A*
  431:391–403, 2005 — <https://arxiv.org/abs/astro-ph/0412697>
* D. J. Thomson, *Proc. IEEE* 70(9):1055–1096, 1982; F-test formulation verified
  at <https://arxiv.org/html/2405.18509>; implementation
  <https://github.com/aaryapatil/tapify>
* Q. Wen, K. He, L. Sun et al., RobustPeriod, SIGMOD 2021,
  DOI [10.1145/3448016.3452779](https://doi.org/10.1145/3448016.3452779),
  arXiv:2002.09535
* G. M. Ljung, G. E. P. Box, *Biometrika* 65:297–303, 1978
* Mann–Kendall trend test with Sen's slope (non-parametric monotonic trend;
  median of pairwise slopes)
* P. Welch, *IEEE Trans. Audio Electroacoust.* 15:70–73, 1967; semantics via
  <https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html>
* DPSS via the tridiagonal eigenvector formulation —
  <https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.windows.dpss.html>
  (Percival & Walden 1993; Slepian, *Bell Syst. Tech. J.* 1978)
* W. J. Riley, *Handbook of Frequency Stability Analysis*, NIST SP 1065, 2008 —
  <https://tf.nist.gov/general/pdf/2220.pdf> (Eqs. 6, 7, 10, 11, 64; Table 15;
  §5.27, §11.2, §11.4, §11.5, §11.6)
* D. W. Allan, *Proc. IEEE* 54(2):221–230, 1966 —
  DOI [10.1109/PROC.1966.4634](https://doi.org/10.1109/PROC.1966.4634)
* V. Ossenkopf, *A&A* 479:915, 2008 —
  DOI [10.1051/0004-6361:20079188](https://doi.org/10.1051/0004-6361:20079188)
* Fisher's exact g-test — statistic and exact p-value verified at
  <https://www.mathworks.com/help/signal/ug/significance-testing-for-periodic-component.html>
  (Percival & Walden 1993; Wichert, Fokianos & Strimmer, *Bioinformatics*
  20:5–20, 2004)
* J. VanderPlas, "Understanding the Lomb–Scargle Periodogram", *ApJS* 236:16,
  2018 — FAP valid only under a white-noise null
* T. Donoghue et al., *Nature Neuroscience* 23:1655–1665, 2020 —
  DOI [10.1038/s41593-020-00744-x](https://doi.org/10.1038/s41593-020-00744-x);
  <https://github.com/fooof-tools/fooof>
* C. Truong, L. Oudre, N. Vayatis, *ruptures* — <https://arxiv.org/abs/1801.00826>
* W. Aewallin, `allantools` — <https://github.com/aewallin/allantools> (LGPL-3.0)

**Imaging-system stability QA**

* L. Friedman, G. H. Glover, *J. Magn. Reson. Imaging* 23(6):827–839, 2006 —
  DOI [10.1002/jmri.20583](https://doi.org/10.1002/jmri.20583)
* R. M. Weisskoff, *Magn. Reson. Med.* 36:643–645, 1996 (radius of decorrelation)
* A. Schmidt et al., *JMRI*, 2024 —
  DOI [10.1002/jmri.28748](https://doi.org/10.1002/jmri.28748) (TIM)
* Y. Lu et al., "Quality assurance of human functional MRI: a literature
  review", *Quant. Imaging Med. Surg.* —
  <https://qims.amegroups.org/article/view/25794/html>

**Flicker metrology and temporal vision**

* CIE TN 006:2016, *Visual Aspects of Time-Modulated Lighting Systems* —
  <https://files.cie.co.at/883_CIE_TN_006-2016.pdf> (§4.3 Eq. 4; §4.3.4; §4.4)
* CIE TN 012:2021, *Guidance on the Measurement of Temporal Light Modulation* —
  <https://files.cie.co.at/CIE_TN_012_2021.pdf>
* Y. Cai, A. Bozorgian, M. Ashraf, R. Wanat, R. K. Mantiuk, elaTCSF, SIGGRAPH
  Asia 2024 —
  DOI [10.1145/3680528.3687586](https://doi.org/10.1145/3680528.3687586),
  arXiv:2503.16759,
  <https://www.cl.cam.ac.uk/research/rainbow/projects/elaTCSF/>
* R. K. Mantiuk et al., ColorVideoVDP, *ACM TOG* 43(4), 2024 —
  DOI [10.1145/3658144](https://doi.org/10.1145/3658144), arXiv:2401.11485;
  FovVideoVDP, *ACM TOG* 40(4), 2021

**Added in pass 6 (§15)**

* C. Torrence, G. P. Compo, "A Practical Guide to Wavelet Analysis", *Bull.
  Amer. Meteor. Soc.* 79(1):61–78, 1998 —
  <https://psl.noaa.gov/people/gilbert.p.compo/Torrence_compo1998.pdf>;
  code <https://github.com/ct6502/wavelets>
* A. Grinsted, J. C. Moore, S. Jevrejeva, "Application of the cross wavelet
  transform and wavelet coherence to geophysical time series", *Nonlinear
  Processes in Geophysics* 11:561–566, 2004 —
  DOI [10.5194/npg-11-561-2004](https://doi.org/10.5194/npg-11-561-2004)
* S. Vaughan, Bayesian spectral analysis / posterior predictive approach to
  periodicity in red noise (2010) — escalation path only
* Hübner et al., Gaussian-process comparison of quasi-periodic versus red-noise
  models — escalation path only
* P. Ebelin, G. Denes, T. Akenine-Möller, K. Åström, M. Oskarsson,
  W. H. McIlhagga, "Estimates of Temporal Edge Detection Filters in Human
  Vision", *ACM Trans. Appl. Percept.* 21(2), 2024 —
  DOI [10.1145/3639052](https://doi.org/10.1145/3639052)
* "No-Reference Rendered Video Quality Assessment: Dataset and Metrics" (ReVQ),
  arXiv:2510.13349, 2025
* Autocorrelation-adjusted Mann–Kendall (prewhitening / variance-corrected
  variants) and Sen's slope

**Recovered in the retrieval pass (§11)**

* C. Lei et al., Deep Video Prior, NeurIPS 2020 — <https://arxiv.org/abs/2010.11838>
  (E_warp Eqs. 6–7, and the per-frame mean-intensity trace of Fig. 8)
* P. M. B. van Roosmalen, R. L. Lagendijk, J. Biemond, "Correction of Intensity
  Flicker in Old Film Sequences", *IEEE Trans. Circuits Syst. Video Technol.*
  9(7):1013–1027, 1999 —
  DOI [10.1109/76.795055](https://doi.org/10.1109/76.795055)
* IEC 61000-4-15 flickermeter blocks and weighting-filter constants, as
  reproduced in an IMEKO TC4 2014 paper ("Matlab based flickermeter"); the
  normative text remains paywalled
* JEITA and VESA FMA flicker formulas, as documented by Chroma ATE
  (instrument-vendor documentation, not the standards' normative text)
* R. Boitard, R. Cozot, D. Thoreau, K. Bouatouch, *Video Tone Mapping* (book
  chapter, 2016) and *Survey of Temporal Brightness Artifacts in Video Tone
  Mapping*, HDRi 2014
* L. K. Choi, A. C. Bovik, "Video quality assessment accounting for temporal
  visual masking of local flicker", *Signal Processing: Image Communication*
  67:182–198, 2018 (FS-MOVIE; motion silencing, after Suchow & Alvarez,
  *Curr. Biol.* 21(2):140–143, 2011)
* R. Soundararajan, A. C. Bovik, ST-RRED —
  <http://live.ece.utexas.edu/research/Quality/ST-RRED/>
* P. Zsoldos, "Evaluating the Effect of Compression on Video Temporal
  Consistency Using Objective Quality Metrics", arXiv:2605.18378

**Video temporal metrics examined**

* Survey: "Spatiotemporal Consistency in Video Generation" —
  <https://arxiv.org/html/2502.17863v1>
* C. Lei, X. Ren, Z. Zhang, Q. Chen, "Blind Video Deflickering by Neural
  Filtering with a Flawed Atlas", CVPR 2023 — <https://arxiv.org/abs/2303.08120>,
  <https://github.com/ChenyangLEI/All-In-One-Deflicker>
* Z. Wan et al., "Bringing Old Films Back to Life", CVPR 2022 —
  <https://arxiv.org/abs/2203.17276>
* M. Chu et al., TecoGAN, *ACM TOG* 2020 — <https://arxiv.org/abs/1811.09393>
* R. Henschel et al., StreamingT2V — <https://arxiv.org/abs/2403.14773>
* P. Dai et al., video demoiréing — <https://arxiv.org/abs/2204.02957>
* Z. Huang et al., VBench, CVPR 2024 — <https://arxiv.org/abs/2311.17982>
* D. Du et al., underwater video enhancement —
  <https://arxiv.org/html/2403.11506v1>
* Q. Zhu et al., WaterWave — <https://arxiv.org/html/2512.05492>
* S. Chen et al., Video Depth Anything, CVPR 2025 —
  <https://arxiv.org/html/2501.12375v3>
* G. Yang et al., FreMOTR, ACM MM 2022 —
  DOI [10.1145/3503161.3547781](https://doi.org/10.1145/3503161.3547781)
* K. Allen et al., "Direct Motion Models for Assessing Generated Videos" —
  <https://arxiv.org/abs/2505.00209>
* S. Liu et al., "Bundled camera paths for video stabilization", *ACM TOG* 2013 —
  DOI [10.1145/2461912.2461995](https://doi.org/10.1145/2461912.2461995);
  formulation verified at <https://ar5iv.labs.arxiv.org/html/1909.02641>
* J. Sturm et al., "A Benchmark for the Evaluation of RGB-D SLAM Systems",
  IROS 2012 — <https://cvg.cit.tum.de/_media/spezial/bib/sturm12iros.pdf>
* P. Bergmann, R. Wang, D. Cremers, "Online Photometric Calibration of Auto
  Exposure Video", *IEEE RA-L*, 2017 —
  <https://github.com/tum-vision/online_photometric_calibration>
* O. J. Hénaff, R. L. T. Goris, E. P. Simoncelli, *Nat. Neurosci.* 22:984–991,
  2019 — DOI [10.1038/s41593-019-0377-4](https://doi.org/10.1038/s41593-019-0377-4);
  restated at <https://arxiv.org/html/2507.00583v3>
* H.-Y. Wu et al., Eulerian Video Magnification, *ACM TOG* 2012 —
  DOI [10.1145/2185520.2185561](https://doi.org/10.1145/2185520.2185561)
* N. Marwan et al., *Physics Reports* 438:237–329, 2007 —
  DOI [10.1016/j.physrep.2006.11.001](https://doi.org/10.1016/j.physrep.2006.11.001)
* W.-S. Lai et al., ECCV 2018 —
  <http://vllab.ucmerced.edu/wlai24/video_consistency/>; C. Lei et al.,
  NeurIPS 2020 — <https://arxiv.org/abs/2010.11838>. Original formulations
  **could not be read this session**; the CVPR'23 restatement is used instead.

---

## 11. Retrieval pass — recovered sources and re-tested rejections

Every source the earlier passes could not open was re-attempted through
alternate routes: direct PDF download with local decoding (Flate **and** LZW,
the latter added specifically for pre-2000 scanned-era files), ar5iv/HTML
mirrors, author copies, institutional repositories, standards-sample servers,
and vendor documentation. **Six of eight recovered. No rejection changed.**

| source | earlier status | outcome | rejection after reading |
|---|---|---|---|
| Lei et al., DVP (E_warp) | image-only PDF | **recovered**, Eqs. (6)–(7) | holds — §11.1 |
| VBench dimensions | HTTP 403 | **recovered** via ar5iv | holds, and now stronger — §11.2 |
| van Roosmalen et al. 1999 | scanned PDF, no text layer | **recovered** via LZW decode | holds, and closes a door — §11.3 |
| IEC 61000-4-15 flickermeter | paywalled | **recovered** via IMEKO reproduction | holds, now quantitative — §11.4 |
| JEITA / VESA display metrics | paywalled + 403 | **recovered** at vendor level | holds — §11.5 |
| Boitard et al., tone mapping | text extraction failed | **recovered** via LZW decode | holds, and supports the recommendation — §11.6 |
| Video-coding flicker metrics | IEEE paywall | **not recovered** — both open mirrors refuse connections (`ECONNREFUSED`, HTTP 400) | holds on stated properties — §11.8 |
| Lai et al. ECCV'18 original | 403 / 404 / >10 MB | **not recovered** | immaterial — formulation verified via two independent restatements, §11.1 |

Additionally, two FR/RR video-quality models that no earlier pass had examined
were retrieved and tested: **FS-MOVIE** and **ST-RRED** (§11.7).

---

### 11.1 Warping error, long-term variant — Lei et al., NeurIPS 2020

**Recovered.** Equations (6)–(7), verbatim in substance:

```text
E_pair(O_t, O_s) = ( 1 / sum_i M_{t,s}(x_i) ) * sum_i M_{t,s}(x_i) * || O_t(x_i) - W(O_s)(x_i) ||_1
E_warp({O_t})    = ( 1 / (T-1) ) * sum_{t=2..T} { E_pair(O_t, O_1) + E_pair(O_t, O_{t-1}) }
```

`M_{t,s}` is the occlusion map for the pair, `W` is backward warping with
optical flow. The paper attributes the consecutive-frame term to prior work and
the **frame-1 term** to Lai et al. — so the family is now verified from two
independent restatements (this, and the CVPR'23 deflicker paper's identical
form), which is why Lai's own PDF being unreachable is immaterial.

**Rejection holds, and is now quantitative rather than structural.** The
long-term term averages `E_pair(O_t, O_1)` over every `t`. Its validity mask
`M_{t,1}` is the overlap between frame `t` and frame 1. Phase 2B measured
coverage already falling to 77–89 % at a separation of **8 frames** on a
41-frame window; at separations of hundreds of frames on a swim-through the
overlap goes to zero, the mask empties, and Phase 2B's own rule — a score is
`None` when the mask is empty, and two configurations are comparable only if
their coverage is — makes the quantity undefined long before it becomes wrong.
DVP's own datasets are 30–200 frames of modest motion, where this is tolerable.
Ours are 900 frames of translation through a reef, where it is not.

**One finding in this paper actively supports the recommendation.** Section 4
does not rely on E_warp alone to show long-term drift. It plots a **per-frame
mean-intensity trace** (their Fig. 8) and reads it by eye, observing that a
competing method handles flicker "well in the short term, but the difference
between the first and last frame is too large". That is precisely a 1-D
appearance trajectory used to expose long-range drift — reached for because the
pairwise metric could not show it, and then left unquantified.

---

### 11.2 VBench dimensions — Huang et al., CVPR 2024

**Recovered.** Verified definitions:

* **Temporal flickering** — mean absolute difference across **consecutive**
  frames, normalised to [0,1]. Critically, it is computed on **static test
  scenes**: the benchmark does not mask motion, it *selects videos that have
  none*.
* **Subject consistency** — DINO feature cosine similarity of each frame to
  both the first frame and the preceding frame.
* **Background consistency** — identical structure with CLIP image features.
* **Motion smoothness** — drop the odd frames, re-interpolate them with a video
  frame-interpolation model, compare to the originals by MAE.
* **Dynamic degree** — mean of the largest 5 % of RAFT optical-flow magnitudes
  between consecutive frames.

**Rejection holds and is now stronger than "weaker than MC-Warp".** The flicker
dimension is *undefined* for our footage: it presupposes a static scene, and
every clip in the frozen test set has camera motion, four of them substantial.
Subject and background consistency are long-range but learned-feature-based and
would register a swim-through's legitimate scene change as inconsistency by
construction. Motion smoothness measures whether motion follows an
interpolation prior, which restoration does not alter.

---

### 11.3 Intensity flicker in old film — van Roosmalen, Lagendijk & Biemond, IEEE TCSVT 9(7):1013–1027, 1999

**Recovered** from a scanned PDF by adding LZW stream decoding. Verified model:
the observed frame is `alpha(x,y,n) * original(x,y,n) + beta(x,y,n) + noise`,
where α and β are the multiplicative and additive intensity-flicker parameters,
**assumed spatially smooth functions** (α = 1, β = 0 when no flicker), and the
noise term is zero-mean, of known variance, and uncorrelated with the original.
The original is recovered by a linear MMSE estimator; parameters are estimated
by equalising local frame means and variances temporally; a **reliability
measure** thresholded on the noise variance flags unreliable estimates. Motion
is handled by global (phase-correlation) compensation plus local-motion
*detection*, and where local motion is detected the parameters are **not
estimated but interpolated from stationary regions**, because local motion
estimators assume constant luminance, which flicker violates.

**Rejection holds, and reading it closes a door that was previously ajar.**
Two independent reasons:

1. **It is a correction method, not a diagnostic.** It has no measure of
   temporal stability to borrow.
2. **Its model is exactly what Phase 2B deliberately refused.** Phase 2B chose
   one *global scalar* gain and bias precisely because that is "the lowest-
   capacity form that is structurally incapable of absorbing the failure the
   metric exists to catch" — a scalar applied to all channels cannot represent
   a red-only change at all. A **spatially smooth α(x,y,n), β(x,y,n) field**
   has vastly more freedom; fitted between corrected frames it could absorb
   genuine restoration flicker as "illumination", destroying the anti-gaming
   guarantee that Phase 2B verified three separate ways. So the answer to
   "should the `lights` local-illumination confound be fixed with a
   van-Roosmalen-style spatially varying model?" is **no**, on record, with the
   reason stated.

Its local-motion handling is also a useful precedent for a different reason: it
independently arrives at the same posture as Phase 2B's coverage discipline —
where correspondence cannot be trusted, do not estimate; declare and fill from
elsewhere, rather than pretending.

---

### 11.4 IEC 61000-4-15 flickermeter — recovered

**Recovered** via an IMEKO TC4 conference paper that reproduces the standard's
functional blocks. The chain is: input voltage adaptor → squaring demodulator →
a first-order high-pass at 0.05 Hz plus a 6th-order Butterworth low-pass at
35 Hz plus the lamp–eye–brain **weighting filter** → squaring and first-order
low-pass smoothing (the brain's memory effect) → on-line statistical
classification producing `P_st`. The weighting filter's constants, as
reproduced there:

```text
k = 1.74802,  lambda = 2*pi*4.05981,  omega_1 = 2*pi*9.15494,
omega_2 = 2*pi*2.27979,  omega_3 = 2*pi*1.22535,  omega_4 = 2*pi*21.9
```

giving a bandpass whose peak sensitivity sits near 8.8 Hz. The paper states the
filter was fitted to tests on **sinusoidal voltage fluctuations driving a
60 W / 230 V / 50 Hz filament lamp**, with the limit set where 50 % of tested
observers noticed the fluctuation. (The extracted algebraic layout was mangled
by the decoder; the constants are unambiguous, but the exact arrangement should
be read from the standard before anyone implements it.)

**Rejection holds, and is now quantitative rather than "cannot read it".**

1. **Observation window.** `P_st` is defined by percentile statistics
   (P0.1, P1, P3, P10, P50) over a **10-minute** observation period. Week 8's
   run is **30 seconds** — 1/20th of the window the statistic is defined on.
   The percentiles would be estimated from far too little data to mean what the
   standard says they mean.
2. **Calibration target — but not a categorical bar.** The chain is calibrated
   for an incandescent filament lamp, whose thermal time constant is baked into
   the weighting curve. **Correction (pass 6):** an earlier version treated this
   as disqualifying. It is not — CIE TN 006 itself notes that a *modified*
   flickermeter with the incandescent-lamp model removed can serve as a general
   flicker-visibility measure. The honest objections are narrower: CIE TN 006's
   scope is the visibility of time-modulated *lighting*, explicitly excluding
   TV/broadcast/personal-video capture interactions; CIE TN 012 notes that
   transferring the principles to displays generally requires different
   measurement arrangements; sensitivity depends on application and viewing
   conditions; and none of it supplies a statistical null for "estimator noise
   versus real pumping".
3. **It is subsumed.** CIE TN 006 §4.4 documents the *generic* time-domain
   framework of which the IEC flickermeter is explicitly named as one example
   embodiment — and the generic form lets a modern, display-appropriate
   sensitivity curve (elaTCSF) be substituted for the filament-lamp one. If
   this direction is ever taken, take it through C6, not through IEC.

---

### 11.5 JEITA and VESA display flicker metrics — recovered

**Recovered** at instrument-vendor documentation level (Chroma ATE), not from
the standards' normative text — stated so the provenance is not overclaimed.

```text
JEITA    = 10 * log10( Px / P0 )  [dB]
```

where the luminance waveform is first passed through a filter representing the
eye's flicker perception, then FFT'd; `P0` is the power at DC and `Px` the
power at frequency `x`.

```text
VESA FMA = (Vmax - Vmin) / [ (Vmax + Vmin) / 2 ]   (as a percentage)
```

i.e. peak-to-peak modulation depth normalised by the mean — the classic
"percent flicker".

**Rejections hold, for different reasons each.**

* **JEITA is subsumed by C6.** It is a perceptually-filtered power spectrum
  normalised to DC — structurally the `C_m / T_m` normalisation of CIE TN 006
  Eq. (4), but reported per frequency in dB rather than pooled, and **without
  an absolute visibility threshold**. C6 does the same thing with a documented
  threshold at 1.0 and a defensible pooling rule. There is nothing here that C6
  does not do better, and its filter is display-standard rather than
  substitutable.
* **VESA FMA is degenerate for our purpose.** It is `max − min` over the record.
  Over a 30 s parameter trace that single number would be driven by whichever
  is largest of a monotonic drift, a one-frame spike, or an oscillation, with
  **no way to tell which** — it conflates precisely the three failure modes
  Week 8 must distinguish. A robust modulation depth on the *detrended* trace
  is already the "level / spread" line of the §8 battery, which is the useful
  part of this idea with the fatal part removed.

---

### 11.6 Boitard et al., video tone mapping — recovered

**Recovered** by LZW-decoding the book-chapter PDF. The relevant passage,
in substance: temporal artifacts appear because tone mapping operators "adapt
their mapping using image statistics that tend to be unstable over time", and —
the operative sentence — **"Analyzing the overall brightness of each frame over
time is usually sufficient to detect those artifacts. An overall brightness
metric can be, for example, the mean luma value of an image."** Their Figure 1
plots that trace for the HDR source and the tone-mapped output together, showing
the source stable while the output shows abrupt variations.

**Rejection holds — there is no objective metric here to borrow.** The chapter
offers a taxonomy (global flickering, local flickering, temporal noise, temporal
brightness incoherency, temporal object incoherency, hue coherency) and a
qualitative plot; evaluation in that literature is subjective.

**But it is the third independent confirmation of the recommendation's core
move.** Three separate communities, facing a global parameter that pumps —
tone mapping (this), blind video temporal consistency (§11.1, DVP's Fig. 8), and
functional MRI quality assurance (§6 C5) — all reduce the problem to a
**per-frame 1-D global trace compared against the input's own trace**. Two of
the three then stop at reading the plot. fMRI QA is the one that went on to
quantify it, and that is exactly the step being proposed here. Note also that
Boitard's method compares the output trace to the *source* trace, which is the
same discipline as Phase 2B's mandatory `--method none` input baseline.

---

### 11.7 Two FR/RR video-quality models tested for the first time

**FS-MOVIE** — L. K. Choi, A. C. Bovik, "Video quality assessment accounting for
temporal visual masking of local flicker", *Signal Processing: Image
Communication* 67:182–198, 2018. Recovered in full. It computes spatiotemporal
Gabor bandpass responses on **reference and distorted** videos, applies a V1
motion-energy model and divisive normalisation to extract the spectral
signature of local flicker, and pools:

```text
FS-MOVIE = TP{ CoV(Q_S) * sqrt( CoV(Q_T) ) }
```

**Rejected: full-reference.** It requires a pristine reference video, which this
project does not have and cannot have for real footage.

**But it contributes the single most important new fact of this retrieval pass,
and Week 8 must account for it.** FS-MOVIE exists because of *motion silencing*
(Suchow & Alvarez 2011): the measured finding, which the paper restates as its
own result, that **"local flicker visibility is strongly reduced by the presence
of large, coherent object motions"**, and that the effect is significant enough
to be worth modelling explicitly in a quality metric.

The consequence for this project is direct and was not previously on record:

> All else equal, a given amplitude of local flicker **may be more visible on a
> near-static clip than on a fast swim-through**. So the physical ordering of
> clips by measured instability need not be the perceptual ordering by
> objectionability. This is a tendency, not a correction factor (§9).

Phase 2B already has the ingredients to see this: `murky_shark` is the
near-static clip (0.03 px/frame at @1) and it is also where gray-world's
relative jump was largest (2.73×) and where, as Phase 2B noted, "flicker is most
visible to the eye". `swimthrough` has the largest motion. Motion silencing says
that is not a coincidence and not only a signal-to-noise effect — it is also a
property of the observer. **Week 8 should therefore not rank clips by measured
instability and assume that ranking is perceptual**, and should not dismiss a
smaller measured instability on `murky_shark` as less important than a larger
one on `swimthrough`. This is an interpretation rule, not a metric, and it
costs nothing to adopt.

**ST-RRED** — R. Soundararajan, A. C. Bovik, "Video quality assessment by
reduced reference spatio-temporal entropic differencing", IEEE TCSVT, 2013;
project page <http://live.ece.utexas.edu/research/Quality/ST-RRED/>. Measures
quality deviation by spatial and temporal entropic differences in the band-pass
domain, needing as little as 1/576th of the reference video's information.
**Rejected: reduced-reference is still referenced.** The fraction is of a
*pristine* video's information; our only available reference is the uncorrected
input, which the restoration is supposed to change. Feeding that pair to any
FR or RR model measures the strength of the restoration, not its stability.

The same disposal applies to the **MOVIE index** (full-reference, quality along
motion trajectories) and to **T-SSIM / T-PSNR**, which a 2026 study of
compression and temporal consistency evaluates alongside them. That study's
useful contribution for us is negative and confirmatory: it frames the field's
problem as spatial metrics failing to expose temporal instability, and its
remedies are all full-reference.

---

### 11.8 Still not recovered, and why it no longer matters

* **Video-coding flicker metrics** (H.264/HEVC periodic-intra flicker). The
  IEEE versions are paywalled; the two open-access mirrors that host the
  relevant thesis refused connections at the network level (`ECONNREFUSED`
  130.238.7.110, and HTTP 400 from the CORE fileserver) across repeated
  attempts. **The rejection does not depend on the missing algebra.** Two
  properties are stated consistently in accessible sources and are each
  independently disqualifying: the assessment algorithms are **full-reference**
  (they compare the coded video against the original uncompressed video), and
  the named psychovisual instance is **TSSIM**, structural similarity computed
  between consecutive frames on detected flicker regions — an SSIM variant,
  which the brief and `PLAN.md` exclude outright. A third property, that these
  metrics target **static background macroblocks** at a **known GOP period**,
  removes any remaining applicability to a moving camera with no reference and
  no periodic coding structure.
* **Lai et al., ECCV 2018, original PDF** — 403 from the CVF mirror, 404 from
  the author's project page, and the arXiv PDF exceeds the fetch size limit.
  **Immaterial:** the formulation is verified from two independent restatements
  (§11.1), which agree with each other.
* Two further items were not re-attempted because they are superseded by
  sources already read: the JSID variable-refresh-rate flicker paper (superseded
  by elaTCSF, from the same research group, which was read in full), and the
  EURASIP "visual rhythms" paper (the x–t slice recommended in §9 is an
  elementary construction and is not attributed to it).

---

### 11.9 Verdict of the retrieval pass

Nothing recovered is additive. Every recovered candidate fails on at least one
of four properties the project cannot negotiate:

```text
requires a pristine reference video   -> FS-MOVIE, ST-RRED, MOVIE, T-SSIM/T-PSNR,
                                         video-coding flicker metrics, TAE, MABD,
                                         RWE
                                         (NOT tOF/tLP -- see S12; usable without
                                          GT via the input-as-reference variant,
                                          rejected on other grounds)
presupposes a static or near-static scene -> VBench temporal flickering
is a correction method, not a measure -> van Roosmalen, Boitard, MCTF
is calibrated for a stimulus or over
a window we do not have               -> IEC flickermeter (10-min Pst window; the
                                         filament-lamp model can be removed per
                                         CIE, but the TCSF basis and application
                                         assumptions remain),
                                         JEITA/VESA (subsumed or degenerate)
```

**The recommendation of §1 is unchanged**, and the one substantive addition from
this pass is an interpretation rule rather than an instrument: motion silencing
(§11.7) means measured instability and perceived objectionability are ordered
differently across the frozen test set, and Week 8 must not conflate them.

---

## 12. Pass 5 — the flicker-metric literature, properly

An earlier pass concluded too quickly that flicker metrics did not exist in the
needed form. Pushed to look harder, this pass found **seven no-reference video
flicker metrics** plus a compression-based measure and the original Lai
formulation. §5's headline claim has been corrected accordingly. Every one of
them was read in its actual formulation and every one is still rejected — but
now on specific, quantitative grounds rather than absence.

### 12.1 Lai et al., ECCV 2018 — recovered in full

Retrieved from the ECVA open-access mirror after CVF (403), the author page
(404) and arXiv (>10 MB) all failed. Equations (5)–(6):

```text
E_warp(V_t, V_{t+1}) = ( 1 / sum_i M_t^(i) ) * sum_i M_t^(i) * || V_t^(i) - V_hat_{t+1}^(i) ||_2^2
E_warp(V)            = ( 1 / (T-1) ) * sum_{t=1..T-1} E_warp(V_t, V_{t+1})
```

`V_hat_{t+1}` is the warped next frame; `M_t ∈ {0,1}` is a **non-occlusion
mask** from a separate occlusion detector. Two details the restatements had
obscured: Lai's evaluation uses **squared L2**, not L1, and his reported
`E_warp` averages **consecutive pairs only** — the long-range "to frame 1" term
belongs to the *training loss* and to a different citation, not to his
evaluation metric.

**Rejection holds**, and Lai supplies the argument himself. §4.4, verbatim in
substance: *an extremely blurred video may have high temporal stability but low
perceptual similarity; the processed video itself has perfect perceptual
similarity but is temporally unstable; the two must be balanced.* That is
Phase 2B's case G — blur cutting a photometric temporal score by 64 % — stated
independently by the originators of the metric, seven years earlier. It is
strong corroboration that the frozen stack's insistence on treating spatial
fidelity as a separate axis is the field's own conclusion, not a local quirk.

Phase 2B's MC-Warp differs from Lai's in two deliberate ways that now look
better-founded: **L1 instead of squared L2** (Phase 2B: L1 "is far less
dominated by the handful of pixels — bubbles, marine snow, a thin rope, an
occlusion edge — that Phase 2A showed dominate an underwater residual"), and
**forward-backward consistency** instead of a separate occlusion detector.

### 12.2 The seven no-reference flicker metrics

| metric | source | what it actually computes | why rejected |
|---|---|---|---|
| **Guthier et al. flicker detection** | SPIE EI 2011, "Flicker reduction in tone mapped HDR video" | per-frame **geometric-mean brightness** `Ī = exp((1/n)Σ log(I_j+δ))`; flicker flagged when `\|Ī_t − Ī_{t−1}\|` exceeds a JND threshold from **Stevens' power law** evaluated at the previous frame's level, `k` tuned in a subjective study | consecutive-frame only, and **no motion compensation at all**: on a swim-through, legitimate scene change moves `Ī` constantly. Their own worked example is a camera turn toward a window — they *want* it to fire on a real transition and then smooth it, which is precisely the behaviour `PLAN.md` Week 8 §2 forbids ("a stabilizer that produces excellent temporal metrics by lagging behind a real transition is incorrect") |
| **CTI** (Kim et al.) | via the DIBR quality overview, arXiv:1911.07036 | detects flicker regions from **motion-compensated frame differences**, then computes **structural similarity** on those regions, weighted by pixel count | an SSIM variant — excluded outright by the brief and `PLAN.md`; pairwise; blur-rewarding; adds a region-detection threshold that would have to be tuned against the frozen clips |
| **FDI** (Zhou et al.) | *Comput. Vis. Image Underst.*, via the same overview | **gradient variations** between frames locate candidate flickering blocks; the flicker distortion itself is then measured as a distance in the **SVD domain** of those blocks against the previous frame | *(Correction: an earlier version called this "gradient-domain, therefore discards low-frequency intensity" — too reductive: the gradient step is region **detection**, the distortion is measured in the SVD domain.)* Rejected on accurate grounds: DIBR-specific, adjacent-frame, block-and-threshold machinery, no long-time trajectory, no calibrated stochastic null, no evident robustness to underwater illumination |
| **VBench temporal flickering** | CVPR 2024 | mean absolute difference across consecutive frames, computed on **static test scenes** | undefined for our footage — it does not mask motion, it selects videos that have none |
| **WCS Flicker Penalty (FP)** | arXiv:2508.00144, 2025 | `ε(t) = ‖I_{t+1} − warp(I_t,φ_t)‖₁ / ‖I_{t+1}‖₁` with RAFT flow; `FP = mean_t ε(t)` | **this is MC-Warp@1**, self-normalised, minus coverage, minus illumination handling, minus the alignment-robust companion, minus an error bar, plus a heuristic clamp to "avoid counting real object motion as flicker" |
| **BG-Flicker** | FluentAvatar, arXiv:2509.12052 | temporal stability restricted to background regions | requires a semantic foreground/background split; the underwater analogue would exclude exactly the moving animal the metric most needs to see |
| **AB(Var) / per-pixel temporal std** | video-enhancement literature | standard deviation of each pixel's value across frames | assumes a static camera; on a swim-through it measures the scene sweeping past |

**The pattern is uniform and worth stating once.** Every no-reference flicker
metric in the literature handles camera motion in one of three ways: it ignores
motion (Guthier, AB(Var)), it *excludes* motion (VBench static scenes,
BG-Flicker background-only), or it *compensates* motion with optical flow and
then takes a pairwise photometric residual (CTI, FDI, WCS-FP). The third route
is MC-Warp, which the project already has — with coverage, an illumination
model, a resampling floor and an error bar that none of these carry.

**Correction (pass 6): an earlier version claimed "there is no fourth route in
the literature". That universal claim is withdrawn** — see ReVQ (§12.5), a 2025
learned no-reference model that builds a temporal-stability stream on
multi-timescale motion-aligned differencing. The defensible statement is
narrower: *among the methods reviewed, none reduces the problem to a trajectory
and tests it against a calibrated stochastic null*, which is what the carried
candidate does.

### 12.3 Full-reference flicker metrics, for completeness

Rejected as a class (no clean reference video exists for real footage), but
recorded so the class is not re-searched: **VQA-SIAT** (spatio-temporal tubes
within QA-GoPs, activity + flickering, temporal gradient along motion
trajectories); **SR-3DVQA** (treats the video as a 3-D volume, decomposes into
**X-T and Y-T spatiotemporal layers**, sparse-representation flicker estimation
on the temporal layers); **PSPTNR** (perceptual temporal noise,
`((P_n − P_{n−1}) − (R_n − R_{n−1}))²` filtered through JND models and motion
masks); **FS-MOVIE**; **MOVIE**; **T-SSIM / T-PSNR**; **ST-RRED**
(reduced-reference, but referenced); and the H.264/HEVC intra-flicker metrics.

Two of these are worth noting for reasons other than adoption. **SR-3DVQA's
X-T / Y-T layer decomposition** is the published lineage of the spatio-temporal
slice recommended in §9 as a zero-cost inspection — the idea is not novel here
and has been used for flicker estimation before. **PSPTNR's** second-difference
form is the same construction as the demoiréing paper's RWE, arrived at
independently, and both need ground truth.

### 12.4 A compression-based measure — a genuinely different family

**OMIQ** — Biemond, van Roosmalen & Lagendijk, "Restoration and Storage of Film
and Video Archive Material", in *Signal Processing for Multimedia*, IOS Press,
1999 (AURORA project). Recovered in full.

```text
delta_Q = E(corrected) - E(impaired)            (Eq. 30)
```

where `E` is coding efficiency, in either of two units. In **dB**: encode both
sequences at a fixed bit rate and take `E` as the PSNR between input and decoded
output. In **bits**: set the rate so the two PSNRs match, and `E` is the
compressed size — so `delta_Q` reads as "how many bits of irrelevant information
the restoration removed". The stated assumptions are that restoration removes
artifacts, and that removing artifacts increases coding efficiency, "because
removing these reduces the magnitude of the prediction errors both in a temporal
and a spatial sense".

This is the only genuinely novel family the whole review turned up that is
**no-reference, whole-sequence, and motion-compensated for free** (the encoder
does the motion compensation), and it directly penalises temporal
unpredictability. It deserved a serious look. It is rejected on four grounds,
the first of which the authors state themselves:

1. **Blur-gamed, by the authors' own admission.** They exclude sharpness
   artifacts from the method's scope precisely because "deblurred images require
   more bits for coding than the out of focus originals" — i.e. a *blurred*
   output codes cheaper and would score as improved. This is Phase 2B case G
   again, in a third independent source.
2. **It cannot separate the three failure modes.** One scalar per sequence
   cannot distinguish drift from period-2 pumping from a one-frame spike, which
   is the entire discrimination Week 8 needs.
3. **Enormous hidden configuration surface.** Encoder, rate-control mode, GOP
   length, and motion-search settings all move the number, and none of them is
   predeclarable from physics. `PLAN.md` forbids tuning thresholds against the
   frozen clips; this would be a dozen such thresholds wearing a codec.
4. **It conflates spatial and temporal predictability** — its own justification
   says prediction error falls "both in a temporal and a spatial sense".

---

### 12.5 Two further candidates found in pass 6

**ReVQ — learned no-reference temporal-stability stream.** "No-Reference
Rendered Video Quality Assessment: Dataset and Metrics", arXiv:2510.13349
(2025). Builds an explicit temporal-stability branch for flicker and moving
jaggies: short ~5-frame subsets, dense motion estimation, disocclusion handling,
backward alignment, **multi-timescale differencing**, and a learned prediction of
a Temporal Stability MOS.

*Why it matters here:* its existence refutes the earlier "no fourth route"
phrasing and shows the field is actively building motion-aligned,
multi-timescale temporal-stability predictors.

*Still rejected:* trained for rendered/game artifacts; short temporal windows;
still flow/warp-based, so it inherits the coverage and resampling confounds;
predicts a learned MOS rather than an interpretable physical diagnosis; and it
supplies no calibrated long-duration stochastic null.

**Temporal edge-detection filters — Ebelin et al., 2024.** "Estimates of
Temporal Edge Detection Filters in Human Vision", *ACM Trans. Applied
Perception* 21(2),
DOI [10.1145/3639052](https://doi.org/10.1145/3639052). Derives human temporal
edge-detection filters from a psychophysical study (models including the
derivative of the infinite symmetric exponential function, and a TCSF-based
model) and demonstrates a proof of concept by putting the filter into a **flicker
detection pipeline**; code is released.

*Why it matters here:* for the eventual perceptual question this is more
naturally localised in *video* space than applying a full-field lighting
sensitivity curve to an attenuation coefficient. **It belongs beside — arguably
before — CIE/elaTCSF in the perceptual escalation path**, which the earlier
perceptual survey missed.

*Still not the Week 8 detector:* perceptual rather than causal; short-timescale;
image- and display-dependent; and camera motion would have to be handled — and
flow-aligning it reintroduces the interpolation and coverage problems the
parameter route exists to avoid.

---

## 13. Adversarial review — every option, argued against

Each candidate is given its strongest case, then the case against. The carried
candidate is attacked hardest, because it is the one that could do damage.

### 13.1 Against the carried candidate (C1, parameter-trajectory testing)

**Best case for it.** No fixed lag, so no aliasing blind spot. Structurally
immune to blur, resampling, masking and coverage. Free. Names the causal
variable. Has a calibrated null. Has an independent precedent as a complete
protocol in fMRI QA.

**Case against — six attacks, three of which land.**

1. **"The parameter may not be a scalar per frame."** *Lands.* Week 5's
   backscatter estimate may be a spatial field, not a number. Reducing it to a
   trace requires a choice (mean? median? a percentile?), and a bad choice can
   hide instability — a field that oscillates with zero spatial mean is
   invisible to the mean. **Mitigation to write into Week 8:** declare the
   reduction explicitly, and compute the battery on more than one reduction
   (mean, median, and a high and low spatial percentile). If they disagree, that
   disagreement is itself the finding.
2. **"Statistical significance is not importance."** *Lands, hard.* With 900
   samples, a peak carrying 0.01 % of the trace's variance can reach p < 0.001
   and mean nothing. A project whose stated discipline is "never treat a metric
   improvement as a successful experiment without visually inspecting the
   output" is exactly the kind that could be misled by a p-value.
   **Mitigation:** the effect size is mandatory, not optional — always report
   the amplitude in the parameter's own physical units and the fraction of
   detrended variance carried, and require *both* before calling anything a
   finding.
3. **"The continuum fit can absorb the signal you are testing for."** *Lands,
   and it is the subtlest failure.* Vaughan's method fits a power-law continuum
   to the periodogram — including the peak. A broad, quasi-periodic pumping
   biases the fitted continuum upward and hides itself. **Mitigation:** fit the
   continuum robustly with candidate peaks excluded and iterate, and never skip
   plotting the PSD. This is a genuine argument for keeping the plain Welch view
   beside the test rather than replacing it.
4. **"Multiple comparisons across parameters × clips × frequencies."** Partly
   lands. Vaughan's trials correction covers frequencies within one trace; it
   does not cover five parameters across five clips. **Mitigation:** predeclare
   which traces are primary before looking, exactly as Phase 2B predeclared its
   fit domain and guards.
5. **"It cannot see spatially localised instability."** Already the stated kill
   criterion (§9); not a new objection.
6. **"It is a second instrument to maintain."** Does not land. It is ~100 lines
   of numpy, needs no new dependency, and lives outside the frozen evaluator.

**Verdict: survives, with three mandatory mitigations** (declared reduction,
effect size beside p-value, robust continuum fit + always plot the PSD). Those
are now conditions of adoption, not optional advice.

### 13.2 Against the runner-up (C6, CIE TN 006 + elaTCSF) — and it is now weaker

**Best case for it.** An absolute threshold at 1.0 that means "just visible",
which is exactly the "how big is too big" question Phase 2B refused to
hard-code. Free, standardised, open code, cheap.

**Case against — and pass 5 added a decisive new argument.**

1. **The threshold transfer was already unvalidated** — `T_v(f)` is calibrated
   for full-field luminance modulation, not for "the attenuation coefficient
   oscillates 3 %".
2. **New: motion silencing.** FS-MOVIE exists because local flicker visibility
   is strongly suppressed by sufficiently large coherent motion (§11.7). Neither
   CIE TN 006 nor elaTCSF models that suppression — their sensitivity data come
   from static, full-field stimuli. Applying a static-stimulus visibility model
   without motion masking can therefore **overestimate local-flicker visibility
   under strong coherent motion**; the size of that error is content- and
   viewing-dependent, so the direction is arguable but the magnitude is not
   known. So the perceptual route is not merely
   unvalidated on our content; it is unvalidated in a way where we can already
   name the sign of the error.
3. **No null distribution.** `M_v1` is a point estimate; it cannot say whether
   a value of 0.9 is real or noise.

**Verdict: demoted from "strong runner-up" to "only after detection fires, and
only after the transfer is validated against measured on-screen modulation".**

### 13.3 Against every rejected candidate, one line each

| candidate | strongest case for it | why it still fails |
|---|---|---|
| Long-range / anchor warp error | genuinely long-range, uses machinery we have | mask empties on a 900-frame swim-through; Phase 2B's own comparability rule makes it undefined before it is wrong |
| Guthier flicker detection | no-reference, 1-D trace, perceptual threshold, trivial | no motion compensation; fires on legitimate scene change, which is the behaviour PLAN explicitly forbids rewarding |
| CTI | no-reference, motion-compensated | SSIM variant — excluded by the brief; blur-rewarding; tunable region threshold |
| FDI | no-reference, block-localised | DIBR-specific, adjacent-frame, block-and-threshold machinery, no long-time trajectory, no calibrated stochastic null. *(Not "gradient-domain": the gradient step is region detection; distortion is measured in the SVD domain — §12.2.)* |
| VBench flickering | human-validated: Spearman ρ ≈ 0.887 metric-vs-human on the Temporal Flickering dimension | requires static scenes; undefined on all five frozen clips. *(Correction: an earlier version cited "~99 %" — that figure is the correlation between human model-preference rankings across evaluation sets, not metric-to-human agreement.)* |
| WCS Flicker Penalty | 2025, "unified", flow-based | it is MC-Warp@1 with fewer guards |
| OMIQ (coding efficiency) | no-reference, whole-sequence, motion-compensated free | blur-gamed by authors' admission; one scalar cannot separate drift/pumping/spike; codec configuration surface |
| RWE / MABD / PSPTNR / TAE | well-established | all require ground truth |
| tOF / tLP | usable without GT via TecoGAN's input-as-reference variant | consecutive-frame; tOF measures motion preservation, not stability; tLP adds LPIPS. tLP retained as a Week 9 candidate |
| FS-MOVIE / MOVIE / T-SSIM / ST-RRED / VQA-SIAT / SR-3DVQA | principled perceptual models | full- or reduced-reference |
| Stability score (stabilization) | the one published trajectory-spectral metric | scores slow drift as *stable* — sign-inverted for our failure mode |
| Trajectory curvature | scale-free, no reference | motion-dominated in image space; blind to drift by design |
| TRAJAN / motion histograms | genuinely long-window | measures motion plausibility, which restoration does not alter |
| ColorVideoVDP | the best temporal vision model available | full-reference, plus a display model |
| Learned NR-VQA (FAST-VQA, DOVER, StableVQA) | correlates with humans | scores attractiveness; blur-sensitive in the wrong direction; against invariant 5 |
| IEC flickermeter | standardised, perceptual | 10-minute window vs our 30 s; filament-lamp calibration |
| JEITA | perceptually filtered spectrum | subsumed by C6, without C6's absolute threshold |
| VESA FMA / percent flicker | trivially cheap | peak-to-peak over the record conflates drift, spike and oscillation |
| IES flicker index | waveform-shape aware | defined per *cycle* — presupposes the period we are trying to detect |
| Allan / Hadamard deviation | noise-type decomposition | ADEV at one τ is the same two-sample family as MC-Warp@k; kept only as a supporting plot |
| Fisher's g / Lomb–Scargle FAP | exact nulls | assume **white** noise; our estimator noise will be red |
| specparam / FOOOF | separates 1/f from peaks | returns parameter estimates, not a decision rule |
| RQA / DFA / EMD / spectral kurtosis | genuinely different mathematics | each introduces free parameters that would have to be tuned against the frozen clips, which PLAN forbids |
| STL / BFAST / SSA | principled trend + seasonal decomposition | subsumed by the battery; STL and BFAST presuppose a known season; SSA retained as an optional view |
| **Wavelet coherence** | time-localised coupling with phase statistics | **not rejected — promoted in pass 6 to the first escalation for ambiguous covariate attribution (§15.2)** |
| Control-theoretic step response (overshoot, settling time, steady-state error) | the exact vocabulary for "follow a true step without overshoot" | **not rejected** — this is the right language for `PLAN.md` Week 5/6's synthetic-transition test and should be used there; it is a stabiliser-tuning diagnostic, not a long-duration stability metric |
| Flow-of-output vs flow-of-input | no-reference, uses machinery we have | answers a different question — whether restoration damages downstream correspondence — worth doing in Week 9 (benchmark/task utility), not Week 8 |

### 13.4 What can and cannot be claimed about coverage

**An earlier version of this section presented a four-axis taxonomy and claimed
"every occupied cell was reached; the carried candidate is the one empty cell".
That claim is withdrawn.** The axes are neither exhaustive nor independent, and
pass 6 found several methods that do not sit cleanly in them — time-localised
wavelet significance, cross-wavelet coherence, Bayesian spectral model
comparison, Gaussian-process QPO-versus-red-noise model selection, learned
motion-aligned temporal-stability streams, and temporal-edge perceptual models
(§12.5, §15). A literature search is open-ended, and a "completeness proof" built
from a self-designed taxonomy is not a proof.

The taxonomy is retained below as a map of *what was searched*, not as an
argument that the search was exhaustive:

```text
SIGNAL        pixels | spatial-frequency coefficients | learned features |
              motion field | point tracks | compression bitstream |
              global scalar trace | physical parameters

COMPARISON    consecutive frames | fixed lag k | to a distant anchor |
              all-pairs matrix | whole trajectory | against a reference video |
              against a covariate

DOMAIN        time | frequency | wavelet | eigen/SVD | phase space

CALIBRATION   none | learned from human MOS | psychophysical threshold |
              statistical null distribution
```

**The defensible claim, and the only one this document now makes:**

> Among the methods reviewed, I did not find a published video metric
> simultaneously satisfying all of: no pristine reference; robustness to
> substantial camera motion; genuinely long-window trajectory analysis;
> interpretable decomposition of drift versus pumping versus spike; and
> calibrated statistical significance.

That is enough to justify carrying the candidate. It is not a claim that no such
method exists anywhere.

**And within the "whole trajectory × statistical calibration" region, the carried
candidate is one option among several**, not a unique occupant — frequentist
periodogram tests, time-localised wavelet significance, Bayesian spectral models
and GP model comparison all live there (§15). That is precisely why the Week 8
design must be a *decision tree* rather than a precommitment to one test
(§15.6).

## 14. Position after five passes — superseded

The five-pass position ("carry one candidate; Vaughan or Thomson as the primary
test") is superseded by §15 and §16, which keep the architectural conclusion but
replace the single-instrument framing with a decision tree and correct six
factual errors. Section number retained so earlier cross-references still
resolve.

---

## 15. Pass 6 — the missed family, and the corrected Week 8 design

An independent review checked this document's central claims against primary
sources and searched beyond its candidate set. It confirmed the architectural
conclusion, found several factual errors (now corrected in place, each marked
*Correction (pass 6)*), and identified **one genuinely strong missed family**
plus three escalation paths. This section records them and revises the Week 8
design accordingly.

### 15.1 The missed family: time-localised wavelet significance

**Torrence & Compo, "A Practical Guide to Wavelet Analysis", *Bull. Amer.
Meteor. Soc.* 79(1):61–78, 1998** —
<https://psl.noaa.gov/people/gilbert.p.compo/Torrence_compo1998.pdf>; software
at <https://github.com/ct6502/wavelets>. Read directly.

**What it provides that nothing else in this review does.** Theoretical white-
and red-noise wavelet power spectra are derived, checked against Monte Carlo,
and used to establish **a null hypothesis for the significance of a peak in the
wavelet power spectrum**. Red noise is modelled as lag-1 autoregressive,
`x_n = alpha·x_{n−1} + z_n`, with normalised Fourier spectrum

```text
P_k = (1 - alpha^2) / (1 + alpha^2 - 2·alpha·cos(2*pi*k/N)),   alpha = 0 -> white
```

Wavelet power at each point is χ²-distributed (2 DOF for a complex wavelet such
as Morlet; 1 DOF for a real-valued one such as the DOG/Mexican hat), and
smoothing in time or scale raises the DOF and therefore the confidence, with
empirical DOF formulas given. The **cone of influence** is defined as the
e-folding time of the autocorrelation of wavelet power at each scale, chosen so
that power from an edge discontinuity falls by `e^-2`.

**Why this is the right tool for a case the carried candidate handles badly.**
The plausible Week 8 failure is not necessarily a coherent 3.2 Hz line for the
whole 30 s. It could be:

```text
seconds  0-8    quiet
seconds  8-17   pumping at 2.4-3.1 Hz
seconds 17-30   quiet
```

or a frequency that wanders with swell, motion or estimator state. A global
periodogram test **averages the temporal localisation away**, and Thomson's
F-test is deliberately tuned for a strictly periodic, phase-coherent line —
exactly the wrong instrument for a transient burst. A continuous wavelet
transform gives `P(t, f)` rather than only `P(f)`, *with* a significance level
against a fitted white- or red-noise background.

The cone of influence is not a footnote for us: on a **30 s record** it removes a
substantial fraction of the time–frequency plane at the low frequencies where
slow pumping would live. That is a quantitative limit Week 8 must state up front,
in the same spirit as the existing "a 30 s clip cannot separate a 30 s-period
oscillation from drift".

### Mandatory caveat: pointwise wavelet significance is not enough

Torrence & Compo give the significance of wavelet power **at a point** against a
white- or red-noise background. Scanning an entire time–frequency plane and
circling every point above a nominal 95 % threshold is a large multiple-
comparisons problem — later literature says so explicitly, and by construction a
95 % pointwise threshold marks ~5 % of a null plane as "significant".

This matters more here than it would elsewhere, because the whole reason for
choosing this family over an image-space metric was **calibrated significance**.
A wavelet plot decorated with spurious pointwise contours would forfeit exactly
the advantage being bought.

Requirement:

> Predeclare the searched region of the time–frequency plane where possible, or
> control/calibrate a **global** false-positive rate — by null simulation, a
> max-statistic, or another defensible multiplicity treatment — before any
> wavelet feature is reported as significant.

**Status: promoted to a first-class branch of the Week 8 decision tree** (§15.6),
not an optional extra. This was a real omission from passes 1–5, where wavelets
appeared only inside RobustPeriod and as a dismissed "optional view".

### 15.2 Attribution, done properly: cross-wavelet and wavelet coherence

**Grinsted, Moore & Jevrejeva, "Application of the cross wavelet transform and
wavelet coherence to geophysical time series", *Nonlinear Processes in
Geophysics* 11:561–566, 2004**,
DOI [10.5194/npg-11-561-2004](https://doi.org/10.5194/npg-11-561-2004); software
released.

The earlier design proposed attributing a peak by running the same spectrum on
input-derived covariates and checking whether the same bump appears. That is
primitive. Cross-wavelet transform and wavelet coherence examine the
relationship between two series **in time–frequency space**, with **phase-angle
statistics** to test whether a relationship is consistent with a causal
mechanism, and **Monte Carlo significance against red-noise backgrounds**.

For our attribution problem this is close to tailor-made:

```text
backscatter_parameter(t)   vs   camera_motion_magnitude(t)
attenuation_R(t)           vs   input frame-mean luminance(t)
parameter(t)               vs   range(t)
```

The difference in evidential strength is large. "Both PSDs have a bump near
0.6 Hz" is weak. "The parameter and the camera-motion magnitude are coherent at
0.6 Hz **only during seconds 8–18**, with a stable phase relationship" is strong
evidence of legitimate scene/camera coupling rather than restoration
instability — and it is precisely the discrimination `PLAN.md` Week 8 §4 asks for
when it says the objective is to identify *cause*.

**What it does and does not establish.** Grinsted et al. use phase-angle
statistics to build confidence in causal relationships and to test mechanistic
models, with Monte Carlo significance against red-noise backgrounds. But
coherence can also arise from a **common driver**. The permanent wording:

> Significant coherence plus a stable phase relationship strengthens the evidence
> for mechanistic coupling. It does not by itself establish causality, and it
> does not prove the covariate *caused* the parameter variation.

**Status: the first escalation for attribution**, to be used when ordinary
covariate inspection is ambiguous. Not implemented by default.

### 15.3 Two further escalation paths, for when the null model is the problem

* **Bayesian spectral analysis — Vaughan (2010).** A Bayesian successor to the
  2005 test, using MCMC and posterior predictive checking, motivated by the fact
  that continuum-model choice materially changes claimed periodicity
  significance. Use only if the null-model choice becomes the limiting
  uncertainty — which is a more principled escalation than repeatedly patching a
  power-law fit.
* **Gaussian-process QPO-versus-red-noise model comparison — Hübner et al.**
  Uses GPs to distinguish quasi-periodic signals from red noise, explicitly
  noting that heteroscedasticity and non-stationarity can bias periodogram
  analyses. Almost certainly overkill for Week 8; recorded because it is a real
  alternative occupant of the "trajectory × statistical calibration" region and
  therefore part of why §13.4's completeness claim was withdrawn.

### 15.4 Do not precommit to a noise model — and analyse innovations separately

**Correction to the carried candidate's framing.** Passes 2–5 leaned toward
"the estimator noise will be red, therefore Vaughan". That is a plausible guess
about an estimator **that does not exist yet**, and Vaughan himself stresses that
a periodicity result is only as good as the assumed background spectrum: a poorly
fitting AR(1) or power law manufactures false detections. The Week 8 order must
therefore be:

```text
1. inspect the trace and the innovations
2. characterise the background spectrum empirically
3. choose a null model AND test its adequacy
4. only then test for periodicity
```

**A second, deeper correction: a physical parameter is not expected to be
white.** Water genuinely changes; a descent genuinely changes attenuation. What
has a principled claim to whiteness is the **innovation / prediction residual**
of a correctly specified estimator. So Weeks 5–6 must persist, *separately*:

```text
raw per-frame physical estimate
stabilised estimate
innovation / prediction residual
estimator uncertainty or covariance, where the model provides one
input-derived covariates
```

and Week 8 then asks four different questions rather than one:

```text
raw estimate    -> did the estimated environment genuinely change?
stabilised      -> did the correction parameters pump?
innovation      -> is the estimator/filter mis-specified or under-modelled?
output          -> did any of that become visible?
```

**Also:** the NIS χ² consistency test named in §8 is appropriate **only if the
estimator actually supplies a defensible innovation covariance** — i.e. a
probabilistic state-space formulation. Do not bolt NIS onto an EMA or an ad-hoc
adaptive smoother merely because it is standard filter theory.

### 15.5 The spatial-field problem needs more than four summary statistics

§13.1's mitigation — compute the battery on the mean, median and a high and low
spatial percentile of a parameter *field* — is better than a single mean but does
not guarantee detection. A field can oscillate with an essentially zero global
mean:

```text
left half   +delta
right half  -delta
alternating in time
```

Every global summary stays flat forever. If parameter fields become real, the
principled escalation is:

```text
P(x, y, t)
  -> low-rank spatial decomposition, or fixed physically meaningful regions
  -> a few temporal component trajectories
  -> the same Week 8 temporal analysis on each
```

Not to be built now. Recorded so the permanent note does not imply that four
summary statistics are sufficient.

### 15.6 The corrected Week 8 design

This supersedes the single-instrument framing of §9. Phase 2B is unchanged in
both versions.

```text
WEEKS 5-6  (do this now, it is the only irreversible item)
  persist per frame, unsummarised:
      raw physical estimates
      stabilised estimates
      innovations / residuals
      estimator confidence or covariance where meaningful
      input-derived covariates (luminance, camera motion, range)
  on synthetic transitions, record control-theoretic step response:
      settling time | lag | overshoot | steady-state error

WEEK 8  DEFAULT — no test chosen in advance
  plot the trajectories
  robust effect sizes (physical units, always)
  spike statistics (robust z on max |delta p|)
  ACF, PSD, drift (Sen slope + autocorrelation-aware significance)
  the frozen Phase 2B per-pair appearance trajectory
  characterise the background spectrum; do NOT assume it

BRANCH  approximately stationary, phase-coherent pumping
  -> validated continuum + multitaper / periodogram significance
     (Thomson F-test; Vaughan if a power-law continuum genuinely fits)

BRANCH  transient, bursty, or frequency-wandering pumping
  -> time-localised wavelet power with a validated background
     (Torrence & Compo; respect the cone of influence on a 30 s record)
     pointwise significance is NOT sufficient over a whole t-f plane:
     predeclare the searched region or control a global false-positive rate

BRANCH  attribution to motion / illumination / range is ambiguous
  -> cross-wavelet transform and wavelet coherence with covariates
     (Grinsted et al.; phase statistics, Monte Carlo significance)
     coherence + stable phase = evidence of coupling, NOT causality:
     a common driver produces both

BRANCH  traces are outlier- or trend-contaminated, or carry several periods
  -> RobustPeriod

BRANCH  null-model choice is the limiting uncertainty
  -> Bayesian spectral analysis; GP QPO-vs-red-noise model comparison

BRANCH  output flickers while every physical trace is clean
  -> flow-aligned appearance trajectories (the §9 contingency)

PERCEPTUAL QUESTION — only after detection, never before
  -> temporal-edge perceptual models (Ebelin et al.)
  -> CIE TN 006 + elaTCSF, with the transfer validated first
  -> ColorVideoVDP in a well-posed A/B (dynamic vs frozen parameters),
     read as "is the difference between two pipeline variants visible",
     never as "is the restoration correct"

NEVER CONFLATE
  statistical significance | physical amplitude | perceptual visibility
```

**The MC-Warp lag sweep is demoted to a contingency.** §9 step 5 proposed a
30-lag sweep as a mandatory characterisation. It is intellectually neat and the
cost estimate (~8.5 min) stands, but as a *required* measurement it walks straight
back into coverage decay, correspondence error, resampling floor and
lag-dependent visible regions — the four things the parameter route exists to
escape. Use it only to demonstrate an appearance-space signature for a
periodicity the parameter traces have already found, or when parameter-space and
image-space evidence disagree.

### 15.7 Adoption preconditions, consolidated

**These are six *conditions*, not six instruments.** They are the methodological
preconditions the carried family must satisfy before it may be adopted. The
inventory of instruments actually being carried is §16.1.

The carried candidate is adopted only if all six hold:

1. **Declared spatial reduction**, with sensitivity checks across several
   reductions — and §15.5's escalation if fields are involved.
2. **Effect size beside every p-value**, in the parameter's own physical units
   and as a fraction of detrended variance. Significance without amplitude is
   not a finding.
3. **Background spectrum characterised and its adequacy tested** before any
   periodicity test; the PSD always plotted.
4. **Autocorrelation-aware trend testing** — prewhitened or variance-corrected
   Mann–Kendall, or a GLS/state-space trend test — with Sen's slope as the
   robust effect size.
5. **Multiplicity controlled at every level at which it exists.**

   ```text
   within one trace     trials correction over the scanned frequencies
   across a t-f plane   pointwise wavelet significance is NOT sufficient;
                        predeclare the searched region, or calibrate a global
                        false-positive rate (null simulation / max-statistic)
   above the trace      5 clips x several parameters x several spatial
                        reductions x several diagnostics. Predeclare a SMALL
                        confirmatory family, or correct across it. Everything
                        outside that family is labelled EXPLORATORY and cannot
                        support a conclusion on its own.
   ```

6. **The background fit is predeclared, or the whole procedure is calibrated.**
   An earlier version of this document said "robust continuum fit with candidate
   peaks excluded". That mitigation, taken naively, is itself a selection bias:
   identifying peaks from the same data, removing them, refitting a lower
   continuum, and then applying a significance formula that assumes the continuum
   was fitted independently will overstate significance. The safe rule:

   > Use a predeclared robust background-fitting procedure. If the fit involves
   > data-driven peak exclusion or any iterative selection, calibrate the
   > **entire fit → exclusion → test pipeline** under the null, by simulation or
   > posterior predictive checking.

   This is also the sharpest argument for the Bayesian escalation in §15.3:
   continuum-model uncertainty, nuisance parameters and data-driven selection all
   change significance, and a posterior predictive framework accounts for them
   rather than patching around them.

---

## 16. Final position

### 16.1 Inventory — what is actually being carried

The rejection in this document is narrow: **do not add another image-space
pairwise metric to the frozen Phase 2B evaluator.** That is one rejection, not a
blanket one. The following are adopted, conditionally adopted, or carried:

| # | instrument | status | where |
|---|---|---|---|
| 1 | Welch PSD of the detrended trace | adopted — default view | §15.6 |
| 2 | Ljung–Box whiteness | adopted — companion | §6 C2 |
| 3 | Sen's slope + autocorrelation-aware trend test | adopted — drift | §15.7 |
| 4 | Robust z on max \|Δp\| | adopted — spikes | §8 |
| 5 | Overlapping ADEV vs τ | adopted — timescale-dependent stability | §6 C4 |
| 6 | **Torrence & Compo wavelet significance** | branch — transient/wandering pumping | §15.1 |
| 7 | Thomson multitaper harmonic F-test | branch — stationary coherent line | §6 C2b |
| 8 | Vaughan red-noise periodogram test | branch — *if* a power-law continuum fits | §6 C1a |
| 9 | **Grinsted cross-wavelet coherence** | first escalation — attribution | §15.2 |
| 10 | RobustPeriod | escalation — dirty traces, multiple periods | §6 C3 |
| 11 | Bayesian spectral / GP QPO comparison | escalation — null-model uncertainty | §15.3 |
| 12 | Control-theoretic step response (settling, lag, overshoot, steady-state error) | **adopted outright, Weeks 5–6** | §13.3 |
| 13 | Kalman innovation whiteness / NIS | conditional — only with a defensible covariance | §15.4 |
| 14 | fMRI-QA protocol shape | methodological template | §6 C5 |
| 15 | PELT / `ruptures` change-point | retained — case I | §9 |
| 16 | Motion silencing | adopted — interpretation rule | §9, §11.7 |
| 17 | **Per-frame log-average brightness trace** | adopted — free, available now | §17.1 |
| 18 | x–t spatio-temporal slice | adopted — free inspection | §9 |
| 19 | Long-range anchor warp error | conditional — `murky_shark` only | §17 |
| 20 | Eulerian Video Magnification | conditional — `murky_shark` only | §17 |
| 21 | IES flicker index | conditional — only once a period is known | §17.2 |
| 22 | tLP, tOF | deferred — Week 9 task preservation | §12, §17.2 |
| 23 | Ebelin temporal-edge → CIE+elaTCSF → ColorVideoVDP A/B | perceptual escalation, after detection only | §15.6 |

Twenty-three items, of which four are adopted outright and available before any
estimator exists (5, 12, 17, 18 — plus 16, which is a reading rule). What is
rejected is the thing that would have been easiest to add and least useful:
another pairwise flicker number.

### 16.2 Position after seven passes


**Unchanged, and now independently checked: Phase 2B stays frozen. No new
image-space flicker or video metric is added.**

**Changed by pass 7** (final editorial and statistical cleanup):

1. §1 rewritten to match §15.6 — it no longer names a "primary" test.
2. Stale pre-pass-6 cells cleaned from the §2 survey table, the §6 summary
   table, the §8 battery, §11.9 and §13.3.
3. §9 marked **historical**; implement from §15.6.
4. **Wavelet multiplicity requirement added** (§15.1) — pointwise significance
   over a whole time–frequency plane is not sufficient.
5. **Multiplicity above the trace added** (§15.7 condition 5) — clips ×
   parameters × reductions × diagnostics.
6. **"Exclude peaks and refit" replaced** (§15.7 condition 6) — that mitigation
   is itself a selection bias unless the whole pipeline is calibrated under the
   null.
7. Wavelet coherence qualified as **association, not causation**.
8. The CIE/motion-silencing claim softened from "known direction" to
   content- and viewing-dependent.
9. Instrument inventory added (§16.1), after the six *preconditions* were
   mistaken for a count of six carried instruments.

**Changed by pass 6:**

1. **Six factual corrections** made in place: MAWE is *not* the motion-reduction
   ratio; tOF/tLP are *not* inherently ground-truth-only; VBench's flicker
   metric correlates with humans at ρ ≈ 0.887, not "~99 %"; FDI's SVD stage was
   misdescribed as gradient-domain; the long-video-depth field *does* evaluate
   consistency quantitatively; and the IEC flickermeter's incandescent-lamp
   calibration is not a categorical bar, since CIE documents a modified form.
2. **One genuinely missed family promoted**: time-localised wavelet
   significance (Torrence & Compo), for transient or frequency-wandering
   pumping that a global spectral test averages away.
3. **Attribution upgraded** from "does the same bump appear in a covariate?" to
   cross-wavelet coherence with phase statistics.
4. **Three statistical overclaims withdrawn**: the red-noise precommitment, the
   Ljung–Box authorisation gate, and plain Mann–Kendall.
5. **The "completeness proof" withdrawn** (§13.4) and replaced with a bounded,
   defensible claim.
6. **Week 8 is now a decision tree, not a single instrument** (§15.6), with four
   consolidated adoption conditions (§15.7).
7. **The document is retitled** from "exhaustive" to "comprehensive adversarial"
   literature review.

**The single action item that is time-sensitive and irreversible:** Weeks 5–6
must persist unsummarised per-frame raw estimates, stabilised estimates,
innovations and covariates. Everything else in this document can wait for
Week 8. That cannot — if those traces are summarised away, the entire
recommended analysis becomes impossible.

---

## 17. Partial applications — methods that fail in general but hold under stated conditions

Passes 1–6 judged each candidate against the *whole* frozen test set and rejected
anything that failed on the hard clips. That was too binary. Several rejected
methods fail for one specific reason — **camera motion** — and the test set
contains a clip where that reason does not apply.

**`murky_shark` is the project's static-scene probe.** Phase 2B measured it:
0.03 px/frame at @1, a motion-reduction ratio of only 1.37× at @1 because
"motion compensation barely helps, because there is barely any motion", and
coverage of 96.3 / 90.9 / 89.7 % at @1/@4/@8 — "the least lag decay of any clip,
because almost nothing leaves the frame". It is also where gray-world's relative
jump was largest (2.73×) and where Phase 2B noted flicker "is most visible to the
eye" — which motion silencing (§11.7) now explains as partly an observer effect,
not only signal-to-noise.

That single fact reopens four rejections **on that clip only**.

| method | general rejection | condition under which it holds | what it buys |
|---|---|---|---|
| **Long-range / anchor warp error** (Lai; Lei Eqs. 6–7) | mask empties over hundreds of frames of translation | `murky_shark`, where coverage is nearly flat with lag | a genuine long-range appearance comparison using **frozen machinery only**, on the one clip where it is defined |
| **VBench's static-scene design** | requires static footage we do not have | we do have one: `murky_shark` | reframes an existing asset — the least motion-confounded flicker probe in the test set |
| **Eulerian Video Magnification** (Wu et al. 2012) | assumes a near-static camera; amplifies parallax on a swim-through | `murky_shark` approximately satisfies the assumption | a *visualisation* that makes sub-threshold pumping visible, on the one clip where it is valid |
| **Guthier's signal** (not his detector) | the detector has no motion compensation and fires on real scene change | use the **signal**, drop the detector and the JND threshold | see below — this one applies everywhere, not just to `murky_shark` |

### 17.1 The log-average brightness trace — free, and worth having in Week 8

Guthier's per-frame brightness measure is the geometric mean

```text
I_bar(t) = exp( (1/n) * sum_j log( I_j(t) + delta ) )
```

chosen over the arithmetic mean because it resists outliers and better matches
perceived average brightness. Boitard reaches for the same construction ("an
overall brightness metric can be, for example, the mean luma value of an image",
perceptually encoded before averaging), and Deep Video Prior plots mean intensity
per frame for the same purpose. Three independent communities converge on it.

**What is rejected is Guthier's *detector*** — consecutive-frame differencing
against a JND threshold, with no motion compensation, which on our footage fires
on legitimate scene change and would reward a stabiliser that lags a real
transition.

**What is adopted is the *signal*.** Computed per frame on the **input** and on
the **corrected output** separately, it is:

* free — no optical flow, no warp, no mask, no resampling, no inference;
* available immediately, before any physical estimator exists;
* the natural appearance-space companion to the parameter traces, and the
  concrete form of the §9 contingency;
* interpretable only in comparison — the corrected trace against the input
  trace, exactly the discipline of the frozen evaluator's `--method none`
  baseline.

Feed it to the same §8 battery. It is not an addition to the frozen Phase 2B
metrics; it is a covariate.

### 17.2 Two smaller conditional inclusions

* **IES flicker index** — `area above the mean / total area`, per cycle. Rejected
  as a detector because it presupposes the period. **But once a period has been
  established** by §15.6's branch, it is a cheap waveform-shape descriptor that
  separates a smooth sinusoid from a spiky sawtooth at equal amplitude — which
  matters, because those two have different causes.
* **tOF** (TecoGAN) — flow computed on the corrected output versus flow computed
  on the input. Rejected for Week 8 because it measures motion preservation, not
  stability. **Adopted as a Week 9 question:** does restoration perturb estimated
  correspondence? SEA-RAFT is already wired in, so the cost is inference only.

### 17.3 The general lesson

A candidate should be judged against **the spread of the frozen test set**, not
against its hardest member. `CLAUDE.md` invariant 6 already says this for
pipeline changes — "if a change helps one category and hurts another, document
the tradeoff" — and it applies to instruments too. Several methods above are
usable on one category and not others; the correct disposition is a stated
condition, not a blanket rejection.
