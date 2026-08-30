"""Week 2 Phase 2B — synthetic validation of the motion-aware temporal metrics.

Everything here runs in the ordinary project venv with an ANALYTIC flow
backend: a stub that returns a flow field the test itself constructs. That is
deliberate. Using a real network would fold two unknowns together — "is the
metric right?" and "did SEA-RAFT find the right correspondence?" — and only
the first is under test here. With exact known correspondence, any residual
the metric reports is the metric's own behaviour.

The cases follow the Phase 2B brief:

  A  stable integer translation          -> raw and illum-aware MC-Warp ~0
  B  stable fractional translation       -> small nonzero, characterised
  C  global gain change                  -> raw rises, canonical drops
  D  global gain + bias                  -> raw rises, canonical drops
  E  corrected-only red flicker          -> canonical must NOT remove it
  F  one-frame appearance spike          -> a clear per-pair spike
  G  blur                                -> lowers a temporal score (not a win)
  H  occlusion / disocclusion            -> excluded, denominator correct
  I  localised illumination              -> global model explains only part
  J  coverage gaming                     -> lower score comes with lower coverage

plus the invariants: correspondence and illumination parameters come only
from the original input, lags use direct flow with no chaining, inference is
reused, nothing unbounded is retained, and no weighted overall score exists.
"""

import dataclasses

import cv2
import numpy as np
import pytest

from uw import metrics as M
from uw.flow import FlowResult, OpticalFlowBackend
from uw.metrics import (
    BackendComparison,
    BackendComparisonCell,
    IlluminationFit,
    compare_backends_common_mask,
    TemporalLagMetrics,
    TemporalMetrics,
    alignment_robust_warp_error,
    apply_illumination,
    evaluate_temporal,
    evaluate_temporal_pair,
    fit_illumination,
    linear_luminance,
    metric_eval_size,
    temporal_delta_e,
    temporal_warp_error,
    warp_with_support,
)
from uw.types import Frame

H, W = 180, 320


# ---------------------------------------------------------------------------
# Analytic backends
# ---------------------------------------------------------------------------


class ConstantFlowBackend(OpticalFlowBackend):
    """Returns a rigid (u, v) displacement scaled by the requested lag.

    The lag scaling is what makes it a legitimate stand-in for a *direct*
    lag-k estimator: asked for t -> t+4 it returns 4x the per-frame motion in
    one field, exactly as a direct inference would, never a composition of
    four adjacent fields.
    """

    name = "analytic_constant"

    def __init__(self, u=0.0, v=0.0):
        self.u, self.v = float(u), float(v)
        self.calls = []

    def describe(self):
        return {"backend": self.name, "u": self.u, "v": self.v}

    def estimate(self, frames, index_t, index_t1):
        self.calls.append((index_t, index_t1))
        h, w = frames[index_t].image.shape[:2]
        k = index_t1 - index_t
        flow = np.zeros((h, w, 2), np.float32)
        flow[..., 0] = self.u * k
        flow[..., 1] = self.v * k
        return FlowResult(flow=flow, valid_mask=np.ones((h, w), bool),
                          metadata={"inference_size": (h, w),
                                    "index_t": index_t, "index_t1": index_t1})


class FieldBackend(OpticalFlowBackend):
    """Returns caller-supplied forward/backward fields, so a test can make the
    forward/backward consistency check disagree wherever it likes."""

    name = "analytic_field"

    def __init__(self, forward, backward):
        self.forward, self.backward = forward, backward
        self.calls = []

    def describe(self):
        return {"backend": self.name}

    def estimate(self, frames, index_t, index_t1):
        self.calls.append((index_t, index_t1))
        flow = self.forward if index_t1 > index_t else self.backward
        return FlowResult(flow=flow.astype(np.float32).copy(),
                          valid_mask=np.isfinite(flow).all(axis=2),
                          metadata={"inference_size": flow.shape[:2]})


# ---------------------------------------------------------------------------
# Sequence builders
# ---------------------------------------------------------------------------


def texture(h=H, w=W, seed=0):
    """A textured, non-negative linear-light image with real gradients.

    Random noise alone would make every alignment test trivially hard and
    every blur test trivially easy, so this is smoothed noise plus hard edges
    — the mix of soft texture and high-contrast boundaries that the alignment
    sensitivity question is actually about.
    """
    rng = np.random.default_rng(seed)
    base = rng.random((h, w, 3)).astype(np.float32)
    base = cv2.GaussianBlur(base, (0, 0), 2.0)
    base = (base - base.min()) / (base.max() - base.min())
    base = base * 0.5 + 0.08
    base[40:80, 60:140] += 0.25          # a bright rectangle: hard edges
    base[:, 200:204] = 0.72              # a thin vertical bar: sub-pixel bait
    return np.clip(base, 0.0, 1.0).astype(np.float32)


def frames_of(images):
    return [Frame(image=np.asarray(im, np.float32), metadata={"frame_index": i})
            for i, im in enumerate(images)]


def translate(image, dx, dy):
    """Shift content by (dx, dy) px with the same bilinear resampler the
    metric uses, so integer shifts are exact and fractional ones are not."""
    h, w = image.shape[:2]
    xs, ys = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    return cv2.remap(np.asarray(image, np.float32),
                     (xs - dx).astype(np.float32), (ys - dy).astype(np.float32),
                     interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)


def translating_sequence(n, dx, dy, seed=0):
    base = texture(seed=seed)
    return frames_of([translate(base, dx * i, dy * i) for i in range(n)])


def interior(mask_shape, margin=20):
    """A mask that avoids the frame border, where resampling a translated
    synthetic sequence invents content that no metric should be judged on."""
    m = np.zeros(mask_shape, bool)
    m[margin:-margin, margin:-margin] = True
    return m


# ===========================================================================
# cv2.remap / coordinate-convention correctness  (Phase 2B section 13)
# ===========================================================================


def test_remap_receives_contiguous_float32_absolute_maps(monkeypatch):
    """The maps handed to cv2.remap must be absolute source coordinates, in
    float32, C-contiguous — the four things that silently corrupt a warp."""
    captured = {}
    real_remap = cv2.remap

    def spy(src, map1, map2, **kw):
        captured["map1"], captured["map2"] = map1, map2
        captured["interpolation"] = kw.get("interpolation")
        return real_remap(src, map1, map2, **kw)

    monkeypatch.setattr(cv2, "remap", spy)
    img = texture()
    flow = np.zeros((H, W, 2), np.float32)
    flow[..., 0] = 3.0
    flow[..., 1] = -2.0
    warp_with_support(img, flow)

    for key in ("map1", "map2"):
        arr = captured[key]
        assert arr.dtype == np.float32, f"{key} dtype is {arr.dtype}, not float32"
        assert arr.flags["C_CONTIGUOUS"], f"{key} is not C-contiguous"
        assert arr.shape == (H, W)
    # Absolute, not relative: map_x = x + u, map_y = y + v.
    xs, ys = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    assert np.allclose(captured["map1"], xs + 3.0)
    assert np.allclose(captured["map2"], ys - 2.0)
    assert captured["interpolation"] == cv2.INTER_LINEAR


