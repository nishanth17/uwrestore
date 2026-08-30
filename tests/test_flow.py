"""Tests for uw/flow.py — the model-agnostic flow maths.

These deliberately test the conventions, not any model: channel order,
direction, resize rescaling, warping, and the forward/backward consistency
criterion. Everything here is analytic, so a failure means the convention
drifted, not that a network got worse.
"""

import numpy as np
import pytest

from uw.flow import (
    FB_ALPHA,
    FB_BETA,
    CachingFlowBackend,
    FlowResult,
    OpticalFlowBackend,
    flow_magnitude,
    forward_backward_consistency,
    resize_flow,
    sample_flow,
    warp_to_source,
)


def constant_flow(h, w, u, v):
    f = np.zeros((h, w, 2), np.float32)
    f[..., 0] = u
    f[..., 1] = v
    return f


# --------------------------------------------------------------------------
# FlowResult
# --------------------------------------------------------------------------


def test_flow_result_rejects_wrong_shape():
    with pytest.raises(ValueError, match=r"\(H, W, 2\)"):
        FlowResult(flow=np.zeros((4, 5, 3), np.float32), valid_mask=np.ones((4, 5), bool))


def test_flow_result_rejects_mismatched_mask():
    with pytest.raises(ValueError, match="valid_mask shape"):
        FlowResult(flow=np.zeros((4, 5, 2), np.float32), valid_mask=np.ones((3, 5), bool))


def test_backend_interface_is_abstract():
    be = OpticalFlowBackend()
    with pytest.raises(NotImplementedError):
        be.estimate([], 0, 1)
    with pytest.raises(NotImplementedError):
        be.describe()


# --------------------------------------------------------------------------
# resize_flow: the grid and the vectors must scale together
# --------------------------------------------------------------------------


def test_resize_flow_halving_halves_vectors():
    f = constant_flow(100, 200, 10.0, -4.0)
    out = resize_flow(f, 50, 100)
    assert out.shape == (50, 100, 2)
    assert np.allclose(out[..., 0], 5.0)
    assert np.allclose(out[..., 1], -2.0)


def test_resize_flow_scales_axes_independently():
    """Non-uniform resize: u follows width, v follows height, never crossed."""
    f = constant_flow(100, 200, 10.0, -4.0)
    out = resize_flow(f, 300, 100)          # height x3, width x0.5
    assert np.allclose(out[..., 0], 5.0)    # 10 * 100/200
    assert np.allclose(out[..., 1], -12.0)  # -4 * 300/100


def test_resize_flow_roundtrip_preserves_motion():
    f = constant_flow(64, 96, 7.5, 3.25)
    back = resize_flow(resize_flow(f, 32, 48), 64, 96)
    assert np.allclose(back, f, atol=1e-4)


def test_resize_flow_identity_is_a_copy():
    f = constant_flow(8, 8, 1.0, 2.0)
    out = resize_flow(f, 8, 8)
    out[0, 0, 0] = 99.0
    assert f[0, 0, 0] == 1.0


# --------------------------------------------------------------------------
# warp_to_source: direction and channel order
# --------------------------------------------------------------------------


def _ramp_image(h, w):
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    return np.stack([xs / w, ys / h, np.zeros_like(xs)], axis=-1)


def test_warp_recovers_a_known_translation():
    """target(x, y) == source(x - dx, y - dy)  =>  flow = (dx, dy)."""
    h, w, dx, dy = 40, 60, 5, -3
    src = _ramp_image(h, w)
    tgt = np.zeros_like(src)
    tgt[max(dy, 0):h + min(dy, 0), max(dx, 0):w + min(dx, 0)] = \
        src[max(-dy, 0):h + min(-dy, 0), max(-dx, 0):w + min(-dx, 0)]

    warped, inside = warp_to_source(tgt, constant_flow(h, w, dx, dy))
    interior = np.zeros((h, w), bool)
    interior[8:-8, 8:-8] = True
    assert np.allclose(warped[interior], src[interior], atol=1e-5)
    assert inside[interior].all()


