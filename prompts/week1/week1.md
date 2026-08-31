Read CLAUDE.md first and follow its invariants strictly.

Do not modify CLAUDE.md or PLAN.md. If you believe a project rule needs changing, explain why instead of changing it.

Build the Week 1 skeleton for this underwater restoration project.

Scope: everything below except the ΔE/CIEDE2000 metric implementation. I will implement that separately with another model, so stub it out exactly as described and do not implement it.

The goal of this session is a minimal but real working foundation, not a future-proof framework. Avoid overengineering, unnecessary abstractions, or speculative features.

For Week 1, an eager implementation of FrameSequence backed by a list is acceptable, as long as the FrameSequence interface itself does not require callers to know that. Do not spend this session building a streaming/windowed decoder — that's future work if and when a real clip actually needs it. The explicit per-source transfer-function mapping (sRGB EOTF vs GoPro Protune vs RAW linear) below is a real invariant to implement now, not optional polish.

Use standard Python dependencies (numpy, opencv-python) only. Do not add heavyweight ML/CV dependencies this session (torch, torchvision, decord, ffmpeg-python, rawpy, etc.) unless something below explicitly requires it — none of it does.

## 1. uw/types.py and uw/io.py

`uw/types.py` contains only the core data abstractions — `Frame` and
`FrameSequence` — no processing or I/O logic. `uw/io.py` contains loading
and saving, importing the types from `uw/types.py`. This split matters
because later stages (depth, restoration, temporal) will all need to import
`Frame`/`FrameSequence` without pulling in I/O code.

In `uw/types.py`, implement `Frame` and `FrameSequence`.

In `uw/io.py`, implement:

```
load(path) -> FrameSequence
save(frames: FrameSequence, path)
```

`FrameSequence` is the project's abstraction for an ordered iterable
collection of Frames — a photo is a `FrameSequence` of length 1, a video is
a `FrameSequence` of length N. For Week 1, backing it with a plain list
internally is fine — callers should just never need to know or care
whether it's eager or lazy. Don't build a streaming/windowed decoder this
session, and don't build a formal ABC/protocol hierarchy for it — a simple
class is enough.

`FrameSequence` must support at minimum:
- iteration (`for frame in sequence`)
- `len()`
- indexing (`sequence[i]`), since it's list-backed this session

Callers should never need to know or care whether storage is eager or
lazy — but for Week 1, since it's list-backed, all three of the above are
straightforward to support and are relied on by the tests below.

`Frame` is a simple dataclass containing:

- image: float RGB numpy array, shape (H, W, 3)
- metadata:
  - source path
  - frame index
  - fps if video
  - original colorspace / transfer function

Frame invariant (must hold everywhere):

- image is always RGB, never BGR
- image is always floating point
- image is always normalized to [0,1]
- image is always LINEAR-light RGB

Ingest must explicitly map from the **source transfer function** to linear
RGB — this is a per-source decision, not a single blanket conversion:

- standard sRGB EOTF (typical consumer jpg/png, standard video profiles)
- GoPro Protune Flat curve (if detectable from metadata, or pass an
  explicit `--profile` flag if not auto-detectable — don't guess silently)
- RAW sensor linear (already linear — no EOTF mapping needed, just decode)

If the input transfer function cannot be determined reliably, fail loudly
or require an explicit `--profile` argument. Do not silently assume a
profile because the filename or codec looks familiar (e.g. no
`if "GOPR" in filename: profile = "protune"` guessing) — a wrong silent
assumption here is worse than an error asking for clarification.

Document which profile was assumed for a given input in the Frame's
metadata, so it's inspectable later, not just applied and forgotten.

Support:

- common image formats (jpg/png)
- common video formats (mp4/mov)

Prefer OpenCV for initial implementation unless there is a strong reason not to. Do not add multiple decoding libraries unnecessarily. OpenCV loads images and video frames in BGR by default — explicitly convert to RGB (`cv2.cvtColor(..., cv2.COLOR_BGR2RGB)`) immediately upon ingestion, before any other processing and before constructing the `Frame`. This is a common silent bug: forgetting this step won't error, it'll just quietly swap red and blue for the rest of the pipeline.

Behavior:

- A single image returns a `FrameSequence` of length 1.
- A video returns a `FrameSequence` yielding one Frame per decoded frame.
- The caller should never need separate image vs video logic — same API,
  same return type, iterate either way.

Implement:

```
save(frames: FrameSequence, path)
```

Requirements:

- Convert linear RGB back to the appropriate output transfer function
  before writing. For Week 1, only standard sRGB export is required — the
  architecture should preserve enough metadata (e.g. what profile was
  assumed on ingest) that additional output profiles can be added later,
  but don't implement output profile selection now.
- Infer image vs video from extension.
- Do not overwrite source files silently.
- If the output path already exists, either fail clearly with an error or
  require an explicit `--overwrite` flag — don't silently replace it (a
  bare `cv2.imwrite(path, image)` will overwrite without asking; guard
  against that explicitly).