def test_warp_direction_sign_and_axes_are_not_interchangeable():
    """A sign flip, a reversed direction or an x/y swap must all be visible.

    Uses |dx| != |dy| with opposite signs, so no symmetry can hide a mistake.
    """
    base = texture()
    dx, dy = 7.0, -3.0
    target = translate(base, dx, dy)      # content moved by (+7, -3)
    flow = np.zeros((H, W, 2), np.float32)
    flow[..., 0], flow[..., 1] = dx, dy

    ok_warp, _ = warp_with_support(target, flow)
    m = interior((H, W))
    correct = float(np.abs(ok_warp[m] - base[m]).mean())

    def residual(u, v, swap=False):
        f = np.zeros((H, W, 2), np.float32)
        f[..., 0], f[..., 1] = (v, u) if swap else (u, v)
        w, _ = warp_with_support(target, f)
        return float(np.abs(w[m] - base[m]).mean())

    assert correct < 2e-3
    assert residual(-dx, -dy) > 20 * correct      # sign flip
    assert residual(dx, dy, swap=True) > 20 * correct   # x/y swap
    assert residual(dx + 1.0, dy) > 5 * correct   # off-by-one


def test_resized_flow_vectors_rescale_with_the_grid():
    """A lag-k field resized to another grid must change magnitude with it."""
    from uw.flow import resize_flow
    flow = np.zeros((H, W, 2), np.float32)
    flow[..., 0], flow[..., 1] = 8.0, -4.0
    half = resize_flow(flow, H // 2, W // 2)
    assert np.allclose(half[..., 0], 4.0, atol=1e-5)
    assert np.allclose(half[..., 1], -2.0, atol=1e-5)


def test_warp_support_excludes_nonfinite_and_out_of_frame():
    img = texture()
    img[100, 100] = np.nan
    flow = np.zeros((H, W, 2), np.float32)
    warped, ok = warp_with_support(img, flow)
    # the NaN pixel and its bilinear support are unusable...
    assert not ok[100, 100]
    # ...and nothing non-finite escapes into the warped image where ok.
    assert np.isfinite(warped[ok]).all()

    flow[..., 0] = 10_000.0
    _, ok_out = warp_with_support(texture(), flow)
    assert not ok_out.any()


# ===========================================================================
# Case A — stable integer translation
# ===========================================================================


def test_case_a_integer_translation_has_near_zero_warp_error():
    seq = translating_sequence(12, 3, 2)
    backend = ConstantFlowBackend(3.0, 2.0)
    result = evaluate_temporal(seq, seq, backend, lags=(1, 4, 8),
                               n_anchors=2, eval_long_side=None)
    for lag in result.lags:
        assert lag.raw_warp is not None
        assert lag.raw_warp < 1e-3, f"lag {lag.lag} raw MC-Warp {lag.raw_warp}"
        assert lag.illumination_aware_warp < 1e-3
        # the uncompensated residual is orders of magnitude larger — motion
        # compensation is doing the work, not a low-contrast scene
        assert lag.uncompensated > 100 * max(lag.raw_warp, 1e-9)
        assert lag.temporal_delta_e < 0.5
        assert lag.valid_fraction > 0.5


# ===========================================================================
# Case B — stable fractional translation (alignment sensitivity)
# ===========================================================================


def test_case_b_fractional_translation_residual_is_small_but_nonzero():
    """Characterises the floor imposed by bilinear resampling alone.

    The sequence has *no* appearance change: a sub-pixel shift plus a warp
    back with the exactly correct flow. Whatever residual remains is pure
    interpolation/resampling error, and it is not zero — that is the number
    the alignment-sensitivity study in FINDINGS.md quantifies against real
    footage.
    """
    seq = translating_sequence(4, 0.5, 0.25)
    backend = ConstantFlowBackend(0.5, 0.25)
    frac = evaluate_temporal(seq, seq, backend, lags=(1,), n_anchors=1,
                             eval_long_side=None).lag(1)

    integer = evaluate_temporal(translating_sequence(4, 1, 0),
                                translating_sequence(4, 1, 0),
                                ConstantFlowBackend(1.0, 0.0), lags=(1,),
                                n_anchors=1, eval_long_side=None).lag(1)

    assert frac.raw_warp > integer.raw_warp
    assert frac.raw_warp < 0.02, "sub-pixel resampling floor is unexpectedly large"
    # It is a real floor, not noise: it must be well above the integer case.
    assert frac.raw_warp > 5 * max(integer.raw_warp, 1e-9)


def test_alignment_robust_companion_lowers_the_subpixel_floor():
    """The companion exists only if a fixed low-pass materially suppresses
    the sub-pixel floor. This pins that behaviour; it never replaces MC-Warp."""
    seq = translating_sequence(4, 0.5, 0.25)
    flow = np.zeros((H, W, 2), np.float32)
    flow[..., 0], flow[..., 1] = 0.5, 0.25
    raw, _ = temporal_warp_error(seq[0].image, seq[1].image, flow)
    robust, _ = alignment_robust_warp_error(seq[0].image, seq[1].image, flow)
    assert robust < raw


# ===========================================================================
# Case C / D — global gain, and gain + bias
# ===========================================================================


def _gain_bias_sequence(gain, bias, n=6, dx=2, dy=1):
    """Frame i = gain^i * translate(base) + bias*i — a legitimate, simple,
    global illumination/exposure ramp riding on top of known motion."""
    base = texture(seed=3)
    out = []
    for i in range(n):
        img = translate(base, dx * i, dy * i) * (gain ** i) + bias * i
        out.append(np.clip(img, 0.0, 1.2).astype(np.float32))
    return frames_of(out)


def test_case_c_global_gain_raises_raw_and_the_canonical_metric_removes_it():
    seq = _gain_bias_sequence(gain=1.10, bias=0.0)
    stable = translating_sequence(6, 2, 1, seed=3)
    backend = ConstantFlowBackend(2.0, 1.0)

    gained = evaluate_temporal(seq, seq, backend, lags=(1,), n_anchors=1,
                               eval_long_side=None).lag(1)
    flat = evaluate_temporal(stable, stable, backend, lags=(1,), n_anchors=1,
                             eval_long_side=None).lag(1)

    assert gained.raw_warp > 10 * flat.raw_warp, "gain must raise raw MC-Warp"
    assert gained.illumination.status == "fitted"
    assert gained.illumination.gain == pytest.approx(1 / 1.10, rel=0.05)
    # the canonical metric explains most of a legitimate global gain
    assert gained.illumination_aware_warp < 0.25 * gained.raw_warp
    assert gained.illumination_explained_fraction > 0.75


def test_case_d_gain_plus_bias_is_within_model_capacity():
    seq = _gain_bias_sequence(gain=1.08, bias=0.03)
    backend = ConstantFlowBackend(2.0, 1.0)
    lag = evaluate_temporal(seq, seq, backend, lags=(1,), n_anchors=1,
                            eval_long_side=None).lag(1)
    assert lag.illumination.status == "fitted"
    assert lag.illumination.gain == pytest.approx(1 / 1.08, rel=0.08)
    assert lag.illumination.bias < 0.0   # inverse of a positive additive step
    assert lag.illumination_aware_warp < 0.3 * lag.raw_warp
    assert lag.illumination_explained_fraction > 0.7


# ===========================================================================
# Case E — corrected-only red-channel flicker  (the anti-gaming test)
# ===========================================================================


def _red_flicker(frames, amplitude=0.15):
    out = []
    for i, f in enumerate(frames):
        img = f.image.copy()
        img[..., 0] *= (1.0 + amplitude) if i % 2 else (1.0 - amplitude)
        out.append(img)
    return frames_of(out)


def test_case_e_corrected_only_red_flicker_survives_the_canonical_metric():
    """THE critical anti-gaming case.

    The input is temporally stable, so the input-derived illumination
    transform is the identity. The simulated corrected output pumps its red
    channel. The canonical metric must report that pumping essentially
    undiminished — if illumination parameters were ever fitted on the
    corrected frames, a scalar gain would absorb part of it and the metric
    would be helping a restoration hide its own flicker.
    """
    original = translating_sequence(6, 2, 1, seed=5)
    corrected = _red_flicker(original)
    backend = ConstantFlowBackend(2.0, 1.0)
    lag = evaluate_temporal(original, corrected, backend, lags=(1,), n_anchors=2,
                            eval_long_side=None).lag(1)

    assert lag.input_raw_warp < 1e-3                 # the input really is stable
    assert lag.illumination.gain == pytest.approx(1.0, abs=0.02)
    assert lag.illumination.bias == pytest.approx(0.0, abs=0.005)

    assert lag.raw_warp > 0.01, "the flicker must show up at all"
    # not fitted away: the canonical value stays within a few percent of raw
    assert lag.illumination_aware_warp > 0.95 * lag.raw_warp
    assert lag.temporal_delta_e > 1.0                # and it is a colour change
    assert lag.temporal_delta_e > 10 * lag.input_temporal_delta_e


def test_illumination_fit_never_sees_the_corrected_frames():
    """Same fit, whatever the corrected sequence is. Structural, not statistical."""
    original = _gain_bias_sequence(gain=1.1, bias=0.02)
    backend = ConstantFlowBackend(2.0, 1.0)

    fits = []
    for corrected in (original,
                      _red_flicker(original, 0.4),
                      frames_of([f.image * 0.3 + 0.2 for f in original])):
        lag = evaluate_temporal(original, corrected, backend, lags=(1,),
                                n_anchors=1, eval_long_side=None).lag(1)
        fits.append((lag.illumination.gain, lag.illumination.bias))
    assert len(set(fits)) == 1, f"illumination fit moved with the corrected input: {fits}"


def test_apply_illumination_is_chroma_preserving_by_construction():
    """A scalar gain+bias cannot recolour anything — the property that makes
    corrected-only chroma flicker unfittable rather than merely unfitted."""
    fit = IlluminationFit(gain=1.4, bias=0.05)
    img = texture(seed=7)
    out = apply_illumination(img, fit)
    assert np.allclose(out, img * 1.4 + 0.05)
    # equal treatment of channels: differences scale by the gain alone
    assert np.allclose(out[..., 0] - out[..., 1], (img[..., 0] - img[..., 1]) * 1.4)


# ===========================================================================
# Case F — one-frame appearance/colour spike
# ===========================================================================


def test_case_f_single_frame_spike_shows_up_as_a_per_pair_spike():
    frames = [texture(seed=9) for _ in range(6)]
    frames[3] = np.clip(frames[3] * 1.0 + np.array([0.2, -0.05, -0.05], np.float32), 0, 1.2)
    seq = frames_of(frames)
    backend = ConstantFlowBackend(0.0, 0.0)
    lag = evaluate_temporal(seq, seq, backend, lags=(1,),
                            anchors=(0, 1, 2, 3, 4), eval_long_side=None).lag(1)

    by_anchor = {p["index_t"]: p["raw_warp"] for p in lag.pairs}
    spiking = [by_anchor[2], by_anchor[3]]     # (2->3) and (3->4)
    quiet = [by_anchor[0], by_anchor[1]]
    assert min(spiking) > 100 * max(max(quiet), 1e-9)
    de = {p["index_t"]: p["temporal_delta_e"] for p in lag.pairs}
    assert min(de[2], de[3]) > 5 * max(de[0], de[1], 1e-9)


# ===========================================================================
# Case G — blur lowers a temporal score, which is not superiority
# ===========================================================================


def test_case_g_blur_lowers_the_temporal_score_and_that_is_not_a_win():
    """Documented, tested, and deliberately NOT compensated for.

    A blurred output has less high-frequency content to misalign, so it wins
    on every photometric temporal residual. That is precisely why spatial
    fidelity stays a separate evaluation axis and why no helper in this
    module ranks two results.
    """
    original = translating_sequence(4, 0.5, 0.25, seed=11)
    blurred = frames_of([cv2.GaussianBlur(f.image, (0, 0), 2.0) for f in original])
    backend = ConstantFlowBackend(0.5, 0.25)

    base = evaluate_temporal(original, original, backend, lags=(1,), n_anchors=1,
                             eval_long_side=None).lag(1)
    blur = evaluate_temporal(original, blurred, backend, lags=(1,), n_anchors=1,
                             eval_long_side=None).lag(1)

    assert blur.raw_warp < base.raw_warp
    assert blur.illumination_aware_warp < base.illumination_aware_warp
    # ...and nothing in the module would call that an improvement. The only
    # comparison helper that exists compares BACKENDS on a common mask, never
    # two pipeline results, and it takes no corrected sequence at all.
    comparers = [n for n in dir(M)
                 if any(k in n for k in ("better", "rank", "compare", "score"))
                 and not n.startswith("_")]
    assert comparers == ["compare_backends_common_mask"], comparers
    import inspect
    params = inspect.signature(M.compare_backends_common_mask).parameters
    assert "corrected" not in params
    assert list(params)[:3] == ["original", "backend_a", "backend_b"]


# ===========================================================================
# Case H — occlusion / disocclusion
# ===========================================================================


def test_case_h_disocclusion_is_excluded_and_the_denominator_is_correct():
    """A band whose forward/backward round trip disagrees must be dropped from
    both the numerator and the denominator, and must show up in coverage."""
    seq = translating_sequence(3, 0, 0, seed=13)
    corrupted = [f.image.copy() for f in seq]
    corrupted[1][:, :80] += 0.4                  # a big change in a band
    corrupted = frames_of(corrupted)

    zero = np.zeros((H, W, 2), np.float32)
    inconsistent = zero.copy()
    inconsistent[:, :80, 0] = 5.0                # forward says +5, backward 0
    backend = FieldBackend(forward=inconsistent, backward=zero)

    lag = evaluate_temporal(seq, corrupted, backend, lags=(1,), n_anchors=1,
                            eval_long_side=None).lag(1)
    # the 80-px band (25 % of the width) is gone from the measurement
    assert lag.valid_fraction == pytest.approx(0.75, abs=0.02)
    # and what remains is unaffected by the change inside the excluded band
    assert lag.raw_warp < 1e-6

    everything = FieldBackend(forward=zero, backward=zero)
    full = evaluate_temporal(seq, corrupted, everything, lags=(1,), n_anchors=1,
                             eval_long_side=None).lag(1)
    assert full.valid_fraction > 0.99
    assert full.raw_warp > 0.09      # 0.4 over 25 % of the frame, /3 channels


def test_empty_mask_returns_none_not_zero():
    """No valid pixels is a different result from a poorly-supported one:
    the value is None (undefined), and coverage is 0."""
    seq = translating_sequence(3, 0, 0, seed=15)
    far = np.zeros((H, W, 2), np.float32)
    far[..., 0] = 10_000.0
    backend = FieldBackend(forward=far, backward=far)
    lag = evaluate_temporal(seq, seq, backend, lags=(1,), n_anchors=1,
                            eval_long_side=None).lag(1)
    assert lag.valid_fraction == 0.0
    assert lag.raw_warp is None
    assert lag.uncompensated is None
    assert lag.motion_reduction_ratio is None
    assert "low-coverage" in lag.status


# ===========================================================================
# Case I — localised illumination
# ===========================================================================


def _local_light(image, cx, cy, radius, amplitude):
    ys, xs = np.mgrid[0:image.shape[0], 0:image.shape[1]].astype(np.float32)
    bump = amplitude * np.exp(-(((xs - cx) ** 2 + (ys - cy) ** 2) / (2 * radius ** 2)))
    return np.clip(image + bump[..., None], 0.0, 1.5).astype(np.float32)


def test_case_i_global_model_only_partly_explains_a_local_light():
    """A camera-mounted-light analogue: a bright patch that moves with the
    camera. A global gain/bias must NOT be able to make this go away, and the
    limitation has to be visible rather than absorbed."""
    base = texture(seed=17)
    seq = frames_of([
        base,
        _local_light(base, cx=90, cy=60, radius=25, amplitude=0.45),
        _local_light(base, cx=110, cy=70, radius=25, amplitude=0.45),
    ])
    backend = ConstantFlowBackend(0.0, 0.0)
    lag = evaluate_temporal(seq, seq, backend, lags=(1,), n_anchors=1,
                            eval_long_side=None).lag(1)

    assert lag.raw_warp > 0.005
    # the global model helps a little (the patch does raise the mean) but
    # nowhere near enough — most of the local change survives
    assert lag.illumination_aware_warp > 0.5 * lag.raw_warp
    assert lag.illumination_explained_fraction < 0.5


def test_case_i_local_light_does_not_mask_corrected_only_flicker_elsewhere():
    """The two failure modes must remain separable: legitimate local light in
    the input, restoration flicker somewhere else in the output."""
    base = texture(seed=19)
    original = frames_of([base, _local_light(base, 60, 50, 22, 0.4)])
    corrected = []
    for i, f in enumerate(original):
        img = f.image.copy()
        if i == 1:
            img[120:, 200:, 0] *= 1.5     # corrected-only red flicker, elsewhere
        corrected.append(img)
    corrected = frames_of(corrected)

    backend = ConstantFlowBackend(0.0, 0.0)
    lag = evaluate_temporal(original, corrected, backend, lags=(1,), n_anchors=1,
                            eval_long_side=None).lag(1)
    assert lag.raw_warp > lag.input_raw_warp
    assert lag.temporal_delta_e > lag.input_temporal_delta_e


# ===========================================================================
# Case J — coverage gaming
# ===========================================================================


def test_case_j_a_lower_score_from_masking_comes_with_lower_coverage():
    """Two evaluations of the same footage differing only in what they exclude.

    Excluding the hard region really does lower the residual. The reporting
    has to make that purchase visible — a lower number arriving with a much
    lower coverage — and nothing in the module is allowed to call it better.
    """
    seq = translating_sequence(3, 0, 0, seed=21)
    corrupted = [f.image.copy() for f in seq]
    corrupted[1][:, :180] += 0.5           # the hard region: 56 % of the width
    corrupted = frames_of(corrupted)

    zero = np.zeros((H, W, 2), np.float32)
    generous = FieldBackend(forward=zero, backward=zero)
    masking = FieldBackend(forward=zero.copy(), backward=zero.copy())
    masking.forward[:, :180, 0] = 5.0      # FB-inconsistent -> excluded

    wide = evaluate_temporal(seq, corrupted, generous, lags=(1,), n_anchors=1,
                             eval_long_side=None).lag(1)
    narrow = evaluate_temporal(seq, corrupted, masking, lags=(1,), n_anchors=1,
                               eval_long_side=None).lag(1)

    assert narrow.raw_warp < wide.raw_warp           # "better" score...
    assert narrow.valid_fraction < 0.5               # ...bought with coverage
    assert wide.valid_fraction > 0.99
    assert "low-coverage" in narrow.status
    assert "low-coverage" not in wide.status
    # the score itself is preserved, not deleted, so a reader can judge
    assert narrow.raw_warp is not None


# ===========================================================================
# Reporting invariants
# ===========================================================================


def test_no_weighted_overall_temporal_score_exists():
    lag_fields = {f.name for f in dataclasses.fields(TemporalLagMetrics)}
    top_fields = {f.name for f in dataclasses.fields(TemporalMetrics)}
    for name in lag_fields | top_fields:
        assert "overall" not in name and "combined" not in name and name != "score"
    # the five quantities stay separate
    assert {"raw_warp", "illumination_aware_warp", "uncompensated",
            "motion_reduction_ratio", "valid_fraction"} <= lag_fields


def test_every_lag_reports_coverage_and_all_five_quantities():
    seq = translating_sequence(12, 2, 1, seed=23)
    result = evaluate_temporal(seq, seq, ConstantFlowBackend(2.0, 1.0),
                               lags=(1, 4, 8), n_anchors=2, eval_long_side=None)
    assert [l.lag for l in result.lags] == [1, 4, 8]
    for lag in result.lags:
        assert 0.0 <= lag.valid_fraction <= 1.0
        assert lag.raw_warp is not None
        assert lag.illumination_aware_warp is not None
        assert lag.uncompensated is not None
        assert lag.status
        assert lag.input_raw_warp is not None
        assert lag.input_uncompensated is not None


def test_lags_use_direct_flow_and_never_chain_adjacent_pairs():
    seq = translating_sequence(12, 2, 1, seed=25)
    backend = ConstantFlowBackend(2.0, 1.0)
    evaluate_temporal(seq, seq, backend, lags=(1, 4, 8), anchors=(0,),
                      eval_long_side=None)
    assert backend.calls == [(0, 1), (1, 0), (0, 4), (4, 0), (0, 8), (8, 0)]
    for a, b in backend.calls:
        assert abs(b - a) in (1, 4, 8), "a lag was served by composing shorter hops"


def test_inference_is_reused_exactly_twice_per_pair():
    """One forward and one backward pass serve the FB mask, both warps, both
    residual families, the illumination fit, temporal ΔE and the ratios."""
    seq = translating_sequence(12, 2, 1, seed=27)
    backend = ConstantFlowBackend(2.0, 1.0)
    evaluate_temporal(seq, seq, backend, lags=(1, 4), anchors=(0, 2),
                      alignment_robust=True, eval_long_side=None)
    assert len(backend.calls) == 2 * 2 * 2   # lags x anchors x directions


def test_result_retains_no_image_or_flow_arrays():
    """Bounded memory: what leaves an evaluation is scalars, not fields."""
    seq = translating_sequence(12, 2, 1, seed=29)
    result = evaluate_temporal(seq, seq, ConstantFlowBackend(2.0, 1.0),
                               lags=(1, 4), n_anchors=2, eval_long_side=None)

    def walk(obj, path="result"):
        assert not isinstance(obj, np.ndarray), f"ndarray retained at {path}"
        if dataclasses.is_dataclass(obj):
            for f in dataclasses.fields(obj):
                walk(getattr(obj, f.name), f"{path}.{f.name}")
        elif isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, f"{path}[{k!r}]")
        elif isinstance(obj, (list, tuple)):
            for i, v in enumerate(obj):
                walk(v, f"{path}[{i}]")

    walk(result)


