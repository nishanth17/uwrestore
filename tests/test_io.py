import cv2
import numpy as np

from uw.io import load, save
from uw.types import Frame, FrameSequence


def _write_solid_bgr_image(path, bgr):
    image = np.zeros((8, 8, 3), dtype=np.uint8)
    image[:, :] = bgr
    cv2.imwrite(str(path), image)


def _write_synthetic_video(path, num_frames=5, size=(8, 8)):
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, 10.0, size)
    for i in range(num_frames):
        frame = np.full((size[1], size[0], 3), fill_value=i * 20, dtype=np.uint8)
        writer.write(frame)
    writer.release()


def test_image_load_returns_frame_sequence_of_length_1(tmp_path):
    path = tmp_path / "img.png"
    _write_solid_bgr_image(path, (50, 100, 200))  # BGR
    frames = load(path)
    assert len(frames) == 1


def test_video_iteration_yields_expected_frame_count(tmp_path):
    path = tmp_path / "clip.mp4"
    _write_synthetic_video(path, num_frames=5)
    frames = load(path)
    assert len(frames) == 5
    count = 0
    for _ in frames:
        count += 1
    assert count == 5


def test_rgb_channel_ordering_is_preserved_not_bgr(tmp_path):
    path = tmp_path / "img.png"
    # BGR on disk: blue=50, green=100, red=200 -> after RGB fix, red channel
    # should be the brightest.
    _write_solid_bgr_image(path, (50, 100, 200))
    frames = load(path)
    frame = frames[0]
    r, g, b = frame.image[0, 0, 0], frame.image[0, 0, 1], frame.image[0, 0, 2]
    assert r > g > b


def test_frame_invariant_holds_on_load(tmp_path):
    path = tmp_path / "img.png"
    _write_solid_bgr_image(path, (10, 128, 250))
    frame = load(path)[0]
    assert frame.image.dtype.kind == "f"
    assert frame.image.min() >= 0.0
    assert frame.image.max() <= 1.0
    # linear-light: sRGB midtone (128/255 ~ 0.50) should map below 0.50
    # once converted to linear, since the sRGB EOTF darkens midtones.
    assert frame.image[0, 0, 1] < 0.50


def test_saved_output_can_be_loaded_again(tmp_path):
    src_path = tmp_path / "src.png"
    _write_solid_bgr_image(src_path, (50, 100, 200))
    frames = load(src_path)

    out_path = tmp_path / "out.png"
    save(frames, out_path)
    reloaded = load(out_path)

    assert len(reloaded) == 1
    assert np.allclose(frames[0].image, reloaded[0].image, atol=1e-2)


def test_save_refuses_to_overwrite_without_flag(tmp_path):
    path = tmp_path / "out.png"
    frame = Frame(image=np.zeros((4, 4, 3), dtype=np.float32), metadata={})
    save(FrameSequence([frame]), path)
    try:
        save(FrameSequence([frame]), path)
        assert False, "expected FileExistsError"
    except FileExistsError:
        pass
    save(FrameSequence([frame]), path, overwrite=True)


def test_save_refuses_to_overwrite_source_path(tmp_path):
    src_path = tmp_path / "src.png"
    _write_solid_bgr_image(src_path, (10, 20, 30))
    frames = load(src_path)
    try:
        save(frames, src_path, overwrite=True)
        assert False, "expected ValueError for overwriting source"
    except ValueError:
        pass