def test_warp_u_channel_moves_horizontally_only():
    """A pure-u flow must not shift anything vertically (no x/y swap)."""
    h, w = 30, 40
    img = _ramp_image(h, w)
    warped, _ = warp_to_source(img, constant_flow(h, w, 4.0, 0.0))
    interior = (slice(5, -5), slice(5, -5))
    # green channel encodes y and must be untouched
    assert np.allclose(warped[interior][..., 1], img[interior][..., 1], atol=1e-5)
    # red channel encodes x and must have shifted by exactly 4/w
    assert np.allclose(warped[interior][..., 0] - img[interior][..., 0], 4.0 / w, atol=1e-5)


def test_warp_marks_out_of_frame_samples_invalid():
    h, w = 20, 20
    img = np.ones((h, w, 3), np.float32)
    warped, inside = warp_to_source(img, constant_flow(h, w, 15.0, 0.0))
    assert not inside[:, -5:].any()      # pushed off the right edge
    assert (warped[:, -5:] == 0).all()
    assert inside[:, :4].all()


def test_warp_rejects_grid_mismatch():
    with pytest.raises(ValueError, match="same grid"):
        warp_to_source(np.zeros((10, 10, 3), np.float32), constant_flow(20, 20, 0, 0))


def test_warp_handles_nonfinite_flow():
    h, w = 16, 16
    img = np.ones((h, w, 3), np.float32)
    f = constant_flow(h, w, 1.0, 1.0)
    f[5, 5, 0] = np.nan
    f[6, 6, 1] = np.inf
    warped, inside = warp_to_source(img, f)
    assert not inside[5, 5] and not inside[6, 6]
    assert np.isfinite(warped).all()


# --------------------------------------------------------------------------
# forward/backward consistency
# --------------------------------------------------------------------------


def test_fb_consistency_accepts_an_exactly_invertible_pair():
    h, w = 50, 60
    valid, err = forward_backward_consistency(
        constant_flow(h, w, 4.0, -2.0), constant_flow(h, w, -4.0, 2.0)
    )
    interior = np.zeros((h, w), bool)
    interior[6:-6, 6:-6] = True
    assert valid[interior].all()
    assert np.allclose(err[interior], 0.0, atol=1e-4)


def test_fb_consistency_rejects_a_broken_round_trip():
    h, w = 50, 60
    # backward flow points the same way as forward: round-trip error 8 px
    valid, err = forward_backward_consistency(
        constant_flow(h, w, 4.0, 0.0), constant_flow(h, w, 4.0, 0.0)
    )
    interior = (slice(6, -6), slice(6, -6))
    assert not valid[interior].any()
    assert np.allclose(err[interior], 8.0, atol=1e-4)


def test_fb_threshold_matches_the_published_formula():
    """A round-trip error sitting either side of the criterion flips it."""
    h, w = 40, 40
    fwd = constant_flow(h, w, 3.0, 0.0)
    # |w|^2 = 9. Pick e so that e^2 is just under / just over the bound.
    # bound = alpha*(9 + |w'|^2) + beta, and |w'| = |e - 3|.
    for e, expected in ((0.6, True), (1.2, False)):
        bwd = constant_flow(h, w, -3.0 + e, 0.0)
        valid, err = forward_backward_consistency(fwd, bwd, FB_ALPHA, FB_BETA)
        interior = (slice(6, -6), slice(6, -6))
        bound = FB_ALPHA * (9.0 + (3.0 - e) ** 2) + FB_BETA
        assert (e ** 2 <= bound) is expected, "test constants drifted"
        assert valid[interior].all() == expected


def test_fb_consistency_marks_out_of_frame_unevaluable():
    h, w = 20, 20
    valid, err = forward_backward_consistency(
        constant_flow(h, w, 15.0, 0.0), constant_flow(h, w, -15.0, 0.0)
    )
    assert not valid[:, -4:].any()
    assert np.isnan(err[:, -4:]).all()