def test_on_arrays_callback_sees_the_pair_and_the_result_still_holds_nothing():
    seq = translating_sequence(4, 1, 0, seed=31)
    seen = []
    evaluate_temporal(seq, seq, ConstantFlowBackend(1.0, 0.0), lags=(1,),
                      anchors=(0,), eval_long_side=None,
                      on_arrays=lambda payload: seen.append(set(payload)))
    assert len(seen) == 1
    assert {"flow_forward", "flow_backward", "mask", "warped_corrected",
            "illum_warped_corrected", "illumination"} <= seen[0]


# ===========================================================================
# Illumination-model guards
# ===========================================================================


def test_fit_declines_when_luminance_has_no_spread():
    """Gain and bias are not separable from a constant image; the model must
    say so and fall back to identity rather than invent a number."""
    flat = np.full((H, W, 3), 0.3, np.float32)
    mask = np.ones((H, W), bool)
    fit = fit_illumination(flat, flat * 1.2, mask)
    assert fit.is_identity
    assert "luminance-spread-too-small" in fit.status
    assert (fit.gain, fit.bias) == (1.0, 0.0)


def test_fit_declines_on_a_domain_that_is_too_small():
    img = texture()
    mask = np.zeros((H, W), bool)
    mask[:10, :10] = True
    fit = fit_illumination(img, img, mask)
    assert fit.is_identity
    assert "fit-domain-too-small" in fit.status


