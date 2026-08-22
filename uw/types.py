"""Core data abstractions: Frame and FrameSequence.

No I/O or processing logic here — see uw/io.py for loading/saving and
uw/colorspace.py, uw/baselines.py etc. for processing. This split lets
later stages (depth, restoration, temporal) depend on the types without
pulling in I/O.
"""

from dataclasses import dataclass, field

import numpy as np

# Valid values for Frame.metadata["transfer_function"]:
#   "srgb"        - standard sRGB EOTF was applied to reach linear light
#   "protune"     - GoPro Protune Flat curve was applied (see colorspace.py
#                    for the approximation/stub status of this mapping)
#   "raw_linear"  - input array was already linear light; no EOTF applied
TRANSFER_FUNCTIONS = ("srgb", "protune", "raw_linear")


@dataclass
class Frame:
    """A single linear-light RGB frame plus provenance metadata.

    Invariant, must hold everywhere a Frame is constructed or returned:
    - image is RGB, never BGR
    - image is floating point
    - image is normalized to [0, 1]
    - image is linear-light RGB (no gamma/EOTF encoding remaining)
    """

    image: np.ndarray  # float, shape (H, W, 3), RGB, linear-light, [0, 1]
    metadata: dict = field(default_factory=dict)
    # metadata keys used by this project:
    #   source_path: str
    #   frame_index: int
    #   fps: float | None        (None for stills)
    #   transfer_function: str   (one of TRANSFER_FUNCTIONS; the profile
    #                             assumed/detected on ingest for this source)


class FrameSequence:
    """An ordered collection of Frames.

    A photo is a FrameSequence of length 1; a video is a FrameSequence of
    length N. Week 1 backs this with a plain list — callers must not rely
    on that; they should only use iteration, len(), and indexing.
    """

    def __init__(self, frames):
        self._frames = list(frames)

    def __iter__(self):
        return iter(self._frames)

    def __len__(self):
        return len(self._frames)

    def __getitem__(self, index):
        return self._frames[index]