def test_fb_consistency_propagates_nonfinite_flow():
    h, w = 20, 20
    fwd = constant_flow(h, w, 1.0, 0.0)
    bwd = constant_flow(h, w, -1.0, 0.0)
    fwd[5, 5, 0] = np.nan
    bwd[9, 9, 1] = np.nan
    valid, err = forward_backward_consistency(fwd, bwd)
    assert not valid[5, 5]
    assert np.isnan(err[5, 5])
    # forward pixel (row 9, col 8) steps to (9, 9) and reads the poisoned
    # backward pixel; so do its neighbours, via the bilinear support.
    assert not valid[9, 8]
    assert np.isnan(err[9, 8])
    assert not valid[9, 7]
    assert valid[9, 4]           # far enough away to be unaffected


def test_fb_consistency_rejects_grid_mismatch():
    with pytest.raises(ValueError, match="same grid"):
        forward_backward_consistency(constant_flow(4, 4, 0, 0), constant_flow(5, 5, 0, 0))


# --------------------------------------------------------------------------
# misc
# --------------------------------------------------------------------------


def test_sample_flow_is_bilinear():
    f = np.zeros((4, 4, 2), np.float32)
    f[..., 0] = np.arange(4, dtype=np.float32)[None, :]   # u = x
    mx = np.array([[1.5]], np.float32)
    my = np.array([[2.0]], np.float32)
    out = sample_flow(f, mx, my)
    assert out.shape == (1, 1, 2)
    assert np.isclose(out[0, 0, 0], 1.5)


def test_flow_magnitude():
    f = constant_flow(3, 3, 3.0, 4.0)
    assert np.allclose(flow_magnitude(f), 5.0)


# --------------------------------------------------------------------------
# CachingFlowBackend — Week 2 Phase 2C/2D evaluation reuse
# --------------------------------------------------------------------------


class _CountingBackend(OpticalFlowBackend):
    """Records every estimate() call it actually serves."""

    name = "counting"

    def __init__(self):
        self.calls = []

    def describe(self):
        return {"backend": self.name}

    def estimate(self, frames, index_t, index_t1):
        self.calls.append((id(frames[index_t]), id(frames[index_t1]), index_t, index_t1))
        h, w = 4, 4
        return FlowResult(
            flow=np.zeros((h, w, 2), np.float32),
            valid_mask=np.ones((h, w), bool),
            metadata={"inference_size": (h, w)},
        )


def _sentinels(n):
    """n distinct, non-interned objects standing in for Frames — plain
    small strings/ints risk CPython interning/reusing the same id() for
    separately-constructed literals, which would silently defeat these
    identity tests. object() has no such risk."""
    return [object() for _ in range(n)]


def test_caching_backend_hits_on_repeat_calls_with_the_same_frame_objects():
    inner = _CountingBackend()
    cached = CachingFlowBackend(inner)
    frames = _sentinels(2)

    r1 = cached.estimate(frames, 0, 1)
    r2 = cached.estimate(frames, 0, 1)

    assert r1 is r2
    assert len(inner.calls) == 1
    assert cached.hits == 1
    assert cached.misses == 1


def test_caching_backend_survives_evaluate_temporals_list_rewrap():
    """The key reason the cache is keyed on frames[i], not on id(frames):
    uw.metrics.evaluate_temporal does `original = list(original)`
    unconditionally, so the SAME underlying Frame objects arrive wrapped in
    a DIFFERENT list on every call. A container-identity cache would miss
    every time; an element-identity cache must still hit."""
    inner = _CountingBackend()
    cached = CachingFlowBackend(inner)
    frame_a, frame_b = _sentinels(2)
    original_list = [frame_a, frame_b]

    cached.estimate(original_list, 0, 1)
    cached.estimate(list(original_list), 0, 1)  # a fresh list, same elements

    assert len(inner.calls) == 1
    assert cached.hits == 1
    assert cached.misses == 1