def test_fit_excludes_highlights_and_near_black():
    """Clipped and near-black pixels carry no usable illumination information
    at 8-bit sRGB, so they must not enter the fit domain."""
    img = np.full((H, W, 3), 0.4, np.float32)
    img[:60] = 0.999          # highlights
    img[60:120] = 0.0005      # near black
    rng = np.random.default_rng(2)
    img[120:] = rng.random((H - 120, W, 3)).astype(np.float32) * 0.6 + 0.1
    fit = fit_illumination(img, img.copy(), np.ones((H, W), bool))
    usable = (H - 120) * W
    assert fit.fit_pixels <= usable
    assert fit.fit_pixels > 0.9 * usable


def _contaminate(image, fraction, value=0.9, seed=35):
    """Replace a fraction of pixels with a constant bright value.

    The hard case on purpose: such a pixel is an outlier in the warped frame
    AND unrelated to the reference, i.e. HIGH LEVERAGE — which is what a
    bubble, a lit particle or a specular glint actually is. An M-estimator
    that only bounds the influence of large residuals does not resist those.
    """
    rng = np.random.default_rng(seed)
    out = image.copy()
    out[rng.random(image.shape[:2]) < fraction] = value
    return out


@pytest.mark.parametrize("fraction", [0.0, 0.05, 0.15])
def test_fit_is_robust_to_high_leverage_contamination(fraction):
    """Bubbles and marine snow must not drag the fit within its breakdown."""
    base = texture(seed=33)
    target = ((base - 0.02) / 1.25).astype(np.float32)   # true gain 1.25, bias 0.02
    fit = fit_illumination(base, _contaminate(target, fraction),
                           np.ones((H, W), bool))
    assert fit.status == "fitted"
    assert fit.gain == pytest.approx(1.25, rel=0.02)
    assert fit.bias == pytest.approx(0.02, abs=0.005)


