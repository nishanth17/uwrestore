"""Which Phase 3A runs are missing, and why.

EXPLORATORY. Main project venv. Read-only.

Two batches share one 24 GB machine, so a run can be lost to memory pressure
without the driver script noticing (each step is `|| echo`, deliberately, so one
casualty does not abort the sweep). A missing result must never be mistaken for
a method failure, so this enumerates what SHOULD exist against what does, and
classifies each gap:

    ok              a complete result
    method_failure  the run finished and reported its own failure -- REAL evidence
    incomplete      a directory exists but no run.json/clip.json -- the process
                    died mid-stage; NOT evidence about the method
    absent          never started
    stale           produced before the `Mapper.multiple_models` fix, so its
                    registration number is an artefact of a single initial-pair
                    draw rather than a property of the configuration
"""

from __future__ import annotations

import argparse
import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
W3 = os.path.join(REPO_ROOT, "experiments", "week3_geometry")

CLASSICAL_EXPECTED = [(c, clip, 0) for c in ("A", "B", "C_off", "C_on")
                      for clip in ("wreck_07", "wreck_05", "cenote_01",
                                   "swimthrough_02", "wreck_01", "wreck_03")]
CLASSICAL_EXPECTED += [(c, clip, r) for c in ("C_off", "C_on") for clip in
                       ("wreck_07", "wreck_05") for r in (1, 2)]
CLASSICAL_EXPECTED += [("A", clip, 1) for clip in ("wreck_07", "wreck_05")]

DENSE_EXPECTED = [(c, clip) for c in ("D_mapanything", "E0_vggt", "E_wat3r_ren")
                  for clip in ("wreck_07", "wreck_05", "cenote_01",
                               "swimthrough_02", "wreck_01", "wreck_03")]
DENSE_EXPECTED += [(f"{c}_run1", "wreck_07") for c in
                   ("D_mapanything", "E0_vggt", "E_wat3r_ren")]


def classify_classical(cfg, clip, rep):
    d = os.path.join(W3, "outputs", "colmap", cfg, clip, f"run{rep}")
    j = os.path.join(d, "run.json")
    if os.path.exists(j):
        r = json.load(open(j))
        if r.get("failed_at"):
            # A stage that died on an EXTERNAL signal is not a method failure.
            # One batch was deliberately killed mid-flight when a configuration
            # error was found; those runs must be re-run, not reported as
            # evidence about the configuration.
            log = os.path.join(d, "stdout.log")
            if os.path.exists(log):
                tail = open(log, errors="ignore").read()[-8000:]
                if "SIGTERM" in tail or "SIGKILL" in tail:
                    return "incomplete", f"killed by external signal during {r['failed_at']}"
            return "method_failure", r["failed_at"]
        if "submodel_registered_images" not in r:
            # Written before multiple_models was restored to COLMAP's default;
            # its registration count is not comparable with the others.
            return "stale", f"pre-fix run, {r['result']['registered_images']}/48"
        return "ok", f"{r['result']['registered_images']}/48"
    return ("incomplete", "dir exists, no run.json") if os.path.isdir(d) else ("absent", "")


def classify_dense(cfg, clip):
    d = os.path.join(W3, "outputs", "range", cfg, clip)
    j = os.path.join(d, "clip.json")
    if os.path.exists(j):
        r = json.load(open(j))
        # A pose-convention check whose FALSIFICATION control scores the same as
        # the correct convention has not checked anything. That happens when the
        # check ran on a frame whose pose is the identity -- VGGT-family models
        # anchor their world frame to camera 0 -- so such a run is marked stale
        # and re-run rather than quietly counted as validated.
        checks = r.get("conventions", {}).get("pose_convention_check") or []
        for c in checks:
            good = c.get("relative_median_disagreement")
            bad = c.get("relative_median_disagreement_with_pose_INVERTED")
            if good is None or bad is None:
                continue
            if bad <= good * 2.0:
                return "stale", (f"degenerate pose check on frame {c.get('frame')} "
                                 f"(inverted {bad:.3f} vs correct {good:.3f})")
        return "ok", f"{r['n_frames']} frames"
    return ("incomplete", "dir exists, no clip.json") if os.path.isdir(d) else ("absent", "")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rerun-script", default=None,
                    help="write a shell script that re-runs everything not ok")
    args = ap.parse_args()

    lines, missing = [], []
    for cfg, clip, rep in CLASSICAL_EXPECTED:
        st, note = classify_classical(cfg, clip, rep)
        lines.append(f"{st:<15} classical {cfg:<9} {clip:<16} run{rep}  {note}")
        if st in ("incomplete", "absent", "stale"):
            missing.append(("classical", cfg, clip, rep))
    for cfg, clip in DENSE_EXPECTED:
        st, note = classify_dense(cfg, clip)
        lines.append(f"{st:<15} dense     {cfg:<16} {clip:<16}      {note}")
        if st in ("incomplete", "absent", "stale"):
            missing.append(("dense", cfg, clip, 0))
    for ln in sorted(lines):
        print(ln)
    n_ok = sum(1 for ln in lines if ln.startswith("ok"))
    print(f"\n{n_ok}/{len(lines)} complete; {len(missing)} need re-running "
          f"(method_failure entries are RESULTS, not gaps, and are not re-run)")

    if args.rerun_script and missing:
        with open(args.rerun_script, "w") as fh:
            fh.write("#!/bin/bash\n# Auto-generated: re-run only the runs lost to "
                     "process death, never a run that reported its own failure.\nset -u\n")
            for kind, cfg, clip, rep in missing:
                if kind == "classical":
                    fh.write(f".venv/bin/python -m experiments.week3_geometry.scripts."
                             f"run_colmap --config {cfg} --clip {clip} --repeat {rep} "
                             f"--overwrite || echo '  -> nonzero exit'\n")
                else:
                    base = cfg.replace("_run1", "")
                    rp = " --repeat 1" if cfg.endswith("_run1") else ""
                    if base == "D_mapanything":
                        fh.write(f"experiments/week3_geometry/.venv-mapanything/bin/python "
                                 f"-m experiments.week3_geometry.scripts.run_mapanything "
                                 f"--clip {clip}{rp} --overwrite || echo '  -> nonzero exit'\n")
                    else:
                        model = "vggt" if base == "E0_vggt" else "wat3r_ren"
                        fh.write(f"experiments/week3_geometry/.venv-vggt/bin/python "
                                 f"-m experiments.week3_geometry.scripts.run_vggt_family "
                                 f"--model {model} --clip {clip}{rp} --overwrite "
                                 f"|| echo '  -> nonzero exit'\n")
        os.chmod(args.rerun_script, 0o755)
        print(f"wrote {args.rerun_script}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
