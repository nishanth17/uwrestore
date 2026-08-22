import numpy as np

from uw.colorspace import linear_to_srgb, srgb_to_linear


def test_black_maps_to_black():
    array = np.array([0.0, 0.0, 0.0])
    assert np.allclose(srgb_to_linear(array), 0.0)
    assert np.allclose(linear_to_srgb(array), 0.0)


def test_white_maps_to_white():
    array = np.array([1.0, 1.0, 1.0])
    assert np.allclose(srgb_to_linear(array), 1.0)
    assert np.allclose(linear_to_srgb(array), 1.0)


def test_round_trip_linear_srgb_linear():
    rng = np.random.default_rng(0)
    linear = rng.uniform(0.0, 1.0, size=(16, 16, 3)).astype(np.float32)
    round_tripped = srgb_to_linear(linear_to_srgb(linear))
    assert np.allclose(linear, round_tripped, atol=1e-4)


def test_srgb_to_linear_does_not_mutate_input():
    array = np.array([0.1, 0.5, 0.9])
    original = array.copy()
    srgb_to_linear(array)
    assert np.array_equal(array, original)


def test_linear_to_srgb_does_not_mutate_input():
    array = np.array([0.1, 0.5, 0.9])
    original = array.copy()
    linear_to_srgb(array)
    assert np.array_equal(array, original)