def test_fit_breaks_down_past_its_stated_limit_and_says_so():
    """Documents the limit rather than pretending there isn't one.

    The estimator keeps the best-fitting 70 % of the fit domain, so its
    breakdown point is 30 %. Past that the fit is wrong, and a guard has to
    catch it: either the gain leaves its sanity range, or the transform fails
    to reduce the input residual it was fitted to explain and is rejected.
    Either way the result is the identity transform, which makes the
    canonical metric equal the raw one — never a confident wrong number.
    """
    base = texture(seed=33)
    target = ((base - 0.02) / 1.25).astype(np.float32)
    fit = fit_illumination(base, _contaminate(target, 0.40), np.ones((H, W), bool))
    assert fit.is_identity
    assert "gain-out-of-range" in fit.status


def test_a_fit_that_does_not_reduce_the_input_residual_is_rejected():
    """The model's acceptance test is measured on the input, never the output.

    A transform can be perfectly good on its fit domain and bad on the frame:
    here the top third is clipped highlight, excluded from the fit (nothing
    to learn from a clipped pixel) but still measured, and it does not share
    the midtones' 2x brightening. Applying the midtone gain to it makes the
    frame-wide residual worse, so the transform is rejected and the canonical
    metric falls back to the raw one.
    """
    rng = np.random.default_rng(51)
    mid = (rng.random((H - 60, W, 3)).astype(np.float32) * 0.3 + 0.15)
    reference = np.empty((H, W, 3), np.float32)
    target = np.empty((H, W, 3), np.float32)
    reference[:60] = 0.98          # clipped highlight: above ILLUM_HIGHLIGHT_LINEAR
    target[:60] = 0.98             # ...and unchanged between the frames
    reference[60:] = mid
    target[60:] = mid / 2.0        # midtones: a clean, fittable 2x

    on_midtones = fit_illumination(reference[60:], target[60:],
                                   np.ones((H - 60, W), bool))
    assert on_midtones.status == "fitted"
    assert on_midtones.gain == pytest.approx(2.0, rel=0.02)

    seq = frames_of([reference, target])
    lag = evaluate_temporal(seq, seq, ConstantFlowBackend(0.0, 0.0), lags=(1,),
                            n_anchors=1, eval_long_side=None).lag(1)
    assert lag.illumination.is_identity
    assert "no-input-residual-reduction" in lag.illumination.status
    assert lag.illumination_aware_warp == pytest.approx(lag.raw_warp)


