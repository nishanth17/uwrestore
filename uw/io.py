"""Loading and saving FrameSequences.

Ingest maps from an explicit source transfer function to linear-light RGB
(CLAUDE.md invariant 1). The caller must state which profile applies via
`profile=`; this module never guesses a profile from filename or codec.

Export converts linear-light RGB back to an output transfer function
(sRGB only, for Week 1) at the last possible step.
"""

import os

import cv2
import numpy as np

from uw.colorspace import linear_to_srgb, protune_flat_to_linear, srgb_to_linear
from uw.types import TRANSFER_FUNCTIONS, Frame, FrameSequence

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".exr"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv"}

DEFAULT_OUTPUT_FPS = 30.0


def _to_unit_float(array: np.ndarray) -> np.ndarray:
    """Decoded pixel array (any common dtype) -> float32 in [0, 1]."""
    if np.issubdtype(array.dtype, np.floating):
        return array.astype(np.float32)
    if array.dtype == np.uint8:
        return array.astype(np.float32) / 255.0
    if array.dtype == np.uint16:
        return array.astype(np.float32) / 65535.0
    raise ValueError(f"unsupported pixel dtype on ingest: {array.dtype}")


def _apply_transfer_function(unit_float_rgb: np.ndarray, profile: str) -> np.ndarray:
    if profile == "srgb":
        return srgb_to_linear(unit_float_rgb)
    if profile == "raw_linear":
        return unit_float_rgb
    if profile == "protune":
        return protune_flat_to_linear(unit_float_rgb)
    raise ValueError(
        f"unknown transfer function profile {profile!r}; must be one of {TRANSFER_FUNCTIONS}"
    )


def _classify_path(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    raise ValueError(
        f"cannot determine whether {path!r} is an image or video from its "
        f"extension {ext!r}; supported image extensions: {sorted(IMAGE_EXTENSIONS)}, "
        f"video extensions: {sorted(VIDEO_EXTENSIONS)}"
    )


def _load_image(path: str, profile: str) -> FrameSequence:
    bgr = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if bgr is None:
        raise IOError(
            f"failed to decode image {path!r} (if this is an EXR, OpenCV may "
            f"need the OPENCV_IO_ENABLE_OPENEXR=1 environment variable set)"
        )
    if bgr.ndim == 2:
        bgr = cv2.cvtColor(bgr, cv2.COLOR_GRAY2BGR)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    unit_float = _to_unit_float(rgb)
    linear = _apply_transfer_function(unit_float, profile)
    frame = Frame(
        image=linear.astype(np.float32),
        metadata={
            "source_path": os.path.abspath(path),
            "frame_index": 0,
            "fps": None,
            "transfer_function": profile,
        },
    )
    return FrameSequence([frame])


def _load_video(path: str, profile: str) -> FrameSequence:
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise IOError(f"failed to open video {path!r}")
    fps = cap.get(cv2.CAP_PROP_FPS) or None
    frames = []
    try:
        index = 0
        while True:
            ok, bgr = cap.read()
            if not ok:
                break
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            unit_float = _to_unit_float(rgb)
            linear = _apply_transfer_function(unit_float, profile)
            frames.append(
                Frame(
                    image=linear.astype(np.float32),
                    metadata={
                        "source_path": os.path.abspath(path),
                        "frame_index": index,
                        "fps": fps,
                        "transfer_function": profile,
                    },
                )
            )
            index += 1
    finally:
        cap.release()
    if not frames:
        raise IOError(f"video {path!r} decoded zero frames")
    return FrameSequence(frames)


def load(path, profile: str = "srgb") -> FrameSequence:
    """Load an image or video into a FrameSequence, converted to linear RGB.

    `profile` states the source transfer function explicitly — one of
    TRANSFER_FUNCTIONS ("srgb", "protune", "raw_linear"). It is never
    inferred from filename or codec; the caller (or the CLI's --profile
    flag) must state it. Defaults to "srgb", the common case for
    consumer jpg/png/video — pass profile explicitly for Protune or
    already-linear (RAW-exported) sources.
    """
    path = str(path)
    if profile not in TRANSFER_FUNCTIONS:
        raise ValueError(f"profile must be one of {TRANSFER_FUNCTIONS}, got {profile!r}")
    kind = _classify_path(path)
    if kind == "image":
        return _load_image(path, profile)
    return _load_video(path, profile)


def _linear_frame_to_srgb_bgr_uint8(frame: Frame) -> np.ndarray:
    srgb = linear_to_srgb(frame.image)
    srgb_uint8 = np.clip(srgb * 255.0 + 0.5, 0, 255).astype(np.uint8)
    return cv2.cvtColor(srgb_uint8, cv2.COLOR_RGB2BGR)


def _save_image(frame: Frame, path: str) -> None:
    bgr_uint8 = _linear_frame_to_srgb_bgr_uint8(frame)
    ok = cv2.imwrite(path, bgr_uint8)
    if not ok:
        raise IOError(f"failed to write image {path!r}")


def _save_video(frames: FrameSequence, path: str) -> None:
    first = frames[0]
    fps = first.metadata.get("fps") or DEFAULT_OUTPUT_FPS
    height, width = first.image.shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(path, fourcc, fps, (width, height))
    if not writer.isOpened():
        raise IOError(f"failed to open video writer for {path!r}")
    try:
        for frame in frames:
            writer.write(_linear_frame_to_srgb_bgr_uint8(frame))
    finally:
        writer.release()


def save(frames: FrameSequence, path, overwrite: bool = False) -> None:
    """Save a FrameSequence, converting linear RGB to sRGB for export.

    Week 1 only supports sRGB output. Refuses to overwrite an existing
    file unless `overwrite=True`, and always refuses to write to any
    frame's own recorded source_path, overwrite or not (CLAUDE.md
    invariant 7: never modify or overwrite original source footage).
    """
    path = str(path)
    abs_path = os.path.abspath(path)

    for frame in frames:
        source_path = frame.metadata.get("source_path")
        if source_path is not None and os.path.abspath(source_path) == abs_path:
            raise ValueError(
                f"refusing to write to {path!r}: it is the source_path of one "
                f"of the frames being saved (never overwrite source footage)"
            )

    if os.path.exists(path) and not overwrite:
        raise FileExistsError(
            f"{path!r} already exists; pass overwrite=True (CLI: --overwrite) to replace it"
        )

    kind = _classify_path(path)
    if kind == "image":
        if len(frames) != 1:
            raise ValueError(
                f"cannot save a {len(frames)}-frame FrameSequence to an image path {path!r}"
            )
        _save_image(frames[0], path)
    else:
        _save_video(frames, path)
