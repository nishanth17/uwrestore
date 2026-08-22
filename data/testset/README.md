# Frozen test set

This directory is **frozen**. Never modify, rename, or delete files here
without an explicit decision to re-freeze the set (see CLAUDE.md
invariant 6 and PLAN.md's per-session `uw score` gate). Both still images
and clips should eventually exist in each category — Week 1 only creates
the folder structure; no real footage is added yet.

- `chart/` — color chart / reference target footage, used for
  chart-referenced ΔE ground truth (see `data/chart_refs.json`).
- `distance/` — normal-visibility scenes with subjects at varying
  distances from the camera, for range-dependent correction testing.
- `murky/` — low-visibility, backscatter-heavy footage.
- `lights/` — footage lit (partly or fully) by artificial dive
  lights/flashlights rather than ambient sunlight.
- `swimthrough/` — continuous swim-through video, for temporal
  consistency evaluation specifically (not single-frame quality).

Every change gets checked against the full spread of these categories, not
just one (CLAUDE.md invariant 6) — a gain in one category that costs
another must be documented, not hidden.