- Preserve RGB ordering.

---

## 2. uw/colorspace.py

Implement pure functions:

```
srgb_to_linear(array)
linear_to_srgb(array)
```

Requirements:

- Standard sRGB EOTF formulas.
- No I/O.
- Pure functions.
- Unit-testable.
- Preserve numpy array behavior.

If a GoPro Protune Flat -> linear mapping isn't something you can implement
correctly from first principles this session (it's not a simple gamma
curve), it's fine to implement a documented approximation or stub it with
a clear TODO and note the limitation — don't fabricate an inaccurate
formula silently. Flag this explicitly in your end-of-session summary.

---

## 3. uw/baselines.py

Implement:

```
gray_world(frame: Frame) -> Frame
```

Requirements:

- Operates in LINEAR light.
- Scale R/G/B channel means toward neutral gray.
- Return a new Frame, do not mutate input.
- Preserve metadata.
- Do not silently hide clipping behavior.

---

## 4. uw/metrics.py

Do not implement ΔE/CIEDE2000.

Create:

```
delta_e(frame: Frame, chart_patches: dict) -> float
```

that raises exactly:

```
NotImplementedError("implemented separately — see week 1 notes")
```

Implement:

```
temporal_stability(frames: FrameSequence) -> float
```

as a placeholder metric — e.g. mean RGB per frame, then variance across
frames. Iterate over the FrameSequence rather than assuming a specific
backing structure, so it keeps working if the implementation changes later.

Document clearly that this is only a placeholder proxy and not the final video-quality metric.

---

## 5. uw/cli.py

Use the standard library `argparse` for CLI parsing. Do not use external
libraries like `click` or `typer` — this falls under the same
standard-library-only constraint as the rest of the session.

Implement:

### Score

Command:

```
uw score <path>
```

Behavior:

- Load input.
- Run gray_world baseline.
- Print temporal_stability.
- Print:

```
ΔE: not yet implemented
```

Do not attempt ΔE calculation.

---

### Correct

Command:

```
uw correct <path> --method gray_world --out <path>
```

Behavior:

- Load input.
- Apply requested correction.
- Save output.

Only implement:

```
gray_world
```

as the available method.

---

## 6. data/testset/

Create directory structure:

```
data/testset/
    chart/
    distance/
    murky/
    lights/
    swimthrough/
```

Do not add actual footage.

Create a README explaining what belongs in each folder:

- chart:
  - color chart/reference footage

- distance:
  - scenes with objects at varying distances

- murky:
  - low visibility/backscatter-heavy footage

- lights:
  - artificial dive lights/flashlight footage

- swimthrough:
  - continuous video movement for temporal evaluation

Mention that both still images and clips should eventually exist.

Create:

```
data/chart_refs.json
```

with placeholder structure:

```json
{
  "patch_name": {
    "L": 0,
    "a": 0,
    "b": 0
  }
}
```

---

## 7. LOG.md

Create:

```
LOG.md
```

Include:

- header describing logging format:
  - date
  - change made
  - ΔE before/after
  - temporal stability before/after
  - visual observations
  - surprises/failures
  - next hypothesis

Add an initial entry for this session:

- Week 1 skeleton created.
- ΔE not implemented yet.
- Baseline pipeline exists.
- Metrics are placeholders where noted.
- Note explicitly whether Protune Flat -> linear was implemented properly,
  approximated, or stubbed.

---

## Tests

Write minimal real tests for:

### colorspace.py

Test:

- black maps correctly
- white maps correctly
- round-trip:

```
linear -> sRGB -> linear
```

approximately preserves values.
- srgb_to_linear and linear_to_srgb do not mutate their input array
  (return a new array; the caller's original array is unchanged after
  the call).

### io.py

Test:

- image load returns a FrameSequence of length 1.
- iterating a FrameSequence from a short synthetic video yields the
  expected number of Frames.
- saved output can be loaded again.
- Frame invariant holds:
  - RGB
  - floating point
  - [0,1]
  - linear-light

Avoid large fixtures. Use small generated test images/clips.

---

## Before finishing

Run:

1. All tests.
2. Run a sample `uw score` only if you create a small synthetic test
   fixture as part of this session (e.g. a generated image and a short
   generated clip) — don't go looking for real footage that doesn't
   exist yet.
3. Verify:
   - delta_e is still only a stub.
   - no CLAUDE.md/PLAN.md changes.
   - Frame invariant is maintained everywhere.
   - FrameSequence is used consistently as an interface — no caller
     branches on photo-vs-video.

At the end, summarize:

- files created/modified
- tests run
- any assumptions made (especially around Protune Flat handling)
- any issues or follow-up items

Remember: this is the correctness-first Week 1 baseline. Do not add future depth models, temporal models, neural components, or restoration algorithms yet.