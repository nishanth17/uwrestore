"""Baseline correction methods. Week 1: gray-world only.

Correction stages operate on linear-light RGB and are pure functions of a
Frame (CLAUDE.md invariant 3): they never mutate their input and never hold
hidden state.
"""

import numpy as np

from uw.types import Frame


def gray_world(frame: Frame) -> Frame:
    """Scale R/G/B channel means toward neutral gray, in linear light.

    Returns a new Frame; does not mutate the input. Values may exceed
    [0, 1] after scaling — this is not clipped here, so downstream
    consumers (e.g. export) see the true, unclipped result and decide how
    to handle it, rather than clipping being silently baked in.
    """
    image = frame.image
    channel_means = image.reshape(-1, 3).mean(axis=0)
    overall_mean = channel_means.mean()

    # Avoid divide-by-zero for a degenerate (e.g. pure black) channel.
    scale = np.where(channel_means > 0, overall_mean / np.where(channel_means == 0, 1, channel_means), 1.0)

    corrected = image * scale.reshape(1, 1, 3)

    clipped_fraction = float(np.mean((corrected < 0) | (corrected > 1)))

    new_metadata = dict(frame.metadata)
    new_metadata["gray_world_channel_scale"] = scale.tolist()
    new_metadata["gray_world_out_of_range_fraction"] = clipped_fraction

    return Frame(image=corrected.astype(image.dtype), metadata=new_metadata)