def test_fit_declines_an_absurd_gain():
    base = texture(seed=37)
    fit = fit_illumination(base, (base * 0.2).astype(np.float32),
                           np.ones((H, W), bool))
    assert fit.is_identity
    assert "gain-out-of-range" in fit.status


def test_identity_fit_makes_the_canonical_metric_equal_the_raw_one():
    seq = translating_sequence(3, 1, 0, seed=39)
    flat = frames_of([np.full((H, W, 3), 0.3, np.float32),
                      np.full((H, W, 3), 0.36, np.float32),
                      np.full((H, W, 3), 0.3, np.float32)])
    lag = evaluate_temporal(flat, flat, ConstantFlowBackend(0.0, 0.0), lags=(1,),
                            n_anchors=1, eval_long_side=None).lag(1)
    assert lag.illumination.is_identity
    assert lag.illumination_aware_warp == pytest.approx(lag.raw_warp)
    assert "illumination-identity" in lag.status


# ===========================================================================
# Temporal ΔE
# ===========================================================================


def test_temporal_delta_e_is_zero_for_identical_content_and_positive_for_a_tint():
    img = texture(seed=41)
    mask = np.ones((H, W), bool)
    same, cov = temporal_delta_e(img, img, mask)
    assert same == pytest.approx(0.0, abs=1e-9)
    assert cov > 0.95
    tinted = img.copy()
    tinted[..., 0] *= 1.3
    shifted, _ = temporal_delta_e(img, tinted, mask)
    assert shifted > 1.0


def test_temporal_delta_e_excludes_near_black_and_reports_the_coverage():
    img = texture(seed=43)
    img[:90] = 0.0001                  # below the 8/255 floor
    value, cov = temporal_delta_e(img, img.copy(), np.ones((H, W), bool))
    assert value == pytest.approx(0.0, abs=1e-9)
    assert cov == pytest.approx(0.5, abs=0.02)


def test_temporal_delta_e_uses_the_project_ciede2000_path():
    """No second ΔE implementation: the same function `delta_e` uses."""
    from uw.colorspace import linear_rgb_to_lab
    a = np.full((8, 8, 3), 0.2, np.float64)
    b = np.full((8, 8, 3), 0.2, np.float64)
    b[..., 0] = 0.35
    value, _ = temporal_delta_e(a, b, np.ones((8, 8), bool))
    expected = M.ciede2000(linear_rgb_to_lab(a[0, 0]), linear_rgb_to_lab(b[0, 0]))
    assert value == pytest.approx(expected, rel=1e-9)


# ===========================================================================
# Grid / resolution discipline
# ===========================================================================


def test_metric_eval_size_matches_phase_2a_grid_and_never_upscales():
    assert metric_eval_size(1080, 1920) == (540, 960)
    assert metric_eval_size(1920, 1080) == (960, 540)     # portrait decode
    assert metric_eval_size(2160, 3840) == (540, 960)     # 4K
    assert metric_eval_size(180, 320) == (180, 320)       # already small


def test_evaluation_records_source_flow_and_metric_resolutions():
    seq = frames_of([texture(540, 960, seed=45) for _ in range(3)])
    result = evaluate_temporal(seq, seq, ConstantFlowBackend(1.0, 0.0), lags=(1,),
                               n_anchors=1)
    assert result.source_size_hw == (540, 960)
    assert result.metric_size_hw == (540, 960)
    assert result.flow_inference_size_hw == (540, 960)
    assert result.backend == "analytic_constant"


def test_input_and_corrected_are_resized_identically():
    """A pipeline comparison must never become a resampling comparison."""
    big = [texture(360, 640, seed=47) for _ in range(2)]
    original = frames_of(big)
    corrected = frames_of([im * 1.1 for im in big])
    result = evaluate_temporal(original, corrected, ConstantFlowBackend(0.0, 0.0),
                               lags=(1,), n_anchors=1, eval_long_side=320)
    assert result.metric_size_hw == (180, 320)
    lag = result.lag(1)
    # identical resampling on both sides => an exact 1.1x relationship survives
    assert lag.raw_warp == pytest.approx(1.1 * lag.input_raw_warp, rel=1e-6)


# ===========================================================================
# The deprecated Week 1 placeholder
# ===========================================================================


def test_week1_placeholder_is_still_reproducible_but_marked_deprecated():
    seq = frames_of([np.full((4, 4, 3), 0.2, np.float32),
                     np.full((4, 4, 3), 0.4, np.float32)])
    assert M.temporal_stability(seq) == pytest.approx(0.01)
    assert "DEPRECATED" in M.temporal_stability.__doc__


# ===========================================================================
# Temporal aliasing: what a lag set can and cannot see
# ===========================================================================