def test_caching_backend_misses_on_genuinely_different_frame_objects():
    inner = _CountingBackend()
    cached = CachingFlowBackend(inner)
    # Independently constructed sentinels, standing in for two SEPARATE
    # resize_sequence_linear() calls (or two different clips) — genuinely
    # different Frame objects, even if their pixels happened to match.
    clip_a, clip_b = _sentinels(2), _sentinels(2)

    cached.estimate(clip_a, 0, 1)
    cached.estimate(clip_b, 0, 1)

    assert len(inner.calls) == 2
    assert cached.hits == 0
    assert cached.misses == 2


def test_caching_backend_distinguishes_index_pairs():
    inner = _CountingBackend()
    cached = CachingFlowBackend(inner)
    frames = _sentinels(3)

    cached.estimate(frames, 0, 1)
    cached.estimate(frames, 1, 0)  # backward flow — a different pair
    cached.estimate(frames, 0, 1)  # repeat of the first — should hit

    assert len(inner.calls) == 2
    assert cached.hits == 1
    assert cached.misses == 2


def test_caching_backend_describe_reports_hit_counts_and_delegates():
    inner = _CountingBackend()
    cached = CachingFlowBackend(inner)
    frames = _sentinels(2)
    cached.estimate(frames, 0, 1)
    cached.estimate(frames, 0, 1)
    d = cached.describe()
    assert d["backend"] == "counting"
    assert d["cache_hits"] == 1
    assert d["cache_misses"] == 1


def test_caching_backend_name_defaults_to_inner_backends_name():
    cached = CachingFlowBackend(_CountingBackend())
    assert cached.name == "counting"


def test_caching_backend_retains_only_the_requested_pairs():
    """Phase 2C/2D §18: reuse must preserve bounded-memory behavior — the
    cache holds one entry per distinct (frame_t, frame_t+k) pair actually
    requested, never a whole clip. For the standard access pattern
    (3 anchors x 3 lags x 2 directions) that is exactly 18 entries."""
    cached = CachingFlowBackend(_CountingBackend())
    frames = _sentinels(41)
    for anchor in (16, 18, 20):
        for lag in (1, 4, 8):
            cached.estimate(frames, anchor, anchor + lag)
            cached.estimate(frames, anchor + lag, anchor)
    assert len(cached._cache) == 18
    assert cached.misses == 18
    assert cached.hits == 0


def test_caching_backend_is_not_a_module_level_global():
    """Two independent instances must not share state (CLAUDE.md invariant
    3: explicit state, no hidden globals)."""
    inner_a, inner_b = _CountingBackend(), _CountingBackend()
    cached_a, cached_b = CachingFlowBackend(inner_a), CachingFlowBackend(inner_b)
    frames = _sentinels(2)

    cached_a.estimate(frames, 0, 1)
    cached_b.estimate(frames, 0, 1)  # a fresh instance, so this must MISS

    assert cached_a.misses == 1
    assert cached_b.misses == 1
    assert len(inner_a.calls) == 1
    assert len(inner_b.calls) == 1


def test_caching_backend_survives_object_id_reuse():
    """AR-05 REGRESSION. The cache keyed on id() without holding the frames
    alive, so CPython could hand a collected frame's address to an
    unrelated object and turn a genuine miss into a false hit returning
    stale flow. Reproduced directly before the fix."""
    import gc

    inner = _CountingBackend()
    cached = CachingFlowBackend(inner)
    frames = _sentinels(2)
    first = cached.estimate(frames, 0, 1)
    stale_id = id(frames[0])

    del frames
    gc.collect()

    for _ in range(500):
        candidate = [object(), object()]
        if id(candidate[0]) == stale_id:
            result = cached.estimate(candidate, 0, 1)
            assert result is not first, "returned stale flow for a different frame"
            assert len(inner.calls) == 2
            return
    pytest.skip("could not provoke id reuse in this interpreter run")
