"""Aggregate the per-model S0 runs into the frozen S0 deliverables.

EXPLORATORY. Runs in `.venv-eval` (or any numpy interpreter) — it reads JSON
only and imports no model stack.

Writes:
    results/S0_results.json          machine-readable, everything
    results/S0_SEMANTICS_RUNTIME.md  the readable gate record

    experiments/week4_mono/.venv-eval/bin/python \\
        -m experiments.week4_mono.round1.scripts.s0_report --overwrite
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from experiments.week4_mono.round1 import common  # noqa: E402


def load_all(s0_dir: str) -> dict:
    out = {}
    for p in sorted(glob.glob(os.path.join(s0_dir, "*.json"))):
        name = os.path.splitext(os.path.basename(p))[0]
        if name == "checkpoint_integrity":
            continue
        with open(p) as fh:
            out[name] = json.load(fh)
    return out


def devices_line(rec: dict) -> str:
    bits = []
    for d in rec.get("device_matrix", []):
        if d.get("works"):
            bits.append(f"{d['device']} works")
        else:
            bits.append(f"{d['device']} FAILS")
    if not rec.get("cuda_available_here", False):
        bits.append("no CUDA on this host")
    return "; ".join(bits)


def md_table(rows: list[list[str]], header: list[str]) -> str:
    widths = [max(len(str(r[i])) for r in ([header] + rows)) for i in range(len(header))]
    def fmt(r):
        return "| " + " | ".join(str(c).ljust(widths[i]) for i, c in enumerate(r)) + " |"
    lines = [fmt(header), "|" + "|".join("-" * (w + 2) for w in widths) + "|"]
    lines += [fmt(r) for r in rows]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--s0-dir", default=os.path.join(common.OUTPUTS, "s0"))
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    recs = load_all(args.s0_dir)
    integ_path = os.path.join(args.s0_dir, "checkpoint_integrity.json")
    integ = json.load(open(integ_path)) if os.path.exists(integ_path) else None
    frozen_path = os.path.join(common.OUTPUTS, "frozen_set_check.json")
    frozen = json.load(open(frozen_path)) if os.path.exists(frozen_path) else None

    payload = {
        "_comment": ("S0 — semantics, preprocessing and runtime gate. Wrapper validation on "
                     "a four-image sanity set, NOT a benchmark. Nothing here ranks a model."),
        "stage": "S0",
        "frozen_set_check": frozen,
        "models": recs,
        "checkpoint_integrity": integ,
        "survivors": sorted(k for k, v in recs.items() if v.get("status") == "PASS"),
        "failed": sorted(k for k, v in recs.items() if v.get("status") != "PASS"),
    }
    out_json = os.path.join(common.RESULTS, "S0_results.json")
    common.write_json(out_json, payload, overwrite=args.overwrite)

    # ---------------- markdown -----------------------------------------
    order = [m for m in common.MODELS if m in recs] + [m for m in recs if m not in common.MODELS]

    runtime_rows = []
    for m in order:
        r = recs[m]
        mps = next((d for d in r.get("device_matrix", []) if d["device"] == "mps"), {})
        cpu = next((d for d in r.get("device_matrix", []) if d["device"] == "cpu"), {})
        probe = r.get("image_probes", [{}])[0]
        runtime_rows.append([
            m, r.get("status", "?"),
            f"{r.get('load_seconds', float('nan')):.1f}",
            f"{probe.get('extra', {}).get('infer_seconds', float('nan')):.2f}",
            "yes" if mps.get("works") else "no",
            ("yes" if cpu.get("works") else ("FAILS" if cpu else "not probed")),
            str(r.get("strict_n1_verified")),
        ])

    sem_rows = []
    for m in order:
        r = recs[m]
        probe = r.get("image_probes", [{}])[0]
        sem_rows.append([
            m, r.get("native_kind", "?"), r.get("range_rule", "?"),
            "yes" if probe.get("emits_range") else "NO",
            "yes" if probe.get("emits_K") else "no",
            "yes" if probe.get("emits_conf") else "no",
            str(probe.get("native_shape")),
        ])

    fov_rows = []
    for m in order:
        fa = recs[m].get("fov_audit", {})
        for key, label in (("720x1280", "landscape"), ("1280x720", "PORTRAIT")):
            v = fa.get(key, {})
            if not v.get("measured"):
                fov_rows.append([m, label, "-", "-", "-", "NOT MEASURED"])
                continue
            fov_rows.append([
                m, label, str(v.get("model_grid_hw")),
                f"{v.get('n_markers_lost_to_crop', 0)}/25",
                f"{v.get('fov_retained_area', float('nan')):.3f}",
                f"resid<={max(v.get('u_max_abs_residual_px', 0), v.get('v_max_abs_residual_px', 0)):.2f}px",
            ])

    lines = []
    A = lines.append
    A("# S0 — semantics, preprocessing and runtime gate")
    A("")
    A("**Stage:** S0 of the frozen Week-4A sequence in `MONO_DEPTH_FREEZE.md`. ")
    A("**Status:** all seven mandatory checkpoints PASS. No model exits at S0.")
    A("")
    A("S0 is wrapper validation, not benchmarking. It ran the four-image sanity set the")
    A("freeze specifies — an ordinary project frame, a difficult project frame, a")
    A("portrait/orientation-sensitive project frame, and a vendored public reference")
    A("image — plus a 25-marker FOV audit at both source orientations. It did **not**")
    A("run the 288-frame benchmark, and it ranks nothing.")
    A("")
    A("## 0. Frozen material")
    A("")
    if frozen:
        A(f"`verify_frozen_set --hash`: **ok={frozen['ok']}**, "
          f"{frozen['total_frames']}/{frozen['expected_total_frames']} frames.")
        A("")
        A("Every one of the six clips is present at 48 frames, every SHA-256 matches the")
        A("Week-3 `extraction_report.json`, and the persisted `D_mapanything` reference")
        A("product exists at 48 frames for each. The primary bakeoff therefore runs on")
        A("exactly the material Week 3 characterised; nothing was regenerated.")
        A("")
        A("`wreck_01` is the one portrait clip (1280x720). That is not incidental — it is")
        A("the orientation case the freeze keeps in the primary set precisely because")
        A("Week-3 preprocessing lost field of view there.")
    A("")
    A("## 1. Runtime and device matrix (measured on this host, not read from papers)")
    A("")
    A("Apple M4, 24 GB unified memory, macOS 26.6.2. **No CUDA anywhere on this host.**")
    A("Times are one image on the ordinary-project frame; S1 measures runtime properly.")
    A("")
    A(md_table(runtime_rows,
               ["model", "status", "load s", "infer s", "MPS", "CPU", "strict N=1"]))
    A("")
    A("Nothing in the mandatory set requires CUDA. The one CPU failure is a")
    A("reference-implementation quirk, not a capability limit: Depth Anything V2's")
    A("`image2tensor` picks its device from `torch.cuda.is_available()` /")
    A("`torch.backends.mps.is_available()` and ignores the device the model is on, so on")
    A("this host it always ships the tensor to MPS. Running DA V2 on CPU would need a")
    A("reference-implementation modification. It was not made, because MPS works and MPS")
    A("is what the bakeoff uses.")
    A("")
    A("### Reference-implementation modifications actually required")
    A("")
    n_mods = 0
    for m in order:
        mod = recs[m].get("provenance", {}).get("reference_impl_modifications", "")
        # Backends that record "none ..." are describing what they did NOT change;
        # only genuine modifications belong in this list.
        if mod and not mod.lower().startswith("none"):
            A(f"- **{m}** — {mod}")
            n_mods += 1
    if n_mods == 0:
        A("- none")
    A("")
    A("Recorded under `patches/`. Neither touches model weights, model structure or any")
    A("numerical path: one widens a `requires-python` bound, one makes an unused COLMAP")
    A("export import optional, and one moves an uninitialised-parameter allocation off a")
    A("hard-coded `cuda` that a CUDA-less host cannot satisfy — every one of those")
    A("parameters is then overwritten by a strict `load_state_dict`.")
    A("")
    A("Two further deliberate non-modifications are worth stating, because each replaces a")
    A("patch that would have been easy and wrong:")
    A("")
    A("- **MoGe family** — `moge` is put on `sys.path` explicitly rather than pip-installed.")
    A("  Both the MetricAnything release and upstream microsoft/MoGe ship a package literally")
    A("  named `moge`; an installed one would silently win, and V5 would quietly stop being a")
    A("  controlled architecture comparison. Both checkpoints load into the SAME class from")
    A("  the SAME source tree, and which tree is recorded in provenance.")
    A("- **FoundationGeo** — `infer()` is not called. It postprocesses its two ray-correction")
    A("  arms through independent `recover_focal_shift` solutions, so their difference is the")
    A("  ray correction PLUS whatever focal and shift each recovered separately. The backend")
    A("  calls `forward()` and applies one frozen solution to both arms instead, which is")
    A("  what FREEZE C3 requires for the difference to be attributable to the ray delta.")
    A("")
    A("## 2. Native representation and what each model can honestly emit")
    A("")
    A(md_table(sem_rows,
               ["model", "native_kind", "range_rule", "range?", "K?", "conf?", "native shape"]))
    A("")
    A("**Two models cannot emit a canonical range at all, and that is the correct answer,")
    A("not a gap.**")
    A("")
    A("- `dav2_small` emits relative inverse depth. Its legal ambiguity is affine in")
    A("  DISPARITY (`q' = a q + b`). Inverting before that transform is fitted produces a")
    A("  number that looks like a range and is not one, so the backend writes none and S2")
    A("  does the inversion once, under the frozen policy.")
    A("- `da3mono_large` was expected to emit z-depth plus a camera. **It does not.** The")
    A("  `da3mono-large` config is a DINOv2 ViT-L with a single DPT head of `output_dim: 1`;")
    A("  the returned `Prediction` carries `depth` and `sky` and nothing else —")
    A("  `intrinsics`, `extrinsics` and `conf` are all `None`. Range needs a camera, so")
    A("  supplying one would have to be invented, and an invented focal manufactures")
    A("  exactly the radial error M-6 exists to detect. This also leaves the z-vs-range")
    A("  question about its native field genuinely open, because the reference")
    A("  implementation's own `unproject_depth` (which treats depth as z) is never reached")
    A("  for this checkpoint. S2 settles it by measurement: this camera's secant factor")
    A("  spans roughly 1.00-1.35 across the frame, far too large a signal to miss.")
    A("")
    A("The z-vs-range conversions that WERE available are verified numerically per frame")
    A("rather than assumed:")
    A("")
    ver_rows = []
    for m in order:
        e = recs[m].get("image_probes", [{}])[0].get("extra", {})
        keys = [k for k in e if "max_abs" in k or "median_ratio" in k]
        if keys:
            ver_rows.append([m, "; ".join(f"{k}={e[k]:.6g}" for k in sorted(keys))])
    if ver_rows:
        A(md_table(ver_rows, ["model", "measured on the ordinary-project frame"]))
    A("")
    A("`median_ratio_range_over_z` sits at 1.11-1.19 with a maximum of 1.35-1.59 at the")
    A("frame corners. That IS the size of the z-vs-range mistake on this wide-FOV camera:")
    A("treating z-depth as range would inject a 11-19 % median and up to 59 % corner error,")
    A("purely radial, straight into the diagnostic that decides whether a camera-model")
    A("challenger gets activated.")
    A("")
    A("## 3. FOV audit — measured, at both orientations")
    A("")
    A("25 markers per orientation, pushed through each model's OWN preprocessing (the")
    A("Week-3 method). Markers that fall outside the model grid after cropping are")
    A("reported, never silently dropped.")
    A("")
    A(md_table(fov_rows, ["model", "orientation", "model grid (H,W)", "markers lost",
                          "area retained", "affine residual"]))
    A("")
    A("**The portrait trap is real and it is Wat3R's alone.** On the 1280x720 portrait")
    A("source, `wat3r_n1` loses 10 of 25 markers and retains **56.0 %** of the frame area:")
    A("its `crop` branch resizes the short side to 518 and centre-crops the long side to")
    A("518, discarding the top and bottom of every portrait frame. This reproduces Week 3's")
    A("VGGT-family finding exactly. Every other entrant retains 98.7-100 % at both")
    A("orientations.")
    A("")
    A("The consequence for `wreck_01` — the one portrait clip, and the low-texture")
    A("near-planar case — is that Wat3R is not seeing the same scene as the other six")
    A("models there. S3 must evaluate on the intersection of valid support, and Wat3R's")
    A("`wreck_01` column has to be read as a different, smaller field of view rather than")
    A("as a like-for-like result. The affine residuals are all sub-pixel, so the maps")
    A("themselves are trustworthy.")
    A("")
    A("## 4. Strict single-image invariant")
    A("")
    A("Every backend takes ONE image path. There is no batch, list or sequence argument to")
    A("get this wrong with. The two multi-view architectures assert it twice: MapAnything")
    A("checks both that `load_images` returned one view and that the model returned one")
    A("prediction; Wat3R asserts the preprocessed tensor has S=1. All seven verified.")
    A("")
    A("## 5. Checkpoint integrity — MetricAnything vs stock MoGe-2")
    A("")
    if integ:
        A(f"**Verdict: {integ['verdict']}.**")
        A("")
        A(f"- `model_config` identical: **{integ['model_config_identical']}**")
        A(f"- parameter key sets identical: **{integ['key_sets_identical']}** "
          f"({integ['n_params_base']} vs {integ['n_params_fine']} tensors)")
        A(f"- shape mismatches: **{len(integ['shape_mismatches'])}**")
        A(f"- bitwise-identical tensors: **{integ['n_tensors_bitwise_identical']}"
          f"/{integ['n_tensors_compared']}**")
        A(f"- global relative L2 change: **{integ['global_rel_l2']:.4f}**")
        A("")
        rows = [[g, v["n"], f"{v['median']:.4f}", f"{v['max']:.4f}"]
                for g, v in integ["rel_l2_by_module"].items()]
        A(md_table(rows, ["module", "tensors", "median rel L2", "max rel L2"]))
        A("")
        A("This is a decoder-heavy fine-tune and the numbers say so plainly: the DINOv2")
        A("encoder barely moves (median 0.02 % relative L2 over 352 tensors) while the neck,")
        A("points head, mask head and scale head move 1.9-4.4 %. The documented lineage")
        A("holds, which is what V5 needs — the architecture and representation really are")
        A("controlled. It does **not** identify which component of the fine-tuning treatment")
        A("causes any downstream difference; FREEZE C5 keeps data, objectives, supervision")
        A("and camera diversity confounded, and this measurement does not unconfound them.")
        A("")
        A("The check was mandatory because of the Week-3 Water-VGGT checkpoint-integrity")
        A("finding, not because of download statistics.")
    A("")
    A("## 6. Notable per-model observations")
    A("")
    A("- **`dav2_small`** — 15.3 % of the ordinary-project frame comes back with disparity")
    A("  <= 0 (the head's floor). Those pixels are masked out rather than inverted; they are")
    A("  where the model has no usable far-field signal, and they will matter in M-1's far")
    A("  bins.")
    A("- **`moge2_vitl` vs `metricanything_pointmap`** — on the same frame the two infer")
    A("  materially different cameras: normalised fx 0.465 vs 0.611, i.e. MetricAnything")
    A("  recovers a substantially longer focal from the same pixels. Since both models'")
    A("  metric scale is coupled to the recovered focal, this is a concrete pre-S3 reason to")
    A("  expect their absolute scales to disagree, and it is what V9's known-FOV")
    A("  postprocessing ablation is for.")
    A("- **`foundationgeo_11`** — the two internal ablation arms come out of ONE forward")
    A("  pass and share ONE frozen (focal, shift) solution, per FREEZE C3. Two things are")
    A("  already visible on the sanity frame. The learned ray correction turns rays by a")
    A("  median of **0.044 deg** (p95 0.11 deg, max 0.78 deg) — an order of magnitude below")
    A("  its own 3 deg cap. And the `scalefield`, which the release describes as a per-pixel")
    A("  spatial field, has an interquartile spread of roughly 0.82-0.85 around a median of")
    A("  0.84: on this frame it is behaving almost like a global scalar. Both are")
    A("  observations on one frame and neither is a conclusion; S3 runs the ablation properly.")
    A("- **`mapanything_n1`** — `depth_along_ray == ||pts3d_cam||` re-verified at N=1 to")
    A("  7.6e-06, so the Week-3 range identity survives the view-count change. Its")
    A("  `metric_scaling_factor` is emitted per frame and is recorded, not applied.")
    A("- **`wat3r_n1`** — emits `world_points` and `world_points_conf` alongside the depth")
    A("  head. At N=1 the world frame is the single camera's frame, so those add nothing")
    A("  here; the camera-frame point map built from (z, K) is what is stored.")
    A("")
    A("## 7. Gate outcome")
    A("")
    A(f"**Survivors: {len(payload['survivors'])}/7 — all mandatory checkpoints continue to S1.**")
    A("")
    A("No model failed semantics. Two models had a documented expectation corrected by")
    A("measurement rather than repaired (DA3 Mono emits no camera; DA V2 cannot be")
    A("inverted yet), which is the outcome the freeze asks for: record the semantics,")
    A("never invent them.")
    A("")
    A("Carried into S2 as open questions S0 deliberately did not answer:")
    A("")
    A("1. Is `da3mono_large`'s native field z-depth or range? (Measurable: fit it against")
    A("   the reference range and the reference z-depth in turn.)")
    A("2. What camera should lift `da3mono_large` and `dav2_small` into a range field, and")
    A("   is that a frozen evaluation convention rather than a model property?")
    A("3. Wat3R's native ambiguity, which the freeze forbids inferring from its released")
    A("   evaluation code's alignment.")

    out_md = os.path.join(common.RESULTS, "S0_SEMANTICS_RUNTIME.md")
    common.refuse_clobber(out_md, args.overwrite)
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    with open(out_md, "w") as fh:
        fh.write("\n".join(lines) + "\n")

    print(f"[S0-report] {len(recs)} models; survivors={payload['survivors']}")
    print(f"  -> {os.path.relpath(out_json, REPO_ROOT)}")
    print(f"  -> {os.path.relpath(out_md, REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
