# uwrestore

Physically-grounded underwater image and video restoration. This is not a
color filter or a make-colors-pop enhancement tool — the goal is to recover
the most plausible scene appearance that would have existed without
underwater degradation (attenuation, backscatter, color cast), by modeling
the physics of light underwater rather than applying stylistic correction.
Restoration happens in linear light, and photos and video share one
pipeline (a photo is a video with one frame).

## Status

See `LOG.md` for current progress and session history.

## Install

Requires Python >= 3.10.

```bash
pip install -e ".[dev]"
```

Dependencies are deliberately minimal: numpy and opencv-python-headless
(plus pytest for the dev extra).

## Usage

```bash
# Score a corrected input (temporal stability always; ΔE if a chart is given)
uw score path/to/input.mp4 --profile srgb --chart data/chart_refs.json

# Apply a correction method and write the result
uw correct path/to/input.mp4 --method gray_world --out out.mp4
```

`--profile` selects the source transfer function (default `srgb`) so linear
conversion assumptions are always explicit, never guessed. `uw correct`
refuses to overwrite an existing output file unless `--overwrite` is passed.

## Project rules and roadmap

- `CLAUDE.md` — the invariants this project must never violate (linear-light
  processing, video-first architecture, ablation flags, data safety, etc.)
- `PLAN.md` — the week-by-week roadmap and current phase
- `LOG.md` — running log of scores and observations across sessions