def test_a_period_2_flicker_is_invisible_at_even_lags():
    """MC-Warp@k cannot see an oscillation whose period divides k.

    Found on real footage: a synthetic period-2 red flicker injected into the
    `lights` clip raised MC-Warp@1 but LOWERED MC-Warp@8, because frames t
    and t+8 sit on the same phase of the oscillation and carry the identical
    red gain. This is a property of any lag-k comparison, not a bug, and it
    is the concrete reason the metric reports three lags instead of one — but
    it also means the @1/@4/@8 set is blind to a period-4 oscillation at both
    of its longer lags.
    """
    original = translating_sequence(12, 0, 0, seed=53)
    corrected = _red_flicker(original, 0.2)
    backend = ConstantFlowBackend(0.0, 0.0)
    result = evaluate_temporal(original, corrected, backend, lags=(1, 2, 4),
                               anchors=(0, 2), eval_long_side=None)
    assert result.lag(1).raw_warp > 0.01              # in phase opposition
    assert result.lag(2).raw_warp < 1e-6              # same phase: invisible
    assert result.lag(4).raw_warp < 1e-6
    # temporal ΔE aliases identically — it shares the correspondence, not the
    # sampling, so it cannot rescue a frequency the lag set does not sample.
    assert result.lag(1).temporal_delta_e > 1.0
    assert result.lag(2).temporal_delta_e < 1e-6


# ===========================================================================
# Linear light, and no silent clipping
# ===========================================================================


def test_residuals_scale_linearly_with_the_data():
    """The residual lives in the data's own linear units.

    Scaling both sequences by a constant scales every photometric residual by
    exactly that constant. A metric that encoded to sRGB (or clipped, or
    applied any other non-linearity) before differencing could not do this,
    so this pins "linear-light RGB, nothing encoded on the way in".
    """
    seq = translating_sequence(4, 0.5, 0.25, seed=55)
    scaled = frames_of([f.image * 0.4 for f in seq])
    backend = ConstantFlowBackend(0.5, 0.25)
    a = evaluate_temporal(seq, seq, backend, lags=(1,), n_anchors=1,
                          eval_long_side=None).lag(1)
    b = evaluate_temporal(scaled, scaled, backend, lags=(1,), n_anchors=1,
                          eval_long_side=None).lag(1)
    assert b.raw_warp == pytest.approx(0.4 * a.raw_warp, rel=1e-6)
    assert b.uncompensated == pytest.approx(0.4 * a.uncompensated, rel=1e-6)
    assert b.motion_reduction_ratio == pytest.approx(a.motion_reduction_ratio, rel=1e-6)


def test_out_of_range_values_are_measured_not_clipped():
    """gray_world deliberately produces values above 1.0 in linear light, and
    a metric that clipped them would under-report exactly the instability a
    large corrective gain creates."""
    base = texture(seed=57)
    hot = np.stack([base[..., 0] * 6.0, base[..., 1], base[..., 2]], axis=-1)
    seq = frames_of([hot, hot * 1.0])
    seq[1].image[..., 0] *= 1.5          # a big excursion, well above 1.0
    assert seq[1].image.max() > 1.0
    lag = evaluate_temporal(seq, seq, ConstantFlowBackend(0.0, 0.0), lags=(1,),
                            n_anchors=1, eval_long_side=None).lag(1)
    expected = float(np.abs(seq[1].image - seq[0].image).mean())
    assert lag.raw_warp == pytest.approx(expected, rel=1e-4)


# ===========================================================================
# The single-pair entry point, and the project's one definition of luminance
# ===========================================================================


def test_evaluate_temporal_pair_returns_scalars_and_reports_provenance():
    """The per-pair API is what visualisation and per-frame inspection use."""
    seq = translating_sequence(6, 2, 1, seed=59)
    backend = ConstantFlowBackend(2.0, 1.0)
    pair = evaluate_temporal_pair(seq, seq, backend, index_t=1, lag=4)

    assert (pair["index_t"], pair["index_t1"], pair["lag"]) == (1, 5, 4)
    assert backend.calls == [(1, 5), (5, 1)]        # direct, both directions
    assert pair["flow_inference_size_hw"] == (H, W)
    for key in ("raw_warp", "illumination_aware_warp", "uncompensated",
                "input_raw_warp", "temporal_delta_e", "valid_fraction"):
        assert isinstance(pair[key], float)
    assert pair["illumination"]["model"] == "global_gain_bias_luminance"

    with pytest.raises(IndexError):
        evaluate_temporal_pair(seq, seq, backend, index_t=4, lag=4)
    with pytest.raises(ValueError, match="lag must be positive"):
        evaluate_temporal_pair(seq, seq, backend, index_t=0, lag=0)


def test_linear_luminance_is_the_projects_own_xyz_y_row():
    """One definition of luminance in the codebase, not two."""
    from uw.colorspace import LINEAR_SRGB_TO_XYZ_D65, linear_rgb_to_xyz

    img = texture(seed=61)
    assert np.allclose(linear_luminance(img), linear_rgb_to_xyz(img)[..., 1])
    assert np.allclose(linear_luminance(np.ones((2, 2, 3))),
                       LINEAR_SRGB_TO_XYZ_D65[1].sum())
    # not clipped: out-of-range linear values are reported as they are
    assert linear_luminance(np.full((1, 1, 3), 3.0))[0, 0] == pytest.approx(
        3.0 * LINEAR_SRGB_TO_XYZ_D65[1].sum())


# ===========================================================================
# Cross-backend comparison — the masking-policy trap
# ===========================================================================


class NamedFieldBackend(FieldBackend):
    """A FieldBackend with a distinguishable name, so two can be compared."""

    def __init__(self, name, forward, backward):
        super().__init__(forward, backward)
        self.name = name

    def describe(self):
        return {"backend": self.name}


def test_masking_advantage_vanishes_on_the_common_mask():
    """The whole reason cross-backend numbers must not use each backend's own
    mask, made concrete.

    Both backends return the SAME flow, so their correspondence quality is
    identical by construction. One of them additionally throws away the
    difficult half of the frame. On its own mask that would look like a large
    win; on the intersection the two are indistinguishable, and the coverage
    difference is reported instead of being laundered into the score.
    """
    seq = translating_sequence(3, 0, 0, seed=63)
    hard = [f.image.copy() for f in seq]
    hard[1][:, :180] += 0.5
    seq = frames_of([seq[0].image, hard[1], hard[1]])

    zero = np.zeros((H, W, 2), np.float32)
    generous = NamedFieldBackend("generous", zero.copy(), zero.copy())
    fussy = NamedFieldBackend("fussy", zero.copy(), zero.copy())
    fussy.forward[:, :180, 0] = 5.0      # FB-inconsistent there -> excluded

    result = compare_backends_common_mask(
        seq, generous, fussy, lags=(1,), anchors=(0,), eval_long_side=None)
    cell = result.cells[0]

    assert cell.own_fraction["generous"] > 0.99
    assert cell.own_fraction["fussy"] < 0.5          # it measures far less...
    assert cell.common_fraction < 0.5                # ...so the common set is small
    # ...and on that common set the two are identical, because they are.
    assert cell.raw_warp["generous"] == pytest.approx(cell.raw_warp["fussy"])
    assert cell.verdict == "tie"
    assert result.tally == {"generous": 0, "fussy": 0, "tie": 1}


