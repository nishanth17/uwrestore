"""Stage 3/4/6 — inspectable diagnostics.

EXPLORATORY. Main project venv (numpy + opencv only; no matplotlib, per
CLAUDE.md invariant 8 — the plots here are simple enough to draw with cv2).

CLAUDE.md invariant 5: a metric improvement is not a result until the output has
been looked at. These are the images that get looked at.

Produces, under `--out-dir`:
    range_<config>_<clip>.jpg        dense range maps, one tile per sampled frame
    conf_<config>_<clip>.jpg         the matching confidence maps
    diff_<a>_vs_<b>_<clip>.jpg       per-pixel relative range difference after
                                     ONE clip-level global scale
    traj_<clip>.jpg                  classical camera trajectories, all configs,
                                     top-down and side, each normalised only by
                                     its own extent (they are not co-registered)

Range maps use a per-CLIP colour scale shared across configurations and frames,
so a frame that drifts looks different rather than being renormalised into
looking the same. Invalid pixels are magenta, never black — black would read as
"near".
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import cv2
import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week3_geometry.geometry import fit_global_scale, sample_at_observations  # noqa: E402
from experiments.week3_geometry.rangeio import RangeReader  # noqa: E402
from experiments.week3_geometry.scripts.compare import (  # noqa: E402
    RANGE_ROOT, W3, load_classical, load_preprocess_maps, map_to_grid,
)

INVALID = (255, 0, 255)   # magenta in BGR-ish terms; unmistakable


def colorize_range(r, valid, lo, hi):
    """Range -> a perceptually ordered colour map with explicit invalid pixels.

    LOG range, deliberately. Attenuation and backscatter are exponential in
    range, so equal ratios matter equally; a linear ramp puts almost the whole
    colour budget into the far field, where the restoration has least signal,
    and flattens the near field, where it has most.
    """
    r = np.asarray(r, dtype=np.float64)
    v = np.asarray(valid, dtype=bool)
    lo = max(float(lo), 1e-6)
    hi = max(float(hi), lo * 1.001)
    with np.errstate(invalid="ignore", divide="ignore"):
        x = (np.log(np.where(r > 0, r, np.nan)) - np.log(lo)) / (np.log(hi) - np.log(lo))
    x = np.clip(x, 0, 1)
    x = np.where(v & np.isfinite(x), x, 0.0)
    img = cv2.applyColorMap((255 * (1 - x)).astype(np.uint8), cv2.COLORMAP_TURBO)
    img[~v] = INVALID
    return img


def tile(images, cols, labels=None, label_h=18):
    h, w = images[0].shape[:2]
    rows = int(np.ceil(len(images) / cols))
    canvas = np.zeros((rows * (h + label_h), cols * w, 3), np.uint8)
    for i, im in enumerate(images):
        r, c = divmod(i, cols)
        y0 = r * (h + label_h)
        canvas[y0 + label_h:y0 + label_h + h, c * w:(c + 1) * w] = im
        if labels:
            cv2.putText(canvas, labels[i], (c * w + 3, y0 + 13),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (230, 230, 230), 1, cv2.LINE_AA)
    return canvas


def clip_scale(reader, frames):
    lo, hi = [], []
    for i in frames:
        rec = reader.by_index[i]
        if np.isfinite(rec["range_p05"]):
            lo.append(rec["range_p05"])
            hi.append(rec["range_p95"])
    if not lo:
        return 1e-3, 1.0
    # Trim to the 10th/90th percentile of the per-frame p05/p95, so one frame
    # with a sky-facing infinity does not eat the whole colour scale.
    return float(np.percentile(lo, 10)), float(np.percentile(hi, 90))


def pick_frames(reader, k=8):
    idx = reader.frame_indices
    if len(idx) <= k:
        return idx
    return [idx[i] for i in np.linspace(0, len(idx) - 1, k).round().astype(int)]


def render_dense(cfg, clip, out_dir, cell_w=260, cols=4, overwrite=False):
    try:
        rd = RangeReader(RANGE_ROOT, cfg, clip)
    except FileNotFoundError:
        return []
    frames = pick_frames(rd)
    lo, hi = clip_scale(rd, frames)
    rimgs, cimgs, labels = [], [], []
    for i in frames:
        r, v, c = rd.load(i, want_conf=True)
        r = np.asarray(r)
        v = np.asarray(v)
        img = colorize_range(r, v, lo, hi)
        sc = cell_w / img.shape[1]
        rimgs.append(cv2.resize(img, (cell_w, int(round(img.shape[0] * sc))),
                                interpolation=cv2.INTER_NEAREST))
        labels.append(f"f{i} valid {100*float(v.mean()):.0f}%")
        if c is not None:
            c = np.asarray(c, dtype=np.float64)
            fin = np.isfinite(c)
            p1, p99 = (np.percentile(c[fin], [1, 99]) if fin.any() else (0, 1))
            x = np.clip((c - p1) / max(p99 - p1, 1e-9), 0, 1)
            ci = cv2.applyColorMap((255 * x).astype(np.uint8), cv2.COLORMAP_VIRIDIS)
            ci[~fin] = INVALID
            cimgs.append(cv2.resize(ci, (cell_w, int(round(ci.shape[0] * sc))),
                                    interpolation=cv2.INTER_NEAREST))
    written = []
    os.makedirs(out_dir, exist_ok=True)
    for name, imgs in (("range", rimgs), ("conf", cimgs)):
        if not imgs:
            continue
        p = os.path.join(out_dir, f"{name}_{cfg}_{clip}.jpg")
        if os.path.exists(p) and not overwrite:
            raise SystemExit(f"refusing to overwrite {p!r} (pass --overwrite)")
        canvas = tile(imgs, cols, labels)
        cv2.putText(canvas, f"{cfg} {clip}  {name}  scale {lo:.2f}-{hi:.2f} "
                            f"(shared across frames; magenta = invalid)",
                    (4, canvas.shape[0] - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                    (255, 255, 255), 1, cv2.LINE_AA)
        cv2.imwrite(p, canvas, [cv2.IMWRITE_JPEG_QUALITY, 88])
        written.append(p)
    return written


def render_diff(cfg_a, fam_a, cfg_b, fam_b, clip, maps, out_dir,
                cell_w=260, cols=4, overwrite=False):
    """Per-pixel relative range difference after ONE clip-level global scale."""
    try:
        ra = RangeReader(RANGE_ROOT, cfg_a, clip)
        rb = RangeReader(RANGE_ROOT, cfg_b, clip)
    except FileNotFoundError:
        return []
    rep = json.load(open(os.path.join(W3, "outputs", "frames", "extraction_report.json")))
    src_hw = tuple(rep["clips"][clip]["extracted_shape_hw"])
    key = f"{src_hw[0]}x{src_hw[1]}"
    ma, mb = maps[fam_a][key], maps[fam_b][key]
    frames = [i for i in pick_frames(ra) if i in rb.by_index]
    if not frames:
        return []

    # One scale for the clip, fitted on the SAME frames that will be drawn.
    A, B = [], []
    for i in ra.frame_indices:
        if i not in rb.by_index:
            continue
        Ra, Va = ra.load(i)
        Rb, Vb = rb.load(i)
        ha, wa = np.asarray(Ra).shape
        vv, uu = np.meshgrid(np.arange(0, ha, 6, dtype=np.float64),
                             np.arange(0, wa, 6, dtype=np.float64), indexing="ij")
        uva = np.stack([uu.ravel(), vv.ravel()], axis=1)
        src = np.empty_like(uva)
        src[:, 0] = (uva[:, 0] - ma["u_offset"]) / ma["u_scale"]
        src[:, 1] = (uva[:, 1] - ma["v_offset"]) / ma["v_scale"]
        va, oka = sample_at_observations(np.asarray(Ra, np.float64), np.asarray(Va, bool), uva)
        vb, okb = sample_at_observations(np.asarray(Rb, np.float64), np.asarray(Vb, bool),
                                         map_to_grid(src, mb))
        ok = oka & okb
        if ok.any():
            A.append(va[ok])
            B.append(vb[ok])
    if not A:
        return []
    s = fit_global_scale(np.concatenate(A), np.concatenate(B)).scale

    imgs, labels = [], []
    for i in frames:
        Ra, Va = ra.load(i)
        Rb, Vb = rb.load(i)
        ha, wa = np.asarray(Ra).shape
        vv, uu = np.meshgrid(np.arange(ha, dtype=np.float64),
                             np.arange(wa, dtype=np.float64), indexing="ij")
        uva = np.stack([uu.ravel(), vv.ravel()], axis=1)
        src = np.empty_like(uva)
        src[:, 0] = (uva[:, 0] - ma["u_offset"]) / ma["u_scale"]
        src[:, 1] = (uva[:, 1] - ma["v_offset"]) / ma["v_scale"]
        vb, okb = sample_at_observations(np.asarray(Rb, np.float64), np.asarray(Vb, bool),
                                         map_to_grid(src, mb))
        a = np.asarray(Ra, np.float64).ravel()
        oka = np.asarray(Va, bool).ravel()
        ok = oka & okb & np.isfinite(a) & np.isfinite(vb) & (vb > 0)
        rel = np.full(a.shape, np.nan)
        rel[ok] = (s * a[ok] - vb[ok]) / vb[ok]
        rel = rel.reshape(ha, wa)
        # Diverging blue-white-red built by hand: OpenCV ships no diverging map,
        # and a sequential one (JET/TURBO) would hide the sign of the residual,
        # which is the whole point of a difference image.
        x = np.clip((rel + 0.3) / 0.6, 0, 1)          # +/-30 % full scale
        t = (2.0 * x - 1.0)                            # -1 .. +1
        neg, pos = np.clip(-t, 0, 1), np.clip(t, 0, 1)
        img = np.stack([                               # BGR
            (255 * (1 - pos)).astype(np.uint8),
            (255 * (1 - neg - pos)).clip(0, 255).astype(np.uint8),
            (255 * (1 - neg)).astype(np.uint8)], axis=-1)
        img[~np.isfinite(rel)] = INVALID
        sc = cell_w / img.shape[1]
        imgs.append(cv2.resize(img, (cell_w, int(round(img.shape[0] * sc))),
                               interpolation=cv2.INTER_NEAREST))
        fin = np.isfinite(rel)
        labels.append(f"f{i} med {100*np.median(rel[fin]):+.1f}%" if fin.any() else f"f{i} -")
    os.makedirs(out_dir, exist_ok=True)
    p = os.path.join(out_dir, f"diff_{cfg_a}_vs_{cfg_b}_{clip}.jpg")
    if os.path.exists(p) and not overwrite:
        raise SystemExit(f"refusing to overwrite {p!r} (pass --overwrite)")
    canvas = tile(imgs, cols, labels)
    cv2.putText(canvas, f"({cfg_a} x {s:.3f}) - {cfg_b}, relative. blue=-30% red=+30%, "
                        f"ONE clip-level scale, magenta=invalid",
                (4, canvas.shape[0] - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                (255, 255, 255), 1, cv2.LINE_AA)
    cv2.imwrite(p, canvas, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return [p]


def render_trajectories(clip, configs, out_dir, size=340, overwrite=False):
    """Camera centres per classical config, top-down (XZ) and side (XY).

    Each configuration is drawn in its OWN normalised frame. They are not
    co-registered and the plots must not be read as an overlay: the point is the
    SHAPE of each trajectory — smooth arc vs jittering vs collapsed.
    """
    from experiments.week3_geometry.scripts.compare import _T_cw
    panels, labels = [], []
    for cfg in configs:
        m = load_classical(cfg, clip)
        if m is None:
            continue
        C = []
        for img in sorted(m["images"].values(), key=lambda i: i["name"]):
            T = _T_cw(img["qvec_wxyz_cw"], img["tvec_cw"])
            C.append(-T[:3, :3].T @ T[:3, 3])
        if len(C) < 2:
            continue
        C = np.asarray(C)
        for k, (ax, ay, nm) in enumerate([(0, 2, "top XZ"), (0, 1, "side XY")]):
            img = np.full((size, size, 3), 24, np.uint8)
            p = C[:, [ax, ay]]
            span = max(p.max(0) - p.min(0)); span = span if span > 0 else 1.0
            q = ((p - p.min(0)) / span * (size - 40) + 20).astype(int)
            for j in range(len(q) - 1):
                t = j / max(len(q) - 2, 1)
                cv2.line(img, tuple(q[j]), tuple(q[j + 1]),
                         (int(255 * (1 - t)), 160, int(255 * t)), 1, cv2.LINE_AA)
            for pt in q:
                cv2.circle(img, tuple(pt), 2, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.putText(img, f"{cfg} {nm} n={len(C)}", (6, size - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1, cv2.LINE_AA)
            panels.append(img)
            labels.append(f"{cfg} {nm}")
    if not panels:
        return []
    os.makedirs(out_dir, exist_ok=True)
    p = os.path.join(out_dir, f"traj_{clip}.jpg")
    if os.path.exists(p) and not overwrite:
        raise SystemExit(f"refusing to overwrite {p!r} (pass --overwrite)")
    canvas = tile(panels, 4, labels)
    cv2.putText(canvas, f"{clip}: camera centres, each config in ITS OWN normalised frame "
                        f"(NOT co-registered). blue->magenta = time.",
                (4, canvas.shape[0] - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                (255, 255, 255), 1, cv2.LINE_AA)
    cv2.imwrite(p, canvas, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return [p]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default=os.path.join(W3, "outputs", "diagnostics"))
    ap.add_argument("--clips", nargs="*", default=None)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    spec = json.load(open(os.path.join(W3, "configs", "phase3a_clips.json")))
    clips = args.clips or [c["id"] for c in spec["clips"]]
    maps = load_preprocess_maps()
    dense = {"D_mapanything": "mapanything", "E0_vggt": "vggt", "E_wat3r_ren": "wat3r_ren"}
    n = 0
    for clip in clips:
        for cfg in dense:
            n += len(render_dense(cfg, clip, args.out_dir, overwrite=args.overwrite))
        for a, fa, b, fb in [("E0_vggt", "vggt", "E_wat3r_ren", "wat3r_ren"),
                             ("D_mapanything", "mapanything", "E0_vggt", "vggt")]:
            n += len(render_diff(a, fa, b, fb, clip, maps, args.out_dir,
                                 overwrite=args.overwrite))
        n += len(render_trajectories(clip, ["A", "B", "C_off", "C_on"], args.out_dir,
                                     overwrite=args.overwrite))
    print(f"wrote {n} diagnostic images to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