def test_a_real_correspondence_difference_survives_the_common_mask():
    """The converse: a backend whose flow is actually wrong loses, on the same
    pixels, and the disputed-band EPE is reported."""
    # A fractional true motion, so the correct flow leaves the ordinary
    # sub-pixel resampling residual rather than an exact zero — which is what
    # real footage always looks like, and keeps the ratio defined.
    seq = translating_sequence(3, 4.5, 0, seed=65)
    good_flow = np.zeros((H, W, 2), np.float32)
    good_flow[..., 0] = 4.5
    bad_flow = good_flow.copy()
    bad_flow[..., 0] = 2.0                     # well short of the true motion

    good = NamedFieldBackend("good", good_flow, -good_flow)
    bad = NamedFieldBackend("bad", bad_flow, -bad_flow)

    cell = compare_backends_common_mask(
        seq, good, bad, lags=(1,), anchors=(0,), eval_long_side=None).cells[0]

    assert cell.raw_warp["good"] < cell.raw_warp["bad"]
    assert cell.motion_reduction_ratio["good"] > cell.motion_reduction_ratio["bad"]
    assert cell.verdict == "good"
    assert cell.flow_epe_px["median_overall"] == pytest.approx(2.5, abs=0.01)


def test_comparison_reports_a_cell_tally_and_no_aggregate_score():
    seq = translating_sequence(12, 2, 0, seed=67)
    flow = np.zeros((H, W, 2), np.float32)
    flow[..., 0] = 2.0
    a = NamedFieldBackend("a", flow, -flow)
    b = NamedFieldBackend("b", flow.copy(), -flow)

    result = compare_backends_common_mask(seq, a, b, lags=(1,), anchors=(0, 2),
                                          eval_long_side=None)
    assert sum(result.tally.values()) == len(result.cells)
    fields = {f.name for f in dataclasses.fields(BackendComparison)}
    fields |= {f.name for f in dataclasses.fields(BackendComparisonCell)}
    for name in fields:
        assert "overall" not in name and "combined" not in name
    assert "score" not in fields
    # identical backends must be a tie, not noise-ranked
    assert result.cells[0].verdict == "tie"


def test_comparison_refuses_two_backends_with_the_same_name():
    seq = translating_sequence(3, 0, 0, seed=69)
    zero = np.zeros((H, W, 2), np.float32)
    with pytest.raises(ValueError, match="distinguishable"):
        compare_backends_common_mask(
            seq, FieldBackend(zero, zero), FieldBackend(zero, zero),
            lags=(1,), anchors=(0,), eval_long_side=None)


def test_comparison_costs_four_inferences_per_anchor_and_lag():
    seq = translating_sequence(12, 2, 0, seed=71)
    zero = np.zeros((H, W, 2), np.float32)
    a = NamedFieldBackend("a", zero.copy(), zero.copy())
    b = NamedFieldBackend("b", zero.copy(), zero.copy())
    compare_backends_common_mask(seq, a, b, lags=(1, 4), anchors=(0, 2),
                                 eval_long_side=None)
    assert len(a.calls) == 2 * 2 * 2 and len(b.calls) == 2 * 2 * 2
    for calls in (a.calls, b.calls):
        assert {abs(j - i) for i, j in calls} == {1, 4}   # direct, never chained


# ---------------------------------------------------------------------------
# Review findings AR-01 / AR-03 — evaluation-domain independence and reuse
# ---------------------------------------------------------------------------


def test_corrected_output_cannot_shrink_the_evaluation_domain():
    """AR-01 REGRESSION. The mask used to include `ok_corr` and the
    corrected frame's own finiteness, and that mask was then handed to
    `fit_illumination` — so a correction emitting non-finite output
    silently excluded exactly the pixels it had damaged AND perturbed the
    supposedly original-only illumination fit. Measured before the fix:
    corrected-only NaN moved coverage 1.0000 -> 0.5333."""
    rng = np.random.default_rng(0)
    original = [Frame(image=rng.uniform(0.2, 0.6, (30, 30, 3)).astype(np.float32),
                      metadata={}) for _ in range(3)]
    backend = ConstantFlowBackend(0.0, 0.0)

    finite = [Frame(image=f.image * 0.9, metadata={}) for f in original]
    clean = evaluate_temporal_pair(original, finite, backend, 0, 1)

    damaged = []
    for f in original:
        image = (f.image * 0.9).copy()
        image[:14, :, :] = np.nan
        damaged.append(Frame(image=image, metadata={}))
    dirty = evaluate_temporal_pair(original, damaged, backend, 0, 1)

    assert dirty["valid_fraction"] == clean["valid_fraction"]
    assert dirty["illumination"]["gain"] == clean["illumination"]["gain"]
    assert dirty["illumination"]["bias"] == clean["illumination"]["bias"]
    # The damage is reported rather than masked away.
    assert clean["corrected_nonfinite_fraction"] == 0.0
    assert dirty["corrected_nonfinite_fraction"] > 0.4


def test_prepared_pair_is_reused_not_recomputed_across_configurations():
    """AR-03 REGRESSION. Reuse must cover the mask and the illumination
    transform, not only the flow: previously each configuration recomputed
    forward/backward consistency and re-fitted illumination."""
    rng = np.random.default_rng(1)
    original = [Frame(image=rng.uniform(0.2, 0.6, (30, 30, 3)).astype(np.float32),
                      metadata={}) for _ in range(3)]
    backend = ConstantFlowBackend(0.0, 0.0)

    prepared = M.prepare_temporal_pair(original, backend, 0, 1)
    calls_after_prepare = len(backend.calls)

    results = []
    for scale in (0.5, 1.0, 2.0, 4.0, 8.0, 16.0):
        corrected = [Frame(image=f.image * scale, metadata={}) for f in original]
        results.append(evaluate_temporal_pair(
            original, corrected, backend, 0, 1, prepared=prepared))

    assert len(backend.calls) == calls_after_prepare  # zero extra inference
    # Every configuration saw the identical evaluation domain and transform.
    assert len({r["valid_fraction"] for r in results}) == 1
    assert len({r["illumination"]["gain"] for r in results}) == 1


def test_prepare_temporal_pairs_is_bounded_to_anchor_times_lag():
    rng = np.random.default_rng(2)
    original = [Frame(image=rng.uniform(0.2, 0.6, (20, 20, 3)).astype(np.float32),
                      metadata={}) for _ in range(12)]
    prepared = M.prepare_temporal_pairs(
        original, ConstantFlowBackend(0.0, 0.0), lags=(1, 2, 4), anchors=(0, 2, 4))
    assert len(prepared) == 9
